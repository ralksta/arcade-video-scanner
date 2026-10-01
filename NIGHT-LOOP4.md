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

- [ ] **Loop AF — Gleichzeitigkeit (Rest)**
      - [x] Gleichzeitige Anmeldungen: Brute-Force-Sperre ließ parallel **40 von 40**
            Versuchen durch (Grenze 5); `SessionManager` hatte gar keine Sperre
      - [x] Ähnlichkeits-Cache: Sperren seit Iteration 95 sauber. Dabei gefunden:
            Vektoren verschiedener Modelle wurden miteinander verglichen
      - [ ] „Wo noch?"-Durchgang: dasselbe check-then-act-Muster an weiteren Stellen
- [ ] **Loop AG — Grenzen: leer, eins, sehr viele**
      - [ ] Null Einträge / ein Eintrag: Routen, Statistiken, Divisionen, Oberfläche
      - [ ] Sehr viele: 100.000 Einträge (synthetisch, nur in tmp-DB)
      - [ ] Datei ohne Endung, Pfade an der Längengrenze, Sonderzeichen, Symlink-Schleifen
- [ ] **Phase 0.1 — iOS-Client zurückziehen** (siehe UMSETZUNGSPLAN.md)
- [ ] **Phase 3 — Escaping priorisiert** (Vorlage `dev-docs/frontend-escaping.md`)
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
