from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication

from transcrb.config import OverlayCfg
from transcrb.ui.overlay import PillOverlay


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _cfg(**overrides) -> OverlayCfg:
    return OverlayCfg(**overrides)


def _mock_screen(x=0, y=0, w=1920, h=1080, avail_bottom_gap=40):
    screen = MagicMock()
    avail = QRect(x, y, w, h - avail_bottom_gap)
    screen.availableGeometry.return_value = avail
    return screen


@pytest.fixture
def overlay(qtbot):
    cfg = _cfg()
    with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
        w = PillOverlay(cfg)
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# __init__ / initial state
# ---------------------------------------------------------------------------

class TestInit:
    def test_initial_mode_is_recording(self, overlay):
        assert overlay._mode == PillOverlay._MODE_RECORDING

    def test_initial_opacity_is_zero(self, overlay):
        assert overlay.windowOpacity() == pytest.approx(0.0)

    def test_paste_callback_is_none(self, overlay):
        assert overlay._paste_callback is None

    def test_last_hold_ms_default(self, overlay):
        assert overlay._last_hold_ms == 5000

    def test_auto_hide_timer_single_shot(self, overlay):
        assert overlay._auto_hide_timer.isSingleShot()

    def test_clickthrough_set_on_init(self, overlay):
        assert overlay.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_stack_shows_recording_widget_on_init(self, overlay):
        assert overlay._stack.currentWidget() is overlay._recording_widget

    def test_cfg_stored(self, overlay):
        assert isinstance(overlay._cfg, OverlayCfg)

    def test_fixed_size_matches_cfg(self, overlay):
        cfg = _cfg(width=300, height=90)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        assert w.width() == 300
        assert w.height() == 90

    def test_background_color_from_cfg(self, overlay):
        assert overlay._bg.red() == 12
        assert overlay._bg.green() == 12
        assert overlay._bg.blue() == 14
        assert overlay._bg.alpha() == 230


# ---------------------------------------------------------------------------
# show_fade
# ---------------------------------------------------------------------------

