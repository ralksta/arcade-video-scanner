"""
test_sessions_survive_restart.py
--------------------------------
Sitzungen überleben einen Neustart des Servers (2026-10-02).

Bis dahin lebten sie nur im Speicher. Eine Sitzung soll 30 Tage gelten, aber
jeder Neustart — Update, Docker-Neustart — meldete alle Geräte ab. Am
Fernseher hiess das: Benutzername und Passwort mit der Fernbedienung neu
eintippen.

Ein „Neustart“ ist hier ein zweiter SessionManager auf derselben Datei.
"""
import time

from arcade_scanner.security import auth
from arcade_scanner.security.auth import SessionManager


def test_a_session_is_still_valid_after_a_restart(tmp_path):
    path = tmp_path / "sessions.db"
    token = SessionManager(store_path=str(path)).create_session("alice")

    after_restart = SessionManager(store_path=str(path))
    assert after_restart.get_username(token) == "alice"


def test_the_file_holds_no_usable_token(tmp_path):
    """Nur der Hash steht drin — wer die Datei liest, kann sich nicht anmelden."""
    path = tmp_path / "sessions.db"
    token = SessionManager(store_path=str(path)).create_session("alice")

    raw = path.read_bytes()
    assert token.encode() not in raw
    assert SessionManager._hash(token).encode() in raw


def test_logout_survives_the_restart_too(tmp_path):
    path = tmp_path / "sessions.db"
    before = SessionManager(store_path=str(path))
    token = before.create_session("alice")
    before.revoke_session(token)

    assert SessionManager(store_path=str(path)).get_username(token) is None


def test_expired_sessions_stay_expired_and_are_removed(tmp_path):
    path = tmp_path / "sessions.db"
    before = SessionManager(store_path=str(path))
    old = before.create_session("alice")
    fresh = before.create_session("bob")
    before._db().execute("UPDATE sessions SET created_at = ? WHERE token_hash = ?",
                         (time.time() - before.timeout - 60, SessionManager._hash(old)))
    before._db().commit()

    after = SessionManager(store_path=str(path))
    assert after.get_username(old) is None
    assert after.get_username(fresh) == "bob"
    rows = after._db().execute("SELECT username FROM sessions").fetchall()
    assert rows == [("bob",)]


def test_prune_also_clears_the_file(tmp_path):
    path = tmp_path / "sessions.db"
    m = SessionManager(store_path=str(path))
    m.create_session("alice")
    assert m.prune_sessions(now=time.time() + m.timeout + 60) == 1
    assert m._db().execute("SELECT COUNT(*) FROM sessions").fetchone() == (0,)


def test_an_unusable_file_never_blocks_a_login(tmp_path):
    """Rechte, volle Platte, kaputter Pfad: dann eben nur im Speicher."""
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    m = SessionManager(store_path=str(blocker / "sessions.db"))
    token = m.create_session("alice")
    assert m.get_username(token) == "alice"
    assert m._store_path is None


def test_a_manager_without_path_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    m = SessionManager()
    m.get_username(m.create_session("alice"))
    assert list(tmp_path.iterdir()) == []


def test_the_server_instance_uses_the_data_dir():
    from arcade_scanner.config import config

    assert auth._default_store_path() == f"{config.hidden_data_dir}/sessions.db"
    # Im Test abgeschaltet (conftest), sonst schriebe die Suite nach arcade_data/.
    assert auth.session_manager._store_path is None
