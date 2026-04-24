from __future__ import annotations

import time

import keyboard
from loguru import logger
from PySide6.QtCore import QObject, Signal


class HotkeyBridge(QObject):
    pressed = Signal()
    released = Signal()

    def __init__(self, combo: str, debounce_ms: int = 150) -> None:
        super().__init__()
        self._combo = combo.strip().lower()
        self._combo_keys = {k.strip() for k in self._combo.split("+") if k.strip()}
        self._single_key = next(iter(self._combo_keys)) if len(self._combo_keys) == 1 else None
        self._down = False
        self._last_release = 0.0
        self._debounce_s = debounce_ms / 1000
        self._hook = None

    def start(self) -> None:
        if self._hook is not None:
            return
        self._hook = keyboard.hook(self._on_event)
        logger.info(f"hotkey registered: {self._combo}")

    def stop(self) -> None:
        if self._hook is None:
            return
        try:
            keyboard.unhook(self._hook)
        except Exception as e:
            logger.debug(f"unhook error: {e}")
        self._hook = None

    def _on_event(self, e) -> None:
        if self._single_key is not None:
            self._handle_single(e)
        else:
            self._handle_combo(e)

    def _handle_single(self, e) -> None:
        name = (getattr(e, "name", "") or "").lower()
        if name != self._single_key:
            return
        ev = getattr(e, "event_type", None)
        if ev == "down":
            if self._down:
                return
            if (time.monotonic() - self._last_release) < self._debounce_s:
                return
            self._down = True
            self.pressed.emit()
        elif ev == "up":
            if not self._down:
                return
            self._down = False
            self._last_release = time.monotonic()
            self.released.emit()

    def _handle_combo(self, e) -> None:
        all_down = all(keyboard.is_pressed(k) for k in self._combo_keys)
        if all_down and not self._down:
            if (time.monotonic() - self._last_release) < self._debounce_s:
                return
            self._down = True
            self.pressed.emit()
        elif not all_down and self._down:
            self._down = False
            self._last_release = time.monotonic()
            self.released.emit()
