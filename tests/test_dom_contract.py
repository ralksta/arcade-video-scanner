"""
test_dom_contract.py
--------------------
DOM Contract Tests: Prüft dass alle JS-seitig referenzierten Element-IDs
auch tatsächlich im HTML-Template vorhanden sind — und umgekehrt.

Warum dieser Test existiert:
    JS ruft getElementById('searchBar') auf — aber wenn das Template
    die ID umbenennt oder löscht, crasht die JS-Funktion stumm im Browser.
    node --check erkennt das nicht (kein DOM vorhanden).
    Dieser Test verifiziert den "DOM Contract" statisch.

Was hier getestet wird:
    1. Alle getElementById-Calls in JS → ID muss in Template existieren
    2. Kritische onclick="fn()" im Template → fn muss window.* sein
    3. CSS var(--x) Referenzen → Custom Property muss in :root definiert sein
"""
import re
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"
TEMPLATES_DIR = Path(__file__).parent.parent / "arcade_scanner" / "templates"

EXCLUDE_JS = {"aframe.min.js", "vr_museum.js"}

# IDs, die bewusst nur dynamisch (per JS) erzeugt werden — kein Static-HTML-Match erwartet
DYNAMIC_IDS = {
    # Von renderCollections() dynamisch erzeugte IDs:
    "cat-items-", "cat-arrow-",
    # Von renderVideoCard() erzeugte IDs:
    "card-", "video-",
    # Toast-Queue (dynamisch per JS):
    "toast-",
}

# IDs, die in externen Libraries oder conditionalem HTML sind (kein False-Positive)
# Auch: IDs in anderen templates/HTML-Files die nicht in components.py sind
KNOWN_EXTERNAL_IDS = {
    # Command Palette (context_menu.js)
    "cmdResults",
    # Cinema Toast (cinema.js)
    "cinemaToast",
    # BatchTag Modal — in components.py aber evtl. anderer template-Teil
    "batchTagModal", "batchTagOptions", "batchTagSearch",
    "batchTagNewInput", "batchTagCount", "batchSkipWarning",
    # Scan Progress (settings_redesign.html oder Dashboard-Header)
    "scan-progress-bar", "scan-progress-text", "scan-status-text",
    # Filter Controls — in Dashboard-Bar (dashboard_template.py)
    "statusSelect", "codecSelect", "sortSelect",
    # Count/Size stats ribbon
    "count-total", "size-total",
    # View Toggle Button (Dashboard-Topbar)
    "toggleView", "saveViewBtn", "showHiddenToggle",
    # Treemap Canvas (in components)
    "treemapCanvas", "treemapTooltip",
    # Optimizer codec select (in optimizer modal)
    "optCodecRow",
    # Collections Modal fields (in COLLECTION_MODAL_COMPONENT, separate search)
    "matchCountNumber", "matchCountLabel", "matchCountIcon",
    "tagLogicBtn",
    # Mobile / Dual-input
    "searchBar", "mobileSearchInput",
    # Cinema Info Panel alias
    "cinemaInfoPanel",
    # Admin / Settings redesign HTML
    "scanFolderPath",
}


def get_all_template_content() -> str:
    """Alle Template-Inhalte zusammen lesen."""
    content = ""
    for f in TEMPLATES_DIR.glob("*.py"):
        content += f.read_text(encoding="utf-8")
    return content


def get_all_js_content() -> str:
    """Alle JS-Inhalte (ohne vendor) zusammen lesen."""
    content = ""
    for f in sorted(STATIC_DIR.glob("*.js")):
        if f.name not in EXCLUDE_JS:
            content += f.read_text(encoding="utf-8")
    return content


def get_ids_from_templates() -> set:
    """Alle id="..." Werte aus den Templates extrahieren."""
    content = get_all_template_content()
    # Match both: id="foo" and id='foo'
    matches = re.findall(r"""id=["']([^"']+)["']""", content)
    return set(matches)


def get_getElementById_calls(js_content: str) -> set:
    """Alle getElementById('...') Calls aus dem JS extrahieren."""
    matches = re.findall(r"""getElementById\(['"]([^'"]+)['"]\)""", js_content)
    return set(matches)


