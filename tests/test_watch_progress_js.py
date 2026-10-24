"""
test_watch_progress_js.py
-------------------------
Die Browser-Seite von „Weiterschauen" (static/watch_progress.js).

Die Schwellen stehen maßgeblich im Server (test_watch_progress.py). Der Browser
spiegelt sie, damit Startseite und Player bis zur nächsten Antwort dasselbe
zeigen — dieser Test hält die Spiegelung ehrlich.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "watch_progress_harness.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")


@pytest.fixture(scope="module")
def out():
    proc = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_loads_from_server(out):
    assert out["loaded"] is True


def test_continue_watching_is_newest_first_and_only_known_media(out):
    """Gesehene (Position 0) und fremde Pfade gehören nicht in die Reihe."""
    assert out["continueOrder"] == ["/lib/new.mp4", "/lib/old.mp4"]


def test_resume_positions(out):
    assert out["resumeOld"] == 50
    assert out["resumeDone"] == 0
    assert out["ratioNew"] == pytest.approx(70 / 600)


def test_short_peek_is_neither_sent_nor_stored(out):
    assert out["shortPeekRequests"] == 0
    assert out["shortPeekStored"] is None


def test_record_posts_and_moves_to_the_front(out):
    assert out["postBody"] == {"path": "/lib/old.mp4", "position": 300, "duration": 600}
    assert out["continueAfterRecord"][0] == "/lib/old.mp4"


def test_near_the_end_counts_as_watched(out):
    assert out["finished"]["position"] == 0
    assert out["finished"]["watched"] is True


def test_clear(out):
    assert out["clearBody"] == {"path": "/lib/old.mp4", "clear": True}
    assert out["afterClear"] is None
