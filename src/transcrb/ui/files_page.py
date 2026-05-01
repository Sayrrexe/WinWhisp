from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from transcrb.asr.file_manager import FileJob, FileJobStatus, FileManager
from transcrb.asr.file_pipeline import SUPPORTED_EXTENSIONS, is_supported
from transcrb.paths import transcripts_dir
from transcrb.ui.window_chrome import LinkButton, PrimaryButton


_STATUS_TEXT = {
    FileJobStatus.PENDING: "ожидает извлечения",
    FileJobStatus.EXTRACTING: "извлекаю аудио…",
    FileJobStatus.QUEUED: "в очереди",
    FileJobStatus.RUNNING: "распознаю",
    FileJobStatus.DONE: "готово",
    FileJobStatus.FAILED: "ошибка",
    FileJobStatus.CANCELLED: "отменено",
}

_STATUS_KIND = {
    FileJobStatus.PENDING: "dim",
    FileJobStatus.EXTRACTING: "warn",
    FileJobStatus.QUEUED: "dim",
    FileJobStatus.RUNNING: "ok",
    FileJobStatus.DONE: "ok",
    FileJobStatus.FAILED: "err",
    FileJobStatus.CANCELLED: "dim",
}


FILES_STYLE = """
QFrame#dropZone {
    background: transparent;
    border: none;
}
QFrame#dropZone[hover="true"] {
    background: transparent;
    border: none;
}
QLabel#dropTitle { color: #E8E8EA; font-size: 15px; font-weight: 600; }
QLabel#dropSub { color: #9A9CA3; font-size: 12.5px; }
QLabel#dropHint { color: #5A5C63; font-size: 11.5px; }

QFrame#jobItem {
    background: transparent;
    border: none;
}
QFrame#jobItem[active="true"] {
    border: none;
}
QLabel#jobName { color: #E8E8EA; font-size: 13px; font-weight: 600; }
QLabel#jobSub { color: #9A9CA3; font-size: 11.5px; }
QLabel#jobIcon {
    color: #9A9CA3;
    font-size: 16px;
    font-weight: 600;
    qproperty-alignment: AlignCenter;
}
QLabel#jobIcon[kind="ok"] { color: #5FE89C; }
QLabel#jobIcon[kind="warn"] { color: #FFC766; }
QLabel#jobIcon[kind="err"] { color: #F26565; }

QLabel#jobBadge {
    color: #9A9CA3;
    padding: 2px 9px;
    font-size: 10.5px;
    font-weight: 500;
}
QLabel#jobBadge[kind="ok"] { color: #5FE89C; }
QLabel#jobBadge[kind="warn"] { color: #FFC766; }
QLabel#jobBadge[kind="err"] { color: #F26565; }

QPushButton#jobActBtn {
    color: #C8C9CD;
    padding: 5px 11px;
    font-size: 11.5px;
    font-weight: 500;
}
QPushButton#jobActBtn:disabled { color: #3A3C42; }

QProgressBar#jobProgress {
    background: rgba(255, 255, 255, 0.06);
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar#jobProgress::chunk { background: #31D27A; border-radius: 3px; }
QProgressBar#jobProgress[kind="warn"]::chunk { background: #FFC766; }
QProgressBar#jobProgress[kind="err"]::chunk { background: #F26565; }
QProgressBar#jobProgress[kind="dim"]::chunk { background: rgba(255, 255, 255, 0.22); }

QLabel#filesEmpty { color: #5A5C63; font-size: 12px; }
QLabel#filesQueueTitle {
    color: #5A5C63;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
}
"""


