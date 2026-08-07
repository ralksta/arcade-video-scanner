# Optimizer Candidates View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/candidates` view ranking the library by expected re-encode savings (heuristic + real encode history), with direct add-to-queue actions.

**Architecture:** A pure-logic advisor module in `arcade_scanner/core/` scores every video (bitrate-per-pixel heuristic, overridden by median real `saved_pct` from `encode_history.jsonl` when a bucket has ≥3 samples). A new session-guarded route serves the ranked list; a new frontend view (cloned from the duplicates-view pattern) renders it and queues files via the existing encoding queue. A new `optimized_at` column marks finished files.

**Tech Stack:** Python stdlib + pydantic (server), vanilla JS (frontend), SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-08-07-optimizer-candidates-design.md`

## Global Constraints

- No new runtime dependencies (server deps stay: pydantic, Pillow, imagehash).
- CI is blocking: `.venv/bin/ruff check .` and `.venv/bin/mypy` must pass; all new code fully type-annotated. Line length 100 (E501 ignored, but stay reasonable).
- Tests: `.venv/bin/pytest` (testpaths = tests/). JS files must pass `node --check` (`tests/test_js_syntax.py`) and the DOM contract (`tests/test_dom_contract.py`).
- Conventional commits with scope (`feat(web): ...`, `feat(core): ...`). Work on the feature branch (worktree), not `dev` directly.
- Comments may be German or English.
- `INSERT OR REPLACE` upsert semantics: every media column MUST be in `_COLUMNS` + `VideoEntry` + `_entry_to_tuple` + `_row_to_api_dict`, and per-file user state must be re-copied in the scanner merge (`manager.py`) — otherwise a rescan wipes it.

---

### Task 1: Advisor core — classifiers + heuristic estimate

**Files:**
- Create: `arcade_scanner/core/optimization_advisor.py`
- Test: `tests/test_optimization_advisor.py`

**Interfaces:**
- Consumes: `CODEC_EFFICIENCY` from `arcade_scanner/core/bitrate_analyzer.py:25`; `VideoEntry` from `arcade_scanner/models/video_entry.py`.
- Produces: `bitrate_class(kbps: float) -> str`, `resolution_class(height: int) -> str`, `estimate_heuristic(entry: VideoEntry, target_codec: str) -> tuple[float, bool] | None` (saved_pct 0–100, known-codec-pair flag), dataclass `CandidateEstimate(file_path, size_mb, codec, width, height, bitrate_mbps, thumb, estimated_saved_mb, estimated_saved_pct, confidence, source, reason)`.

Note on the bucket helpers: `resolution_class`/`bitrate_class` exist in `scripts/optimizer_utils.py:22-41`. That module is deliberately import-standalone for the optimizer scripts, so we DUPLICATE the two tiny functions here and pin them with a parity test (Task decision per spec; do NOT import from `scripts/` in server code).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_optimization_advisor.py
"""Unit tests for the optimization advisor (pure logic, no ffmpeg/fs)."""
from arcade_scanner.core import optimization_advisor as adv
from arcade_scanner.models.video_entry import VideoEntry
from scripts import optimizer_utils


def _entry(**kw) -> VideoEntry:
    base = dict(file_path="/lib/a.mp4", size_mb=1000.0, bitrate_mbps=45.0,
                codec="h264", width=3840, height=2160, frame_rate=30.0,
                media_type="video")
    base.update(kw)
    return VideoEntry(**base)


def test_bucket_helpers_parity_with_optimizer_utils():
    for kbps in (0, 1000, 2499, 2500, 7999, 8000, 19999, 20000, 50000):
        assert adv.bitrate_class(kbps) == optimizer_utils.bitrate_class(kbps)
    for h in (0, 480, 576, 577, 720, 800, 801, 1080, 1200, 1201, 1440, 1600, 1601, 2160):
        assert adv.resolution_class(h) == optimizer_utils.resolution_class(h)


def test_heuristic_high_bitrate_4k_h264_saves_a_lot():
    result = adv.estimate_heuristic(_entry(), "hevc")
    assert result is not None
    saved_pct, known = result
    assert known is True
    assert saved_pct > 60  # 45 Mbit/s 4K h264 is far above the ~12 Mbit/s reference


def test_heuristic_lean_1080p_h264_saves_moderately():
    result = adv.estimate_heuristic(
        _entry(bitrate_mbps=3.5, width=1920, height=1080), "hevc")
    assert result is not None
    saved_pct, _ = result
    assert 20 < saved_pct < 50  # bounded by the codec factor, not the reference


def test_heuristic_same_codec_saves_little():
    fat = adv.estimate_heuristic(_entry(), "hevc")
    same = adv.estimate_heuristic(_entry(codec="hevc"), "hevc")
    assert same is not None and fat is not None
    assert same[0] < fat[0]


def test_heuristic_av1_target_beats_hevc_target():
    h = adv.estimate_heuristic(_entry(), "hevc")
    a = adv.estimate_heuristic(_entry(), "av1")
    assert a is not None and h is not None
    assert a[0] >= h[0]


def test_heuristic_unknown_codec_pair_flagged():
    result = adv.estimate_heuristic(_entry(codec="prores"), "hevc")
    assert result is not None
    assert result[1] is False


def test_heuristic_missing_data_returns_none():
    assert adv.estimate_heuristic(_entry(bitrate_mbps=0.0), "hevc") is None
    assert adv.estimate_heuristic(_entry(height=0), "hevc") is None


def test_heuristic_savings_capped():
    result = adv.estimate_heuristic(_entry(bitrate_mbps=200.0), "hevc")
    assert result is not None
    assert result[0] <= 85.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_optimization_advisor.py -v`
Expected: FAIL / errors with "No module named 'arcade_scanner.core.optimization_advisor'"

- [ ] **Step 3: Write the implementation**

