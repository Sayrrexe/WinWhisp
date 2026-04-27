from __future__ import annotations

import time
from unittest.mock import MagicMock, call, patch

import pytest

from transcrb.app import State, TranscrbApp, _ensure_vocab_file, _get_foreground_hwnd
from transcrb.config import Config


# ---------------------------------------------------------------------------
# Fixture: builds TranscrbApp instance without __init__ (bypasses all Qt deps)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(tmp_path):
    obj = TranscrbApp.__new__(TranscrbApp)
    cfg = Config()

    obj.cfg = cfg
    obj.vocab = MagicMock()
    obj.state = State.LOADING
    obj._press_time = 0.0
    obj._session_started_at = 0.0
    obj._recording_hwnd = None
    obj._pending_chunks = 0
    obj._focus_lost = False
    obj._session_text = []
    obj._processing_finished_at = 0.0

    obj.tray = MagicMock()
    obj.window = MagicMock()
    obj.overlay = MagicMock()
    obj.audio = MagicMock()
    obj.asr = MagicMock()
    obj.hotkey = MagicMock()
    obj.history = MagicMock()
    obj.runtime = MagicMock()
    obj.updater = MagicMock()
    obj.files = MagicMock()

    timer_release = MagicMock()
    timer_release.isActive.return_value = False
    obj._release_timer = timer_release

    timer_max = MagicMock()
    timer_max.isActive.return_value = False
    obj._max_duration_timer = timer_max

    return obj


# ---------------------------------------------------------------------------
# _ensure_vocab_file
# ---------------------------------------------------------------------------

def test_ensure_vocab_file_skips_if_exists(tmp_path):
    target = tmp_path / "vocab.yaml"
    target.write_text("existing")
    with patch("transcrb.app.vocab_path", return_value=target), \
         patch("transcrb.app.shutil.copyfile") as cp:
        _ensure_vocab_file()
        cp.assert_not_called()


def test_ensure_vocab_file_copies_when_missing(tmp_path):
    target = tmp_path / "vocab.yaml"
    src = tmp_path / "default_vocab.yaml"
    src.write_text("default")
    with patch("transcrb.app.vocab_path", return_value=target), \
         patch("transcrb.app.resources_dir", return_value=tmp_path):
        _ensure_vocab_file()
        assert target.exists()
        assert target.read_text() == "default"


def test_ensure_vocab_file_no_src_no_error(tmp_path):
    target = tmp_path / "vocab.yaml"
    empty_dir = tmp_path / "nodefaults"
    empty_dir.mkdir()
    with patch("transcrb.app.vocab_path", return_value=target), \
         patch("transcrb.app.resources_dir", return_value=empty_dir):
        _ensure_vocab_file()
        assert not target.exists()


def test_ensure_vocab_file_creates_parent(tmp_path):
    target = tmp_path / "sub" / "dir" / "vocab.yaml"
    src_dir = tmp_path / "res"
    src_dir.mkdir()
    (src_dir / "default_vocab.yaml").write_text("v")
    with patch("transcrb.app.vocab_path", return_value=target), \
         patch("transcrb.app.resources_dir", return_value=src_dir):
        _ensure_vocab_file()
        assert target.exists()


def test_ensure_vocab_file_idempotent(tmp_path):
    target = tmp_path / "vocab.yaml"
    src_dir = tmp_path / "res"
    src_dir.mkdir()
    (src_dir / "default_vocab.yaml").write_text("v")
    with patch("transcrb.app.vocab_path", return_value=target), \
         patch("transcrb.app.resources_dir", return_value=src_dir):
        _ensure_vocab_file()
        _ensure_vocab_file()
    assert target.read_text() == "v"


# ---------------------------------------------------------------------------
# _get_foreground_hwnd
# ---------------------------------------------------------------------------

def test_get_foreground_hwnd_returns_value():
    win32gui = MagicMock()
    win32gui.GetForegroundWindow.return_value = 12345
    with patch.dict("sys.modules", {"win32gui": win32gui}):
        result = _get_foreground_hwnd()
    assert result == 12345


def test_get_foreground_hwnd_returns_int_type():
    win32gui = MagicMock()
    win32gui.GetForegroundWindow.return_value = 99
    with patch.dict("sys.modules", {"win32gui": win32gui}):
        result = _get_foreground_hwnd()
    assert isinstance(result, int)


def test_get_foreground_hwnd_returns_none_on_exception():
    with patch("builtins.__import__", side_effect=ImportError):
        result = _get_foreground_hwnd()
    assert result is None


def test_get_foreground_hwnd_returns_none_on_other_exception():
    win32gui = MagicMock()
    win32gui.GetForegroundWindow.side_effect = OSError("fail")
    with patch.dict("sys.modules", {"win32gui": win32gui}):
        result = _get_foreground_hwnd()
    assert result is None


def test_get_foreground_hwnd_zero_handle():
    win32gui = MagicMock()
    win32gui.GetForegroundWindow.return_value = 0
    with patch.dict("sys.modules", {"win32gui": win32gui}):
        result = _get_foreground_hwnd()
    assert result == 0


def test_get_foreground_hwnd_consistent_across_calls():
    win32gui = MagicMock()
    win32gui.GetForegroundWindow.return_value = 555
    with patch.dict("sys.modules", {"win32gui": win32gui}):
        r1 = _get_foreground_hwnd()
        r2 = _get_foreground_hwnd()
    assert r1 == r2 == 555


# ---------------------------------------------------------------------------
# _set_state
# ---------------------------------------------------------------------------

def test_set_state_updates_state_enum(app):
    app._set_state(State.IDLE)
    assert app.state == State.IDLE


