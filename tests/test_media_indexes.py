"""
test_media_indexes.py
---------------------
Welche Indizes die ``media``-Tabelle trägt — und warum genau diese.

Die Tabelle hatte acht Indizes, angelegt für „common filter/sort queries".
Gefiltert und sortiert wird aber im Frontend: der Server liefert über
``/api/videos`` alle Zeilen aus, und kein SQL im Projekt verwendet ``status``,
``codec``, ``size_mb``, ``favorite`` oder ``vaulted`` in einem WHERE oder
ORDER BY. Fünf Indizes wurden also bei jedem Upsert gepflegt und von keinem
Query-Plan je benutzt (an der realen Bibliothek gemessen: 2000 Upserts 47 ms
statt 16 ms, Datei 5,58 MB statt 3,48 MB).

Diese Tests halten beide Richtungen fest: die drei nötigen Indizes müssen da
sein *und* von den jeweiligen Abfragen benutzt werden, die fünf entfernten
dürfen nicht zurückkommen, ohne dass eine Abfrage sie rechtfertigt.
"""
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.database.sqlite_store import SQLiteStore

REQUIRED = {
    "idx_mtime": "ORDER BY mtime DESC LIMIT/OFFSET (get_page)",
    "idx_media_type": "DELETE FROM media WHERE media_type = 'image'",
    "idx_thumb": "SELECT * FROM media WHERE thumb = ?",
}

REMOVED = ["idx_status", "idx_codec", "idx_size_mb", "idx_favorite", "idx_vaulted"]


def _store_in(directory) -> SQLiteStore:
    """SQLiteStore auf einem temporären Datenverzeichnis.

    Der Pfad kommt aus config.hidden_data_dir, nicht aus dem Konstruktor —
    gleiches Muster wie in test_sqlite_store.py.
    """
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(directory)
    with patch("arcade_scanner.database.sqlite_store.config", mock_config):
        store = SQLiteStore()
        store._ensure_connection()
    return store


@pytest.fixture
def store(tmp_path):
    return _store_in(tmp_path)


def _indexes_of(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='index' AND tbl_name='media' AND sql IS NOT NULL"
    )
    return {r[0] for r in rows}


def _indexes(store) -> set[str]:
    rows = store._conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='index' AND tbl_name='media' AND sql IS NOT NULL"
    )
    return {r[0] for r in rows}


@pytest.mark.parametrize("name", sorted(REQUIRED))
def test_required_index_exists(store, name):
    assert name in _indexes(store), f"{name} fehlt — gebraucht für: {REQUIRED[name]}"


def test_no_unused_indexes_on_a_fresh_database(store):
    leftover = _indexes(store) & set(REMOVED)
    assert not leftover, (
        f"Ungenutzte Indizes wieder angelegt: {sorted(leftover)}. "
        "Ein Index gehört nur dann hierher, wenn eine Abfrage ihn auch benutzt."
    )


def test_existing_databases_are_migrated(tmp_path):
    """
    Bestehende Installationen haben die fünf Indizes noch. Ohne den
    DROP-Schritt bliebe der Schreib-Overhead dort für immer bestehen.
    """
    # Erst ein normales Schema anlegen, dann den Altzustand herstellen: die
    # fünf Indizes von Hand ergänzen, so wie eine bestehende Installation sie
    # mitbringt.
    _store_in(tmp_path)._conn.close()

    legacy = sqlite3.connect(tmp_path / "media_library.db")
    for name, column in (
        ("idx_status", "status"), ("idx_codec", "codec"), ("idx_size_mb", "size_mb"),
        ("idx_favorite", "favorite"), ("idx_vaulted", "vaulted"),
    ):
        legacy.execute(f"CREATE INDEX IF NOT EXISTS {name} ON media({column})")
    legacy.commit()
    assert _indexes_of(legacy) >= set(REMOVED), "Altzustand nicht hergestellt"
    legacy.close()

    store = _store_in(tmp_path)

    leftover = _indexes(store) & set(REMOVED)
    assert not leftover, f"Nach dem Öffnen noch vorhanden: {sorted(leftover)}"


@pytest.mark.parametrize("query,expected_index", [
    ("SELECT * FROM media WHERE thumb = 'x.jpg'", "idx_thumb"),
    ("SELECT * FROM media ORDER BY mtime DESC LIMIT 40", "idx_mtime"),
    ("DELETE FROM media WHERE media_type = 'image'", "idx_media_type"),
])
def test_query_plan_actually_uses_the_index(store, query, expected_index):
    """
    Gegenprobe: Ein Index, den der Planer nicht anfasst, ist nur Schreiblast.
    Genau so sind die fünf entfernten entstanden.
    """
    plan = " ".join(str(row[3]) for row in store._conn.execute("EXPLAIN QUERY PLAN " + query))
    assert expected_index in plan, f"Planer nutzt {expected_index} nicht: {plan}"


def test_file_path_lookup_needs_no_extra_index(store):
    """file_path ist PRIMARY KEY — SQLite legt dafür selbst einen Index an."""
    plan = " ".join(
        str(row[3])
        for row in store._conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM media WHERE file_path = '/x'"
        )
    )
    assert "sqlite_autoindex_media_1" in plan or "USING INDEX" in plan
    assert "SCAN media" not in plan, "Einzelabfrage über file_path läuft als Full Scan"


def test_removed_indexes_are_documented_in_the_schema(store):
    """
    Der nächste Mensch soll sehen, dass die Indizes bewusst fehlen — sonst
    legt er sie „zur Sicherheit" wieder an.
    """
    import inspect

    source = inspect.getsource(SQLiteStore._create_table)
    for name in REMOVED:
        assert name in source, f"{name} wird entfernt, aber nirgends begründet"
