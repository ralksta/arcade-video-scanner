"""
test_security_headers.py
------------------------
Jede Antwort trägt die Sicherheitskopfzeilen.

Der Server schickte **keine einzige** davon: kein `nosniff`, kein
`X-Frame-Options`, keine `Referrer-Policy`, keine CSP. Bei einer angemeldeten
Oberfläche, die Dateien löschen und verschieben kann, ist besonders der
fehlende Rahmenschutz greifbar: Ohne ihn lässt sich die Seite in einen fremden
Rahmen legen und der Nutzer auf Schaltflächen locken, die er nicht sieht.

Geprüft wird an `end_headers()` selbst, nicht an einer einzelnen Route —
genau darum geht es: dass keine Antwort daran vorbeikommt, egal aus welchem
Zweig sie stammt.
"""
import io

import pytest


def _handler(command="GET", origin=None):
    """Ein FinderHandler ohne echten Socket, wie in test_http_performance.py."""
    from arcade_scanner.server.api_handler import FinderHandler

    class FakeHeaders(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    h = FinderHandler.__new__(FinderHandler)
    h.request_version = "HTTP/1.1"
    h.requestline = f"{command} /test HTTP/1.1"
    h.client_address = ("127.0.0.1", 12345)
    h.command = command
    h.path = "/test"
    h.headers = FakeHeaders({"Origin": origin} if origin else {})
    h.wfile = io.BytesIO()
    h.close_connection = False
    return h


def _kopfzeilen(command="GET", origin=None, status=200):
    h = _handler(command, origin)
    h.send_response(status)
    h.send_header("Content-Length", "0")
    h.end_headers()
    roh = h.wfile.getvalue().decode("latin-1")
    gefunden = {}
    for zeile in roh.split("\r\n"):
        if ": " in zeile:
            name, _, wert = zeile.partition(": ")
            gefunden.setdefault(name.lower(), []).append(wert)
    return gefunden


@pytest.mark.parametrize("name,wert", [
    ("x-content-type-options", "nosniff"),
    ("x-frame-options", "DENY"),
    ("referrer-policy", "same-origin"),
])
def test_kopfzeile_liegt_auf_jeder_antwort(name, wert):
    for command in ("GET", "POST", "HEAD"):
        gefunden = _kopfzeilen(command)
        assert gefunden.get(name) == [wert], f"{name} fehlt bei {command}"


def test_auch_auf_fehlerantworten():
    """Eine 401 vom Anmeldezweig ist genauso eine Seite wie jede andere."""
    gefunden = _kopfzeilen(status=401)
    assert gefunden.get("x-frame-options") == ["DENY"]


def test_csp_deckt_ab_was_die_oberflaeche_wirklich_laedt():
    csp = _kopfzeilen()["content-security-policy"][0]
    # Tailwind vom CDN und die Google-Schriften stehen in index.html bzw.
    # login.html. Fehlt eins davon in der Richtlinie, bleibt die Oberflaeche
    # ungestaltet -- das ist der teure Fehler bei einer CSP.
    assert "https://cdn.tailwindcss.com" in csp
    assert "https://fonts.googleapis.com" in csp
    assert "https://fonts.gstatic.com" in csp
    # 57 onclick-Attribute in den Seiten: ohne das steht die Oberflaeche still.
    assert "'unsafe-inline'" in csp


def test_csp_schliesst_die_wege_nach_draussen():
    csp = _kopfzeilen()["content-security-policy"][0]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "base-uri 'self'" in csp


def test_kopfzeilen_stehen_nur_einmal():
    """Doppelte CSP-Zeilen mit verschiedenen Werten ignorieren Browser
    teilweise ganz — dann waere die Richtlinie wirkungslos."""
    gefunden = _kopfzeilen()
    for name in ("content-security-policy", "x-frame-options",
                 "x-content-type-options", "referrer-policy"):
        assert len(gefunden[name]) == 1, f"{name} steht mehrfach"
