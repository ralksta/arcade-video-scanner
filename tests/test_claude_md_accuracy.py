"""
test_claude_md_accuracy.py
--------------------------
Was `CLAUDE.md` behauptet, muss stimmen.

Die Datei ist die Einstiegsbeschreibung des Projekts — für neue Mitarbeiter
ebenso wie für Werkzeuge, die daraus ihr Bild vom Code bilden. Eine falsche
Angabe dort wirkt länger und breiter als ein Fehler in einer einzelnen Funktion:
sie wird geglaubt, nicht geprüft.

In dieser Nacht enthielt sie zwei Unrichtigkeiten:

1. Sie beschrieb die Mehrbenutzer-Trennung über ein Bereinigen des HTML-Dumps
   von Nutzerfeldern. Der Dump enthält gar keine Einträge mehr; der zuständige
   Code war toter Text. Wer sich auf die Bereinigung verlassen hätte, hätte auf
   eine Zusage gebaut, die der Code nicht gibt.
2. Sie räumte fünf verschiedene Versionsnummern als gegeben ein, statt sie zu
   beheben.

Beides ist korrigiert. Diese Tests halten die überprüfbaren Aussagen fest —
nicht den Prosatext, sondern das, was sich gegen den Code halten lässt.
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CLAUDE_MD = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

# In der Doku genannte Dateien, die es absichtlich nur zur Laufzeit gibt.
GENERATED_AT_RUNTIME = {
    "src/views/credentials.json",   # von tv_client/prebuild.js erzeugt
    "video_cache.json",             # Altbestand, laut Doku „if present"
}


def _referenced_files():
    return set(re.findall(r"`([A-Za-z0-9_./-]+\.(?:py|js|json|md|css|sh|toml))`", CLAUDE_MD))


def test_every_referenced_file_exists():
    """
    Ein Verweis auf eine Datei, die es nicht gibt, schickt den Leser ins Leere.
    Geprüft wird der Basisname, weil die Doku Dateien oft im Kontext eines
    zuvor genannten Verzeichnisses nennt.
    """
    all_names = {p.name for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts}

    missing = []
    for ref in sorted(_referenced_files()):
        if ref in GENERATED_AT_RUNTIME:
            continue
        if (ROOT / ref).exists() or Path(ref).name in all_names:
            continue
        missing.append(ref)

    assert not missing, f"CLAUDE.md verweist auf nicht vorhandene Dateien: {missing}"


def test_runtime_generated_files_have_a_generator():
    """
    Gegenprobe zur Ausnahmeliste: Wer dort steht, braucht eine Stelle, die die
    Datei erzeugt — sonst ist die Ausnahme nur eine Ausrede.
    """
    prebuild = (ROOT / "tv_client" / "prebuild.js").read_text(encoding="utf-8")
    assert "credentials.json" in prebuild

    store = (ROOT / "arcade_scanner" / "database" / "sqlite_store.py").read_text(encoding="utf-8")
    assert "_migrate_from_json" in store
    assert "video_cache.json" in store


def test_the_route_module_list_is_complete():
    """
    Die Liste nannte fünf Module, es sind neun. Wer nach einer Route sucht,
    findet sie sonst nicht dort, wo die Doku sie vermuten lässt.
    """
    documented = set(
        re.search(r"routes/` \(([^)]+)\)", CLAUDE_MD).group(1).replace(" ", "").split(",")
    )
    actual = {
        p.stem for p in (ROOT / "arcade_scanner" / "server" / "routes").glob("*.py")
        if p.stem != "__init__"
    }
    assert documented == actual, (
        f"Doku nennt {sorted(documented)}, vorhanden sind {sorted(actual)}"
    )


@pytest.mark.parametrize("flag", [
    "--skip-setup", "--ssl", "--rebuild", "--rebuild-thumbs", "--cleanup",
])
def test_documented_cli_flags_exist(flag):
    """Die Kommandozeilen aus der Doku sind das, was jemand tatsächlich eintippt."""
    assert flag in CLAUDE_MD, f"{flag} ist gar nicht dokumentiert — Test veraltet?"
    main_py = (ROOT / "arcade_scanner" / "main.py").read_text(encoding="utf-8")
    assert flag in main_py, f"{flag} steht in CLAUDE.md, aber nicht in main.py"


@pytest.mark.parametrize("command", ["list", "add", "passwd"])
def test_documented_user_management_commands_exist(command):
    script = (ROOT / "scripts" / "manage_users.py").read_text(encoding="utf-8")
    assert f'"{command}"' in script or f"'{command}'" in script


def test_multi_user_isolation_claim_matches_the_code():
    """
    Die alte Fassung beschrieb ein Bereinigen des Dumps von Nutzerfeldern —
    der Dump enthält gar keine Einträge. Die neue Fassung muss das sagen.
    """
    isolation = [ln for ln in CLAUDE_MD.splitlines() if "Multi-user isolation" in ln]
    assert isolation, "Abschnitt zur Trennung fehlt"

    line = isolation[0]
    assert "no** media entries" in line or "no media entries" in line

    dashboard = (ROOT / "arcade_scanner" / "templates" / "dashboard_template.py").read_text(
        encoding="utf-8"
    )
    assert "window.ALL_VIDEOS = []" in dashboard, "Der Dump bettet wieder Einträge ein"


def test_the_stdlib_only_claim_is_backed_by_a_test():
    """
    „The server is Python stdlib only" ist eine Zusage mit Folgen. Sie hat
    seit dieser Nacht einen Wächter — die Aussage soll nicht wieder ungeprüft
    dastehen.
    """
    assert "stdlib only" in CLAUDE_MD
    assert (ROOT / "tests" / "test_runtime_dependencies.py").is_file()


def test_version_claim_points_at_the_single_source():
    from arcade_scanner import __version__

    assert "arcade_scanner/__version__" in CLAUDE_MD
    assert "don't trust any single one" not in CLAUDE_MD, (
        "Die alte Einräumung der Versions-Drift steht wieder da."
    )
    assert __version__ in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]


def test_commit_convention_is_actually_followed_on_this_branch():
    """
    „Commit style: conventional commits with scope". Gegenprobe an den Commits
    dieses Branches — eine Konvention, die niemand einhält, ist keine.
    """
    result = subprocess.run(
        ["git", "log", "--format=%s", "-40"],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    if result.returncode != 0:
        pytest.skip("git nicht verfügbar")

    subjects = [s for s in result.stdout.splitlines() if s.strip()]
    assert subjects, "Keine Commits gefunden"

    pattern = re.compile(r"^(feat|fix|docs|test|refactor|perf|style|chore|build|ci)(\([^)]+\))?!?: .+")
    offenders = [s for s in subjects if not pattern.match(s)]

    # Merge-Commits folgen der Konvention naturgemäß nicht.
    offenders = [s for s in offenders if not s.startswith("Merge ")]

    assert len(offenders) <= len(subjects) // 4, (
        f"{len(offenders)} von {len(subjects)} Commits ohne konventionelles Präfix:\n  "
        + "\n  ".join(offenders[:5])
    )
