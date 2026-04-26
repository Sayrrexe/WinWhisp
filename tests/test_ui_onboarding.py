from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from transcrb.asr.catalog import DEFAULT_MODEL, MODELS
from transcrb.config import Config
from transcrb.ui.onboarding import (
    DEFAULT_HOTKEY,
    HOTKEY_PRESETS,
    STEPS,
    _HotkeyCaptureDialog,
    _StepperBar,
    _detect_gpu,
    _fmt_size,
    _hotkey_pretty,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp_instance(qapp):
    return qapp


@pytest.fixture()
def cfg():
    return Config()


@pytest.fixture()
def window(qapp_instance, cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "transcrb.ui.onboarding.default_appdata_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "transcrb.ui.onboarding._detect_gpu",
        lambda: None,
    )
    monkeypatch.setattr(
        "transcrb.ui.onboarding.models_dir",
        lambda: tmp_path / "models",
    )
    with patch("transcrb.ui.onboarding.DownloaderThread"):
        from transcrb.ui.onboarding import OnboardingWindow
        w = OnboardingWindow(cfg)
        yield w
        w.close()


# ---------------------------------------------------------------------------
# _fmt_size
# ---------------------------------------------------------------------------

class TestFmtSize:
    def test_zero_returns_dash(self):
        assert _fmt_size(0) == "—"

    def test_negative_returns_dash(self):
        assert _fmt_size(-1) == "—"

    def test_kilobytes(self):
        assert _fmt_size(1024) == "1 KB"

    def test_megabytes(self):
        assert _fmt_size(1024 ** 2) == "1 MB"

    def test_gigabytes(self):
        assert _fmt_size(1024 ** 3) == "1.0 GB"

    def test_fractional_gigabytes(self):
        result = _fmt_size(int(1.5 * 1024 ** 3))
        assert "1.5 GB" in result

    def test_just_below_mb(self):
        assert "KB" in _fmt_size(1024 ** 2 - 1)

    def test_just_below_gb(self):
        assert "MB" in _fmt_size(1024 ** 3 - 1)

    def test_large_mb_value(self):
        assert "MB" in _fmt_size(500 * 1024 * 1024)


# ---------------------------------------------------------------------------
# _detect_gpu
# ---------------------------------------------------------------------------

class TestDetectGpu:
    def test_returns_first_line_on_success(self):
        with patch("subprocess.check_output", return_value=b"RTX 3060, 12288 MiB\nother line"):
            result = _detect_gpu()
        assert result == "RTX 3060, 12288 MiB"

    def test_returns_none_on_exception(self):
        with patch("subprocess.check_output", side_effect=FileNotFoundError):
            assert _detect_gpu() is None

    def test_returns_none_on_timeout(self):
        with patch("subprocess.check_output", side_effect=subprocess.TimeoutExpired("nvidia-smi", 2)):
            assert _detect_gpu() is None

    def test_returns_none_on_empty_output(self):
        with patch("subprocess.check_output", return_value=b""):
            assert _detect_gpu() is None

    def test_returns_none_on_whitespace_only(self):
        with patch("subprocess.check_output", return_value=b"   \n  "):
            assert _detect_gpu() is None

    def test_strips_whitespace_from_gpu_name(self):
        with patch("subprocess.check_output", return_value=b"  RTX 3060  "):
            result = _detect_gpu()
        assert result == "RTX 3060"

    def test_called_process_error_returns_none(self):
        with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "nvidia-smi")):
            assert _detect_gpu() is None


# ---------------------------------------------------------------------------
# _hotkey_pretty
# ---------------------------------------------------------------------------