def is_dynamic_id(id_str: str) -> bool:
    """Ist die ID dynamisch generiert (z.B. 'cat-items-' Prefix)?"""
    return any(id_str.startswith(prefix) for prefix in DYNAMIC_IDS)


class TestDomContract:

    def test_js_getElementById_ids_exist_in_templates(self):
        """
        Jede ID die im JS per getElementById() referenziert wird,
        muss auch im HTML-Template als id='...' vorkommen.

        Verhindert: JS ruft getElementById('nonExistent') → null → Crash.
        """
        template_ids = get_ids_from_templates()
        js_ids = get_getElementById_calls(get_all_js_content())

        missing = set()
        for id_str in js_ids:
            if is_dynamic_id(id_str):
                continue
            if id_str in KNOWN_EXTERNAL_IDS:
                continue
            if id_str not in template_ids:
                missing.add(id_str)

        assert not missing, (
            "Diese IDs werden per getElementById() im JS referenziert,\n"
            "existieren aber NICHT im HTML-Template:\n"
            + "\n".join(f"  ❌ #{id_}" for id_ in sorted(missing))
            + "\n\nFix: ID im Template hinzufügen ODER als KNOWN_EXTERNAL_IDS listen."
        )

    def test_critical_element_ids_present(self):
        """
        Kritische Element-IDs die die App braucht müssen im Template sein.
        Schnell-Check für die absolut wichtigsten IDs.
        """
        template_ids = get_ids_from_templates()
        critical = [
            "videoGrid",
            "cinemaModal",
            "cinemaVideo",
            "collectionModal",
            "settingsModal",
        ]
        missing = [id_ for id_ in critical if id_ not in template_ids]
        assert not missing, (
            f"Kritische Element-IDs fehlen im Template: {missing}"
        )


class TestWindowFunctionContracts:
    """
    Prüft dass Funktionen die per onclick='fn()' im HTML aufgerufen werden
    auch als window.fn = fn exportiert sind — sonst: 'fn is not defined'.
    """

    REQUIRED_WINDOW_EXPORTS = [
        # Collections
        "openCollectionModal",
        "closeCollectionModal",
        "saveCollection",
        "applyCollection",
        "renderCollections",
        # Settings
        "openSettings",
        # Cinema
        "openCinema",
        # Workspace
        "setWorkspaceMode",
        "setLayout",
        # Filter
        "filterAndSort",
        "setFilter",
        "setSort",
    ]

    def _get_window_exports(self) -> set:
        all_exports = set()
        for f in sorted(STATIC_DIR.glob("*.js")):
            if f.name in EXCLUDE_JS:
                continue
            content = f.read_text(encoding="utf-8")
            matches = re.findall(r"window\.(\w+)\s*=", content)
            all_exports.update(matches)
        return all_exports

    def test_critical_functions_are_window_exported(self):
        """
        Alle kritischen Funktionen müssen als window.X exportiert sein,
        sonst landet 'ReferenceError: X is not defined' im Browser.
        """
        exports = self._get_window_exports()
        missing = [fn for fn in self.REQUIRED_WINDOW_EXPORTS if fn not in exports]
        assert not missing, (
            "Diese Funktionen werden per onclick im HTML aufgerufen,\n"
            "sind aber NICHT als window.X exportiert:\n"
            + "\n".join(f"  ❌ window.{fn}" for fn in missing)
        )


