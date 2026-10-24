"""
test_version_consistency.py
---------------------------
Es gibt genau eine Versionsnummer.

Vorher standen fünf verschiedene im Projekt:

| Ort | Wert |
|---|---|
| `pyproject.toml` | 4.9.0 |
| `main.py`, argparse-Beschreibung | 6.3 |
| `main.py`, Startbanner | 6.7 |
| `CHANGELOG.md`, letzter Abschnitt | 6.8.0 |
| `README.md` | 7.0.0 |

`CLAUDE.md` räumte das ausdrücklich ein: „Version numbers drift across files …
don't trust any single one as authoritative." Eine Doku, die ihre eigene
Unzuverlässigkeit festhält, beschreibt das Problem — sie löst es nicht.

7.0.0 ist der belegte Stand: Commit `e8dc9a9` („bump version to 7.0.0 with
AV1/ffmpeg 8.1 release notes") und `c22d11b` („update README for v7.0.0"). Die
Nummer wurde damals nur im README gesetzt.

Quelle ist jetzt `arcade_scanner.__version__`; `pyproject.toml` liest sie über
`[tool.setuptools.dynamic]`, `main.py` gibt sie aus.
"""
import re
from pathlib import Path

import pytest

from arcade_scanner import __version__

ROOT = Path(__file__).parent.parent

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_is_a_sane_semver():
    assert SEMVER.match(__version__), f"Unerwartetes Format: {__version__!r}"


def test_pyproject_reads_the_version_dynamically():
    """
    Der Wert darf dort nicht noch einmal stehen — genau so ist er auf 4.9.0
    stehen geblieben, während der Rest weiterzog.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'dynamic = ["version"]' in text
    assert 'version = {attr = "arcade_scanner.__version__"}' in text

    project_block = text.split("[project]", 1)[1].split("\n[", 1)[0]
    hardcoded = [
        line for line in project_block.splitlines()
        if line.strip().startswith("version =") and "attr" not in line
    ]
    assert not hardcoded, f"Version doppelt gepflegt: {hardcoded}"


def test_main_prints_the_single_source():
    """Banner und argparse-Beschreibung trugen zwei verschiedene Nummern."""
    text = (ROOT / "arcade_scanner" / "main.py").read_text(encoding="utf-8")

    assert "from arcade_scanner import __version__" in text
    assert "{__version__}" in text

    stale = re.findall(r"Arcade Media Scanner \d+\.\d+", text)
    assert not stale, f"Fest eingetragene Version in main.py: {stale}"


def test_readme_headline_matches():
    """
    Das README trug als einziges die richtige Nummer. Es soll sie behalten —
    aber gemeinsam mit dem Rest wandern.
    """
    first_line = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]
    assert __version__ in first_line, (
        f"README-Überschrift ({first_line!r}) nennt nicht {__version__}"
    )


def test_changelog_has_no_entry_for_this_version_yet():
    """
    Festgehalten, nicht behoben: Zu 7.0.0 gibt es keinen CHANGELOG-Abschnitt,
    obwohl die Version veröffentlicht wurde. Die zugehörigen Einträge zu
    erfinden wäre schlimmer als die Lücke — hier steht nur, dass sie besteht.

    Wird der Abschnitt nachgetragen, schlägt dieser Test fehl und gehört
    entfernt.
    """
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{__version__}]" not in changelog, (
        "Es gibt jetzt einen CHANGELOG-Abschnitt für diese Version — "
        "diesen Test bitte löschen."
    )


@pytest.mark.parametrize("stale", ["4.9.0", "6.3", "6.7"])
def test_the_old_numbers_are_gone_from_code_and_packaging(stale):
    """
    Gegenprobe: Die alten Werte dürfen in Paketierung und Startpfad nicht mehr
    auftauchen. Im CHANGELOG bleiben sie natürlich stehen — dort gehören sie hin.
    """
    for relative in ("pyproject.toml", "arcade_scanner/main.py"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        code_lines = [
            line for line in text.splitlines()
            if not line.strip().startswith("#")
        ]
        assert stale not in "\n".join(code_lines), f"{stale} steht noch in {relative}"
