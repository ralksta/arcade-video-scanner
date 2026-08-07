# Auto-Tagging Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rule-based auto-tagging — a rule is a Smart-Collection-style query plus a target tag; rules run server-side after every scan (and on demand) with apply-once semantics.

**Architecture:** A pure-Python port of the client-side `evaluateCollectionMatch` evaluator (`core/criteria_eval.py`, pinned to the JS original by a Node-vm parity test) feeds a rule engine (`core/auto_tagger.py`) that merges tags into per-user data and records applied (user, rule, path) triples in a new SQLite table. A new route module provides rule CRUD + manual run; two one-line post-scan hooks trigger the engine. UI: a small "save as auto-tag rule" control in the existing collection modal plus an "Auto-Tagging" settings section.

**Tech Stack:** Python stdlib + pydantic (server), vanilla JS (frontend), SQLite, pytest, Node (parity test only).

**Spec:** `docs/superpowers/specs/2026-08-07-auto-tagging-design.md`

## Global Constraints

- No new runtime dependencies (server deps stay: pydantic, Pillow, imagehash). Node is used only inside tests (same as the existing JS contract tests).
- CI is blocking: `.venv/bin/ruff check .` and `.venv/bin/mypy arcade_scanner` must pass; all new code fully type-annotated.
- Tests: `.venv/bin/pytest`; JS files must pass `node --check` (`tests/test_js_syntax.py`) and the DOM contract (`tests/test_dom_contract.py`).
- Conventional commits with scope. Work on the feature branch (worktree), not `dev`.
- Apply-once semantics (spec): a tag applied by a rule becomes a normal tag; manual removal is final — the rule never re-applies it. Bookkeeping lives in the main DB (`auto_tag_applied`), NOT in the `user_data` JSON blob.
- Server-side evaluation must stay faithful to `evaluateCollectionMatch` (`arcade_scanner/server/static/collections.js:515-632`): unknown/extra criteria fields are ignored, hidden (vaulted) videos never match.
- `UserStore.add_user` is an upsert (INSERT OR REPLACE keyed on username) that swallows exceptions — persist a user ONCE per run, not per file.
- Out of scope (YAGNI, per spec): rule priorities, multiple tags per rule, synchronized tag removal, TV/iOS client changes.

---

### Task 1: Python criteria evaluator (`core/criteria_eval.py`)

**Files:**
- Create: `arcade_scanner/core/criteria_eval.py`
- Test: `tests/test_criteria_eval.py`

**Interfaces:**
- Consumes: nothing from this feature; operates on the API-dict video shape produced by `SQLiteStore._row_to_api_dict` / `get_all_dicts()` (keys: `FilePath`, `Size_MB`, `Status`, `codec`, `tags`, `hidden`, `favorite`, `Width`, `Height`, `Duration_Sec`, `media_type`, `imported_at`, `mtime`).
- Produces: `video_matches(video: dict, criteria: dict | None, now: int | None = None) -> bool` plus helpers `resolution_category(video: dict) -> str`, `orientation_category(video: dict) -> str`, `matches_date_filter(video: dict, date_filter, now: int) -> bool`. Tasks 2 and 4 rely on exactly these names.

The port must mirror the JS logic 1:1, including its quirks (e.g. `timestamp == 0` fails any non-"all" date filter; `favorites: None` means "don't care"; `include.status` value `"optimized_files"` matches `"_opt"` in the path). The JS reads both alias spellings (`width`/`Width`) — keep that.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_criteria_eval.py
"""Unit tests for the Python port of evaluateCollectionMatch (collections.js)."""
from arcade_scanner.core.criteria_eval import (
    matches_date_filter,
    orientation_category,
    resolution_category,
    video_matches,
)

NOW = 1_786_000_000  # fixed "now" for date tests


def _video(**kw) -> dict:
    base = {
        "FilePath": "/lib/clip.mp4", "Size_MB": 500.0, "Status": "OK",
        "codec": "h264", "tags": [], "hidden": False, "favorite": False,
        "Width": 1920, "Height": 1080, "Duration_Sec": 120.0,
        "media_type": "video", "imported_at": NOW - 3600, "mtime": NOW - 3600,
    }
    base.update(kw)
    return base


def _criteria(**kw) -> dict:
    base = {
        "tagLogic": "any",
        "include": {"status": [], "codec": [], "tags": [], "resolution": [],
                    "orientation": [], "media_type": [], "format": []},
        "exclude": {"status": [], "codec": [], "tags": [], "resolution": [],
                    "orientation": [], "media_type": [], "format": []},
        "favorites": None,
        "date": {"type": "any", "relative": None, "from": None, "to": None},
        "size": {"min": None, "max": None},
        "duration": {"min": None, "max": None},
        "search": "",
    }
    base.update(kw)
    return base


def _inc(**kw):
    c = _criteria()
    c["include"].update(kw)
    return c


def _exc(**kw):
    c = _criteria()
    c["exclude"].update(kw)
    return c


class TestHelpers:
    def test_resolution_categories(self):
        assert resolution_category(_video(Width=3840, Height=2160)) == "4k"
        assert resolution_category(_video(Width=1920, Height=1080)) == "1080p"
        assert resolution_category(_video(Width=1280, Height=720)) == "720p"
        assert resolution_category(_video(Width=640, Height=480)) == "sd"
        # max dimension counts — portrait 4k is still 4k
        assert resolution_category(_video(Width=2160, Height=3840)) == "4k"
        # lowercase alias spelling also read
        assert resolution_category({"width": 3840, "height": 2160}) == "4k"

    def test_orientation_categories(self):
        assert orientation_category(_video(Width=1920, Height=1080)) == "landscape"
        assert orientation_category(_video(Width=1080, Height=1920)) == "portrait"
        assert orientation_category(_video(Width=1000, Height=1000)) == "square"
        assert orientation_category(_video(Width=0, Height=0)) == "unknown"

    def test_date_filter(self):
        recent = _video(imported_at=NOW - 3 * 86400)
        old = _video(imported_at=NOW - 40 * 86400)
        f7 = {"type": "relative", "relative": "7d", "from": None, "to": None}
        assert matches_date_filter(recent, f7, NOW) is True
        assert matches_date_filter(old, f7, NOW) is False
        assert matches_date_filter(old, {"type": "any"}, NOW) is True
        assert matches_date_filter(old, None, NOW) is True
        # JS quirk: no timestamp at all fails any real filter
        assert matches_date_filter(_video(imported_at=0, mtime=0), f7, NOW) is False
        # mtime is the fallback when imported_at is 0
        assert matches_date_filter(_video(imported_at=0, mtime=NOW - 3600), f7, NOW) is True


