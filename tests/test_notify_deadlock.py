"""
test_notify_deadlock.py
-----------------------
Zwei gleichzeitige Anfragen konnten den Server zum Stillstand bringen.

`upsert()`, `bulk_upsert()` und `remove()` riefen `_notify_change()` **innerhalb**
von `_write_lock` auf. Die Beobachter sind fremde Objekte mit eigenen Sperren —
und einer von ihnen, `SimilarityCache`, hielt seine genau dann, wenn er in die
Datenbank hineinliest:

    Anfrage A  /api/similar → SimilarityCache.get() nimmt seine Sperre
               und liest dann get_mean_vectors() → will _write_lock
    Anfrage B  irgendein Schreibvorgang hält _write_lock
               und ruft _notify_change() → will die Sperre von A

Beide warten auf den jeweils anderen. Und weil `_write_lock` dabei gehalten
bleibt, steht danach **jeder** weitere Schreibvorgang — der Server ist dann
nicht langsam, sondern tot. Es braucht dafür nichts Ausgefallenes: Jemand
öffnet ein Video mit der Ähnlich-Leiste, während der Scanner schreibt.

`store_embedding()` hat es von Anfang an richtig gemacht und benachrichtigt
ausserhalb der Sperre. Die drei anderen tun es jetzt auch.

Zusätzlich ist die andere Seite geradegezogen: `SimilarityCache.get()` liest
nicht mehr unter der eigenen Sperre. Eine Verklemmung braucht beide
Richtungen, und wer nur eine repariert, verlässt sich darauf, dass die andere
so bleibt.

Geprüft wird ausgeführt: zwei echte Threads, die genau diese beiden Wege
gleichzeitig gehen. Ohne die Korrektur endet der Test in der Zeitüberschreitung
statt in einer Behauptung — deshalb steht überall ein `timeout`.
"""
import ast
import threading
from pathlib import Path

import pytest

STORE = Path(__file__).parent.parent / "arcade_scanner" / "database" / "sqlite_store.py"


# --- Der Ablauf, der sich verklemmte ---

class LangsamerStore:
    """Bildet die beiden Wege nach: schreiben (mit Sperre) und lesen (mit Sperre)."""

    def __init__(self):
        self._write_lock = threading.RLock()
        self.on_change_callbacks = []
        self.im_lesen = threading.Event()

    def register_on_change(self, cb):
        self.on_change_callbacks.append(cb)

    def _notify_change(self):
        for cb in self.on_change_callbacks:
            try:
                cb()
            except Exception:
                pass

    def get_mean_vectors(self):
        # Der Leser meldet sich, *bevor* er die Schreibsperre haben will —
        # damit der Schreiber garantiert dazwischenkommt.
        self.im_lesen.set()
        with self._write_lock:
            return []

    def upsert_in_der_alten_form(self):
        """Absichtlich die **alte**, gefährliche Form: benachrichtigen unter
        der Sperre.

        So wird geprüft, dass schon die Cache-Seite allein reicht. Beide
        Seiten in der reparierten Form gegeneinander zu stellen würde nichts
        aussagen — es könnte auch nur eine von beiden tragen.
        """
        with self._write_lock:
            self._notify_change()


def test_a_write_and_a_similar_request_do_not_deadlock():
    """
    Der Kern. Ohne die Korrektur kommt keiner der beiden Threads zurück.
    """
    from arcade_scanner.server.routes.similar import SimilarityCache

    store = LangsamerStore()
    cache = SimilarityCache()
    fertig = []

    def liest():
        cache.get(store)
        fertig.append("leser")

    def schreibt():
        store.im_lesen.wait(timeout=5)
        store.upsert_in_der_alten_form()
        fertig.append("schreiber")

    a = threading.Thread(target=liest, daemon=True)
    b = threading.Thread(target=schreibt, daemon=True)
    a.start()
    b.start()
    a.join(timeout=10)
    b.join(timeout=10)

    assert sorted(fertig) == ["leser", "schreiber"], (
        f"Verklemmt — zurückgekommen ist nur: {fertig}"
    )


