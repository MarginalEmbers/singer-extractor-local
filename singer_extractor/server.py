"""Local-only HTTP interface for the timeline; no third-party assets or services."""

import mimetypes
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .engine import Extractor
from .two_stage import TwoStageExtractor
from .two_stage_assets import verify_assets
from .weights import ROOT
from .workspace import Workspace

WEB = Path(__file__).parent / "web"
MAX_UPLOAD = 500 * 1024**2
FORMATS = {".wav", ".flac", ".mp3", ".ogg"}


class Bounds(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    start: float = Field(default=0, ge=0)
    end: float = Field(default=1, gt=0)


class ExtractRequest(Bounds):
    mode: Literal["two-stage", "legacy"] = "two-stage"
    whole: bool = False
    reference_start: float = Field(default=0, ge=0)
    reference_source: Literal["song", "reference"] = "song"
    embedding_rate: Literal[16000, 44100] = 44100
    device: Literal["auto", "cuda", "cpu"] = "auto"


class ExportRequest(Bounds):
    whole: bool = False


class ChooseRequest(ExportRequest):
    candidate: Literal[1, 2]


def save_upload(file, directory):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in FORMATS:
        raise ValueError("请选择 WAV、FLAC、MP3 或 OGG 音频。")
    directory.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(suffix=suffix, dir=directory, delete=False)
    path = Path(temporary.name)
    size = 0
    try:
        with temporary:
            while block := file.file.read(1024**2):
                size += len(block)
                if size > MAX_UPLOAD:
                    raise ValueError("音频文件不能超过 500 MB。")
                temporary.write(block)
        if not size:
            raise ValueError("文件为空。")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def build_app(
    cache_dir=None,
    output_dir=None,
    extractor_factory=Extractor,
    model_dir=None,
    two_stage_factory=TwoStageExtractor,
):
    # Windows registry MIME mappings can otherwise serve ES modules as text/plain.
    mimetypes.add_type("application/javascript", ".mjs")
    mimetypes.add_type("application/javascript", ".js")
    workspace = Workspace(
        cache_dir or ROOT / ".cache" / "workspaces-v2",
        output_dir or ROOT / "outputs",
        extractor_factory,
        two_stage_factory,
    )

    @asynccontextmanager
    async def lifespan(app):
        yield
        workspace.close()

    app = FastAPI(
        title="Singer Extractor · 目标歌手提取",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.workspace = workspace

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "只允许本机访问。"}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.headers.get('host')}"
            if origin and origin != expected:
                return JSONResponse({"detail": "拒绝跨站请求。"}, status_code=403)
            if request.headers.get("x-singer-client") != "timeline":
                return JSONResponse({"detail": "缺少本地客户端标记。"}, status_code=403)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > MAX_UPLOAD + 1024**2
            except ValueError:
                return JSONResponse({"detail": "无效的请求长度。"}, status_code=400)
            if too_large:
                return JSONResponse({"detail": "音频文件不能超过 500 MB。"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; media-src 'self' blob:; img-src 'self' data:; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid_input(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")

    app.mount("/assets", StaticFiles(directory=WEB), name="assets")

    @app.get("/api/health")
    def health():
        try:
            verify_assets(Path(model_dir or ROOT / "models") / "two-stage")
            weights = "ready"
        except ValueError as exc:
            weights = str(exc)
        return {"version": __version__, "weights": weights}

    @app.post("/api/projects")
    def upload_song(file: Annotated[UploadFile, File()]):
        path = save_upload(file, workspace.cache_dir)
        try:
            name = (file.filename or "歌曲").replace("\\", "/").split("/")[-1]
            return workspace.add(path, name).snapshot()
        finally:
            path.unlink(missing_ok=True)
            file.file.close()

    @app.post("/api/projects/demo")
    def demo():
        rate = 24000
        t = np.arange(12 * rate + 17, dtype=np.float32) / rate
        signal = 0.08 * np.sin(2 * np.pi * (220 * t + np.sin(t)))
        signal += (t > 4) * 0.04 * np.sin(2 * np.pi * 440 * t)
        temporary = tempfile.NamedTemporaryFile(
            suffix=".wav", dir=workspace.cache_dir, delete=False
        )
        path = Path(temporary.name)
        temporary.close()
        try:
            sf.write(path, signal, rate, subtype="FLOAT")
            return workspace.add(path, "功能自检音频（合成音，非歌曲）", demo=True).snapshot()
        finally:
            path.unlink(missing_ok=True)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str):
        return workspace.project(project_id).snapshot()

    @app.post("/api/projects/{project_id}/reference")
    def reference(project_id: str, file: Annotated[UploadFile, File()]):
        path = save_upload(file, workspace.cache_dir)
        try:
            name = (file.filename or "参考音频").replace("\\", "/").split("/")[-1]
            return workspace.set_reference(project_id, path, name).snapshot()
        finally:
            path.unlink(missing_ok=True)
            file.file.close()

    @app.get("/api/projects/{project_id}/audio/{track}")
    def audio(project_id: str, track: str, revision: int | None = None):
        project = workspace.project(project_id)
        with project.lock:
            if track in ("original", "reference"):
                if track == "reference" and project.reference is None:
                    raise HTTPException(404, "没有单独的参考音频。")
                path = project.directory / f"{track}.wav"
            elif track in ("candidate1", "candidate2"):
                version = project.candidate_revision if revision is None else revision
                if project.candidates is None or not 1 <= version <= project.candidate_revision:
                    raise HTTPException(404, "找不到这个候选音轨版本。")
                path = project.directory / f"{track}-{version}.wav"
            elif track in ("target", "residual"):
                version = project.revision if revision is None else revision
                if not 0 <= version <= project.revision:
                    raise HTTPException(404, "找不到这个音频版本。")
                path = project.directory / f"{track}-{version}.wav"
            else:
                raise HTTPException(404, "找不到音轨。")
        if not path.exists():
            raise HTTPException(404, "音频文件已不可用，请重新导入。")
        return FileResponse(path, media_type="audio/wav")

    @app.post("/api/projects/{project_id}/extract")
    def extract(project_id: str, options: ExtractRequest):
        return workspace.submit(project_id, options.model_dump())

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return workspace.job(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        return workspace.cancel(job_id)

    @app.post("/api/projects/{project_id}/mute")
    def mute(project_id: str, bounds: Bounds):
        project = workspace.project(project_id)
        project.mute(bounds.start, bounds.end)
        return project.snapshot()

    @app.post("/api/projects/{project_id}/choose")
    def choose(project_id: str, options: ChooseRequest):
        project = workspace.project(project_id)
        project.choose_candidate(options.candidate, options.start, options.end, options.whole)
        return project.snapshot()

    @app.post("/api/projects/{project_id}/undo")
    def undo(project_id: str):
        project = workspace.project(project_id)
        project.undo()
        return project.snapshot()

    @app.post("/api/projects/{project_id}/export")
    def export(project_id: str, options: ExportRequest):
        return workspace.export(project_id, options.start, options.end, options.whole)

    @app.get("/api/exports/{export_id}/{filename}")
    def download(export_id: str, filename: str):
        if export_id not in workspace.exports or filename not in {
            "target.wav",
            "residual.wav",
            "report.json",
            "stems.zip",
        }:
            raise HTTPException(404, "找不到导出文件。")
        return FileResponse(workspace.exports[export_id] / filename, filename=filename)

    return app
