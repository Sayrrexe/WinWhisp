from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication

from transcrb.asr.downloader import (
    MODEL_REPO_PREFIX,
    DownloaderThread,
    DownloaderWorker,
    _ProgressTqdm,
    _hf_total_size,
)


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    return app


@pytest.fixture(autouse=True)
def reset_progress_tqdm_state():
    _ProgressTqdm.init_state(0, None)
    yield
    _ProgressTqdm.init_state(0, None)


# ---------------------------------------------------------------------------
# _hf_total_size
# ---------------------------------------------------------------------------


def _make_entry(size):
    e = MagicMock()
    e.size = size
    return e


def test_hf_total_size_sums_entries(monkeypatch):
    entries = [_make_entry(100), _make_entry(200), _make_entry(300)]
    api_mock = MagicMock()
    api_mock.return_value.list_repo_tree.return_value = entries
    monkeypatch.setitem(sys.modules, "huggingface_hub", MagicMock(HfApi=api_mock))
    assert _hf_total_size("some/repo") == 600


def test_hf_total_size_handles_none_size(monkeypatch):
    entries = [_make_entry(None), _make_entry(50)]
    api_mock = MagicMock()
    api_mock.return_value.list_repo_tree.return_value = entries
    monkeypatch.setitem(sys.modules, "huggingface_hub", MagicMock(HfApi=api_mock))
    assert _hf_total_size("repo") == 50


def test_hf_total_size_empty_tree(monkeypatch):
    api_mock = MagicMock()
    api_mock.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", MagicMock(HfApi=api_mock))
    assert _hf_total_size("repo") == 0


def test_hf_total_size_api_raises_returns_zero(monkeypatch):
    api_mock = MagicMock()
    api_mock.return_value.list_repo_tree.side_effect = RuntimeError("network error")
    monkeypatch.setitem(sys.modules, "huggingface_hub", MagicMock(HfApi=api_mock))
    assert _hf_total_size("repo") == 0


def test_hf_total_size_import_fail_returns_zero(monkeypatch):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    assert _hf_total_size("repo") == 0


def test_hf_total_size_mixed_zero_and_valid_sizes(monkeypatch):
    entries = [_make_entry(0), _make_entry(0), _make_entry(777)]
    api_mock = MagicMock()
    api_mock.return_value.list_repo_tree.return_value = entries
    monkeypatch.setitem(sys.modules, "huggingface_hub", MagicMock(HfApi=api_mock))
    assert _hf_total_size("repo") == 777


# ---------------------------------------------------------------------------
# _ProgressTqdm
# ---------------------------------------------------------------------------


def test_progress_tqdm_init_state_sets_fields():
    cb = MagicMock()
    _ProgressTqdm.init_state(500, cb)
    assert _ProgressTqdm._state["total"] == 500
    assert _ProgressTqdm._state["callback"] is cb
    assert _ProgressTqdm._state["downloaded"] == 0


def test_progress_tqdm_update_accumulates_and_calls_callback():
    received = []
    _ProgressTqdm.init_state(1000, lambda d, t: received.append((d, t)))
    bar = _ProgressTqdm(total=1000)
    bar.update(300)
    bar.update(200)
    assert _ProgressTqdm._state["downloaded"] == 500
    assert received[-1] == (500, 1000)


def test_progress_tqdm_update_zero_is_noop():
    calls = []
    _ProgressTqdm.init_state(1000, lambda d, t: calls.append((d, t)))
    bar = _ProgressTqdm(total=1000)
    bar.update(0)
    assert calls == []
    assert _ProgressTqdm._state["downloaded"] == 0


def test_progress_tqdm_none_callback_no_crash():
    _ProgressTqdm.init_state(1000, None)
    bar = _ProgressTqdm(total=1000)
    bar.update(100)


def test_progress_tqdm_reset_via_init_state():
    cb1 = MagicMock()
    _ProgressTqdm.init_state(100, cb1)
    bar = _ProgressTqdm(total=100)
    bar.update(50)
    assert _ProgressTqdm._state["downloaded"] == 50

    cb2 = MagicMock()
    _ProgressTqdm.init_state(200, cb2)
    assert _ProgressTqdm._state["downloaded"] == 0
    assert _ProgressTqdm._state["total"] == 200
    assert _ProgressTqdm._state["callback"] is cb2


