"""
test_user_feedback.py
---------------------
Rückmeldungen an den Nutzer laufen über *einen* Kanal.

Das Dashboard hatte beides nebeneinander: 30 blockierende `alert()`-Dialoge und
34 Toasts — dieselbe Art Information, einmal als Systemdialog mitten im Bild,
einmal als dezente Einblendung unten rechts. `alert()` blockiert außerdem den
Thread, sieht in jedem Browser anders aus und lässt sich nicht stapeln.

Was hier festgehalten wird:
    1. Kein `alert()` mehr im Frontend (`confirm()` bleibt — es liefert einen
       Rückgabewert, für den es keinen Ersatz im Bestand gibt).
    2. Toasts liegen über allem, was sie sonst verdecken würde.
    3. Jeder Toast benennt einen der bekannten Typen.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"
COMPONENTS = (ROOT / "arcade_scanner" / "templates" / "components.py").read_text(encoding="utf-8")

JS_FILES = sorted(STATIC_DIR.glob("*.js"))
VALID_TYPES = {"info", "success", "error", "warning"}


def _code_lines(source: str) -> str:
    """Quelltext ohne Kommentarzeilen.

    Kommentare erklären oft genau das, wovor der Test warnt — hier stand
    `alert(1)` in der Begründung einer behobenen Stelle und löste den Wächter
    aus. Ein Wächter mit Fehlalarmen wird beim nächsten Mal ignoriert.
    """
    return "\n".join(
        "" if line.strip().startswith(("//", "*", "/*")) else line
        for line in source.splitlines()
    )


@pytest.mark.parametrize("js_file", JS_FILES, ids=lambda p: p.name)
def test_no_blocking_alert_dialogs(js_file):
    source = _code_lines(js_file.read_text(encoding="utf-8"))
    hits = [
        f"{js_file.name}:{source[:m.start()].count(chr(10)) + 1}"
        for m in re.finditer(r"(?<![\w.])alert\s*\(", source)
    ]
    assert not hits, (
        "alert() blockiert den Thread und bricht aus dem Design aus — "
        "showToast(...) benutzen:\n  " + "\n  ".join(hits)
    )


@pytest.mark.parametrize("js_file", JS_FILES, ids=lambda p: p.name)
def test_toast_types_are_known(js_file):
    """Ein Tippfehler im Typ fällt sonst nur daran auf, dass die Farbe fehlt."""
    source = _code_lines(js_file.read_text(encoding="utf-8"))
    bad = []
    for m in re.finditer(r"showToast\([^;]*?,\s*'([a-z]+)'", source, re.S):
        if m.group(1) not in VALID_TYPES:
            bad.append(f"{js_file.name}:{source[:m.start()].count(chr(10)) + 1}: '{m.group(1)}'")
    assert not bad, f"Unbekannter Toast-Typ (erlaubt: {sorted(VALID_TYPES)}):\n  " + "\n  ".join(bad)


def test_toasts_render_above_the_bottom_panels():
    """
    Optimizer- und GIF-Panel sitzen `bottom-4` — genau dort, wo die Toasts
    erscheinen. Liegt der Toast darunter, ist die Rückmeldung unsichtbar.
    """
    css = (STATIC_DIR / "settings.css").read_text(encoding="utf-8")
    toast_block = css.split(".settings-toast {", 1)[1].split("}", 1)[0]
    toast_z = int(re.search(r"z-index:\s*(\d+)", toast_block).group(1))

    panel_z = [int(z) for z in re.findall(r"z-\[(\d{4,})\]", COMPONENTS)]
    assert panel_z, "Keine hoch gestapelten Panels im Template gefunden — Test veraltet?"
    assert toast_z > max(panel_z), (
        f"Toasts liegen auf z-index {toast_z}, das höchste Panel auf {max(panel_z)} — "
        "Meldungen wären dahinter unsichtbar."
    )


def test_confirm_is_still_allowed():
    """
    Gegenprobe zur alert-Regel: `confirm()` liefert einen Rückgabewert und hat
    im Bestand keinen Ersatz. Verschwindet es irgendwann komplett, soll dieser
    Test auffallen, damit die Begründung oben nicht stehen bleibt.
    """
    uses_confirm = any(
        re.search(r"(?<![\w.])confirm\s*\(", f.read_text(encoding="utf-8"))
        for f in JS_FILES
    )
    assert uses_confirm, "Kein confirm() mehr — die Ausnahme in diesem Modul ist überholt."
