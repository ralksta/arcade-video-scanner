import json
import os
import socket
import time

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


def generate_html_report(results, report_file, server_port=8000):
    total_mb = sum(r["Size_MB"] for r in results)

    # Aggregate Folder Data
    folders_data = {}
    for r in results:
        fdir = os.path.dirname(r["FilePath"])
        if fdir not in folders_data:
            folders_data[fdir] = {"count": 0, "size_mb": 0}
        folders_data[fdir]["count"] += 1
        folders_data[fdir]["size_mb"] += r["Size_MB"]

    # Prepare JSON Data
    folders_json = json.dumps(folders_data)

    # Strip user-specific data from static dump for multi-user support
    # (The frontend will hydrate this via /api/user/data)
    clean_results = []
    for r in results:
        # Create a copy to modify without affecting the passed dict references (if they are mutable)
        # Assuming r is a dict from model_dump
        r_clean = r.copy()
        # Reset user fields to defaults
        r_clean["favorite"] = False
        r_clean["hidden"] = False # aliased from vaulted
        r_clean["tags"] = []
        clean_results.append(r_clean)

    user_settings_json = json.dumps(config.settings.model_dump())

    # Logic for enabled state: Must be installed AND enabled in settings
    opt_avail_str = 'true' if config.optimizer_available else 'false'
    opt_enabled_str = 'true' if (config.optimizer_available and config.settings.enable_optimizer) else 'false'

    active_theme = CURRENT_THEME

    # 1. Prepare Header (Themed)
    header_html = render_header(
        active_theme,
        hostname=socket.gethostname().upper(),
        count=len(results),
        size_gb=f"{total_mb/1024:.1f}"
    )

    # 2. Prepare Cinema Modal (Conditional Optimize Button)
    opt_btn_html = ""
    if config.optimizer_available and config.settings.enable_optimizer:
        # Die einzige Primaeraktion der Rail — traegt als einzige den Accent.
        opt_btn_html = """
        <button class="cinema-rail-btn is-primary" onclick="cinemaOptimize()" title="Optimize Video [O]" aria-label="Optimize this video">
            <span class="cinema-rail-icon"><span class="material-icons">bolt</span></span>
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
                <span id="emptyStateIcon" class="material-icons text-[44px] text-text-muted opacity-60 mb-3">search_off</span>
                <h2 id="emptyStateTitle" class="text-[16px] font-semibold text-text-main mb-1.5">Nichts gefunden</h2>
                <p id="emptyStateHint" class="text-[13px] text-text-muted max-w-md leading-6"></p>
                <div id="emptyStateActions" class="flex flex-wrap items-center justify-center gap-2 mt-5"></div>
            </div>

            <!-- Loading Spinner -->
            <div id="loadingSentinel" class="h-24 flex items-center justify-center opacity-0 transition-opacity">
                <span class="material-icons animate-spin text-arcade-cyan text-3xl">refresh</span>
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
        window.FOLDERS_DATA = {folders_json};
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

    external_scripts = f"""
    <link rel="stylesheet" href="/static/styles.css?v={int(time.time())}">
    <link rel="stylesheet" href="/static/timeline_scrubber.css?v={int(time.time())}">
    <script src="/static/store.js?v={int(time.time())}"></script>
    <script src="/static/formatters.js?v={int(time.time())}"></script>
    <script src="/static/api.js?v={int(time.time())}"></script>
    <script src="/static/utils.js?v={int(time.time())}"></script>
    <script src="/static/treemap_layout.js?v={int(time.time())}"></script>
    <script src="/static/treemap.js?v={int(time.time())}"></script>
    <script src="/static/settings.js?v={int(time.time())}"></script>
    <script src="/static/autotag.js?v={int(time.time())}"></script>
    <script src="/static/duplicates.js?v={int(time.time())}"></script>
    <script src="/static/candidates.js?v={int(time.time())}"></script>
    <script src="/static/filter_engine.js?v={int(time.time())}"></script>
    <script src="/static/workspace.js?v={int(time.time())}"></script>
    <script src="/static/cards.js?v={int(time.time())}"></script>
    <script src="/static/batch_operations.js?v={int(time.time())}"></script>
    <script src="/static/tag_manager.js?v={int(time.time())}"></script>
    <script src="/static/folder_browser.js?v={int(time.time())}"></script>
    <script src="/static/engine.js?v={int(time.time())}"></script>
    <script src="/static/optimizer.js?v={int(time.time())}"></script>
    <script src="/static/cinema.js?v={int(time.time())}"></script>
    <script src="/static/timeline_scrubber.js?v={int(time.time())}"></script>
    <script src="/static/gif_export.js?v={int(time.time())}"></script>
    <script src="/static/collections.js?v={int(time.time())}"></script>
    <script src="/static/context_menu.js?v={int(time.time())}"></script>
    <script src="/static/shortcuts.js?v={int(time.time())}"></script>
    <script src="/static/empty_state.js?v={int(time.time())}"></script>
    """

    # Combine content using Theme-aware Base Layout
    final_html = render_base_layout(
        active_theme,
        content=main_body_html + external_scripts,
        scripts=full_scripts_block,
    )

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(final_html)
