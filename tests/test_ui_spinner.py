import sys
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from transcrb.ui.spinner import Spinner


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# __init__ — defaults
# ---------------------------------------------------------------------------

def test_init_default_angle(qapp):
    s = Spinner()
    assert s._angle == 0.0


def test_init_default_speed(qapp):
    s = Spinner()
    assert s._speed == 6.0


def test_init_default_arc(qapp):
    s = Spinner()
    assert s._arc == 110.0


def test_init_default_accent_color(qapp):
    s = Spinner()
    assert s._accent == QColor("#31D27A")


def test_init_timer_not_active(qapp):
    s = Spinner()
    assert not s._timer.isActive()


def test_init_minimum_size(qapp):
    s = Spinner()
    assert s.minimumSize().width() == 28
    assert s.minimumSize().height() == 28


def test_init_transparent_for_mouse_events(qapp):
    s = Spinner()
    assert s.testAttribute(Qt.WA_TransparentForMouseEvents)


# ---------------------------------------------------------------------------
# __init__ — custom kwargs
# ---------------------------------------------------------------------------

def test_init_custom_accent(qapp):
    s = Spinner(accent="#FF0000")
    assert s._accent == QColor("#FF0000")


def test_init_custom_rotation_speed(qapp):
    s = Spinner(rotation_speed_deg=12.0)
    assert s._speed == 12.0


def test_init_custom_arc_span(qapp):
    s = Spinner(arc_span_deg=180.0)
    assert s._arc == 180.0


def test_init_fps60_interval(qapp):
    s = Spinner(fps=60)
    assert s._timer.interval() == 16  # int(1000/60) = 16


def test_init_fps30_interval(qapp):
    s = Spinner(fps=30)
    assert s._timer.interval() == 33  # int(1000/30) = 33


def test_init_fps1000_clamped_to_1(qapp):
    s = Spinner(fps=1000)
    assert s._timer.interval() == 1  # int(1000/1000) = 1, max(1, 1) = 1


def test_init_fps2000_clamped_to_1(qapp):
    s = Spinner(fps=2000)
    assert s._timer.interval() == 1  # int(1000/2000) = 0, max(1, 0) = 1


def test_init_fps0_raises(qapp):
    with pytest.raises(ZeroDivisionError):
        Spinner(fps=0)


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

def test_start_activates_timer(qapp):
    s = Spinner()
    s.start()
    assert s._timer.isActive()
    s.stop()


def test_start_idempotent(qapp):
    s = Spinner()
    s.start()
    s.start()
    assert s._timer.isActive()
    s.stop()


def test_start_preserves_interval(qapp):
    s = Spinner(fps=30)
    interval_before = s._timer.interval()
    s.start()
    assert s._timer.interval() == interval_before
    s.stop()


def test_start_does_not_reset_angle(qapp):
    s = Spinner()
    s._angle = 45.0
    s.start()
    assert s._angle == 45.0
    s.stop()


def test_start_when_already_running_does_not_restart(qapp):
    s = Spinner()
    s.start()
    timer_id_before = s._timer.timerId()
    s.start()
    assert s._timer.timerId() == timer_id_before
    s.stop()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

def test_stop_deactivates_timer(qapp):
    s = Spinner()
    s.start()
    s.stop()
    assert not s._timer.isActive()


def test_stop_when_not_running_is_safe(qapp):
    s = Spinner()
    s.stop()
    assert not s._timer.isActive()


def test_stop_does_not_change_angle(qapp):
    s = Spinner()
    s._angle = 90.0
    s.stop()
    assert s._angle == 90.0


def test_stop_allows_restart(qapp):
    s = Spinner()
    s.start()
    s.stop()
    s.start()
    assert s._timer.isActive()
    s.stop()


def test_stop_idempotent(qapp):
    s = Spinner()
    s.stop()
    s.stop()
    assert not s._timer.isActive()


# ---------------------------------------------------------------------------
# _tick
# ---------------------------------------------------------------------------

def test_tick_increments_angle_by_speed(qapp):
    s = Spinner(rotation_speed_deg=6.0)
    s._tick()
    assert s._angle == pytest.approx(6.0)


def test_tick_accumulates_across_calls(qapp):
    s = Spinner(rotation_speed_deg=6.0)
    s._tick()
    s._tick()
    assert s._angle == pytest.approx(12.0)


def test_tick_wraps_at_360(qapp):
    s = Spinner(rotation_speed_deg=6.0)
    s._angle = 358.0
    s._tick()
    assert s._angle == pytest.approx(4.0)


def test_tick_exact_360_wraps_to_0(qapp):
    s = Spinner(rotation_speed_deg=6.0)
    s._angle = 354.0
    s._tick()
    assert s._angle == pytest.approx(0.0)


def test_tick_calls_update(qapp):
    s = Spinner()
    with patch.object(s, "update") as mock_update:
        s._tick()
        mock_update.assert_called_once()


def test_tick_uses_custom_speed(qapp):
    s = Spinner(rotation_speed_deg=1.5)
    s._tick()
    assert s._angle == pytest.approx(1.5)


@pytest.mark.parametrize("start,speed,expected", [
    (0.0, 6.0, 6.0),
    (180.0, 6.0, 186.0),
    (356.0, 6.0, 2.0),
    (0.0, 90.0, 90.0),
    (270.0, 100.0, 10.0),
])
def test_tick_angle_transitions(qapp, start, speed, expected):
    s = Spinner(rotation_speed_deg=speed)
    s._angle = start
    s._tick()
    assert s._angle == pytest.approx(expected)


# ---------------------------------------------------------------------------
# paintEvent — via grab() (no direct paint device needed)
# ---------------------------------------------------------------------------

def test_paint_event_produces_pixmap_at_default_size(qapp):
    s = Spinner()
    s.resize(64, 64)
    s.show()
    px = s.grab()
    assert not px.isNull()
    assert px.width() == 64
    assert px.height() == 64
    s.hide()


def test_paint_event_after_resize_100(qapp):
    s = Spinner()
    s.resize(100, 100)
    s.show()
    px = s.grab()
    assert not px.isNull()
    assert px.width() == 100
    s.hide()


def test_paint_event_after_tick(qapp):
    s = Spinner()
    s.resize(64, 64)
    s._tick()
    s.show()
    px = s.grab()
    assert not px.isNull()
    s.hide()


def test_paint_event_at_minimum_size(qapp):
    s = Spinner()
    s.resize(28, 28)
    s.show()
    px = s.grab()
    assert not px.isNull()
    assert px.width() == 28
    s.hide()


def test_paint_event_with_custom_accent(qapp):
    s = Spinner(accent="#0000FF")
    s.resize(64, 64)
    s.show()
    px = s.grab()
    assert not px.isNull()
    s.hide()


def test_paint_event_non_square_widget(qapp):
    s = Spinner()
    s.resize(120, 60)
    s.show()
    px = s.grab()
    assert not px.isNull()
    assert px.width() == 120
    assert px.height() == 60
    s.hide()
