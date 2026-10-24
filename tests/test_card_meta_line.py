"""
test_card_meta_line.py
----------------------
Größe und Bitrate sollen auf der Kachel sichtbar sein, ohne dass man erst
„Details“ einschaltet. Die ausführliche Werkstatt-Zeile (Pfad, Codec,
Bitrate-Balken) soll dafür nicht dauerhaft mitlaufen.

Die Kachel setzt `createVideoCard()` in engine.js zusammen; die Werte kommen
aus `cardMetaLine()` in formatters.js. Geprüft wird die Funktion ausgeführt
(node-Harness, wie bei den übrigen JS-Modulen) und statisch, dass die Kachel
sie benutzt und die CSS-Regel sie in Details/Werkstatt ausblendet.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HARNESS = Path(__file__).parent / "card_meta_harness.js"
ENGINE = (ROOT / "arcade_scanner" / "server" / "static" / "engine.js").read_text(
    encoding="utf-8")
STYLES = (ROOT / "arcade_scanner" / "server" / "static" / "styles.css").read_text(
    encoding="utf-8")

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def meta(videos):
    fixture = Path(__file__).parent / "_card_meta_fixtures.json"
    fixture.write_text(json.dumps(videos), encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    finally:
        fixture.unlink(missing_ok=True)


def test_a_video_shows_size_and_bitrate():
    assert meta([{"Size_MB": 1433.6, "Bitrate_Mbps": 8.24,
                  "media_type": "video"}]) == ["1.4 GB · 8.2 Mbps"]


def test_an_image_shows_only_the_size():
    assert meta([{"Size_MB": 500.0, "Bitrate_Mbps": 5.0,
                  "media_type": "image"}]) == ["500.0 MB"]


def test_missing_values_do_not_crash():
    assert meta([{}]) == ["0.0 MB · 0.0 Mbps"]


def test_the_card_uses_the_helper_without_the_details_class():
    body = ENGINE.split("function createVideoCard", 1)[1].split("\nfunction ", 1)[0]

    assert "cardMetaLine(v)" in body
    assert 'class="card-meta-line ' in body
    assert "card-meta-line tech-only" not in body


def test_details_and_workshop_views_hide_the_compact_line():
    assert "body.show-tech .card-meta-line" in STYLES
    for workspace in ("optimized", "duplicates", "candidates"):
        assert f'body[data-workspace="{workspace}"] .card-meta-line' in STYLES
