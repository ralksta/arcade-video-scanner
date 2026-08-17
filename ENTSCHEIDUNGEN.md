# Entscheidungen zum Nachtlauf

Ralfs Antworten auf die offenen Punkte aus `NACHTLAUF-BERICHT.md`.
Aufgenommen am 17.08.2026. **Nichts davon ist umgesetzt** — diese Datei hält
nur fest, was gelten soll, damit die Umsetzung später nicht wieder von vorn
diskutiert werden muss.

Stand: 2 von 9 Punkten entschieden.

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
