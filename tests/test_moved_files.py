"""
test_moved_files.py
-------------------
Was passiert mit Tags, Favoriten und der Vault-Marke, wenn eine Datei
**umzieht**?

Bisher: Sie sind weg. Der Nutzerzustand hängt in diesem Projekt ausschließlich
am Pfad. Wer im Dateimanager `urlaub.mp4` in `urlaub-2019.mp4` umbenennt oder
in einen anderen Ordner schiebt, erzeugt aus Sicht der Bibliothek zwei
Vorgänge: eine verschwundene Datei und eine neue. Der Aufräumschritt nach dem
Scan löscht daraufhin die alte Zeile — und der Kommentar an genau dieser
Stelle sagt selbst, worum es geht: „user state — favorites, tags, vault flags —
that no rescan can restore".

Das trifft den Alltag härter als es klingt. Ordnung in einer Mediathek zu
schaffen *besteht* aus Umbenennen und Verschieben. Wer seine Bibliothek
aufräumt, verliert dabei genau die Arbeit, die er vorher in sie gesteckt hat —
und zwar still.

Erkannt wird ein Umzug an dem, was er nicht verändert: Dateigröße,
Änderungszeitpunkt und Laufzeit. Nur **eindeutige** Paare zählen. Passt ein
Fingerabdruck auf mehrere Dateien, bleibt es beim alten Verhalten: Eine
falsche Zuordnung würde fremde Tags anhängen, eine fehlende kostet nur das,
was ohnehin verloren war.
"""
import binascii
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.scanner.move_detect import detect_moves, fingerprint_of


class FakeEntry:
    """Nur die Felder, die den Fingerabdruck ausmachen."""

    def __init__(self, size_mb=100.0, mtime=1700000000, duration_sec=60.0,
                 imported_at=0):
        self.size_mb = size_mb
        self.mtime = mtime
        self.duration_sec = duration_sec
        self.imported_at = imported_at


# --- Der Fingerabdruck ---

def test_two_entries_of_the_same_file_share_a_fingerprint():
    a = FakeEntry()
    b = FakeEntry()

    assert fingerprint_of(a) == fingerprint_of(b)


def test_a_different_size_is_a_different_file():
    assert fingerprint_of(FakeEntry(size_mb=100.0)) != \
        fingerprint_of(FakeEntry(size_mb=100.001))


def test_a_different_mtime_is_a_different_file():
    assert fingerprint_of(FakeEntry(mtime=1700000000)) != \
        fingerprint_of(FakeEntry(mtime=1700000001))


def test_an_entry_without_a_size_has_no_fingerprint():
    """
    Sonst „stimmen" zwei unvollständige Einträge aus abgebrochenen Scans
    miteinander überein, und der Zustand landet an einer beliebigen Stelle.
    """
    assert fingerprint_of(FakeEntry(size_mb=0)) is None


def test_an_entry_without_an_mtime_has_no_fingerprint():
    assert fingerprint_of(FakeEntry(mtime=0)) is None


def test_a_broken_field_does_not_raise():
    kaputt = FakeEntry()
    kaputt.mtime = "vorgestern"

    assert fingerprint_of(kaputt) is None


# --- Die Zuordnung ---

def test_a_renamed_file_is_recognised():
    moves = detect_moves(
        gone={"/media/urlaub.mp4": FakeEntry()},
        arrived={"/media/urlaub-2019.mp4": FakeEntry()},
    )

    assert moves == {"/media/urlaub.mp4": "/media/urlaub-2019.mp4"}


def test_a_file_moved_to_another_folder_is_recognised():
    moves = detect_moves(
        gone={"/media/neu/film.mp4": FakeEntry()},
        arrived={"/media/sortiert/2019/film.mp4": FakeEntry()},
    )

    assert moves == {"/media/neu/film.mp4": "/media/sortiert/2019/film.mp4"}


def test_a_genuinely_deleted_file_is_not_matched_to_anything():
    moves = detect_moves(
        gone={"/media/weg.mp4": FakeEntry(size_mb=100.0)},
        arrived={"/media/ganz-anders.mp4": FakeEntry(size_mb=250.0)},
    )

    assert moves == {}


def test_nothing_is_matched_when_nothing_disappeared():
    assert detect_moves(gone={}, arrived={"/media/neu.mp4": FakeEntry()}) == {}


# --- Vorsicht bei Mehrdeutigkeit ---

