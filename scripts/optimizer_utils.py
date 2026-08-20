"""optimizer_utils.py — pure helper logic for the video optimizer.

Kept free of ffmpeg/subprocess calls so it is unit-testable and importable
by video_optimizer.py, mac_worker.py and the test suite alike.
"""
from __future__ import annotations

import json
import re
import statistics
from datetime import datetime
from datetime import time as dtime
from pathlib import Path

DEFAULT_HISTORY_PATH = Path.home() / ".arcade-scanner" / "logs" / "encode_history.jsonl"


# ---------------------------------------------------------------------------
# Encode history — learn the winning starting Q from past encodes
# ---------------------------------------------------------------------------

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


def narrow_quality_window(n_values: int, predicted_idx: int, radius: int = 1) -> tuple[int, int]:
    """Clamped (low, high) index window around a pre-search prediction."""
    lo = max(0, predicted_idx - radius)
    hi = min(n_values - 1, predicted_idx + radius)
    return (lo, hi)


# ---------------------------------------------------------------------------
# Worker scheduling / battery awareness
# ---------------------------------------------------------------------------

def parse_schedule(spec: str) -> tuple[dtime, dtime] | None:
    """Parse "HH:MM-HH:MM" into a (start, end) time window. None if invalid."""
    try:
        start_s, end_s = spec.strip().split("-")
        sh, sm = (int(x) for x in start_s.split(":"))
        eh, em = (int(x) for x in end_s.split(":"))
        return (dtime(sh, sm), dtime(eh, em))
    except (ValueError, AttributeError):
        return None


def is_within_schedule(window: tuple[dtime, dtime], now: dtime | None = None) -> bool:
    """True if `now` falls inside the window; handles overnight wrap (22:00-06:00)."""
    if now is None:
        now = datetime.now().time()
    start, end = window
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def battery_from_pmset(output: str) -> bool:
    """True if macOS `pmset -g batt` output indicates battery power."""
    return "Battery Power" in output


# ---------------------------------------------------------------------------
# HDR / 10-bit safety
# ---------------------------------------------------------------------------

_HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}  # PQ (HDR10), HLG

# Per-codec 10-bit adjustments; codecs not listed cannot safely encode HDR here.
_HDR_CAPABLE = {
    "hevc_videotoolbox": {"profile": "main10", "pix_fmt": "p010le"},
    "hevc_nvenc":        {"profile": "main10", "pix_fmt": "p010le"},
    "libx265":           {"profile": "main10", "pix_fmt": "yuv420p10le"},
}


def is_hdr_or_10bit(info: dict) -> bool:
    pix = str(info.get("pix_fmt") or "")
    if "10" in pix or "12" in pix:
        return True
    if str(info.get("color_transfer") or "") in _HDR_TRANSFERS:
        return True
    return str(info.get("color_primaries") or "") == "bt2020"


def apply_hdr_adjustments(profile: dict, info: dict) -> dict | None:
    """Return a profile copy adjusted for a 10-bit/HDR source, or None if the
    encoder can't do it safely (caller should skip the file instead of
    silently mistagging BT.2020/PQ content as BT.709)."""
    caps = _HDR_CAPABLE.get(profile.get("codec", ""))
    if not caps:
        return None
    adj = dict(profile)
    args = list(profile.get("encoder_args", []))
    if "-profile:v" in args:
        args[args.index("-profile:v") + 1] = caps["profile"]
    else:
        args.extend(["-profile:v", caps["profile"]])
    adj["encoder_args"] = args
    # 8-bit surface format in the filter chain -> 10-bit
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


# ---------------------------------------------------------------------------
# Two-pass loudnorm
# ---------------------------------------------------------------------------

LOUDNORM_TARGETS = {"moderate": -19, "enhanced": -16}

# Pre-chain must be identical between measurement and encode pass so the
# loudnorm measurement reflects the gated/filtered signal it will normalize.
AUDIO_PRE_CHAIN = ("aformat=channel_layouts=stereo,highpass=f=100,"
                   "agate=threshold=-55dB:range=0.05:ratio=2")