def test_set_state_updates_runtime_state(app):
    app._set_state(State.RECORDING)
    assert app.runtime.state == "recording"


def test_set_state_transitions_all_states(app):
    for s in State:
        app._set_state(s)
        assert app.state == s


def test_set_state_runtime_value_is_string(app):
    app._set_state(State.IDLE)
    assert isinstance(app.runtime.state, str)


def test_set_state_runtime_value_matches_enum_value(app):
    for s in State:
        app._set_state(s)
        assert app.runtime.state == s.value


def test_set_state_idempotent(app):
    app._set_state(State.IDLE)
    app._set_state(State.IDLE)
    assert app.state == State.IDLE
    assert app.runtime.state == "idle"


def test_set_state_sequential_transitions(app):
    transitions = [State.LOADING, State.IDLE, State.RECORDING, State.PROCESSING, State.IDLE]
    for s in transitions:
        app._set_state(s)
    assert app.state == State.IDLE
    assert app.runtime.state == "idle"


# ---------------------------------------------------------------------------
# _on_model_loaded
# ---------------------------------------------------------------------------

def test_on_model_loaded_loading_to_idle(app):
    app.state = State.LOADING
    app._on_model_loaded()
    assert app.state == State.IDLE


def test_on_model_loaded_sets_runtime_flag(app):
    app.state = State.LOADING
    app._on_model_loaded()
    assert app.runtime.model_loaded is True


def test_on_model_loaded_shows_notification_when_configured(app):
    app.state = State.LOADING
    app.cfg.tray.show_notifications = True
    app._on_model_loaded()
    app.tray.notify.assert_called_once()


def test_on_model_loaded_no_notification_when_disabled(app):
    app.state = State.LOADING
    app.cfg.tray.show_notifications = False
    app._on_model_loaded()
    app.tray.notify.assert_not_called()


def test_on_model_loaded_from_idle_stays_idle(app):
    app.state = State.IDLE
    app._on_model_loaded()
    assert app.state == State.IDLE


def test_on_model_loaded_updates_tooltip(app):
    app.state = State.IDLE
    app._on_model_loaded()
    app.tray.set_tooltip.assert_called()


# ---------------------------------------------------------------------------
# _on_model_unloaded
# ---------------------------------------------------------------------------

def test_on_model_unloaded_clears_runtime_flag(app):
    app.runtime.model_loaded = True
    app._on_model_unloaded()
    assert app.runtime.model_loaded is False


def test_on_model_unloaded_updates_tooltip(app):
    app._on_model_unloaded()
    app.tray.set_tooltip.assert_called_once()


def test_on_model_unloaded_tooltip_contains_hotkey(app):
    app.cfg.hotkey.combo = "right ctrl"
    app._on_model_unloaded()
    call_args = app.tray.set_tooltip.call_args[0][0]
    assert "right ctrl" in call_args


def test_on_model_unloaded_does_not_change_state(app):
    app.state = State.IDLE
    app._on_model_unloaded()
    assert app.state == State.IDLE


def test_on_model_unloaded_idempotent(app):
    app.runtime.model_loaded = True
    app._on_model_unloaded()
    app._on_model_unloaded()
    assert app.runtime.model_loaded is False


def test_on_model_unloaded_from_any_state(app):
    for s in State:
        app.state = s
        app.runtime.model_loaded = True
        app._on_model_unloaded()
        assert app.runtime.model_loaded is False


# ---------------------------------------------------------------------------
# _on_audio_level
# ---------------------------------------------------------------------------

def test_on_audio_level_emits_when_recording(app):
    import numpy as np
    app.state = State.RECORDING
    bands = np.zeros(10)
    with patch("transcrb.app.signals") as sig:
        app._on_audio_level(0.5, bands)
        sig.rms_updated.emit.assert_called_once_with(0.5, bands)


def test_on_audio_level_noop_when_idle(app):
    import numpy as np
    app.state = State.IDLE
    with patch("transcrb.app.signals") as sig:
        app._on_audio_level(0.5, np.zeros(10))
        sig.rms_updated.emit.assert_not_called()


def test_on_audio_level_noop_when_processing(app):
    import numpy as np
    app.state = State.PROCESSING
    with patch("transcrb.app.signals") as sig:
        app._on_audio_level(0.5, np.zeros(10))
        sig.rms_updated.emit.assert_not_called()


def test_on_audio_level_noop_when_loading(app):
    import numpy as np
    app.state = State.LOADING
    with patch("transcrb.app.signals") as sig:
        app._on_audio_level(0.1, np.zeros(5))
        sig.rms_updated.emit.assert_not_called()


def test_on_audio_level_passes_bands_unchanged(app):
    import numpy as np
    app.state = State.RECORDING
    bands = np.array([0.1, 0.2, 0.3])
    with patch("transcrb.app.signals") as sig:
        app._on_audio_level(0.5, bands)
    _, call_bands = sig.rms_updated.emit.call_args[0]
    assert (call_bands == bands).all()


# ---------------------------------------------------------------------------
# _on_hotkey_pressed
# ---------------------------------------------------------------------------

def test_hotkey_pressed_idle_to_recording(app):
    app.state = State.IDLE
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    assert app.state == State.RECORDING


def test_hotkey_pressed_loading_to_recording(app):
    # Code allows LOADING → RECORDING (guard is "not in (IDLE, LOADING)")
    app.state = State.LOADING
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    assert app.state == State.RECORDING


def test_hotkey_pressed_ignored_during_processing(app):
    app.state = State.PROCESSING
    app._on_hotkey_pressed()
    assert app.state == State.PROCESSING
    app.audio.start.assert_not_called()


