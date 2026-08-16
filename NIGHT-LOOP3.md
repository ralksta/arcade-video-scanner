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

- [x] **Loop A — UX** — ausgereizt (6 Punkte, 1 bewusst offen gelassen)
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
      - [ ] **Frage an Ralf**: Der Ordner-Browser bekam einen eigenen Bottom-Nav-
            Eintrag, weil die View-Toggles auf dem Handy fehlten; dafür flog
            **Vault** aus der Bottom-Nav (CHANGELOG, „Mobile-Navigation"). Der
            Grund ist jetzt weg — soll Vault dort zurück? Nicht eigenmächtig
            geändert, das ist eine Design-Entscheidung.
      - [x] Rückmeldungen vereinheitlicht: 30 `alert()` → Toasts; dabei
            Toast-z-index unter Optimizer-/GIF-Panel entdeckt und behoben
      - [x] ROADMAP-Haken für „Customizable grid layout" nachgezogen
- [ ] **Loop B — Performance** (Messung an der echten DB: 8788 Einträge, 4,95 MB JSON)
      - [x] `/api/videos`-Antwort-Cache: ~105 ms CPU/Request gespart
      - Messwerte: `SELECT *` 40 ms · `_row_to_api_dict` 68 ms · `json.dumps` 42 ms ·
        `gzip(6)` 54 ms (→ 0,56 MB) · Filterschleife 10,5 ms
      - [ ] Indizes prüfen: 8 Stück auf `media`, aber keiner auf `file_path`-Präfix
      - [x] Caching-Header geprüft: Thumbnails (`max-age=604800` + 304) und
            Static (`no-cache` + 304 + gzip) waren korrekt — der Fehler lag im
            Cache-Buster `?v={int(time.time())}`, der alles entwertete
      - [ ] HTML-Dump (`index.html`, 204 KB) — wird bei jeder Änderung neu erzeugt
      - [ ] Filterschleife: `os.path.abspath` pro Eintrag kostet 8,8 der 10,5 ms.
            Nach dem Antwort-Cache nur noch bei Cache-Miss relevant — bewusst
            zurückgestellt, weil eine Semantikänderung (Normalisierung) riskanter
            wäre als der Gewinn
- [ ] **Loop C — Feature**: Ein abgeschlossenes, kleines Feature inkl. Tests + CHANGELOG.

## Zyklus 2 (Loops werden nach Zyklus 1 festgelegt)

- [ ] Loop D — ?
- [ ] Loop E — ?

## Journal

<!-- Jede Iteration hängt hier eine Zeile an: was gemacht, was gelernt, was als Nächstes. -->

- **Iteration 6 (Loop B, Cache-Buster)** — Die Header waren alle richtig
  gesetzt; entwertet wurde der Cache eine Ebene höher, in der URL. Lehre: bei
  Caching-Fragen nicht nur die Header prüfen, sondern ob die URL überhaupt
  stabil bleibt. Nebenbei zwei Tests entschärft, die sich nach der Umstellung
  still selbst übersprungen hätten (`pytest.skip`, wenn ein Dateiname nicht
  gefunden wird) — die prüfen jetzt gegen `SCRIPT_MODULES` als echten Vertrag.
  Nächstes: Indizes und HTML-Dump.

- **Iteration 5 (Loop B, Performance)** — Erst gemessen, dann gefixt. Gelernt:
  gzip und ein Medien-Cache waren längst da — die Lücke lag dazwischen, nämlich
  dass beide teuren Schritte (Serialisieren, Komprimieren) trotz unveränderter
  Daten jedes Mal neu liefen. Zweite Lehre beim Absichern: zwei Routen
  invalidieren den Medien-Cache direkt, nicht über `register_on_change` — ein
  zweiter Cache daneben wäre dort still veraltet. Deshalb hängt der abgeleitete
  Cache jetzt am Medien-Cache statt an der DB. Nächstes: Indizes und
  Caching-Header.

- **Iteration 4 (Loop A, Rückmeldungen)** — `alert()` komplett abgelöst.
  Gelernt: Der eigentliche Fund kam nicht aus der Umstellung selbst, sondern aus
  der Frage „wo erscheinen die Toasts eigentlich?" — z-index 10000 gegen zwei
  Panels auf 10050/10100, beide `bottom-4`. Die Meldungen im Optimizer waren also
  schon vorher unsichtbar, unabhängig von dieser Änderung. Loop A ist damit
  ausgereizt bis auf die 44-px-Touch-Ziele, die ohne Browser nicht seriös zu
  beurteilen sind. Nächstes: Loop B (Performance).

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
