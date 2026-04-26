import sys

from loguru import logger

from transcrb.paths import log_dir


def _reconfigure_stdio_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def setup_logging(level: str = "INFO") -> None:
    _reconfigure_stdio_utf8()
    logger.remove()
    logger.add(
        log_dir() / "winwhisp.log",
        level=level,
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
        backtrace=False,
        diagnose=False,
    )
    if sys.stderr is not None:
        logger.add(sys.stderr, level=level, colorize=False)
