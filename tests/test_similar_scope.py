"""
test_similar_scope.py
---------------------
`GET /api/similar` beantwortet „was sieht ähnlich aus?" über einen Index, der
**installationsweit** ist. Die Bibliotheken sind es nicht.

Zwei Lücken:

**1. Kein Kontobezug.** Ausgeschlossen wurden nur die Vault-Pfade des Nutzers.
Die Treffer selbst kamen aus dem gesamten Index — also auch aus den Scan-Zielen
*anderer* Konten, mit vollem Pfad und Verzeichnisnamen in der Antwort. In dieser
Installation heisst das: Das Zweitkonto mit dem Ziel `/media_ralf` hätte über
Ähnlichkeitstreffer Dateien unter `/media` und `/media_nas` gesehen.

`/api/videos` und der Duplikat-Scan filtern an derselben Stelle längst pro
Nutzer. Hier fehlte es.

**2. Fällt der Nutzerdatensatz aus, entfiel die Vault-Filterung.**

    u = user_db.get_user(user_name)
    if u and u.data.vaulted:
        exclude.update(...)

`u is None` — also ein Lesefehler — hiess: nichts ausschliessen, und die
Antwort enthielt Vault-Pfade. Dieselbe Richtung des Fehlers wie im Browser- und
im TV-Client heute Nacht, nur diesmal serverseitig und mit den Pfaden im
Klartext.

Die Regel für Nutzer ohne eingerichtete Ziele ist bewusst dieselbe wie in
`/api/videos`: Admin sieht alles, alle anderen nichts. Zwei Antworten auf
dieselbe Frage im selben Haus wären schlimmer als eine strenge.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import similar


class FakeHandler:
    def __init__(self, path):
        self.path = path
        self.status = None
        self.error = None
        self.payload = None
        self.wfile = MagicMock()

    def get_current_user(self):
        return "privat"

    def send_response(self, code):
        self.status = code

    def send_error(self, code, message=""):
        self.error = code

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass


def make_user(targets, vaulted=(), is_admin=False):
    u = MagicMock()
    u.is_admin = is_admin
    u.data.scan_targets = list(targets)
    u.data.vaulted = list(vaulted)
    return u


VECTORS = {
    "/media_ralf/eigenes.mp4": [1.0, 0.0],
    "/media_ralf/auch_eigenes.mp4": [0.9, 0.1],
    "/media/fremdes.mp4": [1.0, 0.0],
    "/media_nas/auch_fremd.mp4": [0.95, 0.05],
    "/media_ralf/privat.mp4": [1.0, 0.0],
}


def query(user, path="/media_ralf/eigenes.mp4", vectors=None):
    """Ruft die Route auf und gibt die zurückgelieferten Pfade zurück."""
    handler = FakeHandler(f"/api/similar?path={path}&limit=10")
    media_db = MagicMock()
    user_db = MagicMock()
    user_db.get_user.return_value = user

    sent = {}

    def capture(_h, payload):
        sent.update(payload)

    with patch.object(similar, "_get_deps", return_value=(media_db, user_db)), \
         patch.object(similar._cache, "get", return_value=dict(vectors or VECTORS)), \
         patch.object(similar, "send_json", capture):
        similar.handle_get(handler)

    return handler, [r["file_path"] for r in sent.get("results", [])]


# --- 1. Kontobezug ---

def test_results_stay_inside_the_users_own_targets():
    """
    Der Fund: Vorher standen `/media/fremdes.mp4` und `/media_nas/auch_fremd.mp4`
    in der Antwort — Pfade aus den Zielen eines anderen Kontos.
    """
    _handler, paths = query(make_user(["/media_ralf"]))

    assert paths, "Die eigenen Treffer fehlen jetzt auch"
    assert all(p.startswith("/media_ralf/") for p in paths), paths


def test_a_sibling_directory_with_a_shared_prefix_is_outside():
    """
    `/media` darf nicht `/media_ralf` und `/media_nas` mit einschliessen — das
    sind genau die drei Ziele dieser Installation.
    """
    _handler, paths = query(
        make_user(["/media"]), path="/media/fremdes.mp4")

    assert paths == [] or all(p.startswith("/media/") for p in paths), paths
    assert not any(p.startswith("/media_ralf") or p.startswith("/media_nas")
                   for p in paths), paths


def test_the_query_file_itself_is_never_returned():
    _handler, paths = query(make_user(["/media_ralf"]))

    assert "/media_ralf/eigenes.mp4" not in paths


def test_vaulted_files_are_excluded():
    _handler, paths = query(
        make_user(["/media_ralf"], vaulted=["/media_ralf/privat.mp4"]))

    assert "/media_ralf/privat.mp4" not in paths


# --- 2. Wenn der Nutzer nicht lesbar ist ---

def test_an_unreadable_user_gets_no_results_at_all():
    """
    Vorher: `if u and u.data.vaulted` — ein `None` hiess „nichts
    ausschliessen", und die Antwort enthielt Vault-Pfade im Klartext.
    """
    handler, paths = query(None)

    assert handler.error == 503
    assert paths == []


# --- Nutzer ohne eingerichtete Ziele ---

def test_an_admin_without_targets_sees_everything():
    """Dieselbe Regel wie in /api/videos, nicht eine zweite."""
    _handler, paths = query(make_user([], is_admin=True))

    assert len(paths) == len(VECTORS) - 1  # ohne die Abfragedatei selbst


def test_a_normal_user_without_targets_sees_nothing():
    _handler, paths = query(make_user([], is_admin=False))

    assert paths == []


def test_the_rule_matches_the_one_in_the_video_route():
    """
    Der Beleg, dass es dieselbe Regel ist und nicht zufällig dasselbe
    Ergebnis. Ändert sich eine der beiden, wird das hier sichtbar.
    """
    from pathlib import Path

    api = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "api_handler.py"
    ).read_text(encoding="utf-8")

    assert "if not user_targets and u.is_admin:" in api
    assert 'getattr(u, "is_admin", False)' in (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "similar.py"
    ).read_text(encoding="utf-8")


# --- Die gemeinsame Grenzprüfung ---

def test_the_shared_boundary_helper_is_used_everywhere():
    """
    Die Rechnung „liegt Pfad in Verzeichnis" stand an vier Stellen einzeln da,
    dreimal ohne Verzeichnisgrenze. Jetzt an einer.
    """
    from pathlib import Path

    base = Path(__file__).parent.parent / "arcade_scanner"
    for rel in ("server/api_handler.py", "server/routes/similar.py"):
        source = (base / rel).read_text(encoding="utf-8")
        code = "\n".join(
            ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
        )
        assert "path_is_within(" in code, f"{rel} prüft wieder selbst"
        assert ".startswith(t)" not in code, (
            f"{rel} vergleicht wieder ohne Verzeichnisgrenze"
        )


@pytest.mark.parametrize("candidate,directory,expected", [
    ("/media/film.mp4", "/media", True),
    ("/media", "/media", True),
    ("/media/", "/media", True),
    ("/media_nas/film.mp4", "/media", False),
    ("/media_ralf/film.mp4", "/media", False),
    ("/medien/film.mp4", "/media", False),
    ("/media/film.mp4", "/media/", True),
    ("", "/media", False),
    ("/media/film.mp4", "", False),
])
def test_the_boundary_helper_itself(candidate, directory, expected):
    from arcade_scanner.security import path_is_within

    assert path_is_within(candidate.rstrip(os.sep) or candidate, directory) is expected
