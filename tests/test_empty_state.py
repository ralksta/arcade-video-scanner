"""
test_empty_state.py
-------------------
Contract-Tests für den Leer-Zustand des Grids.

Vorher zeigte das Dashboard bei 0 Treffern eine leere Fläche. Diese Tests
pinnen die Verdrahtung und — per node-vm — das Verhalten von
describeEmptyState(): welche Erklärung bei welchem Zustand erscheint.
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

EMPTY_STATE_JS = (STATIC_DIR / "empty_state.js").read_text(encoding="utf-8")
DASHBOARD_PY = (TEMPLATES_DIR / "dashboard_template.py").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


def _describe(state: dict) -> dict:
    """
    Führt describeEmptyState() in node aus — mit `state` als window-Vorbelegung.

    Kein DOM nötig: die Funktion liest ausschließlich window-Globals.
    """
    harness = textwrap.dedent(f"""
        const window = globalThis;
        window.escapeHtml = (s) => String(s);
        Object.assign(window, {json.dumps(state)});
        {EMPTY_STATE_JS.replace("window.updateEmptyState = updateEmptyState;", "")}
        console.log(JSON.stringify(describeEmptyState()));
    """)
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", harness],
        capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode == 0, f"node failed:\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


BASE = {
    "ALL_VIDEOS": [],
    "searchTerm": "",
    "workspaceMode": "lobby",
    "currentFilter": "all",
    "currentCodec": "all",
    "minSizeMB": None,
    "maxSizeMB": None,
    "dateFilter": "all",
    "activeTags": [],
    "filterUntaggedOnly": False,
    "filteredVideos": [],
    "currentLayout": "grid",
}


def test_empty_library_offers_settings_and_scan():
    state = _describe(BASE)
    assert state["icon"] == "video_library"
    labels = [a["fn"] for a in state["actions"]]
    assert "openSettings()" in labels
    assert "rescanLibrary()" in labels


def test_search_without_hits_offers_clearing_the_search():
    state = _describe({**BASE, "ALL_VIDEOS": [{"FilePath": "/a.mp4"}], "searchTerm": "zzz"})
    assert state["icon"] == "search_off"
    assert "zzz" in state["hint"]
    assert [a["fn"] for a in state["actions"]] == ["clearSearchTerm()"]


def test_filters_without_hits_offer_reset():
    state = _describe({**BASE, "ALL_VIDEOS": [{"FilePath": "/a.mp4"}], "currentCodec": "av1"})
    assert state["icon"] == "search_off"
    assert [a["fn"] for a in state["actions"]] == ["resetFilters()"]


def test_search_and_filters_offer_both_ways_out():
    state = _describe({
        **BASE,
        "ALL_VIDEOS": [{"FilePath": "/a.mp4"}],
        "searchTerm": "abc",
        "activeTags": ["urlaub"],
    })
    assert [a["fn"] for a in state["actions"]] == ["clearSearchTerm()", "resetFilters()"]


@pytest.mark.parametrize("mode,icon", [
    ("vault", "lock"),
    ("favorites", "star_border"),
    ("optimized", "compress"),
])
def test_empty_workspaces_explain_themselves(mode, icon):
    state = _describe({**BASE, "ALL_VIDEOS": [{"FilePath": "/a.mp4"}], "workspaceMode": mode})
    assert state["icon"] == icon
    assert state["actions"] == []
    assert state["hint"]


def test_search_term_is_escaped_into_the_hint():
    """Dateinamen-Suchen mit < oder & dürfen das Markup nicht brechen."""
    assert "escapeHtml(search)" in EMPTY_STATE_JS


# --- Verdrahtung ---

def test_script_is_loaded_and_ids_exist():
    assert "/static/empty_state.js" in DASHBOARD_PY
    for element_id in ("emptyState", "emptyStateIcon", "emptyStateTitle",
                       "emptyStateHint", "emptyStateActions"):
        assert f'id="{element_id}"' in DASHBOARD_PY


def test_render_paths_refresh_the_empty_state():
    """renderUI() und setLayout() müssen updateEmptyState() aufrufen."""
    engine = (STATIC_DIR / "engine.js").read_text(encoding="utf-8")
    workspace = (STATIC_DIR / "workspace.js").read_text(encoding="utf-8")
    assert "updateEmptyState()" in engine
    assert "updateEmptyState()" in workspace


def test_treemap_and_folderbrowser_never_show_the_grid_empty_state():
    assert "layout === 'grid' || layout === 'list'" in EMPTY_STATE_JS
