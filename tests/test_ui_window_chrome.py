from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from transcrb.ui.window_chrome import (
    FramelessMainWindow,
    TitleBar,
    _RESIZE_MARGIN,
    chrome_stylesheet,
)


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# chrome_stylesheet
# ---------------------------------------------------------------------------


class TestChromeStylesheet:
    def test_returns_str(self):
        assert isinstance(chrome_stylesheet(), str)

    def test_non_empty(self):
        assert len(chrome_stylesheet()) > 0

    def test_contains_titlebar_selector(self):
        assert "titleBar" in chrome_stylesheet()

    def test_contains_background_color(self):
        assert "#0A0A0B" in chrome_stylesheet()

    def test_deterministic(self):
        assert chrome_stylesheet() == chrome_stylesheet()

    def test_contains_title_label_selector(self):
        assert "titleBarTitle" in chrome_stylesheet()

    def test_contains_sub_label_selector(self):
        assert "titleBarSub" in chrome_stylesheet()


# ---------------------------------------------------------------------------
# TitleBar.__init__
# ---------------------------------------------------------------------------


class TestTitleBarInit:
    def test_default_show_maximize_creates_btn_max(self, qapp):
        tb = TitleBar("Test")
        assert tb._btn_max is not None

    def test_show_maximize_false_btn_max_is_none(self, qapp):
        tb = TitleBar("Test", show_maximize=False)
        assert tb._btn_max is None

    def test_title_label_text(self, qapp):
        tb = TitleBar("MyApp")
        assert tb._title_lbl.text() == "MyApp"

    def test_fixed_height(self, qapp):
        tb = TitleBar("X")
        assert tb.height() == 44

    def test_close_btn_exists(self, qapp):
        tb = TitleBar("X")
        assert tb._btn_close is not None

    def test_min_btn_exists(self, qapp):
        tb = TitleBar("X")
        assert tb._btn_min is not None

    def test_object_name_is_title_bar(self, qapp):
        tb = TitleBar("X")
        assert tb.objectName() == "titleBar"

    def test_minimize_signal_connected(self, qapp):
        tb = TitleBar("X")
        spy = []
        tb.minimize_requested.connect(lambda: spy.append(1))
        tb._btn_min.click()
        assert spy == [1]

    def test_close_signal_connected(self, qapp):
        tb = TitleBar("X")
        spy = []
        tb.close_requested.connect(lambda: spy.append(1))
        tb._btn_close.click()
        assert spy == [1]

    def test_maximize_signal_connected_when_shown(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        spy = []
        tb.maximize_toggle_requested.connect(lambda: spy.append(1))
        tb._btn_max.click()
        assert spy == [1]


# ---------------------------------------------------------------------------
# TitleBar.set_title
# ---------------------------------------------------------------------------


class TestTitleBarSetTitle:
    def test_updates_label_text(self, qapp):
        tb = TitleBar("Old")
        tb.set_title("New")
        assert tb._title_lbl.text() == "New"

    def test_empty_string_allowed(self, qapp):
        tb = TitleBar("Something")
        tb.set_title("")
        assert tb._title_lbl.text() == ""

    def test_unicode_title(self, qapp):
        tb = TitleBar("X")
        tb.set_title("Настройки")
        assert tb._title_lbl.text() == "Настройки"

    def test_repeated_set(self, qapp):
        tb = TitleBar("A")
        tb.set_title("B")
        tb.set_title("C")
        assert tb._title_lbl.text() == "C"

    def test_long_title(self, qapp):
        tb = TitleBar("X")
        long = "A" * 256
        tb.set_title(long)
        assert tb._title_lbl.text() == long


# ---------------------------------------------------------------------------
# TitleBar.set_max_state
# ---------------------------------------------------------------------------


class TestTitleBarSetMaxState:
    def test_no_crash_when_btn_max_is_none(self, qapp):
        tb = TitleBar("X", show_maximize=False)
        tb.set_max_state(True)

    def test_tooltip_changes_to_restore_when_maximized(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        tb.set_max_state(True)
        assert tb._btn_max.toolTip() == "Восстановить"

    def test_tooltip_changes_to_expand_when_normal(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        tb.set_max_state(True)
        tb.set_max_state(False)
        assert tb._btn_max.toolTip() == "Развернуть"

    def test_max_state_stored_in_btn(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        tb.set_max_state(True)
        assert tb._btn_max._maximized is True

    def test_same_state_twice_noop(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        tb.set_max_state(False)
        tb.set_max_state(False)
        assert tb._btn_max._maximized is False


# ---------------------------------------------------------------------------
# TitleBar.mousePressEvent
# ---------------------------------------------------------------------------


def _mouse_event(btn: Qt.MouseButton) -> QMouseEvent:
    p = QPointF(10.0, 10.0)
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        p,
        p,
        btn,
        btn,
        Qt.KeyboardModifier.NoModifier,
    )


class TestTitleBarMousePress:
    def test_left_button_calls_start_system_move(self, qapp):
        tb = TitleBar("X")
        mock_wh = MagicMock()
        with patch.object(tb, "window", return_value=MagicMock(windowHandle=MagicMock(return_value=mock_wh))):
            tb.mousePressEvent(_mouse_event(Qt.MouseButton.LeftButton))
        mock_wh.startSystemMove.assert_called_once()

    def test_left_button_accepts_event(self, qapp):
        tb = TitleBar("X")
        mock_wh = MagicMock()
        with patch.object(tb, "window", return_value=MagicMock(windowHandle=MagicMock(return_value=mock_wh))):
            ev = _mouse_event(Qt.MouseButton.LeftButton)
            tb.mousePressEvent(ev)
        assert ev.isAccepted()

    def test_right_button_does_not_call_start_system_move(self, qapp):
        tb = TitleBar("X")
        mock_wh = MagicMock()
        with patch.object(tb, "window", return_value=MagicMock(windowHandle=MagicMock(return_value=mock_wh))):
            tb.mousePressEvent(_mouse_event(Qt.MouseButton.RightButton))
        mock_wh.startSystemMove.assert_not_called()

    def test_none_window_handle_does_not_crash(self, qapp):
        tb = TitleBar("X")
        with patch.object(tb, "window", return_value=MagicMock(windowHandle=MagicMock(return_value=None))):
            tb.mousePressEvent(_mouse_event(Qt.MouseButton.LeftButton))

    def test_left_press_twice_calls_start_system_move_twice(self, qapp):
        tb = TitleBar("X")
        mock_wh = MagicMock()
        with patch.object(tb, "window", return_value=MagicMock(windowHandle=MagicMock(return_value=mock_wh))):
            tb.mousePressEvent(_mouse_event(Qt.MouseButton.LeftButton))
            tb.mousePressEvent(_mouse_event(Qt.MouseButton.LeftButton))
        assert mock_wh.startSystemMove.call_count == 2


# ---------------------------------------------------------------------------
# TitleBar.mouseDoubleClickEvent
# ---------------------------------------------------------------------------


def _dclick_event(btn: Qt.MouseButton) -> QMouseEvent:
    p = QPointF(10.0, 10.0)
    return QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        p,
        p,
        btn,
        btn,
        Qt.KeyboardModifier.NoModifier,
    )


class TestTitleBarDoubleClick:
    def test_left_dclick_emits_maximize_toggle(self, qapp):
        tb = TitleBar("X")
        spy = []
        tb.maximize_toggle_requested.connect(lambda: spy.append(1))
        tb.mouseDoubleClickEvent(_dclick_event(Qt.MouseButton.LeftButton))
        assert spy == [1]

    def test_left_dclick_accepts_event(self, qapp):
        tb = TitleBar("X")
        tb.maximize_toggle_requested.connect(lambda: None)
        ev = _dclick_event(Qt.MouseButton.LeftButton)
        tb.mouseDoubleClickEvent(ev)
        assert ev.isAccepted()

    def test_right_dclick_does_not_emit(self, qapp):
        tb = TitleBar("X")
        spy = []
        tb.maximize_toggle_requested.connect(lambda: spy.append(1))
        tb.mouseDoubleClickEvent(_dclick_event(Qt.MouseButton.RightButton))
        assert spy == []

    def test_multiple_dclicks_emit_multiple_times(self, qapp):
        tb = TitleBar("X")
        spy = []
        tb.maximize_toggle_requested.connect(lambda: spy.append(1))
        for _ in range(3):
            tb.mouseDoubleClickEvent(_dclick_event(Qt.MouseButton.LeftButton))
        assert len(spy) == 3

    def test_middle_button_dclick_does_not_emit(self, qapp):
        tb = TitleBar("X")
        spy = []
        tb.maximize_toggle_requested.connect(lambda: spy.append(1))
        tb.mouseDoubleClickEvent(_dclick_event(Qt.MouseButton.MiddleButton))
        assert spy == []


# ---------------------------------------------------------------------------
# FramelessMainWindow.install_titlebar
# ---------------------------------------------------------------------------


class TestInstallTitlebar:
    def test_minimize_signal_connected_to_show_minimized(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        spy = []
        win.showMinimized = lambda: spy.append("min")
        win.install_titlebar(tb)
        tb.minimize_requested.emit()
        assert spy == ["min"]

    def test_close_signal_connected_to_close(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        spy = []
        win.close = lambda: spy.append("close")
        win.install_titlebar(tb)
        tb.close_requested.emit()
        assert spy == ["close"]

    def test_maximize_toggle_connected_to_toggle_max(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        win.install_titlebar(tb)
        with patch.object(win, "_toggle_max_restore") as mock_toggle:
            tb.maximize_toggle_requested.emit()
        mock_toggle.assert_called_once()

    def test_title_bar_stored(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        win.install_titlebar(tb)
        assert win._title_bar is tb

    def test_second_install_replaces_stored_reference(self, qapp):
        win = FramelessMainWindow()
        tb1 = TitleBar("A")
        tb2 = TitleBar("B")
        win.install_titlebar(tb1)
        win.install_titlebar(tb2)
        assert win._title_bar is tb2


# ---------------------------------------------------------------------------
# FramelessMainWindow._toggle_max_restore
# ---------------------------------------------------------------------------


class TestToggleMaxRestore:
    def test_normal_calls_show_maximized(self, qapp):
        win = FramelessMainWindow()
        with patch.object(win, "isMaximized", return_value=False), \
             patch.object(win, "showMaximized") as mock_max:
            win._toggle_max_restore()
        mock_max.assert_called_once()

    def test_maximized_calls_show_normal(self, qapp):
        win = FramelessMainWindow()
        with patch.object(win, "isMaximized", return_value=True), \
             patch.object(win, "showNormal") as mock_normal:
            win._toggle_max_restore()
        mock_normal.assert_called_once()

    def test_normal_does_not_call_show_normal(self, qapp):
        win = FramelessMainWindow()
        with patch.object(win, "isMaximized", return_value=False), \
             patch.object(win, "showNormal") as mock_normal:
            win._toggle_max_restore()
        mock_normal.assert_not_called()

    def test_maximized_does_not_call_show_maximized(self, qapp):
        win = FramelessMainWindow()
        with patch.object(win, "isMaximized", return_value=True), \
             patch.object(win, "showMaximized") as mock_max:
            win._toggle_max_restore()
        mock_max.assert_not_called()

    def test_toggle_twice_alternates(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        win.install_titlebar(tb)
        calls = []
        with patch.object(win, "isMaximized", side_effect=[False, True]), \
             patch.object(win, "showMaximized", side_effect=lambda: calls.append("max")), \
             patch.object(win, "showNormal", side_effect=lambda: calls.append("normal")):
            tb.maximize_toggle_requested.emit()
            tb.maximize_toggle_requested.emit()
        assert calls == ["max", "normal"]


# ---------------------------------------------------------------------------
# FramelessMainWindow.changeEvent
# ---------------------------------------------------------------------------


class TestChangeEvent:
    def test_propagates_maximized_state(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        win.install_titlebar(tb)
        states = []
        tb.set_max_state = lambda v: states.append(v)
        with patch.object(win, "isMaximized", return_value=True):
            win.changeEvent(QEvent(QEvent.Type.WindowStateChange))
        assert states == [True]

    def test_propagates_normal_state(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        win.install_titlebar(tb)
        states = []
        tb.set_max_state = lambda v: states.append(v)
        with patch.object(win, "isMaximized", return_value=False):
            win.changeEvent(QEvent(QEvent.Type.WindowStateChange))
        assert states == [False]

    def test_no_crash_when_title_bar_is_none(self, qapp):
        win = FramelessMainWindow()
        assert win._title_bar is None
        win.changeEvent(QEvent(QEvent.Type.WindowStateChange))

    def test_other_event_type_still_calls_set_max_state(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        win.install_titlebar(tb)
        states = []
        tb.set_max_state = lambda v: states.append(v)
        with patch.object(win, "isMaximized", return_value=False):
            win.changeEvent(QEvent(QEvent.Type.FontChange))
        assert len(states) == 1

    def test_state_matches_is_maximized_return(self, qapp):
        win = FramelessMainWindow()
        tb = TitleBar("X")
        win.install_titlebar(tb)
        states = []
        tb.set_max_state = lambda v: states.append(v)
        with patch.object(win, "isMaximized", return_value=True):
            win.changeEvent(QEvent(QEvent.Type.WindowStateChange))
        with patch.object(win, "isMaximized", return_value=False):
            win.changeEvent(QEvent(QEvent.Type.WindowStateChange))
        assert states == [True, False]


# ---------------------------------------------------------------------------
# FramelessMainWindow.nativeEvent — hit zone logic
# ---------------------------------------------------------------------------


def _pack_lparam(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


_WM_NCHITTEST = 0x0084
_WM_GETMINMAXINFO = 0x0024

_HT = {
    "HTLEFT": 10,
    "HTRIGHT": 11,
    "HTTOP": 12,
    "HTTOPLEFT": 13,
    "HTTOPRIGHT": 14,
    "HTBOTTOM": 15,
    "HTBOTTOMLEFT": 16,
    "HTBOTTOMRIGHT": 17,
}

_L = 100
_T = 200
_W = 800
_H = 600
_R = _L + _W
_B = _T + _H
_M = _RESIZE_MARGIN


def _run_nchittest(win: FramelessMainWindow, x: int, y: int):
    fake = SimpleNamespace(message=_WM_NCHITTEST, lParam=_pack_lparam(x, y))
    with patch.object(win, "isMaximized", return_value=False), \
         patch.object(win, "isFullScreen", return_value=False), \
         patch.object(win, "frameGeometry", return_value=QRect(_L, _T, _W, _H)), \
         patch("ctypes.wintypes.MSG") as mock_cls:
        mock_cls.from_address.return_value = fake
        return win.nativeEvent(b"windows_generic_MSG", 0)


@pytest.mark.skipif(sys.platform != "win32", reason="win32 only")
class TestNativeEventHitZones:
    def test_top_edge_returns_httop(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _L + 50, _T + _M - 1) == (True, _HT["HTTOP"])

    def test_bottom_edge_returns_htbottom(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _L + 50, _B - 1) == (True, _HT["HTBOTTOM"])

    def test_left_edge_returns_htleft(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _L + _M - 1, _T + 50) == (True, _HT["HTLEFT"])

    def test_right_edge_returns_htright(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _R - _M, _T + 50) == (True, _HT["HTRIGHT"])

    def test_top_left_corner_returns_httopleft(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _L + _M - 1, _T + _M - 1) == (True, _HT["HTTOPLEFT"])

    def test_top_right_corner_returns_httopright(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _R - _M, _T + _M - 1) == (True, _HT["HTTOPRIGHT"])

    def test_bottom_left_corner_returns_htbottomleft(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _L + _M - 1, _B - 1) == (True, _HT["HTBOTTOMLEFT"])

    def test_bottom_right_corner_returns_htbottomright(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _R - _M, _B - 1) == (True, _HT["HTBOTTOMRIGHT"])

    def test_interior_falls_through_to_super(self, qapp):
        win = FramelessMainWindow()
        fake = SimpleNamespace(message=_WM_NCHITTEST, lParam=_pack_lparam(_L + 100, _T + 100))
        with patch.object(win, "isMaximized", return_value=False), \
             patch.object(win, "isFullScreen", return_value=False), \
             patch.object(win, "frameGeometry", return_value=QRect(_L, _T, _W, _H)), \
             patch("ctypes.wintypes.MSG") as mock_cls:
            mock_cls.from_address.return_value = fake
            with pytest.raises(ValueError):
                win.nativeEvent(b"windows_generic_MSG", 0)

    def test_left_at_margin_boundary_not_left(self, qapp):
        win = FramelessMainWindow()
        fake = SimpleNamespace(message=_WM_NCHITTEST, lParam=_pack_lparam(_L + _M, _T + 50))
        with patch.object(win, "isMaximized", return_value=False), \
             patch.object(win, "isFullScreen", return_value=False), \
             patch.object(win, "frameGeometry", return_value=QRect(_L, _T, _W, _H)), \
             patch("ctypes.wintypes.MSG") as mock_cls:
            mock_cls.from_address.return_value = fake
            with pytest.raises(ValueError):
                win.nativeEvent(b"windows_generic_MSG", 0)

    def test_right_at_margin_boundary_is_right(self, qapp):
        win = FramelessMainWindow()
        assert _run_nchittest(win, _R - _M, _T + 50) == (True, _HT["HTRIGHT"])

    def test_maximized_falls_through(self, qapp):
        win = FramelessMainWindow()
        fake = SimpleNamespace(message=_WM_NCHITTEST, lParam=_pack_lparam(_L + _M - 1, _T + _M - 1))
        with patch.object(win, "isMaximized", return_value=True) as mock_max, \
             patch.object(win, "isFullScreen", return_value=False), \
             patch.object(win, "frameGeometry", return_value=QRect(_L, _T, _W, _H)), \
             patch("ctypes.wintypes.MSG") as mock_cls:
            mock_cls.from_address.return_value = fake
            with pytest.raises(ValueError):
                win.nativeEvent(b"windows_generic_MSG", 0)
        mock_max.assert_called()

    def test_fullscreen_falls_through(self, qapp):
        win = FramelessMainWindow()
        fake = SimpleNamespace(message=_WM_NCHITTEST, lParam=_pack_lparam(_L + _M - 1, _T + _M - 1))
        with patch.object(win, "isMaximized", return_value=False), \
             patch.object(win, "isFullScreen", return_value=True) as mock_fs, \
             patch.object(win, "frameGeometry", return_value=QRect(_L, _T, _W, _H)), \
             patch("ctypes.wintypes.MSG") as mock_cls:
            mock_cls.from_address.return_value = fake
            with pytest.raises(ValueError):
                win.nativeEvent(b"windows_generic_MSG", 0)
        mock_fs.assert_called()

    def test_non_nchittest_routes_to_minmaxinfo_handler(self, qapp):
        win = FramelessMainWindow()
        fake = SimpleNamespace(message=_WM_GETMINMAXINFO, lParam=0)
        with patch.object(win, "_handle_minmaxinfo", return_value=(True, 0)) as mock_handler, \
             patch("ctypes.wintypes.MSG") as mock_cls:
            mock_cls.from_address.return_value = fake
            win.nativeEvent(b"windows_generic_MSG", 0)
        mock_handler.assert_called_once()

    def test_wrong_event_type_string_falls_through(self, qapp):
        win = FramelessMainWindow()
        with patch.object(win, "isMaximized") as mock_max:
            try:
                win.nativeEvent(b"other_event", 0)
            except Exception:
                pass
        mock_max.assert_not_called()

    def test_non_win32_platform_skips_hit_zones(self, qapp):
        import transcrb.ui.window_chrome as m
        win = FramelessMainWindow()
        orig = m.sys.platform
        m.sys.platform = "linux"
        try:
            with patch.object(win, "isMaximized") as mock_max:
                try:
                    win.nativeEvent(b"windows_generic_MSG", 0)
                except Exception:
                    pass
            mock_max.assert_not_called()
        finally:
            m.sys.platform = orig


# ---------------------------------------------------------------------------
# FramelessMainWindow._handle_minmaxinfo
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="win32 only")
class TestHandleMinMaxInfo:
    def _make_info_and_msg(self):
        import ctypes

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class MINMAXINFO(ctypes.Structure):
            _fields_ = [
                ("ptReserved", POINT),
                ("ptMaxSize", POINT),
                ("ptMaxPosition", POINT),
                ("ptMinTrackSize", POINT),
                ("ptMaxTrackSize", POINT),
            ]

        info = MINMAXINFO()
        msg = SimpleNamespace(lParam=ctypes.addressof(info))
        return ctypes, msg, info

    def test_returns_true_zero_on_success(self, qapp):
        import ctypes
        win = FramelessMainWindow()
        ctypes_mod, msg, _ = self._make_info_and_msg()
        screen = MagicMock()
        screen.availableGeometry.return_value = QRect(0, 0, 1920, 1040)
        screen.geometry.return_value = QRect(0, 0, 1920, 1080)
        with patch.object(win, "screen", return_value=screen):
            result = win._handle_minmaxinfo(ctypes_mod, msg)
        assert result == (True, 0)

    def test_sets_max_size_from_available_geometry(self, qapp):
        import ctypes
        win = FramelessMainWindow()
        ctypes_mod, msg, info = self._make_info_and_msg()
        screen = MagicMock()
        screen.availableGeometry.return_value = QRect(0, 40, 1920, 1040)
        screen.geometry.return_value = QRect(0, 0, 1920, 1080)
        with patch.object(win, "screen", return_value=screen):
            win._handle_minmaxinfo(ctypes_mod, msg)
        assert info.ptMaxSize.x == 1920
        assert info.ptMaxSize.y == 1040

    def test_sets_max_position_offset(self, qapp):
        import ctypes
        win = FramelessMainWindow()
        ctypes_mod, msg, info = self._make_info_and_msg()
        screen = MagicMock()
        screen.availableGeometry.return_value = QRect(0, 40, 1920, 1040)
        screen.geometry.return_value = QRect(0, 0, 1920, 1080)
        with patch.object(win, "screen", return_value=screen):
            win._handle_minmaxinfo(ctypes_mod, msg)
        assert info.ptMaxPosition.x == 0
        assert info.ptMaxPosition.y == 40

    def test_returns_false_zero_when_no_screen(self, qapp):
        import ctypes
        win = FramelessMainWindow()
        _, msg, _ = self._make_info_and_msg()
        with patch.object(win, "screen", return_value=None), \
             patch("transcrb.ui.window_chrome.QGuiApplication.primaryScreen", return_value=None):
            result = win._handle_minmaxinfo(ctypes, msg)
        assert result == (False, 0)

    def test_returns_false_zero_on_screen_exception(self, qapp):
        import ctypes
        win = FramelessMainWindow()
        _, msg, _ = self._make_info_and_msg()
        bad_screen = MagicMock()
        bad_screen.availableGeometry.side_effect = RuntimeError("exploded")
        with patch.object(win, "screen", return_value=bad_screen):
            result = win._handle_minmaxinfo(ctypes, msg)
        assert result == (False, 0)

    def test_multi_monitor_position_offset(self, qapp):
        import ctypes
        win = FramelessMainWindow()
        ctypes_mod, msg, info = self._make_info_and_msg()
        screen = MagicMock()
        screen.availableGeometry.return_value = QRect(1920, 0, 1920, 1080)
        screen.geometry.return_value = QRect(1920, 0, 1920, 1080)
        with patch.object(win, "screen", return_value=screen):
            win._handle_minmaxinfo(ctypes_mod, msg)
        assert info.ptMaxPosition.x == 0
        assert info.ptMaxPosition.y == 0


# ---------------------------------------------------------------------------
# _ChromeButton.set_max_state (via TitleBar._btn_max)
# ---------------------------------------------------------------------------


class TestChromeButtonSetMaxState:
    def test_initial_maximized_is_false(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        assert tb._btn_max._maximized is False

    def test_set_true_updates_flag(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        tb._btn_max.set_max_state(True)
        assert tb._btn_max._maximized is True

    def test_set_false_updates_flag(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        tb._btn_max.set_max_state(True)
        tb._btn_max.set_max_state(False)
        assert tb._btn_max._maximized is False

    def test_same_state_repeated_no_flip(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        tb._btn_max.set_max_state(False)
        tb._btn_max.set_max_state(False)
        assert tb._btn_max._maximized is False

    def test_toggle_sequence(self, qapp):
        tb = TitleBar("X", show_maximize=True)
        for expected in [True, False, True, False]:
            tb._btn_max.set_max_state(expected)
            assert tb._btn_max._maximized is expected