def parse_loudnorm_json(stderr_text: str) -> dict | None:
    """Extract the loudnorm measurement JSON block from ffmpeg stderr."""
    matches = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr_text, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def build_audio_filter_chain(audio_mode: str, measured: dict | None = None) -> str | None:
    """Audio filter chain for the given mode; None = no filtering (plain AAC).

    With a valid measurement, loudnorm runs in linear (transparent) mode
    instead of the pumping-prone dynamic mode.
    """
    target_i = LOUDNORM_TARGETS.get(audio_mode)
    if target_i is None:
        return None
    ln = f"loudnorm=I={target_i}:TP=-1.5:LRA=11"
    if measured:
        keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
        vals = {k: str(measured.get(k, "")) for k in keys}
        usable = all(vals[k] not in ("", "-inf", "inf", "nan", "None") for k in keys)
        if usable:
            ln += (f":measured_I={vals['input_i']}:measured_TP={vals['input_tp']}"
                   f":measured_LRA={vals['input_lra']}:measured_thresh={vals['input_thresh']}"
                   f":offset={vals['target_offset']}:linear=true")
    return f"{AUDIO_PRE_CHAIN},{ln}"


# ---------------------------------------------------------------------------
# Scene-aware SSIM sample selection
# ---------------------------------------------------------------------------

def select_top_windows(bucket_bytes: dict[int, int], duration: float, n: int = 3,
                       window: float = 3.0, bucket_len: float = 5.0) -> list[float]:
    """Pick the highest-bitrate bucket in each of n equal regions of the video.

    High packet density = high motion/complexity = where compression artifacts
    live. Fixed 25/50/75%% points can land on static menus and overestimate
    quality. Falls back to those percentages when no packet data exists.
    Returns sorted, de-duplicated window start times clamped into the video.
    """
    max_start = max(0.0, duration - window - 0.5)

    def _fallback() -> list[float]:
        return sorted({min(duration * p, max_start) for p in (0.25, 0.50, 0.75)})[:n]

    if not bucket_bytes or duration <= 0:
        return _fallback()

    region_len = duration / n
    starts: set = set()
    for r in range(n):
        lo_t, hi_t = r * region_len, (r + 1) * region_len
        lo_b = int(lo_t / bucket_len)
        hi_b = max(lo_b + 1, int(hi_t / bucket_len))
        candidates = {b: sz for b, sz in bucket_bytes.items() if lo_b <= b < hi_b}
        if candidates:
            best_bucket = max(candidates, key=candidates.get)
            starts.add(max(0.0, min(best_bucket * bucket_len, max_start)))
        else:
            starts.add(max(0.0, min(lo_t + region_len / 2, max_start)))
    return sorted(starts)[:n]


# ---------------------------------------------------------------------------
# Rate control
# ---------------------------------------------------------------------------

# A pass may peak at this multiple of its own average target before the
# encoder is reined in. 2x leaves room for I-frames and hotspots while
# keeping the pass anywhere near the size it is aiming for.
PASS_MAXRATE_FACTOR = 2.0


def clamp_maxrate_to_pass(maxrate_kbps: float | None, bufsize_kbps: float | None,
                          target_bitrate_kbps: float | None,
                          factor: float = PASS_MAXRATE_FACTOR) -> tuple:
    """Tighten a file-wide peak cap down to what THIS pass is aiming for.

    The file-wide maxrate comes from analysing the source, so it sits far above
    the individual quality-ladder targets. Left alone, the encoder is free to
    spend several times a pass's target bitrate in busy scenes and overshoot the
    size goal — which makes the ladder rungs nearly indistinguishable.

    Returns (maxrate, bufsize); passes the originals straight through when
    there is no per-pass target to clamp against.
    """
    if not target_bitrate_kbps or target_bitrate_kbps <= 0:
        return maxrate_kbps, bufsize_kbps
    cap = target_bitrate_kbps * factor
    if maxrate_kbps and maxrate_kbps > 0:
        cap = min(maxrate_kbps, cap)
    if maxrate_kbps and cap >= maxrate_kbps:
        return maxrate_kbps, bufsize_kbps  # file-wide cap already tighter
    return cap, cap * 2.0
