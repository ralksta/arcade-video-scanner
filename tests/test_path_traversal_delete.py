"""
test_path_traversal_delete.py
-----------------------------
`/api/discard_optimized` und `/api/keep_optimized` löschen bzw. verschieben nur
noch innerhalb der erlaubten Verzeichnisse.

Beide Endpunkte sind sitzungspflichtig, nahmen den Pfad aber ungeprüft aus dem
Request entgegen. Bei `discard_optimized` endete das hier:

    else:
        # Standard Mode discard
        if os.path.exists(abs_path):
            os.remove(abs_path)

Dieser Zweig läuft, wenn zum Pfad *kein* Datenbank-Eintrag existiert oder er
nicht im Review-Status ist — also für jeden beliebigen Pfad. Ein angemeldeter
Nutzer konnte damit jede Datei löschen, die der Serverprozess schreiben darf,
weit außerhalb der Bibliothek. In einer Mehrbenutzer-Installation reicht dafür
ein gewöhnliches Konto.

`keep_optimized` hat dieselbe Klasse: `shutil.move` auf ungeprüfte Pfade.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import files


class FakeHandler:
    """Handler-Attrappe nach dem Muster aus test_routes_files.py."""

    def __init__(self, path, user="alice"):
        self.path = path
        self._user = user
        self.wfile = MagicMock()
        self.status = None
        self.error = None
        self.error_message = ""

    def get_current_user(self):
        return self._user

    def send_response(self, code):
        self.status = code

    def send_error(self, code, message=""):
        self.error = code
        self.error_message = message

    def send_header(self, *_):
        pass

    def end_headers(self):
        pass


@pytest.fixture
def library(tmp_path, monkeypatch):
    """Ein erlaubtes Bibliotheksverzeichnis und eine Datei weit außerhalb."""
    media = tmp_path / "media"
    media.mkdir()
    inside = media / "clip.mp4"
    inside.write_text("video")

    outside = tmp_path / "privat" / "wichtig.txt"
    outside.parent.mkdir()
    outside.write_text("nicht anfassen")

    fake_config = MagicMock()
    fake_config.active_scan_targets = [str(media)]
    fake_config.review_dir = str(tmp_path / "review")
    monkeypatch.setattr(files, "config", fake_config)

    return inside, outside


def test_discard_refuses_a_path_outside_the_library(library):
    inside, outside = library
    handler = FakeHandler(f"/api/discard_optimized?path={outside}")

    files._handle_discard_optimized(handler)

    assert handler.error == 403, f"Erwartet 403, war {handler.error}"
    assert outside.exists(), "Die Datei außerhalb der Bibliothek wurde gelöscht"


def test_discard_still_works_inside_the_library(library):
    inside, _ = library
    handler = FakeHandler(f"/api/discard_optimized?path={inside}")

    with patch.object(files, "db") as fake_db:
        fake_db.get.return_value = None
        files._handle_discard_optimized(handler)

    assert handler.error is None, f"Unerwarteter Fehler: {handler.error}"
    assert not inside.exists(), "Datei in der Bibliothek wurde nicht gelöscht"


@pytest.mark.parametrize("attack", [
    "/etc/hosts",
    "../../../etc/passwd",
    "/root/.ssh/id_rsa",
])
def test_classic_traversal_targets_are_rejected(library, attack):
    handler = FakeHandler(f"/api/discard_optimized?path={attack}")
    files._handle_discard_optimized(handler)
    assert handler.error == 403


def test_keep_optimized_refuses_paths_outside_the_library(library):
    inside, outside = library
    handler = FakeHandler(
        f"/api/keep_optimized?original={outside}&optimized={inside}"
    )

    files._handle_keep_optimized(handler)

    assert handler.error == 403
    assert outside.exists()


def test_keep_optimized_refuses_when_only_the_target_is_foreign(library, tmp_path):
    """Beide Pfade werden geprüft, nicht nur der erste."""
    inside, _ = library
    foreign = tmp_path / "woanders.mp4"
    foreign.write_text("x")

    handler = FakeHandler(f"/api/keep_optimized?original={inside}&optimized={foreign}")
    files._handle_keep_optimized(handler)

    assert handler.error == 403


def test_review_directory_stays_allowed(library, tmp_path):
    """
    Optimizer-Ergebnisse liegen im Review-Verzeichnis, das außerhalb der
    Scan-Ziele liegt. Eine zu enge Prüfung hätte die Review-Funktion zerstört.
    """
    review = tmp_path / "review"
    review.mkdir()
    review_file = review / "job_1_clip.mp4"
    review_file.write_text("optimiert")

    handler = FakeHandler(f"/api/discard_optimized?path={review_file}")
    with patch.object(files, "db") as fake_db:
        fake_db.get.return_value = None
        files._handle_discard_optimized(handler)

    assert handler.error is None, f"Review-Datei fälschlich abgelehnt: {handler.error_message}"
    assert not review_file.exists()


def test_both_handlers_use_the_shared_validator():
    """
    Gegenprobe im Quelltext: Beide gehen über dieselbe Prüfung. Ein Handler,
    der sie umgeht, hat wieder die alte Lücke.
    """
    source = (
        Path(__file__).parent.parent
        / "arcade_scanner" / "server" / "routes" / "files.py"
    ).read_text(encoding="utf-8")

    for handler_name in ("_handle_discard_optimized", "_handle_keep_optimized"):
        block = source.split(f"def {handler_name}", 1)[1].split("\ndef ", 1)[0]
        assert "_sanitize_media_path" in block, f"{handler_name} prüft den Pfad nicht"
        assert "os.path.abspath(path)" not in block, (
            f"{handler_name} baut den Pfad wieder ungeprüft zusammen"
        )
