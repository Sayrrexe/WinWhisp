import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from transcrb.config import load_config
from transcrb.paths import resources_dir

_SINGLETON_MUTEX_NAME = "WinWhisp-Singleton-{8d2c7f5a-3b71-4a4e-9e0f-7c4b1e1a0e1f}"
_singleton_handle = None


def _acquire_singleton_or_exit() -> None:
    global _singleton_handle
    if sys.platform != "win32":
        return
    try:
        import win32api
        import win32event
        import winerror
    except ImportError:
        return
    handle = win32event.CreateMutexW(None, False, _SINGLETON_MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        print("WinWhisp уже запущен — открой иконку в трее.", file=sys.stderr)
        sys.exit(0)
    _singleton_handle = handle


def main() -> int:
    _acquire_singleton_or_exit()

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    icon_file = resources_dir() / "icon.ico"
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

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
        wizard.raise_()
        wizard.activateWindow()
        return app.exec()

    from transcrb.app import TranscrbApp

    _ = TranscrbApp()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
