from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from transcrb.config import Config
from transcrb.runtime import AppRuntime, HistoryEntry, HistoryStore
from transcrb.text.vocab import Vocab


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _vocab() -> Vocab:
    return Vocab()


def _cfg() -> Config:
    return Config()


def _store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(path=tmp_path / "hist.jsonl")


def _entry(text: str = "hello", duration: float = 1.0) -> HistoryEntry:
    return HistoryEntry(when=datetime.now(), text=text, duration_s=duration)


# ---------------------------------------------------------------------------
# HistoryStore.__init__ / _load
# ---------------------------------------------------------------------------

def test_historystore_init_no_path_empty():
    s = HistoryStore(path=None)
    assert s.count() == 0
    assert s.all() == []


def test_historystore_init_missing_file_empty(tmp_path):
    s = HistoryStore(path=tmp_path / "missing.jsonl")
    assert s.count() == 0


def test_historystore_load_valid_jsonl(tmp_path):
    p = tmp_path / "h.jsonl"
    when = datetime(2024, 1, 15, 10, 0, 0)
    p.write_text(
        json.dumps({"when": when.isoformat(), "text": "foo", "duration_s": 2.5}) + "\n",
        encoding="utf-8",
    )
    s = HistoryStore(path=p)
    assert s.count() == 1
    assert s.all()[0].text == "foo"
    assert s.all()[0].duration_s == 2.5


