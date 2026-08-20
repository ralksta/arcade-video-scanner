"""Pins optimization_advisor's savings math to savings_parity.json.

The identical fixture lives in the videocrunch repo, which owns the encoder and
carries its own copy of this math. Both repos test against the same file, so a
change on either side fails the build on both.

DO NOT regenerate this fixture to make a failure go away. A failure means the
two implementations have diverged; decide deliberately which behaviour is
correct, change both, and update the fixture in both repos in the same breath.
"""
import json
from pathlib import Path

import pytest

from arcade_scanner.core.optimization_advisor import estimate_savings_pct

FIXTURE = Path(__file__).parent / "fixtures" / "savings_parity.json"
CASES = json.loads(FIXTURE.read_text())


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
