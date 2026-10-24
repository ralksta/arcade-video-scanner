"""
test_optimizer_encoder_config.py
--------------------------------
Die beiden Funktionen, die bestimmen, *wie* kodiert wird.

`apply_encoding_preset()` übersetzt die Auswahl fast/balanced/best in
Encoder-Argumente, `apply_scale_to_filter()` schreibt die Filterkette um, wenn
herunterskaliert werden soll. Beide sind reine Funktionen — und beide waren
ungetestet, obwohl ein Fehler dort still das falsche Ergebnis erzeugt: eine
wirkungslose Preset-Auswahl fällt niemandem auf, eine kaputte Filterkette
lässt den Encode scheitern.

**Getestet wird gegen die echten Profile aus `ENCODER_PROFILES`**, nicht gegen
erfundene. Ein erster Versuch mit einem selbst gebauten Profil
(`{'encoder_args': ['-rc', 'vbr']}`) legte nahe, die Preset-Wahl bliebe bei
VideoToolbox und VAAPI wirkungslos. Sie ist es nicht — das synthetische Profil
enthielt schlicht keinen der Schlüssel, die dort ersetzt werden. Wer die
Wirklichkeit prüfen will, muss die wirklichen Daten nehmen.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import video_optimizer as vo  # noqa: E402

PRESETS = ("fast", "balanced", "best")


def _args(profile_key: str, preset: str) -> list[str]:
    return vo.apply_encoding_preset(vo.ENCODER_PROFILES[profile_key], preset)["encoder_args"]


# --- Preset-Übersetzung ---

@pytest.mark.parametrize("profile_key", sorted(vo.ENCODER_PROFILES))
def test_the_original_profile_is_never_mutated(profile_key):
    """
    Die Profile sind Modul-Konstanten. Würden sie in Place geändert, träge der
    zweite Encode einer Sitzung das Preset des ersten.
    """
    before = list(vo.ENCODER_PROFILES[profile_key]["encoder_args"])
    vo.apply_encoding_preset(vo.ENCODER_PROFILES[profile_key], "fast")
    vo.apply_encoding_preset(vo.ENCODER_PROFILES[profile_key], "best")

    assert vo.ENCODER_PROFILES[profile_key]["encoder_args"] == before


@pytest.mark.parametrize("profile_key,expected", [
    ("nvenc", {"fast": "p2", "balanced": "p5", "best": "p7"}),
    ("av1_nvenc", {"fast": "p2", "balanced": "p5", "best": "p7"}),
    ("qsv", {"fast": "veryfast", "balanced": "medium", "best": "slow"}),
    ("libx265", {"fast": "veryfast", "balanced": "medium", "best": "slow"}),
])
def test_preset_families_map_to_their_encoder_values(profile_key, expected):
    for preset, value in expected.items():
        args = _args(profile_key, preset)
        assert "-preset" in args, f"{profile_key}/{preset}: kein -preset gesetzt"
        assert args[args.index("-preset") + 1] == value


def test_svtav1_uses_numeric_presets_in_the_right_direction():
    """Bei SVT-AV1 ist die kleinere Zahl die langsamere, bessere Stufe."""
    fast = int(_args("av1_software", "fast")[1])
    balanced = int(_args("av1_software", "balanced")[1])
    best = int(_args("av1_software", "best")[1])

    assert fast > balanced > best, f"Reihenfolge stimmt nicht: {fast}/{balanced}/{best}"


def test_videotoolbox_switches_realtime_not_preset():
    """
    VideoToolbox kennt kein -preset. Der Regler ist -realtime: 1 = schnell,
    0 = mehr Zeit für bessere Kompression.
    """
    fast = _args("videotoolbox", "fast")
    best = _args("videotoolbox", "best")

    assert "-preset" not in fast, "VideoToolbox bekam ein -preset, das es nicht kennt"
    assert fast[fast.index("-realtime") + 1] == "1"
    assert best[best.index("-realtime") + 1] == "0"


def test_vaapi_switches_compression_level():
    """VAAPI kennt weder -preset noch -realtime, wohl aber -compression_level."""
    fast = _args("vaapi", "fast")
    best = _args("vaapi", "best")

    assert "-preset" not in fast
    assert "-realtime" not in fast, "-realtime wurde eingefügt, obwohl VAAPI es nicht kennt"

    fast_level = int(fast[fast.index("-compression_level") + 1])
    best_level = int(best[best.index("-compression_level") + 1])
    assert fast_level > best_level, "Höherer Wert muss die schnellere Stufe sein"


@pytest.mark.parametrize("profile_key", sorted(vo.ENCODER_PROFILES))
def test_every_profile_reacts_to_the_preset_choice(profile_key):
    """
    Der eigentliche Anspruch: Kein Profil darf die Auswahl stillschweigend
    ignorieren. Wer „best" wählt, soll etwas anderes bekommen als bei „fast".
    """
    assert _args(profile_key, "fast") != _args(profile_key, "best"), (
        f"{profile_key}: fast und best erzeugen dieselben Argumente — "
        "die Preset-Wahl bleibt dort wirkungslos"
    )


def test_an_unknown_preset_falls_back_without_crashing():
    args = _args("nvenc", "gibtsnicht")
    assert "-preset" in args


# --- Filterkette beim Herunterskalieren ---

@pytest.mark.parametrize("profile_key", sorted(vo.ENCODER_PROFILES))
def test_scaling_rewrites_exactly_one_scaler(profile_key):
    original = vo.ENCODER_PROFILES[profile_key]["video_filter"]
    scaled = vo.apply_scale_to_filter(original, 720)

    assert "720" in scaled, f"{profile_key}: Zielhöhe fehlt in {scaled!r}"
    assert scaled.count("scale") == original.count("scale"), (
        f"{profile_key}: Anzahl der Scaler hat sich geändert"
    )


@pytest.mark.parametrize("chain,expected", [
    ("format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2", "format=yuv420p,scale=-2:720"),
    ("scale_cuda=trunc(iw/2)*2:trunc(ih/2)*2:format=yuv420p", "scale_cuda=-2:720:format=yuv420p"),
    ("scale_vaapi=w=iw:h=ih:format=nv12", "scale_vaapi=w=-2:h=720:format=nv12"),
])
def test_each_scaler_dialect_is_rewritten_in_its_own_syntax(chain, expected):
    """
    Drei Scaler, drei Schreibweisen. Die Umschreibung darf die jeweils andere
    nicht anwenden — `scale_vaapi=-2:720` wäre für ffmpeg ungültig.
    """
    assert vo.apply_scale_to_filter(chain, 720) == expected


def test_the_rest_of_the_chain_is_left_alone():
    """format=… und HDR-Pixelformate dürfen nicht verloren gehen."""
    chain = "format=yuv420p10le,scale=trunc(iw/2)*2:trunc(ih/2)*2,setparams=colorspace=bt2020nc"
    result = vo.apply_scale_to_filter(chain, 1080)

    assert "format=yuv420p10le" in result
    assert "setparams=colorspace=bt2020nc" in result


@pytest.mark.parametrize("height", [0, -1])
def test_a_non_positive_height_leaves_the_chain_untouched(height):
    chain = "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    assert vo.apply_scale_to_filter(chain, height) == chain


def test_a_chain_without_a_scaler_is_returned_unchanged():
    assert vo.apply_scale_to_filter("format=yuv420p", 720) == "format=yuv420p"


# --- Gegenprobe mit echtem ffmpeg ---

ffmpeg = shutil.which("ffmpeg")


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg not on PATH")
@pytest.mark.parametrize("height", [360, 720, 1080])
def test_the_software_chain_is_accepted_by_ffmpeg(height):
    """
    Statt zu glauben, dass die erzeugte Kette gültig ist: ffmpeg fragen.
    Nur der Software-Pfad — für CUDA und VAAPI fehlt hier die Hardware.
    """
    chain = vo.apply_scale_to_filter(
        vo.ENCODER_PROFILES["libx265"]["video_filter"], height
    )
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=size=1280x720:duration=0.1",
         "-vf", chain, "-frames:v", "1", "-f", "null", "-"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"ffmpeg lehnt {chain!r} ab:\n{result.stderr}"
