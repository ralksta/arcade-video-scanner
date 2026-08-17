# Entscheidungen zum Nachtlauf

Ralfs Antworten auf die offenen Punkte aus `NACHTLAUF-BERICHT.md`.
Aufgenommen am 17.08.2026. **Nichts davon ist umgesetzt** — diese Datei hält
nur fest, was gelten soll, damit die Umsetzung später nicht wieder von vorn
diskutiert werden muss.

Stand: 5 von 9 Punkten entschieden.

---

## 1. Der iOS-Client — **zurückziehen**

Der Client ist seit dem Entfernen der DeoVR-Routen funktionsunfähig (404 auf
jede Bibliotheksabfrage) und schickt zusätzlich keine Sitzung mit, stammt also
aus der Zeit vor der Mehrbenutzer-Umstellung. Zwei getrennte Baustellen, ohne
Mac und Xcode nicht prüfbar.

**Entschieden:** zurückziehen.

Was das bei der Umsetzung heißt — und was dabei ausdrücklich zu klären ist:

- `ios_client/` aus dem Arbeitsbaum entfernen. Der Code bleibt in der
  Git-Historie und ist jederzeit rückholbar; der letzte Commit vor dem
  Entfernen sollte in der Commit-Nachricht genannt werden, damit man ihn
  wiederfindet.
- `dev-docs/ios-client-status.md` **behalten** und um einen Satz ergänzen, dass
  der Client zurückgezogen wurde und warum. Das Dokument beschreibt beide
  Brüche und den Reparaturweg — es ist das, was eine spätere Rückholung
  braucht.
