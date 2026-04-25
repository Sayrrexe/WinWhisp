from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from transcrb.config import Config, save_config
from transcrb.paths import appdata_dir, config_path, vocab_path
from transcrb.runtime import AppRuntime, HistoryEntry, HistoryStore
from transcrb.text.vocab import Vocab


APP_VERSION = "0.1.0"
ACCENT = "#31D27A"

SIDEBAR_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "",
        [
            ("dashboard", "◆", "Дашборд"),
            ("history", "↺", "История"),
        ],
    ),
    (
        "Конфигурация",
        [
            ("about", "ⓘ", "О программе"),
            ("general", "⚙", "Общие"),
            ("model", "◇", "Модель распознавания"),
            ("audio", "◉", "Микрофон и запись"),
            ("inject", "↘", "Вставка текста"),
            ("overlay", "◐", "Внешний вид"),
        ],
    ),
    (
        "Данные",
        [
            ("vocab", "⌥", "Словарь"),
            ("logs", "⛁", "Логи и диагностика"),
        ],
    ),
]


_STYLE = """
* {
    font-family: "Inter", "Segoe UI Variable", "Segoe UI", sans-serif;
    color: #E8E8EA;
}

QMainWindow, QWidget#root { background: #0A0A0B; }

QWidget#sidebar {
    background: #0E0E10;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

QLabel#sidebarBrand {
    color: #E8E8EA;
    font-size: 14px;
    font-weight: 600;
    padding: 22px 18px 2px 18px;
}
QLabel#sidebarBrandSub {
    color: #5A5C63;
    font-size: 11px;
    padding: 0 18px 16px 18px;
}
QLabel#sidebarGroup {
    color: #5A5C63;
    font-size: 10px;
    font-weight: 600;
    padding: 14px 20px 6px 20px;
    letter-spacing: 1px;
}

QPushButton#sideItem {
    background: transparent;
    color: #9A9CA3;
    border: none;
    text-align: left;
    padding: 9px 14px 9px 18px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#sideItem:hover { background: #131316; color: #E8E8EA; }
QPushButton#sideItem:checked { background: rgba(49, 210, 122, 0.14); color: #4FE090; }
QPushButton#sideItem:checked:hover { background: rgba(49, 210, 122, 0.20); }

QWidget#content { background: #0A0A0B; }

QLabel#pageTitle {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.4px;
}
QLabel#pageSub {
    color: #5A5C63;
    font-size: 13px;
}

QFrame#card {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
}
QLabel#cardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #E8E8EA;
}
QLabel#cardKicker {
    color: #5A5C63;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#cardBody { color: #9A9CA3; font-size: 12.5px; }
QLabel#cardMuted { color: #5A5C63; font-size: 12px; }

QPushButton#linkBtn {
    background: #1A1A1E;
    color: #E8E8EA;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12.5px;
    font-weight: 500;
}
QPushButton#linkBtn:hover { background: #222227; border: 1px solid rgba(255, 255, 255, 0.12); }

QPushButton#primaryBtn {
    background: #31D27A;
    color: #0A0A0B;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12.5px;
    font-weight: 600;
}
QPushButton#primaryBtn:hover { background: #4FE090; }
QPushButton#primaryBtn:disabled { background: #1A1A1E; color: #5A5C63; }

QFrame#heroCard {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
}
QLabel#heroTitle {
    font-size: 16px;
    font-weight: 600;
    color: #E8E8EA;
}
QLabel#heroSub {
    color: #9A9CA3;
    font-size: 12.5px;
}

QLabel#kbd {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 5px;
    padding: 1px 9px;
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
    font-size: 11.5px;
    color: #E8E8EA;
}

QLabel#pillOk {
    background: rgba(49, 210, 122, 0.10);
    border: 1px solid rgba(49, 210, 122, 0.25);
    color: #4FE090;
    padding: 3px 11px;
    border-radius: 9px;
    font-size: 11.5px;
}
QLabel#pillWarn {
    background: rgba(255, 178, 44, 0.10);
    border: 1px solid rgba(255, 178, 44, 0.25);
    color: #FFC766;
    padding: 3px 11px;
    border-radius: 9px;
    font-size: 11.5px;
}
QLabel#pillDim {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: #9A9CA3;
    padding: 3px 11px;
    border-radius: 9px;
    font-size: 11.5px;
}

QLabel#compIcon {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    color: #9A9CA3;
    font-size: 13px;
    qproperty-alignment: AlignCenter;
}
QLabel#compName { font-size: 12.5px; font-weight: 500; color: #E8E8EA; }
QLabel#compMeta { color: #5A5C63; font-size: 11px; }
QLabel#compVal  { color: #E8E8EA; font-size: 12px; font-weight: 500; }
QLabel#compValDim { color: #9A9CA3; font-size: 12px; font-weight: 500; }

QFrame#rowSep { background: rgba(255, 255, 255, 0.06); max-height: 1px; min-height: 1px; border: none; }

QFrame#filterBar {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 9px;
}
QPushButton#filterBtn {
    background: transparent;
    color: #5A5C63;
    border: none;
    padding: 5px 12px;
    font-size: 11.5px;
    font-weight: 500;
    border-radius: 6px;
}
QPushButton#filterBtn:hover { color: #E8E8EA; }
QPushButton#filterBtn:checked { background: #222227; color: #E8E8EA; }

QLabel#daySep {
    color: #5A5C63;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 1px;
}

QFrame#historyItem {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}
QFrame#historyItem:hover {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.10);
}
QLabel#itemTime {
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
    font-size: 11.5px;
    color: #9A9CA3;
}
QLabel#itemAgo { color: #5A5C63; font-size: 10.5px; }
QLabel#itemTxt { font-size: 12.5px; color: #E8E8EA; }
QLabel#itemMeta { color: #5A5C63; font-size: 10.5px; }
QPushButton#itemActBtn {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    color: #9A9CA3;
    font-size: 12px;
}
QPushButton#itemActBtn:hover { color: #4FE090; border: 1px solid rgba(49, 210, 122, 0.30); }

QLabel#historyEmpty {
    color: #5A5C63;
    font-size: 12.5px;
}

QLabel#rowTitle { color: #E8E8EA; font-size: 13px; font-weight: 500; }
QLabel#rowDesc { color: #5A5C63; font-size: 11.5px; }
QLabel#sliderVal {
    color: #9A9CA3;
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
    font-size: 11px;
}

QFrame#divider {
    background: rgba(255, 255, 255, 0.05);
    max-height: 1px;
    min-height: 1px;
    border: none;
}
QFrame#dividerDashed {
    background: transparent;
    border: none;
    border-top: 1px dashed rgba(255, 255, 255, 0.08);
    max-height: 1px;
    min-height: 1px;
}

QPushButton#disclosure {
    background: transparent;
    color: #9A9CA3;
    border: none;
    text-align: left;
    padding: 8px 0;
    font-size: 11.5px;
}
QPushButton#disclosure:hover { color: #E8E8EA; }

QSlider#hslider::groove:horizontal {
    height: 3px;
    background: #222227;
    border-radius: 1px;
}
QSlider#hslider::sub-page:horizontal {
    background: #31D27A;
    border-radius: 1px;
}
QSlider#hslider::add-page:horizontal {
    background: #222227;
    border-radius: 1px;
}
QSlider#hslider::handle:horizontal {
    background: #FFFFFF;
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.20);
}
QSlider#hslider::handle:horizontal:hover { background: #F0F0F0; }

QComboBox#select {
    background: #1A1A1E;
    color: #E8E8EA;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    padding: 5px 28px 5px 11px;
    font-size: 12.5px;
    min-width: 110px;
}
QComboBox#select:hover { border: 1px solid rgba(255, 255, 255, 0.10); }
QComboBox#select::drop-down { border: none; width: 24px; }
QComboBox#select::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid #9A9CA3;
    margin-right: 8px;
}
QComboBox#select QAbstractItemView {
    background: #1A1A1E;
    color: #E8E8EA;
    border: 1px solid rgba(255, 255, 255, 0.10);
    selection-background-color: rgba(49, 210, 122, 0.20);
    selection-color: #E8E8EA;
    padding: 4px;
    outline: 0;
}

QPushButton#kbdBtn {
    background: #1A1A1E;
    color: #9A9CA3;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton#kbdBtn:hover { background: #222227; color: #E8E8EA; border: 1px solid rgba(255, 255, 255, 0.12); }

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 6px 3px; }
QScrollBar::handle:vertical { background: #232328; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #2D2D33; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


def _make_logo_pixmap(size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    bg = QPainterPath()
    radius = size * 0.24
    bg.addRoundedRect(0, 0, size, size, radius, radius)
    p.fillPath(bg, QBrush(QColor("#131316")))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(26, 26, 30))
    p.drawRoundedRect(1, 1, size - 2, size - 2, radius - 1, radius - 1)
    dot = size * 0.34
    inset = (size - dot) / 2
    p.setBrush(QColor(ACCENT))
    p.drawRoundedRect(int(inset), int(inset), int(dot), int(dot), int(dot * 0.32), int(dot * 0.32))
    p.end()
    return pm


def _make_pulse_pixmap(size: int = 110, *, color: str = ACCENT, dim: bool = False) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    cx = size / 2
    cy = size / 2
    base = QColor(color)
    glow = QColor(base)
    glow.setAlphaF(0.10 if dim else 0.18)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(glow))
    p.drawEllipse(QPointF(cx, cy), size * 0.46, size * 0.46)
    ring = QColor(base)
    if dim:
        ring.setAlphaF(0.45)
    p.setBrush(QBrush(ring))
    p.drawEllipse(QPointF(cx, cy), size * 0.30, size * 0.30)
    p.setBrush(QBrush(QColor("#0A0A0B")))
    p.drawEllipse(QPointF(cx, cy), size * 0.18, size * 0.18)
    inner = QColor(base)
    if dim:
        inner.setAlphaF(0.55)
    p.setBrush(QBrush(inner))
    p.drawEllipse(QPointF(cx, cy), size * 0.10, size * 0.10)
    p.end()
    return pm


def _label(text: str, name: str = "", *, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def _kbd(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("kbd")
    lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
    return lbl


def _pill(text: str, kind: str = "dim") -> QLabel:
    name = {"ok": "pillOk", "warn": "pillWarn", "dim": "pillDim"}.get(kind, "pillDim")
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
    return lbl


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


def _open_path(path: Path) -> None:
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix:
                path.touch()
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        pass


def _link_button(text: str, on_click) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("linkBtn")
    b.setCursor(Qt.PointingHandCursor)
    b.clicked.connect(on_click)
    return b


def _primary_button(text: str, on_click) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("primaryBtn")
    b.setCursor(Qt.PointingHandCursor)
    b.clicked.connect(on_click)
    return b


class _ElideLabel(QLabel):
    def __init__(self, text: str = "", object_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
        self._full = text
        super().setText(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full = text
        self._update_elide()

    def fullText(self) -> str:
        return self._full

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_elide()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        fm = self.fontMetrics()
        return QSize(160, fm.height() + 2)

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        fm = self.fontMetrics()
        return QSize(40, fm.height() + 2)

    def _update_elide(self) -> None:
        fm = self.fontMetrics()
        elided = fm.elidedText(self._full, Qt.ElideRight, max(0, self.width() - 2))
        super().setText(elided)


class _ToggleSwitch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(34, 20)

    def sizeHint(self) -> QSize:
        return QSize(34, 20)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        track = QRectF(0, 0, self.width(), self.height())
        p.setPen(Qt.NoPen)
        if on:
            glow = QColor(ACCENT)
            glow.setAlphaF(0.18)
            p.setBrush(glow)
            p.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 12, 12)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(track, 10, 10)
        else:
            p.setBrush(QColor("#222227"))
            p.drawRoundedRect(track, 10, 10)
            p.setPen(QColor(255, 255, 255, 16))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), 9.5, 9.5)
        thumb_d = 16.0
        thumb_y = (self.height() - thumb_d) / 2
        thumb_x = (self.width() - thumb_d - 1) if on else 1
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0A0A0B" if on else "#CFD0D3"))
        p.drawEllipse(QRectF(thumb_x, thumb_y, thumb_d, thumb_d))
        p.end()


class _ValueSlider(QWidget):
    valueChanged = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str = " мс",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._suffix = suffix
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setObjectName("hslider")
        self._slider.setMinimum(minimum)
        self._slider.setMaximum(maximum)
        self._slider.setValue(value)
        self._slider.setFixedWidth(180)
        self._slider.setCursor(Qt.PointingHandCursor)

        self._val = QLabel()
        self._val.setObjectName("sliderVal")
        self._val.setFixedWidth(58)
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        h.addWidget(self._slider)
        h.addWidget(self._val)

        self._slider.valueChanged.connect(self._on_changed)
        self._update_label(value)

    def _on_changed(self, v: int) -> None:
        self._update_label(v)
        self.valueChanged.emit(v)

    def _update_label(self, v: int) -> None:
        self._val.setText(f"{v}{self._suffix}")

    def value(self) -> int:
        return self._slider.value()


class _Disclosure(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._toggle = QPushButton(self._compose(False))
        self._toggle.setObjectName("disclosure")
        self._toggle.setCursor(Qt.PointingHandCursor)
        self._toggle.setCheckable(True)
        self._toggle.toggled.connect(self._on_toggled)
        v.addWidget(self._toggle)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        self._body.setVisible(False)
        v.addWidget(self._body)

    def _compose(self, opened: bool) -> str:
        arrow = "⌄" if opened else "›"
        return f"  {arrow}   {self._title}"

    def _on_toggled(self, opened: bool) -> None:
        self._body.setVisible(opened)
        self._toggle.setText(self._compose(opened))

    def add_row(self, row: QWidget) -> None:
        if self._body_layout.count() > 0:
            self._body_layout.addWidget(_divider())
        self._body_layout.addWidget(row)


def _divider(*, dashed: bool = False) -> QFrame:
    d = QFrame()
    d.setObjectName("dividerDashed" if dashed else "divider")
    d.setFixedHeight(1)
    return d


def _setting_row(title: str, desc: str, control: QWidget) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 12, 0, 12)
    h.setSpacing(20)

    meta = QVBoxLayout()
    meta.setContentsMargins(0, 0, 0, 0)
    meta.setSpacing(2)
    meta.addWidget(_label(title, "rowTitle"))
    if desc:
        meta.addWidget(_label(desc, "rowDesc", wrap=True))

    meta_wrap = QWidget()
    meta_wrap.setLayout(meta)
    h.addWidget(meta_wrap, 1)
    h.addWidget(control, 0, Qt.AlignVCenter | Qt.AlignRight)
    return row


class _Sidebar(QWidget):
    page_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(248)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        brand = _label("WinWhisp", "sidebarBrand")
        sub = _label(f"v{APP_VERSION}", "sidebarBrandSub")
        root.addWidget(brand)
        root.addWidget(sub)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for idx, (group_title, items) in enumerate(SIDEBAR_GROUPS):
            if group_title:
                root.addWidget(_label(group_title, "sidebarGroup"))
            elif idx > 0:
                root.addSpacing(8)
            for key, icon, title in items:
                btn = QPushButton(f"  {icon}    {title}")
                btn.setObjectName("sideItem")
                btn.setCheckable(True)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda _checked, k=key: self.page_changed.emit(k))
                self._group.addButton(btn)
                self._buttons[key] = btn
                wrap = QWidget()
                wl = QHBoxLayout(wrap)
                wl.setContentsMargins(8, 0, 8, 1)
                wl.addWidget(btn)
                root.addWidget(wrap)

        root.addStretch(1)

        footer_wrap = QWidget()
        fw = QHBoxLayout(footer_wrap)
        fw.setContentsMargins(18, 14, 18, 18)
        footer = _label("© 2026 Sayrrexe", "cardMuted")
        fw.addWidget(footer)
        root.addWidget(footer_wrap)

    def select(self, key: str, *, emit: bool = True) -> None:
        btn = self._buttons.get(key)
        if btn is None:
            return
        btn.setChecked(True)
        if emit:
            self.page_changed.emit(key)


def _build_about_page() -> QWidget:
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(40, 36, 40, 36)
    outer.setSpacing(20)

    hero = _card()
    hl = QHBoxLayout(hero)
    hl.setContentsMargins(28, 26, 28, 26)
    hl.setSpacing(22)

    logo = QLabel()
    logo.setPixmap(_make_logo_pixmap(72))
    logo.setFixedSize(72, 72)
    hl.addWidget(logo, 0, Qt.AlignTop)

    text_box = QVBoxLayout()
    text_box.setSpacing(4)

    name = _label("WinWhisp")
    nf = QFont()
    nf.setPointSize(22)
    nf.setBold(True)
    name.setFont(nf)
    text_box.addWidget(name)

    sub = _label("Push-to-talk диктовка с локальным распознаванием речи")
    sub.setStyleSheet("color: #9A9CA3; font-size: 13.5px;")
    sub.setWordWrap(True)
    text_box.addWidget(sub)

    text_box.addSpacing(12)

    chips = QHBoxLayout()
    chips.setSpacing(8)
    chips.setContentsMargins(0, 0, 0, 0)
    for txt, color in (
        (f"v{APP_VERSION}", "#9A9CA3"),
        ("Windows", "#9A9CA3"),
        ("Локально", ACCENT),
    ):
        chip = QLabel(txt)
        chip.setStyleSheet(
            f"background: #1A1A1E; color: {color}; padding: 4px 10px;"
            "border-radius: 999px; font-size: 11.5px; font-weight: 500;"
        )
        chips.addWidget(chip)
    chips.addStretch(1)
    text_box.addLayout(chips)

    hl.addLayout(text_box, 1)
    outer.addWidget(hero)

    row = QHBoxLayout()
    row.setSpacing(16)

    author = _card()
    al = QVBoxLayout(author)
    al.setContentsMargins(24, 22, 24, 22)
    al.setSpacing(6)
    al.addWidget(_label("АВТОР", "cardKicker"))
    al.addSpacing(2)
    al.addWidget(_label("Sayrrexe", "cardTitle"))
    al.addWidget(_label("sayrrexe@gmail.com", "cardMuted"))
    al.addStretch(1)

    tech = _card()
    tl = QVBoxLayout(tech)
    tl.setContentsMargins(24, 22, 24, 22)
    tl.setSpacing(6)
    tl.addWidget(_label("ДВИЖОК", "cardKicker"))
    tl.addSpacing(2)
    tl.addWidget(_label("faster-whisper", "cardTitle"))
    tl.addWidget(
        _label("Python 3.11 · PySide6 · CTranslate2 · CUDA 12", "cardBody", wrap=True)
    )
    tl.addStretch(1)

    row.addWidget(author, 1)
    row.addWidget(tech, 1)
    outer.addLayout(row)

    files = _card()
    fl = QVBoxLayout(files)
    fl.setContentsMargins(24, 22, 24, 24)
    fl.setSpacing(6)
    fl.addWidget(_label("ФАЙЛЫ ПРИЛОЖЕНИЯ", "cardKicker"))
    fl.addSpacing(2)
    fl.addWidget(_label("Конфиг и данные", "cardTitle"))
    fl.addWidget(
        _label(
            "Конфигурация, словарь, модели и логи лежат в %APPDATA%\\WinWhisp\\.",
            "cardBody",
            wrap=True,
        )
    )
    fl.addSpacing(12)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(8)
    btn_row.setContentsMargins(0, 0, 0, 0)
    btn_row.addWidget(_link_button("Открыть config.yaml", lambda: _open_path(config_path())))
    btn_row.addWidget(_link_button("Открыть vocab.yaml", lambda: _open_path(vocab_path())))
    btn_row.addWidget(_link_button("Папка приложения", lambda: _open_path(appdata_dir())))
    btn_row.addStretch(1)
    fl.addLayout(btn_row)

    outer.addWidget(files)
    outer.addStretch(1)
    return page


def _build_placeholder(title: str, hint: str) -> QWidget:
    page = QWidget()
    outer = QVBoxLayout(page)
    outer.setContentsMargins(40, 36, 40, 36)
    outer.setSpacing(8)
    outer.addWidget(_label(title, "pageTitle"))
    outer.addWidget(_label(hint, "pageSub"))

    holder = _card()
    hl = QVBoxLayout(holder)
    hl.setContentsMargins(28, 32, 28, 32)
    hl.setSpacing(10)
    hl.addWidget(_label("Раздел в разработке", "cardTitle"))
    hl.addWidget(
        _label(
            "Скоро здесь появятся переключатели и поля для этой группы настроек.",
            "cardBody",
            wrap=True,
        )
    )
    outer.addSpacing(10)
    outer.addWidget(holder)
    outer.addStretch(1)
    return page


PAGE_FACTORIES: dict[str, tuple[str, str]] = {
    "model": ("Модель распознавания", "Whisper-движок и параметры декодирования."),
    "audio": ("Микрофон и запись", "Источник звука и логика VAD-чанков."),
    "inject": ("Вставка текста", "Поведение при смене фокуса и тайминги вставки."),
    "overlay": ("Внешний вид", "Pill-overlay и акцентный цвет."),
    "vocab": ("Словарь", "Hotwords, замены и стоп-фразы."),
    "logs": ("Логи и диагностика", "Просмотр лог-файлов и состояние модели."),
}


_INJECT_LABEL = {
    "inject": "вставлять",
    "notify": "уведомить",
    "skip": "пропустить",
}

_INJECT_DETAIL = {
    "inject": "всегда вставлять, даже после смены фокуса",
    "notify": "при смене фокуса показать pill «Вставить ещё раз»",
    "skip": "только копировать в буфер, не вставлять",
}


def _format_uptime(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _state_title(state: str, model_loaded: bool) -> str:
    if state == "loading" or not model_loaded and state == "idle":
        return "Подготовка модели" if state == "loading" else "Готов · модель в спячке"
    if state == "recording":
        return "Идёт запись"
    if state == "processing":
        return "Обрабатываю"
    return "Готов к диктовке"


def _audio_device_text(cfg: Config) -> tuple[str, str]:
    name = cfg.audio.device or "по умолчанию"
    sr = cfg.audio.samplerate / 1000
    chan = "моно" if cfg.audio.channels == 1 else f"{cfg.audio.channels} канала"
    return name, f"{sr:.0f} кГц · {chan}"


def _hotkey_pretty(combo: str) -> str:
    parts = [p.strip() for p in combo.split("+")]
    pretty = []
    for p in parts:
        low = p.lower()
        if low == "right ctrl":
            pretty.append("Right Ctrl")
        elif low == "left ctrl":
            pretty.append("Left Ctrl")
        elif low == "ctrl":
            pretty.append("Ctrl")
        elif low == "shift":
            pretty.append("Shift")
        elif low == "alt":
            pretty.append("Alt")
        else:
            pretty.append(p.capitalize())
    return " + ".join(pretty)


class _DashboardPage(QWidget):
    reload_requested = Signal()
    open_config_requested = Signal()
    open_vocab_requested = Signal()

    def __init__(self, runtime: AppRuntime, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runtime = runtime
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.setSpacing(14)

        outer.addWidget(_label("Дашборд", "pageTitle"))
        outer.addWidget(_label("Текущее состояние приложения и горячих параметров.", "pageSub"))
        outer.addSpacing(8)

        self._hero = self._build_hero()
        outer.addWidget(self._hero)

        self._components = self._build_components()
        outer.addWidget(self._components)

        outer.addSpacing(2)
        outer.addLayout(self._build_actions())
        outer.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _build_hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("heroCard")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(22, 20, 22, 20)
        hl.setSpacing(20)

        self._pulse_label = QLabel()
        self._pulse_label.setFixedSize(110, 110)
        self._pulse_pix_active = _make_pulse_pixmap(110, dim=False)
        self._pulse_pix_dim = _make_pulse_pixmap(110, dim=True)
        self._pulse_label.setPixmap(self._pulse_pix_active)
        hl.addWidget(self._pulse_label, 0, Qt.AlignVCenter | Qt.AlignLeft)

        text_box = QVBoxLayout()
        text_box.setSpacing(8)
        text_box.setContentsMargins(0, 6, 0, 6)

        self._hero_title = _label("Готов к диктовке", "heroTitle")
        text_box.addWidget(self._hero_title)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)
        sub_row.setContentsMargins(0, 0, 0, 0)
        sub_row.addWidget(_label("Зажмите", "heroSub"))
        self._hero_kbd = _kbd("Right Ctrl")
        sub_row.addWidget(self._hero_kbd)
        sub_row.addWidget(_label("и говорите.", "heroSub"))
        sub_row.addStretch(1)
        text_box.addLayout(sub_row)

        self._hero_sub2 = _label("Текст вставится в активное поле.", "heroSub")
        self._hero_sub2.setWordWrap(True)
        text_box.addWidget(self._hero_sub2)

        text_box.addSpacing(2)

        pill_row = QHBoxLayout()
        pill_row.setSpacing(6)
        pill_row.setContentsMargins(0, 0, 0, 0)
        self._pill_model = _pill("● модель в VRAM", kind="ok")
        self._pill_uptime = _pill("аптайм 00:00:00", kind="dim")
        pill_row.addWidget(self._pill_model)
        pill_row.addWidget(self._pill_uptime)
        pill_row.addStretch(1)
        text_box.addLayout(pill_row)

        hl.addLayout(text_box, 1)
        return hero

    def _build_components(self) -> QFrame:
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 14)
        cl.setSpacing(0)
        cl.addWidget(_label("КОМПОНЕНТЫ", "cardKicker"))
        cl.addSpacing(8)

        self._comp_rows: dict[str, dict[str, QLabel]] = {}
        rows_def = [
            ("model", "◇", "Whisper-модель"),
            ("audio", "◉", "Микрофон"),
            ("hotkey", "⌘", "Горячая клавиша"),
            ("inject", "↘", "Режим вставки"),
            ("vocab", "⌥", "Словарь"),
        ]
        for i, (key, icon, name) in enumerate(rows_def):
            row, refs = self._make_component_row(icon, name)
            self._comp_rows[key] = refs
            cl.addWidget(row)
            if i < len(rows_def) - 1:
                sep = QFrame()
                sep.setObjectName("rowSep")
                sep.setFixedHeight(1)
                cl.addWidget(sep)
        return card

    def _make_component_row(self, icon: str, name: str) -> tuple[QFrame, dict[str, QLabel]]:
        row = QFrame()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 10, 0, 10)
        rl.setSpacing(12)

        ic = QLabel(icon)
        ic.setObjectName("compIcon")
        ic.setFixedSize(30, 30)
        ic.setAlignment(Qt.AlignCenter)
        rl.addWidget(ic, 0, Qt.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        text_box.setContentsMargins(0, 0, 0, 0)
        name_lbl = _label(name, "compName")
        meta_lbl = _label("", "compMeta")
        text_box.addWidget(name_lbl)
        text_box.addWidget(meta_lbl)
        text_w = QWidget()
        text_w.setLayout(text_box)
        rl.addWidget(text_w, 1)

        right_box = QHBoxLayout()
        right_box.setSpacing(6)
        right_box.setContentsMargins(0, 0, 0, 0)
        kbd_lbl = _kbd("")
        kbd_lbl.hide()
        val_lbl = _label("", "compVal")
        val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_box.addStretch(1)
        right_box.addWidget(kbd_lbl)
        right_box.addWidget(val_lbl)
        right_w = QWidget()
        right_w.setLayout(right_box)
        rl.addWidget(right_w, 0)

        return row, {"meta": meta_lbl, "val": val_lbl, "kbd": kbd_lbl}

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 4, 0, 0)
        row.addWidget(_link_button("Открыть config.yaml", lambda: self.open_config_requested.emit()))
        row.addWidget(_link_button("Открыть словарь", lambda: self.open_vocab_requested.emit()))
        row.addStretch(1)
        row.addWidget(_primary_button("Перезагрузить конфиг", lambda: self.reload_requested.emit()))
        return row

    def refresh(self) -> None:
        cfg = self._runtime.cfg
        vocab = self._runtime.vocab
        state = self._runtime.state
        model_loaded = self._runtime.model_loaded

        self._hero_title.setText(_state_title(state, model_loaded))
        self._hero_kbd.setText(_hotkey_pretty(cfg.hotkey.combo))

        mode = cfg.injection.on_focus_change
        if mode == "notify":
            self._hero_sub2.setText(
                "При смене фокуса появится pill «Вставить ещё раз». Текст в буфере."
            )
        elif mode == "skip":
            self._hero_sub2.setText("Текст будет скопирован в буфер обмена.")
        else:
            self._hero_sub2.setText("Текст вставится в активное поле.")

        if model_loaded:
            self._pill_model.setText("● модель в VRAM")
            self._pill_model.setObjectName("pillOk")
        elif state == "loading":
            self._pill_model.setText("● загружается")
            self._pill_model.setObjectName("pillWarn")
        else:
            self._pill_model.setText("○ модель выгружена")
            self._pill_model.setObjectName("pillDim")
        self._pill_model.style().unpolish(self._pill_model)
        self._pill_model.style().polish(self._pill_model)

        self._pill_uptime.setText(f"аптайм {_format_uptime(self._runtime.uptime_s())}")

        self._pulse_label.setPixmap(
            self._pulse_pix_active if model_loaded else self._pulse_pix_dim
        )

        self._update_components(cfg, vocab, state, model_loaded)

    def _update_components(
        self, cfg: Config, vocab: Vocab, state: str, model_loaded: bool
    ) -> None:
        m = self._comp_rows["model"]
        m["meta"].setText(f"{cfg.asr.model} · {cfg.asr.device.upper()} · {cfg.asr.compute_type}")
        if model_loaded:
            m["val"].setText("загружена")
            m["val"].setObjectName("compVal")
        elif state == "loading":
            m["val"].setText("загружается…")
            m["val"].setObjectName("compValDim")
        else:
            m["val"].setText("выгружена")
            m["val"].setObjectName("compValDim")
        m["val"].style().unpolish(m["val"])
        m["val"].style().polish(m["val"])
        m["kbd"].hide()

        a = self._comp_rows["audio"]
        dev_name, dev_meta = _audio_device_text(cfg)
        a["meta"].setText(f"{dev_name} · {dev_meta}")
        if state == "recording":
            a["val"].setText("идёт запись")
        else:
            a["val"].setText("готов")
        a["kbd"].hide()

        h = self._comp_rows["hotkey"]
        h["meta"].setText(f"push-to-talk · debounce {cfg.hotkey.debounce_ms} мс")
        h["val"].setText("")
        h["kbd"].setText(_hotkey_pretty(cfg.hotkey.combo))
        h["kbd"].show()

        i = self._comp_rows["inject"]
        i["meta"].setText(_INJECT_DETAIL[cfg.injection.on_focus_change])
        i["val"].setText(_INJECT_LABEL[cfg.injection.on_focus_change])
        i["kbd"].hide()

        v = self._comp_rows["vocab"]
        n_hot = len(vocab.hotwords)
        n_repl = len(vocab.replacements)
        n_hall = len(vocab.hallucinations)
        v["meta"].setText(f"{n_hot} hotword · {n_repl} замен · {n_hall} стоп-фраз")
        v["val"].setText("активен" if (n_hot or n_repl or n_hall) else "пуст")
        v["kbd"].hide()


_MONTHS_RU = [
    "янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек",
]


def _ago_text(when: datetime, now: datetime) -> str:
    delta = now - when
    secs = int(delta.total_seconds())
    if secs < 0:
        return "—"
    if secs < 30:
        return "только что"
    if secs < 60:
        return f"{secs} с"
    mins = secs // 60
    if mins < 60:
        return f"{mins} мин"
    hours = mins // 60
    if hours < 24:
        return f"{hours} ч"
    days = (now.date() - when.date()).days
    if days == 1:
        return "вчера"
    return f"{days} дн"


def _day_section(when: datetime, now: datetime) -> str:
    today = now.date()
    d = when.date()
    diff = (today - d).days
    if diff == 0:
        return "Сегодня"
    if diff == 1:
        return "Вчера"
    return f"{d.day} {_MONTHS_RU[d.month - 1]}"


def _meta_text(entry: HistoryEntry) -> str:
    return f"·  {len(entry.text)} симв  ·  {entry.duration_s:.1f} с"


class _HistoryPage(QWidget):
    copy_requested = Signal(str)
    paste_requested = Signal(str)

    def __init__(self, history: HistoryStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history = history
        self._filter = "all"
        self._last_count = -1
        self._last_filter = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 16)
        head.setSpacing(12)

        head_left = QVBoxLayout()
        head_left.setContentsMargins(0, 0, 0, 0)
        head_left.setSpacing(3)
        head_left.addWidget(_label("История диктовок", "pageTitle"))
        self._sub_label = _label("Лог сессий ведётся в %APPDATA%\\WinWhisp\\history.jsonl", "pageSub")
        head_left.addWidget(self._sub_label)
        head.addLayout(head_left, 1)

        head.addWidget(self._build_filters(), 0, Qt.AlignBottom)
        outer.addLayout(head)

        self._list_holder = QWidget()
        self._list_layout = QVBoxLayout(self._list_holder)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        outer.addWidget(self._list_holder)
        outer.addStretch(1)

        history.subscribe(self._schedule_refresh)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30_000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

        self.refresh()

    def _build_filters(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("filterBar")
        fl = QHBoxLayout(bar)
        fl.setContentsMargins(3, 3, 3, 3)
        fl.setSpacing(2)
        self._filter_group = QButtonGroup(bar)
        self._filter_group.setExclusive(True)
        for key, name in (("all", "Все"), ("today", "Сегодня"), ("week", "Неделя")):
            b = QPushButton(name)
            b.setObjectName("filterBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            if key == self._filter:
                b.setChecked(True)
            b.clicked.connect(lambda _checked=False, k=key: self._set_filter(k))
            self._filter_group.addButton(b)
            fl.addWidget(b)
        return bar

    def _set_filter(self, key: str) -> None:
        if key == self._filter:
            return
        self._filter = key
        self.refresh(force=True)

    def _schedule_refresh(self) -> None:
        QTimer.singleShot(0, self.refresh)

    def _filtered_entries(self, now: datetime) -> list[HistoryEntry]:
        all_entries = self._history.all()
        if self._filter == "today":
            today = now.date()
            return [e for e in all_entries if e.when.date() == today]
        if self._filter == "week":
            cutoff = now.timestamp() - 7 * 24 * 3600
            return [e for e in all_entries if e.when.timestamp() >= cutoff]
        return all_entries

    def refresh(self, *, force: bool = False) -> None:
        count = self._history.count()
        if not force and count == self._last_count and self._filter == self._last_filter:
            self._update_ago_only()
            return
        self._last_count = count
        self._last_filter = self._filter

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        now = datetime.now()
        entries = self._filtered_entries(now)
        total = self._history.count()
        self._sub_label.setText(self._build_sub_text(total, len(entries)))

        if not entries:
            empty = _label(self._empty_text(), "historyEmpty")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            empty.setMinimumHeight(120)
            self._list_layout.addWidget(empty)
            return

        current_section = ""
        section_count = 0
        section_label: QLabel | None = None
        section_buckets: dict[str, int] = {}
        for e in entries:
            sec = _day_section(e.when, now)
            section_buckets[sec] = section_buckets.get(sec, 0) + 1

        for entry in entries:
            sec = _day_section(entry.when, now)
            if sec != current_section:
                if section_label is not None:
                    self._list_layout.addSpacing(6)
                current_section = sec
                section_count = section_buckets[sec]
                noun = self._record_noun(section_count)
                section_label = _label(f"{sec.upper()} · {section_count} {noun}", "daySep")
                holder = QWidget()
                hl = QHBoxLayout(holder)
                hl.setContentsMargins(2, 8, 2, 4)
                hl.addWidget(section_label)
                hl.addStretch(1)
                self._list_layout.addWidget(holder)
            self._list_layout.addWidget(self._make_item(entry, now))

    def _empty_text(self) -> str:
        if self._filter == "today":
            return "Сегодня ещё ничего не диктовали. Зажмите хоткей и говорите."
        if self._filter == "week":
            return "За последнюю неделю записей нет."
        return (
            "История пока пуста.\n"
            "Каждая успешная диктовка появится здесь и сохранится в history.jsonl."
        )

    def _build_sub_text(self, total: int, shown: int) -> str:
        if total == 0:
            return "Лог сессий ведётся в %APPDATA%\\WinWhisp\\history.jsonl"
        if self._filter == "all":
            return f"Всего записей: {total}"
        return f"Показано {shown} из {total}"

    @staticmethod
    def _record_noun(n: int) -> str:
        last = n % 10
        last2 = n % 100
        if 11 <= last2 <= 14:
            return "записей"
        if last == 1:
            return "запись"
        if 2 <= last <= 4:
            return "записи"
        return "записей"

    def _make_item(self, entry: HistoryEntry, now: datetime) -> QFrame:
        w = QFrame()
        w.setObjectName("historyItem")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        when_box = QVBoxLayout()
        when_box.setSpacing(1)
        when_box.setContentsMargins(0, 0, 0, 0)
        time_lbl = _label(entry.when.strftime("%H:%M"), "itemTime")
        time_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        ago_lbl = _label(_ago_text(entry.when, now), "itemAgo")
        ago_lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        when_box.addWidget(time_lbl)
        when_box.addWidget(ago_lbl)
        when_w = QWidget()
        when_w.setLayout(when_box)
        when_w.setFixedWidth(64)
        layout.addWidget(when_w, 0, Qt.AlignTop)
        when_w.setProperty("ago_label", ago_lbl)
        when_w.setProperty("entry_when", entry.when.isoformat())

        body = QVBoxLayout()
        body.setSpacing(3)
        body.setContentsMargins(0, 0, 0, 0)
        txt_lbl = _ElideLabel(entry.text, "itemTxt")
        txt_lbl.setToolTip(entry.text)
        body.addWidget(txt_lbl)
        body.addWidget(_label(_meta_text(entry), "itemMeta"))
        body_w = QWidget()
        body_w.setLayout(body)
        layout.addWidget(body_w, 1)

        acts = QHBoxLayout()
        acts.setSpacing(4)
        acts.setContentsMargins(0, 0, 0, 0)
        copy_btn = QPushButton("⧉")
        copy_btn.setObjectName("itemActBtn")
        copy_btn.setToolTip("Копировать в буфер")
        copy_btn.setFixedSize(28, 28)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(lambda _checked=False, t=entry.text: self.copy_requested.emit(t))
        acts.addWidget(copy_btn)

        paste_btn = QPushButton("↵")
        paste_btn.setObjectName("itemActBtn")
        paste_btn.setToolTip("Вставить в активное поле")
        paste_btn.setFixedSize(28, 28)
        paste_btn.setCursor(Qt.PointingHandCursor)
        paste_btn.clicked.connect(lambda _checked=False, t=entry.text: self.paste_requested.emit(t))
        acts.addWidget(paste_btn)

        acts_w = QWidget()
        acts_w.setLayout(acts)
        layout.addWidget(acts_w, 0, Qt.AlignTop)
        return w

    def _update_ago_only(self) -> None:
        now = datetime.now()
        for i in range(self._list_layout.count()):
            item = self._list_layout.itemAt(i)
            w = item.widget() if item is not None else None
            if w is None:
                continue
            for child in w.findChildren(QWidget):
                ago_lbl = child.property("ago_label")
                iso = child.property("entry_when")
                if ago_lbl is not None and iso:
                    try:
                        when = datetime.fromisoformat(iso)
                        ago_lbl.setText(_ago_text(when, now))
                    except ValueError:
                        pass


class SettingsWindow(QMainWindow):
    reload_requested = Signal()
    paste_text_requested = Signal(str)
    copy_text_requested = Signal(str)
    config_changed = Signal(dict)

    def __init__(
        self,
        runtime: AppRuntime | None = None,
        *,
        standalone: bool = False,
    ) -> None:
        super().__init__()
        self._standalone = standalone
        self._runtime = runtime or _default_runtime()
        self._pending_changes: dict[str, object] = {}
        self.setWindowTitle("WinWhisp")
        self.setStyleSheet(_STYLE)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._flush_save)

        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        w, h = 920, 600
        if avail is not None:
            self.resize(w, h)
            cx = avail.x() + (avail.width() - w) // 2
            cy = avail.y() + (avail.height() - h) // 2
            self.move(cx, cy)
        else:
            self.resize(w, h)
        self.setMinimumSize(880, 560)

        root = QWidget(self)
        root.setObjectName("root")
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = _Sidebar(self)
        layout.addWidget(self._sidebar)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName("content")
        layout.addWidget(self._stack, 1)

        self._pages: dict[str, int] = {}

        self._dashboard = _DashboardPage(self._runtime)
        self._dashboard.reload_requested.connect(self.reload_requested.emit)
        self._dashboard.open_config_requested.connect(lambda: _open_path(config_path()))
        self._dashboard.open_vocab_requested.connect(lambda: _open_path(vocab_path()))

        self._history_page = _HistoryPage(self._runtime.history)
        self._history_page.copy_requested.connect(self.copy_text_requested.emit)
        self._history_page.paste_requested.connect(self.paste_text_requested.emit)

        self._add_page("dashboard", self._dashboard)
        self._add_page("history", self._history_page)
        self._add_page("about", _build_about_page())
        self._add_page("general", self._build_general_page())
        for key, (title, hint) in PAGE_FACTORIES.items():
            self._add_page(key, _build_placeholder(title, hint))

        self._sidebar.page_changed.connect(self._on_page_change)
        self._sidebar.select("dashboard")

    def runtime(self) -> AppRuntime:
        return self._runtime

    def _add_page(self, key: str, widget: QWidget) -> None:
        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        idx = self._stack.addWidget(scroll)
        self._pages[key] = idx

    def _on_page_change(self, key: str) -> None:
        idx = self._pages.get(key)
        if idx is not None:
            self._stack.setCurrentIndex(idx)
        if key == "dashboard":
            self._dashboard.refresh()
        elif key == "history":
            self._history_page.refresh(force=True)

    def refresh_dashboard(self) -> None:
        self._dashboard.refresh()

    def _set_cfg_value(self, path: str, value) -> None:
        keys = path.split(".")
        obj = self._runtime.cfg
        for k in keys[:-1]:
            obj = getattr(obj, k)
        setattr(obj, keys[-1], value)
        self._pending_changes[path] = value
        self._save_timer.start()

    def _flush_save(self) -> None:
        try:
            save_config(self._runtime.cfg)
        except Exception:
            return
        if self._pending_changes:
            changes = dict(self._pending_changes)
            self._pending_changes.clear()
            self.config_changed.emit(changes)

    def _build_general_page(self) -> QWidget:
        cfg = self._runtime.cfg
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.setSpacing(8)

        outer.addWidget(_label("Общие", "pageTitle"))
        outer.addWidget(_label("Запуск, горячая клавиша, уведомления и логирование.", "pageSub"))
        outer.addSpacing(18)

        card = _card()
        body = QVBoxLayout(card)
        body.setContentsMargins(22, 6, 22, 14)
        body.setSpacing(0)

        autostart = _ToggleSwitch()
        autostart.setChecked(cfg.autostart)
        autostart.toggled.connect(lambda v: self._set_cfg_value("autostart", v))
        self._append_row(
            body,
            _setting_row(
                "Запускать вместе с Windows",
                "Автозагрузка через ярлык в shell:startup",
                autostart,
            ),
        )

        self._append_row(
            body,
            _setting_row(
                "Горячая клавиша",
                "Удерживайте, чтобы записывать",
                self._make_hotkey_control(cfg),
            ),
        )

        hold = _ValueSlider(0, 1000, cfg.hotkey.min_hold_ms)
        hold.valueChanged.connect(lambda v: self._set_cfg_value("hotkey.min_hold_ms", v))
        self._append_row(
            body,
            _setting_row(
                "Минимальное удержание",
                "Чтобы случайные нажатия не запускали запись",
                hold,
            ),
        )

        notif = _ToggleSwitch()
        notif.setChecked(cfg.tray.show_notifications)
        notif.toggled.connect(lambda v: self._set_cfg_value("tray.show_notifications", v))
        self._append_row(
            body,
            _setting_row(
                "Уведомления в трее",
                "Сообщать о готовности модели",
                notif,
            ),
        )

        err = _ToggleSwitch()
        err.setChecked(cfg.tray.notify_on_error)
        err.toggled.connect(lambda v: self._set_cfg_value("tray.notify_on_error", v))
        self._append_row(
            body,
            _setting_row(
                "Уведомлять об ошибках",
                "Показывать всплывающее окно при сбое",
                err,
            ),
        )

        log_combo = QComboBox()
        log_combo.setObjectName("select")
        log_combo.setCursor(Qt.PointingHandCursor)
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            log_combo.addItem(level)
        idx = log_combo.findText(cfg.log_level.upper())
        if idx >= 0:
            log_combo.setCurrentIndex(idx)
        log_combo.currentTextChanged.connect(lambda v: self._set_cfg_value("log_level", v))
        self._append_row(
            body,
            _setting_row(
                "Уровень логирования",
                "Логи в %APPDATA%\\WinWhisp\\logs\\",
                log_combo,
            ),
        )

        body.addSpacing(6)
        body.addWidget(_divider(dashed=True))

        disclosure = _Disclosure("Дополнительно (debounce, хвост)")

        debounce = _ValueSlider(0, 500, cfg.hotkey.debounce_ms)
        debounce.valueChanged.connect(lambda v: self._set_cfg_value("hotkey.debounce_ms", v))
        disclosure.add_row(
            _setting_row("Debounce", "Защита от двойных срабатываний", debounce)
        )

        tail = _ValueSlider(0, 1500, cfg.hotkey.release_tail_ms)
        tail.valueChanged.connect(lambda v: self._set_cfg_value("hotkey.release_tail_ms", v))
        disclosure.add_row(
            _setting_row(
                "Хвост после отпускания",
                "Пауза перед остановкой записи — поможет не обрезать конец фразы",
                tail,
            )
        )

        body.addWidget(disclosure)

        outer.addWidget(card)
        outer.addStretch(1)
        return page

    @staticmethod
    def _append_row(layout: QVBoxLayout, row: QWidget) -> None:
        if layout.count() > 0:
            layout.addWidget(_divider())
        layout.addWidget(row)

    def _make_hotkey_control(self, cfg: Config) -> QWidget:
        wrap = QWidget()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        kbd = _kbd(_hotkey_pretty(cfg.hotkey.combo))
        h.addWidget(kbd)

        edit = QPushButton("изменить")
        edit.setObjectName("kbdBtn")
        edit.setCursor(Qt.PointingHandCursor)
        edit.setToolTip(
            "Захват клавиши пока не реализован — отредактируйте config.yaml вручную"
        )
        edit.clicked.connect(lambda: _open_path(config_path()))
        h.addWidget(edit)
        return wrap

    def _apply_dark_titlebar(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            if not hwnd:
                return
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception:
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_dark_titlebar()
        self._dashboard.refresh()

    def closeEvent(self, event) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._flush_save()
        if self._standalone:
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()

    def open_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()


def _default_runtime() -> AppRuntime:
    return AppRuntime(cfg=Config(), vocab=Vocab())
