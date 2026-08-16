# Nachtlauf 3 — Loop-Zyklen auf `feat/nightly-loops`

Autonomer Nachtlauf, gestartet 2026-08-16. Branch: `feat/nightly-loops` (aus `dev`).

## Rahmen (vom User vorgegeben)

- **Kein Push, kein PR, kein Merge.** Nur lokale Commits auf `feat/nightly-loops`.
- Scope: alles — Web-Frontend/Templates, Server/Routes/DB, Scanner/Optimizer, TV/iOS-Clients.
- Features: freie Wahl (Roadmap-Punkte + eigene naheliegende Verbesserungen).
- Größere Refactorings erlaubt, wenn ein Loop es rechtfertigt.
- Vor JEDEM Commit: `.venv/bin/pytest` grün + `.venv/bin/ruff check .` nicht schlechter als Baseline.
- Conventional Commits mit Scope. Jeder Loop-Schritt = eigener Commit.

## Baseline (Start)

- `pytest`: 880 passed, 1 xfailed
- `ruff`: 8 vorbestehende Fehler (api_handler I001, generate_proxies E702 ×5, 2× Test-I001)

## Zyklus 1

- [x] **Loop A — UX** (2 Commits)
      - [x] Tastaturkürzel-Overlay `?` + globale Shortcuts (`/`, `1`–`4`) — `150eb83`
      - [x] Kontextbezogener Leer-Zustand statt weißer Fläche — `ae18a9a`
      - Verworfen: „Grid-Layout konfigurierbar" aus der ROADMAP ist längst da
        (`gridScaleSlider` + `--grid-min-width`, `workspace.js:130`) — nur der
        Haken fehlt. Wird in einem Doku-Commit nachgezogen.
- [ ] **Loop B — Performance**: Messen, dann fixen. Kandidaten: SQLite-Indizes für die
      heißen Query-Pfade, Thumbnail-/Static-Caching-Header, HTML-Dump-Größe, JS-Renderpfad
      (DocumentFragment statt innerHTML-Konkatenation), N+1 in Routen.
- [ ] **Loop C — Feature**: Ein abgeschlossenes, kleines Feature inkl. Tests + CHANGELOG.

## Zyklus 2 (Loops werden nach Zyklus 1 festgelegt)

- [ ] Loop D — ?
- [ ] Loop E — ?

## Journal

<!-- Jede Iteration hängt hier eine Zeile an: was gemacht, was gelernt, was als Nächstes. -->

- **Iteration 1 (Loop A, UX)** — Shortcut-Overlay + Leer-Zustand. Gelernt: die
  Ladereihenfolge-Tests (`test_js_completeness`, `test_dashboard_template`) suchten
  Dateinamen als nackte Substrings; `find("engine.js")` traf `filter_engine.js`.
  Jetzt auf `/static/<name>.js` verschärft. Nächstes: Loop B (Performance) —
  zuerst messen (Query-Zeiten, HTML-Dump-Größe, Render-Pfad), dann fixen.
