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

> Nachtrag: Der Ruff-Baseline-Wert von 8 Fehlern ist am Ende von Loop G auf 0
> gefallen. Die Suite steht bei 1474 statt 880 Tests.

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

- [x] **Loop E — Konsistenz zwischen den Clients** — ausgereizt
      - [x] Endpunkt-Abgleich: **iOS-Client seit `8c6008a` funktionsunfähig**
            (tote DeoVR-Routen + keine Sitzung). Dokumentiert statt blind
            repariert — keine Swift-Toolchain zum Prüfen. Vertrags-Test ergänzt
      - [x] Filter-Semantik: TV-Client las `v.status` statt `v.Status` — Status-
            Filter kehrten sich um. Plus Codec-Vergleich, `favorites: false` und
            Vault-Regel angeglichen; Differenztest gegen den Browser-Matcher
      - [x] Antwortformat-Annahmen: `v.resolution` gibt es nicht (Auflösung
            fehlte still im Label) — plus Server-Adresse an 9 Stellen fest
            verdrahtet, jetzt in `serverConfig.js`
      `CLAUDE.md` warnt ausdrücklich davor, dass TV- und iOS-Client bei
      API-Änderungen mitgezogen werden müssen; frühere Commits haben genau das
      nachgeholt. Nach einer Nacht mit Änderungen an `/api/videos`,
      `/api/similar` und der Proxy-Auflösung lohnt der Abgleich:
      - Welche Filter-/Sortier-Semantik weicht ab?
      - Welche neuen Endpunkte fehlen den Clients?
      - Wo sind Annahmen über Antwortformate fest verdrahtet?

## Zyklus 3

Wieder aus Funden abgeleitet, nicht frei gewählt.

- [x] **Loop F — Sicherheit und Datentrennung** — ausgereizt (5 Funde)
      Das Produkt beschreibt sich als „self-hosted, privacy-first" mit
      Mehrbenutzer-Trennung. In Loop B fiel dabei ein echtes Leck auf
      (`FOLDERS_DATA` mit fremden Ordnerpfaden im gemeinsamen Dump) — gefunden
      nur, weil ich zufällig einen Test für eine Doku-Zusage schrieb. Das
      verdient eine gezielte Durchsicht:
      - [x] Sitzungs-Token im Log: `/stream`-Zeilen wurden nur unterdrückt,
        solange `verbose_scanning` aus war — die Diagnose-Option schrieb also
        gültige Zugangs-Token mit. Wird jetzt immer maskiert.
      - [x] Pfad-Prüfungen: `discard_optimized` löschte **beliebige Dateien**
        (Zweig ohne DB-Bindung), `keep_optimized` verschob ungeprüft. Beide
        jetzt über `sanitize_path`; gegen den alten Stand verifiziert
      - [x] `/api/debug/dump` war **unauthentifiziert**: Nutzerliste, Scan-Ziele,
        Dateipfade. Jetzt admin-pflichtig; Rundum-Test fand zusätzlich
        `/api/cache-stats` offen
      - [x] `innerHTML`: Grid-Karte und Vergleichskarte maskieren jetzt.
        87 weitere Fundstellen erhoben, **nicht** pauschal umgestellt —
        dokumentiert in `dev-docs/frontend-escaping.md`
      - [x] Trennung: `/api/settings` mischt sauber pro Nutzer — mit einer
        Ausnahme: `saved_views` ist global, enthält aber Suchbegriff und
        Ordnerpfad. Als Produktentscheidung dokumentiert, nicht eigenmächtig
        geändert (`dev-docs/saved-views-are-shared.md`)

- [x] **Loop G — Altlasten im Repository** — ausgereizt
      Beim Durchsuchen sind wiederholt Dateien aufgefallen, die nicht mehr
      dazugehören: macOS-Ressourcenzweige (`._*.py`, die als Python-Dateien
      gescannt werden und Analysen stören), `docker-compose.yml_back2`,
      `screenlog.0`, eine gebaute `.ipk`, sowie `test_api.py`, `test_dump.py`,
      `test_probe*.py`, `test_ui.js`, `test_puppeteer.js` und `run_fix.py` im
      Wurzelverzeichnis — die sehen aus wie Tests, laufen aber nicht mit der
      Suite. Dazu die acht vorbestehenden Ruff-Fehler.
      - [x] Ad-hoc-Skripte nach `scripts/adhoc/` verschoben (nicht gelöscht) —
            beim Einsammeln durch pytest hätten sie die echte DB migriert
      - [x] `.ipk` (15 MB Binärpaket) aus Git entfernt, Datei bleibt lokal
      - Befund: `._*`, `screenlog.0` und `*_back*` standen bereits in
        `.gitignore` — sie liegen nur lokal, nicht im Repository
      - [x] Die acht vorbestehenden Ruff-Fehler behoben; Ruff-Konfiguration auf
            `[tool.ruff.lint]` umgestellt (die Deprecation-Warnung lief bei
            jedem Lauf mit). **Ruff ist erstmals vollständig sauber.**

## Zyklus 4

Beide Themen haben sich in dieser Nacht schon zufällig als ergiebig erwiesen —
jetzt systematisch.

