from __future__ import annotations

import queue
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import Qt

from transcrb.config import AsrCfg
from transcrb.text.vocab import Vocab
from transcrb.asr.worker import AsrWorker, _Prepare, _Reload, _PREPARE, _RELOAD, _Request


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cfg():
    return AsrCfg(idle_unload_s=60)


@pytest.fixture()
def vocab():
    return Vocab(
        hotwords=["pytest", "Django"],
        replacements={"пул реквест": "pull request"},
        hallucinations=[],
    )


def _fake_engine(transcribe_return="result text", loaded=True):
    eng = MagicMock()
    eng.is_loaded.return_value = loaded
    eng.load.return_value = None
    eng.warmup.return_value = None
    eng.transcribe.return_value = transcribe_return
    eng.unload.return_value = None
    return eng


_created_workers: list[AsrWorker] = []


def _make_worker(cfg=None, vocab=None, trailing_space=False):
    cfg = cfg or AsrCfg(idle_unload_s=60)
    vocab = vocab or Vocab()
    with patch("transcrb.asr.worker.WhisperEngine"):
        w = AsrWorker(cfg, vocab, trailing_space=trailing_space)
    _created_workers.append(w)
    return w


@pytest.fixture(autouse=True)
def _cleanup_workers():
    yield
    for w in _created_workers:
        try:
            t = getattr(w, "_thread", None)
            if t is not None:
                if t.isRunning():
                    t.quit()
                    t.wait(2000)
                t.deleteLater()
        except Exception:
            pass
    _created_workers.clear()


def _drive_run(worker, messages):
    q = MagicMock()
    q.get.side_effect = messages
    worker._queue = q
    worker._run()


def _collect(signal):
    seen = []
    signal.connect(seen.append, Qt.ConnectionType.DirectConnection)
    return seen


def _collect_void(signal):
    seen = []
    signal.connect(lambda: seen.append(True), Qt.ConnectionType.DirectConnection)
    return seen


# ---------------------------------------------------------------------------
# _is_prompt_echo
# ---------------------------------------------------------------------------

