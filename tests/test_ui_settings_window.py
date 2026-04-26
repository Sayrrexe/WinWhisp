from __future__ import annotations

import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from transcrb.config import Config, AudioCfg
from transcrb.runtime import AppRuntime, HistoryEntry, HistoryStore
from transcrb.text.vocab import Vocab


# ---------------------------------------------------------------------------
# QApplication fixture (session-scoped, no GPU, no display drivers needed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# _format_uptime
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _format_uptime


def test_format_uptime_zero():
    assert _format_uptime(0) == "00:00:00"


def test_format_uptime_below_minute():
    assert _format_uptime(59) == "00:00:59"


def test_format_uptime_exactly_one_minute():
    assert _format_uptime(60) == "00:01:00"


def test_format_uptime_one_hour():
    assert _format_uptime(3600) == "01:00:00"


def test_format_uptime_multi_hour():
    assert _format_uptime(3661) == "01:01:01"


def test_format_uptime_large():
    assert _format_uptime(86399) == "23:59:59"


@pytest.mark.parametrize("secs,expected", [
    (0, "00:00:00"),
    (1, "00:00:01"),
    (3600, "01:00:00"),
    (7322, "02:02:02"),
])
def test_format_uptime_parametrized(secs, expected):
    assert _format_uptime(secs) == expected


# ---------------------------------------------------------------------------
# _state_title
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _state_title


def test_state_title_loading_state():
    assert _state_title("loading", True) == "Подготовка модели"
    assert _state_title("loading", False) == "Подготовка модели"


def test_state_title_idle_model_unloaded():
    assert _state_title("idle", False) == "Готов · модель в спячке"


def test_state_title_idle_model_loaded():
    assert _state_title("idle", True) == "Готов к диктовке"


def test_state_title_recording():
    assert _state_title("recording", True) == "Идёт запись"


def test_state_title_recording_model_unloaded():
    assert _state_title("recording", False) == "Идёт запись"


def test_state_title_processing():
    assert _state_title("processing", True) == "Обрабатываю"


def test_state_title_processing_model_unloaded():
    assert _state_title("processing", False) == "Обрабатываю"


def test_state_title_unknown_state_loaded():
    assert _state_title("unknown", True) == "Готов к диктовке"


# ---------------------------------------------------------------------------
# _audio_device_text
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _audio_device_text


def test_audio_device_text_default_device():
    cfg = Config()
    cfg.audio.device = None
    name, meta = _audio_device_text(cfg)
    assert name == "по умолчанию"


def test_audio_device_text_custom_device():
    cfg = Config()
    cfg.audio.device = "Realtek HD Audio"
    name, meta = _audio_device_text(cfg)
    assert name == "Realtek HD Audio"


def test_audio_device_text_mono_channel():
    cfg = Config()
    cfg.audio.channels = 1
    _, meta = _audio_device_text(cfg)
    assert "моно" in meta


def test_audio_device_text_stereo_channel():
    cfg = Config()
    cfg.audio.channels = 2
    _, meta = _audio_device_text(cfg)
    assert "2 канала" in meta


def test_audio_device_text_samplerate_khz():
    cfg = Config()
    cfg.audio.samplerate = 16000
    _, meta = _audio_device_text(cfg)
    assert "16 кГц" in meta


def test_audio_device_text_samplerate_44100():
    cfg = Config()
    cfg.audio.samplerate = 44100
    _, meta = _audio_device_text(cfg)
    assert "44 кГц" in meta


def test_audio_device_text_three_channels():
    cfg = Config()
    cfg.audio.channels = 3
    _, meta = _audio_device_text(cfg)
    assert "3 канала" in meta


# ---------------------------------------------------------------------------
# _hotkey_pretty
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _hotkey_pretty


def test_hotkey_pretty_right_ctrl():
    assert _hotkey_pretty("right ctrl") == "Right Ctrl"


def test_hotkey_pretty_left_ctrl():
    assert _hotkey_pretty("left ctrl") == "Left Ctrl"


def test_hotkey_pretty_ctrl_only():
    assert _hotkey_pretty("ctrl") == "Ctrl"


def test_hotkey_pretty_shift():
    assert _hotkey_pretty("shift") == "Shift"


def test_hotkey_pretty_alt():
    assert _hotkey_pretty("alt") == "Alt"


def test_hotkey_pretty_combo_with_plus():
    result = _hotkey_pretty("ctrl+shift+z")
    assert result == "Ctrl + Shift + Z"


