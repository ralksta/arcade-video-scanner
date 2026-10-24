"""
test_tv_vault_guard.py
----------------------
Derselbe Vault-Fehler wie im Browser-Client — nur auf dem Fernseher.

`MainPanel.js` holt Videos und Nutzerdaten parallel und setzt danach::

    if (userData) {
        ...
        v.hidden = vaultSet.has(v.FilePath);
    }

    setAllVideos(videosData);      // ← lief unabhängig davon

Ist `/api/user/data` nicht erreichbar, wird `userData` zu `null`. Dann bleibt
`v.hidden` auf jedem Eintrag `undefined` — und **jeder** Filter im TV-Client
prüft `!v.hidden`::

    allVideos.filter(v => ... && !v.hidden)          Startseite
    allVideos.filter(v => v.favorite && !v.hidden)   Favoriten
    allVideos.filter(v => v.hidden)                  Vault

`undefined` ist falsy, also stand der gesamte Vault auf der Startseite. Auf
einem Fernseher im Wohnzimmer ist das die denkbar falscheste Richtung des
Fehlers.

Gefunden, weil ich nach dem Fund im Browser-Client (siehe
`tests/test_vault_visibility.py`) dieselbe Frage an den zweiten Client gestellt
habe. Das ist der Grund, warum es diesen Loop gibt: Abweichungen zwischen den
Clients fallen nicht auf, weil niemand beide nebeneinander hält.

Geprüft wird hier am Quelltext. `MainPanel.js` ist ein React-Modul mit JSX; die
Änderung liegt in einem Effekt und im Render, also nicht in einer Funktion, die
sich wie `matchesCollectionCriteria` herausschneiden und einzeln ausführen
liesse (siehe `tests/tv_eval_harness.js`).
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN_PANEL = (ROOT / "tv_client" / "src" / "views" / "MainPanel.js").read_text(
    encoding="utf-8")
FILTER_ENGINE = (
    ROOT / "arcade_scanner" / "server" / "static" / "filter_engine.js"
).read_text(encoding="utf-8")


def code_only(source: str) -> str:
    """Kommentare raus — sonst prüft der Test die Erklärung statt des Codes."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(
        re.sub(r"(^|\s)//.*$", "", line) for line in source.splitlines()
    )


# --- Der Fund ---

def test_missing_user_data_stops_the_library_from_being_shown():
    code = code_only(MAIN_PANEL)

    assert "if (!userData) {" in code, "Der fehlende Fall wird nicht abgefangen"

    guard = code.split("if (!userData) {", 1)[1].split("}", 1)[0]
    assert "setUserDataFailed(true)" in guard
    assert "return" in guard


def test_the_guard_comes_before_the_videos_are_handed_over():
    """
    Die Reihenfolge ist der ganze Punkt: `setAllVideos()` danach, nicht davor.
    """
    code = code_only(MAIN_PANEL)

    assert code.index("if (!userData) {") < code.index("setAllVideos(videosData)")


def test_the_screen_says_why():
    """Ein leerer Fernseher ohne Erklärung wäre die zweitschlechteste Antwort."""
    assert "Nutzerdaten konnten nicht geladen werden" in MAIN_PANEL
    assert "Vault" in MAIN_PANEL


def test_the_grid_is_not_rendered_in_that_state():
    code = code_only(MAIN_PANEL)

    assert "{!loading && !userDataFailed && (" in code, (
        "Die Kachelansicht hängt nicht am neuen Zustand"
    )


# --- Die Filter, um die es geht ---

def test_every_view_relies_on_the_hidden_flag():
    """
    Der Beleg, warum ein fehlendes `hidden` so weit reicht: Es gibt keinen
    zweiten Schutz. Fällt der Wert weg, fällt jede Ansicht auf.
    """
    code = code_only(MAIN_PANEL)

    assert code.count("!v.hidden") >= 4
    assert "allVideos.filter(v => v.hidden)" in code, "Die Vault-Ansicht fehlt"


def test_the_vault_view_itself_would_be_empty_without_user_data():
    """
    Die Kehrseite, die den Fehler so unauffällig machte: Ohne Nutzerdaten war
    die Vault-Ansicht leer — es sah also aus, als sei nichts versteckt, statt
    als sei etwas kaputt.
    """
    code = code_only(MAIN_PANEL)

    assert "allVideos.filter(v => v.hidden)" in code


# --- Gleichstand zwischen den Clients ---

def test_both_clients_guard_against_the_same_thing():
    """
    Der eigentliche Zweck dieses Loops. Fällt der Schutz in einem der beiden
    Clients weg, wird dieser Test rot — und nicht erst der Nutzer stutzig.
    """
    assert "window.userDataLoaded === false" in FILTER_ENGINE
    assert "setUserDataFailed(true)" in MAIN_PANEL


def test_both_clients_read_the_same_endpoint():
    assert "/api/user/data" in MAIN_PANEL
    assert "/api/user/data" in (
        ROOT / "arcade_scanner" / "server" / "static" / "engine.js"
    ).read_text(encoding="utf-8")


def test_the_tv_client_only_uses_endpoints_that_exist():
    """
    Nebenprüfung, nachdem im Browser-Client zwei Knöpfe auf nie gebaute Routen
    zeigten (`/api/user/export`, `/api/user/import`).
    """
    server = ROOT / "arcade_scanner" / "server"
    known = set()
    for py in server.rglob("*.py"):
        if py.name.startswith("._") or "__pycache__" in py.parts:
            continue
        known.update(re.findall(r'"(/api/[a-z0-9_/]+)"', py.read_text(encoding="utf-8")))

    used = set()
    for js in (ROOT / "tv_client" / "src").rglob("*.js"):
        used.update(re.findall(r"['\"`](/api/[a-z0-9_/]+)", code_only(
            js.read_text(encoding="utf-8"))))

    missing = {u for u in used
               if u not in known and not any(k.startswith(u) or u.startswith(k)
                                             for k in known)}
    assert missing == set(), f"TV-Client ruft Routen auf, die es nicht gibt: {missing}"
