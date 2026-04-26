from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


_PHASE_STEP_ACTIVE = 0.06
_PHASE_STEP_INACTIVE = 0.02
_INACTIVE_ALPHA_SCALE = 0.4

_ARC_COUNT = 3
_ARC_PHASE_OFFSET = 0.33
_ARC_RADIUS_BASE = 1.4
_ARC_RADIUS_GROWTH = 2.0
_ARC_START_ANGLE = 110
_ARC_SPAN_ANGLE = 80


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
        self._phase += _PHASE_STEP_ACTIVE if self._active else _PHASE_STEP_INACTIVE
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * 0.45, h * 0.55
        base_r = min(w, h) * 0.14

        self._draw_body(p, cx, cy, base_r)
        self._draw_pulse_arcs(p, cx, cy, base_r)

    def _draw_body(self, p: QPainter, cx: float, cy: float, base_r: float) -> None:
        body_rect = QRectF(cx - base_r * 0.55, cy - base_r * 0.9, base_r * 1.1, base_r * 1.8)
        p.setPen(QPen(self._accent, max(1.5, base_r * 0.25)))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(body_rect, base_r * 0.5, base_r * 0.5)

    def _draw_pulse_arcs(self, p: QPainter, cx: float, cy: float, base_r: float) -> None:
        pen = QPen(self._accent)
        pen.setCapStyle(Qt.RoundCap)
        active_scale = 1.0 if self._active else _INACTIVE_ALPHA_SCALE
        for i in range(_ARC_COUNT):
            t = (self._phase + i * _ARC_PHASE_OFFSET) % 1.0
            r = base_r * (_ARC_RADIUS_BASE + t * _ARC_RADIUS_GROWTH)
            col = QColor(self._accent)
            col.setAlphaF(max(0.0, 1.0 - t) * active_scale)
            pen.setColor(col)
            pen.setWidthF(max(1.2, base_r * 0.22))
            p.setPen(pen)
            arc_rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            p.drawArc(arc_rect, int(_ARC_START_ANGLE * 16), int(_ARC_SPAN_ANGLE * 16))
