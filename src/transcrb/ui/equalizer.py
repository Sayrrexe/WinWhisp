from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class EqualizerBars(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        n_bars: int = 10,
        fps: int = 30,
        accent: str = "#31D27A",
        smoothing: float = 0.35,
    ) -> None:
        super().__init__(parent)
        self._n = n_bars
        self._heights = np.full(n_bars, 0.1, dtype=np.float32)
        self._targets = np.full(n_bars, 0.1, dtype=np.float32)
        self._smoothing = smoothing
        self._accent = QColor(accent)
        self._active = False
        self._phase = 0.0
        self._idle_offsets = np.arange(n_bars, dtype=np.float32) * 0.6

        self._timer = QTimer(self)
        self._timer.setInterval(max(1, int(1000 / fps)))
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMinimumSize(120, 40)

    def set_bands(self, bands: np.ndarray, active: bool = True) -> None:
        if bands is None or len(bands) == 0:
            self._targets[:] = 0.1
            self._active = False
            return
        if len(bands) != self._n:
            idx = np.linspace(0, len(bands) - 1, self._n)
            bands = np.interp(idx, np.arange(len(bands)), bands)
        self._targets = np.clip(bands.astype(np.float32), 0.05, 1.0)
        self._active = active

    def set_idle(self) -> None:
        self._active = False
        self._targets[:] = 0.1

    def _tick(self) -> None:
        if not self._active:
            self._phase += 0.08
            self._targets = (0.18 + 0.08 * np.sin(self._phase + self._idle_offsets)).astype(np.float32)
        self._heights += (self._targets - self._heights) * self._smoothing
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        gap = 4
        bar_w = max(2, (w - gap * (self._n - 1)) / self._n)
        max_h = h * 0.82
        min_h = max(4, h * 0.08)
        cy = h / 2
        radius = bar_w / 2
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent)
        for i in range(self._n):
            bh = max(min_h, float(self._heights[i]) * max_h)
            x = i * (bar_w + gap)
            p.drawRoundedRect(QRectF(x, cy - bh / 2, bar_w, bh), radius, radius)
