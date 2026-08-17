"""
test_onboarding_guard.py
------------------------
Wann läuft der Einrichtungsassistent — und wann darf er es auf keinen Fall?

`onboarding.py` hatte bis hierher **keinen einzigen Test**, dabei entscheidet
es, was gescannt wird, legt das Admin-Konto an, schreibt die Einstellungen und
bietet an, sämtliche Datenbanken zu löschen. Es läuft genau einmal — und
deshalb sieht es nie wieder jemand an.

Zwei Wege, auf denen es über einer **bestehenden** Installation loslief:

**1. Unlesbare Einstellungen galten als frische Installation.**

    except Exception:
        return True

Die Entscheidung hing allein an `settings.json`. Zusammen mit dem gekürzten
Schreiben (siehe `tests/test_settings_durability.py`) genügte ein Stromausfall
beim Speichern: Datei halb geschrieben, nächster Start, Assistent läuft.

**2. Ohne Terminal lief er trotzdem — und zwar still.**

`prompt()` fängt `EOFError` ab und gibt den Vorgabewert zurück. Mit stdin auf
`/dev/null` nachgemessen: Der Assistent stürzt nicht ab, sondern beantwortet
sich jede Frage selbst mit der Vorgabe und schreibt danach die Konfiguration.
Ein Serverstart aus systemd oder Docker hätte so eine eingerichtete
Installation umkonfiguriert, ohne dass irgendwo etwas steht.

Der Löschzweig selbst ist gut abgesichert — er hängt an einer ausdrücklichen
Frage mit Vorgabe „nein" und einer Warnung. Er war nie das Problem; das
Problem war, dass die Frage überhaupt gestellt wurde.
"""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner import onboarding


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Ein leeres Datenverzeichnis, auf das onboarding und config zeigen."""
    from arcade_scanner import config as config_module

    monkeypatch.setattr(config_module, "HIDDEN_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config_module, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    return tmp_path


def write_settings(data_dir, **values):
    (data_dir / "settings.json").write_text(json.dumps(values), encoding="utf-8")


# --- Der echte Erstlauf muss weiter funktionieren ---

def test_a_truly_empty_directory_runs_the_wizard(data_dir):
    assert onboarding.should_run_wizard() is True


def test_settings_without_the_completed_flag_run_the_wizard(data_dir):
    write_settings(data_dir, theme="dark")

    assert onboarding.should_run_wizard() is True


def test_a_completed_setup_does_not_run_the_wizard(data_dir):
    write_settings(data_dir, first_run_completed=True)

    assert onboarding.should_run_wizard() is False


# --- 1. Bestehende Daten ---

@pytest.mark.parametrize("existing", ["users.db", "media_library.db"])
def test_existing_data_prevents_the_wizard(data_dir, existing):
    """
    Der stärkste Beleg dafür, dass es keine frische Installation ist: Es liegen
    schon Daten da. Das schlägt jede Angabe in settings.json.
    """
    (data_dir / existing).write_bytes(b"SQLite format 3\x00")
    write_settings(data_dir, theme="dark")  # ohne first_run_completed

    assert onboarding.should_run_wizard() is False


def test_existing_data_prevents_the_wizard_even_without_settings(data_dir):
    """Der Fall, der vorher am eindeutigsten „Erstlauf" ergab."""
    (data_dir / "users.db").write_bytes(b"SQLite format 3\x00")

    assert onboarding.should_run_wizard() is False


def test_installation_exists_reports_an_empty_directory_as_empty(data_dir):
    assert onboarding.installation_exists() is False


# --- 2. Unlesbare Einstellungen ---

def test_corrupt_settings_do_not_count_as_a_fresh_installation(data_dir, capsys):
    """
    Der Fund. Vorher: `except Exception: return True` — und damit lief der
    Assistent nach einem halb geschriebenen settings.json über einer
    eingerichteten Installation los.
    """
    (data_dir / "settings.json").write_text('{"theme": "dark"', encoding="utf-8")

    assert onboarding.should_run_wizard() is False
    assert "not readable" in capsys.readouterr().out


