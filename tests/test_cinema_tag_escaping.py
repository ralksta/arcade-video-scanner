"""
test_cinema_tag_escaping.py
---------------------------
Tag-Namen im Wiedergabe-Dialog standen in interpolierten `onclick`-Attributen.

    <span ...>${tagName}</span>
    <button onclick="event.stopPropagation(); toggleCinemaTag('${tagName}')" ...>

    <button onclick="toggleCinemaTag('${tag.name}')" style="--tag-color: ${tag.color}">
        <span class="tag-dot" style="background-color: ${tag.color}"></span>
        ${tag.name}
    </button>

Tag-Namen und -Farben gibt der Nutzer frei ein. Der harmlose Fall genügt schon:
Ein Tag namens **„Ralfs Auswahl"** — mit Apostroph — beendet das JavaScript im
Attribut vorzeitig, und der Knopf tut nichts mehr. Alles darüber hinaus wäre
eingeschleuster Code.

Ein früherer Lauf hat genau dieses Muster an fünf anderen Stellen behoben;
`cinema.js` blieb übrig, obwohl neun andere Dateien `escapeHtml()` benutzen.

**HTML-Maskierung allein hätte hier nicht gereicht.** Der Browser dekodiert
Entitäten im Attributwert, *bevor* der Inhalt als JavaScript gelesen wird — aus
`&#39;` würde wieder ein Apostroph, und der Knopf wäre weiterhin kaputt. Der
richtige Weg ist der, den `tag_manager.js` schon geht: Knoten bauen,
`textContent` setzen, Handler per `addEventListener` anhängen. Dann gibt es gar
keinen Attributstring, in den etwas hineingeraten könnte.

Geprüft wird ausgeführt: `cinema_tags_harness.js` lädt cinema.js in einen
node-Kontext mit einer DOM-Attrappe und meldet, was als *Text* ankommt und ob
irgendwo `onclick=` im erzeugten Markup steht.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CINEMA_JS = (ROOT / "arcade_scanner" / "server" / "static" / "cinema.js").read_text(
    encoding="utf-8")
HARNESS = Path(__file__).parent / "cinema_tags_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def render(assigned, available):
    fixture = Path(__file__).parent / "_cinema_tag_fixtures.json"
    fixture.write_text(json.dumps({
        "video": {"FilePath": "/media/film.mp4", "tags": assigned},
        "availableTags": available,
    }), encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    finally:
        fixture.unlink(missing_ok=True)


def tag(name, color="#22c55e"):
    return {"name": name, "color": color}


# --- Der alltägliche Fall ---

def test_a_tag_with_an_apostrophe_arrives_intact():
    """
    Kein Angriff, nur ein Name: „Ralfs Auswahl". Im interpolierten `onclick`
    beendete der Apostroph die JavaScript-Zeichenkette, und der Knopf tat
    nichts mehr.
    """
    result = render(["Ralfs Auswahl"], [tag("Ralfs Auswahl")])

    assert "Ralfs Auswahl" in result["assigned"]["texts"]
    assert "Ralfs Auswahl" in result["available"]["texts"]


def test_a_tag_with_a_quote_arrives_intact():
    result = render(['Der "gute" Kram'], [tag('Der "gute" Kram')])

    assert 'Der "gute" Kram' in result["assigned"]["texts"]


def test_a_tag_with_a_backslash_arrives_intact():
    result = render(["C:\\Pfad"], [tag("C:\\Pfad")])

    assert "C:\\Pfad" in result["assigned"]["texts"]


# --- Der Fall, der Code wäre ---

@pytest.mark.parametrize("boese", [
    "<img src=x onerror=alert(1)>",
    "'); alert(1); //",
    '"><script>alert(1)</script>',
    "</span><script>alert(1)</script>",
])
def test_a_tag_name_never_becomes_markup(boese):
    """
    Der Name muss als **Text** ankommen. Erschiene er im Markup, wäre er Code.
    """
    result = render([boese], [tag(boese)])

    assert boese in result["assigned"]["texts"], "Der Name kommt nicht als Text an"
    assert boese not in result["assigned"]["html"]
    assert boese not in result["available"]["html"]


def test_no_inline_handler_markup_is_produced():
    """
    Die eigentliche Änderung: Es gibt gar keinen Attributstring mehr, in den
    etwas hineingeraten könnte.
    """
    result = render(["'); alert(1); //"], [tag("'); alert(1); //")])

    assert result["assigned"]["hasInlineHandlerMarkup"] is False
    assert result["available"]["hasInlineHandlerMarkup"] is False


def test_a_tag_colour_is_not_interpolated_into_markup():
    """Auch die Farbe kommt aus der Eingabe des Nutzers."""
    result = render(["x"], [tag("x", color='#fff" onload="alert(1)')])

    assert 'onload="alert(1)' not in result["available"]["html"]
    assert 'onload="alert(1)' not in result["assigned"]["html"]


# --- Was weiterhin gelten muss ---

def test_an_empty_tag_list_renders_nothing():
    result = render([], [])

    assert result["assigned"]["texts"] == []


def test_assigned_tags_are_a_subset_of_the_available_ones():
    result = render(["a"], [tag("a"), tag("b")])

    assert result["assigned"]["texts"] == ["a"]
    assert sorted(result["available"]["texts"]) == ["a", "b"]


# --- Struktur ---

def test_cinema_js_no_longer_interpolates_into_onclick():
    """
    Der Rundumschlag über die Datei. Kommentare zählen nicht — der Kommentar
    über der Änderung nennt das alte Muster.
    """
    import re

    source = re.sub(r"/\*.*?\*/", "", CINEMA_JS, flags=re.S)
    code = "\n".join(
        re.sub(r"(^|\s)//.*$", "", line) for line in source.splitlines()
    )

    offenders = [
        line.strip() for line in code.splitlines()
        if "onclick=" in line and "${" in line
    ]
    assert offenders == [], f"Interpolation in onclick: {offenders}"


def test_it_follows_the_pattern_the_tag_manager_already_uses():
    """
    Der Beleg, dass es keine neue Erfindung ist: `tag_manager.js` baut seine
    Tag-Knöpfe seit einem früheren Lauf genau so.
    """
    manager = (
        ROOT / "arcade_scanner" / "server" / "static" / "tag_manager.js"
    ).read_text(encoding="utf-8")

    assert "addEventListener('click', () => toggleTagFilter(tag.name))" in manager
    assert "addEventListener('click', () => toggleCinemaTag(tag.name))" in CINEMA_JS
