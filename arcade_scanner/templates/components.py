# -*- coding: utf-8 -*-
# Modular HTML Components using Tailwind CSS

BASE_LAYOUT = """<!DOCTYPE html>
<html lang="de" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>Arcade Video Dashboard</title>
    
    <!-- Fonts -->
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=SF+Mono:wght@400;600&display=swap" rel="stylesheet">
    
    <!-- Tailwind CSS (CDN for Protoyping/Python-only env) -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        'arcade-bg': '#090012',
                        'arcade-purple': '#1a0530',
                        'arcade-magenta': '#8F0177',
                        'arcade-pink': '#DE1A58',
                        'arcade-gold': '#F4B342',
                        'arcade-cyan': '#00ffd0',
                        'glass': 'rgba(255, 255, 255, 0.05)',
                        'glass-border': 'rgba(255, 255, 255, 0.1)',
                    }},
                    fontFamily: {{
                        sans: ['Inter', 'sans-serif'],
                        mono: ['SF Mono', 'monospace'],
                    }},
                    boxShadow: {{
                        'neon-gold': '0 0 10px rgba(244, 179, 66, 0.3)',
                        'neon-cyan': '0 0 10px rgba(0, 255, 208, 0.3)',
                    }}
                }}
            }}
        }}
    </script>
    
    <style>
        /* Custom Arcade Effects that are hard in standard Tailwind */
        body {{
            background-color: #090012;
            -webkit-tap-highlight-color: transparent;
        }}
        
        .scrollbar-hide::-webkit-scrollbar {{
            display: none;
        }}
        .scrollbar-hide {{
            -ms-overflow-style: none;
            scrollbar-width: none;
        }}
        
        /* Glassmorphism Utilities */
        .glass-panel {{
            background: rgba(20, 20, 30, 0.6);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.08);
        }}
        
        /* JS Active State Helpers */
        #folderSidebar.active {{ transform: translateX(0); }}
        #batchBar.active {{ transform: translateY(0); }}
        #optimizePanel.active {{ transform: translateY(0); }}
        #settingsModal.active {{ display: flex !important; opacity: 1; pointer-events: auto; }}
        #cinemaModal.active {{ opacity: 1; pointer-events: auto; }}
        #cinemaInfoPanel.active {{ transform: translateX(0); }}
        
        /* Hide scrollbar for clean UI */
        .hide-scrollbar::-webkit-scrollbar {{
            display: none;
        }}
        .hide-scrollbar {{
            -ms-overflow-style: none;
            scrollbar-width: none;
        }}
        
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
            flex-direction: row !important;
            height: 140px;
            align-items: center;
        }}

        .list-view .card-media {{
            width: 240px !important;
            height: 100% !important;
            flex-shrink: 0;
            aspect-ratio: auto !important;
        }}
        
        .list-view .card-media img {{
             object-fit: cover;
        }}

        .list-view h3 {{
             font-size: 1.1rem;
             margin-bottom: 0.25rem;
        }}
    </style>
</head>
<body class="bg-arcade-bg text-white min-h-screen flex flex-col md:flex-row overflow-x-hidden antialiased selection:bg-arcade-cyan/30 selection:text-arcade-cyan">
    <div class="relative z-10 w-full flex flex-col md:flex-row">
        {content}
    </div>
    
    <!-- Scripts -->
    <script>
        {scripts}
    </script>
</body>
</html>
"""

HEADER_COMPONENT = """
<header class="fixed top-0 left-0 right-0 z-50 bg-arcade-bg/95 backdrop-blur border-b border-white/5 h-[34px] md:h-16 flex items-center justify-between px-3 md:px-6 pt-safe-top transition-all duration-300">
    <!-- Logo Area -->
    <div class="flex items-center gap-3">
        <div class="text-arcade-gold font-bold tracking-wider text-xs md:text-xl uppercase flex items-center gap-2">
            <span class="md:hidden">Arcade Scanner</span>
            <span class="hidden md:inline text-transparent bg-clip-text bg-gradient-to-r from-arcade-gold to-yellow-200 drop-shadow-sm">
                ARCADE VIDEO SCANNER
            </span>
        </div>
    </div>

    <!-- Desktop Stats (Hidden on Mobile) -->
    <div class="hidden md:flex items-center gap-4 text-xs font-mono text-gray-400 bg-black/40 px-3 py-1.5 rounded-lg border border-white/5">
        <div class="flex items-center gap-2">
            <span class="material-icons text-[14px] text-arcade-gold">dns</span>
            <span>{hostname}</span>
        </div>
        <span class="text-white/20">|</span>
        <div class="flex items-center gap-2">
            <span class="material-icons text-[14px] text-arcade-cyan">movie</span>
            <span id="header-count">{count}</span> Videos
        </div>
        <span class="text-white/20">|</span>
        <div class="flex items-center gap-2">
            <span class="material-icons text-[14px] text-arcade-pink">save</span>
            <span id="header-size">{size_gb} GB</span>
        </div>
    </div>
    
    <!-- Mobile Actions (Settings) -->
    <button onclick="openSettings()" class="md:hidden p-1 text-gray-400 hover:text-white">
        <span class="material-icons text-[18px]">settings</span>
    </button>
</header>
<!-- Spacer for Fixed Header -->
<div class="h-[34px] md:h-16 w-full"></div>
"""

