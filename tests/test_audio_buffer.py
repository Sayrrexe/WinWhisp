import threading
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

sd = pytest.importorskip("sounddevice")
from transcrb.audio.capture import AudioCapture


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _cap(**kw) -> AudioCapture:
    defaults = dict(
        samplerate=16000,
        chunk_min_s=0.1,
        chunk_max_s=0.25,
        chunk_silence_s=0.05,
        chunk_silence_rms=0.01,
    )
    defaults.update(kw)
    return AudioCapture(**defaults)


def _set_buf(cap: AudioCapture, data: np.ndarray) -> None:
    n = len(data)
    cap._chunk_buf[:n] = data
    cap._chunk_idx = n


# ---------------------------------------------------------------------------
# existing tests (preserved verbatim)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _find_silence_cut — prefix-sum invariant
# ---------------------------------------------------------------------------

def test_find_silence_cut_returns_none_below_min():
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05)
    short = np.zeros(10, dtype=np.float32)
    _set_buf(cap, short)
    assert cap._find_silence_cut(10) is None


def test_find_silence_cut_returns_none_all_speech():
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05)
    n = cap._min_samples + 200
    loud = np.full(n, 1.0, dtype=np.float32)
    _set_buf(cap, loud)
    assert cap._find_silence_cut(n) is None


def test_find_silence_cut_locates_trailing_silence():
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05, chunk_silence_rms=0.01)
    speech_len = cap._min_samples
    silence_len = cap._silence_samples * 2
    data = np.concatenate([
        np.full(speech_len, 1.0, dtype=np.float32),
        np.zeros(silence_len, dtype=np.float32),
    ])
    _set_buf(cap, data)
    n = len(data)
    cut = cap._find_silence_cut(n)
    assert cut is not None
    assert cap._min_samples <= cut <= n


def test_find_silence_cut_result_within_bounds():
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05)
    speech_len = cap._min_samples + 100
    silence_len = cap._silence_samples + 50
    data = np.concatenate([
        np.full(speech_len, 0.5, dtype=np.float32),
        np.zeros(silence_len, dtype=np.float32),
    ])
    n = len(data)
    _set_buf(cap, data)
    cut = cap._find_silence_cut(n)
    assert cut is not None
    assert cut >= cap._min_samples
    assert cut <= n


def test_find_silence_cut_threshold_strict_less_than():
    # Use a value that is genuinely above threshold even after float32 quantisation.
    # chunk_silence_rms=0.01 → thresh_sq=1e-4; rms=0.02 → sq=4e-4 > 1e-4 per sample.
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05, chunk_silence_rms=0.01)
    sw = cap._silence_samples
    speech_len = cap._min_samples
    above_rms = np.float32(0.02)
    data = np.concatenate([
        np.full(speech_len, 1.0, dtype=np.float32),
        np.full(sw, above_rms, dtype=np.float32),
    ])
    n = len(data)
    _set_buf(cap, data)
    cut = cap._find_silence_cut(n)
    assert cut is None


def test_find_silence_cut_below_threshold_triggers_cut():
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05, chunk_silence_rms=0.01)
    sw = cap._silence_samples
    speech_len = cap._min_samples
    below_rms = cap._silence_thresh_sq ** 0.5 * 0.5
    data = np.concatenate([
        np.full(speech_len, 1.0, dtype=np.float32),
        np.full(sw, below_rms, dtype=np.float32),
    ])
    n = len(data)
    _set_buf(cap, data)
    cut = cap._find_silence_cut(n)
    assert cut is not None


def test_find_silence_cut_first_silence_wins():
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05, chunk_silence_rms=0.01)
    sw = cap._silence_samples
    speech_len = cap._min_samples
    data = np.concatenate([
        np.full(speech_len, 1.0, dtype=np.float32),
        np.zeros(sw, dtype=np.float32),
        np.full(50, 1.0, dtype=np.float32),
        np.zeros(sw, dtype=np.float32),
    ])
    n = len(data)
    _set_buf(cap, data)
    cut = cap._find_silence_cut(n)
    assert cut is not None
    assert cut <= speech_len + sw + 1


