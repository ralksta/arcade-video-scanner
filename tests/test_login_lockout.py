"""
test_login_lockout.py
---------------------
Die Brute-Force-Sperre ließ sich durch einen Header aushebeln.

`/api/login` bestimmte die Kennung für die Sperre so::

    client_ip = (
        self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or self.client_address[0]
    )

`X-Forwarded-For` setzt der Client. Wer den Server direkt erreicht — im LAN
oder über Tailscale — schickt bei jedem Versuch einen anderen erfundenen Wert
und bekommt jedes Mal einen frischen Zähler: fünf Versuche je Fantasie-IP,
beliebig viele Fantasie-IPs. Die Sperre war damit wirkungslos.

Bemerkenswert: `core/proxy_resolver.py` benennt dieselbe Eigenschaft
ausdrücklich — „XFF is forgeable — harmless here, because the worst outcome is
a different quality tier of a file the caller may already access." Dort stimmt
die Begründung. Der Login-Pfad hat dieselbe Logik noch einmal inline, ohne den
Vorbehalt — und dort ist sie nicht harmlos.

Ob dem Header zu trauen ist, hängt vom Aufbau ab (steht ein nginx davor?) und
lässt sich im Code nicht entscheiden. Deshalb zählt jetzt zusätzlich der
**Benutzername** mit: den muss ein Angreifer nennen, er lässt sich nicht
fälschen. Nebeneffekt in die richtige Richtung — hinter einem Proxy teilen sich
alle Nutzer eine IP, und die Konto-Sperre trifft nur das angegriffene Konto.
"""
import hashlib
import re
import threading
import time
from pathlib import Path
from time import sleep as time_sleep

import pytest

from arcade_scanner.security.auth import (
    _LOCKOUT_SECONDS,
    _MAX_ATTEMPTS,
    _WINDOW_SECONDS,
    SessionManager,
)

ROOT = Path(__file__).parent.parent
HANDLER = (ROOT / "arcade_scanner" / "server" / "api_handler.py").read_text(encoding="utf-8")


@pytest.fixture
def manager():
    return SessionManager()


# --- Die Sperre selbst ---

def test_lockout_triggers_after_the_configured_number_of_failures(manager):
    for _ in range(_MAX_ATTEMPTS - 1):
        manager.record_failure("10.0.0.1")
        assert not manager.is_locked_out("10.0.0.1")

    manager.record_failure("10.0.0.1")
    assert manager.is_locked_out("10.0.0.1")


def test_the_remaining_count_decreases(manager):
    remaining = [manager.record_failure("10.0.0.1") for _ in range(_MAX_ATTEMPTS)]
    assert remaining == sorted(remaining, reverse=True)
    assert remaining[-1] == 0


def test_a_successful_login_clears_the_history(manager):
    for _ in range(_MAX_ATTEMPTS - 1):
        manager.record_failure("10.0.0.1")

    manager.record_success("10.0.0.1")

    assert manager.record_failure("10.0.0.1") == _MAX_ATTEMPTS - 1


def test_keys_are_independent(manager):
    """Die Sperre einer Kennung darf keine andere treffen."""
    for _ in range(_MAX_ATTEMPTS):
        manager.record_failure("10.0.0.1")

    assert manager.is_locked_out("10.0.0.1")
    assert not manager.is_locked_out("10.0.0.2")
    assert not manager.is_locked_out("user:alice")


def test_old_attempts_fall_out_of_the_window(manager, monkeypatch):
    """Vier Fehlversuche vor Stunden dürfen den fünften heute nicht sperren."""
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() - _WINDOW_SECONDS - 60)
    for _ in range(_MAX_ATTEMPTS - 1):
        manager.record_failure("10.0.0.1")

    monkeypatch.setattr(time, "time", real_time)
    assert manager.record_failure("10.0.0.1") == _MAX_ATTEMPTS - 1
    assert not manager.is_locked_out("10.0.0.1")


