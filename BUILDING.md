# Building WinWhisp from source

If you'd rather not run the unsigned release binary, you can reproduce it locally. The same steps drive the GitHub Actions release pipeline.

## Prerequisites

- Windows 10 / 11 x64.
- [`uv`](https://docs.astral.sh/uv/) — pulls Python 3.11 and all dependencies into a local venv. No system Python needed.
- (Optional, only for the installer) [Inno Setup 6](https://jrsoftware.org/isinfo.php) — install via `choco install innosetup -y` or download from the official site.

## Run from source

```powershell
git clone https://github.com/Sayrrexe/WinWhisp.git
cd WinWhisp
uv sync                      # Python 3.11 + all deps into .venv
uv run python -m transcrb
```

That's enough — what you get is functionally identical to the installed app, just without the `.exe` wrapper, the start-menu shortcut, and autostart.

## PyInstaller bundle (no installer)

```powershell
uv run pyinstaller --clean packaging/transcrb.spec
# → dist\winwhisp\winwhisp.exe
```

The bundle is self-contained — it ships the Python runtime, Qt, and the bundled NVIDIA cuBLAS / cuDNN wheels. You can copy `dist\winwhisp\` anywhere and run `winwhisp.exe`.

## Reproducible installer

Same artifact CI publishes:

```powershell
.\scripts\build_installer.ps1
# → dist\installer\WinWhisp-<version>-setup.exe
```

The script runs PyInstaller, then invokes Inno Setup against `packaging\installer.iss`. The resulting setup is byte-for-byte the same shape as the GitHub Release one (signature aside — releases are unsigned too, but the SHA-256 of the bundled tree should match commit-for-commit).

## Tests

```powershell
uv run pytest                                # full suite
uv run pytest -k vocab                       # by name
uv run python scripts/smoke_asr.py           # end-to-end transcription smoke
uv run python scripts/smoke_ui.py            # overlay / tray smoke
```

Tests don't need a GPU, a microphone, or the Whisper model — every external dependency is either mocked or exercised at the pure-function level.

## Releases

Tagging triggers everything. Push a `vX.Y.Z` tag and `.github/workflows/release.yml`:

1. patches `__version__` in `src/transcrb/__init__.py` to match the tag,
2. builds the PyInstaller bundle,
3. compiles the Inno Setup installer + a portable `.zip`,
4. extracts the matching `## [X.Y.Z]` block from `CHANGELOG.md` as release notes,
5. publishes a GitHub Release with both artifacts.

The release fails if `CHANGELOG.md` has no section for the tag, so update the changelog **in the same commit** that bumps the version. Pre-release tags (`v0.2.0-rc1`, `v0.2.0-beta1`) are auto-flagged as pre-releases by the workflow.

## Layout

```
src/transcrb/        application code (package name stays `transcrb`, brand is `WinWhisp`)
  app.py             Qt main, state machine
  audio/capture.py   PortAudio callback + VAD chunking
  asr/engine.py      faster-whisper wrapper, CUDA → CPU/int8 fallback
  asr/worker.py      QThread, eager-load + idle-unload
  text/postprocess.py  longest-match-first regex, hallucination drop
  text/inject.py     clipboard stash → Ctrl+V → restore
  ui/                overlay, tray, onboarding
packaging/           PyInstaller spec + Inno Setup script
scripts/             dev wrappers and smoke runners
resources/           bundled defaults (icon, vocab.yaml)
tests/               pytest, no GPU/mic required
```

User data — `config.yaml`, `vocab.yaml`, models, logs — always lives in `%APPDATA%\WinWhisp\`, in both dev and frozen builds.