- [x] **Loop H — Behauptungen der Doku gegen den Code prüfen** — ausgereizt
      Genau diese Frage fand das `FOLDERS_DATA`-Leck: `CLAUDE.md` beschrieb einen
      Trennungs-Mechanismus, den es so nicht mehr gab. Und der Abhängigkeits-
      Wächter entstand aus derselben Frage. Weitere Kandidaten:
      - [x] Versionsnummern: fünf verschiedene gefunden (4.9.0 / 6.3 / 6.7 /
        6.8.0 / 7.0.0). Eine Quelle in `arcade_scanner/__version__`, CLAUDE.md
        korrigiert. Offen und dokumentiert: 7.0.0 hat keinen CHANGELOG-Abschnitt
      - [x] CLAUDE.md systematisch geprüft: alle 30 Dateiverweise, fünf
        CLI-Flags und drei Nutzer-Kommandos stimmen. Einzige Unrichtigkeit: die
        Routen-Liste nannte 5 von 9 Modulen. Wächter-Test ergänzt.
      - [x] README: Zusage „100% locally" traf nicht zu — Dashboard lädt
        Tailwind und Schriften von CDNs. Zusage präzisiert, Beseitigung
        dokumentiert (`dev-docs/external-resources.md`)
      - [x] `ROADMAP.md` geprüft: keine offenen Haken mehr (die zwei fehlenden
        heute Nacht gesetzt), alle 9 Dateiverweise und 4 Endpunkte stimmen —
        `client.js` wird korrekt als *ehemalige* Datei genannt

- [x] **Loop I — Tests, die nichts prüfen** — ausgereizt, **keine gefunden**
      Heute Nacht zweimal zufällig gefunden: ein `pytest.skip`, das nach einer
      Umstellung immer griff, und Ladereihenfolge-Tests, die per Substring das
      falsche Ergebnis verglichen und zufällig grün waren. Systematisch suchen:
      - Tests ohne `assert`
      - `skip`/`xfail`, deren Bedingung immer zutrifft
      - Zusicherungen, die nicht fehlschlagen können (`assert True`,
        `assert x or not x`, Vergleiche gegen sich selbst)
      - Parametrisierungen mit leerer Liste
      - Mocks, die so umfassend sind, dass der Test nur den Mock prüft

## Zyklus 5

- [x] **Loop J — Maskierung dort, wo die Angriffsfläche wirklich ist** — ausgereizt
      Löst eine Schuld ein, die ich in `dev-docs/frontend-escaping.md` selbst
      benannt habe: Von den 87 Fundstellen sind `folder_browser.js` (Ordnernamen)
      und `tag_manager.js` (frei vergebene Tags) die einzigen mit echtem
      Fremdeinfluss. Einzeln beurteilen, mit node-Tests belegen — nicht pauschal
      `escapeHtml()` darüberziehen.

- [x] **Loop K — Der Optimizer** — ausgereizt (1 Fehler, 2× kein Fehler)
      - [x] `parse_time_to_seconds`: las Trim-Zeiten anders als ffmpeg — die
            SSIM-Prüfung verglich dadurch die falschen Bilder
      - [x] `apply_encoding_preset` und `apply_scale_to_filter` abgedeckt —
            **kein Fehler**, beide arbeiten korrekt; der Software-Filter ist
            gegen echtes ffmpeg geprüft
      - [x] `build_ffmpeg_command` abgedeckt — kein Fehler; der erzeugte Aufruf
            wird von echtem ffmpeg ausgeführt, nicht nur inspiziert
      `scripts/video_optimizer.py` ist die größte Einzeldatei und das
      Kernversprechen des Produkts (50–80 % Ersparnis), aber die
      Entscheidungslogik ist kaum abgedeckt: 25 Divisionen mit variablem
      Divisor, 15 stumme Handler. Ohne Medien lässt sich kein Encode prüfen —
      die reinen Rechen- und Entscheidungsfunktionen aber sehr wohl.

## Zyklus 6

- [x] **Loop L — Sitzungen und Anmeldung**
      - [x] Brute-Force-Sperre war per `X-Forwarded-For` aushebelbar — Sperre
            auf den Benutzernamen ergänzt
      - [x] Sitzungsverfall, Token-Erzeugung, Abmeldung geprüft: **korrekt**
      - [x] Benutzernamen waren über die Antwortzeit erratbar (Faktor 220) —
            Ableitung läuft jetzt auch für unbekannte Namen
      - [x] Nutzerverwaltung: Skript war unausführbar (fremder absoluter Pfad
            in der Shebang-Zeile), leeres Passwort wurde angenommen
      - [ ] **Für Ralf:** Standardkonto `admin`/`admin`, kein Löschen/Entziehen,
            Passwortwechsel beendet laufende Sitzungen nicht → im Bericht
      `security/auth.py` speichert bei jeder Sitzung ein `created_at` — ob es je
      ausgewertet wird, ist offen. Ein Token, das nie verfällt, ist nach dem
      Fund „Token im Zugriffslog" (Loop F) besonders relevant: was einmal
      irgendwo landete, gilt dann für immer. Weiter: Passwort-Hashing,
      Abmeldung, Sitzungen über Neustarts.

