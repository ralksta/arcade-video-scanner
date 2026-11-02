# Aufgabenliste: Offene Ideen vom 2026-10-24

Legende: `[ ]` offen, `[x]` erledigt. Reihenfolge und Abhängigkeiten stehen in
`tasks/plan.md`. Jede Aufgabe endet mit einer Prüfung; ein Checkpoint wird erst
abgehakt, wenn alle Punkte darüber grün sind.

## Stand 2026-10-24

- **Task 1 abgeschlossen.** 2643 Tests grün, `ruff` sauber, Backup
  `arcade_data/users.db.bak-20261024` (integrity_check ok), Container healthy
  auf 7.0.0.
- **Tasks 2–4 auf Datenebene abgeschlossen.** Die Definitionen und Regeln
  wurden über den Projekt-eigenen `update_user()`-Weg angelegt und mit
  `run_auto_tag_rules()` angewendet (einmaliges Skript
  `/tmp/arcade_origin_tags.py`, nicht im Repo).
- Ergebnis: 140 + 39 Pfade, Überschneidung 0, Treffer außerhalb von
  ProSessions 0, `web` außerhalb der fünf Web-Ordner 0.
- **Nachtrag Umbenennung:** Die Tags heißen jetzt `OD-Pro-Web` (Amber
  `#F4B342`) und `OD-Pro-Self` (Pink `#ec4899`). Definitionen, alle 179
  Pfad-Tags und beide Regeln wurden gemeinsam umbenannt; alte Namen kommen
  nicht mehr vor (`/tmp/arcade_rename_origin_tags.py`).
- **Browser-Sichtprüfung bestanden** (Nutzer, 2026-10-24): Karten und
  Tag-Filter zeigen die neuen Namen.
- **Papierkorb-Test bestanden** (Nutzer, 2026-10-24): Löschen, Eintrag im
  Papierkorb, Zurückholen mit erhaltenem Favoriten/Tag/Fortschritt und
  endgültiges Leeren waren erfolgreich. Die 30-Tage-Ablauf-Simulation
  (Task 10) ist noch offen.
- **Zusatzwunsch Sortierung (2026-10-24):** Das Web-Dropdown bietet jetzt
  Name A–Z/Z–A, Bitrate, Größe, Laufzeit und Datum jeweils in beide
  Richtungen. Alte Sortierwerte bleiben gültig. Implementiert in
  `components.py` und `filter_engine.js`, abgesichert in
  `tests/test_date_sorting.py`; Dashboard-Dump neu erzeugt.
- **Zusatzwunsch Kachel-Infos (2026-10-24):** Eine leise Zeile unter dem
  Titel zeigt Größe und Bitrate, die Länge bleibt das Badge auf dem Bild.
  In „Details“ und den Werkstatt-Ansichten wird die Zeile ausgeblendet.
  Implementiert in `formatters.js`/`engine.js`/`styles.css`, abgesichert in
  `tests/test_card_meta_line.py`.
- **Zusatzwunsch Papierkorb-Dialog (2026-10-24):** Löschen und endgültiges
  Leeren fragen nicht mehr mit `window.confirm()`, sondern mit einem Dialog
  im Design-System (`confirm_dialog.js` + `CONFIRM_DIALOG_COMPONENT`).
  Dateinamen stehen als Liste darin, „Abbrechen“ ist vorausgewählt,
  Escape/Hintergrund schließen, der Fokus ist eingesperrt.
- **Release 7.1.0 geschnitten und deployed (2026-10-24):**
  `06cf035 feat(web): Sortierung, Kachel-Infos und Papierkorb-Dialog`,
  `1487df3 chore(release): 7.1.0`. Container meldet 7.1.0, HTTP ok.
  **Offen:** PR `dev` → `main` (siehe Release-Split unten).
