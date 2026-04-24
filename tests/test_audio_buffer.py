import numpy as np
import pytest

sd = pytest.importorskip("sounddevice")
from transcrb.audio.capture import AudioCapture


def test_band_computation_shape():
    cap = AudioCapture(n_bands=10)
    chunk = np.sin(np.linspace(0, 20 * np.pi, 480)).astype(np.float32)
    bands = cap._compute_bands(chunk)
    assert bands.shape == (10,)
    assert bands.max() <= 1.0 + 1e-6
    assert bands.min() >= 0.0


def test_band_computation_on_short_chunk_pads():
    cap = AudioCapture(n_bands=8)
    chunk = np.zeros(100, dtype=np.float32)
    bands = cap._compute_bands(chunk)
    assert bands.shape == (8,)


def test_initial_state():
    cap = AudioCapture(max_duration_s=5, samplerate=16000)
    assert not cap.is_running()
    duration = cap.stop()
    assert duration == 0.0


def test_force_cut_at_max():
    collected: list[np.ndarray] = []
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=0.1,
        chunk_max_s=0.25,
        chunk_silence_s=0.05,
        chunk_silence_rms=0.01,
        on_chunk=lambda c: collected.append(c),
    )
    cap._callback(np.ones((4000, 1), dtype=np.float32), 4000, None, None)
    assert len(collected) == 1
    assert collected[0].shape == (4000,)
    assert np.all(collected[0] == 1.0)


def test_cuts_at_silence_not_mid_word():
    collected: list[np.ndarray] = []
    rng = np.random.RandomState(0)
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=0.1,
        chunk_max_s=2.0,
        chunk_silence_s=0.1,
        chunk_silence_rms=0.01,
        on_chunk=lambda c: collected.append(c),
    )
    speech = (rng.randn(2000) * 0.2).astype(np.float32)
    silence = np.zeros(2000, dtype=np.float32)
    audio = np.concatenate([speech, silence])[:, None]
    cap._callback(audio, len(audio), None, None)
    assert len(collected) >= 1
    first_len = len(collected[0])
    assert 2000 <= first_len <= 4000


def test_no_cut_below_min():
    collected: list[np.ndarray] = []
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=1.0,
        chunk_max_s=5.0,
        chunk_silence_s=0.1,
        chunk_silence_rms=0.01,
        on_chunk=lambda c: collected.append(c),
    )
    audio = np.zeros((8000, 1), dtype=np.float32)
    cap._callback(audio, 8000, None, None)
    assert len(collected) == 0


def test_stop_without_start_returns_early():
    collected: list[np.ndarray] = []
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=1.0,
        chunk_max_s=5.0,
        on_chunk=lambda c: collected.append(c),
    )
    cap._callback(np.full((800, 1), 0.5, dtype=np.float32), 800, None, None)
    assert len(collected) == 0
    cap.stop(emit_tail=True)
    assert len(collected) == 0
