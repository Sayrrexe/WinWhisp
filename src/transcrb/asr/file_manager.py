from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal

from transcrb.asr.file_pipeline import (
    FfmpegFailed,
    FfmpegMissing,
    extract_audio,
    is_supported,
    split_audio,
)
from transcrb.asr.worker import AsrWorker
from transcrb.config import FilesCfg
from transcrb.paths import transcripts_dir


class FileJobStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FileSegment:
    chunk_idx: int
    text: str
    t_start: float
    t_end: float


@dataclass
class FileJob:
    job_id: str
    path: Path
    status: FileJobStatus = FileJobStatus.PENDING
    audio: Optional[np.ndarray] = None
    chunks: list[tuple[int, int]] = field(default_factory=list)
    processed: int = 0
    segments: list[FileSegment] = field(default_factory=list)
    output_paths: list[Path] = field(default_factory=list)
    error: str = ""
    duration_s: float = 0.0
    waiting_for_hotkey: bool = False


_INVALID_CHARS = re.compile(r"[\\/:*?\"<>|]")
_SAMPLERATE = 16000


class FileManager(QObject):
    job_added = Signal(str)
    job_state_changed = Signal(str)
    job_removed = Signal(str)

    _extract_done = Signal(str, object, object)
    _extract_failed = Signal(str, str)

    def __init__(
        self,
        asr: AsrWorker,
        files_cfg: FilesCfg,
        samplerate: int = _SAMPLERATE,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._asr = asr
        self._cfg = files_cfg
        self._samplerate = samplerate
        self._jobs: dict[str, FileJob] = {}
        self._order: list[str] = []
        self._active_job_id: Optional[str] = None
        self._in_flight_chunk: Optional[int] = None
        self._extracting: bool = False

        self._asr.file_chunk_ready.connect(self._on_chunk_ready, Qt.QueuedConnection)
        self._asr.file_chunk_failed.connect(self._on_chunk_failed, Qt.QueuedConnection)
        self._extract_done.connect(self._on_extracted, Qt.QueuedConnection)
        self._extract_failed.connect(self._on_extract_failed, Qt.QueuedConnection)

    def update_cfg(self, cfg: FilesCfg) -> None:
        self._cfg = cfg

    def jobs(self) -> list[FileJob]:
        return [self._jobs[j] for j in self._order]

    def job(self, job_id: str) -> Optional[FileJob]:
        return self._jobs.get(job_id)

    def active_count(self) -> int:
        return sum(
            1
            for j in self._jobs.values()
            if j.status
            in (
                FileJobStatus.PENDING,
                FileJobStatus.EXTRACTING,
                FileJobStatus.QUEUED,
                FileJobStatus.RUNNING,
            )
        )

    def add(self, path: Path) -> Optional[str]:
        if not path.exists():
            logger.warning(f"file not found: {path}")
            return None
        if not is_supported(path):
            logger.warning(f"unsupported extension: {path.suffix}")
            return None
        job = FileJob(job_id=uuid.uuid4().hex, path=path)
        self._jobs[job.job_id] = job
        self._order.append(job.job_id)
        self.job_added.emit(job.job_id)
        self._maybe_extract_next()
        return job.job_id

    def remove(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        if job.status == FileJobStatus.RUNNING and self._active_job_id == job_id:
            job.status = FileJobStatus.CANCELLED
            self._active_job_id = None
            self._in_flight_chunk = None
            self.job_state_changed.emit(job_id)
            self._send_next()
        else:
            job.status = FileJobStatus.CANCELLED
        self._order.remove(job_id)
        self._jobs.pop(job_id, None)
        self.job_removed.emit(job_id)

    def clear_completed(self) -> None:
        to_remove = [
            jid
            for jid, j in self._jobs.items()
            if j.status in (FileJobStatus.DONE, FileJobStatus.FAILED, FileJobStatus.CANCELLED)
        ]
        for jid in to_remove:
            self._order.remove(jid)
            self._jobs.pop(jid, None)
            self.job_removed.emit(jid)

    def _maybe_extract_next(self) -> None:
        if self._extracting:
            return
        next_id = next(
            (jid for jid in self._order if self._jobs[jid].status == FileJobStatus.PENDING),
            None,
        )
        if next_id is None:
            return
        job = self._jobs[next_id]
        job.status = FileJobStatus.EXTRACTING
        self.job_state_changed.emit(next_id)
        self._extracting = True
        threading.Thread(
            target=self._extract_in_thread,
            args=(next_id, job.path),
            daemon=True,
        ).start()

    def _extract_in_thread(self, job_id: str, path: Path) -> None:
        try:
            audio = extract_audio(path, self._samplerate)
            chunks = split_audio(
                audio,
                self._samplerate,
                chunk_max_s=self._cfg.chunk_max_s,
                chunk_min_s=self._cfg.chunk_min_s,
                silence_s=self._cfg.chunk_silence_s,
                silence_rms=self._cfg.chunk_silence_rms,
            )
            self._extract_done.emit(job_id, audio, chunks)
        except FfmpegMissing as e:
            self._extract_failed.emit(job_id, str(e))
        except FfmpegFailed as e:
            msg = f"{e}\n{e.stderr}".strip() if e.stderr else str(e)
            self._extract_failed.emit(job_id, msg)
        except Exception as e:
            logger.exception("file extraction failed")
            self._extract_failed.emit(job_id, str(e))

    def _on_extracted(self, job_id: str, audio: np.ndarray, chunks: list) -> None:
        self._extracting = False
        job = self._jobs.get(job_id)
        if job is None or job.status == FileJobStatus.CANCELLED:
            self._maybe_extract_next()
            return
        job.audio = audio
        job.chunks = list(chunks)
        job.duration_s = float(audio.shape[0]) / self._samplerate
        job.status = FileJobStatus.QUEUED
        self.job_state_changed.emit(job_id)
        self._send_next()
        self._maybe_extract_next()

    def _on_extract_failed(self, job_id: str, msg: str) -> None:
        self._extracting = False
        job = self._jobs.get(job_id)
        if job is not None:
            job.status = FileJobStatus.FAILED
            job.error = msg
            self.job_state_changed.emit(job_id)
        self._maybe_extract_next()

    def _send_next(self) -> None:
        if self._in_flight_chunk is not None:
            return
        if self._active_job_id is None:
            for jid in self._order:
                j = self._jobs[jid]
                if j.status == FileJobStatus.QUEUED:
                    self._active_job_id = jid
                    j.status = FileJobStatus.RUNNING
                    self.job_state_changed.emit(jid)
                    break
        if self._active_job_id is None:
            return
        job = self._jobs[self._active_job_id]
        if job.processed >= len(job.chunks):
            self._finalize_job(job)
            self._active_job_id = None
            self._send_next()
            return
        chunk_idx = job.processed
        s, e = job.chunks[chunk_idx]
        if job.audio is None:
            return
        audio_chunk = np.ascontiguousarray(job.audio[s:e])
        t_start = s / self._samplerate
        t_end = e / self._samplerate
        self._in_flight_chunk = chunk_idx
        self._asr.submit_file_chunk(audio_chunk, job.job_id, chunk_idx, t_start, t_end)

    def _on_chunk_ready(
        self,
        job_id: str,
        chunk_idx: int,
        text: str,
        t_start: float,
        t_end: float,
    ) -> None:
        job = self._jobs.get(job_id)
        if job is None or job.status != FileJobStatus.RUNNING:
            self._in_flight_chunk = None
            self._send_next()
            return
        job.segments.append(FileSegment(chunk_idx, text, t_start, t_end))
        job.processed += 1
        self.job_state_changed.emit(job_id)
        self._in_flight_chunk = None
        self._send_next()

    def _on_chunk_failed(self, job_id: str, chunk_idx: int, error: str) -> None:
        job = self._jobs.get(job_id)
        self._in_flight_chunk = None
        if job is None:
            self._send_next()
            return
        job.error = error
        job.status = FileJobStatus.FAILED
        self.job_state_changed.emit(job_id)
        if self._active_job_id == job_id:
            self._active_job_id = None
        self._send_next()

    def _finalize_job(self, job: FileJob) -> None:
        try:
            job.output_paths = self._save_outputs(job)
            job.status = FileJobStatus.DONE
            logger.info(
                f"file done: {job.path.name} → "
                f"{', '.join(p.name for p in job.output_paths)}"
            )
        except Exception as e:
            logger.exception("failed to save transcripts")
            job.status = FileJobStatus.FAILED
            job.error = f"Не удалось сохранить транскрипт: {e}"
        finally:
            job.audio = None
            self.job_state_changed.emit(job.job_id)

    def _save_outputs(self, job: FileJob) -> list[Path]:
        target_dir = self._target_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = _INVALID_CHARS.sub("_", job.path.stem) or "transcript"
        base = target_dir / f"{stem}_{timestamp}"
        paths: list[Path] = []
        ordered = sorted(job.segments, key=lambda s: s.chunk_idx)
        if self._cfg.save_txt:
            txt = base.with_suffix(".txt")
            txt.write_text(_build_txt(ordered), encoding="utf-8")
            paths.append(txt)
        if self._cfg.save_srt:
            srt = base.with_suffix(".srt")
            srt.write_text(_build_srt(ordered), encoding="utf-8")
            paths.append(srt)
        return paths

    def _target_dir(self) -> Path:
        if self._cfg.output_dir:
            p = Path(self._cfg.output_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return transcripts_dir()


def _build_txt(segments: list[FileSegment]) -> str:
    parts = [s.text.strip() for s in segments if s.text and s.text.strip()]
    return ("\n".join(parts) + "\n") if parts else ""


def _build_srt(segments: list[FileSegment]) -> str:
    lines: list[str] = []
    idx = 1
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{_srt_time(seg.t_start)} --> {_srt_time(seg.t_end)}")
        lines.append(text)
        lines.append("")
        idx += 1
    return "\n".join(lines)


def _srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms_total = int(round(seconds * 1000))
    h, rem = divmod(ms_total, 3600 * 1000)
    m, rem = divmod(rem, 60 * 1000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
