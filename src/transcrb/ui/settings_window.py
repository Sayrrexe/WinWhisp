from __future__ import annotations

import os
import re
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
    QPen,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from transcrb.asr.catalog import MODELS, model_label
from transcrb.asr.downloader import DownloaderThread
from transcrb.asr.file_manager import FileManager
from transcrb.config import Config, save_config
from transcrb.paths import appdata_dir, config_path, log_dir, models_dir, resources_dir, transcripts_dir, vocab_path
from transcrb.runtime import AppRuntime, HistoryEntry, HistoryStore
from transcrb.text.vocab import Vocab
from transcrb.ui.files_page import FILES_STYLE, FilesPage
from transcrb.ui.window_chrome import (
    FramelessMainWindow,
    LinkButton,
    PrimaryButton,
    TitleBar,
    chrome_stylesheet,
)


APP_VERSION = "0.1.4"
ACCENT = "#31D27A"

SIDEBAR_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "",
        [
            ("dashboard", "home", "Дашборд"),
            ("files", "files", "Файлы"),
            ("history", "history", "История"),
        ],
    ),
    (
        "Конфигурация",
        [
            ("general", "gear", "Общие"),
            ("model", "speaker", "Модель распознавания"),
            ("audio", "mic", "Микрофон и запись"),
            ("inject", "inject", "Вставка текста"),
            ("overlay", "eye", "Внешний вид"),
        ],
    ),
    (
        "Данные",
        [
            ("vocab", "book", "Словарь"),
            ("logs", "logs", "Логи и диагностика"),
        ],
    ),
]


_STYLE = """
* {
    font-family: "Inter", "Segoe UI Variable", "Segoe UI", sans-serif;
    color: #E8E8EA;
}

QMainWindow, QWidget#root { background: #1B1B1F; }

QWidget#sidebar {
    background: #16161A;
    border-right: 1px solid rgba(255, 255, 255, 0.10);
}

QLabel#sidebarGroup {
    color: #5A5C63;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 1.4px;
}
QFrame#sidebarSep {
    background: rgba(255, 255, 255, 0.05);
    max-height: 1px;
    min-height: 1px;
    border: none;
}
QLabel#sidebarFoot {
    color: #5A5C63;
    font-size: 11px;
    font-weight: 500;
}

QWidget#content { background: #1B1B1F; }

QLabel#pageTitle {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.4px;
}
QLabel#pageSub {
    color: #5A5C63;
    font-size: 13.5px;
}

QFrame#card {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
}
QLabel#cardTitle {
    font-size: 14px;
    font-weight: 600;
    color: #E8E8EA;
}
QLabel#cardKicker {
    color: #5A5C63;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
}
QLabel#cardBody { color: #9A9CA3; font-size: 13px; }
QLabel#cardMuted { color: #5A5C63; font-size: 12.5px; }

QPushButton#linkBtn {
    background: transparent;
    border: none;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton#primaryBtn {
    background: transparent;
    border: none;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 700;
}

QFrame#heroCard {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.10);
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
    background: #1F1F24;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-bottom: 2px solid rgba(0, 0, 0, 0.45);
    border-radius: 6px;
    padding: 3px 11px;
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
    font-weight: 600;
    color: #E8E8EA;
}

QLabel#pillOk {
    background: rgba(49, 210, 122, 0.14);
    border: 1px solid rgba(49, 210, 122, 0.30);
    color: #5FE89C;
    padding: 4px 12px;
    border-radius: 11px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#pillWarn {
    background: rgba(255, 178, 44, 0.14);
    border: 1px solid rgba(255, 178, 44, 0.30);
    color: #FFC766;
    padding: 4px 12px;
    border-radius: 11px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#pillDim {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #9A9CA3;
    padding: 4px 12px;
    border-radius: 11px;
    font-size: 12px;
    font-weight: 600;
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
    border: 1px solid rgba(255, 255, 255, 0.10);
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
QPushButton#filterBtn:checked { background: rgba(255, 255, 255, 0.06); color: #E8E8EA; }

QLabel#daySep {
    color: #5A5C63;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 1px;
}

QFrame#historyItem {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
}
QFrame#historyItem:hover {
    background: #17171B;
    border: 1px solid rgba(255, 255, 255, 0.18);
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
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 7px;
    color: #9A9CA3;
    font-size: 12px;
}
QPushButton#itemActBtn:hover { color: #4FE090; border: 1px solid rgba(49, 210, 122, 0.30); }

QLabel#historyEmpty {
    color: #5A5C63;
    font-size: 12.5px;
}

QLabel#rowTitle { color: #E8E8EA; font-size: 13.5px; font-weight: 600; }
QLabel#rowDesc { color: #5A5C63; font-size: 12px; }
QLabel#sliderVal {
    color: #C8CACE;
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
    font-weight: 600;
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
    height: 6px;
    background: #1F1F24;
    border-radius: 3px;
}
QSlider#hslider::sub-page:horizontal {
    background: #31D27A;
    border-radius: 3px;
}
QSlider#hslider::add-page:horizontal {
    background: #1F1F24;
    border-radius: 3px;
}
QSlider#hslider::handle:horizontal {
    background: #FFFFFF;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
    border: 2px solid rgba(255, 255, 255, 0.30);
}
QSlider#hslider::handle:horizontal:hover { background: #F0F0F0; border: 2px solid rgba(49, 210, 122, 0.55); }
QSlider#hslider::handle:horizontal:pressed { background: #E0E0E0; }

QComboBox#select {
    background: #1A1A1E;
    color: #E8E8EA;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 9px;
    padding: 8px 32px 8px 14px;
    font-size: 13px;
    font-weight: 500;
    min-width: 130px;
}
QComboBox#select:hover { border: 1px solid rgba(255, 255, 255, 0.18); background: #1F1F24; }
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
    color: #C8CACE;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 9px;
    padding: 7px 14px;
    font-size: 12.5px;
    font-weight: 600;
}
QPushButton#kbdBtn:hover { background: #222227; color: #E8E8EA; border: 1px solid rgba(255, 255, 255, 0.18); }
QPushButton#kbdBtn:pressed { background: #161619; }

QFrame#toast {
    background: #131316;
    border: 1px solid rgba(49, 210, 122, 0.32);
    border-radius: 10px;
}
QFrame#toast[kind="warn"] {
    border: 1px solid rgba(255, 178, 44, 0.35);
}
QLabel#toastIcon {
    color: #4FE090;
    font-size: 13px;
    font-weight: 700;
}
QLabel#toastIcon[kind="warn"] {
    color: #FFC766;
}
QLabel#toastText {
    color: #E8E8EA;
    font-size: 12.5px;
    font-weight: 500;
}

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 6px 3px; }
QScrollBar::handle:vertical { background: #232328; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #2D2D33; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QFrame#pathRow {
    background: transparent;
    border: none;
}
QFrame#pathRow:hover { background: rgba(255, 255, 255, 0.04); border-radius: 8px; }
QLabel#pathKicker {
    color: #5A5C63;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.1px;
}
QLabel#pathValue {
    color: #C8CACE;
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
    font-size: 11.5px;
}
QPushButton#pathBtn {
    background: #1A1A1E;
    color: #9A9CA3;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 7px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#pathBtn:hover { background: #222227; color: #E8E8EA; border: 1px solid rgba(255, 255, 255, 0.14); }

QPushButton#logToolBtn {
    background: #1A1A1E;
    color: #C8CACE;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 11.5px;
    font-weight: 600;
}
QPushButton#logToolBtn:hover { background: #222227; color: #E8E8EA; border: 1px solid rgba(255, 255, 255, 0.14); }
QPushButton#logToolBtn:checked {
    background: rgba(49, 210, 122, 0.16);
    color: #5FE89C;
    border: 1px solid rgba(49, 210, 122, 0.32);
}

QFrame#logFrame {
    background: #0E0E10;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
}

QPlainTextEdit#logViewer {
    background: transparent;
    color: #C8CACE;
    border: none;
    padding: 12px 14px;
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
    font-size: 11.5px;
    selection-background-color: rgba(49, 210, 122, 0.22);
}

QLabel#liveDot {
    color: #5FE89C;
    font-size: 13px;
    font-weight: 700;
}
QLabel#logFoot {
    color: #5A5C63;
    font-size: 11px;
    font-family: "JetBrains Mono", Consolas, "Cascadia Mono", monospace;
}
"""


