"""Timeline projects, bounded inference jobs, reversible edits and aligned exports."""

import json
import math
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from . import __version__
from .audio import read_audio
from .engine import Extractor
from .weights import manifest

MAX_SECONDS = 3600
PEAK_BINS = 4096


def sample_range(start, end, rate, length):
    if not all(math.isfinite(value) for value in (start, end)):
        raise ValueError("时间必须是有效数字。")
    if start < 0 or end <= start or end > length / rate + 1 / rate:
        raise ValueError("请选择音频范围内有效的起点和终点。")
    begin, finish = round(start * rate), min(length, round(end * rate))
    if begin >= finish:
        raise ValueError("选区太短。")
    return begin, finish


def merge_ranges(ranges):
    result = []
    for begin, end in sorted(ranges):
        if result and begin <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((begin, end))
    return result


def covered(ranges, begin, end):
    return any(left <= begin and right >= end for left, right in merge_ranges(ranges))


def waveform(audio, bins=PEAK_BINS):
    """Min/max envelope retains short transients, unlike stride downsampling."""
    bins = min(bins, len(audio))
    boundaries = np.linspace(0, len(audio), bins + 1, dtype=np.int64)
    lows = np.minimum.reduceat(audio, boundaries[:-1])
    highs = np.maximum.reduceat(audio, boundaries[:-1])
    return np.stack((lows, highs), axis=1).round(6).tolist()


