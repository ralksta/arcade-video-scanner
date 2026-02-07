# Performance Optimization Roadmap

Future optimizations for the Arcade Media Scanner, ranked by estimated impact.

## High Impact

### 1. Switch from JSON to SQLite
The `JSONStore` loads the entire 50K-entry JSON file into memory, parses it into Pydantic models, and serializes everything on every save. SQLite would provide:
- Instant record lookups without loading entire dataset
- Incremental writes (no full-file serialization)
- ACID guarantees for concurrent access
- Query filtering at the storage layer

### 2. Lazy Thumbnail Generation
Currently thumbnails are generated during scan for *every* file. Instead, generate on first request (when the UI actually needs to display them). Benefits:
- Faster scan completion (no FFmpeg calls for thumbnails)
- Avoids generating thumbnails for files the user may never browse
- HTTP endpoint serves a placeholder → triggers async generation → returns real thumb on next request

## Medium Impact

### 3. Parallel Directory Walking
Currently each scan target is walked sequentially. For multiple targets on different volumes (e.g., `/Volumes/Server4TB` + `/Users/ralfo/Downloads`), walking them in parallel threads would overlap the I/O wait.

### 4. Don't Double-Load the DB
`JSONStore.__init__` calls `self.load()`, and then `main.py` calls `db.load()` again. The second load is redundant on a clean startup. Fix: remove the `load()` call from `__init__` and make it explicit.

## Lower Impact

### 5. Skip `purge_broken_media()` on Cold Start
This function lists all thumbnails and stats them on every launch. Could be:
- Deferred to run after scan completes
- Only run when `--cleanup` flag is passed
- Rate-limited to run once per day

### 6. Streaming JSON Parse
Instead of `json.load()` (which reads the entire file into memory), use `ijson` for streaming parse. Only matters if the JSON file is very large (100MB+).
