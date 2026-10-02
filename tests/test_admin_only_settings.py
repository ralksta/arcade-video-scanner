"""
test_admin_only_settings.py
---------------------------
Globale Einstellungen nur für Admins (Entscheidung 2026-10-02).

Der Server verwirft globale Schlüssel von Nicht-Admins (test_routes_settings.py).
Hier: die Oberfläche blendet genau diese Felder aus — und nur diese; die
Sicherung der globalen Einstellungen gibt es nur noch für Admins.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import files

ROOT = Path(__file__).parent.parent
TEMPLATE = (ROOT / "arcade_scanner" / "templates" / "components.py").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "arcade_scanner" / "server" / "static" / "settings.js").read_text(encoding="utf-8")


def _container_of(element_id: str) -> str:
    """Der öffnende Tag der innersten <section> bzw. Karte um ein Element."""
    pos = TEMPLATE.index(f'id="{element_id}"')
    before = TEMPLATE[:pos]
    starts = [m for m in re.finditer(r"<(section|div class=\"ds-settings-card)[^>]*>", before)]
    return starts[-1].group(0)


@pytest.mark.parametrize("element_id", [
    "defaultExclusionsContainer", "settingsVerboseScanning", "settingsOptimizer",
])
def test_global_fields_are_admin_only(element_id):
    assert "data-admin-only" in _container_of(element_id), element_id


@pytest.mark.parametrize("element_id", [
    "settingsTargets", "settingsExcludes", "settingsScanImages", "settingsSensitiveDirs",
])
def test_own_fields_stay_visible(element_id):
    assert "data-admin-only" not in _container_of(element_id), (
        f"{element_id} gehört dem Nutzer — darf nicht ausgeblendet werden"
    )


@pytest.mark.parametrize("section", ["performance", "backup"])
def test_whole_global_tabs_are_admin_only(section):
    button = re.search(rf'<button class="settings-nav-item[^"]*" data-section="{section}"[^>]*>', TEMPLATE)
    assert button and "data-admin-only" in button.group(0)


def test_content_sections_are_not_marked():
    """Die Reiter-Inhalte schalten über `hidden` um — dort nichts markieren."""
    for match in re.finditer(r'<div class="content-section[^>]*>', TEMPLATE):
        assert "data-admin-only" not in match.group(0)


def test_the_dialog_applies_the_flag_without_the_hidden_class():
    open_fn = SETTINGS_JS.split("async function openSettings", 1)[1].split("\nasync function ", 1)[0]
    assert "applyAdminOnlyVisibility(data.is_admin === true)" in open_fn
    apply_fn = SETTINGS_JS.split("function applyAdminOnlyVisibility", 1)[1].split("\n}", 1)[0]
    assert "style.display" in apply_fn and "hidden" not in apply_fn.replace("// ", "")


# --- Backup ---

def _backup(is_admin, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"proxy_root": "/srv"}', encoding="utf-8")
    handler = MagicMock()
    handler.get_current_user.return_value = "kim"
    account = MagicMock()
    account.is_admin = is_admin
    user_db = MagicMock()
    user_db.get_user.return_value = account
    with patch("arcade_scanner.server.api_handler.user_db", user_db), \
         patch("arcade_scanner.config.SETTINGS_FILE", str(settings_file)):
        files._handle_backup(handler)
    return handler


def test_a_non_admin_gets_no_backup(tmp_path):
    handler = _backup(False, tmp_path)
    handler.send_error.assert_called_once()
    assert handler.send_error.call_args[0][0] == 403
    handler.wfile.write.assert_not_called()


def test_an_admin_gets_the_backup(tmp_path):
    handler = _backup(True, tmp_path)
    handler.send_error.assert_not_called()
    handler.wfile.write.assert_called_once_with(b'{"proxy_root": "/srv"}')