def test_progress_tqdm_multiple_bars_accumulate():
    received = []
    _ProgressTqdm.init_state(1000, lambda d, t: received.append((d, t)))
    bar1 = _ProgressTqdm(total=1000)
    bar2 = _ProgressTqdm(total=1000)
    bar1.update(100)
    bar2.update(200)
    assert _ProgressTqdm._state["downloaded"] == 300


# ---------------------------------------------------------------------------
# DownloaderWorker.run — short-circuit when model.bin exists
# ---------------------------------------------------------------------------


def test_worker_run_skips_download_if_model_bin_exists(qapp, tmp_path):
    model_dir = tmp_path / "tiny"
    model_dir.mkdir()
    (model_dir / "model.bin").write_bytes(b"\x00")

    worker = DownloaderWorker("tiny", tmp_path)
    progress_vals = []
    finished_vals = []
    worker.progress.connect(lambda d, t: progress_vals.append((d, t)))
    worker.finished.connect(finished_vals.append)

    worker.run()

    assert finished_vals == [str(model_dir)]
    assert progress_vals == [(1, 1)]


def test_worker_run_happy_path(qapp, tmp_path, monkeypatch):
    model_name = "base"
    model_dir = tmp_path / model_name

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = [_make_entry(1000)]
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker(model_name, tmp_path)
    finished_vals = []
    failed_vals = []
    worker.finished.connect(finished_vals.append)
    worker.failed.connect(failed_vals.append)

    worker.run()

    assert failed_vals == []
    assert finished_vals == [str(model_dir)]


def test_worker_run_emits_final_progress_when_total_known(qapp, tmp_path, monkeypatch):
    model_name = "small"
    total_size = 999

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = [_make_entry(total_size)]
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker(model_name, tmp_path)
    progress_vals = []
    worker.progress.connect(lambda d, t: progress_vals.append((d, t)))

    worker.run()

    assert (total_size, total_size) in progress_vals


def test_worker_run_no_final_progress_when_total_zero(qapp, tmp_path, monkeypatch):
    model_name = "medium"

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker(model_name, tmp_path)
    progress_vals = []
    finished_vals = []
    worker.progress.connect(lambda d, t: progress_vals.append((d, t)))
    worker.finished.connect(finished_vals.append)

    worker.run()

    assert finished_vals
    assert progress_vals == []


def test_worker_run_fails_when_huggingface_hub_missing(qapp, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)

    worker = DownloaderWorker("tiny", tmp_path)
    failed_vals = []
    finished_vals = []
    worker.failed.connect(failed_vals.append)
    worker.finished.connect(finished_vals.append)

    worker.run()

    assert failed_vals
    assert finished_vals == []


def test_worker_run_fails_when_snapshot_raises(qapp, tmp_path, monkeypatch):
    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = OSError("disk full")
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker("base", tmp_path)
    failed_vals = []
    finished_vals = []
    worker.failed.connect(failed_vals.append)
    worker.finished.connect(finished_vals.append)

    worker.run()

    assert "disk full" in failed_vals[0]
    assert finished_vals == []


def test_worker_run_fails_when_model_bin_missing_after_download(qapp, tmp_path, monkeypatch):
    def fake_snapshot(repo_id, local_dir, tqdm_class):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        # intentionally writes no model.bin

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker("large", tmp_path)
    failed_vals = []
    finished_vals = []
    worker.failed.connect(failed_vals.append)
    worker.finished.connect(finished_vals.append)

    worker.run()

    assert failed_vals
    assert "model.bin" in failed_vals[0]
    assert finished_vals == []


def test_worker_run_uses_correct_repo_name(qapp, tmp_path, monkeypatch):
    captured = {}

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        captured["repo_id"] = repo_id
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker("large-v3", tmp_path)
    worker.run()

    assert captured["repo_id"] == f"{MODEL_REPO_PREFIX}large-v3"


def test_worker_run_target_subdir_uses_model_name(qapp, tmp_path, monkeypatch):
    captured = {}

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        captured["local_dir"] = local_dir
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker("medium", tmp_path)
    worker.run()

    assert Path(captured["local_dir"]) == tmp_path / "medium"


# ---------------------------------------------------------------------------
# DownloaderWorker.cancel
# ---------------------------------------------------------------------------


def test_worker_cancel_sets_flag(qapp, tmp_path):
    worker = DownloaderWorker("tiny", tmp_path)
    assert worker._cancelled is False
    worker.cancel()
    assert worker._cancelled is True


def test_worker_on_progress_suppressed_after_cancel(qapp, tmp_path):
    worker = DownloaderWorker("tiny", tmp_path)
    progress_vals = []
    worker.progress.connect(lambda d, t: progress_vals.append((d, t)))
    worker.cancel()
    worker._on_progress(100, 1000)
    assert progress_vals == []


