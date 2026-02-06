import json
import os
from typing import Dict, List, Optional
from ..config import config
from ..models.video_entry import VideoEntry

class JSONStore:
    """
    Handles persistence of video metadata to a JSON file.
    Acts as a repository for VideoEntry objects.
    """
    def __init__(self):
        self.cache_file = config.cache_file
        self._data: Dict[str, VideoEntry] = {}
        self.load()

    def load(self) -> None:
        """Loads data from disk and converts to VideoEntry models."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    if not isinstance(raw_data, dict):
                        raw_data = {}
                    
                    self._data = {}
                    for path, entry_dict in raw_data.items():
                        try:
                            # Ensure the key is preserved as file_path if missing in body
                            if "FilePath" not in entry_dict:
                                entry_dict["FilePath"] = path
                                
                            self._data[path] = VideoEntry(**entry_dict)
                        except Exception as e:
                            print(f"⚠️ Skipping corrupted cache entry for {path}: {e}")
                            
            except Exception as e:
                print(f"❌ Error loading cache: {e}")
                self._data = {}
        else:
            self._data = {}

    def get_data_snapshot(self) -> Dict[str, VideoEntry]:
        """Returns a thread-safe snapshot of the current data."""
        return self._data.copy()

    def save(self, data_snapshot: Optional[Dict[str, VideoEntry]] = None) -> None:
        """
        Persists current state to disk using atomic write pattern.
        
        Prevents data corruption from:
        - Concurrent writes (race conditions)
        - Disk full errors
        - Process crashes during write
        """
        import tempfile
        import shutil
        
        try:
            target_data = data_snapshot if data_snapshot is not None else self._data

            # Convert models back to JSON-compatible dicts (using aliases like Size_MB)
            dump_data = {
                path: entry.model_dump(by_alias=True) 
                for path, entry in target_data.items()
            }
            
            # Atomic write pattern: write to temp file, then rename
            cache_dir = os.path.dirname(self.cache_file)
            
            # Create temp file in same directory (ensures same filesystem for atomic rename)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=cache_dir,
                prefix=".cache_tmp_",
                suffix=".json"
            )
            
            try:
                # Write to temp file
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(dump_data, f, indent=4, ensure_ascii=False)
                
                # Atomic rename (overwrites old file)
                # This is atomic on POSIX systems
                shutil.move(temp_path, self.cache_file)
                
                print(f"✅ Database saved ({len(target_data)} entries)")
                
            except Exception as e:
                # Cleanup temp file on error
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                raise e
                
        except Exception as e:
            print(f"❌ Error saving database: {e}")

    def get_all(self) -> List[VideoEntry]:
        return list(self._data.values())

    def get(self, path: str) -> Optional[VideoEntry]:
        return self._data.get(path)

    def upsert(self, entry) -> None:
        """Insert or Update an entry. Accepts VideoEntry or MediaAsset."""
        from ..models.media_asset import MediaAsset
        
        # If it's a MediaAsset, convert to VideoEntry for storage
        if isinstance(entry, MediaAsset):
            video_entry = VideoEntry(
                file_path=entry.file_path,
                size_mb=entry.size_mb,
                status=entry.status,
                media_type=entry.media_type.value if hasattr(entry.media_type, 'value') else str(entry.media_type),
                # Copy video metadata if present
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
                # User state
                favorite=entry.favorite,
                vaulted=entry.vaulted,
                tags=entry.tags,
                thumb=entry.thumb,
                # Chronology
                imported_at=entry.imported_at,
                mtime=entry.mtime
            )
            entry = video_entry
            
        self._data[entry.file_path] = entry

    def remove(self, path: str) -> None:
        if path in self._data:
            del self._data[path]

# Singleton instance
db = JSONStore()