def _make_logo_pixmap(size: int = 64) -> QPixmap:
    icon_file = resources_dir() / "icon.ico"
    if icon_file.exists():
        src = QPixmap(str(icon_file))
        if not src.isNull():
            return src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
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
    p.setBrush(QBrush(QColor("#1B1B1F")))
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


def _link_button(text: str, on_click) -> LinkButton:
    b = LinkButton(text)
    b.setObjectName("linkBtn")
    b.clicked.connect(on_click)
    return b


def _primary_button(text: str, on_click) -> PrimaryButton:
    b = PrimaryButton(text)
    b.setObjectName("primaryBtn")
    b.clicked.connect(on_click)
    return b


def _repolish(*widgets: QWidget) -> None:
    for w in widgets:
        w.style().unpolish(w)
        w.style().polish(w)


def _model_installed(key: str) -> bool:
    return (models_dir() / key / "model.bin").exists()


def _wrap_layout(layout) -> QWidget:
    w = QWidget()
    w.setLayout(layout)
    return w


_MODEL_INSTALLED_ROLE = Qt.UserRole + 17


class _ModelItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = option.rect
        bg_rect = QRectF(rect).adjusted(4, 2, -4, -2)

        if option.state & QStyle.State_Selected:
            path = QPainterPath()
            path.addRoundedRect(bg_rect, 7, 7)
            painter.fillPath(path, QColor(49, 210, 122, 38))
        elif option.state & QStyle.State_MouseOver:
            path = QPainterPath()
            path.addRoundedRect(bg_rect, 7, 7)
            painter.fillPath(path, QColor(255, 255, 255, 14))

        installed = bool(index.data(_MODEL_INSTALLED_ROLE))
        name = str(index.data(Qt.DisplayRole) or "")

        font = QFont(option.font)
        font.setPointSizeF(10.0)
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        painter.setPen(QColor("#E8E8EA"))
        painter.drawText(
            rect.adjusted(16, 0, -130, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            name,
        )

        right_inset = 14
        if installed:
            label = "установлена"
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(label)
            pad_x = 9
            dot_r = 3.0
            dot_gap = 7
            content_w = int(dot_r * 2 + dot_gap + text_w)
            pill_w = content_w + pad_x * 2
            pill_h = 20
            pill_x = rect.right() - right_inset - pill_w
            pill_y = rect.top() + (rect.height() - pill_h) // 2
            pill_rect = QRectF(pill_x, pill_y, pill_w, pill_h)

            pill_path = QPainterPath()
            pill_path.addRoundedRect(pill_rect, pill_h / 2, pill_h / 2)
            painter.fillPath(pill_path, QColor(49, 210, 122, 36))
            painter.setPen(QPen(QColor(49, 210, 122, 90), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(pill_path)

            dot_cx = pill_rect.left() + pad_x + dot_r
            dot_cy = pill_rect.center().y()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#31D27A"))
            painter.drawEllipse(QPointF(dot_cx, dot_cy), dot_r, dot_r)

            text_x = dot_cx + dot_r + dot_gap
            painter.setPen(QColor("#5FE89C"))
            painter.drawText(
                QRectF(text_x, pill_rect.top(), text_w + 2, pill_rect.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                label,
            )
        else:
            painter.setPen(QColor("#5A5C63"))
            painter.drawText(
                rect.adjusted(0, 0, -right_inset, 0),
                Qt.AlignVCenter | Qt.AlignRight,
                "не скачана",
            )

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        s = super().sizeHint(option, index)
        s.setHeight(36)
        s.setWidth(max(s.width(), 280))
        return s


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
    _TRACK_W = 50
    _TRACK_H = 28

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self._TRACK_W + 4, self._TRACK_H + 4)

    def sizeHint(self) -> QSize:
        return QSize(self._TRACK_W + 4, self._TRACK_H + 4)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        on = self.isChecked()
        ox = (self.width() - self._TRACK_W) / 2
        oy = (self.height() - self._TRACK_H) / 2
        track = QRectF(ox, oy, self._TRACK_W, self._TRACK_H)
        radius = self._TRACK_H / 2

        p.setPen(Qt.NoPen)

        if on:
            glow = QColor(ACCENT)
            glow.setAlphaF(0.22)
            p.setBrush(glow)
            p.drawRoundedRect(track.adjusted(-3, -3, 3, 3), radius + 3, radius + 3)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(track, radius, radius)
            p.setPen(QPen(QColor(0, 0, 0, 38), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), radius - 0.5, radius - 0.5)
        else:
            p.setBrush(QColor("#1F1F24"))
            p.drawRoundedRect(track, radius, radius)
            p.setPen(QPen(QColor(255, 255, 255, 26), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5), radius - 0.5, radius - 0.5)

        thumb_d = self._TRACK_H - 6
        thumb_y = oy + (self._TRACK_H - thumb_d) / 2
        thumb_x = ox + (self._TRACK_W - thumb_d - 3) if on else ox + 3

        p.setPen(Qt.NoPen)
        shadow = QColor(0, 0, 0, 60)
        p.setBrush(shadow)
        p.drawEllipse(QRectF(thumb_x, thumb_y + 1, thumb_d, thumb_d))

        p.setBrush(QColor("#FFFFFF" if on else "#D6D7DB"))
        p.drawEllipse(QRectF(thumb_x, thumb_y, thumb_d, thumb_d))

        if on:
            check = QPen(QColor(ACCENT), 2.0)
            check.setCapStyle(Qt.RoundCap)
            check.setJoinStyle(Qt.RoundJoin)
            p.setPen(check)
            cx = thumb_x + thumb_d / 2
            cy = thumb_y + thumb_d / 2
            p.drawLine(QPointF(cx - 4, cy), QPointF(cx - 1, cy + 3))
            p.drawLine(QPointF(cx - 1, cy + 3), QPointF(cx + 4, cy - 3))

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


def _draw_side_icon(p: QPainter, name: str, rect: QRectF, color: QColor) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(color, 1.7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    x = rect.x()
    y = rect.y()
    s = min(rect.width(), rect.height())
    cx = x + rect.width() / 2
    cy = y + rect.height() / 2

    if name == "home":
        roof_top = QPointF(cx, cy - s * 0.36)
        left = QPointF(cx - s * 0.40, cy - s * 0.04)
        right = QPointF(cx + s * 0.40, cy - s * 0.04)
        path = QPainterPath()
        path.moveTo(left)
        path.lineTo(roof_top)
        path.lineTo(right)
        p.drawPath(path)
        body = QRectF(cx - s * 0.32, cy - s * 0.04, s * 0.64, s * 0.42)
        p.drawRoundedRect(body, 1.5, 1.5)
        door = QRectF(cx - s * 0.10, cy + s * 0.10, s * 0.20, s * 0.28)
        p.drawRoundedRect(door, 1.0, 1.0)

    elif name == "history":
        radius = s * 0.36
        ring = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        path = QPainterPath()
        path.arcMoveTo(ring, 70)
        path.arcTo(ring, 70, 290)
        p.drawPath(path)
        tip_angle = 70.0
        import math
        tip_x = cx + radius * math.cos(math.radians(tip_angle))
        tip_y = cy - radius * math.sin(math.radians(tip_angle))
        arrow = QPainterPath()
        arrow.moveTo(QPointF(tip_x - s * 0.10, tip_y - s * 0.04))
        arrow.lineTo(QPointF(tip_x, tip_y))
        arrow.lineTo(QPointF(tip_x + s * 0.04, tip_y - s * 0.10))
        p.drawPath(arrow)
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy - s * 0.20))
        p.drawLine(QPointF(cx, cy), QPointF(cx + s * 0.16, cy + s * 0.04))

    elif name == "gear":
        import math
        outer = s * 0.40
        inner = s * 0.30
        tooth = s * 0.08
        teeth = 8
        path = QPainterPath()
        for i in range(teeth):
            a = (i * 360 / teeth) - 90
            ar = math.radians(a)
            x1 = cx + (outer + tooth * 0.4) * math.cos(ar - math.radians(7))
            y1 = cy + (outer + tooth * 0.4) * math.sin(ar - math.radians(7))
            x2 = cx + (outer + tooth) * math.cos(ar)
            y2 = cy + (outer + tooth) * math.sin(ar)
            x3 = cx + (outer + tooth * 0.4) * math.cos(ar + math.radians(7))
            y3 = cy + (outer + tooth * 0.4) * math.sin(ar + math.radians(7))
            if i == 0:
                path.moveTo(QPointF(x1, y1))
            else:
                path.lineTo(QPointF(x1, y1))
            path.lineTo(QPointF(x2, y2))
            path.lineTo(QPointF(x3, y3))
            next_a = ((i + 1) * 360 / teeth) - 90
            mid = math.radians((a + next_a) / 2 + 4)
            mx = cx + outer * math.cos(mid)
            my = cy + outer * math.sin(mid)
            path.lineTo(QPointF(mx, my))
        path.closeSubpath()
        p.drawPath(path)
        hole = QRectF(cx - inner * 0.45, cy - inner * 0.45, inner * 0.9, inner * 0.9)
        p.drawEllipse(hole)

    elif name == "speaker":
        head_r = s * 0.13
        head = QRectF(cx - head_r - s * 0.08, cy - s * 0.30, head_r * 2, head_r * 2)
        p.drawEllipse(head)
        torso = QPainterPath()
        tx = cx - s * 0.08
        torso.moveTo(QPointF(tx - s * 0.18, cy + s * 0.22))
        torso.cubicTo(
            QPointF(tx - s * 0.18, cy - s * 0.06),
            QPointF(tx + s * 0.18, cy - s * 0.06),
            QPointF(tx + s * 0.18, cy + s * 0.22),
        )
        p.drawPath(torso)
        bx = cx + s * 0.10
        by1 = cy - s * 0.24
        by2 = cy - s * 0.10
        by3 = cy + s * 0.04
        line_w_short = s * 0.16
        line_w_long = s * 0.26
        p.drawLine(QPointF(bx, by1), QPointF(bx + line_w_long, by1))
        p.drawLine(QPointF(bx, by2), QPointF(bx + line_w_short, by2))
        p.drawLine(QPointF(bx, by3), QPointF(bx + line_w_long * 0.75, by3))

    elif name == "mic":
        cap = QRectF(cx - s * 0.14, cy - s * 0.34, s * 0.28, s * 0.42)
        p.drawRoundedRect(cap, s * 0.14, s * 0.14)
        arc = QRectF(cx - s * 0.26, cy - s * 0.18, s * 0.52, s * 0.46)
        path = QPainterPath()
        path.arcMoveTo(arc, 200)
        path.arcTo(arc, 200, 140)
        p.drawPath(path)
        p.drawLine(QPointF(cx, cy + s * 0.20), QPointF(cx, cy + s * 0.34))
        p.drawLine(
            QPointF(cx - s * 0.12, cy + s * 0.34),
            QPointF(cx + s * 0.12, cy + s * 0.34),
        )

    elif name == "inject":
        field = QRectF(cx - s * 0.34, cy + s * 0.04, s * 0.68, s * 0.30)
        p.drawRoundedRect(field, 2.0, 2.0)
        caret_x = cx - s * 0.20
        p.drawLine(
            QPointF(caret_x, cy + s * 0.10),
            QPointF(caret_x, cy + s * 0.28),
        )
        arrow = QPainterPath()
        arrow.moveTo(QPointF(cx, cy - s * 0.34))
        arrow.lineTo(QPointF(cx, cy - s * 0.02))
        p.drawPath(arrow)
        head = QPainterPath()
        head.moveTo(QPointF(cx - s * 0.10, cy - s * 0.12))
        head.lineTo(QPointF(cx, cy - s * 0.02))
        head.lineTo(QPointF(cx + s * 0.10, cy - s * 0.12))
        p.drawPath(head)

    elif name == "eye":
        path = QPainterPath()
        left = QPointF(cx - s * 0.40, cy)
        right = QPointF(cx + s * 0.40, cy)
        path.moveTo(left)
        path.cubicTo(
            QPointF(cx - s * 0.20, cy - s * 0.30),
            QPointF(cx + s * 0.20, cy - s * 0.30),
            right,
        )
        path.cubicTo(
            QPointF(cx + s * 0.20, cy + s * 0.30),
            QPointF(cx - s * 0.20, cy + s * 0.30),
            left,
        )
        p.drawPath(path)
        pupil = QRectF(cx - s * 0.13, cy - s * 0.13, s * 0.26, s * 0.26)
        p.drawEllipse(pupil)
        p.save()
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        glint = QRectF(cx - s * 0.06, cy - s * 0.06, s * 0.12, s * 0.12)
        p.drawEllipse(glint)
        p.restore()

    elif name == "book":
        spine_x = cx
        top = cy - s * 0.30
        bottom = cy + s * 0.30
        left_page = QPainterPath()
        left_page.moveTo(QPointF(cx - s * 0.36, top + s * 0.04))
        left_page.lineTo(QPointF(spine_x - s * 0.02, top + s * 0.10))
        left_page.lineTo(QPointF(spine_x - s * 0.02, bottom))
        left_page.lineTo(QPointF(cx - s * 0.36, bottom - s * 0.04))
        left_page.closeSubpath()
        p.drawPath(left_page)
        right_page = QPainterPath()
        right_page.moveTo(QPointF(cx + s * 0.36, top + s * 0.04))
        right_page.lineTo(QPointF(spine_x + s * 0.02, top + s * 0.10))
        right_page.lineTo(QPointF(spine_x + s * 0.02, bottom))
        right_page.lineTo(QPointF(cx + s * 0.36, bottom - s * 0.04))
        right_page.closeSubpath()
        p.drawPath(right_page)
        p.drawLine(
            QPointF(cx - s * 0.28, cy - s * 0.04),
            QPointF(cx - s * 0.10, cy - s * 0.02),
        )
        p.drawLine(
            QPointF(cx + s * 0.10, cy - s * 0.02),
            QPointF(cx + 0.28 * s, cy - s * 0.04),
        )
        p.drawLine(
            QPointF(cx - s * 0.28, cy + s * 0.10),
            QPointF(cx - s * 0.12, cy + s * 0.12),
        )
        p.drawLine(
            QPointF(cx + s * 0.12, cy + s * 0.12),
            QPointF(cx + s * 0.28, cy + s * 0.10),
        )

    elif name == "logs":
        outer = QRectF(cx - s * 0.34, cy - s * 0.34, s * 0.68, s * 0.68)
        p.drawRoundedRect(outer, 3.0, 3.0)
        p.drawLine(
            QPointF(cx - s * 0.20, cy - s * 0.16),
            QPointF(cx + s * 0.20, cy - s * 0.16),
        )
        p.drawLine(
            QPointF(cx - s * 0.20, cy),
            QPointF(cx + s * 0.10, cy),
        )
        p.drawLine(
            QPointF(cx - s * 0.20, cy + s * 0.16),
            QPointF(cx + s * 0.20, cy + s * 0.16),
        )

    elif name == "files":
        body = QRectF(cx - s * 0.30, cy - s * 0.34, s * 0.46, s * 0.68)
        path = QPainterPath()
        path.moveTo(QPointF(body.left(), body.top()))
        path.lineTo(QPointF(body.right() - s * 0.14, body.top()))
        path.lineTo(QPointF(body.right(), body.top() + s * 0.14))
        path.lineTo(QPointF(body.right(), body.bottom()))
        path.lineTo(QPointF(body.left(), body.bottom()))
        path.closeSubpath()
        p.drawPath(path)
        fold = QPainterPath()
        fold.moveTo(QPointF(body.right() - s * 0.14, body.top()))
        fold.lineTo(QPointF(body.right() - s * 0.14, body.top() + s * 0.14))
        fold.lineTo(QPointF(body.right(), body.top() + s * 0.14))
        p.drawPath(fold)
        arrow_x = cx - s * 0.04
        arrow_top = cy + s * 0.04
        arrow_bot = cy + s * 0.20
        p.drawLine(QPointF(arrow_x, arrow_top), QPointF(arrow_x, arrow_bot))
        head = QPainterPath()
        head.moveTo(QPointF(arrow_x - s * 0.10, arrow_bot - s * 0.10))
        head.lineTo(QPointF(arrow_x, arrow_bot))
        head.lineTo(QPointF(arrow_x + s * 0.10, arrow_bot - s * 0.10))
        p.drawPath(head)

    p.restore()


class _SideItem(QAbstractButton):
    def __init__(self, key: str, icon: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._icon = icon
        self._title = title
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def key(self) -> str:
        return self._key

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        active = self.isChecked()
        hovered = self.underMouse()

        rect = QRectF(self.rect())
        body = rect.adjusted(8, 2, -8, -2)

        p.setPen(Qt.NoPen)
        if active:
            p.setBrush(QColor(49, 210, 122, 38))
            p.drawRoundedRect(body, 10, 10)
        elif hovered:
            p.setBrush(QColor(255, 255, 255, 14))
            p.drawRoundedRect(body, 10, 10)

        if active:
            bar = QRectF(body.left() + 3, body.top() + 9, 3, body.height() - 18)
            p.setBrush(QColor(ACCENT))
            p.drawRoundedRect(bar, 1.5, 1.5)

        text_color = QColor("#FFFFFF") if active else (
            QColor("#E8E8EA") if hovered else QColor("#B0B2B8")
        )
        icon_color = QColor("#5FE89C") if active else (
            QColor("#E8E8EA") if hovered else QColor("#9A9CA3")
        )

        icon_left = body.left() + 14
        icon_size = 20.0
        icon_rect = QRectF(
            icon_left,
            body.top() + (body.height() - icon_size) / 2,
            icon_size,
            icon_size,
        )
        _draw_side_icon(p, self._icon, icon_rect, icon_color)

        text_x = icon_left + icon_size + 14
        text_rect = QRectF(text_x, body.top(), body.right() - text_x - 10, body.height())
        text_font = QFont("Segoe UI Variable Display", 0)
        if not text_font.exactMatch():
            text_font = QFont("Segoe UI", 0)
        text_font.setPixelSize(13)
        text_font.setBold(True)
        p.setFont(text_font)
        p.setPen(text_color)

        fm = p.fontMetrics()
        elided = fm.elidedText(self._title, Qt.ElideRight, int(text_rect.width()))
        p.drawText(text_rect, int(Qt.AlignVCenter | Qt.AlignLeft), elided)

        p.end()


class _Sidebar(QWidget):
    page_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(248)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 16, 0, 0)
        root.setSpacing(0)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, _SideItem] = {}

        for idx, (group_title, items) in enumerate(SIDEBAR_GROUPS):
            if idx > 0:
                root.addSpacing(14)
            if group_title:
                kicker_wrap = QWidget()
                kw = QHBoxLayout(kicker_wrap)
                kw.setContentsMargins(22, 6, 22, 8)
                kw.addWidget(_label(group_title.upper(), "sidebarGroup"))
                kw.addStretch(1)
                root.addWidget(kicker_wrap)
            for key, icon, title in items:
                item = _SideItem(key, icon, title)
                item.clicked.connect(lambda _checked=False, k=key: self.page_changed.emit(k))
                self._group.addButton(item)
                self._buttons[key] = item
                root.addWidget(item)

        root.addStretch(1)

        sep = QFrame()
        sep.setObjectName("sidebarSep")
        sep.setFixedHeight(1)
        sep_wrap = QWidget()
        sw = QHBoxLayout(sep_wrap)
        sw.setContentsMargins(18, 0, 18, 0)
        sw.addWidget(sep)
        root.addWidget(sep_wrap)

        footer_wrap = QWidget()
        fw = QHBoxLayout(footer_wrap)
        fw.setContentsMargins(22, 14, 22, 16)
        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("sidebarFoot")
        author = QLabel("Sayrrexe")
        author.setObjectName("sidebarFoot")
        author.setAlignment(Qt.AlignRight)
        fw.addWidget(ver)
        fw.addStretch(1)
        fw.addWidget(author)
        root.addWidget(footer_wrap)

    def select(self, key: str, *, emit: bool = True) -> None:
        btn = self._buttons.get(key)
        if btn is None:
            return
        btn.setChecked(True)
        if emit:
            self.page_changed.emit(key)


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
    "audio": ("Микрофон и запись", "Источник звука и логика VAD-чанков."),
    "inject": ("Вставка текста", "Поведение при смене фокуса и тайминги вставки."),
    "overlay": ("Внешний вид", "Pill-overlay и акцентный цвет."),
    "vocab": ("Словарь", "Hotwords, замены и стоп-фразы."),
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
        meta_lbl = _label("", "compMeta")
        text_box.addWidget(_label(name, "compName"))
        text_box.addWidget(meta_lbl)
        rl.addWidget(_wrap_layout(text_box), 1)

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
        rl.addWidget(_wrap_layout(right_box), 0)

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
        _repolish(self._pill_model)

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
        _repolish(m["val"])
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
        when_w = _wrap_layout(when_box)
        when_w.setFixedWidth(64)
        when_w.setProperty("ago_label", ago_lbl)
        when_w.setProperty("entry_when", entry.when.isoformat())
        layout.addWidget(when_w, 0, Qt.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(3)
        body.setContentsMargins(0, 0, 0, 0)
        txt_lbl = _ElideLabel(entry.text, "itemTxt")
        txt_lbl.setToolTip(entry.text)
        body.addWidget(txt_lbl)
        body.addWidget(_label(_meta_text(entry), "itemMeta"))
        layout.addWidget(_wrap_layout(body), 1)

        acts = QHBoxLayout()
        acts.setSpacing(4)
        acts.setContentsMargins(0, 0, 0, 0)
        acts.addWidget(self._make_act_btn("⧉", "Копировать в буфер", entry.text, self.copy_requested))
        acts.addWidget(self._make_act_btn("↵", "Вставить в активное поле", entry.text, self.paste_requested))
        layout.addWidget(_wrap_layout(acts), 0, Qt.AlignTop)
        return w

    @staticmethod
    def _make_act_btn(icon: str, tooltip: str, text: str, signal) -> QPushButton:
        b = QPushButton(icon)
        b.setObjectName("itemActBtn")
        b.setToolTip(tooltip)
        b.setFixedSize(28, 28)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _checked=False, t=text: signal.emit(t))
        return b

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


def _fmt_bytes(n: int) -> str:
    if n <= 0:
        return "—"
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    return f"{n / 1024:.0f} KB"


_LOG_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})"
    r" \| (?P<level>[A-Z]+)\s*\|"
    r" (?P<loc>[^-]+) - (?P<msg>.*)$"
)

