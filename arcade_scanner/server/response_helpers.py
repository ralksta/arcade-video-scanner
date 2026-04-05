"""response_helpers.py - Wiederverwendbare HTTP-Response-Hilfsfunktionen.

Konsolidiert den immer gleichen send_response/send_header/end_headers-
Boilerplate, der zuvor ~47x in api_handler.py dupliziert war.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from arcade_scanner.config import MAX_REQUEST_SIZE


def send_json(handler: BaseHTTPRequestHandler, data: object, status: int = 200) -> None:
    """Sendet eine JSON-Antwort mit korrektem Content-Type und Content-Length.

    Args:
        handler: Der aktive HTTP-Request-Handler.
        data: Serialisierbares Python-Objekt (dict, list, …).
        status: HTTP-Statuscode (default 200).
    """
    body = json.dumps(data, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


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