- [x] **Loop M — Der Scanner: was wird tatsächlich gescannt?**
      - [x] Drei Wege, über Symlinks in einen ausgeschlossenen Baum zu gelangen
      - [x] **Alle mitgelieferten Standard-Ausschlüsse waren wirkungslos**
            (`@eaDir`, `#recycle`, `$RECYCLE.BIN`, …) — drei Schreibweisen
            werden jetzt verstanden
      - [ ] **Für Ralf:** Groß/Kleinschreibung auf case-insensitiven
            Dateisystemen (macOS) → im Bericht
      - [x] Abgesicherter Modus: Tag-Vergleich einseitig case-sensitiv,
            Eintrag ohne Pfad legte den ganzen Filter lahm
      - [x] Unlesbare Benutzerdatenbank löste einen Scan des ganzen Homes aus
            — ohne die Ausschlüsse, die aus derselben Quelle kommen
      Ausschlüsse sind bei diesem Produkt eine Datenschutz-Funktion
      (`exclude_paths`, `sensitive_dirs`). Ein Fehler dort heißt: Verzeichnisse
      landen in der Bibliothek, die der Nutzer ausdrücklich ausgenommen hat.
      Reine Logik, ohne Medien prüfbar.

## Zyklus 7

Gewählt nach demselben Maßstab wie bisher: Wo richtet ein Fehler echten
Schaden an, und lässt er sich ohne Hardware und ohne Ralfs Daten prüfen?

- [x] **Loop N — Die Warteschlange**
      - [x] Fertige Umwandlung konnte eine fremde Datei überschreiben
            (zwei betroffene Paare in Ralfs Bibliothek)
      - [x] Verwaiste Jobs blockierten ihre Datei dauerhaft — aufgeräumt wurde
            nur, wenn ein Arbeiter nach Arbeit fragt
      - [x] Lokale Umwandlung liess sich für eine Datei starten, an der die
            Warteschlange gerade arbeitet
      - [x] Unbekannte Job-Zustände erzeugten Zeilen, die keine Stelle mehr
            anfasst
      - [ ] **Für Ralf:** zwei *lokale* Läufe derselben Datei bleiben möglich —
            dafür müssten lokale Umwandlungen in die Warteschlange
      In Ralfs Datenbank stehen 18 Jobs. Die Warteschlange ist der einzige
      Teil des Produkts, der *Dateien ersetzt* — ein Zustandsfehler heißt hier
      nicht „Anzeige falsch", sondern im schlimmsten Fall eine halb
      geschriebene Datei an der Stelle des Originals. Fragen: Was passiert bei
      einem Neustart mitten im Encode? Kann ein Job zweimal laufen (Server +
      `mac_worker.py`)? Bleiben Jobs für immer auf „running" stehen?

- [ ] **Loop O — Duplikaterkennung** (läuft)
      - [x] Löschrouten prüften gegen die Ziele *aller* Nutzer
      - [x] `is_path_allowed` verglich per `startswith` ohne Verzeichnisgrenze
            — `/media` erlaubte `/media_nas` und `/media_ralf`
      - [ ] **Für Ralf:** die übrigen fünf `is_path_allowed`-Aufrufe sind
            weiterhin installationsweit → im Bericht
      - [ ] Offen: Gruppenbildung, `recommended_keep`, Re-Encode-Erkennung
      Der zweite Bereich mit einer löschenden Aktion. Was gilt als Duplikat,
      wie oft irrt sich das, und was passiert beim Zusammenführen mit Tags und
      Favoriten des unterlegenen Eintrags? Perceptual Hashing ist reine Logik,
      also ohne Medien prüfbar.

## Abschluss vor dem Morgen

- [x] Übergabebericht geschrieben: `NACHTLAUF-BERICHT.md` — sechs Punkte für
      Ralfs Entscheidung zuerst, dann Sicherheits- und Korrektheitsfunde,
      Performance-Messwerte, und ein Abschnitt „Was ich falsch hatte".

## Journal

<!-- Jede Iteration hängt hier eine Zeile an: was gemacht, was gelernt, was als Nächstes. -->

- **Iteration 49 (Loop O, Löschumfang)** — Der Duplikat-Scan reicht die
  Scan-Ziele des angemeldeten Nutzers durch, die beiden **löschenden** Routen
  daneben nicht: `is_path_allowed(abs_path)` ohne zweites Argument fällt auf die
  Vereinigung der Ziele aller Nutzer zurück. Ein Zweitkonto konnte über die API
  Dateien löschen, die es in der Oberfläche nie zu sehen bekommt. Beim
  Testschreiben fiel der eigentliche Fund auf: Die Prüfung vergleicht per
  `startswith` **ohne Verzeichnisgrenze**. `/media` galt damit als Erlaubnis für
  `/media_nas` und `/media_ralf` — genau die drei Scan-Ziele dieser
  Installation. Solange niemand eigene Verzeichnisse übergab, entschied die
  Zeile über nichts; die Vereinigung enthielt alle drei ohnehin. Gelernt:
  Ein latenter Fehler wird nicht dadurch entdeckt, dass man ihn liest, sondern
  dadurch, dass etwas anfängt, sich auf ihn zu verlassen. Mein erster
  Negativtest bestand aus dem falschen Grund (der erfundene Pfad existierte
  nicht) — mit echten Dateien wurde er rot. Nächstes: Gruppenbildung und
  `recommended_keep`.

