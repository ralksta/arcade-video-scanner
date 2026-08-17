"""
test_filter_engine_edges.py
---------------------------
Drei Stellen im Filter, die ich mir angesehen und **nicht** geändert habe.

Der Wert dieser Datei liegt nicht in einer Korrektur, sondern darin, dass die
Messungen nicht verlorengehen: Jede der drei sah nach einem Fehler aus, und
jede war bei genauerem Hinsehen entweder harmlos oder eine Auslegungsfrage, die
dem Nutzer gehört. Ohne diese Tests müsste das jemand ein zweites Mal
herausfinden.

**1. Die Paarbildung im „Optimiert"-Modus überschreibt gleiche Stämme.**

    const key = dir + '|' + stem;
    map.set(key, v);

Liegen `film.mkv` und `film.mp4` im selben Ordner, verdrängt der zweite den
ersten. In dieser Installation gibt es genau zwei solche Paare. Folgenlos ist
es, weil aus zwei Dateien ohne `_opt`-Suffix ohnehin kein Paar entsteht — die
Map dient nur der Paarsuche.

**2. `optimized_files` sucht `_opt` im ganzen Pfad.**

Also auch in Ordnernamen. An der echten Bibliothek nachgezählt: 94 Treffer,
alle im Dateinamen — kein einziger über einen Ordner. 92 davon tragen das
Suffix am Ende, zwei nicht (`…_MP4_opt Upscaled.mp4`, `…_opt_test.mp4`). Ob
die mitgezählt werden sollen, ist eine Frage an den Nutzer und keine an den
Code; in einem reinen Anzeigefilter ist zwei zu viel harmlos.

**3. `vaulted` und `favorite` stehen noch in der Medientabelle.**

Mit dem Alias `hidden` bzw. `favorite` — also unter genau den Namen, die das
Frontend pro Nutzer überschreibt. Das sah nach einem Leck zwischen Konten aus.
Ist es nicht: Alle 8788 Zeilen tragen dort 0, geschrieben wird nur beim
Durchreichen des Modells. Der Test unten hält das fest, damit es auffällt,
wenn wieder jemand anfängt, dorthin zu schreiben — dann wäre es eins.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
FILTER_JS = (ROOT / "arcade_scanner" / "server" / "static" / "filter_engine.js").read_text(
    encoding="utf-8")

HARNESS = Path(__file__).parent / "vault_guard_harness.js"
node = shutil.which("node")


def run_filter(videos, workspace_mode="lobby"):
    fixture = Path(__file__).parent / "_filter_edge_fixtures.json"
    fixture.write_text(json.dumps({
        "videos": videos, "userDataLoaded": True, "workspaceMode": workspace_mode,
    }), encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    finally:
        fixture.unlink(missing_ok=True)


def video(path, **extra):
    entry = {
        "FilePath": path, "Status": "OK", "Size_MB": 100.0, "codec": "h264",
        "_fileNameLower": path.rsplit("/", 1)[-1].lower(), "_codecLower": "h264",
        "_folder": path.rsplit("/", 1)[0], "tags": [], "favorite": False,
        "hidden": False, "mtime": 1700000000,
    }
    entry.update(extra)
    return entry


# --- 1. Gleiche Stämme im selben Ordner ---

@pytest.mark.skipif(node is None, reason="node not on PATH")
def test_two_files_with_the_same_stem_produce_no_pair():
    """
    Die Map verliert eine der beiden — folgenlos, weil ohne `_opt`-Suffix
    ohnehin kein Paar entsteht. Genau dieser Fall kommt in der Bibliothek
    zweimal vor.
    """
    result = run_filter(
        [video("/media/film.mkv"), video("/media/film.mp4")],
        workspace_mode="optimized",
    )

    assert result["shownCount"] == 0


@pytest.mark.skipif(node is None, reason="node not on PATH")
def test_a_real_optimized_pair_is_found():
    """Die Gegenprobe: So sieht ein Paar aus, das gefunden werden soll."""
    result = run_filter(
        [video("/media/film.mkv"), video("/media/film_opt.mp4", Size_MB=40.0)],
        workspace_mode="optimized",
    )

    assert result["shownCount"] == 1


@pytest.mark.skipif(node is None, reason="node not on PATH")
def test_a_review_pair_is_found():
    """Der Weg, den der Prüfmodus erzeugt: beide Dateien im selben Job-Ordner."""
    result = run_filter([
        video("/media/.review/job_5_film/film_original.mkv"),
        video("/media/.review/job_5_film/film_optimized.mp4", Size_MB=40.0),
    ], workspace_mode="optimized")

    assert result["shownCount"] == 1


@pytest.mark.skipif(node is None, reason="node not on PATH")
def test_pairs_are_not_formed_across_directories():
    """Sonst würde `a/film.mkv` mit `b/film_opt.mp4` gepaart."""
    result = run_filter([
        video("/media/a/film.mkv"),
        video("/media/b/film_opt.mp4", Size_MB=40.0),
    ], workspace_mode="optimized")

    assert result["shownCount"] == 0


# --- 2. Die _opt-Erkennung ---

def test_the_optimized_filter_looks_at_the_whole_path():
    """
    Festgehalten, wie es ist. An der echten Bibliothek nachgezählt: 94
    Treffer, alle im Dateinamen, kein einziger über einen Ordnernamen. Zwei
    davon tragen `_opt` ohne Suffix-Bedeutung.

    Das enger zu fassen hiesse zu entscheiden, was „optimiert" bedeutet — das
    steht dem Nutzer zu, nicht mir. In einem Anzeigefilter ist zwei zu viel
    ausserdem folgenlos.
    """
    assert "v.FilePath.includes('_opt')" in FILTER_JS
    assert "v.FilePath.includes('_trim')" in FILTER_JS


# --- 3. Die globalen Spalten ---

def test_the_shared_columns_are_never_written_from_user_actions():
    """
    `vaulted`/`favorite` in der Medientabelle tragen die Aliasse `hidden` und
    `favorite` — dieselben Namen, die das Frontend pro Nutzer überschreibt. Das
    sah nach einem Leck zwischen Konten aus; alle 8788 Zeilen tragen dort
    jedoch 0, und geschrieben wird nur beim Durchreichen des Modells.

    Schlägt dieser Test an, hat jemand angefangen, Nutzeraktionen dorthin zu
    schreiben — und dann sähe der eine Nutzer, was der andere weggelegt hat.
    """
    routes = ROOT / "arcade_scanner" / "server" / "routes"
    offenders = {}

    for py in sorted(routes.glob("*.py")):
        source = py.read_text(encoding="utf-8")
        code = "\n".join(
            ln for ln in source.splitlines() if not ln.lstrip().startswith("#")
        )
        for needle in ("entry.vaulted =", "entry.favorite =",
                       ".vaulted = True", ".vaulted = False"):
            if needle in code:
                offenders.setdefault(py.name, []).append(needle)

    assert offenders == {}, (
        f"Nutzeraktionen schreiben in die gemeinsamen Spalten: {offenders}"
    )


def test_the_per_user_state_is_the_authoritative_one():
    """
    Der Beleg für die Richtung: Das Frontend überschreibt `hidden` und
    `favorite` nach dem Laden aus `/api/user/data`.
    """
    engine = (ROOT / "arcade_scanner" / "server" / "static" / "engine.js").read_text(
        encoding="utf-8")
    block = engine.split("async function loadUserData()", 1)[1].split("\n    }", 1)[0]

    assert "v.hidden = vaultSet.has(v.FilePath)" in block
    assert "v.favorite = favSet.has(v.FilePath)" in block
