# Embedding Foundation (Similarity, Part 1 of 4) — Design

**Date:** 2026-08-07
**Status:** Approved design, pending implementation plan

## Series context

Part 1 of the similarity/semantic feature series:

1. **Embedding foundation** (this spec) — indexer, storage, `/api/similar`
2. "Similar videos" strip in cinema mode
3. Theme view (offline clustering + cluster tagging)
4. Semantic text search (needs a runtime text encoder; architecture decided then)

Each part gets its own spec → plan → implementation cycle.

## Summary

A standalone GPU indexer computes CLIP-style embeddings for every video (and
image) in the library and stores them in the main SQLite DB. The server — which
gains **no new runtime dependency** — serves k-nearest-neighbour queries over the
stored vectors via a new session-guarded endpoint. Everything runs locally
(server and indexer share one machine: 32 GB RAM, RTX 4090); privacy model
unchanged.

Decisions made during brainstorming:

- Runtime: **PyTorch + open_clip**, CUDA (CPU fallback), installed via an
  optional dependency group — never in the server's runtime deps.
- Sampling: **12 uniformly spaced frames** per video (5%–95% of duration),
  per-frame embeddings **and** the normalized mean stored.
- No pHash sequences (YAGNI): frame embeddings cover re-encode/resolution
  similarity; exact duplicates remain the duplicate detector's job.
- Trigger: **manual CLI run** (incremental), optional `--watch --interval N`.
  No server-triggered indexing in part 1.

## Architecture

Two strictly separated sides, modeled on the optimizer:

- **Indexer** — `scripts/media_indexer.py`, standalone script. Deps via
  `pip install -e ".[indexer]"` (torch, open_clip_torch). Reads the media list
  from the main DB, writes embeddings back directly (same machine, no polling
  protocol).
- **Server** — reads vectors, computes cosine similarity in pure Python
  (2K × 512-float brute force ≈ tens of ms; no NumPy). Fully functional when no
  index exists.

## Data model

Two new tables in the main SQLite DB (`sqlite_store.py` schema setup):

```sql
CREATE TABLE IF NOT EXISTS embedding_meta (
    file_path   TEXT PRIMARY KEY,
    model       TEXT NOT NULL,
    dim         INTEGER NOT NULL,
    mtime       REAL NOT NULL,
    indexed_at  TEXT NOT NULL,
    mean_vector BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS frame_embeddings (
    file_path   TEXT NOT NULL,
    frame_index INTEGER NOT NULL,
    ts_sec      REAL NOT NULL,
    vector      BLOB NOT NULL,
    PRIMARY KEY (file_path, frame_index)
);
```

- Vectors: float32 blobs (`struct`-decodable server-side), **L2-normalized on
  write**, so similarity = dot product.
- `model` is bookkeeping for staleness: rows written by a different model than
  the current run are re-indexed.
- `frame_embeddings` is written in part 1 but not yet queried (enables later
  excerpt detection).

## Indexer behaviour

- Default model: open_clip **ViT-B-16** (dual encoder — keeps part 4 possible);
  `--model` to override.
- Per video: 12 uniform timestamps across 5%–95% of duration; frames extracted
  via ffmpeg; batched GPU inference; store per-frame vectors + normalized mean.
- Images (`media_type == "image"`): indexed too, as a single "frame"; same
  tables — similarity later works for photos as well.
- Incremental: skip entries whose `embedding_meta` row matches current `mtime`
  **and** model; delete rows for files no longer in the media table.
- CLI: one-shot run (default), `--watch --interval N` loop, `--rebuild` to drop
  and re-index, optimizer-style progress output.
- Very short videos (duration < ~2 s or fewer decodable frames than requested):
  index whatever frames are extractable, minimum 1.

## API

New route file `arcade_scanner/server/routes/similar.py`, wired like existing
route modules; session required:

- `GET /api/similar?path=<file>&limit=12`
  - Response: `{"status": "ok", "results": [{"file_path": ..., "score": ...}]}`
    sorted by descending cosine similarity of mean vectors, excluding the query
    file itself.
  - Results are filtered to entries the requesting user may see (vault logic
    consistent with existing routes).
  - No index at all → HTTP 200 `{"status": "not_indexed"}`.
  - Query path unknown or not indexed → 404.
- Mean vectors are lazily loaded into an in-process cache on first request;
  invalidated via `SQLiteStore.register_on_change` and/or a cheap staleness
  check, so a fresh indexer run is picked up without server restart.

## Error handling

- Indexer: undecodable files are logged and skipped (run continues); CUDA
  unavailable → CPU fallback with a warning; DB writes per file are atomic
  (meta + frames in one transaction).
- Server: malformed/missing `path` → 400; unknown path → 404; vault-filtered
  results simply omitted.

## Testing

All CI tests must run **without** the ML stack installed:

- Unit tests: float32 blob encode/decode, normalization, pure-Python kNN with
  hand-built vectors (known ordering).
- Route tests: `/api/similar` against fixture rows in the new tables — session
  enforcement, vault filtering, `not_indexed`, 404, limit.
- Indexer logic tests with a mocked model: timestamp sampling (5–95%, short
  videos), incremental skip logic (mtime match, model mismatch), deleted-file
  cleanup.
- Schema test: new tables created on fresh and existing DBs.

## CI constraints

Blocking Ruff + mypy: all new code type-annotated and lint-clean. The `[indexer]`
optional dependency group must not leak into server runtime imports (server
modules never import torch/open_clip).
