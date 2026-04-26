from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def widget(qapp):
    from transcrb.ui.equalizer import EqualizerBars
    return EqualizerBars(n_bars=10, fps=30, smoothing=0.35)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_heights_initialized_to_point_one(self, widget):
        assert np.allclose(widget._heights, 0.1)

    def test_targets_initialized_to_point_one(self, widget):
        assert np.allclose(widget._targets, 0.1)

    def test_active_is_false_initially(self, widget):
        assert widget._active is False

    def test_phase_is_zero_initially(self, widget):
        assert widget._phase == 0.0

    def test_n_bars_stored(self, widget):
        assert widget._n == 10

    def test_smoothing_stored(self, widget):
        assert widget._smoothing == pytest.approx(0.35)

    def test_custom_n_bars(self, qapp):
        from transcrb.ui.equalizer import EqualizerBars
        w = EqualizerBars(n_bars=5)
        assert len(w._heights) == 5
        assert len(w._targets) == 5

    def test_timer_interval_from_fps(self, qapp):
        from transcrb.ui.equalizer import EqualizerBars
        w = EqualizerBars(fps=10)
        assert w._timer.interval() == 100

    def test_timer_interval_clipped_to_1ms_at_high_fps(self, qapp):
        from transcrb.ui.equalizer import EqualizerBars
        w = EqualizerBars(fps=9999)
        assert w._timer.interval() >= 1


# ---------------------------------------------------------------------------
# set_bands
# ---------------------------------------------------------------------------


class TestSetBands:
    def test_none_input_resets_targets(self, widget):
        widget.set_bands(None)
        assert np.allclose(widget._targets, 0.1)

    def test_none_input_sets_active_false(self, widget):
        widget._active = True
        widget.set_bands(None)
        assert widget._active is False

    def test_empty_array_resets_targets(self, widget):
        widget.set_bands(np.array([]))
        assert np.allclose(widget._targets, 0.1)

    def test_empty_array_sets_active_false(self, widget):
        widget._active = True
        widget.set_bands(np.array([]))
        assert widget._active is False

    def test_matching_length_stored_directly(self, widget):
        bands = np.linspace(0.2, 0.8, 10)
        widget.set_bands(bands, active=True)
        assert np.allclose(widget._targets, bands)

    def test_active_set_true_when_signal_provided(self, widget):
        widget._active = False
        widget.set_bands(np.ones(10) * 0.5)
        assert widget._active is True

    def test_active_false_override_respected(self, widget):
        widget.set_bands(np.ones(10) * 0.5, active=False)
        assert widget._active is False

    def test_values_clipped_above_one(self, widget):
        widget.set_bands(np.full(10, 2.0))
        assert np.all(widget._targets <= 1.0)

    def test_values_clipped_below_0_05(self, widget):
        widget.set_bands(np.full(10, 0.0))
        assert np.all(widget._targets >= 0.05)

    def test_negative_values_clipped_to_0_05(self, widget):
        widget.set_bands(np.full(10, -5.0))
        assert np.allclose(widget._targets, 0.05)

    def test_resampling_fewer_bands(self, widget):
        short = np.linspace(0.1, 0.9, 5)
        widget.set_bands(short)
        assert len(widget._targets) == 10

    def test_resampling_more_bands(self, widget):
        long_bands = np.linspace(0.1, 0.9, 20)
        widget.set_bands(long_bands)
        assert len(widget._targets) == 10

    def test_resampled_first_value_matches_input(self, widget):
        bands = np.array([0.2, 0.5, 0.8], dtype=np.float32)
        widget.set_bands(bands)
        assert widget._targets[0] == pytest.approx(0.2, abs=1e-4)

    def test_resampled_last_value_matches_input(self, widget):
        bands = np.array([0.2, 0.5, 0.8], dtype=np.float32)
        widget.set_bands(bands)
        assert widget._targets[-1] == pytest.approx(0.8, abs=1e-4)

    def test_dtype_is_float32(self, widget):
        widget.set_bands(np.ones(10, dtype=np.float64))
        assert widget._targets.dtype == np.float32

    @pytest.mark.parametrize("level", [0.1, 0.5, 1.0])
    def test_uniform_bands_round_trip(self, widget, level):
        widget.set_bands(np.full(10, level))
        assert np.allclose(widget._targets, level)

    def test_max_value_1_not_clipped(self, widget):
        widget.set_bands(np.full(10, 1.0))
        assert np.allclose(widget._targets, 1.0)

    def test_min_value_0_05_not_clipped(self, widget):
        widget.set_bands(np.full(10, 0.05))
        assert np.allclose(widget._targets, 0.05)


# ---------------------------------------------------------------------------
# set_idle
# ---------------------------------------------------------------------------


class TestSetIdle:
    def test_active_becomes_false(self, widget):
        widget._active = True
        widget.set_idle()
        assert widget._active is False

    def test_targets_reset_to_0_1(self, widget):
        widget._targets[:] = 0.9
        widget.set_idle()
        assert np.allclose(widget._targets, 0.1)

    def test_heights_unchanged_by_set_idle(self, widget):
        widget._heights[:] = 0.7
        widget.set_idle()
        assert np.allclose(widget._heights, 0.7)

    def test_idempotent(self, widget):
        widget.set_idle()
        widget.set_idle()
        assert widget._active is False
        assert np.allclose(widget._targets, 0.1)

    def test_set_idle_after_set_bands(self, widget):
        widget.set_bands(np.ones(10) * 0.9)
        assert widget._active is True
        widget.set_idle()
        assert widget._active is False
        assert np.allclose(widget._targets, 0.1)