def test_hotkey_pretty_single_letter_capitalized():
    assert _hotkey_pretty("f5") == "F5"


def test_hotkey_pretty_space_around_plus():
    result = _hotkey_pretty("ctrl + alt + x")
    assert result == "Ctrl + Alt + X"


def test_hotkey_pretty_unknown_key_capitalized():
    assert _hotkey_pretty("space") == "Space"


# ---------------------------------------------------------------------------
# _ago_text
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _ago_text


def _dt(seconds_ago: float) -> tuple[datetime, datetime]:
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = now - timedelta(seconds=seconds_ago)
    return when, now


def test_ago_text_future_returns_dash():
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = now + timedelta(seconds=10)
    assert _ago_text(when, now) == "—"


def test_ago_text_just_now():
    when, now = _dt(5)
    assert _ago_text(when, now) == "только что"


def test_ago_text_exactly_30_seconds():
    when, now = _dt(30)
    assert _ago_text(when, now) == "30 с"


def test_ago_text_seconds_below_minute():
    when, now = _dt(45)
    assert _ago_text(when, now) == "45 с"


def test_ago_text_one_minute():
    when, now = _dt(60)
    assert _ago_text(when, now) == "1 мин"


def test_ago_text_many_minutes():
    when, now = _dt(59 * 60)
    assert _ago_text(when, now) == "59 мин"


def test_ago_text_one_hour():
    when, now = _dt(3600)
    assert _ago_text(when, now) == "1 ч"


def test_ago_text_many_hours():
    when, now = _dt(23 * 3600)
    assert _ago_text(when, now) == "23 ч"


def test_ago_text_yesterday():
    # "вчера" branch: hours >= 24 AND calendar diff == 1 day
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = datetime(2024, 6, 14, 10, 0, 0)
    assert _ago_text(when, now) == "вчера"


def test_ago_text_multi_day():
    when, now = _dt(3 * 24 * 3600 + 100)
    assert _ago_text(when, now) == "3 дн"


# ---------------------------------------------------------------------------
# _day_section
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _day_section, _MONTHS_RU


def test_day_section_today():
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = datetime(2024, 6, 15, 8, 30, 0)
    assert _day_section(when, now) == "Сегодня"


def test_day_section_yesterday():
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = datetime(2024, 6, 14, 23, 59, 0)
    assert _day_section(when, now) == "Вчера"


def test_day_section_older_includes_day_number():
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = datetime(2024, 6, 13, 10, 0, 0)
    result = _day_section(when, now)
    assert "13" in result


def test_day_section_older_includes_month_name():
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = datetime(2024, 6, 1, 0, 0, 0)
    result = _day_section(when, now)
    assert _MONTHS_RU[5] in result


def test_day_section_different_month():
    now = datetime(2024, 6, 15, 12, 0, 0)
    when = datetime(2024, 3, 10, 0, 0, 0)
    result = _day_section(when, now)
    assert _MONTHS_RU[2] in result


@pytest.mark.parametrize("month_idx", range(12))
def test_day_section_all_months_in_months_list(month_idx):
    assert _MONTHS_RU[month_idx]


# ---------------------------------------------------------------------------
# _meta_text
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _meta_text


def test_meta_text_char_count():
    entry = HistoryEntry(datetime.now(), "hello", 2.5)
    result = _meta_text(entry)
    assert "5 симв" in result


def test_meta_text_duration_one_decimal():
    entry = HistoryEntry(datetime.now(), "test", 3.75)
    result = _meta_text(entry)
    assert "3.8 с" in result


def test_meta_text_zero_duration():
    entry = HistoryEntry(datetime.now(), "x", 0.0)
    result = _meta_text(entry)
    assert "0.0 с" in result


def test_meta_text_empty_text():
    entry = HistoryEntry(datetime.now(), "", 1.0)
    result = _meta_text(entry)
    assert "0 симв" in result


def test_meta_text_unicode_counted_by_len():
    entry = HistoryEntry(datetime.now(), "привет", 1.0)
    result = _meta_text(entry)
    assert "6 симв" in result


# ---------------------------------------------------------------------------
# _fmt_bytes
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _fmt_bytes


def test_fmt_bytes_zero():
    assert _fmt_bytes(0) == "—"


def test_fmt_bytes_negative():
    assert _fmt_bytes(-1) == "—"


def test_fmt_bytes_kilobytes():
    assert _fmt_bytes(1024) == "1 KB"


def test_fmt_bytes_megabytes():
    assert _fmt_bytes(1024 ** 2) == "1 MB"