NAVIGATION_COMPONENT = """
<!-- Desktop Sidebar (Hidden on Mobile) -->
<nav class="hidden md:flex flex-col w-64 fixed left-0 top-16 bottom-0 bg-arcade-bg/50 border-r border-white/5 p-4 gap-1 z-[100]">
    <div class="text-[11px] font-bold text-gray-500 uppercase tracking-widest mb-2 px-3">Workspace</div>
    
    <button id="m-lobby" onclick="setWorkspaceMode('lobby')" class="nav-item active group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-300 hover:bg-white/5 transition-all">
        <div class="nav-indicator absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-arcade-cyan rounded-r transition-opacity"></div>
        <span class="material-icons text-[20px] text-arcade-cyan">dashboard</span>
        <span class="font-medium group-[.active]:text-white">Lobby</span>
        <span id="count-lobby" class="ml-auto text-[11px] text-gray-500 font-mono"></span>
    </button>

    <button id="m-favorites" onclick="setWorkspaceMode('favorites')" class="nav-item group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-300 hover:bg-white/5 transition-all">
        <div class="nav-indicator absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-arcade-gold rounded-r opacity-0 transition-opacity"></div>
        <span class="material-icons text-[20px] group-hover:text-arcade-gold group-[.active]:text-arcade-gold">star</span>
        <span class="font-medium group-[.active]:text-white">Favoriten</span>
        <span id="count-favorites" class="ml-auto text-[11px] text-gray-500 font-mono"></span>
    </button>
    
    <button id="m-optimized" onclick="setWorkspaceMode('optimized')" class="nav-item group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-300 hover:bg-white/5 transition-all">
        <div class="nav-indicator absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
        <span class="material-icons text-[20px] group-hover:text-arcade-cyan group-[.active]:text-arcade-cyan">offline_bolt</span>
        <span class="font-medium group-[.active]:text-white">Review</span>
        <span id="count-review" class="ml-auto text-[11px] text-gray-500 font-mono"></span>
    </button>

    <button id="m-vault" onclick="setWorkspaceMode('vault')" class="nav-item group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-300 hover:bg-white/5 transition-all">
        <div class="nav-indicator absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-arcade-magenta rounded-r opacity-0 transition-opacity"></div>
        <span class="material-icons text-[20px] group-hover:text-arcade-magenta group-[.active]:text-arcade-magenta">archive</span>
        <span class="font-medium group-[.active]:text-white">Vault</span>
        <span id="count-vault" class="ml-auto text-[11px] text-gray-500 font-mono"></span>
    </button>
    
    <div class="mt-auto border-t border-white/5 pt-3">
        <button onclick="openSettings()" class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-colors">
            <span class="material-icons text-[20px]">settings</span>
            <span>Settings</span>
        </button>
    </div>
    
</nav>

<!-- Mobile Bottom Tab Bar (Fixed Bottom) -->
<nav class="md:hidden fixed bottom-0 left-0 right-0 h-[60px] pb-safe-bottom bg-[#090012]/95 backdrop-blur-xl border-t border-white/10 z-50 flex justify-around items-center px-2">
    <button onclick="setWorkspaceMode('lobby')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-gray-500 hover:text-arcade-cyan active:text-arcade-cyan transition-colors">
        <span class="material-icons text-[24px]">dashboard</span>
        <span class="text-[9px] font-medium">Lobby</span>
    </button>
    
    <button onclick="setWorkspaceMode('favorites')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-gray-500 hover:text-arcade-gold active:text-arcade-gold transition-colors">
        <span class="material-icons text-[24px]">star</span>
        <span class="text-[9px] font-medium">Favs</span>
    </button>
    
    <button onclick="setWorkspaceMode('optimized')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-gray-500 hover:text-arcade-cyan active:text-arcade-cyan transition-colors">
        <span class="material-icons text-[24px]">offline_bolt</span>
        <span class="text-[9px] font-medium">Review</span>
    </button>
    
    <button onclick="setWorkspaceMode('vault')" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-gray-500 hover:text-arcade-magenta active:text-arcade-magenta transition-colors">
        <span class="material-icons text-[24px]">archive</span>
        <span class="text-[9px] font-medium">Vault</span>
    </button>
    
    <button onclick="document.getElementById('mobileSearchInput').focus()" class="flex flex-col items-center justify-center p-1 w-12 gap-1 text-gray-500 hover:text-white transition-colors">
        <span class="material-icons text-[24px]">search</span>
        <span class="text-[9px] font-medium">Search</span>
    </button>
</nav>
"""

