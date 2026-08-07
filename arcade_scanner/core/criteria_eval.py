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
