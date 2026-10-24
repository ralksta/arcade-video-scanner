"""
test_tv_collection_parity.py
----------------------------
Der TV-Client bewertet Smart Collections **genau** wie der Browser.

Dieselbe Semantik existiert im Projekt dreimal: im Browser
(`collections.js`), serverseitig (`core/criteria_eval.py`, per
`test_criteria_parity.py` an den Browser gepinnt) und im TV-Client
(`tv_client/src/collectionMatch.js`).

Bis 2026-10-02 durfte der TV-Client Medientyp, Format, Auflösung,
Ausrichtung, Größe, Dauer und Datum überspringen („mehr Treffer sind
erklärbar“). Auf dem Fernseher zeigte damit jede Standard-Collection alle
5458 Videos, „All Photos“ in einer Bibliothek ohne Fotos eingeschlossen.
Die Collections werden im Browser definiert; der Fernseher wertet sie nur
aus und muss deshalb alle Dimensionen kennen. Jetzt: exakte Übereinstimmung
für jede Fixture.

Früher gefunden: Der TV-Client las `v.status`, die API liefert `Status`.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "criteria_parity.json"
BROWSER_HARNESS = Path(__file__).parent / "js_eval_harness.js"
TV_HARNESS = Path(__file__).parent / "tv_eval_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")

def _run(harness: Path) -> list[bool]:
    out = subprocess.run(
        [node, str(harness), str(FIXTURES)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


MATCHER = Path(__file__).parent.parent / "tv_client" / "src" / "collectionMatch.js"


def _matcher_code() -> str:
    """Der Matcher ohne Kommentare — die nennen den alten Fehler beim Namen."""
    return "\n".join(
        line for line in MATCHER.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("//")
    )


@pytest.fixture(scope="module")
def evaluated():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data, _run(BROWSER_HARNESS), _run(TV_HARNESS)


def test_both_harnesses_cover_all_fixtures(evaluated):
    data, browser, tv = evaluated
    assert len(browser) == len(data["cases"])
    assert len(tv) == len(data["cases"])


def test_every_fixture_agrees(evaluated):
    """Gleiches Urteil wie der Browser — für jede Dimension, ohne Ausnahme."""
    data, browser, tv = evaluated
    drift = [f"{case['name']}: Browser={want} TV={got}"
             for case, want, got in zip(data["cases"], browser, tv) if want != got]
    assert not drift, "TV-Client weicht vom Browser ab:\n  " + "\n  ".join(drift)


def test_the_panel_uses_the_shared_matcher():
    panel = (Path(__file__).parent.parent / "tv_client" / "src" / "views" / "MainPanel.js").read_text(
        encoding="utf-8")
    assert "from '../collectionMatch'" in panel
    assert "const matchesCollectionCriteria" not in panel, "Eine zweite Kopie im Panel"


def test_status_is_read_from_the_capitalised_field():
    """
    Der eigentliche Fund. `v.status` ist immer undefined, weil die API `Status`
    liefert — ein Tippfehler, der das Verhalten umkehrt statt es zu brechen.
    """
    matcher = _matcher_code()

    assert ".Status" in matcher
    # Nur am Eintrag — `inc.status`/`exc.status` sind Felder der Kriterien.
    assert not re.search(r"\b(?:v|video)\.status\b", matcher), (
        "Kleingeschriebenes .status am Eintrag ist wieder da")


def test_codec_matching_is_substring_based():
    """
    Die API liefert auch Werte wie „hevc (Main 10)". Der Browser prüft per
    Teilstring; ein exakter Vergleich verfehlt genau die Dateien, um die es geht.
    """
    assert "codec.includes(c.toLowerCase())" in _matcher_code()
