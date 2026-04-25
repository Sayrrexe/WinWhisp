from __future__ import annotations

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from transcrb.paths import resources_dir


def _fallback_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(4, 4, 56, 56), 14, 14)
    p.fillPath(path, QBrush(QColor(12, 12, 14)))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#31D27A"))
    body = QRectF(22, 16, 20, 28)
    p.drawRoundedRect(body, 10, 10)
    p.setBrush(Qt.NoBrush)
    pen_col = QColor("#31D27A")
    p.setPen(pen_col)
    for i, r in enumerate((32, 40, 48)):
        p.setOpacity(1.0 - i * 0.25)
        p.drawArc(QRectF(32 - r / 2, 32 - r / 2, r, r), 30 * 16, 120 * 16)
    p.end()
    return QIcon(pm)


class TrayIcon(QObject):
    quit_requested = Signal()
    open_requested = Signal()
    reload_requested = Signal()

    def __init__(self, app_title: str = "WinWhisp") -> None:
        super().__init__()
        self._title = app_title
        self._tray = QSystemTrayIcon()
        icon_file = resources_dir() / "icon.ico"
        icon = QIcon(str(icon_file)) if icon_file.exists() else _fallback_icon()
        self._tray.setIcon(icon)
        self._tray.setToolTip(app_title)

        menu = QMenu()

        a_open = QAction("Открыть", menu)
        a_open.triggered.connect(self.open_requested.emit)
        menu.addAction(a_open)

        menu.addSeparator()

        a_quit = QAction("Выход", menu)
        a_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(a_quit)

        self._menu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.open_requested.emit()

    def show(self) -> None:
        self._tray.show()

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def set_tooltip(self, text: str) -> None:
        self._tray.setToolTip(text)
