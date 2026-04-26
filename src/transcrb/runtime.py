from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from transcrb.config import Config
from transcrb.text.vocab import Vocab


@dataclass
class HistoryEntry:
    when: datetime
    text: str
    duration_s: float


class HistoryStore:
    def __init__(self, path: Path | None = None, max_items: int = 200) -> None:
        self._path = path
        self._max = max_items
        self._items: deque[HistoryEntry] = deque(maxlen=max_items)
        self._listeners: list[Callable[[], None]] = []
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        loaded = [e for e in (self._parse_line(l) for l in lines[-self._max :]) if e is not None]
        loaded.sort(key=lambda e: e.when, reverse=True)
        self._items = deque(loaded, maxlen=self._max)

    @staticmethod
    def _parse_line(line: str) -> HistoryEntry | None:
        line = line.strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
            return HistoryEntry(
                datetime.fromisoformat(obj["when"]),
                str(obj.get("text", "")),
                float(obj.get("duration_s", 0.0)),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def add(self, text: str, duration_s: float) -> None:
        entry = HistoryEntry(datetime.now(), text.strip(), float(max(0.0, duration_s)))
        if not entry.text:
            return
        self._items.appendleft(entry)
        self._append_to_disk(entry)
        self._notify()

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass

    def _append_to_disk(self, entry: HistoryEntry) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                json.dump(
                    {
                        "when": entry.when.isoformat(timespec="milliseconds"),
                        "text": entry.text,
                        "duration_s": round(entry.duration_s, 2),
                    },
                    f,
                    ensure_ascii=False,
                )
                f.write("\n")
        except OSError:
            pass

    def all(self) -> list[HistoryEntry]:
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def subscribe(self, callback: Callable[[], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass


@dataclass
class AppRuntime:
    cfg: Config
    vocab: Vocab
    history: HistoryStore = field(default_factory=HistoryStore)
    state: str = "loading"
    model_loaded: bool = False
    started_at: float = field(default_factory=time.monotonic)

    def uptime_s(self) -> int:
        return max(0, int(time.monotonic() - self.started_at))
