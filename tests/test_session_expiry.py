"""
test_session_expiry.py
----------------------
Zwei Listen, die nie kleiner wurden.

**Die Sperrliste.** `record_failure()` legt bei jedem gescheiterten
Anmeldeversuch einen Eintrag an. Der Schlüssel kommt aus der Anfrage: die IP
aus `X-Forwarded-For` und der Kontoschlüssel aus dem eingetippten
Benutzernamen. Entfernt wurde ein Eintrag nur, wenn **derselbe** Schlüssel
später eine erfolgreiche Anmeldung hatte — für erfundene Werte passiert das
nie.

Damit konnte jeder, der den Anmeldeport erreicht, den Arbeitsspeicher des
Servers unbegrenzt wachsen lassen: ohne Konto, mit gewöhnlichen Anfragen, eine
neue Kopfzeile je Versuch. Der Server ist ein einzelner Prozess ohne
Speichergrenze; am Ende steht er.

Dabei war nichts an dieser Liste je dafür gedacht, länger als eine
Viertelstunde zu leben — Zeitfenster und Sperrdauer sind beide 900 Sekunden.
Sie wurde nur nie aufgeräumt. Das ist der eigentliche Fund dieses Themenfelds:
Ein Ablaufdatum, das nirgends vollstreckt wird, ist keines.

**Die Sitzungsliste.** Dasselbe milder: Eine abgelaufene Sitzung verschwand
erst, wenn jemand ihr Token noch einmal vorzeigte. Bei einem vergessenen Gerät
nie.

Aufgeräumt wird jetzt beim Schreiben — dort, wo die Listen wachsen. Beim
Deckeln fliegen **nicht gesperrte** Einträge zuerst: Eine laufende Sperre
wegzuwerfen wäre genau das Loch, das die Sperre schließen soll.
"""
import time

import pytest

from arcade_scanner.security.auth import (
    _LOCKOUT_SECONDS,
    _MAX_ATTEMPTS,
    _MAX_FAILED_RECORDS,
    _WINDOW_SECONDS,
    SessionManager,
)


@pytest.fixture
def manager():
    return SessionManager()


# --- Der Fund: die Sperrliste wuchs unbegrenzt ---

def test_a_flood_of_invented_keys_stays_bounded(manager):
    """
    Jeder Fehlversuch mit einem neuen `X-Forwarded-For` legte einen Eintrag an,
    der nie wieder verschwand.
    """
    for i in range(_MAX_FAILED_RECORDS * 2):
        manager.record_failure(f"10.0.{i // 256}.{i % 256}")

    assert len(manager._failed) <= _MAX_FAILED_RECORDS


def test_expired_records_are_dropped(manager):
    """
    Der Normalfall, der ohne Angriff eintritt: ein paar Fehlversuche, dann
    Ruhe. Nach dem Zeitfenster ist der Eintrag wirkungslos — und weg.

    Aufgeräumt wird erst, wenn die Liste die Obergrenze erreicht: Darunter ist
    sie ein paar Kilobyte groß, und bei jedem Fehlversuch über alle Einträge zu
    laufen wäre die zweite Art, den Server zu beschäftigen.
    """
    manager._failed["1.2.3.4"] = {"attempts": [time.time() - _WINDOW_SECONDS - 10]}
    for i in range(_MAX_FAILED_RECORDS):
        manager._failed[f"fuell-{i}"] = {"attempts": [time.time() - _WINDOW_SECONDS - 10]}

    manager.record_failure("5.6.7.8")

    assert "1.2.3.4" not in manager._failed


def test_a_record_inside_the_window_is_kept(manager):
    manager.record_failure("1.2.3.4")

    manager.record_failure("5.6.7.8")

    assert "1.2.3.4" in manager._failed


def test_small_lists_are_left_alone(manager):
    """
    Unterhalb der Grenze wird nichts angefasst — auch nichts Abgelaufenes.
    Das ist Absicht: Der Aufwand lohnt erst, wenn es etwas zu holen gibt.
    """
    manager._failed["alt"] = {"attempts": [time.time() - _WINDOW_SECONDS - 10]}

    manager.record_failure("neu")

    assert "alt" in manager._failed


# --- Die Sperre darf dabei nicht verloren gehen ---

def test_an_active_lockout_survives_a_flood(manager):
    """
    Der Punkt, an dem eine schlecht gebaute Obergrenze zum Loch wird: Könnte
    ein Angreifer die Liste vollschreiben und damit die Sperre seines Opfers
    hinausdrängen, wäre die Deckelung schlimmer als das Wachstum.
    """
    for _ in range(_MAX_ATTEMPTS):
        manager.record_failure("user:ralf")
    assert manager.is_locked_out("user:ralf")

    for i in range(_MAX_FAILED_RECORDS * 2):
        manager.record_failure(f"10.0.{i // 256}.{i % 256}")

    assert manager.is_locked_out("user:ralf")


def test_the_lockout_still_ends_on_time(manager):
    for _ in range(_MAX_ATTEMPTS):
        manager.record_failure("1.2.3.4")
    assert manager.is_locked_out("1.2.3.4")

    manager._failed["1.2.3.4"]["locked_until"] = time.time() - 1

    assert manager.is_locked_out("1.2.3.4") is False


def test_counting_is_unchanged(manager):
    """Die Aufräumerei darf die Zählung nicht verstellen."""
    verbleibend = [manager.record_failure("1.2.3.4") for _ in range(_MAX_ATTEMPTS)]

    assert verbleibend == [4, 3, 2, 1, 0]
    assert manager.is_locked_out("1.2.3.4")


def test_a_success_still_clears_the_history(manager):
    manager.record_failure("1.2.3.4")

    manager.record_success("1.2.3.4")

    assert "1.2.3.4" not in manager._failed


def test_the_lockout_duration_is_untouched(manager):
    for _ in range(_MAX_ATTEMPTS):
        manager.record_failure("1.2.3.4")

    bis = manager._failed["1.2.3.4"]["locked_until"]

    assert _LOCKOUT_SECONDS - 5 < bis - time.time() <= _LOCKOUT_SECONDS


# --- Die Sitzungsliste ---

def test_expired_sessions_are_removed_without_being_visited(manager):
    """
    Vorher verfiel eine Sitzung erst, wenn jemand ihr Token noch einmal
    vorzeigte. Bei einem vergessenen Gerät nie.
    """
    token = manager.create_session("ralf")
    manager._sessions[token]["created_at"] = time.time() - manager.timeout - 1

    manager.create_session("gast")

    assert token not in manager._sessions


def test_a_valid_session_is_not_removed(manager):
    token = manager.create_session("ralf")

    manager.create_session("gast")

    assert manager.get_username(token) == "ralf"


def test_pruning_reports_how_many_went(manager):
    for i in range(3):
        manager._sessions[f"token-{i}"] = {
            "username": "ralf",
            "created_at": time.time() - manager.timeout - 1,
        }

    assert manager.prune_sessions() == 3
    assert manager._sessions == {}


def test_an_expired_token_is_still_refused(manager):
    """Die alte Prüfung beim Zugriff bleibt — sie ist die eigentliche."""
    token = manager.create_session("ralf")
    manager._sessions[token]["created_at"] = time.time() - manager.timeout - 1

    assert manager.get_username(token) is None


def test_revoking_still_works(manager):
    token = manager.create_session("ralf")

    manager.revoke_session(token)

    assert manager.get_username(token) is None
