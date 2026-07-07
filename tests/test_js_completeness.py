"""
test_js_completeness.py
-----------------------
Contract tests: Ensures that every JS module in static/ is registered
in dashboard_template.py's script list, and vice versa — no orphaned
files, no missing modules.

Why this exists:
    After a refactor that split engine.js into many smaller modules,
    the new files (filter_engine.js, cards.js, workspace.js, etc.)
    existed on disk but were NOT included in the HTML template.
    The app loaded silently with missing functions → empty grid.

    Bidirectional checks prevent both:
      A) New file added to disk but forgotten in template → missing script
      B) Script listed in template pointing to a deleted/renamed file → 404
"""
import re
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"
TEMPLATE_FILE = (
    Path(__file__).parent.parent
    / "arcade_scanner"
    / "templates"
    / "dashboard_template.py"
)

# Files that are intentionally excluded from the template
# (vendored, loaded conditionally, or only used by other scripts)
EXCLUDED_FROM_TEMPLATE = {
    "aframe.min.js",   # loaded dynamically by vr_museum.js at runtime
    "vr_museum.js",    # loaded on-demand by VR Museum feature (WebXR, 45KB)
}

# Files that are listed in the template but may not follow the standard naming
# (e.g., CSS files referenced via <link>, not <script>)
TEMPLATE_NON_SCRIPT_REFS = set()


def get_template_js_files() -> set[str]:
    """Extract all JS filenames referenced in dashboard_template.py."""
    source = TEMPLATE_FILE.read_text(encoding="utf-8")
    # Match both /static/foo.js and foo.js?v=... patterns
    matches = re.findall(r'/static/([^"\'?]+\.js)', source)
    return set(matches)


def get_disk_js_files() -> set[str]:
    """Return all *.js filenames in the static directory."""
    return {f.name for f in STATIC_DIR.glob("*.js")}


class TestJsCompleteness:

    def test_all_disk_files_are_in_template(self):
        """Every JS file on disk must be listed in dashboard_template.py."""
        on_disk = get_disk_js_files() - EXCLUDED_FROM_TEMPLATE
        in_template = get_template_js_files()

        missing = on_disk - in_template
        assert not missing, (
            "The following JS files exist on disk but are NOT listed in "
            "dashboard_template.py — they will never be loaded by the browser:\n"
            + "\n".join(f"  • {f}" for f in sorted(missing))
        )

    def test_all_template_files_exist_on_disk(self):
        """Every JS file listed in dashboard_template.py must exist on disk."""
        on_disk = get_disk_js_files()
        in_template = get_template_js_files() - TEMPLATE_NON_SCRIPT_REFS

        phantom = in_template - on_disk
        assert not phantom, (
            "The following JS files are listed in dashboard_template.py "
            "but do NOT exist on disk — the browser will get a 404:\n"
            + "\n".join(f"  • {f}" for f in sorted(phantom))
        )

    def test_template_can_be_imported(self):
        """dashboard_template.py must be importable without errors."""
        import importlib
        try:
            import arcade_scanner.templates.dashboard_template as dt
            importlib.reload(dt)
        except Exception as e:
            pytest.fail(f"dashboard_template.py failed to import: {e}")

    def test_store_js_loads_before_engine_js(self):
        """store.js must appear before engine.js in the template (state before logic)."""
        source = TEMPLATE_FILE.read_text(encoding="utf-8")
        store_pos = source.find("store.js")
        engine_pos = source.find("engine.js")

        assert store_pos != -1, "store.js not found in template"
        assert engine_pos != -1, "engine.js not found in template"
        assert store_pos < engine_pos, (
            "store.js must be loaded BEFORE engine.js — "
            "engine.js depends on globals defined in store.js"
        )

    def test_filter_engine_loads_before_cards_js(self):
        """filter_engine.js must appear before cards.js (filterAndSort defined before use)."""
        source = TEMPLATE_FILE.read_text(encoding="utf-8")
        filter_pos = source.find("filter_engine.js")
        cards_pos = source.find("cards.js")

        if filter_pos == -1 or cards_pos == -1:
            pytest.skip("filter_engine.js or cards.js not in template")

        assert filter_pos < cards_pos, (
            "filter_engine.js must be loaded BEFORE cards.js — "
            "cards.js calls filterAndSort() which is defined in filter_engine.js"
        )
