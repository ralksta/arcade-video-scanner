"""
test_js_syntax.py
-----------------
Contract test: Every JS file in the static/ directory must be
syntactically valid JavaScript.

Why this exists:
    During refactoring, a JS file (filter_engine.js) was saved
    mid-edit with an unclosed function body. The browser loaded it
    silently, causing the entire application grid to be empty.
    `node --check` catches this class of bug in milliseconds,
    without needing a browser.

What is checked:
    - All *.js files in arcade_scanner/server/static/ (excl. aframe.min.js)
    - Parsed with `node --check` (V8 syntax validation, no execution)
    - Any SyntaxError → test fails with the node error message
"""
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"

# Exclude known large vendored bundles that are pre-minified and always valid
EXCLUDE = {"aframe.min.js"}


def all_js_files():
    return [
        f for f in sorted(STATIC_DIR.glob("*.js"))
        if f.name not in EXCLUDE
    ]


def pytest_generate_tests(metafunc):
    if "js_file" in metafunc.fixturenames:
        metafunc.parametrize("js_file", all_js_files(), ids=lambda f: f.name)


@pytest.fixture(scope="session")
def node_binary():
    binary = shutil.which("node")
    if not binary:
        pytest.skip("node not found in PATH — skipping JS syntax checks")
    return binary


def test_js_syntax_valid(js_file, node_binary):
    """Each JS file must pass `node --check` (syntax validation only, no execution)."""
    result = subprocess.run(
        [node_binary, "--check", str(js_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Syntax error in {js_file.name}:\n{result.stderr.strip()}"
    )


def test_the_syntax_check_is_not_blind(js_file, node_binary, tmp_path):
    """Prüft den Prüfer: Fängt `node --check` in dieser Datei überhaupt etwas?

    `node --check` meldet für Dateien, die es als ES-Modul erkennt (also alles
    mit `import`/`export`), **Erfolg — auch bei offensichtlich kaputtem Code**.
    Nachgemessen mit node 26:

        import x from 'y';
        const a = (((;          →  node --check … ; echo $?  →  0

    Für die Dateien in `static/` stimmt das heute nicht: keine benutzt
    Modul-Syntax, alle 28 werden wirklich geprüft. Es genügt aber ein einziges
    `import` in einer dieser Dateien, und der Test oben wird für sie
    stillschweigend wertlos — grün, ohne etwas geprüft zu haben.

    Deshalb wird hier jeder Datei ein Syntaxfehler angehängt und verlangt, dass
    er auffällt.
    """
    broken = tmp_path / js_file.name
    broken.write_text(
        js_file.read_text(encoding="utf-8") + "\nconst __kaputt = (((;\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [node_binary, "--check", str(broken)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode != 0, (
        f"{js_file.name}: node --check übersieht einen eingebauten Syntaxfehler. "
        "Vermutlich enthält die Datei jetzt Modul-Syntax (import/export) — dann "
        "prüft der Test darüber nichts mehr und braucht ein anderes Werkzeug."
    )