def test_the_lock_expires(manager, monkeypatch):
    for _ in range(_MAX_ATTEMPTS):
        manager.record_failure("10.0.0.1")
    assert manager.is_locked_out("10.0.0.1")

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + _LOCKOUT_SECONDS + 1)
    assert not manager.is_locked_out("10.0.0.1")


# --- Der eigentliche Fund: die Kennung ---

def test_the_login_route_locks_on_the_account_too():
    """
    Ohne diese zweite Kennung genügt ein wechselnder X-Forwarded-For, um
    beliebig oft zu raten.
    """
    block = HANDLER.split("Brute-force rate limiting", 1)[1].split("Verify credentials", 1)[0]

    assert "account_key" in block, "Keine Sperre auf den Benutzernamen"
    assert 'f"user:{username.lower()}"' in block, (
        "Die Konto-Kennung muss aus dem Benutzernamen kommen — und "
        "gross/klein einheitlich, sonst umgeht 'Alice' die Sperre von 'alice'"
    )
    assert "begin_attempt(client_ip, account_key)" in block


def test_both_keys_are_counted_before_the_password_check():
    """
    Gezählt wird beim Beginn, nicht nach dem Fehlschlag — siehe
    ``test_parallel_attempts_cannot_exceed_the_limit``.
    """
    block = HANDLER.split("Brute-force rate limiting", 1)[1]
    assert "begin_attempt(client_ip, account_key)" in block
    assert block.index("begin_attempt(") < block.index("verify_password("), (
        "Die Sperre muss vor der Passwortprüfung zählen, sonst rasen parallele "
        "Anfragen durch, solange PBKDF2 läuft"
    )
    route = block.split("Invalid credentials", 1)[0]
    assert "is_locked_out(" not in route, (
        "Eine getrennte Prüfung vor dem Zählen ist genau die Lücke"
    )
    assert "record_failure(" not in route, (
        "Der Versuch ist in begin_attempt() schon gezählt — ein zweites "
        "Zählen halbiert die erlaubten Versuche"
    )


def test_both_keys_are_cleared_on_success():
    block = HANDLER.split("create_session(username)", 1)[0]
    assert "record_success(client_ip)" in block
    assert "record_success(account_key)" in block


def test_account_lockout_survives_a_rotating_forwarded_header(manager):
    """
    Der Angriff, den es zu verhindern gilt: jede Anfrage mit einer anderen
    erfundenen IP. Die Konto-Kennung bleibt dieselbe und zählt mit.
    """
    for i in range(_MAX_ATTEMPTS):
        fake_ip = f"203.0.113.{i}"
        assert not manager.is_locked_out(fake_ip), "IP-Sperre greift hier erwartungsgemäß nicht"
        manager.record_failure(fake_ip)
        manager.record_failure("user:alice")

    assert manager.is_locked_out("user:alice"), (
        "Trotz wechselnder IPs muss das Konto gesperrt sein"
    )


def test_a_shared_proxy_ip_does_not_lock_other_accounts(manager):
    """
    Die Gegenrichtung: Hinter einem Proxy teilen sich alle eine IP. Wird sie
    gesperrt, darf das andere Konten nicht treffen — deshalb ist die
    Konto-Sperre die feinere Kennung, nicht ein Ersatz für Nachdenken.
    """
    for _ in range(_MAX_ATTEMPTS):
        manager.record_failure("192.168.1.1")
        manager.record_failure("user:mallory")

    assert manager.is_locked_out("user:mallory")
    assert not manager.is_locked_out("user:ralf")


# --- Gleichzeitige Anmeldungen ---