```python
# arcade_scanner/core/optimization_advisor.py
"""Optimization advisor — ranks videos by expected savings from re-encoding.

Pure logic (no ffmpeg/subprocess): unit-testable, consumed by the
/api/candidates route. Heuristic baseline from bitrate-per-resolution +
codec efficiency; overridden by real results from encode_history.jsonl
(written by scripts/video_optimizer.py) when a bucket has enough samples.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models.video_entry import VideoEntry
from .bitrate_analyzer import CODEC_EFFICIENCY

DEFAULT_HISTORY_PATH = Path.home() / ".arcade-scanner" / "logs" / "encode_history.jsonl"

# --- bucket helpers -------------------------------------------------------
# Deliberately duplicated from scripts/optimizer_utils.py (that module stays
# import-standalone for the optimizer scripts); parity is pinned by
# tests/test_optimization_advisor.py::test_bucket_helpers_parity_with_optimizer_utils.


def bitrate_class(kbps: float) -> str:
    if kbps < 2500:
        return "low"
    if kbps < 8000:
        return "med"
    if kbps < 20000:
        return "high"
    return "ultra"


def resolution_class(height: int) -> str:
    if height <= 576:
        return "sd"
    if height <= 800:
        return "720"
    if height <= 1200:
        return "1080"
    if height <= 1600:
        return "1440"
    return "2160"


# --- heuristic ------------------------------------------------------------

# Reference bitrates (kbps) for a well-compressed HEVC encode at ~30 fps.
_REF_KBPS = {"sd": 1500.0, "720": 2500.0, "1080": 4000.0, "1440": 8000.0, "2160": 12000.0}
_AV1_REF_FACTOR = 0.85    # AV1 hits the same quality a bit leaner
_SAME_CODEC_EFF = 0.85    # re-encoding within the same codec gains little
_DEFAULT_EFF = 0.65       # unknown source codec: assume h264-like gains
_MAX_SAVED_PCT = 85.0     # never predict more than this
_TARGET_ALIASES = {"hevc": {"hevc", "h265"}, "av1": {"av1"}}


def _codec_efficiency(source_codec: str, target_codec: str) -> tuple[float, bool]:
    """(bitrate multiplier source→target, is the pair actually known?)."""
    src = (source_codec or "").lower()
    if src in _TARGET_ALIASES.get(target_codec, {target_codec}):
        return _SAME_CODEC_EFF, True
    eff = CODEC_EFFICIENCY.get((src, target_codec))
    if eff is not None:
        return eff, True
    return _DEFAULT_EFF, False


def estimate_heuristic(entry: VideoEntry, target_codec: str) -> Optional[tuple[float, bool]]:
    """Estimated saved percentage (0-100) for re-encoding `entry`.

    Returns (saved_pct, known_codec_pair) or None when the entry lacks the
    metadata to say anything (no bitrate / no height from ffprobe).
    """
    source_kbps = (entry.bitrate_mbps or 0.0) * 1000.0
    height = entry.height or 0
    if source_kbps <= 0 or height <= 0:
        return None

    eff, known = _codec_efficiency(entry.codec or "", target_codec)

    ref = _REF_KBPS[resolution_class(height)]
    if target_codec == "av1":
        ref *= _AV1_REF_FACTOR
    fps = entry.frame_rate or 0.0
    if fps > 0:
        ref *= min(max(fps / 30.0, 0.5), 2.0)

    # Predicted output: codec factor applied to the source, but never above
    # what a clean target-codec encode needs at this resolution (`ref`).
    predicted_kbps = min(source_kbps * eff, max(ref, source_kbps * (1 - _MAX_SAVED_PCT / 100)))
    saved_pct = max(0.0, (1.0 - predicted_kbps / source_kbps) * 100.0)
    return min(saved_pct, _MAX_SAVED_PCT), known


@dataclass
class CandidateEstimate:
    file_path: str
    size_mb: float
    codec: str
    width: int
    height: int
    bitrate_mbps: float
    thumb: str
    estimated_saved_mb: float
    estimated_saved_pct: float
    confidence: str  # "high" | "medium" | "low"
    source: str      # "history" | "heuristic"
    reason: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_optimization_advisor.py -v`
Expected: all PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner/core/optimization_advisor.py tests/test_optimization_advisor.py
.venv/bin/mypy arcade_scanner/core/optimization_advisor.py
git add arcade_scanner/core/optimization_advisor.py tests/test_optimization_advisor.py
git commit -m "feat(core): optimization advisor — heuristic savings estimate"
```

---

### Task 2: Advisor core — encode history override

**Files:**
- Modify: `arcade_scanner/core/optimization_advisor.py` (append)
- Test: `tests/test_optimization_advisor.py` (append)

**Interfaces:**
- Consumes: history JSONL records as written by `scripts/video_optimizer.py:2043-2053`: `{ts, file, encoder, codec, height, source_kbps, q, ssim, saved_pct}`. `saved_pct` is a percentage 0–100. `codec` holds encoder-profile names like `hevc_nvenc`, `libx265`, `av1_nvenc` — target matching is by substring.
- Produces: `class EncodeHistory` with `__init__(self, path: Path = DEFAULT_HISTORY_PATH)` and `median_saved_pct(self, target_codec: str, height: int, source_kbps: float, min_samples: int = 3) -> Optional[tuple[float, int]]` returning (median saved_pct, sample count). Reload is mtime-cached.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_optimization_advisor.py
import json


def _write_history(tmp_path, records):
    p = tmp_path / "encode_history.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


def _rec(**kw):
    base = dict(ts="2026-08-01T00:00:00", file="x.mp4", encoder="hevc_nvenc",
                codec="hevc_nvenc", height=2160, source_kbps=45000, q=30,
                ssim=0.97, saved_pct=70.0)
    base.update(kw)
    return base


def test_history_median_with_enough_samples(tmp_path):
    p = _write_history(tmp_path, [_rec(saved_pct=60.0), _rec(saved_pct=70.0),
                                  _rec(saved_pct=80.0)])
    h = adv.EncodeHistory(p)
    result = h.median_saved_pct("hevc", 2160, 45000)
    assert result == (70.0, 3)


def test_history_too_few_samples_returns_none(tmp_path):
    p = _write_history(tmp_path, [_rec(), _rec()])
    assert adv.EncodeHistory(p).median_saved_pct("hevc", 2160, 45000) is None


def test_history_bucket_mismatch_returns_none(tmp_path):
    p = _write_history(tmp_path, [_rec(), _rec(), _rec()])
    h = adv.EncodeHistory(p)
    assert h.median_saved_pct("hevc", 720, 45000) is None      # other resolution class
    assert h.median_saved_pct("hevc", 2160, 3000) is None      # other bitrate class


def test_history_target_codec_matching(tmp_path):
    p = _write_history(tmp_path, [
        _rec(codec="av1_nvenc", saved_pct=80.0), _rec(codec="av1_nvenc", saved_pct=80.0),
        _rec(codec="av1_nvenc", saved_pct=80.0),
        _rec(codec="libx265", saved_pct=50.0), _rec(codec="libx265", saved_pct=50.0),
        _rec(codec="libx265", saved_pct=50.0),
    ])
    h = adv.EncodeHistory(p)
    assert h.median_saved_pct("av1", 2160, 45000) == (80.0, 3)
    assert h.median_saved_pct("hevc", 2160, 45000) == (50.0, 3)


def test_history_corrupt_lines_and_missing_file(tmp_path):
    p = tmp_path / "encode_history.jsonl"
    p.write_text('not json\n{"broken": \n' + json.dumps(_rec()) + "\n", encoding="utf-8")
    assert adv.EncodeHistory(p).median_saved_pct("hevc", 2160, 45000) is None  # 1 < 3
    missing = adv.EncodeHistory(tmp_path / "nope.jsonl")
    assert missing.median_saved_pct("hevc", 2160, 45000) is None


def test_history_mtime_cache_reloads_on_change(tmp_path):
    p = _write_history(tmp_path, [_rec(), _rec(), _rec()])
    h = adv.EncodeHistory(p)
    assert h.median_saved_pct("hevc", 2160, 45000) is not None
    import os
    _write_history(tmp_path, [_rec(saved_pct=10.0)] * 3)
    os.utime(p, (1, 1))  # force a different mtime either way
    assert h.median_saved_pct("hevc", 2160, 45000) == (10.0, 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_optimization_advisor.py -k history -v`
