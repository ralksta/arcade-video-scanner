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
import re
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


def _handler_bodies() -> dict[str, str]:
    """Quelltext aller handle_*-Funktionen in den Routen-Modulen.

    Viele Zweige prüfen die Sitzung nicht selbst, sondern delegieren an einen
    Handler, der es tut. Ohne diesen Schritt meldet die Analyse genau solche
    Routen fälschlich als offen — beim Schreiben dieses Tests passiert mit
    `/api/settings/remove-photos`, das sehr wohl geschützt ist.
    """
    bodies = {}
    routes_dir = ROOT / "arcade_scanner" / "server" / "routes"
    for path in list(routes_dir.glob("*.py")) + [HANDLER]:
        if path.name.startswith("._"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bodies[node.name] = ast.unparse(node)
    return bodies


def _branch_is_guarded(node: ast.If, handler_bodies: dict[str, str]) -> bool:
    body_source = "\n".join(ast.unparse(stmt) for stmt in node.body)
    if "get_current_user" in body_source or "require_auth" in body_source:
        return True

    # Delegation verfolgen: ruft der Zweig einen handle_*-Handler auf, zählt
    # dessen Prüfung.
    for called in re.findall(r"\b(handle_\w+)\s*\(", body_source):
        target = handler_bodies.get(called, "")
        if "get_current_user" in target or "require_auth" in target:
            return True
    return False


@pytest.mark.parametrize("method", ["do_GET", "do_POST"])
def test_every_api_route_checks_the_session(method):
    """
    Es gibt kein globales Auth-Gate: jede Route prüft selbst. Genau deshalb
    konnte eine einzelne die Prüfung vergessen — und genau deshalb braucht es
    diesen Durchlauf über alle Zweige.
    """
    tree = ast.parse(HANDLER.read_text(encoding="utf-8"))
    handler_bodies = _handler_bodies()

    dispatch = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == method),
        None,
    )
    assert dispatch is not None, f"{method} nicht gefunden"

    unguarded = []
    checked = 0
    for node in ast.walk(dispatch):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare)
                and test.comparators
                and isinstance(test.comparators[0], ast.Constant)
                and isinstance(test.comparators[0].value, str)
                and test.comparators[0].value.startswith("/api/")):
            continue

        route = test.comparators[0].value
        if route in ALLOWED_WITHOUT_SESSION:
            continue

        checked += 1
        if not _branch_is_guarded(node, handler_bodies):
            unguarded.append(route)

    assert checked > 0, f"Keine Routen in {method} erkannt — Analyse veraltet?"
    assert not unguarded, (
        f"API-Route in {method} ohne Sitzungsprüfung:\n  " + "\n  ".join(unguarded)
        + "\nEntweder prüfen oder in ALLOWED_WITHOUT_SESSION eintragen."
    )


# Routen, die bewusst ohne Sitzung erreichbar sind.
ALLOWED_WITHOUT_SESSION = {
    "/api/health",      # Health-Check für Docker/Monitoring, gibt nur Status und Zeilenzahl
    "/api/health/",
    "/api/login",       # muss ohne Sitzung erreichbar sein
    "/api/logout",      # arbeitet auf dem Cookie, nicht auf einer geprüften Sitzung
}
