from __future__ import annotations

import numpy as np


def is_mostly_silent(audio: np.ndarray, silence_rms: float, frac: float = 0.85) -> bool:
    if audio.size == 0:
        return True
    thresh = float(silence_rms)
    silent_count = int(np.count_nonzero(np.abs(audio) < thresh))
    return silent_count / audio.size >= frac


def peak_normalize(
    audio: np.ndarray,
    target_peak: float = 0.95,
    max_gain: float = 8.0,
) -> np.ndarray:
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if peak <= 0.0 or not np.isfinite(peak):
        return audio
    gain = min(target_peak / peak, max_gain)
    if gain <= 1.0 + 1e-6:
        out = audio if gain >= 1.0 else (audio * gain).astype(audio.dtype, copy=False)
    else:
        out = (audio * gain).astype(audio.dtype, copy=False)
    return np.clip(out, -1.0, 1.0)


def trim_trailing_silence(
    audio: np.ndarray,
    sr: int,
    silence_rms: float,
    window_ms: int = 200,
    keep_ms: int = 120,
) -> np.ndarray:
    n = audio.size
    if n == 0:
        return audio
    sw = max(1, int(sr * window_ms / 1000))
    pad = max(0, int(sr * keep_ms / 1000))
    thresh_sq = float(silence_rms) ** 2
    if n <= sw:
        mean_sq = float(np.mean(audio.astype(np.float64) ** 2))
        return audio if mean_sq >= thresh_sq else audio[:0]
    sq = audio.astype(np.float64) ** 2
    prefix = np.empty(n + 1, dtype=np.float64)
    prefix[0] = 0.0
    np.cumsum(sq, out=prefix[1:])
    sums = prefix[sw : n + 1] - prefix[: n - sw + 1]
    threshold = thresh_sq * sw
    above = sums >= threshold
    if not np.any(above):
        return audio[:0]
    last_above_start = int(np.where(above)[0][-1])
    speech_end = last_above_start + sw
    return audio[: min(n, speech_end + pad)]
