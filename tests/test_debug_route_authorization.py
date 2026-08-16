"""
test_debug_route_authorization.py
---------------------------------
`/api/debug/dump` ist admin-pflichtig.

Die Route gab den kompletten Systemzustand **ohne jede Prüfung** heraus:

- `active_scan_targets` und `active_exclude_paths` — die Ordnerstruktur der
  Bibliothek,
- sämtliche Benutzernamen mit Admin-Flag und ihren Scan-Zielen,
- Beispielzeilen aus der Datenbank mit echten Dateipfaden,
- den Inhalt der Mount-Verzeichnisse.

Jede andere API-Route prüft die Sitzung in ihrem eigenen Zweig; ein globales
Gate gibt es nicht. Bei dieser einen fehlte die Prüfung schlicht. Wer den Port
erreichte — im LAN oder über Tailscale — bekam die Benutzerliste und die
Bibliotheksstruktur, ohne angemeldet zu sein.

Admin statt nur angemeldet, weil der Inhalt alle Nutzer betrifft und nicht nur
den anfragenden.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HANDLER = ROOT / "arcade_scanner" / "server" / "api_handler.py"


def _debug_route_block() -> str:
    source = HANDLER.read_text(encoding="utf-8")
    start = source.index('elif self.path == "/api/debug/dump":')
    return source[start:source.index("\n            elif ", start + 10)]


def test_route_rejects_anonymous_callers():
    block = _debug_route_block()
    assert "self.get_current_user()" in block, "Keine Sitzungsprüfung in der Route"
    assert 'send_error(401' in block


def test_route_rejects_non_admins():
    """
    Der Dump enthält die Scan-Ziele *aller* Nutzer. Ein normaler Nutzer würde
    damit erfahren, welche Verzeichnisse die anderen eingebunden haben.
    """
    block = _debug_route_block()
    assert "is_admin" in block
    assert 'send_error(403' in block


def test_authorization_runs_before_any_data_is_collected():
    """
    Die Prüfung muss vor dem Zusammentragen stehen — sonst liest die Route
    Nutzerliste und Datenbank auch für Aufrufer, die nichts davon sehen dürfen.
    """
    block = _debug_route_block()
    auth_position = block.index("send_error(403")
    data_position = block.index("debug_info = {")
    assert auth_position < data_position


@pytest.mark.parametrize("leaked", [
    "active_scan_targets",
    "hidden_data_dir",
    "username",
    "targets",
])
def test_the_dump_really_contains_sensitive_fields(leaked):
    """
    Gegenprobe zur Begründung: Schrumpft der Dump irgendwann auf harmlose
    Angaben, wäre die Admin-Pflicht überzogen — dann soll dieser Test auffallen
    und die Entscheidung neu gestellt werden.
    """
    assert leaked in _debug_route_block()


def test_every_api_get_route_checks_the_session():
    """
    Es gibt kein globales Auth-Gate: jede Route prüft selbst. Genau deshalb
    konnte eine einzelne die Prüfung vergessen. Dieser Test zählt die Zweige.
    """
    source = HANDLER.read_text(encoding="utf-8")
    tree = ast.parse(source)

    do_get = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "do_GET"
    )

    unguarded = []
    for node in ast.walk(do_get):
        if not isinstance(node, ast.If):
            continue
        # Zweige der Form:  elif self.path == "/api/..."
        test = node.test
        if not (isinstance(test, ast.Compare)
                and isinstance(test.comparators[0], ast.Constant)
                and isinstance(test.comparators[0].value, str)
                and test.comparators[0].value.startswith("/api/")):
            continue

        route = test.comparators[0].value
        if route in ALLOWED_WITHOUT_SESSION:
            continue

        body_source = "\n".join(ast.unparse(stmt) for stmt in node.body)
        if "get_current_user" not in body_source and "require_auth" not in body_source:
            unguarded.append(route)

    assert not unguarded, (
        "API-Route ohne Sitzungsprüfung:\n  " + "\n  ".join(unguarded)
        + "\nEntweder prüfen oder in ALLOWED_WITHOUT_SESSION eintragen."
    )


# Routen, die bewusst ohne Sitzung erreichbar sind.
ALLOWED_WITHOUT_SESSION = {
    "/api/health",      # Health-Check für Docker/Monitoring, gibt nur Status und Zeilenzahl
    "/api/health/",
    "/api/login",       # muss ohne Sitzung erreichbar sein
    "/api/logout",      # arbeitet auf dem Cookie, nicht auf einer geprüften Sitzung
}
