from __future__ import annotations

import os
import shutil
import sys
import time
from enum import Enum

import numpy as np
import pyperclip
from loguru import logger
from PySide6.QtCore import QObject, QProcess, Qt, QTimer
from PySide6.QtWidgets import QApplication

from transcrb.asr.file_manager import FileManager
from transcrb.asr.worker import AsrWorker
from transcrb.audio.capture import AudioCapture
from transcrb.autostart import is_autostart_enabled, set_autostart
from transcrb.config import Config, load_config, save_config
from transcrb.hotkey import HotkeyBridge
from transcrb.logging_setup import setup_logging
from transcrb.paths import appdata_dir, models_dir, resources_dir, vocab_path
from transcrb.runtime import AppRuntime, HistoryStore
from transcrb.signals import signals
from transcrb.text.inject import inject
from transcrb.text.vocab import Vocab, load_vocab
from transcrb.ui.overlay import PillOverlay
from transcrb.ui.settings_window import SettingsWindow
from transcrb.ui.tray import TrayIcon
from transcrb.ui.update_dialog import UpdateDialog
from transcrb.updater import UpdateChecker


PROCESSING_INACTIVITY_MS = 30_000


class State(Enum):
    LOADING = "loading"
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


def _ensure_vocab_file() -> None:
    target = vocab_path()
    if target.exists():
        return
    src = resources_dir() / "default_vocab.yaml"
    if src.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)


def _get_foreground_hwnd() -> int | None:
    try:
        import win32gui

        return win32gui.GetForegroundWindow()
    except Exception:
        return None


