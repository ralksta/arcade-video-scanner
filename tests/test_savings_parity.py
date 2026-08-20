"""Pins optimization_advisor's savings math to savings_parity.json.

The identical fixture lives in the videocrunch repo, which owns the encoder and
carries its own copy of this math. Both repos test against the same file, so a
change on either side fails the build on both.

DO NOT regenerate this fixture to make a failure go away. A failure means the
two implementations have diverged; decide deliberately which behaviour is
correct, change both, and update the fixture in both repos in the same breath.

Besides `estimate_savings_pct`, the fixture also pins the two bucketing helpers
(`bitrate_class` / `resolution_class`) and the listing threshold
`MIN_LISTED_SAVED_PCT` — all duplicated across the two repos, all silent when
they drift. Each repo's own boundary tests only ever check its own copy.
"""
import json
from pathlib import Path

import pytest

from arcade_scanner.core.optimization_advisor import (
    MIN_LISTED_SAVED_PCT,
    bitrate_class,
    estimate_savings_pct,
    resolution_class,
)

FIXTURE = Path(__file__).parent / "fixtures" / "savings_parity.json"
DATA = json.loads(FIXTURE.read_text())
CASES = DATA["estimate_savings_pct"]


def test_fixture_is_not_empty():
    assert len(CASES) >= 18


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['source_codec']}->{c['target_codec']}@{c['height']}p/{c['source_kbps']}k")
def test_matches_fixture(case):
    result = estimate_savings_pct(
        float(case["source_kbps"]), case["height"], float(case["fps"]),
        case["source_codec"], case["target_codec"])
    if case["expected"] is None:
        assert result is None
        return
    assert result is not None
    saved, known = result
    assert saved == pytest.approx(case["expected"][0], abs=1e-6)
    assert known is case["expected"][1]


@pytest.mark.parametrize("kbps,expected", DATA["bitrate_class"])
def test_bitrate_class_matches_fixture(kbps, expected):
    assert bitrate_class(float(kbps)) == expected


@pytest.mark.parametrize("height,expected", DATA["resolution_class"])
def test_resolution_class_matches_fixture(height, expected):
    assert resolution_class(int(height)) == expected


def test_min_listed_saved_pct_matches_fixture():
    assert MIN_LISTED_SAVED_PCT == DATA["constants"]["MIN_LISTED_SAVED_PCT"]
