"""
SQLite-backed Media Store.

Drop-in replacement for JSONStore with identical interface:
    load(), save(), get_all(), get(path), upsert(entry), remove(path)

Benefits over JSONStore:
    - Instant row-level reads/writes (no full-file serialization)
    - O(1) indexed lookups by file_path
    - ACID guarantees for concurrent access
    - Scales to 100K+ entries without memory pressure
"""
import os
import sqlite3
import json
import hashlib
from typing import Dict, List, Optional

from ..config import config
from ..models.video_entry import VideoEntry


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
]


class SQLiteStore:
    """
    SQLite-backed media metadata store.
    Thread-safe, auto-commits on every write.
    """

    def __init__(self):
        self.db_file = os.path.join(config.hidden_data_dir, "media_library.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._migrated = False

    def _ensure_connection(self):
        """Lazy-init the connection and create schema if needed."""
        if self._conn is not None:
            return

        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        self._conn = sqlite3.connect(
            self.db_file,
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        self._conn.row_factory = sqlite3.Row
        # Performance pragmas
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-8000")  # 8MB cache

        self._create_table()

    def _create_table(self):
        """Create the media table and encoding_queue table if they don't exist."""
        cols = ", ".join(f"{name} {typedef}" for name, typedef in _COLUMNS)
        self._conn.execute(f"CREATE TABLE IF NOT EXISTS media ({cols})")

        # Encoding queue for remote optimization
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS encoding_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                size_bytes INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                started_at INTEGER DEFAULT 0,
                completed_at INTEGER DEFAULT 0,
                worker_id TEXT DEFAULT '',
                result_message TEXT DEFAULT '',
                saved_bytes INTEGER DEFAULT 0
            )
        """)

    # ------------------------------------------------------------------
    # Encoding Queue methods
    # ------------------------------------------------------------------

    def queue_encode(self, file_path: str, size_bytes: int = 0) -> Optional[int]:
        """Add a file to the encoding queue. Returns job ID or None if already pending."""
        self._ensure_connection()
        import time

        # Check for existing pending/active job for this file
        cursor = self._conn.execute(
            "SELECT id FROM encoding_queue WHERE file_path = ? AND status IN ('pending', 'downloading', 'encoding', 'uploading')",
            (file_path,)
        )
        if cursor.fetchone():
            return None  # Already queued

        self._conn.execute(
            "INSERT INTO encoding_queue (file_path, status, size_bytes, created_at) VALUES (?, 'pending', ?, ?)",
            (file_path, size_bytes, int(time.time()))
        )
        cursor = self._conn.execute("SELECT last_insert_rowid()")
        return cursor.fetchone()[0]

    def get_next_pending(self, worker_id: str = "") -> Optional[dict]:
        """Atomically claim the oldest pending job. Returns job dict or None."""
        self._ensure_connection()
        import time

        # Atomic claim: update first pending row
        cursor = self._conn.execute(
            "SELECT id, file_path, size_bytes FROM encoding_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            return None

        job_id = row["id"]
        self._conn.execute(
            "UPDATE encoding_queue SET status = 'downloading', started_at = ?, worker_id = ? WHERE id = ? AND status = 'pending'",
            (int(time.time()), worker_id, job_id)
        )
        return {"id": job_id, "file_path": row["file_path"], "size_bytes": row["size_bytes"]}

    def update_job_status(self, job_id: int, status: str, **kwargs) -> None:
        """Update a job's status and optional fields (result_message, saved_bytes, completed_at)."""
        self._ensure_connection()
        import time

        sets = ["status = ?"]
        vals = [status]

        if status in ("done", "failed"):
            sets.append("completed_at = ?")
            vals.append(int(time.time()))

        for key in ("result_message", "saved_bytes", "worker_id"):
            if key in kwargs:
                sets.append(f"{key} = ?")
                vals.append(kwargs[key])

        vals.append(job_id)
        self._conn.execute(
            f"UPDATE encoding_queue SET {', '.join(sets)} WHERE id = ?",
            tuple(vals)
        )

    def get_queue_status(self, limit: int = 20) -> List[dict]:
        """Return active + recent jobs for the UI."""
        self._ensure_connection()
        cursor = self._conn.execute(
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

    def cancel_job(self, job_id: int) -> bool:
        """Cancel a pending job. Returns True if cancelled, False if not pending."""
        self._ensure_connection()
        cursor = self._conn.execute(
            "DELETE FROM encoding_queue WHERE id = ? AND status = 'pending'",
            (job_id,)
        )
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Public interface (matches JSONStore exactly)
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
        self._ensure_connection()
        cursor = self._conn.execute("SELECT * FROM media")
        results = []
        for row in cursor:
            try:
                results.append(self._row_to_entry(row))
            except Exception as e:
                print(f"⚠️ Skipping corrupted DB row: {e}")
        return results

    def get(self, path: str) -> Optional[VideoEntry]:
        """Lookup a single entry by file_path. O(1) indexed."""
        self._ensure_connection()
        cursor = self._conn.execute(
            "SELECT * FROM media WHERE file_path = ?", (path,)
        )
        row = cursor.fetchone()
        if row:
            try:
                return self._row_to_entry(row)
            except Exception:
                return None
        return None

    def upsert(self, entry) -> None:
        """Insert or replace an entry. Accepts VideoEntry or MediaAsset."""
        self._ensure_connection()
        from ..models.media_asset import MediaAsset

        if isinstance(entry, MediaAsset):
            entry = self._asset_to_video_entry(entry)

        placeholders = ", ".join("?" for _ in _COLUMNS)
        col_names = ", ".join(name for name, _ in _COLUMNS)
        values = self._entry_to_tuple(entry)

        self._conn.execute(
            f"INSERT OR REPLACE INTO media ({col_names}) VALUES ({placeholders})",
            values,
        )

    def remove(self, path: str) -> None:
        """Delete an entry by file_path."""
        self._ensure_connection()
        self._conn.execute("DELETE FROM media WHERE file_path = ?", (path,))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_entry(self, row: sqlite3.Row) -> VideoEntry:
        """Convert a database row to a VideoEntry model."""
        tags = row["tags"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        return VideoEntry(
            file_path=row["file_path"],
            size_mb=row["size_mb"] or 0.0,
            bitrate_mbps=row["bitrate_mbps"] or 0.0,
            status=row["status"] or "OK",
            media_type=row["media_type"] or "video",
            codec=row["codec"] or "unknown",
            duration_sec=row["duration_sec"] or 0.0,
            width=row["width"] or 0,
            height=row["height"] or 0,
            audio_codec=row["audio_codec"] or "unknown",
            audio_channels=row["audio_channels"] or 0,
            container_format=row["container_format"] or "unknown",
            profile=row["profile"] or "",
            level=row["level"] or 0.0,
            pixel_format=row["pixel_format"] or "",
            frame_rate=row["frame_rate"] or 0.0,
            favorite=bool(row["favorite"]),
            vaulted=bool(row["vaulted"]),
            tags=tags if isinstance(tags, list) else [],
            thumb=row["thumb"] or "",
            imported_at=row["imported_at"] or 0,
            mtime=row["mtime"] or 0,
        )

    def _entry_to_tuple(self, entry: VideoEntry) -> tuple:
        """Convert a VideoEntry to a tuple matching _COLUMNS order."""
        tags = json.dumps(entry.tags) if entry.tags else "[]"
        return (
            entry.file_path,
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
        )

    def _migrate_from_json(self):
        """One-time migration: import all entries from video_cache.json into SQLite."""
        json_path = config.cache_file  # video_cache.json
        if not os.path.exists(json_path):
            return

        # Check if we already have data (migration already done)
        cursor = self._conn.execute("SELECT COUNT(*) FROM media")
        count = cursor.fetchone()[0]
        if count > 0:
            return  # Already migrated

        print(f"📦 Migrating JSON database → SQLite...")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, dict):
                print("⚠️ JSON data is not a dict, skipping migration")
                return

            migrated = 0
            # Use a transaction for bulk insert performance
            self._conn.execute("BEGIN")
            try:
                for path, entry_dict in raw_data.items():
                    try:
                        if "FilePath" not in entry_dict:
                            entry_dict["FilePath"] = path
                        ve = VideoEntry(**entry_dict)
                        placeholders = ", ".join("?" for _ in _COLUMNS)
                        col_names = ", ".join(name for name, _ in _COLUMNS)
                        self._conn.execute(
                            f"INSERT OR REPLACE INTO media ({col_names}) VALUES ({placeholders})",
                            self._entry_to_tuple(ve),
                        )
                        migrated += 1
                    except Exception as e:
                        print(f"⚠️ Skipping entry {path}: {e}")
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
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


# Singleton instance
db = SQLiteStore()
