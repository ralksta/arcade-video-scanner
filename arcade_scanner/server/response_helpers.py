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


def read_json_body(handler: BaseHTTPRequestHandler) -> dict | list | None:
    """Liest den Request-Body und parst ihn als JSON.

    Prüft außerdem gegen ``MAX_REQUEST_SIZE`` um DoS zu verhindern.
    Bei Fehler wird der passende HTTP-Error **bereits gesendet** und ``None``
    zurückgegeben.

    Args:
        handler: Der aktive HTTP-Request-Handler.

    Returns:
        Geparste JSON-Daten oder None (Fehler wurde bereits gesendet).
    """
    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except (ValueError, TypeError):
        send_json_error(handler, 400, "Invalid Content-Length")
        return None

    if content_length > MAX_REQUEST_SIZE:
        handler.send_error(413, "Request payload too large")
        return None

    try:
        raw = handler.rfile.read(content_length)
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        send_json_error(handler, 400, f"Invalid JSON: {exc}")
        return None