- **Iteration 48 (Loop N, Zustände — Loop N abgeschlossen)** — `update_job_status`
  nahm jede Zeichenkette an, und `/api/queue/complete` reicht das Feld ungeprüft
  aus dem Rumpf der Anfrage durch. Ein `"encoded"` statt `"done"` hätte den Job
  in ein Nirgendwo versetzt: Die Warteschlange entscheidet überall anhand von
  Zugehörigkeit zu zwei Mengen — aktiv (`pending`, `downloading`, `encoding`,
  `uploading`) und endgültig (`done`, `failed`, `cancelled`) —, und ein Wert
  ausserhalb beider ist weder aufräumbar noch abgeschlossen. Gelernt: Wenn
  Logik über Mengenzugehörigkeit statt über Gleichheit entscheidet, ist der
  gefährliche Wert nicht der falsche, sondern der, der in keine Menge fällt.
  Die beiden Mengen stehen jetzt als Konstanten da statt in jeder Abfrage neu
  aufgezählt. Nächstes: Loop O (Duplikaterkennung).

- **Iteration 47 (Loop N, doppelte Ausführung)** — Die Warteschlange sichert
  ihre Übernahme per Compare-and-Swap ab, und der Kommentar begründet es
  ausdrücklich: sonst „two workers encode the same file and race on the same
  output path". Genau dieser Zustand liess sich trotzdem herstellen — nur nicht
  über die Warteschlange. `/compress` und `/batch_compress` starten den
  Optimierer direkt und fragten nirgends nach, ob ein Mac gerade an derselben
  Datei arbeitet. Am aufschlussreichsten: `candidates.py:42` benutzt
  `get_active_queue_paths()` längst, um belegte Dateien aus den Vorschlägen zu
  nehmen. Die Information lag bereit — nur die beiden Stellen, die tatsächlich
  einen Encoder starten, haben sie nicht abgefragt. Gelernt: Eine Absicherung
  schützt den Weg, auf dem sie steht; ein zweiter Weg zum selben Ziel erbt sie
  nicht. Dritter Fund dieser Nacht nach demselben Muster (Iterationen 43, 46).
  Zwei lokale Läufe derselben Datei bleiben möglich — das wäre eine
  Entwurfsänderung, steht im Bericht. Nächstes: Loop O (Duplikaterkennung).

- **Iteration 46 (Loop N, verwaiste Jobs)** — Dasselbe Muster wie in
  Iteration 43, an ganz anderer Stelle: Die Aufräumfunktion für verwaiste Jobs
  ist sorgfältig gebaut (Frist, Zählung der Versuche, Aufgeben nach dreien) und
  hing an genau einer Stelle — `get_next_pending()`. Aufgeräumt wurde also nur,
  wenn ein Arbeiter nach Arbeit fragt. Für den Fall, für den sie gedacht ist —
  der Arbeiter ist weg —, gab es damit niemanden mehr, der sie auslöst. Der Job
  blieb auf `encoding` stehen, das Dashboard zeigte ihn ewig als laufend, und
  die Datei liess sich nie wieder einreihen. Gelernt: Eine Selbstheilung, die
  nur der Gesunde auslösen kann, heilt nicht. Aufgeräumt wird jetzt auch beim
  Lesen des Status — ein Lesezugriff, der schreibt, aber der Entwurf hat
  bewusst keinen Hintergrund-Scheduler, und das Dashboard fragt ohnehin
  regelmässig. Nächstes: doppelte Ausführung (Server neben `mac_worker.py`).

- **Iteration 45 (Loop N, Zielkollision)** — Der Warteschlangen-Code ist gut
  abgesichert: Übernahme per Compare-and-Swap, Wiederaufnahme verwaister Jobs,
  Integritätsprüfung vor dem Ersetzen, Ablehnung nicht-atomarer Verschiebungen
  über Dateisystemgrenzen. Genau deshalb war die Lücke dort, wo niemand
  hinsieht: `atomic_replace` prüft, *wie* ersetzt wird, aber nicht, *was* am
  Zielort liegt. Der Optimierer schreibt immer `.mp4`, aus `film.mkv` wird
  `film.mp4` — liegt daneben schon eine, ist sie danach weg. `os.replace` und
  `os.rename` schweigen dazu. Gelernt: Eine sorgfältig gebaute Prüfkette
  erzeugt Vertrauen, das auf die Nachbarzeile abfärbt. In Ralfs Bibliothek
  gibt es zwei solche Paare — der Fund ist nicht theoretisch. Beide
  Ersetzungspfade brechen jetzt ab statt zu überschreiben; welche Datei bleibt,
  kann nur er entscheiden. Nächstes: Warteschlangen-Zustände (Neustart mitten
  im Encode, doppelte Ausführung).

