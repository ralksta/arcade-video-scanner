"""
test_tv_safe_storage.py
-----------------------
Ein gesperrtes `localStorage` machte den Fernseher schwarz.

Der TV-Client weiß das an einer Stelle längst. In `serverConfig.js` steht seit
jeher ein try/catch mit der Begründung im Kommentar: „webOS kann localStorage
je nach Kontext sperren — dann eben der Default."

An sechs anderen Stellen stand der Zugriff ungeschützt, und zwei davon an der
denkbar schlechtesten:

    App.js:12    im Rumpf der App-Komponente, beim ersten Rendern
    App.js:67    ebenda, bei jedem Rendern
    MainPanel.js beim Laden der Bibliothek und beim Abmelden
    LoginPanel.js zweimal beim Speichern des Tokens

Eine Ausnahme im Rumpf einer React-Komponente bedeutet keinen halb aufgebauten
Bildschirm, sondern gar keinen. Auf einem Fernseher gibt es keine
Entwicklerkonsole, in der man nachsähe: Der Nutzer sieht schwarz und hat keinen
Anhaltspunkt.

Derselbe Fund und dieselbe Lösung wie im Browser-Client, wo `safe_storage.js`
aus genau diesem Grund als erstes Skript geladen wird. Dass beide Clients
denselben Fehler getrennt voneinander hatten, ist der eigentliche Punkt: Die
Erkenntnis stand im Repo, sie war nur nicht angewandt.

Geprüft wird ausgeführt: `tv_safe_storage_harness.js` lädt das Modul in einen
node-Kontext, in dem der Speicher wirft oder fehlt.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
TV_SRC = ROOT / "tv_client" / "src"
HARNESS = Path(__file__).parent / "tv_safe_storage_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def run(mode):
    out = subprocess.run([node, str(HARNESS), mode],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# --- Gesperrter Speicher ---

def test_a_locked_storage_does_not_raise():
    """Der Kern: Es darf nicht werfen, sonst rendert die App gar nicht."""
    result = run("throws")

    assert result["loaded"] is True, result.get("error")
    assert result["get_existing"] is None


def test_reading_falls_back_when_locked():
    assert run("throws")["get_fallback"] == "ersatz"


def test_writing_reports_failure_instead_of_raising():
    assert run("throws")["set_ok"] is False


def test_removing_reports_failure_instead_of_raising():
    assert run("throws")["remove_ok"] is False


# --- Gar kein Speicher ---

def test_a_missing_storage_behaves_like_a_locked_one():
    """
    Der ältere Zweig im Code prüfte `typeof window !== 'undefined'` — der Fall
    „window da, localStorage nicht" blieb offen.
    """
    result = run("missing")

    assert result["loaded"] is True
    assert result["get_fallback"] == "ersatz"
    assert result["set_ok"] is False


# --- Normalbetrieb ---

def test_values_survive_a_working_storage():
    result = run("works")

    assert result["get_existing"] == "ja"
    assert result["set_ok"] is True
    assert result["roundtrip"] == "abc"


def test_removing_works():
    result = run("works")

    assert result["remove_ok"] is True
    assert result["after_remove"] is None


def test_a_missing_key_yields_the_fallback():
    result = run("works")

    assert result["get_missing"] is None
    assert result["get_fallback"] == "ersatz"


# --- Keine direkten Zugriffe mehr ---

def test_no_tv_file_touches_local_storage_directly():
    """
    Sonst hilft der gutmütige Zugriff nur dort, wo jemand daran gedacht hat —
    und gedacht hatte bisher genau eine Datei daran.
    """
    erlaubt = {"serverConfig.js", "safeStorage.js"}
    offenders = {}

    for js in sorted(TV_SRC.rglob("*.js")):
        if js.name in erlaubt:
            continue
        source = js.read_text(encoding="utf-8")
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        code = "\n".join(
            re.sub(r"(^|\s)//.*$", "", line) for line in source.splitlines()
        )
        hits = [line.strip() for line in code.splitlines() if "localStorage" in line]
        if hits:
            offenders[js.name] = hits

    assert offenders == {}, f"Direkter localStorage-Zugriff: {offenders}"


def test_the_three_views_use_the_helper():
    for name, erwartet in (
        ("App/App.js", "getItem"),
        ("views/LoginPanel.js", "setItem"),
        ("views/MainPanel.js", "getItem"),
    ):
        source = (TV_SRC / name).read_text(encoding="utf-8")
        assert "from '../safeStorage'" in source, name
        assert erwartet in source, name


def test_the_browser_client_had_the_same_lesson():
    """
    Der Beleg, dass es kein erfundenes Problem ist: Im Browser-Client wurde
    genau das in einem früheren Lauf behoben — und im TV-Client stand die
    Begründung sogar schon im Kommentar.
    """
    assert (ROOT / "arcade_scanner" / "server" / "static" / "safe_storage.js").exists()

    config = (TV_SRC / "serverConfig.js").read_text(encoding="utf-8")
    assert "webOS kann localStorage" in config
