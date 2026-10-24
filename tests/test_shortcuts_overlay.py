"""
test_shortcuts_overlay.py
-------------------------
Contract-Tests für das Tastaturkürzel-Overlay (`?`).

Das Overlay ist reine Doku — und Doku, die niemand prüft, veraltet. Diese Tests
pinnen die Verdrahtung (Modal im Template, Script eingebunden, Button vorhanden)
und stellen sicher, dass die im Overlay dokumentierten Cinema-/Duplikat-Tasten
tatsächlich noch in den jeweiligen Key-Handlern vorkommen.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"
TEMPLATES_DIR = ROOT / "arcade_scanner" / "templates"

SHORTCUTS_JS = (STATIC_DIR / "shortcuts.js").read_text(encoding="utf-8")
COMPONENTS_PY = (TEMPLATES_DIR / "components.py").read_text(encoding="utf-8")
DASHBOARD_PY = (TEMPLATES_DIR / "dashboard_template.py").read_text(encoding="utf-8")


def test_shortcuts_script_is_loaded_by_dashboard():
    from arcade_scanner.templates.dashboard_template import SCRIPT_MODULES

    assert "shortcuts.js" in SCRIPT_MODULES


def test_shortcuts_modal_is_rendered_by_dashboard():
    assert "SHORTCUTS_MODAL_COMPONENT," in DASHBOARD_PY, "Import fehlt"
    assert "{SHORTCUTS_MODAL_COMPONENT}" in DASHBOARD_PY, "Platzierung im Body fehlt"


def test_modal_ids_used_by_js_exist_in_template():
    for element_id in ("shortcutsModal", "shortcutsBody", "shortcutsCloseBtn"):
        assert f'id="{element_id}"' in COMPONENTS_PY, f"{element_id} fehlt im Template"


def test_help_button_opens_overlay():
    assert 'id="shortcutsBtn"' in COMPONENTS_PY
    assert 'onclick="openShortcutsHelp()"' in COMPONENTS_PY


def test_public_api_is_exported_on_window():
    for fn in ("openShortcutsHelp", "closeShortcutsHelp", "toggleShortcutsHelp"):
        assert f"window.{fn} = {fn};" in SHORTCUTS_JS


def test_shortcut_key_class_is_styled():
    """renderShortcutSections() nutzt .shortcut-key — das CSS muss existieren."""
    assert "shortcut-key" in SHORTCUTS_JS
    assert ".shortcut-key {" in COMPONENTS_PY


def _documented_keys(section_title: str) -> set[str]:
    """Zieht die einzelnen Tasten einer Sektion aus SHORTCUT_SECTIONS."""
    block = SHORTCUTS_JS.split(f"title: '{section_title}'", 1)[1].split("},\n    {", 1)[0]
    return {k for k in re.findall(r"keys: \[([^\]]+)\]", block) for k in re.findall(r"'([^']+)'", k)}


def test_documented_cinema_keys_exist_in_cinema_handler():
    handler = (STATIC_DIR / "cinema.js").read_text(encoding="utf-8")
    handler = handler.split("function cinemaKeyHandler", 1)[1]
    for key in ("f", "v", "i", "g", "o"):
        assert f"key === '{key}'" in handler, f"Cinema-Shortcut '{key}' dokumentiert, aber nicht implementiert"
    assert "ArrowLeft" in handler and "ArrowRight" in handler


def test_documented_duplicate_keys_exist_in_duplicate_handler():
    handler = (STATIC_DIR / "duplicates.js").read_text(encoding="utf-8")
    handler = handler.split("function duplicateCheckerKeyHandler", 1)[1]
    for key in ("1", "2", "s", "a"):
        assert f"key === '{key}'" in handler, f"Duplikat-Shortcut '{key}' dokumentiert, aber nicht implementiert"


def test_global_shortcuts_ignore_typing_and_modifier_keys():
    """Regressionsschutz: '/' und '1'-'4' dürfen beim Tippen nicht feuern."""
    assert "isTypingTarget(e.target)" in SHORTCUTS_JS
    assert "e.ctrlKey || e.metaKey || e.altKey" in SHORTCUTS_JS
    assert "isContentEditable" in SHORTCUTS_JS


def test_global_shortcuts_yield_to_cinema_and_duplicate_checker():
    assert "isModalActive()" in SHORTCUTS_JS
    assert "duplicateCheckerState" in SHORTCUTS_JS
    assert "cinemaModal" in SHORTCUTS_JS


def test_cinema_section_documents_all_reserved_keys():
    """
    cinemaKeyHandler reserviert Tasten gegen Tag-Shortcuts. Was dort reserviert
    ist, muss im Overlay auch erklärt sein — sonst wundert sich der Nutzer,
    warum sein Tag-Shortcut auf 'f' nicht greift.
    """
    cinema_js = (STATIC_DIR / "cinema.js").read_text(encoding="utf-8")
    match = re.search(r"reservedKeys = \[([^\]]+)\]", cinema_js)
    assert match, "reservedKeys-Liste in cinema.js nicht gefunden"
    reserved = {k for k in re.findall(r"'([^']+)'", match.group(1))}
    letters = {k for k in reserved if len(k) == 1 and k.isalpha()}

    documented = {k.lower() for k in _documented_keys("Cinema")}
    missing = letters - documented
    assert not missing, f"Reservierte Cinema-Tasten fehlen im Overlay: {sorted(missing)}"