Expected: FAIL with "has no attribute 'EncodeHistory'"

- [ ] **Step 3: Write the implementation**

```python
# append to arcade_scanner/core/optimization_advisor.py

# History `codec` holds encoder-profile names (hevc_nvenc, libx265, av1_nvenc…);
# match the requested target codec by substring.
_TARGET_SUBSTRINGS = {"hevc": ("hevc", "265"), "av1": ("av1",)}


class EncodeHistory:
    """mtime-cached reader over encode_history.jsonl (best-effort, never raises)."""

    def __init__(self, path: Path = DEFAULT_HISTORY_PATH) -> None:
        self.path = path
        self._mtime: float = -1.0
        self._records: list[dict] = []

    def _load(self) -> list[dict]:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            self._records = []
            self._mtime = -1.0
            return self._records
        if mtime == self._mtime:
            return self._records
        records: list[dict] = []
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(rec, dict) and rec.get("saved_pct") is not None:
                        records.append(rec)
        except OSError:
            records = []
        self._records = records
        self._mtime = mtime
        return self._records

    def median_saved_pct(self, target_codec: str, height: int, source_kbps: float,
                         min_samples: int = 3) -> Optional[tuple[float, int]]:
        """Median real saved_pct for the (target, resolution class, bitrate class) bucket."""
        substrings = _TARGET_SUBSTRINGS.get(target_codec, (target_codec,))
        want = (resolution_class(height), bitrate_class(source_kbps))
        samples: list[float] = []
        for rec in self._load():
            codec_str = f"{rec.get('codec', '')}{rec.get('encoder', '')}".lower()
            if not any(s in codec_str for s in substrings):
                continue
            try:
                key = (resolution_class(int(rec.get("height", 0))),
                       bitrate_class(float(rec.get("source_kbps", 0))))
                if key == want:
                    samples.append(float(rec["saved_pct"]))
            except (TypeError, ValueError):
                continue
        if len(samples) < min_samples:
            return None
        return (float(statistics.median(samples)), len(samples))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_optimization_advisor.py -v`
Expected: all PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner tests
.venv/bin/mypy arcade_scanner/core/optimization_advisor.py
git add arcade_scanner/core/optimization_advisor.py tests/test_optimization_advisor.py
git commit -m "feat(core): encode-history override for savings estimates"
```

---

### Task 3: Advisor core — build_candidates (ranking + exclusions + summary)

**Files:**
- Modify: `arcade_scanner/core/optimization_advisor.py` (append)
- Test: `tests/test_optimization_advisor.py` (append)

**Interfaces:**
- Consumes: Tasks 1+2 (`estimate_heuristic`, `EncodeHistory`, `CandidateEstimate`); `VideoEntry.optimized_at` (Task 4 adds it — until then `getattr(entry, "optimized_at", 0)` is used, keep that spelling so Task 3 works standalone).
- Produces: `build_candidates(entries: list[VideoEntry], target_codec: str, history: EncodeHistory, exclude_paths: set[str], limit: int = 100) -> dict` returning `{"summary": {"total_files", "total_estimated_saved_mb", "history_based"}, "results": [dict, ...]}` (results are `CandidateEstimate.__dict__` copies, sorted by `estimated_saved_mb` desc). Summary totals cover ALL candidates, results are capped at `limit`. `MIN_LISTED_SAVED_PCT = 10.0`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_optimization_advisor.py

def _empty_history(tmp_path):
    return adv.EncodeHistory(tmp_path / "none.jsonl")


def test_build_candidates_sorted_by_absolute_mb(tmp_path):
    entries = [
        _entry(file_path="/lib/small.mp4", size_mb=100.0),            # ~same pct, less MB
        _entry(file_path="/lib/big.mp4", size_mb=8000.0),
        _entry(file_path="/lib/lean.mp4", size_mb=5000.0, bitrate_mbps=1.2,
               width=1280, height=720),                                # < 10% → dropped
    ]
    out = adv.build_candidates(entries, "hevc", _empty_history(tmp_path), set())
    paths = [r["file_path"] for r in out["results"]]
    assert paths == ["/lib/big.mp4", "/lib/small.mp4"]
    assert out["results"][0]["estimated_saved_mb"] > out["results"][1]["estimated_saved_mb"]


def test_build_candidates_exclusions(tmp_path):
    entries = [
        _entry(file_path="/lib/queued.mp4"),
        _entry(file_path="/lib/done.mp4", optimized_at=1723000000),
        _entry(file_path="/lib/photo.jpg", media_type="image"),
        _entry(file_path="/lib/nodata.mp4", bitrate_mbps=0.0),
        _entry(file_path="/lib/ok.mp4"),
    ]
    out = adv.build_candidates(entries, "hevc", _empty_history(tmp_path),
                               exclude_paths={"/lib/queued.mp4"})
    assert [r["file_path"] for r in out["results"]] == ["/lib/ok.mp4"]


def test_build_candidates_history_beats_heuristic(tmp_path):
    p = _write_history(tmp_path, [_rec(saved_pct=40.0), _rec(saved_pct=42.0),
                                  _rec(saved_pct=44.0)])
    out = adv.build_candidates([_entry()], "hevc", adv.EncodeHistory(p), set())
    r = out["results"][0]
    assert r["source"] == "history"
    assert r["confidence"] == "high"
    assert r["estimated_saved_pct"] == 42.0
    assert r["estimated_saved_mb"] == 420.0  # 1000 MB * 42%
    assert out["summary"]["history_based"] == 1


def test_build_candidates_confidence_levels(tmp_path):
    out = adv.build_candidates(
        [_entry(file_path="/lib/known.mp4"),
         _entry(file_path="/lib/odd.mp4", codec="prores")],
        "hevc", _empty_history(tmp_path), set())
    by_path = {r["file_path"]: r for r in out["results"]}
    assert by_path["/lib/known.mp4"]["confidence"] == "medium"
    assert by_path["/lib/odd.mp4"]["confidence"] == "low"
    assert all(r["source"] == "heuristic" for r in out["results"])


def test_build_candidates_summary_counts_all_but_results_capped(tmp_path):
    entries = [_entry(file_path=f"/lib/v{i}.mp4") for i in range(5)]
    out = adv.build_candidates(entries, "hevc", _empty_history(tmp_path), set(), limit=2)
    assert len(out["results"]) == 2
    assert out["summary"]["total_files"] == 5
    assert out["summary"]["total_estimated_saved_mb"] > out["results"][0]["estimated_saved_mb"]


def test_build_candidates_reason_mentions_codec_and_resolution(tmp_path):
    out = adv.build_candidates([_entry()], "hevc", _empty_history(tmp_path), set())
    reason = out["results"][0]["reason"]
    assert "h264" in reason.lower()
    assert "2160" in reason or "4k" in reason.lower()
```

