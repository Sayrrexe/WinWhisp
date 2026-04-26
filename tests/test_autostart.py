from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, call, patch


def _make_winreg_mock() -> MagicMock:
    m = MagicMock()
    m.HKEY_CURRENT_USER = 0x80000001
    m.KEY_SET_VALUE = 0x0002
    m.KEY_READ = 0x20019
    m.REG_SZ = 1
    m.OpenKey.return_value.__enter__ = lambda s, *a: MagicMock()
    m.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    return m


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WinWhisp"


# ---------------------------------------------------------------------------
# _exe_path
# ---------------------------------------------------------------------------


def test_exe_path_frozen_returns_quoted_executable():
    with patch.object(sys, "frozen", True, create=True), patch.object(
        sys, "executable", r"C:\App\winwhisp.exe"
    ):
        from importlib import reload
        import transcrb.autostart as m

        reload(m)
        result = m._exe_path()
        assert result == r'"C:\App\winwhisp.exe"'


def test_exe_path_dev_mode_includes_m_transcrb():
    with patch.object(sys, "executable", r"C:\Python\python.exe"):
        if hasattr(sys, "frozen"):
            del sys.frozen
        from importlib import reload
        import transcrb.autostart as m

        reload(m)
        result = m._exe_path()
        assert result == r'"C:\Python\python.exe" -m transcrb'


def test_exe_path_dev_mode_no_frozen_attribute():
    fake_sys = SimpleNamespace(executable=r"C:\Python\python.exe")
    with patch("transcrb.autostart.sys", fake_sys):
        import transcrb.autostart as m

        result = m._exe_path()
        assert "-m transcrb" in result
        assert "python.exe" in result


def test_exe_path_frozen_no_script_flag():
    fake_sys = SimpleNamespace(executable=r"C:\App\winwhisp.exe", frozen=True)
    with patch("transcrb.autostart.sys", fake_sys):
        import transcrb.autostart as m

        result = m._exe_path()
        assert "-m transcrb" not in result
        assert "winwhisp.exe" in result


def test_exe_path_result_is_always_quoted():
    fake_sys = SimpleNamespace(executable=r"C:\path with spaces\app.exe", frozen=True)
    with patch("transcrb.autostart.sys", fake_sys):
        import transcrb.autostart as m

        result = m._exe_path()
        assert result.startswith('"') and result.endswith('"')


# ---------------------------------------------------------------------------
# set_autostart(enabled=True)
# ---------------------------------------------------------------------------


def test_set_autostart_enable_calls_set_value_ex():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(True)

    winreg.SetValueEx.assert_called_once_with(
        key_handle, APP_NAME, 0, winreg.REG_SZ, m._exe_path()
    )


def test_set_autostart_enable_opens_correct_key():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(True)

    winreg.OpenKey.assert_called_once_with(
        winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
    )


def test_set_autostart_enable_does_not_call_delete_value():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(True)

    winreg.DeleteValue.assert_not_called()


def test_set_autostart_enable_idempotent_no_error():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(True)
        m.set_autostart(True)

    assert winreg.SetValueEx.call_count == 2


def test_set_autostart_no_winreg_import_returns_silently():
    with patch.dict("sys.modules", {"winreg": None}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(True)


# ---------------------------------------------------------------------------
# set_autostart(enabled=False)
# ---------------------------------------------------------------------------


def test_set_autostart_disable_calls_delete_value():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(False)

    winreg.DeleteValue.assert_called_once_with(key_handle, APP_NAME)


def test_set_autostart_disable_does_not_call_set_value_ex():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(False)

    winreg.SetValueEx.assert_not_called()


def test_set_autostart_disable_key_not_found_is_silent():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg.DeleteValue.side_effect = FileNotFoundError

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(False)


def test_set_autostart_disable_idempotent():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg.DeleteValue.side_effect = FileNotFoundError

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(False)
        m.set_autostart(False)

    assert winreg.DeleteValue.call_count == 2


def test_set_autostart_disable_no_winreg_returns_silently():
    with patch.dict("sys.modules", {"winreg": None}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.set_autostart(False)


# ---------------------------------------------------------------------------
# is_autostart_enabled
# ---------------------------------------------------------------------------


def test_is_autostart_enabled_true_when_value_present():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg.QueryValueEx.return_value = (r'"C:\App\winwhisp.exe"', 1)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        assert m.is_autostart_enabled() is True


def test_is_autostart_enabled_false_when_key_missing():
    winreg = _make_winreg_mock()
    winreg.OpenKey.side_effect = FileNotFoundError

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        assert m.is_autostart_enabled() is False


def test_is_autostart_enabled_false_when_value_missing():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg.QueryValueEx.side_effect = FileNotFoundError

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        assert m.is_autostart_enabled() is False


def test_is_autostart_enabled_false_when_empty_string():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg.QueryValueEx.return_value = ("", 1)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        assert m.is_autostart_enabled() is False


def test_is_autostart_enabled_opens_hkcu_run_key():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg.QueryValueEx.return_value = (r'"C:\App\winwhisp.exe"', 1)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.is_autostart_enabled()

    winreg.OpenKey.assert_called_once_with(
        winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ
    )


def test_is_autostart_enabled_false_when_no_winreg():
    with patch.dict("sys.modules", {"winreg": None}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        assert m.is_autostart_enabled() is False


def test_is_autostart_enabled_queries_app_name():
    winreg = _make_winreg_mock()
    key_handle = MagicMock()
    winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle)
    winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg.QueryValueEx.return_value = (r'"C:\App\winwhisp.exe"', 1)

    with patch.dict("sys.modules", {"winreg": winreg}):
        import importlib
        import transcrb.autostart as m

        importlib.reload(m)
        m.is_autostart_enabled()

    winreg.QueryValueEx.assert_called_once_with(key_handle, APP_NAME)


# ---------------------------------------------------------------------------
# round-trip: enable then check, disable then check
# ---------------------------------------------------------------------------


def test_enable_then_is_enabled_roundtrip():
    winreg_set = _make_winreg_mock()
    key_handle_set = MagicMock()
    winreg_set.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle_set)
    winreg_set.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    winreg_read = _make_winreg_mock()
    key_handle_read = MagicMock()
    winreg_read.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle_read)
    winreg_read.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    winreg_read.QueryValueEx.return_value = (r'"C:\App\winwhisp.exe"', 1)

    import importlib
    import transcrb.autostart as m

    with patch.dict("sys.modules", {"winreg": winreg_set}):
        importlib.reload(m)
        m.set_autostart(True)
    winreg_set.SetValueEx.assert_called_once()

    with patch.dict("sys.modules", {"winreg": winreg_read}):
        importlib.reload(m)
        assert m.is_autostart_enabled() is True


def test_disable_then_is_enabled_returns_false():
    winreg_set = _make_winreg_mock()
    key_handle_set = MagicMock()
    winreg_set.OpenKey.return_value.__enter__ = MagicMock(return_value=key_handle_set)
    winreg_set.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    winreg_read = _make_winreg_mock()
    winreg_read.OpenKey.side_effect = FileNotFoundError

    import importlib
    import transcrb.autostart as m

    with patch.dict("sys.modules", {"winreg": winreg_set}):
        importlib.reload(m)
        m.set_autostart(False)
    winreg_set.DeleteValue.assert_called_once()

    with patch.dict("sys.modules", {"winreg": winreg_read}):
        importlib.reload(m)
        assert m.is_autostart_enabled() is False