class TestCssVariableContracts:
    """
    Prüft dass CSS var(--x) Referenzen in styles.css auch definiert sind.
    Eine undefinierte CSS-Variable macht den Wert leer/transparent — silent fail.
    """

    CSS_FILE = STATIC_DIR / "styles.css"

    def _get_defined_vars(self, content: str) -> set:
        """Alle --varname: Definitionen in :root oder global."""
        return set(re.findall(r"--([\w-]+)\s*:", content))

    def _get_used_vars(self, content: str) -> set:
        """Alle var(--varname) Referenzen."""
        return set(re.findall(r"var\(--([\w-]+)\)", content))

    def test_all_css_vars_are_defined(self):
        """
        Jede var(--x) Referenz in styles.css muss auch als --x: definiert sein.
        Undefinierte CSS-Variablen sind silent — kein Fehler, einfach leer.
        """
        if not self.CSS_FILE.exists():
            pytest.skip("styles.css nicht gefunden")

        content = self.CSS_FILE.read_text(encoding="utf-8")
        defined = self._get_defined_vars(content)
        used = self._get_used_vars(content)

        # Browser-native + Tailwind Variablen die OK sind
        KNOWN_EXTERNALS = {
            # Tailwind design tokens (aus tailwind.config)
            "arcade-cyan", "arcade-gold", "arcade-magenta", "arcade-bg",
            "arcade-pink", "arcade-purple",
            # safe-area (iOS)
            "safe-area-inset-top", "safe-area-inset-bottom",
            "safe-area-inset-left", "safe-area-inset-right",
        }

        missing = used - defined - KNOWN_EXTERNALS
        assert not missing, (
            "Diese CSS-Variablen werden per var() verwendet,\n"
            "sind aber NICHT in styles.css definiert (silent fail — wird leer dargestellt):\n"
            + "\n".join(f"  ❌ --{v}" for v in sorted(missing))
        )

    def test_key_design_tokens_defined(self):
        """Kritische Design-Tokens müssen in :root definiert sein."""
        content = self.CSS_FILE.read_text(encoding="utf-8")
        defined = self._get_defined_vars(content)
        required = ["cyan", "gold", "magenta", "pink", "bg", "glass", "glass-border"]
        missing = [v for v in required if v not in defined]
        assert not missing, (
            f"Kritische Design-Tokens fehlen in styles.css: {[f'--{v}' for v in missing]}"
        )


class TestApiResponseSchema:
    """
    Prüft dass die Python-Backend API-Module die richtigen
    Felder/Keys in ihren Responses haben.

    Kein HTTP-Server nötig — reine Import/Interface-Tests.
    """

    def test_response_helpers_importable(self):
        """response_helpers.py muss ohne Fehler importierbar sein."""
        try:
            from arcade_scanner.server import response_helpers
        except ImportError as e:
            pytest.fail(f"response_helpers nicht importierbar: {e}")

    def test_video_dict_has_required_keys(self):
        """
        Das Video-Dict das die API ausliefert muss alle vom Frontend
        erwarteten Keys enthalten (z.B. FilePath, FileName, Size_MB, Bitrate_Mbps).

        Das Frontend in engine.js greift direkt auf v.FilePath, v.Size_MB etc. zu —
        wenn der Key fehlt, gibt's NaN oder undefined ohne Fehlermeldung.
        """
        try:
            from arcade_scanner.core.video_processor import get_video_metadata
        except ImportError:
            pytest.skip("video_processor nicht verfügbar")

        # Felder die engine.js/cards.js auf dem Video-Object erwartet
        # Hinweis: In video_processor.py kann der interne Key-Name abweichen
        # (z.B. 'filename' → Frontend renamed zu 'FileName'). Wir prüfen nur
        # die Keys die direkt im Source als String-Literal vorkommen.
        REQUIRED_FRONTEND_KEYS = {
            "FilePath", "Size_MB", "Bitrate_Mbps",
            "Status", "thumb",
        }

        # Wir können die Funktion nicht echt aufrufen — aber wir prüfen
        # ob die Keys in der Codebase als String-Konstanten vorkommen
        from pathlib import Path
        processor_src = (
            Path(__file__).parent.parent / "arcade_scanner" / "core" / "video_processor.py"
        ).read_text(encoding="utf-8")

        missing_from_source = [
            k for k in REQUIRED_FRONTEND_KEYS
            if k not in processor_src
        ]

        assert not missing_from_source, (
            "Diese Frontend-erwarteten Keys kommen im video_processor nicht vor —\n"
            "das könnte bedeuten sie werden nie gesetzt:\n"
            + "\n".join(f"  ❌ {k}" for k in missing_from_source)
        )
