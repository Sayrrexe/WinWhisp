from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QWidget,
)


_RESIZE_MARGIN = 6
_TITLE_HEIGHT = 44
_BTN_W = 46


_CHROME_STYLE = """
QWidget#titleBar {
    background: #0A0A0B;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
QLabel#titleBarTitle {
    color: #E8E8EA;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.1px;
}
QLabel#titleBarSub {
    color: #5A5C63;
    font-size: 11.5px;
    font-weight: 500;
}
"""


class _ChromeButton(QPushButton):
    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self._maximized = False
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(_BTN_W, _TITLE_HEIGHT)
        self.setFlat(True)
        self.setStyleSheet("background: transparent; border: none;")

    def set_max_state(self, maximized: bool) -> None:
        if self._maximized != maximized:
            self._maximized = maximized
            self.update()

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        hovered = self.underMouse()
        pressed = self.isDown()

        if hovered or pressed:
            if self._kind == "close":
                bg = QColor("#C42B1C") if not pressed else QColor("#A8261A")
            else:
                bg = QColor("#1A1A1E") if not pressed else QColor("#222227")
            p.fillRect(self.rect(), bg)

        if self._kind == "close" and (hovered or pressed):
            ink = QColor("#FFFFFF")
        else:
            ink = QColor("#E8E8EA") if hovered or pressed else QColor("#9A9CA3")

        pen = QPen(ink, 1.4)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        cx = self.width() / 2
        cy = self.height() / 2
        s = 5.0

        if self._kind == "min":
            p.drawLine(QPointF(cx - s, cy), QPointF(cx + s, cy))
        elif self._kind == "max":
            if self._maximized:
                back = QRectF(cx - s + 2, cy - s, 2 * s - 2, 2 * s - 2)
                front = QRectF(cx - s, cy - s + 2, 2 * s - 2, 2 * s - 2)
                p.drawRect(back)
                p.fillRect(front.adjusted(0.5, 0.5, -0.5, -0.5), QColor("#0A0A0B") if not (hovered or pressed) else (
                    QColor("#1A1A1E") if self._kind != "close" else QColor("#C42B1C")
                ))
                p.drawRect(front)
            else:
                p.drawRect(QRectF(cx - s, cy - s, 2 * s, 2 * s))
        elif self._kind == "close":
            p.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
            p.drawLine(QPointF(cx - s, cy + s), QPointF(cx + s, cy - s))

        p.end()