VIDEO_CARD_COMPONENT = """
<!-- Video Card Template -->
<div class="video-card group relative bg-surface rounded-xl overflow-hidden border border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-neon-cyan/20 w-full flex flex-col">
    <!-- Thumbnail Area -->
    <div class="relative w-full aspect-video bg-black overflow-hidden">
        <img src="{thumbnail_url}" alt="{title}" loading="lazy" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105">
        
        <!-- Duration Badge -->
        <span class="absolute bottom-1 right-1 bg-black/80 px-1.5 py-0.5 rounded text-[10px] font-mono text-white font-bold backdrop-blur-sm">
            {duration}
        </span>
        
        <!-- Status Badges -->
        <div class="absolute top-1 left-1 flex flex-wrap gap-1">
            {badges}
        </div>
    </div>
    
    <!-- Content Area (Mobile: Minimal, Desktop: Detailed) -->
    <div class="p-2 md:p-3 flex flex-col gap-1">
        <div class="flex justify-between items-start gap-2">
            <h3 class="text-sm font-medium text-gray-200 leading-tight line-clamp-2 md:line-clamp-1 group-hover:text-arcade-cyan transition-colors" title="{title}">
                {title}
            </h3>
            <!-- Menu Button (Desktop only hover) -->
            <button class="text-gray-500 hover:text-white md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                <span class="material-icons text-[16px]">more_vert</span>
            </button>
        </div>
        
        <!-- Metadata -->
        <div class="flex items-center gap-2 text-[10px] text-gray-500 font-mono mt-1">
            <span class="bg-white/5 px-1.5 py-0.5 rounded">{resolution}</span>
            <span>{size}</span>
            <span class="hidden md:inline">• {codec}</span>
        </div>
    </div>
</div>
"""
OPTIMIZE_PANEL_COMPONENT = """
<!-- Optimize Panel (Tailwind) -->
<div id="optimizePanel" class="fixed bottom-0 left-0 right-0 bg-[#101018]/95 backdrop-blur-xl border-t border-white/10 p-6 translate-y-[110%] transition-transform duration-300 z-[10100] shadow-[0_-10px_40px_rgba(0,0,0,0.5)] flex flex-col gap-4">
    <!-- Active state class 'translate-y-0' handled by JS -->
    
    <!-- Audio Row -->
    <div class="flex items-center gap-4 flex-wrap">
        <div class="text-xs text-gray-400 font-bold uppercase tracking-widest w-[60px]">Audio</div>
        <div class="flex bg-white/5 rounded-lg p-0.5">
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-white bg-white/10 shadow-sm transition-all" id="optAudioEnhanced" onclick="setOptAudio('enhanced')">Enhanced</div>
            <div class="px-4 py-1.5 text-sm cursor-pointer rounded-md text-gray-400 hover:text-white transition-all" id="optAudioStandard" onclick="setOptAudio('standard')">Standard</div>
        </div>
        <div class="flex-1"></div>
        <span class="text-xs text-gray-500" id="optAudioDesc">Smart normalization & noise reduction</span>
    </div>
    
    <!-- Trim Row -->
    <div class="flex items-center gap-4 flex-wrap">
        <div class="text-xs text-gray-400 font-bold uppercase tracking-widest w-[60px]">Trim</div>
        <input type="text" class="bg-black/30 border border-white/10 text-white px-3 py-1.5 rounded-md font-mono text-center w-[100px] focus:border-arcade-cyan/50 focus:outline-none" id="optTrimStart" placeholder="00:00:00">
        
        <button class="w-[30px] h-[30px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition-colors" onclick="setTrimFromHead('start')" title="Set Start">
            <span class="material-icons text-[16px]">arrow_downward</span>
        </button>
        
        <div class="w-[10px] text-center text-gray-600">-</div>
        
        <input type="text" class="bg-black/30 border border-white/10 text-white px-3 py-1.5 rounded-md font-mono text-center w-[100px] focus:border-arcade-cyan/50 focus:outline-none" id="optTrimEnd" placeholder="END">
        
        <button class="w-[30px] h-[30px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition-colors" onclick="setTrimFromHead('end')" title="Set End">
            <span class="material-icons text-[16px]">arrow_downward</span>
        </button>
        
        <button class="w-[30px] h-[30px] flex items-center justify-center border border-white/10 rounded-md text-gray-400 hover:bg-white/10 hover:text-white transition-colors ml-2" onclick="clearTrim()" title="Clear">
            <span class="material-icons text-[16px]">close</span>
        </button>
    </div>
    
    <!-- Actions -->
    <div class="flex items-center gap-4 mt-2">
        <button class="flex-1 py-2.5 rounded-lg font-bold cursor-pointer text-gray-400 bg-white/5 hover:bg-white/10 hover:text-white transition-all max-w-[120px]" onclick="closeOptimize()">Cancel</button>
        
        <button class="flex-1 py-2.5 rounded-lg font-bold cursor-pointer text-white bg-arcade-cyan/20 text-arcade-cyan border border-arcade-cyan/50 shadow-[0_0_15px_rgba(0,255,208,0.2)] hover:bg-arcade-cyan hover:text-black transition-all flex items-center justify-center gap-2" onclick="triggerOptimization()">
            <span class="material-icons">bolt</span> START OPTIMIZATION
        </button>
    </div>
</div>
"""

