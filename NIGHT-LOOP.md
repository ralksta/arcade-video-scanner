# Nachtlauf-Anweisungen (Ralph Loop)

Du arbeitest im Worktree `/Users/ralfo/git/arcade-video-scanner/.claude/worktrees/auto-tagging-night` auf Branch `night/auto-tagging` (basiert auf `dev`). Arbeite vollständig autonom — es gibt bis morgen früh keinen Menschen, der Fragen beantwortet. Triff Entscheidungen selbst und dokumentiere sie in Commit-Messages.

## Zustand ermitteln (Beginn JEDER Iteration)

1. `git log --oneline -15` und die Checkboxen in `docs/superpowers/plans/2026-08-07-auto-tagging.md` lesen.
2. Den ersten nicht abgehakten Schritt fortsetzen. NIE einen erledigten Task wiederholen.

## Phase 1 — Auto-Tagging-Plan umsetzen

Setze `docs/superpowers/plans/2026-08-07-auto-tagging.md` vollständig um, Task für Task, streng nach Plan:

- TDD: Test zuerst schreiben, fehlschlagen sehen, implementieren, grün sehen, committen (Commit-Messages wie im Plan angegeben).
- Nach jedem erledigten Schritt die Checkbox im Plan-File abhaken (`- [x]`) und die Plan-Änderung mit committen — das ist dein Fortschritts-Gedächtnis zwischen Iterationen.
- Vor jedem Commit müssen bestehen: `.venv/bin/pytest` (komplett), `.venv/bin/ruff check .`, `.venv/bin/mypy arcade_scanner`. CI ist blockierend — niemals rot committen.
- Den manuellen Browser-Smoke-Test in Task 6 Schritt 4 ÜBERSPRINGEN; stattdessen im Commit-Text vermerken „Smoke-Test dem Reviewer überlassen".
- Widerspricht der Plan dem realen Code (Zeilennummern, Namen), folge dem realen Code und dokumentiere die Abweichung im Commit-Text.

## Phase 2 — Härtung (nur wenn Phase 1 komplett abgehakt ist)

Kleine, unabhängige Commits:

1. **escapeHtml-Helper**: Gemeinsame Funktion (z. B. in `arcade_scanner/server/static/utils.js`, als `window.escapeHtml` exportiert) und Anwendung auf ALLE interpolierten Dateinamen/Pfade in `arcade_scanner/server/static/duplicates.js` — auch in `data-path`-Attributen (Dateinamen mit `"`, `&`, `<` dürfen weder Markup brechen noch Klicks totlegen). Contract-Tests (`tests/test_dom_contract.py`, `test_js_completeness.py`) aktualisieren, falls nötig.
2. **Routen-Testabdeckung**: Route-Handler in `arcade_scanner/server/routes/` ohne eigene Tests finden (Abgleich mit `tests/test_routes_*.py`) und Characterization-Tests im Stil von `tests/test_routes_queue.py` schreiben (FakeHandler-Muster; Session-Pflicht-Checks zuerst — das hat historisch die meisten echten Bugs gefunden). Findest du dabei einen ECHTEN Bug: nicht fixen, sondern als `xfail`-Test mit Begründung dokumentieren.

## Phase 3 — Abschluss

1. `git push -u origin night/auto-tagging`
2. PR gegen `dev` erstellen: `gh pr create --base dev` mit Titel `feat: Auto-Tagging-Regeln (Nachtlauf)` und einer Zusammenfassung beider Phasen. PR-Body endet mit: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
3. NICHTS mergen. Keine anderen Branches anfassen. Niemals force-pushen.

## Abbruch-Regel

Wenn du am selben Problem 3 Iterationen ohne Fortschritt hängst: Blocker unter `## NACHTLAUF-BLOCKER` in `docs/superpowers/plans/2026-08-07-auto-tagging.md` dokumentieren, committen, pushen, PR trotzdem erstellen (mit dem erreichten Stand) und dann die Completion-Promise ausgeben.

## Ende

NUR wenn Phase 1 komplett ist, alle Tests/Lints grün sind und der PR erstellt wurde (oder die Abbruch-Regel griff): gib exakt aus: `<promise>NACHTLAUF-KOMPLETT</promise>`
