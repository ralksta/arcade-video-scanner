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

    def save(self) -> None:
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
            # Convert models back to JSON-compatible dicts (using aliases like Size_MB)
            dump_data = {
                path: entry.model_dump(by_alias=True) 
                for path, entry in self._data.items()
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
                
                print(f"✅ Database saved ({len(self._data)} entries)")
                
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

    def upsert(self, entry: VideoEntry) -> None:
        """Insert or Update an entry."""
        self._data[entry.file_path] = entry

    def remove(self, path: str) -> None:
        if path in self._data:
            del self._data[path]

# Singleton instance
db = JSONStore()
