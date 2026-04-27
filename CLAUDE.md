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

Скрипты-обёртки в `scripts/`: `run.ps1`, `test.ps1`, `build_exe.ps1`, плюс ручные smoke-тесты `smoke_asr.py`, `smoke_ui.py`, `smoke_settings.py`, `smoke_files.py`. Для быстрой итерации над UI / ASR изолированно вызывай их через `uv run python scripts/smoke_ui.py`.

## Архитектура

Основной поток — Qt main (`src/transcrb/app.py`), координатор состояний. Конечный автомат `State`: `LOADING → IDLE → RECORDING → PROCESSING → IDLE`. Все переходы идут через `TranscrbApp`, остальные потоки только эмитят Qt-сигналы с `QueuedConnection`.

Четыре потока, все общаются через `signals.py`:

1. **Qt main** — оркестрация состояний, вставка текста, overlay, tray, settings.
2. **PortAudio callback** (`audio/capture.py`) — пишет сэмплы в ring buffer, режет на чанки по VAD (скользящий RMS через prefix-sum), эмитит `on_chunk`. На тишину ≥ `chunk_silence_s` после достижения `chunk_min_s` — cut; иначе force cut на `chunk_max_s`. Эта логика горячая, изменения вроде смены алгоритма тишины обязаны сохранять prefix-sum инвариант (см. `_find_silence_cut`).
3. **keyboard hook** (`hotkey.py`, lib `keyboard`) — одна клавиша обрабатывается через сравнение `event.name` (именно так различается `right ctrl` vs `left ctrl`), комбинации — через `keyboard.is_pressed`. Debounce общий.
4. **AsrWorker QThread** (`asr/worker.py`) — `queue.PriorityQueue` из кортежей `(priority, seq, item)`: hotkey/`_Prepare`/`_Reload` priority 0, `_FileRequest` priority 1, stop priority −1. Hotkey-задача всегда выскакивает раньше любого файлового чанка, поэтому переключение «файл → живая речь» занимает максимум время одного file-чанка. На `queue.get(timeout=idle_unload_s)` по `Empty` — выгрузка модели из VRAM, `loaded` / `unloaded` сигналы тикают трей. Hotkey-результат идёт в `ready`, файловый — в `file_chunk_ready(job_id, chunk_idx, text, t_start, t_end)`.