class _RoundLabel(QLabel):
    _BG = {
        "": (255, 255, 255, 13),
        "ok": (49, 210, 122, 31),
        "warn": (255, 199, 102, 31),
        "err": (255, 102, 102, 31),
        "dim": (255, 255, 255, 13),
    }
    _BORDER = {
        "": (255, 255, 255, 26),
        "ok": (49, 210, 122, 92),
        "warn": (255, 199, 102, 92),
        "err": (255, 102, 102, 92),
        "dim": (255, 255, 255, 26),
    }
    _TEXT = {
        "": QColor("#9A9CA3"),
        "ok": QColor("#5FE89C"),
        "warn": QColor("#FFC766"),
        "err": QColor("#F26565"),
        "dim": QColor("#9A9CA3"),
    }

    def __init__(self, text: str = "", radius: float = 9, parent=None) -> None:
        super().__init__(text, parent)
        self._radius = radius
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:
        kind = self.property("kind") or ""
        bg = QColor(*self._BG.get(kind, self._BG[""]))
        border = QColor(*self._BORDER.get(kind, self._BORDER[""]))
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, self._radius, self._radius)
        p.setPen(QPen(border, 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), max(1.0, self._radius - 1), max(1.0, self._radius - 1))
        p.setPen(self._TEXT.get(kind, self._TEXT[""]))
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class _RoundActBtn(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:
        enabled = self.isEnabled()
        hovered = self.underMouse() and enabled
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        if hovered:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 8))
            p.drawRoundedRect(r, 7, 7)
        border = QColor(255, 255, 255, 15 if not enabled else (61 if hovered else 36))
        p.setPen(QPen(border, 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 6, 6)
        text_color = QColor("#3A3C42" if not enabled else ("#E8E8EA" if hovered else "#C8C9CD"))
        p.setPen(text_color)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class _DropZone(QFrame):
    files_dropped = Signal(list)
    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setProperty("hover", False)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAutoFillBackground(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 26, 22, 26)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Перетащите аудио или видео сюда")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)
        sub_row.setAlignment(Qt.AlignCenter)
        sub = QLabel("или")
        sub.setObjectName("dropSub")
        browse = LinkButton("выберите файл…")
        browse.setObjectName("linkBtn")
        browse.clicked.connect(self.browse_requested.emit)
        sub_row.addWidget(sub)
        sub_row.addWidget(browse)
        layout.addLayout(sub_row)

        exts = " · ".join(sorted({e.lstrip(".") for e in SUPPORTED_EXTENSIONS}))
        hint = QLabel(exts)
        hint.setObjectName("dropHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        hover = self.property("hover") == "true"
        bg = QColor(49, 210, 122, 15) if hover else QColor("#0E0E10")
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 16, 16)
        border_color = QColor("#31D27A") if hover else QColor(255, 255, 255, 36)
        pen = QPen(border_color, 2.0)
        pen.setDashPattern([5.0, 4.0])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 15, 15)
        p.end()

    def _set_hover(self, value: bool) -> None:
        self.setProperty("hover", "true" if value else "false")
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _has_supported_files(event):
            event.acceptProposedAction()
            self._set_hover(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        files = _extract_supported_files(event)
        self._set_hover(False)
        if files:
            event.acceptProposedAction()
            self.files_dropped.emit(files)
        else:
            event.ignore()


class _JobItem(QFrame):
    remove_requested = Signal(str)
    open_requested = Signal(str)

    def __init__(self, job: FileJob, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("jobItem")
        self.setProperty("active", "false")
        self.setAutoFillBackground(False)
        self._job_id = job.job_id

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        self._icon = _RoundLabel("…", radius=9)
        self._icon.setObjectName("jobIcon")
        self._icon.setFixedSize(34, 34)
        root.addWidget(self._icon, 0, Qt.AlignTop)

        center = QVBoxLayout()
        center.setSpacing(6)
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        self._name = QLabel(job.path.name)
        self._name.setObjectName("jobName")
        self._name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._name.setMinimumWidth(0)
        self._name.setWordWrap(True)
        self._name.setToolTip(str(job.path))
        name_row.addWidget(self._name, 1)
        self._badge = _RoundLabel("", radius=10)
        self._badge.setObjectName("jobBadge")
        name_row.addWidget(self._badge)
        center.addLayout(name_row)

        self._progress = QProgressBar()
        self._progress.setObjectName("jobProgress")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        center.addWidget(self._progress)

        self._sub = QLabel("")
        self._sub.setObjectName("jobSub")
        self._sub.setWordWrap(True)
        self._sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._sub.setMinimumWidth(0)
        center.addWidget(self._sub)
        root.addLayout(center, 1)

        self._open_btn = _RoundActBtn("Открыть")
        self._open_btn.setObjectName("jobActBtn")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.clicked.connect(lambda: self.open_requested.emit(self._job_id))
        self._open_btn.setVisible(False)
        root.addWidget(self._open_btn)

        self._remove_btn = _RoundActBtn("Удалить")
        self._remove_btn.setObjectName("jobActBtn")
        self._remove_btn.setCursor(Qt.PointingHandCursor)
        self._remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._job_id))
        root.addWidget(self._remove_btn)

        self.refresh(job, hotkey_active=False)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#131316"))
        p.drawRoundedRect(r, 12, 12)
        if self.property("active") == "true":
            border_color = QColor(49, 210, 122, 102)
        else:
            border_color = QColor(255, 255, 255, 26)
        pen = QPen(border_color, 2.0)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 11, 11)
        p.end()

    def job_id(self) -> str:
        return self._job_id

    def refresh(self, job: FileJob, *, hotkey_active: bool) -> None:
        status = job.status
        kind = _STATUS_KIND.get(status, "dim")
        self._icon.setProperty("kind", kind)
        self._icon.setText(_status_glyph(status))

        self._badge.setProperty("kind", kind)
        badge_text = _STATUS_TEXT.get(status, status.value)
        if status == FileJobStatus.RUNNING and hotkey_active:
            badge_text = "пауза · hotkey"
            self._badge.setProperty("kind", "warn")
        self._badge.setText(badge_text)

        total = max(1, len(job.chunks))
        pct = 0
        if status in (FileJobStatus.RUNNING, FileJobStatus.QUEUED):
            pct = int(job.processed * 100 / total)
        elif status == FileJobStatus.DONE:
            pct = 100
        elif status == FileJobStatus.EXTRACTING:
            pct = 0
        elif status == FileJobStatus.FAILED:
            pct = int(job.processed * 100 / total) if job.chunks else 0
        self._progress.setValue(pct)

        prog_kind = "ok" if status == FileJobStatus.DONE else (
            "warn" if (status == FileJobStatus.RUNNING and hotkey_active) else (
                "err" if status == FileJobStatus.FAILED else (
                    "dim" if status in (FileJobStatus.QUEUED, FileJobStatus.PENDING, FileJobStatus.EXTRACTING, FileJobStatus.CANCELLED) else "ok"
                )
            )
        )
        self._progress.setProperty("kind", prog_kind)
        self._progress.style().unpolish(self._progress)
        self._progress.style().polish(self._progress)

        self.setProperty(
            "active",
            "true" if status == FileJobStatus.RUNNING else "false",
        )
        self.update()

        for w in (self._badge, self._icon):
            w.update()

        self._sub.setText(_build_sub_text(job, hotkey_active=hotkey_active))

        self._open_btn.setVisible(
            status == FileJobStatus.DONE and bool(job.output_paths)
        )


