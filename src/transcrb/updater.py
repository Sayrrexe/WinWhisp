from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from transcrb import __version__
from transcrb.config import UpdaterCfg
from transcrb.paths import appdata_dir


_API_TEMPLATE = "https://api.github.com/repos/{repo}/releases/latest"
_REQUEST_TIMEOUT_S = 10
_DOWNLOAD_TIMEOUT_S = 120
_INSTALLER_PATTERN = re.compile(r"setup.*\.exe$", re.IGNORECASE)
_INSTALLER_FLAGS = [
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
]


def _state_path() -> Path:
    return appdata_dir() / "update_state.json"


def _updates_dir() -> Path:
    p = appdata_dir() / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_state() -> dict:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"updater: failed to read state file: {e}")
        return {}


def _save_state(state: dict) -> None:
    p = _state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.debug(f"updater: failed to write state file: {e}")


def _format_exc(e: BaseException) -> str:
    parts: list[str] = []
    winerror = getattr(e, "winerror", None)
    if winerror is not None:
        parts.append(f"winerror={winerror}")
    errno = getattr(e, "errno", None)
    if errno is not None:
        parts.append(f"errno={errno}")
    reason = getattr(e, "reason", None)
    if reason is not None and reason is not e:
        parts.append(f"reason={_safe_str(reason)}")
    parts.append(_safe_str(e))
    return " ".join(p for p in parts if p)


def _safe_str(obj: object) -> str:
    for attr in ("strerror", "args"):
        val = getattr(obj, attr, None)
        if val is None:
            continue
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        if isinstance(val, tuple):
            for item in val:
                if isinstance(item, bytes):
                    return item.decode("utf-8", errors="replace")
                if isinstance(item, str) and item:
                    return item
    try:
        s = str(obj)
    except Exception:
        return repr(obj)
    if not s:
        return repr(obj)
    try:
        return s.encode("utf-8", errors="replace").decode("utf-8")
    except Exception:
        return repr(obj)


def _parse_version(s: str) -> tuple[int, int, int]:
    s = s.strip().lstrip("v").split("-")[0].split("+")[0]
    parts: list[int] = []
    for p in s.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def fetch_latest_release(repo: str) -> dict | None:
    url = _API_TEMPLATE.format(repo=repo)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"WinWhisp-Updater/{__version__}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_S) as resp:
            data = resp.read()
        return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info(f"updater: no releases yet for {repo}")
            return None
        logger.warning(f"updater: HTTP {e.code} from GitHub: {e.reason}")
        return None
    except Exception as e:
        detail = _format_exc(e)
        logger.warning(f"updater: fetch failed [{type(e).__name__}]: {detail}")
        return None


def find_installer_asset(release: dict) -> dict | None:
    assets = release.get("assets") or []
    for asset in assets:
        name = str(asset.get("name") or "")
        if _INSTALLER_PATTERN.search(name):
            return asset
    return None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


class UpdateChecker(QObject):
    update_available = Signal(str, dict)
    no_update = Signal(str)
    check_failed = Signal(str)

    def __init__(self, cfg: UpdaterCfg, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._spawn_check)
        self._busy = False
        self._latest_release: dict | None = None

    def start(self) -> None:
        if not self._cfg.enabled:
            logger.info("updater: disabled in config")
            return
        QTimer.singleShot(self._cfg.initial_delay_s * 1000, self._spawn_check)
        if self._cfg.check_interval_hours > 0:
            self._timer.start(self._cfg.check_interval_hours * 3600 * 1000)
        logger.info(
            f"updater: enabled, interval={self._cfg.check_interval_hours}h, repo={self._cfg.repo}"
        )

    def stop(self) -> None:
        self._timer.stop()

    def latest_release(self) -> dict | None:
        return self._latest_release

    def check_now(self, *, force_notify: bool = True) -> None:
        if self._busy:
            logger.info("updater: check already in progress")
            return
        self._busy = True
        threading.Thread(
            target=self._do_check, args=(force_notify,), daemon=True
        ).start()

    def _spawn_check(self) -> None:
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=self._do_check, args=(False,), daemon=True).start()

    def _do_check(self, force_notify: bool) -> None:
        try:
            release = fetch_latest_release(self._cfg.repo)
            if release is None:
                self.check_failed.emit("Не удалось получить данные о релизе.")
                return
            tag = str(release.get("tag_name") or "").strip()
            if not tag:
                self.check_failed.emit("Релиз без тега.")
                return
            if not is_newer(tag, __version__):
                logger.info(f"updater: up to date ({__version__} >= {tag})")
                self.no_update.emit(tag)
                return
            self._latest_release = release
            state = _load_state()
            already = state.get("last_notified") == tag
            if not already:
                state["last_notified"] = tag
                _save_state(state)
            if force_notify or not already:
                logger.info(f"updater: new release {tag} (current {__version__})")
                self.update_available.emit(tag, release)
            else:
                logger.info(f"updater: already notified about {tag}")
        finally:
            self._busy = False


class UpdateDownloader(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, asset: dict, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._asset = asset
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        url = str(self._asset.get("browser_download_url") or "")
        name = str(self._asset.get("name") or "WinWhisp-setup.exe")
        if not url:
            self.failed.emit("URL установщика не найден в релизе.")
            return

        target = _updates_dir() / name
        tmp = target.with_suffix(target.suffix + ".part")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"WinWhisp-Updater/{__version__}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_S) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                self.progress.emit(0, total)
                with open(tmp, "wb") as fh:
                    while True:
                        if self._cancelled:
                            break
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total)
        except Exception as e:
            logger.error(f"updater: download failed: {e}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            self.failed.emit(f"Скачивание не удалось: {e}")
            return

        if self._cancelled:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            self.failed.emit("Отменено")
            return

        try:
            target.unlink(missing_ok=True)
            tmp.rename(target)
        except Exception as e:
            logger.error(f"updater: rename failed: {e}")
            self.failed.emit(f"Не удалось сохранить файл: {e}")
            return

        logger.info(f"updater: downloaded installer to {target}")
        self.finished_ok.emit(str(target))


def launch_installer(
    installer_path: str | Path,
    relaunch_path: str | Path | None = None,
) -> None:
    p = Path(installer_path)
    if not p.exists():
        raise FileNotFoundError(f"installer not found: {p}")

    if os.name != "nt":
        args = [str(p), *_INSTALLER_FLAGS]
        logger.info(f"updater: launching installer {args}")
        subprocess.Popen(args, close_fds=True)
        return

    relaunch = Path(relaunch_path) if relaunch_path else None
    script_path = _write_installer_wrapper(p, relaunch)
    creationflags = (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    )
    logger.info(
        f"updater: launching installer wrapper {script_path} relaunch={relaunch}"
    )
    subprocess.Popen(
        ["cmd", "/c", "call", str(script_path)],
        close_fds=True,
        creationflags=creationflags,
    )


def _write_installer_wrapper(installer: Path, relaunch: Path | None) -> Path:
    script_path = _updates_dir() / "run_update.cmd"
    flags_line = " ".join(_INSTALLER_FLAGS)
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f'start "" /WAIT "{installer}" {flags_line}',
    ]
    if relaunch is not None:
        lines.append(f'if exist "{relaunch}" start "" "{relaunch}"')
    lines.append('(del "%~f0") >nul 2>&1')
    script_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return script_path
