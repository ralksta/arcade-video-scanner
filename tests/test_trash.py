"""Tests für den Papierkorb (core/trash.py).

Der Papierkorb ist die einzige Rückholmöglichkeit für ausdrücklich gelöschte
Medien. Getestet wird deshalb nicht nur der Normalfall, sondern auch das, was
sonst Daten kostet: ein belegter Zielpfad, eine fehlende Datei im Korb, eine
Ablauffrist und der Rückfall auf den zentralen Korb außerhalb der Scan-Ziele.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from arcade_scanner.core import trash


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    return root


@pytest.fixture
def index(tmp_path):
    return tmp_path / "trash_index.json"


@pytest.fixture
def fallback(tmp_path):
    return tmp_path / "central-trash"


def _make_file(root, name="clip.mp4", content=b"video-bytes"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _move(path, root, index, fallback, **kwargs):
    return trash.move_to_trash(
        str(path),
        deleted_by="ralf",
        roots=[str(root)],
        index_path=str(index),
        fallback_dir=str(fallback),
        **kwargs,
    )


def test_move_lands_in_trash_inside_the_scan_root(library, index, fallback):
    path = _make_file(library)

    entry = _move(path, library, index, fallback)

    assert not path.exists()
    assert entry["trash_path"].startswith(str(library / ".arcade-trash"))
    assert os.path.exists(entry["trash_path"])
    assert entry["original_path"] == str(path)
    assert entry["deleted_by"] == "ralf"
    assert entry["size"] == len(b"video-bytes")


def test_restore_returns_file_and_removes_entry(library, index, fallback):
    path = _make_file(library, "urlaub.mp4", b"original")
    entry = _move(path, library, index, fallback)

    trash.restore(entry["id"], index_path=str(index))

    assert path.read_bytes() == b"original"
    assert not os.path.exists(entry["trash_path"])
    assert trash.list_entries(index_path=str(index)) == []


def test_restore_never_overwrites_a_new_file(library, index, fallback):
    path = _make_file(library, "clip.mp4", b"old")
    entry = _move(path, library, index, fallback)
    path.write_bytes(b"new")

    with pytest.raises(FileExistsError):
        trash.restore(entry["id"], index_path=str(index))

    assert path.read_bytes() == b"new"
    assert os.path.exists(entry["trash_path"])
    assert len(trash.list_entries(index_path=str(index))) == 1


def test_restore_reports_a_missing_trash_file(library, index, fallback):
    path = _make_file(library)
    entry = _move(path, library, index, fallback)
    os.remove(entry["trash_path"])

    with pytest.raises(FileNotFoundError):
        trash.restore(entry["id"], index_path=str(index))


def test_files_outside_all_roots_use_the_central_trash(tmp_path, library, index, fallback):
    outside = tmp_path / "other-volume"
    outside.mkdir()
    path = _make_file(outside)

    entry = _move(path, library, index, fallback)

    assert entry["trash_path"].startswith(str(fallback))
    assert not path.exists()


def test_entries_are_listed_with_display_fields(library, index, fallback):
    path = _make_file(library, "unterordner/clip.mp4")
    _move(path, library, index, fallback)

    entries = trash.list_entries(index_path=str(index))

    assert len(entries) == 1
    assert entries[0]["name"] == "clip.mp4"
    assert entries[0]["folder"] == str(library / "unterordner")
    assert 0 <= entries[0]["days_left"] <= trash.TRASH_RETENTION_DAYS


def test_purge_expired_removes_old_entries_only(library, index, fallback):
    old_path = _make_file(library, "alt.mp4")
    new_path = _make_file(library, "neu.mp4")
    old_entry = _move(old_path, library, index, fallback)
    _move(new_path, library, index, fallback)

    data = json.loads(index.read_text(encoding="utf-8"))
    data["entries"][old_entry["id"]]["deleted_at"] = (
        datetime.now(timezone.utc) - timedelta(days=trash.TRASH_RETENTION_DAYS + 1)
    ).isoformat()
    index.write_text(json.dumps(data), encoding="utf-8")

    purged = []
    result = trash.purge_expired(
        index_path=str(index), on_purge=lambda paths: purged.extend(paths)
    )

    assert result["purged"] == 1
    assert not os.path.exists(old_entry["trash_path"])
    assert not old_path.exists()
    assert not new_path.exists()  # liegt weiterhin im Korb
    remaining = trash.list_entries(index_path=str(index))
    assert [e["original_path"] for e in remaining] == [str(new_path)]
    assert purged == [str(old_path)]


def test_fresh_entries_survive_the_retention_check(library, index, fallback):
    path = _make_file(library)
    entry = _move(path, library, index, fallback)

    result = trash.purge_expired(index_path=str(index))

    assert result["purged"] == 0
    assert os.path.exists(entry["trash_path"])


def test_empty_removes_everything_and_cleans_up(library, index, fallback):
    first = _make_file(library, "a.mp4")
    second = _make_file(library, "b.mp4")
    first_entry = _move(first, library, index, fallback)
    second_entry = _move(second, library, index, fallback)

    purged = []
    result = trash.empty(index_path=str(index), on_purge=lambda paths: purged.extend(paths))

    assert result["purged"] == 2
    assert not os.path.exists(first_entry["trash_path"])
    assert not os.path.exists(second_entry["trash_path"])
    assert trash.list_entries(index_path=str(index)) == []
    assert set(purged) == {str(first), str(second)}


def test_scope_check_works_for_a_file_that_no_longer_exists(tmp_path):
    """Der Kern des Papierkorbs: Der Originalpfad ist nach dem Löschen leer.

    `is_path_allowed()` verlangt Existenz und hätte einem normalen Konto den
    eigenen Papierkorb leer gezeigt.
    """
    from arcade_scanner.server.routes.trash import _path_in_scope

    root = tmp_path / "media"
    root.mkdir()
    missing = str(root / "geloescht.mp4")

    assert _path_in_scope(missing, [str(root)])
    assert not _path_in_scope(str(tmp_path / "media2" / "x.mp4"), [str(root)])
    assert _path_in_scope(missing, None)  # Admin


def test_missing_source_does_not_leave_a_ghost_entry(library, index, fallback):
    path = library / "weg.mp4"

    with pytest.raises(FileNotFoundError):
        _move(path, library, index, fallback)

    assert trash.list_entries(index_path=str(index)) == []
