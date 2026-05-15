import ctypes
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from transcrb.config import load_config
from transcrb.paths import resources_dir

_SINGLETON_MUTEX_NAME = "WinWhisp-Singleton-{8d2c7f5a-3b71-4a4e-9e0f-7c4b1e1a0e1f}"
_ERROR_ALREADY_EXISTS = 183
_singleton_handle = None


def _acquire_singleton_or_exit() -> None:
    global _singleton_handle
    if sys.platform != "win32":
        return
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.GetLastError.restype = ctypes.c_uint32
    handle = kernel32.CreateMutexW(None, False, _SINGLETON_MUTEX_NAME)
    last_error = kernel32.GetLastError()
    if not handle:
        return
    if last_error == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
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