class TestHotkeyPretty:
    def test_right_ctrl(self):
        assert _hotkey_pretty("right ctrl") == "Right Ctrl"

    def test_left_ctrl(self):
        assert _hotkey_pretty("left ctrl") == "Left Ctrl"

    def test_right_alt(self):
        assert _hotkey_pretty("right alt") == "Right Alt"

    def test_right_shift(self):
        assert _hotkey_pretty("right shift") == "Right Shift"

    def test_right_win(self):
        assert _hotkey_pretty("right win") == "Right Win"

    def test_modifier_ctrl_capitalized(self):
        assert _hotkey_pretty("ctrl") == "Ctrl"

    def test_modifier_shift_capitalized(self):
        assert _hotkey_pretty("shift") == "Shift"

    def test_modifier_alt_capitalized(self):
        assert _hotkey_pretty("alt") == "Alt"

    def test_modifier_win_capitalized(self):
        assert _hotkey_pretty("win") == "Win"

    def test_combo_with_plus(self):
        result = _hotkey_pretty("ctrl+shift")
        assert result == "Ctrl + Shift"

    def test_unknown_key_capitalized(self):
        assert _hotkey_pretty("f12") == "F12"

    def test_three_part_combo(self):
        result = _hotkey_pretty("ctrl+alt+delete")
        assert result == "Ctrl + Alt + Delete"

    def test_case_insensitive_input(self):
        assert _hotkey_pretty("RIGHT CTRL") == "Right Ctrl"

    def test_spaces_around_plus_stripped(self):
        result = _hotkey_pretty("ctrl + shift")
        assert result == "Ctrl + Shift"


# ---------------------------------------------------------------------------
# _StepperBar.set_active
# ---------------------------------------------------------------------------

class TestStepperBar:
    def test_set_active_middle(self, qapp_instance):
        bar = _StepperBar(["A", "B", "C"])
        bar.set_active(1)
        assert bar._active == 1

    def test_set_active_first(self, qapp_instance):
        bar = _StepperBar(["A", "B", "C"])
        bar.set_active(0)
        assert bar._active == 0

    def test_set_active_last(self, qapp_instance):
        bar = _StepperBar(["A", "B", "C"])
        bar.set_active(2)
        assert bar._active == 2

    def test_set_active_clamps_below_zero(self, qapp_instance):
        bar = _StepperBar(["A", "B"])
        bar.set_active(-5)
        assert bar._active == 0

    def test_set_active_clamps_above_max(self, qapp_instance):
        bar = _StepperBar(["A", "B", "C"])
        bar.set_active(100)
        assert bar._active == 2

    def test_initial_active_is_zero(self, qapp_instance):
        bar = _StepperBar(STEPS)
        assert bar._active == 0


# ---------------------------------------------------------------------------
# OnboardingWindow — _goto state
# ---------------------------------------------------------------------------

class TestGoto:
    def test_initial_step_is_zero(self, window):
        assert window._stack.currentIndex() == 0

    def test_goto_updates_stack_index(self, window):
        window._goto(2)
        assert window._stack.currentIndex() == 2

    def test_goto_step0_hides_back_button(self, window):
        window._goto(0)
        assert not window._btn_back.isVisible()

    def test_goto_step1_enables_back_button(self, window):
        window._goto(1)
        assert window._btn_back.isEnabled()

    def test_goto_step4_next_text_is_download(self, window):
        window._goto(4)
        assert "Скачать" in window._btn_next.text()

    def test_goto_step0_next_text_is_start(self, window):
        window._goto(0)
        assert "Поехали" in window._btn_next.text()

    def test_goto_download_step_hides_footer(self, window):
        window._goto(len(STEPS))
        assert window._foot.isHidden()

    def test_goto_normal_step_shows_footer(self, window):
        window._goto(2)
        assert not window._foot.isHidden()

    def test_goto_updates_progress_label(self, window):
        window._goto(2)
        assert window._lbl_progress.text() == f"3 / {len(STEPS)}"

    def test_goto_download_step_clears_progress_label(self, window):
        window._goto(len(STEPS))
        assert window._lbl_progress.text() == ""


