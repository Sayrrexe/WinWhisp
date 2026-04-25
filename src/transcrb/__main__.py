import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from transcrb.config import load_config


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    cfg = load_config()

    if not cfg.onboarded:
        from transcrb.ui.onboarding import OnboardingWindow

        holder: dict[str, object] = {}

        def on_completed() -> None:
            from transcrb.app import TranscrbApp

            holder["app"] = TranscrbApp()

        def on_cancelled() -> None:
            holder["cancelled"] = True
            app.exit(1)

        wizard = OnboardingWindow(cfg)
        wizard.completed.connect(on_completed)
        wizard.cancelled.connect(on_cancelled)
        wizard.show()
        return app.exec()

    from transcrb.app import TranscrbApp

    _ = TranscrbApp()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
