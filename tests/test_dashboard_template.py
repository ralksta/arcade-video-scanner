"""
test_dashboard_template.py
---------------------------
Integration tests: Exercises generate_html_report() end-to-end and
validates the produced HTML shell is well-formed and complete.

Why this exists:
    The HTML report is the single entry point for the browser.
    Bugs here (missing scripts, broken f-string escaping, wrong
    cache-buster placeholders) silently produce a broken page.

What is checked:
    - Template generates valid HTML without exceptions
    - Every <script src> URL in the output resolves to an existing file
    - Cache-busters are real Unix timestamps (not literal Python code)
    - Core JS globals are declared in the inline <script> block
    - No duplicate <script src> for the same file
"""
import re
import time
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"
REPORT_DIR = Path(__file__).parent.parent / "arcade_data"


@pytest.fixture(scope="module")
def generated_html(tmp_path_factory):
    """Generate a fresh HTML report into a temp file and return its content."""
    from arcade_scanner.templates.dashboard_template import generate_html_report

    out_file = tmp_path_factory.mktemp("reports") / "index.html"
    # Minimal stub results — we only care about the HTML shell here
    stub_results = [
        {
            "FilePath": "/tmp/test_video.mp4",
            "Size_MB": 100.0,
            "Bitrate_Mbps": 4.0,
            "Duration_Sec": 120.0,
            "Resolution": "1920x1080",
            "codec": "h264",
            "Status": "HIGH",
            "thumb": "placeholder.jpg",
            "favorite": False,
            "hidden": False,
            "tags": [],
            "mtime": int(time.time()),
            "imported_at": int(time.time()),
            "media_type": "video",
        }
    ]
    generate_html_report(stub_results, str(out_file), server_port=8000)
    return out_file.read_text(encoding="utf-8")


class TestDashboardTemplateOutput:

    def test_html_is_generated_without_exception(self, generated_html):
        """generate_html_report must complete without raising."""
        assert len(generated_html) > 1000, "Generated HTML suspiciously short"

    def test_all_script_src_files_exist(self, generated_html):
        """Every <script src='/static/X.js?v=...'>  must point to an existing file."""
        # Extract all /static/*.js references
        script_srcs = re.findall(r'src=["\']\/static\/([^"\'?]+\.js)', generated_html)
        missing = []
        for filename in script_srcs:
            path = STATIC_DIR / filename
            if not path.exists():
                missing.append(filename)

        assert not missing, (
            "The following script files are referenced in the generated HTML "
            "but do NOT exist on disk (browser will get a 404):\n"
            + "\n".join(f"  • {f}" for f in sorted(missing))
        )

    def test_cache_busters_are_real_timestamps(self, generated_html):
        """
        Cache-buster query params must be real Unix timestamps, not Python
        source code like `{int(time.time())}` (which happens when f-string
        escaping is wrong with double braces).
        """
        # Should NOT contain literal Python expressions
        assert "{int(time.time())}" not in generated_html, (
            "The HTML contains a literal '{int(time.time())}' string — "
            "the f-string escaping in dashboard_template.py is broken. "
            "Use single braces {int(time.time())} inside the f-string, not double."
        )

        # Should contain plausible timestamps (10-digit Unix timestamps)
        ts_values = re.findall(r'\?v=(\d+)', generated_html)
        current_ts = int(time.time())
        assert ts_values, "No cache-buster timestamps found in generated HTML"
        for ts in ts_values:
            val = int(ts)
            # Must be within the last year and not in the future (+1min tolerance)
            assert current_ts - 86400 * 365 < val <= current_ts + 60, (
                f"Cache-buster timestamp {val} looks invalid (expected ~{current_ts})"
            )

    def test_no_duplicate_script_tags(self, generated_html):
        """Each JS file must appear at most once in the generated HTML."""
        script_srcs = re.findall(r'src=["\']\/static\/([^"\'?]+\.js)', generated_html)
        seen = set()
        duplicates = []
        for src in script_srcs:
            if src in seen:
                duplicates.append(src)
            seen.add(src)

        assert not duplicates, (
            "The following JS files are included more than once:\n"
            + "\n".join(f"  • {f}" for f in sorted(set(duplicates)))
        )

    def test_core_js_globals_are_declared(self, generated_html):
        """
        The inline <script> block must declare the expected global
        variables that JS modules depend on at startup.
        """
        required_globals = [
            "window.ALL_VIDEOS",
            "window.SERVER_PORT",
            "window.userSettings",
        ]
        for glob in required_globals:
            assert glob in generated_html, (
                f"Expected global '{glob}' not found in generated HTML — "
                "JS modules that reference it at load time will crash."
            )

    def test_store_js_before_engine_js_in_html(self, generated_html):
        """store.js (state management) must be loaded before engine.js."""
        store_pos = generated_html.find("store.js")
        engine_pos = generated_html.find("engine.js")
        assert store_pos != -1, "store.js not in generated HTML"
        assert engine_pos != -1, "engine.js not in generated HTML"
        assert store_pos < engine_pos, (
            "store.js must appear before engine.js in the generated HTML"
        )

    def test_filter_engine_before_cards_in_html(self, generated_html):
        """filter_engine.js must be loaded before cards.js."""
        filter_pos = generated_html.find("filter_engine.js")
        cards_pos = generated_html.find("cards.js")
        if filter_pos == -1 or cards_pos == -1:
            pytest.skip("filter_engine.js or cards.js not in HTML")
        assert filter_pos < cards_pos, (
            "filter_engine.js must appear before cards.js in the generated HTML"
        )
