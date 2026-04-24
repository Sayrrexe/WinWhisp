import os
import sys
from pathlib import Path


def _add_nvidia_dll_dirs() -> None:
    if sys.platform != "win32":
        return
    add = getattr(os, "add_dll_directory", None)
    if add is None:
        return
    try:
        import nvidia  # type: ignore

        path_list = list(getattr(nvidia, "__path__", []))
        if not path_list:
            return
        base = Path(path_list[0])
    except Exception:
        return
    for sub in ("cublas/bin", "cudnn/bin", "cuda_nvrtc/bin", "cuda_runtime/bin"):
        p = base / sub
        if p.exists():
            try:
                add(str(p))
                os.environ["PATH"] = f"{p}{os.pathsep}{os.environ.get('PATH', '')}"
            except OSError:
                pass


_add_nvidia_dll_dirs()
