from __future__ import annotations

import itertools
import queue

import numpy as np
from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal

from transcrb.asr.engine import WhisperEngine
from transcrb.config import AsrCfg
from transcrb.text.postprocess import is_hallucination, postprocess
from transcrb.text.vocab import (
    PROMPT_PREFIX,
    Vocab,
    build_hotwords_string,
    build_initial_prompt,
    is_prompt_echo,
)


PRIORITY_STOP = -1
PRIORITY_CONTROL = 0
PRIORITY_HOTKEY = 0
PRIORITY_FILE = 1


class _Request:
    __slots__ = ("audio",)

    def __init__(self, audio: np.ndarray) -> None:
        self.audio = audio


class _FileRequest:
    __slots__ = ("audio", "job_id", "chunk_idx", "t_start", "t_end")

    def __init__(
        self,
        audio: np.ndarray,
        job_id: str,
        chunk_idx: int,
        t_start: float,
        t_end: float,
    ) -> None:
        self.audio = audio
        self.job_id = job_id
        self.chunk_idx = chunk_idx
        self.t_start = t_start
        self.t_end = t_end


class _Prepare:
    pass


class _Reload:
    pass


class _Stop:
    pass


_PREPARE = _Prepare()
_RELOAD = _Reload()
_STOP = _Stop()


class AsrWorker(QObject):
    ready = Signal(str)
    error = Signal(str)
    loaded = Signal()
    unloaded = Signal()
    file_chunk_ready = Signal(str, int, str, float, float)
    file_chunk_failed = Signal(str, int, str)

    def __init__(
        self,
        cfg: AsrCfg,
        vocab: Vocab,
        trailing_space: bool = True,
        prompt_prefix: str = PROMPT_PREFIX,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._vocab = vocab
        self._trailing_space = trailing_space
        self._prompt_prefix = prompt_prefix
        self._engine: WhisperEngine | None = None
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = itertools.count()
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        self._initial_prompt = ""
        self._hotwords = ""

    def _enqueue(self, priority: int, item: object) -> None:
        self._queue.put((priority, next(self._seq), item))

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._enqueue(PRIORITY_STOP, None)
        self._thread.quit()
        self._thread.wait(3000)

    def submit(self, audio: np.ndarray) -> None:
        self._enqueue(PRIORITY_HOTKEY, _Request(audio))

    def submit_file_chunk(
        self,
        audio: np.ndarray,
        job_id: str,
        chunk_idx: int,
        t_start: float,
        t_end: float,
    ) -> None:
        self._enqueue(
            PRIORITY_FILE,
            _FileRequest(audio, job_id, chunk_idx, t_start, t_end),
        )

    def prepare(self) -> None:
        self._enqueue(PRIORITY_CONTROL, _PREPARE)

    def request_reload(self) -> None:
        self._enqueue(PRIORITY_CONTROL, _RELOAD)

    def update_vocab(self, vocab: Vocab) -> None:
        self._vocab = vocab
        self._rebuild_prompts()

    def _is_prompt_echo(self, raw: str) -> bool:
        if not self._initial_prompt:
            return False
        return is_prompt_echo(raw, prompt_prefix=self._prompt_prefix)

    def _rebuild_prompts(self) -> None:
        hotwords = self._vocab.hotwords
        self._initial_prompt = (
            build_initial_prompt(hotwords, prefix=self._prompt_prefix) if hotwords else ""
        )
        self._hotwords = build_hotwords_string(hotwords) if hotwords else ""

    def _ensure_loaded(self) -> bool:
        if self._engine is not None and self._engine.is_loaded():
            return True
        self._engine = WhisperEngine(self._cfg)
        try:
            self._engine.load()
            self._engine.warmup()
        except Exception as e:
            logger.exception("engine load failed")
            self.error.emit(f"Не удалось загрузить модель: {e}")
            self._engine = None
            return False
        self._rebuild_prompts()
        self.loaded.emit()
        return True

    def _unload_if_loaded(self) -> None:
        if self._engine and self._engine.is_loaded():
            self._engine.unload()
            self.unloaded.emit()

    def _handle_reload(self) -> None:
        self._unload_if_loaded()
        self._engine = None

    def _handle_request(self, audio: np.ndarray) -> None:
        try:
            raw = self._engine.transcribe(
                audio,
                initial_prompt=self._initial_prompt,
                hotwords=self._hotwords,
            )
            if is_hallucination(raw, self._vocab.hallucinations_all):
                logger.info(f"dropped hallucination: {raw!r}")
                self.ready.emit("")
                return
            if self._is_prompt_echo(raw):
                logger.info(f"dropped prompt echo: {raw!r}")
                self.ready.emit("")
                return
            text = postprocess(raw, self._vocab, trailing_space=self._trailing_space)
            self._log_preview(audio, text)
            self.ready.emit(text)
        except Exception as e:
            logger.exception("transcription failed")
            self.error.emit(f"Ошибка транскрибации: {e}")

    def _handle_file_request(self, req: _FileRequest) -> None:
        try:
            raw = self._engine.transcribe(
                req.audio,
                initial_prompt=self._initial_prompt,
                hotwords=self._hotwords,
            )
            if is_hallucination(raw, self._vocab.hallucinations_all):
                self.file_chunk_ready.emit(req.job_id, req.chunk_idx, "", req.t_start, req.t_end)
                return
            if self._is_prompt_echo(raw):
                self.file_chunk_ready.emit(req.job_id, req.chunk_idx, "", req.t_start, req.t_end)
                return
            text = postprocess(raw, self._vocab, trailing_space=False)
            self._log_preview(req.audio, text, prefix=f"[file {req.job_id[:6]} #{req.chunk_idx}]")
            self.file_chunk_ready.emit(req.job_id, req.chunk_idx, text, req.t_start, req.t_end)
        except Exception as e:
            logger.exception("file chunk transcription failed")
            self.file_chunk_failed.emit(req.job_id, req.chunk_idx, str(e))

    @staticmethod
    def _log_preview(audio: np.ndarray, text: str, *, prefix: str = "") -> None:
        preview = (text or "").strip().replace("\n", " ")
        if len(preview) > 80:
            preview = preview[:79] + "…"
        head = f"{prefix} " if prefix else ""
        logger.info(f"{head}transcribed ({len(audio) / 16000:.2f}s): {preview!r}")

    def _run(self) -> None:
        if not self._ensure_loaded():
            return

        while True:
            idle = max(5, int(self._cfg.idle_unload_s))
            try:
                _, _, req = self._queue.get(timeout=idle)
            except queue.Empty:
                self._unload_if_loaded()
                continue

            if req is None or isinstance(req, _Stop):
                return

            if isinstance(req, _Reload):
                self._handle_reload()
                continue

            if isinstance(req, _Prepare):
                self._ensure_loaded()
                continue

            if not self._ensure_loaded():
                continue

            if isinstance(req, _FileRequest):
                self._handle_file_request(req)
            elif isinstance(req, _Request):
                self._handle_request(req.audio)