def test_worker_on_progress_emits_before_cancel(qapp, tmp_path):
    worker = DownloaderWorker("tiny", tmp_path)
    progress_vals = []
    worker.progress.connect(lambda d, t: progress_vals.append((d, t)))
    worker._on_progress(50, 1000)
    assert progress_vals == [(50, 1000)]


def test_worker_cancel_after_download_emits_failed(qapp, tmp_path, monkeypatch):
    def fake_snapshot(repo_id, local_dir, tqdm_class):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker("base", tmp_path)
    worker.cancel()

    failed_vals = []
    finished_vals = []
    worker.failed.connect(failed_vals.append)
    worker.finished.connect(finished_vals.append)

    worker.run()

    # cancel is checked only after snapshot_download returns — download still completes
    assert failed_vals == ["Отменено"]
    assert finished_vals == []


def test_worker_cancel_does_not_interrupt_in_flight_download(qapp, tmp_path, monkeypatch):
    """Documents that cancel() cannot interrupt snapshot_download mid-run."""
    side_effects = []

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        side_effects.append("started")
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")
        side_effects.append("completed")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    worker = DownloaderWorker("base", tmp_path)

    original_snapshot = hf_mock.snapshot_download

    def cancelling_snapshot(**kwargs):
        worker.cancel()
        return original_snapshot(**kwargs)

    hf_mock.snapshot_download = cancelling_snapshot

    failed_vals = []
    worker.failed.connect(failed_vals.append)

    worker.run()

    assert "started" in side_effects
    assert "completed" in side_effects
    assert failed_vals == ["Отменено"]


# ---------------------------------------------------------------------------
# DownloaderThread
# ---------------------------------------------------------------------------


def test_downloader_thread_cancel_delegates_to_worker(qapp, tmp_path):
    thread = DownloaderThread("tiny", tmp_path)
    assert thread._worker._cancelled is False
    thread.cancel()
    assert thread._worker._cancelled is True


def test_downloader_thread_run_forwards_finished_ok(qapp, tmp_path, monkeypatch):
    model_name = "base"

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    thread = DownloaderThread(model_name, tmp_path)
    finished_vals = []
    thread.finished_ok.connect(finished_vals.append)

    thread.run()

    assert finished_vals == [str(tmp_path / model_name)]


def test_downloader_thread_run_forwards_failed(qapp, tmp_path, monkeypatch):
    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = OSError("net error")
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    thread = DownloaderThread("base", tmp_path)
    failed_vals = []
    thread.failed.connect(failed_vals.append)

    thread.run()

    assert "net error" in failed_vals[0]


def test_downloader_thread_run_forwards_progress(qapp, tmp_path, monkeypatch):
    model_name = "tiny"
    total_size = 500

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = [_make_entry(total_size)]
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    thread = DownloaderThread(model_name, tmp_path)
    progress_vals = []
    thread.progress.connect(lambda d, t: progress_vals.append((d, t)))

    thread.run()

    assert (total_size, total_size) in progress_vals


def test_downloader_thread_already_downloaded_skips(qapp, tmp_path, monkeypatch):
    model_name = "large"
    model_dir = tmp_path / model_name
    model_dir.mkdir()
    (model_dir / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    thread = DownloaderThread(model_name, tmp_path)
    finished_vals = []
    thread.finished_ok.connect(finished_vals.append)

    thread.run()

    hf_mock.snapshot_download.assert_not_called()
    assert finished_vals == [str(model_dir)]


def test_downloader_thread_idempotent_second_run(qapp, tmp_path, monkeypatch):
    model_name = "small"
    call_count = {"n": 0}

    def fake_snapshot(repo_id, local_dir, tqdm_class):
        call_count["n"] += 1
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"\x00")

    hf_mock = MagicMock()
    hf_mock.snapshot_download.side_effect = fake_snapshot
    hf_mock.HfApi.return_value.list_repo_tree.return_value = []
    monkeypatch.setitem(sys.modules, "huggingface_hub", hf_mock)

    thread1 = DownloaderThread(model_name, tmp_path)
    thread1.run()

    thread2 = DownloaderThread(model_name, tmp_path)
    finished_vals = []
    thread2.finished_ok.connect(finished_vals.append)
    thread2.run()

    assert call_count["n"] == 1
    assert finished_vals == [str(tmp_path / model_name)]