@dataclass
class Project:
    id: str
    directory: Path
    name: str
    audio: np.ndarray
    rate: int
    demo: bool = False
    target: np.ndarray = field(init=False)
    coverage: list = field(default_factory=list)
    history: list = field(default_factory=list)
    edits: list = field(default_factory=list)
    reference: np.ndarray | None = None
    reference_rate: int = 0
    reference_name: str = ""
    revision: int = 0
    busy: str | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    envelopes: dict = field(default_factory=dict)

    def __post_init__(self):
        self.target = np.zeros_like(self.audio)
        self.envelopes["original"] = waveform(self.audio)
        sf.write(self.directory / "original.wav", self.audio, self.rate, subtype="FLOAT")
        self.refresh_media()

    def refresh_media(self):
        residual = self.audio - self.target
        for name, audio in (("target", self.target), ("residual", residual)):
            sf.write(
                self.directory / f"{name}-{self.revision}.wav",
                audio,
                self.rate,
                subtype="FLOAT",
            )
            self.envelopes[name] = waveform(audio)

    def require_idle(self):
        if self.busy:
            raise ValueError("这个项目正在处理，请等待完成或先取消任务。")

    def snapshot(self):
        with self.lock:
            return {
                "id": self.id,
                "name": self.name,
                "demo": self.demo,
                "duration": len(self.audio) / self.rate,
                "sample_rate": self.rate,
                "samples": len(self.audio),
                "revision": self.revision,
                "busy": self.busy,
                "coverage": [[a / self.rate, b / self.rate] for a, b in self.coverage],
                "complete": covered(self.coverage, 0, len(self.audio)),
                "undo_available": bool(self.history),
                "waveforms": self.envelopes,
                "playback_peak": max(
                    1.0,
                    float(np.abs(self.audio).max()),
                    float(np.abs(self.target).max()),
                    float(np.abs(self.audio - self.target).max()),
                ),
                "reference": None
                if self.reference is None
                else {
                    "name": self.reference_name,
                    "duration": len(self.reference) / self.reference_rate,
                    "waveform": waveform(self.reference),
                },
                "audio": {
                    "original": f"/api/projects/{self.id}/audio/original",
                    "target": f"/api/projects/{self.id}/audio/target?revision={self.revision}",
                    "residual": f"/api/projects/{self.id}/audio/residual?revision={self.revision}",
                    "reference": f"/api/projects/{self.id}/audio/reference?revision={self.revision}",
                },
            }

    def replace(self, begin, end, values, action):
        if values.shape != (end - begin,) or not np.isfinite(values).all():
            raise ValueError("模型输出长度或数值无效，没有修改结果。")
        before = self.target[begin:end].copy()
        self.history.append((begin, end, before, self.coverage.copy()))
        while len(self.history) > 10 or (
            len(self.history) > 1 and sum(item[2].nbytes for item in self.history) > 64 * 1024**2
        ):
            self.history.pop(0)
        # Five-millisecond crossfades stay INSIDE the selection; outside samples never change.
        weight = np.ones(len(values), dtype=np.float32)
        fade = min(round(0.005 * self.rate), len(values) // 2)
        if fade and begin > 0:
            weight[:fade] = np.linspace(0, 1, fade, dtype=np.float32)
        if fade and end < len(self.audio):
            weight[-fade:] = np.linspace(1, 0, fade, dtype=np.float32)
        self.target[begin:end] = before * (1 - weight) + values * weight
        self.coverage = merge_ranges([*self.coverage, (begin, end)])
        self.revision += 1
        self.edits.append(
            {
                **action,
                "start_seconds": begin / self.rate,
                "end_seconds": end / self.rate,
                "revision": self.revision,
            }
        )
        self.refresh_media()

    def mute(self, start, end):
        with self.lock:
            self.require_idle()
            begin, finish = sample_range(start, end, self.rate, len(self.audio))
            self.replace(begin, finish, np.zeros(finish - begin, np.float32), {"action": "mute"})

    def undo(self):
        with self.lock:
            self.require_idle()
            if not self.history:
                raise ValueError("没有可以撤销的操作。")
            begin, end, before, coverage = self.history.pop()
            self.target[begin:end] = before
            self.coverage = coverage
            self.revision += 1
            self.edits.append({"action": "undo", "revision": self.revision})
            self.refresh_media()


class Workspace:
    def __init__(self, cache_dir, output_dir, extractor_factory=Extractor):
        self.cache_dir, self.output_dir = Path(cache_dir), Path(output_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.projects, self.jobs, self.exports = {}, {}, {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="singer-inference")
        self.extractor_factory = extractor_factory
        self.engine = None
        self.engine_device = None
        self.lock = threading.RLock()

    def project(self, project_id):
        with self.lock:
            if project_id not in self.projects:
                raise ValueError("项目不存在或服务已重启，请重新导入歌曲。")
            return self.projects[project_id]

    def add(self, path, name, demo=False):
        audio, rate = read_audio(path)
        if len(audio) < 3 * rate:
            raise ValueError("歌曲至少需要 3 秒，才能选择歌手参考。")
        if len(audio) / rate > MAX_SECONDS:
            raise ValueError("第一版时间线暂支持最长 60 分钟的音频。")
        with self.lock:
            if len(self.projects) >= 3:
                old = next((key for key, value in self.projects.items() if not value.busy), None)
                if old is None:
                    raise ValueError("已有三个项目正在处理，请等待任务完成。")
                del self.projects[old]
            key = uuid.uuid4().hex
            directory = self.cache_dir / key
            directory.mkdir()
            project = Project(key, directory, name, audio, rate, demo=demo)
            self.projects[key] = project
            return project

    def set_reference(self, project_id, path, name):
        project = self.project(project_id)
        audio, rate = read_audio(path)
        if len(audio) < 3 * rate or len(audio) / rate > MAX_SECONDS:
            raise ValueError("参考音频需要至少 3 秒，且不超过 60 分钟。")
        with project.lock:
            project.require_idle()
            project.reference, project.reference_rate = audio, rate
            project.reference_name = name
            sf.write(project.directory / "reference.wav", audio, rate, subtype="FLOAT")
            project.revision += 1
            project.refresh_media()
        return project

    def submit(self, project_id, options):
        project = self.project(project_id)
        with project.lock:
            project.require_idle()
            start = 0.0 if options["whole"] else options["start"]
            end = len(project.audio) / project.rate if options["whole"] else options["end"]
            begin, finish = sample_range(start, end, project.rate, len(project.audio))
            use_external = options["reference_source"] == "reference"
            if use_external and project.reference is None:
                raise ValueError("请先导入单独的参考音频。")
            reference = project.reference if use_external else project.audio
            ref_rate = project.reference_rate if use_external else project.rate
            ref_start = options["reference_start"]
            ref_begin, ref_end = sample_range(ref_start, ref_start + 3, ref_rate, len(reference))
            reference = reference[ref_begin:ref_end].copy()
            if float(np.abs(reference).max()) < 1e-6:
                raise ValueError("这 3 秒接近静音，请重新选择目标歌手参考。")
            job_id = uuid.uuid4().hex
            job = {
                "id": job_id,
                "project_id": project_id,
                "status": "queued",
                "progress": 0.0,
                "message": "等待处理",
                "cancelled": False,
                "start": begin / project.rate,
                "end": finish / project.rate,
            }
            self.jobs[job_id] = job
            project.busy = job_id
        self.executor.submit(self._run, project, job, begin, finish, reference, ref_rate, options)
        return self.job(job_id)

    def _run(self, project, job, begin, end, reference, ref_rate, options):
        began = time.perf_counter()
        try:
            job.update(status="running", message="正在加载模型")
            if job["cancelled"]:
                raise InterruptedError
            if self.engine is None or self.engine_device != options["device"]:
                self.engine = self.extractor_factory(device=options["device"])
                self.engine_device = options["device"]

            def progress(value, message):
                if job["cancelled"]:
                    raise InterruptedError
                job.update(progress=float(value), message=message)

            result = self.engine.extract(
                project.audio[begin:end],
                project.rate,
                reference,
                ref_rate,
                options["embedding_rate"],
                progress=progress,
            )
            with project.lock:
                if job["cancelled"]:
                    raise InterruptedError
                project.replace(
                    begin,
                    end,
                    result,
                    {
                        "action": "extract",
                        "device": self.engine.device,
                        "reference_source": options["reference_source"],
                        "reference_start_seconds": options["reference_start"],
                        "embedding_sample_rate": options["embedding_rate"],
                        "elapsed_seconds": round(time.perf_counter() - began, 3),
                    },
                )
            job.update(status="completed", progress=1.0, message="处理完成")
        except InterruptedError:
            job.update(status="cancelled", message="已取消，之前的结果保持不变")
        except Exception as exc:
            job.update(status="failed", message=str(exc))
        finally:
            with project.lock:
                project.busy = None

    def job(self, job_id):
        if job_id not in self.jobs:
            raise ValueError("找不到任务。")
        return {key: value for key, value in self.jobs[job_id].items() if key != "cancelled"}

    def cancel(self, job_id):
        self.job(job_id)
        job = self.jobs[job_id]
        if job["status"] in ("queued", "running"):
            job["cancelled"] = True
            job["message"] = "正在取消，将在当前分段结束后停止"
        return self.job(job_id)

    def export(self, project_id, start, end, whole):
        project = self.project(project_id)
        with project.lock:
            project.require_idle()
            begin, finish = (
                (0, len(project.audio))
                if whole
                else sample_range(start, end, project.rate, len(project.audio))
            )
            if not covered(project.coverage, begin, finish):
                raise ValueError("导出范围仍有未处理的片段。请先提取或明确标记静音。")
            key = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
            directory = self.output_dir / key
            directory.mkdir(parents=True)
            original = project.audio[begin:finish]
            target = project.target[begin:finish]
            for name, values in (("target", target), ("residual", original - target)):
                sf.write(directory / f"{name}.wav", values, project.rate, subtype="FLOAT")
            config = manifest()
            report = {
                "version": __version__,
                "model": config["variant"],
                "sample_rate": project.rate,
                "channels": 1,
                "samples": finish - begin,
                "start_seconds": begin / project.rate,
                "duration_seconds": (finish - begin) / project.rate,
                "whole_song": whole,
                "demo_signal": project.demo,
                "quality_evaluated": False,
                "target_peak": float(np.abs(target).max()),
                "edits": project.edits.copy(),
                "boundary_fade_seconds": 0.005,
                "model_hashes": {item["name"]: item["sha256"] for item in config["files"]},
                "note": "残差包含伴奏、其他歌手与分离误差；单声道浮点 WAV，不做自动响度归一化。",
            }
            (directory / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            with zipfile.ZipFile(directory / "stems.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                for name in ("target.wav", "residual.wav", "report.json"):
                    archive.write(directory / name, name)
            self.exports[key] = directory
            return {
                "id": key,
                "start": begin / project.rate,
                "duration": (finish - begin) / project.rate,
                "files": {
                    name: f"/api/exports/{key}/{name}"
                    for name in ("target.wav", "residual.wav", "report.json", "stems.zip")
                },
            }

    def close(self):
        for job in self.jobs.values():
            job["cancelled"] = True
        self.executor.shutdown(wait=True, cancel_futures=True)
