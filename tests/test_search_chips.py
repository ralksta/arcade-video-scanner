"""
test_search_chips.py
--------------------
Der Collection-Dialog speichert weiterhin **einen** Suchtext, zeigt Ordner
und Tags aber als Chips. Diese Tests pinnen das Zerlegen und Zusammensetzen —
sonst würde eine Collection beim erneuten Öffnen anders aussehen oder anders
filtern als beim Speichern.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "search_chips_harness.js"
node = shutil.which("node")

pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


@pytest.fixture(scope="module")
def result():
    out = subprocess.run(
        [node, str(HARNESS)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


def test_paths_and_tags_become_chips_while_keywords_stay_in_the_field(result):
    mixed = result["mixed"]
    assert mixed["input"] == "web -trailer"
    assert mixed["chips"] == [
        {"type": "folder", "value": "/media/ralf/OD", "negated": False},
        {"type": "tag", "value": "Lady Sinister", "negated": False},
    ]


def test_chips_and_free_text_are_composed_back_into_one_query(result):
    assert result["mixed"]["composed"] == '/media/ralf/OD "#Lady Sinister" web -trailer'


def test_multiple_folder_chips_stay_separate_and_are_ored(result):
    multiple = result["multiplePaths"]
    assert multiple["chips"] == [
        {"type": "folder", "value": "/media/a", "negated": False},
        {"type": "folder", "value": "/media/b", "negated": False},
    ]
    # Ohne Leerzeichen im Pfad sind keine Anführungszeichen nötig.
    assert multiple["composed"] == "/media/a /media/b"


def test_plain_keywords_do_not_create_chips(result):
    assert result["freeOnly"] == {
        "input": "web -trailer",
        "chips": [],
        "composed": "web -trailer",
    }


def test_empty_search_stays_empty(result):
    assert result["empty"] == {"input": "", "chips": [], "composed": ""}
