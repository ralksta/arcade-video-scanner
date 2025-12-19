import os
from arcade_scanner.app_config import HIDDEN_DATA_DIR, PORT, OPTIMIZER_SCRIPT, OPTIMIZER_AVAILABLE

def generate_html_report(results, report_file):
    total_mb = sum(r["Size_MB"] for r in results)
    
    # Aggregate Folder Data
    folders_data = {}
    for r in results:
        fdir = os.path.dirname(r["FilePath"])
        if fdir not in folders_data:
            folders_data[fdir] = {"count": 0, "size_mb": 0}
        folders_data[fdir]["count"] += 1
        folders_data[fdir]["size_mb"] += r["Size_MB"]
    
    import json
    folders_json = json.dumps(folders_data)
    all_videos_json = json.dumps(results)
    
    html_content = f"""<!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>Arcade Video Dashboard</title>
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
        <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body data-port="{PORT}">
        <canvas id="starfield"></canvas>
        <div class="scanlines"></div>
        
        <header class="arcade-header">
            <div class="grid-bg"></div>
            <div class="logo-container" onclick="resetDashboard()" style="cursor:pointer">
                <div class="glitch-wrapper">
                    <h1 class="video-scanner-text">ARCADE VIDEO SCANNER</h1>
                </div>
            </div>
            <div class="stats-display">
                STATUS: READY // 
                TOTAL: <span id="count-total">{len(results)}</span> VIDEOS // 
                VOLUME: <span id="size-total">{total_mb/1024:.1f} GB</span>
            </div>
        </header>

        <div class="top-bar">
            <div class="container controls">
                <input type="text" id="searchBar" placeholder="Suchen..." oninput="onSearchInput()">
                
                <div style="flex-shrink:0; height:24px; width:1px; background:rgba(255,255,255,0.1); margin:0 8px;"></div>
                
                <select id="statusSelect" onchange="setFilter(this.value)">
                    <option value="all">ALL VIDEOS</option>
                    <option value="HIGH">🚨 HIGH BITRATE</option>
                    <option value="OK">✅ OPTIMIZED</option>
                </select>
                
                <select id="codecSelect" onchange="setCodecFilter(this.value)">
                    <option value="all">ALLE CODECS</option>
                    <option value="h264">H.264 / AVC</option>
                    <option value="hevc">H.265 / HEVC</option>
                </select>

                <select id="sortSelect" onchange="setSort(this.value)">
                    <option value="bitrate">SORT: BITRATE</option>
                    <option value="size">SORT: DATEIGRÖSSE</option>
                    <option value="name">SORT: NAME</option>
                </select>

                <div style="flex-grow:1;"></div>
                
                <div style="width:1px; height:24px; background:rgba(255,255,255,0.1); margin:0 8px;"></div>

                <button class="filter-btn action-btn" id="toggleView" onclick="toggleLayout()"><span class="material-icons">view_list</span></button>
                
                <a href="javascript:location.reload()" class="filter-btn action-btn" title="Neu laden"><span class="material-icons">refresh</span></a>

                <button class="filter-btn action-btn" id="folderBtn" onclick="toggleFolderSidebar()" title="Ordner Explorer">
                    <span class="material-icons">folder</span>
                </button>

                <button class="filter-btn action-btn" id="settingsBtn" onclick="openSettings()" title="Einstellungen">
                    <span class="material-icons">settings</span>
                </button>
            </div>
        </div>

        <div class="workspace-bar">
            <div class="container">
                <div class="segmented-control">
                    <button class="segment-btn active" id="m-lobby" onclick="setWorkspaceMode('lobby')">LOBBY</button>
                    <button class="segment-btn" id="m-favorites" onclick="setWorkspaceMode('favorites')">⭐ FAVORITEN</button>
                    <button class="segment-btn" id="m-vault" onclick="setWorkspaceMode('vault')">VAULT</button>
                </div>
            </div>
        </div>

        <div id="treemapLegend" class="treemap-legend" style="display: none;">
            <div class="container">
                <div class="legend-content">
                    <button id="treemapBackBtn" class="filter-btn" onclick="treemapZoomOut()" style="display: none; margin-right: 12px;">
                        <span class="material-icons">arrow_back</span> ZURÜCK
                    </button>
                    <span class="legend-title">SPEICHER TREEMAP</span>
                    <div class="legend-items">
                        <span class="legend-item"><span class="legend-color high"></span> HIGH BITRATE</span>
                        <span class="legend-item"><span class="legend-color ok"></span> OPTIMIZED</span>
                    </div>
                    <span class="legend-hint">Klicken zum Abspielen • Hover für Details</span>
                </div>
            </div>
        </div>

        <div id="folderSidebar" class="folder-sidebar">
            <div class="sidebar-header">
                <h3>ORDNER</h3>
                <span class="material-icons" style="cursor:pointer" onclick="toggleFolderSidebar()">close</span>
            </div>
            <div id="folderList" class="folder-list"></div>
        </div>

        <div class="container">
            <div id="videoGrid"></div>
            <div id="treemapContainer" style="display: none;"></div>
            <div id="loadingSentinel" style="height: 100px; display: flex; align-items: center; justify-content: center; opacity: 0;">
                 <span class="material-icons" style="animation: spin 1s linear infinite;">refresh</span>
            </div>
        </div>
        
        <div id="cinemaModal">
            <span class="cinema-close" onclick="closeCinema()">&times;</span>
            <span id="cinemaTitle" class="cinema-title">MOVIE PLAYER</span>
            <video id="cinemaVideo" controls preload="metadata"></video>
        </div>
        
        <div id="batchBar" class="selection-bar">
            <span><strong id="batchCount">0</strong> Videos ausgewählt</span>
            {f'''<button class="filter-btn active" onclick="triggerBatchCompress()">
                <span class="material-icons">bolt</span> OPTIMIEREN
            </button>''' if OPTIMIZER_AVAILABLE else ""}
            <button class="filter-btn" onclick="triggerBatchFavorite(true)" style="background:var(--gold); color:#000; border-color:var(--gold);">
                <span class="material-icons">star</span> FAVORISIEREN
            </button>
            <button class="filter-btn" onclick="triggerBatchHide(true)" style="background:var(--deep-purple); border-color:var(--glass-border);">
                <span class="material-icons">archive</span> VAULT
            </button>
            <button class="filter-btn" onclick="clearSelection()" style="background:transparent; border-color:white;">
                Abbrechen
            </button>
        </div>
        
        <div id="settingsModal" class="settings-modal">
            <div class="settings-content">
                <div class="settings-header">
                    <h2><span class="material-icons">settings</span> Einstellungen</h2>
                    <span class="material-icons settings-close" onclick="closeSettings()">close</span>
                </div>
                
                <div class="settings-body">
                    <div class="settings-section">
                        <label>📁 Scan-Ordner (einer pro Zeile)</label>
                        <textarea id="settingsTargets" rows="5" placeholder="C:\\Videos\nD:\\Media"></textarea>
                        <div class="settings-hint" id="defaultTargetsHint"></div>
                    </div>
                    
                    <div class="settings-section">
                        <label>🛡️ Standard-Ausschlüsse</label>
                        <div class="settings-hint">Diese Ordner werden standardmäßig ignoriert. Deaktivieren Sie Checkboxen, um sie zu scannen.</div>
                        <div id="defaultExclusionsContainer" class="exclusions-list"></div>
                    </div>
                    
                    <div class="settings-section">
                        <label>🚫 Zusätzliche Ausschlüsse (einer pro Zeile)</label>
                        <textarea id="settingsExcludes" rows="3" placeholder="Eigene Ausschlüsse..."></textarea>
                    </div>
                    
                    <div class="settings-section settings-row">
                        <div>
                            <label>Mindestgröße (MB)</label>
                            <input type="number" id="settingsMinSize" min="1" value="100">
                        </div>
                        <div>
                            <label>Bitrate-Schwellwert (kbps)</label>
                            <input type="number" id="settingsBitrate" min="1000" value="15000">
                        </div>
                    </div>
                    
                    <div class="settings-warning">
                        <span class="material-icons">warning</span>
                        Änderungen erfordern einen Neustart der App
                    </div>
                </div>
                
                <div class="settings-footer">
                    <button class="filter-btn" onclick="closeSettings()">Abbrechen</button>
                    <button class="filter-btn active" onclick="saveSettings()">
                        <span class="material-icons">save</span> Speichern
                    </button>
                </div>
            </div>
        </div>
        
        <iframe name='h_frame' style='display:none;'></iframe>

        <script>
            window.SERVER_PORT = {PORT};
            window.FOLDERS_DATA = {folders_json};
            window.ALL_VIDEOS = {all_videos_json};
            window.OPTIMIZER_AVAILABLE = {'true' if OPTIMIZER_AVAILABLE else 'false'};
        </script>
        <script src="/static/treemap_layout.js"></script>
        <script src="/static/client.js"></script>
    </body>
    </html>"""

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)
