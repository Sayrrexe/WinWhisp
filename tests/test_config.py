import pytest
import yaml
from pydantic import ValidationError

from transcrb.config import (
    AsrCfg,
    AudioCfg,
    Config,
    HotkeyCfg,
    InjectionCfg,
    OverlayCfg,
    TrayCfg,
    VocabCfg,
    load_config,
    save_config,
)


# ---------------------------------------------------------------------------
# original tests preserved
# ---------------------------------------------------------------------------


def test_defaults():
    c = Config()
    assert c.hotkey.combo == "right ctrl"
    assert c.asr.model == "large-v3"
    assert c.asr.compute_type == "float16"
    assert c.injection.method == "unicode"
    assert c.overlay.bars == 10


def test_round_trip(tmp_path):
    p = tmp_path / "cfg.yaml"
    c = Config()
    c.hotkey.combo = "ctrl+alt+x"
    c.audio.max_duration_s = 77
    save_config(c, p)
    loaded = load_config(p)
    assert loaded.hotkey.combo == "ctrl+alt+x"
    assert loaded.audio.max_duration_s == 77


def test_missing_file_creates_default(tmp_path):
    p = tmp_path / "nope.yaml"
    c = load_config(p)
    assert p.exists()
    assert c.hotkey.combo == "right ctrl"


# ---------------------------------------------------------------------------
# HotkeyCfg
# ---------------------------------------------------------------------------


def test_hotkey_defaults():
    h = HotkeyCfg()
    assert h.combo == "right ctrl"
    assert h.min_hold_ms == 250
    assert h.debounce_ms == 150
    assert h.release_tail_ms == 500


@pytest.mark.parametrize("field,bad", [
    ("min_hold_ms", "not-an-int"),
    ("debounce_ms", "x"),
    ("release_tail_ms", []),
])
def test_hotkey_invalid_types(field, bad):
    with pytest.raises(ValidationError):
        HotkeyCfg(**{field: bad})


def test_hotkey_combo_arbitrary_string():
    h = HotkeyCfg(combo="ctrl+shift+z")
    assert h.combo == "ctrl+shift+z"


def test_hotkey_zero_timings():
    h = HotkeyCfg(min_hold_ms=0, debounce_ms=0, release_tail_ms=0)
    assert h.min_hold_ms == 0
    assert h.debounce_ms == 0
    assert h.release_tail_ms == 0


def test_hotkey_large_timing():
    h = HotkeyCfg(min_hold_ms=999999)
    assert h.min_hold_ms == 999999


# ---------------------------------------------------------------------------
# AudioCfg
# ---------------------------------------------------------------------------


def test_audio_defaults():
    a = AudioCfg()
    assert a.device is None
    assert a.samplerate == 16000
    assert a.channels == 1
    assert a.block_ms == 30
    assert a.max_duration_s == 120
    assert a.rms_smoothing == pytest.approx(0.35)
    assert a.chunk_min_s == pytest.approx(1.5)
    assert a.chunk_max_s == pytest.approx(12.0)
    assert a.chunk_silence_s == pytest.approx(0.8)
    assert a.chunk_silence_rms == pytest.approx(0.015)


@pytest.mark.parametrize("field,bad", [
    ("samplerate", "high"),
    ("channels", "stereo"),
    ("block_ms", None),
    ("max_duration_s", "long"),
])
def test_audio_invalid_types(field, bad):
    with pytest.raises(ValidationError):
        AudioCfg(**{field: bad})


def test_audio_device_none_and_string():
    assert AudioCfg(device=None).device is None
    assert AudioCfg(device="default").device == "default"


def test_audio_samplerate_boundary():
    assert AudioCfg(samplerate=8000).samplerate == 8000
    assert AudioCfg(samplerate=44100).samplerate == 44100
    assert AudioCfg(samplerate=48000).samplerate == 48000


def test_audio_chunk_times_float():
    a = AudioCfg(chunk_min_s=0.5, chunk_max_s=30.0, chunk_silence_s=0.3)
    assert a.chunk_min_s == pytest.approx(0.5)
    assert a.chunk_max_s == pytest.approx(30.0)
    assert a.chunk_silence_s == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# AsrCfg
# ---------------------------------------------------------------------------


def test_asr_defaults():
    a = AsrCfg()
    assert a.model == "large-v3"
    assert a.compute_type == "float16"
    assert a.device == "cuda"
    assert a.device_index == 0
    assert a.language == "ru"
    assert a.beam_size == 5
    assert a.vad_filter is True
    assert a.vad_min_silence_ms == 500
    assert a.temperature == pytest.approx(0.0)
    assert a.condition_on_previous_text is True
    assert a.idle_unload_s == 60


def test_asr_language_none():
    a = AsrCfg(language=None)
    assert a.language is None