# ---------------------------------------------------------------------------
# _tick — smoothing
# ---------------------------------------------------------------------------


class TestTickSmoothing:
    def test_heights_move_toward_targets(self, widget):
        widget._active = True
        widget._targets[:] = 1.0
        widget._heights[:] = 0.0
        widget._tick()
        assert np.all(widget._heights > 0.0)
        assert np.all(widget._heights < 1.0)

    def test_smoothing_factor_governs_step(self, widget):
        widget._active = True
        widget._targets[:] = 1.0
        widget._heights[:] = 0.0
        widget._tick()
        expected = 0.0 + (1.0 - 0.0) * 0.35
        assert np.allclose(widget._heights, expected)

    def test_heights_converge_to_targets_over_ticks(self, widget):
        widget._active = True
        widget._targets[:] = 0.9
        widget._heights[:] = 0.1
        for _ in range(60):
            widget._tick()
        assert np.allclose(widget._heights, 0.9, atol=0.02)

    def test_overshoot_impossible_from_below(self, widget):
        widget._active = True
        widget._targets[:] = 0.6
        widget._heights[:] = 0.1
        for _ in range(100):
            widget._tick()
        assert np.all(widget._heights <= 0.6 + 1e-5)

    def test_heights_decay_toward_lower_target(self, widget):
        widget._active = True
        widget._heights[:] = 0.9
        widget._targets[:] = 0.1
        widget._tick()
        assert np.all(widget._heights < 0.9)

    def test_already_at_target_stays_stable(self, widget):
        widget._active = True
        widget._targets[:] = 0.5
        widget._heights[:] = 0.5
        widget._tick()
        assert np.allclose(widget._heights, 0.5)

    def test_sharp_jump_smoothed_not_instant(self, widget):
        widget._active = True
        widget._heights[:] = 0.1
        widget._targets[:] = 1.0
        widget._tick()
        assert np.all(widget._heights < 1.0)

    def test_smoothing_zero_means_no_movement(self, qapp):
        from transcrb.ui.equalizer import EqualizerBars
        w = EqualizerBars(n_bars=4, smoothing=0.0)
        w._active = True
        w._heights[:] = 0.1
        w._targets[:] = 0.9
        w._tick()
        assert np.allclose(w._heights, 0.1)

    def test_smoothing_one_means_instant(self, qapp):
        from transcrb.ui.equalizer import EqualizerBars
        w = EqualizerBars(n_bars=4, smoothing=1.0)
        w._active = True
        w._heights[:] = 0.1
        w._targets[:] = 0.9
        w._tick()
        assert np.allclose(w._heights, 0.9)

    def test_independent_bars_converge_independently(self, qapp):
        from transcrb.ui.equalizer import EqualizerBars
        w = EqualizerBars(n_bars=2, smoothing=1.0)
        w._active = True
        w._targets[0] = 0.3
        w._targets[1] = 0.7
        w._heights[:] = 0.0
        w._tick()
        assert w._heights[0] == pytest.approx(0.3)
        assert w._heights[1] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# _tick — idle breathing animation
# ---------------------------------------------------------------------------


class TestTickIdleBreathing:
    def test_inactive_phase_advances(self, widget):
        widget._active = False
        widget._phase = 0.0
        widget._tick()
        assert widget._phase == pytest.approx(0.08)

    def test_inactive_phase_cumulative(self, widget):
        widget._active = False
        widget._phase = 0.0
        for _ in range(5):
            widget._tick()
        assert widget._phase == pytest.approx(5 * 0.08)

    def test_inactive_targets_are_sine_based(self, widget):
        widget._active = False
        widget._phase = 0.0
        widget._tick()
        phase_after = 0.08
        expected = 0.18 + 0.08 * np.sin(phase_after + np.arange(10) * 0.6)
        assert np.allclose(widget._targets, expected.astype(np.float32), atol=1e-5)

    def test_inactive_targets_upper_bound(self, widget):
        widget._active = False
        for _ in range(200):
            widget._tick()
        assert np.all(widget._targets <= 0.26 + 1e-4)

    def test_inactive_targets_lower_bound(self, widget):
        widget._active = False
        for _ in range(200):
            widget._tick()
        assert np.all(widget._targets >= 0.10 - 1e-4)

    def test_active_phase_does_not_advance(self, widget):
        widget._active = True
        widget._phase = 1.23
        widget._targets[:] = 0.5
        widget._heights[:] = 0.5
        widget._tick()
        assert widget._phase == pytest.approx(1.23)

    def test_active_targets_not_overwritten_by_breathing(self, widget):
        widget._active = True
        widget._targets[:] = 0.9
        widget._phase = 0.0
        widget._tick()
        assert np.all(widget._heights > 0.1)

    def test_breathing_produces_per_bar_variation(self, widget):
        widget._active = False
        widget._phase = 0.5
        widget._tick()
        assert not np.all(widget._targets == widget._targets[0])
