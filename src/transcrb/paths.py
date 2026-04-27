import os
import shutil
import sys
from pathlib import Path


APP_NAME = "WinWhisp"
_OVERRIDE_FILENAME = ".dir_override"


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _default_appdata() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def _override_pointer() -> Path:
    return _default_appdata() / _OVERRIDE_FILENAME


def _read_override() -> Path | None:
    pointer = _override_pointer()
    if not pointer.exists():
        return None
    try:
        target = Path(pointer.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    if not target.is_absolute() or not target.exists():
        return None
    return target


def write_override(target: Path) -> None:
    _ensure_dir(_default_appdata())
    _override_pointer().write_text(str(target.resolve()), encoding="utf-8")


def clear_override() -> None:
    try:
        _override_pointer().unlink(missing_ok=True)
    except Exception:
        pass


def appdata_dir() -> Path:
    return _ensure_dir(_read_override() or _default_appdata())


def default_appdata_dir() -> Path:
    return _ensure_dir(_default_appdata())


def config_path() -> Path:
    return appdata_dir() / "config.yaml"


def vocab_path() -> Path:
    return appdata_dir() / "vocab.yaml"


def models_dir() -> Path:
    return _ensure_dir(appdata_dir() / "models")


def log_dir() -> Path:
    return _ensure_dir(appdata_dir() / "logs")


def resources_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "resources"
    return Path(__file__).resolve().parent.parent.parent / "resources"


def ffmpeg_path() -> Path | None:
    bundled = resources_dir() / "bin" / "ffmpeg.exe"
    if bundled.exists():
        return bundled
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    return None


def transcripts_dir() -> Path:
    docs_env = os.environ.get("USERPROFILE")
    home = Path(docs_env) if docs_env else Path.home()
    return _ensure_dir(home / "Documents" / APP_NAME / "transcripts")


def ensure_default(file: Path, default_source: Path) -> Path:
    if not file.exists() and default_source.exists():
        shutil.copyfile(default_source, file)
    return file
