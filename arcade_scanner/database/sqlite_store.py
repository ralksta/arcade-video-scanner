"""
SQLite-backed Media Store.

Replaced the original full-file JSON store; the interface is unchanged:
    load(), save(), get_all(), get(path), upsert(entry), remove(path)

Benefits over the JSON format:
    - Instant row-level reads/writes (no full-file serialization)
    - O(1) indexed lookups by file_path
    - ACID guarantees for concurrent access
    - Scales to 100K+ entries without memory pressure
"""
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, List, Optional

from ..config import config
from ..models.video_entry import VideoEntry

logger = logging.getLogger(__name__)

# All VideoEntry fields → SQLite columns
# Primary key is file_path (TEXT). All other fields map 1:1.
_COLUMNS = [
    ("file_path", "TEXT PRIMARY KEY"),
    ("size_mb", "REAL DEFAULT 0"),
    ("bitrate_mbps", "REAL DEFAULT 0"),
    ("status", "TEXT DEFAULT 'OK'"),
    ("media_type", "TEXT DEFAULT 'video'"),
    ("codec", "TEXT DEFAULT 'unknown'"),
    ("duration_sec", "REAL DEFAULT 0"),
    ("width", "INTEGER DEFAULT 0"),
    ("height", "INTEGER DEFAULT 0"),
    ("audio_codec", "TEXT DEFAULT 'unknown'"),
    ("audio_channels", "INTEGER DEFAULT 0"),
    ("container_format", "TEXT DEFAULT 'unknown'"),
    ("profile", "TEXT DEFAULT ''"),
    ("level", "REAL DEFAULT 0"),
    ("pixel_format", "TEXT DEFAULT ''"),
    ("frame_rate", "REAL DEFAULT 0"),
    ("favorite", "INTEGER DEFAULT 0"),
    ("vaulted", "INTEGER DEFAULT 0"),
    ("tags", "TEXT DEFAULT '[]'"),
    ("thumb", "TEXT DEFAULT ''"),
    ("imported_at", "INTEGER DEFAULT 0"),
    ("mtime", "INTEGER DEFAULT 0"),
    ("original_path", "TEXT DEFAULT ''"),
    ("optimized_at", "INTEGER DEFAULT 0"),
]


