"""
test_user_data_guard.py
-----------------------
Ohne Nutzerdaten zeigt das Raster nichts an — statt alles.

`loadUserData()` in engine.js holt Favoriten, Tags und die Listen des
abgesicherten Modus (`sensitive_*`) von `/api/user/data`. Schlägt der Aufruf
fehl, bleiben diese Listen leer, und der abgesicherte Modus zeigte genau das,
was er verbergen soll.

Bis Phase 1 (2026-10-02) hieß diese Datei test_vault_visibility.py: Damals
war der Grund für die Sperre der Vault, dessen Liste aus derselben Antwort
kam. Den Vault gibt es nicht mehr, die Sperre bleibt — mit dem abgesicherten
Modus als Grund. Die Vault-Tests sind entfernt.

Die Prüfung sitzt in `filterAndSort()` und nicht an der Aufrufstelle: Ganz am
Ende von engine.js steht ein ``setTimeout(..., 500)``, das `filterAndSort()`
noch einmal anstösst. Ein früher Abbruch beim Laden wäre eine halbe Sekunde
später wieder überholt worden.

Geprüft wird ausgeführt, nicht gelesen — `vault_guard_harness.js` (Name aus
der Vault-Zeit) lädt filter_engine.js in einen node-Kontext und meldet, was
danach im Raster steht.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "vault_guard_harness.js"
node = shutil.which("node")

pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def run_filter(videos, user_data_loaded, workspace_mode="lobby"):
    payload = {
        "videos": videos,
        "userDataLoaded": user_data_loaded,
        "workspaceMode": workspace_mode,
    }
    fixture = Path(__file__).parent / "_vault_fixtures.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    try:
        out = subprocess.run(
            [node, str(HARNESS), str(fixture)],
            capture_output=True, text=True, timeout=30,
        )
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    finally:
        fixture.unlink(missing_ok=True)


def video(path, favorite=False):
    entry = {
        "FilePath": path, "Status": "OK", "Size_MB": 100.0, "codec": "h264",
        "_fileNameLower": path.rsplit("/", 1)[-1].lower(),
        "_codecLower": "h264", "_folder": path.rsplit("/", 1)[0],
        "tags": [], "favorite": favorite, "mtime": 1700000000,
    }
    return entry


# --- Der Fund ---

def test_nothing_is_shown_when_the_user_data_failed_to_load():
    """
    Der Kern: Fehlen die Nutzerdaten, wird gar nichts angezeigt — statt einer
    Bibliothek, für die der abgesicherte Modus nicht greift.
    """
    result = run_filter(
        [video("/media/harmlos.mp4"), video("/media/privat.mp4")],
        user_data_loaded=False,
    )

    assert result["shownCount"] == 0
    assert result["renderCalls"] == 0, "Das Raster wurde trotzdem aufgebaut"


def test_the_user_is_told_why_and_can_reload():
    """Eine leere Seite ohne Erklärung wäre die zweitschlechteste Antwort."""
    result = run_filter([video("/media/a.mp4")], user_data_loaded=False)

    html = result["gridHtml"]
    assert "abgesicherte Modus" in html
    assert "Neu laden" in html or "reload" in html


def test_an_untouched_flag_means_normal_operation():
    """
    `userDataLoaded` ist zu Beginn `undefined`. Nur ein ausdrückliches `false`
    sperrt — sonst wäre der erste Aufbau vor dem Laden dauerhaft blockiert.
    """
    payload = {"videos": [video("/media/a.mp4")], "workspaceMode": "lobby"}
    fixture = Path(__file__).parent / "_vault_fixtures.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        assert json.loads(out.stdout)["shownCount"] == 1
    finally:
        fixture.unlink(missing_ok=True)


def test_the_favorites_view_still_works():
    result = run_filter(
        [video("/media/a.mp4", favorite=True),
         video("/media/b.mp4")],
        user_data_loaded=True,
        workspace_mode="favorites",
    )

    assert result["shownPaths"] == ["/media/a.mp4"]


# --- Beide Seiten der Verdrahtung ---

def test_the_loader_records_its_outcome():
    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "static" / "engine.js"
    ).read_text(encoding="utf-8")
    block = source.split("async function loadUserData()", 1)[1].split("\n    }", 1)[0]

    assert "window.userDataLoaded = true" in block
    assert "window.userDataLoaded = false" in block


def test_the_guard_sits_in_the_filter_not_at_the_call_site():
    """
    Absichtlich dort: Am Ende von engine.js steht ein `setTimeout(..., 500)`,
    das `filterAndSort()` erneut anstösst. Ein Abbruch an der Aufrufstelle wäre
    eine halbe Sekunde später wieder überholt worden.
    """
    engine = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "static" / "engine.js"
    ).read_text(encoding="utf-8")
    filter_js = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "static" / "filter_engine.js"
    ).read_text(encoding="utf-8")

    assert "filterAndSort();" in engine, "Der nachlaufende Aufruf ist weg — Kommentar anpassen"
    assert "window.userDataLoaded === false" in filter_js
