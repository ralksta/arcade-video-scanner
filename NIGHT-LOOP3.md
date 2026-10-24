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

- [x] **Loop O — Duplikaterkennung**
      - [x] Löschrouten prüften gegen die Ziele *aller* Nutzer
      - [x] `is_path_allowed` verglich per `startswith` ohne Verzeichnisgrenze
            — `/media` erlaubte `/media_nas` und `/media_ralf`
      - [ ] **Für Ralf:** die übrigen fünf `is_path_allowed`-Aufrufe sind
            weiterhin installationsweit → im Bericht
      - [x] Bild-Rückfallweg erklärte „ähnlich groß" zu „exaktes Duplikat"
      - [x] Favoriten, Tags und Vault-Marken überlebten das Löschen und
            wurden von neuen Dateien desselben Pfads geerbt
      - [ ] **Für Ralf:** 15 bereits verwaiste Einträge in seinen Nutzerdaten →
            im Bericht, nicht angefasst
      - [x] `recommended_keep` fiel bei Punktgleichstand auf die
            Eingabereihenfolge — bei Re-Encodes der Normalfall
      - [ ] **Für Ralf:** Bitrate wiegt schwerer als Auflösung (50 gegen
            30 Punkte) → Beobachtung im Bericht, nichts geändert
      Der zweite Bereich mit einer löschenden Aktion. Was gilt als Duplikat,
      wie oft irrt sich das, und was passiert beim Zusammenführen mit Tags und
      Favoriten des unterlegenen Eintrags? Perceptual Hashing ist reine Logik,
      also ohne Medien prüfbar.

## Zyklus 8

- [x] **Loop P — Datensicherung**
      - [x] Beide Knöpfe im Bereich „Backup & Restore" zeigten auf Routen,
            die es nie gab — Export repariert
      - [x] `settings.json` wurde beim Schreiben zuerst geleert; ein defektes
            wurde beim Start ersatzlos überschrieben
      - [ ] **Für Ralf:** Wiederherstellung nicht implementiert, und die
            Sicherung enthält nur `settings.json` → im Bericht
      `/api/backup` gibt es, und eine Sicherung ist genau so viel wert wie die
      Wiederherstellung, die noch niemand versucht hat. Fragen: Was liegt
      drin? Sind die Konten dabei (`users.db`) oder nur die Medien? Lässt sich
      daraus überhaupt ein lauffähiger Zustand herstellen? Eine Sicherung, die
      nur fast vollständig ist, merkt man am schlechtesten Tag.

- [x] **Loop Q — Auslieferung: Streaming und Proxys**
      - [x] Verkürzt gelieferte Streams liessen den Client hängen —
            erreichbar, wenn der Optimierer die Datei währenddessen ersetzt
      - [x] Kein Validator: Bereiche aus zwei verschiedenen Fassungen konnten
            in einer Wiedergabe landen — jetzt `ETag` und `If-Range`
      - [x] Proxy-Entscheidung geprüft: HEAD und GET treffen dieselbe,
            Veraltungsprüfung vorhanden, Adressbereiche korrekt — nichts offen
      Jede Wiedergabe läuft hier durch. Range-Requests, Teilinhalte, Springen
      im Video, und die Entscheidung LAN → Original / Tailscale → Proxy. Reine
      Protokoll-Logik, ohne Mediendateien prüfbar.

## Zyklus 9

- [x] **Loop R — Auto-Tagging**
      - [x] Eigener Fehler aus Iteration 51 gefunden und behoben: Tags wurden
            beim Löschen aufgeräumt, die Auto-Tag-Buchführung nicht
      - [x] Eine Regel mit leeren oder vertippten Kriterien vertaggte die
            gesamte Bibliothek
      Regeln, die selbsttätig Tags in die Nutzerdaten schreiben. Ein Fehler
      hier ist bleibend und sichtbar: falsche Tags an echten Dateien, und
      niemand weiss, woher sie kommen. In Loop C fiel schon auf, dass der
      Aufruf nach dem Scan jahrelang stillschweigend gar nicht lief.

- [x] **Loop S — Erstlauf und Einrichtung**
      - [x] Der Assistent lief über bestehenden Installationen los — bei
            unlesbarem `settings.json` und ohne Terminal sogar stillschweigend
      - [x] `apply_configuration` schrieb an der abgesicherten Stelle vorbei
      - [x] `config.save()` meldete Erfolg, auch wenn das Schreiben scheiterte
      `onboarding.py` schreibt Einstellungen, legt das Admin-Konto an und
      entscheidet, was gescannt wird. Es läuft genau einmal — deshalb sieht es
      niemand nochmal an, und deshalb fällt dort nichts auf. Hängt am
      Standardkonto-Punkt aus dem Bericht.

## Zyklus 10

- [x] **Loop T — Vorschaubilder**
      - [x] Ein geändertes Video behielt sein altes Vorschaubild für immer
      - [x] Der Traversal-Schutz verglich ohne Verzeichnisgrenze — derselbe
            Fehler wie in `is_path_allowed`
      - [ ] **Für Ralf:** 1141 verwaiste Vorschaubilder, 17,3 MB → im Bericht
      - [x] Verwaiste Vorschaubilder werden beim Entfernen verwaister
            Einträge mit gelöscht
      Jede Karte im Raster zeigt eines, und sie sind das einzige, was auf der
      Platte mitwächst, ohne dass jemand hinsieht. Fragen: Werden sie
      erneuert, wenn sich die Datei ändert? Werden sie aufgeräumt, wenn die
      Datei verschwindet? Und was passiert bei einem Pfad, der kein gültiger
      Dateiname ist?

- [x] **Loop U — Der Filter im Frontend**
      - [x] Ein Fehler beim Laden der Nutzerdaten breitete den **gesamten
            Vault** in der normalen Ansicht aus
      - [x] Paarbildung und `_opt`-Erkennung nachgemessen: **nichts zu
            ändern**, Messungen als Tests festgehalten
      `filter_engine.js` entscheidet, was der Nutzer überhaupt sieht — ein
      Fehler dort versteckt Dateien, ohne dass irgendwo etwas fehlt. Über den
      node-Kontext ausführbar, also messbar statt gelesen.

## Zyklus 11

- [x] **Loop V — Der TV-Client**
      - [x] Derselbe Vault-Fehler wie im Browser-Client — auf dem Fernseher
      - [x] `node --check` prüft ESM-Dateien gar nicht; der Syntaxtest sichert
            sich jetzt selbst ab
      - [x] Standard-Sortierung „newest" sortierte nicht nach Datum, sondern
            drehte die Datenbankreihenfolge um — null Überschneidung mit den
            tatsächlich neuesten zehn
      - [x] Login-Pfad und Sammlungs-Matcher geprüft: in Ordnung
      - [ ] **Für Ralf:** Server-Adresse im Login-Bildschirm — bewusst nicht
            gebaut, ohne `node_modules` nicht prüfbar
      Einer von drei Clients, und der einzige, den Ralf laut Commit-Historie
      tatsächlich pflegt. Schon einmal fiel dort auf, dass Smart Collections
      nach dem falschen Feld filterten (`v.status` statt `v.Status`) — solche
      Abweichungen fallen nicht auf, weil niemand beide Clients nebeneinander
      hält. Über node ausführbar.

- [x] **Loop W — Nebenläufigkeit im Server**
      - [x] Gleichzeitige Anfragen desselben Kontos verwarfen einander:
            60 gesetzt, **4 angekommen**
      - [x] Geteilte SQLite-Verbindung geprüft: alle 67 Zugriffe sind gedeckt
      - [x] Tags, Einstellungen und Auto-Tag-Regeln umgestellt; der
            Auto-Tagger bleibt bewusst außen vor, mit Begründung im Code
      - [x] **Nebenbei behoben:** `POST /api/settings` schrieb die globalen
            Einstellungen *vor* der Sitzungsprüfung — seit einem früheren
            Nachtlauf als xfail dokumentiert und liegengeblieben
      Eine geteilte SQLite-Verbindung hinter einem wiedereintrittsfähigen
      Lock, dazu ein ThreadingTCPServer. Der letzte grosse Bereich, in dem ein
      Fehler nicht falsch aussieht, sondern selten.

## Zyklus 12

Die dokumentierten Altlasten sind abgearbeitet: Der xfail zu `/api/settings`
war echt und ist behoben; die verbliebenen (iOS-DeoVR-Routen) sind eine
begründete Entscheidung, kein Versäumnis. Also zwei neue Themenfelder.

- [x] **Loop X — Die Ähnlichkeitssuche**
      - [x] Ergebnisse enthielten Pfade aus den Zielen **anderer** Konten
      - [x] Fiel der Nutzerdatensatz aus, entfiel die Vault-Filterung
      - [x] Die Grenzprüfung „Pfad liegt in Verzeichnis" stand an vier Stellen
            einzeln, dreimal ohne Verzeichnisgrenze — jetzt an einer
      In Loop D habe ich die „Ähnliche Medien"-Leiste gebaut, weil das Backend
      schon da war. Die Tabellen `frame_embeddings` und `embedding_meta` haben
      **null Zeilen**. Wird der Index je gebaut? Eine Funktion, die ich selbst
      ausgeliefert habe und die vielleicht nichts tut, gehört zuerst geprüft.

- [x] **Loop Y — Die Wartungsfunktionen**
      - [x] Jede Wartung brach im Docker-Betrieb still ab
      - [x] Die Zielliste führte dasselbe Verzeichnis zweimal — in beiden
            Funktionen; „previews" gibt es im Code gar nicht
      - [x] `is_safe_to_delete()` verglich ohne Verzeichnisgrenze (fünfte
            Fundstelle derselben Rechnung)
      - [ ] **Für Ralf:** `process_video()` in video_processor.py hat keinen
            einzigen Aufrufer → im Bericht
      `core/maintenance.py` löscht: `purge_media`, `purge_broken_media`,
      `purge_thumbnails`. Alles hinter Kommandozeilen-Schaltern, alles ohne
      Netz. Der letzte löschende Bereich, den ich noch nicht angesehen habe.

## Zyklus 13