# ---------------------------------------------------------------------------
# OnboardingWindow — navigation (next/back)
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_next_advances_step(self, window):
        window._goto(0)
        window._on_next()
        assert window._stack.currentIndex() == 1

    def test_back_returns_to_previous(self, window):
        window._goto(2)
        window._on_back()
        assert window._stack.currentIndex() == 1

    def test_back_from_step0_no_op(self, window):
        window._goto(0)
        window._on_back()
        assert window._stack.currentIndex() == 0

    def test_next_then_next_then_back_correct(self, window):
        window._goto(0)
        window._on_next()
        window._on_next()
        window._on_back()
        assert window._stack.currentIndex() == 1

    def test_back_from_download_step_no_op(self, window):
        window._goto(len(STEPS))
        window._on_back()
        assert window._stack.currentIndex() == len(STEPS)

    def test_next_from_step4_triggers_download(self, window):
        window._goto(4)
        with patch.object(window, "_start_download") as mock_dl:
            window._on_next()
        mock_dl.assert_called_once()

    def test_next_does_not_exceed_final_step(self, window):
        window._goto(len(STEPS) - 1)
        with patch.object(window, "_start_download"):
            window._on_next()
        assert window._stack.currentIndex() != len(STEPS) - 2


# ---------------------------------------------------------------------------
# OnboardingWindow — model selection
# ---------------------------------------------------------------------------

class TestModelSelection:
    def test_default_model_selected(self, window):
        assert window._chosen_model == DEFAULT_MODEL

    def test_select_model_updates_state(self, window):
        window._select_model("tiny")
        assert window._chosen_model == "tiny"

    def test_select_model_deselects_others(self, window):
        window._select_model("small")
        for key, opt in window._model_options:
            expected = key == "small"
            assert opt.property("selected") == ("true" if expected else "false")

    def test_select_each_model_key(self, window):
        for key, *_ in MODELS:
            window._select_model(key)
            assert window._chosen_model == key

    def test_select_model_unknown_key_stores_it(self, window):
        window._select_model("custom-model-xyz")
        assert window._chosen_model == "custom-model-xyz"

    def test_select_model_all_options_deselected_for_unknown(self, window):
        window._select_model("not-a-real-model")
        for _k, opt in window._model_options:
            assert opt.property("selected") == "false"


# ---------------------------------------------------------------------------
# OnboardingWindow — hotkey selection
# ---------------------------------------------------------------------------

class TestHotkeySelection:
    def test_default_hotkey_selected(self, window):
        assert window._chosen_hotkey == DEFAULT_HOTKEY

    def test_select_preset_hotkey(self, window):
        for combo, _, _ in HOTKEY_PRESETS:
            window._select_hotkey(combo)
            assert window._chosen_hotkey == combo

    def test_preset_option_card_becomes_selected(self, window):
        first_combo = HOTKEY_PRESETS[0][0]
        window._select_hotkey(first_combo)
        assert window._hotkey_options[first_combo].property("selected") == "true"

    def test_other_preset_deselected_on_change(self, window):
        combos = [c for c, _, _ in HOTKEY_PRESETS]
        if len(combos) >= 2:
            window._select_hotkey(combos[0])
            window._select_hotkey(combos[1])
            assert window._hotkey_options[combos[0]].property("selected") == "false"
            assert window._hotkey_options[combos[1]].property("selected") == "true"

    def test_custom_key_sets_custom_card_selected(self, window):
        window._select_hotkey("f9")
        assert window._custom_opt.property("selected") == "true"

    def test_custom_key_shows_kbd_label(self, window):
        window._select_hotkey("f9")
        assert not window._custom_kbd.isHidden()

    def test_preset_key_hides_custom_kbd(self, window):
        window._select_hotkey("f9")
        window._select_hotkey(DEFAULT_HOTKEY)
        assert window._custom_kbd.isHidden()

    def test_custom_key_kbd_label_text(self, window):
        window._select_hotkey("pause")
        assert "Pause" in window._custom_kbd.text()


# ---------------------------------------------------------------------------
# OnboardingWindow — _refresh_finish_summary
# ---------------------------------------------------------------------------

