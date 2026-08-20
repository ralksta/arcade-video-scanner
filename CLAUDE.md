# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Arcade Media Scanner — a self-hosted, privacy-first media inventory tool. It scans local video/image libraries with ffprobe, stores metadata in SQLite, and serves a web dashboard for filtering, tagging, duplicate detection, and GPU-accelerated video optimization (HEVC/AV1).

## Commands

```bash
# Run the app (creates/uses .venv, starts server on port 8000)
./run.sh
# or directly:
.venv/bin/python3 -m arcade_scanner.main [--skip-setup] [--ssl] [--rebuild] [--rebuild-thumbs] [--cleanup]

# Setup
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# For dev tools (pytest, ruff, mypy):
.venv/bin/pip install -e ".[dev]"

# Tests (pytest is configured in pyproject.toml; testpaths = tests/)
.venv/bin/pytest
.venv/bin/pytest tests/test_sqlite_store.py                 # one file
.venv/bin/pytest tests/test_sqlite_store.py::test_name      # one test

# Lint (line-length 100, E501 ignored)
.venv/bin/ruff check .

# Video optimizer: lives in the videocrunch repo, cloned as a sibling checkout
# (../videocrunch by default; override with VIDEOCRUNCH_PATH). Not in this repo.

# User management
.venv/bin/python3 scripts/manage_users.py list|add <name> [--admin]|passwd <name>

# webOS TV client (in tv_client/; Enact/React)
npm run serve   # dev server
npm run pack    # production build
npm run lint
npm run test
```

Some tests require `node` on PATH (JS syntax/contract tests shell out to `node --check`). FFmpeg/FFprobe 8.1+ must be installed for scanner and optimizer work.

## Architecture

**No web framework.** The server is Python stdlib only: `socketserver.ThreadingTCPServer` + a custom `http.server` handler (`FinderHandler` in `arcade_scanner/server/api_handler.py`). Route handlers live in `arcade_scanner/server/routes/` (files, queue, tags, settings, duplicates). Runtime dependencies are just pydantic, Pillow, imagehash — keep it that way.

**Server-generated frontend.** The dashboard HTML is built from Python string templates: `arcade_scanner/templates/dashboard_template.py` assembles component constants from `templates/components.py` / `ui_components.py` / `theme.py`. The client-side logic is vanilla JS modules in `arcade_scanner/server/static/` (engine.js, filter_engine.js, cinema.js, store.js, etc.) — no bundler, no build step for the web client.

**JS/HTML contract tests.** Because there is no browser build step, `tests/` contains static contract tests that catch frontend breakage:
- `test_js_syntax.py` — every static JS file must pass `node --check`
- `test_dom_contract.py` — every `getElementById` in JS must have a matching ID in the Python templates (and onclick handlers must be `window.*`); IDs created dynamically at runtime must be added to its `DYNAMIC_IDS` allowlist
- `test_js_completeness.py`, `test_js_runtime_patterns.py`, `test_route_interface.py`

When you add/rename an element ID or a JS global, update both sides or these tests fail.

**Data layer.** `arcade_scanner/database/`: `sqlite_store.py` is the main store (`db`), `user_store.py` holds accounts/sessions (PBKDF2). A legacy `video_cache.json` is imported once at startup by `SQLiteStore._migrate_from_json` if present. All data lives in `arcade_data/` (settings.json, SQLite DB, thumbnails). Multi-user isolation: the static HTML dump is stripped of per-user fields (favorite, hidden/vaulted, tags); the frontend hydrates them via `/api/user/data`.

**Scanner pipeline.** `arcade_scanner/scanner/` — `manager.py` orchestrates, `file_system.py` walks directories with exclusions, `media_probe.py` shells out to ffprobe, `video_inspector.py`/`image_inspector.py` build entries. Startup order in `main.py` matters: cached DB loads and the server starts *first* so the dashboard is usable immediately; scanning runs after.

**Optimizer.** Encoding happens in videocrunch, a separate repo (not yet published; cloned as a sibling checkout, `../videocrunch`). Arcade invokes it as a subprocess (`config.optimizer_path`/`config.batch_path`, resolved via `VIDEOCRUNCH_PATH`) and reads its `encode_history.jsonl` to sharpen its own savings estimates; `arcade_scanner/core/optimization_advisor.py` still does candidate ranking here. `scripts/mac_worker.py` stayed in Arcade — it polls this repo's encoding queue over HTTP and loads the videocrunch engine via the same path resolution. See `dev-docs/video-optimizer.md` and `dev-docs/mac-worker.md`.

**Clients.** Three native clients talk to the same HTTP API: `ios_client/` (SwiftUI), `tv_client/` (webOS, Enact/Limestone + React — `prebuild.js` generates a dummy `src/views/credentials.json` before builds), `webos_client/` (thin packaged web app). When changing API responses or filter semantics, check whether the TV/iOS clients need the same change (see recent commits aligning TV client filtering with the browser client).

## Conventions

- Commit style: conventional commits with scope, e.g. `fix(web): ...`, `feat(tv): ...`. Work happens on `dev`; `main` is for PRs.
- Comments in the codebase are mixed German/English; either is fine.
- Update `CHANGELOG.md` for user-facing changes; `ROADMAP.md` tracks planned features.
- Version numbers drift across files (pyproject.toml, README, banner strings in main.py) — don't trust any single one as authoritative.
- Encoder work happens in `../videocrunch`, not here — this repo no longer contains the encoding engine, hardware-encoder detection, bitrate analysis, or the batch/folder-scan CLI tools.
