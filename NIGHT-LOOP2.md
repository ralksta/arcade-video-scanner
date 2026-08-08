# Nachtlauf 2 — Härtungs-Reste (B) + Embedding-Fundament (C)

Vollautonom, keine Rückfragen möglich. Entscheidungen selbst treffen und in Commit-Messages dokumentieren. NIE mergen, NIE force-pushen, NIE fremde Branches anfassen.

**Zustand ermitteln (Beginn jeder Iteration):** `git worktree list`, `git log --oneline -10` im jeweiligen Worktree, offene PRs (`gh pr list`). Erledigte Phasen NIE wiederholen — Fortschritts-Marker sind die Commits und die PR-Liste.

**Nach jedem Worktree-Wechsel:** `cp /Users/ralfo/git/arcade-video-scanner/.claude/worktrees/auto-tagging-night/.claude/ralph-loop.local.md <neuer-worktree>/.claude/` (Loop-Zustand mitnehmen, falls Datei existiert).

## Phase A — Härtungs-Reste auf PR #33 (Branch worktree-optimizer-candidates)

In den Worktree `/Users/ralfo/git/arcade-video-scanner/.claude/worktrees/optimizer-candidates` wechseln (EnterWorktree mit path). Drei Minors aus dem Final-Review von PR #33, als EIN Commit:

1. `arcade_scanner/database/sqlite_store.py`: `get_active_queue_paths() -> set` → `-> set[str]`.
2. `arcade_scanner/server/routes/candidates.py`: `_get_deps()` Rückgabe-Annotation ergänzen (Tuple der Singletons); Modul bleibt mypy-sauber.
3. `arcade_scanner/server/static/candidates.js`: expliziten `window.X = X`-Exportblock ans Dateiende (renderCandidatesView, setCandidatesCodec, toggleCandidateSelect, queueCandidate, queueSelectedCandidates) — Konvention wie duplicates.js/optimizer.js.