class TestVideoMatches:
    def test_empty_criteria_matches(self):
        assert video_matches(_video(), _criteria()) is True
        assert video_matches(_video(), None) is True

    def test_hidden_never_matches(self):
        assert video_matches(_video(hidden=True), _criteria()) is False

    def test_include_media_type(self):
        c = _inc(media_type=["image"])
        assert video_matches(_video(), c) is False
        assert video_matches(_video(media_type="image"), c) is True

    def test_include_codec_substring(self):
        c = _inc(codec=["hevc"])
        assert video_matches(_video(codec="hevc"), c) is True
        assert video_matches(_video(codec="HEVC"), c) is True
        assert video_matches(_video(codec="h264"), c) is False

    def test_exclude_codec_substring(self):
        c = _exc(codec=["h264"])
        assert video_matches(_video(codec="h264"), c) is False
        assert video_matches(_video(codec="hevc"), c) is True

    def test_include_status_and_optimized_files_special(self):
        assert video_matches(_video(Status="HIGH"), _inc(status=["HIGH"])) is True
        assert video_matches(_video(Status="OK"), _inc(status=["HIGH"])) is False
        c = _inc(status=["optimized_files"])
        assert video_matches(_video(FilePath="/lib/a_opt.mp4"), c) is True
        assert video_matches(_video(FilePath="/lib/a.mp4"), c) is False

    def test_tags_any_vs_all(self):
        v = _video(tags=["gopro", "raw"])
        c_any = _inc(tags=["gopro", "drone"])
        assert video_matches(v, c_any) is True
        c_all = _inc(tags=["gopro", "drone"])
        c_all["tagLogic"] = "all"
        assert video_matches(v, c_all) is False
        c_all2 = _inc(tags=["gopro", "raw"])
        c_all2["tagLogic"] = "all"
        assert video_matches(v, c_all2) is True

    def test_exclude_tags(self):
        assert video_matches(_video(tags=["private"]), _exc(tags=["private"])) is False
        assert video_matches(_video(tags=["work"]), _exc(tags=["private"])) is True

    def test_resolution_and_orientation(self):
        assert video_matches(_video(Width=3840, Height=2160), _inc(resolution=["4k"])) is True
        assert video_matches(_video(), _inc(resolution=["4k"])) is False
        assert video_matches(_video(Width=1080, Height=1920), _inc(orientation=["portrait"])) is True
        assert video_matches(_video(Width=1080, Height=1920), _exc(orientation=["portrait"])) is False

    def test_format_from_extension(self):
        assert video_matches(_video(FilePath="/lib/a.mkv"), _inc(format=["mkv"])) is True
        assert video_matches(_video(FilePath="/lib/a.mp4"), _inc(format=["mkv"])) is False
        assert video_matches(_video(FilePath="/lib/a.mkv"), _exc(format=["mkv"])) is False

    def test_favorites_tristate(self):
        fav, nofav = _video(favorite=True), _video(favorite=False)
        assert video_matches(fav, _criteria(favorites=True)) is True
        assert video_matches(nofav, _criteria(favorites=True)) is False
        assert video_matches(fav, _criteria(favorites=False)) is False
        assert video_matches(nofav, _criteria(favorites=False)) is True
        # None AND the string forms behave like the JS
        assert video_matches(fav, _criteria(favorites=None)) is True
        assert video_matches(nofav, _criteria(favorites="true")) is False

    def test_size_and_duration_bounds(self):
        assert video_matches(_video(Size_MB=2000), _criteria(size={"min": 1000, "max": None})) is True
        assert video_matches(_video(Size_MB=500), _criteria(size={"min": 1000, "max": None})) is False
        assert video_matches(_video(Duration_Sec=30), _criteria(duration={"min": None, "max": 60})) is True
        assert video_matches(_video(Duration_Sec=90), _criteria(duration={"min": None, "max": 60})) is False

    def test_search_matches_filename_and_path(self):
        v = _video(FilePath="/media/GoPro/hero11_dive.mp4")
        assert video_matches(v, _criteria(search="dive")) is True
        assert video_matches(v, _criteria(search="gopro")) is True
        assert video_matches(v, _criteria(search="drone")) is False

    def test_relative_date_include(self):
        c = _criteria(date={"type": "relative", "relative": "7d", "from": None, "to": None})
        assert video_matches(_video(imported_at=NOW - 86400), c, now=NOW) is True
        assert video_matches(_video(imported_at=NOW - 40 * 86400), c, now=NOW) is False

    def test_unknown_criteria_fields_ignored(self):
        c = _criteria()
        c["someFutureField"] = {"x": 1}
        assert video_matches(_video(), c) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_criteria_eval.py -v`
Expected: FAIL with "No module named 'arcade_scanner.core.criteria_eval'"

- [ ] **Step 3: Write the implementation**

```python
# arcade_scanner/core/criteria_eval.py
"""Server-side port of evaluateCollectionMatch (static/collections.js:515).

Operates on the API-dict video shape (SQLiteStore._row_to_api_dict). Kept
faithful to the JS original — quirks included — and pinned by the Node-vm
parity test in tests/test_criteria_parity.py. If you change matching
behaviour here, change collections.js identically or that test fails.
"""
from __future__ import annotations

import time
from typing import Any, Optional

_RELATIVE_SECONDS = {
    "1d": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
    "90d": 90 * 86400,
    "1y": 365 * 86400,
}


def _num(video: dict, *keys: str) -> float:
    for k in keys:
        val = video.get(k)
        if val:
            return float(val)
    return 0.0


def resolution_category(video: dict) -> str:
    max_dim = max(_num(video, "width", "Width"), _num(video, "height", "Height"))
    if max_dim >= 3840:
        return "4k"
    if max_dim >= 1920:
        return "1080p"
    if max_dim >= 1280:
        return "720p"
    return "sd"


def orientation_category(video: dict) -> str:
    width = _num(video, "width", "Width")
    height = _num(video, "height", "Height")
    if width == 0 or height == 0:
        return "unknown"
    ratio = width / height
    if ratio > 1.1:
        return "landscape"
    if ratio < 0.9:
        return "portrait"
    return "square"


def matches_date_filter(video: dict, date_filter: Any, now: int) -> bool:
    if not date_filter or date_filter == "all":
        return True
    if isinstance(date_filter, dict) and date_filter.get("type") == "all":
        return True

    imported = _num(video, "imported_at")
    timestamp = imported if imported > 0 else _num(video, "mtime")
    if timestamp == 0:
        return False

    if isinstance(date_filter, str):
        relative_key: Optional[str] = date_filter
    else:
        relative_key = date_filter.get("relative")

    if relative_key:
        cutoff = now - _RELATIVE_SECONDS.get(relative_key, 0)
        return timestamp >= cutoff
    return True


def _matches_any(video_val: str, arr: list) -> bool:
    if not arr:
        return True
    low = video_val.lower()
    return any(str(v).lower() in low or video_val == v for v in arr)


def _is_excluded(video_val: str, arr: list) -> bool:
    if not arr:
        return False
    low = video_val.lower()
    return any(str(v).lower() in low or video_val == v for v in arr)


