from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import keyboard
import pyperclip
from loguru import logger

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

_ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    )


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    )


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _INPUT_UNION(ctypes.Union):
    _fields_ = (("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT))


class _INPUT(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("u", _INPUT_UNION))


try:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _SendInput = _user32.SendInput
    _SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    _SendInput.restype = wintypes.UINT
except (OSError, AttributeError):
    _SendInput = None


def _safe_set_clipboard(text: str) -> bool:
    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        logger.error(f"clipboard write failed: {e}")
        return False


def _unicode_inputs(text: str) -> list[_INPUT]:
    inputs: list[_INPUT] = []
    for ch in text:
        code = ord(ch)
        if code > 0xFFFF:
            code -= 0x10000
            units = (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF))
        else:
            units = (code,)
        for unit in units:
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                ki = _KEYBDINPUT(0, unit, flags, 0, 0)
                inputs.append(_INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=ki)))
    return inputs


def type_unicode(text: str, *, pre_delay_ms: int = 0, post_delay_ms: int = 0) -> bool:
    if not text:
        return False
    if _SendInput is None:
        logger.error("SendInput unavailable, cannot type unicode")
        return False
    inputs = _unicode_inputs(text)
    if not inputs:
        return False
    if pre_delay_ms:
        time.sleep(pre_delay_ms / 1000)
    arr = (_INPUT * len(inputs))(*inputs)
    sent = _SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))
    if sent != len(inputs):
        err = ctypes.get_last_error()
        logger.warning(f"SendInput sent {sent}/{len(inputs)} (err={err})")
    if post_delay_ms:
        time.sleep(post_delay_ms / 1000)
    return sent > 0


def inject(
    text: str,
    paste_combo: str = "ctrl+v",
    pre_delay_ms: int = 20,
    post_delay_ms: int = 250,
) -> bool:
    if not text:
        return False
    if not _safe_set_clipboard(text):
        return False
    time.sleep(pre_delay_ms / 1000)
    keyboard.send(paste_combo)
    time.sleep(post_delay_ms / 1000)
    return True