def test_the_cache_does_not_hold_its_lock_while_reading():
    """
    Die zweite Richtung: Während `get()` liest, muss `invalidate()`
    durchkommen. Vorher wartete es bis zum Ende des Ladens.
    """
    from arcade_scanner.server.routes.similar import SimilarityCache

    cache = SimilarityCache()
    invalidiert = threading.Event()

    class StoreDerWaehrendDesLesensAendert:
        on_change_callbacks: list = []

        def register_on_change(self, cb):
            pass

        def get_mean_vectors(self):
            t = threading.Thread(target=lambda: (cache.invalidate(),
                                                 invalidiert.set()))
            t.start()
            t.join(timeout=5)
            return []

    cache.get(StoreDerWaehrendDesLesensAendert())

    assert invalidiert.is_set(), "invalidate() kam während des Lesens nicht durch"


def test_a_change_during_the_read_is_not_cached():
    """
    Dieselbe Falle wie im Medien-Cache: Wer beim Lesen überholt wurde, legt
    nichts ab.
    """
    from arcade_scanner.server.routes.similar import SimilarityCache

    cache = SimilarityCache()

    class StoreDerDazwischenfunkt:
        def register_on_change(self, cb):
            pass

        def get_mean_vectors(self):
            cache.invalidate()
            return []

    cache.get(StoreDerDazwischenfunkt())

    assert cache._vectors is None


def test_an_undisturbed_read_is_cached():
    from arcade_scanner.server.routes.similar import SimilarityCache

    cache = SimilarityCache()
    gelesen = []

    class RuhigerStore:
        def register_on_change(self, cb):
            pass

        def get_mean_vectors(self):
            gelesen.append(1)
            return []

    cache.get(RuhigerStore())
    cache.get(RuhigerStore())

    assert len(gelesen) == 1


# --- Die Regel im Store ---

def _notify_calls_inside_the_lock():
    """Alle `self._notify_change()`, die innerhalb eines `with self._write_lock`
    stehen — über den AST, nicht über Einrückungszählen."""
    baum = ast.parse(STORE.read_text(encoding="utf-8"))
    treffer = []

    for funktion in ast.walk(baum):
        if not isinstance(funktion, ast.FunctionDef):
            continue
        for knoten in ast.walk(funktion):
            if not isinstance(knoten, ast.With):
                continue
            haelt_sperre = any(
                "_write_lock" in ast.unparse(item.context_expr)
                for item in knoten.items
            )
            if not haelt_sperre:
                continue
            for innen in ast.walk(knoten):
                if (isinstance(innen, ast.Call)
                        and "_notify_change" in ast.unparse(innen.func)):
                    treffer.append(funktion.name)
    return treffer


def test_nothing_notifies_while_holding_the_write_lock():
    """
    Die Regel, auf die es ankommt — und die nächste Schreibmethode wird sie
    sonst wieder brechen.
    """
    assert _notify_calls_inside_the_lock() == []


def test_the_check_would_catch_a_relapse():
    """
    Die Gegenprobe: Der Prüfer oben muss ein Vorkommen auch finden. Sonst
    stünde da eine Behauptung, die immer wahr ist.
    """
    quelle = """
class S:
    def upsert(self):
        with self._write_lock:
            self._notify_change()
"""
    baum = ast.parse(quelle)
    gefunden = []
    for funktion in ast.walk(baum):
        if not isinstance(funktion, ast.FunctionDef):
            continue
        for knoten in ast.walk(funktion):
            if isinstance(knoten, ast.With) and any(
                    "_write_lock" in ast.unparse(i.context_expr) for i in knoten.items):
                for innen in ast.walk(knoten):
                    if (isinstance(innen, ast.Call)
                            and "_notify_change" in ast.unparse(innen.func)):
                        gefunden.append(funktion.name)

    assert gefunden == ["upsert"]


@pytest.mark.parametrize("methode", ["upsert", "bulk_upsert", "remove", "store_embedding"])
def test_every_writer_still_notifies(methode):
    """
    Verschoben, nicht gestrichen: Ohne die Benachrichtigung würde der Cache
    veraltete Einträge ausliefern — und das wäre der schlimmere Fehler.
    """
    quelle = STORE.read_text(encoding="utf-8")
    block = quelle[quelle.index(f"def {methode}("):]
    block = block[:block.index("\n    def ", 10)]

    assert "_notify_change()" in block
