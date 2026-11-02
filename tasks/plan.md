# Implementierungsplan: Offene Ideen vom 2026-10-24

## Überblick

Die Ideen-Datei `dev-docs/ideas-2026-10-24.md` enthält vier Arbeitsstränge:
Herkunfts-Tags (`web`/`eigene`), einen echten Papierkorb-Test, den Release
7.1.0 und den seit 6.4.1 offenen RAW-Scan. Vision-Auto-Tags bleiben bewusst
außen vor (vertagt, siehe `ROADMAP.md`).

Der Plan arbeitet die Stränge in dieser Reihenfolge ab: erst die
Datenkonfiguration (Herkunfts-Tags), dann die manuelle Verifikation des
Papierkorbs, dann der Release, zuletzt der RAW-Scan. Die ersten beiden
Stränge ändern keinen Code; sie liefern aber die Sicherheit, dass die
vorhandenen Funktionen wirklich tragen, bevor eine Version darauf festgelegt
wird. Der RAW-Scan ist der einzige größere Codeteil und kommt nach dem
Release, damit 7.1.0 nicht durch eine neue Scanner-Funktion blockiert wird.

**Ausdrücklich nicht in diesem Plan:** Vision-Auto-Tags (vertagt), ein
Nachrüsten der Tag-Farbbearbeitung für bestehende Tags (nice-to-have), eine
Änderung an der Meaning von `Include Photos`.

## Entscheidungen

| Entscheidung | Begründung |
|---|---|
| Herkunfts-Tags werden als Auto-Tag-Regeln aus den vorhandenen Collections gebaut, nicht als neue Sonderlogik. | Die Collections `ProSessions – Eigene` (39) und `ProSessions – Web` (140) enthalten bereits die exakten Kriterien. Der Auto-Tagger ist dafür gebaut. |
| Tag-Definitionen werden **vor** dem ersten Regel-Lauf angelegt. | `_ensure_tag_definition()` legt fehlende Tags mit demselben Grün (`#22c55e`) an. Eine nachträgliche Farbänderung gibt es in der UI nicht — nur Kürzel und Löschen. |
| Farben: `web` = `#F4B342` (Amber), `eigene` = `#ec4899` (Pink). | Beide Farben sind bei den vorhandenen Tags noch frei (Korea, xxx, Poppers, Wolford, Pantyhose, fist). |
| Für `web` gilt die exakte Pfadliste der Collection (fünf Web-Ordner), nicht das Keyword `web`. | Das Keyword träfe auch Dateien mit „web“ im Namen außerhalb eines Web-Ordners. Die fünf Pfade sind ODER-verknüpft und damit exakt. |
| Für `eigene` gilt `"/media_ralf/OD/ProSessions" -"*/web*"`. | Entspricht der vorhandenen Collection; der Ausschluss ist ein Pfad-Glob und trifft Web-Ordner unabhängig von Groß-/Kleinschreibung. |
| Der Papierkorb wird mit echten Dateien getestet, nicht nur mit Unit-Tests. | Die Unit-Tests decken die Logik, nicht die UI, den Docker-Pfad und die Aufbewahrungslogik über einen Neustart. |
| Release 7.1.0 bekommt eine 7.0.0-Sektion aus den README-Highlights. | 7.0.0 wurde am 2026-03-17 veröffentlicht, aber nie im CHANGELOG beschrieben. Die Angaben stehen in `README.md`. |
| RAW bekommt einen eigenen Schalter `scan_raw`, nicht `Include Photos`. | `scan_images` ist bei allen Konten aus. Ein Aktivieren würde alle JPG/PNG aufnehmen, nicht nur die ~2.070 RAW-Dateien. |
| RAW-Vorschauen werden ausschließlich mit Pillow aus der eingebetteten JPEG-Vorschau gelesen. | Gemessen in `dev-docs/raw-on-linux.md`; keine neue Laufzeitabhängigkeit. |
| Endungslisten werden in ein gemeinsames Modul gezogen. | Heute führen `file_system.py`, `image_inspector.py` und `video_processor.py` getrennte Listen — genau deshalb fehlen RAW-Dateien im Walker. |
| Docker: Codeänderungen brauchen keinen Rebuild. | `docker-compose.yml` bind-mountet `.:/app`; ein `docker restart arcade-media-scanner` genügt. |
| Der TV-Test wird auf 2026-11-14 verschoben und blockiert den Plan nicht. | Das ausgelieferte IPK ist vom 2026-07-05 und enthält keine Tag-Oberfläche; die Quellen haben sie seit 2026-10-02. Vor dem Test muss die App neu gebaut werden (Task 21). |

## Abhängigkeitsgraph

