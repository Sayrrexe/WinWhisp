from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from transcrb.asr.file_manager import (
    FileJob,
    FileJobStatus,
    FileManager,
    FileSegment,
    _build_srt,
    _build_txt,
    _srt_time,
)
from transcrb.config import FilesCfg


@pytest.fixture()
def fake_asr():
    asr = MagicMock()
    asr.file_chunk_ready = MagicMock()
    asr.file_chunk_failed = MagicMock()
    asr.submit_file_chunk = MagicMock()
    return asr


@pytest.fixture()
def cfg(tmp_path):
    return FilesCfg(output_dir=str(tmp_path))


@pytest.fixture()
def manager(fake_asr, cfg):
    return FileManager(fake_asr, cfg, samplerate=16000)


def _make_supported(tmp_path: Path, name: str = "clip.mp3") -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00" * 32)
    return p


class TestAddRemove:
    def test_add_missing_file_returns_none(self, manager):
        assert manager.add(Path("/nope/missing.mp3")) is None

    def test_add_unsupported_extension_returns_none(self, manager, tmp_path):
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"abc")
        assert manager.add(p) is None

    def test_add_supported_emits_job_added(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        seen = []
        manager.job_added.connect(seen.append)
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        assert job_id is not None
        assert seen == [job_id]
        assert manager.job(job_id).path == p

    def test_jobs_are_returned_in_insertion_order(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        a = _make_supported(tmp_path, "a.mp3")
        b = _make_supported(tmp_path, "b.wav")
        id_a = manager.add(a)
        id_b = manager.add(b)
        ordered = [j.job_id for j in manager.jobs()]
        assert ordered == [id_a, id_b]

    def test_remove_drops_job_and_emits(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        seen = []
        manager.job_removed.connect(seen.append)
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        manager.remove(job_id)
        assert manager.job(job_id) is None
        assert seen == [job_id]

    def test_clear_completed_removes_done_jobs(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        manager.job(job_id).status = FileJobStatus.DONE
        manager.clear_completed()
        assert manager.job(job_id) is None


class TestExtractionFlow:
    def test_extract_done_queues_chunks_and_submits_first(
        self, manager, fake_asr, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        audio = np.zeros(16000 * 60, dtype=np.float32)
        chunks = [(0, 16000 * 30), (16000 * 30, 16000 * 60)]
        manager._on_extracted(job_id, audio, chunks)
        job = manager.job(job_id)
        assert job.status == FileJobStatus.RUNNING
        assert job.chunks == chunks
        fake_asr.submit_file_chunk.assert_called_once()
        called_kwargs = fake_asr.submit_file_chunk.call_args
        assert called_kwargs.args[1] == job_id
        assert called_kwargs.args[2] == 0

    def test_extract_failed_marks_job_failed(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        manager._on_extract_failed(job_id, "ffmpeg fell over")
        job = manager.job(job_id)
        assert job.status == FileJobStatus.FAILED
        assert "ffmpeg" in job.error


class TestChunkProcessing:
    def test_chunk_ready_advances_progress_and_sends_next(
        self, manager, fake_asr, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        audio = np.zeros(16000 * 60, dtype=np.float32)
        chunks = [(0, 16000 * 30), (16000 * 30, 16000 * 60)]
        manager._on_extracted(job_id, audio, chunks)
        fake_asr.submit_file_chunk.reset_mock()

        manager._on_chunk_ready(job_id, 0, "first half", 0.0, 30.0)
        job = manager.job(job_id)
        assert job.processed == 1
        assert len(job.segments) == 1
        fake_asr.submit_file_chunk.assert_called_once()
        assert fake_asr.submit_file_chunk.call_args.args[2] == 1

    def test_chunk_ready_after_all_chunks_finalizes_job(
        self, manager, fake_asr, tmp_path, monkeypatch, cfg
    ):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        audio = np.zeros(16000 * 4, dtype=np.float32)
        chunks = [(0, 16000 * 2), (16000 * 2, 16000 * 4)]
        manager._on_extracted(job_id, audio, chunks)
        manager._on_chunk_ready(job_id, 0, "hello", 0.0, 2.0)
        manager._on_chunk_ready(job_id, 1, "world", 2.0, 4.0)
        job = manager.job(job_id)
        assert job.status == FileJobStatus.DONE
        assert job.output_paths
        for outp in job.output_paths:
            assert outp.exists()

    def test_chunk_failed_marks_job_failed(self, manager, fake_asr, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        audio = np.zeros(16000 * 4, dtype=np.float32)
        chunks = [(0, 16000 * 4)]
        manager._on_extracted(job_id, audio, chunks)
        manager._on_chunk_failed(job_id, 0, "transcribe failed")
        job = manager.job(job_id)
        assert job.status == FileJobStatus.FAILED
        assert "transcribe failed" in job.error


class TestActiveCount:
    def test_active_count_zero_initially(self, manager):
        assert manager.active_count() == 0

    def test_active_count_includes_pending(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        manager.add(p)
        assert manager.active_count() >= 1

    def test_done_jobs_excluded_from_active_count(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "transcrb.asr.file_manager.threading.Thread",
            lambda **kw: MagicMock(start=MagicMock()),
        )
        p = _make_supported(tmp_path)
        job_id = manager.add(p)
        manager.job(job_id).status = FileJobStatus.DONE
        assert manager.active_count() == 0


class TestOutputBuilders:
    def test_srt_time_formats_zero(self):
        assert _srt_time(0) == "00:00:00,000"

    def test_srt_time_handles_hours(self):
        assert _srt_time(3661.5) == "01:01:01,500"

    def test_srt_time_clamps_negative(self):
        assert _srt_time(-1.0) == "00:00:00,000"

    def test_build_txt_joins_segments(self):
        segs = [
            FileSegment(0, "Привет", 0.0, 1.0),
            FileSegment(1, "мир", 1.0, 2.0),
        ]
        text = _build_txt(segs)
        assert "Привет" in text
        assert "мир" in text

    def test_build_txt_skips_empty(self):
        segs = [
            FileSegment(0, "", 0.0, 1.0),
            FileSegment(1, "  ", 1.0, 2.0),
            FileSegment(2, "real", 2.0, 3.0),
        ]
        text = _build_txt(segs)
        assert text.strip() == "real"

    def test_build_srt_has_indexed_blocks(self):
        segs = [
            FileSegment(0, "первый", 0.0, 2.5),
            FileSegment(1, "второй", 2.5, 5.0),
        ]
        srt = _build_srt(segs)
        assert "1\n" in srt
        assert "2\n" in srt
        assert "00:00:00,000 --> 00:00:02,500" in srt
        assert "первый" in srt and "второй" in srt
