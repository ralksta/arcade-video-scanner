"""
test_gif_parameter_validation.py
--------------------------------
Zahlen aus dem Request-Body des GIF-Exports.

`speed` kam ungeprüft durch und landete im Worker als `1/speed`. Der Guard dort
lautet `if speed != 1.0` — für `speed = 0` ist der wahr. Ergebnis: eine
`ZeroDivisionError` im Worker-Thread, der Job endet als „error" mit der Meldung
„division by zero". Nicht abgestürzt, nicht gehangen, aber für den Nutzer
nicht handhabbar: an der Oberfläche steht ein gescheiterter Export ohne
erkennbaren Grund.

Dasselbe galt für `fps=0` (ffmpeg-Filter `fps=0`), negative Geschwindigkeiten
und `NaN` — letzteres kommt durch jede naive Bereichsprüfung, weil NaN sich mit
allem als False vergleicht.
"""
import pytest

from arcade_scanner.server.routes.queue import _bounded_float, _bounded_int

# --- Ganzzahlen ---

def test_default_is_used_when_key_is_absent():
    assert _bounded_int({}, "fps", 15, 1, 50) == 15


def test_value_inside_the_range_passes():
    assert _bounded_int({"fps": 24}, "fps", 15, 1, 50) == 24


def test_numeric_string_is_accepted():
    """Der Browser schickt Formularwerte gern als String."""
    assert _bounded_int({"fps": "30"}, "fps", 15, 1, 50) == 30


@pytest.mark.parametrize("value", [0, 51, -1, 10_000])
def test_out_of_range_is_rejected(value):
    with pytest.raises(ValueError, match="zwischen"):
        _bounded_int({"fps": value}, "fps", 15, 1, 50)


@pytest.mark.parametrize("value", ["schnell", None, [], {}])
def test_non_numeric_is_rejected(value):
    with pytest.raises(ValueError, match="ganze Zahl"):
        _bounded_int({"fps": value}, "fps", 15, 1, 50)


# --- Gleitkommazahlen ---

def test_speed_zero_is_rejected():
    """Der eigentliche Fund: 1/0 im Worker-Thread."""
    with pytest.raises(ValueError, match="zwischen"):
        _bounded_float({"speed": 0}, "speed", 1.0, 0.1, 10.0)


def test_negative_speed_is_rejected():
    with pytest.raises(ValueError, match="zwischen"):
        _bounded_float({"speed": -2.0}, "speed", 1.0, 0.1, 10.0)


@pytest.mark.parametrize("value", [float("nan"), "nan"])
def test_nan_is_rejected(value):
    """
    NaN vergleicht sich mit allem als False. Eine Prüfung der Form
    `if value < low or value > high: raise` ließe es durch — deshalb steht die
    Bedingung als `not (low <= value <= high)` da.
    """
    with pytest.raises(ValueError, match="zwischen"):
        _bounded_float({"speed": value}, "speed", 1.0, 0.1, 10.0)


@pytest.mark.parametrize("value", [float("inf"), float("-inf")])
def test_infinity_is_rejected(value):
    with pytest.raises(ValueError, match="zwischen"):
        _bounded_float({"speed": value}, "speed", 1.0, 0.1, 10.0)


def test_speed_at_the_boundaries_is_allowed():
    assert _bounded_float({"speed": 0.1}, "speed", 1.0, 0.1, 10.0) == 0.1
    assert _bounded_float({"speed": 10.0}, "speed", 1.0, 0.1, 10.0) == 10.0


def test_error_message_names_the_parameter_and_the_value():
    """
    Die Meldung geht als 400 an den Client. „division by zero" war unbrauchbar;
    hier soll stehen, welcher Wert warum abgelehnt wurde.
    """
    with pytest.raises(ValueError) as excinfo:
        _bounded_float({"speed": 99.0}, "speed", 1.0, 0.1, 10.0)

    message = str(excinfo.value)
    assert "speed" in message
    assert "99" in message
    assert "0.1" in message and "10" in message


# --- Verdrahtung ---

def test_gif_route_validates_before_starting_the_job():
    """
    Die Prüfung gehört an die Grenze. Im Worker-Thread wäre sie zwar auch
    wirksam, der Nutzer bekäme aber nur einen gescheiterten Job statt einer
    Antwort, die sagt, was falsch war.
    """
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes" / "queue.py"
    ).read_text(encoding="utf-8")

    validation = source.index("_bounded_float(data, \"speed\"")
    thread_start = source.index("args=(video_path, output_path, palette_path")
    assert validation < thread_start, "Validierung läuft erst nach dem Thread-Start"
