from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from loguru import logger
from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from transcrb.asr.catalog import DEFAULT_MODEL, MODELS
from transcrb.asr.downloader import DownloaderThread
from transcrb.config import Config, save_config
from transcrb.paths import (
    appdata_dir,
    clear_override,
    config_path,
    default_appdata_dir,
    models_dir,
    write_override,
)
from transcrb.ui.settings_window import (
    APP_VERSION,
    _STYLE,
    _make_logo_pixmap,
    _make_pulse_pixmap,
)
from transcrb.ui.window_chrome import (
    FramelessMainWindow,
    TitleBar,
    chrome_stylesheet,
)


ACCENT = "#31D27A"

HOTKEY_PRESETS: list[tuple[str, str, str]] = [
    ("right ctrl", "Right Ctrl", "не конфликтует с Ctrl+C / Ctrl+V — самый безопасный вариант"),
    ("right alt",  "Right Alt",  "если правый Ctrl уже занят чем-то другим"),
]
DEFAULT_HOTKEY = "right ctrl"

STEPS = ["Привет", "Модель", "Хранилище", "Хоткей", "Готово"]


_EXTRA_STYLE = """
QFrame#optCard {
    background: #18181C;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 14px;
}
QFrame#optCard:hover { background: #1F1F24; border: 1px solid rgba(255, 255, 255, 0.14); }
QFrame#optCard[selected="true"] {
    background: rgba(49, 210, 122, 0.10);
    border: 1px solid rgba(49, 210, 122, 0.45);
}

QLabel#optName { color: #E8E8EA; font-size: 14px; font-weight: 600; }
QLabel#optMeta { color: #7A7C82; font-size: 12.5px; }
QLabel#optRight {
    color: #C8CACE;
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 12px;
    font-weight: 600;
}
QLabel#optBadge {
    background: rgba(49, 210, 122, 0.14);
    border: 1px solid rgba(49, 210, 122, 0.35);
    color: #5FE89C;
    padding: 4px 9px;
    border-radius: 9px;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.6px;
}

QFrame#captureBox {
    background: #131316;
    border: 1px dashed rgba(255, 255, 255, 0.16);
    border-radius: 12px;
}
QLabel#captureHead { color: #E8E8EA; font-size: 14px; font-weight: 600; }
QLabel#captureHint { color: #5A5C63; font-size: 11.5px; }

QFrame#pathField {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
}
QLabel#pathText {
    color: #E8E8EA;
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 12px;
}
QLabel#pathGlyph {
    color: #5A5C63;
    font-size: 13px;
}

QFrame#meter {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}
QLabel#meterLabel { color: #9A9CA3; font-size: 12px; }
QLabel#meterNum {
    color: #9A9CA3;
    font-size: 12px;
    font-weight: 500;
}

QProgressBar#dlProgress {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    height: 8px;
    text-align: center;
}
QProgressBar#dlProgress::chunk {
    background: #31D27A;
    border-radius: 5px;
}

QLabel#dlTitle { color: #E8E8EA; font-size: 18px; font-weight: 600; letter-spacing: -0.2px; }
QLabel#dlMeta {
    color: #9A9CA3;
    font-size: 12.5px;
    font-weight: 500;
}
QLabel#dlError { color: #FF8C8C; font-size: 12px; }

QFrame#featCard {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}
QLabel#featGlyph {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    color: #4FE090;
    font-size: 14px;
    qproperty-alignment: AlignCenter;
}
QLabel#featHead { color: #E8E8EA; font-size: 12.5px; font-weight: 600; }
QLabel#featDesc { color: #5A5C63; font-size: 11.5px; }

QFrame#sumRow {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}
QLabel#sumGlyph {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    color: #9A9CA3;
    font-size: 13px;
    qproperty-alignment: AlignCenter;
}
QLabel#sumName { color: #E8E8EA; font-size: 12.5px; font-weight: 500; }
QLabel#sumDesc { color: #5A5C63; font-size: 11.5px; }

QPushButton#stepperFootBtn {
    background: transparent;
    color: #9A9CA3;
    border: none;
    padding: 8px 12px;
    font-size: 12.5px;
    font-weight: 500;
    border-radius: 8px;
}
QPushButton#stepperFootBtn:hover { color: #E8E8EA; }
QPushButton#stepperFootBtn:disabled { color: #36363B; }
"""


def _fmt_size(n: int) -> str:
    if n <= 0:
        return "—"
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    return f"{n / 1024:.0f} KB"


def _detect_gpu() -> str | None:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).decode("utf-8", errors="ignore").strip()
    except Exception:
        return None
    if not out:
        return None
    return out.splitlines()[0].strip()


def _hotkey_pretty(combo: str) -> str:
    parts = [p.strip() for p in combo.split("+")]
    out = []
    for p in parts:
        low = p.lower()
        if low == "right ctrl":
            out.append("Right Ctrl")
        elif low == "left ctrl":
            out.append("Left Ctrl")
        elif low in ("ctrl", "shift", "alt", "win"):
            out.append(low.capitalize())
        elif low == "right alt":
            out.append("Right Alt")
        elif low == "right shift":
            out.append("Right Shift")
        elif low == "right win":
            out.append("Right Win")
        else:
            out.append(p.capitalize())
    return " + ".join(out)


