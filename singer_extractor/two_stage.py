"""Stereo vocal removal followed by two-stream UNMIXX separation.

The upstream network bodies and checkpoints are pinned and loaded at runtime.
Candidate numbers are stream labels, not verified singer identities.
"""

import ast
import gc
import importlib.util
import sys
import time
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .audio import resample_exact
from .engine import choose_device
from .two_stage_assets import prepare_assets


def module_from_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_unmixx(directory, device):
    import yaml

    class BaseModel(nn.Module):
        def __init__(self, sample_rate, in_chan=1):
            super().__init__()
            self._sample_rate, self._in_chan = sample_rate, in_chan

    def pad_x_to_y(x, y):
        if x.shape[-1] != y.shape[-1]:
            raise ValueError("UNMIXX 输出长度不符。")
        return x

    base = Path(directory) / "unmixx/look2hear/models"
    namespace = {
        "__name__": "jinjin_unmixx",
        "BaseModel": BaseModel,
        "pad_x_to_y": pad_x_to_y,
        "activations": module_from_file("jinjin_activations", base / "layers/activations.py"),
        "normalizations": module_from_file(
            "jinjin_normalizations", base / "layers/normalizations.py"
        ),
    }
    tree = ast.parse((base / "unmixx_model.py").read_text("utf8"))
    excluded = {"base_model", "look2hear.models.layers", "asteroid.utils.torch_utils"}
    tree.body = [
        node
        for node in tree.body
        if not (isinstance(node, ast.ImportFrom) and node.module in excluded)
    ]
    exec(compile(tree, str(base / "unmixx_model.py"), "exec"), namespace)
    config = yaml.safe_load((Path(directory) / "unmixx/ckpt/conf.yml").read_text("utf8"))
    model = namespace["UNMIXX"](sample_rate=24000, **config["audionet"]["audionet_config"])
    state = torch.load(
        Path(directory) / "unmixx/ckpt/best.ckpt", map_location="cpu", weights_only=True
    )
    state = state.get("state_dict", state)
    model.load_state_dict(
        {key.removeprefix("audio_model."): value for key, value in state.items()}, strict=True
    )
    return model.eval().requires_grad_(False).to(device)


def load_roformer(directory, device):
    import yaml

    base = Path(directory) / "roformer"
    attend = module_from_file("jinjin_roformer_attend", base / "models/mel_band_roformer/attend.py")
    path = base / "models/mel_band_roformer/mel_band_roformer.py"
    tree = ast.parse(path.read_text("utf8"))
    # Only replace the absolute import, avoiding pollution of the generic 'models' package.
    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.ImportFrom) and node.module == "models.mel_band_roformer.attend"
        )
    ]
    namespace = {"__name__": "jinjin_roformer", "Attend": attend.Attend}
    exec(compile(tree, str(path), "exec"), namespace)

    class ConfigLoader(yaml.SafeLoader):
        pass

    ConfigLoader.add_constructor(
        "tag:yaml.org,2002:python/tuple",
        lambda loader, node: tuple(loader.construct_sequence(node)),
    )
    config = yaml.load(
        (base / "configs/config_vocals_mel_band_roformer.yaml").read_text("utf8"),
        Loader=ConfigLoader,
    )
    model = namespace["MelBandRoformer"](**config["model"])
    state = torch.load(
        Path(directory) / "MelBandRoformer.ckpt", map_location="cpu", weights_only=True
    )
    model.load_state_dict(state, strict=True)
    return model.eval().requires_grad_(False).to(device)


@torch.inference_mode()
def isolate_vocals(model, audio, progress):
    """Author's 8s/50% overlap windowing, with CPU accumulation and validation."""
    device = next(model.parameters()).device
    chunk, step = 352800, 176400
    fade = chunk // 10
    mix = torch.from_numpy(np.ascontiguousarray(audio))
    padded = mix.shape[-1] > 2 * step
    if padded:
        mix = nn.functional.pad(mix, (step, step), mode="reflect")
    length = mix.shape[-1]
    result = torch.zeros((2, length), dtype=torch.float32)
    counter = torch.zeros(length, dtype=torch.float32)
    base_window = torch.ones(chunk)
    base_window[:fade] *= torch.linspace(0, 1, fade)
    base_window[-fade:] *= torch.linspace(1, 0, fade)
    for start in range(0, length, step):
        progress(start / length, "阶段 1/2：分离伴奏与混合人声")
        part = mix[:, start : start + chunk]
        count = part.shape[-1]
        if count < chunk:
            mode = "reflect" if count > chunk // 2 + 1 else "constant"
            part = nn.functional.pad(part, (0, chunk - count), mode=mode)
        autocast = (
            torch.autocast("cuda", dtype=torch.float16) if device.type == "cuda" else nullcontext()
        )
        with autocast:
            predicted = model(part.unsqueeze(0).to(device))[0].float().cpu()
        if predicted.shape != (2, chunk) or not torch.isfinite(predicted).all():
            raise ValueError("RoFormer 模型输出长度或数值无效。")
        window = base_window.clone()
        if start == 0:
            window[:fade] = 1
        elif start + chunk >= length:
            window[-fade:] = 1
        result[:, start : start + count] += predicted[:, :count] * window[:count]
        counter[start : start + count] += window[:count]
    if torch.any(counter <= 0):
        raise ValueError("人声重建存在空缺。")
    output = (result / counter).numpy()
    return output[:, step:-step] if padded else output


