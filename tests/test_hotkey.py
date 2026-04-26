from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(name: str, event_type: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, event_type=event_type)


def _make_bridge(combo: str, debounce_ms: int = 150):
    with patch("transcrb.hotkey.keyboard"):
        from transcrb.hotkey import HotkeyBridge
        return HotkeyBridge(combo=combo, debounce_ms=debounce_ms)


# ---------------------------------------------------------------------------
# __init__ parsing
# ---------------------------------------------------------------------------

class TestInit:
    def test_single_key_detected(self):
        b = _make_bridge("right ctrl")
        assert b._single_key == "right ctrl"

    def test_multi_key_single_key_is_none(self):
        b = _make_bridge("ctrl+shift")
        assert b._single_key is None

    def test_combo_keys_parsed_correctly(self):
        b = _make_bridge("ctrl+shift+a")
        assert b._combo_keys == {"ctrl", "shift", "a"}

    def test_combo_normalized_to_lowercase(self):
        b = _make_bridge("Right Ctrl")
        assert b._combo == "right ctrl"
        assert b._single_key == "right ctrl"

    def test_debounce_converted_to_seconds(self):
        b = _make_bridge("right ctrl", debounce_ms=200)
        assert b._debounce_s == pytest.approx(0.2)

    def test_initial_state_not_down(self):
        b = _make_bridge("right ctrl")
        assert b._down is False

    def test_hook_starts_as_none(self):
        b = _make_bridge("right ctrl")
        assert b._hook is None


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------

class TestStartStop:
    def test_start_calls_hook(self):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("right ctrl")
            b.start()
            kb.hook.assert_called_once_with(b._on_event)

    def test_start_idempotent(self):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("right ctrl")
            b.start()
            b.start()
            assert kb.hook.call_count == 1

    def test_stop_calls_unhook(self):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("right ctrl")
            b.start()
            hook_obj = kb.hook.return_value
            b.stop()
            kb.unhook.assert_called_once_with(hook_obj)

    def test_stop_clears_hook_reference(self):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("right ctrl")
            b.start()
            b.stop()
            assert b._hook is None

    def test_stop_idempotent(self):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("right ctrl")
            b.start()
            b.stop()
            b.stop()
            assert kb.unhook.call_count == 1

    def test_stop_swallows_unhook_exception(self):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            kb.unhook.side_effect = RuntimeError("boom")
            b = HotkeyBridge("right ctrl")
            b.start()
            b.stop()
            assert b._hook is None

    def test_stop_before_start_noop(self):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("right ctrl")
            b.stop()
            kb.unhook.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_single
# ---------------------------------------------------------------------------

class TestHandleSingle:
    def _bridge(self, combo="right ctrl", debounce_ms=0):
        return _make_bridge(combo, debounce_ms=debounce_ms)

    def test_right_ctrl_down_emits_pressed(self, qtbot):
        b = self._bridge()
        with qtbot.waitSignal(b.pressed, timeout=500):
            b._handle_single(_make_event("right ctrl", "down"))

    def test_right_ctrl_up_emits_released(self, qtbot):
        b = self._bridge()
        b._handle_single(_make_event("right ctrl", "down"))
        with qtbot.waitSignal(b.released, timeout=500):
            b._handle_single(_make_event("right ctrl", "up"))

    def test_left_ctrl_ignored(self, qtbot):
        b = self._bridge()
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(_make_event("left ctrl", "down"))

    def test_plain_ctrl_ignored(self, qtbot):
        b = self._bridge()
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(_make_event("ctrl", "down"))

    def test_down_while_already_down_no_double_emit(self, qtbot):
        b = self._bridge()
        b._handle_single(_make_event("right ctrl", "down"))
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(_make_event("right ctrl", "down"))

    def test_up_without_prior_down_no_emit(self, qtbot):
        b = self._bridge()
        with qtbot.assertNotEmitted(b.released):
            b._handle_single(_make_event("right ctrl", "up"))

    def test_debounce_blocks_rapid_repress(self, qtbot):
        b = _make_bridge("right ctrl", debounce_ms=500)
        b._handle_single(_make_event("right ctrl", "down"))
        b._handle_single(_make_event("right ctrl", "up"))
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(_make_event("right ctrl", "down"))

    def test_debounce_allows_press_after_window(self, qtbot, monkeypatch):
        b = _make_bridge("right ctrl", debounce_ms=100)
        b._handle_single(_make_event("right ctrl", "down"))
        b._handle_single(_make_event("right ctrl", "up"))
        monkeypatch.setattr(
            "transcrb.hotkey.time.monotonic",
            lambda: b._last_release + 0.2,
        )
        with qtbot.waitSignal(b.pressed, timeout=500):
            b._handle_single(_make_event("right ctrl", "down"))

    def test_event_name_none_is_ignored(self, qtbot):
        b = self._bridge()
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(SimpleNamespace(name=None, event_type="down"))

    def test_event_missing_name_attr_is_ignored(self, qtbot):
        b = self._bridge()
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(SimpleNamespace(event_type="down"))

    def test_unknown_event_type_no_emit(self, qtbot):
        b = self._bridge()
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(_make_event("right ctrl", "repeat"))

    def test_state_resets_after_up(self, qtbot):
        b = self._bridge()
        b._handle_single(_make_event("right ctrl", "down"))
        b._handle_single(_make_event("right ctrl", "up"))
        assert b._down is False

    def test_down_sets_down_flag(self, qtbot):
        b = self._bridge()
        b._handle_single(_make_event("right ctrl", "down"))
        assert b._down is True

    @pytest.mark.parametrize("name", ["a", "space", "f5", "shift", ""])
    def test_unrelated_keys_ignored(self, qtbot, name):
        b = self._bridge()
        with qtbot.assertNotEmitted(b.pressed):
            b._handle_single(_make_event(name, "down"))

    def test_handle_single_completes_despite_bad_slot(self, qtbot):
        b = _make_bridge("right ctrl", debounce_ms=0)
        results = []
        b.pressed.connect(lambda: results.append(1))
        b._handle_single(_make_event("right ctrl", "down"))
        assert b._down is True
        assert results == [1]


