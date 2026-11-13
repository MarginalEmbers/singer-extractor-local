import hashlib
import sys

import pytest

from singer_extractor import weights
from singer_extractor.desktop_backend import DesktopBackend, portable_directory


def test_frozen_data_directory_follows_executable_not_current_directory(tmp_path, monkeypatch):
    executable = tmp_path / "中文 软件" / "哦，金金的音道分离.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert portable_directory() == executable.parent / "data"


def test_model_setup_reuses_verified_download_and_reports_completion(tmp_path, monkeypatch):
    import gdown

    content = b"test model"
    item = {"name": "model.pth", "sha256": hashlib.sha256(content).hexdigest(), "drive_id": "test"}
    monkeypatch.setattr(weights, "manifest", lambda: {"files": [item]})
    (tmp_path / "model.pth").write_bytes(content)
    monkeypatch.setattr(
        gdown, "download", lambda **kwargs: pytest.fail("Must reuse verified model")
    )
    progress = []
    weights.download_weights(tmp_path, lambda value, message: progress.append(value), quiet=True)
    assert progress == [0.0, 1.0]


def test_failed_model_download_preserves_previous_file(tmp_path, monkeypatch):
    import gdown

    item = {
        "name": "model.pth",
        "sha256": hashlib.sha256(b"correct").hexdigest(),
        "drive_id": "test",
    }
    monkeypatch.setattr(weights, "manifest", lambda: {"files": [item]})
    (tmp_path / "model.pth").write_bytes(b"old")

    def corrupt(**kwargs):
        from pathlib import Path

        Path(kwargs["output"]).write_bytes(b"corrupt")
        return kwargs["output"]

    monkeypatch.setattr(gdown, "download", corrupt)
    with pytest.raises(RuntimeError, match="校验失败"):
        weights.download_weights(tmp_path, quiet=True)
    assert (tmp_path / "model.pth").read_bytes() == b"old"
    assert not (tmp_path / "model.download").exists()


def test_cancelled_startup_never_opens_service(tmp_path):
    backend = DesktopBackend(tmp_path)
    backend.stop()
    with pytest.raises(InterruptedError):
        backend.start()
    assert backend.socket is None and backend.thread is None
