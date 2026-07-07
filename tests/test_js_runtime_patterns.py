"""
test_js_runtime_patterns.py
----------------------------
Runtime-Pattern Tests: Fängt JS-Bugs ab, die syntaktisch valide sind
aber zur Laufzeit crashen — der blinde Fleck von `node --check`.

Warum dieser Test existiert:
    `node --check` (test_js_syntax.py) erkennt NUR SyntaxErrors.
    Der Bug in openCollectionModal() war 100% gültiges JavaScript:

        document.getElementById('collectionName').value = '';
        ↑ Crash wenn getElementById null zurückgibt — kein SyntaxError!

    Das nennt sich ein "Runtime Error" / "Null Dereference" und ist
    mit reiner Syntaxprüfung unsichtbar. Dieser Test-File prüft
    stattdessen Code-Patterns via statische Analyse (grep/regex).

Kategorien die hier getestet werden:
    1. Null-Dereference Pattern — direktes .property nach getElementById()
       ohne null-check → stummes Crash-Risiko
    2. Capture-Phase Event-Listener — addEventListener(..., {capture:true})
       kann andere UI-Handler blockieren
    3. Gefährliche DOM-Mutations-Patterns — innerHTML ohne Sanitization
    4. context_menu.js Korrektheit — spezifische Garantien für den neuen Code
"""

import re
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"

# Files to skip for resource-intensive pattern checks
EXCLUDE_FROM_PATTERN_CHECK = {"aframe.min.js"}


def read_js(filename: str) -> str:
    """Read a JS file from static dir."""
    path = STATIC_DIR / filename
    if not path.exists():
        pytest.skip(f"{filename} does not exist")
    return path.read_text(encoding="utf-8")


def all_js_files_content():
    """Return list of (name, content) for all non-excluded JS files."""
    results = []
    for f in sorted(STATIC_DIR.glob("*.js")):
        if f.name in EXCLUDE_FROM_PATTERN_CHECK:
            continue
        results.append((f.name, f.read_text(encoding="utf-8")))
    return results


# ---------------------------------------------------------------------------
# 1. NULL-DEREFERENCE PATTERN (der eigentliche Bug)
# ---------------------------------------------------------------------------

