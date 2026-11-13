import numpy as np
import pytest
import soundfile as sf

from singer_extractor.audio import crop_audio, overlap_add, read_audio, resample_exact


@pytest.mark.parametrize("length", [1, 79, 100, 101, 179, 180, 181, 499])
def test_chunking_preserves_every_sample_and_boundary(length):
    source = np.random.default_rng(7).normal(size=length).astype(np.float32)
    source[0], source[-1] = 1.0, -1.0
    result = overlap_add(source, lambda chunk: chunk.copy(), 100, 20)
    assert result.shape == source.shape
    np.testing.assert_allclose(result, source, atol=3e-7)


def test_resampling_round_trip_has_exact_requested_length():
    source = np.sin(np.arange(44101) * 2 * np.pi * 220 / 44100).astype(np.float32)
    small = resample_exact(source, 44100, 16000)
    restored = resample_exact(small, 16000, 44100, length=len(source))
    assert len(restored) == len(source)
    assert np.sqrt(np.mean((restored[100:-100] - source[100:-100]) ** 2)) < 0.003


def test_stereo_and_unicode_path(tmp_path):
    path = tmp_path / "中文 路径.wav"
    stereo = np.column_stack((np.ones(800), np.zeros(800))).astype(np.float32)
    sf.write(path, stereo, 8000, subtype="FLOAT")
    audio, rate = read_audio(path)
    assert rate == 8000
    np.testing.assert_allclose(audio, 0.5)


@pytest.mark.parametrize("start,duration", [(-1, 3), (0, -1), (9, 1), (float("nan"), 1)])
def test_invalid_crop_is_rejected(start, duration):
    with pytest.raises(ValueError):
        crop_audio(np.zeros(8000), 8000, start, duration)


def test_nonfinite_model_output_is_rejected():
    with pytest.raises(RuntimeError):
        overlap_add(np.zeros(100), lambda x: x + np.nan, 100, 20)
