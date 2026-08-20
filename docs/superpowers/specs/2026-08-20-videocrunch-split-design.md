# videocrunch — Splitting the Encoder out of Arcade

**Date:** 2026-08-20
**Status:** Approved design, pending implementation plan

## Summary

Extract the video optimization toolchain from `arcade-video-scanner` into a
standalone, publishable project — `videocrunch` — modelled on the existing
sibling project [imgcrunch](https://github.com/ralksta/imgcrunch): a fast
parallel CLI plus a macOS Finder Quick Action, usable without ever having heard
of Arcade. Arcade becomes one consumer among several.

Decisions made during brainstorming:

- Goal: **publish it**, like imgcrunch. Not merely an internal cleanup. That
  makes "no `arcade_scanner` imports, no `~/.arcade-scanner` paths" a hard
  requirement rather than a nicety.
- Scope: **encoder core plus the folder ranking**. The ability to answer "which
  12 of these 150 files are worth encoding" is what separates videocrunch from a
  plain ffmpeg wrapper, and it is the counterpart to imgcrunch's wizard.
- Coupling: **own copy of the savings heuristic on each side**, pinned by a
  shared fixture (see "The seam"). Not a pip/submodule dependency — imgcrunch is
  clone+venv, not a package, and forcing videocrunch into package shape to serve
  one caller would be tail-wagging-dog.
- `mac_worker.py` **stays in Arcade**: it speaks the Arcade server's HTTP queue
  API and would be a foreign body in a published tool.

Out of scope (YAGNI): splitting the 2249-line engine file, a videocrunch GUI,
Linux/Windows Quick-Action equivalents, publishing to PyPI, back-porting the
old `~/.arcade-scanner` history into the new location (it is read, not moved).

## Findings that shaped the design

Three facts about the current coupling, verified before designing:

- **The server never imports the optimizer.** It spawns it as a subprocess by
  path, and that path is already env-configurable
  (`ARCADE_OPTIMIZER_PATH`, `arcade_scanner/config.py:325`;
  `arcade_scanner/server/routes/files.py:632` builds the `batch_controller.py`
  path the same way).
- **The server never parses optimizer stdout.** `routes/queue.py` and
  `routes/files.py` contain no stdout parsing; results come back via the HTTP
  callback (`notify_server`) and the encode log. The console output format
  therefore does *not* become a cross-repo interface — `batch_controller.py`,
  its only parser, moves along with the engine.
- **`core/hw_encode_detect.py` is dead weight in Arcade.** No `arcade_scanner`
  module imports it; only the optimizer scripts and `tests/test_video_processor.py`
  do. (The last consumer was a re-export line removed as an "unused import" in
  `cf62272`.) It moves wholesale, leaving no stub behind.

The only genuine two-way dependency is the savings heuristic, needed by
videocrunch's pre-flight gate and by Arcade's candidates view
(`arcade_scanner/server/routes/candidates.py`).

## What videocrunch becomes

Flat layout mirroring imgcrunch — one engine, one dependency-free calculation
module, shell entry point, installer, tests:

```
videocrunch/
  videocrunch.py     <- scripts/video_optimizer.py        (engine, 2249 lines)
  crunch_utils.py    <- scripts/optimizer_utils.py        (ffmpeg-free pure logic;
                                                           imgcrunch's sizing.py analogue)
  scan.py            <- scripts/scan_folder.py            (folder ranking)
  batch.py           <- scripts/batch_controller.py       (parallel encodes)
  encoders.py        <- arcade_scanner/core/hw_encode_detect.py
  bitrate.py         <- arcade_scanner/core/bitrate_analyzer.py
  savings.py         <- savings math from core/optimization_advisor.py
  crunch.sh                       interactive wizard + CLI entry (cf. resize.sh)
  install_macos_quick_action.sh   Finder integration
  tests/
  requirements.txt
  README.md
```

**Runtime dependencies: none.** Python stdlib plus ffmpeg/ffprobe on PATH —
leaner than imgcrunch, which needs Pillow. This must stay true: it is the
project's main selling point next to speed.

`savings.py` is the piece that needs surgery. Today's heuristic hangs off
`VideoEntry` (pydantic); `estimate_savings_pct()` — the scalar entry point added
for the pre-flight gate — is already the seam and is pydantic-free. It carries
along the `CODEC_EFFICIENCY` table, the only thing the advisor imports from
`bitrate_analyzer` (`optimization_advisor.py:18`).

Entry points a published user sees:

- `bash crunch.sh /path/to/folder` — wizard: scan, ranked list, mark files, encode
- `python3 videocrunch.py FILE [--codec av1] [--scale-height 1080] …` — single file
- `python3 scan.py FOLDER [--no-encode] [--json]` — ranking only
- Finder → right-click → Quick Action, installed by the shell script

## What stays in Arcade

Deleted: `scripts/video_optimizer.py`, `scripts/optimizer_utils.py`,
`scripts/batch_controller.py`, `scripts/scan_folder.py`,
`arcade_scanner/core/hw_encode_detect.py`,
`arcade_scanner/core/bitrate_analyzer.py`, and the tests belonging to them
(`test_optimizer_utils.py`, `test_optimizer_ffmpeg.py`, `test_scan_folder.py`,
`test_batch_controller.py`, `test_bitrate_analyzer.py`, and the
`hw_encode_detect` half of `test_video_processor.py`).

Kept: server, database, dashboard, `models/VideoEntry`, `scripts/mac_worker.py`.

`arcade_scanner/core/optimization_advisor.py` shrinks to what is genuinely
Arcade's: `build_candidates()`, `EncodeHistory`, `_reason()`, the
`VideoEntry` adapter — plus a local copy of the savings math and the
`CODEC_EFFICIENCY` table it needs.

Invocation stays as it is: subprocess by path, configured by two environment
variables with sensible defaults:

- `VIDEOCRUNCH_PATH` — path to `videocrunch.py`, replacing today's
  `ARCADE_OPTIMIZER_PATH` (`config.py:325`), which defaults to a path inside the
  Arcade repo that will no longer exist.
- `VIDEOCRUNCH_BATCH_PATH` — path to `batch.py`. Today `routes/files.py:632`
  assembles the `batch_controller.py` path inline with no override at all; after
  the split that hard-coded assumption has to go.

Both default to a sibling checkout (`../videocrunch/`), which is the layout a
user cloning both repos ends up with anyway.

Added is a readable failure when videocrunch is not installed — today a missing
script surfaces as a subprocess crash. The queue route reports "videocrunch not
found at <path>" and the encoding features degrade visibly instead of
silently.

## The seam

Two things cross the boundary after the split.

### Savings heuristic — parity by fixture

Both repos implement the same math. Instead of a cross-repo import or a parity
test that can only run where both projects happen to be checked out, a
**fixture file** is committed to both:

```
savings_parity.json    # [{source_kbps, height, fps, source_codec,
                       #   target_codec, expected_saved_pct}, …]
```

Each repo has a test asserting its implementation reproduces the fixture. Drift
then fails the build **on both sides**, and neither project needs to know the
other exists. The fixture must cover the cases that have already bitten:
same-codec lean sources (the 683 kbps 720p HEVC case), same-codec fat sources,
cross-codec below and above the resolution reference, and the metadata-missing
`None` returns.

This mirrors existing practice: `bitrate_class`/`resolution_class` are already
deliberately duplicated between `optimization_advisor.py` and
`optimizer_utils.py`, pinned by
`test_optimization_advisor.py::test_bucket_helpers_parity_with_optimizer_utils`.
The fixture is the cross-repo version of that arrangement.

### Encode history

`encode_history.jsonl` is written by the optimizer and read by Arcade's
candidates view to override heuristic estimates with real measured results.

- videocrunch writes to `~/.videocrunch/logs/encode_history.jsonl`
- Arcade's `EncodeHistory` reads `VIDEOCRUNCH_HISTORY_PATH` (env var, matching
  the other two), defaulting to the videocrunch location and **falling back to
  `~/.arcade-scanner/logs/encode_history.jsonl`** when the new file is absent.
  An env var rather than a Settings-UI field: this points at another tool's data
  directory, which is a deployment detail, not a user preference.