def test_hotkey_pressed_ignored_during_grace_period(app):
    app.state = State.IDLE
    app._processing_finished_at = time.monotonic()
    app._on_hotkey_pressed()
    assert app.state == State.IDLE


def test_hotkey_pressed_calls_asr_prepare(app):
    app.state = State.IDLE
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    app.asr.prepare.assert_called_once()


def test_hotkey_pressed_starts_audio(app):
    app.state = State.IDLE
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    app.audio.start.assert_called_once()


def test_hotkey_pressed_shows_overlay_when_enabled(app):
    app.state = State.IDLE
    app.cfg.overlay.enabled = True
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    app.overlay.show_fade.assert_called_once()


def test_hotkey_pressed_no_overlay_when_disabled(app):
    app.state = State.IDLE
    app.cfg.overlay.enabled = False
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    app.overlay.show_fade.assert_not_called()


def test_hotkey_pressed_audio_failure_returns_to_idle(app):
    app.state = State.IDLE
    app.audio.start.side_effect = OSError("no mic")
    with patch("transcrb.app._get_foreground_hwnd", return_value=None):
        app._on_hotkey_pressed()
    assert app.state == State.IDLE


def test_hotkey_pressed_during_recording_with_active_release_timer(app):
    app.state = State.RECORDING
    app._release_timer.isActive.return_value = True
    app._on_hotkey_pressed()
    app._release_timer.stop.assert_called()
    assert app.state == State.RECORDING


def test_hotkey_pressed_resets_session_text(app):
    app.state = State.IDLE
    app._session_text = ["old text"]
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    assert app._session_text == []


def test_hotkey_pressed_starts_max_duration_timer(app):
    app.state = State.IDLE
    app.audio.start.return_value = None
    app._on_hotkey_pressed()
    app._max_duration_timer.start.assert_called_once()


# ---------------------------------------------------------------------------
# _on_hotkey_released
# ---------------------------------------------------------------------------

def test_hotkey_released_not_recording_noop(app):
    app.state = State.IDLE
    app._on_hotkey_released()
    app._release_timer.start.assert_not_called()


def test_hotkey_released_release_timer_active_noop(app):
    app.state = State.RECORDING
    app._release_timer.isActive.return_value = True
    app._on_hotkey_released()
    app._release_timer.start.assert_not_called()


def test_hotkey_released_starts_release_timer_with_tail(app):
    app.state = State.RECORDING
    app.cfg.hotkey.release_tail_ms = 500
    app.cfg.hotkey.min_hold_ms = 0
    app._press_time = time.monotonic() - 1.0
    app._on_hotkey_released()
    app._release_timer.start.assert_called_once_with(500)


def test_hotkey_released_zero_tail_calls_finalize_immediately(app):
    app.state = State.RECORDING
    app.cfg.hotkey.release_tail_ms = 0
    app.cfg.hotkey.min_hold_ms = 0
    app._press_time = time.monotonic() - 1.0
    with patch.object(app, "_finalize_release") as fin:
        app._on_hotkey_released()
        fin.assert_called_once()


def test_hotkey_released_short_hold_calls_finalize_directly(app):
    app.state = State.RECORDING
    app.cfg.hotkey.min_hold_ms = 5000
    app.cfg.hotkey.release_tail_ms = 500
    app._press_time = time.monotonic()
    with patch.object(app, "_finalize_release") as fin:
        app._on_hotkey_released()
        fin.assert_called_once()


# ---------------------------------------------------------------------------
# _finalize_release
# ---------------------------------------------------------------------------

def test_finalize_release_not_recording_noop(app):
    app.state = State.IDLE
    app._finalize_release()
    app.audio.stop.assert_not_called()


def test_finalize_release_short_press_no_chunks_returns_idle(app):
    app.state = State.RECORDING
    app.cfg.hotkey.min_hold_ms = 5000
    app._press_time = time.monotonic()
    app._pending_chunks = 0
    app.cfg.overlay.enabled = False
    app._finalize_release()
    assert app.state == State.IDLE


def test_finalize_release_short_press_hides_overlay(app):
    app.state = State.RECORDING
    app.cfg.hotkey.min_hold_ms = 5000
    app._press_time = time.monotonic()
    app._pending_chunks = 0
    app.cfg.overlay.enabled = True
    app._finalize_release()
    app.overlay.hide_fade.assert_called_once()


def test_finalize_release_valid_press_to_processing(app):
    app.state = State.RECORDING
    app.cfg.hotkey.min_hold_ms = 0
    app._press_time = time.monotonic() - 1.0
    app._pending_chunks = 0
    app.cfg.overlay.enabled = False
    app._finalize_release()
    assert app.state == State.PROCESSING


def test_finalize_release_shows_busy_overlay(app):
    app.state = State.RECORDING
    app.cfg.hotkey.min_hold_ms = 0
    app._press_time = time.monotonic() - 1.0
    app._pending_chunks = 0
    app.cfg.overlay.enabled = True
    app._finalize_release()
    app.overlay.show_busy.assert_called_once()


def test_finalize_release_stops_timers(app):
    app.state = State.RECORDING
    app.cfg.hotkey.min_hold_ms = 0
    app._press_time = time.monotonic() - 1.0
    app._finalize_release()
    app._max_duration_timer.stop.assert_called()
    app._release_timer.stop.assert_called()


def test_finalize_release_pending_chunks_forces_processing(app):
    app.state = State.RECORDING
    app.cfg.hotkey.min_hold_ms = 5000
    app._press_time = time.monotonic()
    app._pending_chunks = 3
    app.cfg.overlay.enabled = False
    app._finalize_release()
    assert app.state == State.PROCESSING


# ---------------------------------------------------------------------------
# _on_audio_chunk
# ---------------------------------------------------------------------------

