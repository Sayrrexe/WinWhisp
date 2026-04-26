import sys

import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    return app


@pytest.fixture
def widget(qapp):
    from transcrb.ui.mic_icon import MicRadarIcon

    w = MicRadarIcon()
    w._timer.stop()
    yield w
    w._timer.stop()
    w.close()


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_init_default_active(widget):
    assert widget._active is True


def test_init_default_phase(widget):
    assert widget._phase == 0.0


def test_init_minimum_size(widget):
    assert widget.minimumSize() == QSize(44, 44)


def test_init_transparent_mouse_attribute(widget):
    assert widget.testAttribute(Qt.WA_TransparentForMouseEvents)


def test_init_accent_color_stored(qapp):
    from transcrb.ui.mic_icon import MicRadarIcon

    w = MicRadarIcon(accent="#FF0000")
    w._timer.stop()
    assert w._accent == QColor("#FF0000")
    w.close()


def test_init_default_accent_color(widget):
    assert widget._accent == QColor("#31D27A")


@pytest.mark.parametrize("fps,expected_interval", [
    (30, 33),
    (60, 16),
    (10, 100),
    (1, 1000),
])
def test_init_timer_interval_matches_fps(qapp, fps, expected_interval):
    from transcrb.ui.mic_icon import MicRadarIcon

    w = MicRadarIcon(fps=fps)
    w._timer.stop()
    assert w._timer.interval() == expected_interval
    w.close()


def test_init_timer_interval_floor_at_fps_10000(qapp):
    from transcrb.ui.mic_icon import MicRadarIcon

    w = MicRadarIcon(fps=10000)
    w._timer.stop()
    assert w._timer.interval() >= 1
    w.close()


# ── set_active ────────────────────────────────────────────────────────────────

def test_set_active_true_to_false(widget):
    widget.set_active(False)
    assert widget._active is False


def test_set_active_false_to_true(widget):
    widget._active = False
    widget.set_active(True)
    assert widget._active is True


def test_set_active_idempotent_true(widget):
    widget.set_active(True)
    widget.set_active(True)
    assert widget._active is True


def test_set_active_idempotent_false(widget):
    widget._active = False
    widget.set_active(False)
    assert widget._active is False


def test_set_active_does_not_change_phase(widget):
    widget._phase = 1.23
    widget.set_active(False)
    assert widget._phase == 1.23


def test_set_active_does_not_stop_timer(qapp):
    from transcrb.ui.mic_icon import MicRadarIcon

    w = MicRadarIcon()
    was_active = w._timer.isActive()
    w.set_active(False)
    assert w._timer.isActive() == was_active
    w._timer.stop()
    w.close()


# ── _tick ─────────────────────────────────────────────────────────────────────

def test_tick_active_increments_phase_by_006(widget):
    widget._active = True
    widget._phase = 0.0
    widget._tick()
    assert abs(widget._phase - 0.06) < 1e-9


def test_tick_inactive_increments_phase_by_002(widget):
    widget._active = False
    widget._phase = 0.0
    widget._tick()
    assert abs(widget._phase - 0.02) < 1e-9


def test_tick_accumulates_monotonically_active(widget):
    widget._active = True
    widget._phase = 0.0
    for i in range(10):
        widget._tick()
    assert abs(widget._phase - 0.6) < 1e-6


def test_tick_accumulates_monotonically_inactive(widget):
    widget._active = False
    widget._phase = 0.0
    for i in range(10):
        widget._tick()
    assert abs(widget._phase - 0.2) < 1e-6


def test_tick_step_changes_when_active_flipped(widget):
    widget._active = True
    widget._phase = 0.0
    widget._tick()
    widget.set_active(False)
    widget._tick()
    assert abs(widget._phase - (0.06 + 0.02)) < 1e-9


def test_tick_calls_update(widget, monkeypatch):
    calls = []
    monkeypatch.setattr(widget, "update", lambda: calls.append(1))
    widget._tick()
    assert len(calls) == 1


def test_tick_large_phase_no_overflow(widget):
    widget._active = True
    widget._phase = 1e6
    widget._tick()
    assert widget._phase > 1e6


# ── paintEvent ────────────────────────────────────────────────────────────────

def _render_to_pixmap(widget, size: int) -> QPixmap:
    widget.resize(size, size)
    pm = QPixmap(size, size)
    pm.fill(QColor("transparent"))
    widget.render(pm)
    return pm


@pytest.mark.parametrize("size", [16, 32, 64, 128])
def test_paint_pixmap_not_null(widget, size):
    pm = _render_to_pixmap(widget, size)
    assert not pm.isNull()


@pytest.mark.parametrize("size", [16, 32, 64, 128])
def test_paint_pixmap_correct_size(widget, size):
    pm = _render_to_pixmap(widget, size)
    assert pm.size() == QSize(size, size)


def test_paint_no_raise_at_minimum_size(widget):
    _render_to_pixmap(widget, 44)


def test_paint_no_raise_tiny_size(widget):
    _render_to_pixmap(widget, 4)


def test_paint_active_vs_inactive_differ(qapp):
    from transcrb.ui.mic_icon import MicRadarIcon

    wa = MicRadarIcon(accent="#FF0000")
    wa._timer.stop()
    wa._phase = 0.0

    wi = MicRadarIcon(accent="#FF0000")
    wi._timer.stop()
    wi._phase = 0.0
    wi.set_active(False)

    pm_active = _render_to_pixmap(wa, 64)
    pm_inactive = _render_to_pixmap(wi, 64)

    img_a = pm_active.toImage()
    img_i = pm_inactive.toImage()

    # The two renders share the same phase=0 so any difference is alpha attenuation
    differing = sum(
        img_a.pixel(x, y) != img_i.pixel(x, y)
        for x in range(64) for y in range(64)
    )
    assert differing > 0
    wa.close()
    wi.close()


def test_paint_accent_color_present_in_image(qapp):
    from transcrb.ui.mic_icon import MicRadarIcon

    accent = "#FF0000"
    w = MicRadarIcon(accent=accent)
    w._timer.stop()
    w._phase = 0.0
    pm = _render_to_pixmap(w, 128)
    img = pm.toImage()

    found = False
    for x in range(128):
        for y in range(128):
            c = img.pixelColor(x, y)
            if c.red() > 200 and c.green() < 50 and c.blue() < 50 and c.alpha() > 0:
                found = True
                break
        if found:
            break

    assert found, "Expected red accent pixels in rendered image"
    w.close()


def test_paint_inactive_body_still_visible(qapp):
    from transcrb.ui.mic_icon import MicRadarIcon

    w = MicRadarIcon(accent="#FF0000")
    w._timer.stop()
    w._phase = 0.0
    w.set_active(False)
    pm = _render_to_pixmap(w, 128)
    img = pm.toImage()

    non_transparent = sum(
        1
        for x in range(128)
        for y in range(128)
        if img.pixelColor(x, y).alpha() > 0
    )
    assert non_transparent > 0
    w.close()


@pytest.mark.parametrize("size", [16, 32, 64, 128])
def test_paint_renders_non_empty_pixels(widget, size):
    pm = _render_to_pixmap(widget, size)
    img = pm.toImage()
    non_transparent = sum(
        1
        for x in range(size)
        for y in range(size)
        if img.pixelColor(x, y).alpha() > 0
    )
    assert non_transparent > 0
