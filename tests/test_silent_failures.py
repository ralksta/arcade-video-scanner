"""
test_silent_failures.py
-----------------------
Wo ein `except` schweigt, muss das eine Entscheidung sein — keine Gewohnheit.

Ein `except Exception: pass` ist an vielen Stellen völlig richtig: eine
`ALTER TABLE`, die scheitert, weil die Spalte längst existiert, braucht keine
Meldung. Teuer wird es dort, wo das Schweigen ein *Feature* abschaltet oder
eine *Prüfung* überspringt — der Nutzer sieht dann nur, dass etwas nicht
passiert, und hat keinen Anhaltspunkt, warum.

Gefunden wurde das hier am Auto-Tagging-Hook: dort stand
`except ImportError: pass` mit dem Kommentar „landet mit PR #34; bis dahin
fehlt das Modul". Der PR ist längst gelandet — seither verschluckte der Guard
jeden echten Importfehler *innerhalb* von auto_tagger, und die Regeln liefen
nach dem Scan schlicht nicht mehr.

Dieser Test hält die Stellen fest, an denen ein Fehler hörbar sein muss.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _except_handlers(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            yield node


def _is_silent(handler: ast.ExceptHandler) -> bool:
    return all(isinstance(st, ast.Pass) for st in handler.body)


# Funktionen, deren Fehler den Nutzer erreichen müssen: sie schalten ein
# sichtbares Verhalten ab, wenn sie scheitern.
MUST_BE_AUDIBLE = [
    ("arcade_scanner/server/routes/files.py", "_run_rescan_in_background"),
    ("arcade_scanner/scanner/manager.py", "run_scan"),
]


@pytest.mark.parametrize("relative_path,function_name", MUST_BE_AUDIBLE)
def test_critical_paths_have_no_silent_handlers(relative_path, function_name):
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"))

    target = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function_name),
        None,
    )
    assert target is not None, f"{function_name} in {relative_path} nicht gefunden"

    silent = [
        f"{relative_path}:{h.lineno}"
        for h in ast.walk(target)
        if isinstance(h, ast.ExceptHandler) and _is_silent(h)
    ]
    assert not silent, (
        f"Stummer except-Block in {function_name} — hier schaltet Schweigen "
        f"sichtbares Verhalten ab:\n  " + "\n  ".join(silent)
    )


def test_auto_tagging_hook_reports_failures():
    """
    Der Hook darf den Scan nicht scheitern lassen (die Bibliothek ist da schon
    aktualisiert), aber schweigen darf er auch nicht.
    """
    source = (ROOT / "arcade_scanner" / "server" / "routes" / "files.py").read_text(
        encoding="utf-8"
    )
    block = source.split("run_post_scan_auto_tagging()", 1)[1][:400]
    assert "except ImportError:" not in block, (
        "Der ImportError-Guard stammt aus der Zeit vor PR #34 und verschluckt "
        "jetzt echte Importfehler im Auto-Tagger."
    )
    assert "Auto-Tagging" in block and "print" in block


def test_upload_integrity_check_reports_a_missing_reference_duration():
    """
    expected_duration = 0 schaltet die Laufzeitprüfung ab. Als Fallback in
    Ordnung — aber nicht lautlos, sonst läuft die schärfste Prüfung gegen einen
    abgeschnittenen Encode ins Leere.
    """
    source = (ROOT / "arcade_scanner" / "server" / "routes" / "queue.py").read_text(
        encoding="utf-8"
    )
    block = source.split("expected_duration = 0.0", 1)[1][:600]
    assert "except Exception:\n                pass" not in block
    assert "Laufzeitprüfung" in block


def test_stale_guards_are_not_left_behind():
    """
    Kommentare, die auf einen künftigen PR verweisen, überleben den PR. Wenn
    das Modul da ist, gehört der Platzhalter weg.
    """
    files_py = (ROOT / "arcade_scanner" / "server" / "routes" / "files.py").read_text(
        encoding="utf-8"
    )
    assert "landet mit PR #34" not in files_py, (
        "Hinweis auf einen gelandeten PR steht noch im Code."
    )
    assert (ROOT / "arcade_scanner" / "core" / "auto_tagger.py").is_file()


def test_swallowed_handlers_stay_within_a_known_budget():
    """
    Kein Verbot, sondern eine Bremse: Wächst die Zahl stummer Handler, soll das
    auffallen und begründet werden — statt sich Datei für Datei einzuschleichen.
    """
    total = 0
    for path in list((ROOT / "arcade_scanner").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        if path.name.startswith("._"):
            continue  # macOS-Ressourcenzweige, kein Python
        try:
            total += sum(1 for h in _except_handlers(path) if _is_silent(h))
        except (SyntaxError, UnicodeDecodeError):
            continue

    assert total <= 43, (
        f"{total} stumme except-Blöcke — beim Anlegen dieses Tests waren es 43. "
        "Jeder neue braucht eine Begründung im Code oder gehört laut gemacht."
    )
