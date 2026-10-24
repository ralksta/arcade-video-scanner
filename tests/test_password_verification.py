"""
test_password_verification.py
-----------------------------
Passwortprüfung: Korrektheit und Laufzeitverhalten.

Das Hashing selbst ist solide — PBKDF2-HMAC-SHA256 mit 100.000 Iterationen,
16 Byte Zufallssalz je Nutzer, konstantzeitiger Vergleich. Der Code sagt das
auch: „Constant-time comparison prevents timing side-channel attacks."

Eine Ebene darüber galt es nicht. Bei einem **unbekannten Benutzernamen** kehrte
`verify_password()` sofort zurück, ohne zu rechnen. Gemessen:

    Nutzer existiert, Passwort falsch :  62,39 ms
    Nutzer existiert nicht            :   0,28 ms   → Faktor 220

Über Netzwerk mühelos unterscheidbar. Damit ließen sich gültige Benutzernamen
erraten, ohne ein Passwort zu kennen — und seit die Anmeldesperre auch am
Benutzernamen hängt (siehe `tests/test_login_lockout.py`), kann man mit dieser
Liste gezielt Konten aussperren.

Die Ableitung läuft jetzt auch für unbekannte Namen, mit einem Wegwerf-Salz.
"""
import binascii
import os
import statistics
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def store(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.user_store.config", mock_config):
        from arcade_scanner.database.user_store import User, UserStore

        s = UserStore()
        salt = os.urandom(16)
        s.add_user(User(
            username="alice",
            password_hash=binascii.hexlify(s.hash_password("richtig", salt)).decode(),
            salt=binascii.hexlify(salt).decode(),
            is_admin=False,
        ))
        yield s


# --- Korrektheit ---

def test_the_right_password_is_accepted(store):
    assert store.verify_password("alice", "richtig") is True


@pytest.mark.parametrize("wrong", ["falsch", "", "Richtig", "richtig ", " richtig"])
def test_a_wrong_password_is_rejected(store, wrong):
    assert store.verify_password("alice", wrong) is False


def test_an_unknown_user_is_rejected(store):
    assert store.verify_password("gibtsnicht", "richtig") is False


def test_the_username_is_case_sensitive(store):
    """
    Festgehalten, damit es eine Entscheidung bleibt: Die Anmeldesperre
    normalisiert auf Kleinschreibung, die Prüfung nicht. Ändert sich eines von
    beiden, muss das andere folgen.
    """
    assert store.verify_password("Alice", "richtig") is False


# --- Ableitung ---

def test_the_hash_depends_on_the_salt(store):
    a = store.hash_password("gleiches-passwort", b"\x01" * 16)
    b = store.hash_password("gleiches-passwort", b"\x02" * 16)
    assert a != b, "Gleiches Passwort, anderes Salz — der Hash muss sich unterscheiden"


def test_the_derivation_is_deterministic(store):
    salt = os.urandom(16)
    assert store.hash_password("x", salt) == store.hash_password("x", salt)


def test_the_iteration_count_is_not_lowered():
    """
    100.000 Iterationen sind der Kostenfaktor gegen Offline-Angriffe auf die
    Datenbank. Eine Senkung ist keine Optimierung, sondern eine Schwächung.
    """
    import inspect

    from arcade_scanner.database.user_store import UserStore

    source = inspect.getsource(UserStore.hash_password)
    assert "100000" in source
    assert "pbkdf2_hmac" in source and "sha256" in source


def test_comparison_is_constant_time():
    import inspect

    from arcade_scanner.database.user_store import UserStore

    assert "compare_digest" in inspect.getsource(UserStore.verify_password)


# --- Das eigentliche Fundstück ---

def test_an_unknown_user_still_costs_a_derivation(store):
    """
    Der strukturelle Beleg: Auch ohne Treffer wird abgeleitet. Ohne diese Zeile
    verrät die Antwortzeit, welche Benutzernamen es gibt.
    """
    import inspect

    from arcade_scanner.database.user_store import UserStore

    source = inspect.getsource(UserStore.verify_password)
    unknown_branch = source.split("if not user:", 1)[1].split("return False", 1)[0]
    assert "hash_password" in unknown_branch, (
        "Bei unbekanntem Namen wird nicht gerechnet — die Antwortzeit verrät "
        "dann, welche Konten existieren"
    )


@pytest.mark.parametrize("run", range(3))
def test_both_paths_take_a_comparable_amount_of_time(store, run):
    """
    Der messende Beleg. Absichtlich großzügig: gemessen wird auf einem
    geteilten Rechner, und die Aussage ist „gleiche Größenordnung", nicht
    „identisch". Vor der Korrektur lag der Faktor bei 220.

    Dreimal ausgeführt, damit ein zufälliger Ausschlag sichtbar würde statt
    sich hinter einer einzelnen Messung zu verstecken.
    """
    def measure(username):
        samples = []
        for _ in range(5):
            start = time.perf_counter()
            store.verify_password(username, "falsches-passwort")
            samples.append(time.perf_counter() - start)
        return statistics.median(samples)

    known = measure("alice")
    unknown = measure("gibtsnicht")

    ratio = max(known, unknown) / max(min(known, unknown), 1e-9)
    assert ratio < 5, (
        f"Laufzeiten unterscheiden sich um Faktor {ratio:.1f} "
        f"(bekannt {known * 1000:.1f} ms, unbekannt {unknown * 1000:.1f} ms) — "
        "das erlaubt das Erraten gültiger Benutzernamen"
    )


def test_the_dummy_salt_is_not_used_for_real_users(store):
    """
    Gegenprobe: Das Wegwerf-Salz darf nirgends in einen echten Datensatz
    geraten — es ist konstant und wäre damit wertlos.
    """
    from arcade_scanner.database.user_store import UserStore

    user = store.get_user("alice")
    assert binascii.unhexlify(user.salt) != UserStore._DUMMY_SALT
