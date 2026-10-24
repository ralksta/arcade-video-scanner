"""
test_saved_views_sharing.py
---------------------------
Hält fest, dass gespeicherte Ansichten *heute* zwischen allen Nutzern geteilt
werden — als Zustandsbeschreibung, nicht als Gutheißung.

`/api/settings` mischt sorgfältig alles über die globalen Einstellungen, was pro
Nutzer gehört: `smart_collections`, `scan_targets`, `exclude_paths`,
`available_tags`, `sensitive_*`. `saved_views` fehlt in dieser Liste und lebt
nur in `AppSettings`, also in der gemeinsamen `settings.json`.

Eine gespeicherte Ansicht enthält den frei eingegebenen Suchbegriff und einen
Ordnerpfad. Jeder angemeldete Nutzer sieht damit, wonach die anderen gesucht
haben, und kann deren Ansichten überschreiben.

Ob das gewollt ist, hängt von der Installation ab — Familie oder getrennte
Konten. Die Entscheidung steht in `dev-docs/saved-views-are-shared.md`. Bis sie
gefallen ist, sichern diese Tests den Ist-Zustand, damit eine Änderung bewusst
geschieht und nicht als Nebenwirkung.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent
SETTINGS_ROUTE = ROOT / "arcade_scanner" / "server" / "routes" / "settings.py"
CONFIG_PY = ROOT / "arcade_scanner" / "config.py"
USER_STORE = ROOT / "arcade_scanner" / "database" / "user_store.py"

PER_USER_FIELDS = [
    "smart_collections",
    "scan_targets",
    "exclude_paths",
    "available_tags",
    "sensitive_dirs",
    "sensitive_tags",
    "sensitive_collections",
]


def _settings_merge_block() -> str:
    source = SETTINGS_ROUTE.read_text(encoding="utf-8")
    return source.split("settings_dump = config.settings.model_dump()", 1)[1][:2000]


def test_the_known_per_user_fields_are_still_overridden():
    """
    Gegenprobe: Verschwindet eines dieser Felder aus der Mischung, ist die
    Trennung an einer weiteren Stelle gebrochen.
    """
    block = _settings_merge_block()
    missing = [f for f in PER_USER_FIELDS if f'settings_dump["{f}"]' not in block]
    assert not missing, f"Nicht mehr pro Nutzer gemischt: {missing}"


def test_saved_views_is_still_global():
    """
    Der dokumentierte Ist-Zustand. Schlägt dieser Test fehl, wurde
    `saved_views` pro Nutzer gemacht — dann gehört
    dev-docs/saved-views-are-shared.md aktualisiert oder gelöscht und dieser
    Test entfernt.
    """
    block = _settings_merge_block()
    assert 'settings_dump["saved_views"]' not in block, (
        "saved_views wird jetzt pro Nutzer gemischt — schön! "
        "dev-docs/saved-views-are-shared.md und diesen Test bitte aufräumen."
    )

    assert "saved_views" in CONFIG_PY.read_text(encoding="utf-8"), (
        "saved_views ist nicht mehr in AppSettings — Zustand hat sich geändert."
    )


def test_saved_views_has_no_per_user_home():
    """Es gibt kein Feld in UserData, in das die Ansichten gehören würden."""
    assert "saved_views" not in USER_STORE.read_text(encoding="utf-8")


def test_a_saved_view_really_carries_search_and_folder():
    """
    Die Begründung für die Einstufung: Ohne Suchbegriff und Ordnerpfad wäre das
    Teilen belanglos.
    """
    settings_js = (
        ROOT / "arcade_scanner" / "server" / "static" / "settings.js"
    ).read_text(encoding="utf-8")
    block = settings_js.split("const newView = {", 1)[1].split("};", 1)[0]

    assert "search:" in block
    assert "folder:" in block


def test_the_decision_is_written_down():
    doc = ROOT / "dev-docs" / "saved-views-are-shared.md"
    assert doc.is_file()

    text = doc.read_text(encoding="utf-8")
    assert "saved_views" in text
    assert "UserData" in text, "Der Weg zur Behebung fehlt"
    assert "Produktentscheidung" in text or "Entscheidungsvorlage" in text