class FilesPage(QWidget):
    file_open_requested = Signal(object)
    open_transcripts_requested = Signal()

    def __init__(self, manager: FileManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._items: dict[str, _JobItem] = {}
        self._hotkey_active = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.setSpacing(8)

        outer.addWidget(self._build_title())
        outer.addSpacing(10)

        self._drop = _DropZone()
        self._drop.files_dropped.connect(self._on_files_dropped)
        self._drop.browse_requested.connect(self._on_browse)
        outer.addWidget(self._drop)
        outer.addSpacing(4)

        outer.addWidget(self._build_actions_row())
        outer.addSpacing(14)

        outer.addWidget(self._build_queue_header())
        outer.addSpacing(6)

        self._queue_holder = QWidget()
        self._queue_layout = QVBoxLayout(self._queue_holder)
        self._queue_layout.setContentsMargins(0, 0, 0, 0)
        self._queue_layout.setSpacing(9)

        self._empty_label = QLabel("Очередь пуста.")
        self._empty_label.setObjectName("filesEmpty")
        self._empty_label.setAlignment(Qt.AlignLeft)
        self._queue_layout.addWidget(self._empty_label)
        self._queue_layout.addStretch(1)

        outer.addWidget(self._queue_holder)
        outer.addStretch(1)

        manager.job_added.connect(self._on_job_added)
        manager.job_state_changed.connect(self._on_job_state_changed)
        manager.job_removed.connect(self._on_job_removed)

        for j in manager.jobs():
            self._add_item(j)

    def set_hotkey_active(self, active: bool) -> None:
        if self._hotkey_active == active:
            return
        self._hotkey_active = active
        for item in self._items.values():
            job = self._manager.job(item.job_id())
            if job is not None:
                item.refresh(job, hotkey_active=active)

    def select_job(self, job_id: str) -> None:
        item = self._items.get(job_id)
        if item is None:
            return
        item.setFocus()

    def _build_title(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        title = QLabel("Файлы")
        title.setObjectName("pageTitle")
        sub = QLabel(
            "Распознавание аудио и видео. Hotkey-расшифровка приоритетна и приостановит файл."
        )
        sub.setObjectName("pageSub")
        sub.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(sub)
        return wrap

    def _build_actions_row(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        browse = PrimaryButton("Выбрать файл…")
        browse.setObjectName("primaryBtn")
        browse.clicked.connect(self._on_browse)
        row.addWidget(browse)

        open_dir = LinkButton("Открыть папку транскриптов")
        open_dir.setObjectName("linkBtn")
        open_dir.clicked.connect(self.open_transcripts_requested.emit)
        row.addWidget(open_dir)

        row.addStretch(1)

        clear = LinkButton("Очистить готовые")
        clear.setObjectName("linkBtn")
        clear.clicked.connect(self._manager.clear_completed)
        row.addWidget(clear)
        return wrap

    def _build_queue_header(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("ОЧЕРЕДЬ")
        title.setObjectName("filesQueueTitle")
        row.addWidget(title)
        row.addStretch(1)
        return wrap

    def _on_browse(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать аудио или видео",
            "",
            f"Аудио и видео ({exts});;Все файлы (*.*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if is_supported(path):
            self._manager.add(path)

    def _on_files_dropped(self, files: list) -> None:
        for f in files:
            self._manager.add(f)

    def _on_job_added(self, job_id: str) -> None:
        job = self._manager.job(job_id)
        if job is None:
            return
        self._add_item(job)

    def _on_job_state_changed(self, job_id: str) -> None:
        item = self._items.get(job_id)
        job = self._manager.job(job_id)
        if item is None or job is None:
            return
        item.refresh(job, hotkey_active=self._hotkey_active)

    def _on_job_removed(self, job_id: str) -> None:
        item = self._items.pop(job_id, None)
        if item is None:
            return
        self._queue_layout.removeWidget(item)
        item.deleteLater()
        if not self._items:
            self._empty_label.setVisible(True)

    def _add_item(self, job: FileJob) -> None:
        if job.job_id in self._items:
            return
        item = _JobItem(job)
        item.remove_requested.connect(self._manager.remove)
        item.open_requested.connect(self._on_open_requested)
        self._empty_label.setVisible(False)
        insert_at = max(0, self._queue_layout.count() - 1)
        self._queue_layout.insertWidget(insert_at, item)
        self._items[job.job_id] = item
        item.refresh(job, hotkey_active=self._hotkey_active)

    def _on_open_requested(self, job_id: str) -> None:
        job = self._manager.job(job_id)
        if job is None or not job.output_paths:
            return
        self.file_open_requested.emit(job.output_paths[0])


def _has_supported_files(event: QDragEnterEvent) -> bool:
    md = event.mimeData()
    if not md.hasUrls():
        return False
    for url in md.urls():
        local = url.toLocalFile()
        if local and is_supported(Path(local)):
            return True
    return False


def _extract_supported_files(event: QDropEvent) -> list[Path]:
    md = event.mimeData()
    if not md.hasUrls():
        return []
    files: list[Path] = []
    for url in md.urls():
        local = url.toLocalFile()
        if not local:
            continue
        path = Path(local)
        if is_supported(path):
            files.append(path)
    return files


def _status_glyph(status: FileJobStatus) -> str:
    if status == FileJobStatus.DONE:
        return "✓"
    if status == FileJobStatus.FAILED:
        return "!"
    if status == FileJobStatus.RUNNING:
        return "▶"
    if status == FileJobStatus.EXTRACTING:
        return "⤓"
    if status == FileJobStatus.QUEUED:
        return "·"
    if status == FileJobStatus.CANCELLED:
        return "×"
    return "·"


def _build_sub_text(job: FileJob, *, hotkey_active: bool) -> str:
    if job.status == FileJobStatus.FAILED:
        return job.error or "не удалось обработать"
    if job.status == FileJobStatus.EXTRACTING:
        return "извлекаю звуковую дорожку через ffmpeg…"
    if job.status == FileJobStatus.PENDING:
        return "будет обработан после освобождения извлечения"
    total = len(job.chunks)
    if job.status == FileJobStatus.RUNNING:
        if hotkey_active:
            return f"приостановлено для живой расшифровки · сегмент {job.processed + 1}/{total}"
        if total > 0:
            t = job.segments[-1].t_end if job.segments else 0.0
            return (
                f"{_fmt_time(t)} / {_fmt_time(job.duration_s)} · "
                f"сегмент {job.processed + 1}/{total}"
            )
    if job.status == FileJobStatus.QUEUED:
        return f"{_fmt_time(job.duration_s)} · ожидает · сегментов: {total}"
    if job.status == FileJobStatus.DONE:
        outputs = ", ".join(p.name for p in job.output_paths)
        return f"сохранено: {outputs}" if outputs else "готово"
    if job.status == FileJobStatus.CANCELLED:
        return "отменено пользователем"
    return ""


def _fmt_time(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
