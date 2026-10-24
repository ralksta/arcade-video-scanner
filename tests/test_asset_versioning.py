"""
test_asset_versioning.py
------------------------
Cache-Buster der statischen Assets.

Vorher stand in jedem der 28 Script-/Link-Tags ``?v={int(time.time())}`` — für
alle Dateien derselbe Wert, neu bei jeder Neugenerierung des HTML-Reports. Der
Report wird nach jedem Scan, jeder Einstellungsänderung und jedem Encode-Upload
neu geschrieben; damit bekamen sämtliche Assets regelmäßig frische URLs.

Eine neue URL ist im Browser-Cache kein 304, sondern ein voller Fehltreffer:
588 KB (122 KB gzip) wurden erneut übertragen, obwohl sich an den Dateien
nichts geändert hatte. Der ``no-cache``-Header des Servers, der sonst für
billige 304er sorgt, lief dabei komplett ins Leere.

Mit der mtime der jeweiligen Datei ändert sich eine URL nur noch, wenn sich
genau diese Datei ändert.
"""
import os
import re
import time
from pathlib import Path

import pytest

from arcade_scanner.config import config
from arcade_scanner.templates import dashboard_template
from arcade_scanner.templates.dashboard_template import (
    SCRIPT_MODULES,
    STYLESHEETS,
    asset_url,
)

STATIC_DIR = Path(config.static_dir)


def test_version_is_the_file_mtime():
    url = asset_url("engine.js")
    expected = int(os.path.getmtime(STATIC_DIR / "engine.js"))
    assert url == f"/static/engine.js?v={expected}"


def test_repeated_calls_are_stable():
    """
    Der eigentliche Fehler: derselbe Aufruf lieferte kurz darauf eine andere
    URL, weil die Zeit weitergelaufen war.
    """
    first = asset_url("engine.js")
    time.sleep(0.01)
    assert asset_url("engine.js") == first


def test_versions_are_not_all_identical():
    """
    Mit ``time.time()`` trugen alle Assets denselben Wert. Unterschiedliche
    Dateien haben unterschiedliche mtimes — trüge weiterhin alles denselben
    Wert, wäre die Umstellung wirkungslos.
    """
    versions = {asset_url(name).split("?v=")[1] for name in SCRIPT_MODULES}
    assert len(versions) > 1, "Alle Assets tragen dieselbe Version — Zeitstempel statt mtime?"


class _StubConfig:
    """config.static_dir ist ein read-only Property — für die beiden Tests
    unten reicht ein Stub mit genau diesem Attribut."""

    def __init__(self, static_dir):
        self.static_dir = str(static_dir)


def test_changing_one_file_changes_only_its_url(tmp_path, monkeypatch):
    """Ein Edit an einer Datei darf die URLs der anderen nicht anfassen."""
    monkeypatch.setattr(dashboard_template, "config", _StubConfig(tmp_path))
    (tmp_path / "a.js").write_text("// a")
    (tmp_path / "b.js").write_text("// b")

    before = {name: asset_url(name) for name in ("a.js", "b.js")}

    os.utime(tmp_path / "a.js", (1_700_000_000, 1_700_000_000))

    assert asset_url("a.js") != before["a.js"]
    assert asset_url("b.js") == before["b.js"]


def test_missing_file_does_not_raise(tmp_path, monkeypatch):
    """
    Eine fehlende Datei ist ein Deployment-Fehler — aber kein Grund, das
    Rendern der ganzen Seite abstürzen zu lassen.
    """
    monkeypatch.setattr(dashboard_template, "config", _StubConfig(tmp_path))
    assert asset_url("gibtsnicht.js") == "/static/gibtsnicht.js?v=0"


@pytest.mark.parametrize("name", SCRIPT_MODULES + STYLESHEETS)
def test_every_listed_asset_exists_on_disk(name):
    """Ein Tippfehler in der Liste wäre sonst erst im Browser als 404 sichtbar."""
    assert (STATIC_DIR / name).is_file(), f"{name} steht in der Liste, fehlt aber auf der Platte"


def test_template_no_longer_uses_a_wall_clock_cache_buster():
    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "templates" / "dashboard_template.py"
    ).read_text(encoding="utf-8")

    # Nur Code-Zeilen prüfen: das Muster kommt bewusst in Docstrings vor, die
    # erklären, warum es früher falsch war.
    offenders = [
        line.strip()
        for line in source.splitlines()
        if "/static/" in line and "time.time()" in line
    ]
    assert not offenders, (
        "Zeitstempel als Cache-Buster entwertet bei jeder Report-Neugenerierung "
        "den kompletten Browser-Cache:\n  " + "\n  ".join(offenders)
    )


def test_generated_html_versions_every_asset(tmp_path):
    """Gegenprobe am gerenderten HTML, nicht nur an der Hilfsfunktion."""
    from arcade_scanner.templates.dashboard_template import generate_html_report

    out = tmp_path / "asset_version_report.html"
    generate_html_report(str(out), server_port=8000)
    html = out.read_text(encoding="utf-8")

    unversioned = [
        match for match in re.findall(r'/static/([a-z_0-9]+\.(?:js|css))(?:\?v=(\d+))?', html)
        if not match[1]
    ]
    assert not unversioned, f"Assets ohne Version im HTML: {sorted({m[0] for m in unversioned})}"
