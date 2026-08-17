"""
test_scan_targets_fallback.py
-----------------------------
Was passiert, wenn die Benutzerdatenbank nicht lesbar ist?

`active_scan_targets` und `active_exclude_paths` lesen **dieselbe Quelle** —
`user_db.get_all_users()`. Und die verschluckt ihre eigenen Fehler und gibt bei
einem Problem eine leere Liste zurück. Für die beiden Aufrufer sah eine
unlesbare Datenbank damit genauso aus wie eine leere:

    active_scan_targets  → keine Ziele  → Rückfall auf das **ganze** Home
    active_exclude_paths → keine Nutzer → **alle** Nutzer-Ausschlüsse weg

Beides zusammen: Der Scanner durchsucht das gesamte Home-Verzeichnis, und
ausgerechnet ohne die Verzeichnisse, die der Nutzer ausgenommen hat. Sichtbar
war davon eine einzelne Warnzeile, die im Scan-Protokoll vorbeiscrollt.

Der Rückfall auf das Home-Verzeichnis selbst ist gewollt — beim ersten Start
ist noch kein Ziel eingerichtet. Er darf nur nicht mehr greifen, wenn der
Grund für „keine Ziele" ein Lesefehler ist. Dann wird nicht gescannt: Für eine
Datenschutz-Funktion ist gar nichts das mildere Ergebnis als alles.
"""
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.config import HOME_DIR, config


@pytest.fixture
def user_db():
    """Ein Store-Ersatz, an dessen Stelle der echte importiert würde."""
    fake = MagicMock()
    fake.last_read_ok = True
    fake.get_all_users.return_value = []

    module = MagicMock()
    module.user_db = fake
    with patch.dict("sys.modules", {"arcade_scanner.database.user_store": module}):
        yield fake


def _user(targets=(), excludes=()):
    u = MagicMock()
    u.data.scan_targets = list(targets)
    u.data.exclude_paths = list(excludes)
    return u


# --- Der gewollte Rückfall ---

def test_without_configured_targets_the_home_directory_is_scanned(user_db):
    """Erster Start: noch nichts eingerichtet, also einmal alles anbieten."""
    assert config.active_scan_targets == [HOME_DIR]


def test_configured_targets_replace_the_fallback(user_db):
    user_db.get_all_users.return_value = [_user(targets=["/data/filme"])]

    assert config.active_scan_targets == ["/data/filme"]


def test_targets_of_all_users_are_collected(user_db):
    user_db.get_all_users.return_value = [
        _user(targets=["/data/a"]), _user(targets=["/data/b", "/data/a"]),
    ]

    assert sorted(config.active_scan_targets) == ["/data/a", "/data/b"]


def test_empty_entries_are_ignored(user_db):
    user_db.get_all_users.return_value = [_user(targets=["", "/data/a", None])]

    assert config.active_scan_targets == ["/data/a"]


# --- Der Fund ---

def test_an_unreadable_user_database_does_not_trigger_a_home_scan(user_db, capsys):
    """
    Vorher nicht unterscheidbar von „noch nichts eingerichtet" — und damit ein
    Scan des gesamten Home-Verzeichnisses.
    """
    user_db.get_all_users.return_value = []
    user_db.last_read_ok = False

    targets = config.active_scan_targets

    assert targets == [], f"Rückfall trotz Lesefehler: {targets}"
    assert HOME_DIR not in targets
    assert "could not read the user database" in capsys.readouterr().out.lower()


def test_the_exclusions_vanish_from_the_same_failure(user_db):
    """
    Der Grund, warum der Rückfall gerade in diesem Fall gefährlich ist: Die
    Ausschlüsse kommen aus derselben Quelle und fehlen zeitgleich. Dieser Test
    hält den Zusammenhang fest — er beschreibt Verhalten, das so bleibt.
    """
    user_db.get_all_users.return_value = []
    user_db.last_read_ok = False

    excludes = config.active_exclude_paths

    assert not any("privat" in e.lower() for e in excludes)
    assert config.active_scan_targets == [], (
        "Ohne Ausschlüsse darf erst recht kein Ersatzziel gescannt werden"
    )


def test_a_readable_but_empty_database_still_falls_back(user_db):
    """Die Gegenprobe: Der gewollte Fall darf nicht mit weggefallen sein."""
    user_db.get_all_users.return_value = []
    user_db.last_read_ok = True

    assert config.active_scan_targets == [HOME_DIR]


def test_a_read_failure_is_recorded_on_the_real_store(tmp_path):
    """
    Das Flag muss der echte Store setzen, nicht nur die Attrappe oben.
    Erzwungen über eine Datenbank, die keine ist.
    """
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.user_store.config", mock_config):
        from arcade_scanner.database.user_store import UserStore

        store = UserStore()
        assert store.get_all_users() != [] or store.last_read_ok

        with patch.object(store, "_get_conn", side_effect=OSError("disk gone")):
            assert store.get_all_users() == []
            assert store.last_read_ok is False

        # Und wieder zurück, sobald es klappt — ein einmaliger Fehler darf
        # nicht dauerhaft jeden Scan blockieren.
        store.get_all_users()
        assert store.last_read_ok is True


# --- Ausschlüsse: Vereinigung über alle Nutzer ---

def test_exclusions_of_all_users_apply_to_everyone(user_db):
    """
    Bewusst die sichere Richtung: Was ein Nutzer ausnimmt, wird gar nicht erst
    eingelesen — also auch nicht für die anderen. Zu viel auszuschließen ist
    ärgerlich, zu wenig bricht ein Versprechen.
    """
    user_db.get_all_users.return_value = [
        _user(excludes=["/home/ralf/privat"]), _user(excludes=["/home/gast/eigenes"]),
    ]

    excludes = config.active_exclude_paths

    assert "/home/ralf/privat" in excludes
    assert "/home/gast/eigenes" in excludes


def test_the_default_exclusions_are_always_included(user_db):
    assert set(config.default_exclusions) <= set(config.active_exclude_paths)