def test_two_identical_files_are_left_alone():
    """
    Zwei Kopien derselben Datei haben denselben Fingerabdruck. Welche wohin
    gezogen ist, lässt sich nicht sagen — und geraten wird hier nicht.
    """
    moves = detect_moves(
        gone={"/media/a.mp4": FakeEntry(), "/media/b.mp4": FakeEntry()},
        arrived={"/media/x.mp4": FakeEntry(), "/media/y.mp4": FakeEntry()},
    )

    assert moves == {}


def test_one_gone_but_two_candidates_is_left_alone():
    moves = detect_moves(
        gone={"/media/a.mp4": FakeEntry()},
        arrived={"/media/x.mp4": FakeEntry(), "/media/y.mp4": FakeEntry()},
    )

    assert moves == {}


def test_the_unambiguous_pair_survives_next_to_an_ambiguous_one():
    """Ein zweifelhaftes Paar darf ein eindeutiges nicht mit verhindern."""
    moves = detect_moves(
        gone={
            "/media/doppelt-a.mp4": FakeEntry(size_mb=100.0),
            "/media/doppelt-b.mp4": FakeEntry(size_mb=100.0),
            "/media/eindeutig.mp4": FakeEntry(size_mb=42.0),
        },
        arrived={
            "/media/x.mp4": FakeEntry(size_mb=100.0),
            "/media/y.mp4": FakeEntry(size_mb=100.0),
            "/media/eindeutig-neu.mp4": FakeEntry(size_mb=42.0),
        },
    )

    assert moves == {"/media/eindeutig.mp4": "/media/eindeutig-neu.mp4"}


# --- Der Nutzerzustand zieht mit um ---