class SQLiteStore:
    """
    SQLite-backed media metadata store.

    Thread-safe via one shared connection guarded by a reentrant lock. Every
    method that touches the connection takes the lock — reads included. See
    _write_lock for why reads cannot be left unguarded.
    """

    def __init__(self):
        self.db_file = os.path.join(config.hidden_data_dir, "media_library.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._migrated = False
        # Guards every use of the shared connection, reads included.
        #
        # sqlite3.threadsafety is 3 on a serialised SQLite build, so the C layer
        # will not crash — but Python's sqlite3 keeps a per-connection statement
        # cache, and threads running the *same* SQL share one prepared
        # statement. Two threads stepping it at once consume each other's rows,
        # and nothing raises: get_all() just returns the wrong set. Measured on
        # an 800-row table with six concurrent readers, results ranged from 0 to
        # 5199 rows.
        #
        # Reentrant because _notify_change fires inside the lock and a callback
        # may re-enter the store.
        self._write_lock = threading.RLock()
        self.on_change_callbacks = []

    def register_on_change(self, callback):
        self.on_change_callbacks.append(callback)

    def _notify_change(self):
        for cb in self.on_change_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _ensure_connection(self) -> sqlite3.Connection:
        """Lazy-init the connection and create schema if needed.

        Returns the live connection so callers get a non-``Optional`` handle.
        """
        if self._conn is not None:
            return self._conn

        with self._write_lock:
            # Re-check inside the lock: two threads can both find _conn empty,
            # and the loser would otherwise open a second connection and leak it.
            if self._conn is not None:
                return self._conn
            self._open_connection()
        assert self._conn is not None  # _open_connection always sets it
        return self._conn

    def _open_connection(self) -> None:
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        conn = sqlite3.connect(
            self.db_file,
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        self._conn = conn
        conn.row_factory = sqlite3.Row
        # Performance pragmas
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache (Performance boost)
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456") # 256MB mmap

        self._create_table()

    def _create_table(self) -> None:
        """Create the media table, indexes, and encoding_queue table if they don't exist."""
        conn = self._conn
        assert conn is not None  # only called from _open_connection
        cols = ", ".join(f"{name} {typedef}" for name, typedef in _COLUMNS)
        conn.execute(f"CREATE TABLE IF NOT EXISTS media ({cols})")

        # Performance indexes for common filter/sort queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON media(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_codec ON media(codec)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_size_mb ON media(size_mb)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mtime ON media(mtime)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_favorite ON media(favorite)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vaulted ON media(vaulted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_type ON media(media_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_thumb ON media(thumb)")

        # Migration: Add original_path to media table if it doesn't exist
        try:
            conn.execute("ALTER TABLE media ADD COLUMN original_path TEXT DEFAULT ''")
        except Exception:
            pass # Already exists

        # Migration: optimized_at marks files already processed by the optimizer
        try:
            conn.execute("ALTER TABLE media ADD COLUMN optimized_at INTEGER DEFAULT 0")
        except Exception:
            pass  # Already exists

        # Encoding queue for remote optimization
        conn.execute("""
            CREATE TABLE IF NOT EXISTS encoding_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                size_bytes INTEGER DEFAULT 0,
                target_codec TEXT DEFAULT 'hevc',
                created_at INTEGER DEFAULT 0,
                started_at INTEGER DEFAULT 0,
                completed_at INTEGER DEFAULT 0,
                worker_id TEXT DEFAULT '',
                result_message TEXT DEFAULT '',
                saved_bytes INTEGER DEFAULT 0
            )
        """)
        # Add target_codec column to existing installations (migration)
        try:
            conn.execute("ALTER TABLE encoding_queue ADD COLUMN target_codec TEXT DEFAULT 'hevc'")
        except Exception:
            pass  # Column already exists

        # Embedding storage (similarity part 1) — written by scripts/media_indexer.py,
        # read by routes/similar.py. Vectors are L2-normalized float32 blobs.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embedding_meta (
                file_path   TEXT PRIMARY KEY,
                model       TEXT NOT NULL,
                dim         INTEGER NOT NULL,
                mtime       REAL NOT NULL,
                indexed_at  TEXT NOT NULL,
                mean_vector BLOB NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS frame_embeddings (
                file_path   TEXT NOT NULL,
                frame_index INTEGER NOT NULL,
                ts_sec      REAL NOT NULL,
                vector      BLOB NOT NULL,
                PRIMARY KEY (file_path, frame_index)
            )
        """)

        # Auto-tagging apply-once bookkeeping (spec: apply-once semantics —
        # a manually removed tag is never re-applied by its rule)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auto_tag_applied (
                username  TEXT NOT NULL,
                rule_id   TEXT NOT NULL,
                file_path TEXT NOT NULL,
                PRIMARY KEY (username, rule_id, file_path)
            )
        """)

    # ------------------------------------------------------------------
    # Embedding storage (similarity)
    # ------------------------------------------------------------------

    def store_embedding(self, file_path: str, model: str, dim: int, mtime: float,
                        mean_vector: bytes, frames: list[tuple[int, float, bytes]]) -> None:
        """Write one file's embeddings atomically, replacing any previous rows."""
        conn = self._ensure_connection()
        safe_path = self._get_safe_path(file_path)
        with self._write_lock:
            conn.execute("BEGIN")
            try:
                conn.execute("DELETE FROM frame_embeddings WHERE file_path = ?", (safe_path,))
                conn.execute(
                    "INSERT OR REPLACE INTO embedding_meta "
                    "(file_path, model, dim, mtime, indexed_at, mean_vector) "
                    "VALUES (?, ?, ?, ?, datetime('now'), ?)",
                    (safe_path, model, dim, mtime, mean_vector),
                )
                conn.executemany(
                    "INSERT INTO frame_embeddings (file_path, frame_index, ts_sec, vector) "
                    "VALUES (?, ?, ?, ?)",
                    [(safe_path, idx, ts, vec) for idx, ts, vec in frames],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        self._notify_change()

    def get_embedding_state(self) -> dict[str, tuple[float, str]]:
        """path → (mtime, model) for incremental skip decisions."""
        conn = self._ensure_connection()
        with self._write_lock:
            cursor = conn.execute("SELECT file_path, mtime, model FROM embedding_meta")
            return {self._decode_safe_path(row["file_path"]): (row["mtime"], row["model"])
                    for row in cursor}

    def get_mean_vectors(self) -> list[tuple[str, str, bytes]]:
        """(path, model, mean_vector blob) for every indexed file."""
        conn = self._ensure_connection()
        with self._write_lock:
            cursor = conn.execute("SELECT file_path, model, mean_vector FROM embedding_meta")
            return [(self._decode_safe_path(row["file_path"]), row["model"], row["mean_vector"])
                    for row in cursor]

    def delete_embedding(self, file_path: str) -> None:
        conn = self._ensure_connection()
        safe_path = self._get_safe_path(file_path)
        with self._write_lock:
            conn.execute("DELETE FROM embedding_meta WHERE file_path = ?", (safe_path,))
            conn.execute("DELETE FROM frame_embeddings WHERE file_path = ?", (safe_path,))

    def prune_embeddings(self, existing_paths: set[str]) -> int:
        """Drop embeddings for files no longer in the library. Returns count removed."""
        removed = 0
        for path in list(self.get_embedding_state()):
            if path not in existing_paths:
                self.delete_embedding(path)
                removed += 1
        return removed
    # ------------------------------------------------------------------
    # Auto-Tagging bookkeeping
    # ------------------------------------------------------------------

    def get_auto_tag_applied(self, username: str, rule_id: str) -> set[str]:
        """file_paths a rule has already been applied to for this user."""
        conn = self._ensure_connection()
        with self._write_lock:
            cursor = conn.execute(
                "SELECT file_path FROM auto_tag_applied WHERE username = ? AND rule_id = ?",
                (username, rule_id),
            )
            return {self._decode_safe_path(row["file_path"]) for row in cursor}

    def mark_auto_tag_applied(self, username: str, rule_id: str, file_paths: list[str]) -> None:
        """Record applied (user, rule, path) triples. Idempotent."""
        if not file_paths:
            return
        conn = self._ensure_connection()
        with self._write_lock:
            conn.executemany(
                "INSERT OR IGNORE INTO auto_tag_applied (username, rule_id, file_path) VALUES (?, ?, ?)",
                [(username, rule_id, self._get_safe_path(p)) for p in file_paths],
            )

    def clear_auto_tag_applied(self, username: str, rule_id: str) -> None:
        """Drop a rule's bookkeeping (rule deleted)."""
        conn = self._ensure_connection()
        with self._write_lock:
            conn.execute(
                "DELETE FROM auto_tag_applied WHERE username = ? AND rule_id = ?",
                (username, rule_id),
            )

    # ------------------------------------------------------------------
    # Encoding Queue methods
    # ------------------------------------------------------------------

    def queue_encode(self, file_path: str, size_bytes: int = 0, target_codec: str = 'hevc') -> Optional[int]:
        """Add a file to the encoding queue. Returns job ID or None if already pending."""
        conn = self._ensure_connection()

        safe_path = self._get_safe_path(file_path)
        # Check-then-insert must hold the lock, or two callers both find no
        # pending job and both insert one for the same file.
        with self._write_lock:
            cursor = conn.execute(
                "SELECT id FROM encoding_queue WHERE file_path = ? AND status IN ('pending', 'downloading', 'encoding', 'uploading')",
                (safe_path,)
            )
            if cursor.fetchone():
                return None  # Already queued

            conn.execute(
                "INSERT INTO encoding_queue (file_path, status, size_bytes, target_codec, created_at) VALUES (?, 'pending', ?, ?, ?)",
                (safe_path, size_bytes, target_codec, int(time.time()))
            )
            cursor = conn.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()[0]

    def get_next_pending(self, worker_id: str = "") -> Optional[dict]:
        """Atomically claim the oldest pending job. Returns job dict or None.

        The claim is a compare-and-swap: the UPDATE only fires while the row is
        still 'pending', and a row count of 0 means another worker won the race,
        so this caller must look for a different job rather than return one it
        does not own. Without that check two workers encode the same file and
        race on the same output path.
        """
        conn = self._ensure_connection()

        with self._write_lock:
            while True:
                cursor = conn.execute(
                    "SELECT id, file_path, size_bytes, target_codec FROM encoding_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    return None

                job_id = row["id"]
                cursor = conn.execute(
                    "UPDATE encoding_queue SET status = 'downloading', started_at = ?, worker_id = ? WHERE id = ? AND status = 'pending'",
                    (int(time.time()), worker_id, job_id)
                )
                if cursor.rowcount == 0:
                    continue  # Someone else claimed it first — try the next one.

                return {
                    "id": job_id,
                    "file_path": self._decode_safe_path(row["file_path"]),
                    "size_bytes": row["size_bytes"],
                    "target_codec": row["target_codec"] or "hevc",
                }

    def update_job_status(self, job_id: int, status: str, **kwargs: Any) -> None:
        """Update a job's status and optional fields (result_message, saved_bytes, completed_at)."""
        conn = self._ensure_connection()

        sets = ["status = ?"]
        vals: List[Any] = [status]

        if status in ("done", "failed"):
            sets.append("completed_at = ?")
            vals.append(int(time.time()))

        for key in ("result_message", "saved_bytes", "worker_id"):
            if key in kwargs:
                sets.append(f"{key} = ?")
                vals.append(kwargs[key])

        vals.append(job_id)
        with self._write_lock:
            conn.execute(
                f"UPDATE encoding_queue SET {', '.join(sets)} WHERE id = ?",
                tuple(vals)
            )

    def get_queue_status(self, limit: int = 20) -> List[dict]:
        """Return active + recent jobs for the UI."""
        conn = self._ensure_connection()
        with self._write_lock:
            cursor = conn.execute(
                """SELECT id, file_path, status, size_bytes, created_at, started_at,
                          completed_at, worker_id, result_message, saved_bytes
                   FROM encoding_queue
                   ORDER BY
                       CASE WHEN status IN ('pending','downloading','encoding','uploading') THEN 0 ELSE 1 END,
                       created_at DESC
                   LIMIT ?""",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_active_queue_paths(self) -> set[str]:
        """file_paths of jobs currently pending or being processed."""
        conn = self._ensure_connection()
        with self._write_lock:
            cursor = conn.execute(
                "SELECT file_path FROM encoding_queue "
                "WHERE status IN ('pending', 'downloading', 'encoding', 'uploading')"
            )
            return {self._decode_safe_path(row["file_path"]) for row in cursor}

    def cancel_job(self, job_id: int) -> bool:
        """Cancel a pending or active job. Returns True if cancelled."""
        self._ensure_connection()
        with self._write_lock:
            return self._cancel_job_locked(job_id)

    def _cancel_job_locked(self, job_id: int) -> bool:
        conn = self._ensure_connection()
        # Delete if still pending
        cursor = conn.execute(
            "DELETE FROM encoding_queue WHERE id = ? AND status = 'pending'",
            (job_id,)
        )
        if cursor.rowcount > 0:
            return True
        # Mark active jobs as cancelled so the worker can detect it
        cursor = conn.execute(
            "UPDATE encoding_queue SET status = 'cancelled', result_message = 'Cancelled by user' "
            "WHERE id = ? AND status IN ('downloading', 'encoding', 'uploading')",
            (job_id,)
        )
        return cursor.rowcount > 0

    def is_job_cancelled(self, job_id: int) -> bool:
        """Check if a job has been cancelled (worker polls this)."""
        conn = self._ensure_connection()
        with self._write_lock:
            row = conn.execute(
                "SELECT status FROM encoding_queue WHERE id = ?", (job_id,)
            ).fetchone()
        return row is not None and row[0] == 'cancelled'

    # ------------------------------------------------------------------
    # Public interface (unchanged from the original JSON store)
    # ------------------------------------------------------------------

    def load(self) -> None:
        """
        Initialize connection and auto-migrate from JSON if needed.
        Kept for backward compatibility — SQLite is always 'loaded'.
        """
        self._ensure_connection()

        # One-time migration from JSON → SQLite
        if not self._migrated:
            self._migrated = True
            self._migrate_from_json()

    def save(self) -> None:
        """No-op — SQLite auto-commits on every write."""
        pass

    def get_all(self) -> List[VideoEntry]:
        """Return all entries as VideoEntry models."""
        conn = self._ensure_connection()
        # Shared connection: readers running the same SQL share one cached
        # prepared statement, and stepping it from two threads makes them
        # consume each other's rows -- silently, with no exception.
        with self._write_lock:
            cursor = conn.execute("SELECT * FROM media")
            results = []
            for row in cursor:
                try:
                    results.append(self._row_to_entry(row))
                except Exception as e:
                    print(f"⚠️ Skipping corrupted DB row: {e}")
            return results

    def get_all_dicts(self) -> List[dict]:
        """Return all entries as plain dictionaries with UI aliases.

        This is much more memory efficient than get_all() for large libraries,
        as it avoids Pydantic model overhead.
        """
        conn = self._ensure_connection()
        # Shared connection: readers running the same SQL share one cached
        # prepared statement, and stepping it from two threads makes them
        # consume each other's rows -- silently, with no exception.
        with self._write_lock:
            cursor = conn.execute("SELECT * FROM media")
            results = []
            for row in cursor:
                try:
                    results.append(self._row_to_api_dict(row))
                except Exception as e:
                    print(f"⚠️ Skipping corrupted DB row (dict): {e}")
            return results

    def get(self, path: str) -> Optional[VideoEntry]:
        """Lookup a single entry by file_path. O(1) indexed."""
        conn = self._ensure_connection()
        # Shared connection: readers running the same SQL share one cached
        # prepared statement, and stepping it from two threads makes them
        # consume each other's rows -- silently, with no exception.
        with self._write_lock:
            # Handle surrogate-escaped paths by using hybrid str/bytes for SQLite
            safe_path = self._get_safe_path(path)
            cursor = conn.execute(
                "SELECT * FROM media WHERE file_path = ?", (safe_path,)
            )
            row = cursor.fetchone()
            if row:
                try:
                    return self._row_to_entry(row)
                except Exception as e:
                    logger.error(f"⚠️ Failed to decode DB row: {e}")
                    return None
            return None

    def get_by_thumb(self, thumb_name: str) -> Optional[VideoEntry]:
        """Fetch a single entry by thumb name."""
        conn = self._ensure_connection()
        # Shared connection: readers running the same SQL share one cached
        # prepared statement, and stepping it from two threads makes them
        # consume each other's rows -- silently, with no exception.
        with self._write_lock:
            cursor = conn.execute(
                "SELECT * FROM media WHERE thumb = ?", (thumb_name,)
            )
            row = cursor.fetchone()
            if row:
                try:
                    return self._row_to_entry(row)
                except Exception as e:
                    logger.error(f"⚠️ Failed to decode DB row for thumb: {e}")
                    return None
            return None

    def upsert(self, entry) -> None:
        """Insert or replace an entry. Accepts VideoEntry or MediaAsset."""
        from ..models.media_asset import MediaAsset

        with self._write_lock:
            conn = self._ensure_connection()
            if isinstance(entry, MediaAsset):
                entry = self._asset_to_video_entry(entry)

            placeholders = ", ".join("?" for _ in _COLUMNS)
            col_names = ", ".join(name for name, _ in _COLUMNS)
            values = self._entry_to_tuple(entry)

            conn.execute(
                f"INSERT OR REPLACE INTO media ({col_names}) VALUES ({placeholders})",
                values,
            )
            self._notify_change()

    def bulk_upsert(self, entries) -> None:
        """Insert or replace multiple entries in a single transaction."""
        from ..models.media_asset import MediaAsset
        if not entries:
            return

        with self._write_lock:
            conn = self._ensure_connection()

            placeholders = ", ".join("?" for _ in _COLUMNS)
            col_names = ", ".join(name for name, _ in _COLUMNS)

            data = []
            for entry in entries:
                if isinstance(entry, MediaAsset):
                    entry = self._asset_to_video_entry(entry)
                data.append(self._entry_to_tuple(entry))

            conn.execute("BEGIN")
            try:
                conn.executemany(
                    f"INSERT OR REPLACE INTO media ({col_names}) VALUES ({placeholders})",
                    data,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            self._notify_change()

    def remove(self, path: str) -> None:
        """Delete an entry by file_path."""
        with self._write_lock:
            conn = self._ensure_connection()
            safe_path = self._get_safe_path(path)
            conn.execute("DELETE FROM media WHERE file_path = ?", (safe_path,))
            self._notify_change()

    def delete_all_photos(self) -> int:
        """Delete all entries where media_type = 'image'. Returns the number of deleted rows."""
        with self._write_lock:
            conn = self._ensure_connection()
            cursor = conn.execute("DELETE FROM media WHERE media_type = 'image'")
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info("Deleted %d photo entries from DB (include_photos disabled)", deleted)
            return deleted

    def get_page(self, page: int = 0, page_size: int = 100) -> List[VideoEntry]:
        """Return a paginated slice of entries. page=0 is the first page.

        This avoids loading the entire library into memory for large collections.
        Use together with count() to build pagination UI.
        """
        conn = self._ensure_connection()
        # Shared connection: readers running the same SQL share one cached
        # prepared statement, and stepping it from two threads makes them
        # consume each other's rows -- silently, with no exception.
        with self._write_lock:
            offset = page * page_size
            cursor = conn.execute(
                "SELECT * FROM media ORDER BY mtime DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            )
            results = []
            for row in cursor:
                try:
                    results.append(self._row_to_entry(row))
                except Exception as e:
                    logger.warning("Skipping corrupted DB row during get_page: %s", e)
            return results

    def count(self) -> int:
        """Return the total number of entries in the store."""
        conn = self._ensure_connection()
        # Shared connection: readers running the same SQL share one cached
        # prepared statement, and stepping it from two threads makes them
        # consume each other's rows -- silently, with no exception.
        with self._write_lock:
            cursor = conn.execute("SELECT COUNT(*) FROM media")
            return cursor.fetchone()[0]

    def cleanup_old_jobs(self, older_than_days: int = 30) -> int:
        """Delete completed/failed/cancelled jobs older than N days. Returns number of deleted rows."""
        conn = self._ensure_connection()
        cutoff = int(time.time()) - (older_than_days * 86400)
        with self._write_lock:
            cursor = conn.execute(
                "DELETE FROM encoding_queue "
                "WHERE status IN ('done', 'failed', 'cancelled') "
                "  AND completed_at > 0 AND completed_at < ?",
                (cutoff,),
            )
            deleted = cursor.rowcount
        if deleted > 0:
            logger.info("Cleaned up %d old encoding_queue jobs (>%dd)", deleted, older_than_days)
        return deleted

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_entry(self, row: sqlite3.Row) -> VideoEntry:
        """Convert a database row to a VideoEntry model."""
        return VideoEntry(**self._row_to_api_dict(row))

    def _row_to_api_dict(self, row: sqlite3.Row) -> dict:
        """Convert a database row to a dictionary with UI-friendly aliases."""
        # Handle surrogate-escaped paths
        file_path = self._decode_safe_path(row["file_path"])

        tags = row["tags"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        return {
            "FilePath": file_path,
            "Size_MB": row["size_mb"] or 0.0,
            "Bitrate_Mbps": row["bitrate_mbps"] or 0.0,
            "Status": row["status"] or "OK",
            "media_type": row["media_type"] or "video",
            "codec": row["codec"] or "unknown",
            "Duration_Sec": row["duration_sec"] or 0.0,
            "Width": row["width"] or 0,
            "Height": row["height"] or 0,
            "AudioCodec": row["audio_codec"] or "unknown",
            "AudioChannels": row["audio_channels"] or 0,
            "Container": row["container_format"] or "unknown",
            "Profile": row["profile"] or "",
            "Level": row["level"] or 0.0,
            "PixelFormat": row["pixel_format"] or "",
            "FrameRate": row["frame_rate"] or 0.0,
            "favorite": bool(row["favorite"]),
            "hidden": bool(row["vaulted"]),
            "tags": tags if isinstance(tags, list) else [],
            "thumb": row["thumb"] or "",
            "imported_at": row["imported_at"] or 0,
            "mtime": row["mtime"] or 0,
            "OriginalPath": row["original_path"] or "",
            "optimized_at": row["optimized_at"] or 0,
        }

    def _entry_to_tuple(self, entry: VideoEntry) -> tuple:
        """Convert a VideoEntry to a tuple matching _COLUMNS order."""
        # Handle surrogate-escaped paths by using hybrid str/bytes for SQLite
        file_path = self._get_safe_path(entry.file_path)

        tags = json.dumps(entry.tags) if entry.tags else "[]"
        return (
            file_path,
            entry.size_mb,
            entry.bitrate_mbps,
            entry.status,
            entry.media_type,
            entry.codec or "unknown",
            entry.duration_sec or 0.0,
            entry.width or 0,
            entry.height or 0,
            entry.audio_codec or "unknown",
            entry.audio_channels or 0,
            entry.container_format or "unknown",
            entry.profile or "",
            entry.level or 0.0,
            entry.pixel_format or "",
            entry.frame_rate or 0.0,
            int(entry.favorite),
            int(entry.vaulted),
            tags,
            entry.thumb or "",
            entry.imported_at or 0,
            entry.mtime or 0,
            entry.original_path or "",
            entry.optimized_at or 0,
        )

    def _asset_to_video_entry(self, entry) -> VideoEntry:
        """Convert a MediaAsset to a VideoEntry for storage."""
        return VideoEntry(
            file_path=entry.file_path,
            size_mb=entry.size_mb,
            status=entry.status,
            media_type=entry.media_type.value if hasattr(entry.media_type, 'value') else str(entry.media_type),
            bitrate_mbps=entry.video_metadata.bitrate_mbps if entry.video_metadata else 0.0,
            duration_sec=entry.video_metadata.duration_sec if entry.video_metadata else 0.0,
            codec=entry.video_metadata.codec if entry.video_metadata else "unknown",
            width=entry.Width,
            height=entry.Height,
            audio_codec=entry.video_metadata.audio_codec if entry.video_metadata else "unknown",
            audio_channels=entry.video_metadata.audio_channels if entry.video_metadata else 0,
            container_format=entry.video_metadata.container if entry.video_metadata else "unknown",
            profile=entry.video_metadata.profile if entry.video_metadata else "",
            level=entry.video_metadata.level if entry.video_metadata else 0.0,
            pixel_format=entry.video_metadata.pixel_format if entry.video_metadata else "",
            frame_rate=entry.video_metadata.frame_rate if entry.video_metadata else 0.0,
            favorite=entry.favorite,
            vaulted=entry.vaulted,
            tags=entry.tags,
            thumb=entry.thumb,
            imported_at=entry.imported_at,
            mtime=entry.mtime,
            original_path=entry.original_path,
            optimized_at=entry.optimized_at,
        )

    def _migrate_from_json(self) -> None:
        """One-time migration: import all entries from video_cache.json into SQLite."""
        json_path = config.cache_file  # video_cache.json
        if not os.path.exists(json_path):
            return

        conn = self._ensure_connection()
        # Check if we already have data (migration already done)
        cursor = conn.execute("SELECT COUNT(*) FROM media")
        count = cursor.fetchone()[0]
        if count > 0:
            return  # Already migrated

        print("📦 Migrating JSON database → SQLite...")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, dict):
                print("⚠️ JSON data is not a dict, skipping migration")
                return

            migrated = 0
            # Use a transaction for bulk insert performance
            conn.execute("BEGIN")
            try:
                for path, entry_dict in raw_data.items():
                    try:
                        if "FilePath" not in entry_dict:
                            entry_dict["FilePath"] = path
                        ve = VideoEntry(**entry_dict)
                        placeholders = ", ".join("?" for _ in _COLUMNS)
                        col_names = ", ".join(name for name, _ in _COLUMNS)
                        conn.execute(
                            f"INSERT OR REPLACE INTO media ({col_names}) VALUES ({placeholders})",
                            self._entry_to_tuple(ve),
                        )
                        migrated += 1
                    except Exception as e:
                        print(f"⚠️ Skipping entry {path}: {e}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

            print(f"✅ Migrated {migrated} entries from JSON → SQLite")

            # Rename JSON file to .bak (non-destructive)
            bak_path = json_path + ".bak"
            try:
                os.rename(json_path, bak_path)
                print(f"📁 JSON file backed up to {os.path.basename(bak_path)}")
            except Exception as e:
                print(f"⚠️ Could not rename JSON file: {e}")

        except Exception as e:
            print(f"❌ Migration failed: {e}")


    def _get_safe_path(self, path: str):
        """
        Return a representation of the path safe for SQLite TEXT columns.
        Uses str for valid UTF-8 (best for affinity/matching) and bytes for surrogates.
        """
        if not isinstance(path, str):
            return path
        try:
            path.encode('utf-8', 'strict')
            return path
        except UnicodeEncodeError:
            return path.encode('utf-8', 'surrogateescape')

    def _decode_safe_path(self, db_path) -> str:
        """Decode a path from the DB (could be str or bytes)."""
        if isinstance(db_path, bytes):
            return db_path.decode('utf-8', 'surrogateescape')
        return str(db_path)


# Singleton instance
db = SQLiteStore()
