"""Открывает SettingsWindow на разделе «Файлы» с замоканым ASR/FileManager.

Полезно для быстрой итерации UI drop-зоны и очереди заданий, не дёргая faster-whisper.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from transcrb.asr.file_manager import FileJob, FileJobStatus, FileManager, FileSegment
from transcrb.config import FilesCfg
from transcrb.ui.settings_window import SettingsWindow


def main() -> int:
    app = QApplication(sys.argv)
    asr = MagicMock()
    asr.file_chunk_ready = MagicMock()
    asr.file_chunk_failed = MagicMock()
    asr.file_chunk_ready.connect = MagicMock()
    asr.file_chunk_failed.connect = MagicMock()
    asr.submit_file_chunk = MagicMock()

    manager = FileManager(asr, FilesCfg(), samplerate=16000)

    fake_running = FileJob(
        job_id="job-running",
        path=Path("interview_2026-04-22.mp4"),
        status=FileJobStatus.RUNNING,
        chunks=[(0, 16000 * 30) for _ in range(18)],
        processed=7,
        duration_s=30 * 18,
        segments=[FileSegment(i, f"сегмент {i}", i * 30, (i + 1) * 30) for i in range(7)],
    )
    fake_queued = FileJob(
        job_id="job-queued",
        path=Path("podcast_ep_45.mp3"),
        status=FileJobStatus.QUEUED,
        chunks=[(0, 16000 * 30) for _ in range(124)],
        duration_s=124 * 30,
    )
    fake_done = FileJob(
        job_id="job-done",
        path=Path("lecture_notes.m4a"),
        status=FileJobStatus.DONE,
        chunks=[(0, 16000 * 30) for _ in range(8)],
        processed=8,
        duration_s=8 * 30,
        output_paths=[Path("lecture_notes.txt"), Path("lecture_notes.srt")],
    )
    for j in (fake_running, fake_queued, fake_done):
        manager._jobs[j.job_id] = j
        manager._order.append(j.job_id)

    win = SettingsWindow(standalone=True, files_manager=manager)
    win.open_to_page("files")
    win.show()

    page = win.files_page()
    if page is not None:
        for j in (fake_running, fake_queued, fake_done):
            page._on_job_added(j.job_id)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