Note: `_entry(optimized_at=...)` requires `VideoEntry` to tolerate the extra
field — its `model_config` has `extra="ignore"`, so before Task 4 the value is
dropped and `getattr(entry, "optimized_at", 0)` returns 0. That makes
`test_build_candidates_exclusions` FAIL on the `/lib/done.mp4` line until
Task 4 lands. Mark exactly that test with
`@pytest.mark.xfail(reason="optimized_at field lands in Task 4", strict=False)`
and REMOVE the marker in Task 4 (`import pytest` at the top if not present).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_optimization_advisor.py -k build_candidates -v`
Expected: FAIL with "has no attribute 'build_candidates'"

- [ ] **Step 3: Write the implementation**

```python
# append to arcade_scanner/core/optimization_advisor.py

MIN_LISTED_SAVED_PCT = 10.0


def _reason(entry: VideoEntry, saved_pct: float, source: str, samples: int) -> str:
    codec = (entry.codec or "unknown").upper().replace("H264", "H.264")
    res = f"{entry.height}p" if (entry.height or 0) > 0 else "?"
    rate = f"{entry.bitrate_mbps:.1f} Mbit/s"
    if source == "history":
        return f"{codec}, {res}, {rate} — {samples} echte Encodes in dieser Klasse"
    return f"{codec}, {res}, {rate} — deutlich über Referenz"


def build_candidates(entries: list[VideoEntry], target_codec: str,
                     history: EncodeHistory, exclude_paths: set[str],
                     limit: int = 100) -> dict:
    """Rank re-encode candidates by absolute expected savings (MB, desc)."""
    candidates: list[CandidateEstimate] = []
    for entry in entries:
        if entry.media_type != "video":
            continue
        if getattr(entry, "optimized_at", 0):
            continue
        if entry.file_path in exclude_paths:
            continue
        heur = estimate_heuristic(entry, target_codec)
        if heur is None:
            continue
        saved_pct, known_pair = heur
        source = "heuristic"
        confidence = "medium" if known_pair else "low"
        samples = 0
        hist = history.median_saved_pct(
            target_codec, entry.height or 0, (entry.bitrate_mbps or 0.0) * 1000.0)
        if hist is not None:
            saved_pct, samples = hist
            source, confidence = "history", "high"
        if saved_pct < MIN_LISTED_SAVED_PCT:
            continue
        candidates.append(CandidateEstimate(
            file_path=entry.file_path,
            size_mb=entry.size_mb,
            codec=entry.codec or "unknown",
            width=entry.width or 0,
            height=entry.height or 0,
            bitrate_mbps=entry.bitrate_mbps or 0.0,
            thumb=entry.thumb or "",
            estimated_saved_mb=round(entry.size_mb * saved_pct / 100.0, 1),
            estimated_saved_pct=round(saved_pct, 1),
            confidence=confidence,
            source=source,
            reason=_reason(entry, saved_pct, source, samples),
        ))

    candidates.sort(key=lambda c: c.estimated_saved_mb, reverse=True)
    return {
        "summary": {
            "total_files": len(candidates),
            "total_estimated_saved_mb": round(sum(c.estimated_saved_mb for c in candidates), 1),
            "history_based": sum(1 for c in candidates if c.source == "history"),
        },
        "results": [c.__dict__.copy() for c in candidates[:limit]],
    }
```

- [ ] **Step 4: Run tests — all pass except the marked xfail**

Run: `.venv/bin/pytest tests/test_optimization_advisor.py -v`
Expected: PASS, with `test_build_candidates_exclusions` XFAIL (removed in Task 4)

- [ ] **Step 5: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner tests
.venv/bin/mypy arcade_scanner/core/optimization_advisor.py
git add arcade_scanner/core/optimization_advisor.py tests/test_optimization_advisor.py
git commit -m "feat(core): build_candidates ranking with exclusions and summary"
```

---

### Task 4: `optimized_at` column end-to-end

**Files:**
- Modify: `arcade_scanner/models/video_entry.py` (add field after `original_path`)
- Modify: `arcade_scanner/database/sqlite_store.py` (`_COLUMNS`, `_create_table` migration, `_entry_to_tuple`, `_row_to_api_dict`; new method `get_active_queue_paths`)
- Modify: `arcade_scanner/scanner/manager.py:239-243` (merge block)
- Modify: `arcade_scanner/server/routes/files.py:179` (`_handle_mark_optimized`)
- Test: `tests/test_sqlite_store.py` (append), `tests/test_routes_files.py` (append), `tests/test_optimization_advisor.py` (remove xfail marker)

