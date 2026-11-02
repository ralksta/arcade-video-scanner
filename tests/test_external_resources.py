"""
test_external_resources.py
--------------------------
Hält fest, welche Fremdserver das Dashboard kontaktiert.

Das README verspricht an erster Stelle: „No data ever leaves your computer. The
scan, database, and web dashboard run 100% locally." Für Scan und Datenbank
stimmt das. Das Dashboard lädt jedoch Tailwind von Cloudflare und Schriften von
Google — bei jedem Aufruf, auch auf der Anmeldeseite vor dem Login.

Die Mediendaten verlassen den Rechner dabei nicht; es geht um IP, User-Agent
und Zeitpunkt der Nutzung. Bei `cdn.tailwindcss.com` kommt hinzu, dass es
ausführbares JavaScript in die angemeldete Sitzung liefert.

Ob das geändert oder die Zusage präzisiert wird, steht in
`dev-docs/external-resources.md` — es ist eine Abwägung gegen die
Architekturentscheidung „no build step", nicht ein eindeutiger Fehler.

Diese Tests sichern den Ist-Zustand: keine neuen Fremdquellen unbemerkt dazu,
und die Behebung fällt auf, wenn sie kommt.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

MARKUP_SOURCES = [
    ROOT / "arcade_scanner" / "templates" / "ui_components.py",
    ROOT / "arcade_scanner" / "templates" / "dashboard_template.py",
    ROOT / "arcade_scanner" / "templates" / "components.py",
    ROOT / "arcade_scanner" / "server" / "static" / "login.html",
    ROOT / "arcade_scanner" / "server" / "static" / "settings_redesign.html",
]

# Seit 2026-11-02 sind alle Schriften und Tailwind lokalisiert — keine Fremdquellen mehr erlaubt.
KNOWN_EXTERNAL_HOSTS: dict[str, str] = {}

HOST_RE = re.compile(r"https?://([a-zA-Z0-9.-]+)")


def _external_hosts(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    hosts = set(HOST_RE.findall(path.read_text(encoding="utf-8")))
    # w3.org taucht nur als SVG-Namensraum auf, es wird nichts geladen.
    return {h for h in hosts if h != "www.w3.org"}


def test_no_unexpected_external_hosts():
    """
    Der eigentliche Zweck: Es dürfen keinerlei Fremdserver aus dem Markup
    oder den Templates kontaktiert werden.
    """
    found = set()
    for path in MARKUP_SOURCES:
        found |= _external_hosts(path)

    unexpected = found - set(KNOWN_EXTERNAL_HOSTS)
    assert not unexpected, (
        f"Fremdquelle im Dashboard gefunden: {sorted(unexpected)}. "
        "Alle Schriften und Stylesheets müssen lokal unter /static/ liegen."
    )


def test_the_login_page_contacts_no_external_hosts():
    """
    Auch vor der Anmeldung darf die Login-Seite keinen Fremdserver kontaktieren.
    """
    hosts = _external_hosts(ROOT / "arcade_scanner" / "server" / "static" / "login.html")
    assert not hosts, f"Anmeldeseite lädt externe Ressourcen: {sorted(hosts)}"


def test_local_fonts_and_tailwind_exist():
    """
    Lokale Schriften (woff2) und vorkompiliertes Tailwind-CSS liegen in static/
    bereit und sind in styles.css bzw. dashboard_template.py verdrahtet.
    """
    static = ROOT / "arcade_scanner" / "server" / "static"
    for font_name in ("inter-latin.woff2", "inter-latin-ext.woff2", "material-icons.woff2"):
        font_file = static / "fonts" / font_name
        assert font_file.is_file() and font_file.stat().st_size > 10_000, (
            f"Lokale Schrift fehlt oder ist leer: {font_file}"
        )

    tailwind_css = static / "tailwind.css"
    assert tailwind_css.is_file() and tailwind_css.stat().st_size > 20_000, (
        "Vorkompiliertes static/tailwind.css fehlt oder ist unvollständig"
    )
    css_text = tailwind_css.read_text(encoding="utf-8")
    # Stichprobe zentraler Design-System-Utilities aus theme.py
    for expected_selector in (".bg-arcade-bg", ".text-text-main", ".bg-card", ".text-arcade-cyan"):
        assert expected_selector in css_text, (
            f"{expected_selector} fehlt in static/tailwind.css"
        )


def test_the_tradeoff_is_documented():
    doc = ROOT / "dev-docs" / "external-resources.md"
    assert doc.is_file()

    text = doc.read_text(encoding="utf-8")
    assert "static/tailwind.css" in text
    assert "no build step" in text


def test_readme_claim_matches_local_reality():
    """
    Die Zusage „100% locally" im README stimmt jetzt ohne CDN-Ausnahme.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    privacy_line = next(
        (ln for ln in readme.splitlines() if "Privacy-First" in ln), ""
    )
    assert privacy_line, "Privacy-Zusage nicht mehr im README gefunden"
    assert "100% locally" in privacy_line
    assert "cdn.tailwindcss.com" not in privacy_line