class TranscrbApp(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.cfg: Config = load_config()
        setup_logging(self.cfg.log_level)
        _ensure_vocab_file()
        self.vocab: Vocab = load_vocab(vocab_path())

        self.history = HistoryStore(appdata_dir() / "history.jsonl")
        self.runtime = AppRuntime(
            cfg=self.cfg,
            vocab=self.vocab,
            history=self.history,
            state=State.LOADING.value,
            model_loaded=False,
        )

        self.state = State.LOADING
        self._press_time = 0.0
        self._session_started_at = 0.0
        self._recording_hwnd: int | None = None
        self._pending_chunks = 0
        self._focus_lost = False
        self._session_text: list[str] = []
        self._processing_finished_at = 0.0

        self.tray = TrayIcon()
        self.tray.set_tooltip("WinWhisp — загрузка модели…")
        self.tray.show()
        self.tray.quit_requested.connect(self._on_quit)
        self.tray.reload_requested.connect(self._on_reload)
        self.tray.update_clicked.connect(self._on_update_clicked)

        self._update_dialog: UpdateDialog | None = None
        self._latest_release: dict | None = None
        self._manual_check_pending = False
        self.updater = UpdateChecker(self.cfg.updater, parent=self)
        self.updater.update_available.connect(
            self._on_update_available, Qt.QueuedConnection
        )
        self.updater.no_update.connect(self._on_no_update, Qt.QueuedConnection)
        self.updater.check_failed.connect(self._on_update_check_failed, Qt.QueuedConnection)
        self.updater.start()

        self.overlay = PillOverlay(self.cfg.overlay)

        self.audio = AudioCapture(
            samplerate=self.cfg.audio.samplerate,
            channels=self.cfg.audio.channels,
            block_ms=self.cfg.audio.block_ms,
            max_duration_s=self.cfg.audio.max_duration_s,
            device=self.cfg.audio.device,
            n_bands=self.cfg.overlay.bars,
            chunk_min_s=self.cfg.audio.chunk_min_s,
            chunk_max_s=self.cfg.audio.chunk_max_s,
            chunk_silence_s=self.cfg.audio.chunk_silence_s,
            chunk_silence_rms=self.cfg.audio.chunk_silence_rms,
            keep_silence_pad_ms=self.cfg.audio.keep_silence_pad_ms,
            on_level=self._on_audio_level,
            on_chunk=lambda c: signals.audio_chunk.emit(c),
        )

        self.asr = AsrWorker(
            self.cfg.asr,
            self.vocab,
            trailing_space=self.cfg.injection.trailing_space,
            prompt_prefix=self.cfg.vocab.prompt_prefix,
            audio_cfg=self.cfg.audio,
        )
        self.asr.loaded.connect(self._on_model_loaded)
        self.asr.unloaded.connect(self._on_model_unloaded)
        self.asr.ready.connect(self._on_transcription_ready)
        self.asr.error.connect(self._on_error)
        self.asr.start()

        self.files = FileManager(
            self.asr,
            self.cfg.files,
            samplerate=self.cfg.audio.samplerate,
            parent=self,
        )
        self.files.job_added.connect(self._on_files_count_changed)
        self.files.job_state_changed.connect(self._on_files_count_changed)
        self.files.job_removed.connect(self._on_files_count_changed)

        self._sync_autostart_from_registry()

        self.window = SettingsWindow(self.runtime, files_manager=self.files)
        self.tray.open_requested.connect(self.window.open_to_front)
        self.tray.files_requested.connect(lambda: self.window.open_to_page("files"))
        self.window.reload_requested.connect(self._on_reload)
        self.window.config_changed.connect(self._on_settings_changed)
        self.window.vocab_changed.connect(self._on_vocab_changed)
        self.window.copy_text_requested.connect(self._on_copy_request)
        self.window.paste_text_requested.connect(self._on_paste_request)
        self.window.check_updates_requested.connect(
            self._on_check_updates_requested, Qt.QueuedConnection
        )
        self.window.install_update_requested.connect(
            self._show_update_dialog, Qt.QueuedConnection
        )

        signals.rms_updated.connect(self.overlay.update_level, Qt.QueuedConnection)
        signals.audio_chunk.connect(self._on_audio_chunk, Qt.QueuedConnection)

        self.hotkey = HotkeyBridge(self.cfg.hotkey.combo, self.cfg.hotkey.debounce_ms)
        self.hotkey.pressed.connect(self._on_hotkey_pressed, Qt.QueuedConnection)
        self.hotkey.released.connect(self._on_hotkey_released, Qt.QueuedConnection)
        self.hotkey.start()

        self._max_duration_timer = QTimer(self)
        self._max_duration_timer.setSingleShot(True)
        self._max_duration_timer.timeout.connect(self._on_max_duration)

        self._release_timer = QTimer(self)
        self._release_timer.setSingleShot(True)
        self._release_timer.timeout.connect(self._finalize_release)

        self._processing_watchdog = QTimer(self)
        self._processing_watchdog.setSingleShot(True)
        self._processing_watchdog.timeout.connect(self._on_processing_stuck)

        logger.info(f"WinWhisp started, hotkey={self.cfg.hotkey.combo}")

    def _sync_autostart_from_registry(self) -> None:
        registry_state = is_autostart_enabled()
        if registry_state != self.cfg.autostart:
            logger.info(
                f"autostart drift: cfg={self.cfg.autostart} registry={registry_state}, "
                f"trusting registry"
            )
            self.cfg.autostart = registry_state
            self.runtime.cfg = self.cfg
            try:
                save_config(self.cfg)
            except Exception as e:
                logger.error(f"failed to persist autostart sync: {e}")
        set_autostart(self.cfg.autostart)

    def _set_state(self, state: State) -> None:
        self.state = state
        self.runtime.state = state.value
        active = state in (State.RECORDING, State.PROCESSING)
        page = self.window.files_page() if hasattr(self, "window") else None
        if page is not None:
            page.set_hotkey_active(active)

    def _on_files_count_changed(self, *_args) -> None:
        self.tray.set_files_count(self.files.active_count())

    def _on_model_loaded(self) -> None:
        self.runtime.model_loaded = True
        if self.state == State.LOADING:
            self._set_state(State.IDLE)
            if self.cfg.tray.show_notifications:
                self.tray.notify("WinWhisp", "Готов. Зажми " + self.cfg.hotkey.combo)
        self.tray.set_tooltip(f"WinWhisp — готов ({self.cfg.hotkey.combo})")

    def _on_model_unloaded(self) -> None:
        self.runtime.model_loaded = False
        self.tray.set_tooltip(f"WinWhisp — модель выгружена ({self.cfg.hotkey.combo})")

    def _on_audio_level(self, rms: float, bands: np.ndarray) -> None:
        if self.state == State.RECORDING:
            signals.rms_updated.emit(rms, bands)

    def _model_is_installed(self) -> bool:
        return (models_dir() / self.cfg.asr.model / "model.bin").exists()

    def _on_hotkey_pressed(self) -> None:
        now = time.monotonic()
        grace_active = (now - self._processing_finished_at) < 0.8
        logger.info(
            f"press: state={self.state.value} pending={self._pending_chunks} grace={grace_active}"
        )
        if self.state == State.RECORDING and self._release_timer.isActive():
            self._release_timer.stop()
            logger.info("release cancelled by re-press within tail window")
            return
        if self.state == State.PROCESSING or grace_active:
            return
        if self.state not in (State.IDLE, State.LOADING):
            return
        if not self._model_is_installed():
            logger.warning(
                f"hotkey ignored: model {self.cfg.asr.model!r} is not installed"
            )
            self._notify(
                f"Модель «{self.cfg.asr.model}» не скачана — откройте настройки",
                kind="warn",
            )
            return
        self._set_state(State.RECORDING)
        self._press_time = time.monotonic()
        self._session_started_at = self._press_time
        self._recording_hwnd = _get_foreground_hwnd()
        self._pending_chunks = 0
        self._focus_lost = False
        self._session_text = []
        self.asr.prepare()
        try:
            self.audio.start()
        except Exception as e:
            self._on_error(f"Не удалось открыть микрофон: {e}")
            self._set_state(State.IDLE)
            return
        if self.cfg.overlay.enabled:
            self.overlay.show_fade()
        self._max_duration_timer.start(self.cfg.audio.max_duration_s * 1000)

    def _on_hotkey_released(self) -> None:
        if self.state != State.RECORDING or self._release_timer.isActive():
            return
        tail_ms = max(0, int(self.cfg.hotkey.release_tail_ms))
        hold_ms = (time.monotonic() - self._press_time) * 1000
        if hold_ms < self.cfg.hotkey.min_hold_ms:
            self._finalize_release()
            return
        if tail_ms == 0:
            self._finalize_release()
            return
        logger.info(f"release pending, tail={tail_ms}ms")
        self._release_timer.start(tail_ms)

    def _finalize_release(self) -> None:
        if self.state != State.RECORDING:
            return
        self._max_duration_timer.stop()
        self._release_timer.stop()
        hold_ms = (time.monotonic() - self._press_time) * 1000
        emit_tail = hold_ms >= self.cfg.hotkey.min_hold_ms
        tail_emitted = self.audio.stop(emit_tail=emit_tail)

        has_work = self._pending_chunks > 0 or tail_emitted
        if not has_work:
            reason = (
                f"discarded short press ({hold_ms:.0f}ms)"
                if not emit_tail
                else f"silent release tail, nothing to transcribe ({hold_ms:.0f}ms)"
            )
            logger.info(reason)
            self._set_state(State.IDLE)
            if self.cfg.overlay.enabled:
                self.overlay.hide_fade()
            return

        self._set_state(State.PROCESSING)
        if self.cfg.overlay.enabled:
            self.overlay.show_busy()
        self._start_processing_watchdog()
        logger.info(
            f"release: state={self.state.value} pending={self._pending_chunks} "
            f"emit_tail={emit_tail} tail_emitted={tail_emitted}"
        )

    def _on_audio_chunk(self, chunk) -> None:
        if chunk is None or len(chunk) == 0:
            return
        prior = "".join(self._session_text[-3:]).strip()[-450:]
        self._pending_chunks += 1
        dur_s = len(chunk) / float(self.cfg.audio.samplerate)
        logger.info(
            f"chunk in: state={self.state.value} pending->{self._pending_chunks} dur={dur_s:.2f}s"
        )
        self.asr.submit(chunk, prior_context=prior)

    def _on_max_duration(self) -> None:
        if self.state == State.RECORDING:
            logger.info("max duration reached, auto-stop")
            self._finalize_release()

    def _on_transcription_ready(self, text: str) -> None:
        if self._pending_chunks > 0:
            self._pending_chunks -= 1
        logger.info(
            f"ready: state={self.state.value} pending->{self._pending_chunks} text_len={len(text)}"
        )
        if self.state == State.PROCESSING:
            self._processing_watchdog.start(PROCESSING_INACTIVITY_MS)
        if text:
            self._session_text.append(text)
            mode = self.cfg.injection.on_focus_change
            if not self._focus_lost and mode != "inject" and self._recording_hwnd:
                cur = _get_foreground_hwnd()
                if cur and cur != self._recording_hwnd:
                    self._focus_lost = True
                    logger.info(f"focus changed, mode={mode}")
            if mode == "inject" or not self._focus_lost:
                self._inject(text, restore=self.cfg.injection.restore_clipboard)
        self._maybe_finish()

    def _maybe_finish(self) -> None:
        if self.state != State.PROCESSING or self._pending_chunks > 0:
            return
        self._processing_watchdog.stop()
        self._set_state(State.IDLE)
        self._processing_finished_at = time.monotonic()
        full = "".join(self._session_text).strip()
        if not full:
            if self.cfg.overlay.enabled:
                self.overlay.hide_fade()
            return

        duration = max(0.0, self._processing_finished_at - self._session_started_at)
        self.history.add(full, duration)

        self._copy_clipboard_safe(full)

        mode = self.cfg.injection.on_focus_change
        if mode == "notify" and self.cfg.overlay.enabled and self._focus_lost:
            self.overlay.show_result(
                on_paste_again=lambda t=full: self._paste_again(t),
                hold_ms=self.cfg.overlay.result_hold_ms,
            )
            return

        if self.cfg.overlay.enabled:
            self.overlay.hide_fade()

    def _paste_again(self, text: str) -> None:
        self._inject(text, restore=False)

    def _inject(self, text: str, *, restore: bool) -> None:
        inject(
            text,
            paste_combo=self.cfg.injection.paste_combo,
            pre_delay_ms=self.cfg.injection.pre_paste_delay_ms,
            post_delay_ms=self.cfg.injection.post_paste_delay_ms,
            restore=restore,
        )

    def _on_error(self, msg: str) -> None:
        logger.error(msg)
        if self.cfg.tray.notify_on_error:
            self.tray.notify("WinWhisp — ошибка", msg)
        if (
            self.state in (State.RECORDING, State.PROCESSING)
            and not self.runtime.model_loaded
        ):
            self._abort_session()

    def _abort_session(self) -> None:
        logger.warning("aborting session due to engine error")
        self._release_timer.stop()
        self._max_duration_timer.stop()
        self._processing_watchdog.stop()
        if self.audio.is_running():
            self.audio.stop(emit_tail=False)
        self._pending_chunks = 0
        self._session_text = []
        self._focus_lost = False
        self._recording_hwnd = None
        self._processing_finished_at = time.monotonic()
        self._set_state(State.IDLE)
        if self.cfg.overlay.enabled:
            self.overlay.hide_fade()

    def _start_processing_watchdog(self) -> None:
        self._processing_watchdog.start(PROCESSING_INACTIVITY_MS)

    def _on_processing_stuck(self) -> None:
        if self.state != State.PROCESSING:
            return
        logger.error(
            f"processing watchdog fired: no progress for "
            f"{self._processing_watchdog.interval()}ms, pending={self._pending_chunks} — "
            f"resetting state and reloading engine"
        )
        if self.cfg.tray.notify_on_error:
            self.tray.notify(
                "WinWhisp",
                "Сессия зависла на обработке — сбросил состояние.",
            )
        self._pending_chunks = 0
        self._session_text = []
        self._focus_lost = False
        self._recording_hwnd = None
        self._processing_finished_at = time.monotonic()
        self._set_state(State.IDLE)
        if self.cfg.overlay.enabled:
            self.overlay.hide_fade()
        self.asr.request_reload()

    def _on_reload(self) -> None:
        logger.info("full app restart requested")
        if getattr(sys, "frozen", False):
            program = sys.executable
            arguments = list(sys.argv[1:])
        else:
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            program = pythonw if os.path.exists(pythonw) else sys.executable
            arguments = ["-m", "transcrb"]
        QProcess.startDetached(program, arguments)
        self._on_quit()

    def _on_settings_changed(self, changes: dict) -> None:
        self._apply_basic_changes(changes)
        pending_model_dl = False
        if any(k.startswith("asr.") for k in changes):
            pending_model_dl = self._maybe_reload_engine(changes)
        self.window.refresh_dashboard()

        if pending_model_dl:
            self._notify(
                f"Модель «{self.cfg.asr.model}» не скачана — нажмите «Скачать», чтобы применить",
                kind="warn",
            )
        else:
            self._notify("Настройки применены")

    def _apply_basic_changes(self, changes: dict) -> None:
        if "autostart" in changes:
            set_autostart(bool(changes["autostart"]))
        if "log_level" in changes:
            setup_logging(str(changes["log_level"]))
        if "hotkey.combo" in changes or "hotkey.debounce_ms" in changes:
            self._rebind_hotkey()
        if "vocab.prompt_prefix" in changes:
            self.asr.set_prompt_prefix(str(changes["vocab.prompt_prefix"]))

    def _on_vocab_changed(self) -> None:
        try:
            self.vocab = load_vocab(vocab_path())
        except Exception as e:
            logger.error(f"vocab reload failed: {e}")
            return
        self.runtime.vocab = self.vocab
        self.asr.update_vocab(self.vocab)
        logger.info("vocab reloaded from disk")

    def _maybe_reload_engine(self, changes: dict) -> bool:
        if self.state in (State.RECORDING, State.PROCESSING):
            return False
        if "asr.model" in changes:
            model_bin = models_dir() / self.cfg.asr.model / "model.bin"
            if not model_bin.exists():
                logger.info(
                    f"asr.model changed to {self.cfg.asr.model} but model is not installed yet, skipping reload"
                )
                return True
        logger.info(f"asr.* changed, requesting engine reload: {list(changes)}")
        self.asr.request_reload()
        return False

    def _notify(self, text: str, *, kind: str = "ok") -> None:
        if not text:
            return
        if self.window.isVisible():
            self.window.show_toast(text, kind=kind)
        elif self.cfg.tray.show_notifications:
            self.tray.notify("WinWhisp", text)

    def _on_copy_request(self, text: str) -> None:
        if not text:
            return
        self._copy_clipboard_safe(text)

    def _copy_clipboard_safe(self, text: str) -> None:
        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.error(f"clipboard copy failed: {e}")

    def _on_paste_request(self, text: str) -> None:
        if not text:
            return
        self._copy_clipboard_safe(text)
        self._inject(text, restore=False)

    def _rebind_hotkey(self) -> None:
        if self.state == State.RECORDING:
            self._release_timer.stop()
            self._max_duration_timer.stop()
            self.audio.stop(emit_tail=False)
            self._set_state(State.IDLE)
            if self.cfg.overlay.enabled:
                self.overlay.hide_fade()
        self.hotkey.stop()
        self.hotkey = HotkeyBridge(self.cfg.hotkey.combo, self.cfg.hotkey.debounce_ms)
        self.hotkey.pressed.connect(self._on_hotkey_pressed, Qt.QueuedConnection)
        self.hotkey.released.connect(self._on_hotkey_released, Qt.QueuedConnection)
        self.hotkey.start()
        self.tray.set_tooltip(f"WinWhisp — готов ({self.cfg.hotkey.combo})")
        logger.info(f"hotkey rebound to {self.cfg.hotkey.combo}")

    def _on_update_available(self, version: str, release: dict) -> None:
        self._latest_release = release
        self.tray.set_update_available(version)
        self.window.set_update_available(version, release)
        if self._manual_check_pending:
            self._manual_check_pending = False
            self._show_update_dialog()
            return
        if self.cfg.tray.show_notifications:
            self.tray.notify(
                "WinWhisp — доступно обновление",
                f"Версия {version}. Нажмите, чтобы установить.",
            )

    def _on_no_update(self, tag: str) -> None:
        self.window.set_no_update(tag)
        if self._manual_check_pending:
            self._manual_check_pending = False
            self._notify(f"Установлена последняя версия ({tag}).")

    def _on_update_check_failed(self, msg: str) -> None:
        self.window.set_update_check_failed(msg)
        if self._manual_check_pending:
            self._manual_check_pending = False
            self._notify(f"Не удалось проверить обновления: {msg}", kind="warn")

    def _on_update_clicked(self) -> None:
        self._show_update_dialog()

    def _on_check_updates_requested(self) -> None:
        self._manual_check_pending = True
        self.window.set_update_checking()
        self.updater.check_now(force_notify=True)

    def _show_update_dialog(self) -> None:
        release = self._latest_release or self.updater.latest_release()
        if not release:
            self._on_check_updates_requested()
            return
        if self._update_dialog is not None and self._update_dialog.isVisible():
            self._update_dialog.raise_()
            self._update_dialog.activateWindow()
            return
        parent = self.window if self.window.isVisible() else None
        dlg = UpdateDialog(release, parent=parent)
        dlg.finished.connect(lambda _r: setattr(self, "_update_dialog", None))
        self._update_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_quit(self) -> None:
        logger.info("quitting")
        self._release_timer.stop()
        self._max_duration_timer.stop()
        self._processing_watchdog.stop()
        self.hotkey.stop()
        if self.audio.is_running():
            self.audio.stop(emit_tail=False)
        self.asr.stop()
        self.updater.stop()
        self.tray.hide()
        QApplication.instance().quit()