**Interfaces:**
- Produces: `VideoEntry.optimized_at: Optional[int] = 0` (unix timestamp, 0 = never); `SQLiteStore.get_active_queue_paths() -> set[str]` (file_paths with queue status pending/downloading/encoding/uploading). Task 5 consumes both.

**CRITICAL:** `upsert` is `INSERT OR REPLACE` over `_COLUMNS` — the column must be in `_COLUMNS`, `_entry_to_tuple`, `_row_to_api_dict` AND be re-copied from `cached_entry` in the scanner merge, or every rescan resets it (same pattern as `favorite`).

- [ ] **Step 1: Write the failing tests**

Follow the existing fixture style in `tests/test_sqlite_store.py` (it builds a store against a tmp dir — reuse its fixture; shown here with a representative `store` fixture name, adapt to the file's actual one):

```python
# append to tests/test_sqlite_store.py

def test_optimized_at_roundtrip(store):
    from arcade_scanner.models.video_entry import VideoEntry
    e = VideoEntry(file_path="/lib/a.mp4", size_mb=10.0, optimized_at=1723000000)
    store.upsert(e)
    got = store.get("/lib/a.mp4")
    assert got is not None
    assert got.optimized_at == 1723000000


def test_optimized_at_defaults_to_zero(store):
    from arcade_scanner.models.video_entry import VideoEntry
    store.upsert(VideoEntry(file_path="/lib/b.mp4", size_mb=10.0))
    got = store.get("/lib/b.mp4")
    assert got is not None
    assert got.optimized_at == 0


def test_get_active_queue_paths(store):
    from arcade_scanner.models.video_entry import VideoEntry
    store.upsert(VideoEntry(file_path="/lib/q.mp4", size_mb=10.0))
    job_id = store.queue_encode("/lib/q.mp4", size_bytes=1, target_codec="hevc")
    assert job_id is not None
    assert store.get_active_queue_paths() == {"/lib/q.mp4"}
    store.update_job_status(job_id, "done")
    assert store.get_active_queue_paths() == set()


def test_optimized_at_migration_on_existing_db(patch_config, tmp_path):
    """A pre-existing DB without the column gets it via ALTER TABLE on open."""
    import sqlite3

    from arcade_scanner.database.sqlite_store import _COLUMNS, SQLiteStore
    db_file = tmp_path / "media_library.db"
    legacy_cols = ", ".join(
        f"{name} {typedef}" for name, typedef in _COLUMNS if name != "optimized_at")
    conn = sqlite3.connect(db_file)
    conn.execute(f"CREATE TABLE media ({legacy_cols})")
    conn.execute("INSERT INTO media (file_path, size_mb) VALUES ('/lib/old.mp4', 5.0)")
    conn.commit()
    conn.close()

    s = SQLiteStore()
    s._ensure_connection()
    entry = s.get("/lib/old.mp4")
    assert entry is not None
    assert entry.optimized_at == 0
```

```python
# append to tests/test_routes_files.py, inside class TestMarkOptimized
# (uses the file's existing FakeHandler / FakeDB / run_route helpers)

    def test_existing_entry_gets_optimized_timestamp(self):
        entry = VideoEntry(FilePath="/media/a.mp4", Size_MB=10.0, Status="HIGH")
        db = FakeDB([entry])
        handler = FakeHandler("/api/mark_optimized?path=/media/a.mp4")

        run_route(handler, fake_db=db)

        assert db.upserted[0].status == "OK"
        assert db.upserted[0].optimized_at > 0
        assert handler.status == 204

    def test_new_entry_gets_optimized_timestamp(self):
        db = FakeDB()
        handler = FakeHandler("/api/mark_optimized?path=/media/new.mp4")

        with patch("arcade_scanner.server.routes.files.os.path.getsize",
                   return_value=5 * 1024 * 1024):
            run_route(handler, fake_db=db)

        assert db.upserted[0].optimized_at > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sqlite_store.py -k optimized -v` and `-k active_queue`
Expected: FAIL (unknown field / missing method)

- [ ] **Step 3: Implement**

`arcade_scanner/models/video_entry.py` — after the `original_path` field:

```python
    optimized_at: Optional[int] = Field(0, description="Unix timestamp of last successful optimization (0 = never)")
```

`arcade_scanner/database/sqlite_store.py`:

1. `_COLUMNS`: append `("optimized_at", "INTEGER DEFAULT 0"),` after `("original_path", ...)`.
2. `_create_table` — after the `original_path` migration block, same pattern:

```python
        # Migration: optimized_at marks files already processed by the optimizer
        try:
            conn.execute("ALTER TABLE media ADD COLUMN optimized_at INTEGER DEFAULT 0")
        except Exception:
            pass  # Already exists
```

3. `_entry_to_tuple` — append `entry.optimized_at or 0,` as the last tuple element (order must match `_COLUMNS`).
4. `_row_to_api_dict` — add `"optimized_at": row["optimized_at"] or 0,` after the `"OriginalPath"` line.
5. New method next to `get_queue_status`:

```python
    def get_active_queue_paths(self) -> set:
        """file_paths of jobs currently pending or being processed."""
        conn = self._ensure_connection()
        with self._write_lock:
            cursor = conn.execute(
                "SELECT file_path FROM encoding_queue "
                "WHERE status IN ('pending', 'downloading', 'encoding', 'uploading')"
            )
            return {self._decode_safe_path(row["file_path"]) for row in cursor}
```

`arcade_scanner/scanner/manager.py` — in the `if cached_entry:` merge block (next to `entry.favorite = cached_entry.favorite`):

```python
                        entry.optimized_at = cached_entry.optimized_at
```

`arcade_scanner/server/routes/files.py` `_handle_mark_optimized` — set the timestamp in both branches (existing entry and newly created one), next to the `status = "OK"` assignments:

```python
        import time as _time
        now = int(_time.time())
        entry = db.get(abs_path)
        if entry:
            entry.status = "OK"
            entry.optimized_at = now
        else:
            ...
            entry = VideoEntry(file_path=abs_path, size_mb=size_mb, Status="OK",
                               optimized_at=now)
```

(If `time` is already imported at module top, use it directly instead of the local import.)

Also: remove the `@pytest.mark.xfail` marker from
`test_build_candidates_exclusions` in `tests/test_optimization_advisor.py`.

- [ ] **Step 4: Run the full affected suites**

Run: `.venv/bin/pytest tests/test_sqlite_store.py tests/test_routes_files.py tests/test_optimization_advisor.py tests/test_scanner_manager.py -v`
Expected: all PASS (including the formerly-xfailed exclusion test), no regressions in scanner/store suites

- [ ] **Step 5: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner tests
.venv/bin/mypy arcade_scanner
git add -A arcade_scanner tests
git commit -m "feat(db): optimized_at column, rescan-safe, set by mark_optimized"
```

---

### Task 5: `/api/candidates` route

**Files:**
- Create: `arcade_scanner/server/routes/candidates.py`
- Modify: `arcade_scanner/server/api_handler.py` (GET dispatch around line 397; `spa_routes` line 438)
- Test: `tests/test_routes_candidates.py`

**Interfaces:**
- Consumes: `build_candidates`, `EncodeHistory`, `DEFAULT_HISTORY_PATH` (Tasks 1–3); `db.get_all()`, `db.get_active_queue_paths()` (Task 4); `user_db.get_user(name).data.vaulted: List[str]` (`arcade_scanner/models/user.py:81`).
- Produces: `GET /api/candidates?codec=hevc|av1&limit=N` → JSON from `build_candidates`. 401 without session, 400 on invalid codec. `handle_get(handler) -> bool` wired BEFORE `files.handle_get` (files is greedy).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_candidates.py
"""Route tests for /api/candidates — FakeHandler pattern from test_routes_queue.py."""
import json
from unittest.mock import MagicMock, patch

from arcade_scanner.models.video_entry import VideoEntry
from arcade_scanner.server.routes import candidates


class FakeHandler:
    def __init__(self, path, user="alice"):
        self.path = path
        self._user = user
        self.wfile = MagicMock()
        self.status = None
        self.error = None
        self.headers = {}

    def get_current_user(self):
        return self._user

    def send_response(self, code):
        self.status = code

    def send_error(self, code, message=""):
        self.error = code

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass

    def body(self):
        raw = b"".join(c.args[0] for c in self.wfile.write.call_args_list)
        return json.loads(raw)


class FakeDB:
    def __init__(self, entries=(), active=()):
        self._entries = list(entries)
        self._active = set(active)

    def get_all(self):
        return self._entries

    def get_active_queue_paths(self):
        return self._active


class FakeUserDB:
    def __init__(self, vaulted=()):
        u = MagicMock()
        u.data.vaulted = list(vaulted)
        self._u = u

    def get_user(self, name):
        return self._u


def _entry(path="/lib/a.mp4", **kw):
    base = dict(file_path=path, size_mb=1000.0, bitrate_mbps=45.0, codec="h264",
                width=3840, height=2160, frame_rate=30.0, media_type="video")
    base.update(kw)
    return VideoEntry(**base)


def run(handler, db=None, user_db=None, tmp_path=None):
    db = db or FakeDB([_entry()])
    user_db = user_db or FakeUserDB()
    with patch.object(candidates, "_get_deps", return_value=(db, user_db)):
        handled = candidates.handle_get(handler)
    return handled


def test_unrelated_path_not_handled():
    assert run(FakeHandler("/api/other")) is False


def test_requires_session():
    h = FakeHandler("/api/candidates", user=None)
    assert run(h) is True
    assert h.error == 401


def test_invalid_codec_400():
    h = FakeHandler("/api/candidates?codec=vp9")
    assert run(h) is True
    assert h.error == 400


def test_returns_ranked_results():
    h = FakeHandler("/api/candidates?codec=hevc")
    db = FakeDB([_entry("/lib/big.mp4", size_mb=8000.0), _entry("/lib/small.mp4", size_mb=100.0)])
    assert run(h, db=db) is True
    body = h.body()
    assert body["summary"]["total_files"] == 2
    assert [r["file_path"] for r in body["results"]] == ["/lib/big.mp4", "/lib/small.mp4"]


def test_excludes_active_queue_and_vaulted():
    h = FakeHandler("/api/candidates")
    db = FakeDB([_entry("/lib/q.mp4"), _entry("/lib/v.mp4"), _entry("/lib/ok.mp4")],
                active={"/lib/q.mp4"})
    udb = FakeUserDB(vaulted=["/lib/v.mp4"])
    run(h, db=db, user_db=udb)
    assert [r["file_path"] for r in h.body()["results"]] == ["/lib/ok.mp4"]


def test_limit_param():
    h = FakeHandler("/api/candidates?limit=1")
    db = FakeDB([_entry(f"/lib/v{i}.mp4") for i in range(3)])
    run(h, db=db)
    body = h.body()
    assert len(body["results"]) == 1
    assert body["summary"]["total_files"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_routes_candidates.py -v`
Expected: FAIL with "No module named ... routes.candidates"

- [ ] **Step 3: Implement the route**

```python
# arcade_scanner/server/routes/candidates.py
"""GET /api/candidates — re-encode candidates ranked by expected savings."""
import os
from urllib.parse import parse_qs, urlparse

from arcade_scanner.core.optimization_advisor import EncodeHistory, build_candidates
from arcade_scanner.server.response_helpers import send_json

VALID_CODECS = {"hevc", "av1"}

# Module-level: EncodeHistory caches by mtime, so reuse across requests.
_history = EncodeHistory()


def _get_deps():
    from arcade_scanner.server.api_handler import db, user_db
    return db, user_db


def handle_get(handler) -> bool:
    parsed = urlparse(handler.path)
    if parsed.path != "/api/candidates":
        return False

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return True

    params = parse_qs(parsed.query)
    codec = params.get("codec", ["hevc"])[0]
    if codec not in VALID_CODECS:
        handler.send_error(400, "Invalid codec (hevc|av1)")
        return True
    try:
        limit = max(1, min(int(params.get("limit", ["100"])[0]), 500))
    except ValueError:
        limit = 100

    try:
        db, user_db = _get_deps()
        exclude = set(db.get_active_queue_paths())
        u = user_db.get_user(user_name)
        if u and u.data.vaulted:
            exclude.update(os.path.abspath(p) for p in u.data.vaulted)
        payload = build_candidates(db.get_all(), codec, _history, exclude, limit)
        send_json(handler, payload)
    except Exception as e:
        print(f"❌ Error building candidates: {e}")
        handler.send_error(500, str(e))
    return True
```

`arcade_scanner/server/api_handler.py` — two edits:

1. GET dispatch (line ~397): extend the import and insert BEFORE `files.handle_get`:

```python
            from .routes import candidates, duplicates, files, queue, settings, tags
            ...
            if candidates.handle_get(self):
                return
            if files.handle_get(self):
```

2. `spa_routes` (line ~438): add `"/candidates"` to the list.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_routes_candidates.py tests/test_route_interface.py -v`
Expected: all PASS (`test_route_interface.py` sanity-checks route modules — if it enumerates them, the new module must conform; check its assertions and follow them)

- [ ] **Step 5: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner tests
.venv/bin/mypy arcade_scanner
git add arcade_scanner/server/routes/candidates.py arcade_scanner/server/api_handler.py tests/test_routes_candidates.py
git commit -m "feat(web): /api/candidates endpoint with queue/vault exclusion"
```

---

### Task 6: Frontend — candidates view

**Files:**
- Create: `arcade_scanner/server/static/candidates.js`
- Modify: `arcade_scanner/templates/ui_components.py` (nav button after the duplicates entry)
- Modify: `arcade_scanner/server/static/workspace.js` (wsColors, mode branch, updateURL, loadFromURL)
- Modify: `arcade_scanner/server/static/filter_engine.js` (early return + ribbon suppression)
- Modify: `arcade_scanner/templates/dashboard_template.py` (script tag after duplicates.js)
- Modify: `tests/test_dom_contract.py` (`DYNAMIC_IDS`)
- Test: existing static suites (`test_js_syntax.py`, `test_dom_contract.py`, `test_js_completeness.py`, `test_js_runtime_patterns.py`, `test_dashboard_template.py`)

**Interfaces:**
- Consumes: `GET /api/candidates` (Task 5); `POST /api/queue/add` with `{file_path, codec}` (existing); `showToast(msg, type)` (existing global); `videoGrid` container + duplicates-mode display toggling in `workspace.js:89-99`.
- Produces: global functions used by onclick handlers (must be plain top-level `function` declarations so they land on `window`): `renderCandidatesView()`, `setCandidatesCodec(codec)`, `toggleCandidateSelect(encodedPath)`, `queueCandidate(encodedPath)`, `queueSelectedCandidates()`. Row IDs are dynamic with prefix `cand-`.

- [ ] **Step 1: Write `candidates.js`**

```javascript
// arcade_scanner/server/static/candidates.js
/**
 * Candidates View — ranks the library by expected re-encode savings.
 * Data: GET /api/candidates (see routes/candidates.py). Queueing reuses
 * POST /api/queue/add like optimizer.js does.
 */

let candState = {
    codec: 'hevc',
    results: [],
    summary: null,
    selected: new Set(),   // file paths
    loading: false,
};

function renderCandidatesView() {
    const grid = document.getElementById('videoGrid');
    if (!grid) return;
    grid.innerHTML = '<div class="p-8 text-center text-gray-400">Analysiere Bibliothek…</div>';
    candState.loading = true;

    fetch(`/api/candidates?codec=${candState.codec}&limit=200`)
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(data => {
            candState.results = data.results || [];
            candState.summary = data.summary || null;
            candState.selected.clear();
            candState.loading = false;
            _renderCandidates(grid);
        })
        .catch(err => {
            candState.loading = false;
            grid.innerHTML = `<div class="p-8 text-center text-red-400">Kandidaten-Analyse fehlgeschlagen: ${err.message}</div>`;
        });
}

function _fmtGB(mb) {
    return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}

function _candHeader() {
    const s = candState.summary || { total_files: 0, total_estimated_saved_mb: 0, history_based: 0 };
    const codecBtn = (c, label) => `
        <button onclick="setCandidatesCodec('${c}')"
                class="px-3 py-1 rounded text-xs font-bold ${candState.codec === c
                    ? 'bg-arcade-cyan text-black'
                    : 'bg-white/10 text-gray-300 hover:bg-white/20'}">${label}</button>`;
    return `
    <div id="candidatesHeader" class="col-span-full p-4 rounded-xl bg-white/5 mb-2">
        <div class="flex flex-wrap items-center gap-4">
            <div>
                <div class="text-2xl font-bold text-arcade-cyan">~${_fmtGB(s.total_estimated_saved_mb)}</div>
                <div class="text-xs text-gray-400">geschätzte Ersparnis · ${s.total_files} Kandidaten
                     · ${s.history_based} mit echter Encode-Historie</div>
            </div>
            <div class="flex items-center gap-2 ml-auto">
                ${codecBtn('hevc', 'HEVC')}${codecBtn('av1', 'AV1')}
                <button id="candQueueSelectedBtn" onclick="queueSelectedCandidates()"
                        class="px-3 py-1 rounded text-xs font-bold bg-arcade-cyan/20 text-arcade-cyan hover:bg-arcade-cyan/30">
                    Auswahl in Queue (${candState.selected.size})
                </button>
            </div>
        </div>
    </div>`;
}

