"""
test_no_production_side_effects.py
----------------------------------
Die Test-Suite darf das echte Datenverzeichnis nicht anfassen.

Wie das passieren konnte: ``ReportDebouncer.schedule()`` startet einen
``threading.Timer``, der eine Sekunde später auf einem Daemon-Thread
``_media_cache.get()`` aufruft. Zu dem Zeitpunkt ist der ``config``-Patch des
auslösenden Tests längst abgeräumt — der Timer greift also auf das echte
``db``-Singleton zu, öffnet ``arcade_data/media_library.db`` samt aller
Schema-Migrationen und überschreibt ``arcade_data/index.html``.

Unbemerkt blieb das, weil ein einzelner Testlauf es nicht zuverlässig
reproduziert: oft endet der Prozess, bevor die Sekunde um ist. Erst ein voller
Lauf ist lang genug — und dann fällt es nur auf, wenn man gezielt hinsieht.

Aufgefallen ist es, als eine Schema-Änderung (Entfernen ungenutzter Indizes)
sich plötzlich in der Produktivdatenbank des Entwicklers wiederfand, ohne dass
die Anwendung je gestartet wurde.
"""
import threading

import pytest


def test_report_debouncer_is_neutralised_during_tests():
    """
    Die autouse-Fixture in conftest.py ersetzt ``schedule``. Fällt sie weg,
    schreibt jeder Testlauf wieder ins echte Datenverzeichnis.
    """
    from arcade_scanner.server import api_handler

    # Der Ersatz ist ein Lambda, keine gebundene Methode der Klasse.
    assert not hasattr(api_handler.report_debouncer.schedule, "__self__"), (
        "report_debouncer.schedule ist nicht ersetzt — die autouse-Fixture in "
        "tests/conftest.py fehlt oder greift nicht."
    )


def test_scheduling_starts_no_timer(_no_background_report_generation):
    """Der Ersatz merkt sich den Aufruf, statt einen Thread zu starten."""
    from arcade_scanner.server import api_handler

    before = threading.active_count()
    api_handler.report_debouncer.schedule(8000)

    assert _no_background_report_generation == [8000], "Aufruf wurde nicht protokolliert"
    assert threading.active_count() == before, "Es wurde doch ein Timer gestartet"


def test_no_timer_is_left_running_from_earlier_tests():
    """
    Ein übrig gebliebener Timer würde nach dem Ende der Suite feuern — also
    genau dann, wenn kein Patch mehr aktiv ist.
    """
    from arcade_scanner.server import api_handler

    timer = api_handler.report_debouncer._timer
    assert timer is None or not timer.is_alive(), (
        "Es läuft noch ein Report-Timer; er würde nach dem Testlauf auf die "
        "echte Datenbank zugreifen."
    )


@pytest.mark.parametrize("route", ["settings.py", "queue.py"])
def test_routes_that_schedule_reports_are_covered_by_the_fixture(route):
    """
    Gegenprobe: Diese Routen stoßen den Report an. Sie brauchen keinen eigenen
    Patch, weil die autouse-Fixture greift — aber wenn hier eine Route
    dazukommt, soll klar sein, dass sie derselben Regel unterliegt.
    """
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / route
    ).read_text(encoding="utf-8")
    assert "report_debouncer" in source, (
        f"{route} stößt den Report nicht mehr an — Liste in diesem Test anpassen."
    )
