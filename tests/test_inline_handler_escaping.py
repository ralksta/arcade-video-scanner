"""
test_inline_handler_escaping.py
-------------------------------
Werte in Inline-Handlern (``onclick="f(…)"``) gehen durch ``jsArg()``.

Vorher stand im Hauptraster — über das **jede** Datei läuft —::

    onclick="…revealInFinder('${v.FilePath.replace(/'/g, "\\\\'")}')"

Geschützt gegen Apostrophe, nicht gegen ``"``: Der HTML-Parser beendet den
Attributwert am ersten Anführungszeichen. Am alten Ausdruck in Node gemessen,
eine Datei ``a" onmouseover="alert(document.cookie)" x=".mp4`` ergab::

    Attributwert: event.stopPropagation(); revealInFinder('a
    Rest im Tag:  onmouseover="alert(document.cookie)" x=".mp4')"

— ein echtes zweites Attribut, das beim Überfahren der Karte feuert. Ein
``\\`` am Namensende ergab einen SyntaxError: alle Knöpfe der Karte tot. Und
``encodeURIComponent`` (Review-Ansicht, Optimieren-Knopf) lässt ``'`` stehen:
``x');alert(1);//.mp4`` war JS-Injektion beim Klick.

``jsArg()`` maskiert in der richtigen Reihenfolge: erst für JavaScript
(``JSON.stringify``), dann für das Attribut (``escapeHtml``).
"""
import html
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"

HOSTILE = [
    'a" onmouseover="alert(document.cookie)" x=".mp4',
    "x');alert(1);//.mp4",
    "Ordner\\",
    "Urlaub '19 & \"Freunde\" <3>.mp4",
    "Zeile\nUmbruch.mp4",
    " Trenner.mp4",
]

# Inline-Handler mit '${…}' — erlaubt nur, wo der Wert nicht von außen kommt.
QUOTED_INTERPOLATION_OK = {
    "c": "candidates.js: Codec aus der festen Liste VALID_CODECS",
    "col.id": "collections.js: vom Client erzeugte ID",
    "r.id": "autotag.js: vom Server erzeugte Regel-ID",
}


def _js_arg_results(values):
    """Ruft jsArg() aus utils.js in einem vm-Kontext auf."""
    harness = textwrap.dedent(f"""
        const vm = require('vm');
        const fs = require('fs');
        const src = [{json.dumps(str(STATIC_DIR / "safe_storage.js"))},
                     {json.dumps(str(STATIC_DIR / "utils.js"))}]
            .map((p) => fs.readFileSync(p, 'utf8')).join('\\n');
        const noop = () => {{}};
        const context = vm.createContext({{
            console,
            // Attrappen wie in test_filename_escaping.py — utils.js setzt beim
            // Laden das Theme.
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
        const values = JSON.parse(fs.readFileSync(0, 'utf8'));
        process.stdout.write(JSON.stringify(values.map((v) => context.jsArg(v))));
    """)
    proc = subprocess.run(["node", "-e", harness], input=json.dumps(values),
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
@pytest.mark.parametrize("name", HOSTILE)
def test_js_arg_survives_attribute_and_js_parsing(name):
    """Attribut lesen wie der HTML-Parser, dekodieren, als JS ausführen."""
    [arg] = _js_arg_results([name])
    markup = f'<button onclick="capture({arg})">'

    value = markup.split('onclick="', 1)[1].split('"', 1)[0]
    assert markup.endswith(f'{value}">'), "Der Wert endete vor dem Ende des Attributs"

    decoded = html.unescape(value)
    js = f"let got; const capture = (v) => {{ got = v; }}; {decoded}; process.stdout.write(JSON.stringify(got));"
    proc = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == name


def test_no_inline_handler_quotes_an_outside_value():
    offenders = []
    for path in sorted(STATIC_DIR.glob("*.js")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for handler in re.findall(r'\bon[a-z]+="([^"]*)"', line):
                for expr in re.findall(r"'\$\{([^}]*)\}'", handler):
                    if expr.strip() not in QUOTED_INTERPOLATION_OK:
                        offenders.append(f"{path.name}:{lineno}: '${{{expr}}}'")
    assert not offenders, (
        "Inline-Handler mit '${…}' — Wert durch jsArg() geben (ohne Anführungszeichen "
        "drumherum) oder mit Begründung in QUOTED_INTERPOLATION_OK eintragen:\n  "
        + "\n  ".join(offenders)
    )


def test_no_handler_relies_on_apostrophe_replacement():
    """Das alte Muster: schützt vor ' und vor nichts sonst."""
    hits = [f"{p.name}:{n}" for p in STATIC_DIR.glob("*.js")
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"""on[a-z]+="[^"]*\.replace\(/'/g""", line)]
    assert not hits, hits


# --- Text-Kontexte mit Fremdherkunft (Nachtlauf 4) ---

TEXT_SITES = [
    ("context_menu.js", "escapeHtml(name)", "Dateiname in der Befehlspalette"),
    ("context_menu.js", "escapeHtml(v.DirectoryPath", "Ordner in der Befehlspalette"),
    ("treemap.js", "escapeHtml(shortName)", "Ordnername im Treemap-Titel"),
    ("treemap.js", "escapeHtml(block.shortName)", "Ordnername im Tooltip"),
    ("treemap.js", "escapeHtml(block.name)", "Dateiname im Tooltip"),
    ("utils.js", "${escapeHtml(message)}", "Toasts tragen Dateinamen (optimizer.js)"),
    ("engine.js", "${escapeHtml(displayName)}", "Ordnername unter /media im Assistenten"),
    ("engine.js", "data-path=\"${escapeHtml(dir.path)}\"", "Ordnerpfad im Assistenten"),
    ("engine.js", "${escapeHtml(c.label)}", "Filter-Chip (Suchbegriff, Tag, Ordner)"),
    ("collections.js", "${escapeHtml(col.name)}", "Sammlungsname"),
]


@pytest.mark.parametrize("filename,needle,why", TEXT_SITES, ids=[w for _, _, w in TEXT_SITES])
def test_outside_text_is_escaped(filename, needle, why):
    assert needle in (STATIC_DIR / filename).read_text(encoding="utf-8"), why
