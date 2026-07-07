import pytest
import os
import sqlite3
import hashlib
from unittest.mock import MagicMock, patch

# Mock config for tests
@pytest.fixture(autouse=True)
def patch_config(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.sqlite_store.config", mock_config), \
         patch("arcade_scanner.scanner.manager.config", mock_config):
        yield mock_config

@pytest.fixture
def store(patch_config):
    from arcade_scanner.database.sqlite_store import SQLiteStore
    s = SQLiteStore()
    s._ensure_connection()
    return s

def test_sqlite_store_handles_surrogates(store):
    from arcade_scanner.models.video_entry import VideoEntry
    
    # Path with a surrogate that often causes UnicodeEncodeError
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"
    
    entry = VideoEntry(
        FilePath=surrogate_path,
        Size_MB=100.0,
        Status="OK"
    )
    
    # 1. Test upsert (writes to DB)
    store.upsert(entry)
    assert store.count() == 1, "Entry was not inserted"
    
    # Check what's in the DB directly
    cur = store._conn.execute("SELECT file_path FROM media")
    row = cur.fetchone()
    print(f"DEBUG: stored file_path type: {type(row[0])}")
    print(f"DEBUG: stored file_path: {row[0]}")
    
    # 2. Test get (reads from DB and matches)
    safe_search_path = store._get_safe_path(surrogate_path)
    print(f"DEBUG: querying for type: {type(safe_search_path)}")
    print(f"DEBUG: querying for: {safe_search_path}")
    print(f"DEBUG: are search bytes equal to stored bytes? {safe_search_path == row[0]}")
    
    retrieved = store.get(surrogate_path)
    assert retrieved is not None, f"Failed to retrieve path: {surrogate_path}"
    assert retrieved.file_path == surrogate_path
        
    # 3. Test remove
    try:
        store.remove(surrogate_path)
        assert store.get(surrogate_path) is None
    except UnicodeEncodeError as e:
        pytest.fail(f"remove failed with UnicodeEncodeError: {e}")

def test_manager_hash_generation_handles_surrogates():
    from arcade_scanner.scanner.manager import ScannerManager
    
    manager = ScannerManager()
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"
    
    # Should not raise UnicodeEncodeError
    try:
        file_hash = hashlib.md5(surrogate_path.encode('utf-8', 'surrogateescape')).hexdigest()
        assert file_hash is not None
    except UnicodeEncodeError as e:
        pytest.fail(f"Hash generation failed with UnicodeEncodeError: {e}")

def test_encoding_queue_handles_surrogates(store):
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"
    
    # 1. Queue job
    try:
        job_id = store.queue_encode(surrogate_path, size_bytes=1000)
        assert job_id is not None
    except UnicodeEncodeError as e:
        pytest.fail(f"queue_encode failed with UnicodeEncodeError: {e}")
        
    # 2. Get next pending
    try:
        job = store.get_next_pending(worker_id="test_worker")
        assert job is not None
        assert job["file_path"] == surrogate_path
    except UnicodeEncodeError as e:
        pytest.fail(f"get_next_pending failed with UnicodeEncodeError: {e}")

def test_thumbnail_hashing_handles_surrogates():
    from arcade_scanner.core.video_processor import create_thumbnail
    from arcade_scanner.config import config
    
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"
    
    # Mock config.thumb_dir
    with patch("arcade_scanner.core.video_processor.config") as mock_cfg, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=1):
        mock_cfg.thumb_dir = "/cache/thumbnails"
        
        # Should not raise UnicodeEncodeError
        try:
            thumb_name = create_thumbnail(surrogate_path)
            assert thumb_name.startswith("thumb_")
            assert thumb_name.endswith(".jpg")
        except UnicodeEncodeError as e:
            pytest.fail(f"create_thumbnail failed with UnicodeEncodeError: {e}")

def test_vr_gallery_quoting_handles_surrogates():
    from urllib.parse import quote as url_quote
    
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"
    
    # Should not raise UnicodeEncodeError
    try:
        quoted = url_quote(surrogate_path, errors='surrogateescape')
        assert "%F6" in quoted  # \udcf6 encoded as %F6
    except UnicodeEncodeError as e:
        pytest.fail(f"url_quote failed with UnicodeEncodeError: {e}")
