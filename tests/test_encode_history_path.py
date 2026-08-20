"""Arcade reads the encode history that videocrunch writes."""
import importlib

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


def test_env_var_wins(fresh_advisor, tmp_path):
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
