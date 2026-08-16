"""
test_optimizer_trim_parsing.py
------------------------------
Die Zeitangaben von `--ss` und `--to` müssen dasselbe bedeuten wie für ffmpeg.

Der Wert geht **roh** an ffmpeg::

    cmd.extend(['-ss', str(ss)])

und wird parallel im Optimizer ausgewertet, um `start_offset` zu bestimmen.
Daraus ergeben sich die SSIM-Vergleichspunkte im Original::

    orig_starts = [start_offset + s for s in opt_starts]

Weichen beide Auslegungen ab, vergleicht die Qualitätsprüfung Bilder von
verschiedenen Stellen des Films. Sie ist die Sicherung, die einen schlechten
Encode davon abhält, das Original zu ersetzen — misst sie an der falschen
Stelle, ist sie wirkungslos.

Vorher lief die Auswertung über `strptime(..., "%H:%M:%S")` und gab bei allem
anderen stillschweigend `0.0` zurück:

| Eingabe | ffmpeg | Optimizer (vorher) |
|---|---|---|
| `1:30` | 90 s | **0 s** |
| `25:00:00` | 90000 s | **0 s** (strptime kennt keine Stunde > 23) |
| `0:0:5.25` | 5,25 s | **0 s** |

Kein Hinweis, kein Fehler — der Encode lief, und die Qualitätsprüfung verglich
Rauschen.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import video_optimizer as vo  # noqa: E402


@pytest.mark.parametrize("value,expected", [
    # Reine Sekunden
    ("90", 90.0),
    ("1.5", 1.5),
    ("0", 0.0),
    # HH:MM:SS
    ("00:01:30", 90.0),
    ("01:00:00", 3600.0),
    ("1:2:3", 3723.0),
    # MM:SS — die Form, die vorher still zu 0 wurde
    ("1:30", 90.0),
    ("0:05", 5.0),
    ("10:00", 600.0),
    # Nachkommastellen
    ("0:0:5.25", 5.25),
    ("00:00:01.5", 1.5),
    # Jenseits von 24 Stunden — strptime lehnte das ab
    ("25:00:00", 90000.0),
    ("100:00:00", 360000.0),
])
def test_parses_the_same_forms_as_ffmpeg(value, expected):
    assert vo.parse_time_to_seconds(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_absent_values_mean_zero(value):
    """Kein Trim angegeben heißt: von Anfang an."""
    assert vo.parse_time_to_seconds(value) == 0.0


@pytest.mark.parametrize("value", ["abc", "1:2:3:4", "::", "1:", ":30", "12:ab"])
def test_unparseable_values_raise_instead_of_returning_zero(value):
    """
    Der Kern des Fundes. Stillschweigend 0 zurückzugeben heißt: das falsche
    Segment kodieren und die Qualitätsprüfung an der falschen Stelle ansetzen.
    """
    with pytest.raises(vo.TimeParseError):
        vo.parse_time_to_seconds(value)


def test_the_error_names_the_value_and_the_allowed_forms():
    with pytest.raises(vo.TimeParseError) as excinfo:
        vo.parse_time_to_seconds("halb drei")

    message = str(excinfo.value)
    assert "halb drei" in message
    assert "HH:MM:SS" in message or "Sekunden" in message


def test_negative_offsets_are_preserved():
    """ffmpeg akzeptiert negative Angaben (relativ zum Ende)."""
    assert vo.parse_time_to_seconds("-10") == -10.0
    assert vo.parse_time_to_seconds("-0:30") == -30.0


# --- Die eigentliche Zusage ---

def test_offset_matches_what_ffmpeg_would_do():
    """
    Gegenprobe zur Begründung: Für jede unterstützte Schreibweise muss unser
    Wert dem entsprechen, was ffmpeg aus derselben Zeichenkette liest.
    ffmpeg liest von rechts — Sekunden, Minuten, Stunden.
    """
    cases = {
        "1:30": 1 * 60 + 30,
        "2:03:04": 2 * 3600 + 3 * 60 + 4,
        "45": 45,
        "0:45": 45,
    }
    for text, ffmpeg_seconds in cases.items():
        assert vo.parse_time_to_seconds(text) == pytest.approx(ffmpeg_seconds), (
            f"{text!r}: wir lesen {vo.parse_time_to_seconds(text)}, "
            f"ffmpeg liest {ffmpeg_seconds}"
        )


def test_main_refuses_to_start_on_an_unreadable_trim():
    """
    Die Prüfung gehört vor den ersten Encode. Ein Abbruch mit klarer Meldung
    ist besser als ein Durchlauf, dessen Qualitätsprüfung nichts aussagt.
    """
    source = (Path(__file__).parent.parent / "scripts" / "video_optimizer.py").read_text(
        encoding="utf-8"
    )
    block = source.split("if args.ss or args.to:", 1)[1].split("files = args.files", 1)[0]

    assert "TimeParseError" in block
    assert "return 1" in block


def test_the_raw_value_still_goes_to_ffmpeg():
    """
    Wir rechnen den Wert nicht um, bevor er an ffmpeg geht — das wäre eine
    zweite Fehlerquelle. Geprüft wird nur, dass beide dasselbe verstehen.
    """
    source = (Path(__file__).parent.parent / "scripts" / "video_optimizer.py").read_text(
        encoding="utf-8"
    )
    assert "cmd.extend(['-ss', str(ss)])" in source


def test_ssim_sample_points_use_the_offset():
    """
    Der Grund, warum die Auswertung überhaupt genau sein muss. Verschwindet
    diese Zeile, verliert dieser Test seinen Anlass — dann gehört er
    überprüft, nicht gelöscht.
    """
    source = (Path(__file__).parent.parent / "scripts" / "video_optimizer.py").read_text(
        encoding="utf-8"
    )
    assert "orig_starts = [start_offset + s for s in opt_starts]" in source
