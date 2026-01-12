# -*- coding: utf-8 -*-
from arcade_scanner.templates.theme import BaseTheme, render_theme_css

def render_base_layout(theme: BaseTheme, content: str, scripts: str, active_theme_name: str = "arcade") -> str:
    """
    Renders the main HTML shell, injecting theme CSS variables and config.
    """
    return f"""<!DOCTYPE html>
<html lang="en" class="dark" data-theme="{active_theme_name}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Arcade Video Dashboard</title>
    
    <!-- Fonts -->
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=SF+Mono:wght@400;600&display=swap" rel="stylesheet">
    
    <!-- Theme CSS Variables -->
    {render_theme_css()}

    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    {theme.render_tailwind_config()}
    
    <style>        
        .scrollbar-hide::-webkit-scrollbar {{ display: none; }}
        .scrollbar-hide {{ -ms-overflow-style: none; scrollbar-width: none; }}
        
        .glass-panel {{
            background: var(--surface-glass);
            backdrop-filter: blur(20px);
            border: 1px solid var(--surface-border);
        }}
        
        /* JS Active State Helpers */
        #folderSidebar.active {{ transform: translateX(0); }}
        #batchBar.active {{ transform: translateY(0); }}
        #optimizePanel.active {{ transform: translateY(0); }}
        #settingsModal.active {{ display: flex !important; opacity: 1; pointer-events: auto; }}
        #cinemaModal.active {{ opacity: 1; pointer-events: auto; }}
        #cinemaInfoPanel.active {{ transform: translateX(0); }}
        
        /* Treemap Tooltip */
        #treemapTooltip {{
            position: fixed;
            z-index: 1000;
            background: rgba(16, 16, 24, 0.95);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
            padding: 12px;
            border-radius: 8px;
            pointer-events: none;
            font-family: 'Inter', sans-serif;
            font-size: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            transition: opacity 0.1s;
        }}
        
        .responsive-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 1rem;
            justify-content: start;
        }}

        /* List View Overrides */
        .list-view {{
            grid-template-columns: 1fr !important;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .list-view .video-card-container {{
             max-width: 100%;
        }}
    </style>
</head>
<body class="{theme.app_bg}">
    {content}
    {scripts}
</body>
</html>
"""

def render_header(theme: BaseTheme, hostname: str, count: int, size_gb: str) -> str:
    return f"""
<header class="{theme.header_container}">
    <!-- Logo Area -->
    <div class="flex items-center gap-3">
        <div class="text-arcade-gold font-bold tracking-wider text-xs md:text-xl uppercase flex items-center gap-2">
            <span class="md:hidden">Arcade Scanner</span>
            <span class="hidden md:inline text-transparent bg-clip-text bg-gradient-to-r from-arcade-gold to-yellow-500 dark:to-yellow-200 drop-shadow-sm">
                ARCADE VIDEO SCANNER
            </span>
        </div>
    </div>

    <!-- Desktop Stats -->
    <div class="hidden md:flex items-center gap-4 text-xs font-mono {theme.text_secondary} bg-black/5 dark:bg-black/40 px-3 py-1.5 rounded-lg border border-black/5 dark:border-white/5">
        <div class="flex items-center gap-2">
            <span class="material-icons text-[14px] text-arcade-gold">dns</span>
            <span>{hostname}</span>
        </div>
        <span class="opacity-20">|</span>
        <div class="flex items-center gap-2">
            <span class="material-icons text-[14px] text-arcade-cyan">movie</span>
            <span id="header-count">{count}</span> Videos
        </div>
        <span class="opacity-20">|</span>
        <div class="flex items-center gap-2">
            <span class="material-icons text-[14px] text-arcade-pink">save</span>
            <span id="header-size">{size_gb} GB</span>
        </div>
        <span class="opacity-20">|</span>
        <button onclick="toggleTheme()" class="hover:bg-black/5 dark:hover:bg-white/10 p-1.5 rounded-lg transition-colors" title="Switch Theme">
            <span class="material-icons text-[18px]" id="themeIcon">light_mode</span>
        </button>
        <span class="opacity-20">|</span>
        <button onclick="logout()" class="hover:bg-red-500/10 p-1.5 rounded-lg transition-colors text-gray-500 hover:text-red-400" title="Logout">
            <span class="material-icons text-[18px]">logout</span>
        </button>
    </div>
    
    <!-- Mobile Actions -->
    <button onclick="openSettings()" class="md:hidden p-1 {theme.text_secondary} hover:text-black dark:hover:text-white">
        <span class="material-icons text-[18px]">settings</span>
    </button>
</header>
<!-- Spacer -->
<div class="h-[34px] md:h-16 w-full"></div>
"""