function _candRow(r, idx) {
    const enc = encodeURIComponent(r.file_path);
    const name = r.file_path.split(/[/\\]/).pop();
    const checked = candState.selected.has(r.file_path) ? 'checked' : '';
    const confColors = { high: 'text-green-400', medium: 'text-yellow-400', low: 'text-gray-400' };
    const confLabel = r.source === 'history' ? 'Historie' : 'Schätzung';
    const thumb = r.thumb ? `<img src="/thumbnails/${r.thumb}" class="w-24 h-14 object-cover rounded" loading="lazy">`
                          : '<div class="w-24 h-14 rounded bg-white/10"></div>';
    return `
    <div id="cand-${idx}" class="col-span-full flex items-center gap-3 p-2 rounded-lg bg-white/5 hover:bg-white/10">
        <input type="checkbox" ${checked} onclick="toggleCandidateSelect('${enc}')">
        <div class="cursor-pointer" onclick="openCinema('${enc}')">${thumb}</div>
        <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium">${name}</div>
            <div class="text-xs text-gray-400">${r.codec.toUpperCase()} · ${r.height}p · ${r.bitrate_mbps.toFixed(1)} Mbit/s · ${_fmtGB(r.size_mb)}</div>
            <div class="text-[11px] text-gray-500">${r.reason}</div>
        </div>
        <div class="text-right shrink-0">
            <div class="text-sm font-bold text-arcade-cyan">−${_fmtGB(r.estimated_saved_mb)}</div>
            <div class="text-[11px] ${confColors[r.confidence] || ''}">${r.estimated_saved_pct}% · ${confLabel}</div>
        </div>
        <button onclick="queueCandidate('${enc}')"
                class="shrink-0 px-3 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-arcade-cyan/30">
            In Queue
        </button>
    </div>`;
}

