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

        duration_s = len(audio) / 16000
        is_short = duration_s < self.cfg.short_audio_s
        kwargs = self._build_transcribe_kwargs(
            initial_prompt="" if is_short else initial_prompt,
            hotwords=hotwords,
            condition_on_previous_text=False if is_short else self.cfg.condition_on_previous_text,
            is_short=is_short,
        )
        segments, info = self._model.transcribe(audio, **kwargs)
        text = "".join(s.text for s in segments)
        logger.debug(
            f"transcribed {duration_s:.2f}s → {len(text)} chars "
            f"(lang={info.language}, prob={info.language_probability:.2f}, short={is_short})"
        )
        return text.strip()

    def transcribe_segments(
        self,
        audio: np.ndarray,
        initial_prompt: str = "",
        hotwords: str = "",
    ) -> list[tuple[float, float, str]]:
        if self._model is None:
            raise RuntimeError("engine not loaded")
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        duration_s = len(audio) / 16000
        is_short = duration_s < self.cfg.short_audio_s
        kwargs = self._build_transcribe_kwargs(
            initial_prompt="" if is_short else initial_prompt,
            hotwords=hotwords,
            condition_on_previous_text=False if is_short else self.cfg.condition_on_previous_text,
            is_short=is_short,
        )
        segments, info = self._model.transcribe(audio, **kwargs)
        out: list[tuple[float, float, str]] = []
        for s in segments:
            start = float(s.start) if s.start is not None else 0.0
            end = float(s.end) if s.end is not None else start
            if end < start:
                end = start
            out.append((start, end, s.text))
        logger.debug(
            f"transcribed {duration_s:.2f}s → {len(out)} segments "
            f"(lang={info.language}, prob={info.language_probability:.2f}, short={is_short})"
        )
        return out

    def _build_transcribe_kwargs(
        self,
        initial_prompt: str,
        hotwords: str,
        condition_on_previous_text: bool,
        is_short: bool = False,
    ) -> dict[str, Any]:
        cfg = self.cfg
        if cfg.sampling_strategy == "greedy":
            beam_size = 1
            best_of = max(1, cfg.best_of)
        else:
            beam_size = max(1, cfg.beam_size)
            best_of = None

        if is_short:
            temperature: float | tuple[float, ...] = cfg.temperature
        elif cfg.temperature_fallback:
            temperature = tuple(cfg.temperature_fallback)
        else:
            temperature = cfg.temperature

        no_speech_threshold = (
            cfg.short_audio_no_speech_threshold if is_short else cfg.no_speech_threshold
        )

        kwargs: dict[str, Any] = dict(
            beam_size=beam_size,
            language=cfg.language,
            task=cfg.task,
            vad_filter=cfg.vad_filter,
            vad_parameters={"min_silence_duration_ms": cfg.vad_min_silence_ms}
            if cfg.vad_filter
            else None,
            temperature=temperature,
            no_speech_threshold=no_speech_threshold,
            log_prob_threshold=cfg.log_prob_threshold,
            compression_ratio_threshold=cfg.compression_ratio_threshold,
            repetition_penalty=cfg.repetition_penalty,
            word_timestamps=cfg.word_timestamps,
            condition_on_previous_text=condition_on_previous_text,
        )
        if best_of is not None:
            kwargs["best_of"] = best_of
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        if hotwords:
            kwargs["hotwords"] = hotwords
        return kwargs
