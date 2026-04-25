"""Открывает окно онбординга без скачивания модели — для итерации UI."""
import sys

from PySide6.QtWidgets import QApplication

from transcrb.config import Config
from transcrb.ui.onboarding import OnboardingWindow


def main() -> int:
    app = QApplication(sys.argv)
    cfg = Config()
    win = OnboardingWindow(cfg)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
