from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
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


_WM_NCHITTEST = 0x0084
_WM_GETMINMAXINFO = 0x0024

_HTLEFT = 10
_HTRIGHT = 11
_HTTOP = 12
_HTTOPLEFT = 13
_HTTOPRIGHT = 14
_HTBOTTOM = 15
_HTBOTTOMLEFT = 16
_HTBOTTOMRIGHT = 17


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
        active = hovered or pressed

        if active:
            p.fillRect(self.rect(), self._background_color(pressed))

        pen = QPen(self._ink_color(active), 1.4)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        cx = self.width() / 2
        cy = self.height() / 2
        s = 5.0

        if self._kind == "min":
            p.drawLine(QPointF(cx - s, cy), QPointF(cx + s, cy))
        elif self._kind == "max":
            self._paint_max_glyph(p, cx, cy, s, active)
        elif self._kind == "close":
            p.drawLine(QPointF(cx - s, cy - s), QPointF(cx + s, cy + s))
            p.drawLine(QPointF(cx - s, cy + s), QPointF(cx + s, cy - s))

        p.end()

    def _background_color(self, pressed: bool) -> QColor:
        if self._kind == "close":
            return QColor("#A8261A") if pressed else QColor("#C42B1C")
        return QColor("#222227") if pressed else QColor("#1A1A1E")

    def _ink_color(self, active: bool) -> QColor:
        if self._kind == "close" and active:
            return QColor("#FFFFFF")
        return QColor("#E8E8EA") if active else QColor("#9A9CA3")

    def _paint_max_glyph(self, p: QPainter, cx: float, cy: float, s: float, active: bool) -> None:
        if not self._maximized:
            p.drawRect(QRectF(cx - s, cy - s, 2 * s, 2 * s))
            return

        back = QRectF(cx - s + 2, cy - s, 2 * s - 2, 2 * s - 2)
        front = QRectF(cx - s, cy - s + 2, 2 * s - 2, 2 * s - 2)
        fill = QColor("#1A1A1E") if active else QColor("#0A0A0B")
        p.drawRect(back)
        p.fillRect(front.adjusted(0.5, 0.5, -0.5, -0.5), fill)
        p.drawRect(front)


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

        h.addWidget(self._build_text_block(title, subtitle), 1)

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

    def _build_text_block(self, title: str, subtitle: str) -> QWidget:
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

        wrap = QWidget()
        wrap.setLayout(text_box)
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return wrap

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

        _dwm_set_int_attr(ctypes, hwnd, 20, 1)
        _dwm_set_int_attr(ctypes, hwnd, 33, 2)

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

        if msg.message == _WM_GETMINMAXINFO:
            return self._handle_minmaxinfo(ctypes, msg)

        if msg.message != _WM_NCHITTEST:
            return super().nativeEvent(eventType, message)

        if self.isMaximized() or self.isFullScreen():
            return super().nativeEvent(eventType, message)

        hit = self._resolve_hit_zone(ctypes, msg)
        if hit is not None:
            return True, hit
        return super().nativeEvent(eventType, message)

    def _resolve_hit_zone(self, ctypes, msg) -> int | None:
        px = ctypes.c_short(msg.lParam & 0xFFFF).value
        py = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        dpr = self.devicePixelRatioF() or 1.0
        x = px / dpr
        y = py / dpr
        rect = self.frameGeometry()

        m = _RESIZE_MARGIN
        left = x < rect.left() + m
        right = x >= rect.right() - m
        top = y < rect.top() + m
        bottom = y >= rect.bottom() - m

        if top and left:
            return _HTTOPLEFT
        if top and right:
            return _HTTOPRIGHT
        if bottom and left:
            return _HTBOTTOMLEFT
        if bottom and right:
            return _HTBOTTOMRIGHT
        if left:
            return _HTLEFT
        if right:
            return _HTRIGHT
        if top:
            return _HTTOP
        if bottom:
            return _HTBOTTOM
        return None

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


def _dwm_set_int_attr(ctypes, hwnd: int, attr: int, value: int) -> None:
    try:
        v = ctypes.c_int(value)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)
        )
    except Exception:
        pass


def chrome_stylesheet() -> str:
    return _CHROME_STYLE


class LinkButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:
        enabled = self.isEnabled()
        hovered = self.underMouse() and enabled
        pressed = self.isDown() and enabled
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        if pressed:
            bg = QColor("#181820")
        elif hovered:
            bg = QColor("#222227")
        else:
            bg = QColor("#1A1A1E")
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 10, 10)
        border = QColor(255, 255, 255, 51) if hovered else QColor(255, 255, 255, 26)
        p.setPen(QPen(border, 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 9, 9)
        p.setPen(QColor("#E8E8EA"))
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:
        enabled = self.isEnabled()
        hovered = self.underMouse() and enabled
        pressed = self.isDown() and enabled
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        if not enabled:
            bg = QColor("#1A1A1E")
        elif pressed:
            bg = QColor("#28B868")
        elif hovered:
            bg = QColor("#4FE090")
        else:
            bg = QColor("#31D27A")
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 10, 10)
        text_color = QColor("#5A5C63") if not enabled else QColor("#0A0A0B")
        p.setPen(text_color)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()