NICHT: escapeHtml in candidates.js (der Helper lebt auf dem night/auto-tagging-Branch; Doppel-Edit von utils.js erzeugt Merge-Konflikte — das ist ein Follow-up NACH dem Merge beider PRs, im PR-#33-Kommentar vermerken via `gh pr comment`).

Verifikation: `.venv/bin/pytest`, `.venv/bin/ruff check .`, `.venv/bin/mypy arcade_scanner`, `node --check arcade_scanner/server/static/candidates.js`. Commit `chore(review): Deferred Minors aus dem Final-Review` und `git push` (Branch ist PR #33 — Push aktualisiert den PR, das ist gewollt).

## Phase B — Embedding-Fundament (C aus dem Brainstorming)

Spec: `docs/superpowers/specs/2026-08-07-embedding-foundation-design.md` (liegt auf dev). Neuer Worktree:
`git worktree add /Users/ralfo/git/arcade-video-scanner/.claude/worktrees/embedding-night -b night/embedding-foundation dev` (aus dem aktuellen Worktree heraus aufrufen), dann per EnterWorktree (path) hineinwechseln, venv aufsetzen (`python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && .venv/bin/pip install -q -e ".[dev]"`), Baseline-Tests.

Zuerst einen Implementierungsplan `docs/superpowers/plans/2026-08-08-embedding-foundation.md` aus der Spec schreiben (Task-Struktur mit Checkboxen wie beim Auto-Tagging-Plan; Code-Level-Detail, TDD) und committen. Dann Task für Task umsetzen, Checkboxen abhaken, TDD, nach jedem Task voller pytest+ruff+mypy.

Kernpunkte aus der Spec (bindend):
- Tabellen `embedding_meta` (file_path PK, model, dim, mtime, indexed_at, mean_vector BLOB) und `frame_embeddings` (file_path, frame_index, ts_sec, vector BLOB; PK (file_path, frame_index)) in `sqlite_store.py`; Store-Methoden zum Schreiben/Lesen (eine Transaktion pro Datei), Löschen verwaister Einträge, mtime/model-basierte Skip-Abfrage.
- `arcade_scanner/core/similarity.py`: Float32-Blob-Codec (struct, KEIN numpy), L2-Normalisierung, Brute-Force-kNN über Mean-Vektoren (Skalarprodukt), In-Memory-Cache mit Invalidierung über `register_on_change`.
- `arcade_scanner/server/routes/similar.py`: `GET /api/similar?path=…&limit=12` — Session-pflichtig, Vault-Filterung wie bestehende Routen, `{"status":"not_indexed"}` bei leerem Index (HTTP 200), 404 bei unbekanntem/unindiziertem Query-Pfad, 400 bei fehlendem path; Dispatch in api_handler VOR files einhängen (GET only).
- `scripts/media_indexer.py`: eigenständiges CLI nach Optimizer-Vorbild — torch/open_clip NUR lazy in der Inferenz-Funktion importieren (Modul muss ohne ML-Stack importierbar sein, Tests mocken das Modell), 12 gleichverteilte Sample-Zeitpunkte über 5%–95% der Laufzeit (Kurzvideos: so viele wie möglich, min. 1; Bilder: 1 „Frame"), ffmpeg-Frame-Extraktion, inkrementell (mtime+model-Skip), `--watch --interval N`, `--rebuild`, `--model` (Default ViT-B-16), Aufräumen gelöschter Dateien, Fehlerdateien loggen+überspringen.
- `pyproject.toml`: optionale Dependency-Gruppe `[indexer]` (torch, open_clip_torch) — NIEMALS in den Server-Runtime-Deps; kein Server-Modul importiert torch.
- Alle CI-Tests OHNE ML-Stack lauffähig: Blob-Codec/kNN-Unit-Tests, Routen-Tests mit Fixture-Zeilen, Sampling-/Inkrement-Logik mit gemocktem Modell, Schema-Test (frische + bestehende DB).
- CHANGELOG `[Unreleased]`-Eintrag.

Abschluss Phase B: `git push -u origin night/embedding-foundation`, PR gegen dev (`gh pr create --base dev`, Titel `feat: Embedding-Fundament — Indexer, Vektor-Store, /api/similar (Teil 1)`), Body mit Hinweis: GPU-Echtlauf des Indexers steht aus (4090-PC), Teil 2–4 (Ähnlich-Leiste, Themen, Textsuche) folgen. Body endet mit `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## Phase C — Falls noch Zeit/Iterationen: weitere Arbeit selbst wählen

Priorisierte Kandidaten (jeweils eigener Branch `night/<thema>` aus dev + eigener PR, gleiche Qualitätsregeln):
1. **ROADMAP-Punkt „Stop a running scan from the UI"**: `POST /api/scan/stop`-Endpoint (Session-pflichtig) der `ScannerManager.stop()` ruft; `/api/rescan` auf Hintergrund-Thread umstellen (202 + Status-Polling statt blockierendem Request, siehe ROADMAP-Notiz); Stop-Button im Scan-Fortschritt der Settings; Tests.
2. Weitere Routen-Testabdeckung (files.py-Handler, die noch keine Tests haben).
Nur beginnen, was auch fertig wird — lieber ein abgeschlossener kleiner PR als ein halber großer.

## Abbruch-Regel

3 Iterationen ohne Fortschritt am selben Problem → Blocker in einer Datei `NACHTLAUF2-BLOCKER.md` im betroffenen Worktree dokumentieren, committen, pushen, erreichten Stand als PR sichern, dann Promise ausgeben.

## Ende

NUR wenn Phase A gepusht ist UND Phase B komplett mit grünen Tests/Lints und erstelltem PR ist (oder die Abbruch-Regel griff): gib exakt aus: `<promise>NACHTLAUF2-KOMPLETT</promise>` — Phase C ist optional und verlängert die Loop nicht.
