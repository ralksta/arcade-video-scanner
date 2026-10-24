"""
test_store_encapsulation.py
---------------------------
Niemand außerhalb des Stores fasst ``_conn`` an.

``SQLiteStore`` teilt sich *eine* Verbindung über alle Threads und schützt sie
mit ``_write_lock`` — Lesezugriffe eingeschlossen. Der Grund steht ausführlich
im Store selbst: Pythons sqlite3 hält einen Statement-Cache pro Verbindung,
zwei Threads mit derselben SQL teilen sich ein vorbereitetes Statement und
konsumieren gegenseitig ihre Zeilen. Nichts wirft, das Ergebnis ist einfach
falsch (gemessen: zwischen 0 und 5199 Zeilen bei einer Tabelle mit 800).

``/api/debug/dump`` griff direkt auf ``db._conn`` zu — am Lock vorbei, und ohne
``_ensure_connection()``: vor dem ersten Zugriff ist ``_conn`` noch ``None``,
der Aufruf lief dann in einen AttributeError.
"""
import ast
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent


def _store_in(directory):
    from arcade_scanner.database.sqlite_store import SQLiteStore

    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(directory)
    with patch("arcade_scanner.database.sqlite_store.config", mock_config):
        return SQLiteStore()


def test_no_module_outside_the_store_touches_the_connection():
    """
    Statischer Contract: ``._conn`` gehört dem Store. Wer Diagnosedaten braucht,
    bekommt eine Methode — sonst schleicht sich der nächste ungeschützte
    Zugriff genauso ein wie der letzte.
    """
    allowed = {"sqlite_store.py", "user_store.py"}
    offenders = []

    for path in list((ROOT / "arcade_scanner").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        if path.name.startswith("._") or path.name in allowed:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(source.splitlines(), 1):
            if "._conn" in line and not line.lstrip().startswith("#"):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()[:70]}")

    assert not offenders, (
        "Direkter Zugriff auf die geteilte Verbindung — umgeht _write_lock:\n  "
        + "\n  ".join(offenders)
    )


def test_sample_rows_opens_the_connection_itself(tmp_path):
    """
    Der frühere Aufruf verließ sich darauf, dass jemand anderes die Verbindung
    schon geöffnet hatte. Auf einem frisch gestarteten Server war das nicht so.
    """
    store = _store_in(tmp_path)
    assert store._conn is None, "Vorbedingung: Verbindung noch nicht offen"

    assert store.get_sample_rows(5) == []
    assert store._conn is not None


def test_sample_rows_returns_the_documented_shape(tmp_path):
    from arcade_scanner.models.video_entry import VideoEntry

    store = _store_in(tmp_path)
    store.upsert(VideoEntry(FilePath="/lib/a.mp4", Size_MB=1.0, Status="OK", media_type="video"))

    rows = store.get_sample_rows(5)
    assert rows == [{"path": "/lib/a.mp4", "status": "OK", "type": "video"}]


def test_sample_rows_respects_the_limit(tmp_path):
    from arcade_scanner.models.video_entry import VideoEntry

    store = _store_in(tmp_path)
    for i in range(10):
        store.upsert(VideoEntry(FilePath=f"/lib/{i}.mp4", Size_MB=float(i)))

    assert len(store.get_sample_rows(3)) == 3
    assert store.get_sample_rows(0) == []


def test_sample_rows_holds_the_lock(tmp_path):
    """
    Gegenprobe: Läuft die Abfrage tatsächlich unter ``_write_lock``? Ein
    zweiter Thread darf sie währenddessen nicht betreten.
    """
    store = _store_in(tmp_path)
    store._ensure_connection()

    entered = threading.Event()
    finished = threading.Event()

    def hold_the_lock():
        with store._write_lock:
            entered.set()
            finished.wait(timeout=2)

    holder = threading.Thread(target=hold_the_lock, daemon=True)
    holder.start()
    entered.wait(timeout=2)

    result = {}

    def try_to_read():
        result["rows"] = store.get_sample_rows(1)

    reader = threading.Thread(target=try_to_read, daemon=True)
    reader.start()
    reader.join(timeout=0.3)

    assert reader.is_alive(), "get_sample_rows lief trotz gehaltenem Lock durch"

    finished.set()
    holder.join(timeout=2)
    reader.join(timeout=2)
    assert result.get("rows") == []


def test_debug_route_uses_the_store_method():
    source = (ROOT / "arcade_scanner" / "server" / "api_handler.py").read_text(encoding="utf-8")
    assert "db.get_sample_rows(20)" in source


def test_store_method_is_documented_with_the_reason():
    """
    Ohne die Begründung im Code greift der nächste Diagnose-Patch wieder direkt
    auf die Verbindung zu.
    """
    from arcade_scanner.database.sqlite_store import SQLiteStore

    doc = SQLiteStore.get_sample_rows.__doc__ or ""
    assert "_write_lock" in doc
    assert "_ensure_connection" in doc


def test_ast_finds_no_private_attribute_access_on_db():
    """Wie oben, aber über den Syntaxbaum statt über Textsuche."""
    offenders = []
    for path in (ROOT / "arcade_scanner" / "server").rglob("*.py"):
        if path.name.startswith("._"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and node.attr.startswith("_")
                    and isinstance(node.value, ast.Name)
                    and node.value.id in ("db", "media_db", "store")):
                offenders.append(f"{path.name}:{node.lineno}: {node.value.id}.{node.attr}")

    assert not offenders, "Zugriff auf private Store-Attribute:\n  " + "\n  ".join(offenders)


@pytest.mark.parametrize("limit", [-5, 0])
def test_negative_limit_is_treated_as_zero(tmp_path, limit):
    """SQLite deutet LIMIT -1 als „alles" — das wäre hier das Gegenteil."""
    from arcade_scanner.models.video_entry import VideoEntry

    store = _store_in(tmp_path)
    store.upsert(VideoEntry(FilePath="/lib/a.mp4", Size_MB=1.0))

    assert store.get_sample_rows(limit) == []
