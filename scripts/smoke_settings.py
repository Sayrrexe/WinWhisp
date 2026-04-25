"""Открывает окно настроек без запуска ASR/трея — для быстрой итерации UI."""
import sys

from PySide6.QtWidgets import QApplication

from transcrb.ui.settings_window import SettingsWindow


def main() -> int:
    app = QApplication(sys.argv)
    win = SettingsWindow(standalone=True)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
