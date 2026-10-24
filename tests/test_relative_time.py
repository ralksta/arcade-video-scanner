"""
test_relative_time.py
---------------------
Ein Auftrag vom April stand als „2952h ago" in der Warteschlange.

`settings.js` hatte für die Alters-Spalte eine eigene kleine Funktion, die bei
Stunden aufhörte. In `formatters.js` steht seit jeher `formatRelativeTime()` —
mit Tagen, Wochen und Monaten. Benutzt hat sie niemand: kein einziger Aufrufer
im ganzen Projekt.

Das ist dasselbe Muster wie beim gesperrten `localStorage` im TV-Client. Die
Antwort lag im Repo, sie war nur nicht angewandt, und daneben stand eine
schlechtere Nachbildung.

Mitgenommen: Ein Zeitstempel aus der **Zukunft** — durch eine falsch gestellte
Uhr auf einem entfernten Arbeiter — ergab „-3 minutes ago". Jetzt „just now".
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "arcade_scanner" / "server" / "static"
HARNESS = Path(__file__).parent / "relative_time_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")

JETZT = 1_700_000_000


def relative(sekunden_her):
    """Wie lange her, aus Sicht eines festen Jetzt."""
    fixture = Path(__file__).parent / "_relative_time_fixture.json"
    fixture.write_text(json.dumps({
        "now": JETZT,
        "cases": [JETZT - s for s in sekunden_her],
    }), encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    finally:
        fixture.unlink(missing_ok=True)


# --- Die Größenordnungen ---

def test_the_scale_goes_all_the_way_up():
    """
    Der Fund: Bei Stunden war Schluss, und ein Auftrag vom April las sich als
    vierstellige Stundenzahl.
    """
    ergebnis = relative([
        30,             # halbe Minute
        300,            # 5 Minuten
        7200,           # 2 Stunden
        3 * 86400,      # 3 Tage
        14 * 86400,     # 2 Wochen
        120 * 86400,    # 4 Monate
    ])

    assert ergebnis == [
        "just now",
        "5 minutes ago",
        "2 hours ago",
        "3 days ago",
        "2 weeks ago",
        "4 months ago",
    ]


def test_the_april_job_reads_as_months():
    """Der Auftrag, an dem es auffiel: 123 Tage alt."""
    assert relative([123 * 86400]) == ["4 months ago"]


# --- Ränder ---

def test_a_timestamp_from_the_future_says_just_now():
    """
    Entsteht durch eine falsch gestellte Uhr auf einem entfernten Arbeiter.
    „-3 minutes ago" wäre die schlechtere Auskunft.
    """
    assert relative([-180]) == ["just now"]


def test_nothing_known_is_empty():
    assert relative([JETZT]) == [""]  # timestamp 0


# --- Es wird auch benutzt ---

def test_the_queue_uses_the_shared_formatter():
    source = (STATIC / "settings.js").read_text(encoding="utf-8")

    assert "formatRelativeTime(ts)" in source


def test_no_second_implementation_is_left():
    """
    Genau daran ist es auseinandergelaufen: Eine Nachbildung neben dem
    Original, die niemand mitpflegt.
    """
    source = (STATIC / "settings.js").read_text(encoding="utf-8")

    assert "`${Math.floor(diff / 3600)}h ago`" not in source


def test_the_formatter_is_loaded_before_its_user():
    from arcade_scanner.templates.dashboard_template import SCRIPT_MODULES

    assert SCRIPT_MODULES.index("formatters.js") < SCRIPT_MODULES.index("settings.js")
