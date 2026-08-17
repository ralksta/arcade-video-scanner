"""
test_duplicate_recommendation.py
--------------------------------
`recommended_keep` — die Datei, die die Oberfläche als „behalten" vorschlägt,
während sie für die anderen einen Löschknopf anbietet.

Sie ist schlicht die erste nach dem Sortieren::

    dup_files.sort(key=lambda f: f.quality_score, reverse=True)
    recommended_keep = dup_files[0].path

Damit hängt alles an der Frage, wie oft zwei Dateien denselben Punktwert
bekommen. Antwort: ständig. Der Bitratenanteil ist bei **50 Punkten**
gedeckelt, also ab 25 Mbps::

    _calculate_video_quality_score:  score += min(bitrate * 2, 50)

Eine 4K-Quelle mit 80 Mbps und ihr 4K-Re-Encode mit 26 Mbps bekommen beide
50 + 30 Punkte. Nachgerechnet: **85,0 gegen 85,0**. In einer Re-Encode-Gruppe
fällt zusätzlich der Codec-Anteil weg — bewusst, weil dort der moderne Codec
gerade die verlustbehaftete Kopie kennzeichnet. Damit bleibt nichts mehr, was
die beiden trennt.

Python sortiert stabil, also entschied die Reihenfolge, in der die Dateien aus
der Datenbank kamen, welche empfohlen wird. Bei Re-Encodes ist das genau die
Frage, um die es geht: Die Empfehlung konnte auf das Original zeigen oder auf
die Kopie — je nachdem.

Der Deckel bleibt, damit sich die Punktwerte insgesamt nicht verschieben. Bei
Gleichstand entscheiden jetzt Bitrate, dann Größe, zuletzt der Pfad.
"""
from unittest.mock import MagicMock

import pytest

from arcade_scanner.core.duplicate_detector import DuplicateDetector


@pytest.fixture
def detector():
    return DuplicateDetector()


def video(path, bitrate, codec="h264", width=3840, height=2160, size_mb=None):
    v = MagicMock()
    v.file_path = path
    v.bitrate_mbps = bitrate
    v.codec = codec
    v.width = width
    v.height = height
    v.size_mb = size_mb if size_mb is not None else bitrate * 100
    v.duration_sec = 3600
    v.thumb = ""
    return v


def image(path, width, height, size_mb):
    img = MagicMock()
    img.file_path = path
    img.width = width
    img.height = height
    img.size_mb = size_mb
    img.thumb = ""
    return img


# --- Der Fund ---

def test_the_high_bitrate_source_is_recommended_over_its_reencode(detector):
    """
    Der Fall, für den die Re-Encode-Erkennung überhaupt existiert: 80 Mbps
    Original gegen 26 Mbps Kopie. Beide erreichen 85,0 Punkte — vorher
    entschied die Eingabereihenfolge.
    """
    group = detector._create_video_group(
        [video("/media/kopie.mp4", 26, codec="hevc"),
         video("/media/original.mkv", 80, codec="h264")],
        match_type="reencode", confidence=0.75,
    )

    assert group.recommended_keep == "/media/original.mkv"


def test_the_order_of_the_input_does_not_decide(detector):
    """Dieselbe Gruppe andersherum eingereicht muss dasselbe ergeben."""
    files = [video("/media/kopie.mp4", 26, codec="hevc"),
             video("/media/original.mkv", 80, codec="h264")]

    a = detector._create_video_group(list(files), match_type="reencode")
    b = detector._create_video_group(list(reversed(files)), match_type="reencode")

    assert a.recommended_keep == b.recommended_keep == "/media/original.mkv"


def test_both_files_really_do_score_the_same(detector):
    """
    Der Beleg, dass der Gleichstand echt ist und nicht herbeigeredet — sonst
    wäre der Test oben aus dem falschen Grund grün.
    """
    quelle = detector._calculate_video_quality_score(
        video("/a", 80, codec="h264"), codec_bonus=False)
    kopie = detector._calculate_video_quality_score(
        video("/b", 26, codec="hevc"), codec_bonus=False)

    assert quelle == kopie == 85.0


def test_the_recommendation_is_stable_across_two_runs(detector):
    """
    Zwei Scans müssen dieselbe Datei vorschlagen. Springt die Empfehlung,
    verliert man das Vertrauen in sie — und klickt entweder blind oder gar
    nicht mehr.
    """
    files = [video("/media/b.mp4", 30), video("/media/a.mp4", 30)]

    first = detector._create_video_group(list(files))
    second = detector._create_video_group(list(files))

    assert first.recommended_keep == second.recommended_keep