_LEVEL_COLORS: dict[str, str] = {
    "TRACE":    "#7A7C84",
    "DEBUG":    "#7AA8FF",
    "INFO":     "#5FE89C",
    "SUCCESS":  "#5FE89C",
    "WARNING":  "#FFC766",
    "ERROR":    "#FF7A7A",
    "CRITICAL": "#FF5D5D",
}

_LEVEL_ORDER = ("DEBUG", "INFO", "WARNING", "ERROR")
_LEVEL_RANK = {lvl: i for i, lvl in enumerate(_LEVEL_ORDER)}


class _LogEntry:
    __slots__ = ("ts", "level", "loc", "msg", "extra")

    def __init__(self, ts: str, level: str, loc: str, msg: str) -> None:
        self.ts = ts
        self.level = level
        self.loc = loc
        self.msg = msg
        self.extra: list[str] = []

    def matches_level(self, min_level: str) -> bool:
        if min_level == "ALL":
            return True
        rank = _LEVEL_RANK.get(self.level.upper(), -1)
        return rank >= _LEVEL_RANK.get(min_level, 0)

    def render(self) -> str:
        head = f"{self.ts.split(' ', 1)[1]}  {self.level:<7}  {self.loc.strip()}  {self.msg}"
        if not self.extra:
            return head
        return head + "\n" + "\n".join(f"        {line}" for line in self.extra)


