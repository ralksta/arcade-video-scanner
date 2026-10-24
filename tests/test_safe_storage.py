"""
test_safe_storage.py
--------------------
`localStorage` ist nicht überall benutzbar.

Manche Browser sperren es bei blockierten Cookies oder im privaten Modus, und
der Zugriff wirft dann bereits beim **Lesen** — nicht erst beim Schreiben. Das
Projekt weiß das an anderer Stelle längst: `tv_client/src/serverConfig.js`
fängt es ausdrücklich ab, mit dem Kommentar „webOS kann localStorage je nach
Kontext sperren".

Im Browser-Client wurde es ungeschützt gelesen, und zwar in drei Dateien
**beim Laden**:

    store.js       ganz oben, zweimal (safeMode)
    utils.js       initTheme(), einer IIFE
    workspace.js   initGridScale(), ebenfalls eine IIFE

`store.js` ist das **erste** Skript der Seite. Eine Ausnahme dort bedeutet
keine halb geladene Oberfläche, sondern gar keine — und zwar bevor irgendein
Fehlerpfad greifen könnte.

Dazu ein zweiter, unabhängiger Weg ins Aus: `collections.js` parste

    JSON.parse(localStorage.getItem('collapsedCategories') || '{}')

ohne Netz. Ein beschädigter Wert hätte die Sammlungsansicht dauerhaft
lahmgelegt — bei jedem Aufruf erneut, weil der Wert stehen bleibt.

Alle Zugriffe laufen jetzt über `window.safeStorage` aus `safe_storage.js` —
einer eigenen Datei, die als erstes Skript geladen wird. In `store.js`
untergebracht hätte der Helfer eine stillschweigende
Ladereihenfolge-Abhängigkeit erzeugt: Zur Laufzeit hätte sie gehalten, aber
mehrere Tests laden einzelne Dateien bewusst für sich, und genau daran ist der
erste Versuch gescheitert.

Geprüft wird ausgeführt: Die Dateien werden in einen node-Kontext geladen, in
dem `localStorage` wirft.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "arcade_scanner" / "server" / "static"
HARNESS = Path(__file__).parent / "safe_storage_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def run(mode: str):
    """Lädt safe_storage.js + store.js mit einem localStorage im gewünschten Zustand."""
    out = subprocess.run([node, str(HARNESS), mode],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# --- Gesperrtes localStorage ---

def test_store_js_loads_when_storage_throws():
    """
    Der Kern: Diese Datei ist das erste Skript der Seite. Wirft sie beim
    Laden, gibt es keine Oberfläche — auch keine kaputte.
    """
    result = run("throws")

    assert result["loaded"] is True, result.get("error")
    assert result["safeMode"] is False


def test_reading_returns_the_fallback_when_storage_throws():
    result = run("throws")

    assert result["get_missing"] is None
    assert result["get_with_fallback"] == "hell"


def test_writing_reports_failure_instead_of_raising():
    result = run("throws")

    assert result["set_ok"] is False


# --- Normalbetrieb ---

def test_values_survive_a_working_storage():
    result = run("works")

    assert result["set_ok"] is True
    assert result["roundtrip"] == "dunkel"


def test_a_stored_safe_mode_is_picked_up():
    result = run("safe_mode_on")

    assert result["safeMode"] is True


def test_a_missing_key_yields_the_fallback():
    result = run("works")

    assert result["get_missing"] is None
    assert result["get_with_fallback"] == "hell"


# --- Beschädigter Inhalt ---

def test_broken_json_falls_back_instead_of_raising():
    """
    Der zweite Weg ins Aus, unabhängig von gesperrtem Speicher: Ein
    beschädigter Wert hätte die Sammlungsansicht bei jedem Aufruf erneut
    lahmgelegt, weil er stehen bleibt.
    """
    result = run("broken_json")

    assert result["json_fallback"] == {"ersatz": True}


def test_valid_json_is_returned():
    result = run("works")

    assert result["json_roundtrip"] == {"a": 1}


# --- Keine direkten Zugriffe mehr ---

def test_no_file_touches_local_storage_directly():
    """
    Sonst hilft der gutmütige Zugriff nur dort, wo jemand daran gedacht hat.
    Kommentare zählen nicht — in `store.js` steht der Name in der Erklärung.
    """
    import re

    offenders = {}
    for js in sorted(STATIC.glob("*.js")):
        if js.name == "aframe.min.js":
            continue
        source = js.read_text(encoding="utf-8")
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        code = "\n".join(
            re.sub(r"(^|\s)//.*$", "", line) for line in source.splitlines()
        )
        hits = [
            line.strip() for line in code.splitlines()
            if "localStorage." in line and "window.localStorage" not in line
        ]
        if hits:
            offenders[js.name] = hits

    assert offenders == {}, f"Direkter localStorage-Zugriff: {offenders}"


def test_the_helper_is_loaded_before_everything_else():
    """
    Fünf Dateien greifen darauf zu. In `store.js` untergebracht hätte es eine
    stillschweigende Ladereihenfolge-Abhängigkeit erzeugt — zur Laufzeit
    unproblematisch, in den Tests nicht, die einzelne Dateien bewusst für sich
    laden. Genau daran ist der erste Versuch gescheitert.
    """
    from arcade_scanner.templates.dashboard_template import SCRIPT_MODULES

    assert SCRIPT_MODULES[0] == "safe_storage.js"
    assert (STATIC / "safe_storage.js").exists()

    users = [name for name in SCRIPT_MODULES
             if name != "safe_storage.js"
             and "safeStorage" in (STATIC / name).read_text(encoding="utf-8")]

    assert len(users) >= 4, users
    for name in users:
        assert SCRIPT_MODULES.index(name) > 0, (
            f"{name} benutzt safeStorage, wird aber nicht danach geladen"
        )


def test_the_tv_client_already_had_this_lesson():
    """
    Der Beleg, dass es kein erfundenes Problem ist: Der TV-Client fängt
    denselben Fall seit jeher ab, mit Begründung.
    """
    tv = (ROOT / "tv_client" / "src" / "serverConfig.js").read_text(encoding="utf-8")

    assert "catch" in tv
    assert "localStorage" in tv
