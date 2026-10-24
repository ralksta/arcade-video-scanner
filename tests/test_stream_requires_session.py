"""
test_stream_requires_session.py
-------------------------------
Die Dateien selbst waren das Einzige, was der Login nicht geschützt hat.

`/stream` prüfte nur `is_path_allowed()` — also ob der Pfad in einem Scan-Ziel
liegt. Eine Sitzungsprüfung gab es nicht, weder bei GET noch bei HEAD. Wer die
Adresse kannte, bekam die Datei: ohne Anmeldung, ohne Konto, an der
Vault-Markierung vorbei. Das trifft den Kern des Programms — ein Werkzeug, das
mit „privacy-first" antritt und dessen Nutzer es über Tailscale erreichbar
machen.

`is_path_allowed()` prüft gegen `config.active_scan_targets`, und das ist die
Vereinigung über **alle** Konten. Der geschützte Bereich war also nicht „meine
Bibliothek", sondern „alles, was irgendjemand hier eingerichtet hat".

Warum es niemandem auffiel: Der Rundum-Test über alle Routen
(`test_debug_route_authorization.py`) sucht nach Zweigen der Form
`self.path == "/api/..."`. `/stream` wird mit `startswith()` erkannt und fiel
deshalb durch das Raster — der Wächter selbst hatte eine Lücke. Der Test unten
schließt sie.

Beide Clients bringen ihre Kennung längst mit: Der Browser schickt das Cookie
am `<video>`-Element mit, der TV-Client hängt `&token=` an. Für den
Query-Parameter-Zweig in `get_current_user()` gibt es keinen anderen Grund als
genau diesen.

Geprüft wird ausgeführt: Der echte Handler beantwortet eine echte Anfrage, und
der Test sieht sich an, was über die Leitung ginge.
"""
import io
from unittest.mock import patch

import pytest


class FakeHeaders(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)


@pytest.fixture
def datei(tmp_path):
    p = tmp_path / "privat.mp4"
    p.write_bytes(b"DAS IST DER INHALT")
    return p


def anfrage(pfad, method="GET", user=None, headers=None):
    """Baut einen echten FinderHandler ohne Socket und lässt ihn antworten."""
    from arcade_scanner.server.api_handler import FinderHandler

    h = FinderHandler.__new__(FinderHandler)
    h.request_version = "HTTP/1.1"
    h.command = method
    h.path = pfad
    h.requestline = f"{method} {pfad} HTTP/1.1"
    h.client_address = ("192.168.1.99", 5555)
    h.headers = FakeHeaders(headers or {})
    h.wfile = io.BytesIO()
    h.rfile = io.BytesIO()
    h.close_connection = False
    h.log_message = lambda *a, **k: None
    h.get_current_user = lambda: user

    with patch("arcade_scanner.server.api_handler.is_path_allowed", return_value=True):
        if method == "GET":
            h.do_GET()
        else:
            h.do_HEAD()

    return h.wfile.getvalue()


# --- Der Fund ---

def test_an_anonymous_request_gets_no_file(datei):
    antwort = anfrage("/stream?path=" + str(datei))

    assert b"401" in antwort.split(b"\r\n")[0]
    assert b"DAS IST DER INHALT" not in antwort


def test_an_anonymous_head_learns_nothing_either(datei):
    """
    Ohne Prüfung beantwortet HEAD die Frage „gibt es diese Datei und wie groß
    ist sie?" für jeden, der den Pfad rät. Das ist weniger als der Inhalt,
    aber es ist mehr als nichts — und es sagt, wo sich das Suchen lohnt.
    """
    antwort = anfrage("/stream?path=" + str(datei), method="HEAD")

    assert b"401" in antwort.split(b"\r\n")[0]


def test_a_signed_in_request_still_gets_the_file(datei):
    """
    Die andere Hälfte: Der Schutz darf die Wiedergabe nicht kaputtmachen.
    """
    antwort = anfrage("/stream?path=" + str(datei), user="ralf")

    assert b"200" in antwort.split(b"\r\n")[0]
    assert b"DAS IST DER INHALT" in antwort


