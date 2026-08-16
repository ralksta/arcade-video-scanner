"""
test_client_endpoint_contract.py
--------------------------------
Jeder Endpunkt, den ein Client aufruft, muss es im Server auch geben.

`CLAUDE.md` warnt ausdrücklich: „When changing API responses or filter
semantics, check whether the TV/iOS clients need the same change." Genau das
ist einmal versäumt worden. Commit `8c6008a` („complete removal of VR Gallery
and DeoVR integration") entfernte `core/deovr_generator.py` samt der Routen
`/api/deovr/library` und `/api/deovr/collection/<id>` — der iOS-Client ruft sie
bis heute auf und bekommt seither auf jede Anfrage einen 404.

Aufgefallen ist das niemandem, weil die Clients in eigenen Sprachen leben:
kein Import bricht, kein Test lief darüber, und wer den Server entwickelt,
startet keinen iOS-Simulator.

Dieser Test ist die Brücke: er liest die Endpunkt-Literale aus dem Quelltext
aller Clients und prüft sie gegen die Routen des Servers. Er ersetzt keinen
Integrationstest, aber er hätte diesen Bruch am Tag seiner Entstehung gemeldet.

Bekannte Brüche stehen in KNOWN_BROKEN, mit Begründung. Ein Eintrag dort ist
eine Schuld, kein Freibrief — siehe `dev-docs/ios-client-status.md`.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SERVER_DIR = ROOT / "arcade_scanner" / "server"

CLIENT_SOURCES = {
    "tv_client": list((ROOT / "tv_client" / "src").rglob("*.js")),
    "ios_client": list((ROOT / "ios_client").glob("*.swift")),
    "webos_client": list((ROOT / "webos_client").rglob("*.js")) if (ROOT / "webos_client").is_dir() else [],
}

# Endpunkte, die ein Client aufruft, die es aber nicht (mehr) gibt.
# Jeder Eintrag braucht eine Begründung und einen Weg heraus.
KNOWN_BROKEN = {
    "/api/deovr/library": (
        "Mit 8c6008a serverseitig entfernt, iOS-Client nie migriert — "
        "siehe dev-docs/ios-client-status.md"
    ),
    "/api/deovr/collection": (
        "Mit 8c6008a serverseitig entfernt, iOS-Client nie migriert — "
        "siehe dev-docs/ios-client-status.md"
    ),
}

ENDPOINT_RE = re.compile(r"""["'`]([^"'`]*?/api/[a-zA-Z0-9_/]+)""")


def _server_routes() -> str:
    """Der gesamte Server-Quelltext — dort stehen die Routen als Literale."""
    parts = []
    for path in SERVER_DIR.rglob("*.py"):
        if path.name.startswith("._"):
            continue
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _client_endpoints(paths):
    """(Endpunkt, Fundstelle) je Client-Datei."""
    found = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in ENDPOINT_RE.finditer(source):
            raw = match.group(1)
            endpoint = "/api/" + raw.split("/api/", 1)[1]
            # Interpolationen und Dateiendungen abschneiden: der Routen-Präfix zählt.
            endpoint = endpoint.split("$")[0].split("\\(")[0].split(".json")[0].rstrip("/")
            line = source[:match.start()].count("\n") + 1
            found.append((endpoint, f"{path.relative_to(ROOT)}:{line}"))
    return found


ALL_CLIENT_ENDPOINTS = [
    pytest.param(endpoint, where, client, id=f"{client}:{endpoint}")
    for client, paths in CLIENT_SOURCES.items()
    for endpoint, where in dict(_client_endpoints(paths)).items()
]


@pytest.mark.parametrize("endpoint,where,client", ALL_CLIENT_ENDPOINTS)
def test_client_endpoint_exists_in_the_server(endpoint, where, client):
    if endpoint in KNOWN_BROKEN:
        pytest.xfail(f"Bekannter Bruch: {KNOWN_BROKEN[endpoint]}")

    routes = _server_routes()
    assert endpoint in routes, (
        f"{client} ruft {endpoint} auf ({where}), der Server kennt die Route nicht.\n"
        "Entweder den Client mitziehen oder den Bruch in KNOWN_BROKEN eintragen "
        "— mit Begründung und einem Weg heraus."
    )


def test_at_least_one_endpoint_per_client_was_found():
    """
    Schutz gegen einen Test, der nichts prüft: Ändert ein Client seine
    Schreibweise so, dass die Suche nichts mehr findet, wäre er still
    ungeprüft.
    """
    for client, paths in CLIENT_SOURCES.items():
        if not paths:
            continue
        assert _client_endpoints(paths), f"Keine Endpunkte in {client} gefunden — Suchmuster veraltet?"


def test_known_broken_entries_are_still_broken():
    """
    Gegenprobe: Wird eine Route wieder eingeführt, gehört der Eintrag aus
    KNOWN_BROKEN entfernt — sonst verdeckt er künftige echte Brüche.
    """
    routes = _server_routes()
    resurrected = [ep for ep in KNOWN_BROKEN if ep in routes]
    assert not resurrected, (
        f"Diese Routen gibt es wieder: {resurrected}. Raus aus KNOWN_BROKEN."
    )


def test_known_broken_entries_are_documented():
    doc = ROOT / "dev-docs" / "ios-client-status.md"
    assert doc.is_file(), "Bekannte Brüche brauchen eine Beschreibung, die man abarbeiten kann"

    text = doc.read_text(encoding="utf-8")
    for endpoint in KNOWN_BROKEN:
        assert endpoint in text, f"{endpoint} ist nicht dokumentiert"