- [x] **Loop Z — Bitraten-Bewertung und Optimierungs-Empfehlung**
      - [x] Nicht lesbare Dateien verschwanden lautlos aus der Wahrnehmung —
            jetzt Zählung mit Beispielen am Ende des Scans
      - [x] „CORRUPT" kommt im Code nirgends mehr vor; die Tiefenprüfung wurde
            für Scan-Geschwindigkeit entfernt → im Bericht
      - [x] `/api/candidates` schlug Dateien **anderer Konten** vor — aus
            dieser Liste heraus wird eingereiht und ersetzt
      - [x] Die Frage „welche Pfade darf dieses Konto sehen" steht jetzt in
            `core/user_scope.py` statt an jeder Stelle einzeln
      `Status` (OK/HIGH/SOURCE) entscheidet, was zum Optimieren vorgeschlagen
      wird — und optimieren heisst hier: Datei ersetzen. An 8788 echten
      Einträgen nachrechenbar.

- [x] **Loop AA — Der Scanner bei kaputten Dateien**
      - [x] Fehlt die Gesamtbitrate im Container, blieb der Eintrag bei 0 —
            und war damit für den gesamten Optimierungs-Weg unsichtbar
      - [x] Eine unlesbare Bilddatei verwarf den **gesamten Stapel** von bis
            zu 100 — dauerhaft, weil derselbe Stapel sie wieder enthält
      - [x] Kein Zeitlimit auf `sips`; der Video-Probe hatte längst eines
      `media_probe`, `video_inspector`, `image_inspector`. Was landet in der
      Bibliothek, wenn ffprobe nichts liefert, Unsinn liefert oder die Datei
      abgeschnitten ist? Eine Null an der falschen Stelle wandert von dort in
      jede Bewertung weiter.

## Zyklus 14

- [x] **Loop AB — Der Report-Dump**
      - [x] Geprüft: `ALL_VIDEOS` ist leer, nur ein Pfad wird eingebettet —
            die Mehrbenutzer-Trennung hält
      - [x] Die Kopfzeile bekam Anzahl und Größe der **gesamten** Bibliothek
            übergeben und benutzte beides nicht — eine Einladung
      - [x] **Der Hintergrund-Rescan scheiterte jedes Mal** an einer
            `model_dump()`-Zeile über bereits fertige Dicts — Cache blieb
            stehen, Report wurde nie erzeugt, „Rescan complete" nie gedruckt
      `index.html` wird auf die Platte geschrieben und von allen Konten
      geteilt. In Loop A war schon einmal Thema, dass dort nichts
      Nutzerspezifisches hineingehört. Jetzt die Erzeugung selbst: Was steht
      wirklich drin, und wann wird sie angestossen?

- [x] **Loop AC — Die verbliebenen Frontend-Dateien**
      - [x] `localStorage` wurde ungeschützt beim Laden gelesen — in der
            **ersten** Datei der Seite; ein gesperrter Speicher hätte gar keine
            Oberfläche ergeben
      - [x] Tag-Namen standen in `cinema.js` in interpolierten
            `onclick`-Attributen — ein Apostroph genügte, um den Knopf
            funktionsunfähig zu machen
      `cinema.js`, `store.js`, `collections.js`. Der Rest des Browser-Clients,
      den noch kein Loop angefasst hat.

## Zyklus 15

Zwei Themenfelder, die in vierzehn Zyklen nie an der Reihe waren — beide
betreffen den Kern des Werkzeugs: ein Inventar über Dateien, die es selbst
nicht kontrolliert.

- [x] **Loop AD — Wenn Dateien draußen verschwinden, umziehen oder umbenannt werden**
      Das Inventar steht in SQLite, die Wahrheit auf der Platte. Zwischen
      beiden liegt alles, was der Nutzer außerhalb der App tut: verschieben,
      umbenennen, Platte abhängen, Netzlaufwerk nicht gemountet. Was macht
      der Scanner daraus — und was macht die Oberfläche?
      - [x] Umzug = Datenverlust: Tags, Favoriten und Vault-Marke hängen am
            Pfad und wurden mit der verwaisten Zeile gelöscht
      - [x] Ein nicht eingehängtes Laufwerk stand nur im Protokoll — im
            Browser sah es aus wie eine kaputte Bibliothek
      - [x] `/stream` lieferte Dateien **ohne Anmeldung** aus
      - [x] Der Wiedergabe-Dialog schwieg, wenn die Datei nicht mehr da war
      - [x] TV-Client: `localStorage` an sechs Stellen ungeschützt, zwei davon
            im Rumpf der App-Komponente
      - [x] Optimieren verlor Favoriten, Vault und Tags — `film.mkv` wird
            `film.mp4`, und der Nutzerzustand hängt am Pfad

- [x] **Loop AE — Zeit: Zeitstempel, Zeitzonen, Sortierung nach Datum**
      Ein Inventar sortiert nach „neu". Woher kommt das Datum, in welcher
      Zeitzone steht es, und was passiert beim Rescan?
      - [x] „Sortieren: Datum" und „hinzugefügt: letzte 7 Tage" meinten zwei
            verschiedene Daten — Optimieren schob alte Filme nach oben
      - [x] Korrektur dazu: beide Fragen sind berechtigt, jetzt zwei Optionen
      - [x] `imported_at=0` bei Bildern ist **kein** Fehler — der Scanner
            stempelt es im gemeinsamen Block
      - [x] Sperrliste und Sitzungsliste wuchsen unbegrenzt — jeder
            Fehlversuch legte einen Eintrag an, der nie verschwand
      - [x] Was **während** eines Scans passiert, fiel dauerhaft durchs
            Raster — der Zeitstempel wurde am Ende genommen
      - [x] Alters-Anzeige der Warteschlange hörte bei Stunden auf, obwohl
            `formatRelativeTime()` seit jeher ungenutzt danebenlag
      - [x] Geprüft und in Ordnung: Datumsanzeige gibt es sonst nirgends
            (keine Zeitzonen-Frage), `_reclaim_stale_locked` deckt hängende
            Aufträge bereits ab (Loop N)

## Zyklus 16

- [ ] **Loop AF — Was passiert bei zwei gleichzeitigen Nutzern?** (läuft)
      Der Server ist ein ThreadingTCPServer, die Clients pollen. Loop W hat
      die Schreibpfade in der Benutzerdatenbank abgesichert; offen ist der
      Rest: gleichzeitige Scans, gleichzeitige Optimierungen derselben Datei,
      der geteilte Zwischenspeicher, gleichzeitige Anmeldungen.
      - [x] Eine Änderung während einer laufenden Anfrage ging verloren — der
            `/api/videos`-Cache hat keine Verfallszeit, also für immer
      - [x] Zwei Anfragen konnten zwei vollständige Scans starten
      - [x] Wer die Seite im falschen Moment lud, bekam eine halbe — der
            HTML-Dump wurde direkt in die ausgelieferte Datei geschrieben
      - [x] Zwei Anfragen konnten zwei Duplikat-Suchen starten — dieselbe
            Stelle wie beim Scanner, zweites Vorkommen
      - [x] **Verklemmung**: Schreibvorgang und `/api/similar` gleichzeitig
            konnten den Server dauerhaft anhalten
      - [x] Geprüft und stehen gelassen: Zwei **lokale** Optimierungen
            derselben Datei bleiben ungeschützt (siehe Bericht)

- [ ] **Loop AG — Die Grenzen: leer, eins, sehr viele**
      Was zeigt die Oberfläche bei null Einträgen, was bei einem, was bei
      hunderttausend? Was macht eine Datei ohne Endung, ein Ordner mit 50.000
      Dateien, ein Pfad an der Längengrenze des Dateisystems?

## Abschluss vor dem Morgen

- [x] Übergabebericht geschrieben: `NACHTLAUF-BERICHT.md` — sechs Punkte für
      Ralfs Entscheidung zuerst, dann Sicherheits- und Korrektheitsfunde,
      Performance-Messwerte, und ein Abschnitt „Was ich falsch hatte".

## Journal

<!-- Jede Iteration hängt hier eine Zeile an: was gemacht, was gelernt, was als Nächstes. -->

- **Iteration 95 (Loop AF, die Verklemmung — schwerster Fund des Laufs)** —
  `upsert()`, `bulk_upsert()` und `remove()` riefen `_notify_change()`
  **innerhalb** von `_write_lock`. Die Beobachter sind fremde Objekte mit
  eigenen Sperren, und `SimilarityCache` hielt seine genau dann, wenn er über
  `get_mean_vectors()` in die Datenbank hineinliest — also in die
  Schreibsperre. Zwei Threads, entgegengesetzte Reihenfolge, beide warten für
  immer. Und weil `_write_lock` dabei gehalten bleibt, steht danach *jeder*
  weitere Schreibvorgang: kein langsamer Server, ein toter. Auslöser genügt:
  jemand öffnet ein Video mit der Ähnlich-Leiste, während der Scanner
  schreibt. `store_embedding()` hat es von Anfang an richtig gemacht — die
  richtige Form stand also im selben Modul (vierter Fall dieser Nacht).
  Beide Richtungen begradigt: im Store ausserhalb der Sperre benachrichtigen,
  im Cache ausserhalb der eigenen Sperre lesen. Eine Verklemmung braucht beide
  Seiten; wer nur eine repariert, verlässt sich darauf, dass die andere so
  bleibt. Gegenprobe: Mit der alten Cache-Seite **hängt** der Test, statt zu
  scheitern — dasselbe wie beim alten `image_inspector` früher in dieser
  Nacht, und der Grund, warum ein `cp`-Rücksicherungsschritt danach nicht mehr
  lief. Ein AST-Test verbietet künftig jedes `_notify_change()` unter der
  Sperre, mit Gegenprobe an einem erfundenen Rückfall.