def test_a_complete_tie_falls_back_to_the_path(detector):
    """Byte-gleiche Kopien: irgendetwas muss entscheiden, und es muss stabil sein."""
    group = detector._create_video_group(
        [video("/media/z.mp4", 20, size_mb=2000),
         video("/media/a.mp4", 20, size_mb=2000)]
    )

    assert group.recommended_keep == "/media/a.mp4"


# --- Was weiterhin gilt ---

def test_bitrate_can_outweigh_resolution(detector):
    """
    Festgehalten, wie es ist, nicht wie ich es erwartet hätte: Ein 720p mit
    30 Mbps (50 + 15 + 15 = 80) schlägt ein 4K mit 10 Mbps (20 + 30 + 15 = 65).
    Die Bitrate trägt bis zu 50 Punkte bei, die Auflösung nur bis 30.

    Mein erster Test behauptete das Gegenteil und wurde zu Recht rot. Ob die
    Gewichtung so gewollt ist, ist eine Produktfrage — ich habe an den
    Punktwerten nichts geändert, nur am Gleichstand. Der Hinweis steht im
    Übergabebericht.
    """
    group = detector._create_video_group([
        video("/media/720p_hoch.mp4", 30, width=1280, height=720),
        video("/media/4k_niedrig.mp4", 10, width=3840, height=2160),
    ])

    assert group.recommended_keep == "/media/720p_hoch.mp4"


def test_at_equal_bitrate_the_higher_resolution_wins(detector):
    """Die Gegenprobe: Bei gleicher Bitrate entscheidet die Auflösung."""
    group = detector._create_video_group([
        video("/media/720p.mp4", 20, width=1280, height=720),
        video("/media/4k.mp4", 20, width=3840, height=2160),
    ])

    assert group.recommended_keep == "/media/4k.mp4"


def test_the_codec_bonus_still_applies_outside_reencode_groups(detector):
    """
    Bei byte-gleichen Kopien ist der moderne Codec ein echtes Argument; nur
    innerhalb einer Re-Encode-Gruppe kennzeichnet er die Ableitung.
    """
    group = detector._create_video_group([
        video("/media/alt.mp4", 10, codec="h264"),
        video("/media/neu.mp4", 10, codec="hevc"),
    ], match_type="exact")

    assert group.recommended_keep == "/media/neu.mp4"


def test_inside_a_reencode_group_the_codec_bonus_is_dropped(detector):
    """
    Sonst empfiehlt der +20-Bonus für HEVC ausgerechnet die verlustbehaftete
    Kopie. Das war schon vorher richtig gelöst und muss es bleiben.
    """
    group = detector._create_video_group([
        video("/media/hevc_kopie.mp4", 10, codec="hevc"),
        video("/media/h264_quelle.mp4", 12, codec="h264"),
    ], match_type="reencode")

    assert group.recommended_keep == "/media/h264_quelle.mp4"


def test_the_savings_refer_to_the_recommended_file(detector):
    """
    Die angezeigte Ersparnis ist alles außer der behaltenen Datei. Ändert sich
    die Empfehlung, muss sich die Rechnung mitändern.
    """
    group = detector._create_video_group([
        video("/media/original.mkv", 80, size_mb=8000),
        video("/media/kopie.mp4", 26, size_mb=2600),
    ], match_type="reencode")

    assert group.recommended_keep == "/media/original.mkv"
    assert group.potential_savings_mb == 2600


# --- Bilder ---

def test_the_larger_image_wins_a_tie(detector):
    group = detector._create_image_group([
        image("/fotos/klein.jpg", 4032, 3024, 2.0),
        image("/fotos/gross.jpg", 4032, 3024, 5.0),
    ], match_type="exact")

    assert group.recommended_keep == "/fotos/gross.jpg"


def test_image_recommendations_are_stable(detector):
    files = [image("/fotos/z.jpg", 4032, 3024, 3.0),
             image("/fotos/a.jpg", 4032, 3024, 3.0)]

    a = detector._create_image_group(list(files), match_type="exact")
    b = detector._create_image_group(list(reversed(files)), match_type="exact")

    assert a.recommended_keep == b.recommended_keep == "/fotos/a.jpg"
