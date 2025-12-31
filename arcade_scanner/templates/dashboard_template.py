import os
import socket
import time
from arcade_scanner.config import config

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
    
    import json
    
    folders_json = json.dumps(folders_data)
    all_videos_json = json.dumps(results)
    user_settings_json = json.dumps(config.settings.model_dump())
    
    # Logic for enabled state: Must be installed AND enabled in settings
    opt_avail_str = 'true' if config.optimizer_available else 'false'
    opt_enabled_str = 'true' if (config.optimizer_available and config.settings.enable_optimizer) else 'false'
    
    html_content = f"""<!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Arcade Video Dashboard</title>
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="/static/styles.css?v={int(time.time()) + 10}">
        <link rel="stylesheet" href="/static/settings.css?v={int(time.time()) + 20}">
        <script>
            window.userSettings = {user_settings_json};
            window.OPTIMIZER_AVAILABLE = {opt_avail_str};
            window.ENABLE_OPTIMIZER = {opt_enabled_str};
            window.FOLDERS_DATA = {folders_json};
        </script>
        <style>
            /* OPTIMIZE PANEL */
            #optimizePanel {{
                position: absolute;
                bottom: 0px; 
                left: 0; 
                right: 0;
                background: rgba(16, 16, 24, 0.95);
                backdrop-filter: blur(10px);
                border-top: 1px solid rgba(255,255,255,0.1);
                padding: 16px 24px 24px 24px;
                transform: translateY(110%);
                transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
                z-index: 10100;
                box-shadow: 0 -10px 40px rgba(0,0,0,0.5);
                display: flex;
                flex-direction: column;
                gap: 16px;
            }}
            .switch input {{ opacity: 0; width: 0; height: 0; }}
            .switch input:checked + .slider {{ background-color: #2196F3; }}
            .switch input:focus + .slider {{ box-shadow: 0 0 1px #2196F3; }}
            .switch input:checked ~ .slider-knob {{ transform: translateX(14px); }}
            #optimizePanel.active {{
            #optimizePanel.active {{
                transform: translateY(0);
            }}
            .opt-row {{
                display: flex;
                align-items: center;
                gap: 16px;
                flex-wrap: wrap;
            }}
            .opt-label {{
                font-size: 0.8rem;
                color: #888;
                font-weight: 600;
                width: 60px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .opt-segmented {{
                display: flex;
                background: rgba(255,255,255,0.05);
                border-radius: 8px;
                padding: 2px;
            }}
            .opt-option {{
                padding: 6px 16px;
                font-size: 0.9rem;
                cursor: pointer;
                border-radius: 6px;
                color: #aaa;
                transition: all 0.2s;
            }}
            .opt-option.selected {{
                background: #333;
                color: #fff;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
            .opt-input {{
                background: rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.1);
                color: #fff;
                padding: 6px 12px;
                border-radius: 6px;
                font-family: monospace;
                width: 100px;
                text-align: center;
            }}
            .opt-btn-small {{
                background: transparent;
                border: 1px solid rgba(255,255,255,0.1);
                color: #ccc;
                width: 30px;
                height: 30px;
                border-radius: 6px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .opt-btn-small:hover {{
                background: rgba(255,255,255,0.1);
                color: #fff;
            }}
            .opt-action-btn {{
                flex: 1;
                padding: 10px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                cursor: pointer;
                font-size: 1rem;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }}
        </style>
    </head>
    <body data-port="{server_port}">
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
                SERVER: {socket.gethostname().upper()} // 
                TOTAL: <span id="count-total">{len(results)}</span> VIDEOS // 
                VOLUME: <span id="size-total">{total_mb/1024:.1f} GB</span>
            </div>
        </header>

        <div class="top-bar">
            <div class="container controls">
                <input type="text" id="searchBar" placeholder="Suchen..." oninput="onSearchInput()">
                
                <button class="view-chip add-view-btn" id="saveViewBtn" onclick="saveCurrentView()" title="Ansicht speichern" style="height:48px; padding:0 16px; border-radius:12px; margin-right:8px; display:none;">
                    <span class="material-icons">bookmark_add</span>
                </button>

                <button class="filter-btn" id="selectAllBtn" onclick="selectAllVisible()" title="Alle auswählen" style="display:none;">
                    <span class="material-icons">done_all</span>
                </button>
                
                <div style="flex-shrink:0; height:24px; width:1px; background:rgba(255,255,255,0.1); margin:0 8px;"></div>
                
                <select id="statusSelect" onchange="setFilter(this.value)">
                    <option value="all">ALL VIDEOS</option>
                    <option value="HIGH">🚨 HIGH BITRATE</option>
                    <option value="OK">✅ NORMAL BITRATE</option>
                    <option value="optimized_files">⚡ OPTIMIZED</option>
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
                    <option value="date">SORT: DATUM (NEU)</option>
                </select>

                <div style="flex-grow:1;"></div>
                
                <div style="width:1px; height:24px; background:rgba(255,255,255,0.1); margin:0 8px;"></div>

                <button class="filter-btn action-btn" id="toggleView" onclick="toggleLayout()"><span class="material-icons">view_list</span></button>
                
                <button class="filter-btn action-btn" id="refreshBtn" onclick="rescanLibrary()" title="Bibliothek neu scannen"><span class="material-icons">refresh</span></button>

                <button class="filter-btn action-btn" id="folderBtn" onclick="toggleFolderSidebar()" title="Ordner Explorer">
                    <span class="material-icons">folder</span>
                </button>

                <button class="filter-btn action-btn" id="settingsBtn" onclick="openSettings()" title="Einstellungen">
                    <span class="material-icons">settings</span>
                </button>
            </div>
            
            <!-- SAVED VIEWS CHIPS -->
            <div class="container" id="savedViewsContainer" style="display:flex; gap:8px; padding:0 24px 12px 24px; flex-wrap:wrap; align-items:center;">
                <!-- Chips will be injected here -->
            </div>
        </div>

        <div class="workspace-bar">
            <div class="container">
                <div class="segmented-control">
                    <button class="segment-btn active" id="m-lobby" onclick="setWorkspaceMode('lobby')">LOBBY</button>
                    <button class="segment-btn" id="m-favorites" onclick="setWorkspaceMode('favorites')">⭐ FAVORITEN</button>
                    <button class="segment-btn" id="m-optimized" onclick="setWorkspaceMode('optimized')">⚡ REVIEW</button>
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
                        <!-- LOG SCALE TOGGLE -->
                        <div style="display:flex; align-items:center; margin-left:16px; gap:8px;">
                             <label class="switch" style="position:relative; display:inline-block; width:34px; height:20px;">
                                <input type="checkbox" id="treemapLogToggle" onchange="toggleTreemapScale()">
                                <span class="slider round" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#ccc; transition:.4s; border-radius:34px;"></span>
                                <span class="slider-knob" style="position:absolute; content:''; height:14px; width:14px; left:3px; bottom:3px; background-color:white; transition:.4s; border-radius:50%;"></span>
                             </label>
                             <span style="font-size:0.8rem; color:#aaa;">LOG SCALE</span>
                        </div>
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
            
            <div id="cinemaInfoPanel" class="cinema-info-panel">
                <div class="info-header">
                    <span class="material-icons">info</span>
                    <span>Technical Details</span>
                </div>
                <div id="cinemaInfoContent" class="info-content"></div>
            </div>
            
            <div class="cinema-actions">
                <button class="cinema-action-btn" onclick="toggleCinemaInfo()" title="Technical Details">
                    <span class="material-icons">info</span>
                    <span>INFO</span>
                </button>
                <button class="cinema-action-btn" onclick="cinemaFavorite()" title="Add to Favorites" style="background:var(--gold); color:#000; border-color:var(--gold);">
                    <span class="material-icons">star</span>
                    <span>FAVORITE</span>
                </button>
                <button class="cinema-action-btn" onclick="cinemaVault()" title="Move to Vault">
                    <span class="material-icons">archive</span>
                    <span>VAULT</span>
                </button>
                <button class="cinema-action-btn" onclick="cinemaLocate()" title="Locate in Filesystem">
                    <span class="material-icons">folder_special</span>
                    <span>LOCATE</span>
                </button>
                {f'''<button class="cinema-action-btn" onclick="cinemaOptimize()" title="Optimize Video">
                    <span class="material-icons">bolt</span>
                    <span>OPTIMIZE</span>
                </button>''' if (config.optimizer_available and config.settings.enable_optimizer) else ""}
            </div>
            
             <div id="optimizePanel">
                <div class="opt-row">
                    <div class="opt-label">AUDIO</div>
                    <div class="opt-segmented">
                        <div class="opt-option selected" id="optAudioEnhanced" onclick="setOptAudio('enhanced')">Enhanced</div>
                        <div class="opt-option" id="optAudioStandard" onclick="setOptAudio('standard')">Standard</div>
                    </div>
                    <div style="flex:1;"></div>
                    <span style="font-size:0.8rem; color:#666;" id="optAudioDesc">Smart normalization & noise reduction</span>
                </div>
                
                <div class="opt-row">
                    <div class="opt-label">TRIM</div>
                    <input type="text" class="opt-input" id="optTrimStart" placeholder="00:00:00">
                    <button class="opt-btn-small" onclick="setTrimFromHead('start')" title="Set Start to Current Pos"><span class="material-icons" style="font-size:16px;">arrow_downward</span></button>
                    <div style="width:10px; text-align:center; color:#555;">-</div>
                    <input type="text" class="opt-input" id="optTrimEnd" placeholder="END">
                    <button class="opt-btn-small" onclick="setTrimFromHead('end')" title="Set End to Current Pos"><span class="material-icons" style="font-size:16px;">arrow_downward</span></button>
                    <button class="opt-btn-small" onclick="clearTrim()" title="Clear Trim"><span class="material-icons" style="font-size:16px;">close</span></button>
                </div>
                
                <div class="opt-row" style="margin-top:8px;">
                    <button class="opt-action-btn" onclick="closeOptimize()" style="background:rgba(255,255,255,0.05); color:#ccc; max-width:100px;">Cancel</button>
                    <button class="opt-action-btn" onclick="triggerOptimization()" style="background:var(--neon-blue); color:#fff; box-shadow: 0 0 15px rgba(0,243,255,0.3);">
                        <span class="material-icons">bolt</span> START OPTIMIZATION
                    </button>
                </div>
            </div>
        </div>
        
        <div id="batchBar" class="selection-bar">
            <span><strong id="batchCount">0</strong> Videos ausgewählt</span>
            {f'''<button class="filter-btn active" onclick="triggerBatchCompress()">
                <span class="material-icons">bolt</span> OPTIMIEREN
            </button>''' if config.optimizer_available else ""}
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
        
        
        <div id="settingsModal" class="settings-modal redesign">
            <div class="settings-container">
                
                <!-- Sidebar Navigation -->
                <aside class="settings-sidebar">
                    <div class="settings-logo">
                        <span class="material-icons">settings</span>
                        <h2>Settings</h2>
                    </div>
                    
                    <nav class="settings-nav">
                        <div class="nav-item active" data-section="scanning">
                            <span class="material-icons">folder_open</span>
                            <span>Scanning</span>
                        </div>
                        <div class="nav-item" data-section="performance">
                            <span class="material-icons">speed</span>
                            <span>Performance</span>
                        </div>
                        <div class="nav-item" data-section="interface">
                            <span class="material-icons">palette</span>
                            <span>Interface</span>
                        </div>
                        
                        <div class="nav-divider"></div>
                        
                        <div class="nav-item" data-section="storage">
                            <span class="material-icons">storage</span>
                            <span>Storage</span>
                        </div>
                    </nav>
                </aside>
                
                <!-- Main Content -->
                <main class="settings-main">
                    
                    <!-- Header -->
                    <header class="settings-header">
                        <div class="settings-title">
                            <h1 id="section-title">Scanning</h1>
                            <p id="section-subtitle">Configure video library scanning behavior</p>
                        </div>
                        <div class="settings-header-actions">
                            <button class="btn-icon" title="Close Settings" onclick="closeSettings()">
                                <span class="material-icons">close</span>
                            </button>
                        </div>
                    </header>
                    
                    <!-- Scrollable Body -->
                    <div class="settings-body">
                        
                        <!-- SCANNING SECTION -->
                        <div class="content-section active" id="content-scanning">
                            
                            <!-- Scan Targets -->
                            <section class="settings-section">
                                <div class="section-header">
                                    <h3 class="section-title">📁 Scan Directories</h3>
                                    <p class="section-description">Add directories that should be scanned for video files. One path per line.</p>
                                </div>
                                
                                <textarea class="textarea-field" id="settingsTargets" placeholder="/Users/username/Videos&#10;/Volumes/Media/Movies" rows="5"></textarea>
                                
                                <div class="alert alert-info">
                                    <span class="material-icons">info</span>
                                    <div>
                                        <strong>Default:</strong> System home directory
                                        <br><span id="defaultTargetsHint" style="opacity: 0.7;"></span>
                                    </div>
                                </div>
                            </section>
                            
                            <!-- Default Exclusions -->
                            <section class="settings-section">
                                <div class="section-header">
                                    <h3 class="section-title">🛡️ System Exclusions</h3>
                                    <p class="section-description">Default paths that are automatically excluded. Uncheck to include them in the scan.</p>
                                </div>
                                
                                <div class="settings-group">
                                    <div class="checkbox-list" id="defaultExclusionsContainer">
                                        <!-- Dynamically populated -->
                                    </div>
                                </div>
                            </section>
                            
                            <!-- Custom Exclusions -->
                            <section class="settings-section">
                                <div class="section-header">
                                    <h3 class="section-title">🚫 Custom Exclusions</h3>
                                    <p class="section-description">Additional paths to exclude from scanning. One path per line.</p>
                                </div>
                                
                                <textarea class="textarea-field" id="settingsExcludes" placeholder="/Users/username/Private&#10;/Volumes/Backup" rows="3"></textarea>
                            </section>
                        </div>
                        
                        <!-- PERFORMANCE SECTION -->
                        <div class="content-section" id="content-performance">
                            
                            <section class="settings-section">
                                <div class="section-header">
                                    <h3 class="section-title">File Size Threshold</h3>
                                    <p class="section-description">Ignore videos smaller than this size (in MB).</p>
                                </div>
                                
                                <div class="settings-group">
                                    <div class="settings-item">
                                        <div class="settings-item-label">
                                            <div class="settings-item-title">Minimum File Size</div>
                                            <div class="settings-item-description">Files below this size will be excluded from the scan</div>
                                        </div>
                                        <div class="number-input-wrapper">
                                            <button class="number-stepper" onclick="adjustSettingsNumber('settingsMinSize', -10)">
                                                <span class="material-icons">remove</span>
                                            </button>
                                            <input type="number" id="settingsMinSize" value="100" min="1">
                                            <button class="number-stepper" onclick="adjustSettingsNumber('settingsMinSize', 10)">
                                                <span class="material-icons">add</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </section>
                            
                            <section class="settings-section">
                                <div class="section-header">
                                    <h3 class="section-title">Bitrate Classification</h3>
                                    <p class="section-description">Videos exceeding this bitrate will be marked as HIGH.</p>
                                </div>
                                
                                <div class="settings-group">
                                    <div class="settings-item">
                                        <div class="settings-item-label">
                                            <div class="settings-item-title">Bitrate Threshold</div>
                                            <div class="settings-item-description">Threshold in kbps (1000-50000)</div>
                                        </div>
                                        <div class="number-input-wrapper">
                                            <button class="number-stepper" onclick="adjustSettingsNumber('settingsBitrate', -1000)">
                                                <span class="material-icons">remove</span>
                                            </button>
                                            <input type="number" id="settingsBitrate" value="15000" min="1000" max="50000">
                                            <button class="number-stepper" onclick="adjustSettingsNumber('settingsBitrate', 1000)">
                                                <span class="material-icons">add</span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </section>
                        </div>
                        
                        <!-- INTERFACE SECTION -->
                        <div class="content-section" id="content-interface">
                            
                            <section class="settings-section">
                                <div class="section-header">
                                    <h3 class="section-title">🎨 Visual Features</h3>
                                    <p class="section-description">Customize the dashboard appearance and behavior.</p>
                                </div>
                                
                                <div class="settings-group">
                                    <div class="settings-item">
                                        <div class="settings-item-label">
                                            <div class="settings-item-title">Fun Facts</div>
                                            <div class="settings-item-description">Show educational overlays during video optimization</div>
                                        </div>
                                        <label class="toggle-switch">
                                            <input type="checkbox" id="settingsFunFacts" onchange="markSettingsUnsaved()">
                                            <span class="toggle-slider"></span>
                                        </label>
                                    </div>
                                </div>
                            </section>
                        </div>
                        
                        <!-- STORAGE SECTION -->
                        <div class="content-section" id="content-storage">
                            
                            <section class="settings-section">
                                <div class="section-header">
                                    <h3 class="section-title">💾 Cache Statistics</h3>
                                    <p class="section-description">Overview of disk space used by thumbnails and preview clips.</p>
                                </div>
                                
                                <div class="stats-grid">
                                    <div class="stat-card">
                                        <div class="stat-card-header">
                                            <span class="material-icons">image</span>
                                            <span>Thumbnails</span>
                                        </div>
                                        <div class="stat-card-value" id="statThumbnails">—</div>
                                    </div>
                                    
                                    <div class="stat-card">
                                        <div class="stat-card-header">
                                            <span class="material-icons">movie</span>
                                            <span>Preview Clips</span>
                                        </div>
                                        <div class="stat-card-value" id="statPreviews">—</div>
                                    </div>
                                    
                                    <div class="stat-card">
                                        <div class="stat-card-header">
                                            <span class="material-icons">storage</span>
                                            <span>Total Cache</span>
                                        </div>
                                        <div class="stat-card-value" id="statTotal">—</div>
                                    </div>
                                </div>
                                
                                <div class="alert alert-warning">
                                    <span class="material-icons">warning</span>
                                    <div>
                                        Änderungen erfordern einen Neustart der App
                                    </div>
                                </div>
                            </section>
                        </div>
                        
                    </div>
                    
                    <!-- Footer with Actions -->
                    <footer class="settings-footer">
                        <div style="display:flex; flex-direction:column; gap:4px;">
                            <div class="save-indicator saved">
                                <span class="material-icons">check_circle</span>
                                <span>All changes saved</span>
                            </div>
                            <div style="font-size:11px; color:rgba(255,255,255,0.4); display:flex; gap:8px;">
                                <span><kbd style="padding:2px 6px; background:rgba(255,255,255,0.05); border-radius:4px; font-family:monospace;">⌘S</kbd> to save</span>
                                <span>•</span>
                                <span><kbd style="padding:2px 6px; background:rgba(255,255,255,0.05); border-radius:4px; font-family:monospace;">ESC</kbd> to close</span>
                            </div>
                        </div>
                        <div class="footer-actions">
                            <button class="filter-btn" onclick="closeSettings()">Abbrechen</button>
                            <button class="filter-btn active" onclick="saveSettings()">
                                <span class="material-icons">save</span> Speichern
                            </button>
                        </div>
                    </footer>
                    
                </main>
                
            </div>
        </div>
        
        
        <iframe name='h_frame' style='display:none;'></iframe>

        <script>
            window.SERVER_PORT = {server_port};
            window.FOLDERS_DATA = {folders_json};
            window.ALL_VIDEOS = {all_videos_json};
            window.userSettings = {user_settings_json};
            window.OPTIMIZER_AVAILABLE = {'true' if config.optimizer_available else 'false'};
        </script>
        <script src="/static/treemap_layout.js?v={int(time.time())}"></script>
        <script src="/static/client.js?v={int(time.time())}"></script>
    </body>
    </html>"""

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)
