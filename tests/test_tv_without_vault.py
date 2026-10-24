"""
test_tv_without_vault.py
------------------------
Der TV-Client nach dem Entfernen des Vaults (UMSETZUNGSPLAN Phase 1).

Bis 2026-10-02 sperrte der Fernseher die ganze Mediathek, wenn
/api/user/data nicht antwortete — sonst wäre der Vault im Raster gelandet
(test_tv_vault_guard.py, entfernt). Den Vault gibt es nicht mehr, und der TV
kennt keinen abgesicherten Modus: Jetzt zeigt er die Mediathek ohne Favoriten
und Tags und sagt es im Untertitel.
"""
import re
from pathlib import Path

PANEL = (Path(__file__).parent.parent / "tv_client" / "src" / "views" / "MainPanel.js").read_text(
    encoding="utf-8")


def test_no_vault_state_is_read_or_filtered():
    assert "vaulted" not in PANEL
    assert not re.search(r"\bv\.hidden\b", PANEL)


def test_the_archive_tab_is_gone():
    assert 'title="Archiv"' not in PANEL


def test_missing_user_data_no_longer_blocks_the_library():
    assert "{!loading && (" in PANEL
    assert "!userDataFailed &&" not in PANEL


def test_missing_user_data_is_mentioned_in_the_subtitle():
    block = PANEL.split("const subtitle = userDataFailed", 1)[1].split(";", 1)[0]
    assert "Nutzerdaten fehlen" in block
