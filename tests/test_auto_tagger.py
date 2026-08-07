# tests/test_auto_tagger.py
"""Rule engine tests — fake stores, no real DB/filesystem."""
from unittest.mock import MagicMock

from arcade_scanner.core import auto_tagger
from arcade_scanner.models.user import User, UserVideoData

NOW = 1_786_000_000


def _video(path="/lib/gopro/a.mp4", **kw) -> dict:
    base = {"FilePath": path, "Size_MB": 100.0, "Status": "OK", "codec": "h264",
            "tags": [], "hidden": False, "favorite": False, "Width": 1920,
            "Height": 1080, "Duration_Sec": 60.0, "media_type": "video",
            "imported_at": NOW - 3600, "mtime": NOW - 3600}
    base.update(kw)
    return base


def _rule(rule_id="r1", tag="gopro", enabled=True, search="gopro") -> dict:
    return {"id": rule_id, "name": tag, "tag": tag, "enabled": enabled,
            "criteria": {"search": search}}


def _user(rules, tags=None, vaulted=None) -> User:
    return User(username="alice", password_hash="x", salt="y",
                data=UserVideoData(auto_tag_rules=rules, tags=tags or {},
                                   vaulted=vaulted or []))


class FakeMediaDB:
    def __init__(self, videos):
        self._videos = videos
        self.applied: dict = {}

    def get_all_dicts(self):
        return self._videos

    def get_auto_tag_applied(self, username, rule_id):
        return set(self.applied.get((username, rule_id), set()))

    def mark_auto_tag_applied(self, username, rule_id, paths):
        self.applied.setdefault((username, rule_id), set()).update(paths)


def _user_db(user):
    db = MagicMock()
    db.get_user.return_value = user
    db.get_all_users.return_value = [user]
    return db


def test_applies_tag_and_records_bookkeeping():
    user = _user([_rule()])
    media = FakeMediaDB([_video(), _video("/lib/other/b.mp4")])
    udb = _user_db(user)

    counts = auto_tagger.run_auto_tag_rules("alice", user_db=udb, media_db=media, now=NOW)

    assert counts == {"r1": 1}
    assert user.data.tags["/lib/gopro/a.mp4"] == ["gopro"]
    assert "/lib/other/b.mp4" not in user.data.tags
    assert media.get_auto_tag_applied("alice", "r1") == {"/lib/gopro/a.mp4"}
    udb.add_user.assert_called_once_with(user)


def test_apply_once_removed_tag_not_reapplied():
    user = _user([_rule()])
    media = FakeMediaDB([_video()])
    media.mark_auto_tag_applied("alice", "r1", ["/lib/gopro/a.mp4"])  # already applied earlier

    counts = auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)

    assert counts == {"r1": 0}
    assert user.data.tags == {}  # user removed it by hand; engine must not re-add


def test_merges_into_existing_tags_without_duplicates():
    user = _user([_rule()], tags={"/lib/gopro/a.mp4": ["manual"]})
    media = FakeMediaDB([_video()])
    auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)
    assert user.data.tags["/lib/gopro/a.mp4"] == ["manual", "gopro"]


def test_disabled_rule_skipped_and_no_rules_no_write():
    user = _user([_rule(enabled=False)])
    udb = _user_db(user)
    counts = auto_tagger.run_auto_tag_rules("alice", user_db=udb, media_db=FakeMediaDB([_video()]), now=NOW)
    assert counts == {}
    udb.add_user.assert_not_called()


def test_vaulted_file_never_matches():
    user = _user([_rule()], vaulted=["/lib/gopro/a.mp4"])
    media = FakeMediaDB([_video()])
    counts = auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)
    assert counts == {"r1": 0}


def test_user_tags_feed_rule_criteria():
    rule = {"id": "r2", "name": "combo", "tag": "combo", "enabled": True,
            "criteria": {"include": {"tags": ["gopro"]}}}
    user = _user([rule], tags={"/lib/gopro/a.mp4": ["gopro"]})
    media = FakeMediaDB([_video()])  # global row has NO tags — user data must drive it
    counts = auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=media, now=NOW)
    assert counts == {"r2": 1}
    assert "combo" in user.data.tags["/lib/gopro/a.mp4"]


def test_tag_definition_created_once():
    user = _user([_rule()])
    auto_tagger.run_auto_tag_rules("alice", user_db=_user_db(user), media_db=FakeMediaDB([_video()]), now=NOW)
    defs = [t for t in user.data.available_tags if t.get("name") == "gopro"]
    assert len(defs) == 1
    assert defs[0]["color"] == auto_tagger.DEFAULT_TAG_COLOR


def test_post_scan_runner_never_raises():
    bad_user_db = MagicMock()
    bad_user_db.get_all_users.side_effect = RuntimeError("boom")
    auto_tagger.run_post_scan_auto_tagging(user_db=bad_user_db, media_db=FakeMediaDB([]))  # must not raise


def test_post_scan_runner_skips_users_without_rules():
    user = _user([])
    udb = _user_db(user)
    auto_tagger.run_post_scan_auto_tagging(user_db=udb, media_db=FakeMediaDB([_video()]))
    udb.add_user.assert_not_called()
