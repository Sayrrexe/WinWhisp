from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class Spinner(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        accent: str = "#31D27A",
        fps: int = 60,
        rotation_speed_deg: float = 6.0,
        arc_span_deg: float = 110.0,
    ) -> None:
        super().__init__(parent)
        self._accent = QColor(accent)
        self._angle = 0.0
        self._speed = rotation_speed_deg
        self._arc = arc_span_deg

        self._timer = QTimer(self)
        self._timer.setInterval(max(1, int(1000 / fps)))
        self._timer.timeout.connect(self._tick)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMinimumSize(28, 28)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + self._speed) % 360.0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        size = max(10, min(w, h) - 8)
        rect = QRectF((w - size) / 2.0, (h - size) / 2.0, size, size)

        pen = QPen()
        pen.setWidthF(max(2.0, size * 0.09))
        pen.setCapStyle(Qt.RoundCap)

        track = QColor(self._accent)
        track.setAlpha(50)
        pen.setColor(track)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)

        pen.setColor(self._accent)
        p.setPen(pen)
        p.drawArc(rect, int(-self._angle * 16), int(self._arc * 16))
