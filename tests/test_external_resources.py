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

import pytest

ROOT = Path(__file__).parent.parent

MARKUP_SOURCES = [
    ROOT / "arcade_scanner" / "templates" / "ui_components.py",
    ROOT / "arcade_scanner" / "templates" / "dashboard_template.py",
    ROOT / "arcade_scanner" / "templates" / "components.py",
    ROOT / "arcade_scanner" / "server" / "static" / "login.html",
    ROOT / "arcade_scanner" / "server" / "static" / "settings_redesign.html",
]

# Bekannte Fremdquellen, Stand 2026-08-17.
KNOWN_EXTERNAL_HOSTS = {
    "cdn.tailwindcss.com": "Tailwind JIT — liefert ausführbares JavaScript",
    "fonts.googleapis.com": "Google Fonts CSS (Inter, Material Icons)",
    "fonts.gstatic.com": "Google Fonts Schriftdateien",
}

HOST_RE = re.compile(r"https?://([a-zA-Z0-9.-]+)")


def _external_hosts(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    hosts = set(HOST_RE.findall(path.read_text(encoding="utf-8")))
    # w3.org taucht nur als SVG-Namensraum auf, es wird nichts geladen.
    return {h for h in hosts if h != "www.w3.org"}


def test_no_unexpected_external_hosts():
    """
    Der eigentliche Zweck: Es sollen keine weiteren Fremdserver dazukommen,
    ohne dass jemand darüber nachdenkt.
    """
    found = set()
    for path in MARKUP_SOURCES:
        found |= _external_hosts(path)

    unexpected = found - set(KNOWN_EXTERNAL_HOSTS)
    assert not unexpected, (
        f"Neue Fremdquelle im Dashboard: {sorted(unexpected)}. "
        "Wenn das gewollt ist, in KNOWN_EXTERNAL_HOSTS eintragen und "
        "dev-docs/external-resources.md ergänzen."
    )


@pytest.mark.parametrize("host,reason", sorted(KNOWN_EXTERNAL_HOSTS.items()))
def test_known_hosts_are_still_used(host, reason):
    """
    Gegenprobe: Verschwindet eine der Quellen, ist das ein Fortschritt — dann
    gehört sie aus der Liste und die Doku aktualisiert.
    """
    found = set()
    for path in MARKUP_SOURCES:
        found |= _external_hosts(path)

    assert host in found, (
        f"{host} wird nicht mehr geladen ({reason}) — schön! "
        "Bitte aus KNOWN_EXTERNAL_HOSTS entfernen und "
        "dev-docs/external-resources.md aktualisieren."
    )


def test_the_login_page_also_contacts_them():
    """
    Wichtig für die Einordnung: Es passiert schon *vor* der Anmeldung, also
    auch für jeden, der die Seite nur aufruft.
    """
    hosts = _external_hosts(ROOT / "arcade_scanner" / "server" / "static" / "login.html")
    assert hosts, "Anmeldeseite lädt nichts mehr extern — Doku aktualisieren"


def test_no_local_replacement_exists_yet():
    """
    Zustandsbeschreibung: Solange nichts lokal liegt, ist die Abhängigkeit echt
    und nicht nur ein Fallback.
    """
    static = ROOT / "arcade_scanner" / "server" / "static"
    local_assets = list(static.glob("*.woff*")) + list(static.rglob("fonts/*"))
    tailwind_css = [p for p in static.glob("*.css") if "tailwind" in p.name.lower()]

    assert not local_assets and not tailwind_css, (
        "Es liegen jetzt lokale Schriften oder eine Tailwind-CSS vor — "
        "dann sollten die CDN-Verweise verschwinden. Siehe "
        "dev-docs/external-resources.md."
    )


def test_the_tradeoff_is_documented():
    doc = ROOT / "dev-docs" / "external-resources.md"
    assert doc.is_file()

    text = doc.read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" in text
    assert "no build step" in text, "Der Konflikt mit der Architekturentscheidung fehlt"
    assert "Entscheidungsvorlage" in text


def test_readme_claim_is_qualified():
    """
    Die Zusage „100% locally" stand ohne Einschränkung da. Sie muss entweder
    zutreffen oder benennen, was ausgenommen ist.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    privacy_line = next(
        (ln for ln in readme.splitlines() if "Privacy-First" in ln), ""
    )
    assert privacy_line, "Privacy-Zusage nicht mehr im README gefunden"
    assert "CDN" in privacy_line or "cdn" in privacy_line, (
        "Die Zusage nennt die CDN-Ausnahme nicht — entweder die Abhängigkeit "
        "beseitigen oder die Aussage präzisieren."
    )
