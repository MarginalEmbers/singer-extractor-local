"""Launch the offline timeline interface on the loopback address."""

import threading
import webbrowser

import uvicorn

from .server import build_app


def launch(inbrowser=True, port=7860):
    if inbrowser:
        timer = threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}"))
        timer.daemon = True
        timer.start()
    uvicorn.run(build_app(), host="127.0.0.1", port=port, log_level="warning")


__all__ = ["build_app", "launch"]
