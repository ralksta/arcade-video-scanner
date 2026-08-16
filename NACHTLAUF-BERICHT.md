# Nachtlauf vom 16./17. August 2026 — Übergabe

Branch `feat/nightly-loops`, 55 Commits, nichts gepusht, nichts gemerged.
Tests: **880 → 1623** (grün). Ruff: **8 vorbestehende Fehler → 0**.
`arcade_data/` nach jeder Iteration nachweislich unverändert.

---

## Zuerst lesen: sechs Punkte brauchen deine Entscheidung

### 1. Der iOS-Client ist seit Monaten funktionsunfähig

Commit `8c6008a` („complete removal of VR Gallery and DeoVR integration")
entfernte `/api/deovr/library` und `/api/deovr/collection/<id>`. Der Client ruft
beide bis heute auf und bekommt auf jede Bibliotheksabfrage einen 404. Dazu
schickt er keinerlei Sitzung mit — er stammt aus der Zeit vor der
Mehrbenutzer-Umstellung.

**Nicht repariert**, weil sich Swift hier weder übersetzen noch testen lässt.
~150 Zeilen ungeprüften Client-Code zu hinterlassen hätte nach Fortschritt
ausgesehen, ohne einer zu sein.

→ `dev-docs/ios-client-status.md` beschreibt beide Brüche und den
Reparaturweg. Enthält auch die ehrliche Alternative: den Client zurückziehen,
falls du ihn nicht mehr nutzt.

### 2. Gespeicherte Ansichten sind für alle Nutzer sichtbar

`/api/settings` mischt sieben Felder sauber pro Nutzer. `saved_views` fehlt in
dieser Liste und lebt global — enthält aber Suchbegriff und Ordnerpfad. Jeder
angemeldete Nutzer sieht, wonach die anderen gesucht haben.

**Nicht geändert**, weil es davon abhängt, was deine Installation ist: In einer
Familien-Installation sind geteilte Ansichten praktisch, bei getrennten Konten
sind sie eine Preisgabe. Die Umstellung bräuchte außerdem eine Datenmigration.

→ `dev-docs/saved-views-are-shared.md`, beide Wege beschrieben.

### 3. Das Dashboard lädt von Cloudflare und Google

Das README versprach „No data ever leaves your computer … 100% locally". Das
Dashboard zieht aber Tailwind von `cdn.tailwindcss.com` und Schriften von
Google — bei jedem Aufruf, auch auf der Anmeldeseite vor dem Login. Deine
Mediendaten bleiben lokal; es geht um IP, User-Agent und Nutzungszeitpunkt.
Der Tailwind-CDN liefert zusätzlich ausführbares JavaScript in deine Sitzung.

**Zusage im README präzisiert** (eine unzutreffende Datenschutz-Aussage ist
schlimmer als eine eingeschränkte). **Abhängigkeit nicht beseitigt**: Schriften
ginge, Tailwind ist der JIT-Compiler und kollidiert mit eurer Entscheidung
„no build step".

→ `dev-docs/external-resources.md`, nach Aufwand sortierter Weg.

### 4. Die Bottom-Nav-Umgehung ist überflüssig geworden

Der Ordner-Browser bekam einen eigenen Bottom-Nav-Eintrag, *weil* die
Ansichts-Umschalter auf dem Handy fehlten — dafür flog **Vault** aus der
Bottom-Nav. Die Umschalter sind jetzt da. Ob Vault zurückkehrt, ist deine
Entscheidung; ich habe nichts angefasst.

### 5. Zu Version 7.0.0 fehlen die Release-Notes

`CHANGELOG.md` hat keinen Abschnitt für 7.0.0, obwohl die Version
veröffentlicht wurde. Ich habe **keine erfunden** — plausibel klingende
Release-Notes wären schlimmer als eine sichtbare Lücke. Ein Test hält sie fest.

### 6. 87 Stellen mit unmaskierten Interpolationen

Der Renderpfad, über den *jede* Datei läuft, ist abgesichert (siehe unten). Die
übrigen 87 Fundstellen sind zu einem erheblichen Teil Fehlalarme; welche echt
sind, lässt sich nur einzeln beurteilen. Pauschal `escapeHtml()` darüberzuziehen
hätte dort Schaden angerichtet, wo bereits maskiert wird.

→ `dev-docs/frontend-escaping.md`, priorisiert.

---

## Sicherheitsfunde (behoben)

| Fund | Auswirkung |
|---|---|
| `/api/discard_optimized` löschte **beliebige Dateien** | Der Standard-Zweig rief `os.remove()` auf jedem Pfad auf, ohne Bindung an einen DB-Eintrag. Jedes angemeldete Konto konnte damit Dateien weit außerhalb der Bibliothek löschen. Ausnutzbarkeit belegt: gegen den alten Stand schlagen die neuen Tests fehl, weil die Datei tatsächlich verschwindet. |
| `/api/debug/dump` war **unauthentifiziert** | Gab ohne Anmeldung Scan-Pfade, sämtliche Benutzernamen mit Admin-Flag und Scan-Zielen sowie echte Dateipfade heraus. Der Rundum-Test fand dabei sofort eine zweite offene Route (`/api/cache-stats`). |
| Sitzungs-Token im Zugriffslog | `/stream`-Zeilen wurden nur unterdrückt, solange `verbose_scanning` **aus** war. Die Diagnose-Option schrieb also gültige Zugangs-Token mit — genau dann, wenn man Logs weitergibt. |
| Dateinamen führten Code aus | `createVideoCard()` setzte den Namen unmaskiert per `innerHTML`. Ein Video namens `<img src=x onerror=…>.mp4` führt beim Aufbau des Grids Code aus. |
| Brute-Force-Sperre per Header aushebelbar | `/api/login` nahm die Kennung aus `X-Forwarded-For` — vom Client gesetzt. Mit wechselndem Wert: fünf Versuche je Fantasie-IP, beliebig viele. Jetzt zählt zusätzlich der Benutzername mit. |
| Tag- und Ordnernamen in interpolierten `onclick`-Handlern | Fünf Stellen. Der Breadcrumb-Handler war sogar abgesichert — aber nur gegen Apostrophe, während das Attribut von Anführungszeichen begrenzt wird. |
| Ordnerpfade fremder Bibliotheken im gemeinsamen HTML-Dump | `FOLDERS_DATA` enthielt die Ordner *aller* Nutzer, mit vollem Pfad im `title`-Attribut. |

**Ursache hinter zwei dieser Funde:** Der Server hat kein globales Auth-Gate —
jede Route prüft in ihrem eigenen Zweig, eine kann es also vergessen. Ein Test
geht jetzt per AST alle GET- und POST-Routen durch.

---

## Korrektheitsfunde (behoben)

- **Auto-Tagging lief nach dem Scan stillschweigend nicht mehr.** Der Hook war
  mit `except ImportError: pass` und dem Kommentar „landet mit PR #34"
  abgesichert. Der PR ist gelandet, der Guard blieb — und verschluckte seither
  echte Importfehler.
- **Veraltete Proxys wurden ausgeliefert.** Geprüft wurde nur, *ob* ein Proxy
  existiert. Nach einer Nachbearbeitung sah man unterwegs eine Fassung, die es
  nicht mehr gibt. (Deckt den offenen Roadmap-Punkt „automatic refresh" ab.)
- **Die Test-Suite schrieb in dein Produktivverzeichnis.** `ReportDebouncer`
  feuert eine Sekunde nach `schedule()` auf einem Daemon-Thread, wenn der
  Config-Patch des Tests weg ist. Jeder volle `pytest`-Lauf hat
  `media_library.db` geöffnet (inklusive Migrationen) und `index.html`
  überschrieben.
- **Ad-hoc-Skripte im Wurzelverzeichnis** (`test_dump.py` & Co.) öffnen beim
  Import die echte Datenbank. Schon `pytest --collect-only` genügte — belegt.
  Verschoben nach `scripts/adhoc/`, nicht gelöscht.
- **TV-Client: Smart Collections filterten nach dem falschen Feld** (`v.status`
  statt `v.Status`) — `pending` traf immer, `optimized` nie.
- **GIF-Export: `speed=0`** scheiterte an einer Division durch null hinter dem
  Guard `speed != 1.0`.
- **`/api/debug/dump` griff an der Thread-Sicherung vorbei** auf die geteilte
  DB-Verbindung — genau die Falle, vor der der Store-Kommentar warnt.
- Vier stille Fehlerpfade hörbar gemacht; 19 von 63 `fetch`-Aufrufen im
  Frontend hatten keinen Fehlerpfad, davon mehrere mit optimistischem
  UI-Update ohne Rollback.

---

## Neue Funktionen

- **„Ähnliche Medien"-Leiste im Cinema** (Taste `S`) — Embedding-Teil 2 aus der
  Roadmap; das Backend gab es schon, nur die Oberfläche fehlte.
- **`/api/similar/status`** + Index-Anzeige in den Einstellungen.
- **Export der Ansicht** als CSV und M3U über die Command-Palette.
- **Tastaturkürzel-Overlay (`?`)** plus `/` für die Suche und `1`–`4` fürs
  Layout.
- **Kontextbezogener Leer-Zustand** statt weißer Fläche.
- **Barrierefreiheit**: Icon-Labels, stumme Icons, Fokus-Käfig für Dialoge.

---

## Performance (gemessen an deiner echten Bibliothek, 8788 Einträge)

| Änderung | Wirkung |
|---|---|
| `/api/videos`-Antwort-Cache | ~105 ms CPU pro Request gespart (40 ms JSON + 54 ms gzip + 10 ms Filtern) |
| Cache-Buster aus Datei-mtime | 588 KB Asset-Traffic entfielen nach jedem Scan; vorher entwertete jede Report-Neugenerierung den Browser-Cache |
| Fünf ungenutzte DB-Indizes entfernt | Schreiben 66 % schneller (2000 Upserts: 47 → 16 ms), Datei 38 % kleiner |
| Toter `clean_results`-Aufbau entfernt | 8788 Dict-Kopien pro Report-Neugenerierung, Ergebnis verworfen |

**Hinweis:** Die Index-Migration lief bereits auf deiner Produktivdatenbank —
sie wäre beim nächsten Start ohnehin passiert. Daten geprüft: 8788 Einträge,
18 Queue-Jobs, alle Tabellen intakt.

---

## Prüfen die Tests wirklich etwas?

Zehn semantische Mutationen eingespielt (Lock entfernt, Pfadprüfung auf
immer-`True`, Stale-Vergleich umgedreht, Token-Maskierung wirkungslos …):
**zehn von zehn erkannt**, vier davon in Code aus dieser Nacht.

→ `dev-docs/test-suite-verification.md`, samt Anleitung zum Wiederholen.

---

## Was ich falsch hatte

Der Vollständigkeit halber, weil es das Vertrauen in den Rest kalibriert:

- Ich hielt kurz den **GIF-Export für tot** (`window.currentCinemaPath` schien
  nie zugewiesen). Die Zuweisung läuft über `Object.defineProperty` am Ende von
  `cinema.js` — mein Grep-Muster traf sie nicht. Alles in Ordnung dort.
- Ich schrieb dem **Modul-Import** zu, die Produktivdatenbank migriert zu haben.
  Verursacher war der `ReportDebouncer`; der Import allein ist harmlos.
- Mein erster Prüflauf meldete **20 fehlende Dateiverweise** in `CLAUDE.md`. Das
  Muster war zu streng; es waren zwei, und beide korrekt.
- Eine Analyse meldete **sechs weggeworfene `save()`-Rückgabewerte** — es waren
  `db.save()`-Aufrufe (dokumentierter No-Op), nicht `config.save()`.
- Mein Auth-Durchlauf meldete `/api/settings/remove-photos` als ungeschützt. Die
  Prüfung steht im delegierten Handler; ich habe den Test genauer gemacht statt
  die Meldung wegzudrücken.

---

## Journal

Der ausführliche Verlauf mit Begründungen pro Iteration steht in
`NIGHT-LOOP3.md`.