class TestShowFade:
    def test_mode_set_to_recording(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert w._mode == PillOverlay._MODE_RECORDING

    def test_clickthrough_enabled_in_recording(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_recording_widget_is_current(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
            w.show_fade()
        assert w._stack.currentWidget() is w._recording_widget

    def test_opacity_animation_targets_1(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert w._opacity_anim.endValue() == pytest.approx(1.0)

    def test_auto_hide_timer_stopped_on_show_fade(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._auto_hide_timer.start(5000)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert not w._auto_hide_timer.isActive()

    def test_icon_set_active_on_show_fade(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._icon.set_active(False)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert w._icon._active is True

    def test_spinner_stopped_on_show_fade(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._spinner.start()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert not w._spinner._timer.isActive()

    def test_show_fade_from_result_switches_back(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
            assert w._mode == PillOverlay._MODE_RESULT
            w.show_fade()
        assert w._mode == PillOverlay._MODE_RECORDING

    def test_show_fade_idempotent_when_already_recording(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
            w.show_fade()
        assert w._mode == PillOverlay._MODE_RECORDING


# ---------------------------------------------------------------------------
# show_busy
# ---------------------------------------------------------------------------

class TestShowBusy:
    def test_mode_set_to_busy(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert w._mode == PillOverlay._MODE_BUSY

    def test_busy_widget_is_current(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert w._stack.currentWidget() is w._busy_widget

    def test_clickthrough_enabled_in_busy(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_spinner_started_on_show_busy(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert w._spinner._timer.isActive()

    def test_opacity_animation_targets_1_in_busy(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert w._opacity_anim.endValue() == pytest.approx(1.0)

    def test_auto_hide_timer_stopped_on_show_busy(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._auto_hide_timer.start(5000)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert not w._auto_hide_timer.isActive()

    def test_show_busy_idempotent_mode_stays_busy(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
            w.show_busy()
        assert w._mode == PillOverlay._MODE_BUSY


# ---------------------------------------------------------------------------
# show_result
# ---------------------------------------------------------------------------

class TestShowResult:
    def test_mode_set_to_result(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        cb = MagicMock()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(cb, hold_ms=99999)
        assert w._mode == PillOverlay._MODE_RESULT

    def test_result_widget_is_current(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert w._stack.currentWidget() is w._result_widget

    def test_paste_callback_stored(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        cb = MagicMock()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(cb, hold_ms=99999)
        assert w._paste_callback is cb

    def test_clickthrough_disabled_in_result(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert not w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_hold_ms_clamped_to_minimum_1500(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=100)
        assert w._last_hold_ms == 1500

    def test_hold_ms_accepted_above_minimum(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=3000)
        assert w._last_hold_ms == 3000

    def test_hold_ms_at_boundary_1500_accepted(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=1500)
        assert w._last_hold_ms == 1500

    def test_auto_hide_timer_started_with_hold_ms(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=4000)
        assert w._auto_hide_timer.isActive()

    def test_opacity_animation_targets_1_in_result(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert w._opacity_anim.endValue() == pytest.approx(1.0)

    def test_spinner_stopped_on_show_result(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._spinner.start()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert not w._spinner._timer.isActive()

    def test_hold_ms_zero_clamped_to_1500(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=0)
        assert w._last_hold_ms == 1500

    def test_hold_ms_negative_clamped_to_1500(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=-500)
        assert w._last_hold_ms == 1500


# ---------------------------------------------------------------------------
# hide_fade
# ---------------------------------------------------------------------------

class TestHideFade:
    def test_auto_hide_timer_stopped(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._auto_hide_timer.start(5000)
        w.hide_fade()
        assert not w._auto_hide_timer.isActive()

    def test_opacity_animation_targets_0(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w.hide_fade()
        assert w._opacity_anim.endValue() == pytest.approx(0.0)

    def test_spinner_stopped_on_hide_fade(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._spinner.start()
        w.hide_fade()
        assert not w._spinner._timer.isActive()

    def test_icon_set_inactive_on_hide_fade(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._icon.set_active(True)
        w.hide_fade()
        assert w._icon._active is False

    def test_opacity_animation_running_after_hide_fade(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w.hide_fade()
        assert w._opacity_anim.state().name in ("Running", "Stopped")

    def test_hide_fade_callable_twice_without_error(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w.hide_fade()
        w.hide_fade()
        assert w._opacity_anim.endValue() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _post_hide
# ---------------------------------------------------------------------------

class TestPostHide:
    def test_hides_widget_when_opacity_is_zero(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
        w.setWindowOpacity(0.0)
        w._post_hide()
        assert not w.isVisible()

    def test_does_not_hide_when_opacity_above_threshold(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
        w.setWindowOpacity(0.5)
        w._post_hide()
        assert w.isVisible()

    def test_resets_to_recording_mode_when_hidden(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._mode = PillOverlay._MODE_RESULT
        w.setWindowOpacity(0.0)
        w._post_hide()
        assert w._mode == PillOverlay._MODE_RECORDING

    def test_recording_widget_restored_after_post_hide(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        w.setWindowOpacity(0.0)
        w._post_hide()
        assert w._stack.currentWidget() is w._recording_widget

    def test_clickthrough_restored_after_post_hide_from_result(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert not w.testAttribute(Qt.WA_TransparentForMouseEvents)
        w.setWindowOpacity(0.0)
        w._post_hide()
        assert w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_threshold_at_0_04_hides(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
        w.setWindowOpacity(0.04)
        w._post_hide()
        assert not w.isVisible()

    def test_above_threshold_does_not_hide(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
        w.setWindowOpacity(0.1)
        w._post_hide()
        assert w.isVisible()


# ---------------------------------------------------------------------------
# _on_paste_clicked
# ---------------------------------------------------------------------------

class TestOnPasteClicked:
    def test_callback_scheduled_on_click(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        called = []
        cb = lambda: called.append(1)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(cb, hold_ms=99999)
        w._on_paste_clicked()
        qtbot.wait(150)
        assert called == [1]

    def test_timer_stopped_on_click(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert w._auto_hide_timer.isActive()
        w._on_paste_clicked()
        assert not w._auto_hide_timer.isActive()

    def test_no_crash_when_callback_is_none(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._paste_callback = None
        w._on_paste_clicked()

    def test_hide_fade_triggered_on_click(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        hide_called = []
        original = w.hide_fade
        w.hide_fade = lambda: hide_called.append(1) or original()
        w._on_paste_clicked()
        assert hide_called == [1]

    def test_callback_called_once(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        cb = MagicMock()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(cb, hold_ms=99999)
        w._on_paste_clicked()
        qtbot.wait(150)
        assert cb.call_count == 1

    def test_previous_callback_replaced_by_new_show_result(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        cb1 = MagicMock()
        cb2 = MagicMock()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(cb1, hold_ms=99999)
            w.show_result(cb2, hold_ms=99999)
        w._on_paste_clicked()
        qtbot.wait(150)
        assert cb2.call_count == 1
        assert cb1.call_count == 0


# ---------------------------------------------------------------------------
# eventFilter — hover stops/restarts timer
# ---------------------------------------------------------------------------

class TestEventFilter:
    def _make_event(self, event_type: QEvent.Type) -> QEvent:
        return QEvent(event_type)

    def test_enter_stops_timer(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert w._auto_hide_timer.isActive()
        w.eventFilter(w._result_btn, self._make_event(QEvent.Enter))
        assert not w._auto_hide_timer.isActive()

    def test_leave_restarts_timer(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        w.eventFilter(w._result_btn, self._make_event(QEvent.Enter))
        assert not w._auto_hide_timer.isActive()
        w.eventFilter(w._result_btn, self._make_event(QEvent.Leave))
        assert w._auto_hide_timer.isActive()

    def test_enter_ignored_outside_result_mode(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._auto_hide_timer.start(5000)
        assert w._mode == PillOverlay._MODE_RECORDING
        w.eventFilter(w._result_btn, self._make_event(QEvent.Enter))
        assert w._auto_hide_timer.isActive()

    def test_event_on_unrelated_obj_ignored(self, qtbot):
        from PySide6.QtWidgets import QWidget as _QWidget
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        other = _QWidget()
        qtbot.addWidget(other)
        w.eventFilter(other, self._make_event(QEvent.Enter))
        assert w._auto_hide_timer.isActive()

    def test_leave_uses_last_hold_ms(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=3000)
        w.eventFilter(w._result_btn, self._make_event(QEvent.Enter))
        w.eventFilter(w._result_btn, self._make_event(QEvent.Leave))
        assert w._auto_hide_timer.isActive()
        assert w._last_hold_ms == 3000


# ---------------------------------------------------------------------------
# update_level
# ---------------------------------------------------------------------------

class TestUpdateLevel:
    def test_no_effect_outside_recording_mode(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        original_active = w._bars._active
        w.update_level(0.5, None)
        assert w._bars._active == original_active

    def test_updates_bars_in_recording_mode_with_none_bands(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._bars.set_idle()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        w.update_level(0.5, None)
        assert w._bars._active is True

    def test_rms_scaled_8x_when_bands_none(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        w.update_level(0.1, None)
        expected = min(1.0, max(0.1, 0.1 * 8.0))
        assert np.allclose(w._bars._targets, expected, atol=0.01)

    def test_rms_clipped_to_1_when_bands_none(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        w.update_level(1.0, None)
        assert np.allclose(w._bars._targets, 1.0, atol=0.01)

    def test_updates_bars_with_provided_bands(self, qtbot):
        cfg = _cfg(bars=5)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        bands = np.array([0.2, 0.4, 0.6, 0.8, 0.9], dtype=np.float32)
        w.update_level(0.0, bands)
        assert w._bars._active is True

    def test_busy_mode_ignored_like_result(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        before = w._bars._active
        w.update_level(0.8, None)
        assert w._bars._active == before


# ---------------------------------------------------------------------------
# _reposition — positioning calculations
# ---------------------------------------------------------------------------

class TestReposition:
    @pytest.mark.parametrize("sw,sh,margin,cw,ch", [
        (1920, 1080, 24, 252, 81),
        (2560, 1440, 40, 300, 90),
        (800, 600, 10, 200, 60),
    ])
    def test_centered_horizontally(self, qtbot, sw, sh, margin, cw, ch):
        cfg = _cfg(width=cw, height=ch, bottom_margin_px=margin)
        screen = _mock_screen(x=0, y=0, w=sw, h=sh, avail_bottom_gap=40)
        avail = screen.availableGeometry.return_value
        with patch.object(QGuiApplication, "primaryScreen", return_value=screen):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        expected_x = avail.x() + (avail.width() - cw) // 2
        assert w.x() == expected_x

    @pytest.mark.parametrize("sw,sh,margin,cw,ch", [
        (1920, 1080, 24, 252, 81),
        (2560, 1440, 40, 300, 90),
        (800, 600, 10, 200, 60),
    ])
    def test_positioned_near_bottom(self, qtbot, sw, sh, margin, cw, ch):
        cfg = _cfg(width=cw, height=ch, bottom_margin_px=margin)
        screen = _mock_screen(x=0, y=0, w=sw, h=sh, avail_bottom_gap=40)
        avail = screen.availableGeometry.return_value
        with patch.object(QGuiApplication, "primaryScreen", return_value=screen):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        expected_y = avail.y() + avail.height() - ch - margin
        assert w.y() == expected_y

    def test_no_crash_when_screen_is_none(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=None):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=None):
            w._reposition()

    def test_offset_screen_repositions_correctly(self, qtbot):
        cfg = _cfg(width=252, height=81, bottom_margin_px=24)
        screen = _mock_screen(x=1920, y=200, w=1920, h=1080, avail_bottom_gap=40)
        avail = screen.availableGeometry.return_value
        with patch.object(QGuiApplication, "primaryScreen", return_value=screen):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        expected_x = avail.x() + (avail.width() - 252) // 2
        assert w.x() == expected_x

    def test_reposition_called_on_show_fade(self, qtbot):
        cfg = _cfg()
        screen = _mock_screen()
        with patch.object(QGuiApplication, "primaryScreen", return_value=screen):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        reposition_calls = []
        original = w._reposition
        w._reposition = lambda: reposition_calls.append(1) or original()
        with patch.object(QGuiApplication, "primaryScreen", return_value=screen):
            w.show_fade()
        assert reposition_calls


# ---------------------------------------------------------------------------
# clickthrough toggle across state transitions
# ---------------------------------------------------------------------------

class TestClickthroughTransitions:
    def test_recording_has_clickthrough(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_result_has_no_clickthrough(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        assert not w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_busy_has_clickthrough(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_recording_to_result_to_recording_restores_clickthrough(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
            w.show_result(lambda: None, hold_ms=99999)
            w.show_fade()
        assert w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_busy_to_result_removes_clickthrough(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
            w.show_result(lambda: None, hold_ms=99999)
        assert not w.testAttribute(Qt.WA_TransparentForMouseEvents)

    def test_result_to_post_hide_restores_clickthrough(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=99999)
        w.setWindowOpacity(0.0)
        w._post_hide()
        assert w.testAttribute(Qt.WA_TransparentForMouseEvents)


# ---------------------------------------------------------------------------
# auto-hide timer timeout → hide_fade
# ---------------------------------------------------------------------------

class TestAutoHideTimeout:
    def test_timer_fires_hide_fade_after_timeout(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        hide_called = []
        w.hide_fade = lambda: hide_called.append(1)
        w._auto_hide_timer.timeout.connect(w.hide_fade)
        w._auto_hide_timer.start(50)
        qtbot.wait(200)
        assert hide_called

    def test_result_show_starts_timer(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_result(lambda: None, hold_ms=5000)
        assert w._auto_hide_timer.isActive()

    def test_hide_fade_stops_timer(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._auto_hide_timer.start(5000)
        w.hide_fade()
        assert not w._auto_hide_timer.isActive()

    def test_show_fade_stops_existing_timer(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._auto_hide_timer.start(5000)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_fade()
        assert not w._auto_hide_timer.isActive()

    def test_show_busy_stops_existing_timer(self, qtbot):
        cfg = _cfg()
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w = PillOverlay(cfg)
        qtbot.addWidget(w)
        w._auto_hide_timer.start(5000)
        with patch.object(QGuiApplication, "primaryScreen", return_value=_mock_screen()):
            w.show_busy()
        assert not w._auto_hide_timer.isActive()
