# Nachtlauf 3 — Loop-Zyklen auf `feat/nightly-loops`

Autonomer Nachtlauf, gestartet 2026-08-16. Branch: `feat/nightly-loops` (aus `dev`).

## Rahmen (vom User vorgegeben)

- **Kein Push, kein PR, kein Merge.** Nur lokale Commits auf `feat/nightly-loops`.
- Scope: alles — Web-Frontend/Templates, Server/Routes/DB, Scanner/Optimizer, TV/iOS-Clients.
- Features: freie Wahl (Roadmap-Punkte + eigene naheliegende Verbesserungen).
- Größere Refactorings erlaubt, wenn ein Loop es rechtfertigt.
- Vor JEDEM Commit: `.venv/bin/pytest` grün + `.venv/bin/ruff check .` nicht schlechter als Baseline.
- Conventional Commits mit Scope. Jeder Loop-Schritt = eigener Commit.

## Abbruch-Kriterium pro Loop (korrigiert nach Rückfrage des Users)

Ein Loop ist **nicht** nach einer festen Anzahl Punkte fertig. Er läuft, bis mir
im jeweiligen Themenfeld nichts Lohnendes mehr einfällt — konkret: bis zwei
aufeinanderfolgende Durchgänge nur noch Kosmetik oder Spekulation hervorbringen.
Erst dann Haken setzen und zum nächsten Loop.

Der 60-Sekunden-Wakeup ist nur der Selbst-Aufweck-Takt, kein Zeitbudget.

## Baseline (Start)

- `pytest`: 880 passed, 1 xfailed
- `ruff`: 8 vorbestehende Fehler (api_handler I001, generate_proxies E702 ×5, 2× Test-I001)

## Zyklus 1

- [ ] **Loop A — UX** (wieder geöffnet: war nach 2 Punkten vorschnell abgehakt)
      - [x] Tastaturkürzel-Overlay `?` + globale Shortcuts (`/`, `1`–`4`) — `150eb83`
      - [x] Kontextbezogener Leer-Zustand statt weißer Fläche — `ae18a9a`
      - [x] Fehler-Zustände: 19/63 `fetch`-Aufrufe ohne Fehlerpfad, `apiWrite()`
            mit Rollback + Regressionstest — `006cd8e`
      - [x] A11y: 14 Icon-Buttons gelabelt, 262 Icons `aria-hidden`,
            Fokus-Käfig für Dialoge (`a11y.js`) — Fokus-Ringe waren schon da
      - [x] Mobile: Ansichts-Umschalter waren `hidden md:flex` — drei von vier
            Ansichten auf dem Handy unerreichbar. Dabei zwei Fehler in den
            gespeicherten Ansichten gefunden (Sichtbarkeit, Apostroph im Namen)
      - [ ] Offen aus diesem Punkt: 64 Buttons unter 44 px Touch-Ziel. Ohne
            Browser nicht verantwortbar zu ändern — braucht visuelle Prüfung
      - [ ] Stille Aktionen: welche Buttons geben heute keinerlei Rückmeldung
      - [ ] ROADMAP-Haken für „Customizable grid layout" nachziehen — ist längst
            da (`gridScaleSlider` + `--grid-min-width`, `workspace.js:130`)
- [ ] **Loop B — Performance**: Messen, dann fixen. Kandidaten: SQLite-Indizes für die
      heißen Query-Pfade, Thumbnail-/Static-Caching-Header, HTML-Dump-Größe, JS-Renderpfad
      (DocumentFragment statt innerHTML-Konkatenation), N+1 in Routen.
- [ ] **Loop C — Feature**: Ein abgeschlossenes, kleines Feature inkl. Tests + CHANGELOG.

## Zyklus 2 (Loops werden nach Zyklus 1 festgelegt)

- [ ] Loop D — ?
- [ ] Loop E — ?

## Journal

<!-- Jede Iteration hängt hier eine Zeile an: was gemacht, was gelernt, was als Nächstes. -->

- **Iteration 3 (Loop A, Mobile)** — Ansichts-Umschalter freigelegt. Gelernt:
  `hidden md:*` ist der stille Killer für Mobile — sieht im Markup harmlos aus und
  fällt auf dem Entwickler-Desktop nie auf. Der neue Test prüft das jetzt über die
  Vorfahren-Kette, nicht nur am Element selbst, und wurde gegen den echten Fehler
  verifiziert (vorher rot, nachher grün). Zweite Lehre: `escapeHtml` rettet
  JS-in-Attribut nicht — der HTML-Parser löst `&#39;` vor dem JS-Parser auf.
  Nächstes: stille Aktionen ohne Rückmeldung.

- **Iteration 2 (Loop A, A11y)** — Icon-Buttons gelabelt, Icons aus der
  Screenreader-Ausgabe genommen, Fokus-Käfig für Dialoge. Gelernt: `:focus-visible`
  war global bereits sauber gelöst (`theme.py:454`) — der Mangel lag nicht bei den
  Ringen, sondern daran, dass der Fokus die Dialoge überhaupt verlassen konnte.
  Ohne jsdom im Projekt (bewusst kein Build-Schritt) stellt der Test die DOM-
  Oberfläche nach, die der Handler benutzt. Nächstes: Mobile-Touch-Ziele.

- **Iteration 1 (Loop A, UX)** — Shortcut-Overlay + Leer-Zustand. Gelernt: die
  Ladereihenfolge-Tests (`test_js_completeness`, `test_dashboard_template`) suchten
  Dateinamen als nackte Substrings; `find("engine.js")` traf `filter_engine.js`.
  Jetzt auf `/static/<name>.js` verschärft. Nächstes: Loop B (Performance) —
  zuerst messen (Query-Zeiten, HTML-Dump-Größe, Render-Pfad), dann fixen.
