# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Все команды запускаются через `uv` (Python 3.11 закреплён в `.python-version` и `pyproject.toml`). Рабочая директория должна быть корнем проекта.

```powershell
uv sync                                       # установка Python 3.11 + зависимостей
uv run python -m transcrb                     # запуск приложения из исходников
uv run pytest                                 # все тесты
uv run pytest tests/test_postprocess.py -v    # один файл
uv run pytest -k build_initial_prompt         # по имени теста
uv run pyinstaller --clean packaging/transcrb.spec   # сборка .exe → dist\winwhisp\
```

Скрипты-обёртки в `scripts/`: `run.ps1`, `test.ps1`, `build_exe.ps1`, плюс ручные smoke-тесты `smoke_asr.py` / `smoke_ui.py`. Для быстрой итерации над UI / ASR изолированно вызывай их через `uv run python scripts/smoke_ui.py`.

## Архитектура

Основной поток — Qt main (`src/transcrb/app.py`), координатор состояний. Конечный автомат `State`: `LOADING → IDLE → RECORDING → PROCESSING → IDLE`. Все переходы идут через `TranscrbApp`, остальные потоки только эмитят Qt-сигналы с `QueuedConnection`.

Четыре потока, все общаются через `signals.py`:

1. **Qt main** — оркестрация состояний, вставка текста, overlay, tray, settings.
2. **PortAudio callback** (`audio/capture.py`) — пишет сэмплы в ring buffer, режет на чанки по VAD (скользящий RMS через prefix-sum), эмитит `on_chunk`. На тишину ≥ `chunk_silence_s` после достижения `chunk_min_s` — cut; иначе force cut на `chunk_max_s`. Эта логика горячая, изменения вроде смены алгоритма тишины обязаны сохранять prefix-sum инвариант (см. `_find_silence_cut`).
3. **keyboard hook** (`hotkey.py`, lib `keyboard`) — одна клавиша обрабатывается через сравнение `event.name` (именно так различается `right ctrl` vs `left ctrl`), комбинации — через `keyboard.is_pressed`. Debounce общий.
4. **AsrWorker QThread** (`asr/worker.py`) — очередь `queue.Queue` из трёх видов сообщений: `_Prepare` (eager-load), `_Request(audio)` (транскрибация), `None` (stop). На `queue.get(timeout=idle_unload_s)` по `Empty` — выгрузка модели из VRAM через `gc.collect()`, `loaded` / `unloaded` сигналы тикают трей.

WhisperEngine (`asr/engine.py`) — обёртка `faster_whisper.WhisperModel`. При падении CUDA load делает автоматический fallback на CPU/int8. `warmup()` на 1 секунде нулей обязателен после load — первый реальный вызов иначе в 3-5× медленнее. Модели качаются с `Systran/faster-whisper-<name>` в `%APPDATA%\WinWhisp\models\<name>\`.

Пост-процессинг (`text/postprocess.py`): словарные замены — единый regex с longest-match-first сортировкой ключей и `(?<!\w)...(?!\w)` для границ Unicode. `preserve_sentence_case` капитализирует букву в начале предложения уже после замен. `hallucinations` (`vocab.yaml`) — блок-лист фраз, возвращаемых Whisper на тишине, дропаются молча. Также дропаются «prompt echo» — когда модель вернула кусок `initial_prompt` вместо транскрипта (`_is_prompt_echo` в worker).

Инжект (`text/inject.py`): stash буфера → copy → `Ctrl+V` → restore. Восстанавливается только `CF_UNICODETEXT`. Режим `on_focus_change`:
- `inject` — вставлять всегда, даже если фокус сменился (опасно, но просится для IDE).
- `notify` (default) — при смене фокуса: текст в буфер, overlay-пилюля → «результат-режим» с кнопкой «Вставить ещё раз» (`overlay.result_hold_ms`).
- `skip` — тихо копировать в буфер.

Overlay (`ui/overlay.py`) — frameless, always-on-top, click-through во время записи (WS_EX_TRANSPARENT). В результат-режиме click-through снимается, но фокус не перехватывается, чтобы `Ctrl+V` летел в предыдущее поле.

## Пути и фрозен-режим

`paths.py` разделяет dev и PyInstaller-билд. `resources_dir()` в frozen-режиме возвращает `sys._MEIPASS/resources`, в dev — `<repo>/resources`. Все изменяемые данные (config, vocab, models, logs) всегда в `%APPDATA%\WinWhisp\`, и в dev и в frozen. Python-пакет по-прежнему называется `transcrb` (импорты `from transcrb.*`), но бренд и пути пользователя — `WinWhisp`.

## CUDA DLL-и

`_cuda_path.py` импортируется самым первым (даже до Qt), вызывает `os.add_dll_directory()` для `nvidia-cublas-cu12` и `nvidia-cudnn-cu12`, которые приходят как pip-пакеты. Без этого `WhisperModel(device="cuda")` падает с `cublas64_12.dll not found`. При смене зависимостей на другую версию CUDA обновить список путей в `_add_nvidia_dll_dirs`.

## Reload конфига

GUI настроек выпилен (будет переделан). Сейчас редактировать `%APPDATA%\WinWhisp\config.yaml` / `vocab.yaml` вручную, трей → «Перезагрузить конфиг» применяет vocab и некоторые поля на лету через `_on_reload`. Смена `hotkey.combo`, `asr.*`, `audio.device/samplerate`, размеров overlay требует полного перезапуска приложения — горячего применения не предусмотрено.

## Hotkey `right ctrl`

Библиотека `keyboard` исторически не различала left/right Ctrl. Текущая реализация читает `event.name == "right ctrl"` напрямую, и это работает. При добавлении новых «односторонних» клавиш (`right shift`, `right alt`, `right win`) поддерживать тот же путь — через `_handle_single`.

## Тесты

`pytest.ini_options` в `pyproject.toml` закрепляет `pythonpath = ["src"]`, поэтому импорты `from transcrb.*` работают без установки пакета. Тесты чистые — не требуют GPU, микрофона или Whisper (всё мокается или работает на уровне чистых функций). Покрывают: VAD-чанкинг (`test_audio_buffer`), `initial_prompt` с лимитом 224 токена (`test_vocab`), longest-match regex и hallucination-drop (`test_postprocess`), pydantic-конфиг (`test_config`), инжект с восстановлением буфера (`test_inject`).

## Стиль кода

Код в проекте намеренно без docstring'ов и поясняющих комментариев; имена и типы несут нагрузку. Follow suit — не добавляй комментарии к тому, что очевидно читается из кода.