class _LogHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self._fmt_ts = self._fmt("#5A5C63")
        self._fmt_loc = self._fmt("#7AA8FF", italic=True)
        self._level_fmts: dict[str, QTextCharFormat] = {
            lvl: self._fmt(color, bold=True) for lvl, color in _LEVEL_COLORS.items()
        }
        self._fmt_msg = self._fmt("#E8E8EA")
        self._fmt_msg_warn = self._fmt("#FFC766")
        self._fmt_msg_err = self._fmt("#FF9C9C")
        self._fmt_extra = self._fmt("#9A9CA3")

    @staticmethod
    def _fmt(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Bold)
        if italic:
            f.setFontItalic(True)
        return f

    def highlightBlock(self, text: str) -> None:
        if not text:
            return
        if text.startswith("        "):
            self.setFormat(0, len(text), self._fmt_extra)
            return

        if len(text) < 18 or text[2] != ":" or text[5] != ":":
            self.setFormat(0, len(text), self._fmt_msg)
            return

        i = 0
        ts_end = 12
        self.setFormat(i, ts_end, self._fmt_ts)
        i = ts_end
        while i < len(text) and text[i] == " ":
            i += 1

        level_start = i
        while i < len(text) and text[i] != " ":
            i += 1
        level = text[level_start:i].upper()
        lvl_fmt = self._level_fmts.get(level, self._fmt_msg)
        self.setFormat(level_start, i - level_start, lvl_fmt)

        while i < len(text) and text[i] == " ":
            i += 1

        loc_start = i
        while i < len(text) and text[i] != " ":
            i += 1
        self.setFormat(loc_start, i - loc_start, self._fmt_loc)

        if i < len(text):
            msg_fmt = self._fmt_msg
            if level == "WARNING":
                msg_fmt = self._fmt_msg_warn
            elif level in ("ERROR", "CRITICAL"):
                msg_fmt = self._fmt_msg_err
            self.setFormat(i, len(text) - i, msg_fmt)


