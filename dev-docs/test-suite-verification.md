# Prüfen die Tests wirklich etwas?

**Stand: 2026-08-17**, erhoben im Nachtlauf (Loop I). Ergebnis: **ja.**

Anlass waren zwei Zufallsfunde derselben Nacht — ein `pytest.skip`, das nach
einer Umstellung immer griff, und Ladereihenfolge-Tests, die per Substring das
falsche Ergebnis verglichen und zufällig grün waren. Wenn so etwas zweimal
zufällig auffällt, lohnt die systematische Frage.

## Was geprüft wurde

### 1. Tests ohne Zusicherung

Sieben Treffer, alle legitim: Es sind „wirft nicht"-Tests, bei denen das
Ausbleiben einer Ausnahme die Aussage ist (`test_post_scan_runner_never_raises`,
`test_template_can_be_imported`, …). Ein achter Treffer war ein Fehlalarm der
Analyse — `test_post_scan_runner_skips_users_without_rules` prüft über
`assert_not_called()`, was ein reiner AST-Blick auf `assert`-Anweisungen nicht
sieht.

### 2. Übersprungene Tests

Zwölf `skipif`-Bedingungen, alle an vorhandene Werkzeuge geknüpft (`node`,
`ffmpeg`, `imagehash`). In dieser Umgebung greift keine davon — ein voller Lauf
meldet null Skips. Auf einer Maschine ohne `node` verschwänden fünf Dateien
still; `CLAUDE.md` weist darauf hin.

### 3. Zusicherungen, die nur Kommentare treffen

Genau dieser Fehler ist mir in derselben Nacht zweimal unterlaufen: eine Prüfung
auf `v.status`, die der eigene erklärende Kommentar erfüllte. Die Suche fand
drei Verdachtsfälle, alle Fehlalarme — einer prüft eine Doku-Datei, zwei prüfen
die *Laufzeit-Ausgabe* eines Handlers statt Quelltext.

### 4. Mutationstest (der eigentliche Beleg)

Die Frage „prüft der Test etwas?" beantwortet man am ehrlichsten, indem man den
Code kaputt macht und nachsieht, ob es auffällt. Zehn semantische Mutationen,
jede einzeln eingespielt und wieder zurückgenommen:

| Mutation | erkannt |
|---|---|
| `similarity`: L2-Normalisierung deaktiviert | ✓ |
| `criteria_eval`: Landscape-Schwelle verfälscht | ✓ |
| `proxy_resolver`: Stale-Vergleich umgedreht | ✓ |
| `validators`: Pfadprüfung gibt immer `True` zurück | ✓ |
| `sqlite_store`: `_write_lock` entfernt | ✓ |
| `response_helpers`: gzip deaktiviert | ✓ |
| Token-Maskierung wirkungslos gemacht | ✓ |
| Pfadprüfung in `discard_optimized` umgangen | ✓ |
| Deckel des Antwort-Caches entfernt | ✓ |
| Stale-Toleranz auf unendlich gesetzt | ✓ |

**Zehn von zehn.** Die letzten vier betreffen Code, der in dieser Nacht
entstanden ist — ein Test, den man selbst schreibt, prüft man am besten auch
selbst gegen die Mutation.

## Vorgehen zum Wiederholen

```bash
cp DATEI /tmp/mut.bak
# semantische Änderung einspielen (Vergleich umdrehen, Konstante verfälschen,
# Prüfung entfernen) — keine Syntaxfehler, die fallen ohnehin auf
.venv/bin/pytest -q | tail -1     # muss "failed" melden
cp /tmp/mut.bak DATEI
```

Wichtig ist die Auswahl: Mutationen, die eine *Zusage* verletzen (Sicherheit,
Korrektheit, Isolation), nicht solche, die nur Kosmetik ändern. Eine Mutation,
die niemand bemerkt, ist entweder eine Lücke im Test — oder ein Hinweis, dass
die Zeile keine Zusage trägt.