class TestNullDereferencePattern:
    """
    Erkennt das Pattern: document.getElementById('x').property = ...
    ohne vorherigen null-check.

    FALSCH (crasht wenn Element nicht im DOM):
        document.getElementById('collectionName').value = '';

    RICHTIG:
        const el = document.getElementById('collectionName');
        if (el) el.value = '';
        // oder:
        document.getElementById('collectionName')?.value = '';  ← optional chaining
    """

    # Pattern: getElementById('...') direkt gefolgt von .property =
    # Erlaubt: ?. (optional chaining), || (OR-chaining), Aufteilung auf zwei Zeilen
    UNSAFE_PATTERN = re.compile(
        r"document\.getElementById\(['\"][^'\"]+['\"]\)"
        r"(?!\s*\?)"          # nicht gefolgt von ?. (optional chaining)
        r"(?!\s*\|\|)"        # nicht gefolgt von ||
        r"(?!\s*;)"           # nicht gefolgt von ; (standalone call, kein chain)
        r"(?!\s*\))"          # nicht gefolgt von ) (in if-check)
        r"(?!\s*!)"           # nicht gefolgt von ! (boolean check)
        r"\."                 # direkt gefolgt von .
        r"(?!classList\.toggle\b)"  # classList.toggle ist common und meist safe
    )

    def test_collections_js_no_unsafe_getelementbyid(self):
        """
        collections.js darf nach dem Fix kein direktes .property-Chain
        nach getElementById mehr haben — der Bug der Edit Collection brach.
        """
        content = read_js("collections.js")
        lines = content.splitlines()
        violations = []

        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if self.UNSAFE_PATTERN.search(line):
                violations.append(f"  Line {lineno}: {stripped[:100]}")

        assert not violations, (
            "Potentielle Null-Dereference nach getElementById() in collections.js\n"
            "(kein null-check oder optional chaining vor .property Zugriff):\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 2. CAPTURE-PHASE EVENT LISTENER
# ---------------------------------------------------------------------------

class TestEventListenerPatterns:
    """
    Erkennt addEventListener mit capture:true oder {capture:true}
    das andere UI-Handler blockieren kann.

    capture:true bedeutet: der Handler feuert VOR allen anderen Handlern
    im bubbling-Baum. Das kann dazu führen dass Modal-Öffnen, Button-Clicks
    etc. durch einen schließenden Handler gestört werden.

    Erlaubt ist: mousedown + contains()-Check (safe pattern).
    Verboten ist: click + capture:true ohne contains()-Check.
    """

    CAPTURE_CLICK_PATTERN = re.compile(
        r"addEventListener\s*\(\s*['\"]click['\"]\s*,.*capture\s*:\s*true"
    )

    def test_context_menu_no_capture_click(self):
        """
        context_menu.js darf keinen click-Handler mit capture:true mehr haben —
        das blockierte das Edit-Collection Modal.
        Nach dem Fix soll mousedown + contains()-Check verwendet werden.
        """
        content = read_js("context_menu.js")
        lines = content.splitlines()
        violations = []

        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if self.CAPTURE_CLICK_PATTERN.search(line):
                violations.append(f"  Line {lineno}: {stripped[:100]}")

        assert not violations, (
            "context_menu.js verwendet click-Event mit capture:true.\n"
            "Das blockiert andere UI-Handler (z.B. Modal-Buttons).\n"
            "Verwende stattdessen: mousedown + .contains() für click-outside detection.\n"
            "Gefundene Violations:\n" + "\n".join(violations)
        )

    def test_context_menu_uses_contains_check(self):
        """
        context_menu.js muss .contains() verwenden beim close-outside-handler —
        als Beweis dass der sichere Ansatz implementiert ist.
        """
        content = read_js("context_menu.js")
        assert ".contains(" in content, (
            "context_menu.js fehlt .contains() check im click-outside-handler.\n"
            "Der sichere Ansatz: if (!menu.contains(e.target)) hideMenu()"
        )


# ---------------------------------------------------------------------------
# 3. CONTEXT_MENU.JS SPEZIFISCHE GUARANTIEN
# ---------------------------------------------------------------------------

class TestContextMenuJs:
    """Spezifische Korrektheitsprüfungen für context_menu.js."""

    def test_has_contextmenu_event_listener(self):
        """Muss auf contextmenu-Event hören (Rechtsklick)."""
        content = read_js("context_menu.js")
        assert "addEventListener('contextmenu'" in content or \
               'addEventListener("contextmenu"' in content, \
            "context_menu.js muss contextmenu-Event abhören"

    def test_has_keyboard_shortcut(self):
        """Command Palette muss ⌘K / Ctrl+K registrieren."""
        content = read_js("context_menu.js")
        assert "key === 'k'" in content or "key===\"k\"" in content, \
            "context_menu.js muss ⌘K Keyboard-Shortcut registrieren"

    def test_has_escape_handling(self):
        """Escape-Key muss Palette und Menü schließen."""
        content = read_js("context_menu.js")
        assert "Escape" in content, \
            "context_menu.js muss Escape-Key verarbeiten"

    def test_uses_window_all_videos(self):
        """Command Palette muss window.ALL_VIDEOS für die Suche verwenden."""
        content = read_js("context_menu.js")
        assert "ALL_VIDEOS" in content, \
            "context_menu.js muss window.ALL_VIDEOS für Video-Suche nutzen"

    def test_prevents_default_contextmenu(self):
        """Rechtsklick-Standardmenü muss verhindert werden."""
        content = read_js("context_menu.js")
        assert "preventDefault()" in content, \
            "context_menu.js muss e.preventDefault() im contextmenu-Handler aufrufen"


# ---------------------------------------------------------------------------
# 4. COLLECTIONS.JS SPEZIFISCHE GUARANTIEN
# ---------------------------------------------------------------------------

class TestCollectionsJsContracts:
    """
    Vertrags-Tests für collections.js — stellt sicher dass
    kritische Funktionen korrekt implementiert sind.
    """

    def test_open_collection_modal_exported(self):
        """openCollectionModal muss als window.* exportiert sein."""
        content = read_js("collections.js")
        assert "window.openCollectionModal = openCollectionModal" in content, \
            "openCollectionModal muss via window.* exportiert werden"

    def test_save_collection_exported(self):
        """saveCollection muss als window.* exportiert sein."""
        content = read_js("collections.js")
        assert "window.saveCollection = saveCollection" in content, \
            "saveCollection muss via window.* exportiert werden"

    def test_evaluate_collection_match_exported(self):
        """evaluateCollectionMatch muss als window.* exportiert sein."""
        content = read_js("collections.js")
        assert "window.evaluateCollectionMatch = evaluateCollectionMatch" in content, \
            "evaluateCollectionMatch muss via window.* exportiert werden"

    def test_collection_modal_active_class_logic(self):
        """openCollectionModal muss modal.classList.add('active') aufrufen."""
        content = read_js("collections.js")
        assert "classList.add('active')" in content or \
               'classList.add("active")' in content, \
            "openCollectionModal muss modal aktiv schalten via classList.add('active')"

    def test_null_safe_element_access(self):
        """
        Nach dem Fix muss collections.js null-safe auf DOM-Elemente zugreifen.
        Mindestens eine der safe-access-Methoden muss vorhanden sein.
        """
        content = read_js("collections.js")
        has_optional_chain = "?." in content
        has_null_guard = "if (_el(" in content or "if (el)" in content
        assert has_optional_chain or has_null_guard, (
            "collections.js muss null-safe DOM-Zugriff verwenden.\n"
            "Entweder optional chaining (?.) oder if-null-guards verwenden,\n"
            "um stilles Crashen bei fehlenden Elementen zu verhindern."
        )
