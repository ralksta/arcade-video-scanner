# Optimizer Candidates View — Design

**Date:** 2026-08-07
**Status:** Approved design, pending implementation plan

## Summary

A dedicated "Top-Kandidaten" view ranking the library by expected optimization
savings. Scoring combines a bitrate-per-pixel heuristic with real results from
`encode_history.jsonl` (the estimate improves with every encode the user runs).
Rows can be queued for encoding directly via the existing encoding queue.

Decisions made during brainstorming:

- Estimation: **two-tier** — heuristic baseline, overridden by the median real
  `saved_pct` from encode history when a bucket has ≥ 3 samples.
- UI: **dedicated view** cloned from the duplicates-view pattern (own route,
  nav button, JS file), with direct queue integration.
- "Already optimized": new **`optimized_at` column**, written by
  `/api/mark_optimized` from now on. No backfill for old encodes (YAGNI) —
  already-HEVC/AV1 files rank low via the codec factor anyway.

Out of scope (YAGNI): probe encodes for display, `_opt.*` backfill, auto-queue
rules, image optimization.

## Scoring engine (server)

New module `arcade_scanner/core/optimization_advisor.py`. Candidate set:
`media_type == "video"`, `optimized_at IS NULL`, no active queue job
(`pending`/`downloading`/`encoding`/`uploading`).

- **Heuristic baseline**: bitrate normalized by pixel count and frame rate,
  compared against a per-resolution-class reference bitrate for "well
  compressed"; multiplied by the codec factor from the existing
  `CODEC_EFFICIENCY` table (`arcade_scanner/core/bitrate_analyzer.py:25`) —
  its first production consumer.
- **History override**: bucket = (resolution class × bitrate class), reusing
  `resolution_class` / `bitrate_class` from `scripts/optimizer_utils.py`. With
  ≥ 3 history records in the bucket, the median real `saved_pct` replaces the
  heuristic estimate. Each result is flagged `source: "heuristic" | "history"`.
- Per-file output: `estimated_saved_mb`, `estimated_saved_pct`, `confidence`,
  and a short human-readable reason (e.g. "H.264, 4K, 45 Mbit/s — far above
  reference").
- Target codec (hevc/av1) is a parameter; it selects the `CODEC_EFFICIENCY`
  column and the history filter.
- `encode_history.jsonl` (`~/.arcade-scanner/logs/`) is read lazily and cached
  with an mtime check; unparseable lines are skipped (matches the existing
  reader's leniency).

Note: `optimizer_utils.py` lives under `scripts/`; the advisor must reuse the
bucket helpers without making the server depend on `scripts/` import hacks —
either move the two small helpers into `arcade_scanner/core/` (optimizer
imports them from there) or duplicate them with a parity test. Decide in the
implementation plan; preference: move to core.

## Schema & API

- New column `optimized_at TEXT` (nullable) on the media table, added like
  previous schema extensions in `sqlite_store.py`. `/api/mark_optimized`
  (`arcade_scanner/server/routes/files.py`) sets it alongside the existing
  status reset. The optimizer already calls this endpoint on success — no
  optimizer change needed.
- New route file `arcade_scanner/server/routes/candidates.py`, session
  required:
  - `GET /api/candidates?codec=hevc&limit=100` →
    `{"summary": {"total_files": N, "total_estimated_saved_mb": M,
    "history_based": K}, "results": [...]}`
  - Sorted by absolute `estimated_saved_mb` descending (large files with
    moderate percentages beat small files with high ones).
  - Vault filtering consistent with existing routes; active-queue files
    excluded.
  - Invalid `codec` → 400.

## UI — view cloned from the duplicates pattern

Four touch points, same as `/duplicates`:

1. SPA route `/candidates` in `api_handler.py` (`spa_routes`).
2. Nav button in `arcade_scanner/templates/ui_components.py` (`nav_btn`).
3. Mode wiring in `static/workspace.js` (wsColors, render branch, URL
   read/write) + early-return in `filter_engine.js`.
4. New `static/candidates.js`, registered in
   `templates/dashboard_template.py` script list; server dispatch like
   `routes/duplicates.py`.

View layout:

- **Header**: prominent total savings ("~120 GB möglich"), target-codec toggle
  (hevc/av1), count of history-backed estimates.
- **Ranked list**: thumbnail, name, codec/resolution/bitrate, estimated
  savings (MB + %), confidence badge, reason text. Thumbnail click opens the
  cinema preview (existing pattern).
- **Actions**: per-row "In Queue" (`queueForRemoteEncode`), multi-select +
  batch queue (`queueBatchForRemoteEncode` exists in `optimizer.js`); queued
  rows disappear on refetch.

New element IDs go into `tests/test_dom_contract.py` (and `DYNAMIC_IDS` for
runtime-created ones).

## Error handling

- Missing/corrupt history file → heuristic-only, no error.
- Videos with missing bitrate/resolution (ffprobe gaps) are skipped.
- Queue-add failures surface via the existing toast/alert pattern.

## Testing

- Unit tests: score formula (codec factor, resolution/fps normalization,
  ordering), history override (fixture JSONL: ≥ 3 samples wins, < 3 falls back,
  corrupt lines skipped), candidate exclusion rules (`optimized_at`, active
  queue jobs).
- Route tests: session enforcement, vault filtering, sorting, `codec`
  validation, summary numbers.
- Migration test: `optimized_at` added on fresh and existing DBs;
  `mark_optimized` sets it.
- DOM contract tests updated.

## CI constraints

Blocking Ruff + mypy: all new code type-annotated and lint-clean. No new
runtime dependencies.
