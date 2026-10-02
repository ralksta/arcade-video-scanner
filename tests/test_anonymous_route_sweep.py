"""
test_anonymous_route_sweep.py
-----------------------------
Jede Route, anonym aufgerufen, am **echten** Server.

Der statische Rundum-Test (`test_debug_route_authorization.py`) liest nur
`api_handler.py`. Die Route-Module sah er nicht — und dort stand
`POST /api/restore` ohne jede Prüfung: Eine anonyme Anfrage überschrieb die
globalen Einstellungen, `ffprobe_path` eingeschlossen. Dieselbe Formlücke wie
bei `/stream` in Nachtlauf 3.

Dieser Test fragt nicht nach dem Quelltext einer Prüfung, sondern nach der
Antwort: Jede Route, die im Server-Code steht, wird ohne Sitzung per GET und
POST aufgerufen. Erlaubt sind 401, 403, 404, 405 und 501 — alles andere muss
unten mit Begründung stehen. Eine neue Route ohne Prüfung fällt damit auf,
egal in welchem Modul und in welcher Schreibweise sie steht.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HELPER = Path(__file__).parent / "anon_sweep_server.py"
REFUSED = {401, 403, 404, 405, 501}

# (Methode, Pfad) → warum diese Route ohne Anmeldung antworten darf.
OPEN_BY_DESIGN = {
    ("GET", "/api/health"): "Gesundheitscheck für Docker/Monitoring",
    ("GET", "/api/health/"): "Gesundheitscheck für Docker/Monitoring",
    ("POST", "/api/logout"): "Abmelden ohne gültige Sitzung ist harmlos",
    ("GET", "/collections/"): "SPA-Route: anonym kommt die Anmeldeseite (wie bei /)",
}


@pytest.fixture(scope="module")
def sweep(tmp_path_factory):
    datadir = tmp_path_factory.mktemp("anon_sweep")
    proc = subprocess.run([sys.executable, str(HELPER), str(datadir)],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)


def test_the_sweep_finds_the_routes(sweep):
    """Ohne diese Probe könnte ein kaputter Regex den Test still leer laufen lassen."""
    paths = {r["path"] for r in sweep}
    for expected in ("/api/videos", "/api/restore", "/api/settings", "/stream?path="):
        assert expected in paths, f"{expected} fehlt in der Routenliste"


def test_no_route_answers_anonymous_callers(sweep):
    open_routes = [
        f"{r['method']} {r['code']} {r['path']}"
        for r in sweep
        if r["code"] not in REFUSED and (r["method"], r["path"]) not in OPEN_BY_DESIGN
    ]
    assert not open_routes, (
        "Diese Routen antworten ohne Anmeldung (Sitzungsprüfung fehlt oder steht "
        "hinter der Eingabeprüfung):\n  " + "\n  ".join(open_routes)
    )
