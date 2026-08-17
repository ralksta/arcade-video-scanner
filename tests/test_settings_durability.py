"""
test_settings_durability.py
---------------------------
Übersteht `settings.json` einen schlechten Moment?

Zwei Fehler, die einzeln unangenehm sind und zusammen die Einstellungen
verlieren.

**Beim Schreiben.** `_save_json_raw()` öffnete die Datei mit ``"w"``, was sie
sofort auf null Bytes kürzt. Bricht der Vorgang danach ab — Stromausfall, volle
Platte, abgeschossener Prozess —, bleibt eine leere oder halbe Datei zurück.

**Beim Lesen.** Ein nicht lesbares `settings.json` wurde beim nächsten Start
durch die Standardwerte **ersetzt**::

    except json.JSONDecodeError as e:
        print(f"⚠️ settings.json is corrupted ({e}) – restoring defaults")
        file_data = dict(DEFAULT_SETTINGS_JSON)
        self._save_json_raw(file_data)

Damit war die Datei endgültig weg — und mit ihr jede Chance, sie von Hand zu
retten, obwohl oft nur eine schließende Klammer fehlt.

Zusammen: Ein unglücklicher Moment beim Speichern, ein Neustart, und Theme,
Größenschwellen, ffmpeg-Pfade, `proxy_root` und `review_dir` stehen wieder auf
Werkseinstellung. Gemeldet wird das mit einer Zeile in der Konsole.

Bemerkenswert: `duplicate_detector.py` schreibt seinen Cache seit jeher über
eine Zwischendatei, mit genau dieser Begründung im Kommentar — „a crash
mid-write would otherwise leave a truncated JSON file". Für die
Einstellungsdatei, die ungleich schwerer zu ersetzen ist, galt das nicht.
"""
import json
from unittest.mock import patch

import pytest


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """Ein `config`-Modul, dessen SETTINGS_FILE im Temporärverzeichnis liegt."""
    from arcade_scanner import config as config_module

    path = tmp_path / "settings.json"
    monkeypatch.setattr(config_module, "SETTINGS_FILE", str(path))
    return path


@pytest.fixture
def cfg(settings_file):
    from arcade_scanner.config import ConfigManager

    return ConfigManager()


# --- Schreiben ---

def test_a_saved_file_is_valid_json(cfg, settings_file):
    cfg._save_json_raw({"theme": "dark", "min_size_mb": 100})

    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "theme": "dark", "min_size_mb": 100,
    }


def test_a_failed_write_leaves_the_previous_file_intact(cfg, settings_file):
    """
    Der Kern: Geht beim Schreiben etwas schief, muss der alte Stand noch da
    sein. Vorher war die Datei zu diesem Zeitpunkt bereits gekürzt.
    """
    settings_file.write_text(json.dumps({"theme": "light", "min_size_mb": 250}),
                             encoding="utf-8")

    with patch("json.dump", side_effect=OSError("Kein Speicherplatz")):
        cfg._save_json_raw({"theme": "dark"})

    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "theme": "light", "min_size_mb": 250,
    }


def test_a_failed_write_leaves_no_debris(cfg, settings_file, tmp_path):
    """Die Zwischendatei darf nicht liegen bleiben."""
    with patch("json.dump", side_effect=OSError("Kein Speicherplatz")):
        cfg._save_json_raw({"theme": "dark"})

    assert list(tmp_path.glob("*.tmp")) == []


def test_the_write_goes_through_a_temporary_file(cfg, settings_file):
    """
    Der strukturelle Beleg. Ohne ihn könnte jemand `os.replace` durch ein
    direktes Schreiben ersetzen, und die Tests oben blieben grün, solange
    `json.dump` nur mittendrin scheitert statt beim Öffnen.
    """
    import inspect

    source = inspect.getsource(type(cfg)._save_json_raw)
    assert ".tmp" in source
    assert "os.replace" in source
    assert "fsync" in source, "Ohne fsync kann der Inhalt die Umbenennung überleben"


def test_saving_twice_leaves_exactly_one_file(cfg, settings_file, tmp_path):
    cfg._save_json_raw({"a": 1})
    cfg._save_json_raw({"a": 2})

    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


# --- Lesen ---

