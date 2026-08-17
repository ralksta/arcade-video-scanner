import json
import os
import socket

from arcade_scanner.config import config
from arcade_scanner.templates.components import (
    BATCH_BAR_COMPONENT,
    CINEMA_MODAL_COMPONENT,
    COLLECTION_MODAL_COMPONENT,
    DUPLICATE_CHECKER_MODAL_COMPONENT,
    FILTER_BAR_COMPONENT,
    FILTER_PANEL_COMPONENT,
    FOLDER_BROWSER_LEGEND_COMPONENT,
    FOLDER_SIDEBAR_COMPONENT,
    GIF_EXPORT_PANEL_COMPONENT,
    HIDDEN_PATH_MODAL_COMPONENT,
    LIST_VIEW_COMPONENT,
    OPTIMIZE_PANEL_COMPONENT,
    SAVED_VIEWS_COMPONENT,
    SETTINGS_MODAL_COMPONENT,
    SETUP_WIZARD_COMPONENT,
    SHORTCUTS_MODAL_COMPONENT,
    TAG_MANAGER_MODAL_COMPONENT,
    TREEMAP_LEGEND_COMPONENT,
)
from arcade_scanner.templates.theme import CURRENT_THEME
from arcade_scanner.templates.ui_components import (
    render_base_layout,
    render_header,
    render_navigation,
)

# Stylesheets und JS-Module in Ladereihenfolge. Die Reihenfolge ist bindend:
# store.js definiert die Globals, auf die engine.js beim Laden zugreift, und
# filter_engine.js muss vor cards.js stehen. Tests pinnen beides.
STYLESHEETS = [
    "styles.css",
    "timeline_scrubber.css",
]

SCRIPT_MODULES = [
    # Muss vorn stehen: store.js, utils.js, workspace.js, collections.js und
    # settings.js greifen über `window.safeStorage` auf localStorage zu.
    "safe_storage.js",
    "store.js",
    "formatters.js",
    "api.js",
    "utils.js",
    "treemap_layout.js",
    "treemap.js",
    "settings.js",
    "autotag.js",
    "duplicates.js",
    "candidates.js",
    "filter_engine.js",
    "workspace.js",
    "cards.js",
    "batch_operations.js",
    "tag_manager.js",
    "folder_browser.js",
    "engine.js",
    "optimizer.js",
    "cinema.js",
    "similar.js",
    "timeline_scrubber.js",
    "gif_export.js",
    "collections.js",
    "context_menu.js",
    "shortcuts.js",
    "empty_state.js",
    "export_view.js",
    "a11y.js",
]


def asset_url(filename: str) -> str:
    """URL eines statischen Assets mit Cache-Buster aus seiner Änderungszeit.

    Vorher stand hier ``?v={int(time.time())}`` — für jede Datei derselbe Wert,
    neu bei jeder Neugenerierung des HTML. Da der Report nach jedem Scan, jeder
    Einstellungsänderung und jedem Encode-Upload neu geschrieben wird, bekamen
    alle 28 Assets regelmäßig frische URLs. Eine neue URL ist im Browser-Cache
    ein Fehltreffer, kein 304: die vollen 588 KB (122 KB gzip) wurden erneut
    übertragen, obwohl sich an ihnen nichts geändert hatte.

    Mit der mtime der jeweiligen Datei ändert sich die URL nur, wenn sich die
    Datei tatsächlich ändert — und dann auch nur ihre eigene.

    Args:
        filename: Dateiname relativ zum statischen Verzeichnis.

    Returns:
        Pfad mit Versions-Query, z. B. ``/static/engine.js?v=1755380000``.
    """
    try:
        version = int(os.path.getmtime(os.path.join(config.static_dir, filename)))
    except OSError:
        # Fehlt die Datei, ist das ein Deployment-Fehler, kein Grund für einen
        # Absturz beim Rendern. Ohne Versionsangabe greift der no-cache-Header
        # des Servers, der Browser revalidiert also ohnehin.
        version = 0
    return f"/static/{filename}?v={version}"