def test_fmt_bytes_gigabytes():
    result = _fmt_bytes(1024 ** 3)
    assert "GB" in result
    assert "1.0" in result


def test_fmt_bytes_partial_megabytes():
    result = _fmt_bytes(512 * 1024)
    assert "512 KB" in result


def test_fmt_bytes_large_gigabytes():
    result = _fmt_bytes(3100 * 1024 * 1024)
    assert "GB" in result


def test_fmt_bytes_small_value():
    result = _fmt_bytes(512)
    assert "KB" in result


# ---------------------------------------------------------------------------
# _HistoryPage._record_noun (static method - Russian plural rules)
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _HistoryPage


def test_record_noun_one():
    assert _HistoryPage._record_noun(1) == "запись"


def test_record_noun_two():
    assert _HistoryPage._record_noun(2) == "записи"


def test_record_noun_three():
    assert _HistoryPage._record_noun(3) == "записи"


def test_record_noun_four():
    assert _HistoryPage._record_noun(4) == "записи"


def test_record_noun_five():
    assert _HistoryPage._record_noun(5) == "записей"


def test_record_noun_eleven_special():
    assert _HistoryPage._record_noun(11) == "записей"


def test_record_noun_twelve_special():
    assert _HistoryPage._record_noun(12) == "записей"


def test_record_noun_thirteen_special():
    assert _HistoryPage._record_noun(13) == "записей"


def test_record_noun_fourteen_special():
    assert _HistoryPage._record_noun(14) == "записей"


def test_record_noun_twenty_one():
    assert _HistoryPage._record_noun(21) == "запись"


def test_record_noun_twenty_two():
    assert _HistoryPage._record_noun(22) == "записи"


def test_record_noun_hundred_eleven():
    assert _HistoryPage._record_noun(111) == "записей"


def test_record_noun_hundred_twelve():
    assert _HistoryPage._record_noun(112) == "записей"


def test_record_noun_zero():
    assert _HistoryPage._record_noun(0) == "записей"


@pytest.mark.parametrize("n,expected", [
    (1, "запись"),
    (2, "записи"),
    (5, "записей"),
    (11, "записей"),
    (21, "запись"),
    (22, "записи"),
    (100, "записей"),
    (101, "запись"),
])
def test_record_noun_parametrized(n, expected):
    assert _HistoryPage._record_noun(n) == expected


# ---------------------------------------------------------------------------
# _HistoryPage._filtered_entries
# ---------------------------------------------------------------------------

def _make_history(entries: list[HistoryEntry]) -> HistoryStore:
    store = HistoryStore(path=None)
    store._items.extend(entries)
    return store


def _entry(dt: datetime, text: str = "x") -> HistoryEntry:
    return HistoryEntry(when=dt, text=text, duration_s=1.0)


@pytest.fixture
def history_page(qapp):
    history = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer") as mock_timer_cls:
        mock_timer_cls.return_value = MagicMock()
        page = _HistoryPage(history)
    return page, history


def test_filtered_entries_all_returns_all(qapp):
    now = datetime(2024, 6, 15, 12, 0, 0)
    e1 = _entry(datetime(2024, 6, 15, 10, 0, 0))
    e2 = _entry(datetime(2024, 6, 10, 8, 0, 0))
    store = _make_history([e1, e2])
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "all"
    result = page._filtered_entries(now)
    assert len(result) == 2


def test_filtered_entries_today_filters(qapp):
    now = datetime(2024, 6, 15, 12, 0, 0)
    e_today = _entry(datetime(2024, 6, 15, 8, 0, 0))
    e_old = _entry(datetime(2024, 6, 14, 8, 0, 0))
    store = _make_history([e_today, e_old])
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "today"
    result = page._filtered_entries(now)
    assert result == [e_today]


def test_filtered_entries_week_filters(qapp):
    now = datetime(2024, 6, 15, 12, 0, 0)
    e_recent = _entry(datetime(2024, 6, 12, 8, 0, 0))
    e_old = _entry(datetime(2024, 6, 1, 8, 0, 0))
    store = _make_history([e_recent, e_old])
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "week"
    result = page._filtered_entries(now)
    assert e_recent in result
    assert e_old not in result


def test_filtered_entries_today_empty_when_no_entries(qapp):
    now = datetime(2024, 6, 15, 12, 0, 0)
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "today"
    assert page._filtered_entries(now) == []


