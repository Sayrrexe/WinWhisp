from __future__ import annotations

import sys
from typing import Callable

import numpy as np
from PySide6.QtCore import (
    QEasingCurve,
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

    def __init__(self, cfg: OverlayCfg) -> None:
        super().__init__(None)
        self._cfg = cfg
        self._bg = QColor(*cfg.background_rgba)
        self._mode = self._MODE_RECORDING
        self._paste_callback: Callable[[], None] | None = None

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

    def _build_recording_widget(self) -> QWidget:
        w = QWidget()
        w.setAttribute(Qt.WA_TransparentForMouseEvents)
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        pad_h = max(10, int(self._cfg.height * 0.15))
        layout.setContentsMargins(16, pad_h, 20, pad_h)
        layout.setSpacing(10)

        icon = MicRadarIcon(w, accent=self._cfg.accent_color, fps=self._cfg.fps)
        icon_size = self._cfg.height - pad_h * 2 - 2
        icon.setFixedSize(icon_size, icon_size)
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
        w = QWidget()
        w.setAttribute(Qt.WA_TransparentForMouseEvents)
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        pad_h = max(10, int(self._cfg.height * 0.15))
        layout.setContentsMargins(16, pad_h, 20, pad_h)
        layout.setSpacing(10)

        icon = MicRadarIcon(w, accent=self._cfg.accent_color, fps=self._cfg.fps)
        icon_size = self._cfg.height - pad_h * 2 - 2
        icon.setFixedSize(icon_size, icon_size)
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
        spin_size = max(20, icon_size - 8)
        spin.setFixedSize(spin_size, spin_size)
        layout.addWidget(spin, 0, Qt.AlignVCenter)
        self._spinner = spin
        self._busy_icon = icon
        return w

    def _build_result_widget(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(w)
        pad_h = max(10, int(self._cfg.height * 0.15))
        layout.setContentsMargins(16, pad_h, 14, pad_h)
        layout.setSpacing(10)

        check = QLabel("✓", w)
        check.setAttribute(Qt.WA_TransparentForMouseEvents)
        check_font = QFont()
        check_font.setPixelSize(max(18, int(self._cfg.height * 0.32)))
        check_font.setBold(True)
        check.setFont(check_font)
        check.setStyleSheet(f"color: {self._cfg.accent_color};")
        check.setFixedWidth(max(20, int(self._cfg.height * 0.3)))
        layout.addWidget(check, 0, Qt.AlignVCenter)

        label = QLabel("Скопировано", w)
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        label_font = QFont()
        label_font.setPixelSize(max(11, int(self._cfg.height * 0.17)))
        label.setFont(label_font)
        label.setStyleSheet("color: #E8E8EA;")
        label.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(label, 1)
        self._result_label = label

        btn = QPushButton("Вставить ещё раз", w)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn_font = QFont()
        btn_font.setPixelSize(max(10, int(self._cfg.height * 0.16)))
        btn_font.setBold(True)
        btn.setFont(btn_font)
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background: {self._cfg.accent_color};
                color: #0C0C0E;
                border: none;
                border-radius: {int(self._cfg.height * 0.22)}px;
                padding: {max(4, int(self._cfg.height * 0.08))}px {max(8, int(self._cfg.height * 0.14))}px;
            }}
            QPushButton:hover {{ background: #3FDE86; }}
            QPushButton:pressed {{ background: #27B366; }}
            """
        )
        btn.clicked.connect(self._on_paste_clicked)
        layout.addWidget(btn, 0, Qt.AlignVCenter)
        self._result_btn = btn
        return w

    def _on_paste_clicked(self) -> None:
        cb = self._paste_callback
        self._auto_hide_timer.stop()
        self.hide_fade()
        if cb is not None:
            QTimer.singleShot(60, cb)

    def _reposition(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        x = avail.x() + (avail.width() - self.width()) // 2
        y = avail.y() + avail.height() - self.height() - self._cfg.bottom_margin_px
        self.setGeometry(x, y, self.width(), self.height())

    def show_fade(self) -> None:
        self._spinner.stop()
        if self._mode != self._MODE_RECORDING:
            self._stack.setCurrentWidget(self._recording_widget)
            self._mode = self._MODE_RECORDING
            self._apply_clickthrough(True)
        self._auto_hide_timer.stop()
        self._reposition()
        self._icon.set_active(True)
        self._bars.set_idle()
        self.show()
        self.raise_()
        self._opacity_anim.stop()
        self._opacity_anim.setDuration(120)
        self._opacity_anim.setStartValue(self.windowOpacity())
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()

    def show_busy(self) -> None:
        if self._mode != self._MODE_BUSY:
            self._mode = self._MODE_BUSY
            self._stack.setCurrentWidget(self._busy_widget)
            self._apply_clickthrough(True)
        self._spinner.start()
        self._busy_icon.set_active(False)
        self._auto_hide_timer.stop()
        self._reposition()
        self.show()
        self.raise_()
        self._opacity_anim.stop()
        self._opacity_anim.setDuration(120)
        self._opacity_anim.setStartValue(self.windowOpacity())
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()

    def show_result(self, preview: str, on_paste_again: Callable[[], None], hold_ms: int = 8000) -> None:
        self._spinner.stop()
        self._paste_callback = on_paste_again
        self._result_label.setText(self._status_text(preview))
        if self._mode != self._MODE_RESULT:
            self._mode = self._MODE_RESULT
            self._stack.setCurrentWidget(self._result_widget)
            self._apply_clickthrough(False)
        self._icon.set_active(False)
        self._bars.set_idle()
        self._reposition()
        self.show()
        self.raise_()
        self._opacity_anim.stop()
        self._opacity_anim.setDuration(140)
        self._opacity_anim.setStartValue(self.windowOpacity())
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()
        self._auto_hide_timer.start(max(1500, hold_ms))

    def hide_fade(self) -> None:
        self._auto_hide_timer.stop()
        self._icon.set_active(False)
        self._bars.set_idle()
        self._spinner.stop()
        self._opacity_anim.stop()
        self._opacity_anim.setDuration(180)
        self._opacity_anim.setStartValue(self.windowOpacity())
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.start()
        QTimer.singleShot(260, self._post_hide)

    def _post_hide(self) -> None:
        if self.windowOpacity() < 0.05:
            self.hide()
            self._spinner.stop()
            if self._mode != self._MODE_RECORDING:
                self._mode = self._MODE_RECORDING
                self._stack.setCurrentWidget(self._recording_widget)
                self._apply_clickthrough(True)

    def _status_text(self, preview: str) -> str:
        p = (preview or "").strip().replace("\n", " ")
        if not p:
            return "Скопировано в буфер"
        if len(p) > 38:
            p = p[:37].rstrip() + "…"
        return p

    def update_level(self, rms: float, bands) -> None:
        if self._mode != self._MODE_RECORDING:
            return
        if bands is None:
            arr = np.full(self._cfg.bars, max(0.1, min(1.0, rms * 8.0)), dtype=np.float32)
            self._bars.set_bands(arr, active=True)
        else:
            self._bars.set_bands(bands, active=True)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        path = QPainterPath()
        radius = rect.height() / 2
        path.addRoundedRect(rect, radius, radius)
        p.fillPath(path, self._bg)
