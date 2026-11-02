# Release-Split: `dev` → `main`

Stand 2026-10-24. Der echte `origin/main` steht auf `7f0234e`
(2026-08-08, Design-System-Login); der lokale `main` wurde darauf
vorgezogen. `dev` ist 234 Commits voraus. Die Commits werden als **vier
gestapelte PRs** gemergt. Jeder Branch ist ein Präfix von `dev`; es wird
nichts umgeschrieben oder gepickt.

**Wichtig:** Die PRs in dieser Reihenfolge mergen und **Merge-Commit statt
Squash** verwenden. Nur so bleibt der nächste Branch ein echter Nachfahre des
vorigen. Nach jedem Merge den nächsten PR gegen `main` öffnen.

| # | Branch | Bereich | Commits | Inhalt |
|---|---|---|---|---|
| 1 | `release/7.1.0-performance` | `origin/main..d2c6c9a` | 34 | Remote-Encoding, Proxy-Streaming, HTTP Keep-Alive/gzip/Cache, A11y, Export, Ähnliche-Leiste, Leer-Zustände, Shortcuts |
| 2 | `release/7.1.0-hardening` | `d2c6c9a..aa6cbd0` | 141 | Sicherheit, Scanner-/Queue-Fixes, Tests, A11y, Security-Header |
| 3 | `release/7.1.0-clients` | `aa6cbd0..26074fc` | 50 | Vault-Entfernung, gespeicherte Ansichten, TV-App im Netflix-Stil, Poster, Wiedergabefortschritt, Startseite, Schau-Modus |
| 4 | `release/7.1.0-web` | `26074fc..1487df3` | 9 | Suche, Papierkorb, Collection-Dialog, Sortierung, Kachel-Infos, Bestätigungsdialog, Release 7.1.0 |

## PR-Titel

1. `7.1.0 — Performance, Proxy-Streaming und Barrierefreiheit`
2. `7.1.0 — Sicherheit und Robustheit`
3. `7.1.0 — TV-App, Vault-Entfernung und Wiedergabefortschritt`
4. `Release 7.1.0 — Suche, Papierkorb und Collection-Dialog`

## Befehle (je eine Zeile)

```
gh pr create --base main --head release/7.1.0-performance --title "7.1.0 — Performance, Proxy-Streaming und Barrierefreiheit" --fill
gh pr create --base main --head release/7.1.0-hardening --title "7.1.0 — Sicherheit und Robustheit" --fill
gh pr create --base main --head release/7.1.0-clients --title "7.1.0 — TV-App, Vault-Entfernung und Wiedergabefortschritt" --fill
gh pr create --base main --head release/7.1.0-web --title "Release 7.1.0 — Suche, Papierkorb und Collection-Dialog" --fill
```

Nach PR 1 mergen, dann PR 2 öffnen; usw. Vor jedem PR prüfen:
`git log --oneline <voriger-cut>..<dieser-cut>`.

## Optional: PR 2 weiter teilen

Der Hardening-PR ist mit 141 Commits der größte. Ein möglicher Schnitt liegt
bei `d84aed2` (2026-08-17, „Zyklus 6 festgelegt"):
- `d2c6c9a..d84aed2` — 31 Commits (Sicherheit, Altlasten, Tests)
- `d84aed2..aa6cbd0` — 110 Commits (Scanner, Queue, Sitzungen, A11y)

Dann wären es fünf PRs. Nur machen, wenn der Hardening-PR zu groß zum
Reviewen ist.

## Status

- [x] PR 1 (#52) gemergt
- [x] PR 2 (#53) gemergt
- [x] PR 3 (#54) gemergt
- [x] PR 4 (#55) gemergt
- [x] `origin/main` = `289dc89`
- [x] `dev` = `main` = `origin/dev` = `origin/main`
- [ ] Release-Branches löschen (optional)

**CI-Hinweis:** Die elf mypy-2.4-Fehler sind behoben (PR #56, `f0754f4`),
und der Cache-Buster-Test ist unabhängig von Checkout-mtimes (`593dd88`).
CI auf #56 war grün, **PR #56 ist gemergt**; `dev` = `main` = `da15f5a`.

## Offen

- [x] Branches pushen
- [x] PR 1–4 anlegen und mergen
- [x] `dev` und `main` gleichziehen
