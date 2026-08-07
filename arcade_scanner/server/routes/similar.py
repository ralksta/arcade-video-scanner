# arcade_scanner/server/routes/similar.py
"""GET /api/similar — nearest neighbours over stored mean embeddings."""
import os
import threading
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from arcade_scanner.core.similarity import decode_vector, top_k
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


def handle_get(handler) -> bool:
    parsed = urlparse(handler.path)
    if parsed.path != "/api/similar":
        return False

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
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

        exclude = {query_path}
        u = user_db.get_user(user_name)
        if u and u.data.vaulted:
            exclude.update(os.path.abspath(p) for p in u.data.vaulted)

        results = top_k(query_vector, vectors.items(), k=limit, exclude=exclude)
        send_json(handler, {"status": "ok",
                            "results": [{"file_path": p, "score": round(s, 4)}
                                        for p, s in results]})
    except Exception as e:
        print(f"❌ Error in /api/similar: {e}")
        handler.send_error(500, str(e))
    return True
