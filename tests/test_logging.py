"""Tests for logging configuration."""

from __future__ import annotations

import json
import logging

from telemachus.config import TelemachusConfig
from telemachus.logging_config import JsonFormatter, PlainFormatter, get_logger, setup_logging


def _close_all_handlers(logger: logging.Logger) -> None:
    """Close all handlers on a logger to release file handles."""
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


class TestLoggingSetup:
    """Tests for logging initialization."""

    def test_setup_logging_returns_root_logger(self, test_config: TelemachusConfig) -> None:
        """setup_logging should return the 'telemachus' root logger."""
        logger = setup_logging(test_config)
        try:
            assert logger.name == "telemachus"
            assert logger.level == logging.INFO
        finally:
            _close_all_handlers(logger)

    def test_setup_logging_creates_log_file(self, test_config: TelemachusConfig) -> None:
        """setup_logging should create the log directory and file."""
        logger = setup_logging(test_config)
        try:
            log_file = test_config.paths.log_dir / "telemachus.log"
            assert test_config.paths.log_dir.exists()
            assert log_file.exists()
        finally:
            _close_all_handlers(logger)

    def test_get_logger_returns_child_logger(self, test_config: TelemachusConfig) -> None:
        """get_logger should return a child logger under telemachus namespace."""
        logger = setup_logging(test_config)
        try:
            child = get_logger("memory.store")
            assert child.name == "telemachus.memory.store"
        finally:
            _close_all_handlers(logger)

    def test_setup_logging_clears_previous_handlers(self, test_config: TelemachusConfig) -> None:
        """Calling setup_logging twice should not duplicate handlers."""
        logger1 = setup_logging(test_config)
        handler_count1 = len(logger1.handlers)
        logger2 = setup_logging(test_config)
        try:
            handler_count2 = len(logger2.handlers)
            assert handler_count1 == handler_count2
        finally:
            _close_all_handlers(logger2)


class TestJsonFormatter:
    """Tests for the JSON log formatter."""

    def test_formats_record_as_json(self) -> None:
        """JsonFormatter should produce valid JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="telemachus.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "telemachus.test"
        assert parsed["message"] == "Test message"
        assert parsed["line"] == 42

    def test_includes_exception_info(self) -> None:
        """JsonFormatter should include exception details when present."""
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "test error"


class TestPlainFormatter:
    """Tests for the plain text log formatter."""

    def test_formats_record_as_plain_text(self) -> None:
        """PlainFormatter should produce human-readable text."""
        formatter = PlainFormatter()
        record = logging.LogRecord(
            name="telemachus.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "INFO" in output
        assert "Test message" in output
        assert "telemachus.test" in output
