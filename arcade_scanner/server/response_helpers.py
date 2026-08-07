"""response_helpers.py - Wiederverwendbare HTTP-Response-Hilfsfunktionen.

Konsolidiert den immer gleichen send_response/send_header/end_headers-
Boilerplate, der zuvor ~47x in api_handler.py dupliziert war.
"""
from __future__ import annotations

import gzip
import json
from http.server import BaseHTTPRequestHandler

# Bodies smaller than this aren't worth the gzip CPU/header overhead.
GZIP_MIN_SIZE = 512


def client_accepts_gzip(handler: BaseHTTPRequestHandler) -> bool:
    """True wenn der Client gzip-komprimierte Antworten akzeptiert."""
    return "gzip" in handler.headers.get("Accept-Encoding", "")


def send_bytes(
    handler: BaseHTTPRequestHandler,
    body: bytes,
    content_type: str,
    status: int = 200,
    cache_control: str | None = None,
    last_modified: float | None = None,
    extra_headers: dict | None = None,
    compress: bool = False,
) -> None:
    """Sendet einen Byte-Body mit Content-Length und optionaler gzip-Kompression.

    Kompression wird nur angewandt wenn ``compress=True``, der Client sie
    akzeptiert und der Body groß genug ist (>= GZIP_MIN_SIZE).
    """
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    if cache_control:
        handler.send_header("Cache-Control", cache_control)
    if last_modified is not None:
        handler.send_header("Last-Modified", handler.date_time_string(last_modified))
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(key, value)
    if compress:
        handler.send_header("Vary", "Accept-Encoding")
        if len(body) >= GZIP_MIN_SIZE and client_accepts_gzip(handler):
            body = gzip.compress(body, compresslevel=6)
            handler.send_header("Content-Encoding", "gzip")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if getattr(handler, "command", "GET") != "HEAD":
        handler.wfile.write(body)


def send_not_modified_if_unchanged(handler: BaseHTTPRequestHandler, mtime: float) -> bool:
    """Sendet 304 Not Modified wenn der If-Modified-Since-Header des Clients
    exakt dem Last-Modified-Wert für ``mtime`` entspricht.

    Exakter String-Vergleich (wie von RFC 9110 für Validatoren empfohlen):
    kein False-Positive-Risiko — bei Nichtübereinstimmung wird schlicht die
    volle Antwort gesendet.

    Returns:
        True wenn 304 gesendet wurde (Caller muss sofort returnen).
    """
    ims = handler.headers.get("If-Modified-Since")
    if ims and ims.strip() == handler.date_time_string(mtime):
        handler.send_response(304)
        handler.end_headers()
        return True
    return False


def send_json(handler: BaseHTTPRequestHandler, data: object, status: int = 200) -> None:
    """Sendet eine JSON-Antwort mit korrektem Content-Type und Content-Length.

    Große Bodies werden gzip-komprimiert wenn der Client es unterstützt.

    Args:
        handler: Der aktive HTTP-Request-Handler.
        data: Serialisierbares Python-Objekt (dict, list, …).
        status: HTTP-Statuscode (default 200).
    """
    body = json.dumps(data, default=str).encode("utf-8")
    send_bytes(handler, body, "application/json", status=status, compress=True)


def send_json_error(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    """Sendet eine JSON-Fehlermeldung mit ``{"error": message}``-Body.

    Args:
        handler: Der aktive HTTP-Request-Handler.
        status: HTTP-Fehlerstatuscode (z. B. 400, 403, 404).
        message: Menschenlesbare Fehlermeldung.
    """
    send_json(handler, {"error": message}, status=status)


def require_auth(handler: BaseHTTPRequestHandler) -> str | None:
    """Prüft ob der Request authentifiziert ist.

    Gibt den Benutzernamen zurück wenn authentifiziert, sendet ansonsten
    automatisch einen 401-Fehler und gibt ``None`` zurück.

    Typische Verwendung::

        user = require_auth(self)
        if user is None:
            return  # 401 wurde bereits gesendet

    Args:
        handler: Der aktive HTTP-Request-Handler (muss ``get_current_user()``
                 definieren).

    Returns:
        Benutzername als str oder None (401 bereits gesendet).
    """
    user = handler.get_current_user()
    if not user:
        send_json_error(handler, 401, "Unauthorized")
    return user