def generate_html_report(report_file, server_port=8000):
    """Schreibt den statischen Dashboard-Dump.

    Nimmt **keine** Medien-Einträge mehr entgegen. Der Dump enthält keine —
    `window.ALL_VIDEOS` startet leer und wird zur Laufzeit über `/api/videos`
    gefüllt, pro Nutzer gefiltert.

    Der frühere Parameter `results` wurde zuletzt nirgends mehr gelesen, aber
    von fünf Aufrufern beschafft, und zwar so::

        results = [e.model_dump(by_alias=True) for e in db.get_all()]

    Das sind 8788 Pydantic-Modelle plus 8788 Umwandlungen je Aufruf, für
    nichts. An einer Stelle (`routes/files.py`, Hintergrund-Rescan) lief es
    sogar über `media_cache.get()`, das bereits Dicts liefert — der Aufruf warf
    dort jedes Mal einen `AttributeError`, und das umgebende `except` machte
    daraus ein „❌ Rescan failed", nachdem der Scan längst durch war. Die
    Zeilen danach — Cache verwerfen und Report neu erzeugen — wurden nie
    erreicht.
    """
    #
    # Keine Ordner-Aggregation mehr im Dump: Diese Datei wird EINMAL erzeugt und
    # an jeden Nutzer ausgeliefert. Die Aggregation enthielt die Ordnerpfade der
    # gesamten Bibliothek — also auch die Verzeichnisse anderer Nutzer, obwohl
    # /api/videos anschließend sauber nach Scan-Zielen filtert. Der Ordner-Baum
    # baut sich jetzt clientseitig aus ALL_VIDEOS auf (buildFoldersData() in
    # folder_browser.js), das bereits pro Nutzer gefiltert ist.

    # Mehrbenutzer-Trennung: Der statische Dump enthält überhaupt keine
    # Medien-Einträge — `window.ALL_VIDEOS` startet als leeres Array, gefüllt
    # wird es erst zur Laufzeit über /api/videos und /api/user/data.
    #
    # Hier stand früher eine Schleife, die von jedem Eintrag eine Kopie zog und
    # darin favorite/hidden/tags zurücksetzte. Seit der Dump keine Einträge mehr
    # einbettet, wurde das Ergebnis nirgends verwendet: 8788 Dict-Kopien und
    # ~10 ms bei jeder Neugenerierung des Reports, ersatzlos verworfen.

    user_settings_json = json.dumps(config.settings.model_dump())

    # Logic for enabled state: Must be installed AND enabled in settings
    opt_avail_str = 'true' if config.optimizer_available else 'false'
    opt_enabled_str = 'true' if (config.optimizer_available and config.settings.enable_optimizer) else 'false'

    active_theme = CURRENT_THEME

    # 1. Prepare Header (Themed)
    header_html = render_header(active_theme, hostname=socket.gethostname().upper())

    # 2. Prepare Cinema Modal (Conditional Optimize Button)
    opt_btn_html = ""
    if config.optimizer_available and config.settings.enable_optimizer:
        # Die einzige Primaeraktion der Rail — traegt als einzige den Accent.
        opt_btn_html = """
        <button class="cinema-rail-btn is-primary" onclick="cinemaOptimize()" title="Optimize Video [O]" aria-label="Optimize this video">
            <span class="cinema-rail-icon"><span class="material-icons" aria-hidden="true">bolt</span></span>
            <span class="cinema-rail-label">Optimize</span>
        </button>
        """

    cinema_modal_html = CINEMA_MODAL_COMPONENT.format(opt_btn=opt_btn_html)

    # 3. Assemble Main Content
    # Render Navigation using Theme
    nav_html = render_navigation(active_theme)

    main_body_html = f"""
    {nav_html}

    {FOLDER_SIDEBAR_COMPONENT}

    <!-- Desktop: Main Content Area (offset by sidebar width) -->
    <div class="flex-1 flex flex-col md:ml-[200px] min-h-screen bg-bg relative overflow-x-hidden max-w-full">
        {header_html}

        {FILTER_BAR_COMPONENT}

        {SAVED_VIEWS_COMPONENT}

        {TREEMAP_LEGEND_COMPONENT}

        {FOLDER_BROWSER_LEGEND_COMPONENT}

        <!-- Quick Stats Ribbon -->
        <div id="quickStatsRibbon"
             style="display:none;align-items:center;gap:8px;flex-wrap:wrap;
                    padding:6px 16px;font-size:12px;
                    border-bottom:1px solid var(--surface-border, rgba(0,0,0,.08));
                    background:var(--surface-glass, rgba(0,0,0,.05));
                    backdrop-filter:blur(4px);
                    color:var(--text-muted, #6b7280);">
        </div>

        <!-- Main Content Container with safe area padding -->
        <main class="flex-1 p-2 md:p-6 pb-[80px] md:pb-6 relative w-full overflow-x-hidden" id="mainContentArea">

            <!-- Video Grid -->
            <div id="videoGrid" class="responsive-grid transition-opacity duration-300 overflow-hidden">
                <!-- Skeleton cards shown while data loads -->
                {''.join(['''
                <div class="group relative w-full bg-card rounded-ds-md overflow-hidden border border-line/60 flex flex-col skeleton-card" aria-hidden="true">
                    <div class="aspect-video bg-ink/5 animate-pulse"></div>
                    <div class="px-[11px] py-2.5 flex flex-col gap-2">
                        <div class="h-3 bg-ink/5 animate-pulse rounded w-3/4"></div>
                        <div class="h-2 bg-ink/5 animate-pulse rounded w-1/2"></div>
                        <div class="h-[3px] bg-ink/5 animate-pulse rounded w-full mt-2"></div>
                    </div>
                </div>''' for _ in range(8)])}
            </div>

            <!-- List View -->
            {LIST_VIEW_COMPONENT}

            <!-- Treemap Container -->
            <div id="treemapContainer" class="hidden h-[70vh] w-full rounded-xl overflow-hidden border border-ink/10 shadow-2xl"></div>

            <!-- Empty State (von engine.js befüllt, wenn 0 Treffer) -->
            <div id="emptyState" class="hidden flex-col items-center justify-center text-center py-20 px-6">
                <span id="emptyStateIcon" class="material-icons text-[44px] text-text-muted opacity-60 mb-3" aria-hidden="true">search_off</span>
                <h2 id="emptyStateTitle" class="text-[16px] font-semibold text-text-main mb-1.5">Nichts gefunden</h2>
                <p id="emptyStateHint" class="text-[13px] text-text-muted max-w-md leading-6"></p>
                <div id="emptyStateActions" class="flex flex-wrap items-center justify-center gap-2 mt-5"></div>
            </div>

            <!-- Loading Spinner -->
            <div id="loadingSentinel" class="h-24 flex items-center justify-center opacity-0 transition-opacity">
                <span class="material-icons animate-spin text-arcade-cyan text-3xl" aria-hidden="true">refresh</span>
            </div>

        </main>


    </div>

    <!-- Modals & Overlays -->
    {cinema_modal_html}
    {DUPLICATE_CHECKER_MODAL_COMPONENT}
    {OPTIMIZE_PANEL_COMPONENT}
    {GIF_EXPORT_PANEL_COMPONENT}
    {SETTINGS_MODAL_COMPONENT}
    {FILTER_PANEL_COMPONENT}
    {TAG_MANAGER_MODAL_COMPONENT}
    {COLLECTION_MODAL_COMPONENT}
    {SETUP_WIZARD_COMPONENT}
    {HIDDEN_PATH_MODAL_COMPONENT}
    {SHORTCUTS_MODAL_COMPONENT}
    {BATCH_BAR_COMPONENT}

    <!-- Hidden frame for form submissions if needed -->
    <iframe name='h_frame' style='display:none;'></iframe>
    """

    # 4. Prepare Scripts
    scripts_html = f"""
        window.SERVER_PORT = {server_port};
        window.FOLDERS_DATA = {{}}; /* aus ALL_VIDEOS aufgebaut, siehe folder_browser.js */
        window.ALL_VIDEOS = []; /* Loaded via API for user isolation */
        window.userSettings = {user_settings_json};
        window.OPTIMIZER_AVAILABLE = {opt_avail_str};
        window.ENABLE_OPTIMIZER = {opt_enabled_str};
    """

    full_scripts_block = f"""
    <script>
    {scripts_html}
    </script>
    """

    stylesheet_tags = "\n    ".join(
        f'<link rel="stylesheet" href="{asset_url(name)}">' for name in STYLESHEETS
    )
    script_tags = "\n    ".join(
        f'<script src="{asset_url(name)}"></script>' for name in SCRIPT_MODULES
    )
    external_scripts = f"""
    {stylesheet_tags}
    {script_tags}
    """

    # Combine content using Theme-aware Base Layout
    final_html = render_base_layout(
        active_theme,
        content=main_body_html + external_scripts,
        scripts=full_scripts_block,
    )

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(final_html)
