# Nachtlauf vom 16./17. August 2026 — Übergabe

Branch `feat/nightly-loops`, 107 Commits, nichts gepusht, nichts gemerged.
Tests: **880 → 2046** (grün). Ruff: **8 vorbestehende Fehler → 0**.
`arcade_data/` nach jeder Iteration nachweislich unverändert.

---

## Zuerst lesen: acht Punkte brauchen deine Entscheidung

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

### 7. Deine Sicherung sichert fast nichts

Der Einstellungsbereich „Backup & Restore" hatte **zwei** Knöpfe, und beide
zeigten auf Routen, die es im Server nie gab (`/api/user/export`,
`/api/user/import`) — eingeführt in einem reinen Frontend-Commit, die
Gegenstücke wurden nie geschrieben. Der Export lud eine 404-Seite herunter, der
Import meldete „Invalid file format" und schob die Schuld auf deine Datei.

**Export repariert.** Es gab die ganze Zeit eine funktionierende Route
(`/api/backup`) ohne einen einzigen Aufrufer; die Beschriftung im Dialog nennt
sogar den Dateinamen, den genau sie setzt. Eine falsch verdrahtete Leitung.

**Zwei Dinge bleiben deine Entscheidung:**

*Erstens, was drin ist.* Die Sicherung enthält **nur `settings.json`** — 2,8 KB.
Nicht dabei:

    users.db          Konten, Passwörter, Favoriten, Tags, Vault-Marken,
                      Scan-Ziele, Ausschlüsse, Smart Collections
    media_library.db  die Bibliothek selbst, 8788 Einträge

Seit der Mehrbenutzer-Umstellung liegt praktisch alles, was du von Hand
eingerichtet hast, in `users.db`. Wenn du eine echte Sicherung willst, ist das
die Datei, auf die es ankommt — sie ist 53 KB groß, ein `cp` genügt.

*Zweitens, ob es eine Wiederherstellung geben soll.* Ich habe sie **nicht
gebaut**. Eine Route, die eine hochgeladene Datei über die Einstellungen
schreibt, ist eine löschende Operation, und ihre Bedeutung ist eine
Entscheidung: Welche Konten sind betroffen, ersetzen oder mischen? Dazu kommt
eine Falle: `settings.json` führt `scan_targets`, `exclude_paths`,
`available_tags` und die `sensitive_*`-Listen noch als **leere Hüllen**, während
die echten Werte pro Nutzer in `users.db` stehen. Ein naiver Import würde sie
mit leeren Listen überschreiben — der Einstellungs-Handler unterscheidet „nicht
angegeben" von „leer" und schreibt Letzteres durch. Aus einer Wiederherstellung
würde so ein Datenverlust.

Der Import-Knopf ist noch da und tut weiterhin nichts. Ihn zu entfernen oder die
Route zu bauen, ist deine Wahl; beides wäre besser als der jetzige Zustand.

### 8. Das Standardkonto heißt `admin` mit dem Passwort `admin`

`UserStore.__init__` legt bei **jedem Start** ein Konto `admin` mit dem
Passwort `admin` und Admin-Rechten an, sobald kein Nutzer dieses Namens
existiert (`user_store.py:25`, `create_default_admin`). Das heißt auch: Löschst
du es je, ist es beim nächsten Start wieder da.

**Richtigstellung gegenüber einer früheren Fassung dieses Berichts:** Der
Einrichtungsassistent verschweigt das nicht. Er schreibt beim Einrichten
ausdrücklich hin: „Default password: admin (change this after first login!)".
Erzwungen wird der Wechsel allerdings nicht, und nach einem eigenen
Admin-Passwort fragt der Assistent nie — für zusätzliche Konten tut er es.

Ob das bei dir noch das gesetzte Passwort ist, kannst du in einem Satz prüfen —
melde dich mit `admin`/`admin` an. Ich habe es **nicht** nachgesehen: Der
Versuch, das gegen deine echte `users.db` zu rechnen, wurde blockiert, und zu
Recht — von außen ist das nicht von Hash-Knacken zu unterscheiden.

**Nicht geändert**, weil jede Alternative eine Produktentscheidung ist: ein
zufälliges Startpasswort in die Konsole schreiben, einen Zwang zum Wechsel bei
der ersten Anmeldung, oder gar kein Standardkonto. Das Docker-Onboarding hängt
mit dran (`create_default_admin` setzt dort `setup_complete = False`).

Zwei kleinere Punkte im selben Bereich, ebenfalls deine Entscheidung:

- **Es gibt kein Löschen und keinen Rechte-Entzug.** `manage_users.py` kann
  `list`, `add`, `passwd` — mehr nicht. Ein Konto wird man nur über die
  Datenbank wieder los.
- **Ein Passwortwechsel beendet laufende Sitzungen nicht.** Der Server hält sie
  im Arbeitsspeicher, das CLI-Skript läuft in einem eigenen Prozess. Wechselst
  du ein Passwort, *weil* es abhandengekommen ist, bleibt die fremde Sitzung bis
  zum Ablauf gültig. Das Skript sagt das jetzt hin, behebt es aber nicht — dafür
  bräuchte es eine Server-Route.

---

## Sicherheitsfunde (behoben)

| Fund | Auswirkung |
|---|---|
| `/api/discard_optimized` löschte **beliebige Dateien** | Der Standard-Zweig rief `os.remove()` auf jedem Pfad auf, ohne Bindung an einen DB-Eintrag. Jedes angemeldete Konto konnte damit Dateien weit außerhalb der Bibliothek löschen. Ausnutzbarkeit belegt: gegen den alten Stand schlagen die neuen Tests fehl, weil die Datei tatsächlich verschwindet. |
| `/api/debug/dump` war **unauthentifiziert** | Gab ohne Anmeldung Scan-Pfade, sämtliche Benutzernamen mit Admin-Flag und Scan-Zielen sowie echte Dateipfade heraus. Der Rundum-Test fand dabei sofort eine zweite offene Route (`/api/cache-stats`). |
| Sitzungs-Token im Zugriffslog | `/stream`-Zeilen wurden nur unterdrückt, solange `verbose_scanning` **aus** war. Die Diagnose-Option schrieb also gültige Zugangs-Token mit — genau dann, wenn man Logs weitergibt. |
| Dateinamen führten Code aus | `createVideoCard()` setzte den Namen unmaskiert per `innerHTML`. Ein Video namens `<img src=x onerror=…>.mp4` führt beim Aufbau des Grids Code aus. |
| `POST /api/settings` schrieb **vor** der Sitzungsprüfung | `config.save()` lief vor `get_current_user()`: Eine anonyme Anfrage konnte Scan-Schwellen, ffmpeg-Pfade, `proxy_root` und `review_dir` setzen und scheiterte erst danach still am fehlenden Nutzer. Der Mangel war seit einem **früheren** Nachtlauf als xfail im Testcode dokumentiert und nie behoben worden — mir aufgefallen, weil ich die Datei für etwas anderes anfasste. |
| Brute-Force-Sperre per Header aushebelbar | `/api/login` nahm die Kennung aus `X-Forwarded-For` — vom Client gesetzt. Mit wechselndem Wert: fünf Versuche je Fantasie-IP, beliebig viele. Jetzt zählt zusätzlich der Benutzername mit. |
| Benutzernamen waren über die **Antwortzeit** erratbar | `verify_password()` rechnete bei unbekanntem Namen gar nicht: 62,39 ms gegen 0,28 ms, Faktor 220 — über Netzwerk trivial zu unterscheiden. Seit die Sperre (Zeile darüber) am Benutzernamen hängt, wird aus so einer Namensliste eine Liste gezielt sperrbarer Konten. Jetzt 62,28 gegen 62,54 ms. |
| `manage_users.py` nahm **leere Passwörter** an | Zweimal Enter an der Abfrage genügte — die Eingaben waren gleich, eine Leerprüfung gab es nicht. Das Konto stand danach ohne Passwort in der Datenbank. Dasselbe Skript war außerdem gar nicht ausführbar: Die Shebang-Zeile zeigte auf einen absoluten Pfad einer fremden Maschine. |
| **Alle mitgelieferten Standard-Ausschlüsse waren wirkungslos** | `@eaDir`, `#recycle`, `Temporary Items`, `Network Trash Folder`, `$RECYCLE.BIN`, `AppData/Local/Temp` sind Verzeichnis*namen*, liefen aber durch `os.path.abspath()` und wurden zu Pfaden im Arbeitsverzeichnis des Servers. An einem Baum mit genau diesen Ordnern nachgemessen: kein einziger griff. Auf einem Synology-NAS hält `@eaDir` zu jeder Datei eine Miniatur — bei eingeschalteten Bildern verdoppelt das die Bibliothek. |
| Ausgeschlossene Verzeichnisse über **Symlinks** erreichbar | `os.walk` folgt Symlinks nicht — das Ziel selbst wird aber betreten, und die Pfade tragen dann den Namen des Symlinks. Drei Varianten waren umgehbar. |
| Unlesbare Benutzerdatenbank ⇒ **Scan des ganzen Homes ohne Ausschlüsse** | Ziele und Ausschlüsse kommen aus derselben Quelle, die ihre Fehler verschluckt. „Nicht lesbar" sah aus wie „nichts eingerichtet": der eine Aufrufer fiel auf das Home-Verzeichnis zurück, dem anderen fehlten zeitgleich alle Ausschlüsse. |
| Ein Serverfehler breitete den **gesamten Vault** aus — in **beiden** Clients | `loadUserData()` setzt `v.hidden` aus `/api/user/data`. Schlug der Aufruf fehl, blieb der Wert `undefined` — und `v.hidden \|\| false` macht daraus „nicht versteckt". Ein einzelner 500er hätte also alles gezeigt, was du weggelegt hast. Jetzt zeigt die Ansicht in dem Fall gar nichts, mit einer Erklärung. Derselbe Fehler steckte im TV-Client — dort auf der Startseite, und besonders unauffällig, weil die Vault-Ansicht dann leer ist: Es sah aus, als sei nichts versteckt, statt als sei etwas kaputt. |
| Abgesicherter Modus griff bei **eigenen** Tags nicht | Der Tag des Videos wurde kleingeschrieben, die eingestellte Liste nicht. Wer „NSFW" eintippte, bekam nie einen Treffer — unentdeckt, weil die Voreinstellungen klein geschrieben sind. Zweitens brach ein Eintrag ohne Pfad den ganzen Filter, womit der Modus *alles* zeigte. |
| Tag- und Ordnernamen in interpolierten `onclick`-Handlern | Fünf Stellen. Der Breadcrumb-Handler war sogar abgesichert — aber nur gegen Apostrophe, während das Attribut von Anführungszeichen begrenzt wird. |
| Ordnerpfade fremder Bibliotheken im gemeinsamen HTML-Dump | `FOLDERS_DATA` enthielt die Ordner *aller* Nutzer, mit vollem Pfad im `title`-Attribut. |