@pytest.mark.parametrize("field,bad", [
    ("beam_size", "five"),
    ("vad_filter", []),
    ("device_index", "gpu0"),
    ("idle_unload_s", "never"),
])
def test_asr_invalid_types(field, bad):
    with pytest.raises(ValidationError):
        AsrCfg(**{field: bad})


def test_asr_temperature_float():
    a = AsrCfg(temperature=0.5)
    assert a.temperature == pytest.approx(0.5)


def test_asr_beam_size_one():
    a = AsrCfg(beam_size=1)
    assert a.beam_size == 1


# ---------------------------------------------------------------------------
# VocabCfg
# ---------------------------------------------------------------------------


def test_vocab_defaults():
    v = VocabCfg()
    assert v.path is None
    assert v.use_initial_prompt is True
    assert v.use_hotwords is True


def test_vocab_path_string():
    v = VocabCfg(path="/some/path/vocab.yaml")
    assert v.path == "/some/path/vocab.yaml"


@pytest.mark.parametrize("field,bad", [
    ("use_initial_prompt", []),
    ("use_hotwords", {}),
])
def test_vocab_invalid_types(field, bad):
    with pytest.raises(ValidationError):
        VocabCfg(**{field: bad})


def test_vocab_flags_false():
    v = VocabCfg(use_initial_prompt=False, use_hotwords=False)
    assert v.use_initial_prompt is False
    assert v.use_hotwords is False


# ---------------------------------------------------------------------------
# InjectionCfg
# ---------------------------------------------------------------------------


def test_injection_defaults():
    i = InjectionCfg()
    assert i.method == "unicode"
    assert i.paste_combo == "ctrl+v"
    assert i.pre_paste_delay_ms == 20
    assert i.post_paste_delay_ms == 250
    assert i.copy_final_to_clipboard is True
    assert i.on_focus_change == "notify"
    assert i.trailing_space is True


@pytest.mark.parametrize("val", ["notify", "inject", "skip"])
def test_injection_focus_change_literals(val):
    i = InjectionCfg(on_focus_change=val)
    assert i.on_focus_change == val


def test_injection_focus_change_invalid():
    with pytest.raises(ValidationError):
        InjectionCfg(on_focus_change="popup")


@pytest.mark.parametrize("val", ["unicode", "paste"])
def test_injection_method_literals(val):
    i = InjectionCfg(method=val)
    assert i.method == val


def test_injection_method_invalid():
    with pytest.raises(ValidationError):
        InjectionCfg(method="type")


@pytest.mark.parametrize("field,bad", [
    ("pre_paste_delay_ms", "fast"),
    ("post_paste_delay_ms", "slow"),
    ("copy_final_to_clipboard", []),
    ("trailing_space", 1.5),
])
def test_injection_invalid_types(field, bad):
    with pytest.raises(ValidationError):
        InjectionCfg(**{field: bad})


def test_injection_no_trailing_space():
    i = InjectionCfg(trailing_space=False)
    assert i.trailing_space is False


# ---------------------------------------------------------------------------
# OverlayCfg
# ---------------------------------------------------------------------------


def test_overlay_defaults():
    o = OverlayCfg()
    assert o.enabled is True
    assert o.width == 252
    assert o.height == 81
    assert o.bottom_margin_px == 24
    assert o.fps == 30
    assert o.bars == 10
    assert o.accent_color == "#31D27A"
    assert o.background_rgba == [12, 12, 14, 230]
    assert o.result_hold_ms == 5000


def test_overlay_background_rgba_mutable_default():
    o1 = OverlayCfg()
    o2 = OverlayCfg()
    o1.background_rgba[0] = 99
    assert o2.background_rgba[0] == 12


@pytest.mark.parametrize("field,bad", [
    ("width", "wide"),
    ("height", "tall"),
    ("fps", "thirty"),
    ("bars", 3.5),
    ("result_hold_ms", "long"),
])
def test_overlay_invalid_types(field, bad):
    with pytest.raises(ValidationError):
        OverlayCfg(**{field: bad})


def test_overlay_disabled():
    o = OverlayCfg(enabled=False)
    assert o.enabled is False


def test_overlay_custom_rgba():
    o = OverlayCfg(background_rgba=[0, 0, 0, 255])
    assert o.background_rgba == [0, 0, 0, 255]


# ---------------------------------------------------------------------------
# TrayCfg
# ---------------------------------------------------------------------------


def test_tray_defaults():
    t = TrayCfg()
    assert t.show_notifications is True
    assert t.notify_on_error is True


@pytest.mark.parametrize("field,bad", [
    ("show_notifications", []),
    ("notify_on_error", {}),
])
def test_tray_invalid_types(field, bad):
    with pytest.raises(ValidationError):
        TrayCfg(**{field: bad})


def test_tray_both_false():
    t = TrayCfg(show_notifications=False, notify_on_error=False)
    assert t.show_notifications is False
    assert t.notify_on_error is False


# ---------------------------------------------------------------------------
# Config top-level
# ---------------------------------------------------------------------------


