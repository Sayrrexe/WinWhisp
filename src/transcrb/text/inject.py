from __future__ import annotations

import time

import keyboard
import pyperclip
from loguru import logger


def _safe_get_clipboard() -> str | None:
    try:
        return pyperclip.paste()
    except Exception as e:
        logger.warning(f"clipboard read failed: {e}")
        return None


def _safe_set_clipboard(text: str) -> bool:
    try:
        pyperclip.copy(text)
        return True
    except Exception as e:
        logger.error(f"clipboard write failed: {e}")
        return False


def inject(
    text: str,
    paste_combo: str = "ctrl+v",
    pre_delay_ms: int = 20,
    post_delay_ms: int = 250,
    restore: bool = True,
) -> bool:
    if not text:
        return False
    old = _safe_get_clipboard() if restore else None
    if not _safe_set_clipboard(text):
        return False
    try:
        time.sleep(pre_delay_ms / 1000)
        keyboard.send(paste_combo)
        time.sleep(post_delay_ms / 1000)
        return True
    finally:
        if old is not None:
            _safe_set_clipboard(old)
