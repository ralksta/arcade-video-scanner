# arcade_scanner/server/routes/similar.py
"""GET /api/similar — nearest neighbours over stored mean embeddings."""
import os
import threading
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from arcade_scanner.core.similarity import decode_vector, top_k
from arcade_scanner.core.user_scope import visible_path_filter
from arcade_scanner.server.response_helpers import send_json


def _get_deps() -> tuple[Any, Any]:
    from arcade_scanner.server.api_handler import db, user_db
    return db, user_db


class SimilarityCache:
    """Decoded mean vectors, loaded lazily and invalidated on store changes.

    Je Pfad liegt ``(model, vector)``: Vergleichbar sind nur Vektoren
    desselben Modells, siehe ``handle_get``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._vectors: Optional[dict[str, tuple[str, list[float]]]] = None
        self._hooked = False
        self._version = 0

    def invalidate(self) -> None:
        with self._lock:
            self._vectors = None
            self._version += 1

    def get(self, media_db: Any) -> dict[str, tuple[str, list[float]]]:
        """Lädt die Vektoren — **ohne** die eigene Sperre zu halten.

        Vorher lief das Lesen innerhalb der Sperre. Das ist die eine Hälfte
        einer Verklemmung: ``get_mean_vectors()`` will die Schreibsperre der
        Datenbank, und ein gleichzeitiger Schreibvorgang hält sie und will
        über ``_notify_change`` hier herein. Die andere Hälfte ist im Store
        behoben (dort wird jetzt ausserhalb der Sperre benachrichtigt); diese
        Seite gehört trotzdem geradegezogen — eine Verklemmung braucht beide
        Richtungen, und wer nur eine repariert, verlässt sich darauf, dass die
        andere so bleibt.

        Der Zähler übernimmt dabei dieselbe Aufgabe wie in ``_MediaCache``:
        Wird während des Lesens invalidiert, wird das Ergebnis zwar geliefert,
        aber nicht abgelegt.
        """
        with self._lock:
            if not self._hooked:
                # store_embedding fires _notify_change, so fresh indexer runs
                # are picked up without a server restart
                media_db.register_on_change(self.invalidate)
                self._hooked = True
            if self._vectors is not None:
                return self._vectors
            version = self._version

        vectors = {path: (model, decode_vector(blob))
                   for path, model, blob in media_db.get_mean_vectors()}

        with self._lock:
            if version == self._version:
                self._vectors = vectors
        return vectors


_cache = SimilarityCache()


def _handle_status(handler) -> bool:
    """GET /api/similar/status — Abdeckung des Ähnlichkeits-Index.

    Die „Ähnliche Medien"-Leiste bleibt leer, solange der Indexer nicht gelaufen
    ist. Ohne diese Auskunft lässt sich von außen nicht unterscheiden, ob es
    keine ähnlichen Medien gibt oder schlicht keinen Index.
    """
    media_db, _ = _get_deps()
    state = media_db.get_embedding_state()
    total = media_db.count()
    indexed = len(state)
    models = sorted({model for _mtime, model in state.values()})

    send_json(handler, {
        "indexed": indexed,
        "total": total,
        "coverage": round(indexed / total * 100, 1) if total else 0.0,
        "models": models,
    })
    return True


def handle_get(handler) -> bool:
    parsed = urlparse(handler.path)
    if parsed.path not in ("/api/similar", "/api/similar/status"):
        return False

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return True

    if parsed.path == "/api/similar/status":
        try:
            return _handle_status(handler)
        except Exception as e:
            print(f"❌ Error in /api/similar/status: {e}")
            handler.send_error(500, str(e))
            return True

    params = parse_qs(parsed.query)
    query_path = params.get("path", [None])[0]
    if not query_path:
        handler.send_error(400, "Missing path parameter")
        return True
    query_path = os.path.abspath(query_path)
    try:
        limit = max(1, min(int(params.get("limit", ["12"])[0]), 100))
    except ValueError:
        limit = 12

    try:
        media_db, user_db = _get_deps()
        vectors = _cache.get(media_db)
        if not vectors:
            send_json(handler, {"status": "not_indexed"})
            return True
        query_entry = vectors.get(query_path)
        if query_entry is None:
            handler.send_error(404, "File not indexed")
            return True
        query_model, query_vector = query_entry

        # Ohne den Nutzerdatensatz ist nicht bekannt, welche Verzeichnisse
        # ihm gehören. Dann lieber nichts ausliefern: Das fiele sonst in die
        # offene Richtung aus — genau der Fehler, der
        # in beiden Clients steckte.
        u = user_db.get_user(user_name)
        if u is None:
            handler.send_error(503, "User data unavailable")
            return True

        exclude = {query_path}

        # Der Index ist installationsweit, die Bibliotheken sind es nicht.
        # Ohne diese Einschränkung liefert die Suche Pfade aus den Zielen
        # *anderer* Konten zurück, vollständig und mit Verzeichnisnamen.
        # Die Regel steht in core/user_scope.py, damit sie nicht an jeder
        # Stelle neu beantwortet wird.
        may_see = visible_path_filter(u)
        # Nur Vektoren desselben Modells. `media_indexer.py --model X`
        # indiziert Datei für Datei neu; währenddessen — oder nach einem
        # Abbruch dauerhaft — liegen zwei Modelle im Index. Deren
        # Skalarprodukt sieht plausibel aus, vergleicht aber zwei
        # verschiedene Räume; bei anderer Dimension schnitt `zip` still ab.
        candidates = [(p, v) for p, (m, v) in vectors.items()
                      if m == query_model and may_see(p)]

        results = top_k(query_vector, candidates, k=limit, exclude=exclude)
        send_json(handler, {"status": "ok",
                            "results": [{"file_path": p, "score": round(s, 4)}
                                        for p, s in results]})
    except Exception as e:
        print(f"❌ Error in /api/similar: {e}")
        handler.send_error(500, str(e))
    return True
