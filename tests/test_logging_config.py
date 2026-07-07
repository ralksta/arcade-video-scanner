"""
Tests for arcade_scanner.logging_config
"""
import logging
import logging.handlers
from pathlib import Path

import pytest


def _fresh_setup(log_dir, level="INFO"):
    """Import + call setup_logging in a clean state (clear handlers first)."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)  # reset level

    from arcade_scanner.logging_config import setup_logging
    setup_logging(level=level, log_dir=log_dir)
    return root


@pytest.fixture(autouse=True)
def restore_root_logger():
    """Snapshot-restore root logger around each test."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    # Teardown: close file handlers created by our code, then restore
    for h in root.handlers:
        if h not in saved_handlers:
            h.close()
    root.handlers.clear()
    root.handlers.extend(saved_handlers)
    root.setLevel(saved_level)


class TestSetupLogging:
    def test_creates_two_handlers(self, tmp_path):
        root = _fresh_setup(tmp_path)
        # One StreamHandler + one RotatingFileHandler
        assert len(root.handlers) == 2

    def test_log_file_created(self, tmp_path):
        _fresh_setup(tmp_path)
        log_file = tmp_path / "arcade_scanner.log"
        assert log_file.exists()

    def test_idempotent(self, tmp_path):
        """Calling setup_logging twice must not add duplicate handlers."""
        _fresh_setup(tmp_path)
        from arcade_scanner.logging_config import setup_logging
        setup_logging(log_dir=tmp_path)  # second call
        root = logging.getLogger()
        assert len(root.handlers) == 2

    def test_log_level_respected(self, tmp_path):
        root = _fresh_setup(tmp_path, level="DEBUG")
        assert root.level == logging.DEBUG

    def test_missing_log_dir_auto_created(self, tmp_path):
        nested = tmp_path / "deep" / "nested"
        _fresh_setup(nested)
        assert nested.is_dir()

    def test_file_handler_is_rotating(self, tmp_path):
        _fresh_setup(tmp_path)
        root = logging.getLogger()
        file_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1
