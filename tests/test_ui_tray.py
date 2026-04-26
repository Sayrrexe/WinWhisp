from __future__ import annotations

from unittest.mock import MagicMock, patch, call
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def _make_tray(icon_exists: bool = False):
    with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
         patch("transcrb.ui.tray.QSystemTrayIcon") as mock_stray_cls:
        mock_icon_file = MagicMock()
        mock_icon_file.exists.return_value = icon_exists
        mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
        mock_stray_cls.return_value = MagicMock()

        from transcrb.ui.tray import TrayIcon
        tray = TrayIcon()
        tray._mock_stray = mock_stray_cls.return_value
        return tray


@pytest.fixture(autouse=True)
def qapp(qapp):
    return qapp


class TestTrayIconInit:
    def test_default_title_is_winwhisp(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            assert t._title == "WinWhisp"

    def test_custom_title_stored(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon("MyApp")
            assert t._title == "MyApp"

    def test_tooltip_set_to_title(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon("TestApp")
            mock_stray.setToolTip.assert_called_once_with("TestApp")

    def test_menu_has_open_action(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            actions = t._menu.actions()
            texts = [a.text() for a in actions if not a.isSeparator()]
            assert "Открыть" in texts

    def test_menu_has_quit_action(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            actions = t._menu.actions()
            texts = [a.text() for a in actions if not a.isSeparator()]
            assert "Выход" in texts

    def test_menu_has_separator(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            separators = [a for a in t._menu.actions() if a.isSeparator()]
            assert len(separators) >= 1

    def test_menu_action_order_open_before_quit(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            texts = [a.text() for a in t._menu.actions()]
            assert texts.index("Открыть") < texts.index("Выход")

    def test_fallback_icon_used_when_file_missing(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls, \
             patch("transcrb.ui.tray._fallback_icon") as mock_fallback:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            TrayIcon()
            mock_fallback.assert_called_once()

    def test_real_icon_used_when_file_exists(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls, \
             patch("transcrb.ui.tray._fallback_icon") as mock_fallback, \
             patch("transcrb.ui.tray.QIcon") as mock_qicon:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = True
            mock_icon_file.__str__ = lambda self: "/fake/icon.ico"
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            TrayIcon()
            mock_fallback.assert_not_called()
            mock_qicon.assert_called_once()

    def test_context_menu_set_on_tray(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            mock_stray.setContextMenu.assert_called_once_with(t._menu)


class TestSignals:
    def _make(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            return TrayIcon()

    def test_open_action_emits_open_requested(self, qtbot):
        t = self._make()
        with qtbot.waitSignal(t.open_requested, timeout=500):
            open_action = next(
                a for a in t._menu.actions()
                if a.text() == "Открыть"
            )
            open_action.trigger()

    def test_quit_action_emits_quit_requested(self, qtbot):
        t = self._make()
        with qtbot.waitSignal(t.quit_requested, timeout=500):
            quit_action = next(
                a for a in t._menu.actions()
                if a.text() == "Выход"
            )
            quit_action.trigger()

    def test_quit_does_not_emit_open_requested(self, qtbot):
        t = self._make()
        with qtbot.assertNotEmitted(t.open_requested):
            quit_action = next(
                a for a in t._menu.actions()
                if a.text() == "Выход"
            )
            quit_action.trigger()

    def test_open_does_not_emit_quit_requested(self, qtbot):
        t = self._make()
        with qtbot.assertNotEmitted(t.quit_requested):
            open_action = next(
                a for a in t._menu.actions()
                if a.text() == "Открыть"
            )
            open_action.trigger()

    def test_signals_declared_on_class(self):
        from transcrb.ui.tray import TrayIcon
        assert hasattr(TrayIcon, "quit_requested")
        assert hasattr(TrayIcon, "open_requested")
        assert hasattr(TrayIcon, "reload_requested")


class TestOnActivated:
    def _make(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"):
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            return TrayIcon()

    def test_trigger_emits_open_requested(self, qtbot):
        from PySide6.QtWidgets import QSystemTrayIcon as QSTI
        t = self._make()
        with qtbot.waitSignal(t.open_requested, timeout=500):
            t._on_activated(QSTI.Trigger)

    def test_double_click_does_not_emit_open_requested(self, qtbot):
        from PySide6.QtWidgets import QSystemTrayIcon as QSTI
        t = self._make()
        with qtbot.assertNotEmitted(t.open_requested):
            t._on_activated(QSTI.DoubleClick)

    def test_middle_click_does_not_emit_open_requested(self, qtbot):
        from PySide6.QtWidgets import QSystemTrayIcon as QSTI
        t = self._make()
        with qtbot.assertNotEmitted(t.open_requested):
            t._on_activated(QSTI.MiddleClick)

    def test_context_does_not_emit_open_requested(self, qtbot):
        from PySide6.QtWidgets import QSystemTrayIcon as QSTI
        t = self._make()
        with qtbot.assertNotEmitted(t.open_requested):
            t._on_activated(QSTI.Context)

    def test_unknown_reason_does_not_emit(self, qtbot):
        t = self._make()
        with qtbot.assertNotEmitted(t.open_requested):
            t._on_activated(99)


class TestShow:
    def test_show_calls_tray_show(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            t.show()
            mock_stray.show.assert_called_once()

    def test_show_called_twice_calls_tray_show_twice(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            t.show()
            t.show()
            assert mock_stray.show.call_count == 2


class TestNotify:
    def _make_with_mock_stray(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            return t, mock_stray

    def test_notify_calls_show_message(self):
        t, mock_stray = self._make_with_mock_stray()
        t.notify("Title", "Body")
        mock_stray.showMessage.assert_called_once()

    def test_notify_passes_title_and_message(self):
        t, mock_stray = self._make_with_mock_stray()
        t.notify("Hello", "World")
        args = mock_stray.showMessage.call_args[0]
        assert args[0] == "Hello"
        assert args[1] == "World"

    def test_notify_uses_information_icon(self):
        from PySide6.QtWidgets import QSystemTrayIcon as QSTI
        t, mock_stray = self._make_with_mock_stray()
        t.notify("T", "M")
        args = mock_stray.showMessage.call_args[0]
        assert args[2] == QSTI.Information

    def test_notify_timeout_is_3000ms(self):
        t, mock_stray = self._make_with_mock_stray()
        t.notify("T", "M")
        args = mock_stray.showMessage.call_args[0]
        assert args[3] == 3000

    def test_notify_empty_strings(self):
        t, mock_stray = self._make_with_mock_stray()
        t.notify("", "")
        mock_stray.showMessage.assert_called_once()
        args = mock_stray.showMessage.call_args[0]
        assert args[0] == ""
        assert args[1] == ""

    def test_notify_multiple_calls(self):
        t, mock_stray = self._make_with_mock_stray()
        t.notify("A", "1")
        t.notify("B", "2")
        assert mock_stray.showMessage.call_count == 2


class TestSetTooltip:
    def _make_with_mock_stray(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon") as mock_cls:
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            mock_stray = MagicMock()
            mock_cls.return_value = mock_stray
            from transcrb.ui.tray import TrayIcon
            t = TrayIcon()
            return t, mock_stray

    def test_set_tooltip_calls_tray_set_tooltip(self):
        t, mock_stray = self._make_with_mock_stray()
        t.set_tooltip("Recording...")
        mock_stray.setToolTip.assert_called_with("Recording...")

    def test_set_tooltip_passes_exact_text(self):
        t, mock_stray = self._make_with_mock_stray()
        t.set_tooltip("idle")
        call_args = mock_stray.setToolTip.call_args_list
        assert call_args[-1] == call("idle")

    def test_set_tooltip_empty_string(self):
        t, mock_stray = self._make_with_mock_stray()
        t.set_tooltip("")
        mock_stray.setToolTip.assert_called_with("")

    def test_set_tooltip_unicode(self):
        t, mock_stray = self._make_with_mock_stray()
        t.set_tooltip("Запись...")
        mock_stray.setToolTip.assert_called_with("Запись...")

    def test_set_tooltip_multiple_calls_last_wins(self):
        t, mock_stray = self._make_with_mock_stray()
        t.set_tooltip("first")
        t.set_tooltip("second")
        call_args = mock_stray.setToolTip.call_args_list
        assert call_args[-1] == call("second")


class TestFallbackIcon:
    def test_fallback_icon_returns_qicon(self):
        from PySide6.QtGui import QIcon
        from transcrb.ui.tray import _fallback_icon
        icon = _fallback_icon()
        assert isinstance(icon, QIcon)

    def test_fallback_icon_not_null(self):
        from transcrb.ui.tray import _fallback_icon
        icon = _fallback_icon()
        assert not icon.isNull()

    def test_fallback_icon_deterministic(self):
        from transcrb.ui.tray import _fallback_icon
        icon1 = _fallback_icon()
        icon2 = _fallback_icon()
        assert not icon1.isNull()
        assert not icon2.isNull()

    def test_fallback_icon_has_pixmap(self):
        from transcrb.ui.tray import _fallback_icon
        icon = _fallback_icon()
        pm = icon.pixmap(64, 64)
        assert pm.width() == 64
        assert pm.height() == 64

    def test_fallback_icon_called_when_ico_missing(self):
        with patch("transcrb.ui.tray.resources_dir") as mock_rdir, \
             patch("transcrb.ui.tray.QSystemTrayIcon"), \
             patch("transcrb.ui.tray._fallback_icon", wraps=None) as mock_fb:
            from PySide6.QtGui import QIcon
            mock_fb.return_value = QIcon()
            mock_icon_file = MagicMock()
            mock_icon_file.exists.return_value = False
            mock_rdir.return_value.__truediv__ = lambda self, x: mock_icon_file
            from transcrb.ui.tray import TrayIcon
            TrayIcon()
            mock_fb.assert_called_once()
