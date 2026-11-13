import json

import numpy as np
import pytest
import soundfile as sf
import torch

from singer_extractor.engine import Extractor, choose_device, run_job
from singer_extractor.weights import ROOT, manifest, verify_weights


def test_missing_model_is_actionable(tmp_path):
    with pytest.raises(ValueError, match="download_models.bat"):
        verify_weights(tmp_path)


def test_modified_checkpoint_is_rejected(tmp_path):
    (tmp_path / "embedding.pth").write_bytes(b"incorrect checkpoint")
    with pytest.raises(ValueError, match="校验失败"):
        verify_weights(tmp_path)


def test_invalid_device_is_rejected():
    with pytest.raises(ValueError):
        choose_device("imaginary")


def test_ui_can_be_constructed_without_weights_or_network(tmp_path):
    from singer_extractor.ui import build_app

    app = build_app(tmp_path / "cache", tmp_path / "exports")
    assert app.title == "Singer Extractor · 目标歌手提取"
    app.state.workspace.close()


def test_export_alignment_residual_and_private_paths(tmp_path):
    class Passthrough:
        config = manifest()
        device = "cpu"

        def extract(self, mixture, rate, reference, reference_rate, embedding_rate, progress):
            assert embedding_rate == 44100
            return mixture * 0.25

    rate = 8000
    mixture = np.random.default_rng(8).uniform(-0.2, 0.2, 5 * rate + 3).astype(np.float32)
    path = tmp_path / "private-song-name.wav"
    sf.write(path, mixture, rate, subtype="FLOAT")
    paths, report_path, report = run_job(
        Passthrough(), path, start=0.5, duration=3.1, output_dir=tmp_path / "exports"
    )
    target, sr = sf.read(paths["target"])
    residual, _ = sf.read(paths["residual"])
    original, _ = sf.read(paths["original"])
    assert len(target) == round(3.1 * rate)
    assert sr == rate
    assert report["start_seconds"] == 0.5
    np.testing.assert_allclose(target + residual, original, atol=2e-8)
    assert str(tmp_path) not in report_path.read_text(encoding="utf-8")
    assert path.name not in report_path.read_text(encoding="utf-8")
    assert json.loads(report_path.read_text(encoding="utf-8"))["quality_evaluated"] is False
    assert report["embedding_sample_rate"] == 44100


@pytest.fixture(scope="module")
def real_engine():
    if not (ROOT / "models" / "film.pth").exists():
        pytest.skip("Official checkpoints have not been downloaded")
    return Extractor(device="auto")


@pytest.mark.integration
def test_real_checkpoint_conditioning_changes_output(real_engine):
    rate = 16000
    t = np.arange(3 * rate, dtype=np.float32) / rate
    # Synthetic signals only verify conditioning, never perceptual singing quality.
    ref_a = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    ref_b = (0.3 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
    a = real_engine.reference_embedding(ref_a, rate)
    b = real_engine.reference_embedding(ref_b, rate)
    assert not torch.allclose(a, b)
    mix = np.random.default_rng(5).normal(0, 0.05, 44100).astype(np.float32)
    out_a = real_engine.predict_chunk(mix, a)
    out_b = real_engine.predict_chunk(mix, b)
    assert np.isfinite(out_a).all() and out_a.shape == mix.shape
    assert np.max(np.abs(out_a - out_b)) > 1e-5


@pytest.mark.integration
def test_silent_and_short_references_are_rejected(real_engine):
    with pytest.raises(ValueError, match="静音"):
        real_engine.reference_embedding(np.zeros(48000, dtype=np.float32), 16000)
    with pytest.raises(ValueError, match="3 秒"):
        real_engine.reference_embedding(np.ones(16000, dtype=np.float32), 16000)


@pytest.mark.integration
def test_real_inference_restores_nonstandard_input_length(real_engine):
    rate = 48000
    t = np.arange(3 * rate + 137, dtype=np.float32) / rate
    source = (0.15 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
    result = real_engine.extract(source, rate, source[: 3 * rate], rate)
    assert result.shape == source.shape
    assert np.isfinite(result).all()
