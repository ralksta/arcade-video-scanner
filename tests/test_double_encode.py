"""
test_double_encode.py
---------------------
Kann dieselbe Datei zweimal gleichzeitig umgewandelt werden?

Es gibt zwei voneinander unabhängige Wege:

    Warteschlange   /api/queue/next  →  mac_worker.py auf einem anderen Rechner
    direkt          video_optimizer.py bzw. batch_controller.py, lokal

Der erste ist gegen Doppelbelegung abgesichert — `get_next_pending()` übernimmt
per Compare-and-Swap, und der Kommentar dort sagt auch warum: „Without that
check two workers encode the same file and race on the same output path."

Der zweite fragte nirgends nach. `/compress` und `/batch_compress` prüften den
Pfad auf Gültigkeit und die Datei auf Existenz — nicht aber, ob gerade ein Mac
an derselben Datei arbeitet. Damit ließ sich genau der Zustand herstellen, den
die Übernahme in der Warteschlange verhindert:

    zwei Encoder, dieselbe Quelle, derselbe Zielname
    einer löscht das Original, während der andere noch daraus liest

Auffällig ist, dass `candidates.py:42` dieselbe Menge bereits benutzt, um
belegte Dateien aus den Vorschlägen zu nehmen. Die Information war also da —
nur an den beiden Stellen, die tatsächlich einen Encoder starten, wurde sie
nicht abgefragt.

**Was hier nicht abgedeckt ist:** zwei *lokale* Läufe derselben Datei. Die
tauchen in keiner Warteschlange auf, weil `batch_controller.py` und
`video_optimizer.py` gar nicht mit ihr sprechen. Das zu schließen hieße, lokale
Umwandlungen dort einzutragen — eine Entwurfsänderung, keine Korrektur. Steht
im Übergabebericht.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import files as files_route

ROUTE_SOURCE = (
    Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "files.py"
).read_text(encoding="utf-8")


@pytest.fixture
def queue_holds():
    """Legt fest, welche Pfade die Warteschlange als belegt meldet."""
    def _set(*paths, raises=None):
        fake = MagicMock()
        if raises is not None:
            fake.get_active_queue_paths.side_effect = raises
        else:
            fake.get_active_queue_paths.return_value = set(paths)
        return patch.object(files_route, "db", fake)
    return _set


# --- Die Prüfung selbst ---

def test_a_queued_file_is_reported_as_busy(queue_holds):
    with queue_holds("/media/film.mkv"):
        assert files_route._busy_in_queue(["/media/film.mkv"]) == {"/media/film.mkv"}


def test_an_untouched_file_is_free(queue_holds):
    with queue_holds("/media/anderes.mkv"):
        assert files_route._busy_in_queue(["/media/film.mkv"]) == set()


def test_a_mixed_selection_reports_only_the_busy_ones(queue_holds):
    with queue_holds("/media/b.mkv"):
        busy = files_route._busy_in_queue(["/media/a.mkv", "/media/b.mkv", "/media/c.mkv"])

    assert busy == {"/media/b.mkv"}


def test_an_unreadable_queue_does_not_block_everything(queue_holds, capsys):
    """
    Die Prüfung soll einen Doppellauf verhindern, nicht die Funktion lahmlegen.
    Fällt die Warteschlange aus, wird nicht blockiert — und es steht in der
    Ausgabe, damit es nicht unbemerkt bleibt.
    """
    with queue_holds(raises=OSError("db weg")):
        assert files_route._busy_in_queue(["/media/film.mkv"]) == set()

    assert "nicht lesbar" in capsys.readouterr().out


# --- Die beiden Startpunkte ---

def test_the_single_optimize_route_checks_before_launching():
    block = ROUTE_SOURCE.split("def _handle_compress", 1)[1].split("def _sanitize_media_path", 1)[0]
    code = "\n".join(
        ln for ln in block.splitlines() if not ln.lstrip().startswith("#")
    )

    assert "_busy_in_queue" in code
    assert code.index("_busy_in_queue") < code.index("subprocess.Popen"), (
        "Die Prüfung steht hinter dem Start des Encoders"
    )


def test_the_batch_route_checks_before_launching():
    block = ROUTE_SOURCE.split("def _handle_batch_compress", 1)[1].split("def _run_rescan_in_background", 1)[0]
    code = "\n".join(
        ln for ln in block.splitlines() if not ln.lstrip().startswith("#")
    )

    assert "_busy_in_queue" in code
    assert code.index("_busy_in_queue") < code.index("batch_controller_path")


def test_the_batch_route_skips_rather_than_aborts():
    """
    Eine belegte Datei in der Auswahl darf die anderen nicht mit aufhalten —
    sonst blockiert ein einziger laufender Job eine Auswahl von fünfzig.
    """
    block = ROUTE_SOURCE.split("def _handle_batch_compress", 1)[1]
    assert "validated_paths = [p for p in validated_paths if p not in busy]" in block


def test_the_single_route_refuses_instead_of_skipping():
    """
    Bei genau einer Datei gibt es nichts zu überspringen — hier ist eine
    Fehlermeldung die ehrliche Antwort, kein stilles Nichtstun.
    """
    block = ROUTE_SOURCE.split("def _handle_compress", 1)[1].split("def _sanitize_media_path", 1)[0]
    assert "send_error(" in block.split("_busy_in_queue", 1)[1][:400]
    assert "409" in block.split("_busy_in_queue", 1)[1][:400]


# --- Der Weg, der schon abgesichert war ---

def test_the_queue_itself_still_claims_atomically():
    """
    Zur Abgrenzung: Die Warteschlange war nie das Problem. Ihre Übernahme ist
    ein Compare-and-Swap, und ein Zähler von 0 bedeutet, dass ein anderer
    Arbeiter schneller war.
    """
    store = (
        Path(__file__).parent.parent / "arcade_scanner" / "database" / "sqlite_store.py"
    ).read_text(encoding="utf-8")
    block = store.split("def get_next_pending", 1)[1].split("def _reclaim_stale_locked", 1)[0]

    assert "AND status = 'pending'" in block, "Die Übernahme ist kein Compare-and-Swap mehr"
    assert "rowcount == 0" in block


def test_the_candidates_route_already_used_the_same_information():
    """
    Der Beleg, dass die Information vorhanden war: Sie wurde nur an den
    Stellen nicht abgefragt, die einen Encoder starten.
    """
    candidates = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "candidates.py"
    ).read_text(encoding="utf-8")

    assert "get_active_queue_paths" in candidates