def _path_row(kicker: str, path: Path, *, open_label: str = "Открыть") -> QFrame:
    row = QFrame()
    row.setObjectName("pathRow")
    h = QHBoxLayout(row)
    h.setContentsMargins(10, 8, 10, 8)
    h.setSpacing(12)

    box = QVBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    box.addWidget(_label(kicker, "pathKicker"))
    val = _ElideLabel(str(path), "pathValue")
    val.setToolTip(str(path))
    box.addWidget(val)
    h.addLayout(box, 1)

    btn = QPushButton(open_label)
    btn.setObjectName("pathBtn")
    btn.setCursor(Qt.PointingHandCursor)
    btn.clicked.connect(lambda _checked=False, p=path: _open_path(p))
    h.addWidget(btn, 0, Qt.AlignVCenter)
    return row


class _LogsPage(QWidget):
    _MAX_BUFFER = 1500
    _INITIAL_TAIL_BYTES = 256 * 1024
    _POLL_MS = 1000

    def __init__(self, runtime: AppRuntime, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runtime = runtime
        self._log_path = log_dir() / "winwhisp.log"
        self._buffer: list[_LogEntry] = []
        self._last_size = 0
        self._last_mtime = 0.0
        self._level_filter = "ALL"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.setSpacing(14)

        outer.addWidget(_label("Логи и диагностика", "pageTitle"))
        outer.addSpacing(4)

        outer.addWidget(self._build_paths_card())
        outer.addLayout(self._build_toolbar())
        outer.addWidget(self._build_log_frame(), 1)
        outer.addWidget(self._foot, 0, Qt.AlignRight)

        self._highlighter = _LogHighlighter(self._viewer.document())

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._POLL_MS)
        self._poll_timer.timeout.connect(self._tick)

        self._reload_full()
        self._render()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._poll_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._poll_timer.stop()

    def _build_paths_card(self) -> QFrame:
        card = _card()
        v = QVBoxLayout(card)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(2)

        v.addWidget(_path_row("ЛОГ-ФАЙЛ", self._log_path, open_label="Открыть"))
        v.addWidget(_divider())
        v.addWidget(_path_row("ПАПКА ДАННЫХ", appdata_dir(), open_label="Проводник"))
        v.addWidget(_divider())
        v.addWidget(_path_row("КОНФИГ", config_path(), open_label="Открыть"))
        v.addWidget(_divider())
        v.addWidget(_path_row("МОДЕЛИ", models_dir(), open_label="Проводник"))
        return card

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 4, 0, 0)
        bar.setSpacing(10)

        self._live_dot = QLabel("●")
        self._live_dot.setObjectName("liveDot")
        bar.addWidget(self._live_dot, 0, Qt.AlignVCenter)

        live_lbl = _label("LIVE", "cardKicker")
        bar.addWidget(live_lbl, 0, Qt.AlignVCenter)

        bar.addStretch(1)

        filt = QFrame()
        filt.setObjectName("filterBar")
        fl = QHBoxLayout(filt)
        fl.setContentsMargins(3, 3, 3, 3)
        fl.setSpacing(2)
        self._level_group = QButtonGroup(filt)
        self._level_group.setExclusive(True)
        for key, name in (
            ("ALL", "Все"),
            ("DEBUG", "Debug"),
            ("INFO", "Info"),
            ("WARNING", "Warn"),
            ("ERROR", "Error"),
        ):
            b = QPushButton(name)
            b.setObjectName("filterBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            if key == self._level_filter:
                b.setChecked(True)
            b.clicked.connect(lambda _checked=False, k=key: self._set_level(k))
            self._level_group.addButton(b)
            fl.addWidget(b)
        bar.addWidget(filt, 0, Qt.AlignVCenter)

        open_btn = QPushButton("Открыть файл")
        open_btn.setObjectName("logToolBtn")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(lambda: _open_path(self._log_path))
        bar.addWidget(open_btn, 0, Qt.AlignVCenter)

        return bar

    def _build_log_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("logFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        self._viewer = QPlainTextEdit()
        self._viewer.setObjectName("logViewer")
        self._viewer.setReadOnly(True)
        self._viewer.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._viewer.setMaximumBlockCount(self._MAX_BUFFER * 4)
        self._viewer.setMinimumHeight(280)
        fl.addWidget(self._viewer)

        self._foot = _label("—", "logFoot")
        return frame

    def _set_level(self, key: str) -> None:
        if key == self._level_filter:
            return
        self._level_filter = key
        self._render()

    def _tick(self) -> None:
        try:
            if not self._log_path.exists():
                if self._buffer:
                    self._buffer.clear()
                    self._last_size = 0
                    self._last_mtime = 0.0
                    self._render()
                return

            stat = self._log_path.stat()
            size = stat.st_size
            mtime = stat.st_mtime

            if size < self._last_size or mtime < self._last_mtime - 1.0:
                self._reload_full()
                self._render()
                return

            if size == self._last_size:
                return

            with self._log_path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(self._last_size)
                chunk = f.read()
            self._last_size = size
            self._last_mtime = mtime
            self._consume_text(chunk)
            self._render()
        except OSError:
            return

    def _reload_full(self) -> None:
        self._buffer.clear()
        self._last_size = 0
        self._last_mtime = 0.0
        if not self._log_path.exists():
            return
        try:
            stat = self._log_path.stat()
            size = stat.st_size
            offset = max(0, size - self._INITIAL_TAIL_BYTES)
            with self._log_path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                if offset > 0:
                    f.readline()
                text = f.read()
            self._last_size = size
            self._last_mtime = stat.st_mtime
            self._consume_text(text)
        except OSError:
            return

    def _consume_text(self, text: str) -> None:
        if not text:
            return
        for raw in text.splitlines():
            line = raw.rstrip("\r")
            if not line:
                continue
            m = _LOG_LINE_RE.match(line)
            if m is None:
                if self._buffer:
                    self._buffer[-1].extra.append(line)
                continue
            entry = _LogEntry(
                m.group("ts"), m.group("level"), m.group("loc"), m.group("msg")
            )
            self._buffer.append(entry)
            if len(self._buffer) > self._MAX_BUFFER:
                self._buffer.pop(0)

    def _render(self) -> None:
        if not self._log_path.exists():
            self._viewer.setPlainText(
                "Лог-файл ещё не создан. Он появится после первой записи приложения."
            )
            self._foot.setText("файл отсутствует")
            return

        if not self._buffer:
            self._viewer.setPlainText("Лог пуст.")
            self._foot.setText(f"{_fmt_bytes(self._last_size)} · 0 строк")
            return

        filtered = [e for e in self._buffer if e.matches_level(self._level_filter)]

        scrollbar = self._viewer.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 4

        if filtered:
            text = "\n".join(e.render() for e in filtered)
        else:
            text = "Под текущий фильтр и поиск ничего не подходит."
        self._viewer.setPlainText(text)

        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())

        total = len(self._buffer)
        shown = len(filtered)
        suffix = ""
        if self._level_filter != "ALL":
            suffix = f"   фильтр: {self._level_filter.lower()}"
        self._foot.setText(
            f"{_fmt_bytes(self._last_size)} · показано {shown} из {total} строк{suffix}"
        )


class _Toast(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setProperty("kind", "ok")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 9, 16, 9)
        h.setSpacing(10)

        self._icon = QLabel("✓")
        self._icon.setObjectName("toastIcon")
        self._icon.setProperty("kind", "ok")
        h.addWidget(self._icon)

        self._text = QLabel("")
        self._text.setObjectName("toastText")
        h.addWidget(self._text)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, *, kind: str = "ok", ms: int = 2400) -> None:
        self._text.setText(text)
        self.setProperty("kind", kind)
        self._icon.setProperty("kind", kind)
        self._icon.setText("✓" if kind == "ok" else "!")
        _repolish(self, self._icon)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(ms)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(20, (parent.width() - self.width()) // 2)
        y = parent.height() - self.height() - 24
        self.move(x, y)


class ModelDownloadDialog(QDialog):
    def __init__(self, model_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = model_key
        self._thread: DownloaderThread | None = None
        self._done = False

        self.setWindowTitle("Скачивание модели")
        self.setModal(True)
        self.setFixedSize(440, 260)
        self.setStyleSheet(
            "QDialog { background: #1B1B1F; }"
            "QLabel#h { color: #E8E8EA; font-size: 16px; font-weight: 600; letter-spacing: -0.2px; }"
            "QLabel#k { color: #5A5C63; font-size: 10.5px; font-weight: 600; letter-spacing: 1px; }"
            "QLabel#m { color: #9A9CA3; font-size: 12.5px; font-weight: 500; }"
            "QLabel#err { color: #FF8C8C; font-size: 12px; }"
            "QProgressBar { background: #131316; border: 1px solid rgba(255,255,255,0.10);"
            " border-radius: 6px; height: 8px; text-align: center; }"
            "QProgressBar::chunk { background: #31D27A; border-radius: 5px; }"
            "QPushButton#primary { background: #31D27A; color: #0A0A0B; border: none;"
            " border-radius: 8px; padding: 8px 16px; font: 600 12.5px 'Inter', sans-serif; }"
            "QPushButton#primary:hover { background: #4FE090; }"
            "QPushButton#secondary { background: #26262B; color: #E8E8EA;"
            " border: 1px solid rgba(255,255,255,0.10); border-radius: 8px;"
            " padding: 8px 14px; font: 500 12.5px 'Inter', sans-serif; }"
            "QPushButton#secondary:hover { background: #2D2D33; }"
        )

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 22)
        v.setSpacing(8)

        kicker = QLabel("СКАЧИВАНИЕ МОДЕЛИ")
        kicker.setObjectName("k")
        kicker.setAlignment(Qt.AlignCenter)
        v.addWidget(kicker)

        self._title = QLabel(f"Скачивается {model_label(model_key)}")
        self._title.setObjectName("h")
        self._title.setAlignment(Qt.AlignCenter)
        v.addWidget(self._title)

        self._meta = QLabel("Подключение к Hugging Face…")
        self._meta.setObjectName("m")
        self._meta.setAlignment(Qt.AlignCenter)
        v.addWidget(self._meta)

        v.addSpacing(10)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        v.addWidget(self._bar)

        self._err = QLabel("")
        self._err.setObjectName("err")
        self._err.setAlignment(Qt.AlignCenter)
        self._err.setWordWrap(True)
        self._err.hide()
        v.addWidget(self._err)

        v.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)

        self._retry_btn = QPushButton("Повторить")
        self._retry_btn.setObjectName("primary")
        self._retry_btn.setCursor(Qt.PointingHandCursor)
        self._retry_btn.clicked.connect(self._start)
        self._retry_btn.hide()
        actions.addWidget(self._retry_btn)

        self._close_btn = QPushButton("Отмена")
        self._close_btn.setObjectName("secondary")
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self._on_close_clicked)
        actions.addWidget(self._close_btn)

        v.addLayout(actions)

        QTimer.singleShot(100, self._start)

    def _start(self) -> None:
        self._err.hide()
        self._retry_btn.hide()
        self._close_btn.setText("Отмена")
        self._bar.setRange(0, 0)
        self._meta.setText("Подключение к Hugging Face…")
        self._title.setText(f"Скачивается {model_label(self._model)}")

        thread = DownloaderThread(self._model, models_dir())
        thread.progress.connect(self._on_progress)
        thread.finished_ok.connect(self._on_finished)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int(downloaded * 100 / total)
            self._bar.setRange(0, 100)
            self._bar.setValue(min(100, pct))
            self._meta.setText(f"{_fmt_bytes(downloaded)} / {_fmt_bytes(total)} · {pct}%")
        else:
            self._bar.setRange(0, 0)
            self._meta.setText(f"Скачано {_fmt_bytes(downloaded)}")

    def _on_finished(self, _path: str) -> None:
        self._done = True
        self._bar.setRange(0, 100)
        self._bar.setValue(100)
        self._title.setText("Готово")
        self._meta.setText(f"Модель {model_label(self._model)} установлена")
        self._close_btn.setText("Закрыть")
        QTimer.singleShot(800, self.accept)

    def _on_failed(self, msg: str) -> None:
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._title.setText("Не удалось скачать")
        self._meta.setText(model_label(self._model))
        self._err.setText(msg)
        self._err.show()
        self._retry_btn.show()
        self._close_btn.setText("Закрыть")

    def _on_close_clicked(self) -> None:
        self.reject()

    def closeEvent(self, event) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.cancel()
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        super().closeEvent(event)