def _kbd(text: str, parent: QWidget | None = None) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setObjectName("kbd")
    lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
    return lbl


def _label(text: str, name: str = "", *, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


class _StepperBar(QWidget):
    def __init__(self, steps: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._steps = steps
        self._active = 0
        self.setFixedHeight(86)

    def set_active(self, idx: int) -> None:
        self._active = max(0, min(idx, len(self._steps) - 1))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        n = len(self._steps)
        if n == 0:
            return

        margin_x = 40
        top = 24
        circle_d = 30

        slots: list[float] = []
        if n == 1:
            slots = [self.width() / 2]
        else:
            slot_w = (self.width() - 2 * margin_x) / (n - 1)
            slots = [margin_x + i * slot_w for i in range(n)]

        font_label = QFont("Inter")
        font_label.setPixelSize(13)
        font_label.setWeight(QFont.DemiBold)
        p.setFont(font_label)
        fm = p.fontMetrics()

        for i in range(n - 1):
            x1 = slots[i]
            x2 = slots[i + 1]
            done = i < self._active
            y = top + circle_d / 2
            pad = circle_d / 2 + 14
            line_x1 = x1 + pad
            line_x2 = x2 - pad
            if line_x2 <= line_x1:
                continue
            color = QColor(ACCENT) if done else QColor(255, 255, 255, 28)
            if done:
                color.setAlphaF(0.42)
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(line_x1, y), QPointF(line_x2, y))

        for i, name in enumerate(self._steps):
            cx = slots[i]
            r = QRectF(cx - circle_d / 2, top, circle_d, circle_d)
            done = i < self._active
            active = i == self._active

            if active:
                glow = QColor(ACCENT)
                glow.setAlphaF(0.22)
                p.setPen(Qt.NoPen)
                p.setBrush(glow)
                p.drawEllipse(r.adjusted(-4, -4, 4, 4))
                p.setBrush(QColor(ACCENT))
                p.drawEllipse(r)
                pen = QPen(QColor(0, 0, 0, 50), 1)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(r.adjusted(0.5, 0.5, -0.5, -0.5))
                p.setPen(QColor("#0A0A0B"))
                f2 = QFont("Inter")
                f2.setPixelSize(13)
                f2.setWeight(QFont.Black)
                p.setFont(f2)
                p.drawText(r, Qt.AlignCenter, str(i + 1))
                p.setFont(font_label)
            elif done:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(49, 210, 122, 36))
                p.drawEllipse(r)
                pen = QPen(QColor(49, 210, 122, 110), 1.5)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(r.adjusted(0.75, 0.75, -0.75, -0.75))
                check = QPen(QColor("#5FE89C"), 2.4)
                check.setCapStyle(Qt.RoundCap)
                check.setJoinStyle(Qt.RoundJoin)
                p.setPen(check)
                ccx = cx
                ccy = top + circle_d / 2
                p.drawLine(
                    QPointF(ccx - 5.5, ccy + 0.5),
                    QPointF(ccx - 1.5, ccy + 4.5),
                )
                p.drawLine(
                    QPointF(ccx - 1.5, ccy + 4.5),
                    QPointF(ccx + 6.0, ccy - 4.5),
                )
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#1A1A1E"))
                p.drawEllipse(r)
                pen = QPen(QColor(255, 255, 255, 22), 1.5)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(r.adjusted(0.75, 0.75, -0.75, -0.75))
                p.setPen(QColor("#7A7C82"))
                f2 = QFont("Inter")
                f2.setPixelSize(12)
                f2.setWeight(QFont.Bold)
                p.setFont(f2)
                p.drawText(r, Qt.AlignCenter, str(i + 1))
                p.setFont(font_label)

            label_color = QColor("#E8E8EA") if active else (
                QColor("#C8CACE") if done else QColor("#5A5C63")
            )
            p.setPen(label_color)
            text_y = top + circle_d + 16 + fm.ascent()
            text_w = fm.horizontalAdvance(name)
            p.drawText(QPointF(cx - text_w / 2, text_y), name)


class _OptionCard(QFrame):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("optCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _make_radio_pixmap(selected: bool, size: int = 22) -> object:
    from PySide6.QtGui import QPixmap

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    inset = 2
    ring_rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    if selected:
        glow = QColor(ACCENT)
        glow.setAlphaF(0.20)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(0, 0, size, size))
        p.setBrush(QColor("#0A0A0B"))
        p.drawEllipse(ring_rect)
        pen = QPen(QColor(ACCENT), 2.4)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(ring_rect)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT))
        d = size * 0.55
        p.drawEllipse(QRectF((size - d) / 2, (size - d) / 2, d, d))
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1A1A1E"))
        p.drawEllipse(ring_rect)
        pen = QPen(QColor("#5A5C63"), 1.8)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(ring_rect)
    p.end()
    return pm


