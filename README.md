# WinWhisp

Фоновая push-to-talk диктовка для Windows. Зажал хоткей, наговорил, отпустил — распознанный текст вставляется в активное поле любого приложения. Работает локально: `faster-whisper large-v3` на GPU, живая нарезка по тишине, кастомный словарь под программистские термины.

## Свойства

- **Локально.** Модель и аудио не покидают машину.
- **Live chunking.** Аудио режется по тишине (VAD), слова распознаются и вставляются пока ты ещё говоришь.
- **Idle unload.** Модель выгружается из VRAM после 60 секунд простоя, грузится обратно при нажатии.
- **Release tail.** После отпускания кнопки 500 мс дослушивается — на случай, если отпустил чуть раньше.
- **Словарь.** `hotwords` (boost при beam search) и `replacements` (regex longest-match-first). Галлюцинации вроде «Субтитры делал DimaTorzok» блочатся.
- **Overlay.** Пилюля внизу экрана: эквалайзер во время записи, крутилка «Обрабатываю…» пока модель жуёт остаток, «Скопировано» с кнопкой «Вставить ещё раз», если фокус сменился.

## Требования

- Windows 10/11.
- NVIDIA GPU с актуальным драйвером (проверено на RTX 3060 12 GB, driver 591.86 / CUDA 13.1). CUDA-тулкит ставить не надо — бандлятся колёса `nvidia-cublas-cu12` и `nvidia-cudnn-cu12`.
- Без GPU тоже работает: в конфиге `asr.device: cpu`, `asr.compute_type: int8`.
- [`uv`](https://docs.astral.sh/uv/) для установки Python 3.11 и зависимостей.

## Быстрый старт

```powershell
git clone https://github.com/Sayrrexe/WinWhisp.git
cd WinWhisp
uv sync                      # Python 3.11 + все зависимости
uv run python -m transcrb    # первый запуск скачивает модель ~3 ГБ в %APPDATA%
```

## Использование

1. Зажми хоткей (по умолчанию — `right ctrl`).
2. Говори.
3. Отпусти.

Текст вставится через `Ctrl+V` в активное поле. Тап короче `min_hold_ms` (250 мс) отбрасывается. Если фокус сменился — текст копируется в буфер, в пилюле появляется кнопка «Вставить ещё раз».

Конфиг и словарь — в `%APPDATA%\WinWhisp\` (`config.yaml`, `vocab.yaml`). Кэш моделей и логи тоже там.

## Конфиг

`config.yaml` прогоняется через pydantic, создаётся с дефолтами при старте. Самое важное:

```yaml
hotkey:
  combo: right ctrl # любая комбинация из библиотеки keyboard
  min_hold_ms: 250 # короче — тап отбрасывается
  release_tail_ms: 500 # дослушивать после отпускания

audio:
  chunk_min_s: 1.5 # мин. длина live-чанка
  chunk_max_s: 8.0 # макс. (force cut)
  chunk_silence_s: 0.25 # окно тишины для разреза
  chunk_silence_rms: 0.015

asr:
  model: large-v3
  compute_type: float16 # или int8_float16, int8
  device: cuda # или cpu
  language: ru
  idle_unload_s: 60

injection:
  on_focus_change: notify # notify | inject | skip
```

Полный набор полей — `src/transcrb/config.py`. Правь YAML, затем трей → «Перезагрузить конфиг»; смена хоткея, модели, device или размеров оверлея требует полного перезапуска.

## Словарь (`vocab.yaml`)

```yaml
hotwords: # попадают в initial_prompt и в hotwords= beam search
  - gitignore
  - pull request
  - PySide6

replacements: # regex longest-match-first, Unicode-границы
  "гит игнор": "gitignore"
  "коммит": "commit"
  "пул реквест": "pull request"

hallucinations: # exact match или substring-якорь с префиксом ~
  - "Спасибо за просмотр."
  - "~DimaTorzok"
  - "~субтитры делал"
```

## Разработка

```powershell
uv run pytest                                      # весь набор
uv run pytest -k vocab                             # по имени
uv run python scripts/smoke_asr.py                 # прогон транскрибации
uv run pyinstaller --clean packaging/transcrb.spec # сборка .exe в dist\winwhisp\
```

## Траблшутинг

**`right ctrl` срабатывает на левый Ctrl.** Текущий код читает `event.name == "right ctrl"` — это работает. Если конфликт — поставь другую комбинацию в конфиге.

**`cublas64_12.dll not found`.** `uv pip list | findstr nvidia` — должны быть `nvidia-cublas-cu12` и `nvidia-cudnn-cu12`.

**Не вставляется в Task Manager / elevated окна.** UIPI: запусти WinWhisp от администратора.

**Whisper вставил «Спасибо за просмотр» или подобное.** Добавь фразу в `vocab.yaml → hallucinations`, трей → «Перезагрузить конфиг». С префиксом `~` — substring-матч.