def test_parallel_attempts_cannot_exceed_the_limit(manager):
    """
    Der Server ist ein ThreadingTCPServer, PBKDF2 gibt die GIL frei. Mit
    getrennter Prüfung (``is_locked_out``) und Zählung (``record_failure``)
    kamen gemessen 40 von 40 gleichzeitigen Versuchen durch.
    """
    n = 40
    barrier = threading.Barrier(n)
    admitted = []

    def attempt():
        barrier.wait()
        if manager.begin_attempt("10.0.0.1", "user:alice"):
            admitted.append(1)
            hashlib.pbkdf2_hmac("sha256", b"guess", b"salt" * 4, 20_000)

    threads = [threading.Thread(target=attempt) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(admitted) == _MAX_ATTEMPTS


def test_sequential_logins_behave_as_before(manager):
    """Wer nacheinander rät, bekommt dieselben fünf Versuche wie bisher."""
    for i in range(_MAX_ATTEMPTS):
        assert manager.begin_attempt("10.0.0.1", "user:alice"), f"Versuch {i + 1}"
        assert manager.remaining_attempts("10.0.0.1", "user:alice") == _MAX_ATTEMPTS - i - 1

    assert not manager.begin_attempt("10.0.0.1", "user:alice")


def test_a_success_on_the_last_attempt_is_not_punished(manager):
    """Der fünfte Versuch setzt die Sperre schon beim Zählen — ein Erfolg hebt sie auf."""
    for _ in range(_MAX_ATTEMPTS):
        assert manager.begin_attempt("10.0.0.1", "user:alice")

    manager.record_success("10.0.0.1")
    manager.record_success("user:alice")

    assert manager.begin_attempt("10.0.0.1", "user:alice")


def test_a_refused_attempt_counts_nowhere(manager):
    """Ist die IP gesperrt, darf das Konto keinen Versuch dazubekommen."""
    for _ in range(_MAX_ATTEMPTS):
        manager.record_failure("10.0.0.1")

    assert not manager.begin_attempt("10.0.0.1", "user:alice")
    assert manager.remaining_attempts("user:alice") == _MAX_ATTEMPTS


def test_concurrent_expiry_of_one_session_does_not_raise(manager, monkeypatch):
    """
    Zwei Anfragen mit demselben abgelaufenen Token: Beide fanden die Sitzung,
    beide riefen ``del`` — die zweite bekam ``KeyError`` und damit eine 500.
    """
    token = manager.create_session("alice")
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + manager.timeout + 1)

    original = manager._sessions

    class SlowDict(dict):
        def get(self, key, default=None):
            value = super().get(key, default)
            time_sleep(0.05)  # beide Threads stehen zwischen get() und del
            return value

    manager._sessions = SlowDict(original)
    errors = []

    def lookup():
        try:
            assert manager.get_username(token) is None
        except Exception as exc:  # noqa: BLE001 — genau das soll nicht passieren
            errors.append(exc)

    threads = [threading.Thread(target=lookup) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


# --- Sitzungen ---

def test_tokens_are_long_and_unique(manager):
    tokens = {manager.create_session("alice") for _ in range(50)}
    assert len(tokens) == 50, "Token wiederholen sich"
    assert all(len(t) == 64 for t in tokens), "secrets.token_hex(32) erwartet 64 Zeichen"
    assert all(re.fullmatch(r"[0-9a-f]+", t) for t in tokens)


def test_a_session_expires_after_the_configured_lifetime(manager, monkeypatch):
    token = manager.create_session("alice")
    assert manager.get_username(token) == "alice"

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + manager.timeout + 1)

    assert manager.get_username(token) is None


def test_an_expired_session_is_dropped_not_just_rejected(manager, monkeypatch):
    """Sonst wächst der Speicher mit jeder je erzeugten Sitzung."""
    token = manager.create_session("alice")
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + manager.timeout + 1)

    manager.get_username(token)
    assert token not in manager._sessions


def test_logout_invalidates_immediately(manager):
    token = manager.create_session("alice")
    manager.revoke_session(token)
    assert manager.get_username(token) is None


def test_an_unknown_token_is_rejected(manager):
    assert manager.get_username("00" * 32) is None
    assert manager.get_username("") is None
