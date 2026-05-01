from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from transcrb.paths import resources_dir


_RAW_CACHE: dict[str, bytes] = {}
_RENDERER_CACHE: dict[tuple[str, str], QSvgRenderer] = {}


def _color_str(color: str | QColor) -> str:
    if isinstance(color, QColor):
        return color.name(QColor.HexArgb) if color.alpha() != 255 else color.name()
    return color


def _load_raw(name: str) -> bytes:
    cached = _RAW_CACHE.get(name)
    if cached is not None:
        return cached
    raw = (resources_dir() / "icons" / f"{name}.svg").read_bytes()
    _RAW_CACHE[name] = raw
    return raw


def _renderer(name: str, color: str) -> QSvgRenderer:
    key = (name, color)
    r = _RENDERER_CACHE.get(key)
    if r is not None:
        return r
    raw = _load_raw(name).replace(b'"currentColor"', f'"{color}"'.encode())
    r = QSvgRenderer(raw)
    _RENDERER_CACHE[key] = r
    return r


def paint_icon(painter: QPainter, name: str, rect: QRectF, color: str | QColor) -> None:
    _renderer(name, _color_str(color)).render(painter, rect)


def icon_pixmap(name: str, color: str | QColor, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    _renderer(name, _color_str(color)).render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def icon(name: str, color: str | QColor, size: int) -> QIcon:
    return QIcon(icon_pixmap(name, color, size))
