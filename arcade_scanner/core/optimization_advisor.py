"""Optimization advisor — ranks videos by expected savings from re-encoding.

Pure logic (no ffmpeg/subprocess): unit-testable, consumed by the
/api/candidates route. Heuristic baseline from bitrate-per-resolution +
codec efficiency; overridden by real results from encode_history.jsonl
(written by videocrunch's engine) when a bucket has enough samples.
"""
from __future__ import annotations

import json
import os
import statistics
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models.video_entry import VideoEntry

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

_VIDEOCRUNCH_HISTORY = Path.home() / ".videocrunch" / "logs" / "encode_history.jsonl"
_LEGACY_HISTORY = Path.home() / ".arcade-scanner" / "logs" / "encode_history.jsonl"


def default_history_path() -> Path:
    """The primary location to report/write history against.

    videocrunch writes to ~/.videocrunch/logs. Installs that ran the optimizer
    while it still lived in this repo have real measured encodes under
    ~/.arcade-scanner/logs — those keep working until videocrunch has written
    its first record, at which point the new location takes over.

    This names a single primary path (used e.g. for display). Actual history
    *reads* go through `EncodeHistory`, which unions both locations when
    neither an explicit path nor an env override narrows it to one file —
    see its docstring for why a single "prefer one, ignore the other" choice
    would silently discard real data.
    """
    override = os.getenv("VIDEOCRUNCH_HISTORY_PATH")
    if override:  # "" is treated as unset, not as an explicit empty path
        return Path(override)
    if _VIDEOCRUNCH_HISTORY.exists():
        return _VIDEOCRUNCH_HISTORY
    if _LEGACY_HISTORY.exists():
        return _LEGACY_HISTORY
    return _VIDEOCRUNCH_HISTORY

# --- bucket helpers -------------------------------------------------------
# Deliberately duplicated from videocrunch's savings.py — that repo owns the
# encoder and needs these standalone. Cross-repo parity is pinned by the shared
# tests/fixtures/savings_parity.json (identical copy in videocrunch), which
# carries the boundary values for both helpers plus MIN_LISTED_SAVED_PCT.


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


def _is_same_codec(source_codec: str, target_codec: str) -> bool:
    """True when re-encoding `source_codec` to `target_codec` is a same-codec pass."""
    src = (source_codec or "").lower()
    return src in _TARGET_ALIASES.get(target_codec, {target_codec})


def _codec_efficiency(source_codec: str, target_codec: str) -> tuple[float, bool, bool]:
    """(bitrate multiplier source→target, is the pair actually known?, is_same_codec)."""
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
                        source_codec: str, target_codec: str) -> Optional[tuple[float, bool]]:
    """Estimated saved percentage (0-100) for re-encoding, from scalars.

    Same math as `estimate_heuristic`, but without a VideoEntry — so
    videocrunch's engine can use it as a pre-flight gate with raw
    ffprobe output. Returns (saved_pct, known_codec_pair) or None when the
    inputs are too incomplete to say anything.
    """
    if source_kbps <= 0 or height <= 0:
        return None

    eff, known, is_same_codec = _codec_efficiency(source_codec or "", target_codec)
    ref = _reference_kbps(height, target_codec, fps or 0.0)

    # Predicted output: codec factor applied to the source, but never above
    # what a clean target-codec encode needs at this resolution (`ref`).
    # For same-codec re-encoding, minimal gains from re-optimization; don't cap at ref.
    if is_same_codec:
        # Same-codec: apply efficiency without ref cap (already efficiently encoded).
        # How much is left depends on how fat the source is RELATIVE to a clean
        # encode at this resolution. A source already far below `ref` has been
        # squeezed once; a second HEVC pass gets almost nothing (measured: a
        # 683 kbps 720p HEVC file yielded 5.7%, not the flat 15% `eff` implies).
        # Scale the gain by source/ref so leanness is priced in.
        leanness = min(1.0, source_kbps / ref) if ref > 0 else 1.0
        effective_eff = 1.0 - (1.0 - eff) * leanness
        predicted_kbps = source_kbps * effective_eff
        predicted_kbps = max(predicted_kbps, source_kbps * (1 - _MAX_SAVED_PCT / 100))
    else:
        # Different-codec: cap at reference rate
        predicted_kbps = min(source_kbps * eff, max(ref, source_kbps * (1 - _MAX_SAVED_PCT / 100)))

    saved_pct = max(0.0, (1.0 - predicted_kbps / source_kbps) * 100.0)
    return min(saved_pct, _MAX_SAVED_PCT), known


