from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from transcrb.paths import ffmpeg_path


SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".mp4", ".mkv", ".mov", ".webm", ".avi", ".wma", ".aiff",
}


class FfmpegMissing(RuntimeError):
    pass


class FfmpegFailed(RuntimeError):
    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def extract_audio(
    path: Path,
    samplerate: int = 16000,
    *,
    loudnorm: bool = False,
) -> np.ndarray:
    binary = ffmpeg_path()
    if binary is None:
        raise FfmpegMissing(
            "ffmpeg не найден. Установите ffmpeg в PATH или положите в resources/bin/ffmpeg.exe."
        )
    cmd = [
        str(binary),
        "-nostdin",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(path),
        "-vn",
    ]
    if loudnorm:
        cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
    cmd.extend([
        "-ac", "1",
        "-ar", str(samplerate),
        "-f", "f32le",
        "pipe:1",
    ])
    creationflags = 0
    try:
        creationflags = subprocess.CREATE_NO_WINDOW
    except AttributeError:
        pass
    proc = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
        creationflags=creationflags,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise FfmpegFailed(
            f"ffmpeg завершился с кодом {proc.returncode}",
            stderr=stderr,
        )
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size == 0:
        raise FfmpegFailed("ffmpeg вернул пустой поток (нет звуковой дорожки?)")
    return np.ascontiguousarray(audio)


def split_audio(
    audio: np.ndarray,
    samplerate: int,
    *,
    chunk_max_s: float,
    chunk_min_s: float,
    silence_s: float,
    silence_rms: float,
) -> list[tuple[int, int]]:
    n = int(audio.shape[0])
    if n == 0:
        return []
    chunk_max = max(1, int(samplerate * chunk_max_s))
    chunk_min = max(1, int(samplerate * chunk_min_s))
    silence_w = max(1, int(samplerate * silence_s))
    if chunk_min >= chunk_max:
        chunk_min = chunk_max // 2
    if silence_w >= chunk_max:
        silence_w = max(1, chunk_max // 4)

    threshold = (float(silence_rms) ** 2) * silence_w

    audio_f64 = audio.astype(np.float64, copy=False)
    sq = audio_f64 * audio_f64
    prefix = np.empty(n + 1, dtype=np.float64)
    prefix[0] = 0.0
    np.cumsum(sq, out=prefix[1:])

    chunks: list[tuple[int, int]] = []
    start = 0
    while start < n:
        remaining = n - start
        if remaining <= chunk_max:
            chunks.append((start, n))
            break
        cut = _find_cut(prefix, start, n, chunk_min, chunk_max, silence_w, threshold)
        if cut <= start:
            cut = min(start + chunk_max, n)
        chunks.append((start, cut))
        start = cut

    return chunks


def _find_cut(
    prefix: np.ndarray,
    start: int,
    n: int,
    chunk_min: int,
    chunk_max: int,
    silence_w: int,
    threshold: float,
) -> int:
    scan_lo = start + max(chunk_min, silence_w)
    scan_hi = min(start + chunk_max, n)
    if scan_lo > scan_hi:
        return scan_hi
    i_lo = scan_lo - silence_w
    i_hi = scan_hi - silence_w
    if i_hi < i_lo:
        return scan_hi
    sums = prefix[i_lo + silence_w : i_hi + silence_w + 1] - prefix[i_lo : i_hi + 1]
    mask = sums < threshold
    if not np.any(mask):
        return scan_hi
    idx = int(np.argmax(mask))
    return i_lo + idx + silence_w
