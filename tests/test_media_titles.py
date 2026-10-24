"""
test_media_titles.py
--------------------
Anzeigetitel statt Dateinamen — in Browser und TV-Client gleich.

Auf Karten, Startseite und im Player stand der rohe Dateiname:
`VID_20251025_121813_115.mp4` statt „25. Okt. 2025 · 12:18“. Die Logik steht
zweimal (static/formatters.js, tv_client/src/displayName.js), weil die beiden
Clients keinen Code teilen; dieser Test hält sie deckungsgleich.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures" / "media_titles.json"
CASES = json.loads(FIXTURES.read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")


@pytest.fixture(scope="module")
def titles():
    proc = subprocess.run(["node", str(HERE / "media_title_harness.js"), str(FIXTURES)],
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize("index", range(len(CASES)), ids=[c[0] or "<leer>" for c in CASES])
def test_browser_title(titles, index):
    name, expected = CASES[index]
    assert titles["browser"][index] == expected


@pytest.mark.parametrize("index", range(len(CASES)), ids=[c[0] or "<leer>" for c in CASES])
def test_tv_title_matches_browser(titles, index):
    assert titles["tv"][index] == titles["browser"][index]
