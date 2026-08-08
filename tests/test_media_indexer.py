# tests/test_media_indexer.py
"""Indexer logic tests — mocked model + extraction, no ffmpeg, no torch."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.media_indexer import (  # noqa: E402
    index_library,
    mean_of,
    needs_index,
    sample_timestamps,
)


class TestSampling:
    def test_twelve_frames_within_span(self):
        ts = sample_timestamps(600.0)
        assert len(ts) == 12
        assert ts[0] == 600.0 * 0.05
        assert ts[-1] == 600.0 * 0.95
        assert ts == sorted(ts)

    def test_short_video_gets_fewer_frames(self):
        assert len(sample_timestamps(3.0)) == 3

    def test_one_second_video_gets_single_middle_frame(self):
        assert sample_timestamps(1.0) == [0.5]

    def test_zero_duration_single_frame_at_start(self):
        assert sample_timestamps(0.0) == [0.0]


class TestNeedsIndex:
    def test_new_file(self):
        assert needs_index("/a", 1.0, "m", {}) is True

    def test_unchanged_is_skipped(self):
        assert needs_index("/a", 1.0, "m", {"/a": (1.0, "m")}) is False

    def test_changed_mtime_reindexes(self):
        assert needs_index("/a", 2.0, "m", {"/a": (1.0, "m")}) is True

    def test_changed_model_reindexes(self):
        assert needs_index("/a", 1.0, "ViT-L-14", {"/a": (1.0, "ViT-B-16")}) is True


def test_mean_of_vectors():
    assert mean_of([[1.0, 0.0], [0.0, 1.0]]) == [0.5, 0.5]


class FakeStore:
    def __init__(self, entries, state=None):
        self._entries = entries
        self._state = state or {}
        self.stored = []
        self.pruned_with = None

    def get_all_dicts(self):
        return self._entries

    def get_embedding_state(self):
        return dict(self._state)

    def prune_embeddings(self, existing):
        self.pruned_with = set(existing)
        return 0

    def store_embedding(self, path, model, dim, mtime, mean_vector, frames):
        self.stored.append({"path": path, "model": model, "dim": dim,
                            "mtime": mtime, "frames": len(frames)})


def _entry(path="/lib/a.mp4", **kw):
    base = {"FilePath": path, "Duration_Sec": 600.0, "media_type": "video", "mtime": 100}
    base.update(kw)
    return base


def _fake_extract(path, timestamps):
    return [b"jpeg"] * len(timestamps)


def _fake_embed(frames):
    return [[1.0, 0.0] for _ in frames]


def test_index_library_indexes_new_and_skips_indexed():
    store = FakeStore(
        [_entry(), _entry("/lib/done.mp4")],
        state={"/lib/done.mp4": (100.0, "ViT-B-16")},
    )
    counters = index_library(store, "ViT-B-16", _fake_embed, extract_fn=_fake_extract)
    assert counters == {"indexed": 1, "skipped": 1, "failed": 0, "pruned": 0}
    assert store.stored[0]["path"] == "/lib/a.mp4"
    assert store.stored[0]["frames"] == 12
    assert store.stored[0]["dim"] == 2
    assert store.pruned_with == {"/lib/a.mp4", "/lib/done.mp4"}


def test_index_library_rebuild_ignores_state():
    store = FakeStore([_entry()], state={"/lib/a.mp4": (100.0, "ViT-B-16")})
    counters = index_library(store, "ViT-B-16", _fake_embed,
                             extract_fn=_fake_extract, rebuild=True)
    assert counters["indexed"] == 1


def test_index_library_image_gets_single_frame():
    store = FakeStore([_entry("/lib/pic.jpg", media_type="image", Duration_Sec=0)])
    index_library(store, "ViT-B-16", _fake_embed, extract_fn=_fake_extract)
    assert store.stored[0]["frames"] == 1


def test_index_library_failure_skips_file_and_continues():
    def broken_extract(path, timestamps):
        if "bad" in path:
            raise RuntimeError("decode error")
        return _fake_extract(path, timestamps)

    store = FakeStore([_entry("/lib/bad.mp4"), _entry("/lib/good.mp4")])
    counters = index_library(store, "ViT-B-16", _fake_embed, extract_fn=broken_extract)
    assert counters["failed"] == 1
    assert counters["indexed"] == 1
    assert [s["path"] for s in store.stored] == ["/lib/good.mp4"]


def test_module_imports_without_ml_stack():
    # This suite runs in a venv WITHOUT torch/open_clip — importing the module
    # (already done above) and its pure helpers must not require them.
    assert "torch" not in sys.modules
    assert "open_clip" not in sys.modules