```
Task 1 (Baseline + Backup)
   │
   ├── Phase 1: Herkunfts-Tags (Tasks 2–5)      [Daten]
   │      2 → 3 → 4 → 5
   │
   ├── Phase 2: Papierkorb-Test (Tasks 6–10)    [manuell]
   │      6 → 7 → 8 → 9 → 10
   │
   └── Phase 3: Release 7.1.0 (Tasks 11–14)
          11 → 12 → 13 → 14
                │
                └── Phase 4: RAW-Scan (Tasks 15–20)
                       15 ──┐
                       16 ──┼→ 17 → 18 → 19 → 20
                            └──┘
```

Task 15 (Vorschau-Helfer) und Task 16 (Schalter) sind voneinander unabhängig
und können parallel laufen. Task 17 braucht Task 16 (der Walker liest
`scan_raw`), Task 18 braucht Task 15 und 17, Task 19 braucht 17 und 18.
Task 20 ist die Verifikation an der echten Bibliothek.

## Aufgabenindex

### Phase 0 — Baseline
- Task 1: Baseline und Sicherung

### Phase 1 — Herkunft als Tag
- Task 2: Tag-Definitionen `web` und `eigene` anlegen
- Task 3: Auto-Tag-Regeln aus den beiden Collections anlegen
- Task 4: Regeln einmal ausführen und Treffer prüfen
- Task 5: Sichtbarkeit auf Karten, im Filter und auf dem Fernseher prüfen

### Checkpoint 1 — Herkunfts-Tags
- [ ] Regeln liefern 39 (`eigene`) und 140 (`web`)
- [ ] Kein Treffer außerhalb von `/media_ralf/OD/ProSessions`
- [ ] Karten, Tag-Filter und TV zeigen beide Tags mit den vereinbarten Farben
- [ ] Review mit dem Nutzer

### Phase 2 — Papierkorb einmal echt testen
- Task 6: Testdatei vorbereiten und Zustand festhalten
- Task 7: Löschen und Papierkorb-Eintrag prüfen
- Task 8: Zurückholen und Zustand prüfen
- Task 9: Endgültig leeren und Aufräumen prüfen
- Task 10: 30-Tage-Ablauf über einen Neustart prüfen

### Checkpoint 2 — Papierkorb
- [ ] Alle fünf Punkte der Ideen-Checkliste sind abgehakt
- [ ] Aufgefundene Fehler sind mit einem Regressionstest behoben
- [ ] Review mit dem Nutzer

### Phase 3 — Release 7.1.0
- Task 11: CHANGELOG (7.1.0 + nachgeholte 7.0.0-Sektion) und Versionsbump
- Task 12: Vollständige Prüfung und Commit auf `dev`
- Task 13: PR von `dev` nach `main`
- Task 14: Deployment im Docker-Container und Smoke-Test

### Checkpoint 3 — Release
- [ ] Version 7.1.0 in Log, README und CHANGELOG
- [ ] PR gemergt, Container gesund, Dashboard und Papierkorb laden
- [ ] Review mit dem Nutzer

### Phase 4 — RAW-Scan
- Task 15: Pillow-Helfer für eingebettete RAW-Vorschauen
- Task 16: Einstellung „RAW-Fotos scannen“ (`scan_raw`)
- Task 17: Gemeinsame Endungsliste und RAW im Datei-Walker
- Task 18: Metadaten und Vorschaubilder für RAW
- Task 19: End-to-End-Test Scan → Eintrag → Thumbnail
- Task 20: Echtest an der Bibliothek im Docker-Container

### Checkpoint 4 — RAW-Scan
- [ ] ~2.070 RAW-Einträge mit Vorschau, keine JPG/PNG-Einträge
- [ ] Stichproben CR2/RAF/DNG korrekt, keine Tracebacks
- [ ] Scan-Dauer und nicht lesbare Formate dokumentiert
- [ ] Review mit dem Nutzer

## Risiken und Gegenmaßnahmen

