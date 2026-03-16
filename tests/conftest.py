# tests/conftest.py
"""
Shared pytest fixtures for arcade-video-scanner tests.
"""
import os
import json
import tempfile
import threading
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(tmp_path) -> Path:
    """Return a path for a temporary SQLite database (isolated per test)."""
    return tmp_path / "test_media.db"


@pytest.fixture
def sample_video_entry():
    """Minimal valid VideoEntry-like dict."""
    return {
        "FilePath": "/fake/video.mp4",
        "Status": "OK",
        "Size_MB": 100.0,
        "Codec": "h264",
        "Bitrate_kbps": 3000,
        "Width": 1920,
        "Height": 1080,
        "Duration": 60.0,
        "mtime": 1700000000.0,
        "favorite": False,
        "vaulted": False,
        "tags": [],
    }
