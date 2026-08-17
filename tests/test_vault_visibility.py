"""
test_vault_visibility.py
------------------------
Ein einzelner Serverfehler breitete den gesamten Vault in der normalen Ansicht
aus.

`loadUserData()` in engine.js holt Favoriten, Tags und die Vault-Liste von
`/api/user/data` und setzt daraus `v.hidden` auf jedem Eintrag. Schlug der
Aufruf fehl, protokollierte die Funktion das und kehrte zurück::

    } else {
        console.warn("User data load failed:", res.status);
        ...
    }

`v.hidden` blieb dann `undefined`. Und der Filter entscheidet so::

    const isHidden = v.hidden || false;
    if (workspaceMode === 'lobby' && isHidden) return false;

`undefined || false` ist `false` — also gilt **nichts** als versteckt, und jede
Datei aus dem Vault steht im normalen Raster. Für eine Funktion, deren einziger
Zweck das Verstecken ist, ist das die falsche Richtung des Fehlers; dieselbe
Klasse wie beim abgesicherten Modus, der bei einem Eintrag ohne Pfad alles
zeigte.

Die Prüfung sitzt jetzt in `filterAndSort()` und nicht an der Aufrufstelle:
Ganz am Ende von engine.js steht ein ``setTimeout(..., 500)``, das
`filterAndSort()` noch einmal anstösst. Ein früher Abbruch beim Laden wäre eine
halbe Sekunde später wieder überholt worden.

Geprüft wird ausgeführt, nicht gelesen — `vault_guard_harness.js` lädt
filter_engine.js in einen node-Kontext und meldet, was danach im Raster steht.
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


def video(path, hidden=None, favorite=False):
    entry = {
        "FilePath": path, "Status": "OK", "Size_MB": 100.0, "codec": "h264",
        "_fileNameLower": path.rsplit("/", 1)[-1].lower(),
        "_codecLower": "h264", "_folder": path.rsplit("/", 1)[0],
        "tags": [], "favorite": favorite, "mtime": 1700000000,
    }
    if hidden is not None:
        entry["hidden"] = hidden
    return entry


# --- Der Fund ---

def test_nothing_is_shown_when_the_user_data_failed_to_load():
    """
    Der Kern: Ist der Vault-Zustand unbekannt, wird gar nichts angezeigt —
    statt einer Bibliothek, in der die versteckten Einträge mitschwimmen.
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
    assert "Vault" in html
    assert "Neu laden" in html or "reload" in html


def test_without_the_guard_every_vaulted_file_would_show(tmp_path):
    """
    Der Beleg, dass es kein theoretisches Problem war: Ohne den `hidden`-Wert
    lässt die Filterzeile alles durch. Hier wird genau der Zustand
    nachgestellt, den ein fehlgeschlagener Ladevorgang hinterlässt — aber mit
    `userDataLoaded` auf `true`, damit die neue Sperre nicht greift.
    """
    result = run_filter(
        [video("/media/a.mp4"), video("/media/privat.mp4")],  # kein `hidden`-Feld
        user_data_loaded=True,
    )

    assert result["shownCount"] == 2, (
        "Ohne hidden-Werte filtert die Zeile nichts weg — genau darum geht es"
    )


# --- Der Normalbetrieb darf sich nicht ändern ---

def test_with_user_data_the_vault_is_filtered_out():
    result = run_filter(
        [video("/media/a.mp4", hidden=False), video("/media/privat.mp4", hidden=True)],
        user_data_loaded=True,
    )

    assert result["shownPaths"] == ["/media/a.mp4"]


def test_the_vault_view_shows_exactly_the_hidden_ones():
    result = run_filter(
        [video("/media/a.mp4", hidden=False), video("/media/privat.mp4", hidden=True)],
        user_data_loaded=True,
        workspace_mode="vault",
    )

    assert result["shownPaths"] == ["/media/privat.mp4"]


def test_an_untouched_flag_means_normal_operation():
    """
    `userDataLoaded` ist zu Beginn `undefined`. Nur ein ausdrückliches `false`
    sperrt — sonst wäre der erste Aufbau vor dem Laden dauerhaft blockiert.
    """
    payload = {"videos": [video("/media/a.mp4", hidden=False)], "workspaceMode": "lobby"}
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
        [video("/media/a.mp4", hidden=False, favorite=True),
         video("/media/b.mp4", hidden=False)],
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
