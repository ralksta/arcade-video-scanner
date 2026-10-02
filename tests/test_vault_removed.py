"""
test_vault_removed.py
---------------------
Der Vault ist als Funktion entfernt (UMSETZUNGSPLAN Phase 1, ENTSCHEIDUNGEN.md
Punkt 4, umgesetzt 2026-10-02).

Zwei Dinge halten diese Tests fest:

1. **Die Daten.** `UserStore.drop_vault_data()` entfernt `vaulted` beim Start
   einmalig aus allen Konten in users.db — ohne Favoriten, Tags oder andere
   Felder anzufassen. Ein zweiter Lauf findet nichts mehr.
2. **Dass er nicht stillschweigend zurückkehrt.** Kein Modellfeld, keine Route,
   keine Oberfläche. Ausdrücklich **nicht** betroffen ist der abgesicherte Modus
   (`sensitive_*`) — eine andere Funktion, die bleibt.

Die Spalte `vaulted` in der Medientabelle bleibt im Schema stehen, damit
bestehende Datenbanken ohne Tabellenumbau weiterlaufen; geschrieben wird 0.
"""
import binascii
import json
import os
import re
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "arcade_scanner" / "server" / "static"


@pytest.fixture
def store(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.user_store.config", mock_config):
        from arcade_scanner.database.user_store import User, UserStore

        s = UserStore()
        for name in ("ralf", "privat"):
            salt = os.urandom(16)
            s.add_user(User(username=name, salt=binascii.hexlify(salt).decode(),
                            password_hash=binascii.hexlify(s.hash_password("pw", salt)).decode()))
        yield s


def _raw(store, name):
    with sqlite3.connect(store.db_path) as conn:
        return json.loads(conn.execute(
            "SELECT user_data FROM users WHERE username = ?", (name,)).fetchone()[0])


def _plant_vault(store, name, paths):
    """Schreibt `vaulted` so in users.db, wie es vor Phase 1 dort stand."""
    data = _raw(store, name)
    data["vaulted"] = list(paths)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE users SET user_data = ? WHERE username = ?",
                     (json.dumps(data), name))


def test_the_migration_removes_the_field_and_keeps_everything_else(store):
    store.update_user("ralf", lambda u: (u.data.favorites.append("/m/a.mp4"),
                                         u.data.tags.update({"/m/a.mp4": ["urlaub"]})))
    _plant_vault(store, "ralf", ["/m/privat.mp4"])
    _plant_vault(store, "privat", ["/m/x.mp4", "/m/y.mp4"])

    assert store.drop_vault_data() == 2

    for name in ("ralf", "privat"):
        assert "vaulted" not in _raw(store, name)
    assert _raw(store, "ralf")["favorites"] == ["/m/a.mp4"]
    assert _raw(store, "ralf")["tags"] == {"/m/a.mp4": ["urlaub"]}


def test_a_second_run_does_nothing(store):
    _plant_vault(store, "ralf", ["/m/privat.mp4"])
    store.drop_vault_data()
    assert store.drop_vault_data() == 0


def test_accounts_without_the_field_are_not_rewritten(store, monkeypatch):
    calls = []
    monkeypatch.setattr(store, "update_user", lambda name, fn: calls.append(name) or True)
    assert store.drop_vault_data() == 0
    assert calls == []


def test_the_migration_runs_at_startup():
    source = (ROOT / "arcade_scanner" / "database" / "user_store.py").read_text(encoding="utf-8")
    block = source.split("def migrate_from_db", 1)[1].split("\n    def ", 1)[0]
    assert "self.drop_vault_data()" in block


# --- Kehrt nicht zurück ---

def test_no_model_carries_a_vault_field():
    from arcade_scanner.models.media_asset import MediaAsset
    from arcade_scanner.models.user import UserVideoData
    from arcade_scanner.models.video_entry import VideoEntry

    for model in (UserVideoData, VideoEntry, MediaAsset):
        assert "vaulted" not in model.model_fields, model.__name__


def test_the_hide_routes_are_gone():
    source = (ROOT / "arcade_scanner" / "server" / "routes" / "files.py").read_text(encoding="utf-8")
    assert '"/hide?"' not in source and '"/batch_hide?' not in source


@pytest.mark.parametrize("js", sorted(p.name for p in STATIC.glob("*.js")))
def test_no_script_knows_the_vault(js):
    source = (STATIC / js).read_text(encoding="utf-8")
    code = "\n".join(ln for ln in source.splitlines() if not ln.lstrip().startswith(("//", "*")))
    assert not re.search(r"\bvault|\bVault|/hide\?|batch_hide|toggleHidden", code), js


def test_safe_mode_is_untouched():
    """Eine andere Funktion — darf beim Aufräumen nicht mitgehen."""
    from arcade_scanner.models.user import UserVideoData
    for field in ("sensitive_dirs", "sensitive_tags", "sensitive_collections"):
        assert field in UserVideoData.model_fields
    assert "function isSensitive" in (STATIC / "utils.js").read_text(encoding="utf-8")
