from __future__ import annotations

import numpy as np
import pytest

from transcrb.audio.preprocess import (
    is_mostly_silent,
    peak_normalize,
    trim_trailing_silence,
)


class TestIsMostlySilent:
    def test_all_zero_is_silent(self):
        assert is_mostly_silent(np.zeros(1000, dtype=np.float32), 0.015) is True

    def test_all_speech_is_not_silent(self):
        assert is_mostly_silent(np.full(1000, 0.3, dtype=np.float32), 0.015) is False

    def test_empty_treated_as_silent(self):
        assert is_mostly_silent(np.zeros(0, dtype=np.float32), 0.015) is True

    def test_below_frac_threshold(self):
        a = np.concatenate([
            np.zeros(800, dtype=np.float32),
            np.full(200, 0.3, dtype=np.float32),
        ])
        assert is_mostly_silent(a, 0.015, frac=0.85) is False

    def test_above_frac_threshold(self):
        a = np.concatenate([
            np.zeros(900, dtype=np.float32),
            np.full(100, 0.3, dtype=np.float32),
        ])
        assert is_mostly_silent(a, 0.015, frac=0.85) is True

    def test_negative_samples_counted_by_abs(self):
        a = np.full(1000, -0.001, dtype=np.float32)
        assert is_mostly_silent(a, 0.015) is True

    def test_strict_below_threshold(self):
        a = np.full(1000, 0.015, dtype=np.float32)
        assert is_mostly_silent(a, 0.015) is False


class TestPeakNormalize:
    def test_quiet_signal_scaled_up_within_max_gain(self):
        a = np.full(1000, 0.05, dtype=np.float32)
        out = peak_normalize(a, target_peak=0.95, max_gain=8.0)
        assert pytest.approx(float(np.max(np.abs(out))), abs=1e-5) == 0.05 * 8.0

    def test_loud_signal_reaches_target_peak(self):
        a = np.linspace(-0.8, 0.8, 1000, dtype=np.float32)
        out = peak_normalize(a, target_peak=0.95, max_gain=8.0)
        assert float(np.max(np.abs(out))) == pytest.approx(0.95, abs=1e-5)

    def test_all_zero_input_returns_input(self):
        a = np.zeros(1000, dtype=np.float32)
        out = peak_normalize(a)
        assert np.all(out == 0)
        assert not np.any(np.isnan(out))

    def test_empty_input_returns_input(self):
        a = np.zeros(0, dtype=np.float32)
        out = peak_normalize(a)
        assert out.size == 0

    def test_clip_to_unity(self):
        a = np.full(100, 0.99, dtype=np.float32)
        out = peak_normalize(a, target_peak=0.95)
        assert float(np.max(np.abs(out))) <= 1.0

    def test_dtype_preserved(self):
        a = np.full(100, 0.1, dtype=np.float32)
        out = peak_normalize(a)
        assert out.dtype == np.float32

    def test_max_gain_cap_respected(self):
        a = np.full(100, 0.001, dtype=np.float32)
        out = peak_normalize(a, target_peak=0.95, max_gain=2.0)
        assert float(np.max(np.abs(out))) <= 0.001 * 2.0 + 1e-5


class TestTrimTrailingSilence:
    def test_speech_followed_by_silence_trimmed(self):
        sr = 16000
        speech = np.full(4000, 0.3, dtype=np.float32)
        silence = np.zeros(8000, dtype=np.float32)
        audio = np.concatenate([speech, silence])
        out = trim_trailing_silence(audio, sr=sr, silence_rms=0.015, window_ms=200, keep_ms=120)
        assert out.size > 0
        assert out.size < audio.size

    def test_all_speech_unchanged(self):
        sr = 16000
        audio = np.full(8000, 0.3, dtype=np.float32)
        out = trim_trailing_silence(audio, sr=sr, silence_rms=0.015, window_ms=200, keep_ms=120)
        assert out.size == audio.size

    def test_all_silence_returns_empty(self):
        sr = 16000
        audio = np.zeros(8000, dtype=np.float32)
        out = trim_trailing_silence(audio, sr=sr, silence_rms=0.015, window_ms=200, keep_ms=120)
        assert out.size == 0

    def test_empty_input_returns_empty(self):
        sr = 16000
        audio = np.zeros(0, dtype=np.float32)
        out = trim_trailing_silence(audio, sr=sr, silence_rms=0.015)
        assert out.size == 0

    def test_short_audio_below_window_preserves_speech(self):
        sr = 16000
        audio = np.full(800, 0.3, dtype=np.float32)
        out = trim_trailing_silence(audio, sr=sr, silence_rms=0.015, window_ms=200, keep_ms=120)
        assert out.size == audio.size

    def test_short_silent_audio_dropped(self):
        sr = 16000
        audio = np.zeros(800, dtype=np.float32)
        out = trim_trailing_silence(audio, sr=sr, silence_rms=0.015, window_ms=200, keep_ms=120)
        assert out.size == 0

    def test_keep_pad_retained_after_speech(self):
        sr = 16000
        speech = np.full(3200, 0.3, dtype=np.float32)
        silence = np.zeros(8000, dtype=np.float32)
        audio = np.concatenate([speech, silence])
        out = trim_trailing_silence(audio, sr=sr, silence_rms=0.015, window_ms=200, keep_ms=120)
        expected_pad = int(sr * 120 / 1000)
        assert out.size >= speech.size
        assert out.size <= speech.size + int(sr * 200 / 1000) + expected_pad