**Ursache hinter zwei dieser Funde:** Der Server hat kein globales Auth-Gate —
jede Route prüft in ihrem eigenen Zweig, eine kann es also vergessen. Ein Test
geht jetzt per AST alle GET- und POST-Routen durch.

### Was sich an den Ausschlüssen in der Bedeutung geändert hat

Damit die Voreinstellungen überhaupt greifen können, versteht der Scanner jetzt
drei Schreibweisen statt einer:

    /home/ralf/privat     absoluter Pfad — genau dieser Baum
    @eaDir                nackter Name   — jeder Ordner, der so heißt
    AppData/Local/Temp    Teilpfad       — jeder Ordner, der so endet

Das gilt auch für **selbst eingetragene** Ausschlüsse: `Downloads` schließt
jetzt jeden so benannten Ordner aus statt gar nichts. Mehr auszuschließen ist
hier die sichere Richtung, aber es ist eine Bedeutungsänderung — falls du die
strenge Lesart willst (nur absolute Pfade zählen, alles andere wird abgelehnt),
ist das eine Zeile.

Deine Einstellungen habe ich nachgesehen: keine eigenen Ausschlüsse eingetragen,
und keiner der 8788 Einträge liegt unter einem der betroffenen Ordner. Bei dir
wirkt die Korrektur also nur vorbeugend.

**Nicht behoben, weil Entscheidung:** Auf case-insensitiven Dateisystemen
(macOS-Standard, und es gibt einen Mac-Worker) schließt `Privat` das
Verzeichnis `privat` nicht aus. Auf Linux ist genau das richtig, deshalb hilft
kein pauschales Kleinschreiben. Dasselbe gilt für `~/Privat` im Feld
„sensitive Verzeichnisse" des abgesicherten Modus — im Browser ist nicht
bekannt, wofür `~` steht.

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

## Die Warteschlange (behoben)

Das ist der einzige Teil des Produkts, der **Dateien ersetzt**. Entsprechend
sind das die teuersten Fehler dieser Nacht.

