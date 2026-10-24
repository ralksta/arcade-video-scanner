"""
test_filename_escaping.py
-------------------------
Dateinamen werden maskiert, bevor sie ins Markup gehen.

Ein Dateiname darf auf jedem gängigen Dateisystem fast jedes Zeichen enthalten,
spitze Klammern eingeschlossen. `createVideoCard()` setzte ihn unmaskiert per
`innerHTML` — eine Datei namens

    <img src=x onerror=fetch('/api/...')>.mp4

führte damit beim Aufbau des Grids Code aus, in der Sitzung des angemeldeten
Nutzers. Für eine Bibliothek aus heruntergeladenen Dateien ist das kein
konstruierter Fall: der Name kommt von außen, das Anzeigen genügt.

Geprüft wird der Pfad, über den *jede* Datei läuft (Karte im Grid) sowie die
Vergleichskarte der Review-Ansicht. Die übrigen Interpolationen im Frontend
sind hier bewusst nicht abgedeckt — siehe `dev-docs/frontend-escaping.md`.
"""
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"
ENGINE_JS = (STATIC_DIR / "engine.js").read_text(encoding="utf-8")
UTILS_JS = (STATIC_DIR / "utils.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

HOSTILE_NAMES = [
    '<img src=x onerror=alert(1)>.mp4',
    '"><script>alert(1)</script>.mp4',
    "Urlaub '2019' & Co.mp4",
    'a"b.mp4',
]


def _escape(value: str) -> str:
    """Führt escapeHtml aus utils.js in einem vm-Kontext aus.

    Die ganze Datei laufen zu lassen ist robuster, als die Funktion per
    String-Operationen herauszuschneiden — utils.js braucht dafür nur
    Attrappen für document und localStorage.
    """
    harness = textwrap.dedent(f"""
        const vm = require('vm');
        const fs = require('fs');

        const src = fs.readFileSync({json.dumps(str(STATIC_DIR / "utils.js"))}, 'utf8');
        const noop = () => {{}};
        const context = vm.createContext({{
            console,
            document: {{
                documentElement: {{ classList: {{ add: noop, remove: noop, toggle: () => false }} }},
                getElementById: () => null,
                createElement: () => ({{ classList: {{ add: noop, remove: noop }}, style: {{}} }}),
                body: {{ appendChild: noop }},
            }},
            localStorage: {{ getItem: () => null, setItem: noop }},
            setTimeout: noop,
            requestAnimationFrame: noop,
        }});
        context.window = context;
        vm.runInContext(src, context);

        const escapeHtml = vm.runInContext('escapeHtml', context);
        console.log(JSON.stringify(escapeHtml({json.dumps(value)})));
    """)
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, f"node failed:\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_escape_helper_neutralises_markup(name):
    escaped = _escape(name)
    assert "<" not in escaped
    assert ">" not in escaped
    assert '"' not in escaped


def test_escape_helper_is_idempotent_enough_for_display():
    """Doppelt maskiert sieht hässlich aus, ist aber nicht unsicher."""
    once = _escape("a&b.mp4")
    assert "&amp;" in once


# --- Verdrahtung im Renderpfad ---

def _function_body(source: str, name: str) -> str:
    return source.split(f"function {name}", 1)[1].split("\nfunction ", 1)[0]


def test_grid_card_escapes_the_file_name():
    """Der Pfad, über den jede einzelne Datei der Bibliothek läuft."""
    body = _function_body(ENGINE_JS, "createVideoCard")

    assert "const safeFileName = escapeHtml(fileName);" in body
    assert "${safeFileName}" in body
    assert "${fileName}</h3>" not in body, "Roher Dateiname steht wieder im Markup"


def test_grid_card_escapes_the_directory_and_full_path():
    body = _function_body(ENGINE_JS, "createVideoCard")

    assert "escapeHtml(dirName)" in body
    assert 'title="${v.FilePath}"' not in body, "Voller Pfad unmaskiert im title-Attribut"


def test_comparison_card_escapes_both_sides():
    """Die Review-Ansicht zeigt Original und optimierte Fassung nebeneinander."""
    body = _function_body(ENGINE_JS, "createComparisonCard")

    assert body.count("escapeHtml(orig.FilePath") >= 1
    assert body.count("escapeHtml(opt.FilePath") >= 1
    assert 'title="${orig.FilePath}"' not in body
    assert 'title="${opt.FilePath}"' not in body


def test_data_path_attribute_uses_setattribute():
    """
    `setAttribute` maskiert selbst — deshalb ist data-path unkritisch, obwohl
    dort der rohe Pfad steht. Festgehalten, damit es nicht versehentlich auf
    String-Interpolation umgestellt wird.
    """
    body = _function_body(ENGINE_JS, "createVideoCard")
    assert "container.setAttribute('data-path', v.FilePath)" in body


def test_remaining_scope_is_documented():
    """
    87 weitere Interpolationen von Namens- und Pfadfeldern sind heute nicht
    geprüft. Das gehört benannt, nicht verschwiegen.
    """
    doc = ROOT / "dev-docs" / "frontend-escaping.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "createVideoCard" in text
    assert "offen" in text.lower()