def video_matches(video: dict, criteria: Optional[dict], now: Optional[int] = None) -> bool:
    """Return True when `video` (API-dict shape) matches `criteria`."""
    if not criteria:
        return True
    if now is None:
        now = int(time.time())

    status = str(video.get("Status") or "")
    codec = str(video.get("codec") or "").lower()
    video_tags = video.get("tags") or []
    resolution = resolution_category(video)
    orientation = orientation_category(video)
    duration = _num(video, "Duration_Sec")
    size_mb = _num(video, "Size_MB")
    media_type = str(video.get("media_type") or "video")
    file_path = str(video.get("FilePath") or "")

    fmt = str(video.get("format") or "").lower()
    if not fmt and file_path:
        fmt = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    if video.get("hidden"):
        return False

    exc = criteria.get("exclude") or {}
    if media_type in (exc.get("media_type") or []):
        return False
    if _is_excluded(fmt, exc.get("format") or []):
        return False
    if _is_excluded(status, exc.get("status") or []):
        return False
    for exc_codec in exc.get("codec") or []:
        if str(exc_codec).lower() in codec:
            return False
    if any(t in video_tags for t in exc.get("tags") or []):
        return False
    if resolution in (exc.get("resolution") or []):
        return False
    if orientation in (exc.get("orientation") or []):
        return False

    inc = criteria.get("include") or {}
    inc_media = inc.get("media_type") or []
    if inc_media and media_type not in inc_media:
        return False
    inc_format = inc.get("format") or []
    if inc_format and not _matches_any(fmt, inc_format):
        return False

    inc_status = inc.get("status") or []
    if inc_status:
        def _status_match(s: str) -> bool:
            if s == "optimized_files":
                return "_opt" in file_path
            return status == s
        if not any(_status_match(str(s)) for s in inc_status):
            return False

    inc_codec = inc.get("codec") or []
    if inc_codec and not any(str(c).lower() in codec for c in inc_codec):
        return False

    inc_tags = inc.get("tags") or []
    if inc_tags:
        if criteria.get("tagLogic") == "all":
            if not all(t in video_tags for t in inc_tags):
                return False
        else:
            if not any(t in video_tags for t in inc_tags):
                return False

    inc_res = inc.get("resolution") or []
    if inc_res and resolution not in inc_res:
        return False
    inc_ori = inc.get("orientation") or []
    if inc_ori and orientation not in inc_ori:
        return False

    favorites = criteria.get("favorites")
    want_only = favorites is True or favorites == "true"
    want_exclude = favorites is False or favorites == "false"
    if want_only or want_exclude:
        is_fav = bool(video.get("favorite") or video.get("Favorite")
                      or video.get("isFavorite") or video.get("IsFavorite"))
        if want_only and not is_fav:
            return False
        if want_exclude and is_fav:
            return False

    if criteria.get("date") and not matches_date_filter(video, criteria["date"], now):
        return False

    dur = criteria.get("duration")
    if dur:
        if dur.get("min") is not None and duration < dur["min"]:
            return False
        if dur.get("max") is not None and duration > dur["max"]:
            return False

    size = criteria.get("size")
    if size:
        if size.get("min") is not None and size_mb < size["min"]:
            return False
        if size.get("max") is not None and size_mb > size["max"]:
            return False

    search = criteria.get("search")
    if search:
        search_lower = str(search).lower()
        filename = file_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if search_lower not in filename and search_lower not in file_path.lower():
            return False

    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_criteria_eval.py -v`
Expected: all PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner/core/criteria_eval.py tests/test_criteria_eval.py
.venv/bin/mypy arcade_scanner/core/criteria_eval.py
git add arcade_scanner/core/criteria_eval.py tests/test_criteria_eval.py
git commit -m "feat(core): Python port of the collection criteria evaluator"
```

---

### Task 2: JS/Python parity test (Node vm harness)

**Files:**
- Create: `tests/js_eval_harness.js`
- Create: `tests/fixtures/criteria_parity.json`
- Test: `tests/test_criteria_parity.py`

**Interfaces:**
- Consumes: `video_matches(video, criteria, now)` from Task 1; `evaluateCollectionMatch` from `arcade_scanner/server/static/collections.js` (loaded in a Node `vm` context — the file's only top-level side effects are `let` declarations and `window.X =` assignments, so a `window: {}` stub suffices; verified).
- Produces: nothing consumed later — this is the drift guard the spec mandates.

The harness pins `Date.now` inside the vm to `FIXED_NOW * 1000` so relative-date fixtures are deterministic on both sides (Python gets `now=FIXED_NOW`).

- [ ] **Step 1: Write the Node harness**

```javascript
// tests/js_eval_harness.js
// Runs evaluateCollectionMatch from collections.js against a fixture file.
// Usage: node js_eval_harness.js <fixtures.json>   → prints JSON array of booleans
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const src = fs.readFileSync(
    path.join(__dirname, '..', 'arcade_scanner', 'server', 'static', 'collections.js'),
    'utf8'
);

const FIXED_NOW_MS = fixtures.now * 1000;
const PinnedDate = { now: () => FIXED_NOW_MS };

const context = vm.createContext({ window: {}, console, Date: PinnedDate, Math });
vm.runInContext(src, context);

const evaluate = vm.runInContext('evaluateCollectionMatch', context);
const results = fixtures.cases.map(c => !!evaluate(c.video, c.criteria));
process.stdout.write(JSON.stringify(results));
```

- [ ] **Step 2: Write the fixtures**

`tests/fixtures/criteria_parity.json` — `now` is the pinned epoch; every case is `{name, video, criteria, expected}`. Cover each criteria dimension, including the quirks:

```json
{
  "now": 1786000000,
  "cases": [
    {"name": "empty criteria matches",
     "video": {"FilePath": "/lib/a.mp4", "Size_MB": 100, "Status": "OK", "codec": "h264", "tags": [], "hidden": false, "favorite": false, "Width": 1920, "Height": 1080, "Duration_Sec": 60, "media_type": "video", "imported_at": 1785996400, "mtime": 1785996400},
     "criteria": {"tagLogic": "any", "include": {"status": [], "codec": [], "tags": [], "resolution": [], "orientation": [], "media_type": [], "format": []}, "exclude": {"status": [], "codec": [], "tags": [], "resolution": [], "orientation": [], "media_type": [], "format": []}, "favorites": null, "date": {"type": "any", "relative": null, "from": null, "to": null}, "size": {"min": null, "max": null}, "duration": {"min": null, "max": null}, "search": ""},
     "expected": true},
    {"name": "hidden never matches",
     "video": {"FilePath": "/lib/a.mp4", "Size_MB": 100, "Status": "OK", "codec": "h264", "tags": [], "hidden": true, "favorite": false, "Width": 1920, "Height": 1080, "Duration_Sec": 60, "media_type": "video", "imported_at": 1785996400, "mtime": 1785996400},
     "criteria": {"include": {"status": [], "codec": [], "tags": [], "resolution": [], "orientation": [], "media_type": [], "format": []}, "exclude": {"status": [], "codec": [], "tags": [], "resolution": [], "orientation": [], "media_type": [], "format": []}},
     "expected": false}
  ]
}
```

Extend the file to at least 20 cases covering: include/exclude codec substring + case-insensitivity, tags any/all, exclude tags, resolution (incl. portrait-4k), orientation, media_type include+exclude, format from extension, status match + `optimized_files` quirk, favorites true/false/"true"/null, size min/max boundary (exactly at min), duration bounds, search filename vs path, relative date 7d inside/outside, `imported_at: 0, mtime: 0` with a date filter (expected false), and one criteria object with an unknown extra field (expected true). Derive `expected` by hand from the JS logic; the test will tell you if you got one wrong — fix the fixture only after confirming which side is actually right.

- [ ] **Step 3: Write the parity test**

```python
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
```

- [ ] **Step 4: Run the parity test**

Run: `.venv/bin/pytest tests/test_criteria_parity.py -v`
Expected: PASS (or a mismatch naming the exact fixture — resolve by checking the JS logic, then fix fixture or port)

- [ ] **Step 5: Lint, commit**

```bash
.venv/bin/ruff check tests/test_criteria_parity.py
node --check tests/js_eval_harness.js
git add tests/js_eval_harness.js tests/fixtures/criteria_parity.json tests/test_criteria_parity.py
git commit -m "test(core): JS/Python parity fixtures for the criteria evaluator"
```

---

### Task 3: `auto_tag_applied` table + rule storage field

**Files:**
- Modify: `arcade_scanner/database/sqlite_store.py` (`_create_table`; three new methods next to the queue methods)
- Modify: `arcade_scanner/models/user.py` (new `UserVideoData` field)
- Test: `tests/test_sqlite_store.py` (append)

**Interfaces:**
- Produces: `SQLiteStore.get_auto_tag_applied(username: str, rule_id: str) -> set[str]`, `SQLiteStore.mark_auto_tag_applied(username: str, rule_id: str, file_paths: list[str]) -> None` (idempotent), `SQLiteStore.clear_auto_tag_applied(username: str, rule_id: str) -> None`; `UserVideoData.auto_tag_rules: List[Dict[str, Any]]` (default `[]`). Rule shape (created by Task 5): `{"id": str, "name": str, "tag": str, "criteria": dict, "enabled": bool}`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_sqlite_store.py

class TestAutoTagApplied:
    def test_roundtrip_and_idempotence(self, store):
        store.mark_auto_tag_applied("alice", "r1", ["/lib/a.mp4", "/lib/b.mp4"])
        store.mark_auto_tag_applied("alice", "r1", ["/lib/a.mp4"])  # duplicate: no error
        assert store.get_auto_tag_applied("alice", "r1") == {"/lib/a.mp4", "/lib/b.mp4"}

    def test_scoped_per_user_and_rule(self, store):
        store.mark_auto_tag_applied("alice", "r1", ["/lib/a.mp4"])
        assert store.get_auto_tag_applied("bob", "r1") == set()
        assert store.get_auto_tag_applied("alice", "r2") == set()

    def test_clear_rule(self, store):
        store.mark_auto_tag_applied("alice", "r1", ["/lib/a.mp4"])
        store.mark_auto_tag_applied("alice", "r2", ["/lib/a.mp4"])
        store.clear_auto_tag_applied("alice", "r1")
        assert store.get_auto_tag_applied("alice", "r1") == set()
        assert store.get_auto_tag_applied("alice", "r2") == {"/lib/a.mp4"}

    def test_empty_mark_is_noop(self, store):
        store.mark_auto_tag_applied("alice", "r1", [])
        assert store.get_auto_tag_applied("alice", "r1") == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sqlite_store.py -k AutoTag -v`
Expected: FAIL with "has no attribute 'mark_auto_tag_applied'"

- [ ] **Step 3: Implement**

`sqlite_store.py` — in `_create_table`, after the `encoding_queue` block:

```python
        # Auto-tagging apply-once bookkeeping (spec: apply-once semantics —
        # a manually removed tag is never re-applied by its rule)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auto_tag_applied (
                username  TEXT NOT NULL,
                rule_id   TEXT NOT NULL,
                file_path TEXT NOT NULL,
                PRIMARY KEY (username, rule_id, file_path)
            )
        """)
```

New methods next to the queue methods:

```python
    def get_auto_tag_applied(self, username: str, rule_id: str) -> set[str]:
        """file_paths a rule has already been applied to for this user."""
        conn = self._ensure_connection()
        with self._write_lock:
            cursor = conn.execute(
                "SELECT file_path FROM auto_tag_applied WHERE username = ? AND rule_id = ?",
                (username, rule_id),
            )
            return {self._decode_safe_path(row["file_path"]) for row in cursor}

    def mark_auto_tag_applied(self, username: str, rule_id: str, file_paths: list[str]) -> None:
        """Record applied (user, rule, path) triples. Idempotent."""
        if not file_paths:
            return
        conn = self._ensure_connection()
        with self._write_lock:
            conn.executemany(
                "INSERT OR IGNORE INTO auto_tag_applied (username, rule_id, file_path) VALUES (?, ?, ?)",
                [(username, rule_id, self._get_safe_path(p)) for p in file_paths],
            )

    def clear_auto_tag_applied(self, username: str, rule_id: str) -> None:
        """Drop a rule's bookkeeping (rule deleted)."""
        conn = self._ensure_connection()
        with self._write_lock:
            conn.execute(
                "DELETE FROM auto_tag_applied WHERE username = ? AND rule_id = ?",
                (username, rule_id),
            )
