"""
test_backup_route_wiring.py
---------------------------
Der Bereich „Backup & Restore" in den Einstellungen — beide Knöpfe zeigten ins
Leere.

    exportSettings()   →  GET  /api/user/export
    importSettings()   →  POST /api/user/import

Keine der beiden Routen existiert im Server. Die einzige `/api/user/*`-Route
ist `/api/user/data`. Beide wurden in einem einzigen Frontend-Commit
eingeführt (`cbe019b`), die Gegenstücke wurden nie geschrieben — es ist also
kein Rückschritt, sondern etwas, das nie fertig wurde.

Was dabei auffiel: `/api/backup` **gibt es**, funktioniert, und hatte bis
hierher keinen einzigen Aufrufer. Die Beschriftung im Einstellungsdialog nennt
sogar den Dateinamen, den genau diese Route setzt::

    components.py:  "Saves as arcade_settings_backup.json"
    files.py:       'attachment; filename="arcade_settings_backup.json"'

Der Export war also eine falsch verdrahtete Leitung, kein fehlendes Stück. Der
**Import** ist ein fehlendes Stück: Eine Route, die eine hochgeladene Datei
über die bestehenden Einstellungen schreibt, ist eine löschende Operation, und
ihre Bedeutung (welche Konten? ersetzen oder mischen?) ist eine Entscheidung.
Nicht erfunden — steht im Übergabebericht.

Der zweite Teil dieser Datei hält fest, **was die Sicherung enthält**, denn das
ist die eigentliche Überraschung: nur `settings.json`. Favoriten, Tags,
Vault-Marken, Konten, Scan-Ziele und Ausschlüsse liegen seit der
Mehrbenutzer-Umstellung in `users.db` und sind nicht dabei — obwohl
`settings.json` die passenden Schlüssel noch als **leere Hüllen** führt.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "arcade_scanner" / "server" / "static"
ROUTES = ROOT / "arcade_scanner" / "server" / "routes"

SETTINGS_JS = (STATIC / "settings.js").read_text(encoding="utf-8")
FILES_PY = (ROUTES / "files.py").read_text(encoding="utf-8")


def code_only(source: str) -> str:
    """JS-Kommentare raus, bevor nach Routen gesucht wird.

    Ohne das prüft der Test die Erklärung statt des Codes: Der Kommentar über
    `exportSettings()` nennt die kaputte Route beim Namen und stünde damit vor
    der richtigen. Derselbe Fehler ist mir in dieser Nacht dreimal passiert —
    ein Hinweis darauf, dass Muster-Tests grundsätzlich auf entkommentiertem
    Text arbeiten sollten.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(
        re.sub(r"(^|\s)//.*$", "", line) for line in source.splitlines()
    )


def server_routes() -> set:
    """Alle Pfad-Zeichenketten, die der Server irgendwo vergleicht.

    `._*` wird übersprungen: macOS legt neben kopierten Dateien
    AppleDouble-Reste an, die kein UTF-8 sind. Sie stehen in `.gitignore` und
    sind nicht eingecheckt — der Scanner überspringt dieselbe Namensform
    (`_is_video`), diese Sammlung tut es jetzt auch.
    """
    routes = set()
    for py in (ROOT / "arcade_scanner" / "server").rglob("*.py"):
        if py.name.startswith("._") or "__pycache__" in py.parts:
            continue
        routes.update(re.findall(r'"(/api/[a-z0-9_/]+)"', py.read_text(encoding="utf-8")))
    return routes


# Bekannte, bewusst offene Lücke. Nach dem Muster von `DYNAMIC_IDS` in
# test_dom_contract.py: eine Ausnahme, die man aufschreiben muss, statt einer
# Prüfung, die man abschaltet.
#
# `/api/user/import` würde eine hochgeladene Datei über die bestehenden
# Einstellungen schreiben. Das ist löschend, und die Bedeutung ist eine
# Entscheidung: Welche Konten sind betroffen? Ersetzen oder mischen? Und was
# passiert mit den leeren Hüllen in settings.json (siehe unten), die dabei
# echte Werte überschreiben würden? Deshalb nicht erfunden.
KNOWN_MISSING_ROUTES = {
    "/api/user/import": "Wiederherstellung nicht implementiert — Entscheidung für Ralf",
}


# --- Der Fund ---

def test_the_export_button_points_at_a_route_that_exists():
    match = re.search(
        r"function exportSettings\(\)\s*\{(.*?)\n\}", code_only(SETTINGS_JS), re.S
    )
    assert match, "exportSettings() nicht gefunden"

    target = re.search(r"'(/api/[^']+)'", match.group(1))
    assert target, "exportSettings() ruft keine API-Route auf"
    assert target.group(1) in server_routes(), (
        f"exportSettings() zeigt auf {target.group(1)} — diese Route gibt es nicht"
    )


def test_the_backup_route_is_actually_called_from_somewhere():
    """
    Sie existierte und funktionierte, nur rief sie niemand auf. Ein Endpunkt
    ohne Aufrufer sieht aus wie Absicht und ist meistens eine lose Leitung.
    """
    callers = [
        p.name for p in STATIC.glob("*.js")
        if "/api/backup" in p.read_text(encoding="utf-8")
    ]
    assert callers, "/api/backup hat wieder keinen Aufrufer im Frontend"


