"""
test_tv_collection_parity.py
----------------------------
Der TV-Client bewertet Smart Collections wie der Browser — soweit er die
jeweilige Dimension überhaupt kennt.

Dieselbe Semantik existiert im Projekt dreimal: im Browser
(`collections.js`), serverseitig (`core/criteria_eval.py`, per
`test_criteria_parity.py` an den Browser gepinnt) und im TV-Client
(`MainPanel.js`). Die dritte Kopie hing an nichts.

Gefunden wurde dabei ein echter Bruch: der TV-Client las `v.status`, die API
liefert das Feld aber als `Status`. Der Wert war also immer `undefined` —
`'optimized'` traf nie, `'pending'` traf immer. Dieselbe Sammlung zeigte auf
dem Fernseher nichts oder alles, im Browser das Richtige.

Der TV-Client deckt bewusst nur einen Teil der Dimensionen ab: seine
Oberfläche bietet keine Auswahl nach Medientyp, Format, Auflösung,
Ausrichtung, Größe oder Dauer. Für Fixtures, die darauf beruhen, wird deshalb
nur geprüft, dass er nicht *strenger* filtert als der Browser — mehr Treffer
sind erklärbar, weniger wären ein Fehler.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "criteria_parity.json"
BROWSER_HARNESS = Path(__file__).parent / "js_eval_harness.js"
TV_HARNESS = Path(__file__).parent / "tv_eval_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")

# Dimensionen, die die TV-Oberfläche nicht anbietet.
TV_UNSUPPORTED = {"media_type", "format", "resolution", "orientation",
                  "size", "duration", "date"}


def _run(harness: Path) -> list[bool]:
    out = subprocess.run(
        [node, str(harness), str(FIXTURES)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


def _matcher_code(source: str) -> str:
    """Der Rumpf von matchesCollectionCriteria ohne Kommentare.

    Kommentare erklären den behobenen Fehler und nennen dabei die alte
    Schreibweise — eine reine Textsuche würde daran hängenbleiben.
    """
    block = source.split("const matchesCollectionCriteria", 1)[1].split("\nconst ", 1)[0]
    return "\n".join(
        line for line in block.splitlines() if not line.strip().startswith("//")
    )


def _dimensions(criteria: dict) -> set[str]:
    used = set()
    for side in ("include", "exclude"):
        used |= set((criteria.get(side) or {}).keys())
    used |= {k for k in criteria if k not in ("include", "exclude")}
    return used


@pytest.fixture(scope="module")
def evaluated():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data, _run(BROWSER_HARNESS), _run(TV_HARNESS)


def test_both_harnesses_cover_all_fixtures(evaluated):
    data, browser, tv = evaluated
    assert len(browser) == len(data["cases"])
    assert len(tv) == len(data["cases"])


def test_supported_dimensions_agree(evaluated):
    """Wo der TV-Client die Dimension kennt, muss er dasselbe Urteil fällen."""
    data, browser, tv = evaluated
    drift = []
    for case, want, got in zip(data["cases"], browser, tv):
        if _dimensions(case["criteria"]) & TV_UNSUPPORTED:
            continue
        if want != got:
            drift.append(f"{case['name']}: Browser={want} TV={got}")

    assert not drift, "TV-Client weicht bei unterstützten Dimensionen ab:\n  " + "\n  ".join(drift)


def test_unsupported_dimensions_are_never_stricter(evaluated):
    """
    Was der TV-Client nicht auswerten kann, darf er nicht zum Ausschluss
    verwenden: mehr Treffer sind erklärbar, fehlende wären ein Fehler.
    """
    data, browser, tv = evaluated
    too_strict = []
    for case, want, got in zip(data["cases"], browser, tv):
        if not (_dimensions(case["criteria"]) & TV_UNSUPPORTED):
            continue
        if want and not got:
            too_strict.append(case["name"])

    assert not too_strict, (
        "TV-Client schließt Videos aus, die der Browser zeigt:\n  " + "\n  ".join(too_strict)
    )


def test_status_is_read_from_the_capitalised_field():
    """
    Der eigentliche Fund. `v.status` ist immer undefined, weil die API `Status`
    liefert — ein Tippfehler, der das Verhalten umkehrt statt es zu brechen.
    """
    source = (Path(__file__).parent.parent / "tv_client" / "src" / "views" / "MainPanel.js").read_text(
        encoding="utf-8"
    )
    matcher = _matcher_code(source)

    assert "v.Status" in matcher
    assert "v.status" not in matcher, "Kleingeschriebenes v.status ist wieder da"


def test_codec_matching_is_substring_based():
    """
    Die API liefert auch Werte wie „hevc (Main 10)". Der Browser prüft per
    Teilstring; ein exakter Vergleich verfehlt genau die Dateien, um die es geht.
    """
    source = (Path(__file__).parent.parent / "tv_client" / "src" / "views" / "MainPanel.js").read_text(
        encoding="utf-8"
    )
    assert "codec.includes(c.toLowerCase())" in _matcher_code(source)


def test_unsupported_dimensions_are_documented_in_the_client():
    """Damit der nächste Mensch die Abweichung als Absicht erkennt."""
    source = (Path(__file__).parent.parent / "tv_client" / "src" / "views" / "MainPanel.js").read_text(
        encoding="utf-8"
    )
    for dimension in ("media_type", "format", "resolution", "orientation"):
        assert dimension in source, f"{dimension} ist nicht als unbedeckt vermerkt"
