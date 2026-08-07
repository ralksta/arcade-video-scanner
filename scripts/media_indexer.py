#!/usr/bin/env python3
"""media_indexer.py — standalone GPU embedding indexer (similarity part 1).

Computes CLIP-style embeddings for every video/image in the library and
stores them in the main SQLite DB (embedding_meta / frame_embeddings).
Modeled on the optimizer scripts: the server never imports this module and
never needs the ML stack — install it separately with:

    pip install -e ".[indexer]"

Usage:
    python3 scripts/media_indexer.py                 # incremental one-shot run
    python3 scripts/media_indexer.py --rebuild       # drop + reindex everything
    python3 scripts/media_indexer.py --watch --interval 3600
    python3 scripts/media_indexer.py --model ViT-B-16

torch/open_clip are imported lazily inside _load_model() so this module
stays importable (and unit-testable) without them.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arcade_scanner.core.similarity import encode_vector  # noqa: E402

DEFAULT_MODEL = "ViT-B-16"
FRAME_COUNT = 12
SPAN_START = 0.05  # sample across 5%–95% of the duration
SPAN_END = 0.95


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without ffmpeg or torch)
# ---------------------------------------------------------------------------

def sample_timestamps(duration: float, count: int = FRAME_COUNT) -> list[float]:
    """Uniform timestamps across 5%–95% of the duration.

    Short videos get fewer samples (at most one per whole second), minimum 1.
    Unknown/zero duration → single frame at 0.
    """
    if duration <= 0:
        return [0.0]
    usable = min(count, max(1, int(duration)))
    if usable == 1:
        return [duration * 0.5]
    start = duration * SPAN_START
    end = duration * SPAN_END
    step = (end - start) / (usable - 1)
    return [start + i * step for i in range(usable)]


def needs_index(path: str, mtime: float, model: str,
                state: dict[str, tuple[float, str]]) -> bool:
    """True when the file is new, changed, or was indexed with another model."""
    entry = state.get(path)
    if entry is None:
        return True
    indexed_mtime, indexed_model = entry
    return indexed_mtime != mtime or indexed_model != model


def mean_of(vectors: list[list[float]]) -> list[float]:
    dim = len(vectors[0])
    return [sum(vec[i] for vec in vectors) / len(vectors) for i in range(dim)]


# ---------------------------------------------------------------------------
# ffmpeg frame extraction
# ---------------------------------------------------------------------------

def extract_frames(path: str, timestamps: list[float]) -> list[bytes]:
    """One JPEG per timestamp via ffmpeg. Raises on total failure."""
    frames: list[bytes] = []
    for ts in timestamps:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{ts:.3f}", "-i", path,
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
            capture_output=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout:
            frames.append(result.stdout)
    if not frames:
        raise RuntimeError(f"ffmpeg could not extract any frame from {path}")
    return frames


# ---------------------------------------------------------------------------
# Model (lazy — the only place torch/open_clip are touched)
# ---------------------------------------------------------------------------

def _load_model(model_name: str):
    try:
        import open_clip
        import torch
    except ImportError as e:
        raise SystemExit(
            f"ML-Stack fehlt ({e}). Installieren mit: pip install -e \".[indexer]\""
        ) from e

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("⚠️ Keine CUDA-GPU gefunden — CPU-Fallback (deutlich langsamer).")
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained="openai" if model_name == "ViT-B-16" else None)
    model = model.to(device).eval()
    return model, preprocess, device


def make_embed_fn(model_name: str):
    """Returns embed(jpeg_frames: list[bytes]) -> list[list[float]]."""
    import io

    from PIL import Image

    model, preprocess, device = _load_model(model_name)

    def embed(jpeg_frames: list[bytes]) -> list[list[float]]:
        import torch
        images = [preprocess(Image.open(io.BytesIO(f)).convert("RGB"))
                  for f in jpeg_frames]
        batch = torch.stack(images).to(device)
        with torch.no_grad():
            features = model.encode_image(batch)
        return [row.tolist() for row in features.cpu()]

    return embed


# ---------------------------------------------------------------------------
# Orchestration (unit-tested with mocked embed/extract functions)
# ---------------------------------------------------------------------------

def index_library(media_db, model_name: str, embed_fn, extract_fn=extract_frames,
                  rebuild: bool = False) -> dict[str, int]:
    """Index all new/changed media. Returns counters for reporting."""
    entries = media_db.get_all_dicts()
    existing_paths = {str(e.get("FilePath") or "") for e in entries}
    pruned = media_db.prune_embeddings(existing_paths)

    state: dict[str, tuple[float, str]] = {} if rebuild else media_db.get_embedding_state()
    counters = {"indexed": 0, "skipped": 0, "failed": 0, "pruned": pruned}

    for entry in entries:
        path = str(entry.get("FilePath") or "")
        if not path:
            continue
        mtime = float(entry.get("mtime") or 0)
        if not needs_index(path, mtime, model_name, state):
            counters["skipped"] += 1
            continue
        try:
            if entry.get("media_type") == "image":
                timestamps = [0.0]
            else:
                timestamps = sample_timestamps(float(entry.get("Duration_Sec") or 0))
            frames = extract_fn(path, timestamps)
            vectors = embed_fn(frames)
            frame_rows = [(i, timestamps[i] if i < len(timestamps) else 0.0,
                           encode_vector(vec)) for i, vec in enumerate(vectors)]
            media_db.store_embedding(
                path, model_name, len(vectors[0]), mtime,
                encode_vector(mean_of(vectors)), frame_rows)
            counters["indexed"] += 1
            print(f"✅ [{counters['indexed']}] {Path(path).name} ({len(vectors)} frames)")
        except Exception as e:
            counters["failed"] += 1
            print(f"❌ Skipping {Path(path).name}: {e}")

    return counters


def main() -> None:
    parser = argparse.ArgumentParser(description="Arcade Scanner Embedding Indexer")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"open_clip model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--rebuild", action="store_true",
                        help="drop skip-state and reindex everything")
    parser.add_argument("--watch", action="store_true",
                        help="keep running and re-check periodically")
    parser.add_argument("--interval", type=int, default=3600,
                        help="seconds between watch runs (default: 3600)")
    args = parser.parse_args()

    from arcade_scanner.database import db as media_db

    embed_fn = make_embed_fn(args.model)
    while True:
        started = time.time()
        counters = index_library(media_db, args.model, embed_fn, rebuild=args.rebuild)
        args.rebuild = False  # only the first watch pass rebuilds
        print(f"🏁 Indexed {counters['indexed']}, skipped {counters['skipped']}, "
              f"failed {counters['failed']}, pruned {counters['pruned']} "
              f"in {time.time() - started:.1f}s")
        if not args.watch:
            break
        time.sleep(max(60, args.interval))


if __name__ == "__main__":
    main()
