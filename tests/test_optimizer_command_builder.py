"""
test_optimizer_command_builder.py
---------------------------------
`build_ffmpeg_command()` — die Stelle, an der aus einem Profil ein Aufruf wird.

Die Funktion kodiert mehrere Regeln, die im Code als Kommentar stehen und deren
Verletzung teuer ist:

- **VideoToolbox**: `-q:v` und `-b:v` schließen einander aus. Sind beide da,
  ignoriert der Encoder `-b:v` und arbeitet im Qualitätsmodus — die
  Größenvorgabe wäre wirkungslos, ohne dass etwas scheitert.
- **SVT-AV1**: stürzt ab, wenn `-crf` mit `-b:v` kombiniert wird. Hier muss die
  Qualitätsangabe immer gesetzt und `-b:v` immer weggelassen werden.
- **Trim vor Eingabe**: `-ss` und `-to` gehören vor `-i`, sonst dekodiert
  ffmpeg von vorn (langsames Seeking).
- **`-bufsize`**: fehlt eine Angabe, wird das Doppelte von `-maxrate` gesetzt.

Solche Regeln überleben Refactorings nur, wenn sie geprüft werden — im Kommentar
stehen sie schon.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import video_optimizer as vo  # noqa: E402

PROFILES = vo.ENCODER_PROFILES


def _cmd(profile_key: str, **kwargs) -> list[str]:
    return vo.build_ffmpeg_command(
        "in.mp4", "out.mp4", PROFILES[profile_key], 50, **kwargs
    )


def _value_after(cmd: list[str], flag: str):
    return cmd[cmd.index(flag) + 1] if flag in cmd else None


# --- Die dokumentierten Ausschlussregeln ---

def test_videotoolbox_drops_quality_flag_when_a_target_bitrate_is_set():
    """
    Beide gesetzt heißt: VideoToolbox ignoriert -b:v und die Größenvorgabe
    verpufft — ohne Fehlermeldung.
    """
    with_target = _cmd("videotoolbox", target_bitrate_kbps=4000)
    without = _cmd("videotoolbox")

    assert "-q:v" not in with_target
    assert "-b:v" in with_target
    assert "-q:v" in without, "Ohne Zielbitrate fehlt die Qualitätsangabe"


def test_svtav1_keeps_crf_and_never_gets_a_target_bitrate():
    """SVT-AV1 stürzt bei -crf zusammen mit -b:v ab."""
    cmd = _cmd("av1_software", target_bitrate_kbps=4000)

    assert "-crf" in cmd, "CRF fehlt — SVT-AV1 steuert die Größe darüber"
    assert "-b:v" not in cmd, "-b:v würde den Encoder abstürzen lassen"


@pytest.mark.parametrize("profile_key", ["nvenc", "qsv", "libx265", "vaapi"])
def test_other_encoders_use_the_target_bitrate(profile_key):
    cmd = _cmd(profile_key, target_bitrate_kbps=4000)
    assert _value_after(cmd, "-b:v") == "4000k"


# --- Trim ---

def test_seek_arguments_come_before_the_input():
    """Hinter -i gestellt dekodiert ffmpeg von Anfang an — deutlich langsamer."""
    cmd = _cmd("libx265", ss="00:01:00", to="00:02:00")

    assert cmd.index("-ss") < cmd.index("-i")
    assert cmd.index("-to") < cmd.index("-i")


def test_the_trim_values_are_passed_through_unchanged():
    """
    Wir rechnen sie nicht um. Genau deshalb muss `parse_time_to_seconds()`
    dieselbe Auslegung haben — siehe tests/test_optimizer_trim_parsing.py.
    """
    cmd = _cmd("libx265", ss="1:30", to="2:45")

    assert _value_after(cmd, "-ss") == "1:30"
    assert _value_after(cmd, "-to") == "2:45"


def test_without_a_trim_no_seek_arguments_appear():
    cmd = _cmd("libx265")
    assert "-ss" not in cmd and "-to" not in cmd


# --- Bitraten-Deckel ---

def test_bufsize_defaults_to_twice_the_maxrate():
    cmd = _cmd("libx265", maxrate_kbps=5000)
    assert _value_after(cmd, "-maxrate") == "5000k"
    assert _value_after(cmd, "-bufsize") == "10000k"


def test_an_explicit_bufsize_wins():
    cmd = _cmd("libx265", maxrate_kbps=5000, bufsize_kbps=7000)
    assert _value_after(cmd, "-bufsize") == "7000k"


def test_no_maxrate_means_no_bufsize():
    cmd = _cmd("libx265")
    assert "-maxrate" not in cmd and "-bufsize" not in cmd


# --- Weitergabe an die Filterkette ---

def test_scale_height_reaches_the_video_filter():
    cmd = _cmd("libx265", scale_height=720)
    assert "720" in _value_after(cmd, "-vf")


def test_without_scale_height_the_profile_filter_is_used_verbatim():
    cmd = _cmd("libx265")
    assert _value_after(cmd, "-vf") == PROFILES["libx265"]["video_filter"]


# --- Audio ---

def test_copy_audio_skips_every_audio_filter():
    cmd = _cmd("libx265", copy_audio=True)
    assert _value_after(cmd, "-c:a") == "copy"
    assert "-af" not in cmd


def test_standard_audio_mode_re_encodes_without_normalisation():
    cmd = _cmd("libx265", audio_mode="standard")
    assert _value_after(cmd, "-c:a") == "aac"


@pytest.mark.parametrize("mode", ["moderate", "enhanced"])
def test_normalising_modes_add_a_filter_chain(mode):
    cmd = _cmd("libx265", audio_mode=mode)
    assert "-af" in cmd
    assert "loudnorm" in _value_after(cmd, "-af")


# --- Copy-Modus ---

def test_video_copy_mode_encodes_nothing():
    cmd = _cmd("libx265", video_mode="copy")

    assert _value_after(cmd, "-c:v") == "copy"
    assert "-vf" not in cmd, "Ein Filter im Copy-Modus erzwingt eine Neukodierung"
    assert "-crf" not in cmd and "-q:v" not in cmd


# --- Gegenprobe mit echtem ffmpeg ---

ffmpeg = shutil.which("ffmpeg")


@pytest.mark.skipif(ffmpeg is None, reason="ffmpeg not on PATH")
@pytest.mark.parametrize("kwargs", [
    {},
    {"scale_height": 360},
    {"maxrate_kbps": 2000},
    {"target_bitrate_kbps": 1500},
    {"audio_mode": "standard"},
])
def test_the_software_command_is_accepted_by_ffmpeg(tmp_path, kwargs):
    """
    Der stärkste verfügbare Beleg: den erzeugten Aufruf tatsächlich laufen
    lassen — mit einer winzigen synthetischen Quelle statt einer Mediendatei.

    Der Codec bleibt libx265, nur das Preset wird auf ultrafast gesetzt. Ein
    erster Versuch tauschte auf x264, um Zeit zu sparen — das schlug fehl, weil
    der Builder `-tag:v hvc1` setzt, was zu H.264 nicht passt. Der Aufruf ist
    also nur *als Ganzes* prüfbar; ein ausgetauschter Codec prüft etwas anderes
    als das, was in Wirklichkeit läuft.
    """
    profile = dict(PROFILES["libx265"])
    profile["encoder_args"] = ["-preset", "ultrafast"]

    source = tmp_path / "src.mp4"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x240:duration=0.5",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         str(source)],
        check=True, capture_output=True, timeout=120,
    )

    out = tmp_path / "out.mp4"
    cmd = vo.build_ffmpeg_command(source, out, profile, 30, **kwargs)
    cmd = [ffmpeg if part == "ffmpeg" else part for part in cmd]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, (
        f"ffmpeg lehnt den erzeugten Aufruf ab ({kwargs}):\n"
        f"{' '.join(str(c) for c in cmd)}\n{result.stderr[-1500:]}"
    )
    assert out.exists() and out.stat().st_size > 0
