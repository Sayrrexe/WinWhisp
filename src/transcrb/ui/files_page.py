from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QFont,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from transcrb.asr.file_manager import FileJob, FileJobStatus, FileManager
from transcrb.asr.file_pipeline import SUPPORTED_EXTENSIONS, is_supported
from transcrb.paths import transcripts_dir
from transcrb.ui.icons import paint_icon
from transcrb.ui.window_chrome import LinkButton, PrimaryButton


_STATUS_TEXT = {
    FileJobStatus.PENDING: "ожидает извлечения",
    FileJobStatus.EXTRACTING: "извлекаю аудио",
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

_FILTER_ALL = "all"
_FILTER_ACTIVE = "active"
_FILTER_DONE = "done"
_FILTER_ERRORS = "errors"

_ACTIVE_STATUSES = {
    FileJobStatus.PENDING,
    FileJobStatus.EXTRACTING,
    FileJobStatus.QUEUED,
    FileJobStatus.RUNNING,
}


FILES_STYLE = """
QLabel#dropStripTitle { color: #E8E8EA; font-size: 14px; font-weight: 600; }
QLabel#dropStripSub { color: #9A9CA3; font-size: 12px; }

QLabel#filesQueueHead { color: #E8E8EA; font-size: 13.5px; font-weight: 600; }
QLabel#filesQueueCount { color: #9A9CA3; font-size: 12px; }

QLabel#jobLineName { color: #E8E8EA; font-size: 13.5px; font-weight: 500; }
QLabel#jobLineNameDim { color: #9A9CA3; font-size: 13.5px; font-weight: 500; }
QLabel#jobLineMeta { color: #9A9CA3; font-size: 11.5px; }
QLabel#jobLinePct { color: #9A9CA3; font-size: 11px; }

QLabel#filesEmpty { color: #5A5C63; font-size: 12px; }
QLabel#filesFooterHint { color: #9A9CA3; font-size: 11.5px; }

QLabel#errDetail {
    background: rgba(0, 0, 0, 70);
    border-left: 2px solid #F26565;
    border-radius: 0px;
    padding: 10px 12px;
    color: #C5A0A0;
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 11px;
}
"""


class _IconBox(QWidget):
    def __init__(self, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(44, 44)
        self.setAutoFillBackground(False)
        self._icon_name = icon_name

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(49, 210, 122, 41))
        p.drawRoundedRect(r, 10, 10)
        size = 22.0
        icon_rect = QRectF(
            (self.width() - size) / 2.0,
            (self.height() - size) / 2.0,
            size,
            size,
        )
        paint_icon(p, self._icon_name, icon_rect, "#5FE89C")
        p.end()


class _MarkerDot(QWidget):
    _COLORS = {
        "ok": QColor("#31D27A"),
        "warn": QColor("#FFC766"),
        "err": QColor("#F26565"),
        "dim": QColor("#5A5C63"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setAutoFillBackground(False)
        self._kind = "dim"

    def set_kind(self, kind: str) -> None:
        if self._kind != kind:
            self._kind = kind
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        color = self._COLORS.get(self._kind, self._COLORS["dim"])
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        ring = QColor(color.red(), color.green(), color.blue(), 38)
        p.setPen(Qt.NoPen)
        p.setBrush(ring)
        p.drawEllipse(QPointF(cx, cy), 8.0, 8.0)
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, cy), 4.0, 4.0)
        p.end()


class _Progress(QWidget):
    _CHUNK = {
        "ok": QColor("#31D27A"),
        "warn": QColor("#FFC766"),
        "err": QColor("#F26565"),
        "dim": QColor(255, 255, 255, 56),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._kind = "ok"
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAutoFillBackground(False)

    def set_value(self, value: int) -> None:
        v = max(0, min(100, int(value)))
        if v != self._value:
            self._value = v
            self.update()

    def set_kind(self, kind: str) -> None:
        if kind != self._kind:
            self._kind = kind
            self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 18))
        p.drawRoundedRect(r, 2.0, 2.0)
        if self._value > 0:
            chunk = QRectF(r)
            chunk.setWidth(r.width() * self._value / 100.0)
            p.setBrush(self._CHUNK.get(self._kind, self._CHUNK["ok"]))
            p.drawRoundedRect(chunk, 2.0, 2.0)
        p.end()


