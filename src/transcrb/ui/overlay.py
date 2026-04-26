from __future__ import annotations

import sys
from typing import Callable

import numpy as np
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QGuiApplication, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from transcrb.config import OverlayCfg
from transcrb.ui.equalizer import EqualizerBars
from transcrb.ui.mic_icon import MicRadarIcon
from transcrb.ui.spinner import Spinner


class PillOverlay(QWidget):
    _MODE_RECORDING = 0
    _MODE_RESULT = 1
    _MODE_BUSY = 2

    _FADE_IN_MS = 120
    _FADE_RESULT_MS = 140
    _FADE_OUT_MS = 180
    _POST_HIDE_DELAY_MS = 260
    _HIDE_OPACITY_THRESHOLD = 0.05
    _MIN_HOLD_MS = 1500
    _PASTE_CALLBACK_DELAY_MS = 60

    def __init__(self, cfg: OverlayCfg) -> None:
        super().__init__(None)
        self._cfg = cfg
        self._bg = QColor(*cfg.background_rgba)
        self._mode = self._MODE_RECORDING
        self._paste_callback: Callable[[], None] | None = None
        self._last_hold_ms: int = 5000
        self._pad_h = max(10, int(cfg.height * 0.15))

        self._base_flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(cfg.width, cfg.height)
        self._apply_clickthrough(True)

        self._stack_host = QWidget(self)
        self._stack_host.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._stack_host.setStyleSheet("background: transparent;")
        self._stack_host.setGeometry(0, 0, cfg.width, cfg.height)

        self._stack = QStackedLayout(self._stack_host)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self._recording_widget = self._build_recording_widget()
        self._result_widget = self._build_result_widget()
        self._busy_widget = self._build_busy_widget()
        self._stack.addWidget(self._recording_widget)
        self._stack.addWidget(self._result_widget)
        self._stack.addWidget(self._busy_widget)
        self._stack.setCurrentWidget(self._recording_widget)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.hide_fade)

        self.setWindowOpacity(0.0)
        self._reposition()

    def _disable_windows_border(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            if not hwnd:
                return
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWA_BORDER_COLOR = 34
            DWMWCP_DONOTROUND = 1
            DWMWA_COLOR_NONE = 0xFFFFFFFE
            pref = ctypes.c_int(DWMWCP_DONOTROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(pref),
                ctypes.sizeof(pref),
            )
            color = ctypes.c_uint(DWMWA_COLOR_NONE)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_BORDER_COLOR,
                ctypes.byref(color),
                ctypes.sizeof(color),
            )
        except Exception:
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._disable_windows_border()

    def _apply_clickthrough(self, ct: bool) -> None:
        flags = self._base_flags
        if ct:
            flags |= Qt.WindowTransparentForInput
        was_visible = self.isVisible()
        pos = self.pos() if was_visible else None
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, ct)
        if was_visible:
            if pos is not None:
                self.move(pos)
            self.show()

    def _make_pill_host(self) -> tuple[QWidget, QHBoxLayout]:
        w = QWidget()
        w.setAttribute(Qt.WA_TransparentForMouseEvents)
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, self._pad_h, 20, self._pad_h)
        layout.setSpacing(10)
        return w, layout

    def _make_mic_icon(self, parent: QWidget) -> MicRadarIcon:
        icon = MicRadarIcon(parent, accent=self._cfg.accent_color, fps=self._cfg.fps)
        icon_size = self._cfg.height - self._pad_h * 2 - 2
        icon.setFixedSize(icon_size, icon_size)
        return icon

    def _build_recording_widget(self) -> QWidget:
        w, layout = self._make_pill_host()
        icon = self._make_mic_icon(w)
        layout.addWidget(icon, 0, Qt.AlignVCenter)

        bars = EqualizerBars(
            w,
            n_bars=self._cfg.bars,
            fps=self._cfg.fps,
            accent=self._cfg.accent_color,
        )
        layout.addWidget(bars, 1)

        self._icon = icon
        self._bars = bars
        return w

    def _build_busy_widget(self) -> QWidget:
        w, layout = self._make_pill_host()
        icon = self._make_mic_icon(w)
        icon.set_active(False)
        layout.addWidget(icon, 0, Qt.AlignVCenter)

        label = QLabel("Обрабатываю…", w)
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        lf = QFont()
        lf.setPixelSize(max(11, int(self._cfg.height * 0.17)))
        lf.setBold(True)
        label.setFont(lf)
        label.setStyleSheet("color: #E8E8EA;")
        layout.addWidget(label, 1)

        spin = Spinner(w, accent=self._cfg.accent_color, fps=self._cfg.fps)
        spin_size = max(20, icon.width() - 8)
        spin.setFixedSize(spin_size, spin_size)
        layout.addWidget(spin, 0, Qt.AlignVCenter)

        self._spinner = spin
        self._busy_icon = icon
        return w

    def _build_result_widget(self) -> QWidget:
        radius = self._cfg.height // 2
        w = QWidget()
        w.setStyleSheet("background: transparent;")

        btn = QPushButton(w)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Нажмите, чтобы вставить ещё раз")
        btn.setGeometry(0, 0, self._cfg.width, self._cfg.height)
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: {radius}px;
            }}
            QPushButton:hover {{
                background: rgba(49, 210, 122, 0.10);
            }}
            QPushButton:pressed {{
                background: rgba(49, 210, 122, 0.18);
            }}
            """
        )
        btn.clicked.connect(self._on_paste_clicked)
        btn.installEventFilter(self)

        content = QWidget(w)
        content.setAttribute(Qt.WA_TransparentForMouseEvents)
        content.setStyleSheet("background: transparent;")
        content.setGeometry(0, 0, self._cfg.width, self._cfg.height)

        outer = QHBoxLayout(content)
        outer.setContentsMargins(16, self._pad_h, 16, self._pad_h)
        outer.setSpacing(0)
        outer.addStretch(1)

        accent = self._cfg.accent_color
        icon = self._make_result_label(content, "↻", max(20, int(self._cfg.height * 0.36)), accent, bold=True)
        outer.addWidget(icon, 0, Qt.AlignVCenter)
        outer.addSpacing(18)

        text_host = QWidget(content)
        text_host.setAttribute(Qt.WA_TransparentForMouseEvents)
        text_host.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_host)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        title = self._make_result_label(
            text_host, "Вставить ещё раз", max(12, int(self._cfg.height * 0.18)), accent, bold=True
        )
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_layout.addWidget(title)

        sub = self._make_result_label(
            text_host, "текст в буфере обмена", max(10, int(self._cfg.height * 0.135)), "#8B8D94", bold=False
        )
        sub.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_layout.addWidget(sub)

        outer.addWidget(text_host, 0, Qt.AlignVCenter)
        outer.addStretch(1)

        content.raise_()

        self._result_btn = btn
        return w

    @staticmethod
    def _make_result_label(parent: QWidget, text: str, px: int, color: str, bold: bool) -> QLabel:
        label = QLabel(text, parent)
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        font = QFont()
        font.setPixelSize(px)
        if bold:
            font.setBold(True)
        label.setFont(font)
        label.setStyleSheet(f"color: {color};")
        return label

    def _on_paste_clicked(self) -> None:
        cb = self._paste_callback
        self._auto_hide_timer.stop()
        self.hide_fade()
        if cb is not None:
            QTimer.singleShot(self._PASTE_CALLBACK_DELAY_MS, cb)

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        x = avail.x() + (avail.width() - self.width()) // 2
        y = avail.y() + avail.height() - self.height() - self._cfg.bottom_margin_px
        self.setGeometry(x, y, self.width(), self.height())

    def _animate_to(self, target: float, duration_ms: int) -> None:
        self._opacity_anim.stop()
        self._opacity_anim.setDuration(duration_ms)
        self._opacity_anim.setStartValue(self.windowOpacity())
        self._opacity_anim.setEndValue(target)
        self._opacity_anim.start()

    def _switch_mode(self, mode: int, widget: QWidget, clickthrough: bool) -> None:
        if self._mode == mode:
            return
        self._mode = mode
        self._stack.setCurrentWidget(widget)
        self._apply_clickthrough(clickthrough)

    def _show_with_fade_in(self, duration_ms: int) -> None:
        self._reposition()
        self.show()
        self.raise_()
        self._animate_to(1.0, duration_ms)

    def show_fade(self) -> None:
        self._spinner.stop()
        self._switch_mode(self._MODE_RECORDING, self._recording_widget, True)
        self._auto_hide_timer.stop()
        self._icon.set_active(True)
        self._bars.set_idle()
        self._show_with_fade_in(self._FADE_IN_MS)

    def show_busy(self) -> None:
        self._switch_mode(self._MODE_BUSY, self._busy_widget, True)
        self._spinner.start()
        self._busy_icon.set_active(False)
        self._auto_hide_timer.stop()
        self._show_with_fade_in(self._FADE_IN_MS)

    def show_result(self, on_paste_again: Callable[[], None], hold_ms: int = 5000) -> None:
        self._spinner.stop()
        self._paste_callback = on_paste_again
        self._last_hold_ms = max(self._MIN_HOLD_MS, hold_ms)
        self._switch_mode(self._MODE_RESULT, self._result_widget, False)
        self._icon.set_active(False)
        self._bars.set_idle()
        self._show_with_fade_in(self._FADE_RESULT_MS)
        self._auto_hide_timer.start(self._last_hold_ms)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "_result_btn", None) and self._mode == self._MODE_RESULT:
            et = event.type()
            if et == QEvent.Enter:
                self._auto_hide_timer.stop()
            elif et == QEvent.Leave:
                self._auto_hide_timer.start(self._last_hold_ms)
        return super().eventFilter(obj, event)

    def hide_fade(self) -> None:
        self._auto_hide_timer.stop()
        self._icon.set_active(False)
        self._bars.set_idle()
        self._spinner.stop()
        self._animate_to(0.0, self._FADE_OUT_MS)
        QTimer.singleShot(self._POST_HIDE_DELAY_MS, self._post_hide)

    def _post_hide(self) -> None:
        if self.windowOpacity() >= self._HIDE_OPACITY_THRESHOLD:
            return
        self.hide()
        self._spinner.stop()
        self._switch_mode(self._MODE_RECORDING, self._recording_widget, True)

    def update_level(self, rms: float, bands) -> None:
        if self._mode != self._MODE_RECORDING:
            return
        if bands is None:
            bands = np.full(self._cfg.bars, max(0.1, min(1.0, rms * 8.0)), dtype=np.float32)
        self._bars.set_bands(bands, active=True)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        path = QPainterPath()
        radius = rect.height() / 2
        path.addRoundedRect(rect, radius, radius)
        p.fillPath(path, self._bg)
