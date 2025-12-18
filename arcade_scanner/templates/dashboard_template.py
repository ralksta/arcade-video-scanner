import os
from arcade_scanner.app_config import HIDDEN_DATA_DIR, PORT, OPTIMIZER_SCRIPT, OPTIMIZER_AVAILABLE
from arcade_scanner.templates.styles import CSS_STYLES
from arcade_scanner.templates.client_script import CLIENT_JS

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
    
    html_content = f"""<!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>Arcade Video Dashboard</title>
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
        <style>{CSS_STYLES}</style>
    </head>
    <body data-port="{PORT}">
        <canvas id="starfield"></canvas>
        <div class="scanlines"></div>
        
        <header class="arcade-header">
            <div class="grid-bg"></div>
            <div class="logo-container">
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
                <input type="text" id="searchBar" placeholder="Suchen..." oninput="filterAndSort()">
                
                <div style="flex-shrink:0; height:24px; width:1px; background:rgba(255,255,255,0.1); margin:0 8px;"></div>
                
                <button class="filter-btn active" id="f-all" onclick="setFilter('all')">ALL</button>
                <button class="filter-btn" id="f-HIGH" onclick="setFilter('HIGH')">🚨 HIGH BITRATE</button>
                <button class="filter-btn" id="f-OK" onclick="setFilter('OK')">✅ OPTIMIZED</button>
                
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

                <div class="segmented-control">
                    <button class="segment-btn active" id="m-lobby" onclick="setWorkspaceMode('lobby')">LOBBY</button>
                    <button class="segment-btn" id="m-vault" onclick="setWorkspaceMode('vault')">VAULT</button>
                </div>
                
                <div style="width:1px; height:24px; background:rgba(255,255,255,0.1); margin:0 8px;"></div>

                <button class="filter-btn action-btn" id="toggleView" onclick="toggleLayout()"><span class="material-icons">view_list</span></button>
                
                <a href="javascript:location.reload()" class="filter-btn action-btn" title="Refresh">🔄 REFRESH</a>

                <button class="filter-btn action-btn" id="folderBtn" onclick="toggleFolderSidebar()" title="Ordner Explorer">
                    <span class="material-icons">folder</span>
                </button>
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
            <div id="videoGrid">"""

    for item in results:
        full_path = item["FilePath"]
        status_class = item["Status"]
        codec = item.get("codec", "unknown")
        opt_path = os.path.splitext(full_path)[0] + "_opt.mp4"
        opt_exists = os.path.exists(opt_path)
        bar_w = min(100, (item["Bitrate_Mbps"] / 25) * 100)
        is_hevc = "hevc" in codec or "h265" in codec
        hidden_val = str(item.get('hidden', False)).lower()

        html_content += f"""
                <div class="video-card-container" data-status="{status_class}" data-codec="{codec}" data-bitrate="{item["Bitrate_Mbps"]}" data-size="{item["Size_MB"]}" data-path="{full_path}" data-hidden="{hidden_val}" data-folder="{os.path.dirname(full_path)}">
                    <div class="content-card">
                        <div class="archive-badge">ARCHIVIERT</div>
                        <div class="checkbox-wrapper">
                            <input type="checkbox" onchange="updateBatchSelection()">
                        </div>
                        <div class="card-media" onmouseenter="handleMouseEnter(this)" onmouseleave="handleMouseLeave(this)" onclick="openCinema(this)">
                            <img src="thumbnails/{item["thumb"]}" class="thumb" loading="lazy">
                            <video class="preview-video" muted loop preload="none" 
                                   data-src="http://localhost:{PORT}/preview?name={item["preview"]}">
                            </video>
                            <div class="quick-actions-overlay">
                                <a href="http://localhost:{PORT}/reveal?path={full_path}" target="h_frame" class="quick-action-btn" title="Im Finder zeigen" onclick="event.stopPropagation()">
                                    <span class="material-icons">visibility</span>
                                </a>
                                <div class="quick-action-btn" title="Wiedergeben" onclick="event.stopPropagation(); openCinema(this.closest('.card-media'))">
                                    <span class="material-icons">play_arrow</span>
                                </div>
                                <div class="quick-action-btn hide-toggle-btn" title="Als gesehen markieren" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))">
                                    <span class="material-icons">{"visibility_off" if not item.get("hidden") else "visibility"}</span>
                                </div>
                                {f'''<a href="http://localhost:{PORT}/compress?path={full_path}" target="h_frame" class="quick-action-btn" title="Optimieren" onclick="event.stopPropagation()">
                                    <span class="material-icons">bolt</span>
                                </a>''' if OPTIMIZER_AVAILABLE else ""}
                            </div>
                        </div>
                        <div class="card-body">
                            <h2 class="file-name">{os.path.basename(full_path)}</h2>
                            <p class="file-dir">{os.path.dirname(full_path)}</p>
                            <div class="bitrate-track">
                                <div class="bitrate-fill" style="width: {bar_w}%"></div>
                            </div>
                            <div style="margin-top: 8px; font-size: 0.8rem; display: flex; justify-content: space-between;">
                                <span>{item["Bitrate_Mbps"]:.1f} Mbps</span>
                                <span style="color:#888;">{item["Size_MB"]:.0f} MB</span>
                            </div>
                        </div>
                        <div class="card-footer">
                            <div style="display:flex; align-items:center;">
                                <span class="badge {status_class}">{item["Status"]}</span>
                                <span class="badge hevc">{"HEVC" if is_hevc else codec.upper()}</span>
                            </div>
                            <div style="display:flex; gap:8px;">
                                <a href="http://localhost:{PORT}/reveal?path={full_path}" target="h_frame" class="btn"><span class="material-icons" style="font-size:18px;">visibility</span></a>
                                {f'''<a href="http://localhost:{PORT}/compress?path={full_path}" target="h_frame" class="btn {"done" if opt_exists else "opt"}">
                                    <span class="material-icons" style="font-size:18px;">{"check_circle" if opt_exists else "bolt"}</span>
                                </a>''' if OPTIMIZER_AVAILABLE else ""}
                            </div>
                        </div>
                    </div>
                </div>"""

    html_content += f"""
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
            <button class="filter-btn" onclick="triggerBatchHide(true)" style="background:var(--deep-purple); border-color:var(--glass-border);">
                <span class="material-icons">visibility_off</span> ALS GELESEN MARKIEREN
            </button>
            <button class="filter-btn" onclick="clearSelection()" style="background:transparent; border-color:white;">
                Abbrechen
            </button>
        </div>
        
        <iframe name='h_frame' style='display:none;'></iframe>

        <script>
            window.SERVER_PORT = {PORT};
            window.FOLDERS_DATA = {folders_json};
            {CLIENT_JS}
        </script>
    </body>
    </html>"""

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)