def test_find_silence_cut_returns_before_silence_window():
    cap = _cap(chunk_min_s=0.1, chunk_silence_s=0.05, chunk_silence_rms=0.01)
    sw = cap._silence_samples
    speech_len = cap._min_samples + sw
    silence_len = sw * 2
    data = np.concatenate([
        np.full(speech_len, 1.0, dtype=np.float32),
        np.zeros(silence_len, dtype=np.float32),
    ])
    n = len(data)
    _set_buf(cap, data)
    cut = cap._find_silence_cut(n)
    assert cut is not None
    assert cut <= speech_len + 1
    assert cut + sw <= n


@pytest.mark.parametrize("sr,min_s,max_s,sil_s", [
    (16000, 0.1, 0.5, 0.05),
    (8000, 0.2, 1.0, 0.1),
    (44100, 0.05, 0.3, 0.02),
])
def test_find_silence_cut_various_params(sr, min_s, max_s, sil_s):
    cap = AudioCapture(
        samplerate=sr,
        chunk_min_s=min_s,
        chunk_max_s=max_s,
        chunk_silence_s=sil_s,
        chunk_silence_rms=0.01,
    )
    sw = cap._silence_samples
    data = np.concatenate([
        np.full(cap._min_samples, 0.5, dtype=np.float32),
        np.zeros(sw * 2, dtype=np.float32),
    ])
    n = len(data)
    _set_buf(cap, data)
    cut = cap._find_silence_cut(n)
    assert cut is not None
    assert cap._min_samples <= cut <= n


# ---------------------------------------------------------------------------
# _try_emit_locked — carry-over and multi-cut
# ---------------------------------------------------------------------------

def test_try_emit_locked_force_cut_boundary():
    collected: list[np.ndarray] = []
    cap = _cap(on_chunk=lambda c: collected.append(c))
    cap._chunk_idx = cap._max_samples
    cap._chunk_buf[: cap._max_samples] = np.ones(cap._max_samples, dtype=np.float32)
    emissions = cap._try_emit_locked()
    for e in emissions:
        cap._emit_chunk(e)
    assert len(collected) == 1
    assert len(collected[0]) == cap._max_samples


def test_try_emit_locked_two_force_cuts():
    collected: list[np.ndarray] = []
    cap = _cap(on_chunk=lambda c: collected.append(c))
    double = cap._max_samples * 2
    buf = np.ones(double + cap.blocksize, dtype=np.float32)
    cap._chunk_buf = buf.copy()
    cap._chunk_idx = double
    emissions = cap._try_emit_locked()
    for e in emissions:
        cap._emit_chunk(e)
    assert len(collected) == 2
    assert all(len(e) == cap._max_samples for e in collected)


def test_try_emit_locked_carry_over_data_preserved():
    collected: list[np.ndarray] = []
    cap = _cap(on_chunk=lambda c: collected.append(c))
    n = cap._max_samples + 10
    data = np.arange(n, dtype=np.float32)
    cap._chunk_buf = np.zeros(n + cap.blocksize, dtype=np.float32)
    cap._chunk_buf[:n] = data
    cap._chunk_idx = n
    emissions = cap._try_emit_locked()
    for e in emissions:
        cap._emit_chunk(e)
    assert cap._chunk_idx == 10
    np.testing.assert_array_equal(
        cap._chunk_buf[:10],
        data[cap._max_samples : cap._max_samples + 10],
    )


def test_try_emit_locked_no_emit_below_min():
    cap = _cap()
    cap._chunk_idx = cap._min_samples - 1
    cap._chunk_buf[: cap._chunk_idx] = np.zeros(cap._chunk_idx, dtype=np.float32)
    emissions = cap._try_emit_locked()
    assert emissions == []


# ---------------------------------------------------------------------------
# _callback — multi-channel, on_level, NaN/inf, buffer growth
# ---------------------------------------------------------------------------

