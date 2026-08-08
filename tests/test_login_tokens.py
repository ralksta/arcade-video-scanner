# -*- coding: utf-8 -*-
"""
Der Login-Screen wird standalone ausgeliefert — ohne den <head> aus
templates/ui_components.py und damit ohne render_theme_css(). Er bringt die
Design-System-Tokens deshalb selbst mit. Diese Tests halten beide Seiten
deckungsgleich, damit die Login-Seite nicht stillschweigend aus der Palette
laeuft, wenn jemand theme.py anfasst.
"""

import re
from pathlib import Path

import pytest

from arcade_scanner.templates.theme import render_theme_css

LOGIN_FILE = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static" / "login.html"

# Nur die Tokens, die die Login-Seite tatsaechlich braucht.
REQUIRED_TOKENS = [
    "ds-bg",
    "ds-surface",
    "ds-border",
    "ds-text",
    "ds-text-muted",
    "ds-accent",
    "ds-accent-hover",
    "ds-danger",
]


def _declared_tokens(css: str) -> dict:
    """Alle `--name: wert;` Deklarationen als Mapping.

    Werte werden von Whitespace befreit, damit `rgba(255, 255, 255, 0.12)` und
    `rgba(255,255,255,0.12)` als gleich gelten — es geht um die Farbe, nicht um
    die Formatierung.
    """
    return {
        name: re.sub(r"\s+", "", value)
        for name, value in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", css)
    }


def _dark_mode_tokens() -> dict:
    """Die Tokens aus dem `.dark {}` Block von theme.py.

    Der Login-Screen ist dark-only, also ist das die richtige Referenz — nicht
    der :root-Block, der die Light-Mode-Werte traegt.
    """
    css = render_theme_css()
    match = re.search(r"\.dark\s*\{(.*?)\n\}", css, re.DOTALL)
    assert match, "Kein .dark-Block in render_theme_css() gefunden"
    return _declared_tokens(match.group(1))


@pytest.fixture(scope="module")
def login_html() -> str:
    if not LOGIN_FILE.exists():
        pytest.skip("login.html nicht gefunden")
    return LOGIN_FILE.read_text(encoding="utf-8")


def test_login_tokens_match_theme(login_html):
    """Jeder in login.html gesetzte --ds-* Wert muss dem aus theme.py entsprechen."""
    theme_tokens = _dark_mode_tokens()
    login_tokens = _declared_tokens(login_html)

    mismatches = []
    for name, login_value in login_tokens.items():
        if not name.startswith("ds-"):
            continue
        theme_value = theme_tokens.get(name)
        if theme_value is None:
            mismatches.append(f"--{name}: in login.html gesetzt, in theme.py unbekannt")
        elif theme_value.lower() != login_value.lower():
            mismatches.append(
                f"--{name}: login.html hat '{login_value}', theme.py hat '{theme_value}'"
            )

    assert not mismatches, (
        "login.html ist aus dem Design System gelaufen — Werte aus theme.py "
        "uebernehmen:\n" + "\n".join(f"  ❌ {m}" for m in mismatches)
    )


def test_login_declares_the_tokens_it_needs(login_html):
    """Fehlt ein Token, faellt die Seite still auf Browser-Defaults zurueck."""
    declared = _declared_tokens(login_html)
    missing = [t for t in REQUIRED_TOKENS if t not in declared]
    assert not missing, f"login.html fehlen diese Tokens: {missing}"


def test_login_has_no_hardcoded_legacy_colors(login_html):
    """Die alte Arcade-Palette darf nicht zurueckkehren."""
    legacy = ["#DE1A58", "#F4B342", "#00ffd0", "#8F0177", "#0d011a"]
    found = [c for c in legacy if c.lower() in login_html.lower()]
    assert not found, f"Legacy-Farben in login.html: {found}"