def test_on_audio_chunk_increments_pending(app):
    import numpy as np
    chunk = np.zeros(160, dtype=np.float32)
    app._on_audio_chunk(chunk)
    assert app._pending_chunks == 1


def test_on_audio_chunk_submits_to_asr(app):
    import numpy as np
    chunk = np.zeros(160, dtype=np.float32)
    app._on_audio_chunk(chunk)
    app.asr.submit.assert_called_once_with(chunk)


def test_on_audio_chunk_none_noop(app):
    app._on_audio_chunk(None)
    assert app._pending_chunks == 0
    app.asr.submit.assert_not_called()


def test_on_audio_chunk_empty_noop(app):
    import numpy as np
    app._on_audio_chunk(np.array([]))
    assert app._pending_chunks == 0
    app.asr.submit.assert_not_called()


def test_on_audio_chunk_multiple_increments(app):
    import numpy as np
    chunk = np.zeros(160, dtype=np.float32)
    app._on_audio_chunk(chunk)
    app._on_audio_chunk(chunk)
    app._on_audio_chunk(chunk)
    assert app._pending_chunks == 3


# ---------------------------------------------------------------------------
# _on_max_duration
# ---------------------------------------------------------------------------

def test_on_max_duration_recording_calls_finalize(app):
    app.state = State.RECORDING
    with patch.object(app, "_finalize_release") as fin:
        app._on_max_duration()
        fin.assert_called_once()


def test_on_max_duration_idle_noop(app):
    app.state = State.IDLE
    with patch.object(app, "_finalize_release") as fin:
        app._on_max_duration()
        fin.assert_not_called()


def test_on_max_duration_processing_noop(app):
    app.state = State.PROCESSING
    with patch.object(app, "_finalize_release") as fin:
        app._on_max_duration()
        fin.assert_not_called()


def test_on_max_duration_loading_noop(app):
    app.state = State.LOADING
    with patch.object(app, "_finalize_release") as fin:
        app._on_max_duration()
        fin.assert_not_called()


def test_on_max_duration_called_once_per_recording(app):
    app.state = State.RECORDING
    call_count = []
    with patch.object(app, "_finalize_release", side_effect=lambda: call_count.append(1)):
        app._on_max_duration()
    assert len(call_count) == 1


# ---------------------------------------------------------------------------
# _on_transcription_ready
# ---------------------------------------------------------------------------

def test_transcription_ready_decrements_pending(app):
    app._pending_chunks = 2
    app.state = State.PROCESSING
    with patch("transcrb.app._get_foreground_hwnd", return_value=None), \
         patch("transcrb.app.inject"):
        app._on_transcription_ready("hello")
    assert app._pending_chunks == 1


def test_transcription_ready_appends_session_text(app):
    app.state = State.PROCESSING
    app._pending_chunks = 1
    with patch("transcrb.app._get_foreground_hwnd", return_value=None), \
         patch("transcrb.app.inject"):
        app._on_transcription_ready("hello")
    assert "hello" in app._session_text


def test_transcription_ready_empty_text_not_injected(app):
    app.state = State.PROCESSING
    app._pending_chunks = 1
    with patch("transcrb.app.inject") as inj:
        app._on_transcription_ready("")
    inj.assert_not_called()


def test_transcription_ready_calls_inject_no_focus_change(app):
    app.state = State.PROCESSING
    app._pending_chunks = 1
    app._focus_lost = False
    app._recording_hwnd = 100
    app.cfg.injection.on_focus_change = "notify"
    with patch("transcrb.app._get_foreground_hwnd", return_value=100), \
         patch("transcrb.app.inject") as inj:
        app._on_transcription_ready("text")
    inj.assert_called_once()


def test_transcription_ready_detects_focus_loss(app):
    app.state = State.PROCESSING
    app._pending_chunks = 1
    app._focus_lost = False
    app._recording_hwnd = 100
    app.cfg.injection.on_focus_change = "notify"
    with patch("transcrb.app._get_foreground_hwnd", return_value=999), \
         patch("transcrb.app.inject"):
        app._on_transcription_ready("text")
    assert app._focus_lost is True


def test_transcription_ready_inject_mode_ignores_focus_loss(app):
    app.state = State.PROCESSING
    app._pending_chunks = 1
    app._focus_lost = True
    app._recording_hwnd = 100
    app.cfg.injection.on_focus_change = "inject"
    with patch("transcrb.app._get_foreground_hwnd", return_value=999), \
         patch("transcrb.app.inject") as inj:
        app._on_transcription_ready("text")
    inj.assert_called_once()


def test_transcription_ready_skip_mode_no_inject(app):
    app.state = State.PROCESSING
    app._pending_chunks = 1
    app._focus_lost = True
    app._recording_hwnd = 100
    app.cfg.injection.on_focus_change = "skip"
    with patch("transcrb.app._get_foreground_hwnd", return_value=999), \
         patch("transcrb.app.inject") as inj:
        app._on_transcription_ready("text")
    inj.assert_not_called()


def test_transcription_ready_calls_maybe_finish(app):
    app.state = State.PROCESSING
    app._pending_chunks = 1
    with patch("transcrb.app._get_foreground_hwnd", return_value=None), \
         patch("transcrb.app.inject"), \
         patch.object(app, "_maybe_finish") as mf:
        app._on_transcription_ready("x")
    mf.assert_called_once()


# ---------------------------------------------------------------------------
# _maybe_finish
# ---------------------------------------------------------------------------

def test_maybe_finish_not_processing_noop(app):
    app.state = State.IDLE
    app._pending_chunks = 0
    app._maybe_finish()
    app.history.add.assert_not_called()


