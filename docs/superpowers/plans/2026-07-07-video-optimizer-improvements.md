# Video Optimizer Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seven optimizer improvements: history-seeded starting Q, HDR/10-bit safety, two-pass loudnorm, scene-aware SSIM sampling, decode-verify before replace, sample-based quality pre-search, and schedule/battery awareness for the remote worker.

**Architecture:** Pure/parseable logic goes into a new sibling module `scripts/optimizer_utils.py` (importable by `video_optimizer.py`, `mac_worker.py`, and tests — scripts/ modules already import each other via same-dir sys.path). All ffmpeg/ffprobe-invoking code stays in `scripts/video_optimizer.py`. Every feature degrades gracefully: on any helper failure the optimizer falls back to today's behavior.

**Tech Stack:** Python 3.10+ stdlib only (no new deps), ffmpeg/ffprobe 8.1+, pytest.

## Global Constraints

- No new runtime dependencies (repo policy: pydantic, Pillow, imagehash only; scripts are stdlib-only).
- `scripts/video_optimizer.py` must remain runnable standalone (guarded imports, graceful fallbacks).
- Conventional commits with scope, e.g. `feat(optimizer): ...`.
- Tests live in `tests/`, run with `.venv/bin/pytest tests/<file> -q`.
- ffmpeg-dependent tests must be skippable: `pytest.mark.skipif(shutil.which("ffmpeg") is None, ...)`.
- Existing behavior contracts: `process_file` returns `(success, bytes_saved)`; `last_encode_result` / `batch_stats` keys must keep working for `batch_controller.py`.

## Test file setup

Both new test files start with this header so `scripts/` is importable:

```python
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
```

---

### Task 1: `optimizer_utils.py` — encode history & starting-Q suggestion

**Files:**
- Create: `scripts/optimizer_utils.py`
- Modify: `scripts/video_optimizer.py` (`last_encode_result` fields, `main()` history append, binary-search first-probe bias in `process_file`)
- Test: `tests/test_optimizer_utils.py`

**Interfaces:**
- Produces: `bitrate_class(kbps: float) -> str` ('low'|'med'|'high'|'ultra'), `resolution_class(height: int) -> str`, `append_encode_history(record: dict, history_path: Path) -> None` (JSONL append), `suggest_q_from_history(encoder_key: str, height: int, source_kbps: float, history_path: Path, min_samples: int = 3) -> int | None` (median winning Q), `nearest_quality_index(quality_values: list[int], q: int) -> int`.

- [ ] **Step 1: Write failing tests** in `tests/test_optimizer_utils.py`:

```python
import json
from optimizer_utils import (
    bitrate_class, resolution_class, append_encode_history,
    suggest_q_from_history, nearest_quality_index,
)

class TestHistory:
    def test_bitrate_class_buckets(self):
        assert bitrate_class(1000) == "low"
        assert bitrate_class(5000) == "med"
        assert bitrate_class(15000) == "high"
        assert bitrate_class(50000) == "ultra"

    def test_resolution_class_buckets(self):
        assert resolution_class(480) == "sd"
        assert resolution_class(720) == "720"
        assert resolution_class(1080) == "1080"
        assert resolution_class(1440) == "1440"
        assert resolution_class(2160) == "2160"

    def test_append_and_suggest_median(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        for q in (55, 65, 60, 60, 58):
            append_encode_history(
                {"encoder": "videotoolbox", "height": 1080,
                 "source_kbps": 12000, "q": q, "ssim": 0.97, "saved_pct": 40.0},
                history_path=hist,
            )
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) == 60

    def test_suggest_needs_min_samples(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        append_encode_history(
            {"encoder": "videotoolbox", "height": 1080,
             "source_kbps": 12000, "q": 60, "ssim": 0.97, "saved_pct": 40.0},
            history_path=hist,
        )
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) is None

    def test_suggest_ignores_other_buckets(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        for _ in range(5):
            append_encode_history(
                {"encoder": "nvenc", "height": 2160,
                 "source_kbps": 40000, "q": 30, "ssim": 0.97, "saved_pct": 40.0},
                history_path=hist,
            )
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) is None

    def test_suggest_survives_corrupt_lines(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        hist.write_text("not json\n{\"broken\":\n")
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) is None

    def test_nearest_quality_index(self):
        assert nearest_quality_index([75, 65, 55, 45], 58) == 2
        assert nearest_quality_index([24, 28, 32, 36, 40, 44], 30) == 1
```

- [ ] **Step 2: Run tests, verify FAIL** (`ModuleNotFoundError: optimizer_utils`)
- [ ] **Step 3: Implement** `scripts/optimizer_utils.py`:

```python
"""optimizer_utils.py — pure helper logic for the video optimizer.

Kept free of ffmpeg/subprocess calls so it is unit-testable and importable
by video_optimizer.py, mac_worker.py and the test suite alike.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

DEFAULT_HISTORY_PATH = Path.home() / ".arcade-scanner" / "logs" / "encode_history.jsonl"


def bitrate_class(kbps: float) -> str:
    if kbps < 2500: return "low"
    if kbps < 8000: return "med"
    if kbps < 20000: return "high"
    return "ultra"


def resolution_class(height: int) -> str:
    if height <= 576: return "sd"
    if height <= 800: return "720"
    if height <= 1200: return "1080"
    if height <= 1600: return "1440"
    return "2160"


def append_encode_history(record: dict, history_path: Path = DEFAULT_HISTORY_PATH) -> None:
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # history is best-effort, never break an encode over it


def suggest_q_from_history(encoder_key: str, height: int, source_kbps: float,
                           history_path: Path = DEFAULT_HISTORY_PATH,
                           min_samples: int = 3) -> int | None:
    """Median winning Q for this (encoder, resolution class, bitrate class) bucket."""
    try:
        if not history_path.exists():
            return None
        want = (encoder_key, resolution_class(height), bitrate_class(source_kbps))
        qs = []
        with open(history_path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = (rec.get("encoder"),
                       resolution_class(int(rec.get("height", 0))),
                       bitrate_class(float(rec.get("source_kbps", 0))))
                if key == want and rec.get("q") is not None:
                    qs.append(int(rec["q"]))
        if len(qs) < min_samples:
            return None
        return int(statistics.median(qs))
    except (OSError, ValueError, TypeError):
        return None


def nearest_quality_index(quality_values: list[int], q: int) -> int:
    return min(range(len(quality_values)), key=lambda i: abs(quality_values[i] - q))
```