```

`models/user.py` — in `UserVideoData`, after `smart_collections`:

```python
    # Auto-Tagging Rules: {"id", "name", "tag", "criteria", "enabled"}
    auto_tag_rules: List[Dict[str, Any]] = Field(default_factory=list, description="Rules that auto-apply a tag to matching files after each scan")
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_sqlite_store.py -v`
Expected: all PASS (including the pre-existing schema tests)

- [ ] **Step 5: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner tests
.venv/bin/mypy arcade_scanner
git add arcade_scanner/database/sqlite_store.py arcade_scanner/models/user.py tests/test_sqlite_store.py
git commit -m "feat(db): auto_tag_applied bookkeeping table and rule storage field"
```

---

### Task 4: Rule engine (`core/auto_tagger.py`) + post-scan hooks

**Files:**
- Create: `arcade_scanner/core/auto_tagger.py`
- Modify: `arcade_scanner/main.py` (between the `run_scan` completion at ~line 89 and the report rebuild at ~line 92)
- Modify: `arcade_scanner/server/routes/files.py` (`_handle_rescan`, between loop teardown ~line 672 and report rebuild ~line 674)
- Test: `tests/test_auto_tagger.py`

**Interfaces:**
- Consumes: `video_matches` (Task 1); `SQLiteStore.get_auto_tag_applied` / `mark_auto_tag_applied` (Task 3); `UserVideoData.auto_tag_rules` / `.tags` / `.favorites` / `.vaulted` / `.available_tags`; `UserStore.get_user` / `get_all_users` / `add_user` (add_user is an upsert; call it ONCE per user per run); `SQLiteStore.get_all_dicts()` for the video list (API-dict shape).
- Produces: `run_auto_tag_rules(username: str, *, user_db, media_db, now: int | None = None) -> dict[str, int]` (rule_id → newly tagged count; empty dict when the user has no enabled rules) and `run_post_scan_auto_tagging(*, user_db=None, media_db=None) -> None` (all users, never raises — this is what the hooks call). `DEFAULT_TAG_COLOR = "#22c55e"`.

Per-user evaluation: the global dict's `tags`/`favorite`/`hidden` fields are overridden with the user's own data before matching (`tags` = `user.data.tags.get(path, [])`, `favorite` = path in `user.data.favorites`, `hidden` = path in `user.data.vaulted`) — per-user state lives in `user_data`, not the media row.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auto_tagger.py
"""Rule engine tests — fake stores, no real DB/filesystem."""
from unittest.mock import MagicMock

from arcade_scanner.core import auto_tagger
from arcade_scanner.models.user import User, UserVideoData

NOW = 1_786_000_000


def _video(path="/lib/gopro/a.mp4", **kw) -> dict:
    base = {"FilePath": path, "Size_MB": 100.0, "Status": "OK", "codec": "h264",
            "tags": [], "hidden": False, "favorite": False, "Width": 1920,
            "Height": 1080, "Duration_Sec": 60.0, "media_type": "video",
            "imported_at": NOW - 3600, "mtime": NOW - 3600}
    base.update(kw)
    return base


def _rule(rule_id="r1", tag="gopro", enabled=True, search="gopro") -> dict:
    return {"id": rule_id, "name": tag, "tag": tag, "enabled": enabled,
            "criteria": {"search": search}}


def _user(rules, tags=None, vaulted=None) -> User:
    return User(username="alice", password_hash="x", salt="y",
                data=UserVideoData(auto_tag_rules=rules, tags=tags or {},
                                   vaulted=vaulted or []))