def test_filtered_entries_week_boundary_inclusive(qapp):
    now = datetime(2024, 6, 15, 12, 0, 0)
    cutoff_ts = now.timestamp() - 7 * 24 * 3600
    cutoff_dt = datetime.fromtimestamp(cutoff_ts + 1)
    e_at_cutoff = _entry(cutoff_dt)
    store = _make_history([e_at_cutoff])
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "week"
    result = page._filtered_entries(now)
    assert e_at_cutoff in result


# ---------------------------------------------------------------------------
# _HistoryPage._build_sub_text
# ---------------------------------------------------------------------------

def test_build_sub_text_zero_total(qapp):
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "all"
    result = page._build_sub_text(0, 0)
    assert "history.jsonl" in result


def test_build_sub_text_filter_all(qapp):
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "all"
    result = page._build_sub_text(10, 10)
    assert "10" in result


def test_build_sub_text_filter_today(qapp):
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "today"
    result = page._build_sub_text(20, 5)
    assert "5" in result and "20" in result


def test_build_sub_text_filter_week(qapp):
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "week"
    result = page._build_sub_text(30, 7)
    assert "7" in result and "30" in result


# ---------------------------------------------------------------------------
# _HistoryPage._empty_text
# ---------------------------------------------------------------------------

def test_empty_text_all(qapp):
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "all"
    assert "history.jsonl" in page._empty_text() or "пуста" in page._empty_text()


def test_empty_text_today(qapp):
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "today"
    assert "Сегодня" in page._empty_text()


def test_empty_text_week(qapp):
    store = HistoryStore(path=None)
    with patch("transcrb.ui.settings_window.QTimer"):
        page = _HistoryPage(store)
    page._filter = "week"
    assert "неделю" in page._empty_text()


# ---------------------------------------------------------------------------
# Module-level constants and structural invariants
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import (
    SIDEBAR_GROUPS,
    PAGE_FACTORIES,
    _INJECT_LABEL,
    _INJECT_DETAIL,
    APP_VERSION,
    ACCENT,
)


def test_sidebar_groups_contains_dashboard():
    all_keys = [key for _, items in SIDEBAR_GROUPS for key, _, _ in items]
    assert "dashboard" in all_keys


def test_sidebar_groups_contains_model():
    all_keys = [key for _, items in SIDEBAR_GROUPS for key, _, _ in items]
    assert "model" in all_keys


def test_sidebar_groups_contains_vocab():
    all_keys = [key for _, items in SIDEBAR_GROUPS for key, _, _ in items]
    assert "vocab" in all_keys


def test_inject_label_covers_all_modes():
    for mode in ("inject", "notify", "skip"):
        assert mode in _INJECT_LABEL


def test_inject_detail_covers_all_modes():
    for mode in ("inject", "notify", "skip"):
        assert mode in _INJECT_DETAIL


def test_inject_label_values_are_non_empty():
    for mode, label in _INJECT_LABEL.items():
        assert label


def test_accent_is_valid_hex_color():
    assert ACCENT.startswith("#")
    assert len(ACCENT) == 7


def test_app_version_semver_format():
    parts = APP_VERSION.split(".")
    assert len(parts) == 3
    for p in parts:
        assert p.isdigit()


# ---------------------------------------------------------------------------
# SettingsWindow._set_cfg_value
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import SettingsWindow


@pytest.fixture
def settings_win(qapp, tmp_path):
    runtime = AppRuntime(cfg=Config(), vocab=Vocab())
    with (
        patch("transcrb.ui.settings_window.models_dir", return_value=tmp_path / "models"),
        patch("transcrb.ui.settings_window.save_config"),
        patch("transcrb.ui.settings_window.config_path", return_value=tmp_path / "config.yaml"),
        patch("transcrb.ui.settings_window.vocab_path", return_value=tmp_path / "vocab.yaml"),
        patch("transcrb.ui.settings_window.appdata_dir", return_value=tmp_path),
        patch("transcrb.ui.settings_window.QGuiApplication"),
    ):
        win = SettingsWindow(runtime, standalone=True)
    return win


def test_set_cfg_value_top_level(settings_win):
    win = settings_win
    win._set_cfg_value("autostart", True)
    assert win._runtime.cfg.autostart is True


def test_set_cfg_value_nested_two_levels(settings_win):
    win = settings_win
    win._set_cfg_value("hotkey.combo", "ctrl+x")
    assert win._runtime.cfg.hotkey.combo == "ctrl+x"


