"""
test_user_data_races.py
-----------------------
Zwei gleichzeitige Anfragen desselben Kontos verwarfen die Änderung des jeweils
anderen.

Der übliche Ablauf im Server ist::

    u = user_db.get_user(user_name)     # lesen
    u.data.favorites.append(pfad)       # ändern
    user_db.add_user(u)                 # zurückschreiben

`add_user()` schreibt den **gesamten** Nutzerdatensatz als ein JSON-Feld
zurück. Der Server ist ein `ThreadingTCPServer`, jede Anfrage läuft also in
einem eigenen Thread. Ein Favorit auf dem Fernseher und ein Tag im Browser
lesen beide den alten Stand — und wer zuletzt schreibt, gewinnt alles.

Nachgemessen mit 60 gleichzeitigen Favoriten auf einem Testkonto::

    einzeln über get_user/add_user :  4 von 60 angekommen, 56 verloren
    über update_user()             : 60 von 60 angekommen

Das ist kein Grenzfall der Nebenläufigkeit, sondern ihre Normalform: Der Verlust
tritt schon bei zwei Anfragen ein, die sich um Millisekunden überschneiden.

`update_user(username, mutate)` hält eine wiedereintrittsfähige Sperre über
Lesen, Ändern und Schreiben. Umgestellt sind bisher die vier Wege mit dem
meisten Verkehr (Favorit und Vault, einzeln und als Stapel). Die übrigen —
Tags, Einstellungen, Auto-Tag-Regeln — stehen noch aus und sind im
Übergabebericht vermerkt; solange sie einzeln lesen, können sie eine
gleichzeitige Änderung weiterhin verwerfen.
"""
import binascii
import os
import threading
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
            username="ralf",
            password_hash=binascii.hexlify(s.hash_password("x", salt)).decode(),
            salt=binascii.hexlify(salt).decode(),
            is_admin=False,
        ))
        yield s


def run_concurrently(fn, count):
    threads = [threading.Thread(target=fn, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


# --- Der Fund, und der Beleg dass er echt ist ---

def test_separate_read_and_write_loses_updates(store):
    """
    Das alte Muster, ausdrücklich nachgestellt. Ohne diesen Test wäre der
    darunter nur eine Behauptung — er zeigt, dass die Sperre etwas verhindert,
    das sonst wirklich passiert.
    """
    def add(i):
        user = store.get_user("ralf")
        user.data.favorites.append(f"/media/{i}.mp4")
        store.add_user(user)

    run_concurrently(add, 60)

    angekommen = len(store.get_user("ralf").data.favorites)
    if angekommen == 60:
        # Möglich, wenn die Threads sich zufällig nicht überschneiden. Dieser
        # Test soll den Verlust *vorführen*, nicht ihn erzwingen — ein
        # Fehlschlag hier wäre eine Aussage über den Scheduler, nicht über den
        # Code. Der Test darunter ist der, der etwas verlangt.
        pytest.skip("Das Rennen ist in diesem Lauf nicht eingetreten")

    assert angekommen < 60


def test_update_user_keeps_every_change(store):
    def add(i):
        store.update_user("ralf", lambda u: u.data.favorites.append(f"/media/{i}.mp4"))

    run_concurrently(add, 60)

    assert len(store.get_user("ralf").data.favorites) == 60


def test_two_different_fields_do_not_clobber_each_other(store):
    """
    Der Fall aus dem Alltag: ein Favorit auf dem Fernseher, ein Tag im
    Browser. Beide hängen im selben JSON-Feld.
    """
    def touch(i):
        if i % 2:
            store.update_user("ralf", lambda u: u.data.favorites.append(f"/f{i}.mp4"))
        else:
            store.update_user(
                "ralf", lambda u: u.data.tags.setdefault(f"/t{i}.mp4", []).append("neu"))

    run_concurrently(touch, 40)

    user = store.get_user("ralf")
    assert len(user.data.favorites) == 20
    assert len(user.data.tags) == 20


def test_removals_survive_too(store):
    """Nicht nur Anhängen — auch das Entfernen darf nicht verlorengehen."""
    store.update_user(
        "ralf", lambda u: u.data.favorites.extend(f"/media/{i}.mp4" for i in range(30)))

    def remove(i):
        store.update_user("ralf", lambda u: u.data.favorites.remove(f"/media/{i}.mp4"))

    run_concurrently(remove, 30)

    assert store.get_user("ralf").data.favorites == []


# --- Verhalten der Methode selbst ---

def test_an_unknown_user_writes_nothing(store):
    called = []

    assert store.update_user("gibtsnicht", lambda u: called.append(u)) is False
    assert called == []


def test_the_mutation_is_applied_and_persisted(store):
    store.update_user("ralf", lambda u: u.data.vaulted.append("/media/privat.mp4"))

    assert store.get_user("ralf").data.vaulted == ["/media/privat.mp4"]


def test_the_lock_is_reentrant(store):
    """
    `update_user()` ruft innerhalb der Sperre `get_user()` und `add_user()`
    auf. Mit einem einfachen Lock stünde die Methode auf sich selbst.
    """
    store.update_user("ralf", lambda u: u.data.favorites.append("/a.mp4"))
    store.update_user("ralf", lambda u: u.data.favorites.append("/b.mp4"))

    assert store.get_user("ralf").data.favorites == ["/a.mp4", "/b.mp4"]


def test_purging_holds_the_lock_across_the_whole_loop(store):
    """
    `purge_paths_from_user_data()` liest, ändert und schreibt jeden Nutzer —
    dasselbe Muster, dieselbe Gefahr.
    """
    import inspect

    from arcade_scanner.database.user_store import UserStore

    source = inspect.getsource(UserStore.purge_paths_from_user_data)
    body = source.split("removed = 0", 1)[1]

    assert body.lstrip().startswith("#") or "with self._write_lock:" in body
    assert body.index("with self._write_lock:") < body.index("for user in")


# --- Welche Wege schon umgestellt sind ---

def test_the_favourite_and_vault_routes_use_update_user():
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "files.py"
    ).read_text(encoding="utf-8")
    code = "\n".join(
        ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
    )

    assert code.count("user_db.update_user(") == 4
    assert "user_db.add_user(" not in code, (
        "In files.py wird wieder einzeln geschrieben — das verliert bei "
        "gleichzeitigen Anfragen Änderungen"
    )


def test_the_remaining_routes_are_listed_as_open():
    """
    Ehrlich festgehalten, was noch aussteht. Verschwindet ein Name aus dieser
    Liste, weil der Weg umgestellt wurde, wird der Test rot — und dann gehört
    der Eintrag hier und im Bericht gestrichen, nicht der Test.
    """
    from pathlib import Path

    base = Path(__file__).parent.parent / "arcade_scanner"
    still_open = {
        "server/routes/tags.py",
        "server/routes/settings.py",
        "server/routes/autotag.py",
        "core/auto_tagger.py",
    }

    for rel in sorted(still_open):
        source = (base / rel).read_text(encoding="utf-8")
        assert "add_user(" in source, (
            f"{rel} schreibt nicht mehr einzeln — Eintrag aus der Liste nehmen"
        )