class FakeMediaDB:
    def __init__(self, videos):
        self._videos = videos
        self.applied: dict[tuple, set] = {}

    def get_all_dicts(self):
        return self._videos

    def get_auto_tag_applied(self, username, rule_id):
        return set(self.applied.get((username, rule_id), set()))

    def mark_auto_tag_applied(self, username, rule_id, paths):
        self.applied.setdefault((username, rule_id), set()).update(paths)


def _user_db(user):
    db = MagicMock()
    db.get_user.return_value = user
    db.get_all_users.return_value = [user]
    return db


def test_applies_tag_and_records_bookkeeping():
    user = _user([_rule()])
    media = FakeMediaDB([_video(), _video("/lib/other/b.mp4")])
    udb = _user_db(user)

    counts = auto_tagger.run_auto_tag_rules("alice", user_db=udb, media_db=media, now=NOW)

    assert counts == {"r1": 1}
    assert user.data.tags["/lib/gopro/a.mp4"] == ["gopro"]
    assert "/lib/other/b.mp4" not in user.data.tags
    assert media.get_auto_tag_applied("alice", "r1") == {"/lib/gopro/a.mp4"}
    udb.add_user.assert_called_once_with(user)


def test_apply_once_removed_tag_not_reapplied():
    user = _user([_rule()])
    media = FakeMediaDB([_video()])
    media.mark_auto_tag_applied("alice", "r1", ["/lib/gopro/a.mp4"])  # already applied earlier

    counts = auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)

    assert counts == {"r1": 0}
    assert user.data.tags == {}  # user removed it by hand; engine must not re-add


def test_merges_into_existing_tags_without_duplicates():
    user = _user([_rule()], tags={"/lib/gopro/a.mp4": ["manual"]})
    media = FakeMediaDB([_video()])
    auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)
    assert user.data.tags["/lib/gopro/a.mp4"] == ["manual", "gopro"]


def test_disabled_rule_skipped_and_no_rules_no_write():
    user = _user([_rule(enabled=False)])
    udb = _user_db(user)
    counts = auto_tagger.run_auto_tag_rules("alice", user_db=udb, media_db=FakeMediaDB([_video()]), now=NOW)
    assert counts == {}
    udb.add_user.assert_not_called()


def test_vaulted_file_never_matches():
    user = _user([_rule()], vaulted=["/lib/gopro/a.mp4"])
    media = FakeMediaDB([_video()])
    counts = auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)
    assert counts == {"r1": 0}


def test_user_tags_feed_rule_criteria():
    rule = {"id": "r2", "name": "combo", "tag": "combo", "enabled": True,
            "criteria": {"include": {"tags": ["gopro"]}}}
    user = _user([rule], tags={"/lib/gopro/a.mp4": ["gopro"]})
    media = FakeMediaDB([_video()])  # global row has NO tags — user data must drive it
    counts = auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)
    assert counts == {"r2": 1}
    assert "combo" in user.data.tags["/lib/gopro/a.mp4"]


def test_tag_definition_created_once():
    user = _user([_rule()])
    auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=FakeMediaDB([_video()]), now=NOW)
    defs = [t for t in user.data.available_tags if t.get("name") == "gopro"]
    assert len(defs) == 1
    assert defs[0]["color"] == auto_tagger.DEFAULT_TAG_COLOR


def test_post_scan_runner_never_raises():
    bad_user_db = MagicMock()
    bad_user_db.get_all_users.side_effect = RuntimeError("boom")
    auto_tagger.run_post_scan_auto_tagging(user_db=bad_user_db, media_db=FakeMediaDB([]))  # must not raise


def test_post_scan_runner_skips_users_without_rules():
    user = _user([])
    udb = _user_db(user)
    auto_tagger.run_post_scan_auto_tagging(user_db=udb, media_db=FakeMediaDB([_video()]))
    udb.add_user.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_auto_tagger.py -v`
Expected: FAIL with "No module named 'arcade_scanner.core.auto_tagger'"

- [ ] **Step 3: Implement the engine**

```python
# arcade_scanner/core/auto_tagger.py
"""Auto-tagging rule engine — applies Smart-Collection-style rules as tags.

Apply-once semantics: (user, rule, path) triples that were tagged once are
recorded in auto_tag_applied and never re-tagged, so manual tag removal is
final. Runs after every scan (run_post_scan_auto_tagging) and on demand via
POST /api/autotag/run.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .criteria_eval import video_matches

logger = logging.getLogger(__name__)

DEFAULT_TAG_COLOR = "#22c55e"


def _ensure_tag_definition(user: Any, tag: str) -> None:
    if any(t.get("name") == tag for t in user.data.available_tags):
        return
    user.data.available_tags.append({"name": tag, "color": DEFAULT_TAG_COLOR, "shortcut": ""})


def run_auto_tag_rules(username: str, *, user_db: Any, media_db: Any,
                       now: Optional[int] = None) -> dict[str, int]:
    """Apply the user's enabled rules. Returns {rule_id: newly_tagged_count}."""
    if now is None:
        now = int(time.time())

    user = user_db.get_user(username)
    if user is None:
        return {}
    rules = [r for r in user.data.auto_tag_rules if r.get("enabled")]
    if not rules:
        return {}

    videos = media_db.get_all_dicts()
    vaulted = set(user.data.vaulted)
    favorites = set(user.data.favorites)
    counts: dict[str, int] = {}
    changed = False

    for rule in rules:
        rule_id = str(rule.get("id") or "")
        tag = str(rule.get("tag") or "")
        if not rule_id or not tag:
            continue
        applied = media_db.get_auto_tag_applied(username, rule_id)
        newly: list[str] = []
        for video in videos:
            path = str(video.get("FilePath") or "")
            if not path or path in applied:
                continue
            effective = {**video,
                         "tags": user.data.tags.get(path, []),
                         "favorite": path in favorites,
                         "hidden": path in vaulted}
            if not video_matches(effective, rule.get("criteria"), now=now):
                continue
            current = user.data.tags.setdefault(path, [])
            if tag not in current:
                current.append(tag)
            newly.append(path)
        if newly:
            _ensure_tag_definition(user, tag)
            media_db.mark_auto_tag_applied(username, rule_id, newly)
            changed = True
        counts[rule_id] = len(newly)

    if changed:
        user_db.add_user(user)  # upsert; exactly one write per run
    return counts


def run_post_scan_auto_tagging(*, user_db: Any = None, media_db: Any = None) -> None:
    """Run all users' rules after a scan. Defensive: never raises."""
    try:
        if user_db is None:
            from ..database.user_store import user_db as _udb
            user_db = _udb
        if media_db is None:
            from ..database.sqlite_store import db as _db
            media_db = _db
        for user in user_db.get_all_users():
            if not any(r.get("enabled") for r in user.data.auto_tag_rules):
                continue
            try:
                counts = run_auto_tag_rules(user.username, user_db=user_db, media_db=media_db)
                total = sum(counts.values())
                if total:
                    print(f"🏷️ Auto-Tagging: {total} neue Tags für {user.username}")
            except Exception:
                logger.exception("Auto-tagging failed for user %s", user.username)
    except Exception:
        logger.exception("Auto-tagging post-scan run failed")
```

Note: the singleton import names must match the actual modules — check `arcade_scanner/database/__init__.py` / how `main.py` imports `db` and `user_db`, and use the same import paths the rest of the codebase uses (e.g. `from arcade_scanner.database.sqlite_store import db`). Adjust the two lazy imports if the real singletons live elsewhere; the tests always inject fakes so they don't depend on this.

- [ ] **Step 4: Wire the two post-scan hooks**

`arcade_scanner/main.py` — inside `background_scan()`, after the `asyncio.run(mgr.run_scan(...))` call and its newline print (~line 89), BEFORE the report rebuild:

```python
            from arcade_scanner.core.auto_tagger import run_post_scan_auto_tagging
            run_post_scan_auto_tagging()
