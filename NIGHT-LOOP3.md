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
- [x] **Loop B — Performance** — ausgereizt (Messung an der echten DB: 8788 Einträge, 4,95 MB JSON)
      - [x] `/api/videos`-Antwort-Cache: ~105 ms CPU/Request gespart
      - Messwerte: `SELECT *` 40 ms · `_row_to_api_dict` 68 ms · `json.dumps` 42 ms ·
        `gzip(6)` 54 ms (→ 0,56 MB) · Filterschleife 10,5 ms
      - [x] Indizes: 5 von 8 wurden von keinem Query-Plan benutzt, entfernt.
            Schreiben 66% schneller, DB 38% kleiner
      - [x] Caching-Header geprüft: Thumbnails (`max-age=604800` + 304) und
            Static (`no-cache` + 304 + gzip) waren korrekt — der Fehler lag im
            Cache-Buster `?v={int(time.time())}`, der alles entwertete
      - [x] HTML-Dump: toter `clean_results`-Aufbau entfernt (8788 Dict-Kopien
            pro Neugenerierung, Ergebnis verworfen) und dabei ein Leck gefunden —
            `FOLDERS_DATA` trug die Ordnerpfade aller Nutzer in den gemeinsamen
            Dump. CLAUDE.md beschrieb außerdem einen Trennungs-Mechanismus, den
            es so nicht mehr gab; korrigiert
      - [ ] Filterschleife: `os.path.abspath` pro Eintrag kostet 8,8 der 10,5 ms.
            Nach dem Antwort-Cache nur noch bei Cache-Miss relevant — bewusst
            zurückgestellt, weil eine Semantikänderung (Normalisierung) riskanter
            wäre als der Gewinn
