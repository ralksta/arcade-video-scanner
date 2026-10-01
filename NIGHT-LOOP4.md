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
