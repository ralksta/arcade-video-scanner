# -*- coding: utf-8 -*-
from arcade_scanner.templates.theme import BaseTheme, render_theme_css


def render_base_layout(theme: BaseTheme, content: str, scripts: str) -> str:
    """
    Renders the main HTML shell, injecting design tokens and Tailwind config.
    """
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Arcade Scanner</title>

    <!-- Fonts: Inter (UI) + Material Icons. Daten laufen im System-Mono-Stack. -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

    <!-- Design Tokens -->
    {render_theme_css()}

    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    {theme.render_tailwind_config()}

    <style>
        .scrollbar-hide::-webkit-scrollbar {{ display: none; }}
        .scrollbar-hide {{ -ms-overflow-style: none; scrollbar-width: none; }}

        .glass-panel {{
            background: var(--ds-surface);
            border: 1px solid var(--ds-hairline);
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
            background: var(--ds-surface-2);
            border: 1px solid var(--ds-hairline-strong);
            color: var(--ds-text);
            padding: 12px;
            border-radius: 8px;
            pointer-events: none;
            font-family: var(--ds-font-sans);
            font-size: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            transition: opacity 0.1s;
        }}

        .responsive-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(var(--grid-min-width, 240px), 1fr));
            gap: 14px;
            justify-content: start;
        }}

        /* List View Overrides */
        .list-view {{
            grid-template-columns: 1fr !important;
            display: flex;
            flex-direction: column;
            gap: 8px;
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
    """App-Topbar: Accent-Dot + Wortmarke links, Mono-Stat-Cluster rechts."""
    return f"""
<header class="{theme.header_container}">
    <!-- Wortmarke -->
    <div class="flex items-center gap-2.5 min-w-0">
        <span class="w-[7px] h-[7px] rounded-[2px] bg-accent flex-shrink-0"></span>
        <span class="font-extrabold text-[14px] tracking-tight text-text-main truncate">Arcade Scanner</span>
    </div>

    <!-- Stat-Cluster -->
    <div class="hidden md:flex items-center gap-3 text-[12px] font-mono text-label">
        <div class="flex items-center gap-1.5">
            <span class="material-icons text-[15px] text-text-muted">dns</span>
            <span>{hostname}</span>
        </div>
        <span class="opacity-30">|</span>
        <div class="flex items-center gap-1.5">
            <span class="material-icons text-[15px] text-text-muted">movie</span>
            <span id="header-video-count">...</span> videos
        </div>
        <span class="opacity-30" id="image-separator" style="display:none;">|</span>
        <div class="flex items-center gap-1.5" id="image-count-section" style="display:none;">
            <span class="material-icons text-[15px] text-text-muted">image</span>
            <span id="header-image-count">...</span> images
        </div>
        <span class="opacity-30">|</span>
        <div class="flex items-center gap-1.5">
            <span class="material-icons text-[15px] text-text-muted">save</span>
            <span id="header-size">...</span>
        </div>
        <span class="opacity-30">|</span>
        <button onclick="toggleTheme()" class="p-1 rounded-md text-text-muted hover:text-text-main transition-colors" title="Light / Dark">
            <span class="material-icons text-[18px]" id="themeIcon">light_mode</span>
        </button>
        <button onclick="logout()" class="p-1 rounded-md text-text-muted hover:text-danger transition-colors" title="Logout">
            <span class="material-icons text-[18px]">logout</span>
        </button>
    </div>

    <!-- Mobile Actions -->
    <button onclick="openSettings()" class="md:hidden p-1 text-text-muted hover:text-text-main">
        <span class="material-icons text-[18px]">settings</span>
    </button>
</header>
<!-- Spacer -->
<div class="h-[46px] md:h-[52px] w-full"></div>
"""


def render_navigation(theme: BaseTheme) -> str:
    """
    Sidebar-Navigation: 200px breit, Section-Labels, Nav-Rows mit
    3px-Accent-Indikator links und Mono-Count rechts.
    """

    def nav_btn(id_val, onclick, icon, label, active=False):
        indicator_state = "" if active else "opacity-0"
        icon_color = "text-accent-tint" if active else "text-text-muted"
        return f"""
    <button id="{id_val}" onclick="{onclick}" class="nav-item {('active' if active else '')} {theme.button_nav(active)}">
        <span class="nav-indicator absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-[15px] bg-accent rounded-r-[2px] transition-opacity {indicator_state}"></span>
        <span class="material-icons text-[19px] {icon_color} transition-colors">{icon}</span>
        <span class="truncate">{label}</span>
        <span id="count-{id_val.replace('m-', '')}" class="ml-auto text-[11px] text-text-muted font-mono"></span>
    </button>
        """

    return f"""
<nav class="{theme.sidebar_container}">
    <div class="ds-eyebrow !text-[10px] px-2.5 mb-2">Workspace</div>

    {nav_btn("m-lobby", "setWorkspaceMode('lobby')", "dashboard", "Lobby", active=True)}
    {nav_btn("m-favorites", "setWorkspaceMode('favorites')", "star", "Favoriten")}
    {nav_btn("m-optimized", "setWorkspaceMode('optimized')", "offline_bolt", "Review")}
    {nav_btn("m-vault", "setWorkspaceMode('vault')", "archive", "Vault")}
    {nav_btn("m-duplicates", "setWorkspaceMode('duplicates')", "content_copy", "Duplicates")}
    {nav_btn("m-candidates", "setWorkspaceMode('candidates')", "savings", "Kandidaten")}

    <!-- Smart Collections Section -->
    <div class="mt-6 pt-4 border-t border-line/60">
        <div class="flex items-center justify-between px-2.5 mb-2">
            <span class="ds-eyebrow !text-[10px]">Collections</span>
            <button onclick="openCollectionModal()" class="text-text-muted hover:text-accent-tint transition-colors" title="New Collection">
                <span class="material-icons text-[16px]">add</span>
            </button>
        </div>
        <div id="collectionsNav" class="space-y-0.5"></div>
    </div>

    <div class="mt-auto pt-4 border-t border-line/60">
        <button onclick="openSettings()" class="w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-md text-[13px] text-label hover:bg-[var(--ds-fill-soft)] hover:text-text-main transition-colors">
            <span class="material-icons text-[19px] text-text-muted">settings</span>
            <span>Settings</span>
        </button>
    </div>
</nav>

<!-- Mobile Nav -->
<nav class="md:hidden fixed bottom-0 left-0 right-0 h-[60px] pb-safe-bottom bg-header border-t border-line/60 z-50 flex justify-around items-center px-2">
    <button onclick="setWorkspaceMode('lobby')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-text-muted active:text-accent-tint transition-colors">
        <span class="material-icons text-[22px]">dashboard</span>
        <span class="text-[9px] font-medium">Lobby</span>
    </button>
    <button onclick="setWorkspaceMode('favorites')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-text-muted active:text-accent-tint transition-colors">
        <span class="material-icons text-[22px]">star</span>
        <span class="text-[9px] font-medium">Favs</span>
    </button>
    <button onclick="setWorkspaceMode('optimized')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-text-muted active:text-accent-tint transition-colors">
        <span class="material-icons text-[22px]">offline_bolt</span>
        <span class="text-[9px] font-medium">Review</span>
    </button>
     <button onclick="setWorkspaceMode('vault')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-text-muted active:text-accent-tint transition-colors">
        <span class="material-icons text-[22px]">archive</span>
        <span class="text-[9px] font-medium">Vault</span>
    </button>
    <button onclick="document.getElementById('mobileSearchInput').focus()" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-text-muted active:text-accent-tint transition-colors">
        <span class="material-icons text-[22px]">search</span>
        <span class="text-[9px] font-medium">Search</span>
    </button>
</nav>
"""