- **Iteration 94 (Loop AF, derselbe Fehler ein zweites Mal)** — Nachdem der
  Scanner sein `_claim()` hatte, war die Frage naheliegend: Wo steht dasselbe
  Muster noch? Die Duplikat-Suche: Route prüft `is_running`, Thread setzt es
  bedingungslos. Hier ist die Folge unangenehmer, weil beide Läufe in
  denselben Fortschritt und dieselbe Ergebnisliste schreiben — der Balken
  springt zwischen zwei Zählungen, und wer zuletzt fertig wird, überschreibt
  die Funde des anderen. Für den Nutzer sieht das aus, als hätte die Suche
  etwas übersehen. `try_begin()` setzt jetzt auch den Anfangszustand im selben
  Schritt; ein abgewiesener zweiter Aufruf ändert nichts, sonst spränge der
  Balken des laufenden auf null. Gelernt: Nach einem behobenen Fund ist „wo
  noch?" die billigste Frage der Nacht — sie hat diesmal zwei Zeilen Code
  gekostet und einen echten Fehler gefunden. Ein Test hält beide Stellen in
  derselben Form, damit die nächste Person nicht nur eine davon findet.
  Nächstes: gleichzeitige Anmeldungen und der Ähnlichkeits-Cache, dann AF
  schließen.