def render_navigation(theme: BaseTheme) -> str:
    """
    Renders the sidebar navigation using theme-aware button styles.
    """
    
    def nav_btn(id_val, onclick, icon, label, color_cls, active=False):
        # We manually construct specific arcade indicators because they use specific colors (gold, cyan, magenta)
        # In a fully generic theme, these colors would be abstractions like 'brand-primary'
        # But for now, we map them.
        
        # Indicator line color class mapping
        bg_color = f"bg-{color_cls}" if "arcade" in color_cls else "bg-purple-500"
        text_color = f"text-{color_cls}" if "arcade" in color_cls else "text-purple-400"
        
        return f"""
    <button id="{id_val}" onclick="{onclick}" class="nav-item {('active' if active else '')} {theme.button_nav(active)} group">
        <div class="nav-indicator absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 {bg_color} rounded-r {'transition-opacity' if active else 'opacity-0 transition-opacity'}"></div>
        <span class="material-icons text-[20px] {text_color} group-hover:{text_color}">{icon}</span>
        <span class="font-medium group-[.active]:text-black dark:group-[.active]:text-white">{label}</span>
        <span id="count-{id_val.replace('m-', '')}" class="ml-auto text-[11px] {theme.text_secondary} font-mono"></span>
    </button>
        """

    return f"""
<nav class="{theme.sidebar_container}">
    <div class="text-[11px] font-bold {theme.text_secondary} uppercase tracking-widest mb-2 px-3">Workspace</div>
    
    {nav_btn("m-lobby", "setWorkspaceMode('lobby')", "dashboard", "Lobby", "arcade-cyan", active=True)}
    {nav_btn("m-favorites", "setWorkspaceMode('favorites')", "star", "Favoriten", "arcade-gold")}
    {nav_btn("m-optimized", "setWorkspaceMode('optimized')", "offline_bolt", "Review", "arcade-cyan")}
    {nav_btn("m-vault", "setWorkspaceMode('vault')", "archive", "Vault", "arcade-magenta")}
    
    <!-- Smart Collections Section -->
    <div class="mt-4 border-t border-black/5 dark:border-white/5 pt-3">
        <div class="flex items-center justify-between px-3 mb-2">
            <span class="text-[11px] font-bold {theme.text_secondary} uppercase tracking-widest">Collections</span>
            <button onclick="openCollectionModal()" class="{theme.text_secondary} hover:text-arcade-cyan transition-colors" title="New Collection">
                <span class="material-icons text-[16px]">add</span>
            </button>
        </div>
        <div id="collectionsNav" class="space-y-0.5"></div>
    </div>
    
    <div class="mt-auto border-t border-black/5 dark:border-white/5 pt-3">
        <button onclick="openSettings()" class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/5 hover:text-black dark:hover:text-white transition-colors">
            <span class="material-icons text-[20px]">settings</span>
            <span>Settings</span>
        </button>
    </div>
</nav>

<!-- Mobile Nav (Simplified, preserving heavy static styles for now or could reuse theme vars) -->
<nav class="md:hidden fixed bottom-0 left-0 right-0 h-[60px] pb-safe-bottom bg-arcade-bg/95 backdrop-blur-xl border-t border-black/5 dark:border-white/10 z-50 flex justify-around items-center px-2">
    <button onclick="setWorkspaceMode('lobby')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 {theme.text_secondary} hover:text-arcade-cyan active:text-arcade-cyan transition-colors">
        <span class="material-icons text-[24px]">dashboard</span>
        <span class="text-[9px] font-medium">Lobby</span>
    </button>
    <button onclick="setWorkspaceMode('favorites')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 {theme.text_secondary} hover:text-arcade-gold active:text-arcade-gold transition-colors">
        <span class="material-icons text-[24px]">star</span>
        <span class="text-[9px] font-medium">Favs</span>
    </button>
    <button onclick="setWorkspaceMode('optimized')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 {theme.text_secondary} hover:text-arcade-cyan active:text-arcade-cyan transition-colors">
        <span class="material-icons text-[24px]">offline_bolt</span>
        <span class="text-[9px] font-medium">Review</span>
    </button>
     <button onclick="setWorkspaceMode('vault')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 {theme.text_secondary} hover:text-arcade-magenta active:text-arcade-magenta transition-colors">
        <span class="material-icons text-[24px]">archive</span>
        <span class="text-[9px] font-medium">Vault</span>
    </button>
    <button onclick="document.getElementById('mobileSearchInput').focus()" class="flex flex-col items-center justify-center p-1 w-12 gap-1 {theme.text_secondary} hover:text-black dark:hover:text-white transition-colors">
        <span class="material-icons text-[24px]">search</span>
        <span class="text-[9px] font-medium">Search</span>
    </button>
</nav>
"""