def test_callback_multichannel_takes_ch0():
    ch0_vals = np.full(800, 0.9, dtype=np.float32)
    ch1_vals = np.full(800, 0.0, dtype=np.float32)
    audio = np.stack([ch0_vals, ch1_vals], axis=1)
    cap = _cap(chunk_min_s=0.01, chunk_max_s=0.2)
    cap._callback(audio, 800, None, None)
    n = cap._chunk_idx
    assert n == 0 or np.all(cap._chunk_buf[:n] >= 0.8)


def test_callback_on_level_fires():
    level_calls: list[tuple] = []
    cap = _cap(on_level=lambda rms, bands: level_calls.append((rms, bands)))
    cap._callback(np.full((160, 1), 0.5, dtype=np.float32), 160, None, None)
    assert len(level_calls) == 1
    rms, bands = level_calls[0]
    assert rms > 0
    assert bands.shape == (cap.n_bands,)


def test_callback_status_logged_no_crash():
    cap = _cap()
    cap._callback(np.zeros((160, 1), dtype=np.float32), 160, None, "input overflow")


def test_callback_nan_samples_force_cut_at_max():
    collected: list[np.ndarray] = []
    cap = _cap(
        chunk_min_s=0.1,
        chunk_max_s=0.25,
        chunk_silence_s=0.05,
        chunk_silence_rms=0.01,
        on_chunk=lambda c: collected.append(c),
    )
    cap._chunk_idx = 0
    nan_audio = np.full((cap._max_samples, 1), float("nan"), dtype=np.float32)
    cap._callback(nan_audio, cap._max_samples, None, None)
    assert len(collected) == 1
    assert len(collected[0]) == cap._max_samples


def test_callback_inf_samples_force_cut_at_max():
    collected: list[np.ndarray] = []
    cap = _cap(
        chunk_min_s=0.1,
        chunk_max_s=0.25,
        chunk_silence_s=0.05,
        chunk_silence_rms=0.01,
        on_chunk=lambda c: collected.append(c),
    )
    inf_audio = np.full((cap._max_samples, 1), float("inf"), dtype=np.float32)
    cap._callback(inf_audio, cap._max_samples, None, None)
    assert len(collected) == 1


def test_callback_buffer_growth_no_crash():
    collected: list[np.ndarray] = []
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=0.1,
        chunk_max_s=0.1,
        chunk_silence_s=0.05,
        chunk_silence_rms=0.01,
        on_chunk=lambda c: collected.append(c),
    )
    original_buf_len = len(cap._chunk_buf)
    oversized = np.zeros((original_buf_len + 500, 1), dtype=np.float32)
    cap._callback(oversized, len(oversized), None, None)


# ---------------------------------------------------------------------------
# start / stop / is_running
# ---------------------------------------------------------------------------

def test_start_creates_input_stream_with_correct_kwargs():
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        mock_stream = MagicMock()
        MockIS.return_value = mock_stream
        cap.start()
        MockIS.assert_called_once_with(
            samplerate=cap.samplerate,
            channels=cap.channels,
            blocksize=cap.blocksize,
            dtype="float32",
            device=cap.device,
            callback=cap._callback,
        )
        mock_stream.start.assert_called_once()


def test_start_double_call_creates_stream_once():
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        cap.start()
        assert MockIS.call_count == 1


def test_start_exception_leaves_stream_none():
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream", side_effect=RuntimeError("no device")):
        with pytest.raises(RuntimeError):
            cap.start()
        assert cap._stream is None
        assert not cap.is_running()


def test_start_sets_is_running():
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        assert not cap.is_running()
        cap.start()
        assert cap.is_running()


def test_stop_after_start_calls_stop_and_close():
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        mock_stream = MagicMock()
        MockIS.return_value = mock_stream
        cap.start()
        cap.stop()
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert not cap.is_running()


def test_stop_returns_positive_duration():
    import time as _time
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        _time.sleep(0.01)
        duration = cap.stop()
        assert duration > 0


def test_stop_emit_tail_false_does_not_call_on_chunk():
    collected: list[np.ndarray] = []
    cap = _cap(on_chunk=lambda c: collected.append(c))
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        cap._chunk_buf[:500] = np.ones(500, dtype=np.float32)
        cap._chunk_idx = 500
        cap.stop(emit_tail=False)
        assert len(collected) == 0


