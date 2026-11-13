"""Single-singer inference and exports, without model downloads or network calls."""

import json
import time
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from .audio import crop_audio, overlap_add, read_audio, resample_exact
from .models import SingerEmbedding, SingerFiLM
from .weights import ROOT, manifest, verify_weights


def choose_device(requested="auto"):
    if requested not in ("auto", "cuda", "cpu"):
        raise ValueError("设备选项必须是 auto、cuda 或 cpu。")
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("未检测到可用 CUDA。请检查 NVIDIA 驱动与 PyTorch 安装，或选择 CPU。")
    return "cuda" if requested != "cpu" and torch.cuda.is_available() else "cpu"


class Extractor:
    def __init__(self, model_dir=None, device="auto"):
        self.model_dir = Path(model_dir or ROOT / "models")
        verify_weights(self.model_dir)
        self.device = choose_device(device)
        self.config = manifest()
        self.sample_rate = int(self.config["sample_rate"])
        self.encoder = SingerEmbedding()
        self.separator = SingerFiLM()
        for model, filename in ((self.encoder, "embedding.pth"), (self.separator, "film.pth")):
            state = torch.load(self.model_dir / filename, map_location="cpu", weights_only=True)
            model.load_state_dict(state, strict=True)
            model.eval().requires_grad_(False).to(self.device)
        self.window = torch.hann_window(self.config["n_fft"], device=self.device)

    @torch.inference_mode()
    def reference_embedding(self, reference, sample_rate, embedding_rate=16000):
        if embedding_rate not in (16000, 44100):
            raise ValueError("参考采样率必须是 16000 或 44100。")
        waveform = resample_exact(reference, sample_rate, embedding_rate)
        required = 3 * embedding_rate
        if len(waveform) < required:
            raise ValueError("参考片段至少需要完整 3 秒，且只有目标歌手在唱。")
        # Fixed, repeatable 3-second reference, matching the training duration.
        waveform = waveform[:required]
        peak = float(np.max(np.abs(waveform)))
        if peak < 1e-6:
            raise ValueError("参考片段接近静音，请选择目标歌手清晰演唱的 3 秒。")
        tensor = torch.from_numpy(waveform / peak).unsqueeze(0).to(self.device)
        return self.encoder(tensor)

    @torch.inference_mode()
    def predict_chunk(self, chunk, embedding):
        waveform = torch.from_numpy(chunk).unsqueeze(0).to(self.device)
        spectrum = torch.stft(
            waveform,
            self.config["n_fft"],
            self.config["hop_length"],
            window=self.window,
            center=True,
            return_complex=True,
        )
        predicted = self.separator(spectrum.abs().unsqueeze(1), embedding).squeeze(1)
        reconstruction = torch.polar(predicted, spectrum.angle())
        audio = torch.istft(
            reconstruction,
            self.config["n_fft"],
            self.config["hop_length"],
            window=self.window,
            center=True,
            length=len(chunk),
        )
        return audio[0].cpu().numpy()

    def extract(
        self, mixture, rate, reference, reference_rate, embedding_rate=16000, progress=None
    ):
        embedding = self.reference_embedding(reference, reference_rate, embedding_rate)
        audio = resample_exact(mixture, rate, self.sample_rate)
        result = overlap_add(
            audio,
            lambda chunk: self.predict_chunk(chunk, embedding),
            chunk_samples=6 * self.sample_rate,
            overlap_samples=self.sample_rate,
            progress=progress,
        )
        return resample_exact(result, self.sample_rate, rate, length=len(mixture))


def run_job(
    extractor,
    song,
    reference_file=None,
    reference_start=0.0,
    start=0.0,
    duration=None,
    output_dir=None,
    embedding_rate=16000,
    progress=None,
):
    began = time.perf_counter()
    song_audio, rate = read_audio(song)
    mixture, offset = crop_audio(song_audio, rate, float(start), duration)
    if reference_file:
        reference_audio, reference_rate = read_audio(reference_file)
    else:
        reference_audio, reference_rate = song_audio, rate
    reference, _ = crop_audio(reference_audio, reference_rate, float(reference_start), 3.0)
    target = extractor.extract(mixture, rate, reference, reference_rate, embedding_rate, progress)
    if not np.isfinite(target).all():
        raise RuntimeError("输出含无效数值，未导出音频。")
    root = Path(output_dir or ROOT / "outputs")
    directory = root / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    # Float WAV preserves amplitude without clipping or per-chunk normalization.
    paths = {key: directory / f"{key}.wav" for key in ("target", "original", "residual")}
    for name, data in (("target", target), ("original", mixture), ("residual", mixture - target)):
        sf.write(paths[name], data, rate, subtype="FLOAT")
    report = {
        "version": "0.1.0",
        "model": extractor.config["variant"],
        "device": extractor.device,
        "torch": torch.__version__,
        "sample_rate": rate,
        "channels": 1,
        "samples": len(target),
        "start_seconds": offset / rate,
        "duration_seconds": len(target) / rate,
        "reference_start_seconds": reference_start,
        "reference_duration_seconds": 3.0,
        "embedding_sample_rate": embedding_rate,
        "chunk_seconds": 6,
        "overlap_seconds": 1,
        "elapsed_seconds": round(time.perf_counter() - began, 3),
        "target_peak": float(np.abs(target).max()),
        "quality_evaluated": False,
        "note": "残差 = 单声道原音 - 目标输出，包含伴奏、其他歌手和分离误差。",
        "model_hashes": {item["name"]: item["sha256"] for item in extractor.config["files"]},
    }
    report_path = directory / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths, report_path, report
