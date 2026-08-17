"""
test_user_state_after_optimize.py
---------------------------------
Wer ein Video optimiert, verlor seine Tags.

Dieselbe Ursache wie beim Umbenennen (`test_moved_files.py`), nur an einer
Stelle, die man täglich benutzt: Beim Optimieren wird aus `film.mkv` die Datei
`film.mp4`. Die Zeile in `media` wird sorgfältig übertragen — Größe, Codec,
Aufnahmedatum, alles. Favoriten, Vault-Marke und Tags liegen aber nicht dort,
sondern in `users.db`, am **Pfad**. Und der ändert sich.

Für den Nutzer sieht es so aus: Dieselbe Datei, derselbe Name in der
Übersicht, nur ohne alles, was er daran gemacht hat. Kein Fehler, keine
Meldung.

Zwei Stellen tun dasselbe und hatten denselben Mangel:

    queue.py   `_replace_media_entry()` — der Fernarbeiter lädt die fertige
               Fassung hoch, sie ersetzt das Original
    files.py   `keep_optimized` im Standardmodus — der Nutzer behält die
               optimierte Fassung von Hand

Der Prüfmodus (`enable_review_mode`) ist nicht betroffen, und zwar durch
Zufall: Dort wandert das Original in einen `.review`-Ordner, während der
Nutzerzustand auf dem ursprünglichen Pfad liegen bleibt — und genau dorthin
kehrt die behaltene Fassung am Ende zurück. Das ist hier festgehalten, damit
es beim nächsten Umbau nicht unbemerkt kippt.
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
        salt = os.urandom(16)
        s.add_user(User(
            username="ralf",
            password_hash=binascii.hexlify(s.hash_password("x", salt)).decode(),
            salt=binascii.hexlify(salt).decode(),
            is_admin=True,
        ))
        yield s


def give(store, favorites=(), vaulted=(), tags=None):
    user = store.get_user("ralf")
    user.data.favorites = list(favorites)
    user.data.vaulted = list(vaulted)
    user.data.tags = dict(tags or {})
    store.add_user(user)


# --- Der Fernarbeiter lädt die fertige Fassung hoch ---

@pytest.fixture
def replace_umgebung(store, tmp_path):
    from arcade_scanner.server.routes import queue as queue_route

    neu = tmp_path / "film.mp4"
    neu.write_bytes(b"x" * 2048)

    eintrag = MagicMock()
    eintrag.model_dump.return_value = {
        "FilePath": "/media/film.mkv",
        "Size_MB": 100.0,
        "Bitrate_Mbps": 12.0,
        "Status": "HIGH",
        "imported_at": 1600000000,
    }

    fake_db = MagicMock()
    fake_db.get.return_value = eintrag

    with patch.object(queue_route, "db", fake_db), \
            patch("arcade_scanner.database.user_store.user_db", store):
        yield queue_route, str(neu)


def test_a_favorite_survives_the_optimization(replace_umgebung, store):
    queue_route, neu = replace_umgebung
    give(store, favorites=["/media/film.mkv"])

    queue_route._replace_media_entry("/media/film.mkv", neu, "hevc")

    assert store.get_user("ralf").data.favorites == [neu]


def test_tags_survive_the_optimization(replace_umgebung, store):
    queue_route, neu = replace_umgebung
    give(store, tags={"/media/film.mkv": ["urlaub", "4k"]})

    queue_route._replace_media_entry("/media/film.mkv", neu, "hevc")

    assert store.get_user("ralf").data.tags == {neu: ["urlaub", "4k"]}


def test_the_vault_mark_survives_the_optimization(replace_umgebung, store):
    """
    Die folgenreichste: Ginge sie verloren, wäre eine weggelegte Datei nach
    dem Optimieren für alle sichtbar — ohne dass irgendwo steht, warum.
    """
    queue_route, neu = replace_umgebung
    give(store, vaulted=["/media/film.mkv"])

    assert store.get_user("ralf").data.vaulted == ["/media/film.mkv"]
    queue_route._replace_media_entry("/media/film.mkv", neu, "hevc")

    assert store.get_user("ralf").data.vaulted == [neu]


def test_an_unchanged_path_writes_nothing(replace_umgebung, store):
    """
    Bleibt der Name gleich (`.mp4` war schon `.mp4`), gibt es nichts
    umzutragen — und die Benutzerdatenbank wird nicht angefasst.
    """
    queue_route, neu = replace_umgebung
    give(store, favorites=[neu])

    with patch.object(store, "remap_paths_in_user_data") as remap:
        queue_route._replace_media_entry(neu, neu, "hevc")

    remap.assert_not_called()


def test_a_failure_does_not_break_the_upload(replace_umgebung, store):
    """
    Der Job ist an dieser Stelle fertig und die Datei ersetzt. Eine Ausnahme
    beim Umtragen darf daraus keinen Fehlschlag machen.
    """
    queue_route, neu = replace_umgebung
    give(store, favorites=["/media/film.mkv"])

    with patch.object(store, "remap_paths_in_user_data",
                      side_effect=RuntimeError("Datenbank gesperrt")):
        queue_route._replace_media_entry("/media/film.mkv", neu, "hevc")
    # Kein Fehler nach oben.


# --- Struktur: beide Stellen tun dasselbe ---

def test_both_replacement_paths_carry_the_state_over():
    """
    Zwei Stellen ersetzen eine Datei durch ihre optimierte Fassung. Eine von
    beiden zu vergessen hieße, dass der Verlust vom gewählten Weg abhängt.
    """
    from pathlib import Path

    root = Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes"

    for name in ("queue.py", "files.py"):
        quelle = (root / name).read_text(encoding="utf-8")
        assert "remap_paths_in_user_data" in quelle, name


def test_the_review_mode_needs_no_remap():
    """
    Festgehalten, warum dort nichts steht: Im Prüfmodus wandert das Original
    in einen `.review`-Ordner, der Nutzerzustand bleibt auf dem ursprünglichen
    Pfad — und genau dorthin kehrt die behaltene Fassung zurück
    (`final_dest = entry_orig.original_path`).
    """
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "server"
              / "routes" / "files.py").read_text(encoding="utf-8")

    assert "final_dest = entry_orig.original_path" in quelle
