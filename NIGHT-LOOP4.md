# Nachtlauf 4 — `feat/nightly-loops-4`

Autonomer Nachtlauf, gestartet 2026-10-01. Branch: `feat/nightly-loops-4` (aus `dev`, `aa6cbd0`).

## Rahmen (vom User gewählt)

- **Kein Push, kein PR, kein Merge.** Nur lokale Commits auf diesem Branch.
- Scope: offene Loops AF + AG aus Nachtlauf 3, dazu aus `UMSETZUNGSPLAN.md`
  nur die zwei Phasen ohne Nutzerdaten: **0.1** (iOS-Client zurückziehen) und
  **3** (Escaping priorisiert).
- **Nicht anfassen:** Phase 0.2 (braucht Gegenlesen), 1, 2, 4, 5 (Nutzerdaten
  bzw. TV-Gerät), 6, 7 (visuelle Prüfung). `arcade_data/` wird nie beschrieben.
- Vor JEDEM Commit: `.venv/bin/pytest` grün + `.venv/bin/ruff check .` sauber.
- Conventional Commits mit Scope, ein Fund = ein Commit.
- Ein Loop endet, wenn zwei Durchgänge hintereinander nur Kosmetik oder
  Spekulation liefern — nicht nach fester Anzahl.
- Unsicherheit oder Design-Entscheidung → als **Frage an Ralf** notieren,
  nicht eigenmächtig entscheiden.

## Baseline (Start)

- `pytest`: 2353 passed, 2 xfailed
- `ruff`: All checks passed

## Reihenfolge

- [x] **Loop AF — Gleichzeitigkeit (Rest)** — ausgereizt (7 Funde)
      - [x] Gleichzeitige Anmeldungen: Brute-Force-Sperre ließ parallel **40 von 40**
            Versuchen durch (Grenze 5); `SessionManager` hatte gar keine Sperre
      - [x] Ähnlichkeits-Cache: Sperren seit Iteration 95 sauber. Dabei gefunden:
            Vektoren verschiedener Modelle wurden miteinander verglichen
      - [x] „Wo noch?": GIF-Ausgabe kollidierte, Upload ignorierte „Abbrechen",
            settings.json ohne Sperre, Vorschaubild halb ausgeliefert,
            Scanner-Singleton ohne Sperre
- [x] **Loop AG — Grenzen: leer, eins, sehr viele** — ausgereizt (5 Funde, 1 Frage)
      - [x] Null Einträge / ein Eintrag: 27 Routen × 2 Konten am echten Server, kein
            500er. Gefunden: `/api/setup/directories` (30 s), `/api/restore` offen,
            drei weitere anonyme Routen
      - [x] Sehr viele: 100.000 Einträge — kein Fehler, nur lineare Kosten (s. Journal)
      - [x] Endungen (RAW → Frage 3), Namen an der 255-Byte-Grenze (behoben),
            Symlink-Schleifen (`os.walk` folgt nicht — sicher), Apostroph → Phase 3
