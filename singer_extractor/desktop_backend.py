"""Portable paths and the lifetime of the desktop's private loopback service."""

import functools
import socket
import sys
import threading
import time
from pathlib import Path

APP_NAME = "哦，金金的音道分离"


def portable_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).resolve().parents[1] / ".cache" / "desktop-data"


class DesktopBackend:
    def __init__(self, directory, progress=lambda value, message: None):
        self.directory = Path(directory).resolve()
        self.progress = progress
        self.cancelled = threading.Event()
        self.server = None
        self.thread = None
        self.app = None
        self.socket = None
        self.url = None

    def report(self, value, message):
        if self.cancelled.is_set():
            raise InterruptedError("启动已取消。")
        self.progress(value, message)

    def start(self, download=True):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.report(0, "正在加载本机运行环境，首次启动可能需要一些时间…")
        import uvicorn

        from .engine import Extractor
        from .server import build_app
        from .weights import download_weights, verify_weights

        models = self.directory / "models"
        try:
            verify_weights(models)
        except ValueError:
            if not download:
                raise
            self.report(0, "首次启动：正在从作者公开地址下载约 29 MB 模型…")
            download_weights(models, self.report, quiet=True)
        self.report(1, "模型已就绪，正在打开时间线…")
        self.app = build_app(
            self.directory / "cache",
            self.directory / "outputs",
            functools.partial(Extractor, model_dir=models),
            model_dir=models,
        )
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(128)
        port = self.socket.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                host="127.0.0.1",
                port=port,
                loop="asyncio",
                http="h11",
                ws="none",
                log_config=None,
                access_log=False,
                lifespan="on",
            )
        )
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.socket]},
            daemon=True,
            name="desktop-local-service",
        )
        self.thread.start()
        deadline = time.monotonic() + 30
        while not self.server.started:
            self.report(1, "正在启动本机音频服务…")
            if not self.thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("本机音频服务启动失败，请查看 data/logs/desktop.log。")
            time.sleep(0.05)
        return self.url

    def stop(self):
        self.cancelled.set()
        if self.app:
            for job in self.app.state.workspace.jobs.values():
                job["cancelled"] = True
        if self.server:
            self.server.should_exit = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=30)
        if self.socket:
            self.socket.close()

    def has_edits(self):
        return self.app and any(
            project.revision or project.busy
            for project in self.app.state.workspace.projects.values()
        )
