# arcade_scanner/core/criteria_eval.py
"""Server-side port of evaluateCollectionMatch (static/collections.js:515).

Operates on the API-dict video shape (SQLiteStore._row_to_api_dict). Kept
faithful to the JS original — quirks included — and pinned by the Node-vm
parity test in tests/test_criteria_parity.py. If you change matching
behaviour here, change collections.js identically or that test fails.
"""
from __future__ import annotations

import re
import time
import unicodedata
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


def _fold_search_text(value: Any) -> str:
    """Kleinschreibung + Umlaute/ß — wie foldSearchText() in search_query.js."""
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ß", "ss")


def _parse_search_query(text: Any) -> tuple[list[tuple[str, bool, bool, bool]], bool]:
    """Zerlegt den Suchtext in (Wert, ausgeschlossen, ist_pfad, ist_tag)."""
    raw = str(text or "")
    terms: list[tuple[str, bool, bool, bool]] = []
    i = 0
    n = len(raw)

    while i < n:
        while i < n and raw[i].isspace():
            i += 1
        if i >= n:
            break

        negated = False
        if raw[i] == "-":
            negated = True
            i += 1

        value_chars: list[str] = []
        if i < n and raw[i] == '"':
            i += 1
            while i < n:
                ch = raw[i]
                if ch == "\\" and i + 1 < n and raw[i + 1] in ('"', "\\"):
                    value_chars.append(raw[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                value_chars.append(ch)
                i += 1
        else:
            start = i
            while i < n and not raw[i].isspace():
                i += 1
            value_chars.append(raw[start:i])

        value = "".join(value_chars)
        if not value:
            continue

        # "#tag" — ein einzelnes "#" bleibt ein normaler Suchbegriff.
        is_tag = value.startswith("#")
        search_value = value[1:] if is_tag else value
        if is_tag and not search_value:
            is_tag = False
            search_value = value

        terms.append((
            search_value,
            negated,
            (not is_tag) and ("/" in search_value or "\\" in search_value),
            is_tag,
        ))

    return terms, len(terms) == 0


def _glob_regex(pattern: str) -> re.Pattern:
    """Pfad-Muster: `*` steht für beliebig viele Zeichen, auch für `/`."""
    parts = ['^']
    for ch in pattern:
        parts.append('.*' if ch == '*' else re.escape(ch))
    parts.append('$')
    return re.compile(''.join(parts))


def _folded_path_matches(folded_file: str, folded_prefix: str) -> bool:
    """Präfix-Vergleich auf Ordnergrenzen (wie foldedPathMatches in JS)."""
    file = folded_file.replace("\\", "/")
    prefix = folded_prefix.replace("\\", "/")
    while len(prefix) > 1 and prefix.endswith("/"):
        prefix = prefix[:-1]
    if not prefix or prefix == "/":
        return True

    start = 0
    while start <= len(file):
        idx = file.find(prefix, start)
        if idx == -1:
            return False
        before_ok = idx == 0 or file[idx - 1] == "/"
        after = idx + len(prefix)
        after_ok = after == len(file) or file[after] == "/"
        if before_ok and after_ok:
            return True
        start = idx + 1
    return False


def _search_matches(file_path: str, search: Any, tags: Optional[list] = None) -> bool:
    """Dieselbe Suchsprache wie static/search_query.js."""
    terms, no_terms = _parse_search_query(search)
    folded_path = _fold_search_text(file_path)
    folded_name = _fold_search_text(file_path.replace("\\", "/").rsplit("/", 1)[-1])
    folded_tags = {_fold_search_text(tag) for tag in (tags or [])}

    if no_terms:
        raw = str(search or "")
        if not raw:
            return True
        # Nur Leerraum/„-": alte Teilstring-Regel (siehe search_query.js).
        literal = _fold_search_text(raw)
        return literal in folded_path or literal in folded_name

    # Begriffe vorbereiten (Pfade normalisieren, Muster einmal kompilieren).
    prepared = []
    for value, negated, is_path, is_tag in terms:
        folded = _fold_search_text(value)
        glob_re = None
        if is_path:
            folded = folded.replace("\\", "/")
            if "*" in folded:
                glob_re = _glob_regex(folded)
        prepared.append((folded, negated, is_path, is_tag, glob_re))

    # Positive Pfade sind eine ODER-Gruppe: „/a /b" = unter /a oder /b.
    has_positive_path = any((not negated) and is_path for _, negated, is_path, _, _ in prepared)
    path_hit = not has_positive_path
    folded_path_norm = folded_path.replace("\\", "/")

    for folded, negated, is_path, is_tag, glob_re in prepared:
        if is_tag:
            hit = folded in folded_tags
        elif glob_re is not None:
            hit = bool(glob_re.match(folded_path_norm))
        elif is_path:
            hit = _folded_path_matches(folded_path, folded)
        else:
            hit = folded in folded_name or folded in folded_path

        if negated:
            if hit:
                return False
        elif is_path:
            if hit:
                path_hit = True
        elif not hit:
            return False
    return path_hit


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


# Die Bedingungen, die `video_matches()` tatsächlich auswertet. Alles andere
# in einem Kriterien-Objekt ist wirkungslos — ein Tippfehler im Schlüssel wird
# stillschweigend ignoriert.
_LIST_CONDITIONS = ("media_type", "format", "status", "codec", "tags",
                    "resolution", "orientation")
_RANGE_CONDITIONS = ("duration", "size")


def narrows_the_selection(criteria: Optional[dict]) -> bool:
    """Schränkt dieses Kriterium überhaupt etwas ein?

    Für Smart Collections ist „keine Angabe = alles zeigen" die richtige
    Vorgabe. Für eine **Auto-Tag-Regel** ist dieselbe Antwort gefährlich: Sie
    schreibt den Tag dann an jede Datei der Bibliothek, und weil jeder Tag nur
    einmal vergeben wird, müsste man ihn anschließend einzeln von Hand wieder
    entfernen. Bei 8788 Einträgen ist das keine Reparatur mehr.

    Erreichbar war das nicht nur über ein leeres Objekt: Ein Kriterium mit
    ausschließlich unbekannten Schlüsseln — ein Tippfehler genügt — passt
    ebenfalls auf alles, weil `video_matches()` nur nach den Schlüsseln sieht,
    die es kennt.
    """
    if not isinstance(criteria, dict):
        return False

    for section in ("include", "exclude"):
        block = criteria.get(section)
        if isinstance(block, dict) and any(block.get(k) for k in _LIST_CONDITIONS):
            return True

    for key in _RANGE_CONDITIONS:
        block = criteria.get(key)
        if isinstance(block, dict) and (block.get("min") is not None
                                        or block.get("max") is not None):
            return True

    if criteria.get("favorites") in (True, False, "true", "false"):
        return True

    date_filter = criteria.get("date")
    if date_filter and not (isinstance(date_filter, dict)
                            and date_filter.get("type") == "all"):
        return True

    if str(criteria.get("search") or "").strip():
        return True

    return False


def video_matches(video: dict, criteria: Optional[dict], now: Optional[int] = None) -> bool:
    """Return True when `video` (API-dict shape) matches `criteria`."""
    # JS: `if (!criteria) return true` — only null/undefined skip evaluation.
    if criteria is None:
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
    if search and not _search_matches(file_path, search, video_tags):
        return False

    return True
