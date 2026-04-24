import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from transcrb.app import TranscrbApp


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _ = TranscrbApp()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
