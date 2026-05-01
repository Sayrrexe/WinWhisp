from __future__ import annotations

import os
import sys
from types import ModuleType

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WinWhisp"


def _exe_path() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    return f'"{exe}" -m transcrb'


def _try_import_winreg() -> ModuleType | None:
    try:
        import winreg
    except ImportError:
        return None
    return winreg


def set_autostart(enabled: bool) -> None:
    winreg = _try_import_winreg()
    if winreg is None:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _exe_path())
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


def is_autostart_enabled() -> bool:
    winreg = _try_import_winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
