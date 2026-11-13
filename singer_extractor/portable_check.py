"""Exercise the actual frozen HTTP/model/export stack without a development Python."""

import io
import json
import sys
import time
import traceback
import zipfile
from pathlib import Path

from . import __version__
from .desktop_backend import APP_NAME, DesktopBackend


def diagnose_bundle(directory, report_path, download=False):
    import numpy as np
    import requests
    import soundfile as sf
    import torch
    from PySide6 import __version__ as qt_version
    from PySide6.QtWebEngineCore import QWebEngineProfile

    report = {
        "application": APP_NAME,
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version,
        "qt": qt_version,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_architectures": torch.cuda.get_arch_list(),
        "web_engine_available": QWebEngineProfile is not None,
        "quality_evaluated": False,
    }
    backend = DesktopBackend(directory)
    try:
        url = backend.start(download=download)
        session = requests.Session()
        session.trust_env = False
        session.headers["X-Singer-Client"] = "timeline"

        def call(path, body=None):
            response = (
                session.get(url + path, timeout=60)
                if body is None
                else session.post(url + path, json=body, timeout=60)
            )
            response.raise_for_status()
            return response.json()

        report["health"] = call("/api/health")
        project = call("/api/projects/demo", {})
        prefix = "/api/projects/" + project["id"]
        job = call(
            prefix + "/extract",
            {
                "whole": True,
                "reference_start": 0,
                "device": "cuda" if torch.cuda.is_available() else "cpu",
            },
        )
        deadline = time.monotonic() + 300
        while job["status"] in {"queued", "running"}:
            if time.monotonic() > deadline:
                raise TimeoutError("Frozen inference took too long")
            time.sleep(0.1)
            job = call("/api/jobs/" + job["id"])
        assert job["status"] == "completed", job
        candidates = call(prefix)
        assert candidates["candidate_range"] and not candidates["complete"]
        call(prefix + "/choose", {"whole": True, "candidate": 1})
        exported = call(prefix + "/export", {"whole": True})
        archive = session.get(url + exported["files"]["stems.zip"], timeout=60)
        archive.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
            target, rate = sf.read(io.BytesIO(package.read("target.wav")))
            residual, _ = sf.read(io.BytesIO(package.read("residual.wav")))
            report["export"] = json.loads(package.read("report.json"))
        original = session.get(url + project["audio"]["original"], timeout=60)
        original.raise_for_status()
        source, _ = sf.read(io.BytesIO(original.content))
        if source.ndim == 2:
            source = source.mean(axis=1)
        assert len(target) == project["samples"] and rate == project["sample_rate"]
        assert np.isfinite(target).all()
        error = float(np.abs(target + residual - source).max())
        assert error < 1e-7
        report.update(ok=True, samples=len(target), sample_rate=rate, residual_max_error=error)
    except Exception:
        report.update(ok=False, error=traceback.format_exc())
    finally:
        backend.stop()
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    if not report["ok"]:
        raise SystemExit(1)
