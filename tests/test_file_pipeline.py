from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from transcrb.asr.file_pipeline import (
    FfmpegMissing,
    SUPPORTED_EXTENSIONS,
    extract_audio,
    is_supported,
    split_audio,
)


class TestIsSupported:
    def test_mp3_supported(self):
        assert is_supported(Path("song.mp3")) is True

    def test_mp4_supported(self):
        assert is_supported(Path("clip.MP4")) is True

    def test_unknown_unsupported(self):
        assert is_supported(Path("doc.pdf")) is False

    def test_no_extension(self):
        assert is_supported(Path("README")) is False

    def test_supported_set_has_audio_and_video(self):
        assert ".mp3" in SUPPORTED_EXTENSIONS
        assert ".mp4" in SUPPORTED_EXTENSIONS
        assert ".wav" in SUPPORTED_EXTENSIONS


class TestExtractAudio:
    def test_raises_when_ffmpeg_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr("transcrb.asr.file_pipeline.ffmpeg_path", lambda: None)
        with pytest.raises(FfmpegMissing):
            extract_audio(tmp_path / "fake.mp3")


class TestSplitAudio:
    def test_empty_audio_returns_empty_list(self):
        audio = np.zeros(0, dtype=np.float32)
        chunks = split_audio(
            audio, 16000,
            chunk_max_s=10.0, chunk_min_s=2.0,
            silence_s=0.3, silence_rms=0.01,
        )
        assert chunks == []

    def test_short_audio_one_chunk(self):
        audio = np.random.randn(16000 * 5).astype(np.float32) * 0.1
        chunks = split_audio(
            audio, 16000,
            chunk_max_s=10.0, chunk_min_s=2.0,
            silence_s=0.3, silence_rms=0.01,
        )
        assert chunks == [(0, len(audio))]

    def test_long_audio_split_at_silence(self):
        sr = 16000
        loud = np.random.randn(sr * 5).astype(np.float32) * 0.5
        silent = np.zeros(sr * 2, dtype=np.float32)
        audio = np.concatenate([loud, silent, loud, silent, loud])
        chunks = split_audio(
            audio, sr,
            chunk_max_s=10.0, chunk_min_s=2.0,
            silence_s=0.5, silence_rms=0.005,
        )
        assert len(chunks) >= 2
        last_end = chunks[-1][1]
        assert last_end == len(audio)

    def test_chunks_cover_entire_audio_without_overlap(self):
        sr = 16000
        audio = np.random.randn(sr * 30).astype(np.float32) * 0.3
        chunks = split_audio(
            audio, sr,
            chunk_max_s=10.0, chunk_min_s=2.0,
            silence_s=0.3, silence_rms=0.01,
        )
        assert chunks[0][0] == 0
        assert chunks[-1][1] == len(audio)
        for i in range(1, len(chunks)):
            assert chunks[i - 1][1] == chunks[i][0]

    def test_no_silence_falls_back_to_max_chunk(self):
        sr = 16000
        audio = np.random.randn(sr * 25).astype(np.float32) * 0.5
        chunks = split_audio(
            audio, sr,
            chunk_max_s=10.0, chunk_min_s=2.0,
            silence_s=0.3, silence_rms=0.001,
        )
        for s, e in chunks[:-1]:
            assert e - s <= sr * 10

    def test_silence_threshold_zero_rms_finds_cut(self):
        sr = 16000
        loud = np.ones(sr * 5, dtype=np.float32) * 0.3
        silent = np.zeros(sr * 1, dtype=np.float32)
        audio = np.concatenate([loud, silent, loud, silent, loud])
        chunks = split_audio(
            audio, sr,
            chunk_max_s=8.0, chunk_min_s=2.0,
            silence_s=0.5, silence_rms=0.01,
        )
        assert len(chunks) >= 2