def estimate_heuristic(entry: VideoEntry, target_codec: str) -> Optional[tuple[float, bool]]:
    """Estimated saved percentage (0-100) for re-encoding `entry`.

    Returns (saved_pct, known_codec_pair) or None when the entry lacks the
    metadata to say anything (no bitrate / no height from ffprobe).
    """
    return estimate_savings_pct(
        (entry.bitrate_mbps or 0.0) * 1000.0,
        entry.height or 0,
        entry.frame_rate or 0.0,
        entry.codec or "",
        target_codec,
    )


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


# --- EncodeHistory --------------------------------------------------------
# History `codec` holds encoder-profile names (hevc_nvenc, libx265, av1_nvenc…);
# match the requested target codec by substring.
_TARGET_SUBSTRINGS = {"hevc": ("hevc", "265"), "av1": ("av1",)}


class EncodeHistory:
    """mtime-cached reader over encode_history.jsonl (best-effort, never raises).

    With no explicit path, this reads the *union* of the videocrunch and
    legacy locations rather than picking one: a naive "prefer videocrunch,
    else legacy" choice would make videocrunch's very first written record
    hide every real measurement an existing install already accumulated
    under ~/.arcade-scanner/logs. Records identical across both files
    (e.g. re-exported history) are only counted once. An explicit
    VIDEOCRUNCH_HISTORY_PATH override, or a `path` passed to the
    constructor, names a single source and is honoured alone.

    Paths are re-resolved on every staleness check (not just at
    construction), so a videocrunch installation that appears after Arcade
    has started is picked up without a restart.

    Records are pre-parsed and bucketed by (resolution class, bitrate class) at
    load time, so `median_saved_pct` is a bucket lookup + substring filter over
    only the matching bucket, not a full linear scan of every record. Reload
    (triggered by an mtime check) and bucket access are both guarded by a lock
    since the instance is shared across server threads.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._explicit_path = path
        # Kept for introspection/back-compat; the effective read set for the
        # no-arg case is recomputed by `_current_paths` on every reload check.
        self.path = path if path is not None else default_history_path()
        self._mtimes: dict[Path, float] = {}
        # bucket (resolution_class, bitrate_class) -> [(lowered codec str, saved_pct), ...]
        self._index: dict[tuple[str, str], list[tuple[str, float]]] = {}
        self._lock = threading.Lock()

    def _current_paths(self) -> list[Path]:
        """Paths to read from, re-resolved fresh every call (see class docstring)."""
        if self._explicit_path is not None:
            return [self._explicit_path]
        override = os.getenv("VIDEOCRUNCH_HISTORY_PATH")
        if override:  # "" is treated as unset, not as an explicit empty path
            return [Path(override)]
        return [_VIDEOCRUNCH_HISTORY, _LEGACY_HISTORY]

    def _reload_if_stale(self) -> None:
        with self._lock:
            paths = self._current_paths()
            mtimes: dict[Path, float] = {}
            for p in paths:
                try:
                    mtimes[p] = p.stat().st_mtime
                except OSError:
                    continue
            if mtimes == self._mtimes:
                return
            index: dict[tuple[str, str], list[tuple[str, float]]] = {}
            # Maps a record's content to the path it was first seen under.
            # Two files agreeing on an identical record is treated as the same
            # entry mirrored between logs and counted once. Repeats *within*
            # one file are never deduplicated — they are independent encodes
            # that happened to land on the same measured numbers (routine with
            # coarse/rounded fields), and dropping them would silently thin
            # out real samples.
            seen: dict[str, Path] = {}
            for p in paths:
                if p not in mtimes:
                    continue
                try:
                    with open(p, encoding="utf-8") as f:
                        for line in f:
                            try:
                                rec = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if not isinstance(rec, dict) or rec.get("saved_pct") is None:
                                continue
                            dedup_key = json.dumps(rec, sort_keys=True)
                            first_seen_in = seen.setdefault(dedup_key, p)
                            if first_seen_in != p:
                                continue
                            try:
                                bucket = (resolution_class(int(rec.get("height", 0))),
                                         bitrate_class(float(rec.get("source_kbps", 0))))
                                saved_pct = float(rec["saved_pct"])
                            except (TypeError, ValueError):
                                continue
                            codec_str = str(rec.get("codec", "")).lower()
                            index.setdefault(bucket, []).append((codec_str, saved_pct))
                except OSError:
                    continue
            self._index = index
            self._mtimes = mtimes

    def median_saved_pct(self, target_codec: str, height: int, source_kbps: float,
                         min_samples: int = 3) -> Optional[tuple[float, int]]:
        """Median real saved_pct for the (target, resolution class, bitrate class) bucket."""
        self._reload_if_stale()
        substrings = _TARGET_SUBSTRINGS.get(target_codec, (target_codec,))
        bucket = (resolution_class(height), bitrate_class(source_kbps))
        with self._lock:
            entries = list(self._index.get(bucket, ()))
        samples = [saved_pct for codec_str, saved_pct in entries
                  if any(s in codec_str for s in substrings)]
        if len(samples) < min_samples:
            return None
        return (float(statistics.median(samples)), len(samples))


# --- build_candidates -------------------------------------------------------

# Also lives in videocrunch's scan.py; pinned to that copy by
# tests/fixtures/savings_parity.json ("constants").
MIN_LISTED_SAVED_PCT = 10.0


def _reason(entry: VideoEntry, saved_pct: float, source: str, samples: int,
           is_same_codec: bool, above_reference: bool) -> str:
    codec = (entry.codec or "unknown").upper()
    res = f"{entry.height}p" if (entry.height or 0) > 0 else "?"
    rate = f"{entry.bitrate_mbps:.1f} Mbit/s"
    if source == "history":
        return f"{codec}, {res}, {rate} — {samples} echte Encodes in dieser Klasse"
    if is_same_codec:
        return f"{codec}, {res}, {rate} — gleicher Codec, geringes Potenzial"
    if above_reference:
        return f"{codec}, {res}, {rate} — deutlich über Referenz"
    return f"{codec}, {res}, {rate} — Codec-Wechsel lohnt"


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
        is_same_codec = _is_same_codec(entry.codec or "", target_codec)
        # History carries no source codec, so a same-codec entry (already HEVC,
        # re-checking against HEVC) would otherwise inherit the median of
        # unrelated h264-source encodes in the same bucket. Skip the override.
        if not is_same_codec:
            hist = history.median_saved_pct(
                target_codec, entry.height or 0, (entry.bitrate_mbps or 0.0) * 1000.0)
            if hist is not None:
                saved_pct, samples = hist
                source, confidence = "history", "high"
        if saved_pct < MIN_LISTED_SAVED_PCT:
            continue
        source_kbps = (entry.bitrate_mbps or 0.0) * 1000.0
        ref_kbps = _reference_kbps(entry.height or 0, target_codec, entry.frame_rate or 0.0)
        above_reference = source_kbps > ref_kbps
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
            reason=_reason(entry, saved_pct, source, samples, is_same_codec, above_reference),
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
