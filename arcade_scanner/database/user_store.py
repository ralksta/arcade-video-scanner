import binascii
import hashlib
import json
import os
import shutil
import sqlite3
import threading
from typing import List, Optional

from arcade_scanner.config import config
from arcade_scanner.models.user import User, UserVideoData


class UserStore:
    """
    Handles persistence of users to a SQLite database.
    """
    def __init__(self):
        self.db_path = os.path.join(config.hidden_data_dir, "users.db")
        self.json_path = os.path.join(config.hidden_data_dir, "users.json")

        # Sagt dem Aufrufer, ob der letzte get_all_users() die Datenbank
        # wirklich lesen konnte. Ohne das ist "keine Benutzer" von "nicht
        # lesbar" nicht zu unterscheiden — und der Scanner leitet aus dem
        # ersten Fall ab, dass er ersatzweise das ganze Home durchsucht.
        self.last_read_ok = True

        # Lesen-Ändern-Schreiben muss am Stück laufen.
        #
        # Der übliche Ablauf im Server ist `get_user()` → Feld ändern →
        # `add_user()`, und `add_user()` schreibt den **gesamten**
        # Nutzerdatensatz als ein JSON-Feld zurück. Der Server ist ein
        # ThreadingTCPServer: Zwei gleichzeitige Anfragen desselben Kontos —
        # ein Favorit auf dem Fernseher, ein Tag im Browser — lesen beide den
        # alten Stand, und der zweite Schreibvorgang überschreibt die Änderung
        # des ersten.
        #
        # Nachgemessen mit 60 gleichzeitigen Favoriten auf einem Testkonto:
        # **4 kamen an, 56 gingen verloren.**
        #
        # Die Sperre ist wiedereintrittsfähig, weil `update_user()` innerhalb
        # ihrer selbst `get_user()` und `add_user()` aufruft.
        self._write_lock = threading.RLock()

        self._init_db()
        self._migrate_from_json_file()

        # Ensure default admin exists if DB is empty
        if not self.get_user("admin"):
            self.create_default_admin()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the users table."""
        conn = None
        try:
            conn = self._get_conn()
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
        finally:
            if conn:
                conn.close()

    def _migrate_from_json_file(self):
        """Migrates existing users.json to SQLite if present."""
        if not os.path.exists(self.json_path):
            return

        # Only migrate if we haven't already (or simple check: if DB likely empty or we want to import?)
        # Better safe: Check if DB has users. If empty, import.
        if len(self.get_all_users()) > 0:
            return

        print("📦 Found legacy users.json, migrating to SQLite...")
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
        conn = None
        try:
            conn = self._get_conn()
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
        finally:
            if conn:
                conn.close()
        return None

    def add_user(self, user: User) -> None:
        """Adds or updates a user."""
        conn = None
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO users (username, password_hash, salt, is_admin, created_at, user_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user.username,
                user.password_hash,
                user.salt,
                1 if user.is_admin else 0,
                user.created_at,
                json.dumps(user.data.model_dump())
            ))
            conn.commit()
        except Exception as e:
            print(f"❌ Error adding user {user.username}: {e}")
        finally:
            if conn:
                conn.close()

    def update_user(self, username: str, mutate) -> bool:
        """Liest den Nutzer, lässt ihn ändern und schreibt ihn zurück — am Stück.

        `mutate` bekommt das `User`-Objekt und ändert es an Ort und Stelle; der
        Rückgabewert wird nicht angesehen. False heisst: Der Nutzer existiert
        nicht, es wurde nichts geschrieben.

        Der Weg über diese Methode ist der einzige, der gegen gleichzeitige
        Anfragen hält. Wer stattdessen `get_user()` und `add_user()` einzeln
        aufruft, liest ausserhalb der Sperre — und verliert bei Gleichzeitigkeit
        die Änderung des jeweils anderen.
        """
        with self._write_lock:
            user = self.get_user(username)
            if user is None:
                return False
            mutate(user)
            self.add_user(user)
            return True

    def get_all_users(self) -> List[User]:
        users = []
        conn = None
        self.last_read_ok = True
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            for row in rows:
                try:
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
                    print(f"⚠️ Failed to load user: {e}")
        except Exception as e:
            print(f"⚠️ Error getting all users: {e}")
            self.last_read_ok = False
        finally:
            if conn:
                conn.close()
        return users

    def create_default_admin(self):
        """Creates a default admin user if none exists."""
        print("👤 Creating default admin user (SQLite)...")
        salt = os.urandom(16)
        pwd_hash = self.hash_password("admin", salt)

        # Docker mode: Trigger setup wizard on first login
        user_data = UserVideoData()
        if os.getenv("CONFIG_DIR"):
            print("🐳 Docker mode - setup wizard will appear on first login")
            user_data.setup_complete = False

        admin_user = User(
            username="admin",
            password_hash=binascii.hexlify(pwd_hash).decode('ascii'),
            salt=binascii.hexlify(salt).decode('ascii'),
            is_admin=True,
            data=user_data
        )
        self.add_user(admin_user)

    def hash_password(self, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)

    # Fester Salt für den Leerlauf-Durchgang unten. Er schützt nichts — sein
    # einziger Zweck ist, dieselbe Rechenzeit zu verbrauchen wie ein echter
    # Versuch.
    _DUMMY_SALT = b"\x00" * 16

    def verify_password(self, username: str, password: str) -> bool:
        """Prüft ein Passwort. False auch für unbekannte Benutzernamen.

        Zur Laufzeit: Bei einem unbekannten Namen kehrte die Funktion früher
        sofort zurück, bei einem bekannten lief die PBKDF2-Ableitung. Gemessen
        waren das 0,28 ms gegen 62 ms — Faktor 220, über Netzwerk mühelos
        unterscheidbar. Damit ließen sich gültige Benutzernamen erraten, ohne
        ein Passwort zu kennen.

        Das wiegt hier schwerer, seit die Anmeldesperre auch am Benutzernamen
        hängt: Wer die gültigen Namen kennt, kann gezielt Konten aussperren.

        Deshalb läuft die Ableitung auch für unbekannte Namen — mit einem
        Wegwerf-Salt, dessen Ergebnis niemand ansieht. Die Antwort ist
        dieselbe, die Dauer ebenfalls.
        """
        import hmac as _hmac
        user = self.get_user(username)
        if not user:
            self.hash_password(password, self._DUMMY_SALT)
            return False

        try:
            salt = binascii.unhexlify(user.salt)
            stored_hash = binascii.unhexlify(user.password_hash)
            new_hash = self.hash_password(password, salt)
            # Constant-time comparison prevents timing side-channel attacks
            return _hmac.compare_digest(new_hash, stored_hash)
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
        self.migrate_sensitive_settings()
        self.cleanup_legacy_settings()

    def migrate_tags(self):
        """Migrates global available_tags to admin user."""
        admin = self.get_user("admin")
        if not admin:
            return

        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path):
            return

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
        if not admin:
            return

        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path):
            return

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
        if not admin:
            return

        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path):
            return

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

    def migrate_sensitive_settings(self):
        """Migrates global sensitive settings (Safe Mode) to admin user."""
        admin = self.get_user("admin")
        if not admin:
            return

        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path):
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            modified = False

            # Sensitive Dirs
            s_dirs = data.get("sensitive_dirs", [])
            for d in s_dirs:
                if d not in admin.data.sensitive_dirs:
                    admin.data.sensitive_dirs.append(d)
                    modified = True

            # Sensitive Tags
            s_tags = data.get("sensitive_tags", [])
            for t in s_tags:
                if t not in admin.data.sensitive_tags:
                    admin.data.sensitive_tags.append(t)
                    modified = True

            # Sensitive Collections
            s_cols = data.get("sensitive_collections", [])
            for c in s_cols:
                if c not in admin.data.sensitive_collections:
                    admin.data.sensitive_collections.append(c)
                    modified = True

            if modified:
                print("📦 Migrated sensitive settings to 'admin'.")
                self.add_user(admin)

        except Exception as e:
            print(f"⚠️ Error migrating sensitive settings: {e}")

    def remap_paths_in_user_data(self, mapping) -> int:
        """Schreibt Favoriten, Vault und Tags von einem Pfad auf einen anderen um.

        `mapping` ist `{alter Pfad: neuer Pfad}`. Zurückgegeben wird die Zahl
        der umgeschriebenen Einträge.

        Gedacht für den Fall, dass eine Datei **umgezogen** ist: Der
        Nutzerzustand hängt hier ausschließlich am Pfad, ein Umbenennen im
        Dateimanager sieht für die Bibliothek deshalb aus wie „alte Datei weg,
        neue Datei da". Favoriten, Vault-Markierung und Tags blieben dabei auf
        dem alten Pfad liegen — unsichtbar, aber für immer, und die neue Datei
        stand ohne alles da.

        Wer den Zustand des neuen Pfades **schon** gesetzt hat, behält ihn: Der
        Umzug ergänzt, er überschreibt nicht. Sonst könnte ein Scan eine
        Entscheidung zurücknehmen, die der Nutzer inzwischen getroffen hat.
        """
        pairs = {old: new for old, new in dict(mapping).items()
                 if old and new and old != new}
        if not pairs:
            return 0

        changed = 0
        # Dieselbe Sperre und dasselbe Muster wie beim Aufräumen darunter:
        # lesen, ändern, zurückschreiben — am Stück.
        with self._write_lock:
            for user in self.get_all_users():
                before = changed

                for old, new in pairs.items():
                    if old in user.data.favorites:
                        user.data.favorites.remove(old)
                        if new not in user.data.favorites:
                            user.data.favorites.append(new)
                        changed += 1

                    if old in user.data.vaulted:
                        user.data.vaulted.remove(old)
                        if new not in user.data.vaulted:
                            user.data.vaulted.append(new)
                        changed += 1

                    if old in user.data.tags:
                        alte_tags = user.data.tags.pop(old)
                        vorhanden = user.data.tags.get(new, [])
                        user.data.tags[new] = vorhanden + [
                            t for t in alte_tags if t not in vorhanden
                        ]
                        changed += 1

                if changed > before:
                    self.add_user(user)

        return changed

    def purge_paths_from_user_data(self, paths) -> int:
        """Entfernt gelöschte Pfade aus Favoriten, Vault und Tags aller Nutzer.

        Zurückgegeben wird die Zahl der entfernten Einträge.

        `db.remove()` löscht nur die Zeile in `media`. Der Nutzerzustand hängt
        aber am **Pfad** und blieb unangetastet, für immer. Zwei Folgen:

        1. Die Listen wachsen mit jeder gelöschten Datei. In dieser
           Installation stehen bereits 12 Tag-Einträge und drei
           Favoriten/Vault-Einträge auf Pfaden, die es nicht mehr gibt.

        2. Die gefährlichere: Entsteht später **dieselbe Pfadangabe erneut** —
           und beim Optimieren entsteht sie regelmäßig neu, weil aus
           ``film.mkv`` wieder ``film.mp4`` wird —, erbt die neue Datei
           stillschweigend den alten Zustand. Ein Video, das als „vaulted"
           galt, ist nach dem Neuanlegen sofort wieder versteckt, ohne dass
           irgendwo steht, warum.

        Aufgerufen wird das bei **ausdrücklichen** Löschungen durch den
        Nutzer. Nicht beim Aufräumen verwaister Einträge nach einem Scan: Dort
        warnt der Code selbst, dass diese Angaben „no rescan can restore" —
        und ein Scan, der sich irrt, würde sie sonst mitnehmen.
        """
        targets = {p for p in paths if p}
        if not targets:
            return 0

        removed = 0
        # Die ganze Schleife unter der Sperre: Sie liest jeden Nutzer, ändert
        # ihn und schreibt ihn zurück — genau das Muster, das ohne Sperre die
        # Änderung eines gleichzeitigen Aufrufers verwirft.
        with self._write_lock:
            for user in self.get_all_users():
                before = removed

                keep_fav = [p for p in user.data.favorites if p not in targets]
                removed += len(user.data.favorites) - len(keep_fav)
                user.data.favorites = keep_fav

                keep_vault = [p for p in user.data.vaulted if p not in targets]
                removed += len(user.data.vaulted) - len(keep_vault)
                user.data.vaulted = keep_vault

                keep_tags = {p: t for p, t in user.data.tags.items() if p not in targets}
                removed += len(user.data.tags) - len(keep_tags)
                user.data.tags = keep_tags

                if removed > before:
                    self.add_user(user)

        return removed

    def cleanup_legacy_settings(self):
        """Removes migrated keys from settings.json."""
        settings_path = os.path.join(config.hidden_data_dir, "settings.json")
        if not os.path.exists(settings_path):
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            keys_to_remove = [
                "smart_collections",
                "scan_targets",
                "exclude_paths",
                "available_tags",
                "sensitive_dirs",
                "sensitive_tags",
                "sensitive_collections"
            ]

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
