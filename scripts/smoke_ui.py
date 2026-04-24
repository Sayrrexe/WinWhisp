"""Показывает pill-overlay на 2 секунды и закрывается. Проверка Qt UI без global-hotkey."""
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import numpy as np

from transcrb.config import OverlayCfg
from transcrb.ui.overlay import PillOverlay


def main():
    app = QApplication(sys.argv)
    ov = PillOverlay(OverlayCfg())
    ov.show_fade()
    def fake_level():
        bands = np.random.rand(10).astype(np.float32)
        ov.update_level(0.5, bands)
    tick = QTimer()
    tick.timeout.connect(fake_level)
    tick.start(50)
    QTimer.singleShot(2000, ov.hide_fade)
    QTimer.singleShot(2500, app.quit)
    print("overlay shown for 2s...")
    code = app.exec()
    print(f"exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
