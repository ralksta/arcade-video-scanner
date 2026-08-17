# arcade_scanner/server/routes/similar.py
"""GET /api/similar — nearest neighbours over stored mean embeddings."""
import os
import threading
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from arcade_scanner.core.similarity import decode_vector, top_k
from arcade_scanner.security import path_is_within
from arcade_scanner.server.response_helpers import send_json


def _get_deps() -> tuple[Any, Any]:
    from arcade_scanner.server.api_handler import db, user_db
    return db, user_db


class SimilarityCache:
    """Decoded mean vectors, loaded lazily and invalidated on store changes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._vectors: Optional[dict[str, list[float]]] = None
        self._hooked = False

    def invalidate(self) -> None:
        with self._lock:
            self._vectors = None

    def get(self, media_db: Any) -> dict[str, list[float]]:
        with self._lock:
            if not self._hooked:
                # store_embedding fires _notify_change, so fresh indexer runs
                # are picked up without a server restart
                media_db.register_on_change(self.invalidate)
                self._hooked = True
            if self._vectors is None:
                self._vectors = {path: decode_vector(blob)
                                 for path, _model, blob in media_db.get_mean_vectors()}
            return self._vectors


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
        query_vector = vectors.get(query_path)
        if query_vector is None:
            handler.send_error(404, "File not indexed")
            return True

        # Ohne den Nutzerdatensatz ist weder bekannt, was im Vault liegt, noch
        # welche Verzeichnisse ihm gehören. Dann lieber nichts ausliefern:
        # Beides fiele sonst in die offene Richtung aus — genau der Fehler, der
        # in beiden Clients steckte.
        u = user_db.get_user(user_name)
        if u is None:
            handler.send_error(503, "User data unavailable")
            return True

        exclude = {query_path}
        exclude.update(os.path.abspath(p) for p in u.data.vaulted)

        # Der Index ist installationsweit, die Bibliotheken sind es nicht.
        # Ohne diese Einschränkung liefert die Suche Pfade aus den Zielen
        # *anderer* Konten zurück — vollständig, mit Verzeichnisnamen. Der
        # Duplikat-Scan und /api/videos filtern an derselben Stelle längst.
        #
        # Dieselbe Regel wie in /api/videos, damit nicht zwei Antworten auf
        # dieselbe Frage im Haus sind: Wer keine Ziele eingerichtet hat, sieht
        # als Admin alles und sonst nichts.
        targets = [os.path.abspath(t) for t in (u.data.scan_targets or []) if t]
        if not targets:
            candidates = list(vectors.items()) if getattr(u, "is_admin", False) else []
        else:
            candidates = [(p, v) for p, v in vectors.items()
                          if any(path_is_within(p, t) for t in targets)]

        results = top_k(query_vector, candidates, k=limit, exclude=exclude)
        send_json(handler, {"status": "ok",
                            "results": [{"file_path": p, "score": round(s, 4)}
                                        for p, s in results]})
    except Exception as e:
        print(f"❌ Error in /api/similar: {e}")
        handler.send_error(500, str(e))
    return True