def test_maybe_finish_pending_chunks_noop(app):
    app.state = State.PROCESSING
    app._pending_chunks = 2
    app._maybe_finish()
    app.history.add.assert_not_called()


def test_maybe_finish_transitions_to_idle(app):
    app.state = State.PROCESSING
    app._pending_chunks = 0
    app._session_text = []
    app.cfg.overlay.enabled = False
    with patch("transcrb.app.pyperclip"):
        app._maybe_finish()
    assert app.state == State.IDLE


def test_maybe_finish_adds_to_history(app):
    app.state = State.PROCESSING
    app._pending_chunks = 0
    app._session_text = ["hello world"]
    app._session_started_at = time.monotonic() - 2.0
    app.cfg.overlay.enabled = False
    with patch("transcrb.app.pyperclip"):
        app._maybe_finish()
    app.history.add.assert_called_once()
    args = app.history.add.call_args[0]
    assert args[0] == "hello world"


def test_maybe_finish_copies_to_clipboard(app):
    app.state = State.PROCESSING
    app._pending_chunks = 0
    app._session_text = ["text"]
    app.cfg.overlay.enabled = False
    with patch("transcrb.app.pyperclip") as pc:
        app._maybe_finish()
    pc.copy.assert_called_once_with("text")


def test_maybe_finish_empty_session_text_hides_overlay(app):
    app.state = State.PROCESSING
    app._pending_chunks = 0
    app._session_text = ["   "]
    app.cfg.overlay.enabled = True
    with patch("transcrb.app.pyperclip"):
        app._maybe_finish()
    app.overlay.hide_fade.assert_called_once()


def test_maybe_finish_notify_mode_focus_lost_shows_result(app):
    app.state = State.PROCESSING
    app._pending_chunks = 0
    app._session_text = ["result text"]
    app._focus_lost = True
    app.cfg.injection.on_focus_change = "notify"
    app.cfg.overlay.enabled = True
    with patch("transcrb.app.pyperclip"):
        app._maybe_finish()
    app.overlay.show_result.assert_called_once()


def test_maybe_finish_notify_mode_no_focus_lost_hides_overlay(app):
    app.state = State.PROCESSING
    app._pending_chunks = 0
    app._session_text = ["result text"]
    app._focus_lost = False
    app.cfg.injection.on_focus_change = "notify"
    app.cfg.overlay.enabled = True
    with patch("transcrb.app.pyperclip"):
        app._maybe_finish()
    app.overlay.hide_fade.assert_called_once()
    app.overlay.show_result.assert_not_called()


def test_maybe_finish_clipboard_error_does_not_crash(app):
    app.state = State.PROCESSING
    app._pending_chunks = 0
    app._session_text = ["text"]
    app.cfg.overlay.enabled = False
    with patch("transcrb.app.pyperclip") as pc:
        pc.copy.side_effect = Exception("clipboard fail")
        app._maybe_finish()
    assert app.state == State.IDLE


# ---------------------------------------------------------------------------
# _paste_again
# ---------------------------------------------------------------------------

def test_paste_again_calls_inject(app):
    with patch("transcrb.app.inject") as inj:
        app._paste_again("some text")
    inj.assert_called_once()
    assert inj.call_args[0][0] == "some text"


def test_paste_again_restore_false(app):
    with patch("transcrb.app.inject") as inj:
        app._paste_again("text")
    assert inj.call_args[1]["restore"] is False


def test_paste_again_uses_config_paste_combo(app):
    app.cfg.injection.paste_combo = "ctrl+shift+v"
    with patch("transcrb.app.inject") as inj:
        app._paste_again("x")
    assert inj.call_args[1]["paste_combo"] == "ctrl+shift+v"


def test_paste_again_empty_string(app):
    with patch("transcrb.app.inject") as inj:
        app._paste_again("")
    inj.assert_called_once_with(
        "",
        paste_combo=app.cfg.injection.paste_combo,
        pre_delay_ms=app.cfg.injection.pre_paste_delay_ms,
        post_delay_ms=app.cfg.injection.post_paste_delay_ms,
        restore=False,
    )


def test_paste_again_unicode_text(app):
    with patch("transcrb.app.inject") as inj:
        app._paste_again("тест на Unicode 日本語")
    assert inj.call_args[0][0] == "тест на Unicode 日本語"


def test_paste_again_uses_configured_delays(app):
    app.cfg.injection.pre_paste_delay_ms = 50
    app.cfg.injection.post_paste_delay_ms = 300
    with patch("transcrb.app.inject") as inj:
        app._paste_again("x")
    assert inj.call_args[1]["pre_delay_ms"] == 50
    assert inj.call_args[1]["post_delay_ms"] == 300


def test_on_reload_debounce_change_rebinds_hotkey(app):
    original_cfg = Config()
    original_cfg.hotkey.combo = app.cfg.hotkey.combo
    original_cfg.hotkey.debounce_ms = 100
    app.cfg = original_cfg

    new_cfg = Config()
    new_cfg.hotkey.combo = original_cfg.hotkey.combo
    new_cfg.hotkey.debounce_ms = 250

    old_hotkey = app.hotkey
    with patch("transcrb.app.load_config", return_value=new_cfg), \
         patch("transcrb.app.load_vocab", return_value=MagicMock()), \
         patch("transcrb.app.vocab_path", return_value=MagicMock()), \
         patch("transcrb.app.HotkeyBridge") as MockBridge:
        MockBridge.return_value = MagicMock()
        app._on_reload()
    old_hotkey.stop.assert_called()


# ---------------------------------------------------------------------------
# _on_error
# ---------------------------------------------------------------------------

def test_on_error_notifies_tray_when_enabled(app):
    app.cfg.tray.notify_on_error = True
    app._on_error("something broke")
    app.tray.notify.assert_called_once()


