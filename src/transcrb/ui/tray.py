from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from transcrb.paths import config_path, resources_dir, vocab_path


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

        a_cfg = QAction("Открыть config.yaml", menu)
        a_cfg.triggered.connect(lambda: _open_in_editor(config_path()))
        menu.addAction(a_cfg)

        a_voc = QAction("Открыть vocab.yaml", menu)
        a_voc.triggered.connect(lambda: _open_in_editor(vocab_path()))
        menu.addAction(a_voc)

        a_reload = QAction("Перезагрузить конфиг", menu)
        a_reload.triggered.connect(self.reload_requested.emit)
        menu.addAction(a_reload)

        menu.addSeparator()

        a_quit = QAction("Выход", menu)
        a_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(a_quit)

        self._menu = menu
        self._tray.setContextMenu(menu)

    def show(self) -> None:
        self._tray.show()

    def notify(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def set_tooltip(self, text: str) -> None:
        self._tray.setToolTip(text)


def _open_in_editor(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    try:
        os.startfile(str(path))  # type: ignore[attr-defined]
    except AttributeError:
        subprocess.Popen(["xdg-open", str(path)])
