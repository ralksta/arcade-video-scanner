"""
test_manage_users_cli.py
------------------------
`scripts/manage_users.py` — das einzige Werkzeug, mit dem Konten angelegt und
Passwörter geändert werden.

Drei Befunde, alle behoben:

1. **Das Skript ließ sich nicht ausführen.** Die Shebang-Zeile zeigte auf
   `/Users/ralfo/git/arcade-video-scanner/.venv/bin/python3` — einen absoluten
   Pfad einer anderen Maschine, mit einem Verzeichnisnamen, den dieses Repo gar
   nicht hat. `./scripts/manage_users.py` schlug mit „Datei nicht gefunden" fehl
   (gemeint war der Interpreter, nicht das Skript). Die sieben Geschwister-
   Skripte benutzen alle `#!/usr/bin/env python3`; dieses war der Ausreißer.
   Über den in CLAUDE.md dokumentierten Aufruf lief es immer.

2. **Ein leeres Passwort wurde angenommen.** Zweimal Enter an der Abfrage
   genügte: Die beiden Eingaben waren gleich, also ging es durch, und das Konto
   stand ohne Passwort in der Datenbank. `--password ""` fiel obendrein auf die
   Abfrage zurück, statt als Fehler zu gelten.

3. **`--password` auf der Kommandozeile** landet in der Shell-History und ist
   während des Aufrufs in `ps` sichtbar. Nicht zu verbieten — für Skripte ist
   das der einzige Weg —, aber es sollte dabeistehen.

Der Import läuft hier über einen **Ersatz für `arcade_scanner.database`**. Das
echte Paket legt beim Import eine `UserStore`-Instanz auf dem Produktivpfad an
und würde die Benutzerdatenbank des Nutzers öffnen — dieselbe Falle wie beim
`ReportDebouncer` in Loop F.
"""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "manage_users.py"