The fallback is not decoration: the existing history already carries real
encodes (47 of the estimates in a current 1649-file scan come from it), and
discarding them would visibly degrade the candidates view on day one.

## Migration order

1. Create the videocrunch repo; copy files, rename, sever `arcade_scanner`
   imports, port the tests that come along.
2. README, `crunch.sh` wizard, `install_macos_quick_action.sh` — the work that
   turns a script collection into a publishable tool.
3. Generate `savings_parity.json` from the current implementation; commit to
   both repos with a test on each side.
4. Strip Arcade: delete the moved modules, reduce `optimization_advisor.py` to
   the Arcade-owned part plus the local savings copy, add path configuration and
   the missing-videocrunch error path.
5. Both suites green. The current 921 tests split across the two repos; neither
   number should drop through deletion alone.

Steps 1–3 leave Arcade fully working (the moved files still exist there), so the
split is not a flag day. Step 4 is the only irreversible one and should be its
own commit.

## Testing

- **videocrunch**: the moved suites (`optimizer_utils`, `optimizer_ffmpeg`,
  `scan_folder`, `batch_controller`, `bitrate_analyzer`, the `hw_encode_detect`
  tests) plus the fixture parity test. ffmpeg-dependent tests keep their
  existing `skipif` guards so the suite runs on a bare CI box.
- **Arcade**: unchanged suites minus the moved ones, plus its own fixture parity
  test and a new test for the missing-videocrunch error path.
- Manual verification before step 4: run a real encode through
  `crunch.sh` and through the Arcade queue, confirming both write history and
  the candidates view still improves its estimates.

## Risks

- **Two encoder-profile tables drifting.** Only videocrunch has one after the
  split, so this is avoided by construction — but it is worth stating that
  Arcade must never grow its own copy of `ENCODER_PROFILES`.
- **The savings fixture becoming a rubber stamp.** If it is regenerated from the
  implementation whenever it fails, it stops pinning anything. Changing the
  fixture must be a deliberate, reviewed act — the same rule the repo's other
  contract tests live by.
- **Two repos, one habit.** Encoder work will keep starting in the Arcade
  checkout out of muscle memory. Arcade's CLAUDE.md needs a pointer saying the
  encoder lives elsewhere now.
