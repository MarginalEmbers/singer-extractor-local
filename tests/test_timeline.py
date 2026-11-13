import io
import json
import threading
import time
import zipfile

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from singer_extractor.server import build_app
from singer_extractor.workspace import Workspace, sample_range, waveform


class FakeExtractor:
    def __init__(self, device):
        self.device = device

    def extract(self, audio, rate, reference, ref_rate, embedding_rate, progress):
        assert len(reference) == ref_rate * 3
        progress(0.5, "test")
        return audio * 0.25


def wav_bytes(rate=8000, seconds=6, silence=False):
    t = np.arange(rate * seconds + 7, dtype=np.float32) / rate
    data = np.zeros_like(t) if silence else 0.1 * np.sin(2 * np.pi * 220 * t)
    stream = io.BytesIO()
    sf.write(stream, data, rate, format="WAV", subtype="FLOAT")
    return stream.getvalue()


@pytest.fixture
def workspace(tmp_path):
    space = Workspace(tmp_path / "cache", tmp_path / "exports", FakeExtractor)
    path = tmp_path / "私密歌曲 测试.wav"
    path.write_bytes(wav_bytes())
    space.add(path, path.name)
    yield space
    space.close()


def finish(space, job):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = space.job(job["id"])
        if current["status"] not in {"queued", "running"}:
            # Wait for the finally block that releases the project lock.
            if space.project(job["project_id"]).busy is None:
                return current
        time.sleep(0.01)
    pytest.fail("Job did not finish")


def options(**overrides):
    return {
        "start": 1,
        "end": 4,
        "whole": False,
        "reference_start": 0,
        "reference_source": "song",
        "device": "cpu",
        "embedding_rate": 16000,
        **overrides,
    }


def test_waveform_keeps_single_sample_transient():
    data = np.zeros(10003, dtype=np.float32)
    data[67], data[-1] = 0.9, -0.8
    peaks = np.asarray(waveform(data, 31))
    assert peaks.shape == (31, 2)
    assert peaks[:, 1].max() == pytest.approx(0.9)
    assert peaks[:, 0].min() == pytest.approx(-0.8)


@pytest.mark.parametrize("start,end", [(-1, 1), (1, 1), (0, 7), (0, float("nan"))])
def test_invalid_timeline_bounds(start, end):
    with pytest.raises(ValueError):
        sample_range(start, end, 8000, 48007)


def test_partial_redo_preserves_outside_and_undo_restores_coverage(workspace):
    project = next(iter(workspace.projects.values()))
    assert finish(workspace, workspace.submit(project.id, options()))["status"] == "completed"
    before = project.target.copy()
    assert not before[:8000].any() and not before[32000:].any()
    np.testing.assert_allclose(before[8040:31960], project.audio[8040:31960] * 0.25)
    with pytest.raises(ValueError, match="未处理"):
        workspace.export(project.id, 0, 6, True)
    project.mute(2, 3)
    np.testing.assert_array_equal(project.target[:16000], before[:16000])
    np.testing.assert_array_equal(project.target[24000:], before[24000:])
    assert not project.target[16040:23960].any()
    project.undo()
    np.testing.assert_array_equal(project.target, before)
    assert project.coverage == [(8000, 32000)]
    project.undo()
    assert project.coverage == [] and not project.target.any()


def test_full_export_exact_length_residual_report_and_zip(workspace):
    project = next(iter(workspace.projects.values()))
    assert (
        finish(workspace, workspace.submit(project.id, options(whole=True)))["status"]
        == "completed"
    )
    result = workspace.export(project.id, 0, 1, True)
    directory = workspace.exports[result["id"]]
    target, rate = sf.read(directory / "target.wav")
    residual, _ = sf.read(directory / "residual.wav")
    assert rate == project.rate and len(target) == len(project.audio)
    np.testing.assert_allclose(target + residual, project.audio, atol=1e-8)
    report_text = (directory / "report.json").read_text(encoding="utf-8")
    assert project.name not in report_text and str(directory.parent) not in report_text
    assert json.loads(report_text)["quality_evaluated"] is False
    with zipfile.ZipFile(directory / "stems.zip") as archive:
        assert set(archive.namelist()) == {"target.wav", "residual.wav", "report.json"}
    partial = workspace.export(project.id, 1, 2.2, False)
    info = sf.info(workspace.exports[partial["id"]] / "target.wav")
    assert info.frames == 9600 and partial["start"] == 1


