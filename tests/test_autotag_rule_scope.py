"""
test_autotag_rule_scope.py
--------------------------
Eine Auto-Tag-Regel, die auf alles passt.

`video_matches()` gibt für ein leeres Kriterium `True` zurück. Für Smart
Collections ist das die richtige Vorgabe — „nichts eingeschränkt" heißt „alles
zeigen". Für eine **Auto-Tag-Regel** ist dieselbe Antwort etwas ganz anderes:

    POST /api/autotag/rules  {"action":"create","tag":"x","criteria":{}}

Diese Regel schreibt `x` an **jede Datei der Bibliothek**. In dieser
Installation sind das 8788 Einträge. Und weil der Auto-Tagger jeden Tag nur
einmal vergibt (damit ein von Hand entfernter Tag entfernt bleibt), lässt er
sich anschließend nur einzeln wieder abnehmen. Das ist keine Reparatur mehr.

Nachgemessen, welche Kriterien auf alles passen:

    {}                       -> True
    None                     -> True
    {"include": {}}          -> True
    {"gibtsnicht": ["x"]}    -> True      <- ein Tippfehler genügt
    {"include": {"tags": []}} -> True

Der letzte Fall ist der unauffälligste: Ein Formular, das eine leere Auswahl
schickt, sieht aus wie eine Regel und ist keine.

Die Auswertung bleibt, wie sie ist — sie wird von den Smart Collections
mitbenutzt, und dort stimmt sie. Geprüft wird beim **Anlegen** der Regel.
"""
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.core.criteria_eval import narrows_the_selection, video_matches


def a_video(**overrides):
    video = {
        "FilePath": "/media/film.mp4", "Size_MB": 100.0, "Status": "OK",
        "codec": "h264", "tags": [], "favorite": False, "hidden": False,
        "media_type": "video", "width": 1920, "height": 1080, "duration_sec": 60,
    }
    video.update(overrides)
    return video


# --- Was auf alles passt ---

@pytest.mark.parametrize("criteria", [
    {},
    None,
    {"include": {}},
    {"exclude": {}},
    {"gibtsnicht": ["x"]},
    {"include": {"tags": []}},
    {"include": {"status": [], "codec": []}},
    {"duration": {}},
    {"size": {"min": None, "max": None}},
    {"date": {"type": "all"}},
])
def test_these_criteria_match_every_video(criteria):
    """
    Der Beleg zuerst: Diese Kriterien passen tatsächlich auf jedes Video. Ohne
    ihn wäre die Prüfung unten eine Behauptung.
    """
    assert video_matches(a_video(), criteria) is True
    assert video_matches(a_video(Status="HIGH", codec="hevc"), criteria) is True


@pytest.mark.parametrize("criteria", [
    {},
    None,
    {"include": {}},
    {"gibtsnicht": ["x"]},
    {"include": {"tags": []}},
    {"duration": {}},
    {"size": {"min": None, "max": None}},
    {"search": "   "},
    {"date": {"type": "all"}},
    "kein dict",
    [],
])
def test_they_are_recognised_as_not_narrowing_anything(criteria):
    assert narrows_the_selection(criteria) is False


# --- Was etwas einschränkt ---

@pytest.mark.parametrize("criteria", [
    {"include": {"status": ["HIGH"]}},
    {"include": {"codec": ["hevc"]}},
    {"include": {"tags": ["urlaub"]}},
    {"include": {"resolution": ["4k"]}},
    {"include": {"orientation": ["portrait"]}},
    {"include": {"media_type": ["image"]}},
    {"include": {"format": ["mkv"]}},
    {"exclude": {"status": ["OK"]}},
    {"exclude": {"tags": ["privat"]}},
    {"duration": {"min": 60}},
    {"duration": {"max": 600}},
    {"size": {"min": 1000}},
    {"favorites": True},
    {"favorites": False},
    {"favorites": "true"},
    {"search": "urlaub"},
    {"date": {"type": "relative", "relative": "last_7_days"}},
])
def test_a_real_condition_is_recognised(criteria):
    assert narrows_the_selection(criteria) is True


def test_favorites_false_counts_as_a_condition():
    """
    `favorites: False` heisst „nur Nicht-Favoriten" — eine echte Bedingung.
    Ein naives `if criteria.get("favorites")` hätte sie übersehen.
    """
    assert narrows_the_selection({"favorites": False}) is True
    assert video_matches(a_video(favorite=True), {"favorites": False}) is False