def test_historystore_load_sorted_newest_first(tmp_path):
    p = tmp_path / "h.jsonl"
    older = datetime(2024, 1, 1, 0, 0, 0)
    newer = datetime(2024, 6, 1, 0, 0, 0)
    lines = [
        json.dumps({"when": older.isoformat(), "text": "old", "duration_s": 1.0}),
        json.dumps({"when": newer.isoformat(), "text": "new", "duration_s": 1.0}),
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = HistoryStore(path=p)
    assert s.all()[0].text == "new"
    assert s.all()[1].text == "old"


def test_historystore_load_skips_malformed_lines(tmp_path):
    p = tmp_path / "h.jsonl"
    good = json.dumps({"when": datetime(2024, 1, 1).isoformat(), "text": "ok", "duration_s": 0.0})
    p.write_text("not-json\n{broken}\n" + good + "\n", encoding="utf-8")
    s = HistoryStore(path=p)
    assert s.count() == 1
    assert s.all()[0].text == "ok"


def test_historystore_load_skips_blank_lines(tmp_path):
    p = tmp_path / "h.jsonl"
    good = json.dumps({"when": datetime(2024, 1, 1).isoformat(), "text": "ok", "duration_s": 0.0})
    p.write_text("\n   \n" + good + "\n\n", encoding="utf-8")
    s = HistoryStore(path=p)
    assert s.count() == 1


def test_historystore_load_respects_max_items(tmp_path):
    p = tmp_path / "h.jsonl"
    lines = [
        json.dumps({"when": datetime(2024, 1, i + 1).isoformat(), "text": f"t{i}", "duration_s": 0.0})
        for i in range(10)
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = HistoryStore(path=p, max_items=3)
    assert s.count() == 3


def test_historystore_load_oserror_silently_ignored(tmp_path, monkeypatch):
    p = tmp_path / "h.jsonl"
    p.write_text("x\n", encoding="utf-8")
    monkeypatch.setattr(Path, "read_text", lambda *a, **kw: (_ for _ in ()).throw(OSError("perm")))
    s = HistoryStore(path=p)
    assert s.count() == 0


def test_historystore_load_missing_when_key_skipped(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text(json.dumps({"text": "no-when", "duration_s": 0.0}) + "\n", encoding="utf-8")
    s = HistoryStore(path=p)
    assert s.count() == 0


# ---------------------------------------------------------------------------
# HistoryStore.add
# ---------------------------------------------------------------------------

def test_historystore_add_increments_count(tmp_path):
    s = _store(tmp_path)
    s.add("hello", 1.0)
    assert s.count() == 1


def test_historystore_add_newest_first():
    s = HistoryStore(path=None)
    s.add("first", 1.0)
    s.add("second", 1.0)
    items = s.all()
    assert items[0].text == "second"
    assert items[1].text == "first"


def test_historystore_add_empty_text_ignored():
    s = HistoryStore(path=None)
    s.add("", 1.0)
    s.add("   ", 1.0)
    assert s.count() == 0


def test_historystore_add_strips_whitespace():
    s = HistoryStore(path=None)
    s.add("  hello  ", 1.0)
    assert s.all()[0].text == "hello"


def test_historystore_add_negative_duration_clamped_to_zero():
    s = HistoryStore(path=None)
    s.add("text", -5.0)
    assert s.all()[0].duration_s == 0.0


def test_historystore_add_writes_to_disk(tmp_path):
    p = tmp_path / "h.jsonl"
    s = HistoryStore(path=p)
    s.add("disk test", 3.0)
    content = p.read_text(encoding="utf-8")
    obj = json.loads(content.strip())
    assert obj["text"] == "disk test"
    assert obj["duration_s"] == 3.0


def test_historystore_add_appends_multiple_lines(tmp_path):
    p = tmp_path / "h.jsonl"
    s = HistoryStore(path=p)
    s.add("one", 1.0)
    s.add("two", 2.0)
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2


def test_historystore_add_respects_max_items():
    s = HistoryStore(path=None, max_items=3)
    for i in range(5):
        s.add(f"item{i}", 1.0)
    assert s.count() == 3


def test_historystore_add_fires_listeners():
    s = HistoryStore(path=None)
    fired = []
    s.subscribe(lambda: fired.append(1))
    s.add("hello", 1.0)
    assert fired == [1]


def test_historystore_add_fires_multiple_listeners():
    s = HistoryStore(path=None)
    a, b = [], []
    s.subscribe(lambda: a.append(1))
    s.subscribe(lambda: b.append(1))
    s.add("x", 1.0)
    assert a == [1]
    assert b == [1]


def test_historystore_add_listener_exception_does_not_propagate():
    s = HistoryStore(path=None)
    def bad():
        raise RuntimeError("boom")
    s.subscribe(bad)
    s.add("safe", 1.0)
    assert s.count() == 1


def test_historystore_add_no_path_no_crash():
    s = HistoryStore(path=None)
    s.add("no path", 1.0)
    assert s.count() == 1


def test_historystore_add_disk_oserror_silently_ignored(tmp_path, monkeypatch):
    p = tmp_path / "h.jsonl"
    s = HistoryStore(path=p)
    import builtins
    real_open = builtins.open
    def failing_open(file, mode="r", **kwargs):
        if "a" in mode and str(p) in str(file):
            raise OSError("disk full")
        return real_open(file, mode, **kwargs)
    monkeypatch.setattr(builtins, "open", failing_open)
    s.add("will fail silently", 1.0)
    assert s.count() == 1


# ---------------------------------------------------------------------------
# HistoryStore._append_to_disk
# ---------------------------------------------------------------------------

def test_append_to_disk_creates_parent_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "h.jsonl"
    s = HistoryStore(path=nested)
    s.add("nested", 1.0)
    assert nested.exists()


def test_append_to_disk_json_fields_complete(tmp_path):
    p = tmp_path / "h.jsonl"
    s = HistoryStore(path=p)
    s.add("check fields", 2.71)
    obj = json.loads(p.read_text(encoding="utf-8").strip())
    assert set(obj.keys()) == {"when", "text", "duration_s"}


def test_append_to_disk_duration_rounded_to_two_decimals(tmp_path):
    p = tmp_path / "h.jsonl"
    s = HistoryStore(path=p)
    s.add("rounding", 1.23456789)
    obj = json.loads(p.read_text(encoding="utf-8").strip())
    assert obj["duration_s"] == round(1.23456789, 2)


def test_append_to_disk_unicode_preserved(tmp_path):
    p = tmp_path / "h.jsonl"
    s = HistoryStore(path=p)
    s.add("Привет мир", 1.0)
    text = p.read_text(encoding="utf-8")
    assert "Привет мир" in text


def test_append_to_disk_noop_when_path_is_none():
    s = HistoryStore(path=None)
    entry = _entry("no write")
    s._append_to_disk(entry)


# ---------------------------------------------------------------------------
# HistoryStore.all / count
# ---------------------------------------------------------------------------

def test_historystore_all_returns_copy_not_internal_ref():
    s = HistoryStore(path=None)
    s.add("a", 1.0)
    lst = s.all()
    lst.clear()
    assert s.count() == 1


def test_historystore_count_zero_on_empty():
    s = HistoryStore(path=None)
    assert s.count() == 0


def test_historystore_all_order_preserved_after_reload(tmp_path):
    p = tmp_path / "h.jsonl"
    older = datetime(2024, 1, 1, 10, 0, 0)
    newer = datetime(2024, 1, 2, 10, 0, 0)
    lines = [
        json.dumps({"when": older.isoformat(), "text": "alpha", "duration_s": 1.0}),
        json.dumps({"when": newer.isoformat(), "text": "beta", "duration_s": 2.0}),
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = HistoryStore(path=p)
    texts = [e.text for e in s.all()]
    assert texts[0] == "beta"
    assert texts[1] == "alpha"


# ---------------------------------------------------------------------------
# HistoryStore.subscribe / unsubscribe
# ---------------------------------------------------------------------------

def test_subscribe_duplicate_ignored():
    s = HistoryStore(path=None)
    cb = MagicMock()
    s.subscribe(cb)
    s.subscribe(cb)
    s.add("x", 1.0)
    assert cb.call_count == 1


def test_unsubscribe_stops_notifications():
    s = HistoryStore(path=None)
    cb = MagicMock()
    s.subscribe(cb)
    s.unsubscribe(cb)
    s.add("x", 1.0)
    cb.assert_not_called()


def test_unsubscribe_nonexistent_no_error():
    s = HistoryStore(path=None)
    cb = MagicMock()
    s.unsubscribe(cb)


def test_subscribe_then_add_fires_on_each_add():
    s = HistoryStore(path=None)
    fired = []
    s.subscribe(lambda: fired.append(1))
    s.add("a", 1.0)
    s.add("b", 1.0)
    assert len(fired) == 2


def test_unsubscribe_one_of_two_listeners():
    s = HistoryStore(path=None)
    a, b = [], []
    cb_a = lambda: a.append(1)
    cb_b = lambda: b.append(1)
    s.subscribe(cb_a)
    s.subscribe(cb_b)
    s.unsubscribe(cb_a)
    s.add("x", 1.0)
    assert a == []
    assert b == [1]


# ---------------------------------------------------------------------------
# HistoryEntry
# ---------------------------------------------------------------------------

def test_historyentry_fields():
    now = datetime.now()
    e = HistoryEntry(when=now, text="entry", duration_s=3.14)
    assert e.when is now
    assert e.text == "entry"
    assert e.duration_s == 3.14


def test_historyentry_dataclass_equality():
    now = datetime(2024, 1, 1)
    e1 = HistoryEntry(when=now, text="x", duration_s=1.0)
    e2 = HistoryEntry(when=now, text="x", duration_s=1.0)
    assert e1 == e2


# ---------------------------------------------------------------------------
# AppRuntime
# ---------------------------------------------------------------------------

def test_appruntime_initial_state():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab())
    assert rt.state == "loading"
    assert rt.model_loaded is False


def test_appruntime_uptime_non_negative():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab())
    assert rt.uptime_s() >= 0


def test_appruntime_uptime_increases():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab(), started_at=time.monotonic() - 5.0)
    assert rt.uptime_s() >= 5


def test_appruntime_uptime_clamped_at_zero_for_future_start():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab(), started_at=time.monotonic() + 9999.0)
    assert rt.uptime_s() == 0


def test_appruntime_default_history_store():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab())
    assert isinstance(rt.history, HistoryStore)
    assert rt.history.count() == 0


def test_appruntime_custom_history_store(tmp_path):
    hs = HistoryStore(path=tmp_path / "h.jsonl")
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab(), history=hs)
    assert rt.history is hs


def test_appruntime_state_mutable():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab())
    rt.state = "idle"
    assert rt.state == "idle"


def test_appruntime_model_loaded_mutable():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab())
    rt.model_loaded = True
    assert rt.model_loaded is True


def test_appruntime_cfg_and_vocab_stored():
    cfg = _cfg()
    vocab = _vocab()
    rt = AppRuntime(cfg=cfg, vocab=vocab)
    assert rt.cfg is cfg
    assert rt.vocab is vocab


def test_appruntime_uptime_integer_type():
    rt = AppRuntime(cfg=_cfg(), vocab=_vocab())
    assert isinstance(rt.uptime_s(), int)