function _renderCandidates(grid) {
    if (!candState.results.length) {
        grid.innerHTML = _candHeader() +
            '<div class="col-span-full p-8 text-center text-gray-400">Keine Kandidaten — Bibliothek sieht gut optimiert aus. 🎉</div>';
        return;
    }
    grid.innerHTML = _candHeader() + candState.results.map(_candRow).join('');
}

function setCandidatesCodec(codec) {
    candState.codec = codec;
    renderCandidatesView();
}

function toggleCandidateSelect(encodedPath) {
    const p = decodeURIComponent(encodedPath);
    if (candState.selected.has(p)) candState.selected.delete(p);
    else candState.selected.add(p);
    const btn = document.getElementById('candQueueSelectedBtn');
    if (btn) btn.textContent = `Auswahl in Queue (${candState.selected.size})`;
}

function _queuePaths(paths) {
    let queued = 0, skipped = 0;
    const requests = paths.map(p =>
        fetch('/api/queue/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: p, codec: candState.codec })
        }).then(r => r.json())
          .then(d => { if (d.success) queued++; else skipped++; })
          .catch(() => { skipped++; })
    );
    Promise.all(requests).then(() => {
        if (typeof showToast === 'function') {
            showToast(`${queued} eingereiht${skipped ? `, ${skipped} übersprungen` : ''}`,
                      skipped ? 'warning' : 'success');
        }
        renderCandidatesView();  // queued files drop out server-side
    });
}