class TestIsPromptEcho:
    def test_empty_prompt_always_false(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = ""
        assert w._is_prompt_echo("это техническая диктовка по программированию") is False

    def test_empty_raw_false(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "non-empty"
        assert w._is_prompt_echo("") is False

    def test_whitespace_only_raw_false(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "non-empty"
        assert w._is_prompt_echo("   ") is False

    def test_default_prefix_match(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "non-empty"
        assert w._is_prompt_echo("это техническая диктовка по программированию") is True

    def test_log_artifact_caught(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "non-empty"
        assert w._is_prompt_echo("Используются термины по программированию.") is True

    def test_unrelated_text_false(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "non-empty"
        assert w._is_prompt_echo("привет как дела сегодня утром") is False

    def test_none_raw_treated_as_empty(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "non-empty"
        assert w._is_prompt_echo(None) is False


# ---------------------------------------------------------------------------
# _ensure_loaded
# ---------------------------------------------------------------------------

class TestEnsureLoaded:
    def test_returns_true_when_already_loaded(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=True)
        w._engine = eng
        with patch("transcrb.asr.worker.WhisperEngine"):
            result = w._ensure_loaded()
        assert result is True
        eng.load.assert_not_called()

    def test_creates_engine_when_none(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._engine = None
        eng = _fake_engine(loaded=False)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng) as MockEng:
            result = w._ensure_loaded()
        assert result is True
        MockEng.assert_called_once_with(cfg)
        eng.load.assert_called_once()
        eng.warmup.assert_called_once()

    def test_emits_loaded_signal_on_success(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._engine = None
        eng = _fake_engine(loaded=False)
        seen = _collect_void(w.loaded)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            w._ensure_loaded()
        assert seen == [True]

    def test_returns_false_on_load_exception(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._engine = None
        eng = _fake_engine()
        eng.load.side_effect = RuntimeError("CUDA gone")
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            result = w._ensure_loaded()
        assert result is False
        assert w._engine is None

    def test_emits_error_signal_on_load_exception(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._engine = None
        eng = _fake_engine()
        eng.load.side_effect = RuntimeError("exploded")
        errors = _collect(w.error)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            w._ensure_loaded()
        assert len(errors) == 1
        assert "exploded" in errors[0]

    def test_rebuilds_prompts_after_load(self, cfg):
        vocab_with_hotwords = Vocab(hotwords=["pytest", "Django"])
        w = _make_worker(cfg, vocab_with_hotwords)
        w._engine = None
        w._initial_prompt = ""
        w._hotwords = ""
        eng = _fake_engine(loaded=False)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            w._ensure_loaded()
        assert w._initial_prompt != ""
        assert w._hotwords != ""

    def test_no_double_load_if_engine_is_loaded(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=True)
        w._engine = eng
        with patch("transcrb.asr.worker.WhisperEngine"):
            w._ensure_loaded()
            w._ensure_loaded()
        assert eng.load.call_count == 0

    def test_engine_set_to_none_on_load_failure(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._engine = None
        eng = _fake_engine()
        eng.load.side_effect = OSError("disk error")
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            w._ensure_loaded()
        assert w._engine is None


# ---------------------------------------------------------------------------
# _run — queue dispatch logic
# ---------------------------------------------------------------------------

class TestRunQueue:
    def test_none_message_stops_run(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=False)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [None])

    def test_prepare_triggers_ensure_loaded(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=False)
        loaded_calls = _collect_void(w.loaded)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_PREPARE, None])
        assert loaded_calls.count(True) >= 1

    def test_request_emits_ready_signal(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(transcribe_return="привет мир", loaded=False)
        results = _collect(w.ready)
        audio = np.zeros(16000, dtype=np.float32)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_Request(audio), None])
        assert len(results) == 1
        assert results[0] != ""

    def test_hallucination_emits_empty_ready(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(transcribe_return="Спасибо за просмотр.", loaded=False)
        results = _collect(w.ready)
        audio = np.zeros(16000, dtype=np.float32)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_Request(audio), None])
        assert results == [""]

    def test_prompt_echo_emits_empty_ready(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "это техническая диктовка по программированию."
        eng = _fake_engine(
            transcribe_return="это техническая диктовка по программированию",
            loaded=True,
        )
        w._engine = eng
        results = _collect(w.ready)
        audio = np.zeros(16000, dtype=np.float32)
        q = MagicMock()
        q.get.side_effect = [_Request(audio), None]
        w._queue = q
        with patch("transcrb.asr.worker.WhisperEngine"):
            w._run()
        assert results == [""]

    def test_transcribe_exception_emits_error_and_continues(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=False)
        eng.transcribe.side_effect = [RuntimeError("boom"), "нормальный текст"]
        errors = _collect(w.error)
        results = _collect(w.ready)
        audio = np.zeros(16000, dtype=np.float32)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_Request(audio), _Request(audio), None])
        assert len(errors) == 1
        assert "boom" in errors[0]
        assert len(results) == 1

    def test_idle_timeout_unloads_engine_and_emits(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=True)
        w._engine = eng
        unloaded = _collect_void(w.unloaded)
        q = MagicMock()
        q.get.side_effect = [queue.Empty, None]
        w._queue = q
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            w._run()
        eng.unload.assert_called_once()
        assert unloaded == [True]

    def test_idle_timeout_no_unload_if_not_loaded(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=False)
        unloaded = _collect_void(w.unloaded)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            eng.is_loaded.return_value = False
            q = MagicMock()
            q.get.side_effect = [queue.Empty, None]
            w._queue = q
            w._run()
        assert unloaded == []

    def test_reload_message_unloads_and_nulls_engine(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=True)
        w._engine = eng
        unloaded = _collect_void(w.unloaded)
        q = MagicMock()
        q.get.side_effect = [_RELOAD, None]
        w._queue = q
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            w._run()
        eng.unload.assert_called()
        assert unloaded == [True]
        assert w._engine is None

    def test_reload_message_no_crash_when_no_engine(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=False)
        w._engine = None
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_RELOAD, None])

    def test_run_exits_immediately_on_initial_load_failure(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine()
        eng.load.side_effect = RuntimeError("no GPU")
        w._engine = None
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            q = MagicMock()
            q.get.side_effect = [None]
            w._queue = q
            w._run()
        q.get.assert_not_called()

    def test_trailing_space_appended_to_result(self, cfg, vocab):
        w = _make_worker(cfg, vocab, trailing_space=True)
        eng = _fake_engine(transcribe_return="hello world", loaded=False)
        results = _collect(w.ready)
        audio = np.zeros(16000, dtype=np.float32)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_Request(audio), None])
        assert len(results) == 1
        assert results[0].endswith(" ")

    def test_multiple_requests_processed_sequentially(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=False)
        eng.transcribe.side_effect = ["первый", "второй", "третий"]
        results = _collect(w.ready)
        audio = np.zeros(16000, dtype=np.float32)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_Request(audio), _Request(audio), _Request(audio), None])
        assert len(results) == 3

    def test_loaded_signal_not_emitted_for_already_loaded_engine(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=True)
        w._engine = eng
        loaded_calls = _collect_void(w.loaded)
        audio = np.zeros(16000, dtype=np.float32)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_Request(audio), _Request(audio), None])
        assert loaded_calls.count(True) == 0

    def test_reload_followed_by_request_reloads_engine(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=True)
        w._engine = eng
        loaded_calls = _collect_void(w.loaded)
        fresh_eng = _fake_engine(loaded=False)
        audio = np.zeros(16000, dtype=np.float32)
        q = MagicMock()
        q.get.side_effect = [_RELOAD, _Request(audio), None]
        w._queue = q
        with patch("transcrb.asr.worker.WhisperEngine", return_value=fresh_eng):
            w._run()
        assert loaded_calls.count(True) == 1

    def test_error_signal_message_contains_exception_text(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        eng = _fake_engine(loaded=False)
        eng.transcribe.side_effect = ValueError("unexpected value 42")
        errors = _collect(w.error)
        audio = np.zeros(16000, dtype=np.float32)
        with patch("transcrb.asr.worker.WhisperEngine", return_value=eng):
            _drive_run(w, [_Request(audio), None])
        assert any("42" in e for e in errors)


# ---------------------------------------------------------------------------
# Public API: submit, prepare, request_reload, update_vocab, start, stop
# ---------------------------------------------------------------------------

class TestPublicApi:
    def test_submit_puts_request_in_queue(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        audio = np.zeros(800, dtype=np.float32)
        w.submit(audio)
        item = w._queue.get_nowait()
        assert isinstance(item, _Request)
        np.testing.assert_array_equal(item.audio, audio)

    def test_prepare_puts_prepare_sentinel(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w.prepare()
        item = w._queue.get_nowait()
        assert isinstance(item, _Prepare)

    def test_request_reload_puts_reload_sentinel(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w.request_reload()
        item = w._queue.get_nowait()
        assert isinstance(item, _Reload)

    def test_stop_puts_none_sentinel(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        mock_thread = MagicMock()
        w._thread = mock_thread
        w.stop()
        item = w._queue.get_nowait()
        assert item is None
        mock_thread.quit.assert_called_once()
        mock_thread.wait.assert_called_once_with(3000)

    def test_start_calls_thread_start(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        mock_thread = MagicMock()
        w._thread = mock_thread
        w.start()
        mock_thread.start.assert_called_once()

    def test_update_vocab_replaces_vocab_reference(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        new_vocab = Vocab(hotwords=["kubernetes", "terraform"])
        w.update_vocab(new_vocab)
        assert w._vocab is new_vocab

    def test_update_vocab_rebuilds_prompts(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = ""
        w._hotwords = ""
        new_vocab = Vocab(hotwords=["kubernetes", "terraform", "ansible"])
        w.update_vocab(new_vocab)
        assert w._initial_prompt != ""
        assert w._hotwords != ""

    def test_update_vocab_clears_prompts_if_no_hotwords(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        w._initial_prompt = "some old prompt"
        w._hotwords = "word1 word2"
        w.update_vocab(Vocab())
        assert w._initial_prompt == ""
        assert w._hotwords == ""

    def test_submit_multiple_items_preserves_order(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        a1 = np.ones(100, dtype=np.float32)
        a2 = np.zeros(100, dtype=np.float32)
        w.submit(a1)
        w.submit(a2)
        item1 = w._queue.get_nowait()
        item2 = w._queue.get_nowait()
        np.testing.assert_array_equal(item1.audio, a1)
        np.testing.assert_array_equal(item2.audio, a2)

    def test_initial_queue_empty(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        assert w._queue.empty()


# ---------------------------------------------------------------------------
# _rebuild_prompts
# ---------------------------------------------------------------------------

class TestRebuildPrompts:
    def test_hotwords_produce_nonempty_prompt(self, cfg):
        w = _make_worker(cfg, Vocab(hotwords=["pytest", "Flask"]))
        w._rebuild_prompts()
        assert w._initial_prompt != ""
        assert w._hotwords != ""

    def test_no_hotwords_produces_empty_strings(self, cfg):
        w = _make_worker(cfg, Vocab())
        w._rebuild_prompts()
        assert w._initial_prompt == ""
        assert w._hotwords == ""

    def test_hotwords_string_contains_all_words(self, cfg):
        words = ["pytest", "Django", "Flask"]
        w = _make_worker(cfg, Vocab(hotwords=words))
        w._rebuild_prompts()
        for word in words:
            assert word in w._hotwords

    def test_prompt_ends_with_period(self, cfg):
        w = _make_worker(cfg, Vocab(hotwords=["pytest"]))
        w._rebuild_prompts()
        assert w._initial_prompt.endswith(".")

    def test_rebuild_is_idempotent(self, cfg):
        w = _make_worker(cfg, Vocab(hotwords=["pytest", "Django"]))
        w._rebuild_prompts()
        p1, h1 = w._initial_prompt, w._hotwords
        w._rebuild_prompts()
        assert w._initial_prompt == p1
        assert w._hotwords == h1

    def test_rebuild_updates_when_vocab_replaced(self, cfg):
        w = _make_worker(cfg, Vocab(hotwords=["pytest"]))
        w._rebuild_prompts()
        w._vocab = Vocab(hotwords=["kubernetes", "terraform"])
        w._rebuild_prompts()
        assert "kubernetes" in w._hotwords
        assert "pytest" not in w._hotwords


# ---------------------------------------------------------------------------
# Init state
# ---------------------------------------------------------------------------

class TestInit:
    def test_engine_starts_as_none(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        assert w._engine is None

    def test_queue_starts_empty(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        assert w._queue.empty()

    def test_trailing_space_flag_stored(self, cfg, vocab):
        w_sp = _make_worker(cfg, vocab, trailing_space=True)
        w_no = _make_worker(cfg, vocab, trailing_space=False)
        assert w_sp._trailing_space is True
        assert w_no._trailing_space is False

    def test_cfg_stored(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        assert w._cfg is cfg

    def test_vocab_stored(self, cfg, vocab):
        w = _make_worker(cfg, vocab)
        assert w._vocab is vocab

    def test_initial_prompt_empty_before_rebuild(self, cfg):
        w = _make_worker(cfg, Vocab())
        assert w._initial_prompt == ""
        assert w._hotwords == ""