def test_set_cfg_value_three_levels(settings_win):
    win = settings_win
    win._set_cfg_value("asr.beam_size", 3)
    assert win._runtime.cfg.asr.beam_size == 3


def test_set_cfg_value_populates_pending_changes(settings_win):
    win = settings_win
    win._pending_changes.clear()
    win._set_cfg_value("log_level", "DEBUG")
    assert "log_level" in win._pending_changes
    assert win._pending_changes["log_level"] == "DEBUG"


def test_set_cfg_value_starts_save_timer(settings_win):
    win = settings_win
    win._save_timer.stop()
    win._set_cfg_value("autostart", False)
    assert win._save_timer.isActive()


def test_set_cfg_value_multiple_keys_accumulated(settings_win):
    win = settings_win
    win._pending_changes.clear()
    win._save_timer.stop()
    win._set_cfg_value("autostart", True)
    win._save_timer.stop()
    win._set_cfg_value("log_level", "ERROR")
    assert "autostart" in win._pending_changes
    assert "log_level" in win._pending_changes


# ---------------------------------------------------------------------------
# SettingsWindow._flush_save
# ---------------------------------------------------------------------------

def test_flush_save_calls_save_config(settings_win):
    win = settings_win
    win._pending_changes = {"autostart": True}
    with patch("transcrb.ui.settings_window.save_config") as mock_save:
        win._flush_save()
    mock_save.assert_called_once_with(win._runtime.cfg)


def test_flush_save_clears_pending(settings_win):
    win = settings_win
    win._pending_changes = {"autostart": True}
    with patch("transcrb.ui.settings_window.save_config"):
        win._flush_save()
    assert win._pending_changes == {}


def test_flush_save_emits_config_changed(settings_win, qapp):
    win = settings_win
    win._pending_changes = {"log_level": "DEBUG"}
    emitted = []
    win.config_changed.connect(lambda d: emitted.append(d))
    with patch("transcrb.ui.settings_window.save_config"):
        win._flush_save()
    assert len(emitted) == 1
    assert emitted[0] == {"log_level": "DEBUG"}


def test_flush_save_swallows_exception(settings_win):
    win = settings_win
    win._pending_changes = {"x": 1}
    with patch("transcrb.ui.settings_window.save_config", side_effect=OSError("disk full")):
        win._flush_save()


def test_flush_save_no_emit_when_no_pending(settings_win, qapp):
    win = settings_win
    win._pending_changes = {}
    emitted = []
    win.config_changed.connect(lambda d: emitted.append(d))
    with patch("transcrb.ui.settings_window.save_config"):
        win._flush_save()
    assert emitted == []


# ---------------------------------------------------------------------------
# SettingsWindow._refresh_model_status
# ---------------------------------------------------------------------------

def test_refresh_model_status_installed_sets_role(settings_win, tmp_path):
    win = settings_win
    models_root = tmp_path / "models"
    first_key = win._model_combo.itemData(0)
    (models_root / first_key).mkdir(parents=True)
    (models_root / first_key / "model.bin").touch()

    from transcrb.ui.settings_window import _MODEL_INSTALLED_ROLE
    with patch("transcrb.ui.settings_window.models_dir", return_value=models_root):
        win._refresh_model_status()
    installed_val = win._model_combo.model().item(0).data(_MODEL_INSTALLED_ROLE)
    assert bool(installed_val) is True


def test_refresh_model_status_not_installed_sets_false(settings_win, tmp_path):
    win = settings_win
    models_root = tmp_path / "models_empty"
    models_root.mkdir(parents=True, exist_ok=True)
    from transcrb.ui.settings_window import _MODEL_INSTALLED_ROLE
    with patch("transcrb.ui.settings_window.models_dir", return_value=models_root):
        win._refresh_model_status()
    installed_val = win._model_combo.model().item(0).data(_MODEL_INSTALLED_ROLE)
    assert bool(installed_val) is False


def test_refresh_model_status_download_btn_hidden_when_installed(settings_win, tmp_path):
    win = settings_win
    models_root = tmp_path / "models2"
    key = win._model_combo.currentData()
    (models_root / key).mkdir(parents=True)
    (models_root / key / "model.bin").touch()
    with patch("transcrb.ui.settings_window.models_dir", return_value=models_root):
        win._refresh_model_status()
    assert not win._model_dl_btn.isVisible()


def test_refresh_model_status_download_btn_visible_when_not_installed(settings_win, tmp_path):
    win = settings_win
    models_root = tmp_path / "models3"
    models_root.mkdir(parents=True)
    with patch("transcrb.ui.settings_window.models_dir", return_value=models_root):
        win._refresh_model_status()
    assert not win._model_dl_btn.isHidden()


