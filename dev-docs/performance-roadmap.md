# Performance Optimization Roadmap

Future optimizations for the Arcade Media Scanner, ranked by estimated impact.

## Medium Impact

### 1. Parallel Directory Walking
Currently each scan target is walked sequentially. For multiple targets on different volumes (e.g., `/Volumes/Server4TB` + `/Users/ralfo/Downloads`), walking them in parallel threads would overlap the I/O wait.

## Lower Impact

### 2. Streaming JSON Parse
Instead of `json.load()` (which reads the entire file into memory), use `ijson` for streaming parse. Only matters if the JSON file is very large (100MB+). _Less relevant now that SQLite is the primary backend._

---

## ✅ Completed (v7.0 — Feb 2026)

### SQLite Migration (was High Impact #1)
Replaced `JSONStore` (full-file JSON load/save) with `SQLiteStore`:
- Instant row-level reads/writes via `INSERT OR REPLACE`
- O(1) indexed lookups by `file_path` (primary key)
- WAL mode + `PRAGMA synchronous=NORMAL` for performance
- Auto-commits — `save()` is now a no-op
- One-time auto-migration from `video_cache.json` on first startup

### Lazy Thumbnail Generation (was High Impact #2)
Thumbnails are no longer generated during the scan pipeline:
- Scan stores only the deterministic thumb name (`thumb_{md5}.jpg`)
- `/thumbnails/` endpoint generates on first HTTP request via `create_thumbnail`
- Reverse-lookup cache maps thumb filenames → source media paths
- Result: scans complete dramatically faster (no FFmpeg calls per file)

---

## ✅ Completed (v6.9.1 — Feb 2026)

### Double DB Load (was #4)
`JSONStore.__init__` called `self.load()`, then `main.py` called `db.load()` again. Removed the redundant `load()` from `__init__`.

### Deferred `purge_broken_media()` (was #5)
Moved from the synchronous startup path into the background scan thread. Dashboard now opens instantly without waiting for thumbnail stat operations.

### Conditional JSON Indent
`save()` now skips `indent=4` for databases with 5,000+ entries, saving 200–500ms per write on large libraries.

### Single `os.stat` per File
Eliminated redundant `os.stat` calls in `ScannerManager._process_path` — now stats once at the top and reuses the result for cache validation and metadata population.

### Set-Arithmetic Orphan Pruning
Replaced `[p for p in existing_paths if p not in found_paths]` with `existing_paths - found_paths` — proper O(n) set difference.

### Correct Prefix Matching in `_should_skip_root`
Replaced `if ex in root` (substring) with `startswith(ex + os.sep)`. Fixes false positives (e.g. `/data2` matching `/data20`) and is semantically correct.
