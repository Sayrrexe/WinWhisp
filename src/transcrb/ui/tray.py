from __future__ import annotations

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from transcrb.paths import resources_dir


_ICON_SIZE = 64
_ACCENT = QColor("#31D27A")
_BACKGROUND = QColor(12, 12, 14)
_NOTIFY_TIMEOUT_MS = 3000


def _fallback_icon() -> QIcon:
    pm = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    backdrop = QPainterPath()
    backdrop.addRoundedRect(QRectF(4, 4, 56, 56), 14, 14)
    painter.fillPath(backdrop, QBrush(_BACKGROUND))

    painter.setPen(Qt.NoPen)
    painter.setBrush(_ACCENT)
    painter.drawRoundedRect(QRectF(22, 16, 20, 28), 10, 10)

    painter.setBrush(Qt.NoBrush)
    painter.setPen(_ACCENT)
    for i, radius in enumerate((32, 40, 48)):
        painter.setOpacity(1.0 - i * 0.25)
        offset = radius / 2
        painter.drawArc(
            QRectF(32 - offset, 32 - offset, radius, radius),
            30 * 16,
            120 * 16,
        )
    painter.end()
    return QIcon(pm)


class TrayIcon(QObject):
    quit_requested = Signal()
    open_requested = Signal()
    reload_requested = Signal()

    def __init__(self, app_title: str = "WinWhisp") -> None:
        super().__init__()
        self._title = app_title
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(self._load_icon())
        self._tray.setToolTip(app_title)
        self._menu = self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)

    def _load_icon(self) -> QIcon:
        icon_file = resources_dir() / "icon.ico"
        if icon_file.exists():
            return QIcon(str(icon_file))
        return _fallback_icon()

    def _build_menu(self) -> QMenu:
        menu = QMenu()

        a_open = QAction("Открыть", menu)
        a_open.triggered.connect(self.open_requested.emit)
        menu.addAction(a_open)

        menu.addSeparator()

        a_quit = QAction("Выход", menu)
        a_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(a_quit)

        return menu

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.open_requested.emit()

    def show(self) -> None:
        self._tray.show()

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.Information, _NOTIFY_TIMEOUT_MS)

    def set_tooltip(self, text: str) -> None:
        self._tray.setToolTip(text)
