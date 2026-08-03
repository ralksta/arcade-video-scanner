"""
Tests for arcade_scanner.database.sqlite_store
Focus: indexes created, write-lock thread safety, cleanup_old_jobs TTL,
       upsert/remove round-trip.
"""
import threading
import time
from unittest.mock import MagicMock, patch

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
        """A reentrant lock guards the shared connection.

        Reentrancy matters: _notify_change fires inside the lock, so a callback
        that re-enters the store would deadlock on a plain Lock.
        """
        assert isinstance(store._write_lock, type(threading.RLock()))

        # Reentrant in practice, not just by type.
        with store._write_lock:
            with store._write_lock:
                pass

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


# ---------------------------------------------------------------------------
# Encoding queue claim semantics
#
# get_next_pending is documented as "Atomically claim the oldest pending job".
# The server is a ThreadingTCPServer and scripts/mac_worker.py polls the queue,
# so several workers can claim concurrently. A job handed to two workers means
# the same file gets encoded twice, with both encodes racing on one output path.
# ---------------------------------------------------------------------------

class TestQueueClaimIsExclusive:
    def test_single_job_goes_to_exactly_one_caller(self, store):
        """With one pending job and many concurrent callers, only one wins."""
        rounds = 40
        n_threads = 8
        double_claims = []

        for round_nr in range(rounds):
            store._conn.execute("DELETE FROM encoding_queue")
            store.queue_encode(f"/fake/clip_{round_nr}.mp4", size_bytes=1234)

            barrier = threading.Barrier(n_threads)
            claims = []
            claims_lock = threading.Lock()

            def claim():
                barrier.wait()  # maximise overlap on the select/update window
                job = store.get_next_pending(worker_id=f"w{threading.get_ident()}")
                if job is not None:
                    with claims_lock:
                        claims.append(job["id"])

            threads = [threading.Thread(target=claim) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            if len(claims) > 1:
                double_claims.append((round_nr, claims))

        assert not double_claims, (
            f"{len(double_claims)}/{rounds} rounds handed one job to multiple "
            f"workers, e.g. {double_claims[0]}"
        )

    def test_every_job_is_claimed_exactly_once(self, store):
        """Draining a full queue from several threads yields no duplicates."""
        n_jobs = 60
        n_threads = 8

        store._conn.execute("DELETE FROM encoding_queue")
        for i in range(n_jobs):
            store.queue_encode(f"/fake/bulk_{i}.mp4", size_bytes=i)

        claims = []
        claims_lock = threading.Lock()
        barrier = threading.Barrier(n_threads)

        def drain():
            barrier.wait()
            while True:
                job = store.get_next_pending(worker_id="bulk")
                if job is None:
                    return
                with claims_lock:
                    claims.append(job["id"])

        threads = [threading.Thread(target=drain) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duplicates = [job_id for job_id in set(claims) if claims.count(job_id) > 1]
        assert not duplicates, f"jobs claimed more than once: {duplicates}"
        assert len(claims) == n_jobs, f"claimed {len(claims)} of {n_jobs} jobs"

    def test_claimed_job_is_marked_downloading(self, store):
        """A successful claim moves the row out of 'pending'."""
        store._conn.execute("DELETE FROM encoding_queue")
        store.queue_encode("/fake/single.mp4")

        job = store.get_next_pending(worker_id="worker-a")
        assert job is not None

        row = store._conn.execute(
            "SELECT status, worker_id FROM encoding_queue WHERE id = ?", (job["id"],)
        ).fetchone()
        assert row["status"] == "downloading"
        assert row["worker_id"] == "worker-a"

        assert store.get_next_pending(worker_id="worker-b") is None

    def test_queue_encode_rejects_duplicate_pending_file(self, store):
        """The same file is not queued twice while a job for it is active."""
        store._conn.execute("DELETE FROM encoding_queue")

        first = store.queue_encode("/fake/dupe.mp4")
        second = store.queue_encode("/fake/dupe.mp4")

        assert first is not None
        assert second is None


# ---------------------------------------------------------------------------
# Concurrent reads on the shared connection
#
# One sqlite3.Connection is shared across server threads
# (check_same_thread=False). sqlite3.threadsafety is 3 on this build, so the C
# layer will not crash -- but Python's sqlite3 keeps a per-connection statement
# cache, and threads running the *same* SQL share one prepared statement. Two
# threads stepping it at once consume each other's rows.
#
# The failure is silent: no exception, just a wrong row count. _MediaCache then
# holds that result for 30 seconds.
# ---------------------------------------------------------------------------

class TestConcurrentReads:
    def _populate(self, store, n):
        from arcade_scanner.models.video_entry import VideoEntry
        store.bulk_upsert([
            VideoEntry(FilePath=f"/fake/clip_{i:05d}.mp4", Size_MB=float(i))
            for i in range(n)
        ])

    def test_concurrent_get_all_returns_the_whole_table_every_time(self, store):
        """Every reader must see all rows, no matter who else is reading."""
        rows = 800
        self._populate(store, rows)
        assert len(store.get_all()) == rows  # baseline, single threaded

        counts = []
        errors = []

        for _ in range(20):
            barrier = threading.Barrier(6)

            def reader():
                barrier.wait()
                try:
                    counts.append(len(store.get_all()))
                except Exception as exc:  # noqa: BLE001 - recording is the point
                    errors.append(f"{type(exc).__name__}: {exc}")

            threads = [threading.Thread(target=reader) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert errors == [], f"first failure: {errors[0]}"
        wrong = [c for c in counts if c != rows]
        assert not wrong, (
            f"{len(wrong)} of {len(counts)} concurrent reads returned a wrong row "
            f"count (saw {sorted(set(wrong))[:5]}, expected {rows})"
        )

    def test_reads_stay_correct_while_a_writer_runs(self, store):
        """A write in flight must not make a concurrent read lose rows."""
        from arcade_scanner.models.video_entry import VideoEntry

        rows = 500
        self._populate(store, rows)

        counts = []
        errors = []

        for round_nr in range(20):
            barrier = threading.Barrier(6)

            def reader():
                barrier.wait()
                try:
                    counts.append(len(store.get_all()))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"read {type(exc).__name__}: {exc}")

            def writer():
                barrier.wait()
                try:
                    store.upsert(VideoEntry(FilePath=f"/fake/clip_{round_nr:05d}.mp4",
                                            Size_MB=1.0))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"write {type(exc).__name__}: {exc}")

            threads = [threading.Thread(target=reader) for _ in range(5)]
            threads.append(threading.Thread(target=writer))
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert errors == [], f"first failure: {errors[0]}"
        # The writer only overwrites existing paths, so the count never changes.
        wrong = [c for c in counts if c != rows]
        assert not wrong, (
            f"{len(wrong)} of {len(counts)} reads saw a wrong row count "
            f"(saw {sorted(set(wrong))[:5]}, expected {rows})"
        )

    def test_lazy_connection_setup_is_not_raced(self, patch_config):
        """Several threads hitting a fresh store must share one connection."""
        from arcade_scanner.database.sqlite_store import SQLiteStore

        fresh = SQLiteStore()
        seen = []
        errors = []
        barrier = threading.Barrier(8)

        def touch():
            barrier.wait()
            try:
                fresh.count()
                seen.append(id(fresh._conn))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=touch) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"first failure: {errors[0]}"
        assert len(set(seen)) == 1, "threads ended up on different connections"
