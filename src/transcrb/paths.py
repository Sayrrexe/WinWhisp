import os
import shutil
import sys
from pathlib import Path


APP_NAME = "WinWhisp"


def appdata_dir() -> Path:
    base = os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Roaming")
    p = Path(base) / APP_NAME
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
