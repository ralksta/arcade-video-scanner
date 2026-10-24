# Umsetzungsplan

Reihenfolge für die neun Entscheidungen aus `ENTSCHEIDUNGEN.md`.
Aufgestellt am 17.08.2026. **Nichts davon ist umgesetzt.**

Die Reihenfolge folgt drei Regeln:

1. **Erst löschen, dann bauen.** Was ohnehin verschwindet, wird nicht vorher
   noch angefasst. Der Vault steckt in Dateien, die vier andere Punkte
   ebenfalls berühren — ihn zuerst zu entfernen erspart doppelte Arbeit.
2. **Abhängigkeiten vor Abhängigem.** Die Wiederherstellung braucht das
   Sicherungsformat und das Beenden von Sitzungen; beides kommt vorher.
3. **Risiko nach hinten.** Die einzige löschende Neuentwicklung steht am Ende,
   wenn der Rest stabil ist.

---

## Vor jeder Phase

- Eigener Branch pro Phase, von `dev` abgezweigt. Eine Phase, ein Branch, ein
  abgeschlossener Zustand.
- `.venv/bin/pytest` und `.venv/bin/ruff check .` grün, bevor etwas gemerged
  wird.
- **Vor Phase 2, 4 und 5:** `arcade_data/users.db` von Hand kopieren. Diese
  drei Phasen fassen Nutzerdaten an, und eine Sicherung gibt es (bis Phase 5)
  nur als `cp`.
- Der Branch `feat/nightly-loops` mit den 145 Commits aus dem Nachtlauf ist
  noch nicht gemerged. **Das gehört zuerst geklärt** — alle Phasen unten
  setzen auf diesem Stand auf.

---

## Phase 0 — Aufräumen ohne Risiko

**Punkte 1 und 5.** Kein Produktionscode, keine Datenberührung. Zuerst, weil es
die Liste kürzt und den Kopf frei macht.

### 0.1 iOS-Client zurückziehen (Punkt 1)

