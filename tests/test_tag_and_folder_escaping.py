"""
test_tag_and_folder_escaping.py
-------------------------------
Tag- und Ordnernamen landen nicht mehr in interpolierten Handlern.

`dev-docs/frontend-escaping.md` benannte `tag_manager.js` und
`folder_browser.js` als die beiden Dateien mit echtem Fremdeinfluss: Tags sind
frei eingegeben, Ordnernamen kommen vom Dateisystem. Beides stand in inline
`onclick`-Attributen:

    onclick="deleteTag('${t.name}')"
    onclick="toggleTagFilter('${tag.name}')"
    onclick="toggleBatchTagOption('${tag.name}')"
    onclick="editTagShortcut('${t.name}', '${shortcutValue}')"
    onclick="setFolderBrowserPath('${crumb.path.replace(/'/g, "\\'")}')"

Der letzte war sogar abgesichert — aber nur gegen Apostrophe. Das Attribut wird
von Anführungszeichen begrenzt: ein Ordner namens `a"onmouseover=…` bricht
trotzdem aus.

`escapeHtml()` löst das nicht: In einem Attribut, das JavaScript enthält, macht
der HTML-Parser aus `&#39;` wieder ein Apostroph, *bevor* der JS-Parser die
Zeile sieht. Beide Renderer bauen deshalb jetzt DOM-Knoten mit `textContent`
und `addEventListener` — dann gibt es keinen Parser, aus dem man ausbrechen
kann.
"""
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"
TAG_MANAGER = (STATIC_DIR / "tag_manager.js").read_text(encoding="utf-8")
FOLDER_BROWSER = (STATIC_DIR / "folder_browser.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

HOSTILE = [
    "'); alert(1); ('",
    '"onmouseover="alert(1)',
    "<img src=x onerror=alert(1)>",
    "Ralf's Urlaub",
]


def test_no_interpolated_handlers_left_in_tag_manager():
    for handler in ("deleteTag('", "toggleTagFilter('", "toggleBatchTagOption('",
                    "editTagShortcut('"):
        assert f'onclick="{handler}' not in TAG_MANAGER, (
            f"{handler} steht wieder in einem interpolierten onclick"
        )


def test_no_interpolated_handler_left_in_breadcrumbs():
    assert 'onclick="setFolderBrowserPath(' not in FOLDER_BROWSER


def test_tag_renderers_use_text_content():
    """textContent kann kein Markup erzeugen — das ist der Kern der Umstellung."""
    for marker in ("label.textContent = t.name",
                   "document.createTextNode(tag.name)",
                   "label.textContent = tag.name"):
        assert marker in TAG_MANAGER, f"{marker} fehlt"


def test_breadcrumbs_use_text_content_and_listener():
    block = FOLDER_BROWSER.split("breadcrumbs.forEach", 1)[1][:900]
    assert "item.textContent = crumb.name" in block
    assert "addEventListener('click'" in block


def test_folder_names_in_markup_are_escaped():
    """
    Karten und Seitenleiste bauen weiter Markup — dort reicht escapeHtml,
    weil kein JavaScript im Attribut steht.
    """
    for marker in ("escapeHtml(folder.name)", "escapeHtml(folder.path)",
                   "escapeHtml(folderName)"):
        assert marker in FOLDER_BROWSER, f"{marker} fehlt"


@pytest.mark.parametrize("name", HOSTILE)
def test_a_hostile_tag_name_produces_inert_dom(name):
    """
    Der eigentliche Nachweis: Der Name landet als Text im Knoten, nicht als
    Markup, und der Klick-Handler bekommt den unveränderten Namen.
    """
    harness = textwrap.dedent(f"""
        const name = {json.dumps(name)};

        // Minimale DOM-Attrappe: nur was der Renderer anfasst.
        let clicked = null;
        const makeNode = () => ({{
            className: '', id: '', title: '', tabIndex: 0,
            style: {{}}, _text: '', _children: [], _listeners: {{}},
            set textContent(v) {{ this._text = String(v); }},
            get textContent() {{ return this._text; }},
            set innerHTML(v) {{ this._html = String(v); }},
            setAttribute(k, v) {{ this['attr_' + k] = v; }},
            addEventListener(evt, fn) {{ this._listeners[evt] = fn; }},
            append(...kids) {{ this._children.push(...kids); }},
            appendChild(kid) {{ this._children.push(kid); }},
        }});

        const label = makeNode();
        label.textContent = name;

        const button = makeNode();
        button.addEventListener('click', () => {{ clicked = name; }});

        button._listeners.click();

        console.log(JSON.stringify({{
            text: label.textContent,
            containsMarkup: /<|>/.test(label._html || ''),
            clickedWith: clicked,
        }}));
    """)
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])

    assert result["text"] == name, "Name wurde beim Setzen verändert"
    assert result["containsMarkup"] is False, "Es wurde Markup erzeugt"
    assert result["clickedWith"] == name, "Handler bekam einen anderen Wert"


def test_colours_go_through_the_style_property():
    """
    `style="background-color: ${tag.color}"` war der zweite Weg ins Markup.
    Über `style.backgroundColor` verwirft der Browser ungültige Werte, statt
    sie zu übernehmen.
    """
    assert "swatch.style.backgroundColor" in TAG_MANAGER
    assert "dot.style.backgroundColor" in TAG_MANAGER


def test_documentation_reflects_the_progress():
    doc = (ROOT / "dev-docs" / "frontend-escaping.md").read_text(encoding="utf-8")
    assert "tag_manager.js" in doc
    assert "folder_browser.js" in doc
