# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Export der aktuellen Ansicht** (CSV und M3U): Über die Command-Palette
  (`Ctrl`/`⌘`+`K` → „Ansicht als …") wird genau das ausgegeben, was gerade zu
  sehen ist — dieselbe Liste, dieselbe Reihenfolge, inklusive aller aktiven
  Filter. CSV mit Pfad, Größe, Dauer, Codec, Bitrate, Auflösung, Status,
  Favorit und Tags (RFC 4180 maskiert, BOM für Excel); M3U mit lokalen
  Dateipfaden für Player, die dieselbe Freigabe eingebunden haben. Ein
  Werkzeug zum Filtern und Auswerten, dessen Ergebnisse in der Oberfläche
  gefangen bleiben, ist nur die halbe Miete. Neu: `static/export_view.js`.

- **Index-Status in den Speicher-Einstellungen**: Neuer Endpunkt
  `/api/similar/status` (Session-pflichtig) meldet, wie viele Medien im
  Ähnlichkeits-Index liegen, wie hoch die Abdeckung ist und mit welchem Modell
  indiziert wurde; die Einstellungen zeigen das als Balken mit Klartext-Hinweis.
  Ohne diese Auskunft ließ sich nicht unterscheiden, ob es zu einem Medium keine
  ähnlichen gibt oder ob schlicht kein Index existiert — die Leiste im Cinema
  sieht in beiden Fällen gleich leer aus.

- **„Ähnliche Medien"-Leiste im Cinema** (Embedding-Fundament, Teil 2): Taste `S`
  oder der Rail-Button blendet über der Transportleiste verwandte Aufnahmen ein,
  mit Vorschaubild und Übereinstimmung in Prozent; ein Klick springt direkt
  dorthin und die Leiste zeigt sofort die Nachbarn des neuen Mediums. Ohne
  Indexlauf erklärt die Leiste, dass erst `scripts/media_indexer.py` laufen muss,
  statt einen Fehler zu zeigen — bei frischer Installation ist das der Normalfall.
  Treffer außerhalb der eigenen Scan-Ziele werden ausgefiltert (`/api/similar`
  filtert den Vault, kennt aber die Pfad-Ziele nicht), und beim schnellen
  Blättern verworfene Antworten überschreiben die Leiste nicht mehr.
  Neu: `static/similar.js`.

- **Tastaturkürzel-Overlay (`?`)**: Das Dashboard hatte eine ganze Reihe
  Tastenkürzel (Cinema: `←`/`→`, `Space`, `F`, `V`, `I`, `G`, `O` plus Tag-Shortcuts;
  Duplikat-Prüfung: `1`/`2`/`S`/`A`; Command-Palette: `Ctrl`/`⌘`+`K`) — dokumentiert
  war davon nichts. `?` öffnet jetzt überall eine Übersicht, ein Tastatur-Button in
  der Filter-Bar tut dasselbe für die Maus. Neu dazu: `/` fokussiert die Suche und
  `1`–`4` schalten zwischen Grid-, Listen-, Treemap- und Ordner-Ansicht um. Die
  globalen Kürzel halten sich zurück, während der Nutzer tippt oder Cinema bzw. die
  Duplikat-Prüfung offen ist. Neu: `static/shortcuts.js`.

- **Eine Sorte Rückmeldung statt zwei**: Das Dashboard nutzte 30 blockierende
  `alert()`-Dialoge neben 34 Toasts — dieselbe Art Information, einmal als
  Systemdialog mitten im Bild, einmal als Einblendung unten rechts. Alle
  `alert()`-Aufrufe sind jetzt Toasts mit passendem Typ (Fehler, Warnung,
  Erfolg, Info); `confirm()` bleibt, weil es einen Rückgabewert liefert. Dabei
  aufgefallen: Toasts lagen auf `z-index: 10000`, das Optimizer- (10050) und das
  GIF-Panel (10100) darüber — und beide sitzen `bottom-4`, also genau dort, wo
  die Toasts erscheinen. Meldungen aus dem Optimizer waren damit unsichtbar.

- **Ansichten auf dem Handy erreichbar**: Die Umschaltung zwischen Grid, Liste,
  Treemap und Ordner-Browser steckte in einem `hidden md:flex`-Container — auf
  einem Telefon gab es damit keinen Weg zu drei der vier Ansichten. Die Umschalter
  sind jetzt auf jeder Breite da; nur der Größen-Slider bleibt Desktop-only, weil
  er auf Touch kaum präzise treffbar ist. Ebenso: gespeicherte Ansichten waren auf
  dem Handy unerreichbar und nahmen auf dem Desktop auch dann Platz weg, wenn gar
  keine gespeichert waren — ihre Sichtbarkeit hängt jetzt am Inhalt.
  Damit entfällt der Grund für die frühere Umgehung, die den Ordner-Browser über
  einen eigenen Bottom-Nav-Eintrag erreichbar machte und dafür **Vault** aus der
  Bottom-Nav nahm (siehe „Mobile-Navigation" unter *Changed*). Ob Vault dort
  zurückkehren soll, bleibt eine Design-Entscheidung und wurde nicht angefasst.

- **Ansichts-Chips mit Apostroph im Namen**: Der Name wurde in einen
  `onclick`-Handler interpoliert; eine Ansicht namens `Ralf's Urlaub` zerlegte
  damit den Handler und machte den Chip unklickbar. Die Chips werden jetzt als
  DOM-Knoten gebaut, ohne String-Interpolation.

- **Barrierefreiheit**: 14 Icon-Buttons (Schließen-Kreuze, Zahlen-Stepper in den
  Einstellungen, Tag löschen, Favorit auf der Karte) hatten keinen zugänglichen
  Namen und wurden nur als „Schaltfläche" angesagt — sie tragen jetzt
  `aria-label`. 262 Material-Icons-Spans sind `aria-hidden`, weil ein
  Screenreader sonst den Ligatur-Namen vorliest („star_border", „more_vert").
  Neu: `static/a11y.js` sperrt den Tastaturfokus in offene Dialoge ein (Tab und
  Shift+Tab laufen im Dialog um) und gibt ihn beim Schließen an das Element
  zurück, von dem aus geöffnet wurde. Vorher tabbte man aus dem offenen Dialog
  in die Seite dahinter.

- **Sichtbare Fehler statt stiller Divergenz**: 19 von 63 `fetch`-Aufrufen im
  Frontend hatten keinerlei Fehlerpfad. Die schlimmsten davon aktualisierten die
  Oberfläche optimistisch und feuerten den Server-Aufruf danach ab — war der
  Server weg, zeigte das Dashboard einen Zustand an, den der Server nie gesehen
  hatte, sichtbar erst beim nächsten Reload. Neu: `apiWrite()` in `api.js` prüft
  den Status, meldet den Fehler und rollt die optimistische Änderung zurück
  (Vault, Favorit, Batch-Vault, Batch-Favorit, Tag anlegen). Ebenfalls behoben:
  „Batch-Optimierung gestartet" erschien auch dann, wenn der Auftrag nie ankam;
  der Einrichtungs-Assistent blieb bei einem Serverfehler dauerhaft leer;
  Views/Collections galten als gespeichert, obwohl der Aufruf scheiterte. Ein
  Test hält alle `fetch`-Aufrufe künftig auf einem Fehlerpfad.

- **Leer-Zustand im Grid**: 0 Treffer hießen bisher: weiße Fläche, keine
  Erklärung, kein Weg zurück. Jetzt erklärt das Grid, *warum* nichts da ist —
  leere Bibliothek (mit Link in die Einstellungen und zum Scan), zu enge Suche
  (mit „Suche löschen"), zu enge Filter (mit „Filter zurücksetzen"), oder ein
  noch leerer Vault/Favoriten/Review-Workspace samt Hinweis, wie man dort etwas
  hineinbekommt. Neu: `static/empty_state.js`.

- **Proxy Streaming**: Every video may have a smaller copy in its own directory
  tree, which is excluded from scans. `/stream` decides per request which file to
  serve — the original on the LAN, the proxy over Tailscale (CGNAT
  `100.64.0.0/10` and `fd7a:115c:a1e0::/48`), falling back to the original when no
  proxy exists. The library still shows exactly one entry per video, and originals
  are never modified. Controlled through `proxy_streaming` / `proxy_root` in the
  Settings UI; `?proxy=0` and `?proxy=1` override the automatic choice, and the
  response carries `X-Arcade-Variant`. New: `core/proxy_resolver.py`,
  `core/master_detect.py` (identifies raw camera material by folder, keyword,
  camera filename scheme and device name, so proxies are built from edits rather
  than from source footage) and `scripts/generate_proxies.py` (creates the proxies
  on a remote NVENC machine, reading originals only).

### Performance
- **Fünf ungenutzte Indizes auf `media` entfernt.** Die Tabelle trug acht
  Indizes, angelegt für „common filter/sort queries" — gefiltert und sortiert
  wird aber im Frontend: der Server liefert über `/api/videos` alle Zeilen aus,
  und kein SQL im Projekt verwendet `status`, `codec`, `size_mb`, `favorite`
  oder `vaulted` in einem WHERE oder ORDER BY. Per `EXPLAIN QUERY PLAN` gegen
  die reale Bibliothek geprüft: kein Plan hat sie je angefasst, bezahlt wurden
  sie bei jedem Upsert. Gemessen: 2000 Upserts in 16 ms statt 47 ms, Datei
  3,48 MB statt 5,58 MB. Bestehende Datenbanken werden beim Öffnen migriert.
  Die drei verbliebenen Indizes (`idx_mtime`, `idx_media_type`, `idx_thumb`)
  sind jeweils einer konkreten Abfrage zugeordnet und per Test daran gepinnt.
- **Browser-Cache für statische Assets wieder wirksam.** Die 28 Script- und
  Link-Tags trugen `?v={int(time.time())}` — für jede Datei denselben Wert, neu
  bei jeder Neugenerierung des HTML-Reports (nach jedem Scan, jeder
  Einstellungsänderung, jedem Encode-Upload). Eine neue URL ist im Browser-Cache
  kein 304, sondern ein voller Fehltreffer: 588 KB (122 KB gzip) wurden erneut
  übertragen, obwohl sich nichts geändert hatte — der `no-cache`-Header des
  Servers, der sonst billige 304er liefert, lief dabei ins Leere. Die Version
  kommt jetzt aus der mtime der jeweiligen Datei, eine URL ändert sich also nur
  noch, wenn sich genau diese Datei ändert.
- **`/api/videos`: ~105 ms CPU pro Request eingespart.** Gemessen an der echten
  Bibliothek (8788 Einträge): der Endpunkt serialisierte bei *jedem* Request
  4,95 MB JSON neu (~40 ms) und komprimierte sie neu (~54 ms), dazu ~10 ms
  Pfadfilterung — obwohl sich zwischen zwei Requests meist nichts ändert, und
  obwohl drei Clients (Browser, TV, iOS) denselben Posten unabhängig zahlen.
  Fertige Bodies liegen jetzt roh *und* gzip-komprimiert im Speicher, geschlüsselt
  nach Scan-Zielen und Admin-Flag; ein Treffer kostet noch einen Dict-Zugriff.
  Der Cache hängt am Medien-Cache und verfällt mit ihm — auch bei den beiden
  Aufrufern, die direkt invalidieren (Fotos löschen, Encode-Upload).

### Fixed
- **Veraltete Proxys wurden stillschweigend ausgeliefert.** Die Auflösung prüfte
  nur, *ob* ein Proxy existiert. Wird ein Original nachbearbeitet — neuer
  Schnitt, andere Tonspur — blieb der alte Proxy liegen und lief unterwegs
  weiter: man sah eine Fassung, die es so nicht mehr gibt, ohne jeden Hinweis.
  `resolve_stream_path()` vergleicht jetzt die Änderungszeiten und fällt bei
  einem veralteten Proxy auf das Original zurück, auch bei erzwungenem
  `?proxy=1` — Korrektheit vor Bandbreite. Zwei Sekunden Toleranz gegen
  FAT-Rundung und rsync/SMB-Versatz. `scripts/generate_proxies.py` übersprang
  jeden vorhandenen Proxy und hätte einen veralteten nie erneuert; es erzeugt
  ihn jetzt neu. Damit ist der offene Roadmap-Punkt „automatische Aktualisierung,
  wenn sich ein Original ändert" abgedeckt.

- **Ordnerpfade fremder Bibliotheken im gemeinsamen HTML-Dump.** `index.html`
  wird einmal erzeugt und an jeden Nutzer ausgeliefert — enthielt aber
  `window.FOLDERS_DATA` mit der Ordner-Aggregation der *gesamten* Bibliothek,
  also auch den Verzeichnissen anderer Nutzer, samt vollem Pfad im
  `title`-Attribut der Ordner-Seitenleiste. `/api/videos` filtert sauber nach
  Scan-Zielen, der Dump umging das. Der Ordner-Baum wird jetzt clientseitig aus
  `ALL_VIDEOS` aufgebaut (`buildFoldersData()`), das bereits pro Nutzer
  gefiltert ist. Gefunden durch einen neuen Test, der prüft, dass aus einem
  Dump mit einem Eintrag `/geheim/privat/urlaub_2019.mp4` nichts davon in der
  Seite landet.

- **Die Test-Suite schrieb ins echte Datenverzeichnis.** `ReportDebouncer.schedule()`
  startet einen `threading.Timer`, der eine Sekunde später auf einem Daemon-Thread
  `_media_cache.get()` aufruft. Zu dem Zeitpunkt ist der `config`-Patch des
  auslösenden Tests längst abgeräumt, der Timer greift also auf das echte
  `db`-Singleton zu: er öffnete `arcade_data/media_library.db` samt aller
  Schema-Migrationen und überschrieb `arcade_data/index.html` — bei jedem vollen
  `pytest`-Lauf. Ein einzelner Testlauf reproduziert das nicht zuverlässig, weil
  der Prozess meist endet, bevor die Sekunde um ist; deshalb blieb es unbemerkt.
  Eine autouse-Fixture in `tests/conftest.py` neutralisiert den Debouncer jetzt
  und protokolliert die Aufrufe stattdessen, damit Tests weiterhin prüfen können,
  *dass* eine Route den Report anstößt.

- **Ordner-Browser: echte Hierarchie statt flacher Liste**. `getSubfoldersAt(null)`
  hielt jeden Pfad für eine oberste Ebene, zu dem es keinen *anderen Ordner mit
  Dateien* als Präfix gab. Da Mount-Verzeichnisse wie `/media_ralf` selbst keine
  Dateien enthalten, landete jeder tiefe Blattordner auf der Startebene — bei einer
  Bibliothek mit 8776 Dateien 153 flache Einträge statt 3 Mounts. Root- und
  Kind-Ebene laufen jetzt über denselben Code und leiten die nächste Ebene aus den
  Pfadsegmenten ab, so dass auch Zwischenordner ohne eigene Dateien eine Ebene
  bilden (`/media_ralf` → `OD`/`korea`/`Reface` → …). Breadcrumbs und die
  Zurück-Navigation folgen derselben Logik und springen keine Ebene mehr über.
- **Browser-Zurück im Ordner-Browser**: Es liefen zwei konkurrierende
  Popstate-Handler (`addEventListener('popstate')` und `window.onpopstate`); der
  zweite überschrieb den gerade wiederhergestellten State. Der zweite Handler
  entfällt, und `loadFromURL()` setzt den Ordnerpfad jetzt aktiv zurück, wenn die
  URL keinen `folderPath` enthält — vorher blieb beim Zurücknavigieren der alte
  Pfad stehen.

- **Light-Mode-Kontraste**: Die Views trugen noch flächendeckend Hardcodes aus
  der dark-only Zeit (`text-white`, `text-gray-400/500/600`, `bg-white/10`,
  `bg-black/40`, `rgba(255,255,255,…)` in `styles.css`), die im hellen Design
  weiß auf weiß bzw. ~2:1 landeten — am deutlichsten in den Settings. Diese
  Utilities zeigen jetzt auf mode-aware Tokens: neue Tailwind-Farbe `ink`
  (Vordergrund als Flächen-/Linienquelle) statt `*-white/N`, die Graustufen
  200–900 auf die semantische Textskala, und die semantischen Farben (HEVC,
  AV1, Bitrate, Optimized, Danger, Info) haben eigene Light-Werte mit ≥4.5:1
  auf Weiß. Gefüllte Buttons/Badges beziehen ihre Textfarbe aus `--ds-on-*`
  (automatisch schwarz/weiß nach Luminanz), Badges auf Thumbnails behalten über
  `--ds-*-media-rgb` den hellen Ton plus dunklen Scrim. `--ds-text-muted` im
  Dark-Mode von `#6b6b76` auf `#7e7e8a` angehoben (3.4:1 → 4.5:1). Der alte
  Block aus `!important`-Overrides in `styles.css` ist damit entfallen.
- `do_HEAD` split the stream path with `split("path=")`, so any appended query
  parameter ended up inside the filename. Now uses `parse_qs` like `do_GET`.

### Changed
- **Mobile-Navigation**: Neuer Eintrag **Ordner** in der Bottom-Nav, der direkt in
  den Ordner-Browser springt — der war auf dem Handy bisher gar nicht erreichbar
  (die View-Toggles sind `hidden md:flex`, nur per Deep-Link zugänglich). Dafür ist
  **Vault** aus der Bottom-Nav entfernt; der Workspace bleibt über `/vault` und den
  Desktop erreichbar.
- **Ordnerliste auf schmalen Viewports**: unterhalb von 768px kompakte Zeilen
  (56px-Thumbnail, Name, Anzahl + Größe, Chevron, ≥64px Tap-Ziel) statt der
  bildschirmfüllenden Karten mit 2×2-Mosaik — damit sind mehrere Ordner gleichzeitig
  sichtbar und Durchklicken fühlt sich wie ein Dateimanager an. Beim Wechsel über den
  Breakpoint (Rotation) wird neu gerendert; die Breadcrumb-Leiste scrollt horizontal
  und springt ans Ende des Pfads.
- **Einheitliches Design System**: Die drei Themes (Arcade/Professional/Candy)
  sind durch *ein* dark-first Theme mit genau einem Brand-Accent (Magenta
  `#c4179f`) ersetzt. Semantische Farben (HEVC-Türkis, AV1-Violett,
  Bitrate-Gold, Optimized-Grün, Danger-Rot) sind ausschließlich Badges und
  Zahlen-Readouts vorbehalten — kein Gold/Cyan/Magenta-Freistil mehr über Nav,
  Buttons und Karten hinweg. Typografie: Inter für UI, System-Mono-Stack
  (tabular-nums) für Größen, Bitraten, Pfade, Codecs und Timestamps.
  Neue Token-Ebene `--ds-*` (Flächen, Accent, Semantik, Spacing 4–48,
  Radius 4–10) in `templates/theme.py`, plus Komponentenklassen für Buttons,
  Chips, Badges und Toggles. Header, Sidebar (200 px, 3px-Accent-Indikator),
  Filterleiste, Video-Karten und Batch-Toolbar sind auf die Spec umgebaut;
  Karten-Hover ist ein ruhiger Border-Lift statt eines mehrfarbigen Glows.
  Die Theme-Auswahl in den Einstellungen und das `theme`-Setting entfallen —
  Light/Dark bleibt über den Header-Toggle erhalten.
- **Login-Screen auf dem Design System**: Der letzte Screen auf der alten
  Arcade-Palette (Pink `#DE1A58`, Gold-Hover, lila Hintergrund) nutzt jetzt
  Flächen, Accent, Radien und Typografie aus dem Token-Set, mit Accent-Dot
  und Wortmarke wie in der App-Topbar. Der animierte Starfield-Canvas ist
  entfallen. Formular, Auth-Logik und Fehlerbehandlung sind unverändert.
- **Cinema-Player, Duplicate-Checker und Settings nach Design-System-Spec**:
  Der Player hat jetzt ein Top-Overlay (Dateiname + Mono-Metadaten), eine
  rechte Action-Rail aus runden 44px-Buttons — neutral bis auf die eine
  Primäraktion (Optimize) — und eine eigene Transport-Leiste mit
  3px-Scrubber, Mono-Timestamps und hervorgehobenem Play-Button anstelle der
  nativen Video-Controls. Der Duplicate-Checker zeigt zwei gleichwertige
  Spalten mit einer fixen 120px-Entscheidungsspalte (Größendelta, Keep,
  Discard); die Empfehlung bekommt eine einzelne Accent-Kontur um die
  Vorschau statt eines flächigen Farbwashs. Das Settings-Panel nutzt die
  Sidebar-Nav-Optik (Accent-Tint + 3px-Indikator), Mono-Readout-Blöcke für
  Verzeichnislisten und 38×22-Toggle-Switches.

### Fixed
- **Kein Scroll-Sprung mehr nach dem Löschen im Grid.** Jedes Neurendern des
  Grids (Löschen, Favorit, Tag-Änderung, Filter) fiel auf einen einzigen
  40er-Batch zurück; die Seite schrumpfte und der Browser sprang nach oben.
  `renderUI()` baut jetzt so viele Batches wieder auf, wie vorher sichtbar
  waren, und stellt die Scroll-Position wieder her — außer bei explizitem
  `scrollToTop` (z. B. Workspace-Wechsel).
- **Remote-Encoding (Mac-Worker) wieder zuverlässig.** Der Worker meldet sich
  jetzt selbst neu an, wenn die Session abläuft — bisher lief er nach jedem
  Server-Neustart endlos in `401`, weil Sessions nur im RAM liegen und
  `_login()` einmalig beim Start aufgerufen wurde. Ohne `--user`/`--password`
  bricht er mit klarer Meldung ab, statt still nichts zu tun; die veralteten
  Beispiele ohne Credentials in Doku und Settings-Hinweis sind korrigiert.
- Download und Upload eines Jobs suchten die Job-ID in den *neuesten* 100
  Einträgen, während der Worker den *ältesten* Job bekommt — ab 100 Jobs in der
  Queue schlug der Download deshalb zuverlässig mit 404 fehl. Beide Endpunkte
  nutzen jetzt einen direkten Lookup per ID.
- Queue-Endpunkte lieferten Dateipfade mit kaputtem Encoding (Surrogates)
  escaped zurück, sodass Down-/Upload die Datei nicht fanden.
- Abgestürzte Worker hinterließen Jobs dauerhaft auf `downloading`/`encoding`;
  dieselbe Datei ließ sich danach nie wieder einreihen. Jobs ohne Heartbeat
  werden nach 15 Minuten neu eingereiht (nach 3 Versuchen `failed`).
- Ein Abbruch durch den Nutzer konnte von einer verspäteten Statusmeldung des
  Workers wieder überschrieben werden; `saved_bytes` wurde bei jedem
  Zwischenstatus auf 0 zurückgesetzt.
- Nach einem abgebrochenen Lauf konnte der Worker eine alte `_opt.mp4` aus dem
  Arbeitsverzeichnis als Erfolg hochladen — jeder Job bekommt jetzt ein eigenes
  Verzeichnis, und der „Datei liegt zufällig da"-Fallback ist entfernt.
- Der Upload las die komplette Datei in den RAM (mehrere GB pro Job) und wurde
  serverseitig weder auf Größe noch auf Vollständigkeit geprüft: eine
  abgebrochene Verbindung galt als fertiger Encode. Jetzt Streaming-Upload,
  Größenlimit und Integritätsprüfung (ffprobe-Dauer + strikter Decode) vor dem
  atomaren Replace.
- Im Standard-Modus (Review Mode aus) legte der Upload nur eine `_opt.mp4`
  neben das Original, ersetzte nichts und erzeugte keinen Datenbankeintrag.
  Die optimierte Datei tritt jetzt atomar an die Stelle des Originals und
  übernimmt dessen Metadaten.
- Unerreichbare Kopien der Queue-Routen in `api_handler.py` entfernt — sie
  hatten keine Auth-Prüfung und wären bei einer Änderung der
  Dispatch-Reihenfolge scharf geworden.
- Duplicate-Checker und Settings-Dialog lagen mit `z-index` unter der
  Sidebar (`z-100`) und wurden von ihr überlappt.
- Reste der alten Palette, die per Inline-Style bzw. hartkodiertem Hex an den
  CSS-Tokens vorbeiliefen: `setWorkspaceMode()` hat der Filterleiste bei jedem
  Workspace-Wechsel eine Cyan/Gold/Magenta-Border plus Farb-Tint zugewiesen und
  damit die neutrale Hairline überschrieben; dazu der aktive Datums-Chip, der
  Hover der Folder-Cards, das HEVC-Label im Treemap und der Batch-Warnhinweis.

### Added
- **Fortschrittsanzeige für Remote-Encodes.** Die Remote-Queue in den
  Einstellungen zeigt jetzt Fortschrittsbalken, aktuelle Phase, Restzeit und
  den Worker-Namen; der Poll-Takt geht auf 2 s, solange Jobs laufen, und auf
  10 s im Leerlauf. Der Worker sendet dafür alle 10 s einen Heartbeat an das
  neue `POST /api/queue/progress`, gespeist aus dem neuen optionalen
  `progress_callback` von `process_file()`. Die Prozentangabe gilt pro
  Encode-Pass — die Qualitätssuche startet den Balken mehrfach neu, deshalb
  steht die Phase daneben.
- **Duplikat-Scan findet re-encodete Videos**: Der bisherige Video-Pass gruppiert
  nach gerundeter Größe + Dauer + Auflösung. Eine transkodierte Kopie (H.264 →
  HEVC, 1080p → 720p, anderer CRF) teilt keinen dieser Werte und landete damit
  nie im selben Bucket — und der visuelle Fallback lief nur *innerhalb* eines
  Buckets, wo alle Dateien ohnehin schon identische Größe und Auflösung haben.
  Genau der häufigste echte Duplikat-Fall in einer transkodierten Bibliothek war
  also unsichtbar. Neuer zweiter Pass: Bucketing nach Dauer (±1,5 s), dann
  Vergleich perceptueller Hashes von drei Frames bei 25/50/75 % der Laufzeit.
  Gruppiert wird nur, wenn *alle* Positionen passen — ein gemeinsamer Vorspann
  reicht nicht, sonst würde eine ganze Serienstaffel zusammenfallen.
  Gruppen erscheinen als `match_type: "reencode"` mit 75 % Confidence.
  Frame-Signaturen werden in `.vframe_cache.json` gecacht; gehasht werden nur
  Videos, die überhaupt einen Dauer-Nachbarn haben. Abschaltbar über
  `find_all_duplicates(..., detect_reencodes=False)`.

### Changed
- **Redundanten visuellen Fallback im Video-Pass entfernt**:
  `_verify_by_content_sample` startete für Dateien, die es nicht über Bytes
  matchen konnte, eine eigene Ein-Frame-Prüfung. Diese Dateien sind genau die,
  die der Exact-Pass ungruppiert lässt — und die übernimmt jetzt der
  Re-Encode-Pass, mit drei Frames statt einem und mit Cache. Der Inline-Weg
  konnte also nur schwächer wiederholen, was ohnehin passiert (~50 Zeilen weg).
- **Bild-Hashing läuft parallel**: Das Dekodieren der Bilder ist die gesamte
  Kosten des ersten Duplikat-Scans, und PIL wie numpy geben dabei den GIL frei.
  Cache-Misses laufen jetzt über einen Thread-Pool (Threads = Kernzahl,
  gedeckelt bei 8). Gemessen auf 4 Kernen: 300 Bilder à 1600×1200 in 2,0 s statt
  6,2 s (3,0×), bei identischer Gruppierung. Nebenbei entfällt pro Bild ein
  `imagehash.hex_to_hash` — das Objekt wurde durch beide Vergleichsphasen
  gereicht, aber nie gelesen (verglichen wird auf `int(hash, 16)`).

### Fixed
- **Bild-Duplikate fielen aus dem Ergebnis, wenn eine Gruppe ihren Partner
  zuerst beanspruchte**: Der Near-Miss-Pass war greedy — wer einmal in einer
  Gruppe steckte, war für alle weiteren Vergleiche verbraucht. Bei A~B und A~C,
  aber B!~C, verschwand je nach Reihenfolge B oder C komplett aus dem Ergebnis
  und wurde als eindeutig gemeldet. Welches von beiden, hing an der
  Iterationsreihenfolge, dieselbe Bibliothek konnte also unterschiedliche
  Antworten liefern. Clustering läuft jetzt über Union-Find: jedes Paar
  innerhalb der Schwelle landet garantiert in derselben Gruppe. Preis dafür ist
  transitives Ketten (A~B, B~C ergibt eine Gruppe, auch wenn A!~C) — bei
  Schwelle 5 über 64 Bit braucht das einen echten Verlauf fast identischer
  Bilder, und die zusammen zu zeigen ist ohnehin die erwartete Antwort.
- **Duplikat-Scan fand keine Duplikate über Batch-Grenzen hinweg**: Die
  Bild-Batches waren echte Slices (`all_images[offset:offset+size]`), und
  verglichen wurde nur *innerhalb* eines Slices. Zwei Kopien desselben Fotos auf
  gegenüberliegenden Seiten einer Grenze — Eintrag 4999 und 5001 — wurden damit
  in keinem einzigen Batch je miteinander verglichen. Zusätzlich überschrieb
  jeder Lauf den Gruppen-Cache mit seinem eigenen Slice-Ergebnis, Batch 2 warf
  also alles weg, was Batch 1 gefunden hatte. Das Limit begrenzt jetzt nur noch,
  wie viele *neue* Hashes ein Lauf berechnet; verglichen wird immer über die
  gesamte Bibliothek. Jeder Lauf liefert damit ein vollständiges Ergebnis, das
  mit jedem weiteren Batch wächst.
- **Nicht dekodierbare Bilder wurden bei jedem Scan neu versucht**: Fehlschläge
  hinterließen keine Spur im Cache. Mit dem neuen Batch-Modell hätte das zu
  einem endlosen "weitere Batches verfügbar" geführt. Sie werden jetzt markiert
  (stat-validiert wie jeder andere Eintrag, eine reparierte Datei wird also
  wieder versucht).
- **Duplikat-Scan empfahl bei Re-Encodes die falsche Datei zum Behalten**:
  `_calculate_video_quality_score` vergibt +20 Punkte für moderne Codecs. Beim
  Abwägen zwischen byte-identischen Kopien ist das richtig, in einer
  Re-Encode-Gruppe genau falsch: die HEVC-Datei ist dort das verkleinerte
  Derivat des H.264-Originals. Der Codec-Bonus entfällt jetzt für
  `reencode`-Gruppen; Auflösung und Bitrate entscheiden.
- **Duplikat-Scan ließ temporäre Frame-Dateien liegen**: Schlug der
  ffmpeg-Aufruf in `_get_video_frame_hash` fehl oder lief in den Timeout, blieb
  die per `NamedTemporaryFile(delete=False)` angelegte Datei in `/tmp` zurück —
  über einen langen Scan mit vielen kaputten Dateien summiert sich das. Cleanup
  läuft jetzt im `finally`.
- **Duplikat-Scan: veraltete perceptual Hashes** (`.phash_cache.json`): Der Cache
  war nur nach Dateipfad indiziert, ohne jede Angabe, aus welchem Dateizustand
  der Hash stammt. Wurde ein Bild an Ort und Stelle geändert (Neu-Export,
  Rotation, Rsync über denselben Pfad), lieferte der Cache weiterhin den alten
  Hash — die Datei landete in einer Duplikatgruppe, die es nicht mehr gab, und
  genau diese Gruppen bietet die UI zum Löschen an. Cache-Einträge tragen jetzt
  `mtime_ns` + Dateigröße und werden bei Abweichung neu berechnet (Format v2).
  Alte v1-Caches werden beim ersten Laden übernommen und mit dem aktuellen
  Dateizustand gestempelt, statt eine komplette Neuberechnung zu erzwingen.
  Das Schreiben läuft jetzt über write-then-rename, damit ein Absturz mitten im
  Speichern nicht den ganzen Cache als kaputtes JSON verwirft.
- **Duplikat-Scan brach sofort ab** (`'dict' object has no attribute 'file_path'`):
  Der OOM-Fix hatte `_media_cache` von `db.get_all()` auf `db.get_all_dicts()`
  umgestellt — API-Dicts mit UI-Aliasen (`FilePath`) statt `VideoEntry`-Modellen.
  Der `DuplicateDetector` arbeitet aber durchgängig attributbasiert
  (`v.file_path`, `v.size_mb`, `media_type`), sodass der Scan-Target-Filter
  stolperte, sobald ein Benutzer Scan-Ziele gesetzt hatte. Der Duplikat-Pfad
  holt die Einträge jetzt wieder über `db.get_all()`.
  Der stille Teil war der gefährlichere: `getattr(dict, 'media_type', 'video')`
  liefert **immer** `'video'`, Bilder wären also nie als Bilder erkannt und nie
  verglichen worden — ohne Fehlermeldung. Neuer Contract-Test
  `test_duplicate_scan_entry_contract.py` hält beide Fälle fest.
- **Kandidaten-Ansicht: "URI malformed"**: Dateinamen mit ungültigen UTF-8-Bytes
  (cp1252-Reste wie `ö`, `ü`, `'`) kommen über Pythons `surrogateescape` als
  einzelne Surrogate im JSON an; `encodeURIComponent` wirft darauf `URIError`.
  Da das beim Rendern passierte, riss eine einzige Datei die komplette Ansicht
  mit. `candidates.js` übergibt jetzt den Ergebnis-Index statt des URL-kodierten
  Pfads an die onclick-Handler. Das behebt nebenbei Dateinamen mit `'`, `"` oder
  `<`, die das HTML-Attribut zerlegten — Anzeigetext und `data-path` werden
  jetzt escaped.
- **Optimize-Button (`engine.js`)**: derselbe `encodeURIComponent` steckte in der
  Kartenvorlage und hätte die Grid-Ansicht mitgerissen (bislang verdeckt, weil
  im Docker-Betrieb der `queueForRemoteEncode`-Zweig greift). Der Button ist
  jetzt in `_optimizeButton()` ausgelagert; neu in `utils.js` ist
  `safeEncodePath()`, das `URIError` abfängt und `null` liefert. Ist ein Pfad
  nicht kodierbar, wird der Button deaktiviert samt Erklärung — bewusst kein
  Reparaturversuch, da die Gegenstelle mit `unquote()` ohne
  `errors='surrogateescape'` dekodiert und den Originalpfad ohnehin nicht
  zurückgewinnen könnte.
- **Duplikat-Ansicht: gleiche Ursache**: Der Löschen-Button in `duplicates.js`
  hatte denselben `encodeURIComponent(file.path)` in der Render-Schleife.
  `deleteDuplicate()` nimmt jetzt Gruppen- und Datei-Index und löst sie sofort
  in den Pfad auf, bevor der Request läuft — sonst würde ein zweiter Klick
  während des laufenden `fetch` seinen Index gegen bereits mutierte Daten
  auflösen und die falsche Datei löschen.

### Added — Embedding Foundation (Ähnlichkeit Teil 1)
- **GPU-Indexer** (`scripts/media_indexer.py`): berechnet CLIP-Embeddings
  (Default ViT-B-16, 12 Frames pro Video, Bilder 1 Frame) und schreibt sie in
  die Haupt-DB. Inkrementell (mtime/Modell), `--watch`, `--rebuild`; eigene
  optionale Dependency-Gruppe `pip install -e ".[indexer]"` — der Server
  selbst bleibt ohne ML-Abhängigkeiten.
- **`GET /api/similar`**: nächste Nachbarn über die gespeicherten
  Mean-Vektoren (pures Python, kein NumPy), Session-pflichtig und
  Vault-gefiltert; Cache invalidiert sich bei Indexer-Läufen selbst.

### Added — Scan-Steuerung
- **Scan stoppen aus der UI** (ROADMAP-Punkt): neuer Stop-Button neben dem
  Rescan-Button, `GET /api/scan/stop` signalisiert `ScannerManager.stop()`.
  Teilergebnisse bleiben erhalten (Orphan-Cleanup wird serverseitig
  übersprungen).
- **`/api/rescan` läuft im Hintergrund**: antwortet sofort mit 202 statt den
  Request zu blockieren (Voraussetzung fürs Stoppen), `GET /api/scan/status`
  zum Pollen; das Frontend lädt nach Abschluss automatisch neu. Doppelte
  Scans werden mit 409 abgewiesen.

### Added — Auto-Tagging Rules
- **Auto-Tag-Regeln**: eine Regel = Smart-Collection-Query + Ziel-Tag. Regeln
  laufen serverseitig nach jedem Scan und auf Knopfdruck (Settings →
  Auto-Tagging). Apply-once: ein manuell entferntes Tag wird nie erneut
  vergeben. Anlegen direkt im Collection-Editor ("Als Regel").
- **Server-seitige Query-Auswertung**: Python-Port des Collection-Evaluators,
  per Node-Paritätstest gegen `collections.js` gepinnt.

### Added — Optimizer Candidates View
- **Kandidaten-Ansicht** (`/candidates`): ranks the library by expected re-encode
  savings (bitrate-per-resolution heuristic + codec efficiency), refined by real
  results from `encode_history.jsonl` once a resolution/bitrate class has ≥3
  encodes. Header shows the total possible savings; rows queue directly into the
  existing encoding queue (HEVC/AV1 toggle).
- **`optimized_at` marker**: successful optimizations now stamp the media entry;
  optimized files no longer appear as candidates (rescan-safe).

### Changed — Video Optimizer V2.5
- **Downscaling**: New `--scale-height H` option scales the encode to H pixels height while keeping the source aspect ratio (width `-2`). Upscaling is refused, the SSIM reference is scaled to match so quality checks stay valid, and the constrained-VBR ladder is adjusted to the target resolution (~pixels^0.75) so a downscale actually converts into savings.
- **Sample-Clip Pre-Search**: The quality binary search now runs on a ~24s stream-copied probe clip first, then narrows the full-encode search to predicted ±1 — typically 1-2 full passes instead of 3-4 (files ≥ 120s; `--no-presearch` to disable).
- **Encode History Seeding**: Successful encodes are logged to `encode_history.jsonl`; future runs start the search at the median winning Q for the same encoder/resolution/bitrate class.
- **HDR/10-bit Safety**: HDR and 10-bit sources are detected; VideoToolbox/NVENC/x265 encode main10 with BT.2020/PQ/HLG color passthrough, other encoders skip the file instead of mistagging it as BT.709 (previously colors washed out).
- **Two-Pass Loudnorm**: Audio loudness is measured once per file and normalized in transparent linear mode instead of pumping-prone dynamic mode (moderate/enhanced audio modes).
- **Scene-Aware SSIM Sampling**: Quality checks sample the highest-bitrate parts of the video (packet analysis) instead of fixed 25/50/75% points.
- **Output Integrity Verification**: Every optimized file must pass a duration check and a full error-strict decode before it replaces anything — truncated or corrupt encodes are discarded automatically.
- **Worker Scheduling**: `mac_worker.py` gains `--schedule "01:00-08:00"` (overnight windows supported) and `--pause-on-battery`.
- **Fixed**: `get_video_info()` never populated width/height/codec (missing `codec_type` in the ffprobe query) — now returns real stream metadata.

### Changed — HTTP Performance Overhaul (Viewing & Streaming)
- **HTTP/1.1 Keep-Alive**: The server now reuses TCP connections instead of opening a new one per request. Thumbnails, static assets, API polling, and video seeking (Range requests) no longer pay a TCP/TLS handshake each time. A safety net guarantees every response either carries a `Content-Length` or closes the connection.
- **gzip Compression**: Dashboard HTML, JS/CSS assets, and JSON API responses (`/api/videos`, settings, tags, duplicates) are gzip-compressed when the client supports it (~75-90% smaller transfers).
- **Browser Caching**: Thumbnails are cached for 7 days (`Cache-Control: public, max-age=604800`); static assets and the dashboard revalidate via `If-Modified-Since` and get cheap `304 Not Modified` answers instead of full re-downloads.
- **Zero-Copy Streaming**: Video streaming uses kernel `sendfile()` (with automatic fallback for SSL and 1 MB chunks instead of 64 KB), plus support for suffix ranges (`bytes=-N`) and correct clamping of over-long ranges.
- **Connection Hygiene**: Idle keep-alive connections time out after 60s; handler threads are daemonized so open connections never block shutdown.

## [6.8.0] - 2026-01-18

### Added
- **Visual Timeline & Scrubber**: Professional visual timeline with frame-accurate seeking and real-time thumbnail previews.
- **Trim Handles**: Visual markers for setting export start/end points.
- **GIF Export Panel**: Replaced modal with a bottom panel UI matching the optimizer workflow.
- **Production Presets**: Resolution (360p-1080p) and FPS (10-30) presets for GIF export.
- **Size Estimation**: Dynamic file size calculation for GIF exports.
- **Current Time Capture**: Buttons to set trim handles to current video time.

### Changed
- **Cinema Mode UX Overhaul**: Redesigned all action buttons with labels, larger touch targets, and backdrop blur.
- **Docker-Aware UI**: Automatically hide "Reveal in Finder" buttons when running in Docker.

## [6.7.1] - 2026-01-16

### Added
- **Fullscreen Duplicate Checker**: Dedicated interface for side-by-side duplicate resolution.
- **Duplicate Shortcuts**: `1`/`←` (Keep A), `2`/`→` (Keep B), `S`/`Space` (Skip), `A` (Auto), `ESC` (Exit).
- **Smart Recommendations**: Green border highlighting for recommended files based on quality score.
- **Progress Tracking**: Group counter (e.g., "47 / 13,771") in duplicate view.

## [6.7.0] - 2026-01-15

### Added
- **Batch Selection Mode**: Click one checkbox to enter selection mode, then click anywhere on cards to toggle.
- **Visual Feedback**: Checkmark overlay on hover and cyan highlights during selection.

### Fixed
- **List View Thumbnails**: Properly constrained thumbnail sizes (fixed full-size image bug).
- **CSS Media Queries**: Fixed desktop grid layout breakage caused by malformed queries.
- **Asset Loading**: Added missing `styles.css` link to dashboard.

## [6.6.0] - 2026-01-14

### Added
- **Binary Search Quality**: O(log n) optimization passes for faster quality targeting.
- **Early Size Abort**: Stop encoding if output exceeds 95% of original size.
- **Fallback Mode**: Use best acceptable result (SSIM >= 0.945) when strict targets fail.

### Changed
- **JS Refactoring**: Extracted `cinema.js`, `collections.js`, and `formatters.js` from `engine.js`.
- **Documentation**: Added JSDoc to major JavaScript functions.

### Fixed
- **Keep/Discard**: Fixed "Keep" button not replacing original file (import shadowing fix).

## [6.5.0] - 2026-01-14

### Added
- **Cinema Tag Display**: View and remove assigned tags directly in the cinema overlay.
- **Docker Live Reload**: Volume mount support for instant code updates in production.

### Fixed
- **Tag System**: Resolved cache-busting and validation issues during tag creation/deletion.

## [6.4.1] - 2026-01-14

### Added
- **RAW Image Support**: Support for 12 RAW formats (CR2, NEF, ARW, DNG, etc.).
- **Smart Image Collections**: Pre-defined filters for Photos, Recent Imports, and Large Files.
- **Persistent Duplicate Cache**: Scan results saved to disk to prevent redundant scans.
- **Rescan Button**: Manual duplicate analysis trigger.

### Fixed
- **Connection Leaks**: Fixed "Too many open files" error with proper SQLite connection management.

## [6.4.0] - 2026-01-14

### Added
- **Duplicate Detection**: Smart metadata + content sampling (512KB start/end) verification.
- **Setup Wizard**: ASCII-based terminal walkthrough for first-run configuration.
- **Database Maintenance**: Tools to purge orphan entries and thumbnails.

## [6.3.0] - 2026-01-12

### Added
- **Unified Media Library**: Full support for scanning and viewing images alongside videos.
- **Cinema Modal Navigation**: Use Arrow keys to navigate through library items.
- **Visual Badges**: Purple "IMG" badge for image cards.

## [6.2.0] - 2026-01-12

### Added
- **Multi-User Accounts**: Secure login with isolated targets, favorites, and tags.
- **SQLite Backend**: Replaced JSON storage for massive library performance.
- **Negative Tag Filters**: Exclude specific tags from search results.
- **Smart Collections**: Save any complex query as a sidebar shortcut.

## [6.1.0] - 2026-01-05

### Added
- **Theme Engine**: Support for multiple themes (Arcade, Professional, Candy).
- **Custom Tagging**: Batch apply custom tags to any media.
- **Search Polish**: Redesigned unified search and filter sidebar.

## [6.0.0] - 2026-01-01

### Added
- **Workspace Differentiation**: Context-aware color accents and background tints for Lobby (Cyan), Favorites (Gold), Review (Cyan), and Vault (Magenta).
- **Professional Navigation**: Enhanced sidebar with structural active states, indicator bars, and workspace-specific iconography.
- **Settings UI Redesign**: Modern, sidebar-based configuration interface inspired by modern OS design standards (Apple/Linear/Stripe).
- **State Management**: Integrated toast notifications, loading spinners, and unsaved changes tracking.
- **Video Optimizer Toggle**: UI toggle in settings to enable/disable optimization features.

### Changed
- **Filter Bar Redesign**: Dynamic workspace-sensitive border colors and background tints.
- **Responsive List View**: Improved card layouts and reduced thumbnail sizes to prevent overflow on wide screens.
- **UI Architecture**: Moved away from hybrid inline styles towards a more structured workspace theming system.

### Fixed
- **Search Logic**: Corrected input binding that caused search to fail.
- **Settings Navigation**: Fixed tab-switching logic and content visibility in the settings modal.
- **UI Overflow**: Resolved horizontal scrolling issues in the list view on high-resolution displays.
- **Refresh Button**: Added missing ID to the rescan button to restore functionality.
- **State Persistence**: Improved persistence check for Video Optimizer settings.

## [5.2.0] - 2025-12-29

### Added
- **Saved Views**: Users can now save their current search queries, filters, and sort settings as named presets.
- **Real-time Status**: The video optimizer script now notifies the running server when a file optimization completes, allowing the UI to update instantly.
- **API Endpoints**: New `/api/settings` (POST) for saving user preferences and `/api/mark_optimized` for external status updates.

### Changed
- **Refactoring**: Extracted video scanning logic from `main.py` into a new dedicated module `core/scanner.py`.
- **Optimizer**: Added `--port` argument to `video_optimizer.py` to enable server notifications.

### Fixed
- **Time Parsing**: Fixed `ValueError` in optimizer progress display when `out_time_ms` is invalid.
- **Scan Logic**: Scanner now correctly identifies optimized files regardless of the minimum size threshold.

## [5.1.1] - 2025-12-19

### Added
- **Cinema Mode Enhancements**: Full-screen video player now includes action buttons for Favorite, Vault, Locate, and Optimize.
- **Cinema Info Panel**: Technical details panel in cinema mode showing codec, bitrate, file size, and status.
- **Select All Button**: New "Select All Visible" button in batch mode to quickly select all filtered videos.
- **Cache Statistics**: Settings modal now displays cache size statistics (thumbnails, previews, and total).
- **Enhanced Treemap Gradients**: Improved visual design with gradient colors for both folder and file views.

### Changed
- **Cleaner Console Output**: Removed verbose "Purging broken media" messages, now only shows when files are actually cleaned.
- **Cinema Mode UX**: Favorite and Vault buttons now show visual feedback when already applied (reduced opacity).
- **Settings Modal Width**: Increased max-width to 800px to accommodate cache statistics.

### Fixed
- **Cinema Mode State Sync**: Favorite/Vault actions in cinema mode now properly update the grid view without requiring reload.

## [5.1.0] - 2025-12-19

### Added
- **Settings UI**: New in-app settings modal (gear icon) to configure scan paths and exclusions directly from the dashboard.
- **Default Exclusions Toggles**: Each default exclusion now shows a description and can be enabled/disabled via checkbox.
- **Hardware-Accelerated Preview Generation**: Preview clips now use GPU encoding (NVENC, VideoToolbox, QuickSync) for 5-10x faster initial scans.
- **Dynamic Worker Count**: Auto-detects GPU VRAM and sets optimal parallel workers (1 per 3GB, max 12).
- **Separate Rebuild Commands**: `--rebuild-thumbs` and `--rebuild-previews` to regenerate media independently.
- **Improved Progress Messages**: Shows "thumbnails...", "previews...", or "processed..." based on rebuild mode.

### Changed
- **Configuration**: Migrated from `local_targets.txt`/`local_excludes.txt` to unified `settings.json` format.
- **Thumbnail Generation**: Now uses letterboxing/pillarboxing to preserve aspect ratio for vertical videos.
- **Default Exclusions**: Now stored with descriptions for better UI presentation.

### Fixed
- Fixed distorted thumbnails for vertical (9:16) videos.
- Improved cache handling to preserve favorite and hidden states during rebuilds.

## [5.0.0] - 2025-12-18

### Added
- **Batch Favorites**: Select multiple videos and mark them all as favorites at once.
- **Cross-Platform Video Optimizer**: NVIDIA NVENC, Apple VideoToolbox, and software fallback support.
- **Fun Facts**: Gaming trivia displayed during optimization.

## [4.9.0] - 2025-12-18

### Added
- **UI Performance Optimization**: Implemented lazy loading and infinite scrolling for the video grid, significantly improving performance for large libraries (tested with 2200+ clips).
- **Robust Static Asset Serving**: Transitioned CSS and JavaScript from Python templates to dedicated static files (`/static/styles.css` and `/static/client.js`) with improved path resolution.
- **Auto-Port Detection**: The server now automatically finds the next available port if the default 8000 is occupied.
- **Address Reuse**: Implemented `SO_REUSEADDR` to prevent "Address already in use" errors during quick restarts.

### Changed
- Improved encoding handling for local configuration files (`local_targets.txt`, `local_excludes.txt`) using UTF-8 with BOM support.
- Updated dashboard template to use static asset links instead of inline/templated scripts and styles.
- Refactored server logic to keep the working directory at the project root for better resource management.

### Fixed
- Resolved Python syntax errors related to global variable declarations in `web_server.py`.
- Fixed asset loading issues (404 errors) by implementing more robust static file routing.
- General bug fixes and stability improvements.