class _IconActBtn(QPushButton):
    def __init__(self, icon_name: str, *, danger: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(28, 28)
        self.setFocusPolicy(Qt.NoFocus)
        self._danger = danger
        self._icon_name = icon_name

    def set_icon(self, icon_name: str) -> None:
        if self._icon_name != icon_name:
            self._icon_name = icon_name
            self.update()

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        hovered = self.underMouse() and self.isEnabled()
        icon_color = QColor("#9A9CA3")
        if hovered:
            p.setPen(Qt.NoPen)
            if self._danger:
                p.setBrush(QColor(242, 101, 101, 36))
                icon_color = QColor("#F26565")
            else:
                p.setBrush(QColor(255, 255, 255, 16))
                icon_color = QColor("#E8E8EA")
            p.drawRoundedRect(r, 7, 7)
        size = 16.0
        icon_rect = QRectF(
            (self.width() - size) / 2.0,
            (self.height() - size) / 2.0,
            size,
            size,
        )
        paint_icon(p, self._icon_name, icon_rect, icon_color)
        p.end()


class _FilterTab(QPushButton):
    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setAutoFillBackground(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(28)
        self._value = value
        f = QFont(self.font())
        f.setPointSize(10)
        self.setFont(f)

    def value(self) -> str:
        return self._value

    def sizeHint(self) -> QSize:
        m = self.fontMetrics()
        return QSize(m.horizontalAdvance(self.text()) + 22, 28)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        hovered = self.underMouse() and self.isEnabled()
        active = self.isChecked()
        text_color = QColor("#9A9CA3")
        if active:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 16))
            p.drawRoundedRect(r, 7, 7)
            text_color = QColor("#E8E8EA")
        elif hovered:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 10))
            p.drawRoundedRect(r, 7, 7)
            text_color = QColor("#E8E8EA")
        p.setPen(text_color)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class _DropStrip(QFrame):
    files_dropped = Signal(list)
    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropStrip")
        self.setAcceptDrops(True)
        self.setProperty("hover", "false")
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAutoFillBackground(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        self._icon = _IconBox("upload")
        layout.addWidget(self._icon, 0, Qt.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Перетащите аудио или видео сюда")
        title.setObjectName("dropStripTitle")
        text_box.addWidget(title)

        exts = ", ".join(sorted({e.lstrip(".") for e in SUPPORTED_EXTENSIONS}))
        sub = QLabel(f"или нажмите «Выбрать файл…» — поддерживаются: {exts}")
        sub.setObjectName("dropStripSub")
        sub.setWordWrap(False)
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub.setMinimumWidth(0)
        text_box.addWidget(sub)

        text_wrap = QWidget()
        text_wrap.setLayout(text_box)
        text_wrap.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(text_wrap, 1)

        browse = PrimaryButton("Выбрать файл…")
        browse.clicked.connect(self.browse_requested.emit)
        layout.addWidget(browse, 0, Qt.AlignVCenter)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        hover = self.property("hover") == "true"
        bg = QColor(49, 210, 122, 18) if hover else QColor("#0E0E10")
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, 12, 12)
        border_color = QColor("#31D27A") if hover else QColor(255, 255, 255, 56)
        pen = QPen(border_color, 2.0)
        pen.setDashPattern([5.0, 4.0])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), 11, 11)
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