CINEMA_MODAL_COMPONENT = """
<!-- Cinema Modal (Tailwind) -->
<div id="cinemaModal" class="fixed inset-0 z-[10000] bg-black opacity-0 pointer-events-none transition-opacity duration-500 flex flex-col justify-center items-center">
    <!-- Active class 'opacity-100 pointer-events-auto' toggled by JS -->
    
    <button class="absolute top-4 right-4 text-white/50 hover:text-white z-50 p-2" onclick="closeCinema()">
        <span class="material-icons text-4xl">close</span>
    </button>
    
    <h2 id="cinemaTitle" class="absolute top-6 left-0 right-0 text-center text-white/80 font-light tracking-[4px] text-lg uppercase pointer-events-none z-40 drop-shadow-lg">Movie Player</h2>
    
    <video id="cinemaVideo" controls preload="metadata" class="max-w-full max-h-[80vh] w-auto h-auto shadow-[0_0_50px_rgba(0,0,0,0.8)] rounded-lg outline-none"></video>
    
    <div id="cinemaInfoPanel" class="absolute top-20 right-4 w-80 bg-black/80 backdrop-blur-md border border-white/10 rounded-lg p-4 transform translate-x-[120%] transition-transform duration-300 z-40 text-sm text-gray-300">
        <div class="flex items-center gap-2 mb-3 text-white font-bold border-b border-white/10 pb-2">
            <span class="material-icons text-sm">info</span>
            <span>Technical Details</span>
        </div>
        <div id="cinemaInfoContent" class="space-y-2 text-xs font-mono"></div>
    </div>
    
    <div class="absolute bottom-8 flex gap-4 z-40">
        <button class="flex flex-col items-center gap-1 text-gray-400 hover:text-white transition-colors group" onclick="toggleCinemaInfo()" title="Info">
            <div class="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center group-hover:bg-white/20 transition-all">
                <span class="material-icons text-lg">info</span>
            </div>
            <span class="text-[10px] tracking-widest uppercase opacity-0 group-hover:opacity-100 transition-opacity">Info</span>
        </button>
        
        <button class="flex flex-col items-center gap-1 text-arcade-gold hover:text-yellow-300 transition-colors group" onclick="cinemaFavorite()" title="Favorite">
            <div class="w-10 h-10 rounded-full bg-arcade-gold/20 flex items-center justify-center border border-arcade-gold/50 group-hover:bg-arcade-gold/40 transition-all">
                <span class="material-icons text-lg">star</span>
            </div>
            <span class="text-[10px] tracking-widest uppercase opacity-0 group-hover:opacity-100 transition-opacity">Fav</span>
        </button>
        
        <button class="flex flex-col items-center gap-1 text-arcade-magenta hover:text-pink-400 transition-colors group" onclick="cinemaVault()" title="Vault">
            <div class="w-10 h-10 rounded-full bg-arcade-magenta/20 flex items-center justify-center border border-arcade-magenta/50 group-hover:bg-arcade-magenta/40 transition-all">
                <span class="material-icons text-lg">archive</span>
            </div>
            <span class="text-[10px] tracking-widest uppercase opacity-0 group-hover:opacity-100 transition-opacity">Vault</span>
        </button>
        
        <button class="flex flex-col items-center gap-1 text-gray-400 hover:text-white transition-colors group" onclick="cinemaLocate()" title="Locate">
            <div class="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center group-hover:bg-white/20 transition-all">
                <span class="material-icons text-lg">folder_special</span>
            </div>
            <span class="text-[10px] tracking-widest uppercase opacity-0 group-hover:opacity-100 transition-opacity">Locate</span>
        </button>
        
        {opt_btn}
    </div>
</div>
"""

