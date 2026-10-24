# Ad-hoc-Diagnoseskripte

Einmal-Skripte aus früheren Fehlersuchen. Sie sind **keine Tests** und laufen
nicht mit der Suite.

## Warum sie hier liegen

Vorher lagen sie im Wurzelverzeichnis und hießen `test_api.py`, `test_dump.py`,
`test_probe*.py`, `run_fix.py`, `test_ui.js`, `test_puppeteer.js`.

Das war gefährlich: alle öffnen die **echte** Datenbank in `arcade_data/`, und
der Modulcode läuft beim Import. `pytest` sammelt Dateien mit `test_`-Präfix
ein — schon das reine Einsammeln genügt, um die Produktivdatenbank zu öffnen
und Schema-Migrationen anzuwenden. Nachgewiesen mit
`pytest --collect-only test_dump.py` gegen eine Kopie im Altzustand: „collected
0 items", und die Datenbank war trotzdem migriert.

Dass es bisher gutging, lag allein an `testpaths = ["tests"]` in
`pyproject.toml`. Ein `pytest test_dump.py`, ein `pytest .` oder eine geänderte
Konfiguration hätte gereicht.

`.gitignore` hält für Ad-hoc-Skripte bereits die Präfixe `debug_`, `check_` und
`verify_` frei — `test_` gehört ausdrücklich nicht dazu.

## Was sie tun

| Datei | Zweck |
|---|---|
| `dump_library.py` | Gibt alle Einträge der Bibliothek aus. Nur lesend. |
| `inspect_user_targets.py` | Zeigt die Scan-Ziele des Admin-Kontos und wie sie gefiltert werden. Nur lesend. |
| `probe_smoke.py` | Kürzester Weg, `MediaProbe` gegen eine Datei laufen zu lassen. |
| `probe_ffprobe_raw.py` | Ruft `ffprobe` direkt auf und zeigt die rohe Ausgabe — für Fälle, in denen die Auswertung etwas verschluckt. |
| `probe_without_swallowing.py` | `MediaProbe` mit deaktiviertem `try/except`, damit der echte Fehler sichtbar wird. |
| `retag_av1_opt_files.py` | **Schreibend.** Sucht `_opt.mp4`-Dateien mit Codec `hevc` und ruft für jede `scripts/fix_av1_tags.py` auf. Vor dem Ausführen die Abfrage lesen. |
| `ui_smoke.js`, `puppeteer_smoke.js` | Browser-Skripte aus früheren Frontend-Prüfungen. |

## Vor dem Ausführen

Diese Skripte arbeiten auf `arcade_data/` — der echten Bibliothek, nicht auf
einer Kopie. Wer etwas ausprobieren will, setzt `CONFIG_DIR` auf ein Verzeichnis
mit einer Kopie:

```bash
CONFIG_DIR=/tmp/arcade_probe .venv/bin/python3 scripts/adhoc/dump_library.py
```
