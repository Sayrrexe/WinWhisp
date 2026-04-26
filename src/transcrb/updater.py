from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal

from transcrb import __version__
from transcrb.config import UpdaterCfg
from transcrb.paths import appdata_dir


_API_TEMPLATE = "https://api.github.com/repos/{repo}/releases/latest"
_REQUEST_TIMEOUT_S = 10


def _state_path() -> Path:
    return appdata_dir() / "update_state.json"


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
            logger.debug(f"updater: no releases yet for {repo}")
            return None
        logger.debug(f"updater: HTTP {e.code} from GitHub: {e.reason}")
        return None
    except Exception as e:
        logger.debug(f"updater: fetch failed: {e}")
        return None


class UpdateChecker(QObject):
    update_available = Signal(str, str)

    def __init__(self, cfg: UpdaterCfg, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cfg = cfg
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._spawn_check)
        self._busy = False
        self._latest_seen: tuple[str, str] | None = None

    def start(self) -> None:
        if not self._cfg.enabled:
            logger.info("updater: disabled in config")
            return
        if self._cfg.check_interval_hours <= 0:
            logger.info("updater: interval <= 0, disabled")
            return
        QTimer.singleShot(self._cfg.initial_delay_s * 1000, self._spawn_check)
        self._timer.start(self._cfg.check_interval_hours * 3600 * 1000)
        logger.info(
            f"updater: enabled, interval={self._cfg.check_interval_hours}h, repo={self._cfg.repo}"
        )

    def stop(self) -> None:
        self._timer.stop()

    def latest(self) -> tuple[str, str] | None:
        return self._latest_seen

    def _spawn_check(self) -> None:
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self) -> None:
        try:
            release = fetch_latest_release(self._cfg.repo)
            if not release:
                return
            tag = str(release.get("tag_name") or "").strip()
            url = str(release.get("html_url") or "").strip()
            if not tag:
                return
            if not is_newer(tag, __version__):
                logger.debug(f"updater: up to date ({__version__} >= {tag})")
                return
            state = _load_state()
            if state.get("last_notified") == tag:
                self._latest_seen = (tag, url)
                logger.debug(f"updater: already notified about {tag}")
                return
            state["last_notified"] = tag
            _save_state(state)
            self._latest_seen = (tag, url)
            logger.info(f"updater: new release {tag} (current {__version__})")
            self.update_available.emit(tag, url)
        finally:
            self._busy = False