TREEMAP_LEGEND_COMPONENT = """
<!-- Treemap Legend -->
<div id="treemapLegend" class="hidden w-full bg-arcade-bg/95 border-b border-white/5 py-2">
    <div class="w-full px-4 flex items-center justify-between">
        <button id="treemapBackBtn" class="hidden items-center gap-2 text-sm text-gray-400 hover:text-white" onclick="treemapZoomOut()">
            <span class="material-icons text-base">arrow_back</span> BACK
        </button>
        
        <div class="flex items-center gap-4 text-xs font-mono text-gray-500">
            <span class="legend-title text-white font-bold tracking-wider">STORAGE MAP</span>
            <span class="legend-hint text-arcade-cyan/70"></span>
            <div class="flex items-center gap-2 border-l border-white/10 pl-4">
                <span class="w-2 h-2 rounded-full bg-arcade-pink"></span> HIGH
                <span class="w-2 h-2 rounded-full bg-arcade-cyan"></span> OPTIMIZED
            </div>
        </div>
        
        <!-- Log Scale Toggle -->
        <label class="flex items-center gap-2 cursor-pointer group">
            <div class="relative w-8 h-4 bg-gray-700 rounded-full transition-colors group-hover:bg-gray-600">
                <input type="checkbox" id="treemapLogToggle" onchange="toggleTreemapScale()" class="peer sr-only">
                <div class="absolute w-3 h-3 bg-white rounded-full left-0.5 top-0.5 peer-checked:translate-x-4 transition-transform"></div>
            </div>
            <span class="text-[10px] text-gray-500 font-bold">LOG SCALE</span>
        </label>
    </div>
</div>
"""


BATCH_BAR_COMPONENT = """
<!-- Batch Selection Bar (Floating) -->
<div id="batchBar" class="fixed bottom-20 md:bottom-8 left-1/2 -translate-x-1/2 z-50 bg-[#1a1a24] border border-white/10 rounded-full shadow-2xl px-6 py-3 flex items-center gap-4 transition-transform duration-300 translate-y-32">
    <!-- Active class 'translate-y-0' handled by JS (display handling needs update to transformation) -->
    
    <span class="text-sm font-bold text-white whitespace-nowrap"><span id="batchCount" class="text-arcade-gold">0</span> Selected</span>
    
    <div class="h-6 w-px bg-white/10"></div>
    
    <button class="flex items-center gap-2 text-xs font-bold text-arcade-cyan hover:text-white transition-colors" onclick="triggerBatchCompress()">
        <span class="material-icons text-base">bolt</span> OPTIMIZE
    </button>
    
    <button class="flex items-center gap-2 text-xs font-bold text-arcade-gold hover:text-white transition-colors" onclick="triggerBatchFavorite(true)">
        <span class="material-icons text-base">star</span> FAV
    </button>
    
    <button class="flex items-center gap-2 text-xs font-bold text-arcade-magenta hover:text-white transition-colors" onclick="triggerBatchHide(true)">
        <span class="material-icons text-base">archive</span> VAULT
    </button>
    
    <div class="h-6 w-px bg-white/10"></div>
    
    <button class="text-gray-500 hover:text-white transition-colors" onclick="clearSelection()">
        <span class="material-icons text-base">close</span>
    </button>
</div>
"""

FOLDER_SIDEBAR_COMPONENT = """
<!-- Folder Sidebar (Off-Canvas) -->
<div id="folderSidebar" class="fixed inset-y-0 left-0 w-80 bg-[#101018]/95 backdrop-blur-xl border-r border-white/10 transform -translate-x-full transition-transform duration-300 z-[60] flex flex-col pt-safe-top">
    <!-- Active class 'translate-x-0' handled by JS -->
    
    <div class="p-4 border-b border-white/10 flex items-center justify-between">
        <h3 class="font-bold text-white tracking-wider">FOLDERS</h3>
        <button class="text-gray-400 hover:text-white" onclick="toggleFolderSidebar()">
            <span class="material-icons">close</span>
        </button>
    </div>
    
    <div id="folderList" class="flex-1 overflow-y-auto p-2 space-y-1">
        <!-- Injected by JS -->
    </div>
</div>
"""

SAVED_VIEWS_COMPONENT = """
<!-- Saved Views Chips -->
<div id="savedViewsContainer" class="hidden md:flex flex-wrap gap-2 px-6 pb-2 items-center">
    <!-- Injected by JS -->
</div>
"""


