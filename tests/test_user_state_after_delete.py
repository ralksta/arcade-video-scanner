"""
test_user_state_after_delete.py
-------------------------------
Was passiert mit Favoriten, Tags und Vault-Marken, wenn eine Datei gelöscht
wird?

Bisher: nichts. `db.remove()` löscht die Zeile in `media`, der Nutzerzustand
hängt aber am **Pfad** und lebt in `UserVideoData` weiter — für immer.

Zwei Folgen, und die zweite ist die unangenehme:

1. Die Listen wachsen mit jeder gelöschten Datei. In dieser Installation
   standen zum Zeitpunkt des Fundes bereits **12 Tag-Einträge**, zwei
   Favoriten und eine Vault-Marke auf Pfaden, die es nicht mehr gibt.

2. Entsteht später **dieselbe Pfadangabe erneut**, erbt die neue Datei
   stillschweigend den alten Zustand. Und sie entsteht regelmäßig neu: Beim
   Optimieren wird aus ``film.mkv`` wieder ``film.mp4`` — genau der Name, den
   die gelöschte Datei trug. Ein Video, das einmal als „vaulted" markiert war,
   ist nach dem Neuanlegen sofort wieder versteckt, und nirgends steht, warum.
   Das ist kein Datenverlust, aber es ist unerklärlich, und unerklärlich ist
   bei einer Sichtbarkeits-Einstellung schlimm genug.

Aufgeräumt wird jetzt bei **ausdrücklichen** Löschungen über die
Duplikat-Routen. Bewusst **nicht** beim Aufräumen verwaister Einträge nach
einem Scan: Der Code dort warnt selbst, dass diese Angaben „no rescan can
restore" — ein Scan, der sich irrt (nicht eingehängtes Laufwerk, abgebrochene
Suche), würde sie sonst mitnehmen. Die Schutzbedingungen dort sind gut, aber
sie sind eine Vermutung über die Wirklichkeit; eine ausdrückliche Löschung ist
keine.
"""
import binascii
import os
from unittest.mock import MagicMock, patch

import pytest


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
    return user


# --- Der Fund ---

def test_a_deleted_path_leaves_no_favorite_behind(store):
    give(store, "ralf", favorites=["/media/weg.mp4", "/media/bleibt.mp4"])

    store.purge_paths_from_user_data(["/media/weg.mp4"])

    assert store.get_user("ralf").data.favorites == ["/media/bleibt.mp4"]


def test_a_deleted_path_leaves_no_vault_mark_behind(store):
    """
    Die folgenreichste der drei: Eine liegengebliebene Vault-Marke versteckt
    eine später neu angelegte Datei desselben Namens, ohne erkennbaren Grund.
    """
    give(store, "ralf", vaulted=["/media/weg.mp4"])

    store.purge_paths_from_user_data(["/media/weg.mp4"])

    assert store.get_user("ralf").data.vaulted == []


def test_a_deleted_path_leaves_no_tags_behind(store):
    give(store, "ralf", tags={"/media/weg.mp4": ["urlaub"], "/media/bleibt.mp4": ["2024"]})

    store.purge_paths_from_user_data(["/media/weg.mp4"])

    assert store.get_user("ralf").data.tags == {"/media/bleibt.mp4": ["2024"]}


def test_the_state_of_every_user_is_cleaned(store):
    """
    Der Pfad kann in mehreren Konten stehen. Bliebe er bei einem liegen, würde
    ausgerechnet dort wieder geerbt.
    """
    give(store, "ralf", favorites=["/media/weg.mp4"])
    give(store, "gast", vaulted=["/media/weg.mp4"], tags={"/media/weg.mp4": ["x"]})

    removed = store.purge_paths_from_user_data(["/media/weg.mp4"])

    assert removed == 3
    assert store.get_user("ralf").data.favorites == []
    assert store.get_user("gast").data.vaulted == []
    assert store.get_user("gast").data.tags == {}


def test_a_new_file_at_the_same_path_starts_clean(store):
    """
    Der Ablauf, um den es geht: `film.mkv` wird optimiert, das Ergebnis heisst
    `film.mp4`, die alte `film.mp4` daneben wurde vorher als Duplikat gelöscht.
    Ohne das Aufräumen wäre die neue Datei sofort versteckt.
    """
    give(store, "ralf", vaulted=["/media/film.mp4"], tags={"/media/film.mp4": ["alt"]})

    store.purge_paths_from_user_data(["/media/film.mp4"])

    user = store.get_user("ralf")
    assert "/media/film.mp4" not in user.data.vaulted
    assert "/media/film.mp4" not in user.data.tags


# --- Nichts darüber hinaus anfassen ---

def test_untouched_paths_survive(store):
    give(store, "ralf",
         favorites=["/media/a.mp4"], vaulted=["/media/b.mp4"],
         tags={"/media/c.mp4": ["t"]})

    assert store.purge_paths_from_user_data(["/media/ganz_anders.mp4"]) == 0

    user = store.get_user("ralf")
    assert user.data.favorites == ["/media/a.mp4"]
    assert user.data.vaulted == ["/media/b.mp4"]
    assert user.data.tags == {"/media/c.mp4": ["t"]}


def test_an_empty_list_changes_nothing(store):
    give(store, "ralf", favorites=["/media/a.mp4"])

    assert store.purge_paths_from_user_data([]) == 0
    assert store.get_user("ralf").data.favorites == ["/media/a.mp4"]


def test_empty_strings_are_ignored(store):
    """Sonst könnte ein leerer Eintrag versehentlich alles treffen."""
    give(store, "ralf", favorites=["/media/a.mp4", ""])

    store.purge_paths_from_user_data(["", None])

    assert "/media/a.mp4" in store.get_user("ralf").data.favorites