def test_refresh_model_status_all_items_updated(settings_win, tmp_path):
    win = settings_win
    models_root = tmp_path / "models_all"
    models_root.mkdir(parents=True)
    with patch("transcrb.ui.settings_window.models_dir", return_value=models_root):
        win._refresh_model_status()
    from transcrb.ui.settings_window import _MODEL_INSTALLED_ROLE
    for i in range(win._model_combo.count()):
        val = win._model_combo.model().item(i).data(_MODEL_INSTALLED_ROLE)
        assert val is False or val is True or val == 0 or val == 1


# ---------------------------------------------------------------------------
# SettingsWindow._on_model_combo_changed
# ---------------------------------------------------------------------------

def test_on_model_combo_changed_updates_cfg(settings_win, tmp_path):
    win = settings_win
    second_key = win._model_combo.itemData(1)
    models_root = tmp_path / "models_chg"
    models_root.mkdir(parents=True)
    with patch("transcrb.ui.settings_window.models_dir", return_value=models_root):
        win._model_combo.setCurrentIndex(1)
    assert win._runtime.cfg.asr.model == second_key


def test_on_model_combo_changed_refreshes_status(settings_win, tmp_path):
    win = settings_win
    models_root = tmp_path / "models_ref"
    models_root.mkdir(parents=True)
    with patch("transcrb.ui.settings_window.models_dir", return_value=models_root) as mock_mdir:
        win._model_combo.setCurrentIndex(0)
    assert mock_mdir.called


# ---------------------------------------------------------------------------
# SettingsWindow sidebar and page navigation
# ---------------------------------------------------------------------------

def test_settings_window_has_all_sidebar_pages(settings_win):
    win = settings_win
    all_keys = [key for _, items in SIDEBAR_GROUPS for key, _, _ in items]
    for key in all_keys:
        assert key in win._pages, f"page key '{key}' missing"


def test_settings_window_dashboard_selected_by_default(settings_win):
    win = settings_win
    current_idx = win._stack.currentIndex()
    assert current_idx == win._pages["dashboard"]


def test_settings_window_page_change_switches_stack(settings_win):
    win = settings_win
    win._on_page_change("model")
    assert win._stack.currentIndex() == win._pages["model"]


def test_settings_window_page_change_unknown_key_no_crash(settings_win):
    win = settings_win
    win._on_page_change("nonexistent_page")


def test_settings_window_close_event_hides_not_closes(settings_win, qapp):
    win = settings_win
    win._standalone = False
    win.show()
    from PySide6.QtGui import QCloseEvent
    event = QCloseEvent()
    win.closeEvent(event)
    assert event.isAccepted() is False


def test_settings_window_close_standalone_accepts(settings_win, qapp):
    win = settings_win
    win._standalone = True
    from PySide6.QtGui import QCloseEvent
    event = QCloseEvent()
    win.closeEvent(event)
    assert event.isAccepted() is True


# ---------------------------------------------------------------------------
# _pill helper
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _pill


def test_pill_ok_objectname():
    lbl = _pill("test", kind="ok")
    assert lbl.objectName() == "pillOk"


def test_pill_warn_objectname():
    lbl = _pill("warn", kind="warn")
    assert lbl.objectName() == "pillWarn"


def test_pill_dim_objectname():
    lbl = _pill("dim", kind="dim")
    assert lbl.objectName() == "pillDim"


def test_pill_unknown_kind_defaults_to_dim():
    lbl = _pill("x", kind="bogus")
    assert lbl.objectName() == "pillDim"


def test_pill_text_is_set():
    lbl = _pill("hello")
    assert lbl.text() == "hello"


# ---------------------------------------------------------------------------
# _label helper
# ---------------------------------------------------------------------------

from transcrb.ui.settings_window import _label


def test_label_text_set():
    lbl = _label("hello")
    assert lbl.text() == "hello"


def test_label_objectname_set():
    lbl = _label("x", "myName")
    assert lbl.objectName() == "myName"


def test_label_wrap_enabled():
    from PySide6.QtWidgets import QLabel
    lbl = _label("wrap text", wrap=True)
    assert lbl.wordWrap() is True


def test_label_no_wrap_by_default():
    lbl = _label("no wrap")
    assert lbl.wordWrap() is False


def test_label_empty_objectname_not_set():
    lbl = _label("x")
    assert lbl.objectName() == ""