SETTINGS_MODAL_COMPONENT = """
<div id="settingsModal" class="hidden fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm opacity-0 transition-opacity duration-300 flex items-center justify-center p-4 md:p-8">
    <div class="settings-container w-full h-full md:w-2/3 md:h-auto md:max-w-5xl md:max-h-[85vh] bg-[#1a1a24] rounded-2xl shadow-2xl flex flex-col md:flex-row overflow-hidden border border-white/10 transform scale-95 transition-transform duration-300">
        
        <!-- Sidebar Navigation -->
        <aside class="w-full md:w-56 bg-[#12121a] border-b md:border-b-0 md:border-r border-white/5 flex md:flex-col shrink-0">
            <div class="p-4 md:p-5 flex items-center gap-3 text-white border-b border-white/5 md:border-none">
                <span class="material-icons text-arcade-gold text-xl">settings</span>
                <h2 class="font-semibold tracking-wide text-lg">Settings</h2>
            </div>
            
            <nav class="flex md:flex-col overflow-x-auto md:overflow-visible p-2 md:px-3 md:py-2 gap-1">
                <button class="settings-nav-item active flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="scanning">
                    <span class="material-icons text-lg">folder_open</span>
                    <span class="hidden md:inline">Scanning</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="performance">
                    <span class="material-icons text-lg">speed</span>
                    <span class="hidden md:inline">Performance</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="interface">
                    <span class="material-icons text-lg">palette</span>
                    <span class="hidden md:inline">Interface</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
                
                <div class="w-px h-6 md:w-full md:h-px bg-white/10 md:my-2 mx-2 md:mx-0"></div>
                
                <button class="settings-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/5 hover:text-white transition-all whitespace-nowrap relative" data-section="storage">
                    <span class="material-icons text-lg">storage</span>
                    <span class="hidden md:inline">Storage</span>
                    <div class="active-indicator absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-6 bg-arcade-cyan rounded-r opacity-0 transition-opacity"></div>
                </button>
            </nav>
        </aside>
        
        <!-- Main Content -->
        <main class="flex-1 flex flex-col min-w-0 bg-[#1a1a24]">
            
            <!-- Header -->
            <header class="p-5 md:p-6 border-b border-white/5 flex justify-between items-center">
                <div>
                    <h1 id="section-title" class="text-xl md:text-2xl font-bold text-white">Scanning</h1>
                    <p id="section-subtitle" class="text-sm text-gray-500 mt-0.5">Configure video library scanning</p>
                </div>
                <button class="text-gray-500 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg" title="Close (ESC)" onclick="closeSettings()">
                    <span class="material-icons">close</span>
                </button>
            </header>
            
            <!-- Scrollable Body -->
            <div class="settings-body flex-1 overflow-y-auto p-5 md:p-6 space-y-6">
                
                <!-- SCANNING SECTION -->
                <div class="content-section active space-y-6" id="content-scanning">
                    <section class="space-y-3">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">folder</span>
                                Scan Directories
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Paths to scan for video files. One per line.</p>
                        </div>
                        <textarea class="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-sm text-gray-300 font-mono focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all resize-none placeholder-gray-600" id="settingsTargets" placeholder="/Users/username/Videos" rows="4" oninput="markSettingsUnsaved()"></textarea>
                        
                        <div class="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 flex gap-3 text-sm text-blue-300">
                             <span class="material-icons text-blue-400 text-lg">info</span>
                             <div>
                                 <strong>Default:</strong> Home directory
                                 <span id="defaultTargetsHint" class="opacity-70 text-xs block mt-0.5"></span>
                             </div>
                        </div>
                    </section>
                    
                    <section class="space-y-3">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-gray-400">block</span>
                                System Exclusions
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Default paths excluded from scanning.</p>
                        </div>
                        <div id="defaultExclusionsContainer" class="bg-black/30 rounded-xl p-4 border border-white/5 space-y-2 max-h-48 overflow-y-auto">
                            <!-- Populated by JS -->
                        </div>
                    </section>
                    
                    <section class="space-y-3">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-pink">remove_circle</span>
                                Custom Exclusions
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Additional paths to exclude.</p>
                        </div>
                        <textarea class="w-full bg-black/40 border border-white/10 rounded-xl p-4 text-sm text-gray-300 font-mono focus:border-arcade-cyan/50 focus:outline-none focus:ring-1 focus:ring-arcade-cyan/30 transition-all resize-none placeholder-gray-600" id="settingsExcludes" placeholder="/Volumes/Backup" rows="2" oninput="markSettingsUnsaved()"></textarea>
                    </section>
                </div>
                
                <!-- PERFORMANCE SECTION -->
                <div class="content-section hidden space-y-6" id="content-performance">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-gold">straighten</span>
                                File Size Threshold
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Ignore videos smaller than this size.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Minimum Size</div>
                                <div class="text-xs text-gray-500 mt-0.5">Files below this are skipped</div>
                            </div>
                            <div class="flex items-center gap-2 bg-black/50 rounded-lg border border-white/10 p-1">
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsMinSize', -10)">
                                    <span class="material-icons text-lg">remove</span>
                                </button>
                                <div class="flex items-center gap-1">
                                    <input type="number" id="settingsMinSize" value="100" min="1" class="bg-transparent text-white font-mono text-center w-14 focus:outline-none" oninput="markSettingsUnsaved()">
                                    <span class="text-gray-500 text-sm">MB</span>
                                </div>
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsMinSize', 10)">
                                    <span class="material-icons text-lg">add</span>
                                </button>
                            </div>
                        </div>
                    </section>
                    
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-pink">local_fire_department</span>
                                Bitrate Classification
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Videos above this are marked as HIGH bitrate.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Bitrate Threshold</div>
                                <div class="text-xs text-gray-500 mt-0.5">Default: 15,000 kbps</div>
                            </div>
                            <div class="flex items-center gap-2 bg-black/50 rounded-lg border border-white/10 p-1">
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsBitrate', -1000)">
                                    <span class="material-icons text-lg">remove</span>
                                </button>
                                <div class="flex items-center gap-1">
                                    <input type="number" id="settingsBitrate" value="15000" min="1000" class="bg-transparent text-white font-mono text-center w-20 focus:outline-none" oninput="markSettingsUnsaved()">
                                    <span class="text-gray-500 text-sm">kbps</span>
                                </div>
                                <button class="w-9 h-9 rounded-md hover:bg-white/10 text-gray-400 hover:text-white flex items-center justify-center transition-colors" onclick="adjustSettingsNumber('settingsBitrate', 1000)">
                                    <span class="material-icons text-lg">add</span>
                                </button>
                            </div>
                        </div>
                    </section>
                </div>
                
                <!-- INTERFACE SECTION -->
                <div class="content-section hidden space-y-6" id="content-interface">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-magenta">auto_awesome</span>
                                Visual Features
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Customize the dashboard experience.</p>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Fun Facts</div>
                                <div class="text-xs text-gray-500 mt-0.5">Educational overlays during optimization</div>
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="settingsFunFacts" class="sr-only peer" onchange="markSettingsUnsaved()">
                                <div class="w-12 h-7 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-arcade-cyan/30 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-6 after:w-6 after:shadow-md after:transition-all peer-checked:bg-arcade-gold"></div>
                            </label>
                        </div>
                        
                        <div class="bg-black/30 rounded-xl p-4 border border-white/5 flex items-center justify-between gap-4">
                            <div class="flex-1">
                                <div class="text-white font-medium text-sm">Video Optimizer</div>
                                <div class="text-xs text-gray-500 mt-0.5">Enable video compression features <span class="text-amber-400">(restart required)</span></div>
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="settingsOptimizer" class="sr-only peer" checked onchange="markSettingsUnsaved()">
                                <div class="w-12 h-7 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-arcade-cyan/30 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-6 after:w-6 after:shadow-md after:transition-all peer-checked:bg-arcade-gold"></div>
                            </label>
                        </div>
                    </section>
                </div>
                
                <!-- STORAGE SECTION -->
                <div class="content-section hidden space-y-6" id="content-storage">
                    <section class="space-y-4">
                        <div>
                            <h3 class="text-base font-medium text-white flex items-center gap-2">
                                <span class="material-icons text-lg text-arcade-cyan">pie_chart</span>
                                Cache Statistics
                            </h3>
                            <p class="text-sm text-gray-500 mt-1">Disk space used by generated assets.</p>
                        </div>
                        
                        <div class="grid grid-cols-3 gap-3">
                            <div class="bg-black/40 p-4 rounded-xl border border-white/5 flex flex-col items-center gap-2">
                                <span class="material-icons text-gray-500 text-2xl">image</span>
                                <span class="text-xs text-gray-500 uppercase tracking-wider">Thumbnails</span>
                                <span class="text-lg font-mono text-white" id="statThumbnails">—</span>
                            </div>
                            <div class="bg-black/40 p-4 rounded-xl border border-white/5 flex flex-col items-center gap-2">
                                <span class="material-icons text-gray-500 text-2xl">movie</span>
                                <span class="text-xs text-gray-500 uppercase tracking-wider">Previews</span>
                                <span class="text-lg font-mono text-white" id="statPreviews">—</span>
                            </div>
                            <div class="bg-black/40 p-4 rounded-xl border border-arcade-cyan/30 flex flex-col items-center gap-2">
                                <span class="material-icons text-arcade-cyan text-2xl">storage</span>
                                <span class="text-xs text-gray-500 uppercase tracking-wider">Total</span>
                                <span class="text-lg font-mono text-arcade-cyan" id="statTotal">—</span>
                            </div>
                        </div>
                        
                        <div class="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 flex gap-3 text-sm text-amber-200">
                            <span class="material-icons text-amber-400 text-lg">info</span>
                            <div>Cache changes require an app restart.</div>
                        </div>
                    </section>
                </div>
            </div>
            
            <!-- Footer -->
            <footer class="p-4 border-t border-white/5 bg-[#12121a] flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <div class="flex items-center gap-2 text-amber-400 text-xs font-medium opacity-0 transition-opacity" id="unsavedIndicator">
                        <span class="material-icons text-sm">warning</span>
                        Unsaved changes
                    </div>
                </div>
                <div class="flex gap-3">
                    <button class="px-4 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-all" onclick="closeSettings()">Cancel</button>
                    <button id="saveSettingsBtn" class="px-5 py-2 rounded-lg text-sm font-bold text-black bg-arcade-cyan hover:bg-cyan-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-arcade-cyan/20 transition-all flex items-center gap-2" onclick="saveSettings()">
                        <span class="material-icons text-lg save-icon">save</span>
                        <svg class="animate-spin h-4 w-4 save-spinner hidden" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span class="save-text">Save</span>
                    </button>
                </div>
            </footer>
            
        </main>
    </div>
</div>

<!-- Settings Toast Notification -->
<div id="settingsToast" class="fixed bottom-6 right-6 z-[200] transform translate-y-20 opacity-0 transition-all duration-300 pointer-events-none">
    <div class="bg-green-500/95 backdrop-blur text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3">
        <span class="material-icons">check_circle</span>
        <span class="font-medium">Settings saved</span>
    </div>
</div>
"""


