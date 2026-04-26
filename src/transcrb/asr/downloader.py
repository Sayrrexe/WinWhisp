from __future__ import annotations

from pathlib import Path
from typing import Callable

from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal
from tqdm.auto import tqdm as _tqdm_base


MODEL_REPO_PREFIX = "Systran/faster-whisper-"


def _hf_total_size(repo: str) -> int:
    try:
        from huggingface_hub import HfApi
    except Exception:
        return 0
    try:
        api = HfApi()
        return sum(int(getattr(e, "size", None) or 0) for e in api.list_repo_tree(repo_id=repo, recursive=True))
    except Exception as e:
        logger.warning(f"failed to fetch repo size for {repo}: {e}")
        return 0


class _ProgressTqdm(_tqdm_base):
    _state: dict = {"downloaded": 0, "total": 0, "callback": None}

    @classmethod
    def init_state(cls, total: int, callback: Callable[[int, int], None] | None) -> None:
        cls._state = {"downloaded": 0, "total": total, "callback": callback}

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("disable", True)
        super().__init__(*args, **kwargs)
        if self.total and not _ProgressTqdm._state["total"]:
            _ProgressTqdm._state["total"] = int(self.total)

    def update(self, n: int = 1) -> None:
        super().update(n)
        if not n:
            return
        state = _ProgressTqdm._state
        state["downloaded"] += n
        cb = state["callback"]
        if cb is not None:
            cb(state["downloaded"], state["total"])


class DownloaderWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, model_name: str, target_dir: Path) -> None:
        super().__init__()
        self._model = model_name
        self._target = Path(target_dir)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        repo = f"{MODEL_REPO_PREFIX}{self._model}"
        target = self._target / self._model
        target.mkdir(parents=True, exist_ok=True)

        if (target / "model.bin").exists():
            self.progress.emit(1, 1)
            self.finished.emit(str(target))
            return

        try:
            from huggingface_hub import snapshot_download
        except Exception as e:
            self.failed.emit(f"Не удалось загрузить huggingface_hub: {e}")
            return

        total = _hf_total_size(repo)
        _ProgressTqdm.init_state(total, self._on_progress)

        try:
            logger.info(f"downloading {repo} → {target}")
            snapshot_download(repo_id=repo, local_dir=str(target), tqdm_class=_ProgressTqdm)
        except Exception as e:
            logger.error(f"model download failed: {e}")
            self.failed.emit(str(e))
            return

        if self._cancelled:
            self.failed.emit("Отменено")
            return

        if not (target / "model.bin").exists():
            self.failed.emit("Модель скачалась, но model.bin не найден")
            return

        if total > 0:
            self.progress.emit(total, total)
        self.finished.emit(str(target))

    def _on_progress(self, downloaded: int, total: int) -> None:
        if self._cancelled:
            return
        self.progress.emit(int(downloaded), int(total))


class DownloaderThread(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, model_name: str, target_dir: Path) -> None:
        super().__init__()
        self._worker = DownloaderWorker(model_name, target_dir)
        self._worker.progress.connect(self.progress.emit)
        self._worker.finished.connect(self.finished_ok.emit)
        self._worker.failed.connect(self.failed.emit)

    def cancel(self) -> None:
        self._worker.cancel()

    def run(self) -> None:
        self._worker.run()
