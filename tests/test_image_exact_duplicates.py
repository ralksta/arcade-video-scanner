"""
test_image_exact_duplicates.py
------------------------------
Der Rückfallweg der Bild-Duplikatsuche — und warum „exact" dort keins war.

`_find_image_duplicates_by_exact()` läuft, wenn `imagehash` nicht verfügbar
ist. Es bildete eine Signatur aus gerundeter Dateigröße und Auflösung::

    signature = f"i:{size_mb}:{width}x{height}"      # size_mb = round(…, 2)

und erklärte alles im selben Fach zu Duplikaten — `match_type="exact"`,
Konfidenz 0,95, direkt in eine Oberfläche, die das Löschen anbietet.

`round(size_mb, 2)` fasst aber alles zusammen, was innerhalb von rund **10 KB**
gleich groß ist. Zwei verschiedene Aufnahmen derselben Kamera, gleiche
Auflösung, ähnliche Dateigröße — das ist kein Grenzfall, das ist der Normalfall
einer Fotosammlung. Der Nutzer bekam zwei völlig verschiedene Bilder als
„exaktes Duplikat" vorgelegt, mit einem Knopf zum Löschen daneben.

Der **Video**-Zweig macht es seit jeher richtig: Die Signatur filtert nur vor,
danach werden die Bytes verglichen — der Kommentar dort sagt es wörtlich,
„Verify with content sampling to avoid false positives". Genau dieser Schritt
fehlte bei den Bildern, obwohl `_verify_by_content_sample()` medienneutral ist.
Bei Bildern unter 1 MB liest sie die Datei sogar ganz; der Vergleich ist dann
nicht „ähnlich groß", sondern byteweise gleich.

Dass der Zweig selten läuft, macht es nicht harmloser — er springt genau dann
ein, wenn ohnehin schon etwas nicht stimmt.
"""
from unittest.mock import MagicMock

import pytest

from arcade_scanner.core.duplicate_detector import DuplicateDetector


@pytest.fixture
def detector():
    return DuplicateDetector()


def make_image(path, size_mb, width=4032, height=3024):
    img = MagicMock()
    img.file_path = str(path)
    img.size_mb = size_mb
    img.width = width
    img.height = height
    img.codec = ""
    img.thumb = ""
    return img


def write(path, content: bytes):
    path.write_bytes(content)
    return path


# --- Der Fund ---

def test_two_different_photos_of_the_same_size_are_not_duplicates(detector, tmp_path):
    """
    Der Fall, der vorher als „exaktes Duplikat" mit Löschknopf erschien: zwei
    verschiedene Aufnahmen, gleiche Auflösung, Dateigrößen im selben
    10-KB-Fach.
    """
    a = write(tmp_path / "IMG_4711.jpg", b"A" * 500_000)
    b = write(tmp_path / "IMG_4712.jpg", b"B" * 500_000)

    groups = detector._find_image_duplicates_by_exact([
        make_image(a, 0.48), make_image(b, 0.48),
    ])

    assert groups == [], "Zwei verschiedene Bilder wurden als Duplikat gemeldet"


def test_sizes_that_only_round_to_the_same_value_are_not_duplicates(detector, tmp_path):
    """
    Präziser: Die Dateien sind nicht einmal gleich groß — nur nach dem Runden.
    """
    a = write(tmp_path / "a.jpg", b"A" * 500_000)
    b = write(tmp_path / "b.jpg", b"B" * 504_000)

    groups = detector._find_image_duplicates_by_exact([
        make_image(a, 0.4768), make_image(b, 0.4806),
    ])

    assert groups == []


def test_genuine_copies_are_still_found(detector, tmp_path):
    """Die Gegenprobe — sonst hätte ich die Funktion nur abgeschaltet."""
    content = b"dasselbe bild" * 40_000
    a = write(tmp_path / "urlaub.jpg", content)
    b = write(tmp_path / "urlaub_kopie.jpg", content)

    groups = detector._find_image_duplicates_by_exact([
        make_image(a, 0.5), make_image(b, 0.5),
    ])

    assert len(groups) == 1
    assert {f.path for f in groups[0].files} == {str(a), str(b)}
    assert groups[0].match_type == "exact"


