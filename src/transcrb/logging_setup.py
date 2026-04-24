import sys

from loguru import logger

from transcrb.paths import log_dir


def setup_logging(level: str = "INFO") -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    logger.remove()
    logger.add(
        log_dir() / "transcrb.log",
        level=level,
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        sys.stderr,
        level=level,
        colorize=False,
    )