- **Iteration 93 (Loop AF, die halbe Seite)** — `generate_html_report()`
  schrieb mit `open(report_file, "w")` direkt in die Datei, die der Server
  unter `/` ausliefert. Das kürzt sie sofort auf null und füllt sie langsam
  wieder: Wer in diesem Fenster lädt, bekommt eine halbe Seite. Und erzeugt
  wird sie nach **jedem** Schreibvorgang — beim Scan-Ende systematisch dann,
  wenn alle Geräte etwas Neues erwarten. Jetzt daneben schreiben und tauschen,
  wie es `config.save()` und der Duplikat-Erkenner im selben Projekt längst
  tun (dritter Fall von „die Antwort lag schon im Repo"). Der Entpreller baut
  außerdem nicht mehr zweimal gleichzeitig.
  Zwei Dinge nebenbei gelernt: Mein Muster-Test ist zum siebten Mal über
  meinen eigenen Docstring gestolpert — der AST-Entkommentierer aus Loop AB
  ist inzwischen Standardwerkzeug. Und mein Nebenläufigkeits-Test war zu
  streng formuliert: Python vergibt die Nummer eines beendeten Threads wieder,
  fünf nacheinander laufende Threads können also denselben Namen tragen. Mit
  einer Schranke prüft er jetzt das, worauf es ankommt — *gleichzeitige*
  Schreiber. Geprüft und stehen gelassen: zwei lokale Optimierungen derselben
  Datei; ein Register mit Verfallszeit würde einen berechtigten zweiten
  Versuch nach einem Abbruch stundenlang blockieren. Steht im Bericht.
  Nächstes: Loop AF schließen, dann Loop AG (Grenzen).

- **Iteration 92 (Loop AF, zwei Scans auf einmal)** — `run_scan()` begann mit
  `if self.is_scanning: return` und `self.is_scanning = True` als zwei
  einzelnen Zeilen. Dazwischen kann ein anderer Thread laufen, und er tut es:
  Die Route prüft ihrerseits nur und startet dann einen eigenen Thread. Zweimal
  geklickt oder Fernseher und Browser kurz hintereinander — beide sahen „läuft
  nicht" und starteten je einen vollständigen Durchlauf über 8788 Dateien, mit
  doppelten ffprobe-Prozessen und zwei Schreibern auf derselben SQLite-Datei.
  Nachsehen und Belegen steckt jetzt in `_claim()` unter einer Sperre — als
  eigene Methode, damit der Test den **Weg des Ablaufs** prüfen kann und nicht
  eine Nachbildung davon. Genau das war der zweite Teil der Arbeit: Mein erster
  Test hatte das Muster im Testcode nachgebaut und wäre auch ohne die Sperre
  grün gewesen. Gelernt (zum zweiten Mal in diesem Lauf): Ein Test, der den
  richtigen Ablauf *nachbildet* statt ihn aufzurufen, prüft mein Verständnis,
  nicht den Code. Nächstes: weiter in Loop AF — gleichzeitige Optimierung
  derselben Datei.

- **Iteration 91 (Loop AF, die verlorene Invalidierung)** — `_MediaCache.get()`
  liest die Datenbank außerhalb des Locks — richtig so — und legte das Ergebnis
  danach bedingungslos ab. Passiert dazwischen ein `invalidate()`, ist es
  wirkungslos: Der überholte Stand landet trotzdem im Cache. Für den
  Medien-Cache heißt das 30 Sekunden alte Daten, für den daraus abgeleiteten
  `/api/videos`-Cache **für immer** — der hat keine Verfallszeit, er lebt
  allein von der Invalidierung. Genau die Umgebung, in der das eintritt, ist
  der Haushalt: Der Fernseher fragt regelmäßig ab, während im Browser gelöscht
  oder optimiert wird. Behoben mit einem Zähler, der jede Invalidierung
  mitzählt; wer beim Lesen überholt wurde, legt nichts ab und die Antwort geht
  trotzdem hinaus. Gelernt: Ein Lesevorgang außerhalb des Locks ist nicht das
  Problem — das bedingungslose *Zurückschreiben* danach ist es. Und ein Cache
  ohne Verfallszeit macht aus einem kurzen Fehler einen dauerhaften. Nächstes:
  weiter in Loop AF — gleichzeitige Scans und gleichzeitige Optimierung
  derselben Datei.

- **Iteration 90 (Loop AE abgeschlossen, die ungenutzte Antwort)** — Die
  Alters-Spalte der Warteschlange hörte bei Stunden auf; ein Auftrag vom April
  stand als „2952h ago" da. In `formatters.js` liegt seit jeher
  `formatRelativeTime()` mit Tagen, Wochen und Monaten — mit **null**
  Aufrufern im ganzen Projekt, während daneben in `settings.js` eine
  schlechtere Nachbildung stand. Dasselbe Muster wie beim gesperrten
  `localStorage` im TV-Client: Die Antwort lag im Repo, sie war nur nicht
  angewandt. Mitgenommen: ein Zeitstempel aus der Zukunft (falsch gestellte
  Uhr auf einem entfernten Arbeiter) ergab „-3 minutes ago". Damit ist AE
  ausgereizt: Datumsanzeigen gibt es sonst nirgends in der Oberfläche, also
  auch keine Zeitzonen-Frage; hängende Aufträge deckt `_reclaim_stale_locked`
  seit Loop N ab. Gelernt — und das gilt jetzt für zwei Funde dieser Nacht:
  „Gibt es dafür schon etwas, das keiner benutzt?" ist eine eigene Suchfrage,
  und sie findet Dinge, die kein Fehlerbericht liefert. Nächstes: Zyklus 16,
  Loop AF (Gleichzeitigkeit).

- **Iteration 89 (Loop AE, das Fenster während des Scans)** — Der Scanner
  überspringt Verzeichnisse, deren mtime älter ist als der letzte Durchlauf.
  Gemerkt hat er sich dafür den Zeitpunkt am **Ende**. Bei 8788 Dateien liegen
  zwischen Anfang und Ende Minuten, und was in dieser Zeit passiert, ist
  danach nicht bloß einmal verpasst, sondern für immer: Der Ordner-mtime von
  02:10 ist kleiner als der gemerkte Stand 02:30, also gilt der Ordner beim
  nächsten Mal als unverändert. Genau die Lage entsteht im Betrieb von selbst
  — der Fernarbeiter lädt optimierte Fassungen zurück, während der nächtliche
  Scan läuft. Gemerkt wird jetzt der Beginn: Das führt höchstens dazu, dass
  einmal zu viel nachgesehen wird. Gelernt: Bei einem Fenster zwischen zwei
  Zeitpunkten ist immer zu fragen, in welche Richtung der Fehler ausschlägt —
  zu viel prüfen kostet Zeit, zu wenig kostet Richtigkeit, und nur eines davon
  merkt man nicht. Nächstes: Loop AE schließen, Zyklus 16 planen.

- **Iteration 88 (Loop AE, Ablaufdaten, die niemand vollstreckt)** — Das
  Themenfeld heißt „Zeit", und der eigentliche Fund war keine Zeitzone, sondern
  eine Frist, die nirgends durchgesetzt wird. `record_failure()` legt bei jedem
  gescheiterten Anmeldeversuch einen Eintrag an; der Schlüssel kommt aus der
  Anfrage (`X-Forwarded-For` und der eingetippte Benutzername), und weg ging er
  nur bei einer erfolgreichen Anmeldung mit **demselben** Schlüssel. Für
  erfundene Werte nie. Damit konnte jeder, der den Anmeldeport erreicht, den
  Arbeitsspeicher unbegrenzt wachsen lassen — ohne Konto, mit gewöhnlichen
  Anfragen. Dabei war nichts an dieser Liste je dafür gedacht, länger als 900
  Sekunden zu leben. Beim Deckeln fliegen nicht gesperrte Einträge zuerst: Eine
  laufende Sperre hinauszudrängen wäre genau das Loch, das die Sperre schließen
  soll — dafür gibt es einen eigenen Test. Zweite, mildere Stelle: abgelaufene
  Sitzungen verfielen erst beim nächsten Vorzeigen ihres Tokens, bei einem
  vergessenen Gerät also nie. Gelernt: Wo ein Zeitfenster steht, gehört die
  Frage dazu, wer es vollstreckt — und dass eine Obergrenze selbst zur Lücke
  werden kann, wenn sie das Falsche verwirft. Nächstes: `cleanup_old_jobs` ist
  toter Code (nie aufgerufen) — nachsehen und im Bericht vermerken statt
  eigenmächtig Verlauf zu löschen.

- **Iteration 87 (Loop AE, Korrektur an mir selbst)** — Zwei Punkte auf der
  Liste, einer davon gegen die vorige Iteration.
  Erstens: `imported_at=0` im `image_inspector` ist kein Fehler. Der Wert wird
  im gemeinsamen Block in `manager.py` gestempelt, den Bilder und Videos
  gleichermaßen durchlaufen — ich hatte den Aufruf auf der Liste, ohne den
  Weg zu Ende gelesen zu haben. Nichts geändert.
  Zweitens, und wichtiger: Die Umstellung der Sortierung in Iteration 86 war
  zu kurz gedacht. Der Grund stimmte, die Folge nicht: Beim **ersten** Scan
  bekommen alle Dateien ihr `imported_at` binnen Minuten, die Reihenfolge
  innerhalb eines solchen Blocks ist die des Verzeichnisdurchlaufs — also
  keine. An der echten Bibliothek nachgesehen: 8788 Einträge auf zehn
  Import-Tage, aber 2858 allein am 07.08. Für die hätte ich „nach Datum" durch
  „nach Scan-Reihenfolge" ersetzt. Es sind eben zwei berechtigte Fragen
  („zuletzt hinzugefügt" gegen „neueste Aufnahme"); jetzt stehen beide im
  Auswahlfeld, der gespeicherte Wert `date` bleibt unverändert. Gelernt: Bevor
  man eine Regel vereinheitlicht, nachsehen, wie die Daten in der Praxis
  aussehen — die Verteilung entscheidet, ob aus einer Vereinheitlichung eine
  Verschlechterung wird. Nächstes: Aufräumfristen der Warteschlange und
  Sitzungsablauf.

- **Iteration 86 (Loop AE, zwei Daten unter einem Namen)** — Es gibt
  `imported_at` (erster Scan) und `mtime` (letzte Änderung). Drei Stellen —
  Datumsfilter, Sammlungen, deren Python-Port — benutzten dieselbe Regel:
  `imported_at`, ersatzweise `mtime`. Die vierte, die Sortierung, rechnete
  allein mit `mtime`, und in der Oberfläche heißen beide „Datum". Folge:
  Optimieren schreibt die Datei neu, also steht ein Film von 2019 danach unter
  „Sortieren: Datum" ganz oben — und mit dem Fernarbeiter kann das über Nacht
  die halbe Bibliothek betreffen. Umgekehrt findet man frisch Hinzugefügtes
  über die Sortierung nicht, obwohl der Filter es zeigt. Die Regel steht jetzt
  einmal als `entryDate()` in utils.js; der TV-Client führt sie als eigene
  Zeile mit (getrennter Build), ein Test hält beide Seiten zusammen. Gelernt:
  Drei gleiche Kopien und eine abweichende sehen beim Lesen aus wie vier
  richtige — was die Abweichung sichtbar macht, ist die Frage „meinen die
  eigentlich dasselbe?", nicht der Vergleich der Zeilen. Ein Test verbietet
  jetzt, die Regel erneut auszuschreiben. Nächstes: weiter in Loop AE —
  Zeitzonen und die Anzeige von Datumsangaben.

- **Iteration 85 (Loop AD, Optimieren = Umzug)** — Der Fund aus Iteration 80
  noch einmal, aber an einer Stelle, die man täglich benutzt: Beim Optimieren
  wird aus `film.mkv` die Datei `film.mp4`. Die Zeile in `media` wird sorgfältig
  übertragen — Größe, Codec, Aufnahmedatum. Favoriten, Vault und Tags liegen
  aber in `users.db` am Pfad, und der ändert sich. Für den Nutzer: dieselbe
  Datei, derselbe Name, ohne alles, was er daran gemacht hat. Zwei Stellen
  (`_replace_media_entry` für den Fernarbeiter, `keep_optimized` für den
  Handbetrieb) hatten denselben Mangel; der Prüfmodus ist durch Zufall heil,
  weil die behaltene Fassung an genau den Pfad zurückkehrt, auf dem der Zustand
  liegen geblieben ist — jetzt festgehalten, damit es nicht unbemerkt kippt.
  Gelernt: Eine Ursache ist erst dann erledigt, wenn man alle Stellen gesucht
  hat, an denen sich ein Pfad ändert — nicht nur die, an der man sie gefunden
  hat. Genau dafür war der Helfer aus Iteration 80 schon da. Nächstes: Loop AD
  schließen, dann Loop AE (Zeit).

- **Iteration 84 (Loop AD, der TV-Client)** — Beim Nachsehen, wie der
  TV-Client mit einer verschwundenen Datei umgeht, stand zwei Zeilen darüber
  etwas Größeres: `localStorage.getItem` im Rumpf der App-Komponente,
  ungeschützt. Insgesamt sechs Stellen in drei Dateien. Auf webOS kann der
  Speicher gesperrt sein — und der Client **weiß** das: In `serverConfig.js`
  steht seit jeher ein try/catch mit genau dieser Begründung im Kommentar. Eine
  Ausnahme im Rumpf einer React-Komponente heißt kein halb aufgebauter
  Bildschirm, sondern gar keiner, und auf einem Fernseher gibt es keine
  Konsole, in der man nachsähe. Derselbe Fund und dieselbe Lösung wie im
  Browser-Client (`safe_storage.js`, früherer Lauf) — beide Clients hatten ihn
  getrennt voneinander. Gelernt: Wenn eine Erkenntnis im Repo als Kommentar
  steht, aber nur an einer Stelle angewandt ist, ist das eine Fundstelle. Der
  Test sucht deshalb im ganzen `tv_client/src`, nicht in einer Dateiliste.
  Nächstes: der `<Video>`-Fehlerfall im TV-Client, dann Loop AE.

- **Iteration 82 (Loop AD, `/stream` ohne Anmeldung)** — Beim Nachsehen, ob
  `/stream` HEAD beantwortet (für die Fehlermeldung aus Iteration 83), stand
  der eigentliche Fund daneben: Die Route prüft `is_path_allowed()` und sonst
  nichts. Keine Sitzung, weder GET noch HEAD. Die Metadaten waren geschützt,
  die Oberfläche, die Benutzerdaten — die Dateien selbst nicht, und die sind
  der Zweck des Programms. Belegt am echten Handler: vorher 200 samt Inhalt,
  jetzt 401. Der Grund, warum es vierzehn Zyklen überlebt hat, ist der
  lehrreiche Teil: Der Rundum-Test über alle Routen sucht nach
  `self.path == "/api/…"`, und `/stream` wird per `startswith()` erkannt. Der
  Wächter hatte eine Formlücke und meldete deshalb Ruhe. Gelernt: Ein Test,
  der „alle X" prüft, ist nur so vollständig wie sein Begriff von X — das
  gehört mitgeprüft, nicht nur das Ergebnis. Offen gelassen und im Bericht
  vermerkt: `/thumbnails/` ist aus demselben Grund offen, eine Sitzungspflicht
  dort schaltet die Vorschaubilder im TV-Client ab. Das entscheidet Ralf.

- **Iteration 83 (Loop AD, der schweigende Wiedergabe-Dialog)** — Weder
  `<video>` noch `<img>` hatten einen error-Handler: fehlt die Datei, öffnet
  sich ein schwarzer Kasten und sonst nichts. Ein Netzlaufwerk, das nach dem
  Ruhezustand nicht wieder da ist, reicht dafür. Der Grund wird jetzt
  nachgeschlagen statt geraten — ein HEAD trennt „Datei weg" (404) von „Server
  sagt nein" (403) und von „Browser kann den Codec nicht" (200); kommt auch
  der HEAD nicht durch, bleibt es bei der allgemeinen Meldung. Gelernt: Drei
  Ursachen, die für den Nutzer identisch aussehen, aber völlig verschiedene
  Reaktionen verlangen — sie zu unterscheiden kostet eine Anfrage. Nächstes:
  Loop AD schließen oder noch offene Punkte? Danach Loop AE (Zeit).

- **Iteration 81 (Loop AD, das abgehängte Laufwerk)** — Der Scanner erkennt
  den Fall seit Loop M und schützt sich richtig davor: kein Aufräumen, keine
  gelöschten Einträge. Gesagt hat er es nur dem Protokoll. Wer den Server als
  Dienst laufen lässt, sieht stattdessen eine vollständige Bibliothek, in der
  jedes Video einen Fehler wirft — und sucht dann bei Codecs, Streaming und
  Rechten, während die Antwort ein Pfad ist, den es gerade nicht gibt. Gelernt:
  Ein Programm, das eine Störung korrekt behandelt, hat sie damit noch nicht
  *mitgeteilt*; die beiden Dinge sind getrennt zu prüfen. `GET /api/settings`
  meldet die fehlenden Ziele jetzt mit — ausdrücklich nur die des eigenen
  Kontos, aus demselben Grund wie bei `FOLDERS_DATA` in Loop AB. Bei einem
  Fehler beim Nachsehen (hängender Mount) wird geschwiegen statt gewarnt.
  Nächstes: weiter in Loop AD — was macht die Wiedergabe mit einer Datei, die
  zwischen Scan und Klick verschwunden ist?

- **Iteration 80 (Loop AD, Umzüge)** — Der Aufräumschritt nach dem Scan war
  schon zweimal Thema (Loop M), und beide Male ging es darum, wann er
  *nichts* löschen darf. Übersehen wurde der Fall, in dem er zu Recht löscht
  und trotzdem Schaden anrichtet: Datei umbenannt. Der Kommentar an der Stelle
  benennt den Verlust sogar selbst — „user state that no rescan can restore" —
  und wurde bisher als Begründung fürs Vorsichtigsein gelesen, nicht als
  offenes Problem. Ordnung in einer Mediathek *besteht* aus Umbenennen und
  Verschieben; der Nutzer verliert also genau beim Aufräumen die Arbeit, die er
  vorher hineingesteckt hat. Erkannt wird der Umzug an dem, was er nicht
  verändert: Größe, mtime, Laufzeit. Nur eindeutige Paare — eine falsche
  Zuordnung hinge fremde Tags an, eine fehlende kostet nur das, was ohnehin
  weg war. Gelernt: Ein Kommentar, der einen Verlust beschreibt, ist eine
  Fundstelle, keine Entwarnung. Nächstes: weiter in Loop AD — was zeigt die
  Oberfläche bei nicht eingehängtem Laufwerk?

- **Iteration 79 (Loop AC, Tag-Namen im Cinema — Loop AC abgeschlossen)** — Ein
  früherer Lauf hat dieses Muster an fünf Stellen behoben; `cinema.js` blieb
  übrig, obwohl neun andere Dateien `escapeHtml()` benutzen und diese hier gar
  nicht. Tag-Namen und -Farben standen in interpolierten `onclick`-Attributen.
  Der harmlose Fall genügt schon: Ein Tag namens „Ralfs Auswahl" beendet die
  JavaScript-Zeichenkette im Attribut, und der Knopf tut nichts mehr.
  Der lehrreiche Teil war die naheliegende Lösung, die **nicht** funktioniert
  hätte: `escapeHtml()` darüberziehen. Der Browser dekodiert Entitäten im
  Attributwert, *bevor* der Inhalt als JavaScript gelesen wird — aus `&#39;`
  würde wieder ein Apostroph, und der Knopf bliebe kaputt. Der richtige Weg
  stand längst in `tag_manager.js`: Knoten bauen, `textContent` setzen, Handler
  per `addEventListener`. Dann gibt es gar keinen Attributstring, in den etwas
  hineingeraten könnte. Gelernt: Maskieren ist kein Universalmittel, sondern
  eine Antwort auf **einen** Kontext; verschachtelte Kontexte (JS in HTML) lässt
  man besser gar nicht erst entstehen. Nächstes: Zyklus 15 planen.

- **Iteration 78 (Loop AC, gesperrter Speicher)** — `localStorage` wirft in
  manchen Browsern schon beim **Lesen** (blockierte Cookies, privater Modus).
  Der Browser-Client las es ungeschützt an drei Stellen beim Laden, darunter in
  `store.js` — dem ersten Skript der Seite. Eine Ausnahme dort ergibt keine
  halb geladene Oberfläche, sondern gar keine. Der TV-Client fängt genau diesen
  Fall seit jeher ab, mit Begründung im Kommentar; der Browser-Client nicht.
  Dazu ein zweiter, unabhängiger Weg ins Aus: ein `JSON.parse` über einen
  gespeicherten Wert ohne Netz, das die Sammlungsansicht bei jedem Aufruf
  erneut lahmgelegt hätte.
  Mein erster Entwurf legte den Helfer in `store.js` — und liess damit **25
  Tests** auflaufen, die einzelne Frontend-Dateien bewusst für sich laden. Zur
  Laufzeit hätte es gehalten (store.js steht vorn), aber eine stillschweigende
  Ladereihenfolge-Abhängigkeit in einem Projekt ohne Modulsystem ist genau die
  Art Fessel, die man später nicht mehr sieht. Jetzt eine eigene Datei
  `safe_storage.js` als erstes Skript, und die Reihenfolge steht ausdrücklich
  im Template und in einem Test. Gelernt: Dass die Tests einzelne Dateien
  isoliert laden, ist kein Testartefakt, sondern die einzige Stelle, an der
  eine solche Abhängigkeit überhaupt auffällt. Nächstes: cinema.js.

- **Iteration 77 (Loop AB, der Rescan-Weg — Loop AB abgeschlossen)** — Der
  Faden aus der vorigen Iteration führte weiter, als ich dachte. Nachdem
  `results` in `generate_html_report()` unbenutzt war, habe ich die fünf
  Aufrufer angesehen: Jeder beschaffte den Wert mit
  `[e.model_dump(by_alias=True) for e in db.get_all()]` — 8788 Pydantic-Modelle
  plus 8788 Umwandlungen, für nichts. **An einer Stelle lief es über
  `media_cache.get()`, das bereits Dicts liefert.** Dort warf die Zeile jedes
  Mal einen `AttributeError`, das umgebende `except` machte daraus ein
  „❌ Rescan failed" — nachdem der Scan längst durch war —, und die zwei Zeilen
  danach wurden nie erreicht: Der Medien-Cache blieb stehen, der Report wurde
  nicht neu erzeugt, „✅ Rescan complete." nie gedruckt. Der Fehler ist damit
  behoben, indem der Parameter verschwand: Es gibt nichts mehr zu beschaffen.
  Gelernt: Toter Code ist nicht nur Ballast — er wird gefüttert, und das
  Füttern kann kaputtgehen, ohne dass jemand den Verlust bemerkt, weil das
  Ergebnis ohnehin niemand liest. Die Trennung ist jetzt strukturell statt
  verhaltensbasiert: Man *kann* dem Dump keine Einträge mehr übergeben.
  Nächstes: Loop AC (cinema.js, store.js, collections.js).

- **Iteration 76 (Loop AB, Report-Dump)** — Zuerst nachgesehen statt vermutet:
  In der erzeugten `index.html` ist `ALL_VIDEOS` tatsächlich leer, und von 23
  eingebetteten Einstellungen ist genau eine ein Pfad (`proxy_root`). Die
  Trennung hält. Der Fund liegt eine Ebene daneben: `render_header()` bekam
  `count` und `size_gb` übergeben — die Zahlen der **gesamten** Bibliothek, für
  eine Datei, die einmal erzeugt und an jedes Konto ausgeliefert wird — und
  benutzte beides nicht; die Kopfzeile rendert `...` und wird zur Laufzeit
  gefüllt. Ich war beim Lesen selbst kurz davor, daraus ein Leck zu schliessen.
  Genau das ist die Gefahr: Wer die Platzhalter „repariert", indem er die
  vorhandenen Argumente einsetzt, baut das Leck. Argumente und die dafür
  gerechnete Gesamtsumme sind jetzt weg, und ein Test hält die Eigenschaft
  fest. Zum sechsten Mal heute Nacht ist dabei mein eigener Erklärkommentar
  über eine eigene Prüfung gestolpert — der Test dort arbeitet jetzt über den
  AST, wo Kommentare gar nicht erst vorkommen. Nächstes: wann der Report
  angestoßen wird.

- **Iteration 75 (Loop AA, Bild-Inspektor — Loop AA abgeschlossen)** — Der
  Inspektor fasst bis zu 100 Dateien in einen `sips`-Aufruf. Das ist gut für
  die Geschwindigkeit und macht zwei Fehler teuer. Erstens: `sips` liefert
  einen Fehlerkode, sobald **eine** Datei nicht lesbar ist — schreibt die
  Eigenschaften der übrigen aber trotzdem nach stdout. Verworfen wurden alle.
  Ein einziges defektes Bild konnte damit bis zu 99 andere **dauerhaft** aus
  der Bibliothek halten, weil derselbe Stapel beim nächsten Scan dieselbe
  kaputte Datei enthält. Zweitens fehlte jedes Zeitlimit, obwohl der
  Video-Probe zwei Dateien weiter genau dafür eines hat — samt Begründung, dass
  der Prozess danach eingesammelt werden muss. Hier wiegt es schwerer: An einem
  Aufruf hängen bis zu 100 wartende Futures.
  Der Beleg war deutlicher als geplant: Gegen den alten Stand **hängt die
  Test-Suite**, statt fehlzuschlagen. Ich musste den Lauf abbrechen und die
  Datei von Hand zurückspielen. Gelernt: Wenn eine Datei zwei Dateien weiter
  eine Lehre aufgeschrieben hat, ist die Frage nicht, ob sie hier auch gilt,
  sondern warum sie noch nicht gezogen wurde. Nächstes: Zyklus 14 planen.

- **Iteration 74 (Loop AA, fehlende Bitrate)** — `media_probe` ist sorgfältig
  gebaut: `_as_float`-Helfer überall, Division geprüft, „N/A" pro Feld
  abgefangen, und der Kommentar begründet auch warum („a single such field must
  zero itself, not cost the whole file"). Genau eine Lücke blieb: Meldet der
  Container gar keine Gesamtbitrate, bleibt der Wert 0 — und das ist keine
  Kleinigkeit, weil `estimate_heuristic()` bei `source_kbps <= 0` sofort
  aussteigt und auch die HIGH/SOURCE-Einstufung nicht greift. Die Datei ist
  damit für den ganzen Optimierungs-Weg unsichtbar, ohne dass irgendwo etwas
  fehlt. In Ralfs Bibliothek trifft es genau **eine von 8788** — die Rechnung
  aus Größe und Dauer ergibt dort 6,29 Mbps. Gelernt beim Testschreiben: Ich
  hatte 6,0 erwartet und MiB mit MB verwechselt; der Unterschied sind 4,9 %,
  genug um eine Einstufung an einer Schwelle kippen zu lassen. Die Rechnung
  steht jetzt ausgeschrieben im Test. Nächstes: image_inspector und
  Zeitüberschreitungen.

- **Iteration 73 (Loop Z, Optimierungs-Vorschläge — Loop Z abgeschlossen)** —
  `/api/candidates` hatte genau dieselben zwei Lücken wie `/api/similar`, Zeile
  für Zeile: `if u and u.data.vaulted` als Fail-Open, und Vorschläge aus dem
  gesamten Bestand statt aus den eigenen Zielen. Der Unterschied liegt in der
  Folge — bei der Ähnlichkeitssuche ist es eine Preisgabe, hier wird aus der
  Liste heraus **eingereiht**, und Einreihen heisst, dass die Datei ersetzt
  wird. Ein Zweitkonto konnte also die Neukodierung fremder Dateien anstossen.
  Weil ich dieselbe Regel damit zum dritten Mal geschrieben hätte, steht sie
  jetzt in `core/user_scope.py` — abgeleitet aus `/api/videos`, nicht neu
  erfunden. Gelernt: Dass zwei Routen denselben Fehler in derselben
  Formulierung haben, ist kein Zufall, sondern ein Hinweis, dass die Frage nie
  an einer Stelle beantwortet wurde. Zwei eigene Testfehler unterwegs: Der
  Antwortschlüssel heisst `results`, und meine Attrappen lieferten für
  `optimized_at` etwas Wahres — damit übersprang `build_candidates()` jeden
  Eintrag, und es sah aus wie ein Filterfehler. Nächstes: Loop AA (Scanner bei
  kaputten Dateien).

- **Iteration 72 (Loop Z, unlesbare Dateien)** — Eine Iteration, in der ich
  mich fast selbst hereingelegt hätte. Die Statusverteilung zeigt 13 Einträge
  mit „CORRUPT", und „CORRUPT" kommt im gesamten Code nicht mehr vor — die
  Tiefenprüfung wurde für Scan-Geschwindigkeit entfernt, sagt der Kommentar in
  `media_probe.py`. Ich prüfte, ob die 13 Dateien noch existieren: keine
  einzige. Beinahe hätte ich das als Fund gemeldet — dann habe ich die
  **gesamte** Bibliothek geprüft, und es sind **alle 8788**. Die Medienpfade
  sind auf diesem Rechner schlicht nicht eingehängt. Gelernt, zum zweiten Mal
  heute Nacht (nach den 1141 Vorschaubildern): Ein Ergebnis, das zu gut zur
  These passt, gehört gegen die Gesamtmenge geprüft, nicht gegen die
  Erwartung. Nebenbei hat der `unavailable_targets`-Schutz im Scanner damit
  seine Berechtigung eindrücklich bewiesen.
  Der echte Fund: Schlägt die Untersuchung fehl, steht dazu eine Zeile im
  Protokoll — bei tausenden Dateien längst weggescrollt, wenn der Scan fertig
  ist. Und das Ergebnis ist leise: Ein bekannter Eintrag behält seine **alten**
  Angaben, ein neuer entsteht gar nicht. Jetzt zählt der Scan sie und nennt sie
  am Ende. Nächstes: die Schwellenwerte und der optimization_advisor.

- **Iteration 71 (Loop Y, Wartungsfunktionen — Loop Y abgeschlossen)** — Drei
  Funde in 91 Zeilen, die vorher keinen Test hatten und Dateien löschen. Der
  folgenreichste: Die Sicherheitsprüfung fragte, ob der **Name** des
  Datenverzeichnisses „arcade_data" enthält. In Docker heisst es `/config` —
  also brach dort jede Wartung still ab, `--rebuild` und `--cleanup` taten
  nichts, ohne dass es so aussah. Ich habe die Prüfung ersetzt durch die, die
  gemeint war: kein Wurzel-, kein Home-Verzeichnis. Das ist eine Änderung an
  einer Sicherheitsprüfung auf einem Löschpfad, und ich schreibe sie deshalb
  ausdrücklich in den Bericht — die eigentliche Begrenzung leistet ohnehin
  `is_safe_to_delete()`. Zweitens stand in beiden Funktionen dasselbe
  Verzeichnis zweimal in der Zielliste; der Docstring versprach „thumbnail and
  preview directories", und ein Vorschau-Verzeichnis gibt es im Code nirgends.
  Drittens verglich `is_safe_to_delete()` ohne Verzeichnisgrenze — die fünfte
  Fundstelle derselben Rechnung heute Nacht, jetzt alle auf
  `security.path_is_within()`. Gelernt: Eine Sicherheitsprüfung, die den
  *Namen* eines Pfads liest statt seiner Lage, prüft eine Verabredung und keine
  Eigenschaft — und Verabredungen gelten nur, bis jemand in Docker startet.
  Nebenbei: `process_video()` hat keinen Aufrufer. Nicht gelöscht, in den
  Bericht.

- **Iteration 70 (Loop X, Ähnlichkeitssuche — Loop X abgeschlossen)** — Ich
  hatte den Loop begonnen mit dem Verdacht, die Funktion sei tot: null Zeilen
  in beiden Embedding-Tabellen. Sie ist es nicht — der Index wird von
  `scripts/media_indexer.py` gebaut, das bewusst eigenständig ist und
  `torch`/`open_clip` nur verzögert lädt; das Extra `[indexer]` gibt es, das
  Skript läuft auch ohne ML-Stack, und `/api/similar/status` sagt genau
  deshalb, wie viel indexiert ist. Alles wie entworfen.
  Die Funde lagen woanders: Die Treffer kamen aus dem **gesamten** Index, also
  auch aus den Scan-Zielen anderer Konten — mit vollem Pfad in der Antwort.
  Und `if u and u.data.vaulted` hiess: Fällt der Nutzerdatensatz aus, wird
  nichts ausgeschlossen, und Vault-Pfade stehen im Klartext in der Antwort.
  Dritter Fund beim Beheben: Die Rechnung „liegt Pfad in Verzeichnis" steht an
  vier Stellen im Projekt, **dreimal** ohne Verzeichnisgrenze — `/media` schloss
  also `/media_nas` und `/media_ralf` mit ein. Jetzt eine gemeinsame
  `path_is_within()`. Gelernt: Ein Verdacht, der sich nicht bestätigt, ist kein
  verlorener Loop — ich war nur deshalb an dieser Datei, weil ich etwas anderes
  vermutet hatte. Nächstes: Loop Y (Wartungsfunktionen).

- **Iteration 69 (Loop W, die übrigen Wege — Loop W abgeschlossen)** — Tags,
  Einstellungen und Auto-Tag-Regeln laufen jetzt ebenfalls über `update_user()`.
  Zwei davon prüfen vor dem Schreiben und antworten mit einem Fehler („Tag gibt
  es schon", „Regel nicht gefunden"); diese Prüfungen gehören mit unter die
  Sperre, sonst stellen zwei gleichzeitige Anfragen beide fest, dass es den Tag
  noch nicht gibt. Der **Auto-Tagger** bleibt bei `add_user()`, und das ist die
  Entscheidung, nicht die Bequemlichkeit: Er liest oben, geht über die gesamte
  Bibliothek und schreibt unten — das Fenster mit einer Sperre zu schliessen
  hiesse, sie über einen kompletten Durchlauf zu halten. Mein erster Versuch
  kopierte die Felder in einem Änderer zusammen; das sah aus wie eine Lösung
  und hätte eine zwischenzeitliche Änderung genauso überschrieben, nur
  unsichtbarer. Zurückgenommen und die Begründung hingeschrieben.
  Beim Umbau fielen **drei Test-Attrappen** auf, die `update_user()` nicht
  kannten: MagicMock gibt stumm etwas Wahres zurück, der Änderer läuft nie —
  die Tests wären grün geblieben, ohne die Route zu prüfen. Jetzt gibt es
  `tests/fake_user_store.py` als eine Stelle dafür.
  Und beim Anfassen von `settings.py` stand dort ein xfail aus einem früheren
  Nachtlauf: `POST /api/settings` schrieb die globalen Einstellungen *vor* der
  Sitzungsprüfung. Der Befund stimmte und war nie behoben worden — jetzt schon.
  Nächstes: Zyklus 12 planen.

- **Iteration 68 (Loop W, verlorene Änderungen)** — Die geteilte
  SQLite-Verbindung habe ich per AST durchgezählt: 67 Zugriffe, 27 davon ohne
  Sperre — und alle 27 erklärbar (Verbindungsaufbau, Methoden mit `_locked` im
  Namen, Startmigration). Das doppelte Prüfen in `_ensure_connection()` ist
  sauber gebaut. Der Fund lag im **anderen** Store: `user_store` öffnet je
  Aufruf eine eigene Verbindung, hatte aber gar keine Sperre — und der übliche
  Ablauf im Server ist `get_user()` → ändern → `add_user()`, wobei `add_user()`
  den *gesamten* Datensatz als ein JSON-Feld zurückschreibt. Bei einem
  ThreadingTCPServer heisst das: Wer zuletzt schreibt, gewinnt alles.
  Nachgemessen mit 60 gleichzeitigen Favoriten: **4 kamen an, 56 gingen
  verloren.** Gelernt: Ich hatte den ganzen Loop auf die geteilte Verbindung
  ausgerichtet, weil dort die Kommentare stehen — die Gefahr lag dort, wo
  niemand einen Kommentar hinterlassen hatte. `update_user()` hält jetzt eine
  wiedereintrittsfähige Sperre über Lesen, Ändern und Schreiben; danach 60 von
  60. Umgestellt sind die vier Wege mit dem meisten Verkehr (Favorit und Vault,
  einzeln und als Stapel); Tags, Einstellungen und Auto-Tag-Regeln stehen noch
  aus und sind als offene Liste in einem Test festgehalten. Nächstes: diese
  vier Wege umstellen.

- **Iteration 67 (Loop V, Sortierung — Loop V abgeschlossen)** — Die
  Standard-Sortierung des TV-Clients heisst „newest" und war
  `sorted.reverse()`. Umgedreht wird damit die Reihenfolge von `/api/videos`,
  und die ist `SELECT * FROM media` ohne `ORDER BY` — also die
  Einfügereihenfolge des ersten Scans. An der echten Bibliothek gemessen:
  Unter „newest" standen Aufnahmen vom Oktober 2025, die tatsächlich neuesten
  sind vom August 2026, **null Überschneidung in den ersten zehn**. Und weil es
  die Vorgabe ist, war genau das beim Einschalten zu sehen. Derselbe Denkfehler
  in „Zuletzt hinzugefügt": `slice(-48)` nahm die letzten 48 Datenbankzeilen.
  Gelernt: `reverse()` sieht aus wie eine Sortierung und ist keine — es
  sortiert nach nichts, es dreht nur um, was ohnehin schon dastand. Der
  Browser-Client rechnete an derselben Stelle immer `b.mtime - a.mtime`.
  Login-Pfad und Sammlungs-Matcher habe ich mitgeprüft: Anmeldedaten sind
  gitignored und werden per prebuild als Dummy erzeugt, der Matcher schliesst
  Vault-Videos bereits aus. Die Server-Adresse im Login-Bildschirm bleibt
  offen — ohne `node_modules` liesse sich die Oberfläche hier weder bauen noch
  linten, und ungeprüfte JSX-Zeilen wären dasselbe Scheinergebnis wie beim
  iOS-Client. Nächstes: Loop W (Nebenläufigkeit).

- **Iteration 66 (Loop V, TV-Client)** — Die erste Frage an den zweiten Client
  war die, die ich gerade beim ersten beantwortet hatte — und die Antwort war
  dieselbe: Fällt `/api/user/data` aus, bleibt `v.hidden` undefined, und jeder
  der vier Filter prüft `!v.hidden`. Der gesamte Vault stand auf der
  Startseite; auf einem Fernseher im Wohnzimmer. Besonders unauffällig, weil die
  Vault-Ansicht dann leer ist — es sah aus, als sei nichts versteckt, statt als
  sei etwas kaputt. Gelernt: Ein Fund in einem Client ist eine Frage an alle
  anderen, und genau dafür lohnt der Loop.
  Zweiter Fund, beim Absichern: **`node --check` prüft ESM-Dateien überhaupt
  nicht** — `import x from 'y'; const a = (((;` kommt mit Rückgabewert 0 durch
  (node 26). Für die 28 Dateien in `static/` stimmt der Test heute noch, weil
  keine Modul-Syntax benutzt; ich habe das durch Anhängen eines Syntaxfehlers
  an jede einzelne nachgemessen. Ein einziges `import` würde die Prüfung
  stillschweigend wertlos machen — der Test prüft jetzt sich selbst.
  Nächstes: Login-Pfad und Sortierung des TV-Clients.

- **Iteration 65 (Loop U, drei Verdachtsfälle — Loop U abgeschlossen)** — Die
  erste Iteration dieser Nacht ohne Korrektur, und das ist das Ergebnis, nicht
  ein Ausbleiben davon. Drei Stellen sahen nach Fehlern aus: Die Paarbildung
  überschreibt gleiche Stämme in einer Map (folgenlos — aus zwei Dateien ohne
  `_opt`-Suffix entsteht ohnehin kein Paar). Die `_opt`-Erkennung sucht im
  ganzen Pfad statt im Dateinamen (an der echten Bibliothek nachgezählt: 94
  Treffer, alle im Dateinamen, kein einziger über einen Ordner; zwei ohne
  Suffix-Bedeutung — enger zu fassen hiesse zu entscheiden, was „optimiert"
  heisst, und das steht Ralf zu). Und die Spalten `vaulted`/`favorite` in der
  Medientabelle tragen die Aliasse `hidden`/`favorite`, also genau die Namen,
  die das Frontend pro Nutzer überschreibt — das sah nach einem Leck zwischen
  Konten aus, alle 8788 Zeilen tragen dort aber 0. Gelernt: Der Unterschied
  zwischen „sieht falsch aus" und „ist falsch" kostet jedes Mal eine Messung,
  und ohne sie hätte ich hier dreimal etwas verschlimmbessert. Die Messungen
  stehen als Tests da, damit sie niemand ein zweites Mal machen muss — der zu
  `vaulted`/`favorite` schlägt an, sobald jemand anfängt, dorthin zu
  schreiben. Nächstes: Zyklus 11 planen.

- **Iteration 64 (Loop U, Vault-Sichtbarkeit)** — `loadUserData()` setzt
  `v.hidden` aus `/api/user/data`. Schlägt der Aufruf fehl, protokolliert die
  Funktion das und kehrt zurück; `v.hidden` bleibt `undefined`, und
  `const isHidden = v.hidden || false` macht daraus „nicht versteckt". Ein
  einzelner Serverfehler hätte also den gesamten Vault im normalen Raster
  ausgebreitet — dieselbe Richtung des Fehlers wie beim abgesicherten Modus in
  Iteration 42. Die Sperre sitzt in `filterAndSort()` und nicht an der
  Aufrufstelle: Am Ende von engine.js steht ein `setTimeout(..., 500)`, das
  noch einmal filtert; ein früher Abbruch wäre eine halbe Sekunde später
  überholt worden. Gelernt beim Testschreiben, und zwar zweimal: Mein Harness
  benutzte falsche Namen für die globalen Filterzustände — und weil
  `filterAndSort()` in einem `try/catch` liegt, das jeden Fehler in einen Toast
  verwandelt, sah der ReferenceError aus wie „alles herausgefiltert". Fünf
  Tests waren grün gewesen, ohne etwas zu prüfen. Der Harness bricht jetzt ab,
  sobald der Toast anschlägt; gegengeprüft, indem ich einen Namen wieder
  entfernt habe. Nächstes: Paarbildung im „Optimiert"-Modus.

- **Iteration 63 (Loop T, Aufräumen — Loop T abgeschlossen)** — Verwaiste
  Vorschaubilder werden jetzt dort entfernt, wo der Scanner ohnehin verwaiste
  Einträge entfernt: hinter denselben Schutzbedingungen (vollständiger Scan,
  erreichbare Ziele). Der Unterschied zum Nutzerzustand, den ich in Iteration 51
  bewusst **nicht** an den Scan gehängt habe, ist der Preis eines Irrtums: Ein
  Vorschaubild ist jederzeit neu berechenbar, ein Tag nicht. Dieselbe Stelle,
  zwei verschiedene Antworten, und beide stehen begründet im Code. Die
  Namensbildung liegt dabei nicht mehr inline in `create_thumbnail()`, sondern
  in `thumbnail_name_for()` — wer das Bild zu einem Pfad *finden* will, musste
  die Rechnung sonst nachbauen, samt `surrogateescape` für Windows-Pfade mit
  kaputten Zeichen. Ralfs 1141 Altlasten sind davon unberührt; sie stehen im
  Bericht. Nächstes: Loop U (Filter im Frontend).

- **Iteration 62 (Loop T, Vorschaubilder)** — Der Name ist `md5(pfad)`, also
  hängt er am Pfad und nicht am Inhalt; erneuert wurde nur, wenn die Datei
  fehlte oder leer war. Ein optimiertes oder zugeschnittenes Video behielt sein
  altes Bild damit für immer — und weil eine Vorschau immer irgendwie plausibel
  aussieht, merkt das niemand. Für die Proxys ist dieselbe Frage längst
  beantwortet (`is_proxy_stale`, samt Toleranz gegen ungenaue mtimes); für die
  Vorschaubilder galt sie nicht. Zum wiederholten Mal dasselbe Muster.
  Nebenbei gemessen: Von 1141 Bildern auf der Platte gehört **keines** zu einem
  der 8788 Einträge — 17,3 MB für Pfade, die es nicht mehr gibt. Ich habe die
  Messung gegen das gespeicherte `thumb`-Feld gegengeprüft, weil ein so glattes
  Ergebnis eher nach Messfehler aussieht als nach Befund; die berechneten Namen
  stimmen exakt. Angefasst habe ich nichts. Ausserdem: Der Traversal-Schutz der
  Auslieferung verglich per `startswith` ohne Verzeichnisgrenze — derselbe
  Fehler, den ich heute Nacht schon in `is_path_allowed()` behoben habe.
  Nächstes: Aufräumen verwaister Bilder beim Entfernen verwaister Einträge.

- **Iteration 61 (Absicherung der Test-Suite)** — Die mtime-Prüfung nach der
  vorigen Iteration schlug an: `users.db` war angefasst worden. Verursacher war
  mein eigener Test — `apply_configuration()` holt sich `user_db` **innerhalb**
  ihres Rumpfes aus dem Modul, und diese Instanz zeigt seit dem Import auf das
  echte Datenverzeichnis. Ein Patch von `config.HIDDEN_DATA_DIR` erreicht sie
  nicht. Daten nachgeprüft: unversehrt (Admin weiterhin 9 Favoriten, 1
  Vault-Marke, 93 Tags, 6 Tag-Definitionen, Ziele `/media` und `/media_nas`) —
  es war ein identisches Neuschreiben derselben Zeile. Gelernt: Ein Patch wirkt
  dort, wo nachgeschlagen wird, nicht dort, wo importiert wurde; und genau
  deshalb ist die mtime-Prüfung nach jeder Iteration kein Ritual. In
  `conftest.py` steht jetzt eine autouse-Sperre, die Schreibzugriffe auf das
  gemeinsame `user_db`-Singleton sofort scheitern lässt — sie hat den einen
  Übeltäter beim ersten Lauf gefunden. Suite danach dreimal durchlaufen,
  `arcade_data` unverändert. Nächstes: Zyklus 10 planen.

- **Iteration 60 (Loop S, Speichern — Loop S abgeschlossen)** — `apply_configuration`
  hatte die Lese-mischen-Schreiben-Logik ein zweites Mal, mit eigenem
  `json.dump` und damit ohne die Zwischendatei aus Iteration 54. Beim Umbauen
  auf `config.save()` fiel der eigentliche Fund an: Die Methode meldet **immer**
  Erfolg. `_save_json_raw()` fängt seine Fehler selbst ab, und `save()`
  verwarf das Ergebnis — obwohl beide Aufrufer in `routes/settings.py` genau
  daran hängen (`if config.save(...)`). Bei voller Platte stand in der
  Oberfläche „gespeichert", während auf der Platte der alte Stand lag; im
  Arbeitsspeicher der neue, also stimmte es bis zum nächsten Neustart sogar.
  Gelernt: Ein `except`, das nur druckt, verwandelt einen Fehler in eine
  Meinung — und wer den Rückgabewert nicht führt, kann ihn oben auch nicht
  prüfen, so richtig die Prüfung dort aussieht. Ausserdem richtiggestellt: Der
  Assistent **sagt** das Standardpasswort `admin` an und fordert zum Wechsel
  auf; ich hatte es im Bericht schärfer formuliert, als es ist. Nächstes:
  Zyklus 10 planen.

- **Iteration 59 (Loop S, Erstlauf)** — 532 Zeilen ohne einen einzigen Test,
  und sie entscheiden, was gescannt wird, legen das Admin-Konto an und bieten
  an, sämtliche Datenbanken zu löschen. Zwei Wege führten über eine
  **bestehende** Installation: `should_run_wizard()` beantwortete jede
  Leseausnahme mit „frische Installation" (`except Exception: return True`) —
  zusammen mit dem gekürzten Schreiben aus Iteration 54 genügte ein
  Stromausfall beim Speichern. Und ohne Terminal lief der Assistent nicht etwa
  auf einen Fehler, sondern **still durch**: `prompt()` fängt EOFError ab und
  liefert den Vorgabewert, also beantwortet er sich mit stdin auf /dev/null
  jede Frage selbst und schreibt anschliessend die Konfiguration. Nachgemessen.
  Gelernt: Ein defensiv gemeintes `except` ist eine Aussage über die Welt — hier
  „ich kann die Datei nicht lesen, also gibt es hier nichts". Der bessere Beleg
  lag danebenan: Es liegen Datenbanken da. Der Löschzweig selbst war nie das
  Problem, er hängt an einer ausdrücklichen Rückfrage mit Vorgabe „nein"; das
  Problem war, dass die Frage überhaupt gestellt wurde. Nächstes:
  `apply_configuration`.

- **Iteration 58 (Loop R, Regelumfang)** — `video_matches({})` gibt `True`
  zurück, und das ist für Smart Collections genau richtig: „nichts
  eingeschränkt" heisst „alles zeigen". Dieselbe Funktion trägt aber auch die
  Auto-Tag-Regeln, und dort heisst dieselbe Antwort: schreibe den Tag an jede
  Datei der Bibliothek — bei Ralf 8788 — und weil jeder Tag nur einmal vergeben
  wird, nur einzeln von Hand wieder abnehmbar. Erreichbar nicht nur über ein
  leeres Objekt: Ein Kriterium mit ausschliesslich unbekannten Schlüsseln, also
  ein Tippfehler, passt ebenfalls auf alles. Gelernt: Eine geteilte Funktion
  erbt ihre Vorgabe, nicht ihren Kontext — „keine Angabe" bedeutet beim Anzeigen
  etwas Harmloses und beim Schreiben etwas Endgültiges. Die Auswertung bleibt
  unangetastet; geprüft wird jetzt beim Anlegen der Regel. Nebenbei lag ich bei
  `{"search": "   "}` falsch — das passt auf fast nichts statt auf alles; der
  Test hat es gezeigt und hält es jetzt fest. Nächstes: Loop S (Erstlauf).

- **Iteration 57 (Loop R, Auto-Tagging)** — Der erste Fund dieser Nacht, den
  ich selbst verursacht habe. Der Auto-Tagger vergibt jeden Tag nur einmal je
  (Nutzer, Regel, Pfad); diese Buchführung hängt am Pfad. Solange auch die Tags
  liegen blieben, war das stimmig: Datei weg, Tag noch da, Regel greift nicht
  mehr. Seit Iteration 51 die Tags beim ausdrücklichen Löschen aufräumt, fielen
  beide auseinander — entsteht später eine Datei unter demselben Pfad, hätte
  sie keinen Tag und bekäme auch keinen mehr, weil die Regel sich für erledigt
  hält. Gelernt: Ich habe in Iteration 51 nach *allem* gesucht, was am Pfad
  hängt, und dabei nur in den Nutzerdaten nachgesehen — die zweite Stelle liegt
  in der Mediendatenbank. Eine Aufräumung ist nur so vollständig wie die Suche
  danach, was sonst noch an derselben Kennung hängt. Beide Schritte stehen
  jetzt beieinander, und ein Test besteht darauf. Nächstes: die Regelauswertung
  selbst.

- **Iteration 56 (Loop Q, Validator)** — Die Auslieferung schickte weder `ETag`
  noch wertete sie `If-Range` aus. Für einen gewöhnlichen Dateiserver wäre das
  lässlich; hier verbergen sich unter derselben Adresse zwei verschiedene
  Dateien — der Optimierer ersetzt Originale an Ort und Stelle, und bei
  eingeschaltetem Proxy-Streaming entscheidet die *Netzwerkadresse des Clients*
  zwischen Original und Proxy. Wer beim Springen einen Bereich nachforderte,
  bekam Bytes aus der Datei, die jetzt dort liegt, ohne merken zu können, dass
  es eine andere ist. Anders als der verkürzte Stream aus Iteration 55 fällt
  das nicht als Hänger auf, sondern als Bildfehler mitten im Video. Gelernt:
  Zwei Funde in Folge aus derselben Wurzel — die Adresse identifiziert hier
  keine feste Datei, und das Protokoll hat für genau diesen Fall einen
  Mechanismus, der schlicht nicht benutzt wurde. Nächstes: die
  Proxy-Entscheidung selbst.

- **Iteration 55 (Loop Q, verkürzte Streams)** — Die Range-Behandlung ist gut
  gebaut und gut getestet; die Kommentare warnen ausdrücklich davor, eine
  falsche `Content-Length` anzukündigen, weil ein Keep-Alive-Client sonst ewig
  wartet. Genau dieser Zustand entsteht trotzdem — nur nicht durch falsches
  Rechnen, sondern weil `socket.sendfile()` bei einer zwischenzeitlich
  gekürzten Datei einfach weniger liefert. Mit einem echten Socket-Paar
  nachgemessen: 100 statt 10000 Bytes, ohne Ausnahme, ohne Fehlerwert.
  Erreichbar ist das hier ganz konkret, weil der Optimierer Mediendateien an
  Ort und Stelle ersetzt. Gelernt: Eine Zusage, die man selbst richtig
  berechnet, kann trotzdem gebrochen werden — von der Wirklichkeit zwischen
  `stat()` und `send()`. Verhindern lässt es sich nicht; jetzt wird die
  Verbindung geschlossen und die Verkürzung gemeldet, statt den Client hängen
  zu lassen. Nächstes: Proxy-Entscheidung LAN/Tailscale.

- **Iteration 54 (Loop P, Haltbarkeit — Loop P abgeschlossen)** — Wenn schon
  Datensicherung, dann auch die Frage, ob die Einstellungsdatei einen
  schlechten Moment übersteht. Zwei Fehler, die zusammen greifen: Geschrieben
  wurde mit `open(..., "w")`, das die Datei sofort auf null kürzt — und ein
  nicht lesbares `settings.json` wurde beim nächsten Start durch die
  Standardwerte **ersetzt**. Ein Stromausfall beim Speichern plus ein Neustart
  genügten also, um Theme, Schwellen, ffmpeg-Pfade und `proxy_root` still auf
  Werkseinstellung zu setzen. Und wieder dasselbe Muster wie in den
  Iterationen 43, 46, 47 und 50: `duplicate_detector.py` schreibt seinen Cache
  seit jeher über eine Zwischendatei — mit genau dieser Begründung im Kommentar
  („a crash mid-write would otherwise leave a truncated JSON file"). Für die
  Datei, die ungleich schwerer zu ersetzen ist, galt sie nicht. Jetzt
  tmp + fsync + `os.replace`, und ein defektes `settings.json` wird als
  `.corrupt` beiseitegelegt statt überschrieben. Nächstes: Loop Q
  (Auslieferung, Range-Requests, Proxy-Entscheidung).

- **Iteration 53 (Loop P, Datensicherung)** — Der Einstellungsbereich
  „Backup & Restore" hat zwei Knöpfe, und beide zeigten auf Routen, die es im
  Server nie gab (`/api/user/export`, `/api/user/import`) — eingeführt in einem
  reinen Frontend-Commit, die Gegenstücke wurden nie geschrieben. Gleichzeitig
  existiert `/api/backup`, funktioniert, und hatte keinen einzigen Aufrufer.
  Die Beschriftung im Dialog nennt sogar den Dateinamen, den genau diese Route
  setzt — der Export war eine falsch verdrahtete Leitung, kein fehlendes
  Stück. Repariert. Der Import bleibt offen: Eine Route, die eine hochgeladene
  Datei über die Einstellungen schreibt, ist löschend, und ihre Bedeutung ist
  eine Entscheidung. Steht als dokumentierte Ausnahme in der Prüfliste, nach
  dem Muster von `DYNAMIC_IDS`. Gelernt (zum dritten Mal heute Nacht): Meine
  eigenen Erklärkommentare nennen das kaputte Ziel beim Namen und stehen damit
  vor dem richtigen — Muster-Tests gehören grundsätzlich auf entkommentierten
  Text. Nächstes: Was in der Sicherung fehlt, in den Bericht.

- **Iteration 52 (Loop O, Empfehlung — Loop O abgeschlossen)** — Die
  Re-Encode-Erkennung lässt den Codec-Bonus bewusst weg, weil der moderne
  Codec dort die verlustbehaftete Kopie kennzeichnet. Gut überlegt — und
  dadurch bleibt bei zwei 4K-Dateien nur noch Bitrate und Auflösung übrig. Der
  Bitratenanteil ist aber bei 50 Punkten gedeckelt, also ab 25 Mbps: Eine
  80-Mbps-Quelle und ihr 26-Mbps-Re-Encode bekommen beide 85,0. Nachgerechnet,
  nicht geschätzt. Bei Punktgleichstand entschied die stabile Sortierung, also
  die Reihenfolge aus der Datenbank — bei Re-Encodes genau die Frage, um die es
  geht. Gelernt: Wer einen Term absichtlich entfernt, sollte prüfen, ob die
  verbleibenden noch trennscharf sind. Der Deckel bleibt, damit sich die
  Punktwerte nicht verschieben; bei Gleichstand entscheiden jetzt Bitrate,
  Größe, Pfad. Nebenbei: Mein Test „Auflösung schlägt Bitrate" wurde rot — sie
  tut es nicht, 50 gegen 30 Punkte. Bestehendes Verhalten, nicht angefasst,
  aber im Bericht. Nächstes: Zyklus 8 planen.

- **Iteration 51 (Loop O, Nutzerzustand beim Löschen)** — `db.remove()` löscht
  die Zeile in `media`; Favoriten, Tags und Vault-Marken hängen aber am Pfad
  und blieben liegen. In Ralfs Daten stehen dadurch bereits 12 Tag-Einträge,
  zwei Favoriten und eine Vault-Marke auf Pfaden, die es nicht mehr gibt — der
  Fund liess sich also direkt an den echten Daten belegen. Der eigentliche
  Schaden ist nicht das Anwachsen, sondern die **Wiederverwendung**: Beim
  Optimieren entsteht aus `film.mkv` wieder `film.mp4`, also genau der Name der
  gelöschten Datei — und die neue erbt stillschweigend deren Zustand. Ein
  Video, das einmal versteckt war, ist sofort wieder versteckt, ohne dass
  irgendwo steht, warum. Gelernt: Zustand, der an einem Namen hängt statt an
  einer Sache, überlebt die Sache. Aufgeräumt wird nur bei **ausdrücklichen**
  Löschungen, nicht beim Aufräumen verwaister Einträge nach einem Scan — dort
  warnt der Code selbst, dass ein Scan sich irren kann. Nächstes:
  `recommended_keep` bei Gleichstand.

- **Iteration 50 (Loop O, Bild-Duplikate)** — Der Video-Zweig filtert mit der
  Signatur nur vor und vergleicht danach die Bytes; der Kommentar sagt es
  wörtlich: „Verify with content sampling to avoid false positives". Der
  Bild-Rückfallweg hatte denselben Aufbau, aber nicht den zweiten Schritt — er
  erklärte alles mit gleicher Auflösung und auf 10 KB gleicher Dateigröße zum
  `match_type="exact"` mit Konfidenz 0,95, in einer Oberfläche mit Löschknopf.
  Für eine Fotosammlung ist das kein Grenzfall, sondern der Normalfall.
  Gelernt: Zwei Zweige mit gleichem Aufbau lesen sich wie zwei Zweige mit
  gleicher Sorgfalt. `_verify_by_content_sample()` war medienneutral und stand
  direkt daneben — bei Bildern unter 1 MB liest sie die Datei sogar ganz.
  Nächstes: `recommended_keep` und was beim Löschen mit Favoriten und Tags
  passiert.

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