WhisperEngine (`asr/engine.py`) — обёртка `faster_whisper.WhisperModel`. При падении CUDA load делает автоматический fallback на CPU/int8. `warmup()` на 1 секунде нулей обязателен после load — первый реальный вызов иначе в 3-5× медленнее. Модели качаются с `Systran/faster-whisper-<name>` в `%APPDATA%\WinWhisp\models\<name>\`.

Пост-процессинг (`text/postprocess.py`): словарные замены — единый regex с longest-match-first сортировкой ключей и `(?<!\w)...(?!\w)` для границ Unicode. `preserve_sentence_case` капитализирует букву в начале предложения уже после замен. `hallucinations` (`vocab.yaml`) — блок-лист фраз, возвращаемых Whisper на тишине, дропаются молча. Также дропаются «prompt echo» — когда модель вернула кусок `initial_prompt` вместо транскрипта (`_is_prompt_echo` в worker).

Инжект (`text/inject.py`): stash буфера → copy → `Ctrl+V` → restore. Восстанавливается только `CF_UNICODETEXT`. Режим `on_focus_change`:
- `inject` — вставлять всегда, даже если фокус сменился (опасно, но просится для IDE).
- `notify` (default) — при смене фокуса: текст в буфер, overlay-пилюля → «результат-режим» с кнопкой «Вставить ещё раз» (`overlay.result_hold_ms`).
- `skip` — тихо копировать в буфер.

Overlay (`ui/overlay.py`) — frameless, always-on-top, click-through во время записи (WS_EX_TRANSPARENT). В результат-режиме click-through снимается, но фокус не перехватывается, чтобы `Ctrl+V` летел в предыдущее поле.

## Распознавание файлов

`asr/file_pipeline.py` извлекает звуковую дорожку через ffmpeg subprocess (`-f f32le`, mono, 16k) и режет получившийся float32-массив через `split_audio` — тот же prefix-sum поиск тишины, что и в `audio/capture.py`, только на готовом массиве. Список расширений `SUPPORTED_EXTENSIONS` собран в одном месте.

`asr/file_manager.py` (`FileManager`) — координатор очереди: один файл за раз обрабатывается на уровне ffmpeg-extraction (фоновый `threading.Thread`), один чанк за раз in-flight в воркере. Это даёт точку прерывания: hotkey попадает в PriorityQueue с priority 0, отрабатывается сразу после текущего file-чанка, FileManager ждёт `file_chunk_ready` и только потом отправляет следующий. Сохраняет `.txt` и `.srt` в `transcripts_dir()` (по дефолту `Documents\WinWhisp\transcripts\<stem>_<timestamp>.{txt,srt}`).

UI: вкладка «Файлы» в `ui/files_page.py` (drop-зона + список заданий с прогрессом), встраивается в `ui/settings_window.py` как страница sidebar `files`. В трее пункт «Файлы…» открывает окно сразу на этом разделе и показывает счётчик активных заданий через `set_files_count`. Drop-zone принимает только `is_supported(path)` — остальное игнорируется.

ffmpeg ищется в `paths.ffmpeg_path()`: сначала bundled в `resources/bin/ffmpeg.exe` (для frozen-сборки и опционально для dev), затем `shutil.which("ffmpeg")`. В CI workflow `release.yml` ffmpeg скачивается перед PyInstaller'ом и кладётся в `resources/bin/`. В dev: либо ffmpeg в PATH, либо вручную скопируй `ffmpeg.exe` в `resources/bin/`. Папка `resources/bin/` в `.gitignore` — бинарь не коммитится.

## Пути и фрозен-режим

`paths.py` разделяет dev и PyInstaller-билд. `resources_dir()` в frozen-режиме возвращает `sys._MEIPASS/resources`, в dev — `<repo>/resources`. Все изменяемые данные (config, vocab, models, logs) всегда в `%APPDATA%\WinWhisp\`, и в dev и в frozen. Python-пакет по-прежнему называется `transcrb` (импорты `from transcrb.*`), но бренд и пути пользователя — `WinWhisp`.

## CUDA DLL-и

`_cuda_path.py` импортируется самым первым (даже до Qt), вызывает `os.add_dll_directory()` для `nvidia-cublas-cu12` и `nvidia-cudnn-cu12`, которые приходят как pip-пакеты. Без этого `WhisperModel(device="cuda")` падает с `cublas64_12.dll not found`. При смене зависимостей на другую версию CUDA обновить список путей в `_add_nvidia_dll_dirs`.

## Reload конфига

GUI настроек живёт в `ui/settings_window.py` (sidebar с разделами «Дашборд», «Файлы», «История», конфиги, логи). Часть полей применяется по ходу через `config_changed` сигнал, часть требует перезапуска. Также можно редактировать `%APPDATA%\WinWhisp\config.yaml` / `vocab.yaml` вручную — трей → «Перезагрузить конфиг» применяет vocab и некоторые поля на лету через `_on_reload`. Смена `hotkey.combo`, `asr.*`, `audio.device/samplerate`, размеров overlay требует полного перезапуска приложения — горячего применения не предусмотрено.

## Hotkey `right ctrl`

Библиотека `keyboard` исторически не различала left/right Ctrl. Текущая реализация читает `event.name == "right ctrl"` напрямую, и это работает. При добавлении новых «односторонних» клавиш (`right shift`, `right alt`, `right win`) поддерживать тот же путь — через `_handle_single`.

## Тесты

`pytest.ini_options` в `pyproject.toml` закрепляет `pythonpath = ["src"]`, поэтому импорты `from transcrb.*` работают без установки пакета. Тесты чистые — не требуют GPU, микрофона или Whisper (всё мокается или работает на уровне чистых функций). Покрывают: VAD-чанкинг (`test_audio_buffer`), `initial_prompt` с лимитом 224 токена (`test_vocab`), longest-match regex и hallucination-drop (`test_postprocess`), pydantic-конфиг (`test_config`), инжект с восстановлением буфера (`test_inject`).

## Стиль кода

Код в проекте намеренно без docstring'ов и поясняющих комментариев; имена и типы несут нагрузку. Follow suit — не добавляй комментарии к тому, что очевидно читается из кода.

## Релизы и версионирование

Сборка exe/installer/zip происходит только в GitHub Actions (`.github/workflows/release.yml`) при push тега `v*`. Workflow сам патчит `__version__` в `src/transcrb/__init__.py` из имени тега и публикует GitHub Release. Локально `pyinstaller` использовать только для отладки сборки — production-артефакт всегда из CI.

Схема версии — SemVer `MAJOR.MINOR.PATCH`:

- **MAJOR (`X.0.0`)** — несовместимые изменения формата `config.yaml` / `vocab.yaml`, переезд `%APPDATA%\WinWhisp\`, смена CUDA-рантайма, что-либо ломающее существующие установки. Bump делать осознанно, обычно вместе с миграционным кодом.
- **MINOR (`0.X.0`)** — новая стабильная версия: фича готова, протестирована, заявляется как релиз для пользователей. PATCH сбрасывается в 0.
- **PATCH (`0.0.X`)** — обычный коммит, меняющий runtime: багфиксы, мелкие улучшения, твики дефолтов, обновления зависимостей, изменения в `packaging/`, `resources/`, `src/transcrb/**`.

Когда **обязательно** тегать (= собирать exe):

- любой коммит в `src/transcrb/**`
- любой коммит в `packaging/transcrb.spec` или `packaging/installer.iss`
- любой коммит, меняющий `resources/**` (vocab, иконки, defaults)
- bump зависимостей в `pyproject.toml` / `uv.lock`, влияющий на runtime

Когда **не нужно** тегать (exe не меняется — пустая сборка только жжёт CI-минуты):

- изменения только в `tests/**`
- изменения только в `scripts/**` (smoke / dev-обёртки)
- правки `CLAUDE.md`, `README.md`, `.gitignore`, документации
- правки `.github/workflows/**`, не связанные с release-логикой
- рефакторинг dev-only файлов

По умолчанию правило простое: один коммит, влияющий на exe = один тег. Стэкать несколько таких коммитов под один тег можно, только если они идут подряд и логически связаны.

### Процедура релиза

```powershell
# после того как изменения закоммичены и запушены в main
git tag v0.1.1                # PATCH bump
git push origin v0.1.1        # триггерит CI → exe + installer + GitHub Release
```

Для stable bump:

```powershell
git tag v0.2.0                # MINOR, PATCH сброшен в 0
git push origin v0.2.0
```

Перед тегом синхронизировать `__version__` в `src/transcrb/__init__.py` с будущим тегом отдельным коммитом — CI всё равно перезапишет его при сборке, но dev-запуск из исходников должен показывать корректную версию.

Pre-release: суффикс `-rc1`, `-beta1` (тег `v0.2.0-rc1`) — release помечается prerelease автоматически (CI смотрит на наличие `-` в версии).

### CHANGELOG.md

`CHANGELOG.md` в корне репо — единственный источник release notes для GitHub Release. Формат — [Keep a Changelog 1.1.0](https://keepachangelog.com/ru/1.1.0/), SemVer. CI извлекает блок `## [X.Y.Z]` из этого файла и подставляет его в тело релиза; если блока для тега нет — сборка падает.

Структура файла:

```markdown
# Changelog

Все значимые изменения проекта документируются здесь.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]
### Added
- Описание новой фичи, которая ещё не вышла в релиз.

## [0.2.0] - 2026-05-10
### Added
- Поддержка hotkey `right alt` для ноутбуков без `right ctrl`.

### Changed
- Whisper-модель по умолчанию — `large-v3-turbo` вместо `large-v3`.

### Fixed
- Падение при первом запуске без CUDA — теперь fallback на CPU/int8.

## [0.1.1] - 2026-04-28
### Fixed
- VAD не резал чанки длиннее 30 секунд при тихой речи.
```

#### Правила для AI-коммитов

1. **Каждый коммит, который влияет на exe, должен дописывать запись в `## [Unreleased]`** в том же коммите. Если секции `[Unreleased]` нет — создать её первой над верхней версией. Если запись очевидно «не влияет на exe» (тесты, доки, scripts) — CHANGELOG не трогать.
2. **При тегировании релиза** переименовать `## [Unreleased]` в `## [X.Y.Z] - YYYY-MM-DD` (абсолютная дата, ISO-8601, в локальной TZ репо), создать новую пустую `## [Unreleased]` сверху. Дата = дата коммита тега, не текущая «человеческая» дата из контекста.
3. **Допустимые подзаголовки** (только эти, в этом порядке, пустые секции опускать):
   - `### Added` — новая функциональность для пользователя.
   - `### Changed` — изменение в существующем поведении или дефолтах.
   - `### Deprecated` — функции, помеченные на удаление в будущих релизах.
   - `### Removed` — удалённая функциональность.
   - `### Fixed` — исправления багов.
   - `### Security` — фиксы уязвимостей.
4. **Стиль записи** — одно предложение, прошедшее или настоящее время, активный залог, точка в конце, на русском. Описывать **что увидит пользователь**, а не как это сделано в коде.
   - Хорошо: «Добавлена поддержка hotkey `right alt`.»
   - Плохо: «Рефакторинг `_handle_single` в `hotkey.py` для поддержки right alt.»
5. **Что писать**: пользовательские изменения — фичи, фиксы багов, изменения дефолтов, новые требования к окружению, breaking changes (формат конфига, путь к данным).
6. **Что не писать**: рефакторинг без изменения поведения, правки тестов, обновления `CLAUDE.md`, dev-скрипты, изменения CI, мелкие bump'ы зависимостей без user-visible эффекта.
7. **Breaking changes** при MAJOR-bump'е выносить в отдельный подблок `### Breaking` (нестандартный для Keep a Changelog, но мы его допускаем) **перед** остальными подзаголовками — в нём явно описать действия пользователя для миграции.
8. **Порядок версий в файле — обратный хронологический** (свежее сверху), `[Unreleased]` всегда самой первой.
9. **Не выдумывать ссылок на коммиты/PR** в записях — голый текст. Никаких эмоджи.
