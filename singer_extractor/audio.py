"""Audio validation, exact-length resampling and overlap-add reconstruction."""

import math
from pathlib import Path
from collections.abc import Callable

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def read_audio(path: str | Path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("找不到音频文件，请重新选择。")
    try:
        audio, rate = sf.read(path, dtype="float32", always_2d=True)
    except (RuntimeError, sf.LibsndfileError) as exc:
        raise ValueError(
            "无法读取音频。第一版支持 WAV、FLAC、MP3、OGG；请将其他格式转为 WAV。"
        ) from exc
    if audio.size == 0 or rate <= 0:
        raise ValueError("音频为空。")
    if not np.isfinite(audio).all():
        raise ValueError("音频包含无效数值。")
    if audio.shape[1] > 2:
        raise ValueError("第一版只接受单声道或立体声音频。")
    return audio.mean(axis=1, dtype=np.float32), int(rate)


def crop_audio(audio, rate, start=0.0, duration=None):
    if not math.isfinite(start) or start < 0:
        raise ValueError("起始时间必须是大于等于 0 的秒数。")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("片段时长必须大于 0。")
    begin = round(start * rate)
    if begin >= len(audio):
        raise ValueError("起始时间超过了音频长度。")
    end = len(audio) if duration is None else min(len(audio), begin + round(duration * rate))
    if end <= begin:
        raise ValueError("选中的片段过短。")
    return np.ascontiguousarray(audio[begin:end]), begin


def resample_exact(audio, source_rate, target_rate, length=None):
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError("采样率必须大于 0。")
    if source_rate == target_rate:
        result = np.asarray(audio, dtype=np.float32)
    else:
        divisor = math.gcd(source_rate, target_rate)
        result = resample_poly(audio, target_rate // divisor, source_rate // divisor)
    expected = round(len(audio) * target_rate / source_rate) if length is None else length
    return np.pad(result[:expected], (0, max(0, expected - len(result)))).astype(np.float32)


def overlap_add(
    audio: np.ndarray,
    predict: Callable,
    chunk_samples: int,
    overlap_samples: int,
    progress: Callable | None = None,
):
    """Bound GPU input size; normalize crossfades without shifting or dropping samples."""
    if len(audio) == 0:
        raise ValueError("音频为空。")
    if not 0 <= overlap_samples < chunk_samples:
        raise ValueError("重叠长度必须小于分段长度。")
    output = np.zeros(len(audio), dtype=np.float32)
    weights = np.zeros(len(audio), dtype=np.float32)
    step = chunk_samples - overlap_samples
    for begin in range(0, len(audio), step):
        end = min(len(audio), begin + chunk_samples)
        valid = end - begin
        chunk = np.pad(audio[begin:end], (0, chunk_samples - valid))
        predicted = np.asarray(predict(chunk), dtype=np.float32)
        if predicted.shape != chunk.shape or not np.isfinite(predicted).all():
            raise RuntimeError("模型返回的音频长度或数值无效。")
        window = np.ones(valid, dtype=np.float32)
        fade = min(overlap_samples, valid)
        if fade and begin > 0:
            window[:fade] *= np.linspace(0, 1, fade + 2, dtype=np.float32)[1:-1]
        if fade and end < len(audio):
            window[-fade:] *= np.linspace(1, 0, fade + 2, dtype=np.float32)[1:-1]
        output[begin:end] += predicted[:valid] * window
        weights[begin:end] += window
        if progress is not None:
            progress(end / len(audio), "正在提取目标歌手")
        if end == len(audio):
            break
    return output / weights