- [x] **Loop C — Feature** — ausgereizt (4 Features)
      - [x] „Ähnliche Medien"-Leiste im Cinema (Embedding Teil 2) — Backend
            `/api/similar` gab es schon, nur die Oberfläche fehlte
      - [x] Index-Status (`/api/similar/status`) + Anzeige in den Einstellungen —
            macht sichtbar, ob die Ähnlich-Leiste überhaupt Daten haben kann
      - [x] Veraltete Proxys erkennen (Roadmap-Punkt „automatische
            Aktualisierung") — Server fällt zurück, Generator erneuert
      - [x] Export der aktuellen Ansicht (CSV/M3U) — ein Inventar-Werkzeug ohne
            Export lässt jede Auswertung in der Oberfläche gefangen

## Zyklus 2

Beide Themen sind aus den Funden von Zyklus 1 abgeleitet, nicht frei erfunden.

- [x] **Loop D — Stille Fehlerpfade und Randfälle** — ausgereizt (4 Fixes, 2 Wächter)
      - [x] 46 nackte `except: pass` erfasst; vier davon schalteten sichtbares
            Verhalten ab (Auto-Tagging nach Scan, Laufzeitprüfung beim Upload,
            Bild-Scan, Resource-Watchdog) — laut gemacht, Rest ist legitim
      - [x] 50 Divisionen mit variablem Divisor geprüft: die meisten sauber
            abgesichert, aber `1/speed` im GIF-Export nicht — Parameter werden
            jetzt an der Grenze validiert
      - [x] Nebenläufigkeit: `/api/debug/dump` las an `_write_lock` vorbei auf
            der geteilten Verbindung — gekapselt, Contract-Test ergänzt
      - [x] Unbegrenztes Wachstum: `GIF_JOBS` wurde nie aufgeräumt — jetzt
            Registry mit Lock, Obergrenze und Ablaufzeit
      - [x] Zusage „nur vier Laufzeit-Abhängigkeiten, kein Framework" abgesichert.
            Kein Fehler gefunden — der Bestand hält sie exakt ein; es fehlte
            nur der Wächter
      - [x] Ignorierte Rückgabewerte: im Server keiner — beide `config.save()`-
            Aufrufer prüfen korrekt. Nur ein Wartungsskript meldete Erfolg,
            ohne den Status anzusehen
      Die ergiebigste Ader der Nacht: veraltete Proxys, ein Cache ohne
      Invalidierung, `FOLDERS_DATA` mit fremden Pfaden, eine Test-Suite die ins
      Produktivverzeichnis schrieb — alle vier hatten gemeinsam, dass nichts
      abstürzte und niemand etwas merkte. Systematisch weitersuchen:
      - Was passiert bei leerer Bibliothek / null Einträgen / Division durch null?
      - Was passiert, wenn zwei Threads dasselbe tun (Scan + Request + Queue)?
      - Wo wird ein Rückgabewert ignoriert, wo ein `except` verschluckt?
      - Wo hängt Korrektheit an einer Zusage, die kein Test prüft?

- [ ] **Loop E — Konsistenz zwischen den Clients**
      - [x] Endpunkt-Abgleich: **iOS-Client seit `8c6008a` funktionsunfähig**
            (tote DeoVR-Routen + keine Sitzung). Dokumentiert statt blind
            repariert — keine Swift-Toolchain zum Prüfen. Vertrags-Test ergänzt
      - [x] Filter-Semantik: TV-Client las `v.status` statt `v.Status` — Status-
            Filter kehrten sich um. Plus Codec-Vergleich, `favorites: false` und
            Vault-Regel angeglichen; Differenztest gegen den Browser-Matcher
      `CLAUDE.md` warnt ausdrücklich davor, dass TV- und iOS-Client bei
      API-Änderungen mitgezogen werden müssen; frühere Commits haben genau das
      nachgeholt. Nach einer Nacht mit Änderungen an `/api/videos`,
      `/api/similar` und der Proxy-Auflösung lohnt der Abgleich:
      - Welche Filter-/Sortier-Semantik weicht ab?
      - Welche neuen Endpunkte fehlen den Clients?
      - Wo sind Annahmen über Antwortformate fest verdrahtet?

## Journal

<!-- Jede Iteration hängt hier eine Zeile an: was gemacht, was gelernt, was als Nächstes. -->

- **Iteration 20 (Loop E, Filter-Semantik)** — Dieselbe Semantik liegt dreimal
  im Projekt: Browser, Python-Port (an den Browser gepinnt) und TV-Client. Die
  dritte Kopie hing an nichts — und enthielt einen Tippfehler, der das Verhalten
  nicht bricht, sondern *umkehrt*: `v.status` statt `v.Status`, also immer
  `undefined`, also traf `pending` immer und `optimized` nie. Der Differenztest
  fand danach sofort eine zweite Abweichung, an die ich nicht gedacht hatte
  (Vault-Videos in Sammlungen). Lehre: bei mehrfach implementierter Logik ist
  der Differenztest wertvoller als jede Durchsicht.

- **Iteration 19 (Loop E, Endpunkt-Abgleich)** — Der größte Fund der Nacht
  gemessen an der Auswirkung: Der iOS-Client spricht Endpunkte an, die es seit
  einem Aufräum-Commit nicht mehr gibt. Er ist damit seit Monaten tot, und
  niemand hat es bemerkt — weil Clients in eigenen Sprachen leben und kein
  Import bricht. Bewusste Entscheidung: **nicht** blind repariert. Ohne
  Swift-Toolchain hätte ich ~150 Zeilen unprüfbaren Code geschrieben, die nach
  Fortschritt aussehen, und der nächste Mensch könnte Geprüftes nicht von
  Ungeprüftem unterscheiden. Stattdessen präzise dokumentiert, was fehlt, plus
  ein Test, der die nächste solche Drift am Tag ihrer Entstehung meldet.

- **Iteration 18 (Loop D, Rückgabewerte)** — Erst eine Fehlanalyse: mein
  AST-Matcher ging nach Funktionsnamen und meldete sechs verworfene `save()`-
  Aufrufe. Das waren `db.save()` (ein dokumentierter No-Op), nicht das
  `config.save()` mit Statusrückgabe. Lehre: bei namensbasierter Suche gehört
  der Empfänger dazu, sonst produziert man Funde, die keine sind. Echter Befund
  nach der Korrektur: beide Server-Aufrufer prüfen sauber, nur ein
  Wartungsskript meldete „Success", ohne hinzusehen. Zwei magere Durchgänge in
  Folge — Loop D ist damit ausgereizt.

- **Iteration 17 (Loop D, Abhängigkeits-Zusage)** — Hier gab es nichts zu
  reparieren: nur pydantic, pydantic-settings, Pillow, imagehash, alle auf
  Modul-Ebene, kein Framework irgendwo. Wert liegt allein im Wächter. Beim
  Verifizieren zweimal danebengegriffen (Einfügung vor `from __future__`, dann
  mitten hinein) — der saubere Nachweis lief am Ende über eine temporäre Datei
  mit `import pluggy`: installiert, aber nicht deklariert, also genau der Fall,
  der beim Entwickeln unsichtbar bleibt und erst bei frischer Installation
  zuschlägt.

- **Iteration 16 (Loop D, unbegrenztes Wachstum)** — Ein Leck, das man nur bei
  einem Werkzeug bemerkt, das *dauerhaft* läuft: ein Modul-Dict ohne Aufräumen.
  Beim Ersetzen war die eigentliche Frage nicht die Obergrenze, sondern die
  Aufbewahrungsdauer — zu kurz, und ein Auftrag verschwindet unter dem noch
  pollenden Client weg. Deshalb ein Test, der genau diese Untergrenze festhält.

- **Iteration 15 (Loop D, Nebenläufigkeit)** — Der Store dokumentiert seine
  Thread-Falle ausführlich und misst sie sogar (0 bis 5199 Zeilen bei 800). Und
  genau daneben griff eine Route direkt auf `_conn` zu. Lehre: eine Warnung im
  Kommentar schützt nur den, der sie liest; ein Test schützt alle. Der neue
  Contract-Test verbietet `._conn` außerhalb des Stores — einmal per Textsuche,
  einmal über den Syntaxbaum.

- **Iteration 14 (Loop D, Randfälle)** — 50 Divisionen mit variablem Divisor
  durchgesehen. Erfreulich: `criteria_eval`, `similarity` und `media_probe` sind
  sauber abgesichert. Der eine Treffer war `1/speed` im GIF-Export, hinter dem
  Guard `speed != 1.0` — der für 0 wahr ist. Ein Guard, der die falsche Frage
  stellt, sieht aus wie Absicherung. Beim Schreiben der Validierung gleich die
  NaN-Falle mitgenommen: `not (low <= x <= high)` statt `x < low or x > high`,
  sonst kommt NaN durch jede Grenze.

- **Iteration 13 (Loop D, stumme Handler)** — Der beste Fund war ein
  *veralteter* Guard, kein falscher: `except ImportError: pass` mit dem
  Kommentar „landet mit PR #34". Der PR kam, der Guard blieb — und verschluckte
  seither echte Fehler. Lehre: Kommentare, die auf einen künftigen Zustand
  verweisen, überleben diesen Zustand und werden dann gefährlich; ein Test
  darauf ist billiger als das Nachlesen. Der Zähler stummer Handler steht jetzt
  als Bremse im Test (43), damit sich neue nicht Datei für Datei einschleichen.

- **Iteration 12 (Loop C, Export)** — CSV-Maskierung gegen Pythons `csv`-Modul
  geprüft statt gegen die eigene Erwartung: ein unabhängiger RFC-4180-Leser muss
  zurückbekommen, was hineinging. Der Test mit Zeilenumbruch im Dateinamen ist
  kein konstruierter Fall — auf Unix ist das erlaubt, und unmaskiert zerreißt es
  die Zeile, ohne dass es bei 8000 Zeilen jemandem auffällt. Loop C ist damit
  ausgereizt; als Nächstes die zwei selbstgewählten Loops.

- **Iteration 11 (Loop C, veraltete Proxys)** — Der offene Roadmap-Punkt war als
  Feature notiert, ist aber ein Korrektheitsproblem: unterwegs bekam man eine
  Videofassung zu sehen, die es nicht mehr gibt. Entscheidung dazu: bei
  veraltetem Proxy auch dann das Original ausliefern, wenn `?proxy=1` ihn
  erzwingt — Bandbreite ist ersetzbar, eine falsche Fassung nicht. Zweiter Teil
  war nötig, damit es rund wird: der Generator übersprang jeden vorhandenen
  Proxy, hätte den veralteten also nie erneuert.

- **Iteration 10 (Loop C, Index-Status)** — Direkte Folge aus Iteration 9: Ein
  Feature, dessen Datengrundlage unsichtbar ist, wirkt kaputt statt leer. Der
  Status-Endpunkt kostet zwanzig Zeilen und beantwortet die Frage, die sonst
  jeder Nutzer an der leeren Leiste stellen würde. Beim Testen an den Rand
  gedacht: leere Bibliothek → Division durch null, jetzt abgedeckt.

- **Iteration 9 (Loop C, Ähnlich-Leiste)** — Zwei Lehren. Erstens: mein eigener
  Test aus Loop A (`test_cinema_section_documents_all_reserved_keys`) hat mich
  gezwungen, die neue Taste `S` auch im Overlay zu dokumentieren — genau wofür
  er da war. Zweitens: Beim Schreiben des Tests für veraltete Antworten fiel auf,
  dass mein Guard die falsche Größe verglich (eigene Merkvariable statt des
  laufenden Pfads); er hätte nur bei sich überholenden Anfragen gegriffen, nicht
  beim Weiterblättern. Der Test hat den Fehler gefunden, nicht das Nachdenken.
  Falscher Alarm zwischendurch: Ich hielt den GIF-Export für tot, weil
  `window.currentCinemaPath` nirgends zugewiesen wird — die Zuweisung läuft über
  `Object.defineProperty` am Ende von cinema.js, was mein Grep-Muster nicht traf.

- **Iteration 8 (Loop B, HTML-Dump)** — Der interessante Teil war nicht die
  Performance. Beim Schreiben eines Tests für die Zusage „der Dump enthält keine
  Nutzerdaten" fiel auf, dass die Zusage nicht galt: `FOLDERS_DATA` enthielt die
  Ordner aller Nutzer. Lehre: Behauptungen aus der Doku als Test formulieren —
  hier hat genau das den Fehler gefunden, nicht das Lesen des Codes.
  Damit ist Loop B ausgereizt.

- **Iteration 7 (Loop B, Indizes)** — 5 von 8 Indizes auf `media` waren reine
  Schreiblast. Lehre: der Kommentar über ihnen („common filter/sort queries")
  beschrieb eine Absicht, keine Abfrage — `EXPLAIN QUERY PLAN` hat es in einer
  Minute geklärt.

  **Korrektur und eigentlicher Befund:** Ich hatte zunächst dem Modul-Import die
  Schuld gegeben, dass die Migration auf der Produktivdatenbank lief. Das war
  falsch — der Import allein ist nachweislich harmlos. Verursacher ist
  `ReportDebouncer`: sein `threading.Timer` feuert eine Sekunde nach
  `schedule()` auf einem Daemon-Thread, wenn der `config`-Patch des Tests schon
  weg ist, und greift auf das echte `db`-Singleton zu. **Jeder volle
  `pytest`-Lauf** hat damit `arcade_data/media_library.db` geöffnet (inklusive
  Migrationen) und `arcade_data/index.html` überschrieben — ein vorbestehender
  Fehler, den meine Index-Änderung nur sichtbar gemacht hat. Gefunden über einen
  Stack-Trace aus `_generate`; die Halbierungssuche führte zuerst in die Irre,
  weil die Eigenschaft zeitabhängig und damit nicht monoton ist.
  Behoben per autouse-Fixture in `tests/conftest.py`, verifiziert: DB und
  index.html bleiben nach einem vollen Lauf unverändert.

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
