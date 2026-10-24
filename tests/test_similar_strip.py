"""
test_similar_strip.py
---------------------
Die „Ähnliche Medien"-Leiste im Cinema (Embedding-Fundament, Teil 2).

Zwei Dinge daran brechen still, wenn man sie nicht festhält:

1. **Veraltete Antworten.** Beim Durchblättern mit ← / → überholen sich die
   Anfragen. Ohne Prüfung zeigt die Leiste die Nachbarn eines Videos, das
   längst nicht mehr läuft — und niemand merkt, dass die Vorschläge zum
   falschen Medium gehören.
2. **Treffer außerhalb der eigenen Scan-Ziele.** `/api/similar` filtert den
   Vault heraus, kennt aber die Pfad-Ziele des Nutzers nicht. Was `ALL_VIDEOS`
   nicht enthält, darf auch nicht in der Leiste erscheinen.
"""
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"
TEMPLATES_DIR = ROOT / "arcade_scanner" / "templates"

SIMILAR_JS = (STATIC_DIR / "similar.js").read_text(encoding="utf-8")
CINEMA_JS = (STATIC_DIR / "cinema.js").read_text(encoding="utf-8")
COMPONENTS_PY = (TEMPLATES_DIR / "components.py").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


def _render(all_videos, api_payload, current_path, path_when_response_arrives=None):
    """
    Führt loadCinemaSimilar() in node aus und gibt das erzeugte Markup zurück.

    `path_when_response_arrives` simuliert Weiterblättern während der Anfrage:
    currentCinemaPath ändert sich, bevor die Antwort eintrifft.
    """
    harness = textwrap.dedent(f"""
        const window = globalThis;
        window.escapeHtml = (s) => String(s);
        window.safeEncodePath = (p) => encodeURIComponent(p);
        window.ALL_VIDEOS = {json.dumps(all_videos)};
        window.currentCinemaPath = {json.dumps(current_path)};

        let body = {{ innerHTML: '' }};
        const panel = {{ classList: {{ contains: () => false, add() {{}}, remove() {{}} }} }};
        window.document = {{
            getElementById: (id) => (id === 'cinemaSimilarBody' ? body
                                   : id === 'cinemaSimilarPanel' ? panel : null),
            addEventListener() {{}},
        }};

        window.fetch = async () => {{
            const later = {json.dumps(path_when_response_arrives)};
            if (later !== null) window.currentCinemaPath = later;
            return {{ ok: true, status: 200, json: async () => ({json.dumps(api_payload)}) }};
        }};

        {SIMILAR_JS}

        loadCinemaSimilar().then(() => console.log(JSON.stringify(body.innerHTML)));
    """)
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, f"node failed:\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


VIDEO_A = {"FilePath": "/media/a.mp4", "thumb": "a.jpg"}
VIDEO_B = {"FilePath": "/media/b.mp4", "thumb": "b.jpg"}


def test_results_are_rendered_with_score_and_name():
    markup = _render(
        [VIDEO_A, VIDEO_B],
        {"status": "ok", "results": [{"file_path": "/media/b.mp4", "score": 0.8123}]},
        current_path="/media/a.mp4",
    )
    assert "b.mp4" in markup
    assert "81%" in markup
    assert "/thumbnails/b.jpg" in markup


def test_hits_outside_the_users_library_are_dropped():
    """
    /api/similar kennt die Scan-Ziele des Nutzers nicht. Was ALL_VIDEOS nicht
    enthält, gehört nicht in die Leiste.
    """
    markup = _render(
        [VIDEO_A],
        {"status": "ok", "results": [{"file_path": "/fremd/geheim.mp4", "score": 0.9}]},
        current_path="/media/a.mp4",
    )
    assert "geheim" not in markup
    assert "Keine ähnlichen Medien gefunden" in markup


def test_stale_response_is_discarded():
    """Weitergeblättert, bevor die Antwort kam — die Leiste bleibt beim Ladehinweis."""
    markup = _render(
        [VIDEO_A, VIDEO_B],
        {"status": "ok", "results": [{"file_path": "/media/b.mp4", "score": 0.9}]},
        current_path="/media/a.mp4",
        path_when_response_arrives="/media/b.mp4",
    )
    assert "b.mp4" not in markup, "Antwort zum alten Pfad wurde trotzdem gerendert"


def test_missing_index_is_explained_not_treated_as_an_error():
    """
    Ohne Indexlauf gibt es keine Vektoren — bei frischer Installation der
    Normalfall. Der Nutzer soll erfahren, was zu tun ist.
    """
    markup = _render([VIDEO_A], {"status": "not_indexed"}, current_path="/media/a.mp4")
    assert "media_indexer.py" in markup


def test_empty_result_set_says_so():
    markup = _render([VIDEO_A], {"status": "ok", "results": []}, current_path="/media/a.mp4")
    assert "Keine ähnlichen Medien gefunden" in markup


# --- Verdrahtung ---

def test_panel_ids_exist_in_the_template():
    for element_id in ("cinemaSimilarPanel", "cinemaSimilarBody"):
        assert f'id="{element_id}"' in COMPONENTS_PY


def test_rail_button_opens_the_strip():
    assert 'onclick="toggleCinemaSimilar()"' in COMPONENTS_PY


def test_shortcut_is_wired_and_reserved():
    """
    Ohne Reservierung würde 'S' als Tag-Shortcut interpretiert — und die
    Leiste ließe sich nie per Taste öffnen.
    """
    handler = CINEMA_JS.split("function cinemaKeyHandler", 1)[1]
    assert "key === 's'" in handler
    assert "'s'," in handler.split("reservedKeys = [", 1)[1].split("]", 1)[0]


def test_strip_follows_navigation_and_closes_with_cinema():
    assert "loadCinemaSimilar()" in CINEMA_JS, "Leiste folgt dem Blättern nicht"
    assert "closeCinemaSimilar()" in CINEMA_JS, "Leiste bleibt nach dem Schließen offen"


def test_script_is_loaded_after_cinema():
    """similar.js liest currentCinemaPath — cinema.js muss vorher geladen sein."""
    from arcade_scanner.templates.dashboard_template import SCRIPT_MODULES

    assert "similar.js" in SCRIPT_MODULES
    assert SCRIPT_MODULES.index("cinema.js") < SCRIPT_MODULES.index("similar.js")


def test_styles_for_the_strip_exist():
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    for cls in (".similar-strip", ".similar-item", ".similar-score", ".similar-note"):
        assert cls in css, f"CSS-Klasse {cls} fehlt"