def test_on_error_no_tray_notify_when_disabled(app):
    app.cfg.tray.notify_on_error = False
    app._on_error("something broke")
    app.tray.notify.assert_not_called()


def test_on_error_message_in_notification(app):
    app.cfg.tray.notify_on_error = True
    app._on_error("disk full")
    args = app.tray.notify.call_args[0]
    assert "disk full" in args


def test_on_error_does_not_change_state(app):
    app.state = State.PROCESSING
    app.cfg.tray.notify_on_error = False
    app._on_error("error")
    assert app.state == State.PROCESSING


def test_on_error_from_audio_start_failure(app):
    app.state = State.IDLE
    app.cfg.tray.notify_on_error = True
    app._on_error("Не удалось открыть микрофон: no device")
    app.tray.notify.assert_called_once()


# ---------------------------------------------------------------------------
# _on_reload
# ---------------------------------------------------------------------------

def test_on_reload_updates_cfg(app):
    new_cfg = Config()
    new_cfg.hotkey.combo = "ctrl+alt+r"
    with patch("transcrb.app.load_config", return_value=new_cfg), \
         patch("transcrb.app.load_vocab", return_value=MagicMock()), \
         patch("transcrb.app.vocab_path", return_value=MagicMock()):
        app._on_reload()
    assert app.cfg is new_cfg


def test_on_reload_updates_vocab(app):
    new_vocab = MagicMock()
    with patch("transcrb.app.load_config", return_value=Config()), \
         patch("transcrb.app.load_vocab", return_value=new_vocab), \
         patch("transcrb.app.vocab_path", return_value=MagicMock()):
        app._on_reload()
    assert app.vocab is new_vocab


def test_on_reload_calls_asr_update_vocab(app):
    with patch("transcrb.app.load_config", return_value=Config()), \
         patch("transcrb.app.load_vocab", return_value=MagicMock()), \
         patch("transcrb.app.vocab_path", return_value=MagicMock()):
        app._on_reload()
    app.asr.update_vocab.assert_called_once()


def test_on_reload_rebinds_hotkey_when_combo_changed(app):
    original_cfg = Config()
    original_cfg.hotkey.combo = "right ctrl"
    app.cfg = original_cfg

    new_cfg = Config()
    new_cfg.hotkey.combo = "ctrl+alt+r"

    old_hotkey = app.hotkey

    with patch("transcrb.app.load_config", return_value=new_cfg), \
         patch("transcrb.app.load_vocab", return_value=MagicMock()), \
         patch("transcrb.app.vocab_path", return_value=MagicMock()), \
         patch("transcrb.app.HotkeyBridge") as MockBridge:
        new_hk = MagicMock()
        MockBridge.return_value = new_hk
        app._on_reload()
    old_hotkey.stop.assert_called()


def test_on_reload_no_rebind_when_combo_unchanged(app):
    same_cfg = Config()
    same_cfg.hotkey.combo = app.cfg.hotkey.combo
    same_cfg.hotkey.debounce_ms = app.cfg.hotkey.debounce_ms
    with patch("transcrb.app.load_config", return_value=same_cfg), \
         patch("transcrb.app.load_vocab", return_value=MagicMock()), \
         patch("transcrb.app.vocab_path", return_value=MagicMock()):
        app._on_reload()
    app.hotkey.stop.assert_not_called()


def test_on_reload_refreshes_dashboard(app):
    with patch("transcrb.app.load_config", return_value=Config()), \
         patch("transcrb.app.load_vocab", return_value=MagicMock()), \
         patch("transcrb.app.vocab_path", return_value=MagicMock()):
        app._on_reload()
    app.window.refresh_dashboard.assert_called_once()


# ---------------------------------------------------------------------------
# _sync_autostart_from_registry
# ---------------------------------------------------------------------------

def test_sync_autostart_no_drift(app):
    app.cfg.autostart = True
    with patch("transcrb.app.is_autostart_enabled", return_value=True), \
         patch("transcrb.app.set_autostart") as sa, \
         patch("transcrb.app.save_config") as sc:
        app._sync_autostart_from_registry()
    sa.assert_called_once_with(True)
    sc.assert_not_called()


def test_sync_autostart_registry_wins_when_drift(app):
    app.cfg.autostart = False
    with patch("transcrb.app.is_autostart_enabled", return_value=True), \
         patch("transcrb.app.set_autostart") as sa, \
         patch("transcrb.app.save_config") as sc:
        app._sync_autostart_from_registry()
    assert app.cfg.autostart is True
    sa.assert_called_once_with(True)
    sc.assert_called_once()


def test_sync_autostart_registry_off_overrides_cfg_on(app):
    app.cfg.autostart = True
    with patch("transcrb.app.is_autostart_enabled", return_value=False), \
         patch("transcrb.app.set_autostart") as sa, \
         patch("transcrb.app.save_config"):
        app._sync_autostart_from_registry()
    assert app.cfg.autostart is False
    sa.assert_called_once_with(False)


def test_sync_autostart_save_failure_logged_not_raised(app):
    app.cfg.autostart = False
    with patch("transcrb.app.is_autostart_enabled", return_value=True), \
         patch("transcrb.app.set_autostart"), \
         patch("transcrb.app.save_config", side_effect=OSError("disk full")):
        app._sync_autostart_from_registry()
    assert app.cfg.autostart is True


# ---------------------------------------------------------------------------
# _on_settings_changed
# ---------------------------------------------------------------------------

def test_settings_changed_autostart(app):
    with patch("transcrb.app.set_autostart") as sa:
        app._on_settings_changed({"autostart": True})
    sa.assert_called_once_with(True)


