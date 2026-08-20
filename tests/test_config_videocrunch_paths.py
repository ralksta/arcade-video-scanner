"""The encoder lives in a separate repo now; Arcade finds it by path."""
import importlib

import pytest


@pytest.fixture
def fresh_config(monkeypatch):
    def _load(**env):
        for key in ("VIDEOCRUNCH_PATH", "VIDEOCRUNCH_BATCH_PATH", "ARCADE_OPTIMIZER_PATH"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        import arcade_scanner.config as cfg
        importlib.reload(cfg)
        return cfg.config
    return _load


def test_defaults_to_a_sibling_checkout(fresh_config):
    c = fresh_config()
    assert c.optimizer_path.endswith("videocrunch/videocrunch.py")
    assert c.batch_path.endswith("videocrunch/batch.py")


def test_env_overrides_both_paths(fresh_config):
    c = fresh_config(VIDEOCRUNCH_PATH="/opt/vc/videocrunch.py",
                     VIDEOCRUNCH_BATCH_PATH="/opt/vc/batch.py")
    assert c.optimizer_path == "/opt/vc/videocrunch.py"
    assert c.batch_path == "/opt/vc/batch.py"


def test_legacy_env_var_wins_over_the_new_one(fresh_config):
    # ARCADE_OPTIMIZER_PATH is a binding constraint: existing installs depend on
    # it continuing to work even after VIDEOCRUNCH_PATH is also set.
    c = fresh_config(ARCADE_OPTIMIZER_PATH="/legacy/video_optimizer.py",
                     VIDEOCRUNCH_PATH="/opt/vc/videocrunch.py")
    assert c.optimizer_path == "/legacy/video_optimizer.py"
    # batch_path has no legacy env var of its own, so it follows optimizer_path's
    # (legacy) directory rather than the new VIDEOCRUNCH_PATH.
    assert c.batch_path == "/legacy/batch.py"


def test_batch_path_follows_the_engine_directory_by_default(fresh_config, tmp_path):
    # Setting only the engine path must not leave batch.py pointing elsewhere.
    engine = tmp_path / "somewhere" / "videocrunch.py"
    engine.parent.mkdir(parents=True)
    engine.touch()
    c = fresh_config(VIDEOCRUNCH_PATH=str(engine))
    assert c.batch_path == str(engine.parent / "batch.py")


def test_availability_reflects_the_filesystem(fresh_config, tmp_path):
    missing = tmp_path / "nope" / "videocrunch.py"
    c = fresh_config(VIDEOCRUNCH_PATH=str(missing))
    assert c.optimizer_available is False

    present = tmp_path / "videocrunch.py"
    present.touch()
    c = fresh_config(VIDEOCRUNCH_PATH=str(present))
    assert c.optimizer_available is True