def test_a_signed_in_head_still_answers(datei):
    antwort = anfrage("/stream?path=" + str(datei), method="HEAD", user="ralf")

    assert b"200" in antwort.split(b"\r\n")[0]


# --- Die Wege, auf denen die Kennung ankommt ---

def test_the_browser_path_is_the_cookie():
    """
    Ein `<video src="/stream?...">` kann keinen Authorization-Header setzen —
    es schickt das Cookie mit. Deshalb muss die Prüfung das Cookie kennen.
    """
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "server"
              / "api_handler.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("def get_current_user"):]
    block = block[:block.index("\n    # LRU thumb")]

    assert "Cookie" in block


def test_the_tv_client_path_is_the_query_token():
    """
    Der TV-Client hängt `&token=` an. Gäbe es diesen Zweig nicht, hätte die
    Sitzungspflicht die Wiedergabe auf dem Fernseher abgeschaltet.
    """
    from pathlib import Path

    tv = (Path(__file__).parent.parent / "tv_client" / "src" / "App"
          / "App.js").read_text(encoding="utf-8")

    assert "/stream?path=" in tv
    assert "token=" in tv


# --- Die Lücke im Wächter ---

def test_the_route_sweep_also_covers_startswith_branches():
    """
    Der Rundum-Test suchte nur nach `self.path == "/api/..."`. `/stream` wird
    mit `startswith()` erkannt und war deshalb nie dabei. Ein Wächter, der
    eine ganze Erkennungsform übersieht, meldet Ruhe, wo keine ist.
    """
    import ast
    import re
    from pathlib import Path

    handler = (Path(__file__).parent.parent / "arcade_scanner" / "server"
               / "api_handler.py")
    tree = ast.parse(handler.read_text(encoding="utf-8"))

    ungeschuetzt = []
    for methode in ("do_GET", "do_HEAD"):
        funktion = next((n for n in ast.walk(tree)
                         if isinstance(n, ast.FunctionDef) and n.name == methode), None)
        assert funktion is not None, f"{methode} nicht gefunden"

        for node in ast.walk(funktion):
            if not isinstance(node, ast.If):
                continue
            test = ast.unparse(node.test)
            treffer = re.search(r"self\.path\.startswith\(\s*[\"']([^\"']+)", test)
            if not treffer:
                continue
            route = treffer.group(1)
            if route in ERLAUBT_OHNE_SITZUNG:
                continue

            körper = "\n".join(ast.unparse(stmt) for stmt in node.body)
            if "get_current_user" not in körper and "require_auth" not in körper:
                ungeschuetzt.append(f"{methode}: {route}")

    assert not ungeschuetzt, (
        "Route ohne Sitzungsprüfung:\n  " + "\n  ".join(ungeschuetzt)
        + "\nEntweder prüfen oder in ERLAUBT_OHNE_SITZUNG eintragen."
    )


# Zweige, die bewusst ohne Sitzung erreichbar sind — mit Begründung.
ERLAUBT_OHNE_SITZUNG = {
    # Vorschaubilder. Ihre Namen sind Hashes des Quellpfades, der Inhalt ist
    # ein verkleinertes Standbild. Eine Sitzungspflicht hier würde die
    # Vorschaubilder im TV-Client abschalten: `thumbnailUrl()` in
    # `tv_client/src/serverConfig.js` hängt keinen Token an, und ein Cookie
    # gibt es dort nicht. Das ist eine Entscheidung für den Betreiber, keine,
    # die ein Testlauf nebenbei trifft — sie steht im Übergabebericht.
    "/thumbnails/",
    # Stylesheets, Skripte und die Login-Seite selbst. Ohne sie gäbe es keine
    # Anmeldemaske.
    "/static/",
    "/arcade_scanner/",
}