- `ios_client/` entfernen; letzten Commit-Hash in der Commit-Nachricht nennen.
- `dev-docs/ios-client-status.md` behalten, um einen Satz zum Rückzug ergänzen.
- Angleichen: `CLAUDE.md` („Drei native Clients"), `README.md`, `ROADMAP.md`,
  `tests/test_client_endpoint_contract.py`, `tests/test_claude_md_accuracy.py`.

**Fertig, wenn:** kein Test und kein Dokument mehr einen funktionierenden
iOS-Client behauptet.

### 0.2 Release-Notes 7.0.0 rekonstruieren (Punkt 5)

- Entwurf aus den Commits zwischen letztem 6.x-Eintrag und 7.0.0.
- **Erst an Ralf**, dann einchecken. Ohne diese Runde ist es eine Vermutung.
- Vermerk in `tests/test_version_consistency.py` anpassen.

**Fertig, wenn:** der Abschnitt steht und von Ralf gegengelesen ist.

---

## Phase 1 — Vault entfernen (Punkt 4)

Die größte Einzelmaßnahme und deshalb früh: Sie **löscht** Code, den die Phasen
2, 3 und 5 sonst mitschleppen würden.

**Betroffen:** 10 Backend-Dateien, 9 JS-Module, beide Template-Dateien, der
TV-Client (`MainPanel.js`, 8 Stellen) und 20 Testdateien.

**Reihenfolge innerhalb der Phase:**

1. Backend: Feld, Routen, Filterlogik. `vaulted` aus `UserVideoData`,
   `VideoEntry`, `MediaAsset`; Vault-Zweige in `routes/files.py`,
   `candidates.py`, `duplicates.py`, `similar.py`.
2. Browser-Client: `cinema.js`, `cards.js`, `context_menu.js`,
   `batch_operations.js`, `filter_engine.js`, `shortcuts.js`, `engine.js`,
   `workspace.js`, `empty_state.js`; Templates.
3. TV-Client: `MainPanel.js` — dort hängt `v.hidden` an acht Stellen, unter
   anderem an der Vault-Ansicht selbst.
4. Tests: die 20 Dateien durchgehen. Was den Vault prüft, wird **entfernt**,
   nicht auskommentiert. `test_vault_visibility.py`, `test_tv_vault_guard.py`
   und `vault_guard_harness.js` verlieren ihren Gegenstand ganz; andere
   (`test_moved_files.py`, `test_user_state_after_optimize.py`) verlieren nur
   ihre Vault-Anteile.

**Bewusst in Kauf genommen:** Die drei aktuell versteckten Dateien (`admin` 1,
`privat` 2) werden sichtbar. So entschieden.

**Offen bei der Umsetzung:** ob `vaulted` per Migration aus `users.db`
verschwindet oder unbenutzt stehenbleibt. Stehenlassen ist rückholbar.

**Nicht vergessen:** Der abgesicherte Modus (`sensitive_tags`,
`sensitive_dirs`, `sensitive_collections`) bleibt. Er ist in Benutzung
(`admin`: 8 Tags, 1 Collection) und eine **andere** Funktion.

> **Hier lohnt eine Zwischenfrage.** Diese Phase erzwingt ohnehin einen neuen
> TV-Client-Build. Damit wird der saubere Weg für Punkt 9 (Token in
> `thumbnailUrl()` anhängen, Route ganz schließen) fast kostenlos — die
> Entscheidung „nur für Nicht-LAN" fiel, *weil* ein TV-Build teuer schien.
> Bevor Phase 6 gebaut wird: Ralf fragen, ob er den sauberen Weg jetzt lieber
> mitnimmt.

**Fertig, wenn:** kein `vaulted`/`hidden` mehr in Produktionscode und Tests,
Suite grün, TV-Client gebaut und auf dem Gerät geprüft.

---

## Phase 2 — Gespeicherte Ansichten pro Nutzer (Punkt 2)

Nach Phase 1, weil beide dieselben Stellen berühren (`models/user.py`,
`routes/settings.py`).

- `saved_views` in `UserVideoData`, neben `smart_collections`.
- In die Zuweisungsliste in `handle_get_settings` aufnehmen — dort fehlt es.
- **Migration:** Bestehende globale Ansichten gehen an den Admin. Darf nur
  **einmal** laufen, sonst kehren gelöschte Ansichten zurück (Muster:
  `cleanup_legacy_settings()`).
- Schreibpfad über `user_db.update_user(name, mutate)`, nicht get + add.
- Die Falle der leeren Hüllen gilt auch hier: Ein Client, der `saved_views`
  nicht mitschickt, darf die Liste nicht löschen.

**Fertig, wenn:** zwei Konten unterschiedliche Ansichten haben und keines die
des anderen sieht; die Migration ein zweites Mal nichts tut.

---

## Phase 3 — Escaping, priorisiert (Punkt 6)

Nach Phase 1, weil dort JS-Module verschwinden, die sonst mitgeprüft würden.

- Vorlage: `dev-docs/frontend-escaping.md`, nach Herkunft sortiert (Tag-,
  Ordner-, Sammlungsnamen, Suchbegriffe).
- **Kein pauschales `escapeHtml()`** — wo schon maskiert wird, entsteht sonst
  `&amp;lt;` auf dem Bildschirm.
- Bevorzugter Weg: Knoten bauen, `textContent`, `addEventListener` — wie in
  `tag_manager.js` und `cinema.js`. In einem `onclick`-Attribut hilft
  HTML-Maskierung ohnehin nicht, weil der Browser Entitäten dekodiert, bevor
  der Inhalt als JavaScript gelesen wird.
- Abgearbeitete Stellen per Test festschreiben.
- Der ungeprüfte Rest bleibt in der Doku stehen, damit „87" nicht als erledigt
  gilt.

**Fertig, wenn:** jede Stelle, an der ein Wert aus einer Eingabe stammen kann,
entweder umgebaut oder als unbedenklich begründet ist.

---

## Phase 4 — Konten (Punkt 8)

**Vor Phase 5**, weil die Wiederherstellung das Beenden von Sitzungen braucht.

### 4.1 Sitzungen eines Nutzers beenden

- `SessionManager` kennt `revoke_session(token)`; gebraucht wird „alle
  Sitzungen dieses Nutzers".
- Server-Route dafür — das CLI-Skript läuft in einem eigenen Prozess und
  kommt an den Arbeitsspeicher des Servers nicht heran.
- Beim Passwortwechsel automatisch auslösen. Der Fall, um den es geht: Du
  wechselst, *weil* das Passwort abhandengekommen ist.

### 4.2 Konto löschen und Rechte entziehen

- `scripts/manage_users.py` um `delete` und Rechte-Entzug erweitern.
- Löschen muss den Nutzerzustand mitnehmen (Favoriten, Tags, Scan-Ziele) —
  sonst bleibt er liegen wie die Pfade vor `purge_paths_from_user_data()`.
- Das letzte Admin-Konto darf sich nicht selbst entrechten oder löschen.

### 4.3 Passwortwechsel erzwingen

- Merker im Nutzerdatensatz („Passwort nie geändert"), **nicht** ein Vergleich
  gegen `admin` — sonst greift es auch, wenn jemand `admin` bewusst setzt.
- Abbruchfall: Wer den Wechsel wegklickt, behält keine angemeldete Sitzung.
- Docker-Onboarding hängt mit dran (`create_default_admin` setzt dort
  `setup_complete = False`).
- Solange `create_default_admin` bei jedem Start läuft, ist „`admin` löschen"
  aus 4.2 für genau diesen Namen eine Illusion. Das gehört zusammen gedacht.

**Fertig, wenn:** ein frisch aufgesetzter Server ohne Wechsel nicht benutzbar
ist, ein Konto löschbar ist und ein Passwortwechsel fremde Sitzungen beendet.

---

## Phase 5 — Sicherung und Wiederherstellung (Punkt 7)

Zuletzt unter den Funktionen, weil die Wiederherstellung die einzige löschende
Neuentwicklung ist und auf allem Vorherigen aufsetzt: Das Datenmodell muss
stehen (Phasen 1 und 2), das Beenden von Sitzungen muss es geben (Phase 4).

### 5.1 Inhalt erweitern (7a)

- `settings.json` + `users.db`, als Archiv statt nackter JSON-Datei.
- Dateiname im Dialog mitändern (heute `arcade_settings_backup.json`).
- `users.db` nicht mitten im Schreiben kopieren — SQLite-Backup-API oder unter
  der vorhandenen Schreibsperre.
- Im Dialog hinschreiben, dass die Sicherung jetzt **Passwort-Hashes**
  enthält, und dass die Bibliothek nicht dabei ist (ein Scan baut sie neu).

### 5.2 Wiederherstellung (7b)

Bedeutung: „zurück auf den Zeitpunkt X" — vollständig ersetzen.

- **Erst den Ist-Zustand automatisch sichern**, mit Zeitstempel. Ohne das ist
  die Entscheidung eine Einbahnstraße.
- Warnung **mit Zahlen** vor dem Ausführen: wie viele Konten und Einträge
  ersetzt werden.
- **Die Falle:** `scan_targets`, `exclude_paths`, `available_tags` und die
  `sensitive_*`-Listen stehen in `settings.json` als leere Hüllen, die echten
  Werte in `users.db`. Der Einstellungs-Handler unterscheidet „nicht
  angegeben" von „leer" und schreibt Letzteres durch — diese Schlüssel müssen
  beim Einspielen **übersprungen** werden, sonst löscht die Wiederherstellung
  genau das, was sie herstellen soll.
- Sitzungspflichtig **und** admin-pflichtig (sie ersetzt fremde Konten mit).
- Danach Sitzungen verwerfen (Phase 4.1) und Caches neu laden, sonst zeigt die
  Oberfläche den alten Stand.

**Fertig, wenn:** ein Durchlauf Sicherung → etwas ändern → Wiederherstellung
den Ausgangszustand ergibt, und ein Import ohne die vier Schlüssel nichts
löscht.

---

## Phase 6 — Vorschaubilder für Nicht-LAN schließen (Punkt 9)

Klein und unabhängig. Steht nach hinten, weil die Zwischenfrage aus Phase 1 sie
überflüssig machen kann.

- LAN/Tailscale-Unterscheidung aus `core/proxy_resolver.py` **mitbenutzen**,
  nicht nachbauen — sonst laufen zwei Begriffe von „lokal" auseinander.
- Die Client-Adresse darf **nicht** aus `X-Forwarded-For` kommen. Genau
  darüber war die Brute-Force-Sperre aushebelbar; sonst genügt eine erfundene
  Kopfzeile für „ich bin im LAN".
- Ausnahmeliste in `tests/test_stream_requires_session.py` anpassen: aus
  „bewusst offen" wird „offen nur im LAN", mit Test für beide Fälle.

**Fertig, wenn:** eine Anfrage von außerhalb ohne Sitzung 401 bekommt, eine aus
dem LAN weiterhin das Bild — und ein gefälschter Header daran nichts ändert.

---

## Phase 7 — Tailwind und Schriften lokal (Punkt 3)

Bewusst allein und zuletzt: Diese Phase bringt einen Build-Schritt ins Projekt
und verändert das Aussehen jeder Seite. Mit etwas anderem vermischt ist eine
Regression nicht mehr zuzuordnen.

1. **Schriften zuerst** — klein, sofort wirksam (auch auf der Anmeldeseite vor
   dem Login), unabhängig prüfbar.
2. **Dann Tailwind.** Vorgebautes CSS einchecken, CDN entfernen.
3. **Test gegen die stille Falle:** aus den Templates die verwendeten Klassen
   ziehen und gegen das gebaute CSS prüfen. Ohne den wirkt eine neue Klasse
   ohne Neubau einfach nicht — und das fällt nur dem auf, der genau hinsieht.
4. Build-Befehl in `CLAUDE.md` unter „Commands" dokumentieren.
5. Erst **danach** eine Content-Security-Policy verschärfen. Solange ein CDN
   nötig ist, müsste sie ihn erlauben, und eine Regel mit Ausnahme für genau
   das Problem ist keine.
6. README und `dev-docs/external-resources.md` nachziehen — die dort
   präzisierte Einschränkung wird danach wieder falsch, nur andersherum.

**Fertig, wenn:** das Dashboard mit getrenntem Internet vollständig und
formatiert lädt.

---

## Was dieser Plan nicht enthält

Aus dem Nachtlauf sind zwei Themenfelder offen geblieben. Sie sind keine
Entscheidung, sondern unerledigte Arbeit:

- **Loop AF** (Gleichzeitigkeit) war nicht ausgereizt — gleichzeitige
  Anmeldungen sind ungeprüft.
- **Loop AG** (Grenzen: null Einträge, ein Eintrag, sehr viele; Datei ohne
  Endung, Ordner mit 50.000 Dateien, Pfad an der Längengrenze) hat nie
  begonnen.

Beides lässt sich jederzeit einschieben und hängt an keiner der Phasen.