- [ ] **Step 4: Run tests, verify PASS**
- [ ] **Step 5: Integrate into `video_optimizer.py`:**
  - Guarded import next to the existing core imports: `try: from optimizer_utils import (...); OPTIMIZER_UTILS_AVAILABLE = True except ImportError: OPTIMIZER_UTILS_AVAILABLE = False` (scripts dir is already on sys.path when run directly; add `sys.path.insert(0, str(Path(__file__).parent))` guard like mac_worker does).
  - In `process_file` after `info = get_video_info(...)`: set `last_encode_result['height'] = info['height']` and `last_encode_result['source_kbps'] = (size_before * 8) / (info['duration'] * 1000)`. Add both keys (default None) to the `last_encode_result` initializer dict at module top.
  - In `process_file` binary-search setup (before the `while low <= high` loop): if utils available and no q_override, call `suggest_q_from_history(profile['_encoder_key'], ...)`; on hit compute `first_mid = nearest_quality_index(quality_values, suggested)` and bias only the first loop iteration: `mid = first_mid if (first_mid is not None and low <= first_mid <= high) else (low + high) // 2; first_mid = None`. Print `History Seed: starting at Q=...`.
  - `profile['_encoder_key']`: set once in `main()` after profile selection (`profile['_encoder_key'] = encoder_key`) and in `apply_encoding_preset` copies it through automatically (it returns a modified dict copy — verify).
  - In `main()` after `write_encode_log(...)`: on `status == 'success'`, `append_encode_history({...})` with encoder_key, height, source_kbps, q, ssim, saved_pct.
- [ ] **Step 6: Run full suite** (`.venv/bin/pytest -q`) — no regressions.
- [ ] **Step 7: Commit** `feat(optimizer): seed binary search starting Q from encode history`

---

### Task 2: HDR / 10-bit safety

**Files:**
- Modify: `scripts/optimizer_utils.py` (detection + profile adjustment), `scripts/video_optimizer.py` (`get_video_info` fields, `build_ffmpeg_command` color args, `process_file` skip/adjust)
- Test: `tests/test_optimizer_utils.py`

