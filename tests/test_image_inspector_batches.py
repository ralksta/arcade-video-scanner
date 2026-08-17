"""
test_image_inspector_batches.py
-------------------------------
Der Bild-Inspektor fasst bis zu 100 Dateien in **einen** `sips`-Aufruf. Das ist
gut für die Geschwindigkeit — und macht zwei Fehler teuer, die einzeln
harmlos wären.

**1. Eine unlesbare Datei verwarf den ganzen Stapel.**

    if proc.returncode != 0:
        # Some files may have failed — resolve with None
        for filepath in files:
            ... future.set_result(None)
        return

`sips` liefert einen Rückgabewert ungleich null, sobald **eine** Datei nicht
lesbar ist — schreibt die Eigenschaften der übrigen aber trotzdem nach stdout.
Verworfen wurden bisher alle. Die betroffenen Bilder gelangten damit nicht in
die Bibliothek, und beim nächsten Scan wieder nicht: Derselbe Stapel enthält
dieselbe kaputte Datei. Ein einziges defektes Bild konnte so bis zu 99 andere
dauerhaft fernhalten.

**2. Kein Zeitlimit.**

`await proc.communicate()` ohne Frist. Der Video-Probe hat für genau dieses
Problem längst eine Lösung, samt Begründung im Kommentar („A timeout only
cancels communicate() — ffprobe itself keeps running. Reap it, or a library
with a few unreadable files leaves one stray process behind per probe.").
Hier wiegt es schwerer: An einem Aufruf hängen bis zu 100 wartende Futures.

`sips` gibt es nur auf macOS; auf dieser Installation läuft der Pillow-Pfad,
und Bilder sind ohnehin abgeschaltet. Der Mac-Worker ist aber Teil dieses
Projekts, und die Lehre stand zwei Dateien weiter längst geschrieben.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arcade_scanner.scanner.image_inspector import ImageInspector

SIPS_OUTPUT = """/bilder/gut1.jpg
  pixelWidth: 1920
  pixelHeight: 1080
  format: jpeg
/bilder/gut2.png
  pixelWidth: 800
  pixelHeight: 600
  format: png