@pytest.fixture
def store(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.user_store.config", mock_config):
        from arcade_scanner.database.user_store import User, UserStore

        s = UserStore()
        for name in ("ralf", "gast"):
            salt = os.urandom(16)
            s.add_user(User(
                username=name,
                password_hash=binascii.hexlify(s.hash_password("x", salt)).decode(),
                salt=binascii.hexlify(salt).decode(),
                is_admin=False,
            ))
        yield s


def give(store, username, favorites=(), vaulted=(), tags=None):
    user = store.get_user(username)
    user.data.favorites = list(favorites)
    user.data.vaulted = list(vaulted)
    user.data.tags = dict(tags or {})
    store.add_user(user)


def test_a_favorite_follows_the_file(store):
    give(store, "ralf", favorites=["/media/alt.mp4", "/media/anderes.mp4"])

    store.remap_paths_in_user_data({"/media/alt.mp4": "/media/neu.mp4"})

    favoriten = store.get_user("ralf").data.favorites
    assert "/media/neu.mp4" in favoriten
    assert "/media/alt.mp4" not in favoriten
    assert "/media/anderes.mp4" in favoriten


def test_the_vault_mark_follows_the_file(store):
    """
    Die folgenreichste der drei: Bliebe sie liegen, wäre eine weggelegte Datei
    nach dem Umbenennen plötzlich wieder für alle sichtbar.
    """
    give(store, "ralf", vaulted=["/media/alt.mp4"])

    store.remap_paths_in_user_data({"/media/alt.mp4": "/media/neu.mp4"})

    assert store.get_user("ralf").data.vaulted == ["/media/neu.mp4"]


def test_tags_follow_the_file(store):
    give(store, "ralf", tags={"/media/alt.mp4": ["urlaub", "2019"]})

    store.remap_paths_in_user_data({"/media/alt.mp4": "/media/neu.mp4"})

    tags = store.get_user("ralf").data.tags
    assert tags == {"/media/neu.mp4": ["urlaub", "2019"]}


def test_every_user_is_remapped(store):
    """Der Umzug betrifft die Datei, nicht ein Konto."""
    give(store, "ralf", favorites=["/media/alt.mp4"])
    give(store, "gast", tags={"/media/alt.mp4": ["gesehen"]})

    store.remap_paths_in_user_data({"/media/alt.mp4": "/media/neu.mp4"})

    assert store.get_user("ralf").data.favorites == ["/media/neu.mp4"]
    assert store.get_user("gast").data.tags == {"/media/neu.mp4": ["gesehen"]}


def test_an_untouched_user_is_left_alone(store):
    give(store, "gast", favorites=["/media/eigenes.mp4"])

    store.remap_paths_in_user_data({"/media/alt.mp4": "/media/neu.mp4"})

    assert store.get_user("gast").data.favorites == ["/media/eigenes.mp4"]


def test_existing_state_on_the_new_path_is_kept(store):
    """
    Der Umzug ergänzt, er überschreibt nicht — sonst nähme ein Scan eine
    Entscheidung zurück, die der Nutzer inzwischen getroffen hat.
    """
    give(store, "ralf", tags={
        "/media/alt.mp4": ["urlaub"],
        "/media/neu.mp4": ["schon vergeben"],
    })

    store.remap_paths_in_user_data({"/media/alt.mp4": "/media/neu.mp4"})

    assert sorted(store.get_user("ralf").data.tags["/media/neu.mp4"]) == [
        "schon vergeben", "urlaub"]


def test_an_empty_mapping_writes_nothing(store):
    give(store, "ralf", favorites=["/media/alt.mp4"])

    assert store.remap_paths_in_user_data({}) == 0
    assert store.get_user("ralf").data.favorites == ["/media/alt.mp4"]


def test_a_path_mapped_to_itself_is_ignored(store):
    assert store.remap_paths_in_user_data({"/media/a.mp4": "/media/a.mp4"}) == 0


# --- Das Zusammenspiel im Scanner ---

@pytest.fixture
def scanner_umgebung(store):
    """`_apply_detected_moves` mit einer Attrappe der Medien-Datenbank."""
    from arcade_scanner.scanner import manager as manager_module

    neue_eintraege = {}
    geschrieben = []

    fake_db = MagicMock()
    fake_db.get.side_effect = lambda p: neue_eintraege.get(p)
    fake_db.upsert.side_effect = lambda e: geschrieben.append(e)

    with patch.object(manager_module, "db", fake_db), \
            patch("arcade_scanner.database.user_store.user_db", store):
        yield manager_module, neue_eintraege, geschrieben


def test_the_scanner_carries_the_state_over_before_deleting(scanner_umgebung, store):
    manager_module, neue, _ = scanner_umgebung
    give(store, "ralf", favorites=["/media/alt.mp4"],
         tags={"/media/alt.mp4": ["urlaub"]})

    alt = FakeEntry(imported_at=1600000000)
    neue["/media/neu.mp4"] = FakeEntry(imported_at=1800000000)

    moves = manager_module._apply_detected_moves(
        {"/media/alt.mp4": alt}, {"/media/alt.mp4"}, {"/media/neu.mp4"})

    assert moves == {"/media/alt.mp4": "/media/neu.mp4"}
    assert store.get_user("ralf").data.favorites == ["/media/neu.mp4"]
    assert store.get_user("ralf").data.tags == {"/media/neu.mp4": ["urlaub"]}


def test_the_import_date_moves_along(scanner_umgebung):
    """
    Sonst stünde jede umbenannte Datei in „zuletzt hinzugefügt" ganz oben,
    obwohl sich nur ihr Name geändert hat.
    """
    manager_module, neue, geschrieben = scanner_umgebung

    alt = FakeEntry(imported_at=1600000000)
    neue["/media/neu.mp4"] = FakeEntry(imported_at=1800000000)

    manager_module._apply_detected_moves(
        {"/media/alt.mp4": alt}, {"/media/alt.mp4"}, {"/media/neu.mp4"})

    assert [e.imported_at for e in geschrieben] == [1600000000]


def test_nothing_happens_without_orphans(scanner_umgebung):
    manager_module, neue, geschrieben = scanner_umgebung
    neue["/media/neu.mp4"] = FakeEntry()

    assert manager_module._apply_detected_moves({}, set(), {"/media/neu.mp4"}) == {}
    assert geschrieben == []


def test_a_failure_does_not_stop_the_scan(scanner_umgebung, store):
    """
    Das Aufräumen danach ist wichtiger als das Umtragen — und ein nicht
    umgetragener Eintrag ist genau der Zustand, den es vorher immer gab.
    """
    manager_module, neue, _ = scanner_umgebung
    neue["/media/neu.mp4"] = FakeEntry()

    with patch.object(store, "remap_paths_in_user_data",
                      side_effect=RuntimeError("Datenbank gesperrt")):
        moves = manager_module._apply_detected_moves(
            {"/media/alt.mp4": FakeEntry()}, {"/media/alt.mp4"}, {"/media/neu.mp4"})

    assert moves == {}


# --- Struktur ---

def test_the_scanner_remaps_before_it_removes():
    """
    Die Reihenfolge ist der ganze Trick: Nach `db.remove()` gibt es den alten
    Eintrag nicht mehr, und damit auch keinen Fingerabdruck.
    """
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "scanner"
              / "manager.py").read_text(encoding="utf-8")

    umzug = quelle.index("_apply_detected_moves(existing_entries")
    loeschen = quelle.index("db.remove(orphan)")

    assert umzug < loeschen