```

`arcade_scanner/server/routes/files.py` — in `_handle_rescan`, after the event-loop teardown (~line 672), BEFORE the report rebuild:

```python
        from arcade_scanner.core.auto_tagger import run_post_scan_auto_tagging
        run_post_scan_auto_tagging()
```

(Both call sites rely on `run_post_scan_auto_tagging` swallowing all errors — a broken rule must never break a scan.)

- [ ] **Step 5: Run tests + the touched suites**

Run: `.venv/bin/pytest tests/test_auto_tagger.py tests/test_routes_files.py tests/test_scanner_manager.py -v`
Expected: all PASS (files-route tests still green: the hook is inside `_handle_rescan`, existing tests for it must not break — if one does because of the new import, patch `run_post_scan_auto_tagging` in that test following the file's patching style)

- [ ] **Step 6: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner tests
.venv/bin/mypy arcade_scanner
git add arcade_scanner/core/auto_tagger.py arcade_scanner/main.py arcade_scanner/server/routes/files.py tests/test_auto_tagger.py tests/test_routes_files.py
git commit -m "feat(core): auto-tagging rule engine with post-scan hooks"
```

---

### Task 5: `/api/autotag` routes

**Files:**
- Create: `arcade_scanner/server/routes/autotag.py`
- Modify: `arcade_scanner/server/api_handler.py` (GET dispatch ~line 398: add `autotag` to the import, insert `if autotag.handle_get(self): return` before `files.handle_get`; POST dispatch ~line 903: add `autotag` to the import, insert `if autotag.handle_post(self): return` after `tags.handle_post`)
- Test: `tests/test_routes_autotag.py`

**Interfaces:**
- Consumes: `run_auto_tag_rules` (Task 4); `UserVideoData.auto_tag_rules` (Task 3); `SQLiteStore.clear_auto_tag_applied` (Task 3); `user_db.get_user`/`add_user`.
- Produces:
  - `GET /api/autotag/rules` → `{"rules": [...]}` (session required)
  - `POST /api/autotag/rules` body `{"action": "create", "name": str, "tag": str, "criteria": dict}` → `{"success": true, "rule": {...}}` (id = `uuid4().hex`, `enabled: true`); `{"action": "delete", "id": str}` → also calls `clear_auto_tag_applied`; `{"action": "toggle", "id": str, "enabled": bool}`
  - `POST /api/autotag/run` → `{"success": true, "results": {rule_id: count}, "total": int}`
  - `handle_get(handler) -> bool`, `handle_post(handler) -> bool`
  - Deliberate deviation from the spec's action list: no `update` action (YAGNI) — editing a rule = delete + re-create in the modal. Reviewers: this is plan-intended, not an omission.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_autotag.py
"""Route tests for /api/autotag/* — FakeHandler pattern from test_routes_queue.py."""
import json
from unittest.mock import MagicMock, patch

from arcade_scanner.models.user import User, UserVideoData
from arcade_scanner.server.routes import autotag


