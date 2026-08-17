"""
test_duplicate_delete_scope.py
------------------------------
Wessen Dateien darf ein Nutzer über die Duplikat-Routen löschen?

Die Auflistung ist pro Nutzer, das Handeln war es nicht. `handle_post` reicht
für den Duplikat-Scan ausdrücklich die Ziele des angemeldeten Nutzers durch::

    u = user_db.get_user(user_name)
    if u and u.data.scan_targets:
        user_targets = [os.path.abspath(t) for t in u.data.scan_targets if t]

Die beiden **löschenden** Routen daneben — `/api/duplicates/delete` und
`/api/bulk_delete` — riefen `is_path_allowed(abs_path)` ohne zweites Argument
auf. Ohne Angabe fällt die Prüfung auf `config.active_scan_targets` zurück, und
das ist die *Vereinigung der Ziele aller Nutzer*.

Ein Zweitkonto konnte damit über die API Dateien löschen, die es in der
Oberfläche nie zu sehen bekommt — es musste nur den Pfad kennen oder raten.
Bei zwei Konten mit getrennten Bibliotheken ist das der Unterschied zwischen
„getrennt" und „nur getrennt angezeigt".

Admins behalten den vollen Umfang; sie verwalten die Installation.

**Das ist nicht die einzige Stelle.** Kein einziger Aufruf von
`is_path_allowed()` im Projekt übergibt eigene Verzeichnisse — alle sieben
fallen auf die Vereinigung zurück. Behoben sind hier die beiden löschenden;
die übrigen stehen im Übergabebericht, weil sie teils Wege betreffen
(Warteschlangen-Upload, Mac-Worker), deren Kontenzuordnung eine Entscheidung
ist und keine Korrektur.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.security.validators import is_path_allowed
from arcade_scanner.server.routes import duplicates

ROUTE_SOURCE = (
    Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "duplicates.py"
).read_text(encoding="utf-8")


def make_user(targets, is_admin=False):
    u = MagicMock()
    u.is_admin = is_admin
    u.data.scan_targets = list(targets)
    return u


@pytest.fixture
def users():
    """Setzt die Benutzerdatenbank, die `_deletable_scope` befragt."""
    store = MagicMock()

    def _set(**by_name):
        store.get_user.side_effect = lambda n: by_name.get(n)
        return patch.object(
            duplicates, "_get_deps",
            return_value=(None, None, store, 1024, None, None, is_path_allowed),
        )

    return _set


# --- Der Umfang je Konto ---

def test_a_normal_user_is_limited_to_their_own_targets(users):
    with users(privat=make_user(["/media_ralf"])):
        assert duplicates._deletable_scope("privat") == ["/media_ralf"]


def test_an_admin_keeps_the_full_scope(users):
    """None heisst: keine Einschränkung — `is_path_allowed` nimmt seine Vorgabe."""
    with users(admin=make_user(["/media"], is_admin=True)):
        assert duplicates._deletable_scope("admin") is None


def test_an_unknown_user_may_delete_nothing(users):
    with users():
        assert duplicates._deletable_scope("gibtsnicht") == []


def test_a_user_without_targets_may_delete_nothing(users):
    """
    Nicht „alles", sondern „nichts". Wer keine Ziele eingerichtet hat, sieht
    auch keine Medien — eine leere Liste ist die passende Antwort, und die
    ungefährliche.
    """
    with users(neu=make_user([])):
        assert duplicates._deletable_scope("neu") == []


# --- Wie die Prüfung darauf reagiert ---

@pytest.fixture
def two_libraries(tmp_path):
    """Zwei getrennte Bibliotheken mit je einer echten Datei.

    Echte Dateien, weil `is_path_allowed()` zusätzlich auf Existenz prüft —
    ein erdachter Pfad wäre schon deshalb abgelehnt worden, und der Test hätte
    aus dem falschen Grund bestanden.
    """
    for name in ("media_ralf", "media_nas", "media_ralfs_bruder"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "film.mkv").write_bytes(b"x")
    return tmp_path


def test_an_empty_scope_blocks_every_path(two_libraries):
    """
    Der Unterschied, auf dem alles beruht: `None` bedeutet „nimm die Vorgabe",
    `[]` bedeutet „nichts erlaubt". Würde `_deletable_scope` im Zweifel `None`
    liefern, wäre die Einschränkung wirkungslos.
    """
    assert is_path_allowed(str(two_libraries / "media_ralf" / "film.mkv"), []) is False


def test_a_path_inside_the_users_target_is_allowed(two_libraries):
    assert is_path_allowed(
        str(two_libraries / "media_ralf" / "film.mkv"),
        [str(two_libraries / "media_ralf")],
    ) is True


def test_a_path_in_another_users_target_is_refused(two_libraries):
    """Der Fund, in einer Zeile."""
    assert is_path_allowed(
        str(two_libraries / "media_nas" / "film.mkv"),
        [str(two_libraries / "media_ralf")],
    ) is False


def test_a_sibling_directory_with_a_shared_prefix_is_refused(two_libraries):
    """`media_ralf` darf nicht auf `media_ralfs_bruder` passen."""
    assert is_path_allowed(
        str(two_libraries / "media_ralfs_bruder" / "film.mkv"),
        [str(two_libraries / "media_ralf")],
    ) is False


# --- Dass die Routen es auch benutzen ---

@pytest.mark.parametrize("route", ["/api/duplicates/delete", "/api/bulk_delete"])
def test_both_deleting_routes_pass_the_scope(route):
    block = ROUTE_SOURCE.split(f'if path == "{route}":', 1)[1].split("send_response(200)", 1)[0]

    assert "_deletable_scope(user_name)" in block, f"{route} ermittelt keinen Umfang"
    assert "is_path_allowed(abs_path, scope)" in block, (
        f"{route} prüft weiterhin ohne Einschränkung"
    )


def test_no_deleting_route_calls_the_check_without_a_scope():
    """
    Die Gegenprobe: Ein `is_path_allowed(abs_path)` ohne zweites Argument darf
    in dieser Datei nicht mehr vorkommen — sonst hätte jemand eine dritte
    löschende Route ergänzt und die Einschränkung vergessen.
    """
    code = "\n".join(
        ln for ln in ROUTE_SOURCE.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "is_path_allowed(abs_path)" not in code


def test_the_scan_route_still_filters_per_user():
    """Das Verhalten, an dem sich die Löschroute jetzt orientiert."""
    block = ROUTE_SOURCE.split('if path == "/api/duplicates/scan":', 1)[1]
    assert "u.data.scan_targets" in block
