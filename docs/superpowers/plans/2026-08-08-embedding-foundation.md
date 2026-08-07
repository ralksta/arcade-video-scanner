# Embedding Foundation Implementation Plan (Similarity Part 1)

> **For agentic workers:** Executed during the 2026-08-08 night run in this worktree. Steps use checkbox (`- [ ]`) syntax as the progress ledger — tick per task, commit alongside the code.

**Goal:** GPU indexer + vector storage + pure-Python kNN + `/api/similar`, exactly as specced in `docs/superpowers/specs/2026-08-07-embedding-foundation-design.md`.

**Architecture:** Indexer (`scripts/media_indexer.py`, optional `[indexer]` deps, lazy torch imports) writes L2-normalized float32 embeddings into two new SQLite tables. The server gains zero dependencies: `core/similarity.py` decodes blobs with `struct` and answers kNN by dot product over an in-memory cache; `routes/similar.py` serves session-guarded, vault-filtered queries.

**Tech Stack:** Python stdlib + pydantic (server); torch + open_clip (indexer only, never imported by server modules); pytest (all tests run WITHOUT the ML stack).

## Global Constraints

- No new server runtime dependencies; no server module imports torch/open_clip.
- Blocking CI: `.venv/bin/pytest`, `.venv/bin/ruff check .`, `.venv/bin/mypy arcade_scanner` — green before every commit.
- Vectors: float32 blobs, L2-normalized on write → similarity = dot product.
- `model` column marks staleness: rows from a different model are re-indexed.
- Default model `ViT-B-16` (dual encoder, keeps Part 4 possible); 12 uniform frames across 5%–95% of duration; short videos: as many as extractable, min 1; images: 1 frame.
- API: `GET /api/similar?path=…&limit=12` → `{"status":"ok","results":[{"file_path","score"}]}`; no index → 200 `{"status":"not_indexed"}`; unknown/unindexed path → 404; missing path → 400; session required; vault-filtered.

---

### Task 1: `core/similarity.py` — blob codec + kNN

**Files:** Create `arcade_scanner/core/similarity.py`; Test `tests/test_similarity.py`

**Produces:** `encode_vector(values: Sequence[float]) -> bytes` (L2-normalizes), `decode_vector(blob: bytes) -> list[float]`, `dot(a: list[float], b: list[float]) -> float`, `top_k(query: list[float], candidates: Iterable[tuple[str, list[float]]], k: int, exclude: set[str]) -> list[tuple[str, float]]` (desc by score).

- [x] Tests: roundtrip codec (float32 precision ~1e-6), normalization (norm 1.0; zero vector stays zero), top_k ordering/limit/exclude.
- [x] Implement with `struct.pack(f"<{n}f", ...)`, no numpy.
- [x] pytest/ruff/mypy green; commit `feat(core): vector codec and pure-python kNN for similarity`.

### Task 2: SQLite embedding tables + store methods

**Files:** Modify `arcade_scanner/database/sqlite_store.py`; Test `tests/test_sqlite_store.py` (append)

**Produces:** tables `embedding_meta(file_path PK, model, dim, mtime, indexed_at, mean_vector BLOB)`, `frame_embeddings(file_path, frame_index, ts_sec, vector BLOB, PK(file_path, frame_index))`; methods `store_embedding(file_path, model, dim, mtime, mean_vector: bytes, frames: list[tuple[int, float, bytes]]) -> None` (one transaction, replaces old rows), `get_embedding_state() -> dict[str, tuple[float, str]]` (path → (mtime, model)), `get_mean_vectors() -> list[tuple[str, str, bytes]]` ((path, model, blob)), `delete_embedding(file_path) -> None`, `prune_embeddings(existing_paths: set[str]) -> int`.

- [ ] Tests: store/read roundtrip, replace-on-restore semantics (old frame rows gone), state map, prune removes orphans, tables exist on fresh DB.
- [ ] Implement in `_create_table` + methods next to the auto-tag/queue sections (same `_write_lock`/`_get_safe_path` conventions).
- [ ] pytest/ruff/mypy green; commit `feat(db): embedding storage tables and access methods`.

### Task 3: `/api/similar` route

**Files:** Create `arcade_scanner/server/routes/similar.py`; Modify `arcade_scanner/server/api_handler.py` (GET dispatch before `files`); Test `tests/test_routes_similar.py`

**Produces:** `handle_get(handler) -> bool`; module-level `SimilarityCache` (mean vectors decoded once, invalidated via `db.register_on_change`); response contract per Global Constraints; vault filtering via requesting user's `data.vaulted` (abspath), query file itself excluded.

- [ ] Tests (FakeHandler pattern from `tests/test_routes_queue.py`, `_get_deps` patched): session 401, missing path 400, empty index → `not_indexed`, unknown path 404, ranked results with limit, vaulted results omitted, query path excluded.
- [ ] Implement + wire dispatch (GET only).
- [ ] pytest/ruff/mypy green; commit `feat(web): /api/similar kNN endpoint over stored embeddings`.

### Task 4: `scripts/media_indexer.py`

**Files:** Create `scripts/media_indexer.py`; Test `tests/test_media_indexer.py`

**Produces:** importable WITHOUT ml deps. Pure helpers: `sample_timestamps(duration: float, count: int = 12) -> list[float]` (uniform across 5%–95%; duration ≤ 0 → `[0.0]`; short videos → fewer, min 1), `needs_index(path, mtime, model, state: dict) -> bool`. CLI: one-shot default, `--watch --interval N`, `--rebuild`, `--model` (default `ViT-B-16`); frame extraction via ffmpeg subprocess; model inference isolated in `_load_model()`/`_embed_frames()` with lazy torch/open_clip imports and clear install hint on ImportError; per-file errors logged + skipped; deleted files pruned; images single frame.

- [ ] Tests: timestamp math (12 frames, 5%–95% bounds, 1s video → 1 frame), `needs_index` (new / same mtime+model skip / changed mtime / changed model), full `index_library` pass with mocked embed function + fake store recording `store_embedding` calls (no ffmpeg: frame extraction mocked).
- [ ] Implement; verify module imports clean without torch installed.
- [ ] pytest/ruff green (scripts/ is outside the mypy target); commit `feat(indexer): standalone GPU media indexer (CLIP embeddings, incremental)`.

### Task 5: `[indexer]` extra + changelog

**Files:** Modify `pyproject.toml` (optional-dependencies group `indexer = ["torch", "open_clip_torch"]`), `CHANGELOG.md`, `ROADMAP.md`.

- [ ] Add extra; assert server test suite still passes without it installed (it is not installed in this venv — that IS the proof).
- [ ] CHANGELOG `[Unreleased]` + ROADMAP entry.
- [ ] Full pytest/ruff/mypy; commit `docs: changelog & roadmap for the embedding foundation`.

### Task 6: Push + PR

- [ ] `git push -u origin night/embedding-foundation`; PR against `dev` (title per NIGHT-LOOP2.md), body notes the pending 4090 real-run and Parts 2–4.
