"""
test_mobile_reachability.py
---------------------------
Was auf dem Handy erreichbar sein muss.

Hintergrund: Die Ansichts-Umschaltung (Grid / Liste / Treemap / Ordner) steckte
in einem `hidden md:flex`-Container. Auf einem Telefon gab es damit keinen Weg
zur Listen-, Treemap- oder Ordner-Ansicht — die Funktionen existierten, waren
aber unerreichbar. Solche Regressionen entstehen still: `hidden md:*` sieht im
Markup harmlos aus und fällt auf dem Entwickler-Desktop nie auf.

Der Test hält deshalb fest, welche Bedienelemente auf jeder Bildschirmbreite
erreichbar bleiben müssen — und welche bewusst Desktop-only sind.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
COMPONENTS = (ROOT / "arcade_scanner" / "templates" / "components.py").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "arcade_scanner" / "server" / "static" / "settings.js").read_text(
    encoding="utf-8"
)

# Elemente, die auf jeder Breite bedienbar sein müssen
MUST_BE_REACHABLE = [
    "viewToggleGrid",
    "viewToggleList",
    "viewToggleTreemap",
    "viewToggleFolder",
    "openFiltersBtn",
    "sortSelect",
    "refreshBtn",
]

# Bewusst Desktop-only, mit Begründung
INTENTIONALLY_DESKTOP_ONLY = {
    "gridScaleContainer": "Ein Slider ist auf Touch kaum präzise treffbar",
    "shortcutsBtn": "Tastaturkürzel gibt es auf dem Handy nicht",
}


def _enclosing_classes(element_id: str) -> list[str]:
    """
    Sammelt die class-Attribute des Elements und seiner offenen Vorfahren.

    Grobe, aber ausreichende Auswertung: von der Fundstelle rückwärts alle
    `<div ... class="...">` einsammeln, die vor dem Element geöffnet und nicht
    wieder geschlossen wurden.
    """
    match = re.search(rf'id="{element_id}"', COMPONENTS)
    assert match, f"{element_id} kommt im Template nicht vor"

    before = COMPONENTS[:match.start()]
    own_tag_start = before.rfind("<")
    own = re.search(r'class="([^"]*)"', COMPONENTS[own_tag_start:match.end() + 400])
    classes = [own.group(1)] if own else []

    # Rückwärts über die div-Tags laufen: jedes `</div>` erhöht die Tiefe,
    # jedes `<div>` schließt eines davon. Was bei Tiefe 0 übrig bleibt, ist ein
    # noch offener Vorfahre des gesuchten Elements.
    depth = 0
    tags = list(re.finditer(r'<(/?)div\b([^>]*?)>', before))
    for tag in reversed(tags):
        if tag.group(1) == "/":
            depth += 1
        elif depth > 0:
            depth -= 1
        else:
            attrs = tag.group(2)
            cls = re.search(r'class="([^"]*)"', attrs)
            if cls:
                classes.append(cls.group(1))
    return classes


@pytest.mark.parametrize("element_id", MUST_BE_REACHABLE)
def test_control_is_not_hidden_on_small_screens(element_id):
    hidden_ancestors = [
        cls for cls in _enclosing_classes(element_id)
        if re.search(r"(^|\s)hidden(\s|$)", cls) and "md:" in cls
    ]
    assert not hidden_ancestors, (
        f"'{element_id}' steckt in einem `hidden md:*`-Container und ist auf dem "
        f"Handy nicht erreichbar:\n  " + "\n  ".join(hidden_ancestors)
    )


@pytest.mark.parametrize("element_id,reason", sorted(INTENTIONALLY_DESKTOP_ONLY.items()))
def test_desktop_only_controls_stay_documented(element_id, reason):
    """
    Gegenprobe: Diese beiden sind absichtlich Desktop-only. Verschwindet die
    Einschränkung, soll dieser Test auffallen und die Liste aktualisiert werden.
    """
    classes = _enclosing_classes(element_id)
    assert any("hidden" in cls and "md:" in cls for cls in classes), (
        f"'{element_id}' ist nicht mehr Desktop-only ({reason}) — Liste anpassen."
    )


def test_saved_views_visibility_follows_content_not_screen_width():
    """
    Der Container war `hidden md:flex`: auf dem Desktop immer sichtbar (auch
    ohne gespeicherte Ansichten), auf dem Handy nie.
    """
    assert "container.classList.toggle('hidden', views.length === 0)" in SETTINGS_JS
    assert "container.classList.toggle('flex', views.length > 0)" in SETTINGS_JS


def test_view_chips_are_built_without_string_interpolation():
    """
    Ansichtsnamen sind frei eingegeben. In einen interpolierten onclick gesetzt,
    zerlegt ein Apostroph den Handler — und escapeHtml rettet das nicht, weil der
    HTML-Parser `&#39;` vor dem JS-Parser wieder auflöst.
    """
    block = SETTINGS_JS.split("function renderSavedViews", 1)[1].split("\n}", 1)[0]
    assert "onclick=" not in block, "View-Chips interpolieren wieder in onclick"
    assert "label.textContent = view.name" in block
    assert "addEventListener('click'" in block