class TestRefreshFinishSummary:
    def test_model_label_shown_in_summary(self, window):
        window._select_model("small")
        window._refresh_finish_summary()
        text = window._sum_model.property("desc_label").text()
        assert "Small" in text

    def test_dir_shown_in_summary(self, window, tmp_path):
        window._chosen_dir = tmp_path
        window._refresh_finish_summary()
        text = window._sum_dir.property("desc_label").text()
        assert str(tmp_path) in text

    def test_hotkey_shown_in_summary(self, window):
        window._select_hotkey(DEFAULT_HOTKEY)
        window._refresh_finish_summary()
        text = window._sum_hotkey.property("desc_label").text()
        assert "Right Ctrl" in text

    def test_size_shown_for_model(self, window):
        window._select_model("large-v3")
        window._refresh_finish_summary()
        text = window._sum_model.property("desc_label").text()
        assert "GB" in text

    def test_unknown_model_uses_key_as_label(self, window):
        window._chosen_model = "custom-xyz"
        window._refresh_finish_summary()
        text = window._sum_model.property("desc_label").text()
        assert "custom-xyz" in text


# ---------------------------------------------------------------------------
# OnboardingWindow — _save_pre_download_config
# ---------------------------------------------------------------------------

class TestSavePreDownloadConfig:
    def test_saves_chosen_model_to_config(self, window, tmp_path):
        window._chosen_dir = tmp_path
        window._chosen_model = "small"
        window._chosen_hotkey = "right alt"
        with patch("transcrb.ui.onboarding.save_config") as mock_save, \
             patch("transcrb.ui.onboarding.clear_override"), \
             patch("transcrb.ui.onboarding.write_override"), \
             patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path):
            result = window._save_pre_download_config()
        assert result is True
        assert window._cfg.asr.model == "small"

    def test_saves_chosen_hotkey_to_config(self, window, tmp_path):
        window._chosen_dir = tmp_path
        window._chosen_hotkey = "right alt"
        with patch("transcrb.ui.onboarding.save_config"), \
             patch("transcrb.ui.onboarding.clear_override"), \
             patch("transcrb.ui.onboarding.write_override"), \
             patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path):
            window._save_pre_download_config()
        assert window._cfg.hotkey.combo == "right alt"

    def test_clears_override_when_default_dir(self, window, tmp_path):
        window._chosen_dir = tmp_path
        with patch("transcrb.ui.onboarding.save_config"), \
             patch("transcrb.ui.onboarding.clear_override") as mock_clear, \
             patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path):
            window._save_pre_download_config()
        mock_clear.assert_called_once()

    def test_writes_override_when_custom_dir(self, window, tmp_path):
        custom = tmp_path / "custom_app_dir"
        custom.mkdir()
        window._chosen_dir = custom
        with patch("transcrb.ui.onboarding.save_config"), \
             patch("transcrb.ui.onboarding.write_override") as mock_write, \
             patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path):
            window._save_pre_download_config()
        mock_write.assert_called_once()

    def test_returns_false_when_save_config_fails(self, window, tmp_path):
        window._chosen_dir = tmp_path
        with patch("transcrb.ui.onboarding.save_config", side_effect=OSError("disk full")), \
             patch("transcrb.ui.onboarding.clear_override"), \
             patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path), \
             patch("PySide6.QtWidgets.QMessageBox.critical"):
            result = window._save_pre_download_config()
        assert result is False

    def test_onboarded_set_false_before_download(self, window, tmp_path):
        window._chosen_dir = tmp_path
        window._cfg.onboarded = True
        with patch("transcrb.ui.onboarding.save_config"), \
             patch("transcrb.ui.onboarding.clear_override"), \
             patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path):
            window._save_pre_download_config()
        assert window._cfg.onboarded is False


# ---------------------------------------------------------------------------
# OnboardingWindow — download callbacks
# ---------------------------------------------------------------------------

