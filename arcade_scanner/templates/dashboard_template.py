import os
import socket
import time
import json
from arcade_scanner.config import config
from arcade_scanner.templates.theme import CURRENT_THEME
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
    LIST_VIEW_COMPONENT,
    OPTIMIZE_PANEL_COMPONENT,
    SETTINGS_MODAL_COMPONENT,
    CINEMA_MODAL_COMPONENT,
    TREEMAP_LEGEND_COMPONENT,
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
    all_videos_json = json.dumps(results)
    user_settings_json = json.dumps(config.settings.model_dump())
    
    # Logic for enabled state: Must be installed AND enabled in settings
    opt_avail_str = 'true' if config.optimizer_available else 'false'
    opt_enabled_str = 'true' if (config.optimizer_available and config.settings.enable_optimizer) else 'false'
    
    # 1. Prepare Header (Themed)
    header_html = render_header(
        CURRENT_THEME,
        hostname=socket.gethostname().upper(),
        count=len(results),
        size_gb=f"{total_mb/1024:.1f}"
    )
    
    # 2. Prepare Cinema Modal (Conditional Optimize Button)
    opt_btn_html = ""
    if config.optimizer_available and config.settings.enable_optimizer:
        opt_btn_html = """
        <button class="flex flex-col items-center gap-1 text-arcade-cyan hover:text-cyan-300 transition-colors group" onclick="cinemaOptimize()" title="Optimize">
            <div class="w-10 h-10 rounded-full bg-arcade-cyan/20 flex items-center justify-center border border-arcade-cyan/50 group-hover:bg-arcade-cyan/40 transition-all shadow-[0_0_15px_rgba(0,255,208,0.2)]">
                <span class="material-icons text-lg">bolt</span>
            </div>
            <span class="text-[10px] tracking-widest uppercase opacity-0 group-hover:opacity-100 transition-opacity">Optimize</span>
        </button>
        """
    cinema_modal_html = CINEMA_MODAL_COMPONENT.format(opt_btn=opt_btn_html)
    
    # 3. Assemble Main Content
    # Render Navigation using Theme
    nav_html = render_navigation(CURRENT_THEME)
    
    main_body_html = f"""
    {nav_html}

    {FOLDER_SIDEBAR_COMPONENT}
    
    <!-- Desktop: Main Content Area (offset by sidebar width) -->
    <div class="flex-1 flex flex-col md:ml-64 min-h-screen bg-arcade-bg relative overflow-x-hidden max-w-full">
        {header_html}
        
        {FILTER_BAR_COMPONENT}

        {SAVED_VIEWS_COMPONENT}
        
        {TREEMAP_LEGEND_COMPONENT}
        
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
    {OPTIMIZE_PANEL_COMPONENT}
    {SETTINGS_MODAL_COMPONENT}
    {FILTER_PANEL_COMPONENT}
    {TAG_MANAGER_MODAL_COMPONENT}
    {COLLECTION_MODAL_COMPONENT}
    {BATCH_BAR_COMPONENT}
    
    <!-- Hidden frame for form submissions if needed -->
    <iframe name='h_frame' style='display:none;'></iframe>
    """
    
    # 4. Prepare Scripts
    scripts_html = f"""
        window.SERVER_PORT = {server_port};
        window.FOLDERS_DATA = {folders_json};
        window.ALL_VIDEOS = {all_videos_json};
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
    <script src="/static/treemap_layout.js?v={int(time.time())}"></script>
    <script src="/static/client.js?v={int(time.time())}"></script>
    """
    
    # Combine content using Theme-aware Base Layout
    final_html = render_base_layout(
        CURRENT_THEME,
        content=main_body_html + external_scripts,
        scripts=full_scripts_block
    )

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(final_html)