class _RadioOption(_OptionCard):
    def __init__(
        self,
        title: str,
        meta: str,
        right_text: str = "",
        badge: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 16, 12)
        h.setSpacing(14)

        self._radio = QLabel()
        self._radio.setFixedSize(22, 22)
        self._radio.setPixmap(_make_radio_pixmap(False))
        h.addWidget(self._radio, 0, Qt.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)
        self._title = _label(title, "optName")
        self._meta = _label(meta, "optMeta")
        text_box.addWidget(self._title)
        text_box.addWidget(self._meta)
        text_w = QWidget()
        text_w.setLayout(text_box)
        h.addWidget(text_w, 1)

        right_box = QHBoxLayout()
        right_box.setSpacing(8)
        right_box.setContentsMargins(0, 0, 0, 0)
        if badge:
            badge_lbl = _label(badge, "optBadge")
            badge_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
            right_box.addWidget(badge_lbl)
        if right_text:
            right_box.addWidget(_label(right_text, "optRight"))
        right_w = QWidget()
        right_w.setLayout(right_box)
        h.addWidget(right_w, 0, Qt.AlignVCenter)

    def set_selected(self, on: bool) -> None:
        super().set_selected(on)
        self._radio.setPixmap(_make_radio_pixmap(on))

    def set_meta(self, text: str) -> None:
        self._meta.setText(text)


class _HotkeyCaptureDialog(QDialog):
    captured = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Захват клавиши")
        self.setModal(True)
        self.setFixedSize(360, 170)
        self.setStyleSheet(
            "QDialog { background: #0A0A0B; }"
            "QLabel#h { color: #E8E8EA; font-size: 14px; font-weight: 600; }"
            "QLabel#hint { color: #5A5C63; font-size: 12px; }"
            "QLabel#ico { color: #4FE090; font-size: 22px; }"
        )
        self._hook = None

        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 22)
        v.setSpacing(10)
        v.setAlignment(Qt.AlignCenter)

        ico = QLabel("⌘")
        ico.setObjectName("ico")
        ico.setAlignment(Qt.AlignCenter)
        v.addWidget(ico)

        head = QLabel("Нажмите клавишу")
        head.setObjectName("h")
        head.setAlignment(Qt.AlignCenter)
        v.addWidget(head)

        hint = QLabel("любая клавиша или модификатор · Esc — отмена")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        v.addWidget(hint)

        self.captured.connect(self._on_captured, Qt.QueuedConnection)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        try:
            import keyboard

            if self._hook is None:
                self._hook = keyboard.hook(self._on_event)
        except Exception as e:
            logger.error(f"hotkey capture: failed to hook keyboard: {e}")
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        self._stop_hook()
        super().closeEvent(event)

    def reject(self) -> None:
        self._stop_hook()
        super().reject()

    def _stop_hook(self) -> None:
        if self._hook is None:
            return
        try:
            import keyboard

            keyboard.unhook(self._hook)
        except Exception:
            pass
        self._hook = None

    def _on_event(self, e) -> None:
        if getattr(e, "event_type", "") != "down":
            return
        name = (getattr(e, "name", "") or "").lower().strip()
        if not name:
            return
        if name == "esc":
            return
        self.captured.emit(name)

    def _on_captured(self, name: str) -> None:
        self._stop_hook()
        self._captured = name
        self.accept()