def test_the_filename_promised_in_the_ui_matches_what_the_route_sends():
    """
    Der Beleg, dass der Knopf für genau diese Route gedacht war — die
    Beschriftung nennt den Dateinamen, den die Route setzt.
    """
    components = (
        ROOT / "arcade_scanner" / "templates" / "components.py"
    ).read_text(encoding="utf-8")

    assert "arcade_settings_backup.json" in components
    assert 'filename="arcade_settings_backup.json"' in FILES_PY


def test_no_frontend_call_targets_a_missing_api_route():
    """
    Der Rundumschlag: Jede `/api/...`-Zeichenkette in den Skripten muss einer
    Route entsprechen, die der Server kennt. So etwas wie
    `/api/user/import` soll nicht wieder unbemerkt liegen bleiben.
    """
    known = server_routes()
    missing = {}

    for js in sorted(STATIC.glob("*.js")):
        if js.name == "aframe.min.js":
            continue
        source = code_only(js.read_text(encoding="utf-8"))
        for call in set(re.findall(r"['\"`](/api/[a-z0-9_/]+)['\"`]", source)):
            # Routen mit Parametern werden serverseitig per startswith
            # verglichen; ein Präfixtreffer genügt hier.
            if call in known or any(k.startswith(call) or call.startswith(k) for k in known):
                continue
            if call in KNOWN_MISSING_ROUTES:
                continue
            missing.setdefault(js.name, []).append(call)

    assert missing == {}, f"Frontend ruft Routen auf, die es nicht gibt: {missing}"


def test_the_known_gap_is_still_a_gap():
    """
    Die Ausnahmeliste darf nicht zum Friedhof werden: Sobald die Route
    existiert, wird dieser Test rot und der Eintrag gehört raus.
    """
    known = server_routes()
    stale = [r for r in KNOWN_MISSING_ROUTES if r in known]

    assert stale == [], (
        f"Diese Routen gibt es inzwischen — Eintrag aus KNOWN_MISSING_ROUTES "
        f"entfernen: {stale}"
    )


# --- Was die Sicherung enthält, festgehalten ---

def test_the_backup_contains_only_the_settings_file():
    """
    Kein Fehler, aber eine Erwartung, die auseinandergehen kann: „Backup"
    klingt nach allem, geliefert wird `settings.json`.

    Die Konten (`users.db`) und die Bibliothek (`media_library.db`) sind nicht
    dabei — und damit auch keine Favoriten, Tags oder Vault-Marken, denn die
    liegen seit der Mehrbenutzer-Umstellung dort.
    """
    block = FILES_PY.split("def _handle_backup", 1)[1].split("\ndef ", 1)[0]

    assert "SETTINGS_FILE" in block
    assert "users.db" not in block
    assert "media_library" not in block


def test_the_settings_file_still_carries_the_migrated_keys_as_empty_shells():
    """
    Der unangenehme Teil: `settings.json` führt `scan_targets`,
    `exclude_paths`, `available_tags` und die `sensitive_*`-Listen weiterhin —
    aber leer, weil die echten Werte pro Nutzer in `users.db` stehen.

    Eine Wiederherstellung, die diese Datei über die Einstellungen schreibt,
    würde also nicht nur nichts zurückbringen, sondern die vorhandenen Werte
    mit leeren Listen überschreiben. Das ist der Grund, warum ich die
    Import-Route **nicht** erfunden habe.
    """
    from arcade_scanner.config import DEFAULT_SETTINGS_JSON

    migrated = ["scan_targets", "exclude_paths", "available_tags",
                "sensitive_dirs", "sensitive_collections"]

    present = [k for k in migrated if k in DEFAULT_SETTINGS_JSON]
    assert present, "Die Schlüssel sind verschwunden — dann Bericht anpassen"

    for key in present:
        assert DEFAULT_SETTINGS_JSON[key] == [], (
            f"{key} hat in settings.json einen Wert — dann ist unklar, welcher "
            "gilt: der dort oder der pro Nutzer in users.db"
        )

    # `sensitive_tags` ist die Ausnahme und trägt echte Voreinstellungen.
    # Ausdrücklich hier vermerkt, weil ich zuerst dasselbe erwartet hatte und
    # der Test zu Recht rot wurde.
    assert DEFAULT_SETTINGS_JSON["sensitive_tags"] == ["nsfw", "adult", "18+"]


def test_settings_written_per_user_would_be_overwritten_by_an_empty_list():
    """
    Die Mechanik dahinter, damit die Warnung oben belegt ist: Der
    Einstellungs-Handler unterscheidet „nicht angegeben" (None) von „leer"
    ([]) — und schreibt eine leere Liste durch.
    """
    settings_py = (ROUTES / "settings.py").read_text(encoding="utf-8")

    assert 'new_settings.pop("scan_targets", None)' in settings_py
    # Die Unterscheidung „nicht angegeben" (None) gegen „leer" ([]) steckt seit
    # dem Umbau auf update_user() in dieser Filterzeile statt in acht
    # `if ... is not None:`-Blöcken. Die Bedeutung ist dieselbe: None fällt
    # weg, eine leere Liste wird durchgeschrieben.
    assert "if v is not None" in settings_py


def test_the_import_button_is_recorded_as_unfinished():
    """
    Solange es keine Route gibt, soll wenigstens festgehalten sein, dass der
    Knopf da ist. Verschwindet er oder kommt die Route, wird dieser Test rot —
    und dann gehört der Bericht angepasst.
    """
    assert "function importSettings()" in SETTINGS_JS
    assert "/api/user/import" not in json.dumps(sorted(server_routes()))