_MODIFIER_KEY_NAMES = frozenset({
    "left shift", "right shift",
    "left ctrl", "right ctrl",
    "left alt", "right alt",
    "left windows", "right windows",
})


class HotkeyCaptureDialog(QDialog):
    _key_captured = Signal(str)

    def __init__(self, current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._captured: str | None = None
        self._hook = None

        self.setWindowTitle("Запись горячей клавиши")
        self.setModal(True)
        self.setFixedSize(440, 240)
        self.setStyleSheet(
            "QDialog { background: #1B1B1F; }"
            "QLabel#k { color: #5A5C63; font-size: 10.5px; font-weight: 600; letter-spacing: 1px; }"
            "QLabel#h { color: #E8E8EA; font-size: 16px; font-weight: 600; letter-spacing: -0.2px; }"
            "QLabel#m { color: #9A9CA3; font-size: 12.5px; font-weight: 500; }"
            "QLabel#preview { color: #E8E8EA; background: #131316;"
            " border: 1px solid rgba(255,255,255,0.10); border-radius: 9px;"
            " padding: 10px 18px; font-size: 14px; font-weight: 600; }"
            "QPushButton#primary { background: #31D27A; color: #0A0A0B; border: none;"
            " border-radius: 8px; padding: 8px 16px; font: 600 12.5px 'Inter', sans-serif; }"
            "QPushButton#primary:hover { background: #4FE090; }"
            "QPushButton#primary:disabled { background: #1F4A2E; color: #5A8B6E; }"
            "QPushButton#secondary { background: #26262B; color: #E8E8EA;"
            " border: 1px solid rgba(255,255,255,0.10); border-radius: 8px;"
            " padding: 8px 14px; font: 500 12.5px 'Inter', sans-serif; }"
            "QPushButton#secondary:hover { background: #2D2D33; }"
        )

        self._key_captured.connect(self._on_key, Qt.QueuedConnection)

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 22)
        v.setSpacing(8)

        kicker = QLabel("ЗАПИСЬ ГОРЯЧЕЙ КЛАВИШИ")
        kicker.setObjectName("k")
        kicker.setAlignment(Qt.AlignCenter)
        v.addWidget(kicker)

        self._title = QLabel("Нажмите клавишу")
        self._title.setObjectName("h")
        self._title.setAlignment(Qt.AlignCenter)
        v.addWidget(self._title)

        self._meta = QLabel(f"Текущая: {_hotkey_pretty(current)}")
        self._meta.setObjectName("m")
        self._meta.setAlignment(Qt.AlignCenter)
        v.addWidget(self._meta)

        v.addSpacing(14)

        self._preview = QLabel("—")
        self._preview.setObjectName("preview")
        self._preview.setAlignment(Qt.AlignCenter)
        v.addWidget(self._preview, 0, Qt.AlignHCenter)

        v.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)

        self._save_btn = QPushButton("Сохранить")
        self._save_btn.setObjectName("primary")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self.accept)
        actions.addWidget(self._save_btn)

        cancel = QPushButton("Отмена")
        cancel.setObjectName("secondary")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)

        v.addLayout(actions)

    def captured(self) -> str | None:
        return self._captured

    def showEvent(self, event) -> None:
        try:
            import keyboard

            if self._hook is None:
                self._hook = keyboard.hook(self._on_kbd_event)
        except Exception:
            pass
        super().showEvent(event)

    def done(self, result: int) -> None:
        self._stop_hook()
        super().done(result)

    def _stop_hook(self) -> None:
        if self._hook is None:
            return
        try:
            import keyboard

            keyboard.unhook(self._hook)
        except Exception:
            pass
        self._hook = None

    def _on_kbd_event(self, e) -> None:
        if getattr(e, "event_type", "") != "down":
            return
        name = (getattr(e, "name", "") or "").lower().strip()
        if not name or name == "esc":
            return
        if name in _MODIFIER_KEY_NAMES:
            self._key_captured.emit(name)
            return
        import keyboard

        mods: list[str] = []
        if keyboard.is_pressed("ctrl"):
            mods.append("ctrl")
        if keyboard.is_pressed("alt"):
            mods.append("alt")
        if keyboard.is_pressed("shift"):
            mods.append("shift")
        combo = "+".join(mods + [name]) if mods else name
        self._key_captured.emit(combo)

    def _on_key(self, combo: str) -> None:
        self._captured = combo
        self._preview.setText(_hotkey_pretty(combo))
        self._title.setText("Готово — можно сохранить")
        self._save_btn.setEnabled(True)