class OnboardingWindow(FramelessMainWindow):
    completed = Signal()
    cancelled = Signal()

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.setWindowTitle("WinWhisp · первый запуск")
        self._cfg = cfg
        self._done = False

        self._chosen_model = DEFAULT_MODEL
        self._chosen_hotkey = DEFAULT_HOTKEY
        self._chosen_dir: Path = default_appdata_dir()
        self._gpu_text = _detect_gpu()
        self._dl_thread: DownloaderThread | None = None
        self._dl_progress_value: tuple[int, int] = (0, 0)

        self.setStyleSheet(_STYLE + _EXTRA_STYLE + chrome_stylesheet())

        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        w, h = 960, 640
        self.resize(w, h)
        self.setMinimumSize(880, 580)
        if avail is not None:
            cx = avail.x() + (avail.width() - w) // 2
            cy = avail.y() + (avail.height() - h) // 2
            self.move(cx, cy)

        root = QWidget(self)
        root.setObjectName("root")
        self.setCentralWidget(root)

        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._title_bar_widget = TitleBar(
            "WinWhisp",
            subtitle="Первый запуск",
            logo=_make_logo_pixmap(20),
            show_maximize=False,
        )
        self.install_titlebar(self._title_bar_widget)
        v.addWidget(self._title_bar_widget)

        self._stepper = _StepperBar(STEPS)
        v.addWidget(self._stepper)

        self._stack = QStackedWidget()
        v.addWidget(self._stack, 1)

        self._foot = self._build_footer()
        v.addWidget(self._foot)

        self._stack.addWidget(self._build_step_welcome())
        self._stack.addWidget(self._build_step_model())
        self._stack.addWidget(self._build_step_storage())
        self._stack.addWidget(self._build_step_hotkey())
        self._stack.addWidget(self._build_step_finish())
        self._stack.addWidget(self._build_step_download())

        self._goto(0)

    # ------------------------------------------------------------- footer

    def _build_footer(self) -> QWidget:
        w = QFrame()
        w.setStyleSheet("QFrame { background: transparent; border: none; }")
        h = QHBoxLayout(w)
        h.setContentsMargins(40, 14, 40, 18)
        h.setSpacing(10)

        self._btn_back = QPushButton("← Назад")
        self._btn_back.setObjectName("stepperFootBtn")
        self._btn_back.setCursor(Qt.PointingHandCursor)
        self._btn_back.clicked.connect(self._on_back)
        h.addWidget(self._btn_back)

        self._lbl_progress = _label("", "cardMuted")
        self._lbl_progress.setStyleSheet(
            "color: #5A5C63; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 11px;"
        )
        h.addWidget(self._lbl_progress)

        h.addStretch(1)

        self._lbl_status = _label("", "cardMuted")
        h.addWidget(self._lbl_status)

        self._btn_skip = QPushButton("Пропустить")
        self._btn_skip.setObjectName("linkBtn")
        self._btn_skip.setCursor(Qt.PointingHandCursor)
        self._btn_skip.clicked.connect(self._on_next)
        self._btn_skip.hide()
        h.addWidget(self._btn_skip)

        self._btn_next = QPushButton("Далее →")
        self._btn_next.setObjectName("primaryBtn")
        self._btn_next.setCursor(Qt.PointingHandCursor)
        self._btn_next.clicked.connect(self._on_next)
        h.addWidget(self._btn_next)

        return w

    # ------------------------------------------------------------- helpers

    def _goto(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        if idx < len(STEPS):
            self._stepper.set_active(idx)
        else:
            self._stepper.set_active(len(STEPS) - 1)

        self._btn_back.setEnabled(idx > 0 and idx < len(STEPS))
        self._btn_back.setVisible(idx < len(STEPS))
        self._btn_skip.hide()
        self._lbl_status.setText("")

        if idx < len(STEPS):
            self._lbl_progress.setText(f"{idx + 1} / {len(STEPS)}")
            self._foot.setVisible(True)
        else:
            self._lbl_progress.setText("")
            self._foot.setVisible(False)

        self._btn_next.show()

        if idx == 0:
            self._btn_next.setText("Поехали →")
            self._btn_back.setVisible(False)
        elif idx == 1:
            self._btn_next.setText("Далее →")
        elif idx == 2:
            self._btn_next.setText("Далее →")
        elif idx == 3:
            self._btn_next.setText("Далее →")
        elif idx == 4:
            self._btn_next.setText("Скачать модель и запустить")
            self._lbl_status.setText("")
        else:
            pass

    def _on_back(self) -> None:
        idx = self._stack.currentIndex()
        if idx == 0:
            return
        if idx >= len(STEPS):
            return
        self._goto(idx - 1)

    def _on_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx == 4:
            self._start_download()
            return
        if idx + 1 < len(STEPS):
            self._refresh_finish_summary()
            self._goto(idx + 1)

    # ============================================================= step 1

    def _build_step_welcome(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 30, 40, 18)
        outer.setSpacing(0)

        head = QHBoxLayout()
        head.setSpacing(22)
        head.setContentsMargins(0, 0, 0, 0)

        logo = QLabel()
        logo.setPixmap(_make_logo_pixmap(84))
        logo.setFixedSize(84, 84)
        head.addWidget(logo, 0, Qt.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(6)
        text_box.setContentsMargins(0, 4, 0, 0)

        kicker = _label("ШАГ 1 · ЗНАКОМСТВО", "cardKicker")
        text_box.addWidget(kicker)

        name = _label("Привет. Это WinWhisp.")
        nf = QFont()
        nf.setPointSize(20)
        nf.setBold(True)
        name.setFont(nf)
        text_box.addWidget(name)

        sub = _label(
            "Push-to-talk диктовка с локальным распознаванием речи. "
            "Зажми клавишу, скажи фразу — текст появится в активном поле. "
            "Никаких облаков, всё работает прямо на твоём GPU.",
            "cardBody",
            wrap=True,
        )
        sub.setStyleSheet("color: #9A9CA3; font-size: 13px; line-height: 1.5;")
        text_box.addWidget(sub)

        head.addLayout(text_box, 1)

        if self._gpu_text:
            pill = _label(f"●  {self._gpu_text}", "pillOk")
            pill.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
            right_col = QVBoxLayout()
            right_col.setContentsMargins(0, 6, 0, 0)
            right_col.addWidget(pill, 0, Qt.AlignTop | Qt.AlignRight)
            right_col.addStretch(1)
            head.addLayout(right_col)

        outer.addLayout(head)
        outer.addSpacing(28)

        feat_row = QHBoxLayout()
        feat_row.setSpacing(10)
        feat_row.addWidget(self._make_feature("⌘", "Удержание клавиши", "Зажал клавишу — пишет, отпустил — расшифровывает."))
        feat_row.addWidget(self._make_feature("◇", "Whisper локально", "faster-whisper на CUDA. Модель в VRAM по требованию."))
        feat_row.addWidget(self._make_feature("↘", "Вставка в любое поле", "Стандартный Ctrl+V — работает везде, где работает буфер."))
        outer.addLayout(feat_row)
        outer.addStretch(1)
        return page

    def _make_feature(self, glyph: str, head: str, desc: str) -> QFrame:
        f = QFrame()
        f.setObjectName("featCard")
        v = QVBoxLayout(f)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        ic = QLabel(glyph)
        ic.setObjectName("featGlyph")
        ic.setFixedSize(28, 28)
        v.addWidget(ic)
        v.addWidget(_label(head, "featHead"))
        v.addWidget(_label(desc, "featDesc", wrap=True))
        v.addStretch(1)
        return f

    # ============================================================= step 2

    def _build_step_model(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 28, 40, 18)
        outer.setSpacing(0)

        outer.addWidget(_label("ШАГ 2 · МОДЕЛЬ РАСПОЗНАВАНИЯ", "cardKicker"))
        outer.addSpacing(4)
        outer.addWidget(_label("Какой Whisper использовать?", "pageTitle"))
        outer.addSpacing(8)
        sub = _label(
            "Модель скачается один раз. Чем больше — тем точнее, но дольше первое нагревание "
            "и больше VRAM. Если есть мощный GPU — бери large-v3.",
            "pageSub",
            wrap=True,
        )
        sub.setMaximumWidth(680)
        outer.addWidget(sub)

        outer.addSpacing(18)

        self._model_options: list[tuple[str, _RadioOption]] = []
        for key, name, desc, size, vram in MODELS:
            badge = "РЕКОМЕНДОВАНО" if key == DEFAULT_MODEL else ""
            right = f"{_fmt_size(size)} · {vram}"
            opt = _RadioOption(name, desc, right_text=right, badge=badge)
            opt.clicked.connect(lambda k=key: self._select_model(k))
            outer.addWidget(opt)
            outer.addSpacing(8)
            self._model_options.append((key, opt))

        outer.addStretch(1)
        self._select_model(DEFAULT_MODEL)
        return page

    def _select_model(self, key: str) -> None:
        self._chosen_model = key
        for k, opt in self._model_options:
            opt.set_selected(k == key)

    # ============================================================= step 3

    def _build_step_storage(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 28, 40, 18)
        outer.setSpacing(0)

        outer.addWidget(_label("ШАГ 3 · ПАПКА ПРИЛОЖЕНИЯ", "cardKicker"))
        outer.addSpacing(4)
        outer.addWidget(_label("Куда сохранять данные?", "pageTitle"))
        outer.addSpacing(8)
        sub = _label(
            "Здесь будут жить конфиг, словарь, скачанные модели и логи. "
            "По умолчанию — стандартный %APPDATA%. Большинству можно не трогать.",
            "pageSub",
            wrap=True,
        )
        sub.setMaximumWidth(680)
        outer.addWidget(sub)

        outer.addSpacing(20)

        head_row = QHBoxLayout()
        head_row.setContentsMargins(0, 0, 0, 6)
        head_row.addWidget(_label("ПУТЬ", "cardKicker"))
        head_row.addStretch(1)
        outer.addLayout(head_row)

        path_field = QFrame()
        path_field.setObjectName("pathField")
        ph = QHBoxLayout(path_field)
        ph.setContentsMargins(12, 10, 8, 10)
        ph.setSpacing(10)
        ph.addWidget(_label("⌗", "pathGlyph"))
        self._path_label = _label(str(self._chosen_dir), "pathText")
        self._path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ph.addWidget(self._path_label, 1)

        btn_browse = QPushButton("Обзор…")
        btn_browse.setObjectName("kbdBtn")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.clicked.connect(self._on_browse_dir)
        ph.addWidget(btn_browse)

        btn_reset = QPushButton("Сбросить")
        btn_reset.setObjectName("kbdBtn")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self._on_reset_dir)
        ph.addWidget(btn_reset)

        outer.addWidget(path_field)
        outer.addSpacing(14)

        self._meter_frame = QFrame()
        self._meter_frame.setObjectName("meter")
        mh = QHBoxLayout(self._meter_frame)
        mh.setContentsMargins(14, 12, 14, 12)
        mh.setSpacing(12)
        self._meter_label = _label("Диск C:", "meterLabel")
        mh.addWidget(self._meter_label)
        self._meter_bar = QProgressBar()
        self._meter_bar.setObjectName("dlProgress")
        self._meter_bar.setFixedHeight(4)
        self._meter_bar.setTextVisible(False)
        self._meter_bar.setRange(0, 100)
        mh.addWidget(self._meter_bar, 1)
        self._meter_num = _label("", "meterNum")
        mh.addWidget(self._meter_num)
        outer.addWidget(self._meter_frame)

        outer.addSpacing(14)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        for glyph, name, desc in (
            ("⚙", "config.yaml", "~2 KB"),
            ("⌥", "vocab.yaml", "~6 KB"),
            ("◇", "models/", "~3 GB"),
            ("⛁", "logs/", "ротация 7 дн"),
        ):
            chips_row.addWidget(self._make_sum_row(glyph, name, desc))
        outer.addLayout(chips_row)

        outer.addStretch(1)

        self._refresh_disk_meter()
        return page

    def _make_sum_row(self, glyph: str, name: str, desc: str) -> QFrame:
        f = QFrame()
        f.setObjectName("sumRow")
        h = QHBoxLayout(f)
        h.setContentsMargins(10, 9, 12, 9)
        h.setSpacing(10)
        ic = QLabel(glyph)
        ic.setObjectName("sumGlyph")
        ic.setFixedSize(26, 26)
        h.addWidget(ic, 0, Qt.AlignVCenter)
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.addWidget(_label(name, "sumName"))
        text_box.addWidget(_label(desc, "sumDesc"))
        w = QWidget()
        w.setLayout(text_box)
        h.addWidget(w, 1)
        return f

    def _on_browse_dir(self) -> None:
        start = str(self._chosen_dir if self._chosen_dir.exists() else default_appdata_dir())
        chosen = QFileDialog.getExistingDirectory(self, "Папка для WinWhisp", start)
        if not chosen:
            return
        target = Path(chosen)
        if not self._validate_dir(target):
            return
        self._chosen_dir = target
        self._path_label.setText(str(target))
        self._refresh_disk_meter()

    def _on_reset_dir(self) -> None:
        self._chosen_dir = default_appdata_dir()
        self._path_label.setText(str(self._chosen_dir))
        self._refresh_disk_meter()

    def _validate_dir(self, target: Path) -> bool:
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".winwhisp_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Папка недоступна",
                f"Нельзя записать в {target}.\n\n{e}",
            )
            return False
        return True

    def _refresh_disk_meter(self) -> None:
        try:
            anchor = self._chosen_dir if self._chosen_dir.exists() else self._chosen_dir.parent
            usage = shutil.disk_usage(str(anchor))
        except Exception:
            self._meter_label.setText("Диск:")
            self._meter_num.setText("—")
            self._meter_bar.setValue(0)
            return
        free = usage.free
        total = usage.total
        used_pct = int(((total - free) / total) * 100) if total else 0
        drive = anchor.anchor.rstrip("\\/") or str(anchor)
        self._meter_label.setText(f"Диск {drive}")
        self._meter_num.setText(f"{_fmt_size(total - free)} / {_fmt_size(total)} занято · {_fmt_size(free)} свободно")
        self._meter_bar.setValue(used_pct)

    # ============================================================= step 4

    def _build_step_hotkey(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 28, 40, 18)
        outer.setSpacing(0)

        outer.addWidget(_label("ШАГ 4 · PUSH-TO-TALK", "cardKicker"))
        outer.addSpacing(4)
        outer.addWidget(_label("Какую клавишу удерживать для записи?", "pageTitle"))
        outer.addSpacing(8)
        outer.addWidget(
            _label(
                "Зажал — пишет, отпустил — расшифровывает и вставляет. Лучшие варианты — "
                "Right Ctrl или Right Alt: их редко жмут, и они не путаются с Ctrl+C / Ctrl+V.",
                "pageSub",
                wrap=True,
            )
        )

        outer.addSpacing(18)

        self._hotkey_options: dict[str, _RadioOption] = {}
        for combo, name, desc in HOTKEY_PRESETS:
            badge = "ПО УМОЛЧАНИЮ" if combo == DEFAULT_HOTKEY else ""
            opt = _RadioOption(name, desc, right_text=_hotkey_pretty(combo), badge=badge)
            opt.clicked.connect(lambda c=combo: self._select_hotkey(c))
            outer.addWidget(opt)
            outer.addSpacing(8)
            self._hotkey_options[combo] = opt

        self._custom_opt = _OptionCard()
        ch = QHBoxLayout(self._custom_opt)
        ch.setContentsMargins(14, 12, 16, 12)
        ch.setSpacing(14)
        self._custom_radio = QLabel()
        self._custom_radio.setFixedSize(18, 18)
        self._custom_radio.setPixmap(_make_radio_pixmap(False))
        ch.addWidget(self._custom_radio, 0, Qt.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.addWidget(_label("Свой вариант", "optName"))
        self._custom_meta = _label("нажми «Захватить» и любую клавишу", "optMeta")
        text_box.addWidget(self._custom_meta)
        tw = QWidget()
        tw.setLayout(text_box)
        ch.addWidget(tw, 1)

        self._custom_kbd = _kbd("—")
        self._custom_kbd.hide()
        ch.addWidget(self._custom_kbd)

        btn_capture = QPushButton("Захватить")
        btn_capture.setObjectName("kbdBtn")
        btn_capture.setCursor(Qt.PointingHandCursor)
        btn_capture.clicked.connect(self._on_capture_hotkey)
        ch.addWidget(btn_capture)

        outer.addWidget(self._custom_opt)

        outer.addSpacing(14)

        outer.addStretch(1)
        self._select_hotkey(DEFAULT_HOTKEY)
        return page

    def _select_hotkey(self, combo: str) -> None:
        self._chosen_hotkey = combo
        for c, opt in self._hotkey_options.items():
            opt.set_selected(c == combo)
        is_custom = combo not in self._hotkey_options
        self._custom_opt.set_selected(is_custom)
        self._custom_radio.setPixmap(_make_radio_pixmap(is_custom))
        if is_custom:
            self._custom_kbd.setText(_hotkey_pretty(combo))
            self._custom_kbd.show()
            self._custom_meta.setText("своя клавиша")
        else:
            self._custom_kbd.hide()
            self._custom_meta.setText("нажми «Захватить» и любую клавишу")

    def _on_capture_hotkey(self) -> None:
        dlg = _HotkeyCaptureDialog(self)
        captured: dict[str, str] = {}

        def remember(name: str) -> None:
            captured["name"] = name

        dlg.captured.connect(remember)
        result = dlg.exec()
        if result != QDialog.Accepted:
            return
        name = captured.get("name", "").strip().lower()
        if not name:
            return
        self._select_hotkey(name)

    # ============================================================= step 5

    def _build_step_finish(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 24, 40, 18)
        outer.setSpacing(0)

        center_top = QVBoxLayout()
        center_top.setSpacing(10)
        center_top.setContentsMargins(0, 6, 0, 0)
        center_top.setAlignment(Qt.AlignHCenter)

        pulse = QLabel()
        pulse.setPixmap(_make_pulse_pixmap(96))
        pulse.setFixedSize(96, 96)
        pulse.setAlignment(Qt.AlignCenter)
        center_top.addWidget(pulse, 0, Qt.AlignHCenter)

        kicker = _label("ШАГ 5 · ВСЁ НАСТРОЕНО", "cardKicker")
        kicker.setAlignment(Qt.AlignCenter)
        center_top.addWidget(kicker)

        title = _label("Готов к диктовке", "pageTitle")
        title.setAlignment(Qt.AlignCenter)
        center_top.addWidget(title)

        sub = _label(
            "Нажми кнопку ниже — модель скачается, и WinWhisp свернётся в трей.",
            "pageSub",
            wrap=True,
        )
        sub.setAlignment(Qt.AlignCenter)
        center_top.addWidget(sub)

        outer.addLayout(center_top)
        outer.addSpacing(20)

        self._fin_grid = QHBoxLayout()
        self._fin_grid.setSpacing(10)
        col_l = QVBoxLayout()
        col_l.setSpacing(8)
        col_r = QVBoxLayout()
        col_r.setSpacing(8)

        self._sum_model = self._make_summary_row("◇", "Модель", "")
        self._sum_dir = self._make_summary_row("⌗", "Папка", "")
        self._sum_hotkey = self._make_summary_row("⌘", "Хоткей", "")
        self._sum_inject = self._make_summary_row("↘", "Вставка", "Ctrl+V в активное поле")

        col_l.addWidget(self._sum_model)
        col_l.addWidget(self._sum_dir)
        col_r.addWidget(self._sum_hotkey)
        col_r.addWidget(self._sum_inject)

        wrap_l = QWidget()
        wrap_l.setLayout(col_l)
        wrap_r = QWidget()
        wrap_r.setLayout(col_r)
        self._fin_grid.addWidget(wrap_l, 1)
        self._fin_grid.addWidget(wrap_r, 1)
        outer.addLayout(self._fin_grid)

        outer.addStretch(1)
        return page

    def _make_summary_row(self, glyph: str, name: str, desc: str) -> QFrame:
        f = QFrame()
        f.setObjectName("sumRow")
        h = QHBoxLayout(f)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(12)
        ic = QLabel(glyph)
        ic.setObjectName("sumGlyph")
        ic.setFixedSize(32, 32)
        h.addWidget(ic, 0, Qt.AlignVCenter)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)
        head = _label(name, "sumName")
        body = _label(desc, "sumDesc", wrap=True)
        f.setProperty("desc_label", body)
        text_box.addWidget(head)
        text_box.addWidget(body)
        w = QWidget()
        w.setLayout(text_box)
        h.addWidget(w, 1)
        return f

    def _refresh_finish_summary(self) -> None:
        model_label = next((n for k, n, *_ in MODELS if k == self._chosen_model), self._chosen_model)
        size = next((s for k, _n, _d, s, _v in MODELS if k == self._chosen_model), 0)
        self._sum_model.property("desc_label").setText(
            f"{model_label} · CUDA · float16 · {_fmt_size(size)}"
        )
        self._sum_dir.property("desc_label").setText(str(self._chosen_dir))
        self._sum_hotkey.property("desc_label").setText(
            f"push-to-talk · удерживать · {_hotkey_pretty(self._chosen_hotkey)}"
        )

    # ============================================================= step 6 (download)

    def _build_step_download(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 0, 40, 24)
        outer.setSpacing(0)

        outer.addStretch(3)

        self._dl_pulse = QLabel()
        self._dl_pulse.setPixmap(_make_pulse_pixmap(110))
        self._dl_pulse.setFixedSize(110, 110)
        self._dl_pulse.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._dl_pulse, 0, Qt.AlignHCenter)

        outer.addSpacing(14)

        kicker = _label("СКАЧИВАНИЕ МОДЕЛИ", "cardKicker")
        kicker.setAlignment(Qt.AlignCenter)
        outer.addWidget(kicker, 0, Qt.AlignHCenter)

        outer.addSpacing(6)

        self._dl_title = _label("Подготовка…", "dlTitle")
        self._dl_title.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._dl_title, 0, Qt.AlignHCenter)

        outer.addSpacing(8)

        self._dl_meta = _label("", "dlMeta")
        self._dl_meta.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._dl_meta, 0, Qt.AlignHCenter)

        outer.addSpacing(20)

        bar_wrap = QHBoxLayout()
        bar_wrap.setContentsMargins(0, 0, 0, 0)
        self._dl_bar = QProgressBar()
        self._dl_bar.setObjectName("dlProgress")
        self._dl_bar.setFixedHeight(8)
        self._dl_bar.setTextVisible(False)
        self._dl_bar.setRange(0, 0)
        self._dl_bar.setMaximumWidth(560)
        bar_wrap.addStretch(1)
        bar_wrap.addWidget(self._dl_bar, 1)
        bar_wrap.addStretch(1)
        outer.addLayout(bar_wrap)

        outer.addSpacing(12)

        self._dl_error = _label("", "dlError", wrap=True)
        self._dl_error.setAlignment(Qt.AlignCenter)
        self._dl_error.hide()
        outer.addWidget(self._dl_error, 0, Qt.AlignHCenter)

        outer.addSpacing(16)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.setAlignment(Qt.AlignCenter)

        self._dl_back_btn = QPushButton("← Назад")
        self._dl_back_btn.setObjectName("linkBtn")
        self._dl_back_btn.setCursor(Qt.PointingHandCursor)
        self._dl_back_btn.clicked.connect(self._on_dl_back)
        self._dl_back_btn.hide()
        actions.addWidget(self._dl_back_btn)

        self._dl_retry_btn = QPushButton("Повторить")
        self._dl_retry_btn.setObjectName("primaryBtn")
        self._dl_retry_btn.setCursor(Qt.PointingHandCursor)
        self._dl_retry_btn.clicked.connect(self._start_download)
        self._dl_retry_btn.hide()
        actions.addWidget(self._dl_retry_btn)

        self._dl_cancel_btn = QPushButton("Отмена")
        self._dl_cancel_btn.setObjectName("linkBtn")
        self._dl_cancel_btn.setCursor(Qt.PointingHandCursor)
        self._dl_cancel_btn.clicked.connect(self._on_dl_cancel)
        actions.addWidget(self._dl_cancel_btn)

        outer.addLayout(actions)
        outer.addStretch(4)
        return page

    # ------------------------------------------------------------- start download

    def _start_download(self) -> None:
        if not self._save_pre_download_config():
            return

        self._goto(len(STEPS))
        self._dl_error.hide()
        self._dl_retry_btn.hide()
        self._dl_back_btn.hide()
        self._dl_cancel_btn.show()
        self._dl_bar.setRange(0, 0)
        self._dl_title.setText(f"Скачивается {self._chosen_model}")
        self._dl_meta.setText("Подключение к Hugging Face…")

        thread = DownloaderThread(self._chosen_model, models_dir())
        thread.progress.connect(self._on_dl_progress)
        thread.finished_ok.connect(self._on_dl_finished)
        thread.failed.connect(self._on_dl_failed)
        thread.finished.connect(thread.deleteLater)
        self._dl_thread = thread
        thread.start()

    def _on_dl_progress(self, downloaded: int, total: int) -> None:
        self._dl_progress_value = (downloaded, total)
        if total > 0:
            pct = int(downloaded * 100 / total) if total else 0
            self._dl_bar.setRange(0, 100)
            self._dl_bar.setValue(min(100, pct))
            self._dl_meta.setText(
                f"{_fmt_size(downloaded)} / {_fmt_size(total)} · {pct}%"
            )
        else:
            self._dl_bar.setRange(0, 0)
            self._dl_meta.setText(f"Скачано {_fmt_size(downloaded)}")

    def _on_dl_finished(self, _path: str) -> None:
        try:
            self._cfg.onboarded = True
            save_config(self._cfg)
        except Exception as e:
            logger.error(f"failed to mark onboarded: {e}")
            self._on_dl_failed(f"Не удалось записать config.yaml: {e}")
            return

        self._dl_bar.setRange(0, 100)
        self._dl_bar.setValue(100)
        self._dl_title.setText("Готово")
        self._dl_meta.setText("Запускаю WinWhisp…")
        self._dl_cancel_btn.hide()

        self._done = True
        QTimer.singleShot(450, self._emit_completed)

    def _emit_completed(self) -> None:
        self.completed.emit()
        self.close()

    def _on_dl_failed(self, msg: str) -> None:
        self._dl_bar.setRange(0, 100)
        self._dl_bar.setValue(0)
        self._dl_title.setText("Не получилось скачать модель")
        self._dl_meta.setText(f"Модель: {self._chosen_model}")
        self._dl_error.setText(msg)
        self._dl_error.show()
        self._dl_cancel_btn.hide()
        self._dl_retry_btn.show()
        self._dl_back_btn.show()

    def _on_dl_cancel(self) -> None:
        if self._dl_thread is not None and self._dl_thread.isRunning():
            self._dl_thread.cancel()
            self._dl_thread.quit()
            self._dl_thread.wait(2000)
        self._dl_thread = None
        self._goto(len(STEPS) - 1)

    def _on_dl_back(self) -> None:
        self._dl_thread = None
        self._goto(len(STEPS) - 1)

    # ------------------------------------------------------------- save

    def _save_pre_download_config(self) -> bool:
        target = self._chosen_dir
        if not self._validate_dir(target):
            return False

        try:
            if target.resolve() == default_appdata_dir().resolve():
                clear_override()
            else:
                write_override(target)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить путь к папке:\n{e}")
            return False

        self._cfg.asr.model = self._chosen_model
        self._cfg.hotkey.combo = self._chosen_hotkey
        self._cfg.onboarded = False

        try:
            save_config(self._cfg, config_path())
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить config.yaml:\n{e}")
            return False
        return True

    # ------------------------------------------------------------- close

    def closeEvent(self, event) -> None:
        if self._done:
            super().closeEvent(event)
            return

        if self._dl_thread is not None and self._dl_thread.isRunning():
            self._dl_thread.cancel()
            self._dl_thread.quit()
            self._dl_thread.wait(2000)
            self._dl_thread = None

        self.cancelled.emit()
        super().closeEvent(event)
