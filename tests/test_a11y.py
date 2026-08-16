"""
test_a11y.py
------------
Barrierefreiheits-Contract des Dashboards.

Drei Dinge werden hier festgehalten:

1. Jeder Button, dessen einziger Inhalt ein Icon ist, braucht einen
   zugänglichen Namen (`aria-label` oder `title`) — sonst kündigt ein
   Screenreader ihn als "Schaltfläche" ohne jede Bedeutung an.
2. Material-Icons-Spans sind `aria-hidden`. Die Icons sind Ligaturen: ohne das
   liest der Screenreader wörtlich "star_border" oder "more_vert" vor.
3. Der Fokus-Käfig für Dialoge hält Tab und Shift+Tab im Dialog und springt
   an beiden Enden korrekt um.
"""
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"
TEMPLATES_DIR = ROOT / "arcade_scanner" / "templates"

MARKUP_FILES = sorted(TEMPLATES_DIR.glob("*.py")) + sorted(STATIC_DIR.glob("*.js"))

BUTTON_RE = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.S)
ICON_SPAN_RE = re.compile(r'<span\b([^>]*\bclass="material-icons[^"]*"[^>]*)>')
TAG_RE = re.compile(r"<[^>]+>")


def _icon_only_buttons(source: str):
    """Buttons, deren sichtbarer Inhalt nur aus einem Icon besteht."""
    found = []
    for match in BUTTON_RE.finditer(source):
        attrs, inner = match.group(1), match.group(2)
        if "material-icons" not in inner:
            continue
        without_icons = re.sub(
            r'<span class="material-icons[^"]*"[^>]*>.*?</span>', "", inner, flags=re.S
        )
        if TAG_RE.sub("", without_icons).strip():
            continue  # trägt sichtbaren Text
        if "aria-label=" in attrs or "title=" in attrs:
            continue
        found.append((source[:match.start()].count("\n") + 1, inner.strip()[:60]))
    return found


@pytest.mark.parametrize("markup_file", MARKUP_FILES, ids=lambda p: p.name)
def test_icon_only_buttons_have_an_accessible_name(markup_file):
    source = markup_file.read_text(encoding="utf-8")
    offenders = [
        f"{markup_file.name}:{line}: {snippet}"
        for line, snippet in _icon_only_buttons(source)
    ]
    assert not offenders, (
        "Button ohne sichtbaren Text und ohne aria-label/title — ein Screenreader "
        "kündigt ihn nur als „Schaltfläche\" an:\n" + "\n".join(offenders)
    )


@pytest.mark.parametrize("markup_file", MARKUP_FILES, ids=lambda p: p.name)
def test_material_icons_are_hidden_from_screen_readers(markup_file):
    source = markup_file.read_text(encoding="utf-8")
    offenders = [
        f"{markup_file.name}:{source[:m.start()].count(chr(10)) + 1}"
        for m in ICON_SPAN_RE.finditer(source)
        if "aria-hidden" not in m.group(1)
    ]
    assert not offenders, (
        "material-icons-Span ohne aria-hidden=\"true\" — der Screenreader liest "
        "den Ligatur-Namen vor (z. B. „star_border\"):\n" + "\n".join(offenders)
    )


# --- Fokus-Käfig ---

A11Y_JS = (STATIC_DIR / "a11y.js").read_text(encoding="utf-8")

pytestmark_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


def _run_trap(active_index: int, shift: bool) -> str:
    """
    Simuliert Tab/Shift+Tab im Fokus-Käfig und meldet, wohin der Fokus geht.

    Kein jsdom im Projekt (bewusst kein Build-Schritt) — der Test stellt daher
    genau die DOM-Oberfläche nach, die _trapHandler benutzt.
    """
    harness = textwrap.dedent(f"""
        const window = globalThis;
        let focused = 'none';
        const make = name => ({{
            name,
            offsetParent: {{}},
            focus() {{ focused = this.name; }},
        }});
        const items = [make('first'), make('middle'), make('last')];
        const modal = {{
            id: 'testModal',
            dataset: {{}},
            contains: el => items.includes(el),
            querySelectorAll: () => items,
            addEventListener() {{}},
            removeEventListener() {{}},
            focus() {{ focused = 'modal'; }},
        }};
        window.document = {{
            activeElement: items[{active_index}],
            addEventListener() {{}},
            contains: () => true,
        }};

        {A11Y_JS.split("document.addEventListener('DOMContentLoaded'")[0]}

        let prevented = false;
        _trapHandler({{
            key: 'Tab',
            shiftKey: {str(shift).lower()},
            currentTarget: modal,
            preventDefault() {{ prevented = true; }},
        }});
        console.log(JSON.stringify({{ focused, prevented }}));
    """)
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, f"node failed:\n{proc.stderr}"
    return proc.stdout.strip().splitlines()[-1]


@pytestmark_node
def test_tab_on_last_element_wraps_to_first():
    assert '"focused":"first"' in _run_trap(active_index=2, shift=False)


@pytestmark_node
def test_shift_tab_on_first_element_wraps_to_last():
    assert '"focused":"last"' in _run_trap(active_index=0, shift=True)


@pytestmark_node
def test_tab_in_the_middle_is_left_alone():
    """Nur an den Enden greifen wir ein — sonst bricht die normale Tab-Reihenfolge."""
    result = _run_trap(active_index=1, shift=False)
    assert '"focused":"none"' in result
    assert '"prevented":false' in result


def test_every_dialog_in_the_template_is_focus_trapped():
    """
    Neue Dialoge müssen in TRAPPED_MODALS landen, sonst tabbt der Nutzer
    hinter das Overlay.
    """
    listed = set(re.findall(r"'(\w+)',", A11Y_JS.split("TRAPPED_MODALS = [", 1)[1].split("]", 1)[0]))

    components = (TEMPLATES_DIR / "components.py").read_text(encoding="utf-8")
    # Dialoge erkennt man an der Rückstell-Regel `#<id>.active { display: flex`
    declared = set(re.findall(r"#(\w+)\.active \{ display: flex", components))

    missing = declared - listed
    assert not missing, f"Dialog(e) ohne Fokus-Käfig in a11y.js: {sorted(missing)}"


def test_focus_is_restored_to_the_opener():
    assert "_focusOrigin.set(modal, document.activeElement)" in A11Y_JS
    assert "document.contains(origin)" in A11Y_JS


def test_a11y_script_is_loaded():
    dashboard = (TEMPLATES_DIR / "dashboard_template.py").read_text(encoding="utf-8")
    assert "/static/a11y.js" in dashboard
