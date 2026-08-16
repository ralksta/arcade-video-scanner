"""
test_fetch_error_handling.py
----------------------------
Jeder `fetch()`-Aufruf im Frontend braucht einen Fehlerpfad.

Warum dieser Test existiert:
    Das Dashboard aktualisiert viele Aktionen optimistisch (Karte umschalten,
    Favorit setzen, Batch-Operationen) und feuerte danach ein `fetch()` ohne
    jede Fehlerbehandlung ab. Ist der Server weg oder antwortet er mit 500,
    bleibt die Oberfläche in einem Zustand stehen, den der Server nie gesehen
    hat — sichtbar wird das erst beim nächsten Reload, wenn alles zurückspringt.

    `node --check` findet das nicht (syntaktisch einwandfrei), und ohne Browser
    gibt es keinen Integrationstest. Also prüfen wir statisch, dass jeder
    Aufruf entweder über `apiWrite()` läuft, ein `.catch()` in seiner Kette hat
    oder in einem `try`-Block steht.
"""
import re
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"

# api.js definiert den Interceptor und apiWrite() selbst — dort steht der
# einzige fetch-Aufruf, der bewusst roh bleibt.
EXCLUDE_FILES = {"api.js"}

LOOKAHEAD = 30   # Zeilen, in denen ein .catch() der Kette stehen darf
LOOKBEHIND = 40  # Zeilen, in denen ein umschließendes try { stehen darf


def _js_files():
    return sorted(f for f in STATIC_DIR.glob("*.js") if f.name not in EXCLUDE_FILES)


def _fetch_call_sites(source: str):
    """Zeilennummern echter fetch()-Aufrufe — Kommentare und Strings ausgenommen."""
    sites = []
    for index, line in enumerate(source.splitlines()):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        if re.search(r"(?<![\w.])fetch\s*\(", line):
            sites.append(index)
    return sites


def _try_block_lines(source: str) -> set[int]:
    """
    Zeilennummern (0-basiert), die lexikalisch in einem try-Block liegen.

    Klammerzählung statt Fenster-Heuristik: ein abgeschlossenes try/catch weiter
    oben im File darf ein späteres, ungeschütztes fetch() nicht decken.
    """
    inside = set()
    depth = 0
    try_depths: list[int] = []
    line = 0

    for i, char in enumerate(source):
        if char == "\n":
            line += 1
        elif char == "{":
            if re.search(r"\btry\s*$", source[max(0, i - 12):i]):
                try_depths.append(depth)
            depth += 1
        elif char == "}":
            depth -= 1
            if try_depths and depth == try_depths[-1]:
                try_depths.pop()

        if try_depths:
            inside.add(line)

    return inside


def _is_handled(lines: list[str], index: int, in_try: set[int]) -> bool:
    ahead = "\n".join(lines[index:index + LOOKAHEAD])
    return ".catch(" in ahead or index in in_try


@pytest.mark.parametrize("js_file", _js_files(), ids=lambda p: p.name)
def test_every_fetch_call_has_an_error_path(js_file):
    source = js_file.read_text(encoding="utf-8")
    lines = source.splitlines()
    in_try = _try_block_lines(source)

    unhandled = [
        f"{js_file.name}:{i + 1}: {lines[i].strip()[:70]}"
        for i in _fetch_call_sites(source)
        if not _is_handled(lines, i, in_try)
    ]

    assert not unhandled, (
        "fetch() ohne Fehlerpfad — scheitert der Aufruf, merkt der Nutzer nichts:\n"
        + "\n".join(unhandled)
        + "\n\nEntweder apiWrite() benutzen, ein .catch() anhängen "
          "oder den await-Aufruf in ein try/catch setzen."
    )


def test_api_write_helper_exists_and_is_exported():
    api_js = (STATIC_DIR / "api.js").read_text(encoding="utf-8")
    assert "async function apiWrite(" in api_js
    assert "window.apiWrite = apiWrite;" in api_js


def test_api_write_reports_non_ok_responses():
    """Ein 500er ist ein Fehler — nicht nur ein Netzwerkabbruch."""
    api_js = (STATIC_DIR / "api.js").read_text(encoding="utf-8")
    assert "response.ok" in api_js
    assert "showToast" in api_js


def test_api_write_runs_the_rollback():
    api_js = (STATIC_DIR / "api.js").read_text(encoding="utf-8")
    assert "typeof rollback === 'function'" in api_js


OPTIMISTIC_ACTIONS = [
    ("cards.js", "toggleHidden"),
    ("cards.js", "toggleFavorite"),
    ("cards.js", "triggerBatchFavorite"),
    ("batch_operations.js", "triggerBatchHide"),
]


@pytest.mark.parametrize("filename,function_name", OPTIMISTIC_ACTIONS)
def test_optimistic_updates_pass_a_rollback(filename, function_name):
    """
    Diese vier ändern erst den lokalen Zustand und rufen dann den Server.
    Ohne rollback bleibt die Anzeige bei einem Serverfehler falsch stehen.
    """
    source = (STATIC_DIR / filename).read_text(encoding="utf-8")
    body = source.split(f"function {function_name}(", 1)[1].split("\nfunction ", 1)[0]
    assert "apiWrite(" in body, f"{function_name} ruft den Server nicht über apiWrite()"
    assert "rollback:" in body, f"{function_name} übergibt keinen rollback"
