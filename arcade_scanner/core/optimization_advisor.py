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


def _codec_efficiency(source_codec: str, target_codec: str) -> tuple[float, bool, bool]:
    """(bitrate multiplier source→target, is the pair actually known?, is_same_codec)."""
    src = (source_codec or "").lower()
    if src in _TARGET_ALIASES.get(target_codec, {target_codec}):
        return _SAME_CODEC_EFF, True, True
    eff = CODEC_EFFICIENCY.get((src, target_codec))
    if eff is not None:
        return eff, True, False
    return _DEFAULT_EFF, False, False


def estimate_heuristic(entry: VideoEntry, target_codec: str) -> Optional[tuple[float, bool]]:
    """Estimated saved percentage (0-100) for re-encoding `entry`.

    Returns (saved_pct, known_codec_pair) or None when the entry lacks the
    metadata to say anything (no bitrate / no height from ffprobe).
    """
    source_kbps = (entry.bitrate_mbps or 0.0) * 1000.0
    height = entry.height or 0
    if source_kbps <= 0 or height <= 0:
        return None

    eff, known, is_same_codec = _codec_efficiency(entry.codec or "", target_codec)

    ref = _REF_KBPS[resolution_class(height)]
    if target_codec == "av1":
        ref *= _AV1_REF_FACTOR
    fps = entry.frame_rate or 0.0
    if fps > 0:
        ref *= min(max(fps / 30.0, 0.5), 2.0)

    # Predicted output: codec factor applied to the source, but never above
    # what a clean target-codec encode needs at this resolution (`ref`).
    # For same-codec re-encoding, minimal gains from re-optimization; don't cap at ref.
    if is_same_codec:
        # Same-codec: apply efficiency without ref cap (already efficiently encoded)
        predicted_kbps = source_kbps * eff
        predicted_kbps = max(predicted_kbps, source_kbps * (1 - _MAX_SAVED_PCT / 100))
    else:
        # Different-codec: cap at reference rate
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


# --- EncodeHistory --------------------------------------------------------
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
