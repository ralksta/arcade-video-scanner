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
