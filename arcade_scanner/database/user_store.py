import sqlite3
import json
import os
import hashlib
import binascii
import shutil
from typing import Optional, List, Dict
from arcade_scanner.config import config
from arcade_scanner.models.user import User, UserVideoData

class UserStore:
    """
    Handles persistence of users to a SQLite database.
    """
    def __init__(self):
        self.db_path = os.path.join(config.hidden_data_dir, "users.db")
        self.json_path = os.path.join(config.hidden_data_dir, "users.json")
        
        self._init_db()
        self._migrate_from_json_file()
        
        # Ensure default admin exists if DB is empty
        if not self.get_user("admin"):
            self.create_default_admin()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the users table."""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL,
                        is_admin INTEGER DEFAULT 0,
                        created_at INTEGER,
                        user_data TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"❌ Error initializing User DB: {e}")

    def _migrate_from_json_file(self):
        """Migrates existing users.json to SQLite if present."""
        if not os.path.exists(self.json_path):
            return

        # Only migrate if we haven't already (or simple check: if DB likely empty or we want to import?)
        # Better safe: Check if DB has users. If empty, import.
        if len(self.get_all_users()) > 0:
            return

        print(f"📦 Found legacy users.json, migrating to SQLite...")
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            count = 0
            for username, data in raw_data.items():
                try:
                    user = User(**data)
                    self.add_user(user)
                    count += 1
                except Exception as e:
                    print(f"⚠️ Failed to migrate user {username}: {e}")
            
            print(f"✅ Migrated {count} users to SQLite.")
            
            # Rename legacy file
            bak_path = self.json_path + ".bak"
            shutil.move(self.json_path, bak_path)
            print(f"Example: Moved users.json to {bak_path}")
            
        except Exception as e:
            print(f"❌ Error migrating users.json: {e}")

    def save(self) -> None:
        """No-op for SQLite implementation as we save on write."""
        pass

    def get_user(self, username: str) -> Optional[User]:
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                if row:
                    data_json = row["user_data"]
                    user_data = UserVideoData(**json.loads(data_json)) if data_json else UserVideoData()
                    
                    return User(
                        username=row["username"],
                        password_hash=row["password_hash"],
                        salt=row["salt"],
                        created_at=row["created_at"],
                        is_admin=bool(row["is_admin"]),
                        data=user_data
                    )
        except Exception as e:
            print(f"⚠️ Error get_user {username}: {e}")
        return None

    def add_user(self, user: User) -> None:
        """Adds or updates a user."""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO users (username, password_hash, salt, is_admin, created_at, user_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user.username,
                    user.password_hash,
                    user.salt,
                    1 if user.is_admin else 0,
                    user.created_at,
                    user.data.model_dump_json()
                ))
                conn.commit()
        except Exception as e:
            print(f"❌ Error adding user {user.username}: {e}")

    def get_all_users(self) -> List[User]:
        users = []
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT * FROM users")
                for row in cursor.fetchall():
                    data_json = row["user_data"]
                    user_data = UserVideoData(**json.loads(data_json)) if data_json else UserVideoData()
                    
                    users.append(User(
                        username=row["username"],
                        password_hash=row["password_hash"],
                        salt=row["salt"],
                        created_at=row["created_at"],
                        is_admin=bool(row["is_admin"]),
                        data=user_data
                    ))
        except Exception as e:
            print(f"⚠️ Error getting all users: {e}")
        return users

    def create_default_admin(self):
        """Creates a default admin user if none exists."""
        print("👤 Creating default admin user (SQLite)...")
        salt = os.urandom(16)
        pwd_hash = self.hash_password("admin", salt)
        
        admin_user = User(
            username="admin",
            password_hash=binascii.hexlify(pwd_hash).decode('ascii'),
            salt=binascii.hexlify(salt).decode('ascii'),
            is_admin=True
        )
        self.add_user(admin_user)

    def hash_password(self, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)

    def verify_password(self, username: str, password: str) -> bool:
        user = self.get_user(username)
        if not user:
            return False
            
        try:
            salt = binascii.unhexlify(user.salt)
            stored_hash = binascii.unhexlify(user.password_hash)
            new_hash = self.hash_password(password, salt)
            return new_hash == stored_hash
        except Exception:
            return False

    def migrate_from_db(self, video_db) -> None:
        """Migrates legacy data from VideoDB to admin user."""
        admin = self.get_user("admin")
        if not admin:
            return

        modified = False
        count_fav = 0
        count_hidden = 0
        count_tags = 0

        for entry in video_db.get_all():
            if entry.favorite and entry.file_path not in admin.data.favorites:
                admin.data.favorites.append(entry.file_path)
                modified = True
                count_fav += 1
            
            if entry.vaulted and entry.file_path not in admin.data.vaulted:
                admin.data.vaulted.append(entry.file_path)
                modified = True
                count_hidden += 1
            
            if entry.tags and entry.file_path not in admin.data.tags:
                admin.data.tags[entry.file_path] = list(entry.tags)
                modified = True
                count_tags += 1

        if modified:
            print(f"📦 Migrating legacy data to 'admin': {count_fav} favs, {count_hidden} hidden, {count_tags} tagged videos.")
            self.add_user(admin) # Save changes
            
        self.migrate_collections()
        self.migrate_scan_settings()
        self.migrate_tags()
        self.cleanup_legacy_settings()

    def migrate_tags(self):
        """Migrates global available_tags to admin user."""
        admin = self.get_user("admin")
        if not admin: return

        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path): return
            
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            legacy_tags = data.get("available_tags", [])
            added = 0
            current_names = {t.get("name") for t in admin.data.available_tags}
            
            for tag in legacy_tags:
                if isinstance(tag, dict) and tag.get("name") not in current_names:
                    admin.data.available_tags.append(tag)
                    added += 1
            
            if added > 0:
                print(f"📦 Migrated {added} tags to 'admin'.")
                self.add_user(admin)

        except Exception as e:
            print(f"⚠️ Error migrating tags: {e}")

    def migrate_scan_settings(self):
        """Migrates global scan targets/excludes to admin user."""
        admin = self.get_user("admin")
        if not admin: return

        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path): return
            
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            legacy_targets = data.get("scan_targets", [])
            added_targets = 0
            for t in legacy_targets:
                if t not in admin.data.scan_targets:
                    admin.data.scan_targets.append(t)
                    added_targets += 1
            
            legacy_excludes = data.get("exclude_paths", [])
            added_excludes = 0
            for e in legacy_excludes:
                if e not in admin.data.exclude_paths:
                    admin.data.exclude_paths.append(e)
                    added_excludes += 1
            
            if added_targets > 0 or added_excludes > 0:
                print(f"📦 Migrated scan settings to 'admin': {added_targets} targets, {added_excludes} excludes.")
                self.add_user(admin)

        except Exception as e:
            print(f"⚠️ Error migrating scan settings: {e}")

    def migrate_collections(self):
        """Migrates smart collections from global settings to admin user."""
        admin = self.get_user("admin")
        if not admin: return

        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path): return

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            legacy_collections = data.get("smart_collections", [])
            if legacy_collections:
                current_ids = {c.get("id") for c in admin.data.smart_collections}
                added = 0
                for col in legacy_collections:
                    if col.get("id") not in current_ids:
                        admin.data.smart_collections.append(col)
                        added += 1
                
                if added > 0:
                     print(f"📦 Migrated {added} smart collections to 'admin'.")
                     self.add_user(admin)

        except Exception as e:
            print(f"⚠️ Error migrating collections: {e}")

    def cleanup_legacy_settings(self):
        """Removes migrated keys from settings.json."""
        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path): return

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            keys_to_remove = ["smart_collections", "scan_targets", "exclude_paths", "available_tags"]
            modified = False
            
            for k in keys_to_remove:
                if k in data:
                    del data[k]
                    modified = True
            
            if modified:
                print("🧹 Cleaning up legacy keys from settings.json...")
                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            print(f"⚠️ Error cleaning settings: {e}")

# Global instance
user_db = UserStore()