def test_a_condition_next_to_junk_still_counts():
    """Ein unbekannter Schlüssel entwertet die übrigen nicht."""
    assert narrows_the_selection({"gibtsnicht": ["x"], "search": "urlaub"}) is True


def test_a_whitespace_only_search_matches_almost_nothing():
    """
    Der eine Fall, bei dem ich falsch lag und der Test es gezeigt hat: Ich
    hatte `{"search": "   "}` zu den Kriterien gezählt, die auf alles passen.
    Das Gegenteil stimmt — `video_matches()` sucht die Leerzeichen wörtlich im
    Dateinamen und findet sie meistens nicht.

    Zurückgewiesen wird die Regel trotzdem, aber aus dem anderen Grund:
    `narrows_the_selection()` schneidet Leerzeichen ab und sieht dann gar keine
    Suchangabe. Beide Wege führen hier zum selben Ergebnis, und beide sind
    richtig — eine Regel aus lauter Leerzeichen ist ein Versehen.
    """
    assert video_matches(a_video(), {"search": "   "}) is False
    assert video_matches(a_video(FilePath="/media/mein film.mp4"), {"search": " "}) is True

    assert narrows_the_selection({"search": "   "}) is False


# --- Die Route ---

def _post(handler_body, route_module):
    """Ruft handle_post mit einem gefälschten Handler auf.

    `_get_deps` wird nur für die Dauer des Aufrufs ersetzt — bliebe die
    Attrappe stehen, würde sie je nach Reihenfolge in
    `tests/test_routes_autotag.py` hineinwirken.
    """
    import json as _json

    body = _json.dumps(handler_body).encode("utf-8")

    handler = MagicMock()
    handler.path = "/api/autotag/rules"
    handler.get_current_user.return_value = "ralf"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile.read.return_value = body

    user = MagicMock()
    user.data.auto_tag_rules = []
    user_db = MagicMock()
    user_db.get_user.return_value = user

    with patch.object(route_module, "_get_deps",
                      return_value=(MagicMock(), user_db)):
        route_module.handle_post(handler)
    return handler, user


def test_a_rule_that_matches_everything_is_refused():
    """
    Der eigentliche Schutz. Vorher wurde die Regel angelegt und beim nächsten
    Lauf an jede Datei der Bibliothek geschrieben.
    """
    from arcade_scanner.server.routes import autotag

    handler, user = _post(
        {"action": "create", "tag": "alles", "criteria": {}}, autotag
    )

    handler.send_error.assert_called_once()
    assert handler.send_error.call_args[0][0] == 400
    assert user.data.auto_tag_rules == [], "Die Regel wurde trotzdem angelegt"


def test_a_typo_in_the_criteria_key_is_refused_too():
    """Der unauffälligere Weg dorthin."""
    from arcade_scanner.server.routes import autotag

    handler, user = _post(
        {"action": "create", "tag": "alles", "criteria": {"inclde": {"status": ["HIGH"]}}},
        autotag,
    )

    assert handler.send_error.call_args[0][0] == 400
    assert user.data.auto_tag_rules == []


def test_the_error_says_why():
    from arcade_scanner.server.routes import autotag

    handler, _ = _post({"action": "create", "tag": "x", "criteria": {}}, autotag)

    message = handler.send_error.call_args[0][1]
    assert "narrow" in message.lower()
    assert "entire library" in message.lower()


def test_a_proper_rule_is_still_created():
    """Die Gegenprobe — sonst hätte ich die Funktion nur abgeschaltet."""
    from arcade_scanner.server.routes import autotag

    handler, user = _post(
        {"action": "create", "tag": "gross",
         "criteria": {"size": {"min": 1000}}},
        autotag,
    )

    handler.send_error.assert_not_called()
    assert len(user.data.auto_tag_rules) == 1
    assert user.data.auto_tag_rules[0]["tag"] == "gross"


def test_a_missing_tag_is_still_refused():
    from arcade_scanner.server.routes import autotag

    handler, user = _post(
        {"action": "create", "tag": "", "criteria": {"size": {"min": 10}}}, autotag
    )

    assert handler.send_error.call_args[0][0] == 400
    assert user.data.auto_tag_rules == []