class _JobLine(QFrame):
    remove_requested = Signal(str)
    open_requested = Signal(str)

    def __init__(self, job: FileJob, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("jobLine")
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self._job_id = job.job_id
        self._kind: str = "dim"
        self._is_done = False
        self._is_error = False
        self._is_active = False
        self._expanded = False
        self._hovered = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 12, 8, 14)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(14)
        row.setContentsMargins(0, 0, 0, 0)

        self._marker = _MarkerDot()
        marker_wrap = QWidget()
        mlay = QVBoxLayout(marker_wrap)
        mlay.setContentsMargins(4, 6, 0, 0)
        mlay.setSpacing(0)
        mlay.addWidget(self._marker, 0, Qt.AlignTop | Qt.AlignLeft)
        mlay.addStretch(1)
        marker_wrap.setFixedWidth(28)
        row.addWidget(marker_wrap)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)

        self._name = QLabel(job.path.name)
        self._name.setObjectName("jobLineName")
        self._name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._name.setMinimumWidth(0)
        self._name.setToolTip(str(job.path))
        self._name.setTextFormat(Qt.PlainText)
        body.addWidget(self._name)

        self._meta = QLabel("")
        self._meta.setObjectName("jobLineMeta")
        self._meta.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._meta.setMinimumWidth(0)
        self._meta.setTextFormat(Qt.RichText)
        body.addWidget(self._meta)

        self._progress_row = QWidget()
        prog_lay = QHBoxLayout(self._progress_row)
        prog_lay.setContentsMargins(0, 6, 0, 0)
        prog_lay.setSpacing(10)
        self._progress = _Progress()
        self._progress.setMaximumWidth(420)
        self._pct = QLabel("0%")
        self._pct.setObjectName("jobLinePct")
        self._pct.setMinimumWidth(46)
        prog_lay.addWidget(self._progress, 1)
        prog_lay.addWidget(self._pct, 0, Qt.AlignVCenter)
        self._progress_row.setVisible(False)
        body.addWidget(self._progress_row)

        body_wrap = QWidget()
        body_wrap.setLayout(body)
        body_wrap.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        row.addWidget(body_wrap, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(2)
        self._expand_btn = _IconActBtn("chevron-down")
        self._expand_btn.setVisible(False)
        self._expand_btn.clicked.connect(self._toggle_expand)
        self._open_btn = _IconActBtn("external-link")
        self._open_btn.setToolTip("Открыть транскрипт")
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(lambda: self.open_requested.emit(self._job_id))
        self._remove_btn = _IconActBtn("x", danger=True)
        self._remove_btn.setToolTip("Удалить из очереди")
        self._remove_btn.setVisible(False)
        self._remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._job_id))
        actions.addWidget(self._expand_btn)
        actions.addWidget(self._open_btn)
        actions.addWidget(self._remove_btn)
        actions_wrap = QWidget()
        actions_wrap.setLayout(actions)
        row.addWidget(actions_wrap, 0, Qt.AlignVCenter)

        outer.addLayout(row)

        self._err_panel = QLabel("")
        self._err_panel.setObjectName("errDetail")
        self._err_panel.setWordWrap(True)
        self._err_panel.setTextFormat(Qt.PlainText)
        self._err_panel.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._err_panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._err_panel.setMinimumWidth(0)
        self._err_panel.setVisible(False)
        err_wrap = QHBoxLayout()
        err_wrap.setContentsMargins(28, 10, 0, 0)
        err_wrap.setSpacing(0)
        err_wrap.addWidget(self._err_panel)
        outer.addLayout(err_wrap)

        self.refresh(job, hotkey_active=False)

    def job_id(self) -> str:
        return self._job_id

    def status_kind(self) -> str:
        return self._kind

    def is_active(self) -> bool:
        return self._is_active

    def is_done(self) -> bool:
        return self._is_done

    def is_error(self) -> bool:
        return self._is_error

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._sync_actions()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._sync_actions()
        self.update()
        super().leaveEvent(event)

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._expand_btn.set_icon("chevron-up" if self._expanded else "chevron-down")
        self._err_panel.setVisible(self._expanded and bool(self._err_panel.text()))
        self._sync_actions()
        self.update()

    def _sync_actions(self) -> None:
        show_actions = self._hovered or self._expanded
        self._remove_btn.setVisible(show_actions)
        self._open_btn.setVisible(show_actions and self._is_done)
        self._expand_btn.setVisible(show_actions and self._is_error)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        if self._expanded:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(242, 101, 101, 10))
            p.drawRoundedRect(r, 10, 10)
        elif self._hovered:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 6))
            p.drawRoundedRect(r, 10, 10)
        sep = QColor(242, 101, 101, 36) if self._expanded else QColor(255, 255, 255, 12)
        p.setPen(QPen(sep, 1.0))
        y = self.height() - 0.5
        p.drawLine(QPointF(8.0, y), QPointF(float(self.width() - 8), y))
        p.end()

    def refresh(self, job: FileJob, *, hotkey_active: bool) -> None:
        status = job.status
        kind = _STATUS_KIND.get(status, "dim")
        if status == FileJobStatus.RUNNING and hotkey_active:
            kind = "warn"
        self._kind = kind
        self._is_done = status == FileJobStatus.DONE
        self._is_error = status == FileJobStatus.FAILED
        self._is_active = status in _ACTIVE_STATUSES

        self._marker.set_kind(kind)
        self._name.setObjectName("jobLineNameDim" if self._is_done else "jobLineName")
        self._name.style().unpolish(self._name)
        self._name.style().polish(self._name)
        self._name.setText(job.path.name)
        self._name.setToolTip(str(job.path))

        self._meta.setText(_build_meta_html(job, hotkey_active=hotkey_active))

        total = max(1, len(job.chunks))
        pct = 0
        show_progress = False
        if status == FileJobStatus.RUNNING:
            pct = int(job.processed * 100 / total)
            show_progress = True
        elif status == FileJobStatus.QUEUED:
            pct = int(job.processed * 100 / total) if job.processed else 0
            show_progress = True
        elif status == FileJobStatus.EXTRACTING:
            pct = 0
            show_progress = True
        self._progress.set_value(pct)
        self._progress.set_kind(kind)
        self._pct.setText(f"{pct}%")
        self._progress_row.setVisible(show_progress)

        err_text = job.error or ""
        self._err_panel.setText(err_text)
        if not self._is_error:
            self._expanded = False
            self._err_panel.setVisible(False)
            self._expand_btn.set_icon("chevron-down")
        else:
            self._err_panel.setVisible(self._expanded and bool(err_text))

        self._sync_actions()
        self.update()