def test_config_top_level_defaults():
    c = Config()
    assert c.schema_version == 1
    assert c.autostart is False
    assert c.log_level == "INFO"
    assert c.onboarded is False


def test_config_top_level_invalid_schema_version():
    with pytest.raises(ValidationError):
        Config(schema_version="one")


def test_config_sub_models_are_correct_types():
    c = Config()
    assert isinstance(c.hotkey, HotkeyCfg)
    assert isinstance(c.audio, AudioCfg)
    assert isinstance(c.asr, AsrCfg)
    assert isinstance(c.vocab, VocabCfg)
    assert isinstance(c.injection, InjectionCfg)
    assert isinstance(c.overlay, OverlayCfg)
    assert isinstance(c.tray, TrayCfg)


def test_config_partial_override():
    c = Config(log_level="DEBUG", autostart=True)
    assert c.log_level == "DEBUG"
    assert c.autostart is True
    assert c.hotkey.combo == "right ctrl"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_partial_yaml_fills_defaults(tmp_path):
    p = tmp_path / "partial.yaml"
    p.write_text("hotkey:\n  combo: ctrl+space\n", encoding="utf-8")
    c = load_config(p)
    assert c.hotkey.combo == "ctrl+space"
    assert c.asr.model == "large-v3"
    assert c.audio.samplerate == 16000


def test_load_empty_yaml_all_defaults(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("{}\n", encoding="utf-8")
    c = load_config(p)
    assert c.hotkey.combo == "right ctrl"
    assert c.schema_version == 1


def test_load_unknown_fields_ignored(tmp_path):
    p = tmp_path / "extra.yaml"
    p.write_text("unknown_field: 42\nhotkey:\n  combo: alt+x\n", encoding="utf-8")
    c = load_config(p)
    assert c.hotkey.combo == "alt+x"


def test_load_malformed_yaml_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(":\nthis: [is: broken\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_config(p)


def test_load_missing_file_writes_file(tmp_path):
    p = tmp_path / "sub" / "cfg.yaml"
    c = load_config(p)
    assert p.exists()
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert raw["hotkey"]["combo"] == "right ctrl"


def test_load_onboarded_injected_when_absent(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("hotkey:\n  combo: right ctrl\n", encoding="utf-8")
    c = load_config(p)
    assert c.onboarded is True


def test_load_onboarded_false_preserved_when_present(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("onboarded: false\n", encoding="utf-8")
    c = load_config(p)
    assert c.onboarded is False


def test_load_onboarded_true_preserved_when_present(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("onboarded: true\n", encoding="utf-8")
    c = load_config(p)
    assert c.onboarded is True


def test_load_missing_file_onboarded_false(tmp_path):
    p = tmp_path / "new.yaml"
    c = load_config(p)
    assert c.onboarded is False


# ---------------------------------------------------------------------------
# save_config
# ---------------------------------------------------------------------------


def test_save_creates_parent_dirs(tmp_path):
    p = tmp_path / "a" / "b" / "c" / "cfg.yaml"
    save_config(Config(), p)
    assert p.exists()


def test_save_produces_valid_yaml(tmp_path):
    p = tmp_path / "cfg.yaml"
    save_config(Config(), p)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    assert "hotkey" in raw
    assert "asr" in raw
    assert "audio" in raw
    assert "overlay" in raw


def test_save_unicode_not_escaped(tmp_path):
    p = tmp_path / "cfg.yaml"
    c = Config()
    c.hotkey.combo = "правый ctrl"
    save_config(c, p)
    text = p.read_text(encoding="utf-8")
    assert "правый ctrl" in text
    assert "\\u" not in text


def test_save_all_sections_present(tmp_path):
    p = tmp_path / "cfg.yaml"
    save_config(Config(), p)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    for section in ("hotkey", "audio", "asr", "vocab", "injection", "overlay", "tray"):
        assert section in raw, f"missing section: {section}"


def test_save_round_trip_full(tmp_path):
    p = tmp_path / "cfg.yaml"
    c = Config()
    c.asr.model = "medium"
    c.asr.language = None
    c.overlay.bars = 7
    c.overlay.background_rgba = [0, 0, 0, 128]
    c.tray.show_notifications = False
    c.autostart = True
    c.log_level = "DEBUG"
    save_config(c, p)
    loaded = load_config(p)
    assert loaded.asr.model == "medium"
    assert loaded.asr.language is None
    assert loaded.overlay.bars == 7
    assert loaded.overlay.background_rgba == [0, 0, 0, 128]
    assert loaded.tray.show_notifications is False
    assert loaded.autostart is True
    assert loaded.log_level == "DEBUG"


def test_save_idempotent(tmp_path):
    p = tmp_path / "cfg.yaml"
    c = Config()
    save_config(c, p)
    first = p.read_text(encoding="utf-8")
    save_config(c, p)
    second = p.read_text(encoding="utf-8")
    assert first == second
