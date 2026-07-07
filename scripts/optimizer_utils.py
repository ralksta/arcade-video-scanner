"""optimizer_utils.py — pure helper logic for the video optimizer.

Kept free of ffmpeg/subprocess calls so it is unit-testable and importable
by video_optimizer.py, mac_worker.py and the test suite alike.
"""
from __future__ import annotations

import json
import statistics
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