"""


def fake_proc(stdout: bytes, returncode: int = 0, hang: bool = False):
    proc = MagicMock()
    proc.returncode = returncode
    if hang:
        async def never(*_a, **_k):
            await asyncio.sleep(3600)
        proc.communicate = never
        proc.returncode = None
        proc.kill = MagicMock()
        proc.wait = AsyncMock()
    else:
        proc.communicate = AsyncMock(return_value=(stdout, b""))
    return proc


async def inspect_batch(paths, proc):
    inspector = ImageInspector()
    inspector.has_sips = True
    inspector.SIPS_TIMEOUT_SEC = 0.05

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)), \
         patch.object(inspector, "_build_asset_from_props",
                      AsyncMock(side_effect=lambda p, props: f"asset:{p}")):
        results = await asyncio.gather(*(inspector.inspect(p) for p in paths))
    return results


# --- 1. Der Stapel ---

def test_a_single_unreadable_file_does_not_discard_the_others():
    """
    Der Fund: `sips` meldet einen Fehlerkode, sobald eine Datei nicht lesbar
    ist — die Eigenschaften der übrigen stehen trotzdem in der Ausgabe.
    Vorher wurden alle verworfen.
    """
    paths = ["/bilder/gut1.jpg", "/bilder/gut2.png", "/bilder/kaputt.jpg"]

    results = asyncio.run(inspect_batch(
        paths, fake_proc(SIPS_OUTPUT.encode(), returncode=1)))

    assert results[0] == "asset:/bilder/gut1.jpg"
    assert results[1] == "asset:/bilder/gut2.png"
    assert results[2] is None, "Die kaputte Datei muss weiterhin None ergeben"


def test_a_clean_batch_still_works():
    results = asyncio.run(inspect_batch(
        ["/bilder/gut1.jpg", "/bilder/gut2.png"],
        fake_proc(SIPS_OUTPUT.encode(), returncode=0)))

    assert results == ["asset:/bilder/gut1.jpg", "asset:/bilder/gut2.png"]


def test_an_empty_output_resolves_everything_to_none():
    """Liefert sips gar nichts, gibt es auch nichts zu retten."""
    results = asyncio.run(inspect_batch(
        ["/bilder/a.jpg", "/bilder/b.jpg"], fake_proc(b"", returncode=1)))

    assert results == [None, None]


def test_undecodable_output_does_not_raise():
    """
    Dateinamen können Bytes enthalten, die kein UTF-8 sind. `decode()` ohne
    Fehlerbehandlung hätte hier den ganzen Stapel mit einer Ausnahme
    beendet — und die landet im äusseren `except`, das ebenfalls alles
    verwirft.
    """
    results = asyncio.run(inspect_batch(
        ["/bilder/a.jpg"], fake_proc(b"\xff\xfe kaputt", returncode=0)))

    assert results == [None]


# --- 2. Das Zeitlimit ---

def test_a_hanging_call_does_not_block_forever():
    """
    Ohne Frist steht mit dem Aufruf der gesamte Bilddurchlauf: An ihm hängen
    bis zu 100 wartende Futures.
    """
    proc = fake_proc(b"", hang=True)

    results = asyncio.run(inspect_batch(["/bilder/a.jpg"], proc))

    assert results == [None]


def test_a_timed_out_process_is_reaped():
    """
    Das Zeitlimit bricht nur `communicate()` ab — sips läuft weiter. Ohne
    Einsammeln bleibt pro Stapel ein Prozess zurück. Genau diese Begründung
    steht im Video-Probe.
    """
    proc = fake_proc(b"", hang=True)

    asyncio.run(inspect_batch(["/bilder/a.jpg"], proc))

    proc.kill.assert_called_once()


def test_the_timeout_matches_the_shape_used_for_video():
    """
    Beide Stellen beantworten dieselbe Frage. Fehlt sie an einer, hängt dort
    irgendwann ein Scan.
    """
    import inspect as _inspect

    from arcade_scanner.scanner import media_probe

    video = _inspect.getsource(media_probe.MediaProbe._run_ffprobe)
    images = _inspect.getsource(ImageInspector._flush_batch)

    for source, name in ((video, "media_probe"), (images, "image_inspector")):
        assert "wait_for" in source, f"{name}: kein Zeitlimit"
        assert "kill()" in source, f"{name}: der Prozess wird nicht eingesammelt"


# --- Die Ausgabe-Auswertung ---

def test_properties_are_matched_to_their_file():
    inspector = ImageInspector()
    parsed = inspector._parse_batch_sips_output(SIPS_OUTPUT)

    assert parsed["/bilder/gut1.jpg"]["pixelWidth"] == "1920"
    assert parsed["/bilder/gut2.png"]["format"] == "png"


def test_a_file_without_properties_is_absent_from_the_result():
    output = SIPS_OUTPUT + "/bilder/kaputt.jpg\n"
    parsed = ImageInspector()._parse_batch_sips_output(output)

    assert "/bilder/kaputt.jpg" not in parsed


@pytest.mark.parametrize("path", [
    "/bilder/mit leerzeichen.jpg",
    "/bilder/mit:doppelpunkt.jpg",
])
def test_awkward_filenames_are_still_matched(path):
    """
    Der Doppelpunkt ist der heikle Fall: Die Eigenschaftszeilen werden an
    `": "` getrennt, und ein Dateiname kann denselben Trenner enthalten. Er
    steht aber ohne Einrückung, und genau daran werden die Zeilen
    unterschieden.
    """
    output = f"{path}\n  pixelWidth: 100\n  pixelHeight: 50\n  format: jpeg\n"
    parsed = ImageInspector()._parse_batch_sips_output(output)

    assert parsed[path]["pixelWidth"] == "100"
