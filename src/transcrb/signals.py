from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    hotkey_pressed = Signal()
    hotkey_released = Signal()
    audio_started = Signal()
    audio_chunk = Signal(object)
    rms_updated = Signal(float, object)
    transcription_ready = Signal(str)
    error = Signal(str)
    state_changed = Signal(str)

    file_added = Signal(str)
    file_progress = Signal(str, int, int)
    file_paused = Signal(str, str)
    file_resumed = Signal(str)
    file_done = Signal(str, str)
    file_failed = Signal(str, str)
    file_removed = Signal(str)
    files_active_count = Signal(int)


signals = AppSignals()
