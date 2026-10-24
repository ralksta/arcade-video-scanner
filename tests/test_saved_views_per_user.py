"""
test_saved_views_per_user.py
----------------------------
Gespeicherte Ansichten gehören dem Konto (UMSETZUNGSPLAN Phase 2,
ENTSCHEIDUNGEN.md Punkt 2).

Bis 2026-10-02 lebte `saved_views` in der globalen settings.json. Eine Ansicht
trägt Suchbegriff und Ordnerpfad — jedes Konto sah damit, wonach die anderen
gesucht hatten, und konnte deren Ansichten überschreiben. Diese Datei ersetzt
`test_saved_views_sharing.py`, der den alten Zustand festhielt.

Geprüft wird an einem echten `UserStore` und einer echten `ConfigManager`-
Instanz im Temporärverzeichnis: Die Migration liest und schreibt beide.
"""
import binascii
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent

VIEW_A = {"id": "v1", "name": "Urlaub", "search": "strand", "folder": "/media/ralf/2019"}
VIEW_B = {"id": "v2", "name": "Drohne", "search": "dji", "folder": "/media/ralf/luft"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Echte config + echter UserStore, beide im Temp-Verzeichnis."""
    from arcade_scanner import config as config_module
    from arcade_scanner.database import user_store as user_store_module

    for name, value in (("HIDDEN_DATA_DIR", tmp_path), ("THUMB_DIR", tmp_path / "t"),
                        ("REVIEW_DIR", tmp_path / "r"),
                        ("SETTINGS_FILE", tmp_path / "settings.json")):
        monkeypatch.setattr(config_module, name, str(value))
    cfg = config_module.ConfigManager()
    monkeypatch.setattr(user_store_module, "config", cfg)

    store = user_store_module.UserStore()
    for name, admin in (("admin", True), ("privat", False)):
        salt = os.urandom(16)
        store.add_user(user_store_module.User(
            username=name, is_admin=admin, salt=binascii.hexlify(salt).decode(),
            password_hash=binascii.hexlify(store.hash_password("pw", salt)).decode()))
    return cfg, store, tmp_path / "settings.json"


def _write_settings(path, **data):
    path.write_text(json.dumps(data), encoding="utf-8")


# --- Route: zwei Konten, zwei Listen ---

def _route(store, cfg, user, body=None):
    from arcade_scanner.server.routes import settings as route

    handler = MagicMock()
    handler.get_current_user.return_value = user
    handler.path = "/api/settings"
    sent = {}
    if body is not None:
        raw = json.dumps(body).encode()
        handler.headers = {"Content-Length": str(len(raw))}
        handler.rfile.read.return_value = raw
    with patch.object(route, "_get_singletons", return_value=(cfg, store, MagicMock(), 10**6)), \
         patch.object(route, "send_json", side_effect=lambda _h, p, **k: sent.update(p)):
        (route.handle_post if body is not None else route.handle_get)(handler)
    return handler, sent


def test_two_accounts_keep_separate_views(env):
    cfg, store, _ = env
    _route(store, cfg, "admin", body={"saved_views": [VIEW_A]})
    _route(store, cfg, "privat", body={"saved_views": [VIEW_B]})

    assert _route(store, cfg, "admin")[1]["saved_views"] == [VIEW_A]
    assert _route(store, cfg, "privat")[1]["saved_views"] == [VIEW_B]


def test_views_no_longer_land_in_the_global_file(env):
    cfg, store, settings_file = env
    _route(store, cfg, "privat", body={"saved_views": [VIEW_B]})
    if settings_file.exists():
        assert "saved_views" not in json.loads(settings_file.read_text(encoding="utf-8"))


def test_a_client_that_omits_the_field_deletes_nothing(env):
    """Die Falle aus ENTSCHEIDUNGEN.md Punkt 7: „nicht angegeben" ≠ „leer"."""
    cfg, store, _ = env
    _route(store, cfg, "admin", body={"saved_views": [VIEW_A]})
    _route(store, cfg, "admin", body={"available_tags": []})
    assert store.get_user("admin").data.saved_views == [VIEW_A]


def test_an_empty_list_does_delete(env):
    cfg, store, _ = env
    _route(store, cfg, "admin", body={"saved_views": [VIEW_A]})
    _route(store, cfg, "admin", body={"saved_views": []})
    assert store.get_user("admin").data.saved_views == []


# --- Migration ---

def test_global_views_move_to_the_admin(env):
    cfg, store, settings_file = env
    _write_settings(settings_file, saved_views=[VIEW_A, VIEW_B], min_size_mb=50)

    assert store.migrate_saved_views() == 2

    assert store.get_user("admin").data.saved_views == [VIEW_A, VIEW_B]
    assert store.get_user("privat").data.saved_views == []
    left = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "saved_views" not in left
    assert left["min_size_mb"] == 50, "Andere Einstellungen müssen bleiben"


def test_the_migration_runs_only_once(env):
    """Gelöschte Ansichten dürfen beim nächsten Start nicht zurückkehren."""
    cfg, store, settings_file = env
    _write_settings(settings_file, saved_views=[VIEW_A, VIEW_B])
    store.migrate_saved_views()

    store.update_user("admin", lambda u: u.data.saved_views.remove(VIEW_A))
    assert store.migrate_saved_views() == 0
    assert store.get_user("admin").data.saved_views == [VIEW_B]


def test_a_failed_takeover_keeps_the_views_in_the_file(env, monkeypatch):
    """Erst übernehmen, dann löschen — nie andersherum."""
    cfg, store, settings_file = env
    _write_settings(settings_file, saved_views=[VIEW_A])
    monkeypatch.setattr(store, "update_user", lambda *a, **k: False)

    assert store.migrate_saved_views() == 0
    assert json.loads(settings_file.read_text(encoding="utf-8"))["saved_views"] == [VIEW_A]


def test_a_failed_removal_does_not_duplicate_on_the_next_start(env, monkeypatch):
    cfg, store, settings_file = env
    _write_settings(settings_file, saved_views=[VIEW_A])
    monkeypatch.setattr(cfg, "remove_keys", lambda keys: False)
    store.migrate_saved_views()
    store.migrate_saved_views()
    assert store.get_user("admin").data.saved_views == [VIEW_A]


def test_without_an_account_named_admin_the_first_admin_gets_them(env):
    cfg, store, settings_file = env
    from arcade_scanner.database.user_store import User
    boss = store.get_user("admin").model_copy(update={"username": "chef"})
    store.add_user(User(**boss.model_dump()))
    # Ein delete_user() gibt es (noch) nicht — Phase 4. Direkt in der Temp-DB.
    import sqlite3
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("DELETE FROM users WHERE username = 'admin'")
    assert store.get_user("admin") is None
    _write_settings(settings_file, saved_views=[VIEW_A])

    store.migrate_saved_views()
    assert store.get_user("chef").data.saved_views == [VIEW_A]


def test_an_empty_global_list_is_just_removed(env):
    cfg, store, settings_file = env
    _write_settings(settings_file, saved_views=[], theme="dark")
    assert store.migrate_saved_views() == 0
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_the_migration_is_part_of_startup():
    source = (ROOT / "arcade_scanner" / "database" / "user_store.py").read_text(encoding="utf-8")
    block = source.split("def migrate_from_db", 1)[1].split("\n    def ", 1)[0]
    assert block.index("migrate_saved_views()") < block.index("cleanup_legacy_settings()")


# --- Was eine Ansicht enthält (Begründung der Trennung) ---

def test_a_saved_view_really_carries_search_and_folder():
    settings_js = (ROOT / "arcade_scanner" / "server" / "static" / "settings.js").read_text(
        encoding="utf-8")
    block = settings_js.split("const newView = {", 1)[1].split("};", 1)[0]
    assert "search:" in block and "folder:" in block


def test_the_global_setting_is_gone():
    from arcade_scanner.config import DEFAULT_SETTINGS_JSON, AppSettings
    assert "saved_views" not in AppSettings.model_fields
    assert "saved_views" not in DEFAULT_SETTINGS_JSON