def test_unreadable_settings_do_not_count_either(data_dir, capsys):
    write_settings(data_dir, first_run_completed=True)

    with patch("builtins.open", side_effect=OSError("Zugriff verweigert")):
        assert onboarding.should_run_wizard() is False

    assert "not readable" in capsys.readouterr().out


# --- 3. Kein Terminal ---

def test_without_a_terminal_the_wizard_is_skipped(data_dir, capsys):
    """
    `prompt()` fängt EOFError ab und liefert den Vorgabewert. Der Assistent
    stürzt ohne stdin also nicht ab — er läuft still durch. Genau deshalb
    braucht es diese Prüfung und nicht bloss einen Fehlerpfad.
    """
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = False

    with patch.object(onboarding.sys, "stdin", fake_stdin), \
         patch.object(onboarding, "run_setup_wizard") as wizard:
        assert onboarding.run_onboarding() is False

    wizard.assert_not_called()
    assert "No interactive terminal" in capsys.readouterr().out


def test_with_a_terminal_the_wizard_runs(data_dir):
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True

    with patch.object(onboarding.sys, "stdin", fake_stdin), \
         patch.object(onboarding, "run_setup_wizard", return_value={}) as wizard, \
         patch.object(onboarding, "apply_configuration") as apply_config:
        assert onboarding.run_onboarding() is True

    wizard.assert_called_once()
    apply_config.assert_called_once()


def test_an_existing_installation_beats_a_terminal(data_dir):
    """Die Reihenfolge: Erst wird geprüft, ob es etwas gibt, dann alles andere."""
    (data_dir / "users.db").write_bytes(b"SQLite format 3\x00")

    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True

    with patch.object(onboarding.sys, "stdin", fake_stdin), \
         patch.object(onboarding, "run_setup_wizard") as wizard:
        assert onboarding.run_onboarding() is False

    wizard.assert_not_called()


# --- Der Löschzweig, so wie er ist ---

def test_the_reset_is_behind_an_explicit_question_defaulting_to_no():
    """
    Festgehalten, weil es gut gelöst ist und so bleiben soll: Das Löschen aller
    Datenbanken hängt an einer Frage mit Vorgabe „nein" und einer Warnung, die
    aufzählt, was verschwindet.
    """
    import inspect

    source = inspect.getsource(onboarding.run_setup_wizard)
    block = source.split("Reset all databases?", 1)

    assert len(block) == 2, "Die Rückfrage vor dem Löschen ist weg"
    assert 'prompt_yes_no("Reset all databases?", False)' in source, (
        "Die Vorgabe ist nicht mehr „nein\""
    )
    assert "reset_databases()" in block[1], (
        "Gelöscht wird woanders als hinter der Rückfrage"
    )


def test_the_reset_only_touches_the_data_directory(data_dir):
    """
    Gegenprobe zum Umfang: Es werden Dateien im Datenverzeichnis entfernt,
    keine Mediendateien.
    """
    import inspect

    source = inspect.getsource(onboarding.reset_databases)

    assert "HIDDEN_DATA_DIR" in source
    assert "THUMB_DIR" in source
    assert "scan_targets" not in source and "active_scan" not in source


def test_the_wizard_writes_the_completed_flag():
    """Sonst liefe er bei jedem Start erneut."""
    import inspect

    assert '"first_run_completed"' in inspect.getsource(onboarding.run_setup_wizard)
    assert 'first_run_completed' in inspect.getsource(onboarding.apply_configuration)


def test_settings_written_by_the_wizard_end_up_in_the_data_directory(data_dir):
    """
    Kein Fund, aber die Verbindung zur Haltbarkeitsprüfung: Der Assistent
    schreibt settings.json mit eigenem Code, nicht über `config._save_json_raw`.
    Verschiebt sich der Pfad, muss beides mitgehen.
    """
    import inspect

    source = inspect.getsource(onboarding.apply_configuration)

    assert "SETTINGS_FILE" in source or "settings.json" in source
    assert os.path.basename(str(data_dir / "settings.json")) == "settings.json"