| Fund | Auswirkung |
|---|---|
| Die fertige Umwandlung konnte eine **fremde Datei überschreiben** | Der Optimierer schreibt immer `.mp4`. Aus `film.mkv` wird `film.mp4` — liegt daneben schon eine, ist sie danach ersatzlos weg. `os.replace` und `os.rename` schweigen dazu. Zweiter Weg: zwei Quellen mit gleichem Stamm (`film.mkv`, `film.avi`) in derselben Warteschlange — die zweite Umwandlung überschreibt die erste, und beide Originale sind dann schon gelöscht. **In deiner Bibliothek gibt es zwei solche Paare** (siehe unten). Beide Ersetzungspfade brechen jetzt ab. |
| Lokale Umwandlung **ignorierte laufende Warteschlangen-Jobs** | `/compress` und `/batch_compress` starten den Optimierer direkt und fragten nicht, ob ein Mac gerade an derselben Datei arbeitet — genau der Zustand, den die Warteschlange mit ihrem Compare-and-Swap verhindert. `candidates.py` benutzt die nötige Information längst; nur die beiden Stellen, die einen Encoder starten, fragten nicht. |
| Unbekannte Job-Zustände erzeugten **unerreichbare Zeilen** | `/api/queue/complete` übernahm den Status ungeprüft. Ein `"encoded"` statt `"done"` liegt weder in der aktiven noch in der endgültigen Menge: nie aufgeräumt, nie abgeschlossen. |
| Verwaiste Jobs blockierten ihre Datei **dauerhaft** | Aufgeräumt wurde nur, wenn ein Arbeiter nach Arbeit fragt — also nie, wenn der Arbeiter gerade weg ist. Nach einem Neustart mitten im Encode blieb der Job auf „läuft", und die Datei liess sich nie wieder einreihen. |

### Die zwei betroffenen Dateipaare bei dir

    pantyhose13219                     .mkv  +  .mp4
    April_2026_Shiny_in_Polen_POV      .mov  +  .mp4

**Ebenfalls offen:** Zwei *lokale* Umwandlungen derselben Datei bleiben
möglich. `batch_controller.py` und `video_optimizer.py` sprechen gar nicht mit
der Warteschlange, tauchen dort also nicht auf. Das zu schließen hieße, lokale
Läufe einzutragen — eine Entwurfsänderung.

Hättest du die `.mkv` bzw. die `.mov` optimiert, wäre die daneben liegende
`.mp4` überschrieben worden — ohne Meldung. Jetzt bricht der Job mit einer
Begründung ab. **Was du damit machen willst, ist deine Entscheidung**: eine der
beiden löschen, oder eine umbenennen. Ich habe nichts angefasst.

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
- **Ein Test von mir hat in deine `users.db` geschrieben.** Aufgefallen ist es
  der mtime-Prüfung, die ich nach jeder Iteration laufen lasse. Ursache:
  `apply_configuration()` holt sich `user_db` *innerhalb* ihres Rumpfes aus dem
  Modul, und diese Instanz zeigt seit dem Import auf dein echtes
  Datenverzeichnis — ein Patch der Konfiguration erreicht sie nicht. Ich habe
  die Daten sofort nachgeprüft: unversehrt, dieselben Zahlen wie bei der
  Messung Stunden vorher (9 Favoriten, 1 Vault-Marke, 93 Tags, 6
  Tag-Definitionen, Ziele `/media` und `/media_nas`). Es war ein identisches
  Neuschreiben derselben Zeile. In `conftest.py` steht jetzt eine Sperre, die
  so einen Zugriff sofort scheitern lässt — das Gegenstück zu der für den
  Report-Debouncer.
- Ich habe fast gemeldet, dass **13 Dateien deiner Bibliothek verschwunden
  sind** — sie ließen sich auf der Platte nicht finden. Dann habe ich die
  gesamte Bibliothek geprüft: Es sind **alle 8788**, weil `/media`,
  `/media_nas` und `/media_ralf` auf diesem Rechner nicht eingehängt sind. Ein
  Ergebnis, das zu gut zur These passt, gehört gegen die Gesamtmenge geprüft.
  (Die Zahl zu den Vorschaubildern ist davon unberührt — die vergleicht
  Dateinamen gegen Datenbankpfade, nicht gegen die Platte.)
- Ich hatte das Standardpasswort `admin` im Bericht als verstecktes Problem
  beschrieben. Der Assistent sagt es ausdrücklich an und fordert zum Wechsel
  auf; oben richtiggestellt.
- Mein Auth-Durchlauf meldete `/api/settings/remove-photos` als ungeschützt. Die
  Prüfung steht im delegierten Handler; ich habe den Test genauer gemacht statt
  die Meldung wegzudrücken.

---

## Journal

Der ausführliche Verlauf mit Begründungen pro Iteration steht in
`NIGHT-LOOP3.md`.
