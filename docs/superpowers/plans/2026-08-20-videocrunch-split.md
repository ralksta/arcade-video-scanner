# videocrunch Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the video optimization toolchain from `arcade-video-scanner` into a standalone, publishable project at `/Users/ralfo/git/videocrunch`, and leave Arcade working as a consumer that invokes it by path.

**Architecture:** videocrunch is a flat collection of stdlib-only Python modules plus a shell wizard, modelled on the sibling project `imgcrunch`. Arcade keeps its server, database and dashboard, calls videocrunch as a subprocess, and holds its own copy of the savings heuristic — the two copies are pinned to identical behaviour by a fixture file committed to both repos.

**Tech Stack:** Python 3.13 (stdlib only — no pydantic, no third-party runtime deps in videocrunch), ffmpeg/ffprobe 8.1+ on PATH, pytest, ruff, bash.

**Spec:** `docs/superpowers/specs/2026-08-20-videocrunch-split-design.md`

## Global Constraints

- **Two working directories.** Arcade is `/Users/ralfo/git/arcade-video-scanner`. videocrunch is `/Users/ralfo/git/videocrunch`. Every task states which one it operates in. Never `cd` between them inside a single command — use absolute paths.
- **videocrunch has zero runtime dependencies.** Python stdlib plus ffmpeg/ffprobe on PATH. No pydantic, no Pillow, no requests. A task that introduces an import outside the stdlib has failed.
- **No `arcade_scanner` imports in videocrunch.** Not even guarded by try/except. Grep is the acceptance test.
- **No `~/.arcade-scanner` paths in videocrunch.** It writes to `~/.videocrunch/logs/`.
- **Tasks 1–7 must not modify anything in the Arcade repo** except where a task explicitly says so (Task 2 touches both). Arcade stays fully working until Task 9.
- **Line length 100, E501 ignored** (both repos, matching Arcade's `pyproject.toml`).
- **Commit style:** conventional commits with scope, e.g. `feat(scan): ...`, `fix(engine): ...`. German or English body, both fine.
- **Arcade test baseline is 921 passed, 1 xfailed.** After Task 10 the Arcade number drops only by the tests that moved; it must never drop because a test was deleted without a home in videocrunch.

---

## File Structure

**videocrunch (new repo):**

| File | Responsibility |
|---|---|
| `videocrunch.py` | Encode engine: quality binary search, SSIM verification, rate control. From `scripts/video_optimizer.py`. |
| `crunch_utils.py` | Pure logic, no ffmpeg: history bucketing, HDR detection, schedule parsing, audio filter chains, rate-control clamping. From `scripts/optimizer_utils.py`. |
| `savings.py` | Savings heuristic: codec efficiency table, resolution reference bitrates, `estimate_savings_pct()`. Extracted from `arcade_scanner/core/optimization_advisor.py`, stripped of `VideoEntry`. |
| `encoders.py` | Hardware encoder detection and worker count. From `arcade_scanner/core/hw_encode_detect.py`. |
| `bitrate.py` | Source bitrate analysis and packet hotspots. From `arcade_scanner/core/bitrate_analyzer.py`. |
| `scan.py` | Folder walk, ffprobe fan-out, ranked candidate table, selection parser. From `scripts/scan_folder.py`, with `build_candidates()` reimplemented without `VideoEntry`. |
| `batch.py` | Parallel encode runner with live table. From `scripts/batch_controller.py`. |
| `crunch.sh` | Wizard / CLI entry point. New. |
| `install_macos_quick_action.sh` | Finder integration installer. New. |
| `savings_parity.json` | Fixture pinning heuristic behaviour. New, mirrored in Arcade. |
| `tests/` | Moved suites plus new ones. |

**Arcade (existing repo), after the split:**

| File | Change |
|---|---|
| `arcade_scanner/core/optimization_advisor.py` | Keeps `build_candidates()`, `EncodeHistory`, `_reason()`, `VideoEntry` adapter; gains a local `CODEC_EFFICIENCY` copy; loses the `bitrate_analyzer` import. |
| `arcade_scanner/config.py` | `optimizer_path` / new `batch_path` read `VIDEOCRUNCH_PATH` / `VIDEOCRUNCH_BATCH_PATH`. |
| `arcade_scanner/server/routes/files.py` | Uses `config.batch_path` instead of deriving the filename. |
| `tests/fixtures/savings_parity.json` | New, identical to videocrunch's copy. |
| Deleted | `scripts/video_optimizer.py`, `scripts/optimizer_utils.py`, `scripts/batch_controller.py`, `scripts/scan_folder.py`, `arcade_scanner/core/hw_encode_detect.py`, `arcade_scanner/core/bitrate_analyzer.py` and their tests. |

---

## Task 1: videocrunch repo skeleton and `savings.py`

**Why first:** `savings.py` is the only file that needs real surgery rather than a move — the heuristic currently depends on `VideoEntry` (pydantic) and on `CODEC_EFFICIENCY` living in another module. Everything else in videocrunch is a rename.

**Working directory:** `/Users/ralfo/git/videocrunch`

**Files:**
- Create: `/Users/ralfo/git/videocrunch/.gitignore`
- Create: `/Users/ralfo/git/videocrunch/requirements.txt`
- Create: `/Users/ralfo/git/videocrunch/requirements-dev.txt`
- Create: `/Users/ralfo/git/videocrunch/pyproject.toml`
- Create: `/Users/ralfo/git/videocrunch/savings.py`
- Test: `/Users/ralfo/git/videocrunch/tests/test_savings.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `savings.CODEC_EFFICIENCY: dict[tuple[str, str], float]`
  - `savings.resolution_class(height: int) -> str` → one of `"sd" | "720" | "1080" | "1440" | "2160"`
  - `savings.bitrate_class(kbps: float) -> str` → one of `"low" | "med" | "high" | "ultra"`
  - `savings.estimate_savings_pct(source_kbps: float, height: int, fps: float, source_codec: str, target_codec: str) -> tuple[float, bool] | None` → `(saved_pct, known_codec_pair)` or `None` when `source_kbps <= 0` or `height <= 0`

- [ ] **Step 1: Create the repo and skeleton files**

```bash
mkdir -p /Users/ralfo/git/videocrunch/tests
cd /Users/ralfo/git/videocrunch
git init -b main

cat > .gitignore <<'EOF'
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/
*_opt.mp4
*._staging_q*
EOF

cat > requirements.txt <<'EOF'
# videocrunch has no runtime dependencies beyond the Python standard library.
# ffmpeg and ffprobe (8.1+) must be on PATH.
EOF

cat > requirements-dev.txt <<'EOF'
pytest>=8.0
ruff>=0.6
EOF

cat > pyproject.toml <<'EOF'
[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
# Same rule set as arcade-video-scanner, but declared under [tool.ruff.lint]
# rather than top-level — the top-level form is deprecated and warns on every run.
select = ["E", "F", "W", "I"]
ignore = ["E501"]
EOF

python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
```

- [ ] **Step 2: Write the failing test**

Create `/Users/ralfo/git/videocrunch/tests/test_savings.py`:

```python
"""Unit tests for the savings heuristic (pure math, no ffmpeg, no I/O)."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from savings import (  # noqa: E402
    bitrate_class,
    estimate_savings_pct,
    resolution_class,
)


class TestClasses:
    def test_bitrate_class_boundaries(self):
        assert bitrate_class(0) == "low"
        assert bitrate_class(2499) == "low"
        assert bitrate_class(2500) == "med"
        assert bitrate_class(7999) == "med"
        assert bitrate_class(8000) == "high"
        assert bitrate_class(19999) == "high"
        assert bitrate_class(20000) == "ultra"

    def test_resolution_class_boundaries(self):
        assert resolution_class(0) == "sd"
        assert resolution_class(576) == "sd"
        assert resolution_class(577) == "720"
        assert resolution_class(800) == "720"
        assert resolution_class(801) == "1080"
        assert resolution_class(1200) == "1080"
        assert resolution_class(1201) == "1440"
        assert resolution_class(1600) == "1440"
        assert resolution_class(1601) == "2160"


class TestEstimateSavingsPct:
    def test_needs_metadata(self):
        assert estimate_savings_pct(0.0, 1080, 30.0, "h264", "hevc") is None
        assert estimate_savings_pct(5000.0, 0, 30.0, "h264", "hevc") is None

    def test_fat_4k_h264_saves_a_lot(self):
        saved, known = estimate_savings_pct(45000.0, 2160, 30.0, "h264", "hevc")
        assert known is True
        assert saved > 60

    def test_lean_1080p_h264_saves_moderately(self):
        saved, _ = estimate_savings_pct(3500.0, 1080, 30.0, "h264", "hevc")
        assert 20 < saved < 50

    def test_same_codec_lean_source_saves_almost_nothing(self):
        # Measured: a 683 kbps 720p HEVC file really only yielded 5.7%.
        saved, _ = estimate_savings_pct(683.0, 720, 25.0, "hevc", "hevc")
        assert saved < 8.0

    def test_same_codec_fat_source_still_worth_it(self):
        saved, _ = estimate_savings_pct(20000.0, 1080, 30.0, "hevc", "hevc")
        assert saved >= 14.0

    def test_unknown_codec_pair_is_flagged(self):
        _, known = estimate_savings_pct(5000.0, 1080, 30.0, "prores", "hevc")
        assert known is False

    def test_av1_target_beats_hevc_target(self):
        av1, _ = estimate_savings_pct(45000.0, 2160, 30.0, "h264", "av1")
        hevc, _ = estimate_savings_pct(45000.0, 2160, 30.0, "h264", "hevc")
        assert av1 >= hevc

    def test_never_predicts_more_than_the_cap(self):
        saved, _ = estimate_savings_pct(500000.0, 2160, 30.0, "mpeg2video", "hevc")
        assert saved <= 85.0

    def test_high_frame_rate_raises_the_reference(self):
        # 60 fps needs more bitrate for the same quality, so a 60 fps source at a
        # given bitrate is comparatively leaner than a 30 fps one.
        sixty, _ = estimate_savings_pct(6000.0, 1080, 60.0, "hevc", "hevc")
        thirty, _ = estimate_savings_pct(6000.0, 1080, 30.0, "hevc", "hevc")
        assert sixty < thirty
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `/Users/ralfo/git/videocrunch/.venv/bin/pytest /Users/ralfo/git/videocrunch/tests/test_savings.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'savings'`

- [ ] **Step 4: Write `savings.py`**

Create `/Users/ralfo/git/videocrunch/savings.py`. This is the heuristic from `arcade_scanner/core/optimization_advisor.py` lines 26–140 plus the `CODEC_EFFICIENCY` table from `arcade_scanner/core/bitrate_analyzer.py:25`, with the `VideoEntry` wrapper dropped:

```python
"""Savings heuristic — how much would re-encoding this file gain?

Pure math, no I/O, no ffmpeg. Answers "is this file worth encoding at all"
before any encoder starts, and ranks folders in scan.py.

The same math lives in arcade-video-scanner's optimization_advisor.py, which
feeds its dashboard candidate list. The two copies are pinned to identical
behaviour by savings_parity.json, committed to both repos — see the parity
test. Change the math here and that test fails on both sides, which is the
point: neither project has to import the other.
"""
from typing import Optional

# Bitrate multiplier for the same perceived quality when going source -> target.
# 0.65 means "HEVC needs 65% of the bitrate H.264 needed".
CODEC_EFFICIENCY: dict = {
    ("h264", "hevc"):  0.65,
    ("h264", "h265"):  0.65,
    ("h264", "av1"):   0.55,
    ("hevc", "h264"):  1.40,
    ("h265", "h264"):  1.40,
    ("hevc", "av1"):   0.80,
    ("h265", "av1"):   0.80,
    ("av1",  "h264"):  1.70,
    ("av1",  "hevc"):  1.25,
    ("av1",  "h265"):  1.25,
    ("mpeg4", "h264"): 0.60,
    ("mpeg4", "hevc"): 0.45,
    ("mpeg2video", "h264"): 0.50,
    ("mpeg2video", "hevc"): 0.35,
    ("vp8",  "h264"):  0.75,
    ("vp9",  "hevc"):  0.90,
    ("vp9",  "h264"):  1.10,
}

# Reference bitrates (kbps) for a well-compressed HEVC encode at ~30 fps.
_REF_KBPS = {"sd": 1500.0, "720": 2500.0, "1080": 4000.0, "1440": 8000.0, "2160": 12000.0}
_AV1_REF_FACTOR = 0.85    # AV1 hits the same quality a bit leaner
_SAME_CODEC_EFF = 0.85    # re-encoding within the same codec gains little
_DEFAULT_EFF = 0.65       # unknown source codec: assume h264-like gains
_MAX_SAVED_PCT = 85.0     # never predict more than this
_TARGET_ALIASES = {"hevc": {"hevc", "h265"}, "av1": {"av1"}}


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


def _is_same_codec(source_codec: str, target_codec: str) -> bool:
    """True when re-encoding `source_codec` to `target_codec` is a same-codec pass."""
    src = (source_codec or "").lower()
    return src in _TARGET_ALIASES.get(target_codec, {target_codec})


def _codec_efficiency(source_codec: str, target_codec: str) -> tuple:
    """(bitrate multiplier source->target, is the pair actually known?, is_same_codec)."""
    if _is_same_codec(source_codec, target_codec):
        return _SAME_CODEC_EFF, True, True
    src = (source_codec or "").lower()
    eff = CODEC_EFFICIENCY.get((src, target_codec))
    if eff is not None:
        return eff, True, False
    return _DEFAULT_EFF, False, False


def _reference_kbps(height: int, target_codec: str, fps: float) -> float:
    """Reference bitrate (kbps) for a clean target-codec encode at this resolution/fps."""
    ref = _REF_KBPS[resolution_class(height)]
    if target_codec == "av1":
        ref *= _AV1_REF_FACTOR
    if fps > 0:
        ref *= min(max(fps / 30.0, 0.5), 2.0)
    return ref


def estimate_savings_pct(source_kbps: float, height: int, fps: float,
                         source_codec: str, target_codec: str) -> Optional[tuple]:
    """Estimated saved percentage (0-100) for re-encoding.

    Returns (saved_pct, known_codec_pair) or None when the inputs are too
    incomplete to say anything (no bitrate or no height from ffprobe).
    """
    if source_kbps <= 0 or height <= 0:
        return None

    eff, known, is_same_codec = _codec_efficiency(source_codec or "", target_codec)
    ref = _reference_kbps(height, target_codec, fps or 0.0)

    if is_same_codec:
        # Same-codec: apply efficiency without ref cap (already efficiently encoded).
        # How much is left depends on how fat the source is RELATIVE to a clean
        # encode at this resolution. A source already far below `ref` has been
        # squeezed once; a second pass in the same codec gets almost nothing
        # (measured: a 683 kbps 720p HEVC file yielded 5.7%, not the flat 15%
        # `eff` implies). Scale the gain by source/ref so leanness is priced in.
        leanness = min(1.0, source_kbps / ref) if ref > 0 else 1.0
        effective_eff = 1.0 - (1.0 - eff) * leanness
        predicted_kbps = source_kbps * effective_eff
        predicted_kbps = max(predicted_kbps, source_kbps * (1 - _MAX_SAVED_PCT / 100))
    else:
        # Different-codec: cap at reference rate
        predicted_kbps = min(source_kbps * eff, max(ref, source_kbps * (1 - _MAX_SAVED_PCT / 100)))

    saved_pct = max(0.0, (1.0 - predicted_kbps / source_kbps) * 100.0)
    return min(saved_pct, _MAX_SAVED_PCT), known
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `/Users/ralfo/git/videocrunch/.venv/bin/pytest /Users/ralfo/git/videocrunch/tests/test_savings.py -q`
Expected: 11 passed

- [ ] **Step 6: Verify the constraints hold**

```bash
cd /Users/ralfo/git/videocrunch
grep -rn "arcade_scanner\|arcade-scanner" --include="*.py" . && echo "FAIL: arcade reference found" || echo "OK: clean"
.venv/bin/ruff check .
```
Expected: `OK: clean`, then `All checks passed!`

- [ ] **Step 7: Commit**

```bash
cd /Users/ralfo/git/videocrunch
git add .gitignore requirements.txt requirements-dev.txt pyproject.toml savings.py tests/test_savings.py
git commit -m "feat(savings): Spar-Heuristik ohne pydantic-Abhängigkeit

Aus arcade-video-scanner extrahiert: Codec-Effizienztabelle, Referenzbitraten
pro Auflösungsklasse und estimate_savings_pct(). Die VideoEntry-Hülle bleibt
dort, hier rechnet die Funktion auf Skalaren.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: Parity fixture in both repos

**Why now:** The fixture must be generated while both implementations are still known-identical. Doing it later, after videocrunch's copy has been touched, would pin whatever drift already happened.

**Working directories:** both

**Files:**
- Create: `/Users/ralfo/git/videocrunch/savings_parity.json`
- Create: `/Users/ralfo/git/videocrunch/tests/test_savings_parity.py`
- Create: `/Users/ralfo/git/arcade-video-scanner/tests/fixtures/savings_parity.json`
- Create: `/Users/ralfo/git/arcade-video-scanner/tests/test_savings_parity.py`

**Interfaces:**
- Consumes: `savings.estimate_savings_pct` (Task 1); `arcade_scanner.core.optimization_advisor.estimate_savings_pct` (already exists).
- Produces: `savings_parity.json` — a JSON list of objects with keys `source_kbps`, `height`, `fps`, `source_codec`, `target_codec`, `expected` (either `null` or `[saved_pct, known]`).

- [ ] **Step 1: Generate the fixture from Arcade's current implementation**

```bash
cd /Users/ralfo/git/arcade-video-scanner
.venv/bin/python3 - <<'EOF'
import json
from pathlib import Path
from arcade_scanner.core.optimization_advisor import estimate_savings_pct

CASES = [
    # (source_kbps, height, fps, source_codec, target_codec)
    (45000, 2160, 30, "h264", "hevc"),      # fat 4K, the flagship case
    (45000, 2160, 30, "h264", "av1"),
    (3500, 1080, 30, "h264", "hevc"),       # lean 1080p, bounded by codec factor
    (6200, 1080, 25, "h264", "hevc"),       # above reference
    (1500, 720, 25, "h264", "hevc"),
    (500, 360, 30, "h264", "hevc"),         # very lean SD
    (683, 720, 25, "hevc", "hevc"),         # same codec, lean: the Ezada regression
    (20000, 1080, 30, "hevc", "hevc"),      # same codec, fat
    (288000, 2160, 25, "hevc", "hevc"),     # 8K camera master
    (4000, 1080, 30, "h265", "hevc"),       # alias spelling
    (4000, 1080, 30, "hevc", "av1"),
    (4000, 1080, 30, "av1", "hevc"),        # target less efficient than source
    (5000, 1080, 30, "prores", "hevc"),     # unknown pair
    (5000, 1080, 60, "hevc", "hevc"),       # fps raises the reference
    (5000, 1080, 0, "hevc", "hevc"),        # fps missing
    (500000, 2160, 30, "mpeg2video", "hevc"),  # cap
    (0, 1080, 30, "h264", "hevc"),          # no bitrate -> None
    (5000, 0, 30, "h264", "hevc"),          # no height -> None
]

out = []
for kbps, h, fps, src, tgt in CASES:
    r = estimate_savings_pct(float(kbps), h, float(fps), src, tgt)
    out.append({
        "source_kbps": kbps, "height": h, "fps": fps,
        "source_codec": src, "target_codec": tgt,
        "expected": None if r is None else [round(r[0], 9), r[1]],
    })

Path("tests/fixtures").mkdir(parents=True, exist_ok=True)
Path("tests/fixtures/savings_parity.json").write_text(json.dumps(out, indent=2) + "\n")
print(f"{len(out)} Fälle geschrieben")
EOF
cp tests/fixtures/savings_parity.json /Users/ralfo/git/videocrunch/savings_parity.json
```

Expected: `18 Fälle geschrieben`

- [ ] **Step 2: Write the parity test for videocrunch**

Create `/Users/ralfo/git/videocrunch/tests/test_savings_parity.py`:

```python
"""Pins savings.py to the behaviour recorded in savings_parity.json.

The identical fixture lives in arcade-video-scanner, which keeps its own copy of
this math for its dashboard. Both repos test against the same file, so a change
on either side fails the build on both.

DO NOT regenerate this fixture to make a failure go away. A failure means the
two implementations have diverged; decide deliberately which behaviour is
correct, change both, and update the fixture in both repos in the same breath.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from savings import estimate_savings_pct  # noqa: E402

FIXTURE = REPO_ROOT / "savings_parity.json"
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
```

- [ ] **Step 3: Write the parity test for Arcade**

Create `/Users/ralfo/git/arcade-video-scanner/tests/test_savings_parity.py` — the same file with two changes: the import comes from `arcade_scanner.core.optimization_advisor`, and `FIXTURE` points at `tests/fixtures/savings_parity.json`:

```python
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
```

- [ ] **Step 4: Run both suites**

```bash
/Users/ralfo/git/videocrunch/.venv/bin/pytest /Users/ralfo/git/videocrunch/tests -q
/Users/ralfo/git/arcade-video-scanner/.venv/bin/pytest /Users/ralfo/git/arcade-video-scanner/tests -q
```
Expected: videocrunch 30 passed; Arcade 940 passed, 1 xfailed (921 + 19 new parity tests)

- [ ] **Step 5: Prove the fixture actually catches drift**

Temporarily break videocrunch's copy and confirm the test fails:

```bash
cd /Users/ralfo/git/videocrunch
sed -i '' 's/_SAME_CODEC_EFF = 0.85/_SAME_CODEC_EFF = 0.80/' savings.py
.venv/bin/pytest tests/test_savings_parity.py -q 2>&1 | tail -3
sed -i '' 's/_SAME_CODEC_EFF = 0.80/_SAME_CODEC_EFF = 0.85/' savings.py
.venv/bin/pytest tests/test_savings_parity.py -q 2>&1 | tail -3
```
Expected: first run fails on the same-codec cases, second run passes again. A fixture that cannot fail is decoration.

- [ ] **Step 6: Commit in both repos**

```bash
cd /Users/ralfo/git/videocrunch
git add savings_parity.json tests/test_savings_parity.py
git commit -m "test(savings): Parity-Fixture gegen arcade-video-scanner

Beide Repos halten eine eigene Implementierung der Spar-Heuristik und testen
gegen dieselbe Fixture-Datei. Drift fällt damit auf beiden Seiten auf, ohne
dass ein Projekt das andere importieren muss.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

cd /Users/ralfo/git/arcade-video-scanner
git add tests/fixtures/savings_parity.json tests/test_savings_parity.py
git commit -m "test(advisor): Parity-Fixture gegen videocrunch

Nagelt die Spar-Heuristik auf ihr heutiges Verhalten fest, bevor der Encoder
in ein eigenes Repo zieht. Die identische Fixture liegt dort.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Verbatim moves — `encoders.py`, `bitrate.py`, `crunch_utils.py`

**Why grouped:** All three are copies with no logic change; only the module name and the history path change. A reviewer would accept or reject them together.

**Working directory:** `/Users/ralfo/git/videocrunch` (reads from Arcade, writes here; Arcade is not modified)

**Files:**
- Create: `/Users/ralfo/git/videocrunch/encoders.py` (from `arcade_scanner/core/hw_encode_detect.py`)
- Create: `/Users/ralfo/git/videocrunch/bitrate.py` (from `arcade_scanner/core/bitrate_analyzer.py`)
- Create: `/Users/ralfo/git/videocrunch/crunch_utils.py` (from `scripts/optimizer_utils.py`)
- Test: `/Users/ralfo/git/videocrunch/tests/test_crunch_utils.py` (from `tests/test_optimizer_utils.py`)
- Test: `/Users/ralfo/git/videocrunch/tests/test_bitrate.py` (from `tests/test_bitrate_analyzer.py`)
- Test: `/Users/ralfo/git/videocrunch/tests/test_encoders.py` (new — extracted from `tests/test_video_processor.py`)

**Interfaces:**
- Consumes: nothing from Task 1 or 2.
- Produces:
  - `encoders.detect_hevc_optimizer_encoder() -> str`
  - `encoders.get_optimal_workers(log_fn=None) -> int`
  - `encoders.get_best_h264_encoder(log_fn=None) -> tuple`
  - `encoders.detect_h264_encoder(log_fn=None) -> tuple`
  - `bitrate.analyze_bitrate(...)`, `bitrate.analyze_packet_hotspots(...)` (signatures unchanged from `bitrate_analyzer.py`)
  - `crunch_utils.DEFAULT_HISTORY_PATH = Path.home() / ".videocrunch" / "logs" / "encode_history.jsonl"`
  - all other `crunch_utils` names unchanged from `optimizer_utils.py`: `append_encode_history`, `apply_hdr_adjustments`, `build_audio_filter_chain`, `clamp_maxrate_to_pass`, `is_hdr_or_10bit`, `narrow_quality_window`, `nearest_quality_index`, `parse_loudnorm_json`, `select_top_windows`, `suggest_q_from_history`, `bitrate_class`, `resolution_class`, `parse_schedule`, `is_within_schedule`, `battery_from_pmset`, `PASS_MAXRATE_FACTOR`

- [ ] **Step 1: Copy the three modules and the two test files**

```bash
A=/Users/ralfo/git/arcade-video-scanner
V=/Users/ralfo/git/videocrunch
cp "$A/arcade_scanner/core/hw_encode_detect.py" "$V/encoders.py"
cp "$A/arcade_scanner/core/bitrate_analyzer.py" "$V/bitrate.py"
cp "$A/scripts/optimizer_utils.py"              "$V/crunch_utils.py"
cp "$A/tests/test_optimizer_utils.py"           "$V/tests/test_crunch_utils.py"
cp "$A/tests/test_bitrate_analyzer.py"          "$V/tests/test_bitrate.py"
```

- [ ] **Step 2: Rewrite the imports and the history path**

```bash
V=/Users/ralfo/git/videocrunch
cd "$V"

# bitrate.py: drop the package-relative import if present
grep -n "^from \.\|^from arcade_scanner" bitrate.py encoders.py crunch_utils.py || echo "keine Paket-Importe"

# crunch_utils.py: history moves out of Arcade's data directory
python3 - <<'EOF'
import pathlib
p = pathlib.Path('/Users/ralfo/git/videocrunch/crunch_utils.py')
s = p.read_text()
old = 'DEFAULT_HISTORY_PATH = Path.home() / ".arcade-scanner" / "logs" / "encode_history.jsonl"'
new = 'DEFAULT_HISTORY_PATH = Path.home() / ".videocrunch" / "logs" / "encode_history.jsonl"'
assert old in s, "history path line not found"
p.write_text(s.replace(old, new, 1))
print("history path updated")
EOF

# tests import the new module names and add the repo root to sys.path
python3 - <<'EOF'
import pathlib, re
V = pathlib.Path('/Users/ralfo/git/videocrunch')
for name, old_mod, new_mod in (
    ('tests/test_crunch_utils.py', 'optimizer_utils', 'crunch_utils'),
    ('tests/test_bitrate.py', 'arcade_scanner.core.bitrate_analyzer', 'bitrate'),
):
    p = V / name
    s = p.read_text()
    s = s.replace(f'from {old_mod} import', f'from {new_mod} import')
    s = s.replace(f'import {old_mod}', f'import {new_mod}')
    s = s.replace('SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"',
                  'REPO_ROOT = Path(__file__).parent.parent')
    s = s.replace('if str(SCRIPTS_DIR) not in sys.path:\n    sys.path.insert(0, str(SCRIPTS_DIR))',
                  'if str(REPO_ROOT) not in sys.path:\n    sys.path.insert(0, str(REPO_ROOT))')
    p.write_text(s)
    print(f"{name}: {old_mod} -> {new_mod}")
EOF
```

Note: the exact `sys.path` preamble differs between the two test files. If a replacement above does not apply, open the file and adjust the preamble by hand so it puts `REPO_ROOT` on `sys.path` — the goal is that `from crunch_utils import ...` and `from bitrate import ...` resolve.

- [ ] **Step 3: Write the encoder test**

Create `/Users/ralfo/git/videocrunch/tests/test_encoders.py`. `tests/test_video_processor.py:9` in Arcade tests `detect_h264_encoder`; that half comes along, the `video_processor` half stays in Arcade:

```python
"""Tests for hardware encoder detection. Requires ffmpeg on PATH."""
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from encoders import (  # noqa: E402
    detect_h264_encoder,
    detect_hevc_optimizer_encoder,
    get_optimal_workers,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_detect_h264_encoder_returns_a_usable_pair():
    encoder, extra_args = detect_h264_encoder(log_fn=lambda _: None)
    assert isinstance(encoder, str) and encoder
    assert isinstance(extra_args, list)


def test_detect_hevc_optimizer_encoder_names_a_known_profile():
    key = detect_hevc_optimizer_encoder()
    # 'vaapi' is reachable on Linux (encoders.py:118) and is a real
    # ENCODER_PROFILES key — leaving it out makes this test pass on macOS
    # and fail on a VAAPI box.
    assert key in {"nvenc", "videotoolbox", "qsv", "vaapi", "libx265",
                   "av1_nvenc", "av1_software"}


def test_get_optimal_workers_is_at_least_one():
    assert get_optimal_workers(log_fn=lambda _: None) >= 1
```

- [ ] **Step 4: Run the tests**

```bash
cd /Users/ralfo/git/videocrunch
.venv/bin/pytest tests -q
```
Expected: all pass. If `test_bitrate.py` fails on an import of something that lived in `arcade_scanner`, fix that import to the local module — no logic changes.

- [ ] **Step 5: Verify constraints**

```bash
cd /Users/ralfo/git/videocrunch
grep -rn "arcade_scanner\|arcade-scanner" --include="*.py" . && echo "FAIL" || echo "OK: clean"
grep -rn "^import \|^from " --include="*.py" . | grep -vE "^\S+:(import|from) (json|os|re|sys|time|math|shutil|subprocess|threading|queue|argparse|logging|datetime|pathlib|typing|concurrent|dataclasses|statistics|collections|functools|itertools|tempfile|hashlib|urllib|signal|socket|platform|glob)" | grep -vE "(encoders|bitrate|crunch_utils|savings|videocrunch|scan|batch)" | grep -v pytest
.venv/bin/ruff check .
```
Expected: `OK: clean`, the second grep prints nothing (no third-party imports), ruff passes.

- [ ] **Step 6: Commit**

```bash
cd /Users/ralfo/git/videocrunch
git add encoders.py bitrate.py crunch_utils.py tests/
git commit -m "feat: Encoder-Erkennung, Bitratenanalyse und Hilfslogik übernommen

Wortgleiche Übernahme aus arcade-video-scanner, geändert sind nur die
Modulnamen und der History-Pfad (~/.videocrunch/logs statt ~/.arcade-scanner).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: The engine — `videocrunch.py`

**Working directory:** `/Users/ralfo/git/videocrunch`

**Files:**
- Create: `/Users/ralfo/git/videocrunch/videocrunch.py` (from `scripts/video_optimizer.py`, 2249 lines)
- Test: `/Users/ralfo/git/videocrunch/tests/test_engine_ffmpeg.py` (from `tests/test_optimizer_ffmpeg.py`)

**Interfaces:**
- Consumes: `encoders.detect_hevc_optimizer_encoder`, `bitrate.analyze_bitrate`, `crunch_utils.*`, `savings.estimate_savings_pct` (Tasks 1 and 3).
- Produces:
  - `videocrunch.process_file(input_path, profile, min_size_mb=0, copy_audio=False, port=None, audio_mode='enhanced', ss=None, to=None, video_mode='compress', q_override=None, presearch=True, scale_height=None, force=False, progress_callback=None) -> tuple[bool, int]`
  - `videocrunch.ENCODER_PROFILES: dict`
  - `videocrunch.detect_encoder() -> str`
  - `videocrunch.get_video_info(path) -> dict | None`
  - `videocrunch.LOG_DIR = Path.home() / ".videocrunch" / "logs"`

- [ ] **Step 1: Copy the engine and its test**

```bash
A=/Users/ralfo/git/arcade-video-scanner
V=/Users/ralfo/git/videocrunch
cp "$A/scripts/video_optimizer.py"      "$V/videocrunch.py"
cp "$A/tests/test_optimizer_ffmpeg.py"  "$V/tests/test_engine_ffmpeg.py"
```

- [ ] **Step 2: Replace the three import blocks**

The engine currently reaches into Arcade three times (`scripts/video_optimizer.py` lines 22–38, 40–49, 51–72). All three are `try/except ImportError` blocks with availability flags. In videocrunch the modules are siblings, always present, so the flags become constants:

```bash
python3 - <<'PYEOF'
import pathlib, re
p = pathlib.Path('/Users/ralfo/git/videocrunch/videocrunch.py')
s = p.read_text()

start = s.index("# Import arcade_scanner core utilities")
end = s.index("# --- CONFIGURATION ---")
head = s[:start]
tail = s[end:]

new_imports = '''# --- Sibling modules -------------------------------------------------------
# All of these live next to this file, so there is no availability dance: the
# flags exist only because the engine used to be embedded in a larger project
# where these modules could be absent.
from bitrate import analyze_bitrate
from encoders import detect_hevc_optimizer_encoder
from savings import estimate_savings_pct
from crunch_utils import (
    append_encode_history,
    apply_hdr_adjustments,
    build_audio_filter_chain,
    clamp_maxrate_to_pass,
    is_hdr_or_10bit,
    narrow_quality_window,
    nearest_quality_index,
    parse_loudnorm_json,
    select_top_windows,
    suggest_q_from_history,
)

BITRATE_ANALYZER_AVAILABLE = True
HW_DETECT_AVAILABLE = True
OPTIMIZER_UTILS_AVAILABLE = True
ADVISOR_AVAILABLE = True

'''
p.write_text(head + new_imports + tail)
print("import blocks replaced")
PYEOF
```

Note: `analyze_packet_hotspots` is **not** imported — it is defined locally at `video_optimizer.py:647` and travels inside the engine file. Importing it from `bitrate` would raise `ImportError` at startup, because `bitrate_analyzer.py` only exports `analyze_bitrate`. Verify after the edit:

```bash
grep -n "def analyze_packet_hotspots\|analyze_packet_hotspots" /Users/ralfo/git/videocrunch/videocrunch.py
```
Expected: one `def` line and its call sites, no import line.

- [ ] **Step 3: Move the log directory**

```bash
python3 - <<'PYEOF'
import pathlib
p = pathlib.Path('/Users/ralfo/git/videocrunch/videocrunch.py')
s = p.read_text()
old = 'LOG_DIR = Path.home() / ".arcade-scanner" / "logs"'
new = 'LOG_DIR = Path.home() / ".videocrunch" / "logs"'
assert old in s
p.write_text(s.replace(old, new, 1))
print("LOG_DIR updated")
PYEOF
```

- [ ] **Step 4: Point the test at the new module**

```bash
python3 - <<'PYEOF'
import pathlib
p = pathlib.Path('/Users/ralfo/git/videocrunch/tests/test_engine_ffmpeg.py')
s = p.read_text()
s = s.replace('from video_optimizer import', 'from videocrunch import')
s = s.replace('SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"',
              'REPO_ROOT = Path(__file__).parent.parent')
s = s.replace('if str(SCRIPTS_DIR) not in sys.path:\n    sys.path.insert(0, str(SCRIPTS_DIR))',
              'if str(REPO_ROOT) not in sys.path:\n    sys.path.insert(0, str(REPO_ROOT))')
p.write_text(s)
print("test rewired")
PYEOF
```

Note: `test_engine_ffmpeg.py` contains `test_process_file_accepts_a_progress_callback`, which asserts `progress_callback` is the **last** parameter of `process_file`. That contract is unchanged by this task — do not reorder the signature.

- [ ] **Step 5: Run the tests**

```bash
cd /Users/ralfo/git/videocrunch
.venv/bin/pytest tests -q
```
Expected: all pass (the ffmpeg-dependent ones run because ffmpeg is installed).

- [ ] **Step 6: Smoke-test a real encode**

```bash
cd /Users/ralfo/git/videocrunch
ffmpeg -y -f lavfi -i "testsrc=duration=20:size=1280x720:rate=25" \
       -f lavfi -i "sine=frequency=440:duration=20" \
       -c:v libx264 -preset ultrafast -b:v 8000k -c:a aac -shortest /tmp/vc_smoke.mp4
.venv/bin/python3 videocrunch.py --audio-mode standard /tmp/vc_smoke.mp4
ls -la /tmp/vc_smoke_opt.mp4 && ls -la ~/.videocrunch/logs/
rm -f /tmp/vc_smoke.mp4 /tmp/vc_smoke_opt.mp4
```
Expected: an `_opt.mp4` is produced (a deliberately bloated 8 Mbit/s 720p source has plenty to give), and the log lands under `~/.videocrunch/logs/`, **not** under `~/.arcade-scanner/`.

- [ ] **Step 7: Verify constraints and commit**

```bash
cd /Users/ralfo/git/videocrunch
grep -rn "arcade_scanner\|arcade-scanner" --include="*.py" . && echo "FAIL" || echo "OK: clean"
.venv/bin/ruff check .
git add videocrunch.py tests/test_engine_ffmpeg.py
git commit -m "feat(engine): Encode-Engine übernommen

video_optimizer.py wird videocrunch.py. Die drei try/except-Importblöcke in
Richtung arcade_scanner entfallen — die Module liegen jetzt daneben. Logs und
Encode-History wandern nach ~/.videocrunch/logs.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: `batch.py`

**Working directory:** `/Users/ralfo/git/videocrunch`

**Files:**
- Create: `/Users/ralfo/git/videocrunch/batch.py` (from `scripts/batch_controller.py`)
- Test: `/Users/ralfo/git/videocrunch/tests/test_batch.py` (from `tests/test_batch_controller.py`)

**Interfaces:**
- Consumes: `encoders.get_best_h264_encoder`, `encoders.get_optimal_workers` (Task 3); spawns `videocrunch.py` as a subprocess (Task 4).
- Produces: `batch.terminal_verdict(line: str) -> tuple[str | None, str | None]`; CLI `python3 batch.py --files a,b,c [--port N] [--audio-mode enhanced|standard]`.

- [ ] **Step 1: Copy and rewire**

```bash
A=/Users/ralfo/git/arcade-video-scanner
V=/Users/ralfo/git/videocrunch
cp "$A/scripts/batch_controller.py"      "$V/batch.py"
cp "$A/tests/test_batch_controller.py"   "$V/tests/test_batch.py"

python3 - <<'PYEOF'
import pathlib
V = pathlib.Path('/Users/ralfo/git/videocrunch')

p = V / 'batch.py'
s = p.read_text()

# The sys.path insert for the Arcade package and the two hw_encode_detect
# imports collapse into one sibling import.
start = s.index("# Add parent path for imports")
end = s.index("# --- COLORS ---")
s = s[:start] + "from encoders import get_best_h264_encoder as get_best_encoder\nfrom encoders import get_optimal_workers\n\n" + s[end:]

s = s.replace('LOG_DIR = Path.home() / ".arcade-scanner" / "logs"',
              'LOG_DIR = Path.home() / ".videocrunch" / "logs"')
s = s.replace('"video_optimizer.py"', '"videocrunch.py"')
s = s.replace("'video_optimizer.py'", "'videocrunch.py'")
p.write_text(s)

t = V / 'tests/test_batch.py'
s = t.read_text()
s = s.replace('from batch_controller import', 'from batch import')
s = s.replace('SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"',
              'REPO_ROOT = Path(__file__).parent.parent')
s = s.replace('if str(SCRIPTS_DIR) not in sys.path:\n    sys.path.insert(0, str(SCRIPTS_DIR))',
              'if str(REPO_ROOT) not in sys.path:\n    sys.path.insert(0, str(REPO_ROOT))')
t.write_text(s)
print("batch rewired")
PYEOF

grep -n "video_optimizer\|arcade" /Users/ralfo/git/videocrunch/batch.py || echo "OK: keine Altlasten"
```

- [ ] **Step 2: Run the tests**

Run: `/Users/ralfo/git/videocrunch/.venv/bin/pytest /Users/ralfo/git/videocrunch/tests/test_batch.py -q`
Expected: 9 passed

- [ ] **Step 3: Smoke-test the batch runner end to end**

```bash
cd /Users/ralfo/git/videocrunch
ffmpeg -y -f lavfi -i "testsrc=duration=15:size=1280x720:rate=25" \
       -c:v libx264 -preset ultrafast -b:v 8000k /tmp/vc_b1.mp4
ffmpeg -y -f lavfi -i "testsrc=duration=15:size=1280x720:rate=25" \
       -c:v libx264 -preset ultrafast -b:v 8000k /tmp/vc_b2.mp4
.venv/bin/python3 batch.py --files "/tmp/vc_b1.mp4,/tmp/vc_b2.mp4" --audio-mode standard
ls -la /tmp/vc_b1_opt.mp4 /tmp/vc_b2_opt.mp4
rm -f /tmp/vc_b1*.mp4 /tmp/vc_b2*.mp4
```
Expected: `Succeeded: 2`, both `_opt.mp4` files present. If it reports `Succeeded: 0` while the files exist, `terminal_verdict` is misclassifying — that is the regression Task 5's test covers.

- [ ] **Step 4: Commit**

```bash
cd /Users/ralfo/git/videocrunch
.venv/bin/ruff check .
git add batch.py tests/test_batch.py
git commit -m "feat(batch): Parallel-Encode-Runner übernommen

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: `scan.py` — the folder ranking

**Why it needs work:** `scripts/scan_folder.py` imports three things from Arcade: `ALLOWED_VIDEO_EXTENSIONS`, `build_candidates`/`EncodeHistory` from the advisor, and `VideoEntry`. In videocrunch the extension list is inlined, the ranking is reimplemented over plain dicts, and `VideoEntry` disappears.

**Working directory:** `/Users/ralfo/git/videocrunch`

**Files:**
- Create: `/Users/ralfo/git/videocrunch/scan.py`
- Test: `/Users/ralfo/git/videocrunch/tests/test_scan.py` (from `tests/test_scan_folder.py`)

**Interfaces:**
- Consumes: `savings.estimate_savings_pct`, `savings.bitrate_class`, `savings.resolution_class` (Task 1); `crunch_utils.DEFAULT_HISTORY_PATH` (Task 3); spawns `batch.py` (Task 5).
- Produces:
  - `scan.find_videos(root: Path) -> list[Path]`
  - `scan.has_optimized_sibling(path: Path) -> bool`
  - `scan.parse_selection(text: str, count: int) -> list[int]`
  - `scan.probe_to_media(file_path: str, probe: dict) -> dict | None` — replaces `entry_from_probe`; returns a plain dict with keys `file_path`, `size_mb`, `bitrate_mbps`, `codec`, `duration_sec`, `width`, `height`, `frame_rate`
  - `scan.rank(media: list[dict], target_codec: str, exclude_paths: set[str], history: EncodeHistory, limit: int) -> dict` with `{"results": [...], "summary": {...}}`

- [ ] **Step 1: Write the failing test**

Create `/Users/ralfo/git/videocrunch/tests/test_scan.py` by copying Arcade's `tests/test_scan_folder.py` and adapting the two class names that change. Copy the file first:

```bash
cp /Users/ralfo/git/arcade-video-scanner/tests/test_scan_folder.py \
   /Users/ralfo/git/videocrunch/tests/test_scan.py
```

Then apply these edits by hand:
- module docstring: replace `scan_folder.py` with `scan.py`
- `SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"` → `REPO_ROOT = Path(__file__).parent.parent`, and the matching `sys.path.insert`
- `from scan_folder import (...)` → `from scan import (...)`, renaming `entry_from_probe` to `probe_to_media`
- in `class TestEntryFromProbe`, every `entry_from_probe(` → `probe_to_media(`, and attribute access becomes dict access: `e.file_path` → `e["file_path"]`, `e.codec` → `e["codec"]`, `e.height` → `e["height"]`, `e.width` → `e["width"]`, `e.frame_rate` → `e["frame_rate"]`, `e.bitrate_mbps` → `e["bitrate_mbps"]`, `e.size_mb` → `e["size_mb"]`. Drop the `assert e.media_type == "video"` line — videocrunch only handles videos, so the field is gone.

Add this new test class at the end of the file, covering the reimplemented ranking:

```python
class TestRank:
    def _media(self, **kw):
        base = dict(file_path="/lib/a.mp4", size_mb=1000.0, bitrate_mbps=12.0,
                    codec="h264", duration_sec=600.0, width=1920, height=1080,
                    frame_rate=25.0)
        base.update(kw)
        return base

    def test_sorts_by_absolute_savings(self):
        from scan import EncodeHistory, rank
        media = [
            self._media(file_path="/lib/small.mp4", size_mb=100.0),
            self._media(file_path="/lib/big.mp4", size_mb=2000.0),
        ]
        out = rank(media, "hevc", set(), EncodeHistory(Path("/nonexistent")), 10)
        names = [r["file_path"] for r in out["results"]]
        assert names == ["/lib/big.mp4", "/lib/small.mp4"]

    def test_drops_candidates_below_the_threshold(self):
        from scan import EncodeHistory, rank
        # A lean HEVC source has nothing to give and must not be listed.
        media = [self._media(codec="hevc", bitrate_mbps=0.683, height=720,
                             width=1280, size_mb=525.0)]
        out = rank(media, "hevc", set(), EncodeHistory(Path("/nonexistent")), 10)
        assert out["results"] == []
        assert out["summary"]["total_files"] == 0

    def test_excluded_paths_are_skipped(self):
        from scan import EncodeHistory, rank
        media = [self._media(file_path="/lib/done.mp4")]
        out = rank(media, "hevc", {"/lib/done.mp4"},
                   EncodeHistory(Path("/nonexistent")), 10)
        assert out["results"] == []

    def test_limit_truncates_results_but_not_the_summary(self):
        from scan import EncodeHistory, rank
        media = [self._media(file_path=f"/lib/{i}.mp4") for i in range(5)]
        out = rank(media, "hevc", set(), EncodeHistory(Path("/nonexistent")), 2)
        assert len(out["results"]) == 2
        assert out["summary"]["total_files"] == 5
```

- [ ] **Step 2: Run to verify it fails**

Run: `/Users/ralfo/git/videocrunch/.venv/bin/pytest /Users/ralfo/git/videocrunch/tests/test_scan.py -q`
Expected: `ModuleNotFoundError: No module named 'scan'`

- [ ] **Step 3: Write `scan.py`**

Start from Arcade's `scripts/scan_folder.py` and make these changes:

```bash
cp /Users/ralfo/git/arcade-video-scanner/scripts/scan_folder.py \
   /Users/ralfo/git/videocrunch/scan.py
```

Then replace the Arcade imports at the top with the block below, and replace `entry_from_probe` with `probe_to_media`:

```python
from savings import bitrate_class, estimate_savings_pct, resolution_class
from crunch_utils import DEFAULT_HISTORY_PATH

# Extensions worth probing. Inlined from arcade-video-scanner's config; a
# standalone tool should not need a config module for a constant list.
VIDEO_EXTENSIONS = frozenset({
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.ts',
})
MIN_LISTED_SAVED_PCT = 10.0
```

`probe_to_media` is `entry_from_probe` with the `VideoEntry(...)` construction replaced by a dict:

```python
def probe_to_media(file_path: str, probe: dict) -> Optional[dict]:
    """Build a media record from raw ffprobe JSON, or None if it is not a video.

    When the container omits `format.bit_rate` (common in Matroska) it is
    derived from size and duration. Without that the entry would rank as
    0 Mbit/s and never appear.
    """
    streams = probe.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        return None

    fmt = probe.get("format", {})
    size_bytes = _as_float(fmt.get("size", 0))
    duration = _as_float(fmt.get("duration", 0))
    bitrate_bps = _as_float(fmt.get("bit_rate", 0))
    if bitrate_bps <= 0 and duration > 0:
        bitrate_bps = size_bytes * 8 / duration

    fps_str = str(video_stream.get("avg_frame_rate", "0/0"))
    if "/" in fps_str:
        numerator, _, denominator = fps_str.partition("/")
        den = _as_float(denominator)
        fps = _as_float(numerator) / den if den > 0 else 0.0
    else:
        fps = _as_float(fps_str)

    return {
        "file_path": file_path,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "bitrate_mbps": round(bitrate_bps / 1_000_000, 2),
        "codec": video_stream.get("codec_name", "unknown"),
        "duration_sec": round(duration, 2),
        "width": _as_int(video_stream.get("width", 0)),
        "height": _as_int(video_stream.get("height", 0)),
        "frame_rate": round(fps, 3),
    }
```

Port `EncodeHistory` and `build_candidates` from `arcade_scanner/core/optimization_advisor.py` into `scan.py` as `EncodeHistory` and `rank()`, replacing every `entry.<field>` with `m["<field>"]` and dropping the `media_type` and `optimized_at` checks (videocrunch only ever sees video files, and it has no database column for "already optimized" — the `_opt.mp4` sibling check in `find_videos`/`has_optimized_sibling` is its equivalent). Keep `_reason()` and its German strings verbatim.

Replace `run_batch`'s target:

```python
def run_batch(paths: list, audio_mode: str, port=None) -> int:
    """Hand the marked files to batch.py for parallel encoding."""
    cmd = [sys.executable, str(Path(__file__).parent / "batch.py"),
           '--files', ",".join(paths), '--audio-mode', audio_mode]
    if port:
        cmd.extend(['--port', str(port)])
    return subprocess.run(cmd).returncode
```

- [ ] **Step 4: Run the tests**

Run: `/Users/ralfo/git/videocrunch/.venv/bin/pytest /Users/ralfo/git/videocrunch/tests -q`
Expected: all pass

- [ ] **Step 5: Smoke-test against a real folder**

```bash
cd /Users/ralfo/git/videocrunch
.venv/bin/python3 scan.py --no-encode --limit 5 ~/Downloads/adrastea
```
Expected: the same ranked table Arcade's `scan_folder.py` produces for that folder. Compare directly:

```bash
/Users/ralfo/git/arcade-video-scanner/.venv/bin/python3 \
    /Users/ralfo/git/arcade-video-scanner/scripts/scan_folder.py \
    --no-encode --limit 5 ~/Downloads/adrastea
```
The two rankings must list the same files in the same order with the same percentages. A mismatch means the `rank()` port changed behaviour — fix `scan.py`, not the test.

- [ ] **Step 6: Commit**

```bash
cd /Users/ralfo/git/videocrunch
grep -rn "arcade_scanner\|VideoEntry\|pydantic" --include="*.py" . && echo "FAIL" || echo "OK: clean"
.venv/bin/ruff check .
git add scan.py tests/test_scan.py
git commit -m "feat(scan): Ordner-Rangliste ohne pydantic

build_candidates rechnet jetzt auf einfachen dicts statt auf VideoEntry, die
Erweiterungsliste ist inline. Damit hängt der Scan an nichts außer ffprobe.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: `crunch.sh`, Quick Action installer, README

**Working directory:** `/Users/ralfo/git/videocrunch`

**Files:**
- Create: `/Users/ralfo/git/videocrunch/crunch.sh`
- Create: `/Users/ralfo/git/videocrunch/install_macos_quick_action.sh`
- Create: `/Users/ralfo/git/videocrunch/README.md`

**Interfaces:**
- Consumes: `scan.py`, `videocrunch.py` (Tasks 4 and 6).
- Produces: `bash crunch.sh <folder|file> [--audio-mode …]`, and a Finder Quick Action named "videocrunch".

- [ ] **Step 1: Write `crunch.sh`**

Model on the Arcade wrapper `scripts/scan-folder-from-finder.sh` (not committed there — read it from disk for the interaction design) and on imgcrunch's `resize.sh` for the wizard shape:

```bash
#!/bin/bash
# videocrunch — folder scan and encode wizard.
#
#   bash crunch.sh ~/Videos              scan the folder, mark what to encode
#   bash crunch.sh ~/Videos/clip.mp4     encode a single file
#   bash crunch.sh ~/Videos --audio-mode standard
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-}"
shift || true

G='\033[0;32m'; BG='\033[1;32m'; Y='\033[0;33m'; R='\033[0;31m'; NC='\033[0m'

if [[ -z "$TARGET" ]]; then
    echo -e "${Y}Usage: bash crunch.sh <Ordner|Datei> [Optionen]${NC}"
    exit 1
fi

PYTHON="$SCRIPT_DIR/.venv/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON="python3"

if ! command -v ffprobe >/dev/null 2>&1; then
    echo -e "${R}ffprobe nicht gefunden. Bitte ffmpeg installieren (brew install ffmpeg).${NC}"
    exit 1
fi

echo -e "${BG}═══════════════════════════════════════════${NC}"
echo -e "${BG}  🎬 videocrunch${NC}"
echo -e "${BG}═══════════════════════════════════════════${NC}"

if [[ -d "$TARGET" ]]; then
    exec "$PYTHON" "$SCRIPT_DIR/scan.py" "$TARGET" "$@"
elif [[ -f "$TARGET" ]]; then
    exec "$PYTHON" "$SCRIPT_DIR/videocrunch.py" "$TARGET" "$@"
else
    echo -e "${R}Nicht gefunden: $TARGET${NC}"
    exit 1
fi
```

- [ ] **Step 2: Write `install_macos_quick_action.sh`**

The installer must generate a `.workflow` bundle in `~/Library/Services/`. The payload script is the one worked out for Arcade's wrapper — path passed to AppleScript as an argument via `quoted form`, so folder names containing apostrophes survive:

```bash
#!/bin/bash
# Installs the "videocrunch" Finder Quick Action into ~/Library/Services/.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_DIR="$HOME/Library/Services/videocrunch.workflow/Contents"
mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_DIR/document.wflow" <<WFLOW
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>AMApplicationBuild</key><string>521</string>
  <key>AMApplicationVersion</key><string>2.10</string>
  <key>AMDocumentVersion</key><string>2</string>
  <key>actions</key>
  <array>
    <dict>
      <key>action</key>
      <dict>
        <key>AMAccepts</key>
        <dict>
          <key>Container</key><string>List</string>
          <key>Optional</key><false/>
          <key>Types</key><array><string>com.apple.cocoa.string</string></array>
        </dict>
        <key>ActionBundlePath</key>
        <string>/System/Library/Automator/Run Shell Script.action</string>
        <key>ActionName</key><string>Run Shell Script</string>
        <key>AMParameterProperties</key>
        <dict>
          <key>COMMAND_STRING</key><dict/>
          <key>inputMethod</key><dict/>
          <key>shell</key><dict/>
        </dict>
        <key>ActionParameters</key>
        <dict>
          <key>COMMAND_STRING</key>
          <string>SCRIPT="$SCRIPT_DIR/crunch.sh"

if [ "\$#" -eq 0 ]; then
    osascript -e 'display alert "Keine Eingabe angekommen" message "Übergabe der Eingabe muss auf \\"als Argumente\\" stehen."'
    exit 1
fi

for d in "\$@"
do
    /usr/bin/osascript \\
        -e 'on run {p}' \\
        -e 'tell application "Terminal" to do script "bash '"\$SCRIPT"' " &amp; quoted form of p' \\
        -e 'end run' "\$d"
done

osascript -e 'tell application "Terminal" to activate'</string>
          <key>inputMethod</key><integer>1</integer>
          <key>shell</key><string>/bin/bash</string>
        </dict>
        <key>BundleIdentifier</key>
        <string>com.apple.RunShellScript</string>
        <key>CFBundleVersion</key><string>2.0.3</string>
      </dict>
    </dict>
  </array>
  <key>workflowMetaData</key>
  <dict>
    <key>serviceApplicationBundleID</key><string>com.apple.finder</string>
    <key>serviceApplicationPath</key><string>/System/Library/CoreServices/Finder.app</string>
    <key>serviceInputTypeIdentifier</key>
    <string>com.apple.Automator.fileSystemObject.folder</string>
    <key>serviceOutputTypeIdentifier</key><string>com.apple.Automator.nothing</string>
    <key>serviceProcessesInput</key><integer>0</integer>
    <key>workflowTypeIdentifier</key><string>com.apple.Automator.servicesMenu</string>
  </dict>
</dict>
</plist>
WFLOW

cat > "$SERVICE_DIR/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>NSServices</key>
  <array>
    <dict>
      <key>NSMenuItem</key><dict><key>default</key><string>videocrunch</string></dict>
      <key>NSMessage</key><string>runWorkflowAsService</string>
      <key>NSSendFileTypes</key><array><string>public.folder</string></array>
    </dict>
  </array>
</dict>
</plist>
PLIST

/System/Library/CoreServices/pbs -flush 2>/dev/null || true
killall Finder 2>/dev/null || true

echo "✅ Quick Action installiert."
echo "   Rechtsklick auf einen Ordner → Schnellaktionen → videocrunch"
echo "   Falls der Eintrag fehlt: Systemeinstellungen → Allgemein →"
echo "   Anmeldeobjekte & Erweiterungen → Finder → videocrunch aktivieren."
```

- [ ] **Step 3: Verify both scripts parse and the installer runs**

```bash
cd /Users/ralfo/git/videocrunch
chmod +x crunch.sh install_macos_quick_action.sh
bash -n crunch.sh && echo "crunch.sh OK"
bash -n install_macos_quick_action.sh && echo "installer OK"
bash crunch.sh ~/Downloads/adrastea --no-encode --limit 3
bash install_macos_quick_action.sh
ls -la ~/Library/Services/videocrunch.workflow/Contents/
```
Expected: both syntax checks pass, the wizard prints the ranked table, the installer creates `document.wflow` and `Info.plist`. Then verify by hand: right-click a folder in Finder → Schnellaktionen → videocrunch opens a Terminal running the scan.

- [ ] **Step 4: Write the README**

Cover, in this order: one-line description, requirements (Python 3.11+, ffmpeg 8.1+), install (clone, venv, `pip install -r requirements-dev.txt` only for tests — there are no runtime deps), the three usage modes (`crunch.sh` wizard, `videocrunch.py` single file, `scan.py --json`), what the quality search actually does (binary search over quality levels with SSIM verification, constrained VBR, savings and quality thresholds and where to change them), the Quick Action installer, and a short "how the savings estimate works" section pointing at `savings.py` and the parity fixture.

State the thresholds explicitly, since they are what a user will want to tune: `MIN_SAVINGS = 20.0`, `MIN_QUALITY = 0.960`, `SSIM_MIN = 0.940`, `SSIM_ACCEPTABLE = 0.945`, `EXCELLENT_SAVINGS_PCT = 50.0`, all in `videocrunch.py`.

- [ ] **Step 5: Commit and publish**

```bash
cd /Users/ralfo/git/videocrunch
git add crunch.sh install_macos_quick_action.sh README.md
git commit -m "feat: Wizard, Quick-Action-Installer und README

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

**STOP — do not publish autonomously.** Creating a public GitHub repo and
pushing to it is an outward-facing, hard-to-retract act: the code becomes
world-readable and may be indexed within minutes. The implementer commits
locally and stops here. Publishing is the human's call:

```bash
# Only after explicit go-ahead:
gh repo create videocrunch --public --source=. --remote=origin \
    --description "Fast parallel video optimizer (HEVC/AV1) with SSIM verification — CLI and macOS Finder Quick Action"
git push -u origin main
```

---

## Task 8: Arcade — shrink the advisor

**Working directory:** `/Users/ralfo/git/arcade-video-scanner`

**Files:**
- Modify: `arcade_scanner/core/optimization_advisor.py:18` (drop the `bitrate_analyzer` import, inline the table)

**Interfaces:**
- Consumes: nothing new.
- Produces: `optimization_advisor.CODEC_EFFICIENCY` (previously re-exported from `bitrate_analyzer`).

- [ ] **Step 1: Run the tests to establish the baseline**

Run: `/Users/ralfo/git/arcade-video-scanner/.venv/bin/pytest -q`
Expected: 940 passed, 1 xfailed

- [ ] **Step 2: Inline the codec table**

Replace `from .bitrate_analyzer import CODEC_EFFICIENCY` (line 18) with the literal table. Use the exact same values as `savings.py` in Task 1 — the parity fixture will catch a typo, which is the point:

```python
# Bitrate multiplier for the same perceived quality when going source -> target.
# Kept here rather than imported: bitrate_analyzer moved to the videocrunch repo
# with the encoder, and this table is the only part of it Arcade ever used.
# The identical table lives in videocrunch's savings.py; savings_parity.json
# pins both.
CODEC_EFFICIENCY: dict = {
    ("h264", "hevc"):  0.65,
    ("h264", "h265"):  0.65,
    ("h264", "av1"):   0.55,
    ("hevc", "h264"):  1.40,
    ("h265", "h264"):  1.40,
    ("hevc", "av1"):   0.80,
    ("h265", "av1"):   0.80,
    ("av1",  "h264"):  1.70,
    ("av1",  "hevc"):  1.25,
    ("av1",  "h265"):  1.25,
    ("mpeg4", "h264"): 0.60,
    ("mpeg4", "hevc"): 0.45,
    ("mpeg2video", "h264"): 0.50,
    ("mpeg2video", "hevc"): 0.35,
    ("vp8",  "h264"):  0.75,
    ("vp9",  "hevc"):  0.90,
    ("vp9",  "h264"):  1.10,
}
```

- [ ] **Step 3: Run the tests**

Run: `/Users/ralfo/git/arcade-video-scanner/.venv/bin/pytest -q`
Expected: 940 passed, 1 xfailed — unchanged. The parity test proves the inlined table is identical.

- [ ] **Step 4: Commit**

```bash
cd /Users/ralfo/git/arcade-video-scanner
git add arcade_scanner/core/optimization_advisor.py
git commit -m "refactor(advisor): CODEC_EFFICIENCY inline statt aus bitrate_analyzer

Die Tabelle war das Einzige, was der Advisor aus bitrate_analyzer gezogen hat.
Das Modul zieht mit dem Encoder in ein eigenes Repo; die Tabelle bleibt hier.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Arcade — configurable paths and a readable failure

**Why before deletion:** After Task 10 the default paths point at files that no longer exist. Wiring the configuration first means the repo is never in a state where encoding is silently broken.

**Working directory:** `/Users/ralfo/git/arcade-video-scanner`

**Files:**
- Modify: `arcade_scanner/config.py:323-329`
- Modify: `arcade_scanner/server/routes/files.py:632-635`
- Test: `tests/test_config_videocrunch_paths.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `config.optimizer_path -> str` — `VIDEOCRUNCH_PATH`, default `<repo parent>/videocrunch/videocrunch.py`
  - `config.batch_path -> str` — `VIDEOCRUNCH_BATCH_PATH`, default `<repo parent>/videocrunch/batch.py`
  - `config.optimizer_available -> bool` (unchanged name, new default target)

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_videocrunch_paths.py`:

```python
"""The encoder lives in a separate repo now; Arcade finds it by path."""
import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture
def fresh_config(monkeypatch):
    def _load(**env):
        for key in ("VIDEOCRUNCH_PATH", "VIDEOCRUNCH_BATCH_PATH", "ARCADE_OPTIMIZER_PATH"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        import arcade_scanner.config as cfg
        importlib.reload(cfg)
        return cfg.config
    return _load


def test_defaults_to_a_sibling_checkout(fresh_config):
    c = fresh_config()
    assert c.optimizer_path.endswith("videocrunch/videocrunch.py")
    assert c.batch_path.endswith("videocrunch/batch.py")


def test_env_overrides_both_paths(fresh_config):
    c = fresh_config(VIDEOCRUNCH_PATH="/opt/vc/videocrunch.py",
                     VIDEOCRUNCH_BATCH_PATH="/opt/vc/batch.py")
    assert c.optimizer_path == "/opt/vc/videocrunch.py"
    assert c.batch_path == "/opt/vc/batch.py"


def test_batch_path_follows_the_engine_directory_by_default(fresh_config, tmp_path):
    # Setting only the engine path must not leave batch.py pointing elsewhere.
    engine = tmp_path / "somewhere" / "videocrunch.py"
    engine.parent.mkdir(parents=True)
    engine.touch()
    c = fresh_config(VIDEOCRUNCH_PATH=str(engine))
    assert c.batch_path == str(engine.parent / "batch.py")


def test_availability_reflects_the_filesystem(fresh_config, tmp_path):
    missing = tmp_path / "nope" / "videocrunch.py"
    c = fresh_config(VIDEOCRUNCH_PATH=str(missing))
    assert c.optimizer_available is False

    present = tmp_path / "videocrunch.py"
    present.touch()
    c = fresh_config(VIDEOCRUNCH_PATH=str(present))
    assert c.optimizer_available is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_config_videocrunch_paths.py -q`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'batch_path'`

- [ ] **Step 3: Implement the config properties**

Replace `arcade_scanner/config.py:323-329` with:

```python
    @property
    def optimizer_path(self) -> str:
        """Path to videocrunch.py — the encoder lives in its own repo.

        Defaults to a sibling checkout, which is what cloning both repos next to
        each other produces. ARCADE_OPTIMIZER_PATH is still honoured so existing
        installs keep working.
        """
        legacy = os.getenv("ARCADE_OPTIMIZER_PATH")
        if legacy:
            return legacy
        default = os.path.join(os.path.dirname(PROJECT_ROOT), "videocrunch", "videocrunch.py")
        return os.getenv("VIDEOCRUNCH_PATH", default)

    @property
    def batch_path(self) -> str:
        """Path to videocrunch's batch.py. Follows optimizer_path unless overridden."""
        return os.getenv(
            "VIDEOCRUNCH_BATCH_PATH",
            os.path.join(os.path.dirname(self.optimizer_path), "batch.py"),
        )

    @property
    def optimizer_available(self) -> bool:
        return os.path.exists(self.optimizer_path)
```

- [ ] **Step 4: Use `batch_path` in the route**

Replace `arcade_scanner/server/routes/files.py:632-635`:

```python
        batch_controller_path = config.batch_path
        if not os.path.exists(batch_controller_path):
            print(f"❌ videocrunch not found at {batch_controller_path} — "
                  f"set VIDEOCRUNCH_BATCH_PATH or clone videocrunch next to this repo")
            handler.send_response(503)
            handler.end_headers()
            return
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/pytest -q`
Expected: 944 passed, 1 xfailed (940 + 4 new)

- [ ] **Step 6: Commit**

```bash
cd /Users/ralfo/git/arcade-video-scanner
git add arcade_scanner/config.py arcade_scanner/server/routes/files.py tests/test_config_videocrunch_paths.py
git commit -m "feat(config): videocrunch über VIDEOCRUNCH_PATH finden

Der Encoder zieht in ein eigenes Repo. Statt eines Pfads in dieses Repo hinein
zeigt die Konfiguration auf ein Geschwister-Checkout, überschreibbar per
Env-Variable. Der Batch-Pfad folgt dem Engine-Pfad, statt seinen Dateinamen
hart zu verdrahten, und ein fehlendes videocrunch meldet 503 statt im
Subprozess zu verrecken.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Arcade — delete the moved modules

**Working directory:** `/Users/ralfo/git/arcade-video-scanner`

**Files:**
- Delete: `scripts/video_optimizer.py`, `scripts/optimizer_utils.py`, `scripts/batch_controller.py`, `scripts/scan_folder.py`
- Delete: `arcade_scanner/core/hw_encode_detect.py`, `arcade_scanner/core/bitrate_analyzer.py`
- Delete: `tests/test_optimizer_utils.py`, `tests/test_optimizer_ffmpeg.py`, `tests/test_scan_folder.py`, `tests/test_batch_controller.py`, `tests/test_bitrate_analyzer.py`
- Modify: `tests/test_video_processor.py` (drop the `hw_encode_detect` half)
- Modify: `arcade_scanner/core/optimization_advisor.py` (docstring reference)
- Modify: `scripts/mac_worker.py` (it imports `video_optimizer` and `optimizer_utils`)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. This task only removes.

- [ ] **Step 1: Confirm nothing in Arcade still imports the doomed modules**

```bash
cd /Users/ralfo/git/arcade-video-scanner
grep -rn "video_optimizer\|optimizer_utils\|batch_controller\|scan_folder\|hw_encode_detect\|bitrate_analyzer" \
    --include="*.py" arcade_scanner/ scripts/ tests/
```
Expected output, and nothing else: `scripts/mac_worker.py` (imports both `video_optimizer` and `optimizer_utils`), `tests/test_video_processor.py` (imports `hw_encode_detect`), and docstring mentions in `optimization_advisor.py`. Anything else must be dealt with before deleting.

- [ ] **Step 2: Decide `mac_worker.py`**

`mac_worker.py` stays in Arcade (it speaks Arcade's queue API) but imports `process_file` from the engine, which is leaving. Change its imports to load videocrunch from `config.optimizer_path`'s directory:

```python
# videocrunch lives in its own repo now; find it the same way the server does.
from arcade_scanner.config import config as _arcade_config

_VC_DIR = str(Path(_arcade_config.optimizer_path).parent)
if _VC_DIR not in sys.path:
    sys.path.insert(0, _VC_DIR)

from crunch_utils import battery_from_pmset, is_within_schedule, parse_schedule  # noqa: E402
```

and at its call site (currently `scripts/mac_worker.py:383`):

```python
        from videocrunch import ENCODER_PROFILES, detect_encoder, process_file
```

- [ ] **Step 3: Trim `tests/test_video_processor.py`**

Delete the `hw_encode_detect` import at line 9 and every test that uses `detect_hw_encoder`; those now live in videocrunch's `tests/test_encoders.py`. Update the module docstring on line 2 to name only `video_processor`.

- [ ] **Step 4: Delete**

```bash
cd /Users/ralfo/git/arcade-video-scanner
git rm scripts/video_optimizer.py scripts/optimizer_utils.py \
       scripts/batch_controller.py scripts/scan_folder.py \
       arcade_scanner/core/hw_encode_detect.py \
       arcade_scanner/core/bitrate_analyzer.py \
       tests/test_optimizer_utils.py tests/test_optimizer_ffmpeg.py \
       tests/test_scan_folder.py tests/test_batch_controller.py \
       tests/test_bitrate_analyzer.py
```

- [ ] **Step 5: Fix the docstring references**

`arcade_scanner/core/optimization_advisor.py` mentions `scripts/video_optimizer.py` in its module docstring (line 6) and in `estimate_savings_pct`'s docstring. Change both to name the videocrunch repo instead.

- [ ] **Step 6: Run the tests**

```bash
cd /Users/ralfo/git/arcade-video-scanner
.venv/bin/pytest -q
.venv/bin/ruff check arcade_scanner/ scripts/ tests/
```
Expected: a number in the 830–870 range, 1 xfailed, no failures. The drop is exactly the moved tests; if a test *fails* rather than disappears, something still depends on a deleted module.

- [ ] **Step 7: Verify the server still starts and the candidates view works**

```bash
cd /Users/ralfo/git/arcade-video-scanner
timeout 25 .venv/bin/python3 -m arcade_scanner.main --skip-setup &
sleep 12
curl -s "http://localhost:8000/api/candidates?limit=3" | head -c 400
echo
wait
```
Expected: JSON with a `results` array. The candidates view is the one server feature that depends on the savings math, so it is the canary for Task 8.

- [ ] **Step 8: Commit**

```bash
cd /Users/ralfo/git/arcade-video-scanner
git add -A
git commit -m "refactor: Encoder-Toolchain nach videocrunch ausgelagert

Engine, Ordner-Scan, Batch-Runner, Encoder-Erkennung und Bitratenanalyse leben
jetzt in https://github.com/ralksta/videocrunch. Arcade ruft sie als Prozess
auf und behält nur, was mit der Bibliothek zu tun hat: Server, Datenbank,
Dashboard und die Kandidaten-Ansicht.

mac_worker.py bleibt hier — er spricht die Queue-API dieses Servers — lädt die
Engine aber aus dem videocrunch-Checkout.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 11: Arcade — documentation

**Working directory:** `/Users/ralfo/git/arcade-video-scanner`

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `dev-docs/video-optimizer.md`

- [ ] **Step 1: Update `CLAUDE.md`**

Three sections lie after the split. Fix each:
- The **Commands** block lists `scripts/video_optimizer.py` and `scripts/manage_users.py`. Replace the optimizer line with a pointer: the encoder lives in the videocrunch repo, cloned next to this one, configured via `VIDEOCRUNCH_PATH`.
- The **Architecture / Optimizer** paragraph describes `scripts/video_optimizer.py` in detail. Replace with two sentences: encoding happens in videocrunch; Arcade invokes it as a subprocess and reads its `encode_history.jsonl`.
- The **JS/HTML contract tests** and **Data layer** sections are untouched by the split — leave them.

Add a line under Conventions, because muscle memory is a real failure mode: encoder work happens in `../videocrunch`, not here.

- [ ] **Step 2: Update `README.md` and `dev-docs/video-optimizer.md`**

`dev-docs/video-optimizer.md` is the full technical reference for the optimizer. It belongs with the code — move its content into videocrunch's README or into `videocrunch/docs/`, and leave a stub here pointing at the new repo.

- [ ] **Step 3: Update `CHANGELOG.md`**

Add under `## [Unreleased]` → `### Changed`:

```markdown
- **Encoder ausgelagert nach [videocrunch](https://github.com/ralksta/videocrunch)**.
  Encode-Engine, Ordner-Rangliste, Batch-Runner, Encoder-Erkennung und
  Bitratenanalyse sind ein eigenständiges Werkzeug geworden — nutzbar ohne
  Arcade, mit eigener Finder-Schnellaktion. Arcade ruft es als Prozess auf
  (`VIDEOCRUNCH_PATH`, Standard: Geschwister-Checkout `../videocrunch/`) und
  liest weiterhin dessen `encode_history.jsonl`, um seine Schätzungen mit echten
  Messwerten zu verbessern. Die Spar-Heuristik liegt bewusst in beiden Repos und
  wird durch `tests/fixtures/savings_parity.json` auf identisches Verhalten
  festgenagelt. Fehlt videocrunch, melden die Encode-Routen 503 statt zu
  verrecken.
```

- [ ] **Step 4: Verify and commit**

```bash
cd /Users/ralfo/git/arcade-video-scanner
grep -rn "scripts/video_optimizer.py\|scripts/batch_controller.py\|scripts/scan_folder.py" \
    --include="*.md" . | grep -v CHANGELOG.md | grep -v docs/superpowers
```
Expected: no hits outside the changelog and the archived specs/plans (those describe history and stay as they are).

```bash
git add CLAUDE.md README.md CHANGELOG.md dev-docs/video-optimizer.md
git commit -m "docs: Verweise auf den ausgelagerten Encoder

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Self-review notes

Checked against the spec:

- Repo layout, zero-dependency rule, entry points → Tasks 1, 3, 4, 5, 6, 7
- Savings heuristic without `VideoEntry` → Task 1
- Parity fixture in both repos, provably able to fail → Task 2 (Step 5 exists precisely because a fixture that cannot fail is decoration)
- `encode_history.jsonl` moving to `~/.videocrunch/logs/` → Tasks 3 (path constant) and 4 (`LOG_DIR`)
- **Arcade reading videocrunch's history with a fallback** → this is the one spec requirement Tasks 1–11 do *not* cover. `arcade_scanner/core/optimization_advisor.py:20` still hard-codes `~/.arcade-scanner/logs/encode_history.jsonl`, and after the split videocrunch writes elsewhere, so the candidates view would slowly stop learning. See Task 12 below.
- Arcade cleanup, path configuration, readable failure → Tasks 8, 9, 10
- Documentation and the muscle-memory risk → Task 11

---

## Task 12: Arcade — read videocrunch's encode history

**Why it exists:** Found during self-review. Without it the split silently degrades the candidates view: videocrunch writes history to `~/.videocrunch/logs/`, Arcade keeps reading `~/.arcade-scanner/logs/`, and every future encode stops improving Arcade's estimates. The failure is invisible — no error, just estimates that never get better.

**Working directory:** `/Users/ralfo/git/arcade-video-scanner`

**Files:**
- Modify: `arcade_scanner/core/optimization_advisor.py:20`
- Test: `tests/test_encode_history_path.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `optimization_advisor.default_history_path() -> Path`

- [ ] **Step 1: Write the failing test**

Create `tests/test_encode_history_path.py`:

```python
"""Arcade reads the encode history that videocrunch writes."""
import importlib

import pytest


@pytest.fixture
def fresh_advisor(monkeypatch):
    def _load(**env):
        monkeypatch.delenv("VIDEOCRUNCH_HISTORY_PATH", raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        import arcade_scanner.core.optimization_advisor as adv
        importlib.reload(adv)
        return adv
    return _load


def test_env_var_wins(fresh_advisor, tmp_path):
    target = tmp_path / "custom.jsonl"
    target.write_text("")
    adv = fresh_advisor(VIDEOCRUNCH_HISTORY_PATH=str(target))
    assert adv.default_history_path() == target


def test_prefers_videocrunch_location_when_it_exists(fresh_advisor, tmp_path, monkeypatch):
    vc = tmp_path / ".videocrunch" / "logs" / "encode_history.jsonl"
    vc.parent.mkdir(parents=True)
    vc.write_text("")
    legacy = tmp_path / ".arcade-scanner" / "logs" / "encode_history.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()
    assert adv.default_history_path() == vc


def test_falls_back_to_the_legacy_location(fresh_advisor, tmp_path, monkeypatch):
    # The existing history holds real measured encodes; discarding them would
    # visibly degrade the candidates view on day one.
    legacy = tmp_path / ".arcade-scanner" / "logs" / "encode_history.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()
    assert adv.default_history_path() == legacy


def test_defaults_to_videocrunch_when_neither_exists(fresh_advisor, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()
    assert adv.default_history_path() == \
        tmp_path / ".videocrunch" / "logs" / "encode_history.jsonl"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_encode_history_path.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'default_history_path'`

- [ ] **Step 3: Implement**

Replace `arcade_scanner/core/optimization_advisor.py:20` with:

```python
import os

_VIDEOCRUNCH_HISTORY = Path.home() / ".videocrunch" / "logs" / "encode_history.jsonl"
_LEGACY_HISTORY = Path.home() / ".arcade-scanner" / "logs" / "encode_history.jsonl"


def default_history_path() -> Path:
    """Where to read encode history from.

    videocrunch writes to ~/.videocrunch/logs. Installs that ran the optimizer
    while it still lived in this repo have real measured encodes under
    ~/.arcade-scanner/logs — those keep working until videocrunch has written
    its first record, at which point the new location takes over.
    """
    override = os.getenv("VIDEOCRUNCH_HISTORY_PATH")
    if override:
        return Path(override)
    if _VIDEOCRUNCH_HISTORY.exists():
        return _VIDEOCRUNCH_HISTORY
    if _LEGACY_HISTORY.exists():
        return _LEGACY_HISTORY
    return _VIDEOCRUNCH_HISTORY


DEFAULT_HISTORY_PATH = default_history_path()
```

`EncodeHistory.__init__` takes `path: Path = DEFAULT_HISTORY_PATH` — a default evaluated at import time. Change it to `path: Optional[Path] = None` and resolve inside, so a test or a late-arriving videocrunch install is picked up:

```python
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path if path is not None else default_history_path()
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/pytest -q`
Expected: all pass, 4 more than after Task 10.

- [ ] **Step 5: Commit**

```bash
cd /Users/ralfo/git/arcade-video-scanner
git add arcade_scanner/core/optimization_advisor.py tests/test_encode_history_path.py
git commit -m "feat(advisor): Encode-History aus dem videocrunch-Verzeichnis lesen

videocrunch schreibt nach ~/.videocrunch/logs. Ohne diese Änderung läse die
Kandidaten-Ansicht weiter am alten Ort und würde stillschweigend aufhören,
aus neuen Encodes zu lernen — ein Fehler ohne Fehlermeldung. Bestehende
Messwerte unter ~/.arcade-scanner/logs bleiben nutzbar, bis videocrunch seinen
ersten Datensatz geschrieben hat.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Done criteria

- `/Users/ralfo/git/videocrunch` is a public GitHub repo, its suite green, `grep -rn "arcade" --include="*.py"` clean.
- `bash crunch.sh ~/Downloads/adrastea` produces the ranked table and can encode a marked selection.
- The Finder Quick Action works on a right-clicked folder.
- Arcade's suite is green, the server starts, `/api/candidates` returns results.
- An encode started from the Arcade queue produces an `_opt.mp4` and a history record that Arcade subsequently reads.
- `savings_parity.json` is byte-identical in both repos.