class FilesPage(QWidget):
    file_open_requested = Signal(object)
    open_transcripts_requested = Signal()

    def __init__(self, manager: FileManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._items: dict[str, _JobLine] = {}
        self._hotkey_active = False
        self._filter = _FILTER_ALL
        self._tabs: list[_FilterTab] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 24)
        outer.setSpacing(0)

        outer.addWidget(self._build_title())
        outer.addSpacing(20)

        self._drop = _DropStrip()
        self._drop.files_dropped.connect(self._on_files_dropped)
        self._drop.browse_requested.connect(self._on_browse)
        outer.addWidget(self._drop)
        outer.addSpacing(22)

        outer.addWidget(self._build_queue_header())
        outer.addSpacing(2)

        self._queue_holder = QWidget()
        self._queue_layout = QVBoxLayout(self._queue_holder)
        self._queue_layout.setContentsMargins(0, 0, 0, 0)
        self._queue_layout.setSpacing(0)

        self._empty_label = QLabel("Очередь пуста.")
        self._empty_label.setObjectName("filesEmpty")
        self._empty_label.setContentsMargins(8, 18, 0, 0)
        self._queue_layout.addWidget(self._empty_label)
        self._queue_layout.addStretch(1)

        outer.addWidget(self._queue_holder, 1)
        outer.addWidget(self._build_footer())

        manager.job_added.connect(self._on_job_added)
        manager.job_state_changed.connect(self._on_job_state_changed)
        manager.job_removed.connect(self._on_job_removed)

        for j in manager.jobs():
            self._add_item(j)
        self._update_queue_count()

    def set_hotkey_active(self, active: bool) -> None:
        if self._hotkey_active == active:
            return
        self._hotkey_active = active
        for item in self._items.values():
            job = self._manager.job(item.job_id())
            if job is not None:
                item.refresh(job, hotkey_active=active)
        self._update_queue_count()

    def select_job(self, job_id: str) -> None:
        item = self._items.get(job_id)
        if item is None:
            return
        item.setFocus()

    def _build_title(self) -> QWidget:
        title = QLabel("Файлы")
        title.setObjectName("pageTitle")
        return title

    def _build_queue_header(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        head = QLabel("Очередь")
        head.setObjectName("filesQueueHead")
        row.addWidget(head)

        self._queue_count = QLabel("")
        self._queue_count.setObjectName("filesQueueCount")
        row.addWidget(self._queue_count)

        row.addStretch(1)

        for label, value in (
            ("Все", _FILTER_ALL),
            ("Активные", _FILTER_ACTIVE),
            ("Готовые", _FILTER_DONE),
            ("Ошибки", _FILTER_ERRORS),
        ):
            tab = _FilterTab(label, value)
            tab.setChecked(value == self._filter)
            tab.clicked.connect(lambda _checked=False, v=value: self._on_filter(v))
            row.addWidget(tab)
            self._tabs.append(tab)

        return wrap

    def _build_footer(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 14, 0, 0)
        row.setSpacing(10)

        sep_top = QFrame()
        sep_top.setFrameShape(QFrame.NoFrame)
        sep_top.setFixedHeight(1)
        sep_top.setStyleSheet("background: rgba(255, 255, 255, 26);")
        outer_wrap = QWidget()
        outer_lay = QVBoxLayout(outer_wrap)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)
        outer_lay.addWidget(sep_top)

        inner_row = QWidget()
        inner = QHBoxLayout(inner_row)
        inner.setContentsMargins(0, 12, 0, 0)
        inner.setSpacing(10)

        hint = QLabel(f"Сохраняется в {transcripts_dir()}")
        hint.setObjectName("filesFooterHint")
        hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hint.setMinimumWidth(0)
        hint.setToolTip(str(transcripts_dir()))
        inner.addWidget(hint, 1)

        open_dir = LinkButton("Открыть транскрипты")
        open_dir.setMinimumHeight(30)
        open_dir.clicked.connect(self.open_transcripts_requested.emit)
        inner.addWidget(open_dir)

        clear = LinkButton("Очистить готовые")
        clear.setMinimumHeight(30)
        clear.clicked.connect(self._manager.clear_completed)
        inner.addWidget(clear)

        outer_lay.addWidget(inner_row)
        return outer_wrap

    def _on_filter(self, value: str) -> None:
        if value == self._filter:
            for tab in self._tabs:
                tab.setChecked(tab.value() == self._filter)
            return
        self._filter = value
        for tab in self._tabs:
            tab.setChecked(tab.value() == value)
        self._apply_filter()

    def _apply_filter(self) -> None:
        any_visible = False
        for item in self._items.values():
            visible = self._matches_filter(item)
            item.setVisible(visible)
            if visible:
                any_visible = True
        if not self._items:
            self._empty_label.setText("Очередь пуста.")
            self._empty_label.setVisible(True)
        elif not any_visible:
            self._empty_label.setText("Под этот фильтр ничего не подходит.")
            self._empty_label.setVisible(True)
        else:
            self._empty_label.setVisible(False)

    def _matches_filter(self, item: _JobLine) -> bool:
        if self._filter == _FILTER_ALL:
            return True
        if self._filter == _FILTER_ACTIVE:
            return item.is_active()
        if self._filter == _FILTER_DONE:
            return item.is_done()
        if self._filter == _FILTER_ERRORS:
            return item.is_error()
        return True

    def _update_queue_count(self) -> None:
        total = len(self._items)
        active = sum(1 for it in self._items.values() if it.is_active())
        if total == 0:
            self._queue_count.setText("")
            return
        files_word = _plural_files(total)
        if active > 0:
            self._queue_count.setText(f"{total} {files_word} · {active} в работе")
        else:
            self._queue_count.setText(f"{total} {files_word}")

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
        self._update_queue_count()

    def _on_job_state_changed(self, job_id: str) -> None:
        item = self._items.get(job_id)
        job = self._manager.job(job_id)
        if item is None or job is None:
            return
        item.refresh(job, hotkey_active=self._hotkey_active)
        item.setVisible(self._matches_filter(item))
        self._update_queue_count()
        self._refresh_empty_state()

    def _on_job_removed(self, job_id: str) -> None:
        item = self._items.pop(job_id, None)
        if item is None:
            return
        self._queue_layout.removeWidget(item)
        item.deleteLater()
        self._update_queue_count()
        self._refresh_empty_state()

    def _add_item(self, job: FileJob) -> None:
        if job.job_id in self._items:
            return
        item = _JobLine(job)
        item.remove_requested.connect(self._manager.remove)
        item.open_requested.connect(self._on_open_requested)
        insert_at = max(0, self._queue_layout.count() - 1)
        self._queue_layout.insertWidget(insert_at, item)
        self._items[job.job_id] = item
        item.refresh(job, hotkey_active=self._hotkey_active)
        item.setVisible(self._matches_filter(item))
        self._refresh_empty_state()

    def _refresh_empty_state(self) -> None:
        if not self._items:
            self._empty_label.setText("Очередь пуста.")
            self._empty_label.setVisible(True)
            return
        any_visible = any(it.isVisible() for it in self._items.values())
        if not any_visible:
            self._empty_label.setText("Под этот фильтр ничего не подходит.")
            self._empty_label.setVisible(True)
        else:
            self._empty_label.setVisible(False)

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


