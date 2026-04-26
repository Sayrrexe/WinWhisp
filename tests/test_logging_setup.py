import sys
from pathlib import Path

import pytest
from loguru import logger


@pytest.fixture(autouse=True)
def _clean_loguru():
    yield
    for hid in list(logger._core.handlers.keys()):
        try:
            logger.remove(hid)
        except Exception:
            pass


@pytest.fixture
def log_tmp(tmp_path, monkeypatch):
    log_path = tmp_path / "logs"
    log_path.mkdir()
    monkeypatch.setattr("transcrb.logging_setup.log_dir", lambda: log_path)
    return log_path


def _handlers():
    return dict(logger._core.handlers)


def _file_handlers(log_path: Path):
    result = []
    for hid, handler in logger._core.handlers.items():
        sink = handler._sink
        if hasattr(sink, "_path") and str(sink._path).startswith(str(log_path)):
            result.append(handler)
    return result


def _stderr_handlers():
    result = []
    for hid, handler in logger._core.handlers.items():
        sink = handler._sink
        if hasattr(sink, "_stream") and sink._stream is sys.stderr:
            result.append(handler)
    return result


class TestSetupLoggingHandlerCount:
    def test_creates_exactly_two_handlers(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        assert len(logger._core.handlers) == 2

    def test_idempotent_two_calls_still_two_handlers(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        setup_logging()
        assert len(logger._core.handlers) == 2

    def test_idempotent_three_calls_still_two_handlers(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        setup_logging()
        setup_logging()
        assert len(logger._core.handlers) == 2


class TestSetupLoggingFileHandler:
    def test_file_created_in_log_dir(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        assert len(handlers) == 1

    def test_file_named_winwhisp_log(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        assert Path(handlers[0]._sink._path).name == "winwhisp.log"

    def test_file_handler_level_info_default(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        assert handlers[0]._levelno == 20  # INFO

    def test_file_handler_level_debug_when_specified(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging("DEBUG")
        handlers = _file_handlers(log_tmp)
        assert handlers[0]._levelno == 10  # DEBUG

    def test_file_handler_rotation_5mb(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        rf = handlers[0]._sink._rotation_function
        assert rf is not None
        assert rf.keywords.get("size_limit") == 5_000_000

    def test_file_handler_retention_5(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        retf = handlers[0]._sink._retention_function
        assert retf is not None
        assert retf.keywords.get("number") == 5

    def test_file_handler_encoding_utf8(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        assert handlers[0]._sink.encoding == "utf-8"

    def test_file_handler_backtrace_false(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        assert handlers[0]._exception_formatter._backtrace is False

    def test_file_handler_diagnose_false(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _file_handlers(log_tmp)
        assert handlers[0]._exception_formatter._diagnose is False


class TestSetupLoggingStderrHandler:
    def test_stderr_handler_present(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        assert len(_stderr_handlers()) == 1

    def test_stderr_handler_level_info_default(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _stderr_handlers()
        assert handlers[0]._levelno == 20

    def test_stderr_handler_level_debug_when_specified(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging("DEBUG")
        handlers = _stderr_handlers()
        assert handlers[0]._levelno == 10

    def test_stderr_handler_colorize_false(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        handlers = _stderr_handlers()
        assert handlers[0]._colorize is False


class TestSetupLoggingDirCreation:
    def test_log_dir_not_required_to_exist_beforehand(self, tmp_path, monkeypatch):
        log_path = tmp_path / "not_yet_created"
        log_path.mkdir()
        monkeypatch.setattr("transcrb.logging_setup.log_dir", lambda: log_path)
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        assert (log_path / "winwhisp.log").exists()

    def test_log_file_is_writable_after_setup(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        logger.info("test message for write check")
        log_file = log_tmp / "winwhisp.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test message for write check" in content


class TestSetupLoggingLevelParam:
    @pytest.mark.parametrize(
        "level,expected_no",
        [
            ("INFO", 20),
            ("DEBUG", 10),
            ("WARNING", 30),
            ("ERROR", 40),
        ],
    )
    def test_level_applied_to_both_handlers(self, log_tmp, level, expected_no):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging(level)
        for hid, handler in logger._core.handlers.items():
            assert handler._levelno == expected_no

    def test_default_level_is_info(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        logger.remove()
        setup_logging()
        for hid, handler in logger._core.handlers.items():
            assert handler._levelno == 20


class TestSetupLoggingStdioReconfigure:
    def test_reconfigure_exception_is_silenced(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        original = sys.stdout.reconfigure

        def boom(*a, **kw):
            raise AttributeError("no reconfigure")

        sys.stdout.reconfigure = boom
        try:
            setup_logging()
        except Exception:
            pytest.fail("setup_logging must not propagate reconfigure errors")
        finally:
            sys.stdout.reconfigure = original

    def test_setup_does_not_raise_in_normal_conditions(self, log_tmp):
        from transcrb.logging_setup import setup_logging

        setup_logging()