@torch.inference_mode()
def unmixx_forward(model, audio):
    tensor = (
        torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
        .view(1, 1, -1)
        .to(next(model.parameters()).device)
    )
    output = model(tensor, istest=True)[0]
    if output.shape != (1, 2, len(audio)) or not torch.isfinite(output).all():
        raise ValueError("UNMIXX 模型输出长度或数值无效。")
    return output[0].float().cpu().numpy()


def separate_chunks(model, audio, progress, chunk_seconds=60, overlap_seconds=30):
    chunk, overlap = round(chunk_seconds * 24000), round(overlap_seconds * 24000)
    if not 0 < overlap < chunk:
        raise ValueError("重叠长度必须小于分段长度。")
    result = np.zeros((2, len(audio)), np.float32)
    weight = np.zeros(len(audio), np.float32)
    logs = []
    for start in range(0, len(audio), chunk - overlap):
        progress(start / len(audio), "阶段 2/2：分离两条候选人声")
        end = min(start + chunk, len(audio))
        # Short previews still need enough STFT context; remove padding before returning.
        wave = audio[start:end]
        padded = np.pad(wave, (0, max(0, 24000 - len(wave))))
        predicted = unmixx_forward(model, padded)[:, : len(wave)]
        swapped, margin = False, None
        if start:
            count = min(overlap, len(wave))
            previous = result[:, start : start + count] / weight[None, start : start + count]
            direct = float(np.mean((previous - predicted[:, :count]) ** 2))
            reverse = float(np.mean((previous - predicted[::-1, :count]) ** 2))
            margin = abs(direct - reverse) / max(direct + reverse, 1e-20)
            if reverse < direct:
                predicted = predicted[::-1].copy()
                swapped = True
        window = np.ones(len(wave), np.float32)
        fade = min(overlap, len(wave))
        if start:
            window[:fade] *= np.linspace(0, 1, fade + 2, dtype=np.float32)[1:-1]
        if end < len(audio):
            window[-fade:] *= np.linspace(1, 0, fade + 2, dtype=np.float32)[1:-1]
        result[:, start:end] += predicted * window
        weight[start:end] += window
        logs.append(
            {
                "start_seconds": start / 24000,
                "swapped": swapped,
                "overlap_assignment_margin": margin,
            }
        )
        if end == len(audio):
            break
    return result / weight[None], logs


class TwoStageExtractor:
    def __init__(self, model_dir=None, device="auto"):
        self.model_dir = model_dir
        self.device = choose_device(device)

    def extract(self, stereo, rate, progress=lambda value, message: None):
        directory = prepare_assets(self.model_dir, lambda v, m: progress(v * 0.05, m))
        stereo = np.asarray(stereo, dtype=np.float32)
        if stereo.ndim != 2 or stereo.shape[1] not in (1, 2) or not np.isfinite(stereo).all():
            raise ValueError("需要有效的单声道或立体声音频。")
        audio = np.stack(
            [resample_exact(stereo[:, channel], rate, 44100) for channel in range(stereo.shape[1])]
        )
        if audio.shape[0] == 1:
            audio = np.repeat(audio, 2, axis=0)
        began = time.perf_counter()
        model = None
        try:
            progress(0.05, "加载 Mel-Band RoFormer…")
            model = load_roformer(directory, self.device)
            vocals = isolate_vocals(model, audio, lambda v, m: progress(0.10 + 0.50 * v, m))
            del model
            model = None
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()
            stage_one = time.perf_counter() - began
            progress(0.60, "加载 UNMIXX…")
            model = load_unmixx(directory, self.device)
            mono = resample_exact(vocals.mean(axis=0), 44100, 24000)
            candidates, alignment = separate_chunks(
                model, mono, lambda v, m: progress(0.65 + 0.30 * v, m)
            )
            result = np.stack(
                [resample_exact(track, 24000, rate, length=len(stereo)) for track in candidates]
            )
            progress(0.98, "正在整理候选轨，完成后请试听选择")
            return result, {
                "pipeline": "mel-band-roformer+unmixx",
                "native_sample_rate": 24000,
                "chunk_seconds": 60,
                "overlap_seconds": 30,
                "alignment": alignment,
                "stage1_seconds": round(stage_one, 3),
                "identity_verified": False,
            }
        except torch.cuda.OutOfMemoryError as exc:
            raise ValueError(
                "GPU 显存不足。请关闭占用显卡的软件，或选择较短片段 / CPU 重试。"
            ) from exc
        finally:
            del model
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()
