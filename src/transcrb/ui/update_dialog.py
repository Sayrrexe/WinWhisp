from __future__ import annotations

import webbrowser

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from transcrb import __version__
from transcrb.updater import (
    UpdateDownloader,
    find_installer_asset,
    is_frozen,
    launch_installer,
)


_STYLE = """
QDialog#updateDlg { background: #0E0E10; }
QLabel#updateTitle {
    color: #E8E8EA;
    font-size: 18px;
    font-weight: 600;
}
QLabel#updateSub {
    color: #8E8E93;
    font-size: 12px;
}
QLabel#updateMeta {
    color: #B0B0B5;
    font-size: 12px;
}
QTextBrowser#updateBody {
    background: #131316;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 12px 14px;
    color: #DCDCE0;
    font-size: 13px;
}
QPushButton#primaryBtn {
    background: #31D27A;
    color: #0A0A0B;
    border: 0;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
}
QPushButton#primaryBtn:hover { background: #3DE085; }
QPushButton#primaryBtn:disabled { background: #2A6F49; color: rgba(10, 10, 11, 0.5); }
QPushButton#linkBtn {
    background: transparent;
    color: #B0B0B5;
    border: 0;
    padding: 8px 12px;
}
QPushButton#linkBtn:hover { color: #E8E8EA; }
QProgressBar {
    background: #1A1A1E;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    color: #E8E8EA;
    text-align: center;
    height: 18px;
}
QProgressBar::chunk { background: #31D27A; border-radius: 5px; }
"""


def _format_size(n: int) -> str:
    if n <= 0:
        return "—"
    units = ["Б", "КБ", "МБ", "ГБ"]
    v = float(n)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.1f} {units[i]}"


class UpdateDialog(QDialog):
    def __init__(self, release: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateDlg")
        self.setStyleSheet(_STYLE)
        self.setWindowTitle("Обновление WinWhisp")
        self.setModal(True)
        self.resize(560, 460)

        self._release = release
        self._asset = find_installer_asset(release)
        self._downloader: UpdateDownloader | None = None
        self._installer_path: str | None = None

        tag = str(release.get("tag_name") or "").lstrip("v")
        body = str(release.get("body") or "Описание изменений отсутствует.").strip()
        url = str(release.get("html_url") or "")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(12)

        title = QLabel(f"Доступна версия {tag}")
        title.setObjectName("updateTitle")
        outer.addWidget(title)

        sub = QLabel(f"Текущая версия: {__version__}")
        sub.setObjectName("updateSub")
        outer.addWidget(sub)

        notes = QTextBrowser()
        notes.setObjectName("updateBody")
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(body)
        notes.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(notes, 1)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        size_text = "—"
        if self._asset:
            size_text = _format_size(int(self._asset.get("size") or 0))
        self._meta_label = QLabel(self._make_meta_text(size_text))
        self._meta_label.setObjectName("updateMeta")
        meta_row.addWidget(self._meta_label)
        meta_row.addStretch(1)
        outer.addLayout(meta_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        outer.addWidget(self._progress)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._open_btn = QPushButton("Открыть на GitHub")
        self._open_btn.setObjectName("linkBtn")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.clicked.connect(lambda: self._open_url(url))
        btn_row.addWidget(self._open_btn)

        btn_row.addStretch(1)

        self._later_btn = QPushButton("Позже")
        self._later_btn.setObjectName("linkBtn")
        self._later_btn.setCursor(Qt.PointingHandCursor)
        self._later_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._later_btn)

        self._action_btn = QPushButton("")
        self._action_btn.setObjectName("primaryBtn")
        self._action_btn.setCursor(Qt.PointingHandCursor)
        self._action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self._action_btn)

        outer.addLayout(btn_row)

        self._set_state_idle()

    def _make_meta_text(self, size_text: str) -> str:
        if self._asset is None:
            return "Установщик не найден в релизе — можно скачать вручную."
        if not is_frozen():
            return (
                "Запущена dev-сборка из исходников — авто-установка недоступна. "
                f"Размер инсталлятора: {size_text}."
            )
        return f"Размер инсталлятора: {size_text}."

    def _set_state_idle(self) -> None:
        if self._asset is None or not is_frozen():
            self._action_btn.setText("Скачать с GitHub")
            self._action_btn.setEnabled(True)
            return
        self._action_btn.setText("Скачать и установить")
        self._action_btn.setEnabled(True)

    def _on_action(self) -> None:
        if self._asset is None or not is_frozen():
            self._open_url(str(self._release.get("html_url") or ""))
            return
        self._start_download()

    def _start_download(self) -> None:
        self._action_btn.setEnabled(False)
        self._action_btn.setText("Скачивание…")
        self._later_btn.setText("Отмена")
        self._later_btn.clicked.disconnect()
        self._later_btn.clicked.connect(self._cancel_download)
        self._progress.setVisible(True)
        self._progress.setValue(0)

        self._downloader = UpdateDownloader(self._asset, parent=self)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished_ok.connect(self._on_downloaded)
        self._downloader.failed.connect(self._on_failed)
        self._downloader.start()

    def _cancel_download(self) -> None:
        if self._downloader is not None:
            self._downloader.cancel()

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int(downloaded * 100 / total)
            self._progress.setRange(0, 100)
            self._progress.setValue(pct)
            self._progress.setFormat(
                f"{_format_size(downloaded)} / {_format_size(total)} ({pct}%)"
            )
        else:
            self._progress.setRange(0, 0)
            self._progress.setFormat(f"{_format_size(downloaded)}")

    def _on_downloaded(self, path: str) -> None:
        self._installer_path = path
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._progress.setFormat("Загружено — запуск установщика…")
        try:
            self._launch_installer()
        except Exception as e:
            logger.error(f"updater: failed to launch installer: {e}")
            self._on_failed(f"Не удалось запустить установщик: {e}")
            return
        self._show_installer_running()

    def _launch_installer(self) -> None:
        if not self._installer_path:
            return
        launch_installer(self._installer_path)

    def _show_installer_running(self) -> None:
        self._meta_label.setText(
            "Установщик запущен. Подтвердите UAC и дождитесь окончания установки — "
            "WinWhisp автоматически перезапустится."
        )
        self._progress.setVisible(False)
        self._action_btn.setVisible(False)
        try:
            self._later_btn.clicked.disconnect()
        except Exception:
            pass
        self._later_btn.setText("Закрыть")
        self._later_btn.clicked.connect(self.reject)

    def _on_failed(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._meta_label.setText(f"Ошибка: {msg}")
        self._action_btn.setText("Повторить")
        self._action_btn.setEnabled(True)
        try:
            self._action_btn.clicked.disconnect()
        except Exception:
            pass
        self._action_btn.clicked.connect(self._on_action)
        self._later_btn.setText("Закрыть")
        try:
            self._later_btn.clicked.disconnect()
        except Exception:
            pass
        self._later_btn.clicked.connect(self.reject)

    def _open_url(self, url: str) -> None:
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.error(f"updater: failed to open url: {e}")

    def closeEvent(self, event) -> None:
        if self._downloader is not None and self._downloader.isRunning():
            self._downloader.cancel()
            self._downloader.wait(2000)
        super().closeEvent(event)