def _build_meta_html(job: FileJob, *, hotkey_active: bool) -> str:
    status = job.status
    parts: list[str] = []

    if status == FileJobStatus.RUNNING and hotkey_active:
        parts.append(_color("пауза · hotkey", "#FFC766"))
        parts.append("приостановлено для живой расшифровки")
    elif status == FileJobStatus.RUNNING:
        parts.append(_color("распознаю", "#5FE89C"))
        total = len(job.chunks)
        if total > 0:
            t = job.segments[-1].t_end if job.segments else 0.0
            parts.append(f"{_fmt_time(t)} / {_fmt_time(job.duration_s)}")
            parts.append(f"сегмент {job.processed + 1}/{total}")
    elif status == FileJobStatus.EXTRACTING:
        parts.append(_color("извлекаю", "#FFC766"))
        parts.append("вытаскиваю звуковую дорожку через ffmpeg")
    elif status == FileJobStatus.PENDING:
        parts.append(_color("ждёт", "#9A9CA3"))
        parts.append("в очереди на извлечение")
    elif status == FileJobStatus.QUEUED:
        parts.append(_color("в очереди", "#9A9CA3"))
        parts.append(f"длительность {_fmt_time(job.duration_s)}")
        parts.append(f"сегментов: {len(job.chunks)}")
    elif status == FileJobStatus.DONE:
        parts.append(_color("готово", "#5FE89C"))
        parts.append(_fmt_time(job.duration_s))
        outputs = ", ".join(p.name for p in job.output_paths)
        if outputs:
            parts.append(_html_escape(outputs))
    elif status == FileJobStatus.FAILED:
        parts.append(_color("ошибка", "#F26565"))
        first_line = (job.error or "не удалось обработать").splitlines()[0]
        parts.append(_html_escape(_truncate(first_line, 90)))
    elif status == FileJobStatus.CANCELLED:
        parts.append(_color("отменено", "#9A9CA3"))
        parts.append("остановлено пользователем")

    sep = '<span style="color:#5A5C63"> · </span>'
    return sep.join(parts)


def _color(text: str, color_hex: str) -> str:
    return f'<span style="color:{color_hex}">{_html_escape(text)}</span>'


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _plural_files(n: int) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return "файл"
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return "файла"
    return "файлов"


def _fmt_time(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