def test_settings_changed_log_level(app):
    with patch("transcrb.app.setup_logging") as sl:
        app._on_settings_changed({"log_level": "DEBUG"})
    sl.assert_called_once_with("DEBUG")


def test_settings_changed_hotkey_combo_rebinds(app):
    old_hotkey = app.hotkey
    with patch("transcrb.app.HotkeyBridge") as MockBridge, \
         patch("transcrb.app.models_dir", return_value=MagicMock()):
        new_hk = MagicMock()
        MockBridge.return_value = new_hk
        app._on_settings_changed({"hotkey.combo": "ctrl+shift+r"})
    old_hotkey.stop.assert_called()


def test_settings_changed_asr_triggers_engine_reload(app):
    with patch.object(app, "_maybe_reload_engine", return_value=False) as mre:
        app._on_settings_changed({"asr.model": "medium"})
    mre.assert_called_once()


def test_settings_changed_refreshes_dashboard(app):
    app._on_settings_changed({})
    app.window.refresh_dashboard.assert_called_once()


def test_settings_changed_no_asr_key_no_reload_engine(app):
    with patch.object(app, "_maybe_reload_engine") as mre:
        app._on_settings_changed({"autostart": False})
    mre.assert_not_called()


def test_settings_changed_pending_download_shows_warn_notify(app):
    with patch.object(app, "_maybe_reload_engine", return_value=True), \
         patch.object(app, "_notify") as notif:
        app._on_settings_changed({"asr.model": "huge"})
    notif.assert_called_once()
    assert notif.call_args[1].get("kind") == "warn"


def test_settings_changed_success_shows_ok_notify(app):
    with patch.object(app, "_maybe_reload_engine", return_value=False), \
         patch.object(app, "_notify") as notif:
        app._on_settings_changed({"asr.model": "medium"})
    notif.assert_called_once()
    assert notif.call_args[1].get("kind", "ok") == "ok"


# ---------------------------------------------------------------------------
# _maybe_reload_engine
# ---------------------------------------------------------------------------

def test_maybe_reload_engine_recording_state_returns_false(app):
    app.state = State.RECORDING
    result = app._maybe_reload_engine({"asr.model": "medium"})
    assert result is False
    app.asr.request_reload.assert_not_called()


def test_maybe_reload_engine_processing_state_returns_false(app):
    app.state = State.PROCESSING
    result = app._maybe_reload_engine({"asr.compute_type": "int8"})
    assert result is False
    app.asr.request_reload.assert_not_called()


def test_maybe_reload_engine_model_not_installed_returns_true(app, tmp_path):
    app.state = State.IDLE
    app.cfg.asr.model = "large-v3"
    with patch("transcrb.app.models_dir", return_value=tmp_path):
        result = app._maybe_reload_engine({"asr.model": "large-v3"})
    assert result is True
    app.asr.request_reload.assert_not_called()


def test_maybe_reload_engine_model_installed_reloads(app, tmp_path):
    app.state = State.IDLE
    app.cfg.asr.model = "tiny"
    model_bin = tmp_path / "tiny" / "model.bin"
    model_bin.parent.mkdir(parents=True)
    model_bin.touch()
    with patch("transcrb.app.models_dir", return_value=tmp_path):
        result = app._maybe_reload_engine({"asr.model": "tiny"})
    assert result is False
    app.asr.request_reload.assert_called_once()


def test_maybe_reload_engine_non_model_change_reloads(app):
    app.state = State.IDLE
    result = app._maybe_reload_engine({"asr.beam_size": 3})
    assert result is False
    app.asr.request_reload.assert_called_once()


# ---------------------------------------------------------------------------
# _notify
# ---------------------------------------------------------------------------

def test_notify_uses_toast_when_window_visible(app):
    app.window.isVisible.return_value = True
    app._notify("hello")
    app.window.show_toast.assert_called_once_with("hello", kind="ok")
    app.tray.notify.assert_not_called()


def test_notify_uses_tray_when_window_hidden_and_notifications_on(app):
    app.window.isVisible.return_value = False
    app.cfg.tray.show_notifications = True
    app._notify("hello")
    app.tray.notify.assert_called_once()
    app.window.show_toast.assert_not_called()


def test_notify_silent_when_window_hidden_and_notifications_off(app):
    app.window.isVisible.return_value = False
    app.cfg.tray.show_notifications = False
    app._notify("hello")
    app.tray.notify.assert_not_called()
    app.window.show_toast.assert_not_called()


def test_notify_empty_text_noop(app):
    app._notify("")
    app.window.show_toast.assert_not_called()
    app.tray.notify.assert_not_called()


def test_notify_warn_kind_passed_to_toast(app):
    app.window.isVisible.return_value = True
    app._notify("warn msg", kind="warn")
    app.window.show_toast.assert_called_once_with("warn msg", kind="warn")


# ---------------------------------------------------------------------------
# _on_copy_request
# ---------------------------------------------------------------------------

def test_on_copy_request_copies_text(app):
    with patch("transcrb.app.pyperclip") as pc:
        app._on_copy_request("hello")
    pc.copy.assert_called_once_with("hello")


def test_on_copy_request_empty_noop(app):
    with patch("transcrb.app.pyperclip") as pc:
        app._on_copy_request("")
    pc.copy.assert_not_called()


def test_on_copy_request_clipboard_error_no_crash(app):
    with patch("transcrb.app.pyperclip") as pc:
        pc.copy.side_effect = Exception("fail")
        app._on_copy_request("text")


def test_on_copy_request_passes_exact_text(app):
    text = "привет мир"
    with patch("transcrb.app.pyperclip") as pc:
        app._on_copy_request(text)
    pc.copy.assert_called_once_with(text)


