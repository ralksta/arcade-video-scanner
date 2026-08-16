"""
test_runtime_dependencies.py
----------------------------
Die Laufzeit-Abhängigkeiten bleiben bei vier.

`CLAUDE.md` sagt zu: „The server is Python stdlib only … Runtime dependencies
are just pydantic, Pillow, imagehash — keep it that way." Das ist eine
Architekturentscheidung mit Folgen: der Server läuft ohne Framework, ohne
Build-Schritt und lässt sich auf einem NAS installieren, ohne einen halben
Paketbaum mitzubringen.

Geprüft wurde das bisher von niemandem. Ein `import requests` in einer Route
oder ein `import numpy` in einem Analysepfad fällt beim Entwickeln nicht auf —
dort ist alles installiert — und schlägt erst bei der nächsten frischen
Installation zu.

Beim Anlegen dieses Tests hielt der Bestand die Zusage vollständig ein; hier
wird also kein Fehler behoben, sondern ein Zustand festgehalten.

Optionale Abhängigkeiten (torch, open_clip für den Indexer) dürfen nur *lazy*
innerhalb einer Funktion importiert werden, damit die Server-Module ohne
ML-Stack importierbar bleiben.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PACKAGE = ROOT / "arcade_scanner"

# Was requirements.txt zusagt, übersetzt in Importnamen.
DECLARED_RUNTIME = {
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "PIL": "Pillow",
    "imagehash": "imagehash",
}

# Optionale Extras: nur lazy erlaubt.
OPTIONAL_LAZY_ONLY = {"torch", "open_clip", "numpy", "cv2"}

WEB_FRAMEWORKS = {"flask", "fastapi", "django", "starlette", "tornado", "bottle",
                  "aiohttp", "quart", "sanic", "werkzeug", "jinja2"}


def _python_files():
    return [f for f in PACKAGE.rglob("*.py") if not f.name.startswith("._")]


def _third_party_imports(path: Path):
    """(root_module, lineno, is_module_level) je Import einer Fremdbibliothek."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return

    # Alles, was nicht in einer Funktion/Klasse steckt, läuft beim Import.
    module_level_ids = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for sub in ast.walk(node):
            module_level_ids.add(id(sub))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.ImportFrom):
            if node.level:
                continue  # relativer Import = eigenes Paket
            root = (node.module or "").split(".")[0]
        else:
            root = node.names[0].name.split(".")[0]

        if not root or root in sys.stdlib_module_names or root == "arcade_scanner":
            continue
        yield root, node.lineno, id(node) in module_level_ids


def test_requirements_file_matches_the_documented_set():
    """Die Liste in requirements.txt ist die Referenz für diesen Test."""
    listed = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            listed.add(line.split(">=")[0].split("==")[0].strip())

    assert listed == set(DECLARED_RUNTIME.values()), (
        f"requirements.txt hat sich geändert: {sorted(listed)}. Wenn das Absicht "
        "ist, gehört die Änderung auch nach CLAUDE.md und in diesen Test."
    )


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_undeclared_module_level_imports(path):
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}: {root}"
        for root, lineno, module_level in _third_party_imports(path)
        if module_level and root not in DECLARED_RUNTIME
    ]
    assert not offenders, (
        "Import einer nicht deklarierten Bibliothek auf Modul-Ebene — das "
        "bricht jede frische Installation:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_optional_extras_are_imported_lazily(path):
    """
    torch und open_clip gehören zur optionalen Indexer-Gruppe. Auf Modul-Ebene
    importiert, wären die Server-Module ohne ML-Stack nicht mehr ladbar.
    """
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}: {root}"
        for root, lineno, module_level in _third_party_imports(path)
        if module_level and root in OPTIONAL_LAZY_ONLY
    ]
    assert not offenders, (
        "Optionale Abhängigkeit auf Modul-Ebene:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_web_framework_anywhere(path):
    """
    „No web framework" ist die tragende Entscheidung der Server-Architektur —
    auch ein lazy importiertes Jinja2 wäre ein Bruch damit.
    """
    offenders = [
        f"{path.relative_to(ROOT)}:{lineno}: {root}"
        for root, lineno, _ in _third_party_imports(path)
        if root.lower() in WEB_FRAMEWORKS
    ]
    assert not offenders, (
        "Web-Framework importiert — der Server ist bewusst reine Standardbibliothek:\n  "
        + "\n  ".join(offenders)
    )


def test_server_modules_import_without_the_optional_stack():
    """
    Gegenprobe zur Lazy-Regel: Die Server-Module müssen sich laden lassen, ohne
    dass torch installiert ist. In dieser Umgebung ist es das ohnehin nicht —
    ein Fehlschlag hier bedeutet, dass ein Modul es doch braucht.
    """
    import importlib

    for module in ("arcade_scanner.server.routes.similar",
                   "arcade_scanner.core.similarity",
                   "arcade_scanner.server.response_helpers"):
        importlib.import_module(module)
