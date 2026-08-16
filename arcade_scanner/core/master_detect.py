"""Detects raw material (masters) and tells it apart from edited versions.

Why: proxy files are generated for streaming from outside the LAN. Camera source
files should be skipped there — they are never watched on the road, but they are
by far the largest material.

A single naming convention cannot be relied upon. Grown libraries contain
"source_muc_DSCF3041.MOV" next to "IMG_2058.MOV" next to "iphone2.MOV". Hence
several signals, and raw material is detected POSITIVELY:

    folder        source/, originals/, raw/, src/, master/, source videos/
    keyword       source, master, untouched (including the typo "ontouched")
    camera scheme IMG_1234, DSCF0480, L1000689, GX010740, A001_..._C006, UUIDs
    device name   iphone.MOV, iphone2.MOV, gopro.mp4

Everything else counts as an edit. The reasoning: cameras assign schematic names.
A descriptive name was typed by a human — and humans name what they exported, not
what fell out of the camera.
"""

from __future__ import annotations

import re
from typing import List, Tuple

MASTER = "master"
EDIT = "edit"
UNCLEAR = "unclear"

MASTER_DIRS = re.compile(
    r"^(sources?|originals?|src|raw|master|source videos?|rohmaterial)$", re.I
)

MASTER_WORDS = re.compile(
    r"\b(source|src|master|untouched|ontouched|unbearbeitet|unedited|original)\b",
    re.I,
)

# Source terms glued to a device name without a separator: "Fujisource.MOV".
# Deliberately a substring match — a media library contains no "resource" or
# "outsource", and the error cost is small either way: at worst a proxy is not
# created, which can be added later at any time.
CONCAT_MASTER = re.compile(r"(source|master|untouched|unbearbeitet|rohmaterial)", re.I)

# Camera-generated filenames — the strongest signal, because it works without
# any naming discipline on the user's part.
CAMERA_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^IMG_\d{3,5}$", re.I), "iPhone/iPad"),
    (re.compile(r"^DSCF\d{3,5}$", re.I), "Fujifilm"),
    (re.compile(r"^L\d{6,8}$", re.I), "Leica"),
    (re.compile(r"^GX\d{6}$", re.I), "GoPro"),
    (re.compile(r"^A\d{3}_\d{6,10}_C\d{3}$", re.I), "Cine-Cam"),
    (re.compile(r"^MVI_\d{3,5}$", re.I), "Canon"),
    (re.compile(r"^DJI_\d{3,5}$", re.I), "DJI"),
    (re.compile(r"^C\d{4}$", re.I), "Sony/Cine"),
    (re.compile(
        r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$", re.I
    ), "iOS export (UUID)"),
]

# Manually renamed raw material: the name is just the recording device.
DEVICE_ONLY = re.compile(
    r"^(iphone|ipad|gopro|fuji|fujifilm|leica|sony|canon|dji|cam|kamera|camera|a7|gh5)"
    r"[ _-]?\d*$",
    re.I,
)

EDIT_WORDS = re.compile(
    r"\b(final|finalized|cut|graded|grading|timeline|projekt|project|sequenz|sequence|"
    r"outtakes?|trailer|resized|cropped|export|edit|opt|full ?video|clip)\b",
    re.I,
)

# Edit terms without a word boundary, because they are written as one word.
CONCAT_EDIT = re.compile(
    r"(firstcut|finalcut|roughcut|precut|4kcut|timeline|fullclip)", re.I
)

YEAR_FOLDER = re.compile(r"(19|20)\d{2}")


def _normalize(text: str) -> str:
    r"""Turn separators into spaces.

    Necessary because ``\b`` does NOT match between "_" and a letter — "_" counts
    as a word character. Without this, "05_2025_Session_Final" would score no hit.
    """
    return re.sub(r"[_\-.]+", " ", text)


def session_of(rel_path: str) -> str:
    """The dated project folder a file belongs to.

    Everything below it (originals/, hdr final/, sdr/, video/) are variants of the
    SAME session. Without this grouping a pure originals/ folder would look like a
    session with no edited version at all.
    """
    dirs = rel_path.replace("\\", "/").split("/")[:-1]
    for i in range(len(dirs) - 1, -1, -1):
        if YEAR_FOLDER.search(dirs[i]):
            return "/".join(dirs[: i + 1])
    while dirs and MASTER_DIRS.match(dirs[-1].strip()):
        dirs = dirs[:-1]
    return "/".join(dirs)


def classify(rel_path: str) -> Tuple[str, List[str]]:
    """(verdict, reasons) for a path. Verdict: master | edit | unclear."""
    parts = rel_path.replace("\\", "/").split("/")
    dirs, filename = parts[:-1], parts[-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename

    reasons: List[str] = []
    # Signals on the FILENAME beat an edit keyword: someone who deliberately
    # names a file "source_fullclip_4k60.mov" has made a decision.
    strong = False

    for d in dirs:
        if MASTER_DIRS.match(d.strip()):
            reasons.append(f'folder "{d}"')

    if MASTER_WORDS.search(_normalize(stem)) or CONCAT_MASTER.search(stem):
        reasons.append("source keyword in the name")
        strong = True

    for pattern, label in CAMERA_PATTERNS:
        if pattern.match(stem.strip()):
            reasons.append(f"camera filename ({label})")
            strong = True
            break

    if DEVICE_ONLY.match(stem.strip()):
        reasons.append("name is just the recording device")
        strong = True

    edited = (
        bool(EDIT_WORDS.search(_normalize(stem)))
        or bool(CONCAT_EDIT.search(stem))
        or any(EDIT_WORDS.search(_normalize(d)) for d in dirs)
    )

    if reasons and edited and not strong:
        # Only the folder says "source" while the name says "final" — genuinely
        # ambiguous, a human has to decide.
        return UNCLEAR, reasons + ["also carries an edit keyword"]
    if reasons:
        return MASTER, reasons
    if edited:
        return EDIT, ["edit keyword"]
    return EDIT, ["named by hand (no camera scheme)"]


def is_master(rel_path: str) -> bool:
    return classify(rel_path)[0] == MASTER
