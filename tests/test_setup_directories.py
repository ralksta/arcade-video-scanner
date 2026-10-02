"""
test_setup_directories.py
-------------------------
``/api/setup/directories`` summierte Größe und Dateizahl jedes Ordners unter
``/media`` per ``os.walk`` — **zweimal** (einmal für die Größe, einmal für die
Zahl), bei jedem Aufruf, für jeden angemeldeten Nutzer, ohne Obergrenze.
Gemessen auf dieser Installation: 711.512 Dateien, 19 s allein fürs Auflisten,
über 30 s für die Antwort. Der Einrichtungs-Assistent wartet so lange.

Dazu verschluckte ein einziges ``getsize``, das scheiterte (Datei während des
Laufs verschwunden — der Optimierer legt ``.part``-Dateien an und entfernt sie
wieder), den **ganzen** Ordner: Er fehlte kommentarlos in der Liste.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import settings as settings_routes


@pytest.fixture
def media(tmp_path):
    root = tmp_path / "media"
    (root / "filme").mkdir(parents=True)
    (root / "filme" / "a.mp4").write_bytes(b"x" * 10)
    (root / "filme" / "sub").mkdir()
    (root / "filme" / "sub" / "b.mp4").write_bytes(b"x" * 20)
    (root / "fotos").mkdir()
    (root / "fotos" / "c.jpg").write_bytes(b"x" * 5)
    return root


def _call(media_root):
    handler = MagicMock()
    handler.get_current_user.return_value = "alice"
    sent = {}
    with patch.object(settings_routes, "SETUP_MEDIA_ROOT", str(media_root)), \
         patch.object(settings_routes, "send_json",
                      side_effect=lambda _h, payload, **kw: sent.update(payload)):
        settings_routes.handle_get_setup_directories(handler)
    return {d["path"]: d for d in sent["directories"]}


def test_sizes_and_counts_are_reported(media):
    dirs = _call(media)
    assert dirs[str(media / "filme")]["size_bytes"] == 30
    assert dirs[str(media / "filme")]["file_count"] == 2
    assert dirs[str(media / "fotos")]["file_count"] == 1


def test_a_vanished_file_does_not_drop_the_whole_directory(media):
    vanished = str(media / "filme" / "sub" / "b.mp4")
    real_getsize = os.path.getsize
    real_lstat = os.lstat

    def flaky_getsize(path):
        if os.fspath(path) == vanished:
            raise FileNotFoundError(path)
        return real_getsize(path)

    def flaky_lstat(path, *a, **kw):
        if os.fspath(path) == vanished:
            raise FileNotFoundError(path)
        return real_lstat(path, *a, **kw)

    with patch("os.path.getsize", flaky_getsize), patch("os.lstat", flaky_lstat):
        dirs = _call(media)

    assert str(media / "filme") in dirs, "Ordner verschwand wegen einer einzigen Datei"
    assert dirs[str(media / "filme")]["size_bytes"] == 10


def test_each_directory_is_walked_once(media):
    real_walk = os.walk
    walked = []

    def counting_walk(top, *a, **kw):
        walked.append(os.fspath(top))
        return real_walk(top, *a, **kw)

    with patch("os.walk", counting_walk):
        _call(media)

    assert sorted(walked) == sorted({str(media / "filme"), str(media / "fotos")}), walked


def test_a_huge_tree_stops_at_the_budget_and_says_so(media):
    """Nach Ablauf des Zeitbudgets: Zahlen als Untergrenze, nicht weiterlaufen."""
    with patch.object(settings_routes, "SETUP_SCAN_BUDGET_SEC", 0.0):
        dirs = _call(media)

    entry = dirs[str(media / "filme")]
    assert entry["complete"] is False
    assert entry["file_count"] <= 2