def test_a_mixed_bucket_yields_only_the_real_pair(detector, tmp_path):
    """
    Drei Dateien in einem Signatur-Fach, davon zwei echte Kopien. Vorher wären
    alle drei eine Gruppe gewesen — und der Nutzer hätte beim Aufräumen die
    dritte mit gelöscht.
    """
    content = b"gleich" * 80_000
    a = write(tmp_path / "a.jpg", content)
    b = write(tmp_path / "b.jpg", content)
    c = write(tmp_path / "c.jpg", b"anders" * 80_000)

    groups = detector._find_image_duplicates_by_exact([
        make_image(a, 0.46), make_image(b, 0.46), make_image(c, 0.46),
    ])

    assert len(groups) == 1
    assert {f.path for f in groups[0].files} == {str(a), str(b)}


# --- Verhalten, das bleiben muss ---

def test_different_resolutions_never_group(detector, tmp_path):
    a = write(tmp_path / "a.jpg", b"X" * 100_000)
    b = write(tmp_path / "b.jpg", b"X" * 100_000)

    groups = detector._find_image_duplicates_by_exact([
        make_image(a, 0.1, width=4032, height=3024),
        make_image(b, 0.1, width=1920, height=1080),
    ])

    assert groups == []


def test_images_without_a_size_are_skipped(detector, tmp_path):
    a = write(tmp_path / "a.jpg", b"X" * 100)

    groups = detector._find_image_duplicates_by_exact([
        make_image(a, 0), make_image(a, 0),
    ])

    assert groups == []


def test_a_single_image_forms_no_group(detector, tmp_path):
    a = write(tmp_path / "a.jpg", b"X" * 100_000)

    assert detector._find_image_duplicates_by_exact([make_image(a, 0.1)]) == []


def test_an_unreadable_file_is_left_out_rather_than_guessed(detector, tmp_path):
    """
    `_get_content_sample_hash()` gibt bei einem Fehler "" zurück, und solche
    Dateien werden nicht gruppiert. Lieber ein Duplikat übersehen als eines
    erfinden — die Aktion dahinter ist Löschen.
    """
    a = write(tmp_path / "a.jpg", b"X" * 100_000)
    fehlt = tmp_path / "gibtsnicht.jpg"

    groups = detector._find_image_duplicates_by_exact([
        make_image(a, 0.1), make_image(fehlt, 0.1),
    ])

    assert groups == []


# --- Die Parallele zum Video-Zweig ---

def test_both_media_types_verify_content_before_grouping():
    """
    Der Video-Zweig prüfte längst, der Bild-Zweig nicht. Dieser Test hält fest,
    dass beide es tun — die nächste Ergänzung soll nicht wieder bei einem
    davon anfangen.
    """
    import inspect

    for method in (
        DuplicateDetector._find_image_duplicates_by_exact,
        DuplicateDetector._find_video_duplicates,
    ):
        source = inspect.getsource(method)
        assert "_verify_by_content_sample" in source, (
            f"{method.__name__} gruppiert ohne Inhaltsprüfung"
        )


def test_the_verification_is_media_agnostic(detector, tmp_path):
    """
    Belegt, warum dieselbe Funktion für Bilder taugt: Sie kennt kein Format,
    sie liest Bytes. Bei kleinen Dateien den ganzen Inhalt.
    """
    a = write(tmp_path / "a.bin", b"identisch" * 100)
    b = write(tmp_path / "b.bin", b"identisch" * 100)
    c = write(tmp_path / "c.bin", b"verschied" * 100)

    files = [MagicMock(file_path=str(p)) for p in (a, b, c)]
    groups = detector._verify_by_content_sample(files)

    assert len(groups) == 1
    assert len(groups[0]) == 2