def test_on_copy_request_unicode(app):
    with patch("transcrb.app.pyperclip") as pc:
        app._on_copy_request("日本語テスト")
    pc.copy.assert_called_once_with("日本語テスト")


# ---------------------------------------------------------------------------
# _on_paste_request
# ---------------------------------------------------------------------------

def test_on_paste_request_copies_and_injects(app):
    with patch("transcrb.app.pyperclip") as pc, \
         patch("transcrb.app.inject") as inj:
        app._on_paste_request("paste me")
    pc.copy.assert_called_once_with("paste me")
    inj.assert_called_once()


def test_on_paste_request_empty_noop(app):
    with patch("transcrb.app.pyperclip") as pc, \
         patch("transcrb.app.inject") as inj:
        app._on_paste_request("")
    pc.copy.assert_not_called()
    inj.assert_not_called()


def test_on_paste_request_inject_restore_false(app):
    with patch("transcrb.app.pyperclip"), \
         patch("transcrb.app.inject") as inj:
        app._on_paste_request("x")
    assert inj.call_args[1]["restore"] is False


def test_on_paste_request_clipboard_error_still_injects(app):
    with patch("transcrb.app.pyperclip") as pc, \
         patch("transcrb.app.inject") as inj:
        pc.copy.side_effect = Exception("clip fail")
        app._on_paste_request("text")
    inj.assert_called_once()


def test_on_paste_request_uses_config_combo(app):
    app.cfg.injection.paste_combo = "ctrl+insert"
    with patch("transcrb.app.pyperclip"), \
         patch("transcrb.app.inject") as inj:
        app._on_paste_request("x")
    assert inj.call_args[1]["paste_combo"] == "ctrl+insert"


# ---------------------------------------------------------------------------
# _rebind_hotkey
# ---------------------------------------------------------------------------

def test_rebind_hotkey_stops_old_hotkey(app):
    app.state = State.IDLE
    old_hotkey = app.hotkey
    with patch("transcrb.app.HotkeyBridge") as MockBridge:
        MockBridge.return_value = MagicMock()
        app._rebind_hotkey()
    old_hotkey.stop.assert_called_once()


def test_rebind_hotkey_creates_new_bridge(app):
    app.state = State.IDLE
    with patch("transcrb.app.HotkeyBridge") as MockBridge:
        new_hk = MagicMock()
        MockBridge.return_value = new_hk
        app._rebind_hotkey()
    MockBridge.assert_called_once_with(app.cfg.hotkey.combo, app.cfg.hotkey.debounce_ms)


def test_rebind_hotkey_starts_new_bridge(app):
    app.state = State.IDLE
    with patch("transcrb.app.HotkeyBridge") as MockBridge:
        new_hk = MagicMock()
        MockBridge.return_value = new_hk
        app._rebind_hotkey()
    new_hk.start.assert_called_once()


def test_rebind_hotkey_during_recording_stops_audio(app):
    app.state = State.RECORDING
    app.cfg.overlay.enabled = False
    with patch("transcrb.app.HotkeyBridge") as MockBridge:
        MockBridge.return_value = MagicMock()
        app._rebind_hotkey()
    app.audio.stop.assert_called_once_with(emit_tail=False)
    assert app.state == State.IDLE


def test_rebind_hotkey_during_recording_hides_overlay(app):
    app.state = State.RECORDING
    app.cfg.overlay.enabled = True
    with patch("transcrb.app.HotkeyBridge") as MockBridge:
        MockBridge.return_value = MagicMock()
        app._rebind_hotkey()
    app.overlay.hide_fade.assert_called_once()


def test_rebind_hotkey_updates_tray_tooltip(app):
    app.state = State.IDLE
    with patch("transcrb.app.HotkeyBridge") as MockBridge:
        MockBridge.return_value = MagicMock()
        app._rebind_hotkey()
    app.tray.set_tooltip.assert_called_once()


# ---------------------------------------------------------------------------
# _on_quit
# ---------------------------------------------------------------------------

def test_on_quit_stops_hotkey(app):
    app.audio.is_running.return_value = False
    with patch("transcrb.app.QApplication") as qa:
        qa.instance.return_value = MagicMock()
        app._on_quit()
    app.hotkey.stop.assert_called_once()


def test_on_quit_stops_asr(app):
    app.audio.is_running.return_value = False
    with patch("transcrb.app.QApplication") as qa:
        qa.instance.return_value = MagicMock()
        app._on_quit()
    app.asr.stop.assert_called_once()


def test_on_quit_stops_audio_when_running(app):
    app.audio.is_running.return_value = True
    with patch("transcrb.app.QApplication") as qa:
        qa.instance.return_value = MagicMock()
        app._on_quit()
    app.audio.stop.assert_called_once_with(emit_tail=False)


def test_on_quit_no_audio_stop_when_not_running(app):
    app.audio.is_running.return_value = False
    with patch("transcrb.app.QApplication") as qa:
        qa.instance.return_value = MagicMock()
        app._on_quit()
    app.audio.stop.assert_not_called()


def test_on_quit_calls_qapp_quit(app):
    app.audio.is_running.return_value = False
    with patch("transcrb.app.QApplication") as qa:
        qapp_mock = MagicMock()
        qa.instance.return_value = qapp_mock
        app._on_quit()
    qapp_mock.quit.assert_called_once()


def test_on_quit_stops_timers(app):
    app.audio.is_running.return_value = False
    with patch("transcrb.app.QApplication") as qa:
        qa.instance.return_value = MagicMock()
        app._on_quit()
    app._release_timer.stop.assert_called()
    app._max_duration_timer.stop.assert_called()
