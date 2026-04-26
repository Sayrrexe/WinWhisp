from __future__ import annotations

import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd
from loguru import logger


class AudioCapture:
    def __init__(
        self,
        samplerate: int = 16000,
        channels: int = 1,
        block_ms: int = 30,
        max_duration_s: int = 120,
        device: str | int | None = None,
        n_bands: int = 10,
        chunk_min_s: float = 1.5,
        chunk_max_s: float = 8.0,
        chunk_silence_s: float = 0.25,
        chunk_silence_rms: float = 0.015,
        on_level: Callable[[float, np.ndarray], None] | None = None,
        on_chunk: Callable[[np.ndarray], None] | None = None,
    ) -> None:
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = max(1, int(samplerate * block_ms / 1000))
        self.max_duration_s = max_duration_s
        self.device = device
        self.n_bands = n_bands
        self.on_level = on_level
        self.on_chunk = on_chunk

        self._min_samples = max(self.blocksize, int(samplerate * chunk_min_s))
        self._max_samples = max(self._min_samples + 1, int(samplerate * chunk_max_s))
        self._silence_samples = max(1, int(samplerate * chunk_silence_s))
        self._silence_thresh_sq = float(chunk_silence_rms) ** 2

        self._chunk_buf = np.zeros(self._max_samples + self.blocksize, dtype=np.float32)
        self._chunk_idx = 0
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._start_time: float = 0.0
        self._fft_window = np.hanning(512).astype(np.float32)
        self._band_edges = np.geomspace(1, 256, n_bands + 1).astype(int)

    def _emit_chunk(self, chunk: np.ndarray) -> None:
        if self.on_chunk is None or len(chunk) == 0:
            return
        try:
            self.on_chunk(chunk)
        except Exception as e:
            logger.debug(f"on_chunk handler error: {e}")

    def _find_silence_cut(self, n: int) -> int | None:
        sw = self._silence_samples
        if n < self._min_samples or n < sw:
            return None
        buf = self._chunk_buf[:n]
        sq = (buf * buf).astype(np.float64, copy=False)
        prefix = np.empty(n + 1, dtype=np.float64)
        prefix[0] = 0.0
        np.cumsum(sq, out=prefix[1:])
        threshold = self._silence_thresh_sq * sw
        start_i = max(0, self._min_samples - sw)
        end_i = n - sw
        if start_i > end_i:
            return None
        sums = prefix[start_i + sw : end_i + sw + 1] - prefix[start_i : end_i + 1]
        mask = sums < threshold
        if not np.any(mask):
            return None
        idx = int(np.argmax(mask))
        return int(start_i + idx + sw)

    def _try_emit_locked(self) -> list[np.ndarray]:
        out_list: list[np.ndarray] = []
        while True:
            cut: int | None = None
            if self._chunk_idx >= self._max_samples:
                cut = self._max_samples
            elif self._chunk_idx >= self._min_samples:
                cut = self._find_silence_cut(self._chunk_idx)
            if cut is None:
                break
            out_list.append(self._chunk_buf[:cut].copy())
            remaining = self._chunk_idx - cut
            if remaining > 0:
                self._chunk_buf[:remaining] = self._chunk_buf[cut : self._chunk_idx].copy()
            self._chunk_idx = remaining
        return out_list

    def _grow_buffer_locked(self, need: int) -> None:
        if need <= len(self._chunk_buf):
            return
        new_size = max(need, len(self._chunk_buf) * 2)
        new_buf = np.zeros(new_size, dtype=np.float32)
        new_buf[: self._chunk_idx] = self._chunk_buf[: self._chunk_idx]
        self._chunk_buf = new_buf

    def _emit_level(self, mono: np.ndarray) -> None:
        if self.on_level is None:
            return
        rms = float(np.sqrt(np.mean(mono**2) + 1e-12))
        bands = self._compute_bands(mono)
        try:
            self.on_level(rms, bands)
        except Exception as e:
            logger.debug(f"on_level handler error: {e}")

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            logger.debug(f"audio status: {status}")
        mono = indata[:, 0] if indata.ndim > 1 else indata
        mono = mono.astype(np.float32, copy=False)

        with self._lock:
            self._grow_buffer_locked(self._chunk_idx + len(mono))
            self._chunk_buf[self._chunk_idx : self._chunk_idx + len(mono)] = mono
            self._chunk_idx += len(mono)
            emissions = self._try_emit_locked()

        for out in emissions:
            self._emit_chunk(out)

        self._emit_level(mono)

    def _compute_bands(self, chunk: np.ndarray) -> np.ndarray:
        if len(chunk) < 512:
            pad = np.zeros(512, dtype=np.float32)
            pad[: len(chunk)] = chunk
            chunk = pad
        else:
            chunk = chunk[-512:]
        spec = np.abs(np.fft.rfft(chunk * self._fft_window))
        bands = np.zeros(self.n_bands, dtype=np.float32)
        for i in range(self.n_bands):
            lo, hi = self._band_edges[i], max(self._band_edges[i] + 1, self._band_edges[i + 1])
            bands[i] = spec[lo:hi].mean() if hi > lo else 0.0
        peak = max(float(bands.max()), 1e-2)
        return np.clip(bands / peak, 0.0, 1.0).astype(np.float32)

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunk_idx = 0
        self._start_time = time.monotonic()
        try:
            self._stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                blocksize=self.blocksize,
                dtype="float32",
                device=self.device,
                callback=self._callback,
            )
            self._stream.start()
            logger.debug("audio stream started")
        except Exception as e:
            logger.error(f"failed to start audio: {e}")
            self._stream = None
            raise

    def stop(self, emit_tail: bool = True) -> float:
        if self._stream is None:
            return 0.0
        try:
            self._stream.stop()
            self._stream.close()
        except Exception as e:
            logger.debug(f"stream close error: {e}")
        self._stream = None
        with self._lock:
            tail_len = self._chunk_idx
            tail = self._chunk_buf[:tail_len].copy() if tail_len > 0 else None
            self._chunk_idx = 0
        if emit_tail and tail is not None:
            self._emit_chunk(tail)
        duration = time.monotonic() - self._start_time
        logger.debug(f"audio stream stopped, duration={duration:.2f}s, tail={tail_len}")
        return duration

    def is_running(self) -> bool:
        return self._stream is not None
