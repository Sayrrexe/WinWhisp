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


signals = AppSignals()
