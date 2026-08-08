# tests/test_criteria_parity.py
"""JS/Python parity: the same fixtures must evaluate identically in
collections.js (via Node vm) and core/criteria_eval.py."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from arcade_scanner.core.criteria_eval import video_matches

FIXTURES = Path(__file__).parent / "fixtures" / "criteria_parity.json"
HARNESS = Path(__file__).parent / "js_eval_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def _load():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_python_side_matches_expectations():
    data = _load()
    for case in data["cases"]:
        got = video_matches(case["video"], case["criteria"], now=data["now"])
        assert got is case["expected"], f"python mismatch: {case['name']}"


def test_js_side_matches_expectations_and_python():
    data = _load()
    out = subprocess.run(
        [node, str(HARNESS), str(FIXTURES)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    js_results = json.loads(out.stdout)
    assert len(js_results) == len(data["cases"])
    for case, js_result in zip(data["cases"], js_results):
        assert js_result is case["expected"], f"js mismatch: {case['name']}"
        py_result = video_matches(case["video"], case["criteria"], now=data["now"])
        assert js_result is py_result, f"drift: {case['name']}"
