from arcade_scanner.database.user_store import user_db
import os

admin = user_db.get_user("admin")
if admin:
    print("Admin scan targets:", admin.data.scan_targets)
    user_targets = [os.path.abspath(t) for t in admin.data.scan_targets if t]
    print("Resolved user targets:", user_targets)
    
    from arcade_scanner.database.sqlite_store import SQLiteStore
    db = SQLiteStore()
    all_entries = db.get_all()
    filtered_videos = []
    
    if not user_targets and admin.is_admin:
        filtered_videos = [e.model_dump(by_alias=True) for e in all_entries]
    elif user_targets:
        for entry in all_entries:
            v_path = os.path.abspath(entry.file_path)
            if any(v_path.startswith(t) for t in user_targets):
                filtered_videos.append(entry.model_dump(by_alias=True))
                
    print(f"API returns {len(filtered_videos)} videos.")
else:
    print("Admin user not found in user_db")
