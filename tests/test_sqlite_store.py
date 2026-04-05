"""
Tests for arcade_scanner.database.sqlite_store
Focus: indexes created, write-lock thread safety, cleanup_old_jobs TTL,
       upsert/remove round-trip.
"""
import os
import sqlite3
import threading
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers & minimal mocks so we can import SQLiteStore without a real config
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_config(tmp_path):
    """Patch config.hidden_data_dir so SQLiteStore uses a temp DB."""
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.sqlite_store.config", mock_config):
        yield mock_config


@pytest.fixture
def store(patch_config):
    from arcade_scanner.database.sqlite_store import SQLiteStore
    s = SQLiteStore()
    s._ensure_connection()
    return s


# ---------------------------------------------------------------------------
# Schema / Indexes
# ---------------------------------------------------------------------------

class TestSchema:
    def test_media_table_exists(self, store):
        cur = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='media'"
        )
        assert cur.fetchone() is not None

    def test_encoding_queue_table_exists(self, store):
        cur = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='encoding_queue'"
        )
        assert cur.fetchone() is not None

    def test_indexes_created(self, store):
        cur = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        index_names = {row[0] for row in cur.fetchall()}
        for expected in ("idx_status", "idx_codec", "idx_size_mb", "idx_mtime"):
            assert expected in index_names, f"Missing index: {expected}"


# ---------------------------------------------------------------------------
# Thread safety – write lock
# ---------------------------------------------------------------------------

class TestWriteLock:
    def test_write_lock_exists(self, store):
        import threading
        assert isinstance(store._write_lock, threading.Lock)

    def test_concurrent_upserts_do_not_raise(self, store, tmp_path):
        """Multiple threads writing simultaneously should not corrupt the DB."""
        from arcade_scanner.models.video_entry import VideoEntry

        errors = []

        def worker(idx):
            try:
                entry = VideoEntry(
                    FilePath=f"/fake/video_{idx}.mp4",
                    Size_MB=float(idx),
                    Status="OK",
                )
                store.upsert(entry)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# cleanup_old_jobs
# ---------------------------------------------------------------------------

class TestCleanupOldJobs:
    def _insert_job(self, store, status, completed_at):
        store._conn.execute(
            "INSERT INTO encoding_queue (file_path, status, completed_at) VALUES (?,?,?)",
            ("/fake/file.mp4", status, completed_at),
        )

    def test_removes_old_completed_jobs(self, store):
        old_ts = int(time.time()) - (40 * 86400)  # 40 days ago
        self._insert_job(store, "done", old_ts)

        deleted = store.cleanup_old_jobs(older_than_days=30)
        assert deleted == 1

    def test_keeps_recent_jobs(self, store):
        recent_ts = int(time.time()) - (5 * 86400)  # 5 days ago
        self._insert_job(store, "done", recent_ts)

        deleted = store.cleanup_old_jobs(older_than_days=30)
        assert deleted == 0

    def test_keeps_pending_jobs(self, store):
        old_ts = int(time.time()) - (40 * 86400)
        self._insert_job(store, "pending", old_ts)

        deleted = store.cleanup_old_jobs(older_than_days=30)
        assert deleted == 0

    def test_multiple_old_jobs_cleaned(self, store):
        old_ts = int(time.time()) - (60 * 86400)
        for status in ("done", "failed", "cancelled"):
            self._insert_job(store, status, old_ts)

        deleted = store.cleanup_old_jobs(older_than_days=30)
        assert deleted == 3


# ---------------------------------------------------------------------------
# get_page() and count()
# ---------------------------------------------------------------------------

class TestGetPage:
    def _insert_entries(self, store, n):
        """Insert n VideoEntries into the store."""
        from arcade_scanner.models.video_entry import VideoEntry
        for i in range(n):
            store.upsert(VideoEntry(FilePath=f"/fake/video_{i:03d}.mp4", Size_MB=float(i)))

    def test_count_empty(self, store):
        assert store.count() == 0

    def test_count_after_inserts(self, store):
        self._insert_entries(store, 5)
        assert store.count() == 5

    def test_get_page_returns_list(self, store):
        self._insert_entries(store, 10)
        page = store.get_page(page=0, page_size=5)
        assert isinstance(page, list)

    def test_get_page_size_respected(self, store):
        self._insert_entries(store, 20)
        page = store.get_page(page=0, page_size=7)
        assert len(page) == 7

    def test_get_page_second_page(self, store):
        self._insert_entries(store, 10)
        page0 = store.get_page(page=0, page_size=5)
        page1 = store.get_page(page=1, page_size=5)
        # Both pages should exist and have different entries
        paths0 = {e.file_path for e in page0}
        paths1 = {e.file_path for e in page1}
        assert len(paths0) == 5
        assert len(paths1) == 5
        assert paths0.isdisjoint(paths1)

    def test_get_page_beyond_end_returns_empty(self, store):
        self._insert_entries(store, 5)
        page = store.get_page(page=99, page_size=10)
        assert page == []