class FakeRFile:
    def __init__(self, payload=b""):
        self._payload = payload
        self._pos = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._payload) - self._pos
        chunk = self._payload[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


class FakeHandler:
    def __init__(self, path, user="alice", body=None):
        self.path = path
        self._user = user
        payload = json.dumps(body).encode() if body is not None else b""
        self.rfile = FakeRFile(payload)
        self.headers = {"Content-Length": str(len(payload))}
        self.wfile = MagicMock()
        self.status = None
        self.error = None

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


def _user(rules=()):
    return User(username="alice", password_hash="x", salt="y",
                data=UserVideoData(auto_tag_rules=list(rules)))


def _rule(rule_id="r1", tag="gopro", enabled=True):
    return {"id": rule_id, "name": tag, "tag": tag, "enabled": enabled, "criteria": {"search": tag}}


def run(handler, user=None, media_db=None, post=False):
    user = user if user is not None else _user()
    user_db = MagicMock()
    user_db.get_user.return_value = user
    media_db = media_db or MagicMock()
    with patch.object(autotag, "_get_deps", return_value=(media_db, user_db)):
        handled = autotag.handle_post(handler) if post else autotag.handle_get(handler)
    return handled, user, user_db, media_db


def test_unrelated_paths_not_handled():
    assert run(FakeHandler("/api/other"))[0] is False
    assert run(FakeHandler("/api/other", body={}), post=True)[0] is False


def test_rules_require_session():
    h = FakeHandler("/api/autotag/rules", user=None)
    handled, *_ = run(h)
    assert handled is True
    assert h.error == 401
    h2 = FakeHandler("/api/autotag/run", user=None, body={})
    handled2, *_ = run(h2, post=True)
    assert handled2 is True
    assert h2.error == 401


def test_list_rules():
    h = FakeHandler("/api/autotag/rules")
    handled, *_ = run(h, user=_user([_rule()]))
    assert handled is True
    assert h.body()["rules"][0]["tag"] == "gopro"


def test_create_rule():
    h = FakeHandler("/api/autotag/rules", body={"action": "create", "name": "GoPro",
                                                "tag": "gopro", "criteria": {"search": "gopro"}})
    handled, user, user_db, _ = run(h, post=True)
    assert handled is True
    body = h.body()
    assert body["success"] is True
    assert body["rule"]["enabled"] is True
    assert len(body["rule"]["id"]) == 32  # uuid4().hex
    assert len(user.data.auto_tag_rules) == 1
    user_db.add_user.assert_called_once()


def test_create_rejects_missing_tag():
    h = FakeHandler("/api/autotag/rules", body={"action": "create", "name": "x", "criteria": {}})
    handled, *_ = run(h, post=True)
    assert handled is True
    assert h.error == 400


def test_delete_rule_clears_bookkeeping():
    h = FakeHandler("/api/autotag/rules", body={"action": "delete", "id": "r1"})
    handled, user, user_db, media_db = run(h, user=_user([_rule()]), post=True)
    assert handled is True
    assert user.data.auto_tag_rules == []
    media_db.clear_auto_tag_applied.assert_called_once_with("alice", "r1")
    user_db.add_user.assert_called_once()


def test_toggle_rule():
    h = FakeHandler("/api/autotag/rules", body={"action": "toggle", "id": "r1", "enabled": False})
    handled, user, *_ = run(h, user=_user([_rule()]), post=True)
    assert handled is True
    assert user.data.auto_tag_rules[0]["enabled"] is False


def test_unknown_action_400():
    h = FakeHandler("/api/autotag/rules", body={"action": "frobnicate"})
    handled, *_ = run(h, post=True)
    assert handled is True
    assert h.error == 400


def test_run_endpoint():
    h = FakeHandler("/api/autotag/run", body={})
    with patch.object(autotag, "run_auto_tag_rules", return_value={"r1": 3}) as mock_run:
        handled, _, user_db, media_db = run(h, post=True)
    assert handled is True
    body = h.body()
    assert body == {"success": True, "results": {"r1": 3}, "total": 3}
    mock_run.assert_called_once_with("alice", user_db=user_db, media_db=media_db)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_routes_autotag.py -v`
Expected: FAIL with "No module named ... routes.autotag"

- [ ] **Step 3: Implement the route module**

```python
# arcade_scanner/server/routes/autotag.py
"""Auto-tagging rules: CRUD (GET/POST /api/autotag/rules) + manual run."""
import json
import uuid

from arcade_scanner.core.auto_tagger import run_auto_tag_rules
from arcade_scanner.server.response_helpers import send_json


def _get_deps():
    from arcade_scanner.server.api_handler import db, user_db
    return db, user_db


def _read_body(handler) -> dict:
    from arcade_scanner.server.api_handler import MAX_REQUEST_SIZE
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0 or length > MAX_REQUEST_SIZE:
        return {}
    data = json.loads(handler.rfile.read(length).decode("utf-8"))
    return data if isinstance(data, dict) else {}


def handle_get(handler) -> bool:
    if handler.path != "/api/autotag/rules":
        return False
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return True
    _, user_db = _get_deps()
    u = user_db.get_user(user_name)
    rules = u.data.auto_tag_rules if u else []
    send_json(handler, {"rules": rules})
    return True


def handle_post(handler) -> bool:
    if handler.path == "/api/autotag/rules":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        try:
            body = _read_body(handler)
        except (json.JSONDecodeError, ValueError):
            handler.send_error(400, "Invalid JSON")
            return True

        media_db, user_db = _get_deps()
        u = user_db.get_user(user_name)
        if not u:
            handler.send_error(401, "Unauthorized")
            return True

        action = body.get("action")
        if action == "create":
            tag = str(body.get("tag") or "").strip()
            criteria = body.get("criteria")
            if not tag or not isinstance(criteria, dict):
                handler.send_error(400, "tag and criteria required")
                return True
            rule = {"id": uuid.uuid4().hex,
                    "name": str(body.get("name") or tag),
                    "tag": tag, "criteria": criteria, "enabled": True}
            u.data.auto_tag_rules.append(rule)
            user_db.add_user(u)
            send_json(handler, {"success": True, "rule": rule})
            return True

        if action == "delete":
            rule_id = str(body.get("id") or "")
            before = len(u.data.auto_tag_rules)
            u.data.auto_tag_rules = [r for r in u.data.auto_tag_rules if r.get("id") != rule_id]
            if len(u.data.auto_tag_rules) == before:
                handler.send_error(404, "Rule not found")
                return True
            media_db.clear_auto_tag_applied(user_name, rule_id)
            user_db.add_user(u)
            send_json(handler, {"success": True})
            return True

        if action == "toggle":
            rule_id = str(body.get("id") or "")
            for r in u.data.auto_tag_rules:
                if r.get("id") == rule_id:
                    r["enabled"] = bool(body.get("enabled"))
                    user_db.add_user(u)
                    send_json(handler, {"success": True, "rule": r})
                    return True
            handler.send_error(404, "Rule not found")
            return True

        handler.send_error(400, "Unknown action")
        return True

    if handler.path == "/api/autotag/run":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        try:
            media_db, user_db = _get_deps()
            results = run_auto_tag_rules(user_name, user_db=user_db, media_db=media_db)
            send_json(handler, {"success": True, "results": results,
                                "total": sum(results.values())})
        except Exception as e:
            print(f"❌ Auto-tag run failed: {e}")
            handler.send_error(500, str(e))
        return True

    return False
```

- [ ] **Step 4: Wire the dispatches**

`api_handler.py` GET (~line 398): import becomes `from .routes import autotag, candidates, duplicates, files, queue, settings, tags`; insert before `files.handle_get`:

```python
            if autotag.handle_get(self):
                return
```

`api_handler.py` POST (~line 903): import becomes `from .routes import autotag, duplicates, queue, settings, tags`; insert after `tags.handle_post`:

```python
            if autotag.handle_post(self):
                return
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_routes_autotag.py tests/test_route_interface.py -v`
Expected: all PASS (make the module conform if `test_route_interface.py` imposes a contract on route modules)

- [ ] **Step 6: Lint, typecheck, commit**

```bash
.venv/bin/ruff check arcade_scanner tests
.venv/bin/mypy arcade_scanner
git add arcade_scanner/server/routes/autotag.py arcade_scanner/server/api_handler.py tests/test_routes_autotag.py
git commit -m "feat(web): /api/autotag rule CRUD and manual run endpoints"
```

---

### Task 6: UI — rule creation in the collection modal + settings section

**Files:**
- Create: `arcade_scanner/server/static/autotag.js`
- Modify: `arcade_scanner/templates/components.py` (collection modal footer ~line 1345; settings nav ~line 1654; new `content-autotagging` panel after the queue panel ~line 2101)
- Modify: `arcade_scanner/server/static/settings.js` (headers map ~line 367-391; nav click handler in `initSettingsNavigation` ~line 311-359)
- Modify: `arcade_scanner/templates/dashboard_template.py` (script tag after `settings.js`)
- Modify: `tests/test_dom_contract.py` (`DYNAMIC_IDS`)
- Test: static suites (`test_js_syntax.py`, `test_dom_contract.py`, `test_js_completeness.py`, `test_js_runtime_patterns.py`, `test_dashboard_template.py`)

**Interfaces:**
- Consumes: `POST/GET /api/autotag/rules`, `POST /api/autotag/run` (Task 5); `collectionCriteriaNew` (module-level criteria object in `collections.js`, populated by the query-builder modal); `showToast(msg, type)` global.
- Produces: window-level functions (top-level `function` declarations): `saveAutoTagRule()`, `renderAutoTagRules()`, `toggleAutoTagRule(id, enabled)`, `deleteAutoTagRule(id)`, `runAutoTagRules()`. Static IDs: `autoTagName` (modal input), `content-autotagging`, `autotagRulesList`, `autotagRunBtn`. Dynamic ID prefix: `atrule-`.

- [ ] **Step 1: Write `autotag.js`**

```javascript
// arcade_scanner/server/static/autotag.js
/**
 * Auto-Tagging Rules UI.
 * - saveAutoTagRule(): called from the collection modal — turns the currently
 *   built query (collectionCriteriaNew from collections.js) into a rule.
 * - Settings section: list, toggle, delete, run now.
 */

function saveAutoTagRule() {
    const input = document.getElementById('autoTagName');
    const tag = (input?.value || '').trim().toLowerCase();
    if (!tag) {
        if (typeof showToast === 'function') showToast('Tag-Name fehlt', 'warning');
        return;
    }
    const criteria = (typeof collectionCriteriaNew !== 'undefined' && collectionCriteriaNew)
        ? JSON.parse(JSON.stringify(collectionCriteriaNew)) : null;
    if (!criteria) {
        if (typeof showToast === 'function') showToast('Keine Kriterien gesetzt', 'warning');
        return;
    }
    fetch('/api/autotag/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'create', name: tag, tag: tag, criteria: criteria })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                if (typeof showToast === 'function') showToast(`Auto-Tag-Regel "${tag}" gespeichert`, 'success');
                input.value = '';
            } else {
                if (typeof showToast === 'function') showToast(data.error || 'Speichern fehlgeschlagen', 'error');
            }
        })
        .catch(() => { if (typeof showToast === 'function') showToast('Speichern fehlgeschlagen', 'error'); });
}