**Interfaces:**
- Produces: `is_hdr_or_10bit(info: dict) -> bool`, `apply_hdr_adjustments(profile: dict, info: dict) -> dict | None` (returns adjusted profile copy with 10-bit args + `color_args` list, or None = encoder can't do it → skip file).
- `build_ffmpeg_command` gains kwarg `color_args: list | None = None`; when None it emits today's bt709 trio.

- [ ] **Step 1: Failing tests:**

```python
from optimizer_utils import is_hdr_or_10bit, apply_hdr_adjustments

SDR = {"pix_fmt": "yuv420p", "color_transfer": "bt709", "color_primaries": "bt709"}
HDR10 = {"pix_fmt": "yuv420p10le", "color_transfer": "smpte2084", "color_primaries": "bt2020"}
HLG = {"pix_fmt": "yuv420p10le", "color_transfer": "arib-std-b67", "color_primaries": "bt2020"}

class TestHdr:
    def test_sdr_not_flagged(self):
        assert is_hdr_or_10bit(SDR) is False

    def test_hdr10_and_hlg_flagged(self):
        assert is_hdr_or_10bit(HDR10) is True
        assert is_hdr_or_10bit(HLG) is True

    def test_10bit_sdr_flagged(self):
        assert is_hdr_or_10bit({**SDR, "pix_fmt": "yuv420p10le"}) is True

    def test_missing_fields_not_flagged(self):
        assert is_hdr_or_10bit({}) is False

    def test_videotoolbox_gets_main10_p010(self):
        profile = {"codec": "hevc_videotoolbox",
                   "encoder_args": ["-profile:v", "main", "-allow_sw", "0"],
                   "video_filter": "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2"}
        adj = apply_hdr_adjustments(profile, HDR10)
        assert adj is not None
        assert "main10" in adj["encoder_args"]
        assert "main" not in [a for a in adj["encoder_args"] if a == "main"]
        assert "p010le" in adj["video_filter"]
        assert "-color_trc" in adj["color_args"]
        assert "smpte2084" in adj["color_args"]
        assert "bt2020" in " ".join(adj["color_args"])

    def test_original_profile_not_mutated(self):
        profile = {"codec": "hevc_videotoolbox",
                   "encoder_args": ["-profile:v", "main"],
                   "video_filter": "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2"}
        apply_hdr_adjustments(profile, HDR10)
        assert profile["encoder_args"] == ["-profile:v", "main"]

    def test_unsupported_encoder_returns_none(self):
        profile = {"codec": "hevc_qsv", "encoder_args": [], "video_filter": "format=yuv420p"}
        assert apply_hdr_adjustments(profile, HDR10) is None
```

- [ ] **Step 2: Run, verify FAIL**
- [ ] **Step 3: Implement in `optimizer_utils.py`:**

```python
_HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}  # PQ, HLG

def is_hdr_or_10bit(info: dict) -> bool:
    pix = str(info.get("pix_fmt") or "")
    if "10" in pix or "12" in pix:
        return True
    if str(info.get("color_transfer") or "") in _HDR_TRANSFERS:
        return True
    return str(info.get("color_primaries") or "") == "bt2020"


# Per-codec 10-bit adjustments; codecs not listed cannot safely encode HDR here.
_HDR_CAPABLE = {
    "hevc_videotoolbox": {"profile": "main10", "pix_fmt": "p010le"},
    "hevc_nvenc":        {"profile": "main10", "pix_fmt": "p010le"},
    "libx265":           {"profile": "main10", "pix_fmt": "yuv420p10le"},
}

def apply_hdr_adjustments(profile: dict, info: dict) -> dict | None:
    caps = _HDR_CAPABLE.get(profile.get("codec", ""))
    if not caps:
        return None
    adj = dict(profile)
    args = list(profile.get("encoder_args", []))
    # swap "-profile:v main" -> main10 (or append if absent)
    if "-profile:v" in args:
        args[args.index("-profile:v") + 1] = caps["profile"]
    else:
        args.extend(["-profile:v", caps["profile"]])
    adj["encoder_args"] = args
    # 8-bit format in the filter chain -> 10-bit surface format
    vf = profile.get("video_filter", "")
    for fmt8 in ("yuv420p", "nv12"):
        vf = vf.replace(f"format={fmt8}", f"format={caps['pix_fmt']}")
    adj["video_filter"] = vf
    # Pass source color metadata through instead of stamping bt709
    trc = str(info.get("color_transfer") or "smpte2084")
    adj["color_args"] = [
        "-colorspace", "bt2020nc",
        "-color_primaries", "bt2020",
        "-color_trc", trc,
    ]
    return adj
```

- [ ] **Step 4: Run, verify PASS**
- [ ] **Step 5: Integrate into `video_optimizer.py`:**
  - `get_video_info`: extend `-show_entries` with `,pix_fmt,color_transfer,color_primaries` and add the three keys to the returned dict (`video_stream.get(...)`, default `''`).
  - `build_ffmpeg_command(..., color_args=None)`: replace the hardcoded `'-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709'` with `*(color_args or ['-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709'])`. Only in compress mode; in `video_mode='copy'` emit no color args at all (metadata is copied).
  - `process_file` after `get_video_info`: if `is_hdr_or_10bit(info)` and compress mode: `profile = apply_hdr_adjustments(profile, info)`; if None → print skip warning, `batch_stats['skipped'] += 1`, set `last_encode_result` reason `'HDR/10-bit source not supported by <codec> — kept original'`, return `(False, 0)`. If adjusted, print `HDR/10-bit source: main10 passthrough enabled` and thread `profile['color_args']` into every `build_ffmpeg_command` call via `run_encode_pass` (`color_args=profile.get('color_args')`).
- [ ] **Step 6: Full suite + `node`-free lint sanity** (`.venv/bin/pytest -q`)
- [ ] **Step 7: Commit** `feat(optimizer): HDR/10-bit detection with main10 passthrough or safe skip`

---

### Task 3: Two-pass loudnorm

**Files:**
- Modify: `scripts/optimizer_utils.py` (filter builder + JSON parse), `scripts/video_optimizer.py` (`measure_loudness`, `build_ffmpeg_command` audio section, `process_file` one-time measure)
- Test: `tests/test_optimizer_utils.py`

**Interfaces:**
- Produces (utils): `parse_loudnorm_json(stderr_text: str) -> dict | None`, `build_audio_filter_chain(audio_mode: str, measured: dict | None = None) -> str | None` (None for 'standard'/unknown → caller uses plain AAC args).
- Produces (video_optimizer): `measure_loudness(input_path, audio_mode) -> dict | None` (runs ffmpeg null pass).
- `build_ffmpeg_command` gains kwarg `loudnorm_measured: dict | None = None`.

- [ ] **Step 1: Failing tests:**

```python
from optimizer_utils import parse_loudnorm_json, build_audio_filter_chain

LOUDNORM_STDERR = """
[Parsed_loudnorm_3 @ 0x600002] 
{
	"input_i" : "-23.61",
	"input_tp" : "-6.53",
	"input_lra" : "5.90",
	"input_thresh" : "-33.79",
	"output_i" : "-19.02",
	"output_tp" : "-2.03",
	"output_lra" : "5.10",
	"output_thresh" : "-29.13",
	"normalization_type" : "dynamic",
	"target_offset" : "0.02"
}
"""

class TestLoudnorm:
    def test_parse_extracts_measurements(self):
        m = parse_loudnorm_json(LOUDNORM_STDERR)
        assert m["input_i"] == "-23.61"
        assert m["target_offset"] == "0.02"

    def test_parse_garbage_returns_none(self):
        assert parse_loudnorm_json("no json here") is None

    def test_dynamic_chain_without_measurement(self):
        chain = build_audio_filter_chain("moderate")
        assert "loudnorm=I=-19:TP=-1.5:LRA=11" in chain
        assert "measured_I" not in chain
        assert chain.startswith("aformat=channel_layouts=stereo")

    def test_linear_chain_with_measurement(self):
        m = parse_loudnorm_json(LOUDNORM_STDERR)
        chain = build_audio_filter_chain("enhanced", measured=m)
        assert "loudnorm=I=-16" in chain
        assert "measured_I=-23.61" in chain
        assert "measured_TP=-6.53" in chain
        assert "measured_LRA=5.90" in chain
        assert "measured_thresh=-33.79" in chain
        assert "offset=0.02" in chain
        assert "linear=true" in chain

    def test_silent_audio_falls_back_to_dynamic(self):
        m = {"input_i": "-inf", "input_tp": "-inf",
             "input_lra": "0.00", "input_thresh": "-inf", "target_offset": "0.00"}
        chain = build_audio_filter_chain("moderate", measured=m)
        assert "measured_I" not in chain

    def test_standard_mode_returns_none(self):
        assert build_audio_filter_chain("standard") is None
```

- [ ] **Step 2: Run, verify FAIL**
- [ ] **Step 3: Implement in `optimizer_utils.py`:**

```python
import re as _re

LOUDNORM_TARGETS = {"moderate": -19, "enhanced": -16}
_AUDIO_PRE_CHAIN = ("aformat=channel_layouts=stereo,highpass=f=100,"
                    "agate=threshold=-55dB:range=0.05:ratio=2")

def parse_loudnorm_json(stderr_text: str) -> dict | None:
    matches = _re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr_text, _re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None

def build_audio_filter_chain(audio_mode: str, measured: dict | None = None) -> str | None:
    target_i = LOUDNORM_TARGETS.get(audio_mode)
    if target_i is None:
        return None
    ln = f"loudnorm=I={target_i}:TP=-1.5:LRA=11"
    if measured:
        keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
        vals = {k: str(measured.get(k, "")) for k in keys}
        usable = all(vals[k] not in ("", "-inf", "inf", "nan") for k in keys)
        if usable:
            ln += (f":measured_I={vals['input_i']}:measured_TP={vals['input_tp']}"
                   f":measured_LRA={vals['input_lra']}:measured_thresh={vals['input_thresh']}"
                   f":offset={vals['target_offset']}:linear=true")
    return f"{_AUDIO_PRE_CHAIN},{ln}"
```

- [ ] **Step 4: Run, verify PASS**
- [ ] **Step 5: Integrate into `video_optimizer.py`:**
  - New `measure_loudness(input_path, audio_mode)`: builds `ffmpeg -hide_banner -nostats -i <in> -map 0:a:0 -af "<dynamic chain with :print_format=json>" -f null -`, `subprocess.run(capture_output=True, text=True, timeout=900)`, returns `parse_loudnorm_json(result.stderr)`. Any exception → None. Print `Audio Analysis: measured -23.6 LUFS → linear loudnorm` on success.
  - `build_ffmpeg_command`: replace the moderate/enhanced literal filter strings with `chain = build_audio_filter_chain(audio_mode, loudnorm_measured)`; if chain: `['-c:a','aac','-b:a','192k','-ar','48000','-af', chain]`, else the plain standard AAC args. (Keeps fallback if utils import failed: guard with `OPTIMIZER_UTILS_AVAILABLE`, else use existing literals.)
  - `process_file`: before the search (after bitrate analysis), when `video_mode=='compress' and not copy_audio and audio_mode in ('moderate','enhanced') and not is_trim`: `loudnorm_measured = measure_loudness(input_path, audio_mode)`; thread through `run_encode_pass` → `build_ffmpeg_command`. For trims keep dynamic single-pass (measurement window differs).
- [ ] **Step 6: Full suite**
- [ ] **Step 7: Commit** `feat(optimizer): two-pass linear loudnorm with per-file measurement`

---

### Task 4: Scene-aware SSIM sampling

**Files:**
- Modify: `scripts/optimizer_utils.py` (`select_top_windows`), `scripts/video_optimizer.py` (`analyze_packet_hotspots` + `process_file`/`run_encode_pass` sample points)
- Test: `tests/test_optimizer_utils.py`

**Interfaces:**
- Produces (utils): `select_top_windows(bucket_bytes: dict[int, int], duration: float, n: int = 3, window: float = 3.0, bucket_len: float = 5.0) -> list[float]` — sorted window start times; falls back to 25/50/75% when buckets empty.
- Produces (video_optimizer): `analyze_packet_hotspots(input_path: Path, bucket_len: float = 5.0) -> dict[int, int]` (bucket index → summed packet bytes via ffprobe CSV).

- [ ] **Step 1: Failing tests:**

```python
from optimizer_utils import select_top_windows

class TestSceneWindows:
    def test_picks_heaviest_bucket_per_third(self):
        # 300s video, 5s buckets: heavy spots at 10s, 150s, 250s
        buckets = {i: 100 for i in range(60)}
        buckets[2] = 9000    # 10-15s (first third)
        buckets[30] = 8000   # 150-155s (second third)
        buckets[50] = 7000   # 250-255s (last third)
        starts = select_top_windows(buckets, 300.0, n=3, window=3.0, bucket_len=5.0)
        assert starts == [10.0, 150.0, 250.0]

    def test_empty_buckets_fall_back_to_percentages(self):
        starts = select_top_windows({}, 100.0, n=3, window=3.0)
        assert starts == [25.0, 50.0, 75.0]

    def test_starts_clamped_inside_duration(self):
        buckets = {19: 9999}  # 95-100s of a 100s video
        starts = select_top_windows(buckets, 100.0, n=3, window=3.0, bucket_len=5.0)
        for s in starts:
            assert 0.0 <= s <= 100.0 - 3.0 - 0.5

    def test_returns_sorted_unique(self):
        buckets = {0: 500, 1: 400, 2: 300}
        starts = select_top_windows(buckets, 15.0, n=3, window=3.0, bucket_len=5.0)
        assert starts == sorted(starts)
        assert len(set(starts)) == len(starts)
```

- [ ] **Step 2: Run, verify FAIL**
- [ ] **Step 3: Implement in `optimizer_utils.py`:**

```python
def select_top_windows(bucket_bytes: dict[int, int], duration: float, n: int = 3,
                       window: float = 3.0, bucket_len: float = 5.0) -> list[float]:
    """Pick the highest-bitrate bucket in each of n equal regions of the video.

    High packet density = high motion/complexity = where compression artifacts
    live. Falls back to evenly spread percentages when no packet data exists.
    """
    max_start = max(0.0, duration - window - 0.5)

    def _fallback() -> list[float]:
        return [min(duration * p, max_start) for p in (0.25, 0.50, 0.75)][:n]

    if not bucket_bytes or duration <= 0:
        return _fallback()

    region_len = duration / n
    starts: list[float] = []
    for r in range(n):
        lo_t, hi_t = r * region_len, (r + 1) * region_len
        lo_b, hi_b = int(lo_t / bucket_len), max(int(lo_t / bucket_len) + 1, int(hi_t / bucket_len))
        candidates = {b: sz for b, sz in bucket_bytes.items() if lo_b <= b < hi_b}
        if not candidates:
            starts.append(min(lo_t + region_len / 2, max_start))
            continue
        best_bucket = max(candidates, key=candidates.get)
        starts.append(min(best_bucket * bucket_len, max_start))
    starts = sorted(set(max(0.0, s) for s in starts))
    while len(starts) < n:  # dedup collapsed windows -> pad with fallback points
        for p in (0.25, 0.50, 0.75):
            cand = min(duration * p, max_start)
            if cand not in starts:
                starts.append(cand)
                break
        else:
            break
    return sorted(starts)[:n]
```

- [ ] **Step 4: Run, verify PASS**
- [ ] **Step 5: Integrate into `video_optimizer.py`:**
  - New `analyze_packet_hotspots(input_path, bucket_len=5.0)`: `ffprobe -v error -select_streams v:0 -show_entries packet=pts_time,size -of csv=p=0 <in>`, run with `subprocess.Popen` streaming stdout line-by-line, accumulate `buckets[int(pts / bucket_len)] += size`, `timeout`-guard via `communicate(timeout=120)`-style try/except returning `{}` on any error.
  - `process_file`, before the search: compute once
    ```python
    dur_for_samples = trim_duration if is_trim else info['duration']
    if OPTIMIZER_UTILS_AVAILABLE and not is_trim and video_mode == 'compress':
        sample_starts = select_top_windows(analyze_packet_hotspots(input_path), dur_for_samples, 3, SAMPLE_DURATION)
    else:
        max_s = max(0.0, dur_for_samples - SAMPLE_DURATION - 0.5)
        sample_starts = [min(dur_for_samples * p, max_s) for p in (0.25, 0.50, 0.75)]
    ```
  - `run_encode_pass`: replace the inline `raw_pts`/`opt_starts` computation with `opt_starts = sample_starts` (clamped already) and keep `orig_starts = [start_offset + s for s in opt_starts]`.
- [ ] **Step 6: Full suite**
- [ ] **Step 7: Commit** `feat(optimizer): scene-aware SSIM sample selection via packet hotspots`

---

### Task 5: Decode-verify before replace

**Files:**
- Modify: `scripts/video_optimizer.py` (`verify_output_integrity`, `promote_staging`, replace all `*.rename(output_path)` promote sites)
- Test: `tests/test_optimizer_ffmpeg.py` (integration, ffmpeg-gated)

**Interfaces:**
- Produces: `verify_output_integrity(path: Path, expected_duration: float, tolerance: float = 1.5) -> tuple[bool, str]`, `promote_staging(staging: Path, output_path: Path, expected_duration: float) -> bool` (verify → rename; on failure unlink staging, print reason, return False).

- [ ] **Step 1: Failing integration tests** in `tests/test_optimizer_ffmpeg.py`:

```python
import shutil
import subprocess
import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)

@pytest.fixture(scope="module")
def tiny_clip(tmp_path_factory):
    """2s synthetic H.264 clip with audio."""
    path = tmp_path_factory.mktemp("clips") / "tiny.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         "-shortest", str(path)],
        check=True, capture_output=True,
    )
    return path

class TestVerifyIntegrity:
    def test_valid_file_passes(self, tiny_clip):
        from video_optimizer import verify_output_integrity
        ok, reason = verify_output_integrity(tiny_clip, expected_duration=2.0)
        assert ok, reason

    def test_wrong_duration_fails(self, tiny_clip):
        from video_optimizer import verify_output_integrity
        ok, reason = verify_output_integrity(tiny_clip, expected_duration=60.0)
        assert not ok
        assert "duration" in reason.lower()

    def test_truncated_file_fails(self, tiny_clip, tmp_path):
        from video_optimizer import verify_output_integrity
        broken = tmp_path / "broken.mp4"
        data = tiny_clip.read_bytes()
        broken.write_bytes(data[: len(data) // 3])
        ok, _reason = verify_output_integrity(broken, expected_duration=2.0)
        assert not ok

    def test_promote_staging_renames_on_success(self, tiny_clip, tmp_path):
        from video_optimizer import promote_staging
        staging = tmp_path / "s.mp4"
        shutil.copy(tiny_clip, staging)
        out = tmp_path / "final.mp4"
        assert promote_staging(staging, out, expected_duration=2.0) is True
        assert out.exists() and not staging.exists()

    def test_promote_staging_refuses_broken_file(self, tiny_clip, tmp_path):
        from video_optimizer import promote_staging
        staging = tmp_path / "s.mp4"
        data = tiny_clip.read_bytes()
        staging.write_bytes(data[: len(data) // 3])
        out = tmp_path / "final.mp4"
        assert promote_staging(staging, out, expected_duration=2.0) is False
        assert not out.exists() and not staging.exists()
```

- [ ] **Step 2: Run, verify FAIL** (ImportError)
- [ ] **Step 3: Implement in `video_optimizer.py`** (near `get_video_info`):

```python
def verify_output_integrity(path: Path, expected_duration: float, tolerance: float = 1.5) -> Tuple[bool, str]:
    """Cheap insurance before the atomic replace: correct duration + clean decode.

    Protects against truncated moov atoms and encoder/driver hiccups that SSIM
    sampling can miss (it only looks at 3 windows).
    """
    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
            capture_output=True, text=True, timeout=60,
        )
        out_duration = float(probe.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError) as e:
        return (False, f"ffprobe failed: {e}")
    if expected_duration > 0 and abs(out_duration - expected_duration) > tolerance:
        return (False, f"duration mismatch: {out_duration:.1f}s vs expected {expected_duration:.1f}s")
    try:
        decode = subprocess.run(
            ['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
             '-an', '-sn', '-f', 'null', '-'],
            capture_output=True, text=True, timeout=1800,
        )
    except (subprocess.SubprocessError, OSError) as e:
        return (False, f"decode check failed to run: {e}")
    if decode.returncode != 0:
        return (False, f"decode errors: {decode.stderr.strip()[:200]}")
    return (True, "ok")


def promote_staging(staging: Path, output_path: Path, expected_duration: float) -> bool:
    print(f" {Y}-> Verifying output integrity...{NC}", end='', flush=True)
    ok, reason = verify_output_integrity(staging, expected_duration)
    if not ok:
        print(f"\r\033[2K {R}-> Output failed integrity check: {reason}. Discarding.{NC}")
        try:
            if staging.exists():
                staging.unlink()
        except OSError:
            pass
        return False
    print(f"\r\033[2K {G}-> Integrity verified.{NC}")
    staging.rename(output_path)
    return True
```

- [ ] **Step 4: Run integration tests, verify PASS**
- [ ] **Step 5: Replace the 5 promote sites in `process_file`** (each currently `X.rename(output_path)`), passing `expected_duration = trim_duration if is_trim else info['duration']`:
  1. Binary-search finalize (`final_path.rename(output_path)`): `if not promote_staging(final_path, output_path, expected_dur): _cleanup_staging(); fall through to the existing "found nothing usable" failure block` (restructure: wrap success block in the promote check).
  2. Linear success (`staging.rename(output_path)`)
  3. Linear SSIM-fail rescue (`linear_best_acceptable_path.rename(...)`)
  4. Interactive keep (`staging.rename(...)`)
  5. Loop-exhausted fallback (`linear_best_acceptable_path.rename(...)`)
  On promote failure at sites 2-5: `batch_stats['failed'] += 1`, set `last_encode_result` reason `'Output failed integrity verification'`, `_cleanup_staging()`, `return (False, 0)`.
- [ ] **Step 6: Full suite**
- [ ] **Step 7: Commit** `feat(optimizer): decode-verify outputs before atomic replace`

---

### Task 6: Sample-based quality pre-search

**Files:**
- Modify: `scripts/optimizer_utils.py` (`narrow_quality_window`), `scripts/video_optimizer.py` (`extract_probe_clip`, `estimate_optimal_q`, `process_file` integration, `--no-presearch` flag)
- Test: `tests/test_optimizer_utils.py` (pure), `tests/test_optimizer_ffmpeg.py` (probe extraction integration)

**Interfaces:**
- Produces (utils): `narrow_quality_window(n_values: int, predicted_idx: int, radius: int = 1) -> tuple[int, int]` → clamped (low, high) indices for the full-encode binary search.
- Produces (video_optimizer): `extract_probe_clip(input_path: Path, sample_starts: list[float], segment_sec: float, work_dir: Path) -> Path | None` (stream-copy concat), `estimate_optimal_q(input_path, profile, quality_values, bitrate_values, sample_starts, audio_mode, copy_audio, work_dir) -> int | None`.
- Constants: `PRESEARCH_MIN_DURATION = 120.0`, `PRESEARCH_SEGMENT_SEC = 8.0`.

- [ ] **Step 1: Failing pure test:**

```python
from optimizer_utils import narrow_quality_window

class TestNarrowWindow:
    def test_center(self):
        assert narrow_quality_window(6, 3, radius=1) == (2, 4)

    def test_clamped_at_edges(self):
        assert narrow_quality_window(6, 0, radius=1) == (0, 1)
        assert narrow_quality_window(6, 5, radius=1) == (4, 5)

    def test_single_value(self):
        assert narrow_quality_window(1, 0, radius=1) == (0, 0)
```

- [ ] **Step 2: Run, verify FAIL**
- [ ] **Step 3: Implement in `optimizer_utils.py`:**

```python
def narrow_quality_window(n_values: int, predicted_idx: int, radius: int = 1) -> tuple[int, int]:
    lo = max(0, predicted_idx - radius)
    hi = min(n_values - 1, predicted_idx + radius)
    return (lo, hi)
```

- [ ] **Step 4: Run, verify PASS. Then failing integration test** (in `test_optimizer_ffmpeg.py`):

```python
@pytest.fixture(scope="module")
def long_clip(tmp_path_factory):
    """30s synthetic clip for probe extraction."""
    path = tmp_path_factory.mktemp("clips") / "long.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=30:size=320x240:rate=24",
         "-c:v", "libx264", "-preset", "ultrafast", "-g", "24", str(path)],
        check=True, capture_output=True,
    )
    return path

class TestProbeExtraction:
    def test_probe_is_short_and_valid(self, long_clip, tmp_path):
        from video_optimizer import extract_probe_clip, get_video_info
        probe = extract_probe_clip(long_clip, [2.0, 12.0, 22.0], segment_sec=4.0, work_dir=tmp_path)
        assert probe is not None and probe.exists()
        info = get_video_info(probe)
        assert 6.0 <= info["duration"] <= 18.0  # ~3x4s, keyframe-aligned slack
```

- [ ] **Step 5: Implement in `video_optimizer.py`:**

```python
PRESEARCH_MIN_DURATION = 120.0
PRESEARCH_SEGMENT_SEC = 8.0


def extract_probe_clip(input_path, sample_starts, segment_sec, work_dir):
    """Stream-copy N short segments into one probe clip (keyframe-aligned, fast)."""
    work_dir = Path(work_dir)
    segments = []
    try:
        for i, start in enumerate(sample_starts):
            seg = work_dir / f"_probe_seg{i}.mp4"
            r = subprocess.run(
                ['ffmpeg', '-y', '-ss', f'{start:.3f}', '-i', str(input_path),
                 '-t', f'{segment_sec:.3f}', '-c', 'copy', '-avoid_negative_ts', 'make_zero',
                 '-loglevel', 'error', str(seg)],
                capture_output=True, timeout=120,
            )
            if r.returncode != 0 or not seg.exists() or seg.stat().st_size == 0:
                return None
            segments.append(seg)
        concat_list = work_dir / "_probe_list.txt"
        concat_list.write_text("".join(f"file '{s.as_posix()}'\n" for s in segments))
        probe = work_dir / "_probe.mp4"
        r = subprocess.run(
            ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_list),
             '-c', 'copy', '-loglevel', 'error', str(probe)],
            capture_output=True, timeout=120,
        )
        if r.returncode != 0 or not probe.exists() or probe.stat().st_size == 0:
            return None
        return probe
    except (subprocess.SubprocessError, OSError):
        return None
    finally:
        for s in segments:
            try: s.unlink()
            except OSError: pass
        try: (work_dir / "_probe_list.txt").unlink()
        except OSError: pass


def estimate_optimal_q(input_path, profile, quality_values, bitrate_values,
                       sample_starts, audio_mode, copy_audio, work_dir):
    """Binary-search Q on a ~24s probe clip instead of the full file.

    Returns the most-compressed Q whose probe encode passes SSIM_MIN, or None
    (probe extraction failed / nothing passed) -> caller runs the normal search.
    """
    probe = extract_probe_clip(input_path, sample_starts, PRESEARCH_SEGMENT_SEC, work_dir)
    if probe is None:
        return None
    probe_info = get_video_info(probe)
    if not probe_info or probe_info['duration'] <= 0:
        try: probe.unlink()
        except OSError: pass
        return None
    probe_dur = probe_info['duration']
    max_s = max(0.0, probe_dur - SAMPLE_DURATION - 0.5)
    probe_ssim_starts = [min(probe_dur * p, max_s) for p in (0.15, 0.50, 0.85)]

    best_q = None
    low, high = 0, len(quality_values) - 1
    print(f"{Y}Pre-Search:{NC} probing Q on {probe_dur:.0f}s sample clip...")
    try:
        while low <= high:
            mid = (low + high) // 2
            q = quality_values[mid]
            out = Path(work_dir) / f"_probe_q{q}.mp4"
            cmd = build_ffmpeg_command(
                probe, out, profile, q, copy_audio=True, audio_mode=audio_mode,
                video_mode='compress',
                target_bitrate_kbps=bitrate_values[mid] if mid < len(bitrate_values) else None,
                color_args=profile.get('color_args'),
            )
            r = subprocess.run(cmd, capture_output=True, timeout=600)
            if r.returncode != 0 or not out.exists():
                return None  # encoder trouble -> let the real search handle it
            ssim = get_multi_ssim(probe, out, probe_ssim_starts, probe_ssim_starts, SAMPLE_DURATION)
            ratio = out.stat().st_size / probe.stat().st_size if probe.stat().st_size else 1.0
            print(f" {Y}   probe Q={q}: SSIM {ssim:.4f}, size ×{ratio:.2f}{NC}")
            try: out.unlink()
            except OSError: pass
            if ssim >= SSIM_MIN and ratio < 1.0:
                best_q = q          # passes -> try more compression
                low = mid + 1
            else:
                high = mid - 1      # fails -> need better quality
    except (subprocess.SubprocessError, OSError):
        return None
    finally:
        try: probe.unlink()
        except OSError: pass
        for f in Path(work_dir).glob("_probe_q*.mp4"):
            try: f.unlink()
            except OSError: pass
    return best_q
```

  Integration in `process_file` (binary-search setup, after Task 1's history seed):
  ```python
  presearch_enabled = presearch and video_mode == 'compress' and not is_trim \
      and use_binary_search and info['duration'] >= PRESEARCH_MIN_DURATION
  if presearch_enabled:
      predicted_q = estimate_optimal_q(input_path, profile, quality_values, bitrate_values,
                                       sample_starts, audio_mode, copy_audio, input_path.parent)
      if predicted_q is not None:
          idx = nearest_quality_index(quality_values, predicted_q)
          low, high = narrow_quality_window(len(quality_values), idx, radius=1)
          print(f"{BG}Pre-Search Result:{NC} Q={predicted_q} -> full search narrowed to "
                f"[{quality_values[low]}..{quality_values[high]}]")
  ```
  (`low, high` initialization moves above this block; history seed's `first_mid` is clamped into the narrowed window.) New `process_file` kwarg `presearch=True`; new CLI flag `parser.add_argument('--no-presearch', action='store_true', help='Skip the sample-clip quality pre-search')`, passed as `presearch=not args.no_presearch`.
- [ ] **Step 6: Run integration + full suite, verify PASS**
- [ ] **Step 7: Commit** `feat(optimizer): sample-clip pre-search narrows full-encode binary search`

---

### Task 7: Worker schedule window & battery awareness

**Files:**
- Modify: `scripts/optimizer_utils.py` (schedule/battery parsing), `scripts/mac_worker.py` (flags + loop gate)
- Test: `tests/test_optimizer_utils.py`

**Interfaces:**
- Produces (utils): `parse_schedule(spec: str) -> tuple[datetime.time, datetime.time] | None`, `is_within_schedule(window: tuple, now: datetime.time | None = None) -> bool` (overnight wrap-around), `battery_from_pmset(output: str) -> bool`.
- Produces (mac_worker): `is_on_battery() -> bool` (darwin: runs `pmset -g batt`; other platforms: False), `--schedule "HH:MM-HH:MM"`, `--pause-on-battery` flags.

- [ ] **Step 1: Failing tests:**

```python
from datetime import time as dtime
from optimizer_utils import parse_schedule, is_within_schedule, battery_from_pmset

class TestSchedule:
    def test_parse_valid(self):
        assert parse_schedule("01:00-08:30") == (dtime(1, 0), dtime(8, 30))

    def test_parse_invalid(self):
        assert parse_schedule("nonsense") is None
        assert parse_schedule("25:00-08:00") is None
        assert parse_schedule("") is None

    def test_within_normal_window(self):
        win = (dtime(9, 0), dtime(17, 0))
        assert is_within_schedule(win, now=dtime(12, 0)) is True
        assert is_within_schedule(win, now=dtime(8, 59)) is False
        assert is_within_schedule(win, now=dtime(17, 1)) is False

    def test_overnight_window_wraps(self):
        win = (dtime(22, 0), dtime(6, 0))
        assert is_within_schedule(win, now=dtime(23, 30)) is True
        assert is_within_schedule(win, now=dtime(3, 0)) is True
        assert is_within_schedule(win, now=dtime(12, 0)) is False

class TestBattery:
    def test_battery_power_detected(self):
        assert battery_from_pmset("Now drawing from 'Battery Power'\n -InternalBattery-0") is True

    def test_ac_power_not_battery(self):
        assert battery_from_pmset("Now drawing from 'AC Power'\n -InternalBattery-0") is False

    def test_garbage_defaults_to_false(self):
        assert battery_from_pmset("") is False
```

- [ ] **Step 2: Run, verify FAIL**
- [ ] **Step 3: Implement in `optimizer_utils.py`:**

```python
from datetime import datetime, time as dtime

def parse_schedule(spec: str) -> tuple[dtime, dtime] | None:
    try:
        start_s, end_s = spec.strip().split("-")
        sh, sm = (int(x) for x in start_s.split(":"))
        eh, em = (int(x) for x in end_s.split(":"))
        return (dtime(sh, sm), dtime(eh, em))
    except (ValueError, AttributeError):
        return None

def is_within_schedule(window: tuple[dtime, dtime], now: dtime | None = None) -> bool:
    if now is None:
        now = datetime.now().time()
    start, end = window
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end  # overnight wrap (e.g. 22:00-06:00)

def battery_from_pmset(output: str) -> bool:
    return "Battery Power" in output
```

- [ ] **Step 4: Run, verify PASS**
- [ ] **Step 5: Integrate into `mac_worker.py`:**
  - Import from `optimizer_utils` (scripts dir already on sys.path).
  - `is_on_battery()`: darwin only → `subprocess.run(['pmset','-g','batt'], capture_output=True, text=True, timeout=5)` → `battery_from_pmset(r.stdout)`; exceptions/other platforms → False.
  - Flags: `--schedule` (default None, help: `Only work within this window, e.g. "01:00-08:00" (overnight OK)`), `--pause-on-battery` (store_true).
  - In `main()` before the loop: `schedule_window = parse_schedule(args.schedule) if args.schedule else None` (invalid spec → print warning, exit 2).
  - In the `while not _shutdown` loop, before `client.poll_next_job()`:
    ```python
    if schedule_window and not is_within_schedule(schedule_window):
        print(f"{Y}⏸  Outside schedule window — sleeping...{NC}", end="\r")
        _sleep_interruptible(args.poll_interval)
        continue
    if args.pause_on_battery and is_on_battery():
        print(f"{Y}🔋 On battery power — paused...{NC}", end="\r")
        _sleep_interruptible(args.poll_interval)
        continue
    ```
    where `_sleep_interruptible(n)` is the existing 1-second-step loop extracted into a tiny helper (respects `_shutdown`).
- [ ] **Step 6: Full suite + `python3 scripts/mac_worker.py --help` smoke check**
- [ ] **Step 7: Commit** `feat(worker): schedule window and pause-on-battery for mac_worker`

---

### Task 8: Docs, changelog, end-to-end smoke

**Files:**
- Modify: `dev-docs/video-optimizer.md` (new sections), `CHANGELOG.md` (Unreleased entries), `README.md` (optimizer bullet list)

- [ ] **Step 1:** Add to `dev-docs/video-optimizer.md`: sections for Pre-Search (probe clip strategy, `--no-presearch`), History Seeding (`encode_history.jsonl` format), HDR handling table (capable codecs vs skip), Two-Pass Loudnorm, Scene-Aware Sampling, Integrity Verification, Worker Scheduling.
- [ ] **Step 2:** CHANGELOG Unreleased: one bullet per feature under `### Changed — Video Optimizer`.
- [ ] **Step 3:** End-to-end smoke: generate a ~150s synthetic clip in the scratchpad, run `.venv/bin/python3 scripts/video_optimizer.py <clip> --encoder libx265` (software encoder — deterministic, no HW dependency) and confirm: pre-search prints, history file written, integrity verification prints, output `_opt.mp4` created OR a clean documented failure path.
- [ ] **Step 4:** Full suite one final time.
- [ ] **Step 5: Commit** `docs(optimizer): document v2.5 pre-search, HDR safety, loudnorm and worker scheduling`

---

## Self-Review

- **Spec coverage:** idea 1 (sample-based search) → Task 6; idea 2 (history Q) → Task 1; idea 3 (HDR) → Task 2; idea 4 (loudnorm) → Task 3; idea 5 (decode-verify) → Task 5; idea 6 (scene-aware sampling) → Task 4; idea 7 (schedule/battery) → Task 7. ✓
- **Placeholder scan:** all steps carry concrete code/commands. ✓
- **Type consistency:** `nearest_quality_index` (Task 1) reused in Task 6; `select_top_windows`/`sample_starts` (Task 4) consumed by Task 6's `estimate_optimal_q`; `color_args` kwarg (Task 2) referenced in Task 6's probe command; `promote_staging` signature consistent. Task ordering matters: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8.