- **Release-Split (2026-10-24):** `origin/main` stand bereits auf `7f0234e`
  (8. August), nicht auf 6.0.0. Daher nur 234 Commits, aufgeteilt in vier
  gestapelte PRs. **PR 1–4 (#52–#55) gemergt**; `dev` = `main` = `289dc89`.
  CI-Typecheck bleibt rot wegen vorbestehender mypy-2.4-Fehler (separates
  Follow-up nötig); Ruff ist an allen Schnitten sauber.
- **Mypy-Fix (2026-10-24):** Elf Typfehler in sechs Dateien behoben
  (`f0754f4`), dazu `test_asset_versioning` unabhängig von Checkout-mtimes
  gemacht (`593dd88`). `mypy 2.4.0`, `ruff` und die volle Suite (2659 Tests)
  sind grün; CI auf PR #56 grün, **PR #56 gemergt**. `dev` = `main` =
  `da15f5a`.
- **TV-Sichtprüfung verschoben auf 2026-11-14.** Grund: Das ausgelieferte
  `com.arcade.scanner.tv_1.0.0_all.ipk` ist vom 2026-07-05 und enthält keine
  Tag-Oberfläche; die Quellen haben sie seit 2026-10-02. Vor dem Test muss die
  App neu gebaut und installiert werden (siehe Task 21).
- **Offen:** Nur noch der TV-Teil von Task 5 (verschoben auf 2026-11-14).


- **RAW-Scan (2026-10-24):** Tasks 15–19 umgesetzt (Helfer, `scan_raw`, gemeinsame Endungsliste, Inspector/Thumbnails, End-to-End-Test). Echt getestet: `admin.scan_raw=true`, **66 RAW** (3 CR2, 37 DNG, 26 RAF) mit 480×270-Vorschau, **0 JPG/PNG**, 73,08 s, keine Tracebacks. Die 2.070 aus der Doku liegen im nicht gemounteten Host-`/media` (2.184); im Container sind es 68, davon 2 AppleDouble-`._`-Reste (bewusst übersprungen).
- **Release 7.2.0 (2026-10-24):** Release-Commit `e900c62`, PR #57 gemergt
  (`dev` = `main` = `d8bae10`), CI grün, Container meldet 7.2.0.

---

## Phase 0 — Baseline

## Task 1: Baseline und Sicherung

**Beschreibung:** Vor allen Änderungen den Ist-Zustand festhalten: Testsuite
und Lint laufen lassen, die Kontendaten sichern, den laufenden Container und
seine Version notieren. Das Backup ist die Versicherung für die
Auto-Tag-Regeln, deren Tags nach dem Lauf nur noch einzeln entfernbar sind.

**Akzeptanzkriterien:**
- [x] Die vollständige Testsuite läuft durch; bekannte Ausfälle sind notiert.
- [x] `ruff check .` meldet nichts.
- [x] `arcade_data/users.db.bak-20261024` existiert und lässt sich öffnen.
- [x] Container `arcade-media-scanner` läuft und meldet Version 7.0.0.

**Verifikation:**
- [x] `.venv/bin/pytest` — 2643 passed
- [x] `.venv/bin/ruff check .` — All checks passed
- [x] `sqlite3 arcade_data/users.db ".backup 'arcade_data/users.db.bak-20261024'"`
- [x] `sqlite3 'file:arcade_data/users.db.bak-20261024?mode=ro' "PRAGMA integrity_check;"` — ok
- [x] `docker logs --tail 20 arcade-media-scanner` — healthy, 7.0.0

**Abhängigkeiten:** Keine

**Voraussichtlich berührte Dateien:**
- keine (nur Laufzeitdaten)

**Geschätzter Umfang:** S

---

## Phase 1 — Herkunft als Tag

## Task 2: Tag-Definitionen `web` und `eigene` anlegen

**Beschreibung:** Im Tag-Manager (Filterleiste → Tags → *Manage*) zwei Tags
anlegen, **bevor** eine Regel läuft: `web` in Amber `#F4B342`, `eigene` in Pink
`#ec4899`. Namen klein schreiben, damit sie exakt zu den Regel-Tags passen.
Der Auto-Tagger übernimmt vorhandene Definitionen unverändert; legt er sie
selbst an, bekommen beide dasselbe Grün, und die UI kann die Farbe später
nicht mehr ändern.

**Akzeptanzkriterien:**
- [x] `available_tags` enthält `web` mit `#F4B342` und `eigene` mit `#ec4899`.
- [ ] Beide Tags erscheinen im Tag-Manager mit der richtigen Farbe
      (Sichtprüfung im Browser offen).
- [x] Zum Zeitpunkt der Anlage gab es noch keine Auto-Tag-Regel.

**Verifikation:**
- [ ] Manuell: Filterleiste → Tags → *Manage*, beide Einträge prüfen.
- [x] `sqlite3 'file:arcade_data/users.db?mode=ro' "SELECT json_extract(user_data,'$.available_tags') FROM users WHERE username='admin';"`
- [x] `sqlite3 'file:arcade_data/users.db?mode=ro' "SELECT json_extract(user_data,'$.auto_tag_rules') FROM users WHERE username='admin';"`

**Ausführung:** Über `/tmp/arcade_origin_tags.py` mit `user_db.update_user()`
angelegt, weil ohne Anmeldung kein UI-Zugriff möglich war. Die Definitionen
wurden vor dem Regel-Lauf geschrieben; die Farben stehen in der DB.

**Abhängigkeiten:** Task 1

**Voraussichtlich berührte Dateien:**
- keine (Kontendaten in `arcade_data/users.db`)

**Geschätzter Umfang:** XS

## Task 3: Auto-Tag-Regeln aus den beiden Collections anlegen

**Beschreibung:** Im Collection-Editor die Sammlung `ProSessions – Web`
öffnen, unten im Fuß `web` in das Feld „auto-tag…“ tippen und **Als Regel**
klicken. Dasselbe mit `ProSessions – Eigene` und `eigene`. Die Regel übernimmt
den aktuellen Suchtext der Sammlung; die Sammlung selbst wird dabei nicht
verändert. Für `web` ist das die exakte ODER-Liste der fünf Web-Ordner, für
`eigene` der Pfadfilter mit `-*/web*`.

**Akzeptanzkriterien:**
- [x] Zwei Regeln sind vorhanden, beide aktiviert, Tags `web` und `eigene`.
- [x] Die `web`-Regel enthält die fünf Pfade:
      `Miss Blossom/web`, `Lady Jessica/web`, `Lady Jenna/Web`,
      `lady asmondena/web`, `Lena/web_videos`.
- [x] Die `eigene`-Regel enthält `"/media_ralf/OD/ProSessions" -"*/web*"`.
- [x] Die Trefferzahlen der Sammlungen stehen weiterhin bei 140 und 39
      (Vorabzählung mit derselben Engine: 140/39).

**Verifikation:**
- [ ] Einstellungen → Auto-Tagging: beide Regeln in der Liste
      (Sichtprüfung im Browser offen).
- [x] `sqlite3 'file:arcade_data/users.db?mode=ro' "SELECT json_extract(user_data,'$.auto_tag_rules') FROM users WHERE username='admin';"`
- [ ] Manuell: Sammlungen `ProSessions – Web` und `ProSessions – Eigene` öffnen und die Trefferzahl ablesen.

**Ausführung:** Die Kriterien wurden direkt aus den beiden vorhandenen
Collections kopiert, nicht neu getippt. Regel-IDs:
`web` = `36f1d0a4b8324553a85f7b6f220e59ce`,
`eigene` = `afd0f45dbd2749f8ba09ae717ec736f4`.

**Abhängigkeiten:** Task 2

**Voraussichtlich berührte Dateien:**
- keine (Kontendaten in `arcade_data/users.db`)

**Geschätzter Umfang:** S

## Task 4: Regeln einmal ausführen und Treffer prüfen

**Beschreibung:** Einstellungen → Auto-Tagging → **Jetzt ausführen**. Erwartet
werden 179 neue Tags (140 `web` + 39 `eigene`). Danach stichprobenartig prüfen,
dass nur Dateien unter `/media_ralf/OD/ProSessions` getroffen wurden und dass
`web` ausschließlich unter den fünf Web-Ordnern liegt. Der Lauf vergibt jeden
Tag je Pfad nur einmal; bei einem Fehlgriff nicht einfach erneut ausführen.

**Akzeptanzkriterien:**
- [x] Der Lauf meldet insgesamt 179 vergebene Tags (140 + 39).
- [x] `web` hat 140 Pfade, `eigene` hat 39 Pfade (Datenebene).
- [x] Keine Datei außerhalb von `/media_ralf/OD/ProSessions` trägt einen der
      beiden Tags (0 Treffer außerhalb).
- [x] Keine Überschneidung: Web-Dateien tragen `web`, aber nicht `eigene`
      (0 gemeinsame Pfade).
- [ ] Die Tags erscheinen in den vereinbarten Farben auf den Karten
      (Sichtprüfung im Browser offen).

**Verifikation:**
- [ ] Manuell: Toast nach „Jetzt ausführen“ und die beiden Suchen `#web` /
      `#eigene` (Sichtprüfung offen).
- [x] Stichprobe außerhalb von ProSessions: Skript hat alle 5.465 Pfade
      geprüft, 0 Treffer außerhalb.
- [x] `sqlite3 'file:arcade_data/users.db?mode=ro' "SELECT json_extract(user_data,'$.tags') FROM users WHERE username='admin';"`

**Ausführung:** `run_auto_tag_rules()` lieferte
`web: 140`, `eigene: 39`, Summe 179. Die 5.465 Bibliothekseinträge wurden
zusätzlich auf Pfade außerhalb ProSessions und auf die fünf Web-Ordner geprüft:
jeweils 0 Abweichungen.

**Abhängigkeiten:** Task 3

**Voraussichtlich berührte Dateien:**
- keine (Kontendaten in `arcade_data/users.db`)

**Geschätzter Umfang:** S

## Task 5: Sichtbarkeit auf Karten, im Filter und auf dem Fernseher prüfen

**Beschreibung:** Die Trennung soll überall sichtbar sein, nicht nur in der
Sidebar. Karten zeigen bis zu drei Tag-Chips, der Tag-Filter der Filterleiste
filtert positiv und negativ, und der TV-Client zeigt Tags in der Detailansicht
sowie als Filter. Der TV muss mit demselben Konto (`admin`) angemeldet sein,
sonst sind die Tags dort erwartungsgemäß nicht vorhanden.

**Akzeptanzkriterien:**
- [x] Karten zeigen `OD-Pro-Web` in Amber und `OD-Pro-Self` in Pink.
- [x] Der Tag-Filter listet beide Tags und filtert positiv wie negativ korrekt.
- [ ] Auf dem TV listet der Tag-Filter beide Tags; die Detailansicht zeigt sie
      bei einer Stichprobe — **verschoben auf 2026-11-14**, vorher neues IPK
      bauen (Task 21).
- [x] Der TV nutzt das Konto `admin`; andere Konten sind laut Review
      ausdrücklich außen vor (dort gibt es die Tags nicht).

**Verifikation:**
- [x] Manuell im Browser: Bibliothek, Filter-Chips, Suche `#OD-Pro-Web` /
      `#OD-Pro-Self` (Nutzer, 2026-10-24).
- [ ] Manuell auf dem TV: Tag-Filter und Detailansicht einer ProSessions-Datei
      (verschoben).

**Befund zum TV:** Das installierte IPK vom 2026-07-05 enthält weder
`tagOptions` noch die Tag-Anzeige; die Quellen enthalten beides seit
2026-10-02. Es ist kein Kontoproblem — die aktiven Sitzungen gehören alle zu
`admin`.

**Abhängigkeiten:** Task 4

**Voraussichtlich berührte Dateien:**
- keine

**Geschätzter Umfang:** S

---

## Checkpoint 1 — Herkunfts-Tags

- [x] 39 `OD-Pro-Self`, 140 `OD-Pro-Web`, kein Treffer außerhalb von ProSessions
- [x] Browser: Karten und Filter zeigen beide Tags mit den vereinbarten Farben
- [ ] TV: verschoben auf 2026-11-14 (neues IPK nötig, Task 21) — blockiert
      Phase 2/3 nicht
- [x] Review mit dem Nutzer (Namen und Farben am 2026-10-24 bestätigt)

---

## Phase 2 — Papierkorb einmal echt testen

## Task 6: Testdatei vorbereiten und Zustand festhalten

**Beschreibung:** Aus den Duplikaten eine entbehrliche Datei auswählen, deren
zweite Kopie in der Bibliothek bleibt. Zusätzlich eine Sicherheitskopie
außerhalb der Bibliothek anlegen. Auf der Testdatei Favorit setzen, den Tag
`trash-test` vergeben und den Wiedergabefortschritt auf etwa 30 Sekunden
stellen. Pfad, Dateigröße und die zweite Kopie notieren.

**Akzeptanzkriterien:**
- [x] Genau eine Testdatei ist ausgewählt; ihr Pfad ist notiert.
- [x] Favorit, Tag `trash-test` und Fortschritt sind gesetzt und sichtbar.
- [x] Eine Sicherheitskopie liegt außerhalb der Scan-Ziele.
- [x] Mindestens eine weitere Kopie desselben Inhalts bleibt in der Bibliothek.
- [x] Der Pfad liegt in einem Scan-Ziel (nicht im zentralen Fallback-Korb).

**Verifikation:**
- [x] Manuell: Favoritenansicht, Tag-Filter `trash-test`, Fortschrittsbalken.
- [x] `ls -l '<pfad>' '<sicherheitskopie>'` (einzeln, mit den notierten Pfaden)

**Ausführung:** Vom Nutzer am 2026-10-24 durchgeführt und bestätigt.

**Abhängigkeiten:** Task 1 (Phase 2 kann parallel zu Phase 1 laufen)

**Voraussichtlich berührte Dateien:**
- keine

**Geschätzter Umfang:** S

## Task 7: Löschen und Papierkorb-Eintrag prüfen

**Beschreibung:** Die Testdatei in der Duplikate-Ansicht ausdrücklich löschen
(nicht die andere Kopie). Danach prüfen: Datei ist vom Originalpfad
verschwunden, Eintrag steht in Einstellungen → Storage → Papierkorb mit Name,
Ordner, Größe, Löschdatum und Restlaufzeit, das Vorschaubild ist noch da, und
der Bibliothekseintrag ist nach dem Aktualisieren weg.

**Akzeptanzkriterien:**
- [x] Die Datei ist am Originalpfad nicht mehr vorhanden.
- [x] Der Papierkorb zeigt genau einen Eintrag mit den erwarteten Angaben.
- [x] Das Vorschaubild existiert weiterhin im Cache.
- [x] Der Bibliothekseintrag ist nach dem Aktualisieren verschwunden.
- [x] Der Eintrag im Papierkorb-Index nennt den richtigen `original_path`.

**Verifikation:**
- [x] Manuell: Duplikate-Ansicht, Einstellungen → Storage → Papierkorb.
- [x] `ls -l '<originalpfad>'` (muss fehlschlagen)
- [x] `docker exec arcade-media-scanner ls -l /cache/thumbnails | grep '<thumb-name>'`

**Ausführung:** Vom Nutzer am 2026-10-24 durchgeführt und bestätigt.

**Abhängigkeiten:** Task 6

**Voraussichtlich berührte Dateien:**
- keine

**Geschätzter Umfang:** S

## Task 8: Zurückholen und Zustand prüfen

**Beschreibung:** Im Papierkorb **Zurückholen** klicken. Die Datei muss wieder
am exakten Originalpfad liegen; Favorit, Tag `trash-test` und der
Wiedergabefortschritt müssen erhalten sein. Der Papierkorb ist danach leer,
das Vorschaubild ist noch da, und der Bibliothekseintrag erscheint nach einem
Aktualisieren wieder.

**Akzeptanzkriterien:**
- [x] Datei liegt wieder am exakten Originalpfad (gleiche Größe).
- [x] Favorit, Tag und Fortschritt sind unverändert vorhanden.
- [x] Der Papierkorb-Eintrag ist verschwunden.
- [x] Das Vorschaubild ist vorhanden.
- [x] Der Eintrag ist nach Aktualisieren/Rescan wieder in der Bibliothek.

**Verifikation:**
- [x] Manuell: Papierkorb, Favoritenansicht, Tag-Filter, Fortschrittsbalken.
- [x] `ls -l '<originalpfad>'`
- [x] Manuell: Datei im Player öffnen und prüfen, dass er bei ~30 s fortsetzt.

**Ausführung:** Vom Nutzer am 2026-10-24 durchgeführt und bestätigt.

**Abhängigkeiten:** Task 7

**Voraussichtlich berührte Dateien:**
- keine

**Geschätzter Umfang:** S

## Task 9: Endgültig leeren und Aufräumen prüfen

**Beschreibung:** Die Testdatei erneut löschen und den Papierkorb endgültig
leeren. Prüfen, dass Datei und Vorschaubild verschwinden, der Papierkorb leer
ist und keine verwaisten Favoriten-/Tag-/Fortschrittseinträge bleiben. Nach
einem Rescan darf kein Geistereintrag auftauchen. Die Sicherheitskopie bleibt
bis zum Abschluss des Checkpoints liegen.

**Akzeptanzkriterien:**
- [x] Datei und Vorschaubild sind endgültig weg.
- [x] Der Papierkorb ist leer.
- [x] Favorit, Tag `trash-test` und Fortschritt sind aus den Kontendaten weg.
- [x] Nach einem Rescan gibt es keinen Eintrag und kein Vorschaubild mehr.
- [x] Die Sicherheitskopie ist noch vorhanden (bis Checkpoint 2).

**Verifikation:**
- [x] Manuell: Papierkorb, Favoritenansicht, Tag-Filter, Fortschritt.
- [x] `ls -l '<originalpfad>'` (muss fehlschlagen)
- [x] Manuell: Rescan anstoßen und Bibliothek aktualisieren.

**Ausführung:** Vom Nutzer am 2026-10-24 durchgeführt und bestätigt.

**Abhängigkeiten:** Task 8

**Voraussichtlich berührte Dateien:**
- keine

**Geschätzter Umfang:** S

## Task 10: 30-Tage-Ablauf über einen Neustart prüfen

**Status: bewusst übersprungen** (Nutzer, 2026-10-24). Die Ablauf-Logik ist
durch `tests/test_trash.py` abgedeckt (`test_purge_expired_removes_old_entries_only`,
`test_fresh_entries_survive_the_retention_check`); der echte Neustart-Test
entfällt.

**Beschreibung:** Einen zweiten kleinen Papierkorb-Eintrag erzeugen. Container
stoppen, `arcade_data/trash_index.json` sichern und beim Test-Eintrag
`deleted_at` auf 31 Tage in der Vergangenheit setzen. Container starten; der
Server räumt den abgelaufenen Eintrag beim Start auf und schreibt eine
Logzeile. Ein frischer Eintrag darf nicht mit aufgeräumt werden.

**Akzeptanzkriterien:**
- [ ] Die Logzeile `🗑️ Papierkorb: 1 abgelaufene Datei(en) ... entfernt`
      erscheint beim Start.
- [ ] Die abgelaufene Datei, ihr Vorschaubild und der Index-Eintrag sind weg.
- [ ] Ein frischer Papierkorb-Eintrag bleibt erhalten.
- [ ] Der Index ist nach dem Eingriff wieder gültiges JSON.

**Verifikation:**
- [ ] `docker stop arcade-media-scanner`
- [ ] `cp arcade_data/trash_index.json arcade_data/trash_index.json.bak`
- [ ] Manuell: nur den Test-Eintrag in `arcade_data/trash_index.json` ändern.
- [ ] `docker start arcade-media-scanner`
- [ ] `docker logs --since 5m arcade-media-scanner 2>&1 | grep Papierkorb`
- [ ] Manuell: Einstellungen → Storage → Papierkorb.

**Abhängigkeiten:** Task 9

**Voraussichtlich berührte Dateien:**
- keine (Laufzeitdaten)

**Geschätzter Umfang:** S

---

## Checkpoint 2 — Papierkorb

- [x] Löschen, Papierkorb-Eintrag, Zurückholen mit Zustand und endgültiges
      Leeren sind bestanden (Nutzer, 2026-10-24)
- [x] Keine Fehler aufgetreten; keine Regressionstests nötig
- [x] 30-Tage-Ablauf (Task 10) bewusst übersprungen; durch Unit-Tests
      abgedeckt (`test_trash.py`)
- [x] Sicherheitskopie kann jetzt gelöscht werden
- [x] Review mit dem Nutzer; Phase 3 freigegeben

---

## Phase 3 — Release 7.1.0

## Task 11: CHANGELOG und Versionsbump

**Beschreibung:** Den Inhalt von `## [Unreleased]` unter
`## [7.1.0] - 2026-10-24` verschieben und `Unreleased` leer lassen. Zusätzlich
eine nachgeholte Sektion `## [7.0.0] - 2026-03-17` mit den README-Highlights
(AV1-Encoding, Smart SSIM Skip) anlegen. `arcade_scanner/__version__` auf
`7.1.0` setzen und die README-Überschrift mitziehen.

**Akzeptanzkriterien:**
- [x] `CHANGELOG.md` hat `[7.1.0] - 2026-10-24` und `[7.0.0] - 2026-03-17`.
- [x] `[Unreleased]` ist leer (nur die Überschrift).
- [x] `arcade_scanner/__init__.py` enthält `__version__ = "7.1.0"`.
- [x] Die README-Überschrift lautet `# Arcade Media Scanner 7.1.0`.
- [x] Der Versionstest ist grün.

**Verifikation:**
- [x] `.venv/bin/pytest tests/test_version_consistency.py`
- [x] `rg -n "^## \[(Unreleased|7\.0\.0|7\.1\.0)\]" CHANGELOG.md`
- [x] `head -1 README.md`

**Abhängigkeiten:** Checkpoint 2

**Voraussichtlich berührte Dateien:**
- `CHANGELOG.md`
- `arcade_scanner/__init__.py`
- `README.md`

**Geschätzter Umfang:** S

## Task 12: Vollständige Prüfung und Commit auf `dev`

**Beschreibung:** Vor dem Release-Commit die gesamte Suite und den Lint laufen
lassen. Danach genau die drei Release-Dateien committen, mit
`chore(release): 7.1.0`. Keine unfertigen RAW-Änderungen mitnehmen.

**Akzeptanzkriterien:**
- [x] `ruff check .` ist sauber.
- [x] Die vollständige Testsuite ist grün.
- [x] `git diff --check` meldet nichts.
- [x] Der Commit enthält nur `CHANGELOG.md`, `README.md`,
      `arcade_scanner/__init__.py` (und ggf. die Aufgabenliste).
- [x] Commit-Nachricht: `chore(release): 7.1.0`.

**Verifikation:**
- [x] `.venv/bin/ruff check .`
- [x] `.venv/bin/pytest` — 2659 passed
- [x] `git diff --check`
- [x] `git show --stat HEAD`

**Abhängigkeiten:** Task 11

**Voraussichtlich berührte Dateien:**
- keine über Task 11 hinaus

**Geschätzter Umfang:** S

## Task 13: PR von `dev` nach `main`

**Beschreibung:** Prüfen, dass `dev` nur die beabsichtigten Release-Commits
vor `main` hat, dann den PR anlegen. Der PR-Text nennt Papierkorb,
Suchsprache/Vorschläge und Collection-Dialog als Inhalt von 7.1.0.

**Akzeptanzkriterien:**
- [ ] `git log --oneline main..dev` enthält keine fremden Commits.
- [ ] Der PR ist gegen `main` gerichtet und beschreibt 7.1.0.
- [ ] Alle Checks sind grün.
- [ ] Der PR wird nicht ohne Review gemergt.

**Verifikation:**
- [ ] `git log --oneline main..dev`
- [ ] `gh pr create --base main --head dev --fill`
- [ ] `gh pr checks --watch`

**Ausführung 2026-10-24:** Der echte `origin/main` stand auf `7f0234e`
(8. August), also 234 Commits hinter `dev` — nicht 570. Aufgeteilt in vier
gestapelte PRs: #52 (Performance), #53 (Sicherheit), #54 (TV/Clients),
#55 (Web/7.1.0). Alle vier gemergt; `dev` = `main` = `289dc89`.

**Abhängigkeiten:** Task 12

**Voraussichtlich berührte Dateien:**
- keine

**Geschätzter Umfang:** S

## Task 14: Deployment und Smoke-Test

**Beschreibung:** Der Compose-Stack bind-mountet `.:/app`; ein Neustart des
Containers genügt, ein Rebuild ist nicht nötig. Nach dem Neustart Version,
Dashboard, Anmeldung und Papierkorb prüfen und die Logs auf Tracebacks
durchsehen.

**Akzeptanzkriterien:**
- [x] Der Container ist gesund.
- [x] Das Log zeigt `--- Arcade Media Scanner 7.1.0 ---`.
- [ ] Dashboard lädt, Anmeldung funktioniert, Papierkorb lädt
      (HTTP ok; Sichtprüfung nach Reload offen).
- [x] Keine neuen Tracebacks im Log.
- [x] Die bestehenden Herkunfts-Tags sind in den Kontendaten weiterhin da.

**Verifikation:**
- [x] `docker restart arcade-media-scanner`
- [x] `docker logs --tail 40 arcade-media-scanner`
- [x] `curl -fsS http://localhost:8000/ > /dev/null`
- [ ] Manuell: Anmeldung, Bibliothek, Einstellungen → Storage → Papierkorb.

**Abhängigkeiten:** Task 13 (nach dem Merge)

**Voraussichtlich berührte Dateien:**
- keine

**Geschätzter Umfang:** S

---

## Checkpoint 3 — Release

- [x] Version 7.1.0 in Log, README und CHANGELOG
- [x] Container gesund, HTTP ok
- [ ] Dashboard und Papierkorb nach Reload manuell prüfen
- [ ] PR `dev` → `main` (570 Commits; Aufteilung entscheiden)
- [x] Review mit dem Nutzer; Phase 4 ist freigegeben

---

## Phase 4 — RAW-Scan

## Task 15: Pillow-Helfer für eingebettete RAW-Vorschauen

**Beschreibung:** Ein neues Modul `arcade_scanner/core/raw_preview.py` liest die
in jeder RAW-Datei eingebettete JPEG-Vorschau, ausschließlich mit Pillow. Reihenfolge:
zuerst `Image.open()` (CR2/DNG, TIFF-basiert), dann der RAF-Kopf (Offset/Länge
bei Byte 84–91, Big-Endian), zuletzt die Suche nach dem größten eingebetteten
JPEG (SOI … EOI). Vor der Rückgabe `ImageOps.exif_transpose` anwenden. Die
Tests erzeugen synthetische Dateien; echte Fotos kommen nicht ins Repo.

**Akzeptanzkriterien:**
- [ ] `open_raw_preview(path)` liefert ein PIL-Bild für TIFF-basierte RAW,
      für den RAF-Kopf und für ein generisch eingebettetes JPEG.
- [ ] Die DNG-Ausrichtung wird über `exif_transpose` korrigiert.
- [ ] Kaputte oder preview-lose Dateien liefern `None`, ohne Ausnahme.
- [ ] Es gibt keine neue Laufzeitabhängigkeit.
- [ ] Nur synthetische Testdateien, keine echten Fotos.

**Verifikation:**
- [ ] `.venv/bin/pytest tests/test_raw_preview.py`
- [ ] `.venv/bin/ruff check arcade_scanner/core/raw_preview.py tests/test_raw_preview.py`

**Abhängigkeiten:** Task 1 (parallel zu Task 16 möglich)

**Voraussichtlich berührte Dateien:**
- `arcade_scanner/core/raw_preview.py` (neu)
- `tests/test_raw_preview.py` (neu)

**Geschätzter Umfang:** S

## Task 16: Einstellung „RAW-Fotos scannen“ (`scan_raw`)

**Beschreibung:** Ein neues kontobezogenes Feld `scan_raw` (Standard `false`)
ergänzt `scan_images`. Die Einstellungen liefern es als
`enable_raw_scanning` aus und speichern es über `update_user()`. In der
Oberfläche kommt eine eigene Karte „RAW-Fotos“ neben „Include Photos“, mit
klarer Beschreibung, dass nur Rohformate aufgenommen werden. Der Setup-Wizard
bleibt unverändert (Standard aus).

**Akzeptanzkriterien:**
- [ ] `UserVideoData.scan_raw` existiert und ist standardmäßig `false`.
- [ ] `GET /api/settings` liefert `enable_raw_scanning`.
- [ ] `POST /api/settings` speichert `scan_raw` für das angemeldete Konto;
      ein Nicht-Admin kann sein eigenes Feld setzen.
- [ ] Die Einstellungen zeigen die Karte „RAW-Fotos“ mit ID
      `settingsScanRAW`; Laden und Speichern funktionieren.
- [ ] `settingsScanRAW` ist unabhängig von `settingsScanImages`.
- [ ] Der DOM-Contract-Test bleibt grün.

**Verifikation:**
- [ ] `.venv/bin/pytest tests/test_routes_settings.py tests/test_dom_contract.py tests/test_js_syntax.py`
- [ ] Manuell: Einstellungen öffnen, Schalter setzen, speichern, neu laden.
- [ ] `sqlite3 'file:arcade_data/users.db?mode=ro' "SELECT json_extract(user_data,'$.scan_raw') FROM users WHERE username='admin';"`

**Abhängigkeiten:** Task 1

**Voraussichtlich berührte Dateien:**
- `arcade_scanner/models/user.py`
- `arcade_scanner/server/routes/settings.py`
- `arcade_scanner/templates/components.py`
- `arcade_scanner/server/static/settings.js`
- `tests/test_routes_settings.py`

**Geschätzter Umfang:** M

## Task 17: Gemeinsame Endungsliste und RAW im Datei-Walker

**Beschreibung:** Ein neues Modul `arcade_scanner/core/media_extensions.py`
führt `STANDARD_IMAGE_EXTENSIONS`, `RAW_EXTENSIONS` und
`ALL_IMAGE_EXTENSIONS` als einzige Quelle. `file_system.py` nutzt
`STANDARD_IMAGE_EXTENSIONS` für `allow_images` und `RAW_EXTENSIONS` für
`allow_raw`; die Größenprüfung wendet die Bildschwelle auf beide an.
`manager.py` ermittelt `scan_raw` über alle Konten und setzt
`fs_scanner.allow_raw`. Die RAW-Liste umfasst die 12 bisher versprochenen
Endungen (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2, PEF, SRW, RAW, RWL).

**Akzeptanzkriterien:**
- [ ] `media_extensions.py` ist die einzige Definition der drei Listen.
- [ ] Der Walker liefert RAW nur bei `allow_raw`, Standardbilder nur bei
      `allow_images`; beide Schalter sind unabhängig.
- [ ] Die Mindestgröße für Bilder gilt auch für RAW.
- [ ] `manager.py` setzt `allow_raw`, wenn mindestens ein Konto `scan_raw`
      aktiviert hat.
- [ ] Tests decken alle vier Schalterkombinationen ab.

**Verifikation:**
- [ ] `.venv/bin/pytest tests/test_file_system.py tests/test_scanner_manager.py`
- [ ] `.venv/bin/ruff check arcade_scanner/core/media_extensions.py arcade_scanner/scanner/file_system.py arcade_scanner/scanner/manager.py`

**Abhängigkeiten:** Task 16

**Voraussichtlich berührte Dateien:**
- `arcade_scanner/core/media_extensions.py` (neu)
- `arcade_scanner/scanner/file_system.py`
- `arcade_scanner/scanner/manager.py`
- `tests/test_file_system.py`

**Geschätzter Umfang:** M

## Task 18: Metadaten und Vorschaubilder für RAW

**Beschreibung:** `image_inspector.py` und `video_processor.py` beziehen ihre
Endungslisten aus `media_extensions.py`. Kann Pillow eine RAW-Datei nicht
öffnen (RAF), nimmt der Inspector die Maße aus der eingebetteten Vorschau und
meldet das Format als Endung. `create_thumbnail()` bekommt einen RAW-Zweig:
Vorschau über `raw_preview` laden, mit `exif_transpose` ausrichten, auf
480×270 einpassen (schwarzer Rand), als JPEG schreiben — kein ffmpeg. Der
bestehende Pfad für normale Bilder bleibt unverändert.

**Akzeptanzkriterien:**
- [ ] `ImageInspector.can_handle()` erkennt alle RAW-Endungen.
- [ ] CR2/DNG liefern Maße über Pillow; RAF über die Vorschau; das gemeldete
      Format ist die Endung (z. B. `raf`).
- [ ] RAW-Vorschaubilder sind 480×270 JPEGs, ausgerichtet und mittig auf
      schwarz gesetzt.
- [ ] Ein nicht lesbares RAW führt zu keiner Ausnahme; der Dateiname steht im
      Log, der Scan läuft weiter.
- [ ] Normale Bilder und Videos verhalten sich unverändert.
- [ ] Synthetische Tests für TIFF-, RAF- und DNG-artige Dateien.

**Verifikation:**
- [ ] `.venv/bin/pytest tests/test_image_inspector_batches.py tests/test_video_processor.py tests/test_raw_preview.py`
- [ ] `.venv/bin/ruff check arcade_scanner/scanner/image_inspector.py arcade_scanner/core/video_processor.py`

**Abhängigkeiten:** Task 15, Task 17

**Voraussichtlich berührte Dateien:**
- `arcade_scanner/scanner/image_inspector.py`
- `arcade_scanner/core/video_processor.py`
- `tests/test_image_inspector_batches.py`
- `tests/test_video_processor.py`

**Geschätzter Umfang:** M

## Task 19: End-to-End-Test Scan → Eintrag → Thumbnail

**Beschreibung:** Ein Integrationstest baut eine temporäre Bibliothek mit
synthetischen CR2-, DNG-, RAF- und JPG-Dateien und lässt den Scanner laufen.
Er prüft die Schalterkombinationen: nur RAW, nur Bilder, beides, nichts.
Zusätzlich ein zweiter Lauf, der keine Duplikate erzeugen darf.

**Akzeptanzkriterien:**
- [ ] `scan_raw=true`, `scan_images=false`: nur RAW-Einträge, jeder mit
      Vorschaubild.
- [ ] Beide Schalter aus: keine Einträge.
- [ ] `scan_images=true`: JPG erscheint zusätzlich.
- [ ] Ein zweiter Scan erzeugt keine doppelten Einträge.
- [ ] Der Test nutzt ausschließlich `tmp_path`, nie die echte Bibliothek.

**Verifikation:**
- [ ] `.venv/bin/pytest tests/test_scanner_manager.py` (oder der neue
      fokussierte Test)
- [ ] `.venv/bin/pytest tests/test_no_stray_test_files.py`

**Abhängigkeiten:** Task 17, Task 18

**Voraussichtlich berührte Dateien:**
- `tests/test_scanner_manager.py` oder `tests/test_raw_scan.py` (neu)

**Geschätzter Umfang:** M

## Task 20: Echtest an der Bibliothek im Docker-Container

**Beschreibung:** In den Einstellungen „RAW-Fotos“ aktivieren, „Include Photos“
aus lassen, Container neu starten und den Scan laufen lassen. Danach die
Bibliothek nach CR2/RAF/DNG filtern, Stichproben auf Vorschaubilder prüfen und
sicherstellen, dass keine JPG/PNG-Einträge dazugekommen sind. Scan-Dauer,
Anzahl und nicht lesbare Formate dokumentieren.

**Akzeptanzkriterien:**
- [x] „RAW-Fotos“ ist an, „Include Photos“ bleibt aus
      (`admin.scan_raw = true`, `admin.scan_images = false`).
- [x] Die Bibliothek enthält CR2-, RAF- und DNG-Einträge: **66**
      (3 CR2, 37 DNG, 26 RAF). Gefunden wurden 68; die zwei fehlenden sind
      AppleDouble-`._`-Dateien, die der Walker bewusst überspringt.
- [x] Stichproben: CR2 4752×3168, RAF 4416×2944, DNG 720×480; alle
      Vorschaubilder sind 480×270 JPEG/RGB.
- [x] Es sind keine JPG/PNG-Einträge hinzugekommen (0).
- [x] Im Log stehen keine Tracebacks; die zwei `._`-Dateien sind der einzige
      „Fehlschlag“ und werden bewusst übersprungen.
- [x] Scan-Dauer und Fehlerzahl notiert: 73,08 s, 5.530 Dateien geprüft,
      66 neu, 0 Fehler; Auto-Tagging vergab 30 neue Tags.

**Verifikation:**
- [x] `docker restart arcade-media-scanner`
- [x] `docker logs --tail 100 arcade-media-scanner`
- [x] Datenbank und Thumbnails direkt geprüft (66 Einträge, 11.324
      Thumbnails im Cache, keine fehlenden Thumb-Felder)
- [ ] Manuell: Einstellungen → RAW-Fotos; Bibliothek nach Format filtern
      (UI-Sichtprüfung durch den Nutzer offen)

**Befund zur Zahl:** Die ~2.070 aus `dev-docs/raw-on-linux.md` beziehen sich
auf das Host-`/media` (dort 2.184 RAW). Der Container mountet unter `/media`
aber `/home/ralfus/4TB_data/Media/xxx` (0 RAW); die 68 liegen in
`/media_ralf` (`/home/ralfus/4TB_data/Media_Ralf`), davon 66 echte. Für die
2.184 müsste das Host-`/media` zusätzlich gemountet und als Scan-Ziel
eingetragen werden — eine Ops-Entscheidung, kein Code-Problem.

**Abhängigkeiten:** Task 19

**Voraussichtlich berührte Dateien:**
- keine (Laufzeitdaten)

**Geschätzter Umfang:** M

---

## Checkpoint 4 — RAW-Scan

- [x] 66 RAW-Einträge (3 CR2, 37 DNG, 26 RAF), alle mit 480×270-Vorschau;
      keine JPG/PNG-Einträge
- [x] Stichproben CR2/RAF/DNG korrekt, keine Tracebacks
- [x] Scan-Dauer (73,08 s) und die zwei übersprungenen `._`-Dateien dokumentiert
- [x] Review mit dem Nutzer; 7.2.0 ist geschnitten und gemergt

---

## Später / verschoben

## Task 21: TV-IPK neu bauen und installieren

**Beschreibung:** Das ausgelieferte `com.arcade.scanner.tv_1.0.0_all.ipk` ist
vom 2026-07-05 und enthält keine Tag-Oberfläche. Die Quellen enthalten
Tag-Filter und Detailansicht seit dem 2026-10-02, das IPK wurde danach nie
neu gebaut. Deshalb zeigt der Fernseher keine Tags, obwohl der Server sie
liefert. Der lokale Build scheitert derzeit mit `sh: 1: enact: not found`;
`@enact/cli` ist weder in `package.json` noch im Lockfile deklariert. Vor dem
TV-Test am 2026-11-14 muss die CLI reproduzierbar verfügbar sein, das IPK neu
gebaut und auf dem TV installiert werden.

**Akzeptanzkriterien:**
- [ ] `npm run pack` funktioniert auf diesem Rechner ohne global installiertes
      `enact` (devDependency oder dokumentierter Weg).
- [ ] Ein frisches IPK liegt vor; sein Bundle enthält die Tag-Oberfläche
      (`Alle Tags`, `tagOptions`, Tag-Anzeige) und `/api/user/data`.
- [ ] Das neue IPK ist auf dem TV installiert.
- [ ] Die TV-Punkte aus Task 5 sind damit geprüft.

**Verifikation:**
- [ ] `cd tv_client && npm run pack`
- [ ] `rg -o "Alle Tags|tagOptions|Tags" build/*.js` (oder der tatsächliche
      Build-Pfad)
- [ ] Manuell auf dem TV: Tag-Filter und Detailansicht.

**Abhängigkeiten:** Task 5 (TV-Teil)

**Voraussichtlich berührte Dateien:**
- `tv_client/package.json`
- `tv_client/package-lock.json`
- `tv_client/README.md` (Build-Hinweis)
- neues `com.arcade.scanner.tv_1.0.0_all.ipk`

**Geschätzter Umfang:** M
