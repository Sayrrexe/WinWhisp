import os
import shutil
import sys
from pathlib import Path


APP_NAME = "WinWhisp"
_OVERRIDE_FILENAME = ".dir_override"


def _default_appdata() -> Path:
    base = os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def _read_override() -> Path | None:
    pointer = _default_appdata() / _OVERRIDE_FILENAME
    if not pointer.exists():
        return None
    try:
        target = Path(pointer.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    if not target.is_absolute():
        return None
    if not target.exists():
        return None
    return target


def write_override(target: Path) -> None:
    default = _default_appdata()
    default.mkdir(parents=True, exist_ok=True)
    pointer = default / _OVERRIDE_FILENAME
    pointer.write_text(str(target.resolve()), encoding="utf-8")


def clear_override() -> None:
    pointer = _default_appdata() / _OVERRIDE_FILENAME
    if pointer.exists():
        try:
            pointer.unlink()
        except Exception:
            pass


def appdata_dir() -> Path:
    target = _read_override() or _default_appdata()
    target.mkdir(parents=True, exist_ok=True)
    return target


def default_appdata_dir() -> Path:
    p = _default_appdata()
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_path() -> Path:
    return appdata_dir() / "config.yaml"


def vocab_path() -> Path:
    return appdata_dir() / "vocab.yaml"


def models_dir() -> Path:
    p = appdata_dir() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_dir() -> Path:
    p = appdata_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resources_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "resources"
    return Path(__file__).resolve().parent.parent.parent / "resources"


def ensure_default(file: Path, default_source: Path) -> Path:
    if not file.exists() and default_source.exists():
        shutil.copyfile(default_source, file)
    return file