# ---------------------------------------------------------------------------
# _handle_combo
# ---------------------------------------------------------------------------

class TestHandleCombo:
    def _bridge_with_mock_kb(self, combo="ctrl+shift", debounce_ms=0):
        with patch("transcrb.hotkey.keyboard") as kb_mock:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge(combo=combo, debounce_ms=debounce_ms)
        b._kb_mock = kb_mock
        return b, kb_mock

    def _set_pressed(self, kb_mock, pressed_keys: set[str]):
        kb_mock.is_pressed.side_effect = lambda k: k in pressed_keys

    def test_all_keys_down_emits_pressed(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            with qtbot.waitSignal(b.pressed, timeout=500):
                b._handle_combo(_make_event("shift", "down"))

    def test_partial_keys_no_emit(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k == "ctrl"
            with qtbot.assertNotEmitted(b.pressed):
                b._handle_combo(_make_event("ctrl", "down"))

    def test_release_one_key_emits_released(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            b._handle_combo(_make_event("shift", "down"))
            kb.is_pressed.side_effect = lambda k: k == "ctrl"
            with qtbot.waitSignal(b.released, timeout=500):
                b._handle_combo(_make_event("shift", "up"))

    def test_no_double_pressed_while_held(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            b._handle_combo(_make_event("shift", "down"))
            with qtbot.assertNotEmitted(b.pressed):
                b._handle_combo(_make_event("shift", "down"))

    def test_debounce_blocks_rapid_repress(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=500)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            b._handle_combo(_make_event("shift", "down"))
            kb.is_pressed.side_effect = lambda k: False
            b._handle_combo(_make_event("shift", "up"))
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            with qtbot.assertNotEmitted(b.pressed):
                b._handle_combo(_make_event("shift", "down"))

    def test_debounce_allows_press_after_window(self, qtbot, monkeypatch):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=100)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            b._handle_combo(_make_event("shift", "down"))
            kb.is_pressed.side_effect = lambda k: False
            b._handle_combo(_make_event("shift", "up"))
            monkeypatch.setattr(
                "transcrb.hotkey.time.monotonic",
                lambda: b._last_release + 0.2,
            )
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            with qtbot.waitSignal(b.pressed, timeout=500):
                b._handle_combo(_make_event("shift", "down"))

    def test_three_key_combo_all_required(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+alt+x", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "alt"}
            with qtbot.assertNotEmitted(b.pressed):
                b._handle_combo(_make_event("alt", "down"))

    def test_three_key_combo_all_down_emits(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+alt+x", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "alt", "x"}
            with qtbot.waitSignal(b.pressed, timeout=500):
                b._handle_combo(_make_event("x", "down"))

    def test_no_released_without_prior_pressed(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: False
            with qtbot.assertNotEmitted(b.released):
                b._handle_combo(_make_event("shift", "up"))

    def test_combo_down_sets_down_flag(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            b._handle_combo(_make_event("shift", "down"))
            assert b._down is True

    def test_combo_released_resets_down_flag(self, qtbot):
        with patch("transcrb.hotkey.keyboard") as kb:
            from transcrb.hotkey import HotkeyBridge
            b = HotkeyBridge("ctrl+shift", debounce_ms=0)
            kb.is_pressed.side_effect = lambda k: k in {"ctrl", "shift"}
            b._handle_combo(_make_event("shift", "down"))
            kb.is_pressed.side_effect = lambda k: False
            b._handle_combo(_make_event("shift", "up"))
            assert b._down is False


# ---------------------------------------------------------------------------
# _on_event routing
# ---------------------------------------------------------------------------

class TestOnEventRouting:
    def test_single_key_routes_to_handle_single(self, monkeypatch):
        b = _make_bridge("right ctrl")
        called = []
        monkeypatch.setattr(b, "_handle_single", lambda e: called.append(e))
        ev = _make_event("right ctrl", "down")
        b._on_event(ev)
        assert called == [ev]

    def test_combo_routes_to_handle_combo(self, monkeypatch):
        b = _make_bridge("ctrl+shift")
        called = []
        monkeypatch.setattr(b, "_handle_combo", lambda e: called.append(e))
        ev = _make_event("ctrl", "down")
        b._on_event(ev)
        assert called == [ev]

    def test_single_key_does_not_call_handle_combo(self, monkeypatch):
        b = _make_bridge("right ctrl")
        monkeypatch.setattr(b, "_handle_combo", lambda e: (_ for _ in ()).throw(AssertionError("should not call")))
        b._on_event(_make_event("right ctrl", "down"))

    def test_combo_does_not_call_handle_single(self, monkeypatch):
        b = _make_bridge("ctrl+shift")
        monkeypatch.setattr(b, "_handle_single", lambda e: (_ for _ in ()).throw(AssertionError("should not call")))
        with patch("transcrb.hotkey.keyboard") as kb:
            kb.is_pressed.return_value = False
            b._on_event(_make_event("ctrl", "down"))