- **Iteration 44 (Loop M, die Voreinstellungen — Loop M abgeschlossen)** — Die
  Warnung aus Iteration 41 („relativer Ausschluss schließt vermutlich nichts
  aus") sprang bei den **mitgelieferten Voreinstellungen** an. Das war kein
  Fehlalarm: `@eaDir`, `#recycle`, `Temporary Items`, `Network Trash Folder`,
  `$RECYCLE.BIN`, `AppData/Local/Temp` sind Verzeichnis*namen*, liefen aber
  durch `os.path.abspath()` und wurden zu Pfaden im Arbeitsverzeichnis des
  Servers. Keine einzige Voreinstellung hat je etwas ausgeschlossen — an einem
  Baum mit genau diesen Ordnern nachgemessen. Gelernt: Der beste Ort für einen
  Fund ist eine Warnung, die man selbst eingebaut hat und die dann bei den
  eigenen Daten anschlägt; ich war einen Schritt davon entfernt, sie als
  „laut, aber harmlos" abzutun. Ausschlüsse werden jetzt in drei Schreibweisen
  verstanden: absoluter Pfad, nackter Name (an jeder Stelle), Teilpfad (auf
  Ordnergrenze). Ralfs Einstellungen geprüft: keine eigenen Ausschlüsse, keine
  betroffenen Einträge — die Korrektur wirkt bei ihm rein vorbeugend.
  Nächstes: Zyklus 7 planen.

- **Iteration 43 (Loop M, Fehlerfall)** — Der schwerste Fund des Loops, und er
  steckte nicht in einer Funktion, sondern zwischen zweien. `active_scan_targets`
  und `active_exclude_paths` lesen dieselbe Quelle, und die verschluckt ihre
  Fehler und liefert eine leere Liste. Für beide Aufrufer sah „Datenbank nicht
  lesbar" damit aus wie „nichts eingerichtet" — der eine schloss daraus, das
  ganze Home zu scannen, der andere, dass es keine Ausschlüsse gibt. Zusammen:
  vollständiger Home-Scan ohne genau die Verzeichnisse, die ausgenommen sein
  sollten. Gelernt: Ein verschluckter Fehler ist nicht dort gefährlich, wo er
  passiert, sondern dort, wo jemand aus dem Ersatzwert eine Absicht ableitet.
  Zwei harmlose Rückfälle ergeben zusammen einen gefährlichen. `get_all_users()`
  merkt sich jetzt, ob es lesen konnte; der Home-Rückfall (gewollt beim ersten
  Start) greift nur noch bei einer wirklich leeren Datenbank. Nächstes: Loop M
  abschließen, dann Zyklus 7 planen.

- **Iteration 42 (Loop M, abgesicherter Modus)** — `sensitive_dirs` hatte ich
  zunächst für ungenutzt gehalten — die Python-Suche fand keinen Leser. Der
  Leser steht im Frontend (`utils.js:isSensitive`), und dort waren zwei Fehler.
  Der schönere: Der Tag des Videos wurde kleingeschrieben, die *eingestellte
  Liste* nicht. Wer „NSFW" eintippte — die naheliegende Schreibweise —, bekam
  `['NSFW'].includes('nsfw')` und nie einen Treffer. Unentdeckt blieb es, weil
  die Voreinstellungen klein geschrieben sind und für die der Vergleich zufällig
  aufging: Der eingebaute Fall belegte den kaputten Pfad nicht. Der zweite:
  `video.FilePath` ungeprüft dereferenziert — ein Eintrag ohne Pfad warf mitten
  in `filterAndSort()`, der Filter fiel ganz aus, und der abgesicherte Modus
  zeigte *alles*. Ein Schutz, der in die offene Richtung versagt.
  Festgehalten, nicht geändert: Der Modus blendet aus, er hält nichts zurück —
  die Daten stehen vollständig in der API-Antwort. Nächstes: Scan-Ziele und der
  Fehlerfall beim Laden der Ausschlüsse.

- **Iteration 41 (Loop M, Ausschlüsse und Symlinks)** — Statt die Logik zu
  lesen, habe ich zuerst einen echten Verzeichnisbaum gebaut und sechs
  Schreibweisen durchgemessen. Vier waren in Ordnung, zwei nicht. Der Fund:
  `os.walk` folgt Symlinks nicht — daraus hatte ich (und offenbar der Code)
  geschlossen, dass Symlinks kein Thema sind. Das **Ziel** wird aber betreten,
  auch wenn es ein Symlink ist, und die entstehenden Pfade tragen dessen Namen.
  Ein Ausschluss auf das echte Verzeichnis passt darauf nie. Drei Varianten
  davon waren umgehbar. Gelernt: Eine Eigenschaft, die für den Rumpf gilt, gilt
  nicht automatisch für den Einstiegspunkt. Die Ausschlüsse werden jetzt einmal
  je Ziel übersetzt — ein `realpath` pro Ausschluss statt eines pro besuchtem
  Ordner, und die abgelegten Pfade bleiben unverändert (sie umzuschreiben würde
  Favoriten und Tags entwerten). Zweiter Fund: ein relativer Ausschluss wird
  gegen das Arbeitsverzeichnis des *Servers* aufgelöst, schließt nichts aus und
  meldet nichts. Nächstes: `sensitive_dirs` und die Scan-Ziele.

- **Iteration 40 (Loop L, Nutzerverwaltung — Loop L abgeschlossen)** — Das
  Skript, mit dem alle Konten dieser Installation angelegt wurden, war gar
  nicht ausführbar: Die Shebang-Zeile zeigte auf einen absoluten Pfad einer
  anderen Maschine, mit einem Verzeichnisnamen, den dieses Repo nicht hat. Über
  den in CLAUDE.md dokumentierten Aufruf lief es immer — deshalb ist es nie
  aufgefallen. Der Test prüft jetzt alle acht Skripte auf dieselbe Zeile; das
  eine abweichende war zwischen sieben gleichen unsichtbar. Zweiter Fund:
  Zweimal Enter an der Passwortabfrage legte ein Konto **ohne Passwort** an —
  die Gleichheitsprüfung war erfüllt, die Leerprüfung fehlte.
  Nicht angefasst und in den Bericht gegeben: das Standardkonto `admin`/`admin`,
  das bei jedem Start neu entsteht, sobald kein Nutzer „admin" existiert.
  Der Versuch, gegen Ralfs echte Datenbank zu prüfen, ob dieses Passwort dort
  noch gilt, wurde blockiert — richtig so, das ist Hash-Knacken, auch wenn die
  Absicht eine andere war. Er kann es selbst in einem Satz feststellen.
  Nächstes: Loop M (Scanner-Ausschlüsse).

- **Iteration 39 (Loop L, Passwortprüfung)** — Das Hashing selbst ist in
  Ordnung: PBKDF2-HMAC-SHA256, 100.000 Iterationen, Zufallssalz je Nutzer,
  konstantzeitiger Vergleich — im Code sogar ausdrücklich als Schutz gegen
  Timing-Angriffe kommentiert. Genau eine Ebene darüber galt der Schutz nicht:
  Bei unbekanntem Benutzernamen kehrte `verify_password()` sofort zurück, ohne
  zu rechnen. Gemessen 62,39 ms gegen 0,28 ms — Faktor 220, über Netzwerk
  trivial unterscheidbar. Gelernt: Eine Gegenmaßnahme schützt nur den Zweig, in
  dem sie steht; der Kommentar über der Funktion sagt nichts über den Zweig
  darüber. Und die Sperre aus Iteration 38 machte es schlimmer, nicht besser —
  seit sie am Benutzernamen hängt, verwandelt eine Namensliste sich in eine
  Liste gezielt sperrbarer Konten. Nach der Korrektur 62,28 ms gegen 62,54 ms,
  Faktor 1,00. Nächstes: Nutzerverwaltung (`scripts/manage_users.py`), dann
  Loop M.

- **Iteration 38 (Loop L, Anmeldung)** — Meine Ausgangsvermutung („Sitzungen
  verfallen nie") war falsch: Verfall, Gleitfenster und Sperrzeit sind sauber
  gebaut. Der Fund lag daneben — die *Kennung* der Sperre kam aus einem
  Client-Header. Besonders auffällig: `proxy_resolver.py` benennt genau diese
  Fälschbarkeit im Kommentar und begründet, warum sie *dort* harmlos ist. Der
  Login-Pfad hat dieselbe Logik noch einmal inline, ohne den Vorbehalt — und
  dort ist sie es nicht. Kopierte Logik erbt den Code, nicht die Begründung.

- **Iteration 37 (Loop K, Kommandobau)** — Die Ausschlussregeln des Builders
  (VideoToolbox: `-q:v` und `-b:v` heben sich auf; SVT-AV1 stürzt bei `-crf`
  plus `-b:v` ab) standen als Kommentar im Code und gelten jetzt als Test. Beim
  ffmpeg-Gegencheck erst auf x264 ausgewichen, um Zeit zu sparen — das schlug
  fehl, weil der Builder `-tag:v hvc1` setzt. Richtig so: Der Aufruf ist nur als
  Ganzes prüfbar, ein ausgetauschter Codec prüft etwas anderes als das, was in
  Wirklichkeit läuft. Mit libx265 und `ultrafast` läuft der Test in Sekunden und
  erzeugt tatsächlich eine Datei. Loop K ist damit ausgereizt: ein echter Fehler
  (Trim-Zeiten), zweimal Bestätigung ohne Fehler.

- **Iteration 36 (Loop K, Encoder-Konfiguration)** — Hier fast einen Fehler
  gemeldet, den es nicht gibt: Mein synthetisches Profil enthielt weder
  `-realtime` noch `-compression_level`, weshalb die Preset-Wahl wirkungslos
  aussah. Die *echten* Profile tragen beides, und beides wird korrekt ersetzt.
  Lehre: Wer die Wirklichkeit prüfen will, muss die wirklichen Daten nehmen —
  die Tests laufen jetzt über `ENCODER_PROFILES` statt über erfundene Eingaben.
  Der erzeugte Software-Filter wird zusätzlich gegen echtes ffmpeg gehalten,
  statt seine Gültigkeit anzunehmen.

- **Iteration 35 (Loop K, Trim-Zeiten)** — Der bisher subtilste Fund. Zwei
  Auslegungen derselben Zeichenkette: ffmpeg bekommt sie roh, der Optimizer
  wertet sie selbst aus. Solange beide übereinstimmen, fällt nichts auf — bei
  `--ss 1:30` (ffmpeg: 90 s, Optimizer: 0) verrutschen die SSIM-Vergleichspunkte
  um anderthalb Minuten, und die Qualitätsprüfung misst an der falschen Stelle.
  Sie ist die Sicherung gegen einen schlechten Encode, der das Original ersetzt.
  Lehre: Wo derselbe Wert zweimal ausgelegt wird, ist die Übereinstimmung eine
  Zusage — und Zusagen gehören getestet.

- **Iteration 34 (Loop J, Tags und Ordner)** — Fünf interpolierte
  `onclick`-Handler mit frei eingegebenen Tag- bzw. Ordnernamen. Der lehrreichste
  war der *abgesicherte*: `crumb.path.replace(/'/g, "\\'")` schützt gegen
  Apostrophe, aber das Attribut begrenzen Anführungszeichen — eine Absicherung,
  die die falsche Grenze kennt, ist keine. Alle auf DOM-Knoten umgestellt.
  Nebenbei mein eigener `alert()`-Wächter aus Loop A ausgelöst: durch einen
  *Kommentar*, der die behobene Stelle erklärt. Genau der Fehlalarm-Typ, den ich
  in derselben Nacht schon einmal hatte — der Wächter filtert jetzt Kommentare,
  wie der `fetch`-Wächter direkt daneben es längst tat.

- **Iteration 33 (Übergabebericht)** — Bewusst als Datei im Repository, nicht
  als veröffentlichte Seite: der Bericht enthält Sicherheitsfunde zu einem
  privaten Medienserver. Aufbau nach Nutzen sortiert, nicht chronologisch — die
  sechs Punkte, die eine Entscheidung brauchen, stehen oben. Eigener Abschnitt
  für die fünf Fehleinschätzungen der Nacht: wer nur die Treffer liest, kann
  den Rest nicht einordnen.

- **Iteration 32 (Loop I, Testqualität)** — Ergebnis: keine leeren Tests. Die
  sieben Treffer „ohne assert" sind legitime „wirft nicht"-Tests, die drei
  Verdachtsfälle bei den Teilstring-Prüfungen allesamt Fehlalarme meiner
  Heuristik. Der eigentliche Beleg kam vom Mutationstest: zehn semantische
  Mutationen eingespielt (Lock entfernt, Pfadprüfung auf immer-True,
  Stale-Vergleich umgedreht, Token-Maskierung wirkungslos …), **zehn von zehn
  erkannt**. Vier davon betrafen Code aus dieser Nacht — wer seine eigenen Tests
  schreibt, sollte sie auch selbst gegen die Mutation prüfen. Dokumentiert in
  `dev-docs/test-suite-verification.md`, samt Anleitung zum Wiederholen.

- **Iteration 31 (Loop H, Privacy-Zusage)** — Die prominenteste Zusage des
  Projekts traf nicht zu: „No data ever leaves your computer" bei einem
  Dashboard, das Tailwind von Cloudflare und Schriften von Google zieht — schon
  auf der Anmeldeseite. Zwei Entscheidungen dabei: Erstens die Zusage
  präzisiert statt sie stehen zu lassen — eine unzutreffende Datenschutz-Aussage
  ist schlimmer als eine eingeschränkte. Zweitens die Abhängigkeit *nicht*
  beseitigt: Schriften ginge, Tailwind ist der JIT-Compiler, und jeder Ersatz
  kollidiert mit „no build step" oder veraltet unbemerkt. Ohne Browser wäre das
  Ergebnis zudem ungeprüft geblieben.

- **Iteration 30 (Loop H, Doku-Verweise)** — Angenehme Überraschung: von 30
  Dateiverweisen in CLAUDE.md stimmten 28 sofort, die zwei Ausreißer waren
  korrekt als „wird erzeugt" bzw. „if present" beschrieben. Auch alle
  Kommandozeilen stimmen. Die einzige echte Unrichtigkeit war die Routen-Liste
  (5 von 9 Modulen genannt) — wer eine Route sucht, findet sie sonst nicht dort,
  wo die Doku sie vermuten lässt. Mein erster Prüflauf meldete 20 fehlende
  Dateien; das Muster war zu streng (Dateinamen im Kontext eines zuvor genannten
  Verzeichnisses). Erst nach der Korrektur blieben zwei übrig, und die waren
  richtig.

- **Iteration 29 (Loop H, Versionen)** — Die Doku sagte die Wahrheit über sich
  selbst („don't trust any single one") und blieb dabei stehen. Das ist die
  gefährlichere Sorte Doku: sie klingt ehrlich und normalisiert den Zustand.
  Belegt war 7.0.0 über zwei Commits; gesetzt worden war die Nummer damals nur
  im README. Bewusst nicht getan: einen CHANGELOG-Abschnitt für 7.0.0
  erfinden — die Einträge kenne ich nicht, und plausibel klingende
  Release-Notes wären schlimmer als eine sichtbare Lücke. Ein Test hält die
  Lücke fest.

- **Iteration 28 (Loop G, Lint)** — Die acht Fehler, die seit Beginn der Nacht
  als Baseline mitliefen, sind weg: drei automatisch (Importsortierung), fünf
  von Hand (eine Zeile mit sechs Semikolon-getrennten Farbdefinitionen).
  Zusätzlich die Ruff-Konfiguration auf `[tool.ruff.lint]` umgestellt — die
  Deprecation-Warnung lief bei *jedem* Aufruf mit und hätte irgendwann dazu
  geführt, dass niemand mehr hinsieht. Nach der Umstellung geprüft, dass die
  Regeln noch greifen (absichtlicher Verstoß wird gemeldet), statt nur „All
  checks passed" zu glauben. Loop G ist damit ausgereizt.

- **Iteration 27 (Loop G, Ad-hoc-Skripte)** — Was wie Aufräumen aussah, war
  wieder ein Sicherheitsthema: fünf Skripte im Wurzelverzeichnis mit
  `test_`-Präfix, die beim Import die echte Datenbank öffnen. Nachgewiesen, dass
  schon `pytest --collect-only` genügt — „collected 0 items" und die Datenbank
  war migriert. Geschützt hat bisher nur `testpaths = ["tests"]`. Verschoben
  statt gelöscht: es sind die Diagnosewerkzeuge des Entwicklers, sie lagen nur
  am falschen Ort. Nebenbefund: die vermuteten Altlasten `._*`, `screenlog.0`
  und `*_back*` standen längst in `.gitignore` — sie liegen nur lokal.

- **Iteration 26 (Loop F, Datentrennung)** — Die Trennung ist besser gebaut,
  als ich erwartet hatte: `/api/settings` mischt sieben Felder sauber pro Nutzer
  über die globalen Einstellungen. Genau eines fehlt — `saved_views`, und das
  trägt Suchbegriff und Ordnerpfad. Hier habe ich bewusst *nicht* repariert: ob
  Ansichten geteilt gehören, hängt davon ab, ob das eine Familien-Installation
  ist oder getrennte Konten. Datenhoheit umzustellen (samt Migration
  bestehender Ansichten) gehört nicht in einen unbeaufsichtigten Nachtlauf. Ein
  Test sichert den Ist-Zustand, damit die Änderung bewusst geschieht.
  Loop F ist damit ausgereizt.

- **Iteration 25 (Loop F, Maskierung)** — Bewusst nur zwei Renderpfade
  angefasst statt aller 87 Fundstellen. `escapeHtml()` pauschal darüberzuziehen
  hätte dort Schaden angerichtet, wo bereits maskiert oder absichtlich Markup
  erzeugt wird (doppelte Maskierung, zerstörte Icon-Spans) — und ohne Browser
  wäre das Ergebnis nicht prüfbar gewesen. Also der Pfad, über den *jede* Datei
  läuft, sauber gemacht und der Rest offen dokumentiert, statt eine
  Halb-Umstellung als erledigt auszugeben.

- **Iteration 24 (Loop F, Pfad-Prüfung)** — Der schwerwiegendste Fund der
  Nacht: `os.remove()` auf einem Pfad direkt aus der Anfrage, in einem Zweig,
  der an keinen Datenbank-Eintrag gebunden war. Auffällig wurde er nur, weil ich
  systematisch alle Handler mit Pfad-Parameter gegen die vorhandenen Validatoren
  gehalten habe — 6 von 12 ohne Prüfung, davon zwei mit Dateisystem-Zugriff. Die
  vier übrigen arbeiten rein auf der Datenbank und sind unkritisch. Wichtig beim
  Fix: das Review-Verzeichnis liegt außerhalb der Scan-Ziele und musste explizit
  erlaubt bleiben, sonst hätte die Prüfung die Optimizer-Funktion zerstört.

- **Iteration 23 (Loop F, offene Routen)** — `/api/debug/dump` gab ohne jede
  Prüfung Benutzerliste und Bibliotheksstruktur heraus. Die Ursache ist
  strukturell: Der Server hat kein globales Auth-Gate, jede Route prüft selbst —
  eine kann es also vergessen, und niemand merkt es. Statt nur diese eine zu
  reparieren, geht ein Test jetzt per AST alle GET-Routen durch und verlangt
  Prüfung oder begründete Ausnahme. Er fand beim ersten Lauf sofort eine zweite
  offene Route (`/api/cache-stats`) — der Test war also mehr wert als der Fix.

- **Iteration 22 (Loop F, Token im Log)** — Der Token als Query-Parameter ist
  eine bewusste Entscheidung (Video-Tags können keinen Header senden) und für
  sich vertretbar. Der Fehler lag darin, dass die Gegenmaßnahme an einer
  Einstellung hing: `/stream` wurde nur unterdrückt, solange die Diagnose aus
  war. Eine harmlos klingende Option schaltete damit das Mitschreiben von
  Zugangsdaten ein — und zwar genau in der Situation, in der man Logs
  weitergibt. Lehre: Schutz darf nicht von einer Komfort-Einstellung abhängen.

- **Iteration 21 (Loop E, Feldnamen und Adressen)** — Nach dem `Status`-Fehler
  systematisch alle Feldzugriffe des TV-Clients gegen die API-Antwort geprüft:
  `v.resolution` existiert nicht, das Label blieb still leer. Beim Schreiben des
  Wächters gegen fest verdrahtete Adressen fand der Test prompt eine neunte
  Stelle, die ich beim Suchen übersehen hatte (Stream-URL in `App.js`) — und
  einen Fehlalarm, den ich als solchen behandelt habe statt ihn wegzudrücken:
  die iOS-Zeile ist Platzhaltertext in einem Eingabefeld. Loop E ist damit
  ausgereizt.

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
