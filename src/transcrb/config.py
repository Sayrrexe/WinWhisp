from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from transcrb.paths import config_path


class HotkeyCfg(BaseModel):
    combo: str = "ctrl+shift+space"
    min_hold_ms: int = 250
    debounce_ms: int = 150
    release_tail_ms: int = 500


class AudioCfg(BaseModel):
    device: str | None = None
    samplerate: int = 16000
    channels: int = 1
    block_ms: int = 30
    max_duration_s: int = 120
    rms_smoothing: float = 0.35
    chunk_min_s: float = 1.5
    chunk_max_s: float = 8.0
    chunk_silence_s: float = 0.25
    chunk_silence_rms: float = 0.015


class AsrCfg(BaseModel):
    model: str = "large-v3"
    compute_type: str = "float16"
    device: str = "cuda"
    device_index: int = 0
    language: str | None = "ru"
    beam_size: int = 5
    vad_filter: bool = True
    vad_min_silence_ms: int = 500
    temperature: float = 0.0
    condition_on_previous_text: bool = False
    idle_unload_s: int = 60


class VocabCfg(BaseModel):
    path: str | None = None
    use_initial_prompt: bool = True
    use_hotwords: bool = True


class InjectionCfg(BaseModel):
    method: Literal["paste"] = "paste"
    paste_combo: str = "ctrl+v"
    pre_paste_delay_ms: int = 20
    post_paste_delay_ms: int = 250
    restore_clipboard: bool = True
    on_focus_change: Literal["notify", "inject", "skip"] = "notify"
    trailing_space: bool = True


class OverlayCfg(BaseModel):
    enabled: bool = True
    width: int = 252
    height: int = 81
    bottom_margin_px: int = 24
    fps: int = 30
    bars: int = 10
    accent_color: str = "#31D27A"
    background_rgba: list[int] = Field(default_factory=lambda: [12, 12, 14, 230])
    result_hold_ms: int = 8000


class TrayCfg(BaseModel):
    show_notifications: bool = True
    notify_on_error: bool = True


class Config(BaseModel):
    schema_version: int = 1
    hotkey: HotkeyCfg = HotkeyCfg()
    audio: AudioCfg = AudioCfg()
    asr: AsrCfg = AsrCfg()
    vocab: VocabCfg = VocabCfg()
    injection: InjectionCfg = InjectionCfg()
    overlay: OverlayCfg = OverlayCfg()
    tray: TrayCfg = TrayCfg()
    autostart: bool = False
    log_level: str = "INFO"


def load_config(path: Path | None = None) -> Config:
    p = path or config_path()
    if not p.exists():
        cfg = Config()
        save_config(cfg, p)
        return cfg
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Config.model_validate(raw)


def save_config(cfg: Config, path: Path | None = None) -> None:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            cfg.model_dump(), f, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