class TitleBar(QWidget):
    minimize_requested = Signal()
    maximize_toggle_requested = Signal()
    close_requested = Signal()

    def __init__(
        self,
        title: str,
        *,
        subtitle: str = "",
        logo: QPixmap | None = None,
        show_maximize: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(_TITLE_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_StyledBackground, True)

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 0, 0, 0)
        h.setSpacing(10)

        if logo is not None:
            logo_lbl = QLabel()
            logo_lbl.setPixmap(logo)
            logo_lbl.setFixedSize(logo.size())
            logo_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            h.addWidget(logo_lbl, 0, Qt.AlignVCenter)

        text_box = QHBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(8)
        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("titleBarTitle")
        self._title_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        text_box.addWidget(self._title_lbl, 0, Qt.AlignVCenter)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("titleBarSub")
            sub.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            text_box.addWidget(sub, 0, Qt.AlignVCenter)
        text_wrap = QWidget()
        text_wrap.setLayout(text_box)
        text_wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        h.addWidget(text_wrap, 1)

        self._btn_min = _ChromeButton("min")
        self._btn_min.setToolTip("Свернуть")
        self._btn_min.clicked.connect(self.minimize_requested.emit)
        h.addWidget(self._btn_min)

        if show_maximize:
            self._btn_max: _ChromeButton | None = _ChromeButton("max")
            self._btn_max.setToolTip("Развернуть")
            self._btn_max.clicked.connect(self.maximize_toggle_requested.emit)
            h.addWidget(self._btn_max)
        else:
            self._btn_max = None

        self._btn_close = _ChromeButton("close")
        self._btn_close.setToolTip("Закрыть")
        self._btn_close.clicked.connect(self.close_requested.emit)
        h.addWidget(self._btn_close)

    def set_title(self, text: str) -> None:
        self._title_lbl.setText(text)

    def set_max_state(self, maximized: bool) -> None:
        if self._btn_max is None:
            return
        self._btn_max.set_max_state(maximized)
        self._btn_max.setToolTip("Восстановить" if maximized else "Развернуть")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            wh = self.window().windowHandle()
            if wh is not None:
                wh.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.maximize_toggle_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class FramelessMainWindow(QMainWindow):
    def __init__(self, *args, **kwargs) -> None:
        self._title_bar: TitleBar | None = None
        self._dwm_applied = False
        super().__init__(*args, **kwargs)
        self.setWindowFlag(Qt.FramelessWindowHint, True)

    def install_titlebar(self, title_bar: TitleBar) -> None:
        title_bar.minimize_requested.connect(self.showMinimized)
        title_bar.maximize_toggle_requested.connect(self._toggle_max_restore)
        title_bar.close_requested.connect(self.close)
        self._title_bar = title_bar

    def _toggle_max_restore(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if self._title_bar is not None:
            self._title_bar.set_max_state(self.isMaximized())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._dwm_applied:
            self._apply_win11_chrome()
            self._dwm_applied = True

    def _apply_win11_chrome(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
        except Exception:
            return

        hwnd = int(self.winId())
        if not hwnd:
            return

        try:
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

        try:
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            corner = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner),
                ctypes.sizeof(corner),
            )
        except Exception:
            pass

        try:
            class MARGINS(ctypes.Structure):
                _fields_ = [
                    ("cxLeftWidth", ctypes.c_int),
                    ("cxRightWidth", ctypes.c_int),
                    ("cyTopHeight", ctypes.c_int),
                    ("cyBottomHeight", ctypes.c_int),
                ]

            margins = MARGINS(1, 1, 1, 1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
                hwnd, ctypes.byref(margins)
            )
        except Exception:
            pass

    def nativeEvent(self, eventType, message):
        if sys.platform != "win32":
            return super().nativeEvent(eventType, message)
        if eventType not in ("windows_generic_MSG", b"windows_generic_MSG"):
            return super().nativeEvent(eventType, message)

        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return super().nativeEvent(eventType, message)

        msg = wintypes.MSG.from_address(int(message))
        WM_NCHITTEST = 0x0084
        WM_GETMINMAXINFO = 0x0024

        if msg.message == WM_GETMINMAXINFO:
            return self._handle_minmaxinfo(ctypes, msg)

        if msg.message != WM_NCHITTEST:
            return super().nativeEvent(eventType, message)

        if self.isMaximized() or self.isFullScreen():
            return super().nativeEvent(eventType, message)

        x = ctypes.c_short(msg.lParam & 0xFFFF).value
        y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        rect = self.frameGeometry()

        m = _RESIZE_MARGIN
        left = x < rect.left() + m
        right = x >= rect.right() - m
        top = y < rect.top() + m
        bottom = y >= rect.bottom() - m

        HTLEFT = 10
        HTRIGHT = 11
        HTTOP = 12
        HTTOPLEFT = 13
        HTTOPRIGHT = 14
        HTBOTTOM = 15
        HTBOTTOMLEFT = 16
        HTBOTTOMRIGHT = 17

        if top and left:
            return True, HTTOPLEFT
        if top and right:
            return True, HTTOPRIGHT
        if bottom and left:
            return True, HTBOTTOMLEFT
        if bottom and right:
            return True, HTBOTTOMRIGHT
        if left:
            return True, HTLEFT
        if right:
            return True, HTRIGHT
        if top:
            return True, HTTOP
        if bottom:
            return True, HTBOTTOM

        return super().nativeEvent(eventType, message)

    def _handle_minmaxinfo(self, ctypes, msg):
        try:
            screen = self.screen() or QGuiApplication.primaryScreen()
            if screen is None:
                return False, 0
            avail = screen.availableGeometry()
            geom = screen.geometry()

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class MINMAXINFO(ctypes.Structure):
                _fields_ = [
                    ("ptReserved", POINT),
                    ("ptMaxSize", POINT),
                    ("ptMaxPosition", POINT),
                    ("ptMinTrackSize", POINT),
                    ("ptMaxTrackSize", POINT),
                ]

            info = MINMAXINFO.from_address(int(msg.lParam))
            info.ptMaxSize.x = avail.width()
            info.ptMaxSize.y = avail.height()
            info.ptMaxPosition.x = avail.x() - geom.x()
            info.ptMaxPosition.y = avail.y() - geom.y()
            return True, 0
        except Exception:
            return False, 0


def chrome_stylesheet() -> str:
    return _CHROME_STYLE
