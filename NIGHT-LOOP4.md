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
      - [ ] Gleichzeitige Anmeldungen (SessionManager, Brute-Force-Sperre, user_store)
      - [ ] Ähnlichkeits-Cache unter parallelen Anfragen
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
