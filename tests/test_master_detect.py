"""Tests for arcade_scanner/core/master_detect.py.

The paths are invented but reproduce the patterns of real, grown libraries:
source subfolders next to edited versions, camera-generated filenames,
hand-picked names, underscores instead of spaces, concatenated terms and typos.
"""

import pytest

from arcade_scanner.core.master_detect import (
    EDIT,
    MASTER,
    UNCLEAR,
    classify,
    is_master,
    session_of,
)


# ── Raw material via the folder ─────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "shoots/2019_09 Berlin/source/source.mov",
    "shoots/2024_04 Hamburg/Source/IMG_8288.MOV",
    "shoots/2020_08 Rom/source videos/iPhone Source.MOV",
    "shoots/2021_03 Wien/originals/IMG_2058.MOV",
    "shoots/2021_03 Wien/raw/x.mov",
    "shoots/2021_03 Wien/src/x.mov",
    "shoots/2021_03 Wien/Rohmaterial/x.mov",
])
def test_master_folders(path):
    assert is_master(path), path


# ── Raw material via the keyword ────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "shoots/2022_11 Prag/source_prg_DSCF3041.MOV",
    "shoots/2026_07 Lissabon/source_file_shoot_07_26.MOV",
    "shoots/x/05_2025_Session_Source.MOV",
    "shoots/x/Fujisource .MOV",          # "source" glued to the device name
    "shoots/x/Session Nov 21_ontouched source file.MOV",   # typo
    "shoots/x/clip_unbearbeitet.mov",
])
def test_master_keywords(path):
    assert is_master(path), path


def test_concatenated_source_keyword():
    """Without a separator the word boundary fails — must still be detected."""
    verdict, reasons = classify("shoots/x/Fujisource.MOV")
    assert verdict == MASTER
    assert any("source keyword" in r for r in reasons)


# ── Raw material via the camera scheme ──────────────────────────────────────

@pytest.mark.parametrize("path,expected_label", [
    ("shoots/x/IMG_5605.mp4", "iPhone/iPad"),
    ("shoots/x/DSCF3041.MOV", "Fujifilm"),
    ("shoots/x/L1000689.MP4", "Leica"),
    ("shoots/x/GX010740.MP4", "GoPro"),
    ("shoots/x/A001_01021446_C006.MOV", "Cine-Cam"),
    ("shoots/x/MVI_1234.MOV", "Canon"),
    ("shoots/x/DJI_0042.MP4", "DJI"),
    ("shoots/x/C0012.MP4", "Sony/Cine"),
    ("shoots/x/68D18503-48DC-4F8E-87C7-29B160A318AB.MP4", "iOS export (UUID)"),
])
def test_camera_filenames(path, expected_label):
    verdict, reasons = classify(path)
    assert verdict == MASTER
    assert any(expected_label in r for r in reasons)


@pytest.mark.parametrize("path", [
    "shoots/x/iphone.MOV", "shoots/x/iphone1.MOV", "shoots/x/iphone2.MOV",
    "shoots/x/gopro.mp4", "shoots/x/leica.mov",
])
def test_device_only_names(path):
    assert is_master(path), path


# ── Edited versions ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "shoots/2025_05 Session/05_2025_Session_Final.mov",   # "_Final" — word boundary!
    "shoots/2025_04 Session/firstcut.mp4",                # concatenated
    "shoots/2025_04 Session/timelinezoomed.mov",          # concatenated
    "shoots/2024_12 Session/Sequenz 01_opt.mp4",
    "shoots/2020_08 Session/final videos/slow motion 30fps.mp4",  # folder carries it
    "shoots/2021_03 Session/hdr final/wide shot 4k60 hdr.mp4",
    "shoots/2026_04 Session/April_2026_Session_outtakes.mp4",
    "shoots/2026_06 Session/4KCut.mp4",
    "shoots/2015_05 Session/finalized videos/take2.mp4",
])
def test_edits(path):
    verdict, _ = classify(path)
    assert verdict == EDIT, path


def test_handwritten_name_defaults_to_edit():
    """No camera scheme and no source signal -> named by hand -> an export."""
    verdict, reasons = classify("shoots/2021_11 Session/Session Nov 21 Video.mov")
    assert verdict == EDIT
    assert "named by hand" in reasons[0]


# ── Precedence rules ────────────────────────────────────────────────────────

def test_filename_master_signal_beats_edit_keyword():
    """A deliberately chosen name wins: 'source_fullclip' is raw material."""
    verdict, _ = classify("shoots/2022_06 Session/source/source_fullclip_4k60.mov")
    assert verdict == MASTER


def test_folder_only_master_signal_with_edit_keyword_is_unclear():
    """Folder says source, name says fullclip — a human has to decide."""
    verdict, reasons = classify("shoots/2022_06 Session/source/fullclip_4k60.mov")
    assert verdict == UNCLEAR
    assert any("edit keyword" in r for r in reasons)


def test_camera_name_in_edit_folder_stays_master():
    """IMG_2058 stays raw material even inside a 'final' folder."""
    assert is_master("shoots/2021_03 Session/hdr final/IMG_2058.MOV")


# ── Session grouping ────────────────────────────────────────────────────────

@pytest.mark.parametrize("path,expected", [
    ("shoots/2021_03 Session/originals/IMG_2058.MOV", "shoots/2021_03 Session"),
    ("shoots/2021_03 Session/hdr final/a.mp4", "shoots/2021_03 Session"),
    ("shoots/2021_03 Session/sdr/b.mp4", "shoots/2021_03 Session"),
    ("shoots/2021_03 Session/c.mp4", "shoots/2021_03 Session"),
])
def test_session_groups_variants_together(path, expected):
    assert session_of(path) == expected


def test_session_without_year_folder_strips_master_dir():
    assert session_of("clips/misc/source/x.mov") == "clips/misc"


def test_session_of_file_at_root():
    assert session_of("x.mov") == ""


# ── Robustness ──────────────────────────────────────────────────────────────

def test_file_without_extension():
    verdict, _ = classify("shoots/x/IMG_5605")
    assert verdict == MASTER


def test_windows_separators():
    assert is_master(r"shoots\originals\IMG_2058.MOV")


def test_umlauts_and_spaces_survive():
    verdict, _ = classify("clips/Aufnahme am Boden_11-20.mp4")
    assert verdict == EDIT