function queueCandidate(encodedPath) {
    _queuePaths([decodeURIComponent(encodedPath)]);
}

function queueSelectedCandidates() {
    if (!candState.selected.size) {
        if (typeof showToast === 'function') showToast('Nichts ausgewählt', 'warning');
        return;
    }
    _queuePaths([...candState.selected]);
}
```

(If `openCinema` is not the actual global to open the cinema modal for a path,
check `cards.js`/`cinema.js` for the function the duplicates view uses for its
thumbnail preview and call that instead — `tests/test_js_completeness.py` will
catch an undefined reference.)

- [ ] **Step 2: Wire the templates and workspace**

`arcade_scanner/templates/ui_components.py` — after the duplicates nav button:

```python
    {nav_btn("m-candidates", "setWorkspaceMode('candidates')", "savings", "Kandidaten", "arcade-gold")}
```

`arcade_scanner/templates/dashboard_template.py` — after the duplicates.js script tag:

```python
    <script src="/static/candidates.js?v={int(time.time())}"></script>
```

`arcade_scanner/server/static/workspace.js`:

1. `wsColors` (line ~66): add `candidates: { accent: '#F4B342', bg: 'rgba(244, 179, 66, 0.05)' }`.
2. Mode branch (line ~89): widen the special case:

```javascript
        if (mode === 'duplicates' || mode === 'candidates') {
            const videoGrid = document.getElementById('videoGrid');
            const treemapContainer = document.getElementById('treemapContainer');
            const loadingSentinel = document.getElementById('loadingSentinel');
            if (videoGrid) videoGrid.style.display = '';
            if (treemapContainer) treemapContainer.style.display = 'none';
            if (loadingSentinel) loadingSentinel.style.display = 'none';

            if (mode === 'duplicates') renderDuplicatesView();
            else renderCandidatesView();
        } else {
```

3. `updateURL` (line ~323): add `else if (workspaceMode === 'candidates') path = '/candidates';` next to the duplicates line.
4. `loadFromURL` (line ~372): add `else if (path === '/candidates') mode = 'candidates';` next to the duplicates line.

`arcade_scanner/server/static/filter_engine.js`:

1. Early return (line ~301): `if (workspaceMode === 'duplicates' || workspaceMode === 'candidates') { return; }`
2. Ribbon suppression — both places that test `workspaceMode !== 'optimized' && workspaceMode !== 'duplicates'` / `=== 'duplicates'` (lines ~301 and ~328 region): include `'candidates'` the same way.

`tests/test_dom_contract.py` — extend `DYNAMIC_IDS`:

```python
    # Von candidates.js dynamisch erzeugte IDs:
    "cand-", "candidatesHeader", "candQueueSelectedBtn",
```

(If the contract test complains about further IDs, add them to the same set —
they are all runtime-rendered.)

- [ ] **Step 3: Run the static contract suites**

Run: `.venv/bin/pytest tests/test_js_syntax.py tests/test_dom_contract.py tests/test_js_completeness.py tests/test_js_runtime_patterns.py tests/test_dashboard_template.py -v`
Expected: all PASS (fix any undefined-global or missing-ID findings they report)

- [ ] **Step 4: Manual smoke test**

Run `./run.sh`, open the dashboard, click "Kandidaten": header with total savings renders, rows listed, codec toggle refetches, "In Queue" shows a toast and the row disappears on refetch, URL is `/candidates` and survives reload. Verify nothing broke in Lobby/Duplicates navigation.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check .
git add arcade_scanner/server/static/candidates.js arcade_scanner/templates/ui_components.py \
        arcade_scanner/templates/dashboard_template.py arcade_scanner/server/static/workspace.js \
        arcade_scanner/server/static/filter_engine.js tests/test_dom_contract.py
git commit -m "feat(web): Kandidaten-Ansicht mit Queue-Anbindung"
```

---

### Task 7: Changelog + full verification

**Files:**
- Modify: `CHANGELOG.md` (`[Unreleased]` section)
- Modify: `ROADMAP.md` (add the feature under the planned/completed section as appropriate)

- [ ] **Step 1: Update CHANGELOG.md** — add under `## [Unreleased]`:

```markdown
### Added — Optimizer Candidates View
- **Kandidaten-Ansicht** (`/candidates`): ranks the library by expected re-encode
  savings (bitrate-per-resolution heuristic + codec efficiency), refined by real
  results from `encode_history.jsonl` once a resolution/bitrate class has ≥3
  encodes. Header shows the total possible savings; rows queue directly into the
  existing encoding queue (HEVC/AV1 toggle).
- **`optimized_at` marker**: successful optimizations now stamp the media entry;
  optimized files no longer appear as candidates (rescan-safe).
```

- [ ] **Step 2: Full verification**

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy arcade_scanner
```

Expected: everything green. Fix anything red before committing.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md ROADMAP.md
git commit -m "docs: changelog & roadmap for the candidates view"
```

Then finish the branch per `superpowers:finishing-a-development-branch` (PR from the feature branch into `dev`).