| Risiko | Schwere | Gegenmaßnahme |
|---|---|---|
| Eine Auto-Tag-Regel trifft zu viele Dateien; Tags sind „apply once“ und nur einzeln von Hand entfernbar. | Hoch | `users.db` vorher sichern; Trefferzahlen der Collections vorher prüfen; Regel erst nach Sichtprüfung der Kriterien ausführen. Bei Fehlgriff: Regel löschen (räumt `auto_tag_applied`), Tags manuell entfernen. |
| Beide Auto-Tags bekommen dasselbe Grün, weil die Definitionen erst beim Lauf entstehen. | Mittel | Definitionen in Task 2 vor Task 3/4 anlegen; Task 4 prüft die Farben. |
| Der Auto-Tag-Lauf überschreibt eine gleichzeitige Änderung desselben Kontos. | Mittel | Lauf dann starten, wenn niemand aktiv arbeitet; Backup vorhanden. Die Einschränkung ist im Code dokumentiert. |
| Beim Papierkorb-Test wird die falsche Datei gelöscht. | Hoch | Nur ein Duplikat mit einer zweiten Kopie außerhalb der Bibliothek verwenden; Pfad vor dem Löschen notieren und im Papierkorb gegenprüfen. |
| Die Ablaufprüfung manipuliert den echten Papierkorb-Index. | Mittel | Container vorher stoppen, Index sichern, nur den einen Test-Eintrag ändern. |
| Der Release-PR enthält unbeabsichtigte Commits. | Mittel | `git log main..dev` vor dem PR prüfen; nur Release-Commits auf `dev`. |
| RAW-Schalter wird mit `Include Photos` verwechselt und flutet die Bibliothek. | Hoch | Eigener Schalter, standardmäßig aus; Task 20 prüft ausdrücklich, dass keine JPG/PNG-Einträge dazukommen. |
| Nicht gemessene RAW-Formate (CR3, PEF, SRW, RAW, RWL) lassen sich nicht lesen. | Mittel | Generischer SOI/EOI-Fallback; ein nicht lesbares Format wird protokolliert und übersprungen, nicht still verschluckt. |
| Der TV zeigt keine Tags, weil das ausgelieferte IPK veraltet ist. | Mittel | Als Task 21 aufgenommen: vor dem TV-Test am 2026-11-14 die Enact-CLI reproduzierbar machen, IPK neu bauen und installieren. Blockiert Phase 2/3 nicht. |
| Tests brauchen `node`, `ffmpeg`/`ffprobe`. | Niedrig | Vor Task 1 prüfen; die Testsuite nutzt beides bereits. |

## Geklärte Punkte (Review am 2026-10-24)

1. **Nur `admin`:** `web`/`eigene` gelten vorerst ausschließlich für das
   Konto `admin`. Für `privat` werden keine Definitionen und Regeln angelegt;
   der TV-Client nutzt `admin`.
2. **RAW bleibt im Plan:** Phase 4 wird in diesem Durchgang mit umgesetzt,
   nicht auf einen späteren Plan verschoben.
3. **Reihenfolge bleibt:** Herkunfts-Tags → Papierkorb-Test → Release 7.1.0 →
   RAW-Scan.
4. **TV-Test verschoben:** Der Nutzer kann TV-Features erst in drei Wochen
   (2026-11-14) testen. Der TV-Teil von Task 5 wird bis dahin zurückgestellt
   und blockiert die übrigen Phasen nicht. Ursache des aktuellen „geht nicht“
   ist der veraltete IPK-Build (Task 21), nicht die Tag-Konfiguration.

## Offene Fragen (nicht blockierend)

1. **Tag-Farben nachträglich ändern:** Die UI erlaubt es für bestehende Tags
   nicht. Falls das öfter gebraucht wird, wäre ein eigener kleiner Task
   „Farbe bearbeiten“ sinnvoll — nicht Teil dieses Plans.
2. **RAW in 7.1.0?** Wenn Phase 4 überraschend schnell fertig ist, könnte der
   Schalter mit in 7.1.0. Empfehlung: nein, eigener Release 7.2.0; 7.1.0
   bleibt der Release für Papierkorb, Suche und Collection-Dialog.
3. **`eigene`-Definition:** Der Glob `-*/web*` schließt auch Dateien aus, deren
   Dateiname mit `web` beginnt (z. B. `webcam.mp4`). In der vorhandenen
   Sammlung ist das so gewollt; falls nicht, wäre die Alternativregel
   `"/ProSessions" -web` (Keyword) oder eine Pfadliste nötig.

## Referenzen

- `dev-docs/ideas-2026-10-24.md` — Ausgangslage
- `arcade_scanner/core/auto_tagger.py`, `core/criteria_eval.py` — Regel-Engine
- `arcade_scanner/server/routes/autotag.py` — CRUD und „Jetzt ausführen“
- `arcade_scanner/core/trash.py`, `routes/trash.py`, `static/trash_ui.js` — Papierkorb
- `dev-docs/raw-on-linux.md` — gemessener RAW-Weg
- `arcade_scanner/scanner/file_system.py`, `scanner/image_inspector.py`,
  `core/video_processor.py` — Endungslisten und Vorschauen
- `tests/test_auto_tagger.py`, `test_trash.py`, `test_file_system.py`,
  `test_version_consistency.py` — bestehende Absicherung