@pytest.fixture
def cli():
    """Lädt das Skript mit einem attrappierten Datenbank-Modul."""
    fake_db = types.ModuleType("arcade_scanner.database")
    fake_db.user_db = MagicMock()
    fake_db.user_db.hash_password.return_value = b"\x00" * 32

    saved = {k: sys.modules.get(k) for k in ("arcade_scanner.database",)}
    sys.modules["arcade_scanner.database"] = fake_db
    try:
        spec = importlib.util.spec_from_file_location("_manage_users_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.user_db = fake_db.user_db
        yield module
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _args(**kwargs):
    ns = MagicMock()
    ns.password = kwargs.get("password")
    ns.username = kwargs.get("username", "bob")
    ns.admin = kwargs.get("admin", False)
    return ns


# --- 1. Ausführbarkeit ---

def test_the_shebang_points_at_an_interpreter_that_can_exist():
    first_line = SCRIPT.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "#!/usr/bin/env python3", (
        f"Shebang ist {first_line!r} — ein absoluter Pfad einer fremden "
        "Maschine macht das Skript unausführbar"
    )


def test_every_executable_script_uses_the_same_shebang():
    """
    Der Ausreißer war genau deshalb schwer zu sehen: Sieben Skripte machen es
    gleich, eines nicht.
    """
    scripts = Path(__file__).parent.parent / "scripts"
    for path in sorted(scripts.glob("*.py")):
        first = path.read_text(encoding="utf-8").splitlines()[0]
        if first.startswith("#!"):
            assert first == "#!/usr/bin/env python3", f"{path.name}: {first!r}"


# --- 2. Leere Passwörter ---

def test_an_empty_password_is_rejected_at_the_prompt(cli, capsys):
    with patch.object(cli.getpass, "getpass", return_value=""):
        assert cli.read_new_password("bob") is None

    assert "empty" in capsys.readouterr().out.lower()


def test_an_empty_password_is_rejected_on_the_command_line(cli):
    assert cli.password_from_args(_args(password=""), "bob") is None


def test_mismatched_passwords_are_rejected(cli, capsys):
    with patch.object(cli.getpass, "getpass", side_effect=["eins", "zwei"]):
        assert cli.read_new_password("bob") is None

    assert "match" in capsys.readouterr().out.lower()


def test_a_matching_non_empty_password_is_accepted(cli):
    with patch.object(cli.getpass, "getpass", side_effect=["geheim", "geheim"]):
        assert cli.read_new_password("bob") == "geheim"


def test_no_account_is_created_without_a_password(cli):
    """Der eigentliche Schaden: ein Konto ohne Passwort in der Datenbank."""
    cli.user_db.get_user.return_value = None

    with patch.object(cli.getpass, "getpass", return_value=""):
        cli.add_user(_args(username="bob"))

    cli.user_db.add_user.assert_not_called()


def test_no_password_is_changed_to_an_empty_one(cli):
    cli.user_db.get_user.return_value = MagicMock()

    with patch.object(cli.getpass, "getpass", return_value=""):
        cli.change_password(_args(username="bob"))

    cli.user_db.add_user.assert_not_called()


# --- 3. Passwort auf der Kommandozeile ---

def test_a_command_line_password_is_used_but_warned_about(cli, capsys):
    result = cli.password_from_args(_args(password="geheim"), "bob")

    assert result == "geheim", "Für Skripte muss der Weg offen bleiben"
    out = capsys.readouterr().out
    assert "History" in out and "ps" in out


def test_no_warning_when_the_password_was_prompted(cli, capsys):
    with patch.object(cli.getpass, "getpass", side_effect=["geheim", "geheim"]):
        cli.password_from_args(_args(password=None), "bob")

    assert "History" not in capsys.readouterr().out


# --- Verhalten, das unverändert bleiben muss ---

def test_an_existing_user_is_not_overwritten_by_add(cli):
    """
    `add_user()` im Store ist ein INSERT OR REPLACE. Ohne die Vorabprüfung im
    Skript würde `add` ein bestehendes Konto stillschweigend überschreiben.
    """
    cli.user_db.get_user.return_value = MagicMock()

    cli.add_user(_args(username="admin", password="neu"))

    cli.user_db.add_user.assert_not_called()


def test_passwd_on_an_unknown_user_creates_nothing(cli):
    cli.user_db.get_user.return_value = None

    cli.change_password(_args(username="gibtsnicht", password="neu"))

    cli.user_db.add_user.assert_not_called()


def test_a_new_user_gets_a_fresh_random_salt(cli):
    cli.user_db.get_user.return_value = None

    salts = []
    for name in ("a", "b"):
        cli.user_db.reset_mock()
        cli.add_user(_args(username=name, password="geheim"))
        salts.append(cli.user_db.add_user.call_args[0][0].salt)

    assert salts[0] != salts[1], "Gleiches Salz für zwei Konten"
    assert len(salts[0]) == 32, "16 Byte hex erwartet"


def test_changing_a_password_also_replaces_the_salt(cli):
    user = MagicMock()
    user.salt = "alt"
    cli.user_db.get_user.return_value = user

    cli.change_password(_args(username="bob", password="neu"))

    assert user.salt != "alt"


def test_the_admin_flag_is_passed_through(cli):
    cli.user_db.get_user.return_value = None

    cli.add_user(_args(username="chef", password="geheim", admin=True))

    assert cli.user_db.add_user.call_args[0][0].is_admin is True


def test_changing_a_password_says_that_sessions_stay_valid(cli, capsys):
    """
    Kein Fehler, aber eine Überraschung: Wer das Passwort wechselt, weil es
    abhandengekommen ist, erwartet, dass die fremde Sitzung endet. Sie endet
    nicht — der Server hält Sitzungen im Arbeitsspeicher, dieses Skript läuft
    in einem eigenen Prozess.
    """
    cli.user_db.get_user.return_value = MagicMock()

    cli.change_password(_args(username="bob", password="neu"))

    assert "Sitzungen" in capsys.readouterr().out