def test_stop_emit_tail_true_emits_remaining():
    collected: list[np.ndarray] = []
    cap = _cap(on_chunk=lambda c: collected.append(c))
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        cap._chunk_buf[:500] = np.ones(500, dtype=np.float32)
        cap._chunk_idx = 500
        cap.stop(emit_tail=True)
        assert len(collected) == 1
        assert len(collected[0]) == 500


def test_stop_idempotent():
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        cap.stop()
        result = cap.stop()
        assert result == 0.0


def test_stop_resets_chunk_idx():
    cap = _cap()
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        cap._chunk_idx = 999
        cap.stop(emit_tail=False)
        assert cap._chunk_idx == 0


# ---------------------------------------------------------------------------
# _emit_chunk
# ---------------------------------------------------------------------------

def test_emit_chunk_no_on_chunk_no_crash():
    cap = AudioCapture()
    cap._emit_chunk(np.ones(100, dtype=np.float32))


def test_emit_chunk_empty_does_not_call_handler():
    handler = MagicMock()
    cap = AudioCapture(on_chunk=handler)
    cap._emit_chunk(np.array([], dtype=np.float32))
    handler.assert_not_called()


def test_emit_chunk_handler_exception_swallowed():
    handler = MagicMock(side_effect=RuntimeError("boom"))
    cap = AudioCapture(on_chunk=handler)
    cap._emit_chunk(np.ones(100, dtype=np.float32))
    handler.assert_called_once()


def test_emit_chunk_calls_handler_with_data():
    received = []
    cap = AudioCapture(on_chunk=lambda c: received.append(c))
    data = np.arange(50, dtype=np.float32)
    cap._emit_chunk(data)
    assert len(received) == 1
    np.testing.assert_array_equal(received[0], data)


# ---------------------------------------------------------------------------
# _compute_bands edge cases
# ---------------------------------------------------------------------------

def test_compute_bands_silent_chunk_near_zero():
    cap = AudioCapture(n_bands=5)
    silent = np.zeros(512, dtype=np.float32)
    bands = cap._compute_bands(silent)
    assert bands.shape == (5,)
    assert bands.max() <= 1.0 + 1e-6


def test_compute_bands_exact_512():
    cap = AudioCapture(n_bands=6)
    chunk = np.random.RandomState(42).randn(512).astype(np.float32)
    bands = cap._compute_bands(chunk)
    assert bands.shape == (6,)


def test_compute_bands_n_bands_1():
    cap = AudioCapture(n_bands=1)
    chunk = np.random.RandomState(1).randn(256).astype(np.float32)
    bands = cap._compute_bands(chunk)
    assert bands.shape == (1,)
    assert 0.0 <= float(bands[0]) <= 1.0 + 1e-6


def test_compute_bands_longer_chunk_uses_last_512():
    cap = AudioCapture(n_bands=4)
    chunk_a = np.zeros(1024, dtype=np.float32)
    chunk_b = chunk_a.copy()
    chunk_b[-512:] = 1.0
    bands_a = cap._compute_bands(chunk_a)
    bands_b = cap._compute_bands(chunk_b)
    assert not np.allclose(bands_a, bands_b)


# ---------------------------------------------------------------------------
# thread safety sanity (lightweight)
# ---------------------------------------------------------------------------