function renderAutoTagRules() {
    const list = document.getElementById('autotagRulesList');
    if (!list) return;
    fetch('/api/autotag/rules')
        .then(r => r.json())
        .then(data => {
            const rules = data.rules || [];
            if (!rules.length) {
                list.innerHTML = '<div class="text-sm text-gray-400">Noch keine Regeln — im Collection-Editor eine Query bauen und als Auto-Tag-Regel speichern.</div>';
                return;
            }
            list.innerHTML = rules.map(r => `
                <div id="atrule-${r.id}" class="flex items-center gap-3 p-2 rounded-lg bg-black/5 dark:bg-white/5">
                    <input type="checkbox" ${r.enabled ? 'checked' : ''}
                           onchange="toggleAutoTagRule('${r.id}', this.checked)">
                    <div class="min-w-0 flex-1">
                        <div class="text-sm font-medium truncate">${r.name}</div>
                        <div class="text-xs text-gray-400">Tag: ${r.tag}</div>
                    </div>
                    <button onclick="deleteAutoTagRule('${r.id}')"
                            class="text-xs text-red-400 hover:text-red-300">Löschen</button>
                </div>`).join('');
        })
        .catch(() => { list.innerHTML = '<div class="text-sm text-red-400">Regeln konnten nicht geladen werden.</div>'; });
}

function toggleAutoTagRule(id, enabled) {
    fetch('/api/autotag/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle', id: id, enabled: enabled })
    }).then(() => renderAutoTagRules());
}

function deleteAutoTagRule(id) {
    fetch('/api/autotag/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id: id })
    }).then(() => renderAutoTagRules());
}

function runAutoTagRules() {
    const btn = document.getElementById('autotagRunBtn');
    if (btn) btn.disabled = true;
    fetch('/api/autotag/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
        .then(r => r.json())
        .then(data => {
            if (typeof showToast === 'function') {
                showToast(data.success ? `${data.total} Tags vergeben` : 'Lauf fehlgeschlagen',
                          data.success ? 'success' : 'error');
            }
        })
        .catch(() => { if (typeof showToast === 'function') showToast('Lauf fehlgeschlagen', 'error'); })
        .finally(() => { if (btn) btn.disabled = false; });
}

window.saveAutoTagRule = saveAutoTagRule;
window.renderAutoTagRules = renderAutoTagRules;
window.toggleAutoTagRule = toggleAutoTagRule;
window.deleteAutoTagRule = deleteAutoTagRule;
window.runAutoTagRules = runAutoTagRules;
```

- [ ] **Step 2: Template edits**

`components.py` — collection modal footer: read lines 1333-1352 first, then insert a compact row ABOVE the existing Cancel/Save button row (`~1345`), inside the footer container:

```html
            <div class="flex items-center gap-2 mr-auto">
                <input id="autoTagName" type="text" placeholder="auto-tag…"
                       class="w-32 px-2 py-1.5 rounded-lg text-xs bg-black/5 dark:bg-white/10 border border-black/10 dark:border-white/10">
                <button onclick="saveAutoTagRule()"
                        class="px-3 py-1.5 rounded-lg text-xs font-bold bg-arcade-cyan/20 text-arcade-cyan hover:bg-arcade-cyan/30"
                        title="Aktuelle Kriterien als Auto-Tag-Regel speichern">Als Regel</button>
            </div>
```

(Adapt the wrapper to the footer's actual flex structure so Cancel/Save stay right-aligned; the diff should keep the existing buttons untouched.)

`components.py` — settings nav (after the queue nav item, ~line 1654):

```html
                <button class="settings-nav-item w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm" data-section="autotagging">
                    <span class="material-icons text-[18px]">sell</span>
                    <span>Auto-Tagging</span>
                </button>
```

(Copy the exact class string from the sibling nav items at lines 1618-1654 — they must stay identical.)

`components.py` — new panel after the queue panel (`id="content-queue"`, ~line 2101, insert after its closing `</div>`):

```html
            <div class="content-section hidden space-y-6" id="content-autotagging">
                <section>
                    <div class="flex items-center justify-between mb-3">
                        <h3 class="text-sm font-bold uppercase tracking-wider text-gray-500">Regeln</h3>
                        <button id="autotagRunBtn" onclick="runAutoTagRules()"
                                class="px-3 py-1.5 rounded-lg text-xs font-bold bg-arcade-cyan/20 text-arcade-cyan hover:bg-arcade-cyan/30">
                            Jetzt ausführen
                        </button>
                    </div>
                    <div id="autotagRulesList" class="space-y-2"></div>
                </section>
            </div>
```

`settings.js` — headers map (~line 367): add

```javascript
            autotagging: { title: 'Auto-Tagging', subtitle: 'Regeln, die passenden Dateien automatisch Tags geben' },
```

`settings.js` — in `initSettingsNavigation`'s nav click handler (read lines 311-359 first; after the call to `updateSettingsHeader(...)` / section switch), add:

```javascript
            if (sectionId === 'autotagging' && typeof renderAutoTagRules === 'function') {
                renderAutoTagRules();
            }
```

(Use the handler's actual variable name for the section id — verify it in the file.)

`dashboard_template.py` — script tag after the `settings.js` line:

```python
    <script src="/static/autotag.js?v={int(time.time())}"></script>
```

`tests/test_dom_contract.py` — extend `DYNAMIC_IDS`:

```python
    # Von autotag.js dynamisch erzeugte Regel-Zeilen:
    "atrule-",
```

- [ ] **Step 3: Run the static suites**

Run: `.venv/bin/pytest tests/test_js_syntax.py tests/test_dom_contract.py tests/test_js_completeness.py tests/test_js_runtime_patterns.py tests/test_dashboard_template.py -v`
Expected: all PASS (fix any undefined-global/missing-ID findings per the tests' conventions)

- [ ] **Step 4: Manual smoke test**

Run the server (`.venv/bin/python3 -m arcade_scanner.main --skip-setup`), log in, open the collection modal, build a query (e.g. search term), enter a tag name, click "Als Regel" → success toast. Open Settings → Auto-Tagging: rule listed, toggle works, "Jetzt ausführen" shows "N Tags vergeben" and the tags appear on matching files after reload. Rescan (settings) must complete without errors.

- [ ] **Step 5: Lint, commit**

```bash
.venv/bin/ruff check .
git add arcade_scanner/server/static/autotag.js arcade_scanner/templates/components.py \
        arcade_scanner/server/static/settings.js arcade_scanner/templates/dashboard_template.py \
        tests/test_dom_contract.py
git commit -m "feat(web): Auto-Tagging-Regeln — Modal-Speichern und Settings-Verwaltung"
```

---

### Task 7: Changelog + full verification

**Files:**
- Modify: `CHANGELOG.md` (`[Unreleased]`), `ROADMAP.md`

- [ ] **Step 1: CHANGELOG entry** — under `## [Unreleased]`:

```markdown
### Added — Auto-Tagging Rules
- **Auto-Tag-Regeln**: eine Regel = Smart-Collection-Query + Ziel-Tag. Regeln
  laufen serverseitig nach jedem Scan und auf Knopfdruck (Settings →
  Auto-Tagging). Apply-once: ein manuell entferntes Tag wird nie erneut
  vergeben. Anlegen direkt im Collection-Editor ("Als Regel").
- **Server-seitige Query-Auswertung**: Python-Port des Collection-Evaluators,
  per Node-Paritätstest gegen `collections.js` gepinnt.
```

`ROADMAP.md`: add a completed entry in the file's established style (✅ + date + feature bullets).

- [ ] **Step 2: Full verification**

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy arcade_scanner
```

Expected: everything green.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md ROADMAP.md
git commit -m "docs: changelog & roadmap for auto-tagging rules"
```

Then finish per `superpowers:finishing-a-development-branch` (PR into `dev`, separate from any other pending PR).