def test_cancel_and_busy_guard_leave_previous_result_untouched(workspace):
    entered, release = threading.Event(), threading.Event()

    class Slow(FakeExtractor):
        def extract(self, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().extract(*args, **kwargs)

    workspace.extractor_factory = Slow
    project = next(iter(workspace.projects.values()))
    job = workspace.submit(project.id, options())
    try:
        assert entered.wait(5)
        with pytest.raises(ValueError, match="正在处理"):
            project.mute(1, 2)
        with pytest.raises(ValueError, match="正在处理"):
            workspace.submit(project.id, options())
        workspace.cancel(job["id"])
    finally:
        release.set()
    assert finish(workspace, job)["status"] == "cancelled"
    assert not project.target.any() and project.coverage == [] and not project.history


def test_failed_model_output_does_not_modify_project(workspace):
    class Invalid(FakeExtractor):
        def extract(self, *args, **kwargs):
            return np.full(1, np.nan, dtype=np.float32)

    workspace.extractor_factory = Invalid
    project = next(iter(workspace.projects.values()))
    job = finish(workspace, workspace.submit(project.id, options()))
    assert job["status"] == "failed" and "无效" in job["message"]
    assert not project.target.any() and not project.history and project.busy is None


def test_external_reference_and_silent_reference_validation(workspace, tmp_path):
    project = next(iter(workspace.projects.values()))
    with pytest.raises(ValueError, match="先导入"):
        workspace.submit(project.id, options(reference_source="reference"))
    reference = tmp_path / "reference.wav"
    reference.write_bytes(wav_bytes(rate=16000, seconds=3))
    workspace.set_reference(project.id, reference, reference.name)
    job = workspace.submit(project.id, options(reference_source="reference"))
    assert finish(workspace, job)["status"] == "completed"
    reference.write_bytes(wav_bytes(silence=True))
    workspace.set_reference(project.id, reference, reference.name)
    with pytest.raises(ValueError, match="静音"):
        workspace.submit(project.id, options(reference_source="reference"))


@pytest.fixture
def client(tmp_path):
    app = build_app(tmp_path / "cache", tmp_path / "exports", FakeExtractor)
    with TestClient(app, headers={"X-Singer-Client": "timeline"}) as result:
        yield result


def test_http_upload_extract_edit_export_workflow(client):
    response = client.post(
        "/api/projects", files={"file": ("中文 路径.wav", wav_bytes(), "audio/wav")}
    )
    assert response.status_code == 200
    project = response.json()
    prefix = "/api/projects/" + project["id"]
    assert project["name"] == "中文 路径.wav" and not project["complete"]
    assert client.post(prefix + "/export", json={"whole": True}).status_code == 400
    job = client.post(prefix + "/extract", json=options(whole=True)).json()
    assert finish(client.app.state.workspace, job)["status"] == "completed"
    project = client.get(prefix).json()
    assert project["complete"]
    response = client.get(project["audio"]["target"])
    assert (
        response.status_code == 200
        and sf.info(io.BytesIO(response.content)).frames == project["samples"]
    )
    assert client.get(prefix + "/audio/target?revision=999").status_code == 404
    assert client.post(prefix + "/mute", json={"start": 1, "end": 2}).json()["undo_available"]
    assert client.post(prefix + "/undo").json()["complete"]
    exported = client.post(prefix + "/export", json={"whole": True}).json()
    archive = client.get(exported["files"]["stems.zip"])
    assert archive.status_code == 200
    assert zipfile.is_zipfile(io.BytesIO(archive.content))
    assert client.get("/api/exports/" + exported["id"] + "/arbitrary.txt").status_code == 404


def test_http_local_origin_validation_and_upload_errors(client):
    assert client.post("/api/projects/demo", headers={"X-Singer-Client": ""}).status_code == 403
    assert (
        client.post("/api/projects/demo", headers={"Origin": "https://example.org"}).status_code
        == 403
    )
    assert client.get("/", headers={"Host": "example.org"}).status_code == 403
    assert client.post("/api/projects", files={"file": ("bad.wav", b"garbage")}).status_code == 400
    assert client.post("/api/projects", files={"file": ("bad.txt", wav_bytes())}).status_code == 400
    demo = client.post("/api/projects/demo").json()
    assert demo["demo"] and not demo["complete"]
    prefix = "/api/projects/" + demo["id"]
    assert client.post(prefix + "/extract", json={"device": "imaginary"}).status_code == 422
    assert client.post(prefix + "/extract", json={"reference_start": 100}).status_code == 400
    assert client.get("/").headers["content-security-policy"].startswith("default-src 'self'")
    assert client.get("/assets/app.js").status_code == 200
    assert "javascript" in client.get("/assets/timeline.mjs").headers["content-type"]