def test_several_paths_at_once(store):
    give(store, "ralf", favorites=["/a.mp4", "/b.mp4", "/c.mp4"])

    removed = store.purge_paths_from_user_data(["/a.mp4", "/c.mp4"])

    assert removed == 2
    assert store.get_user("ralf").data.favorites == ["/b.mp4"]


# --- Wo es aufgerufen wird, und wo bewusst nicht ---

def test_both_deleting_routes_clean_up():
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "duplicates.py"
    ).read_text(encoding="utf-8")

    for route in ("/api/duplicates/delete", "/api/bulk_delete"):
        block = source.split(f'if path == "{route}":', 1)[1].split("send_response(200)", 1)[0]
        assert "_purge_user_state(deleted)" in block, f"{route} räumt nicht auf"


def test_the_scan_orphan_cleanup_deliberately_does_not():
    """
    Festgehalten als Entscheidung, nicht als Versehen: Der Scanner räumt
    verwaiste Zeilen auf, wenn Dateien verschwunden sind — und irrt sich dabei
    unter Umständen (nicht eingehängtes Laufwerk, abgebrochene Suche). Die
    Schutzbedingungen dort sind gut, aber sie sind eine Vermutung über die
    Wirklichkeit. Nutzerzustand daran zu hängen wäre eine Wette.
    """
    from pathlib import Path

    manager = (
        Path(__file__).parent.parent / "arcade_scanner" / "scanner" / "manager.py"
    ).read_text(encoding="utf-8")

    assert "purge_paths_from_user_data" not in manager, (
        "Das Aufräumen hängt jetzt am Scan — dann bitte auch die Begründung "
        "hier anpassen, statt den Test zu löschen"
    )


# --- Die Buchführung des Auto-Taggers muss mitgehen ---
#
# Der Auto-Tagger vergibt jeden Tag nur einmal je (Nutzer, Regel, Pfad) -- damit
# ein von Hand entfernter Tag entfernt bleibt. Diese Buchführung hängt am Pfad
# und wird von `db.remove()` nicht angefasst.
#
# Solange auch die Tags selbst liegen blieben, war das stimmig: Datei weg, Tag
# noch da, Regel greift nicht mehr. Mit dem Aufräumen weiter oben fielen beide
# auseinander -- die Tags verschwinden, der Vermerk bleibt. Entsteht später eine
# Datei unter demselben Pfad, hätte sie keinen Tag und bekäme auch keinen mehr.
#
# Das ist ein Fehler, den das Aufräumen selbst erzeugt hat. Deshalb gehören die
# beiden Schritte zusammen, und deshalb steht der Test hier und nicht woanders.

@pytest.fixture
def media(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.sqlite_store.config", mock_config):
        from arcade_scanner.database.sqlite_store import SQLiteStore

        s = SQLiteStore()
        s._ensure_connection()
        yield s


def test_the_auto_tag_record_is_forgotten_for_a_deleted_path(media):
    media.mark_auto_tag_applied("ralf", "regel-1", ["/media/weg.mp4", "/media/bleibt.mp4"])

    media.forget_auto_tag_paths(["/media/weg.mp4"])

    assert media.get_auto_tag_applied("ralf", "regel-1") == {"/media/bleibt.mp4"}


def test_a_rule_can_tag_a_recreated_path_again(media):
    """
    Der Ablauf, um den es geht: Datei gelöscht, später entsteht unter demselben
    Pfad eine neue. Ohne das Vergessen bliebe sie für immer ungetaggt.
    """
    media.mark_auto_tag_applied("ralf", "regel-1", ["/media/film.mp4"])
    assert "/media/film.mp4" in media.get_auto_tag_applied("ralf", "regel-1")

    media.forget_auto_tag_paths(["/media/film.mp4"])

    assert "/media/film.mp4" not in media.get_auto_tag_applied("ralf", "regel-1")


def test_every_user_and_rule_forgets_the_path(media):
    """Der Pfad kann in mehreren Regeln und Konten vermerkt sein."""
    media.mark_auto_tag_applied("ralf", "regel-1", ["/media/weg.mp4"])
    media.mark_auto_tag_applied("ralf", "regel-2", ["/media/weg.mp4"])
    media.mark_auto_tag_applied("gast", "regel-1", ["/media/weg.mp4"])

    media.forget_auto_tag_paths(["/media/weg.mp4"])

    assert media.get_auto_tag_applied("ralf", "regel-1") == set()
    assert media.get_auto_tag_applied("ralf", "regel-2") == set()
    assert media.get_auto_tag_applied("gast", "regel-1") == set()


def test_forgetting_nothing_is_harmless(media):
    media.mark_auto_tag_applied("ralf", "regel-1", ["/media/a.mp4"])

    assert media.forget_auto_tag_paths([]) == 0
    assert media.forget_auto_tag_paths(["", None]) == 0
    assert media.get_auto_tag_applied("ralf", "regel-1") == {"/media/a.mp4"}


def test_the_delete_routes_do_both_steps():
    """
    Die eine Hälfte ohne die andere ist schlechter als keine von beiden --
    deshalb wird hier geprüft, dass beide Aufrufe beieinander stehen.
    """
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "duplicates.py"
    ).read_text(encoding="utf-8")
    block = source.split("def _purge_user_state", 1)[1].split("\ndef ", 1)[0]

    assert "purge_paths_from_user_data" in block
    assert "forget_auto_tag_paths" in block, (
        "Tags werden aufgeräumt, der Auto-Tag-Vermerk nicht — die Datei bliebe "
        "danach dauerhaft ungetaggt"
    )