def test_callback_thread_safe_concurrent_writes():
    collected: list[np.ndarray] = []
    cap = _cap(
        chunk_min_s=0.1,
        chunk_max_s=0.25,
        chunk_silence_s=0.05,
        on_chunk=lambda c: collected.append(c),
    )
    block = np.zeros((160, 1), dtype=np.float32)

    def writer():
        for _ in range(20):
            cap._callback(block, 160, None, None)

    threads = [threading.Thread(target=writer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


# ---------------------------------------------------------------------------
# silence-cut emit uses keep_silence_pad (not trailing silence)
# ---------------------------------------------------------------------------


def test_silence_cut_emits_with_pad_not_full_silence():
    collected: list[np.ndarray] = []
    sr = 16000
    cap = AudioCapture(
        samplerate=sr,
        chunk_min_s=0.1,
        chunk_max_s=2.0,
        chunk_silence_s=0.1,
        chunk_silence_rms=0.01,
        keep_silence_pad_ms=30,
        on_chunk=lambda c: collected.append(c),
    )
    speech = np.full(2000, 0.3, dtype=np.float32)
    silence = np.zeros(3000, dtype=np.float32)
    audio = np.concatenate([speech, silence])[:, None]
    cap._callback(audio, len(audio), None, None)
    assert len(collected) >= 1
    emit_len = len(collected[0])
    pad_samples = int(sr * 30 / 1000)
    assert 2000 <= emit_len <= 2000 + pad_samples + cap._silence_samples


def test_silence_cut_drops_silence_from_carryover():
    sr = 16000
    cap = AudioCapture(
        samplerate=sr,
        chunk_min_s=0.1,
        chunk_max_s=2.0,
        chunk_silence_s=0.1,
        chunk_silence_rms=0.01,
        keep_silence_pad_ms=30,
        on_chunk=lambda c: None,
    )
    speech = np.full(2000, 0.3, dtype=np.float32)
    silence = np.zeros(2000, dtype=np.float32)
    next_speech = np.full(500, 0.3, dtype=np.float32)
    audio = np.concatenate([speech, silence, next_speech])[:, None]
    cap._callback(audio, len(audio), None, None)
    remaining = cap._chunk_buf[: cap._chunk_idx]
    assert cap._chunk_idx <= len(next_speech) + cap.blocksize
    if cap._chunk_idx > 0:
        assert float(np.max(np.abs(remaining))) >= 0.2


def test_stop_emit_tail_trims_trailing_silence():
    collected: list[np.ndarray] = []
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=0.1,
        chunk_max_s=2.0,
        chunk_silence_s=0.1,
        chunk_silence_rms=0.01,
        keep_silence_pad_ms=30,
        on_chunk=lambda c: collected.append(c),
    )
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        speech = np.full(2000, 0.3, dtype=np.float32)
        silence = np.zeros(8000, dtype=np.float32)
        full = np.concatenate([speech, silence])
        cap._chunk_buf[: len(full)] = full
        cap._chunk_idx = len(full)
        cap.stop(emit_tail=True)
    assert len(collected) == 1
    assert len(collected[0]) < 10000
    assert len(collected[0]) >= 2000


def test_stop_emit_tail_drops_all_silence():
    collected: list[np.ndarray] = []
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=0.1,
        chunk_max_s=2.0,
        chunk_silence_s=0.1,
        chunk_silence_rms=0.01,
        keep_silence_pad_ms=30,
        on_chunk=lambda c: collected.append(c),
    )
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        cap._chunk_buf[:5000] = np.zeros(5000, dtype=np.float32)
        cap._chunk_idx = 5000
        cap.stop(emit_tail=True)
    assert collected == []


def test_stop_emit_tail_short_speech_emitted_as_is():
    collected: list[np.ndarray] = []
    cap = AudioCapture(
        samplerate=16000,
        chunk_min_s=0.1,
        chunk_max_s=2.0,
        chunk_silence_s=0.1,
        chunk_silence_rms=0.01,
        keep_silence_pad_ms=30,
        on_chunk=lambda c: collected.append(c),
    )
    with patch("transcrb.audio.capture.sd.InputStream") as MockIS:
        MockIS.return_value = MagicMock()
        cap.start()
        short_speech = np.full(800, 0.3, dtype=np.float32)
        cap._chunk_buf[: len(short_speech)] = short_speech
        cap._chunk_idx = len(short_speech)
        cap.stop(emit_tail=True)
    assert len(collected) == 1
    assert len(collected[0]) == 800


def test_keep_silence_pad_default_does_not_crash():
    cap = AudioCapture(samplerate=16000)
    assert cap._keep_silence_pad >= 0