FILTER_BAR_COMPONENT = """
<!-- Filter Bar (Sticky on Desktop, Scrollable Row on Mobile) -->
<div class="workspace-indicator sticky top-[34px] md:top-16 z-30 bg-arcade-bg/95 backdrop-blur border-b-2 px-2 md:px-6 py-2 flex flex-col md:flex-row gap-3 md:items-center justify-between transition-all duration-300 overflow-x-hidden" style="border-color: var(--ws-accent, var(--cyan)); background: var(--ws-bg-tint, transparent);">
    <!-- Mobile Search (Full Width) -->
    <div class="w-full md:w-80 lg:w-96 relative flex-shrink min-w-0">
        <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-[18px]">search</span>
        <input type="text" id="mobileSearchInput" oninput="onSearchInput()" placeholder="Suchen..." class="w-full bg-white/5 border border-white/10 rounded-full pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-arcade-cyan/50 focus:bg-white/10 transition-all placeholder-gray-600">
    </div>
    
    <!-- Filter Chips (Horizontal Scroll on Mobile) -->
    <div class="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 scrollbar-hide flex-shrink-0">
        <!-- Status Codec Dropdowns converted to modern Menus/Chips -->
        <select id="statusSelect" onchange="setFilter(this.value)" class="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-arcade-cyan/50 appearance-none min-w-[100px]">
            <option value="all">All Videos</option>
            <option value="new">New</option>
            <option value="optimized_files">Optimized File</option>
        </select>
        
        <select id="codecSelect" onchange="setCodecFilter(this.value)" class="bg-white/5 border border-white/10 rounded-full px-4 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-arcade-cyan/50 appearance-none min-w-[100px]">
            <option value="all">All Codecs</option>
            <option value="hevc">HEVC / H.265</option>
            <option value="h264">H.264</option>
        </select>

        <!-- Sort Dropdown with Icon -->
        <div class="relative group">
            <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-[16px] pointer-events-none group-hover:text-arcade-cyan transition-colors">sort</span>
            <select id="sortSelect" onchange="setSort(this.value)" class="bg-white/5 border border-white/10 rounded-full pl-9 pr-4 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-arcade-cyan/50 appearance-none min-w-[150px] cursor-pointer hover:bg-white/10 transition-colors">
                <option value="bitrate">Bitrate (High &rarr; Low)</option>
                <option value="size">Size (Largest)</option>
                <option value="date">Date (Newest)</option>
            </select>
        </div>
        
        <!-- View Toggles -->
        <div class="hidden md:flex items-center bg-white/5 rounded-lg p-0.5 ml-2 border border-white/5">
            <button onclick="setLayout('grid')" class="p-1.5 rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors" title="Grid View">
                <span class="material-icons text-[18px]">grid_view</span>
            </button>
            <button onclick="setLayout('list')" class="p-1.5 rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors" title="List View">
                 <span class="material-icons text-[18px]">view_list</span>
            </button>
            <button onclick="setLayout('treemap')" class="p-1.5 rounded hover:bg-white/10 text-gray-400 hover:text-white transition-colors" title="Tree View">
                <span class="material-icons text-[18px]">account_tree</span>
            </button>
        </div>
        
        <button id="refreshBtn" onclick="rescanLibrary()" class="bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white p-2 rounded-full transition-colors flex items-center justify-center flex-shrink-0" title="Rescan Library">
            <span class="material-icons text-[18px]">refresh</span>
        </button>
    </div>
</div>
"""

LIST_VIEW_COMPONENT = """
<!-- List View Template (Hidden by default) -->
<div id="listViewContainer" class="hidden w-full overflow-x-auto">
    <table class="w-full text-left border-collapse">
        <thead>
            <tr class="text-xs text-gray-500 border-b border-white/10">
                <th class="p-3 font-medium">File</th>
                <th class="p-3 font-medium">Size</th>
                <th class="p-3 font-medium hidden md:table-cell">Duration</th>
                <th class="p-3 font-medium hidden md:table-cell">Codec</th>
                <th class="p-3 font-medium text-right">Action</th>
            </tr>
        </thead>
        <tbody id="listTableBody" class="text-sm text-gray-300">
            <!-- Rows injected by JS -->
        </tbody>
    </table>
</div>
"""