class TestDownloadCallbacks:
    def test_on_dl_progress_updates_bar_with_total(self, window):
        window._on_dl_progress(512 * 1024, 1024 * 1024)
        assert window._dl_bar.value() == 50
        assert "50%" in window._dl_meta.text()

    def test_on_dl_progress_indeterminate_when_total_zero(self, window):
        window._dl_bar.setRange(0, 100)
        window._on_dl_progress(100, 0)
        assert window._dl_bar.maximum() == 0

    def test_on_dl_progress_clamps_pct_at_100(self, window):
        window._on_dl_progress(2000, 1000)
        assert window._dl_bar.value() <= 100

    def test_on_dl_progress_stores_tuple(self, window):
        window._on_dl_progress(200, 1000)
        assert window._dl_progress_value == (200, 1000)

    def test_on_dl_failed_shows_error_label(self, window):
        window._on_dl_failed("connection refused")
        assert not window._dl_error.isHidden()
        assert "connection refused" in window._dl_error.text()

    def test_on_dl_failed_shows_retry_button(self, window):
        window._on_dl_failed("err")
        assert not window._dl_retry_btn.isHidden()

    def test_on_dl_failed_shows_back_button(self, window):
        window._on_dl_failed("err")
        assert not window._dl_back_btn.isHidden()

    def test_on_dl_failed_hides_cancel_button(self, window):
        window._dl_cancel_btn.show()
        window._on_dl_failed("err")
        assert window._dl_cancel_btn.isHidden()

    def test_on_dl_finished_sets_onboarded_true(self, window):
        window._cfg.onboarded = False
        with patch("transcrb.ui.onboarding.save_config"), \
             patch.object(window, "_emit_completed"):
            window._on_dl_finished("/some/path")
        assert window._cfg.onboarded is True

    def test_on_dl_finished_sets_bar_to_100(self, window):
        with patch("transcrb.ui.onboarding.save_config"), \
             patch.object(window, "_emit_completed"):
            window._on_dl_finished("/path")
        assert window._dl_bar.value() == 100

    def test_on_dl_finished_sets_done_flag(self, window):
        with patch("transcrb.ui.onboarding.save_config"), \
             patch.object(window, "_emit_completed"):
            window._on_dl_finished("/path")
        assert window._done is True

    def test_on_dl_finished_save_failure_calls_failed(self, window):
        with patch("transcrb.ui.onboarding.save_config", side_effect=OSError("no space")), \
             patch.object(window, "_on_dl_failed") as mock_failed:
            window._on_dl_finished("/path")
        mock_failed.assert_called_once()

    def test_on_dl_cancel_goes_to_last_normal_step(self, window):
        window._dl_thread = None
        window._on_dl_cancel()
        assert window._stack.currentIndex() == len(STEPS) - 1

    def test_on_dl_cancel_cancels_running_thread(self, window):
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        window._dl_thread = mock_thread
        window._on_dl_cancel()
        mock_thread.cancel.assert_called_once()

    def test_on_dl_back_goes_to_last_normal_step(self, window):
        window._on_dl_back()
        assert window._stack.currentIndex() == len(STEPS) - 1

    def test_on_dl_back_clears_thread(self, window):
        window._dl_thread = MagicMock()
        window._on_dl_back()
        assert window._dl_thread is None


# ---------------------------------------------------------------------------
# _HotkeyCaptureDialog — _on_event
# ---------------------------------------------------------------------------

