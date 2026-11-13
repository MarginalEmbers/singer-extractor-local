import io
import json
import zipfile

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from singer_extractor.server import build_app
from singer_extractor.two_stage import separate_chunks
from singer_extractor.two_stage_assets import prepare_assets
from singer_extractor.weights import sha256
from test_timeline import finish, options, wav_bytes


class FakeTwoStage:
    def __init__(self, device):
        self.device = device

    def extract(self, stereo, rate, progress):
        assert stereo.ndim == 2
        progress(0.5, "dual")
        mono = stereo.mean(axis=1)
        return np.stack((mono * 0.2, mono * 0.6)), {"pipeline": "fake", "identity_verified": False}


def test_dual_candidates_require_selection_and_support_local_switch_undo(tmp_path):
    app = build_app(tmp_path / "cache", tmp_path / "export", two_stage_factory=FakeTwoStage)
    with TestClient(app, headers={"X-Singer-Client": "timeline"}) as client:
        project = client.post("/api/projects", files={"file": ("song.wav", wav_bytes())}).json()
        prefix = "/api/projects/" + project["id"]
        # No solo reference is required, even if the legacy reference would be out of bounds.
        job = client.post(prefix + "/extract", json={"whole": True, "reference_start": 999}).json()
        assert finish(app.state.workspace, job)["status"] == "completed"
        project = client.get(prefix).json()
        assert project["candidate_range"] == [0, project["duration"]]
        assert not project["complete"] and not project["undo_available"]
        assert client.post(prefix + "/export", json={"whole": True}).status_code == 400
        wav = client.get(project["audio"]["candidate2"]).content
        assert sf.info(io.BytesIO(wav)).frames == project["samples"]
        assert client.get(prefix + "/audio/candidate1?revision=999").status_code == 404
        assert client.post(prefix + "/choose", json={"candidate": 3}).status_code == 422
        assert client.post(prefix + "/choose", json={"candidate": 1, "whole": True}).json()[
            "complete"
        ]
        actual = app.state.workspace.project(project["id"])
        first = actual.target.copy()
        client.post(
            prefix + "/choose", json={"candidate": 2, "start": 1, "end": 2}
        ).raise_for_status()
        np.testing.assert_array_equal(actual.target[:8000], first[:8000])
        np.testing.assert_array_equal(actual.target[16000:], first[16000:])
        np.testing.assert_allclose(actual.target[8050:15950], actual.audio[8050:15950] * 0.6)
        client.post(prefix + "/undo").raise_for_status()
        np.testing.assert_array_equal(actual.target, first)
        result = client.post(prefix + "/export", json={"whole": True}).json()
        report = client.get(result["files"]["report.json"]).json()
        assert report["edits"][0]["candidate"] == 1
        assert not report["candidate_identity_verified"]
        # New preview candidates replace the candidate bank, leaving the edited target intact.
        job = client.post(prefix + "/extract", json={"start": 2, "end": 4}).json()
        assert finish(app.state.workspace, job)["status"] == "completed"
        np.testing.assert_array_equal(actual.target, first)
        assert (
            client.post(prefix + "/choose", json={"candidate": 2, "whole": True}).status_code == 400
        )


def test_invalid_dual_result_preserves_prior_candidates_and_target(tmp_path):
    from singer_extractor.workspace import Workspace

    space = Workspace(tmp_path / "cache", tmp_path / "export", two_stage_factory=FakeTwoStage)
    path = tmp_path / "song.wav"
    path.write_bytes(wav_bytes())
    project = space.add(path, "song")
    try:
        assert (
            finish(space, space.submit(project.id, options(mode="two-stage")))["status"]
            == "completed"
        )
        before = project.candidates.copy()

        class Invalid(FakeTwoStage):
            def extract(self, *args):
                return np.full((2, 1), np.nan), {}

        space.two_stage_factory = Invalid
        assert (
            finish(space, space.submit(project.id, options(mode="two-stage")))["status"] == "failed"
        )
        np.testing.assert_array_equal(project.candidates, before)
        assert project.candidate_revision == 1 and not project.target.any()
    finally:
        space.close()


def test_assets_repair_modified_extracted_code_and_reject_corrupt_archive(tmp_path, monkeypatch):
    archive = tmp_path / "model.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("p/network.py", "original implementation")
        out.writestr("p/private-example.wav", "must not extract")
    manifest = {
        "downloads": [
            {
                "file": "model.zip",
                "bytes": archive.stat().st_size,
                "sha256": sha256(archive),
                "prefix": "p",
                "members": {"network.py": "vendor/network.py"},
            }
        ]
    }
    monkeypatch.setattr("singer_extractor.two_stage_assets.model_manifest", lambda: manifest)
    prepare_assets(tmp_path, download=False)
    model = tmp_path / "vendor/network.py"
    assert model.read_text() == "original implementation"
    model.write_text("modified")
    prepare_assets(tmp_path, download=False)
    assert model.read_text() == "original implementation"
    assert not list(tmp_path.rglob("*.wav"))
    archive.write_bytes(b"bad archive")
    with pytest.raises(ValueError, match="校验失败"):
        prepare_assets(tmp_path, download=False)


def test_overlap_matching_corrects_stream_permutation_without_losing_samples(monkeypatch):
    calls = []

    def predict(model, wave):
        result = np.stack((wave * 0.25, wave * 0.75))
        calls.append(len(wave))
        return result[::-1].copy() if len(calls) % 2 == 0 else result

    monkeypatch.setattr("singer_extractor.two_stage.unmixx_forward", predict)
    audio = np.random.default_rng(42).normal(size=7 * 24000 + 17).astype(np.float32)
    output, report = separate_chunks(None, audio, lambda value, message: None, 4, 2)
    np.testing.assert_allclose(output[0], audio * 0.25, atol=1e-6)
    np.testing.assert_allclose(output[1], audio * 0.75, atol=1e-6)
    assert report[1]["swapped"] and output.shape == (2, len(audio))
    assert len(calls) == 3
    json.dumps(report)
