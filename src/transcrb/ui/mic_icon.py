from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class MicRadarIcon(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        accent: str = "#31D27A",
        fps: int = 30,
    ) -> None:
        super().__init__(parent)
        self._accent = QColor(accent)
        self._phase = 0.0
        self._active = True

        self._timer = QTimer(self)
        self._timer.setInterval(max(1, int(1000 / fps)))
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMinimumSize(44, 44)

    def set_active(self, active: bool) -> None:
        self._active = active

    def _tick(self) -> None:
        self._phase += 0.06 if self._active else 0.02
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * 0.45, h * 0.55
        base_r = min(w, h) * 0.14

        # микрофонная "ножка" как замкнутый дуговой элемент
        body_rect = QRectF(cx - base_r * 0.55, cy - base_r * 0.9, base_r * 1.1, base_r * 1.8)
        p.setPen(QPen(self._accent, max(1.5, base_r * 0.25)))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(body_rect, base_r * 0.5, base_r * 0.5)

        # концентрические пульсирующие арки справа сверху — эффект радиоволн
        pen = QPen(self._accent)
        pen.setCapStyle(Qt.RoundCap)
        for i in range(3):
            t = (self._phase + i * 0.33) % 1.0
            r = base_r * (1.4 + t * 2.0)
            alpha = max(0.0, 1.0 - t)
            col = QColor(self._accent)
            col.setAlphaF(alpha * (1.0 if self._active else 0.4))
            pen.setColor(col)
            pen.setWidthF(max(1.2, base_r * 0.22))
            p.setPen(pen)
            # дуга с верхне-левой стороны микрофона, ~90°
            arc_rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            p.drawArc(arc_rect, int(110 * 16), int(80 * 16))