class TestHotkeyCaptureDialogOnEvent:
    def _make_event(self, name: str, event_type: str) -> SimpleNamespace:
        return SimpleNamespace(name=name, event_type=event_type)

    def test_ignores_non_down_event(self, qapp_instance):
        with patch("transcrb.ui.onboarding.keyboard", create=True):
            dlg = _HotkeyCaptureDialog()
            emitted = []
            dlg.captured.connect(lambda n: emitted.append(n))
            dlg._on_event(self._make_event("a", "up"))
            assert emitted == []

    def test_ignores_esc_key(self, qapp_instance):
        with patch("transcrb.ui.onboarding.keyboard", create=True):
            dlg = _HotkeyCaptureDialog()
            emitted = []
            dlg.captured.connect(lambda n: emitted.append(n))
            dlg._on_event(self._make_event("esc", "down"))
            assert emitted == []

    def test_emits_key_name_on_down(self, qapp_instance):
        with patch("transcrb.ui.onboarding.keyboard", create=True):
            dlg = _HotkeyCaptureDialog()
            emitted = []
            dlg.captured.connect(lambda n: emitted.append(n))
            dlg._on_event(self._make_event("f5", "down"))
            assert "f5" in emitted

    def test_emits_lowercase_name(self, qapp_instance):
        with patch("transcrb.ui.onboarding.keyboard", create=True):
            dlg = _HotkeyCaptureDialog()
            emitted = []
            dlg.captured.connect(lambda n: emitted.append(n))
            dlg._on_event(self._make_event("RIGHT CTRL", "down"))
            assert "right ctrl" in emitted

    def test_ignores_empty_name(self, qapp_instance):
        with patch("transcrb.ui.onboarding.keyboard", create=True):
            dlg = _HotkeyCaptureDialog()
            emitted = []
            dlg.captured.connect(lambda n: emitted.append(n))
            dlg._on_event(self._make_event("", "down"))
            assert emitted == []

    def test_stop_hook_clears_hook(self, qapp_instance):
        import sys
        mock_kb = MagicMock()
        original = sys.modules.get("keyboard")
        try:
            sys.modules["keyboard"] = mock_kb
            dlg = _HotkeyCaptureDialog()
            dlg._hook = MagicMock()
            hook_ref = dlg._hook
            dlg._stop_hook()
            assert dlg._hook is None
            mock_kb.unhook.assert_called_once_with(hook_ref)
        finally:
            if original is None:
                sys.modules.pop("keyboard", None)
            else:
                sys.modules["keyboard"] = original

    def test_stop_hook_idempotent_when_no_hook(self, qapp_instance):
        with patch("transcrb.ui.onboarding.keyboard", create=True):
            dlg = _HotkeyCaptureDialog()
            dlg._hook = None
            dlg._stop_hook()
            assert dlg._hook is None


# ---------------------------------------------------------------------------
# OnboardingWindow — _validate_dir
# ---------------------------------------------------------------------------

class TestValidateDir:
    def test_valid_dir_returns_true(self, window, tmp_path):
        assert window._validate_dir(tmp_path) is True

    def test_nonwritable_dir_returns_false(self, window, tmp_path):
        with patch.object(Path, "mkdir"), \
             patch.object(Path, "write_text", side_effect=PermissionError("denied")), \
             patch("PySide6.QtWidgets.QMessageBox.warning"):
            result = window._validate_dir(tmp_path / "probe_dir")
        assert result is False

    def test_creates_probe_file_and_removes_it(self, window, tmp_path):
        window._validate_dir(tmp_path)
        probe = tmp_path / ".winwhisp_probe"
        assert not probe.exists()

    def test_new_nested_dir_created(self, window, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        result = window._validate_dir(nested)
        assert result is True
        assert nested.exists()


# ---------------------------------------------------------------------------
# OnboardingWindow — _on_reset_dir
# ---------------------------------------------------------------------------

class TestOnResetDir:
    def test_reset_restores_default_dir(self, window, tmp_path):
        window._chosen_dir = tmp_path / "custom"
        with patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path):
            window._on_reset_dir()
        assert window._chosen_dir == tmp_path

    def test_reset_updates_path_label(self, window, tmp_path):
        with patch("transcrb.ui.onboarding.default_appdata_dir", return_value=tmp_path):
            window._on_reset_dir()
        assert str(tmp_path) in window._path_label.text()


# ---------------------------------------------------------------------------
# OnboardingWindow — closeEvent
# ---------------------------------------------------------------------------

class TestCloseEvent:
    def test_cancelled_emitted_when_not_done(self, window):
        window._done = False
        window._dl_thread = None
        emitted = []
        window.cancelled.connect(lambda: emitted.append(True))
        window.close()
        assert emitted == [True]

    def test_cancel_not_emitted_when_done(self, window):
        window._done = True
        emitted = []
        window.cancelled.connect(lambda: emitted.append(True))
        window.close()
        assert emitted == []

    def test_running_thread_cancelled_on_close(self, window):
        window._done = False
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = True
        window._dl_thread = mock_thread
        window.cancelled.connect(lambda: None)
        window.close()
        mock_thread.cancel.assert_called_once()
