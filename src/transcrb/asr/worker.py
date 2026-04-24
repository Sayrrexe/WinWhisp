from __future__ import annotations

import queue

import numpy as np
from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal

from transcrb.asr.engine import WhisperEngine
from transcrb.config import AsrCfg
from transcrb.text.postprocess import is_hallucination, postprocess
from transcrb.text.vocab import Vocab, build_hotwords_string, build_initial_prompt


class _Request:
    __slots__ = ("audio",)

    def __init__(self, audio: np.ndarray) -> None:
        self.audio = audio


class _Prepare:
    pass


_PREPARE = _Prepare()


class AsrWorker(QObject):
    ready = Signal(str)
    error = Signal(str)
    loaded = Signal()
    unloaded = Signal()

    def __init__(
        self,
        cfg: AsrCfg,
        vocab: Vocab,
        trailing_space: bool = True,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._vocab = vocab
        self._trailing_space = trailing_space
        self._engine: WhisperEngine | None = None
        self._queue: queue.Queue[_Request | None] = queue.Queue()
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        self._initial_prompt = ""
        self._hotwords = ""

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
        self._thread.quit()
        self._thread.wait(3000)

    def submit(self, audio: np.ndarray) -> None:
        self._queue.put(_Request(audio))

    def prepare(self) -> None:
        self._queue.put(_PREPARE)

    def update_vocab(self, vocab: Vocab) -> None:
        self._vocab = vocab
        self._rebuild_prompts()

    def _is_prompt_echo(self, raw: str) -> bool:
        if not self._initial_prompt:
            return False
        t = (raw or "").strip().lower()
        if not t or len(t) < 10:
            return False
        prompt_lc = self._initial_prompt.lower()
        if t.rstrip(".!?") in prompt_lc:
            return True
        prefix_len = min(30, max(15, len(prompt_lc) // 3))
        prefix = prompt_lc[:prefix_len]
        if prefix and t.startswith(prefix):
            return True
        return False

    def _rebuild_prompts(self) -> None:
        self._initial_prompt = (
            build_initial_prompt(self._vocab.hotwords) if self._vocab.hotwords else ""
        )
        self._hotwords = (
            build_hotwords_string(self._vocab.hotwords) if self._vocab.hotwords else ""
        )

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

    def _run(self) -> None:
        if not self._ensure_loaded():
            return

        idle = max(5, int(self._cfg.idle_unload_s))

        while True:
            try:
                req = self._queue.get(timeout=idle)
            except queue.Empty:
                if self._engine and self._engine.is_loaded():
                    self._engine.unload()
                    self.unloaded.emit()
                continue

            if req is None:
                return

            if isinstance(req, _Prepare):
                self._ensure_loaded()
                continue

            if not self._ensure_loaded():
                continue

            try:
                raw = self._engine.transcribe(
                    req.audio,
                    initial_prompt=self._initial_prompt,
                    hotwords=self._hotwords,
                )
                if is_hallucination(raw, self._vocab.hallucinations):
                    logger.info(f"dropped hallucination: {raw!r}")
                    self.ready.emit("")
                    continue
                if self._is_prompt_echo(raw):
                    logger.info(f"dropped prompt echo: {raw!r}")
                    self.ready.emit("")
                    continue
                text = postprocess(raw, self._vocab, trailing_space=self._trailing_space)
                preview = (text or "").strip().replace("\n", " ")
                if len(preview) > 80:
                    preview = preview[:79] + "…"
                logger.info(f"transcribed ({len(req.audio) / 16000:.2f}s): {preview!r}")
                self.ready.emit(text)
            except Exception as e:
                logger.exception("transcription failed")
                self.error.emit(f"Ошибка транскрибации: {e}")
