"""
test_unavailable_targets_visible.py
-----------------------------------
Ein nicht eingehängtes Laufwerk sah aus wie ein kaputtes Programm.

Der Scanner erkennt den Fall längst und schützt sich davor — er überspringt
das Aufräumen verwaister Einträge, damit eine abgehängte Platte nicht die halbe
Bibliothek löscht (siehe `manager.py`). Gesagt hat er es aber nur dem
Protokoll:

    ⚠️ 1 scan target(s) unavailable: ['/media_nas']

Wer den Server als Dienst laufen lässt, sieht diese Zeile nie. Er sieht eine
vollständige Bibliothek, in der nichts abspielt — jedes Video ein Fehler. Das
ist genau die Lage, in der man anfängt, an der falschen Stelle zu suchen: an
den Codecs, am Streaming, an den Rechten. Die Antwort ist ein Pfad, der gerade
nicht da ist.

`GET /api/settings` sagt jetzt dazu, welche der Scan-Ziele **dieses Kontos**
nicht existieren, und die Einstellungen zeigen sie an — an der Stelle, an der
die Pfade ohnehin stehen.

Absichtlich nur die eigenen Ziele: Die Antwort geht an den Browser, und fremde
Pfade gehören dort nicht hinein. Genau diese Trennung war in einem früheren
Lauf schon einmal Thema (`FOLDERS_DATA` im HTML-Dump).
"""
import os
from pathlib import Path

import pytest

from arcade_scanner.server.routes.settings import _unreachable

STATIC = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"


# --- Welche Pfade als fehlend gelten ---

def test_a_missing_path_is_reported(tmp_path):
    assert _unreachable([str(tmp_path / "nicht_eingehaengt")]) == \
        [str(tmp_path / "nicht_eingehaengt")]


def test_an_existing_path_is_not_reported(tmp_path):
    assert _unreachable([str(tmp_path)]) == []


def test_only_the_missing_ones_are_listed(tmp_path):
    fehlt = str(tmp_path / "weg")

    assert _unreachable([str(tmp_path), fehlt]) == [fehlt]


def test_a_relative_path_is_resolved_like_the_scanner_does(tmp_path, monkeypatch):
    """
    Der Scanner prüft `abspath(expanduser(...))`. Prüfte diese Stelle etwas
    anderes, wäre die Warnung entweder falsch oder sie bliebe aus.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vorhanden").mkdir()

    assert _unreachable(["vorhanden"]) == []
    assert _unreachable(["fehlt"]) == ["fehlt"]


def test_a_tilde_path_is_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Videos").mkdir()

    assert _unreachable(["~/Videos"]) == []


def test_empty_entries_are_skipped():
    assert _unreachable(["", None]) == []


def test_nothing_is_reported_without_targets():
    assert _unreachable([]) == []


# --- Im Zweifel schweigen ---

def test_a_failing_check_is_not_treated_as_missing(monkeypatch):
    """
    Ein hängender Netzwerk-Mount oder fehlende Rechte auf einem
    Elternverzeichnis lassen die Prüfung scheitern. Eine falsche Warnung über
    ein in Wahrheit erreichbares Ziel wäre schlimmer als gar keine — sie würde
    den Nutzer an einer Stelle suchen lassen, an der nichts ist.
    """
    def boom(_path):
        raise OSError("Stale file handle")

    monkeypatch.setattr(os.path, "exists", boom)

    assert _unreachable(["/media_nas"]) == []


# --- Der Weg in die Antwort ---

def test_the_settings_response_carries_the_list(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from arcade_scanner.server.routes import settings as settings_route

    fehlt = str(tmp_path / "abgehaengt")
    user = MagicMock()
    user.data.scan_targets = [str(tmp_path), fehlt]
    user.data.smart_collections = []
    user.data.exclude_paths = []
    user.data.available_tags = []
    user.data.sensitive_dirs = []
    user.data.sensitive_tags = []
    user.data.sensitive_collections = []

    user_db = MagicMock()
    user_db.get_user.return_value = user
    config = MagicMock()
    config.settings.model_dump.return_value = {}

    monkeypatch.setattr(settings_route, "_get_singletons",
                        lambda: (config, user_db, MagicMock(), 1024))

    gesendet = {}
    monkeypatch.setattr(settings_route, "send_json",
                        lambda handler, payload: gesendet.update(payload))

    handler = MagicMock()
    handler.get_current_user.return_value = "ralf"
    settings_route.handle_get_settings(handler)

    assert gesendet["unavailable_targets"] == [fehlt]


def test_an_anonymous_request_learns_no_paths(monkeypatch):
    """
    Ohne Sitzung gibt es keine Scan-Ziele — und damit auch nichts zu melden.
    """
    from unittest.mock import MagicMock

    from arcade_scanner.server.routes import settings as settings_route

    config = MagicMock()
    config.settings.model_dump.return_value = {}
    monkeypatch.setattr(settings_route, "_get_singletons",
                        lambda: (config, MagicMock(), MagicMock(), 1024))

    gesendet = {}
    monkeypatch.setattr(settings_route, "send_json",
                        lambda handler, payload: gesendet.update(payload))

    handler = MagicMock()
    handler.get_current_user.return_value = None
    settings_route.handle_get_settings(handler)

    assert gesendet["unavailable_targets"] == []


# --- Die Anzeige ---

def test_the_settings_view_renders_the_list():
    from arcade_scanner.templates.components import SETTINGS_MODAL_COMPONENT as SETTINGS_MODAL

    assert 'id="unavailableTargetsCard"' in SETTINGS_MODAL
    assert 'id="unavailableTargetsList"' in SETTINGS_MODAL
    # Verborgen, solange alles erreichbar ist.
    assert 'class="hidden bg-amber-500/10' in SETTINGS_MODAL


def test_the_paths_arrive_as_text_not_as_markup():
    """
    Scan-Ziele tippt der Nutzer selbst ein. Derselbe Weg, den die
    Tag-Namen im Wiedergabe-Dialog gehen mussten.
    """
    source = (STATIC / "settings.js").read_text(encoding="utf-8")
    block = source[source.index("function renderUnavailableTargets"):]
    block = block[:block.index("\n}\n")]

    assert "textContent = path" in block
    assert "innerHTML" not in block


def test_the_card_is_hidden_again_when_everything_is_reachable():
    source = (STATIC / "settings.js").read_text(encoding="utf-8")
    block = source[source.index("function renderUnavailableTargets"):]
    block = block[:block.index("\n}\n")]

    assert "classList.add('hidden')" in block
    assert "classList.remove('hidden')" in block


@pytest.mark.parametrize("aufruf", [
    "renderUnavailableTargets(data.unavailable_targets || [])",
])
def test_the_settings_dialog_calls_it(aufruf):
    """Sonst steht die Funktion da und wird nie ausgeführt."""
    source = (STATIC / "settings.js").read_text(encoding="utf-8")

    assert aufruf in source
