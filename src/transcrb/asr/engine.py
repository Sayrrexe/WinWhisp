from __future__ import annotations

import gc
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from transcrb.config import AsrCfg
from transcrb.paths import models_dir


def ensure_model(name: str, progress_cb=None) -> Path:
    target = models_dir() / name
    if (target / "model.bin").exists():
        return target
    from huggingface_hub import snapshot_download

    repo = f"Systran/faster-whisper-{name}"
    logger.info(f"downloading {repo} → {target}")
    snapshot_download(
        repo_id=repo,
        local_dir=str(target),
        local_dir_use_symlinks=False,
    )
    if progress_cb:
        progress_cb(1.0)
    return target


class WhisperEngine:
    def __init__(self, cfg: AsrCfg) -> None:
        self.cfg = cfg
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None

    def unload(self) -> None:
        if self._model is None:
            return
        logger.info("unloading Whisper model from VRAM")
        self._model = None
        gc.collect()

    def load(self) -> None:
        from faster_whisper import WhisperModel

        self.unload()
        model_path = ensure_model(self.cfg.model)
        path_str = str(model_path)
        logger.info(
            f"loading Whisper {self.cfg.model} device={self.cfg.device} "
            f"compute_type={self.cfg.compute_type}"
        )
        try:
            self._model = WhisperModel(
                path_str,
                device=self.cfg.device,
                device_index=self.cfg.device_index,
                compute_type=self.cfg.compute_type,
            )
        except Exception as e:
            logger.error(f"CUDA load failed ({e}), falling back to CPU int8")
            self._model = WhisperModel(
                path_str,
                device="cpu",
                compute_type="int8",
            )

    def warmup(self) -> None:
        if self._model is None:
            return
        logger.debug("warming up Whisper")
        silence = np.zeros(16000, dtype=np.float32)
        try:
            segs, _ = self._model.transcribe(silence, beam_size=1, language=self.cfg.language)
            for _ in segs:
                pass
        except Exception as e:
            logger.warning(f"warmup failed: {e}")

    def transcribe(
        self,
        audio: np.ndarray,
        initial_prompt: str = "",
        hotwords: str = "",
    ) -> str:
        if self._model is None:
            raise RuntimeError("engine not loaded")
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        kwargs = self._build_transcribe_kwargs(initial_prompt, hotwords)
        segments, info = self._model.transcribe(audio, **kwargs)
        text = "".join(s.text for s in segments)
        logger.debug(
            f"transcribed {len(audio) / 16000:.2f}s → {len(text)} chars "
            f"(lang={info.language}, prob={info.language_probability:.2f})"
        )
        return text.strip()

    def _build_transcribe_kwargs(self, initial_prompt: str, hotwords: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = dict(
            beam_size=self.cfg.beam_size,
            language=self.cfg.language,
            vad_filter=self.cfg.vad_filter,
            vad_parameters={"min_silence_duration_ms": self.cfg.vad_min_silence_ms}
            if self.cfg.vad_filter
            else None,
            temperature=self.cfg.temperature,
            condition_on_previous_text=self.cfg.condition_on_previous_text,
        )
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        if hotwords:
            kwargs["hotwords"] = hotwords
        return kwargs
