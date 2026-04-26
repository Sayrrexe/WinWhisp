# PyInstaller spec — сборка: uv run pyinstaller --clean packaging/transcrb.spec
# На выходе: dist\winwhisp\winwhisp.exe + зависимые DLL (CUDA, cuDNN, PortAudio, ctranslate2).

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

binaries = []
for pkg in ("ctranslate2", "sounddevice", "nvidia.cublas", "nvidia.cudnn"):
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass

hiddenimports = []
for mod in ("faster_whisper", "ctranslate2"):
    try:
        hiddenimports += collect_submodules(mod)
    except Exception:
        pass
hiddenimports += [
    "win32clipboard",
    "win32gui",
    "win32api",
    "win32con",
]

datas = [
    ("../resources/icon.ico", "resources"),
    ("../resources/default_vocab.yaml", "resources"),
]
for pkg in ("faster_whisper", "ctranslate2"):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

a = Analysis(
    ["../src/transcrb/__main__.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["hooks"],
    excludes=["tkinter", "test", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="winwhisp",
    console=False,
    icon="../resources/icon.ico",
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="winwhisp",
)
