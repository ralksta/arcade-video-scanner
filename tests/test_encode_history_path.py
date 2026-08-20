"""Arcade reads the encode history that videocrunch writes."""
import importlib
import json

import pytest


@pytest.fixture
def fresh_advisor(monkeypatch):
    def _load(**env):
        monkeypatch.delenv("VIDEOCRUNCH_HISTORY_PATH", raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        import arcade_scanner.core.optimization_advisor as adv
        importlib.reload(adv)
        return adv
    return _load


def _write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _record(saved_pct, codec="hevc_x265", height=1080, source_kbps=6000):
    return {"codec": codec, "height": height, "source_kbps": source_kbps, "saved_pct": saved_pct}


def test_env_var_wins(fresh_advisor, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    target = tmp_path / "custom.jsonl"
    target.write_text("")
    adv = fresh_advisor(VIDEOCRUNCH_HISTORY_PATH=str(target))
    assert adv.default_history_path() == target


def test_prefers_videocrunch_location_when_it_exists(fresh_advisor, tmp_path, monkeypatch):
    vc = tmp_path / ".videocrunch" / "logs" / "encode_history.jsonl"
    vc.parent.mkdir(parents=True)
    vc.write_text("")
    legacy = tmp_path / ".arcade-scanner" / "logs" / "encode_history.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()
    assert adv.default_history_path() == vc


def test_falls_back_to_the_legacy_location(fresh_advisor, tmp_path, monkeypatch):
    # The existing history holds real measured encodes; discarding them would
    # visibly degrade the candidates view on day one.
    legacy = tmp_path / ".arcade-scanner" / "logs" / "encode_history.jsonl"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()
    assert adv.default_history_path() == legacy


def test_defaults_to_videocrunch_when_neither_exists(fresh_advisor, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()
    assert adv.default_history_path() == \
        tmp_path / ".videocrunch" / "logs" / "encode_history.jsonl"


# --- EncodeHistory: union of both locations, re-resolved at call time ------

def test_encode_history_unions_both_locations_and_reresolves_at_call_time(
        fresh_advisor, tmp_path, monkeypatch):
    """The scenario the write-up's throwaway script exercised, as a real test.

    A legacy-only install already has real history. videocrunch is installed
    later and writes its first records without Arcade restarting. Both the
    already-constructed EncodeHistory instance and a freshly constructed one
    must see the union of both files afterwards, not just whichever existed
    when the object was built.
    """
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()

    legacy = tmp_path / ".arcade-scanner" / "logs" / "encode_history.jsonl"
    _write_records(legacy, [_record(10), _record(12), _record(14)])

    h1 = adv.EncodeHistory()
    assert h1.median_saved_pct("hevc", 1080, 6000) == (12.0, 3)

    # videocrunch appears later; h1 was already constructed before this write.
    vc = tmp_path / ".videocrunch" / "logs" / "encode_history.jsonl"
    _write_records(vc, [_record(50), _record(52), _record(54)])

    # combined samples: 10, 12, 14, 50, 52, 54 -> median of 6 = (14+50)/2
    result = h1.median_saved_pct("hevc", 1080, 6000)
    assert result == (32.0, 6)

    h2 = adv.EncodeHistory()
    assert h2.median_saved_pct("hevc", 1080, 6000) == (32.0, 6)


def test_encode_history_deduplicates_identical_records_across_both_files(
        fresh_advisor, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    adv = fresh_advisor()

    shared = _record(20)
    legacy = tmp_path / ".arcade-scanner" / "logs" / "encode_history.jsonl"
    vc = tmp_path / ".videocrunch" / "logs" / "encode_history.jsonl"
    _write_records(legacy, [shared, _record(22), _record(24)])
    _write_records(vc, [shared])  # identical to legacy's first record

    result = adv.EncodeHistory().median_saved_pct("hevc", 1080, 6000)
    # 3 distinct samples (20, 22, 24), not 4 -- the duplicate is not double-counted.
    assert result == (22.0, 3)


def test_env_override_reads_only_that_file_even_when_both_default_locations_exist(
        fresh_advisor, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    legacy = tmp_path / ".arcade-scanner" / "logs" / "encode_history.jsonl"
    vc = tmp_path / ".videocrunch" / "logs" / "encode_history.jsonl"
    _write_records(legacy, [_record(10), _record(12), _record(14)])
    _write_records(vc, [_record(90), _record(92), _record(94)])

    custom = tmp_path / "custom.jsonl"
    _write_records(custom, [_record(50), _record(52), _record(54)])

    adv = fresh_advisor(VIDEOCRUNCH_HISTORY_PATH=str(custom))
    result = adv.EncodeHistory().median_saved_pct("hevc", 1080, 6000)
    assert result == (52.0, 3)