def test_a_corrupt_file_is_kept_aside(cfg, settings_file, tmp_path):
    """
    Der zweite Fund. Vorher war die kaputte Datei nach diesem Zweig weg —
    dabei fehlt oft nur eine schließende Klammer, und der Rest wäre von Hand
    zu retten gewesen.
    """
    settings_file.write_text('{"theme": "dark", "min_size_mb": 250',
                             encoding="utf-8")

    cfg._load_settings()

    kept = tmp_path / "settings.json.corrupt"
    assert kept.exists(), "Die kaputte Datei wurde ersatzlos überschrieben"
    assert "min_size_mb" in kept.read_text(encoding="utf-8")


def test_after_a_corrupt_file_the_defaults_are_in_place(cfg, settings_file):
    """Die App muss trotzdem starten — nur eben nicht auf Kosten der alten Datei."""
    from arcade_scanner.config import DEFAULT_SETTINGS_JSON

    settings_file.write_text("kaputt{{{", encoding="utf-8")

    cfg._load_settings()

    written = json.loads(settings_file.read_text(encoding="utf-8"))
    assert written["min_size_mb"] == DEFAULT_SETTINGS_JSON["min_size_mb"]


def test_a_readable_file_is_not_touched(cfg, settings_file):
    """Die Gegenprobe: Kein Beiseitelegen, wenn nichts kaputt ist."""
    settings_file.write_text(json.dumps({"theme": "light"}), encoding="utf-8")

    cfg._load_settings()

    assert not (settings_file.parent / "settings.json.corrupt").exists()


# --- Die Parallele ---

def test_the_duplicate_cache_writes_the_same_way():
    """
    Es war zwei Dateien weiter längst richtig gelöst, samt Begründung. Dieser
    Test hält beide Stellen zusammen, damit die nächste Änderung nicht wieder
    nur eine davon erwischt.
    """
    import inspect

    from arcade_scanner.core.duplicate_detector import _StatValidatedHashCache

    assert "os.replace" in inspect.getsource(_StatValidatedHashCache.save)


# --- Der Rückgabewert ---
#
# `_save_json_raw()` fängt seine Fehler selbst ab. `save()` verwarf das
# Ergebnis und meldete anschliessend in jedem Fall Erfolg -- und die beiden
# Aufrufer in routes/settings.py hängen genau daran:
#
#     if config.save(new_settings):
#         ... "success": True
#
# Bei voller Platte oder fehlenden Schreibrechten stand in der Oberfläche
# "gespeichert", während auf der Platte der alte Stand lag. Im Arbeitsspeicher
# stand der neue, also stimmte es bis zum nächsten Neustart sogar -- und danach
# war die Änderung weg, ohne dass irgendwo etwas gemeldet worden wäre.

def test_a_successful_save_reports_success(cfg, settings_file):
    assert cfg.save({"min_size_mb": 300}) is True
    assert json.loads(settings_file.read_text(encoding="utf-8"))["min_size_mb"] == 300


def test_a_failed_save_reports_failure(cfg, settings_file):
    settings_file.write_text(json.dumps({"min_size_mb": 100}), encoding="utf-8")

    with patch("json.dump", side_effect=OSError("Kein Speicherplatz")):
        assert cfg.save({"min_size_mb": 300}) is False


def test_a_failed_save_does_not_change_the_in_memory_settings(cfg, settings_file):
    """
    Sonst zeigt die Oberfläche den neuen Wert an, die Platte trägt den alten,
    und beim nächsten Start springt die Einstellung scheinbar grundlos zurück.
    """
    settings_file.write_text(json.dumps({"min_size_mb": 100}), encoding="utf-8")
    cfg._load_settings()
    before = cfg.settings.min_size_mb

    with patch("json.dump", side_effect=OSError("Kein Speicherplatz")):
        cfg.save({"min_size_mb": 300})

    assert cfg.settings.min_size_mb == before


def test_the_settings_route_still_checks_the_return_value():
    """
    Die Aufrufer prüften schon immer richtig — nur gab es nichts zu prüfen.
    Festgehalten, damit die Prüfung nicht wegoptimiert wird, jetzt wo sie
    etwas bedeutet.
    """
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "settings.py"
    ).read_text(encoding="utf-8")

    assert source.count("if config.save(") == 2