class SettingsWindow(FramelessMainWindow):
    reload_requested = Signal()
    paste_text_requested = Signal(str)
    copy_text_requested = Signal(str)
    config_changed = Signal(dict)

    def __init__(
        self,
        runtime: AppRuntime | None = None,
        *,
        standalone: bool = False,
        files_manager: FileManager | None = None,
    ) -> None:
        super().__init__()
        self._standalone = standalone
        self._runtime = runtime or _default_runtime()
        self._files_manager = files_manager
        self._pending_changes: dict[str, object] = {}
        self.setWindowTitle("WinWhisp")
        self.setStyleSheet(_STYLE + FILES_STYLE + chrome_stylesheet())

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._flush_save)

        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        w, h = 960, 640
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

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._title_bar_widget = TitleBar(
            "WinWhisp",
            subtitle="Настройки",
            logo=_make_logo_pixmap(20),
        )
        self.install_titlebar(self._title_bar_widget)
        outer.addWidget(self._title_bar_widget)

        body = QWidget()
        body.setObjectName("root")
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        outer.addWidget(body, 1)

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

        self._logs_page = _LogsPage(self._runtime)

        self._files_page: FilesPage | None = None
        if self._files_manager is not None:
            self._files_page = FilesPage(self._files_manager)
            self._files_page.open_transcripts_requested.connect(
                lambda: _open_path(transcripts_dir())
            )
            self._files_page.file_open_requested.connect(_open_path)

        self._add_page("dashboard", self._dashboard)
        if self._files_page is not None:
            self._add_page("files", self._files_page)
        else:
            self._add_page(
                "files",
                _build_placeholder(
                    "Файлы",
                    "Раздел недоступен — менеджер файлов не инициализирован.",
                ),
            )
        self._add_page("history", self._history_page)
        self._add_page("general", self._build_general_page())
        self._add_page("model", self._build_model_page())
        self._add_page("logs", self._logs_page)
        for key, (title, hint) in PAGE_FACTORIES.items():
            self._add_page(key, _build_placeholder(title, hint))

        self._sidebar.page_changed.connect(self._on_page_change)
        self._sidebar.select("dashboard")

        self._toast = _Toast(root)

    def runtime(self) -> AppRuntime:
        return self._runtime

    def show_toast(self, text: str, *, kind: str = "ok", ms: int = 2400) -> None:
        if not text:
            return
        self._toast.show_message(text, kind=kind, ms=ms)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        toast = getattr(self, "_toast", None)
        if toast is not None and toast.isVisible():
            toast._reposition()

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

    def _make_toggle(self, path: str, value: bool) -> _ToggleSwitch:
        t = _ToggleSwitch()
        t.setChecked(value)
        t.toggled.connect(lambda v: self._set_cfg_value(path, v))
        return t

    def _make_slider(
        self,
        path: str,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str = " мс",
    ) -> _ValueSlider:
        s = _ValueSlider(minimum, maximum, value, suffix=suffix)
        s.valueChanged.connect(lambda v: self._set_cfg_value(path, v))
        return s

    def _make_text_combo(
        self,
        path: str,
        options: tuple[str, ...],
        current: str,
    ) -> QComboBox:
        c = QComboBox()
        c.setObjectName("select")
        c.setCursor(Qt.PointingHandCursor)
        for v in options:
            c.addItem(v)
        if c.findText(current) < 0:
            c.addItem(current)
        c.setCurrentText(current)
        c.currentTextChanged.connect(lambda v: self._set_cfg_value(path, v))
        return c

    def _add_setting_row(
        self,
        body: QVBoxLayout,
        title: str,
        desc: str,
        control: QWidget,
    ) -> None:
        self._append_row(body, _setting_row(title, desc, control))

    @staticmethod
    def _build_card_page(title: str, sub: str) -> tuple[QWidget, QVBoxLayout, QVBoxLayout]:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 36, 40, 36)
        outer.setSpacing(8)
        outer.addWidget(_label(title, "pageTitle"))
        outer.addWidget(_label(sub, "pageSub"))
        outer.addSpacing(18)

        card = _card()
        body = QVBoxLayout(card)
        body.setContentsMargins(22, 6, 22, 14)
        body.setSpacing(0)
        outer.addWidget(card)
        return page, outer, body

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
        page, outer, body = self._build_card_page(
            "Общие", "Запуск, горячая клавиша, уведомления и логирование."
        )

        self._add_setting_row(
            body,
            "Запускать вместе с Windows",
            "Автозагрузка через ярлык в shell:startup",
            self._make_toggle("autostart", cfg.autostart),
        )
        self._add_setting_row(
            body,
            "Горячая клавиша",
            "Удерживайте, чтобы записывать",
            self._make_hotkey_control(cfg),
        )
        self._add_setting_row(
            body,
            "Минимальное удержание",
            "Чтобы случайные нажатия не запускали запись",
            self._make_slider("hotkey.min_hold_ms", 0, 1000, cfg.hotkey.min_hold_ms),
        )
        self._add_setting_row(
            body,
            "Уведомления в трее",
            "Сообщать о готовности модели",
            self._make_toggle("tray.show_notifications", cfg.tray.show_notifications),
        )
        self._add_setting_row(
            body,
            "Уведомлять об ошибках",
            "Показывать всплывающее окно при сбое",
            self._make_toggle("tray.notify_on_error", cfg.tray.notify_on_error),
        )

        log_combo = self._make_text_combo(
            "log_level", ("DEBUG", "INFO", "WARNING", "ERROR"), cfg.log_level.upper()
        )
        self._add_setting_row(
            body,
            "Уровень логирования",
            "Логи в %APPDATA%\\WinWhisp\\logs\\",
            log_combo,
        )

        body.addSpacing(6)
        body.addWidget(_divider(dashed=True))

        disclosure = _Disclosure("Дополнительно (debounce, хвост)")
        disclosure.add_row(
            _setting_row(
                "Debounce",
                "Защита от двойных срабатываний",
                self._make_slider("hotkey.debounce_ms", 0, 500, cfg.hotkey.debounce_ms),
            )
        )
        disclosure.add_row(
            _setting_row(
                "Хвост после отпускания",
                "Пауза перед остановкой записи — поможет не обрезать конец фразы",
                self._make_slider("hotkey.release_tail_ms", 0, 1500, cfg.hotkey.release_tail_ms),
            )
        )
        body.addWidget(disclosure)

        outer.addStretch(1)
        return page

    def _build_model_page(self) -> QWidget:
        cfg = self._runtime.cfg
        page, outer, body = self._build_card_page(
            "Модель распознавания", "Whisper-движок и параметры декодирования."
        )

        self._add_setting_row(
            body,
            "Активная модель",
            "Whisper, скачивается с Hugging Face",
            self._make_model_control(cfg),
        )
        self._add_setting_row(
            body,
            "Compute type",
            "float16 — быстрее на CUDA, int8 — экономнее по памяти",
            self._make_text_combo(
                "asr.compute_type",
                ("float16", "int8_float16", "int8", "float32"),
                cfg.asr.compute_type,
            ),
        )
        self._add_setting_row(
            body,
            "Устройство",
            "CUDA для GPU, CPU как запасной вариант",
            self._make_text_combo("asr.device", ("cuda", "cpu", "auto"), cfg.asr.device),
        )
        self._add_setting_row(
            body,
            "Язык",
            "auto — определять автоматически из аудио",
            self._make_language_combo(cfg.asr.language),
        )
        self._add_setting_row(
            body,
            "Beam size",
            "Глубина поиска. Больше — точнее, но дольше",
            self._make_slider("asr.beam_size", 1, 10, cfg.asr.beam_size, suffix=""),
        )
        self._add_setting_row(
            body,
            "Выгружать из VRAM после",
            "0 — никогда не выгружать. Освобождает память во время простоя",
            self._make_slider("asr.idle_unload_s", 0, 600, cfg.asr.idle_unload_s, suffix=" с"),
        )

        body.addSpacing(6)
        body.addWidget(_divider(dashed=True))

        disclosure = _Disclosure("VAD-фильтр Whisper")
        disclosure.add_row(
            _setting_row(
                "Включить VAD",
                "Силеро-фильтр в самом Whisper, режет тишину",
                self._make_toggle("asr.vad_filter", cfg.asr.vad_filter),
            )
        )
        disclosure.add_row(
            _setting_row(
                "Минимальная пауза",
                "Длина тишины, после которой Whisper режет фрагмент",
                self._make_slider(
                    "asr.vad_min_silence_ms", 100, 2000, cfg.asr.vad_min_silence_ms
                ),
            )
        )
        body.addWidget(disclosure)

        hint = _label(
            "Изменения применяются автоматически при следующем нажатии хоткея — "
            "движок выгружается из VRAM и перезагружается с новыми параметрами. "
            "Если выбранная модель ещё не скачана, нажми «Установить».",
            wrap=True,
        )
        hint.setStyleSheet("color: #5A5C63; font-size: 11.5px; padding: 4px 4px 0 4px;")
        outer.addWidget(hint)

        outer.addStretch(1)

        self._refresh_model_status()
        return page

    def _on_model_combo_changed(self, _idx: int) -> None:
        key = self._model_combo.currentData()
        if not key:
            return
        self._set_cfg_value("asr.model", key)
        self._refresh_model_status()

    def _refresh_model_status(self) -> None:
        for i in range(self._model_combo.count()):
            item_key = self._model_combo.itemData(i)
            if not item_key:
                continue
            self._model_combo.setItemText(i, model_label(item_key))
            self._model_combo.setItemData(i, _model_installed(item_key), _MODEL_INSTALLED_ROLE)

        key = self._model_combo.currentData()
        if not key:
            self._model_dl_btn.hide()
            return
        self._model_dl_btn.setVisible(not _model_installed(key))

    def _on_download_selected_model(self) -> None:
        key = self._model_combo.currentData()
        if not key:
            return
        dlg = ModelDownloadDialog(key, self)
        result = dlg.exec()
        self._refresh_model_status()
        if result == QDialog.Accepted and self._runtime.cfg.asr.model == key:
            self.config_changed.emit({"asr.model": key})

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
        edit.setToolTip("Записать новую комбинацию клавиш")
        edit.clicked.connect(lambda: self._open_hotkey_capture(kbd))
        h.addWidget(edit)
        return wrap

    def _open_hotkey_capture(self, kbd_label: QLabel) -> None:
        current = self._runtime.cfg.hotkey.combo
        dlg = HotkeyCaptureDialog(current, self)
        if dlg.exec() != QDialog.Accepted:
            return
        combo = dlg.captured()
        if not combo or combo == current:
            return
        self._set_cfg_value("hotkey.combo", combo)
        kbd_label.setText(_hotkey_pretty(combo))
        self.show_toast(
            "Новый хоткей применится после перезапуска приложения",
            kind="warn",
            ms=3500,
        )

    def _make_model_control(self, cfg: Config) -> QWidget:
        self._model_combo = QComboBox()
        self._model_combo.setObjectName("select")
        self._model_combo.setCursor(Qt.PointingHandCursor)
        self._model_combo.setMinimumWidth(160)
        self._model_combo.setItemDelegate(_ModelItemDelegate(self._model_combo))
        self._model_combo.view().setMinimumWidth(300)
        self._model_combo.view().setSpacing(0)
        for key, name, *_ in MODELS:
            self._model_combo.addItem(name, key)
        idx = self._model_combo.findData(cfg.asr.model)
        if idx < 0:
            self._model_combo.addItem(cfg.asr.model, cfg.asr.model)
            idx = self._model_combo.findData(cfg.asr.model)
        self._model_combo.setCurrentIndex(idx)
        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)

        self._model_dl_btn = _link_button("Установить", self._on_download_selected_model)

        wrap = QWidget()
        ml = QHBoxLayout(wrap)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(8)
        ml.addWidget(self._model_combo)
        ml.addWidget(self._model_dl_btn)
        return wrap

    def _make_language_combo(self, current: str | None) -> QComboBox:
        c = QComboBox()
        c.setObjectName("select")
        c.setCursor(Qt.PointingHandCursor)
        for label, value in (("ru", "ru"), ("en", "en"), ("auto", None)):
            c.addItem(label, value)
        for i in range(c.count()):
            if c.itemData(i) == current:
                c.setCurrentIndex(i)
                break
        c.currentIndexChanged.connect(
            lambda i: self._set_cfg_value("asr.language", c.itemData(i))
        )
        return c

    def showEvent(self, event) -> None:
        super().showEvent(event)
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
        self.show()
        self.raise_()
        self.activateWindow()

    def open_to_page(self, key: str) -> None:
        self._sidebar.select(key)
        self.open_to_front()

    def files_page(self) -> FilesPage | None:
        return self._files_page


def _default_runtime() -> AppRuntime:
    return AppRuntime(cfg=Config(), vocab=Vocab())
