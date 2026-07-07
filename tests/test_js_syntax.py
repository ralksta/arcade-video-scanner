"""
test_js_syntax.py
-----------------
Contract test: Every JS file in the static/ directory must be
syntactically valid JavaScript.

Why this exists:
    During refactoring, a JS file (filter_engine.js) was saved
    mid-edit with an unclosed function body. The browser loaded it
    silently, causing the entire application grid to be empty.
    `node --check` catches this class of bug in milliseconds,
    without needing a browser.

What is checked:
    - All *.js files in arcade_scanner/server/static/ (excl. aframe.min.js)
    - Parsed with `node --check` (V8 syntax validation, no execution)
    - Any SyntaxError → test fails with the node error message
"""
import subprocess
import shutil
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"

# Exclude known large vendored bundles that are pre-minified and always valid
EXCLUDE = {"aframe.min.js"}


def all_js_files():
    return [
        f for f in sorted(STATIC_DIR.glob("*.js"))
        if f.name not in EXCLUDE
    ]


def pytest_generate_tests(metafunc):
    if "js_file" in metafunc.fixturenames:
        metafunc.parametrize("js_file", all_js_files(), ids=lambda f: f.name)


@pytest.fixture(scope="session")
def node_binary():
    binary = shutil.which("node")
    if not binary:
        pytest.skip("node not found in PATH — skipping JS syntax checks")
    return binary


def test_js_syntax_valid(js_file, node_binary):
    """Each JS file must pass `node --check` (syntax validation only, no execution)."""
    result = subprocess.run(
        [node_binary, "--check", str(js_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Syntax error in {js_file.name}:\n{result.stderr.strip()}"
    )
