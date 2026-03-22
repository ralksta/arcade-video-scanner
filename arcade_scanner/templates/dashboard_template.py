import os
import socket
import time
import json
from arcade_scanner.config import config
from arcade_scanner.templates.theme import CURRENT_THEME, THEMES
from arcade_scanner.templates.ui_components import (
    render_base_layout,
    render_header,
    render_navigation
)
from arcade_scanner.templates.components import (
    BASE_LAYOUT,
    HEADER_COMPONENT,
    NAVIGATION_COMPONENT,
    FILTER_BAR_COMPONENT,
    FILTER_PANEL_COMPONENT,
    TAG_MANAGER_MODAL_COMPONENT,
    COLLECTION_MODAL_COMPONENT,
    HIDDEN_PATH_MODAL_COMPONENT,
    SETUP_WIZARD_COMPONENT,
    LIST_VIEW_COMPONENT,
    OPTIMIZE_PANEL_COMPONENT,
    GIF_EXPORT_PANEL_COMPONENT,
    SETTINGS_MODAL_COMPONENT,
    CINEMA_MODAL_COMPONENT,
    DUPLICATE_CHECKER_MODAL_COMPONENT,
    TREEMAP_LEGEND_COMPONENT,
    FOLDER_BROWSER_LEGEND_COMPONENT,
    BATCH_BAR_COMPONENT,
    FOLDER_SIDEBAR_COMPONENT,
    SAVED_VIEWS_COMPONENT
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
        
    all_videos_json = json.dumps(clean_results)
    user_settings_json = json.dumps(config.settings.model_dump())
    
    # Logic for enabled state: Must be installed AND enabled in settings
    opt_avail_str = 'true' if config.optimizer_available else 'false'
    opt_enabled_str = 'true' if (config.optimizer_available and config.settings.enable_optimizer) else 'false'
    
    # Determine Active Theme
    active_theme_name = config.settings.theme
    active_theme = THEMES.get(active_theme_name, THEMES['arcade'])
    
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
        opt_btn_html = """
        <button class="flex flex-col items-center gap-1.5 transition-all group" onclick="cinemaOptimize()" title="Optimize Video">
            <div class="w-12 h-12 rounded-xl bg-arcade-cyan/15 backdrop-blur-sm flex items-center justify-center border border-arcade-cyan/40 group-hover:bg-arcade-cyan/25 group-hover:border-arcade-cyan/60 group-hover:scale-105 transition-all shadow-lg shadow-arcade-cyan/10">
                <span class="material-icons text-xl text-arcade-cyan group-hover:text-cyan-300">bolt</span>
            </div>
            <span class="text-[9px] font-semibold tracking-wider uppercase text-arcade-cyan/80 group-hover:text-arcade-cyan transition-colors">Optimize</span>
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
    <div class="flex-1 flex flex-col md:ml-64 min-h-screen bg-arcade-bg relative overflow-x-hidden max-w-full">
        {header_html}
        
        {FILTER_BAR_COMPONENT}

        {SAVED_VIEWS_COMPONENT}
        
        {TREEMAP_LEGEND_COMPONENT}

        {FOLDER_BROWSER_LEGEND_COMPONENT}

        <!-- Main Content Container with safe area padding -->
        <main class="flex-1 p-2 md:p-6 pb-[80px] md:pb-6 relative w-full overflow-x-hidden" id="mainContentArea">
            
            <!-- Video Grid -->
            <div id="videoGrid" class="responsive-grid transition-opacity duration-300 overflow-hidden">
                <!-- Injected via JS -->
            </div>
            
            <!-- List View -->
            {LIST_VIEW_COMPONENT}
            
            <!-- Treemap Container -->
            <div id="treemapContainer" class="hidden h-[70vh] w-full rounded-xl overflow-hidden border border-white/10 shadow-2xl"></div>
            
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
    <script src="/static/treemap_layout.js?v={int(time.time())}"></script>
    <script src="/static/treemap.js?v={int(time.time())}"></script>
    <script src="/static/formatters.js?v={int(time.time())}"></script>
    <script src="/static/state.js?v={int(time.time())}"></script>
    <script src="/static/settings.js?v={int(time.time())}"></script>
    <script src="/static/duplicates.js?v={int(time.time())}"></script>
    <script src="/static/engine.js?v={int(time.time())}"></script>
    <script src="/static/cinema.js?v={int(time.time())}"></script>
    <script src="/static/timeline_scrubber.js?v={int(time.time())}"></script>
    <script src="/static/gif_export.js?v={int(time.time())}"></script>
    <script src="/static/collections.js?v={int(time.time())}"></script>
    """
    
    # Combine content using Theme-aware Base Layout
    final_html = render_base_layout(
        active_theme,
        content=main_body_html + external_scripts,
        scripts=full_scripts_block,
        active_theme_name=active_theme.name
    )

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(final_html)
