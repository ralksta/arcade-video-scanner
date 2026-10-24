"""
test_candidates_scope.py
------------------------
`GET /api/candidates` schlägt vor, welche Dateien sich zu optimieren lohnen.
Aus dieser Liste heraus wird eingereiht — und Einreihen heißt, dass die Datei
am Ende **ersetzt** wird.

Dieselben zwei Lücken wie in `/api/similar`, in derselben Form:

**1. Kein Kontobezug.** `db.get_all()` liefert die gesamte Bibliothek.
Ausgeschlossen wurden nur die Vault-Pfade und die bereits eingereihten Dateien.
Ein Zweitkonto bekam also Vorschläge zu Dateien aus den Scan-Zielen anderer
Konten — mit Pfad, Größe und Vorschaubild — und konnte sie einreihen.

Bei `/api/similar` war das eine Preisgabe. Hier ist es mehr: Die Datei eines
anderen Kontos wird dabei neu kodiert und ersetzt.

**2. Fällt der Nutzerdatensatz aus, entfiel die Vault-Filterung.**

    u = user_db.get_user(user_name)
    if u and u.data.vaulted:
        exclude.update(...)

`u is None` hieß „nichts ausschließen" — Vault-Dateien standen dann als
Optimierungs-Vorschlag da.

Die Regel, wer welche Pfade sehen darf, steht seit diesem Umbau in
`core/user_scope.py` und wird von beiden Routen gefragt, statt an jeder Stelle
neu beantwortet zu werden. Sie stammt aus `/api/videos`, ist also keine neue
Erfindung.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.core.user_scope import visible_path_filter
from arcade_scanner.server.routes import candidates


class FakeHandler:
    def __init__(self, path="/api/candidates?codec=hevc"):
        self.path = path
        self.error = None

    def get_current_user(self):
        return "privat"

    def send_response(self, code):
        pass

    def send_error(self, code, message=""):
        self.error = code

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass


def entry(path, bitrate=20.0, height=1080, codec="h264"):
    e = MagicMock()
    e.file_path = path
    e.bitrate_mbps = bitrate
    e.height = height
    e.width = 1920
    e.codec = codec
    e.size_mb = 2000.0
    e.thumb = ""
    e.frame_rate = 30.0
    e.status = "OK"
    e.media_type = "video"
    # Ohne diese Zeile liefert das MagicMock für `optimized_at` etwas Wahres,
    # und `build_candidates()` überspringt jeden Eintrag als „schon optimiert".
    # Beim ersten Versuch kamen deshalb gar keine Vorschläge zurück — was wie
    # ein Fehler der Filterung aussah und keiner war.
    e.optimized_at = 0
    return e


LIBRARY = [
    entry("/media_ralf/eigenes.mp4"),
    entry("/media_ralf/privat.mp4"),
    entry("/media/fremdes.mp4"),
    entry("/media_nas/auch_fremd.mp4"),
]


def make_user(targets, vaulted=(), is_admin=False):
    u = MagicMock()
    u.is_admin = is_admin
    u.data.scan_targets = list(targets)
    u.data.vaulted = list(vaulted)
    return u


def ask(user, queued=()):
    handler = FakeHandler()
    media_db = MagicMock()
    media_db.get_all.return_value = list(LIBRARY)
    media_db.get_active_queue_paths.return_value = set(queued)
    user_db = MagicMock()
    user_db.get_user.return_value = user

    sent = {}

    def capture(_h, payload):
        sent.update(payload)

    with patch.object(candidates, "_get_deps", return_value=(media_db, user_db)), \
         patch.object(candidates, "send_json", capture):
        candidates.handle_get(handler)

    paths = [c["file_path"] for c in sent.get("results", [])]
    return handler, paths


# --- 1. Kontobezug ---

def test_suggestions_stay_inside_the_users_own_targets():
    """
    Der Fund: Vorher standen `/media/fremdes.mp4` und `/media_nas/auch_fremd.mp4`
    als Vorschlag da — und liessen sich von dort aus einreihen.
    """
    _handler, paths = ask(make_user(["/media_ralf"]))

    assert paths, "Die eigenen Vorschläge fehlen jetzt auch"
    assert all(p.startswith("/media_ralf/") for p in paths), paths


def test_a_sibling_directory_with_a_shared_prefix_is_outside():
    _handler, paths = ask(make_user(["/media"]))

    assert not any(p.startswith("/media_ralf") or p.startswith("/media_nas")
                   for p in paths), paths


def test_vaulted_files_are_not_suggested():
    _handler, paths = ask(
        make_user(["/media_ralf"], vaulted=["/media_ralf/privat.mp4"]))

    assert "/media_ralf/privat.mp4" not in paths


def test_already_queued_files_are_not_suggested():
    """Verhalten, das schon vorher stimmte — es darf beim Umbau nicht wegfallen."""
    _handler, paths = ask(
        make_user(["/media_ralf"]), queued=["/media_ralf/eigenes.mp4"])

    assert "/media_ralf/eigenes.mp4" not in paths


# --- 2. Wenn der Nutzer nicht lesbar ist ---

def test_an_unreadable_user_gets_nothing():
    handler, paths = ask(None)

    assert handler.error == 503
    assert paths == []


# --- Nutzer ohne eingerichtete Ziele ---

def test_an_admin_without_targets_sees_everything():
    _handler, paths = ask(make_user([], is_admin=True))

    assert len(paths) == len(LIBRARY)


def test_a_normal_user_without_targets_sees_nothing():
    _handler, paths = ask(make_user([], is_admin=False))

    assert paths == []


# --- Der gemeinsame Helfer ---

@pytest.mark.parametrize("targets,is_admin,path,expected", [
    (["/media_ralf"], False, "/media_ralf/x.mp4", True),
    (["/media_ralf"], False, "/media/x.mp4", False),
    (["/media"], False, "/media_nas/x.mp4", False),
    (["/media"], False, "/media_ralf/x.mp4", False),
    ([], True, "/irgendwo/x.mp4", True),
    ([], False, "/irgendwo/x.mp4", False),
])
def test_the_shared_rule(targets, is_admin, path, expected):
    user = make_user(targets, is_admin=is_admin)

    assert visible_path_filter(user)(os.path.abspath(path)) is expected


def test_no_user_means_no_paths():
    """
    Der wichtigste Einzelfall: Ist der Datensatz nicht lesbar, ist weder
    bekannt, was im Vault liegt, noch welche Verzeichnisse dem Konto gehören.
    Beides fiele sonst in die offene Richtung aus.
    """
    assert visible_path_filter(None)("/media/x.mp4") is False