- Erwähnungen prüfen und angleichen: `CLAUDE.md` („Drei native Clients"),
  `README.md`, `ROADMAP.md`, sowie `tests/test_client_endpoint_contract.py` und
  `tests/test_claude_md_accuracy.py`, die den Client kennen.
- Offen gelassen, weil nicht gefragt: ob der Ordner ersatzlos verschwindet oder
  als `ios_client/` mit einer README-Datei „eingestellt, siehe dev-docs"
  stehenbleibt. Beides erfüllt die Entscheidung; ersteres ist sauberer,
  letzteres auffindbarer.

---

## 2. Gespeicherte Ansichten — **pro Nutzer trennen**

`saved_views` lebt global, während sieben vergleichbare Felder längst pro Konto
getrennt sind. Eine Ansicht enthält Suchbegriff, Ordnerpfad, Filter und
Sortierung; jeder angemeldete Nutzer sieht (und überschreibt) damit die
Ansichten der anderen.

**Entschieden:** `saved_views` wandert in die Nutzerdaten.

Was bei der Umsetzung zu beachten ist:

- Das Feld gehört in `UserVideoData` (`arcade_scanner/models/user.py`), neben
  `smart_collections`, und in die Zuweisungsliste in
  `routes/settings.py::handle_get_settings` — genau dort fehlt es heute.
- **Migration:** Bestehende globale Ansichten dürfen nicht verschwinden. Sie
  gehen an den Admin; wenn du sie stattdessen an alle Konten kopiert haben
  willst, muss das vorher festgelegt werden. Die Migration darf nur **einmal**
  laufen (sonst tauchen gelöschte Ansichten wieder auf) — dasselbe Muster wie
  bei `cleanup_legacy_settings()`.
- Beim Speichern gilt die Falle aus Punkt 7: Der Einstellungs-Handler
  unterscheidet „nicht angegeben" von „leer" und schreibt Letzteres durch. Ein
  Client, der `saved_views` nicht mitschickt, darf die Liste nicht löschen.
- Schreibpfad über `user_db.update_user(name, mutate)`, nicht get + add —
  sonst gehen bei gleichzeitigen Anfragen Änderungen verloren (Loop W).
- Der TV-Client kennt gespeicherte Ansichten nicht; dort ist nichts zu tun.

---

## 3. Cloudflare und Google — **beides lokal**

Das Dashboard lädt Tailwind von `cdn.tailwindcss.com` und Schriften von Google,
bei jedem Aufruf und auch auf der Anmeldeseite vor dem Login. Hinaus gehen IP,
User-Agent und Nutzungszeitpunkt; der Tailwind-CDN liefert zusätzlich
ausführbares JavaScript in die angemeldete Sitzung.

**Entschieden:** Schriften mitliefern **und** Tailwind durch vorgebautes CSS
ersetzen. Danach läuft das Dashboard vollständig ohne Internet.

Was bei der Umsetzung zu beachten ist:

- Reihenfolge: erst die Schriften (klein, sofort wirksam, unabhängig testbar),
  dann Tailwind. Der Weg nach Aufwand sortiert steht in
  `dev-docs/external-resources.md`.
- **Der Build-Schritt ist die eigentliche Änderung.** Das Projekt hat bewusst
  keinen; ein vorgebautes `styles.css` bringt einen ein — mit der stillen
  Falle, dass eine neu verwendete Tailwind-Klasse ohne Neubau einfach nicht
  wirkt. Dagegen braucht es einen Test, der aus den Templates die verwendeten
  Klassen zieht und gegen das gebaute CSS prüft; sonst fällt es erst im
  Browser auf, und dort nur dem, der genau hinsieht.
- Das gebaute CSS gehört eingecheckt (kein Bundler zur Laufzeit), und der
  Build-Befehl in `CLAUDE.md` unter „Commands" dokumentiert.
- Content-Security-Policy erst danach verschärfen — solange ein CDN nötig ist,
  müsste sie ihn erlauben, und eine Regel mit Ausnahme für genau das Problem
  ist keine.
- README/`dev-docs` anpassen: Die dort präzisierte Einschränkung wird nach der
  Umstellung wieder falsch, nur in die andere Richtung.

---

## 4. Bottom-Nav / Vault — **Vault als Funktion entfernen**

Gefragt war, ob Vault zurück in die Bottom-Nav soll (der Grund für seinen
Rauswurf war weggefallen). Die Antwort geht weiter: Die Funktion soll ganz weg.
Damit erübrigt sich die Nav-Frage — der Ordner-Browser behält seinen Platz.

**Entschieden:** Vault entfernen. Die aktuell versteckten Dateien werden dabei
**einfach wieder sichtbar**; keine Überführung in sensitive Tags, keine
Vorab-Liste.

Was dabei bekannt sein muss:

- **Der Vault ist in Benutzung.** Stand 17.08.2026 in `users.db`:
  `admin` 1 Eintrag, `privat` 2 Einträge. Diese drei Dateien erscheinen nach
  dem Umbau normal in der Bibliothek des jeweiligen Kontos. Das ist so
  gewollt.
- **Vault und abgesicherter Modus sind zwei verschiedene Funktionen.** Der
  Vault versteckt einzelne Dateien pro Konto; der abgesicherte Modus blendet
  Kategorien aus (`sensitive_tags`, `sensitive_dirs`, `sensitive_collections`).
  Letzterer ist ebenfalls in Benutzung (`admin`: 8 sensitive Tags, 1 sensitive
  Collection) und **bleibt bestehen**. Nur der Vault fällt.
- **Umfang:** `vaulted` bzw. `hidden` steckt in 10 Backend-Dateien, 9
  JS-Modulen, beiden Template-Dateien, dem TV-Client (`MainPanel.js`) und 20
  Testdateien. Das ist ein eigener Umbau, kein Aufräumen nebenbei.
- Offen und bei der Umsetzung zu entscheiden: ob das Feld `vaulted` in
  `users.db` per Migration verschwindet oder unbenutzt stehenbleibt.
  Stehenlassen ist ungefährlich und rückholbar; entfernen ist sauberer, aber
  eine Einbahnstraße.
- Beim Umbau fallen zwei Funde dieser Nacht mit weg, weil ihr Gegenstand
  verschwindet: der Vault-Ausfall bei einem Serverfehler (`v.hidden || false`
  in beiden Clients) und die Vault-Anteile der Umzugs- und
  Optimier-Umtragung. Die Tests dazu gehören dann mit entfernt — nicht
  auskommentiert.

---

## 5. Release-Notes zu 7.0.0 — **aus dem Git-Log nachtragen**

`CHANGELOG.md` hat keinen Abschnitt für 7.0.0, obwohl die Version
veröffentlicht wurde. Erfunden wurde bewusst nichts.

**Entschieden:** Aus den Commits zwischen dem letzten 6.x-Eintrag und 7.0.0
einen Entwurf rekonstruieren, den Ralf gegenliest und korrigiert.

Was bei der Umsetzung zu beachten ist:

- Der Entwurf ist eine **Rekonstruktion** und muss als solche entstehen: Was
  sich aus dem Log nicht belegen lässt, kommt nicht hinein. Lieber ein
  Stichpunkt weniger als einer, der plausibel klingt.
- Vorlage ist der Stil der bestehenden Abschnitte im `CHANGELOG.md`, nicht
  eine Commit-Liste. Commits, die nur Umbau ohne sichtbare Wirkung sind,
  gehören nicht in Release-Notes.
- Der Entwurf geht **erst an Ralf**, bevor er eingecheckt wird — er war dabei
  und weiß, was damals die Hauptsache war. Ohne diese Runde ist das Ergebnis
  nicht besser als eine Vermutung.
- `tests/test_version_consistency.py` hält die Lücke derzeit fest; der dortige
  Vermerk muss mit angepasst werden, sobald der Abschnitt existiert.
