from arcade_scanner.database.sqlite_store import SQLiteStore
from arcade_scanner.models.video_entry import VideoEntry

db = SQLiteStore()
print("DB Loaded.")
videos = db.get_all()
print(f"Total videos: {len(videos)}")
for v in videos:
    d = v.model_dump(by_alias=True)
    if d.get("Size_MB") is None:
        print("Missing Size_MB for:", d.get("FilePath"))
    if not isinstance(d.get("Size_MB"), (int, float)):
        print("Invalid Size_MB type for:", d.get("FilePath"), d.get("Size_MB"))
print("Done checking Pydantic dumps.")