- [x] **Phase 0.1 — iOS-Client zurückziehen** — `ios_client/` entfernt, letzter Stand `dec7163`
- [x] **Phase 3 — Escaping priorisiert** — `jsArg()`, 13 Handler + 10 Textstellen, Vault ausgelassen
- [ ] **Abschluss:** Übergabebericht oben in `NACHTLAUF-BERICHT.md` (neuer Abschnitt
      „Nachtlauf 4"), Fragen an Ralf zuerst

## Fragen an Ralf

1. **Dateizugriff über Kontogrenzen.** `/stream`, `HEAD /stream` und
   `/api/export/gif` prüfen nur `is_path_allowed()` — liegt der Pfad in
   *irgendeinem* Scan-Ziel (`config.active_scan_targets` = Ziele **aller**
   Konten). Ein angemeldetes Konto B kann also eine Datei aus den Zielen von A
   abspielen oder als GIF exportieren, wenn es den Pfad kennt oder rät.
   `/api/videos`, `/api/similar` und `/api/candidates` filtern dagegen per
   `core/user_scope.visible_path_filter()`. Soll die Auslieferung dieselbe
   Regel bekommen? Nicht eigenmächtig geändert: Es betrifft den TV-Client, den
   Prüfmodus-Sonderfall und Phase 6 (Vorschaubilder) gleich mit.

2. **Globale Einstellungen für Nicht-Admins.** `POST /api/settings` lässt jedes
   angemeldete Konto die *globalen* Schlüssel schreiben — Scan-Schwellen,
   `proxy_root`, `review_dir` und `ffprobe_path`/`ffmpeg_path`, also welches
   Programm der Server ausführt. Nur die nutzereigenen Felder werden
   herausgezogen. Soll ein Nicht-Admin globale Schlüssel überhaupt ändern
   dürfen? Mein Vorschlag: globale Schlüssel nur für Admins, nutzereigene für
   alle — aber das ändert, was ein Nicht-Admin in den Einstellungen sieht.
   Dazu klein: `GET /api/backup` liefert settings.json auch an Nicht-Admins.
   (`/api/restore` habe ich heute Nacht geschlossen — dort war es eindeutig.)

3. **RAW-Fotos werden nie gescannt.** CHANGELOG und ROADMAP versprechen seit
   v6.4.1 „12 RAW formats (CR2, NEF, ARW, DNG, …)". Die Endungen stehen aber
   nur im `ImageInspector`, nie im Datei-Walker (`file_system.py`), der sie
   gar nicht erst weiterreicht — die Funktion hat nie gearbeitet. Unter
   `/media` liegen 810 CR2, 683 RAF, 577 DNG. Nicht eingeschaltet, weil der
   Inspector RAW über `sips` liest (nur macOS); auf diesem Linux-Server ist
   unklar, was dabei herauskommt — womöglich 2.070 Einträge ohne Vorschau.
   Einschalten (und unter Linux prüfen) oder das Versprechen aus CHANGELOG
   und ROADMAP streichen? Nebenbei: `.3gp`/`.mpg` (3 Videos hier) kennt der
   Scanner nicht, `config.ALLOWED_VIDEO_EXTENSIONS` benutzt niemand.

## Journal

<!-- Jede Iteration hängt hier einen Eintrag an: was gemacht, was gelernt, was als Nächstes. -->

- **Iteration 1 (Loop AF, die Sperre für Höfliche)** — `/api/login` prüfte
  `is_locked_out()`, dann das Passwort, und zählte erst danach mit
  `record_failure()`. Dazwischen läuft PBKDF2 mit 100.000 Runden, und `hashlib`
  gibt dabei die GIL frei. 40 gleichzeitige Versuche: **alle 40** geprüft, bei
  einer Grenze von fünf. Die Sperre hielt also nur Angreifer auf, die brav
  nacheinander raten. Jetzt zählt `begin_attempt()` atomar *vor* der Prüfung;
  ein Erfolg löscht den Zähler wie bisher, nacheinander ändert sich nichts.
  Zweiter Fund an derselben Klasse: Der `SessionManager` hatte überhaupt keine
  Sperre — zwei Anfragen mit demselben abgelaufenen Token liefen beide in
  `del` (Gegenprobe: `KeyError` → 500), und `prune_sessions()` iterierte über
  ein Dict, in das andere Threads schrieben. Nebenbei: Die Sperrmeldung im Log
  sagte „IP user:alice" — der Kontoschlüssel lief durch denselben Text.
  Nächstes: Ähnlichkeits-Cache unter parallelen Anfragen.

- **Iteration 2 (Loop AF → Ähnlichkeits-Cache, zwei Räume)** — Die Sperren des
  `SimilarityCache` sind seit dem Verklemmungs-Fix in Ordnung; die Gleichzeitig-
  keit selbst gab nichts mehr her. Gemessen (synthetisch, 10.000 × 512):
  Dekodieren beim Fehltreffer 243 ms, kNN 271 ms je Anfrage, beides reines
  Python unter der GIL. Der Cache verfällt bei *jedem* Medien-Schreibvorgang,
  nicht nur bei neuen Embeddings — während eines Scans fällt er also praktisch
  ständig. Bewusst **nicht** geändert: Die echte DB hat 0 Embeddings, der Pfad
  läuft hier gar nicht, und eine halbe Sekunde ist kein Fehler.
  Der eigentliche Fund lag beim Lesen: `for path, _model, blob` — das Modell
  wurde verworfen. `media_indexer.py --model X` indiziert Datei für Datei neu,
  während des Laufs (oder nach Ctrl-C für immer) liegen zwei Modelle im Index.
  Gleiche Dimension: plausible Zahlen aus zwei verschiedenen Räumen, der fremde
  Eintrag landete im Test auf Platz 1. Andere Dimension: `zip` schnitt ab, ein
  768er bekam Score 1.0. Jetzt nur noch Kandidaten desselben Modells.
  Nächstes: „Wo noch?" — check-then-act an weiteren Stellen.

- **Iteration 3 (Loop AF, „Wo noch?" — zwei GIFs, eine Datei)** — Die fünf
  Stellen, an denen Threads starten, durchgesehen. Scan und Duplikat-Suche sind
  seit Nachtlauf 3 mit `_claim()`/`try_begin()` geschützt. Der GIF-Export nicht
  — aber anders als gedacht: Er braucht keinen Ausschluss, sondern eindeutige
  Ausgaben. Der Name hing nur an `{basename}_{preset}_{fps}fps.gif`, und
  `VID_0001.mp4` gibt es in jedem Kamera-Ordner. Zwei Exporte, eine Datei;
  `ffmpeg -y` kürzt sie beim zweiten Start. Gegenprobe: beide Exporte zielten
  auf `/tmp/arcade_gif_exports/VID_0001_720p_15fps.gif`. Jetzt trägt der Name
  die Job-ID. Dabei aufgefallen und als **Frage an Ralf** notiert: `/stream`
  und der GIF-Export prüfen nur „liegt in irgendeinem Scan-Ziel", nicht „in
  *deinem*". Offen und klein: Fertige GIFs werden nie gelöscht — das
  Temp-Verzeichnis wächst bis zum Neustart (→ Loop AG, „sehr viele").
  Nächstes: weitere check-then-act-Stellen (Queue-Claim, Settings-Schreiben).

- **Iteration 4 (Loop AF, „Abbrechen" während des Uploads)** — Die Queue im
  Store ist sauber: Abholen per Compare-and-Swap, Einreihen unter der Sperre.
  Die Lücke lag eine Ebene höher. `/api/queue/upload` las den Job, sah seinen
  Status aber nie an. Der Worker prüft den Abbruch einmal *vor* dem Upload —
  der Upload selbst dauert bei einer großen Datei Minuten. Wer in dieser Zeit
  „Abbrechen" klickte, verlor das Original trotzdem, und der Job sprang von
  `cancelled` auf `done` zurück (`update_job_status` ohne `guard_active`).
  Gegenprobe: alle vier Fälle (cancelled/done/failed vorab, Abbruch mitten im
  Empfang) ersetzten am alten Stand das Original. Jetzt zwei Prüfungen — früh,
  um keine Gigabytes umsonst zu empfangen, und verbindlich direkt vor dem
  Ersetzen —, dazu eine Sperre je Job, weil nach einem Reclaim zwei Worker
  denselben Job hochladen können. Der Worker meldet eine 409 als `failed`
  über `/complete` mit Schutz, ein `cancelled` bleibt also stehen.
  Nächstes: Settings-Schreibpfad, dann AF abschließen.

- **Iteration 5 (Loop AF, settings.json)** — `config.save()` las die Datei,
  änderte das Dict und schrieb es zurück, ohne Sperre, über eine Zwischendatei
  mit festem Namen `settings.json.tmp`. Gegenprobe mit acht gleichzeitigen
  Speichervorgängen: **sieben meldeten Fehler** — der erste `os.replace` hatte
  die gemeinsame Zwischendatei schon weggeschoben. Mit zwei Schreibern, deren
  Ausgabe ineinanderläuft, meldete einer Fehler; ohne das Pech beim Umbenennen
  wäre ein Gemisch an die Stelle getreten, und ein unlesbares settings.json
  ersetzt der nächste Start durch Werkseinstellungen. Jetzt eine Modul-Sperre
  um Lesen-Ändern-Schreiben und `mkstemp` je Vorgang. Gelernt: Das
  Durability-Commit aus Nachtlauf 3 hat die Datei gegen *einen* schlechten
  Moment gesichert, nicht gegen *zwei gleichzeitige* — dieselbe Zeile, zwei
  verschiedene Fragen.
  Nächstes: Vorschaubilder (zwei Anfragen erzeugen dasselbe Thumbnail?), dann
  entscheiden, ob AF ausgereizt ist.

- **Iteration 6 (Loop AF, das halbe Vorschaubild)** — Unterbrochen durch einen
  Ausfall der Auto-Mode-Prüfung (mehrere Runden ohne Urteil, nichts verändert;
  danach von selbst wieder angelaufen). ffmpeg schrieb das Vorschaubild direkt
  in die ausgelieferte Datei — dasselbe Muster wie beim HTML-Dump in Nachtlauf
  3, dort gefunden und hier übersehen. Zwei Wege zum halben Bild: Neuaufbau
  eines veralteten Bildes (`-y` kürzt sofort) und Lazy-Erzeugung im Request
  (der zweite sieht „existiert"). Ausgeliefert mit `max-age=604800`: eine
  Woche im Browser. Die Gegenprobe fand einen dritten Fehler, den ich nicht
  gesucht hatte: Ein **gescheiterter** Neuaufbau zerstörte das alte, intakte
  Bild (`b''` statt `OLD`). Jetzt rendert `_render_thumbnail()` in eine
  versteckte Zwischendatei, `os.replace` erst bei Erfolg. Der Wächter für
  stumme `except`-Blöcke schlug an — Budget nicht angehoben, der Block
  protokolliert jetzt.
  Nächstes: „Wo noch?" für genau dieses Muster — `open(…, "w")` auf Dateien,
  die gleichzeitig gelesen werden. Liefert der Durchgang nichts, ist AF durch.

- **Iteration 7 (Loop AF, zwei Durchgänge, Abschluss)** — Erster Durchgang:
  alle `open(…, "w")`. Übrig waren drei. `cleanup_legacy_settings()` schreibt
  settings.json an Sperre und Zwischendatei vorbei — aber nur bei der
  einmaligen Migration einer sehr alten Installation, und **vor** dem
  Serverstart (`main.py:42` gegen `:51`). Duplikat-Cache und Scan-Zeitstempel
  sind neu berechenbar und werden nur beim Start gelesen. Alles Spekulation,
  nichts geändert. Zweiter Durchgang: modulweiter Zustand. Die
  `hw_encode_detect`-Caches sind idempotent (zwei Threads rechnen dasselbe),
  harmlos. Aber `get_scanner_manager()` war ein Lazy-Singleton ohne Sperre, und
  der Server pollt `/api/scan/status`, bevor der Scan-Thread den Manager
  holt. Zwei gleichzeitige Erstaufrufe → zwei Manager mit je eigenem
  `_claim()` → der Doppel-Scan-Schutz aus Nachtlauf 3 wirkungslos.
  Gegenprobe mit langsamem Konstruktor: 8 von 8 Threads bekamen je einen
  eigenen. Ehrlich eingeordnet: Das echte Fenster ist Mikrosekunden breit.
  Behoben, weil drei Zeilen eine Zusage absichern, auf der ein früherer Fix
  ruht. **AF geschlossen**: Der Ertrag fällt (zuletzt ein schmales Fenster und
  ein Durchgang nur mit Spekulation), die offenen Stellen sind durchgesehen.
  Nächstes: Loop AG — null Einträge, ein Eintrag.

- **Iteration 8 (Loop AG, leer — und 711.512 Dateien)** — Ein Prüfskript
  (`/tmp/claude-1000/nl4/probe_routes.py`) startet den echten Server gegen ein
  Temp-Datenverzeichnis (`CONFIG_DIR`), legt Admin und Nutzer an und fragt 27
  GET-Routen ab. Bei leerer Bibliothek: kein einziger 500er — die Divisionen
  waren in Loop D abgesichert. Aber `/api/setup/directories` lief in den
  30-s-Timeout, unabhängig von der Bibliothek: Es summiert jeden Ordner unter
  `/media` per `os.walk`, **zweimal** (Größe, dann Zahl), bei jedem Aufruf, für
  jedes Konto. Gemessen: 711.512 Dateien, 19 s allein fürs Auflisten. Dazu
  warf ein einziges gescheitertes `getsize` den ganzen Ordner aus der Liste
  (Datei während des Laufs verschwunden — der Optimierer erzeugt `.part`).
  Jetzt ein Durchlauf, `lstat` je Datei mit Fehlertoleranz, 3 s Gesamtbudget;
  danach `complete: false`, und der Assistent zeigt „≥". Gegenprobe: 3 von 4
  Tests am alten Stand rot. Der Fetch-Wächter (`.catch` binnen 30 Zeilen)
  schlug an, weil der `.catch` schon vorher genau am Rand stand — Änderung
  ohne zusätzliche Zeile statt Wächter lockern.
  Notiert für Phase 3: `toggleSetupDirectory('${dir.path}')` bricht an einem
  Apostroph im Ordnernamen. Auffällig, noch nicht geprüft: `/api/backup`
  liefert auch einem Nicht-Admin eine Sicherung.
  Nächstes: `/api/backup` für Nicht-Admins, dann ein Eintrag, dann sehr viele.

- **Iteration 9 (Loop AG → Restore ohne Anmeldung — schwerster Fund)** — Die
  Frage war harmlos: Warum bekommt ein Nicht-Admin eine Sicherung? Das
  Gegenstück, `POST /api/restore`, hatte **überhaupt keine** Prüfung. Am
  echten Server (Temp-Datenverzeichnis) belegt: eine anonyme Anfrage
  überschrieb `proxy_root` und `review_dir`; unter den Einstellungen steht
  auch `ffprobe_path`, das der Scanner ausführt. Der Rundum-Wächter
  (`test_debug_route_authorization.py`) prüft nur `api_handler.py`, nicht die
  Route-Module — dieselbe Formlücke wie bei `/stream` in Nachtlauf 3. Und
  `POST /api/settings` hatte exakt diesen Fehler schon einmal, mit Kommentar;
  die Nachbar-Route im selben Modul behielt ihn. Jetzt Sitzung **und** Admin
  (Restore ersetzt, was alle Konten betrifft; so auch Phase 5). Kein Client
  ruft die Route auf — nichts bricht. Neu als **Frage 2**: Nicht-Admins
  schreiben über `/api/settings` die globalen Schlüssel, `ffprobe_path`
  eingeschlossen.
  Nächstes: Den Rundum-Wächter auf die Route-Module ausdehnen — sonst bleibt
  die nächste solche Route genauso unsichtbar.

- **Iteration 10 (Loop AG → der Wächter, der die Route-Module sieht)** — Der
  statische Rundum-Test las nur `api_handler.py`; Restore stand woanders. Ein
  zweiter statischer Test hätte dieselbe Schwäche in anderer Form. Deshalb
  jetzt ein Test, der nach der **Antwort** fragt: `tests/anon_sweep_server.py`
  startet den echten Handler als eigenen Prozess (`CONFIG_DIR` im Temp, Port
  0) und ruft jede Route, die per Regex im Server-Code steht, anonym per GET
  und POST auf. Erlaubt: 401/403/404/405/501, alles andere nur mit
  Begründung in `OPEN_BY_DESIGN`. Erster Lauf: drei weitere Routen.
  `GET /api/settings` gab anonym den globalen Dump — gespeicherte Ansichten,
  `proxy_root`, `review_dir`, ffmpeg-Pfade; der `else`-Zweig stammt aus der
  v7-Umstellung, kein Client fragt vor der Anmeldung.
  `GET /api/duplicates/status` war öffentlich (ein Charakterisierungstest
  sagte es sogar: „reviewers should know it is public"). `POST /api/tags`
  prüfte den Rumpf vor der Sitzung (400 statt 401, ohne Schreibzugriff).
  Drei Charakterisierungstests schrieben das offene Verhalten fest — auf 401
  umgestellt, jeweils strenger als vorher. Gegenprobe für den Wächter selbst:
  Restore-Prüfung vorübergehend entfernt → `POST 200 /api/restore` gemeldet.
  Zwei Fehlversuche unterwegs: Startmeldungen auf stdout zerstörten das JSON,
  und die erste Sabotage ließ die 403-Prüfung stehen und bewies nichts.
  Nebenbei: `start_server()` bindet den Fallback-Port ohne
  `allow_reuse_address` — nach einem schnellen Neustart scheitert er an
  TIME_WAIT. Klein, nicht angefasst.
  Nächstes: ein Eintrag; dann sehr viele (100.000, synthetisch).

- **Iteration 11 (Loop AG, eins und hunderttausend)** — Ein Eintrag: 54
  Abfragen, nichts Auffälliges. 100.000 synthetische Einträge (Temp-DB,
  `bulk_upsert` in 1,7 s): alle Routen antworten richtig. Gemessen:
  `/api/videos` 2,2 s kalt / 0,9 s, `/api/candidates` **4 s bei jedem Aufruf**
  (kein Cache), Prozess-RSS 1 GB. Profil der Vorschläge: 2,3 s `db.get_all()`
  (100.000 Pydantic-Objekte je Anfrage, am Medien-Cache vorbei) und 2,4 s
  `build_candidates()`, davon 0,55 s `stat` der Verlaufsdatei **je Eintrag**
  (`median_saved_pct` → `_reload_if_stale`). Auf die echte Bibliothek
  (5.461) umgerechnet: rund 0,25 s, die `stat`-Aufrufe ~30 ms. **Bewusst nicht
  geändert** — bei realer Größe Kosmetik; steht im Bericht, falls die
  Bibliothek wächst. Probe-Skript stellt jetzt auf Port 0 um (der
  TIME_WAIT-Fallback aus Iteration 10 hatte einen Lauf abgebrochen).
  Nächstes: Dateien ohne/mit seltener Endung (`.ts` erkennt der Inspector,
  `ALLOWED_VIDEO_EXTENSIONS` nicht), lange Pfade, Sonderzeichen, Symlinks.

- **Iteration 12 (Loop AG, Endungen und die 255-Byte-Grenze — AG
  geschlossen)** — Endungen unter `/media` gezählt (nur lesend). Drei Listen
  bestimmen, was als Medium gilt; die von Walker und Inspector stimmen bei
  Videos überein, `config.ALLOWED_VIDEO_EXTENSIONS` ist tot. Der eigentliche
  Fund: RAW steht seit v6.4.1 nur im Inspector — nie gescannt, obwohl
  CHANGELOG und ROADMAP es versprechen (→ Frage 3, nicht eingeschaltet, weil
  der RAW-Pfad `sips` braucht). Symlink-Schleifen: `os.walk` folgt Links nicht.
  Längste Video-Dateinamen hier: 208 Bytes; der GIF-Name käme auf 232. Unter
  der Grenze — aber `.{stem}.job{id}.part` und die Review-Namen hängen bis zu
  ~20 Bytes an, und eine Datei mit langem Namen ließ sich nie optimieren
  (Gegenprobe: `[Errno 36] File name too long`, Job „failed" ohne Grund).
  `_fit_name()` kürzt den Stamm an einer Zeichengrenze, an allen sechs
  Stellen in `queue.py`. **AG geschlossen**: leer, eins, viele, Endungen,
  Länge und Links sind durch; der letzte Durchgang brachte nur noch den
  Grenzfall, der hier real nicht auftritt.
  Nächstes: Phase 0.1 — iOS-Client zurückziehen.

- **Iteration 13 (Phase 0.1, iOS-Client zurückgezogen)** — Nach
  ENTSCHEIDUNGEN.md, Punkt 1. Von den zwei offen gelassenen Varianten die
  „sauberere": Ordner ersatzlos weg, `dev-docs/ios-client-status.md` trägt
  oben den Rückzugsvermerk mit `git checkout dec7163 -- ios_client`
  (`dec7163` = letzter Commit, der `ios_client/` berührte). Angeglichen:
  CLAUDE.md (jetzt „Two native clients"), README, proxy-streaming.md, zwei
  Kommentare „Browser, TV, iOS", CHANGELOG (neuer Abschnitt *Removed*).
  `test_client_endpoint_contract.py`: `KNOWN_BROKEN` ist leer — die beiden
  DeoVR-Einträge rief nur der iOS-Client auf; damit verschwinden auch die
  zwei `xfailed` der Suite, ehrlich und nicht weggedrückt. Der Mechanismus
  bleibt. Stehen gelassen: historische Einträge in CHANGELOG und Berichten,
  „iOS export (UUID)" in `master_detect.py` (iPhone-Dateinamen, nicht der
  Client), `plan-path-criterion.md` (ein Plan von damals).
  Nächstes: Phase 3 — Escaping priorisiert.

- **Iteration 14 (Phase 3, Escaping nach Herkunft)** — Inventar neu erhoben
  (60 Interpolationen von Namensfeldern ohne `escapeHtml` auf der Zeile), nach
  Herkunft sortiert. Der schwerste Rest lag im Hauptraster:
  `onclick="…('${v.FilePath.replace(/'/g, …)}')"` an fünf Stellen. In Node am
  alten Ausdruck gemessen: `a" onmouseover="alert(document.cookie)" x=".mp4`
  erzeugt ein **echtes zweites Attribut** am Button, das beim Überfahren der
  Karte feuert; `Ordner\` macht den Handler zum SyntaxError (alle Knöpfe der
  Karte tot). `encodeURIComponent` lässt `'` stehen — Keep/Discard in der
  Review-Ansicht und der Optimieren-Knopf waren per `x');alert(1);//`
  injizierbar. Statt Einzelreparaturen ein Helfer, der die Schichten richtig
  ordnet: `jsArg(v) = escapeHtml(JSON.stringify(String(v)))` — erst JS, dann
  Attribut; genau die Lücke, die frontend-escaping.md für `escapeHtml` allein
  beschreibt. Test führt es echt aus: Attribut lesen wie der HTML-Parser,
  Entitäten auflösen, in Node ausführen, Original zurückbekommen — für `"`,
  `'`, `\`, Zeilenumbruch und U+2028. Text-Kontexte: Dateinamen in der
  Befehlspalette, Treemap, Assistent; `showToast()` maskiert jetzt selbst
  (kein Aufrufer übergibt Markup, mehrere übergeben Dateinamen). Vault-Stellen
  ausgelassen (Phase 1 löscht sie). **Ohne Browser nicht visuell geprüft** —
  die Umstellung ändert keine Darstellung, nur die Maskierung, aber das steht
  so im Bericht.
  Nächstes: Übergabebericht.
