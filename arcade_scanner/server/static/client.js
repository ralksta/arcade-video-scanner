let currentFilter = 'all';
let currentCodec = 'all';
let currentSort = 'bitrate';
let currentLayout = 'grid'; // grid, list, or treemap
let workspaceMode = 'lobby'; // lobby, mixed, vault
let currentFolder = 'all';
let searchTerm = '';

let filteredVideos = [];
let renderedCount = 0;
const BATCH_SIZE = 40;

// --- STARFIELD ---
const canvas = document.getElementById('starfield');
const ctx = canvas.getContext('2d');
let stars = [];
function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
window.onresize = resize; resize();

for (let i = 0; i < 200; i++) {
    stars.push({ x: Math.random() * canvas.width, y: Math.random() * canvas.height, size: Math.random() * 2, speed: Math.random() * 0.5 + 0.1 });
}

function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#fff';
    stars.forEach(s => {
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
        ctx.fill();
        s.y += s.speed;
        if (s.y > canvas.height) s.y = 0;
    });
    requestAnimationFrame(animate);
}
animate();

// --- DEBOUNCED SEARCH ---
let searchTimeout;
function onSearchInput() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        searchTerm = document.getElementById('searchBar').value.toLowerCase();

        // Show/Hide Save Button based on input
        const saveBtn = document.getElementById('saveViewBtn');
        if (saveBtn) {
            saveBtn.style.display = searchTerm.length > 0 ? 'inline-flex' : 'none';
        }

        currentLayout === 'treemap' ? renderTreemap() : filterAndSort();
    }, 300);
}

// --- UI LOGIC ---
function setFilter(f) {
    currentFilter = f;
    // Reset codec filter when showing all videos
    if (f === 'all') {
        currentCodec = 'all';
        document.getElementById('codecSelect').value = 'all';
    }
    filterAndSort();
}

function setCodecFilter(c) {
    currentCodec = c;
    filterAndSort();
}

function setSort(s) {
    currentSort = s;
    filterAndSort();
}

function setWorkspaceMode(mode) {
    workspaceMode = mode;
    document.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('m-' + mode).classList.add('active');
    if (mode === 'vault') document.body.classList.add('vault-mode');
    else document.body.classList.remove('vault-mode');

    // Add animation class
    const grid = document.getElementById('videoGrid');
    const treemap = document.getElementById('treemapContainer');
    if (grid) {
        grid.classList.remove('animating');
        void grid.offsetWidth; // Trigger reflow
        grid.classList.add('animating');
    }
    if (treemap) {
        treemap.classList.remove('animating');
        void treemap.offsetWidth; // Trigger reflow
        treemap.classList.add('animating');
    }

    filterAndSort();
    updateURL();
}

function toggleLayout() {
    const modes = ['grid', 'list', 'treemap'];
    const icons = {
        grid: 'view_list',      // Shows what's NEXT
        list: 'dashboard',      // Shows what's NEXT  
        treemap: 'view_module'  // Shows what's NEXT
    };

    const currentIndex = modes.indexOf(currentLayout);
    const nextIndex = (currentIndex + 1) % modes.length;
    const nextMode = modes[nextIndex];

    setLayout(nextMode);

    // Update button icon to show what's next
    const btn = document.getElementById('toggleView');
    btn.innerHTML = `<span class="material-icons">${icons[nextMode]}</span>`;
}

function setLayout(layout, skipURLUpdate = false) {
    currentLayout = layout;

    const grid = document.getElementById('videoGrid');
    const treemap = document.getElementById('treemapContainer');
    const sentinel = document.getElementById('loadingSentinel');
    const batchBar = document.getElementById('batchBar');
    const workspaceBar = document.querySelector('.workspace-bar');
    const treemapLegend = document.getElementById('treemapLegend');

    if (layout === 'treemap') {
        grid.style.display = 'none';
        sentinel.style.display = 'none';
        treemap.style.display = 'block';

        // Trigger animation
        treemap.classList.remove('animating');
        void treemap.offsetWidth; // Trigger reflow
        treemap.classList.add('animating');

        // Hide batch bar in treemap view (no checkboxes available)
        if (batchBar) {
            batchBar.style.display = 'none';
        }

        // Hide sort dropdown in treemap view (layout is always by size)
        const sortSelect = document.getElementById('sortSelect');
        if (sortSelect) sortSelect.style.display = 'none';

        // Hide workspace bar, show treemap legend
        if (workspaceBar) workspaceBar.style.display = 'none';
        if (treemapLegend) treemapLegend.style.display = 'block';

        renderTreemap();
        setupTreemapInteraction();
    } else {
        grid.style.display = layout === 'list' ? 'flex' : 'grid';
        sentinel.style.display = 'flex';
        treemap.style.display = 'none';

        // Trigger animation
        grid.classList.remove('animating');
        void grid.offsetWidth; // Trigger reflow
        grid.classList.add('animating');

        // Reset treemap drill-down state
        treemapCurrentFolder = null;

        // Restore batch bar display (will show if items are selected)
        if (batchBar) {
            batchBar.style.display = '';
        }

        // Show workspace bar, hide treemap legend
        if (workspaceBar) workspaceBar.style.display = '';
        if (treemapLegend) treemapLegend.style.display = 'none';

        // Show sort dropdown in grid/list view
        const sortSelect = document.getElementById('sortSelect');
        if (sortSelect) sortSelect.style.display = '';

        if (layout === 'list') {
            grid.classList.add('list-view');
        } else {
            grid.classList.remove('list-view');
        }

        renderUI(false);
    }

    // Update URL to reflect current view
    if (!skipURLUpdate) {
        updateURL();
    }
}

// Update URL to reflect current state
// Update URL to reflect current state
function updateURL() {
    let path = '/';

    // Special handling for Treemap
    if (currentLayout === 'treemap') {
        path = '/treeview';
        const params = new URLSearchParams();
        if (treemapCurrentFolder) {
            params.set('folder', encodeURIComponent(treemapCurrentFolder));
        }
        const qs = params.toString();
        if (qs) path += `?${qs}`;
    } else {
        // Map workspace mode to path
        if (workspaceMode === 'optimized') path = '/review';
        else if (workspaceMode === 'favorites') path = '/favorites';
        else if (workspaceMode === 'vault') path = '/vault';
        else path = '/lobby';
    }

    // Only push if changed
    if (window.location.pathname !== path) {
        window.history.pushState({ layout: currentLayout, folder: treemapCurrentFolder, mode: workspaceMode }, '', path);
    }
}

// Load state from URL on page load
function loadFromURL() {
    const path = window.location.pathname;
    const params = new URLSearchParams(window.location.search);

    // Default
    let mode = 'lobby';
    let layout = 'grid';

    if (path === '/favorites') mode = 'favorites';
    else if (path === '/review') mode = 'optimized';
    else if (path === '/vault') mode = 'vault';
    else if (path === '/treeview') {
        mode = 'lobby';
        layout = 'treemap';
    }

    // Overrides from params
    if (params.get('view') === 'treemap') layout = 'treemap';
    if (params.get('folder')) treemapCurrentFolder = decodeURIComponent(params.get('folder'));

    setWorkspaceMode(mode);

    // Force layout if treeview
    if (layout === 'treemap') {
        setLayout('treemap');
    }
}

// --- PERFORMANCE ENGINE: FILTER & SORT ---
function filterAndSort() {
    let vCount = 0; let tSize = 0;

    // Standard Filtering
    if (workspaceMode === 'optimized') {
        const pairs = [];
        const map = new Map();

        // 1. Map all files by stem (filename without extension)
        window.ALL_VIDEOS.forEach(v => {
            const fileName = v.FilePath.split(/[\\\\/]/).pop();
            const lastDot = fileName.lastIndexOf('.');
            const stem = lastDot > 0 ? fileName.substring(0, lastDot) : fileName;

            // Normalize path to directory to ensure we only pair in same folder
            const lastSlash = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
            const dir = v.FilePath.substring(0, lastSlash);

            const key = dir + '|' + stem;
            map.set(key, v);
        });

        // 2. Find pairs
        // We look for any key that ends in "_opt". 
        // If found, we check if corresponding "non-opt" key exists.

        map.forEach((vOpt, key) => {
            if (key.endsWith('_opt')) {
                const baseKey = key.substring(0, key.length - 4); // Strip _opt

                // Do we have the original?
                // Note: This relies on the original having the exact same stem minus "_opt".
                // Case A: movie.mkv -> movie_opt.mp4 (Stem: "movie" vs "movie_opt").
                // map has "dir|movie" and "dir|movie_opt".

                if (map.has(baseKey)) {
                    const vOrig = map.get(baseKey);

                    // Create a virtual pair object
                    pairs.push({
                        type: 'pair',
                        original: vOrig,
                        optimized: vOpt,
                        diff: vOpt.Size_MB - vOrig.Size_MB
                    });
                }
            }
        });

        filteredVideos = pairs;

    } else {
        filteredVideos = window.ALL_VIDEOS.filter(v => {
            const name = v.FilePath.split(/[\\\\/]/).pop().toLowerCase();
            const status = v.Status;
            const codec = v.codec || 'unknown';
            const isHidden = v.hidden || false;
            const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
            const folder = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';

            let matchesFilter = false;
            if (currentFilter === 'all') matchesFilter = true;
            else if (currentFilter === 'optimized_files') matchesFilter = v.FilePath.includes('_opt');
            else matchesFilter = (status === currentFilter);
            const matchesCodec = (currentCodec === 'all' || codec.includes(currentCodec));
            const matchesSearch = name.includes(searchTerm) || v.FilePath.toLowerCase().includes(searchTerm);
            const matchesFolder = (currentFolder === 'all' || folder === currentFolder);

            let matchesWorkspace = true;
            if (workspaceMode === 'lobby') matchesWorkspace = !isHidden; // Show _opt files too!
            else if (workspaceMode === 'vault') matchesWorkspace = isHidden;
            else if (workspaceMode === 'favorites') matchesWorkspace = v.favorite || false;

            const ok = matchesFilter && matchesCodec && matchesSearch && matchesWorkspace && matchesFolder;
            if (ok) { vCount++; tSize += v.Size_MB; }
            return ok;
        });
    }

    // Sort
    if (workspaceMode !== 'optimized') {
        filteredVideos.sort((a, b) => {
            if (currentSort === 'bitrate') return b.Bitrate_Mbps - a.Bitrate_Mbps;
            if (currentSort === 'size') return b.Size_MB - a.Size_MB;
            if (currentSort === 'name') return a.FilePath.localeCompare(b.FilePath);
            if (currentSort === 'date') return (b.mtime || 0) - (a.mtime || 0); // Newest first
            return 0;
        });
    } else {
        // Sort pairs by date (newest first)? Or name?
        // Default to name for now
        filteredVideos.sort((a, b) => a.original.FilePath.localeCompare(b.original.FilePath));
    }

    document.getElementById('count-total').innerText = vCount;
    document.getElementById('size-total').innerText = formatSize(tSize);

    renderUI(true);
}

function formatSize(mb) {
    if (mb > 1024 * 1024) return (mb / (1024 * 1024)).toFixed(2) + " TB";
    if (mb > 1024) return (mb / 1024).toFixed(2) + " GB";
    return mb.toFixed(0) + " MB";
}

// --- PERFORMANCE ENGINE: INFINITE SCROLL ---
function renderUI(reset) {
    // If in treemap mode, re-render treemap instead
    if (currentLayout === 'treemap') {
        renderTreemap();
        return;
    }

    const grid = document.getElementById('videoGrid');
    if (reset) {
        grid.innerHTML = '';
        renderedCount = 0;
        window.scrollTo(0, 0);
    }
    renderNextBatch();
}

function renderNextBatch() {
    if (renderedCount >= filteredVideos.length) {
        document.getElementById('loadingSentinel').style.opacity = '0';
        return;
    }

    const grid = document.getElementById('videoGrid');
    const fragment = document.createDocumentFragment();
    const nextBatch = filteredVideos.slice(renderedCount, renderedCount + BATCH_SIZE);

    nextBatch.forEach(item => {
        if (item.type === 'pair') {
            const card = createComparisonCard(item);
            fragment.appendChild(card);
        } else {
            const card = createVideoCard(item);
            fragment.appendChild(card);
        }
    });

    grid.appendChild(fragment);
    renderedCount += BATCH_SIZE;

    if (renderedCount < filteredVideos.length) {
        document.getElementById('loadingSentinel').style.opacity = '1';
    } else {
        document.getElementById('loadingSentinel').style.opacity = '0';
    }
}

function createComparisonCard(pair) {
    const orig = pair.original;
    const opt = pair.optimized;

    // Calculate stats
    const diffMB = opt.Size_MB - orig.Size_MB;
    const diffPct = (diffMB / orig.Size_MB) * 100;
    const isSmaller = diffMB < 0;

    const container = document.createElement('div');
    container.className = 'video-card-container comparison-card';
    container.style.gridColumn = "span 2"; // Make it wider

    // Format Display Stats
    const formatSize = (mb) => mb.toFixed(1) + " MB";
    const formatBitrate = (mbps) => mbps.toFixed(1) + " Mbps";

    container.innerHTML = `
        <div class="content-card" style="display:flex; flex-direction:row; height:auto; min-height:400px; padding:16px; gap:16px;">
            
            <!-- ORIGINAL -->
            <div style="flex:1; display:flex; flex-direction:column; min-width:0;">
                <div class="badge" style="align-self:flex-start; margin-bottom:8px; background:#444;">ORIGINAL</div>
                <div class="card-media" onmouseenter="handleMouseEnter(this)" onmouseleave="handleMouseLeave(this)" onclick="openCinema(this)" data-path="${orig.FilePath}">
                    <img src="thumbnails/${orig.thumb}" class="thumb" loading="lazy">
                    <video class="preview-video" muted loop preload="none" 
                           data-src="/preview?name=${orig.preview}">
                    </video>
                </div>
                <div style="margin-top:8px; overflow:hidden;">
                    <div class="file-name" title="${orig.FilePath}" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${orig.FilePath.split(/[\\\\/]/).pop()}</div>
                    <div style="display:flex; justify-content:space-between; color:#bbb; font-size:0.9rem; margin-top:4px;">
                        <span>${formatSize(orig.Size_MB)}</span>
                        <span>${formatBitrate(orig.Bitrate_Mbps)}</span>
                        <span>${orig.codec}</span>
                    </div>
                </div>
                <a href="/reveal?path=${encodeURIComponent(orig.FilePath)}" target="h_frame" class="btn" style="margin-top:10px; width:100%; text-align:center; display:block; padding:8px; background:rgba(255,255,255,0.1); color:rgba(255,255,255,0.9); text-decoration:none; border-radius:4px; transition: background 0.2s;">
                    <span class="material-icons" style="vertical-align:middle; font-size:18px; margin-right:4px;">folder_open</span> Reveal
                </a>
            </div>
            
            <!-- STATS CENTER -->
            <div style="width:160px; display:flex; flex-direction:column; align-items:center; justify-content:center; border-left:1px solid #333; border-right:1px solid #333; padding:0 8px; flex-shrink:0;">
                <div style="font-size:1.5rem; font-weight:bold; color:${isSmaller ? '#4cd964' : '#ff3b30'};">
                    ${diffPct.toFixed(1)}%
                </div>
                <div style="color:#888; font-size:0.8rem; margin-bottom:24px;">
                    ${diffMB.toFixed(1)} MB
                </div>
                
                <button class="filter-btn active" onclick="keepOptimized('${encodeURIComponent(orig.FilePath)}', '${encodeURIComponent(opt.FilePath)}')" style="width:100%; margin-bottom:8px;">
                    <span class="material-icons">check</span> KEEP
                </button>
                <button class="filter-btn" onclick="discardOptimized('${encodeURIComponent(opt.FilePath)}')" style="width:100%; background:transparent; border:1px solid #444;">
                    <span class="material-icons">delete</span> DISCARD
                </button>
            </div>

            <!-- OPTIMIZED -->
            <div style="flex:1; display:flex; flex-direction:column; min-width:0;">
                <div class="badge ok" style="align-self:flex-start; margin-bottom:8px;">OPTIMIZED</div>
                <div class="card-media" onmouseenter="handleMouseEnter(this)" onmouseleave="handleMouseLeave(this)" onclick="openCinema(this)" data-path="${opt.FilePath}">
                    <img src="thumbnails/${opt.thumb}" class="thumb" loading="lazy">
                    <video class="preview-video" muted loop preload="none" 
                           data-src="/preview?name=${opt.preview}">
                    </video>
                </div>
                <div style="margin-top:8px; overflow:hidden;">
                    <div class="file-name" title="${opt.FilePath}" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${opt.FilePath.split(/[\\\\/]/).pop()}</div>
                    <div style="display:flex; justify-content:space-between; color:#bbb; font-size:0.9rem; margin-top:4px;">
                        <span>${formatSize(opt.Size_MB)}</span>
                        <span>${formatBitrate(opt.Bitrate_Mbps)}</span>
                        <span>${opt.codec}</span>
                    </div>
                </div>
                <a href="/reveal?path=${encodeURIComponent(opt.FilePath)}" target="h_frame" class="btn" style="margin-top:10px; width:100%; text-align:center; display:block; padding:8px; background:rgba(255,255,255,0.1); color:rgba(255,255,255,0.9); text-decoration:none; border-radius:4px; transition: background 0.2s;">
                    <span class="material-icons" style="vertical-align:middle; font-size:18px; margin-right:4px;">folder_open</span> Reveal
                </a>
            </div>
            
        </div>
    `;

    // Store data for interactions
    container.setAttribute('data-path', orig.FilePath); // Proxy original
    return container;
}

function keepOptimized(orig, opt) {
    if (!confirm("Replace original with optimized version? This cannot be undone.")) return;
    fetch(`/api/keep_optimized?original=${orig}&optimized=${opt}`)
        .then(() => {
            // Remove from view
            setTimeout(() => {
                location.reload(); // Simplest way to refresh state
            }, 500);
        });
}

function discardOptimized(opt) {
    if (!confirm("Delete the optimized file?")) return;
    fetch(`/api/discard_optimized?path=${opt}`)
        .then(() => {
            setTimeout(() => {
                location.reload();
            }, 500);
        });
}

function createVideoCard(v) {
    const container = document.createElement('div');
    container.className = 'video-card-container';
    container.setAttribute('data-path', v.FilePath);

    const isHevc = (v.codec || '').includes('hevc') || (v.codec || '').includes('h265');
    const barW = Math.min(100, (v.Bitrate_Mbps / 25) * 100);
    const fileName = v.FilePath.split(/[\\\\/]/).pop();
    const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
    const dirName = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';

    container.innerHTML = `
        <div class="content-card">
            <div class="archive-badge">ARCHIVIERT</div>
            <div class="checkbox-wrapper">
                <input type="checkbox" onchange="updateBatchSelection()">
                <div class="favorite-btn ${v.favorite ? 'active' : ''}" title="${v.favorite ? 'Favorit' : 'Zu Favoriten hinzufügen'}" onclick="event.stopPropagation(); toggleFavorite(this.closest('.video-card-container'))">
                    <span class="material-icons">${v.favorite ? 'star' : 'star_border'}</span>
                </div>
            </div>
            <div class="card-media" onmouseenter="handleMouseEnter(this)" onmouseleave="handleMouseLeave(this)" onclick="openCinema(this)">
                <img src="thumbnails/${v.thumb}" class="thumb" loading="lazy">
                <video class="preview-video" muted loop preload="none" 
                       data-src="/preview?name=${v.preview}">
                </video>
                <div class="quick-actions-overlay">
                    <a href="/reveal?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="quick-action-btn" title="Im Finder zeigen" onclick="event.stopPropagation()">
                        <span class="material-icons">folder_open</span>
                    </a>
                    <div class="quick-action-btn" title="Wiedergeben" onclick="event.stopPropagation(); openCinema(this.closest('.card-media'))">
                        <span class="material-icons">play_arrow</span>
                    </div>
                    <div class="quick-action-btn hide-toggle-btn" title="Status ändern" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))">
                        <span class="material-icons">${v.hidden ? 'visibility' : 'visibility_off'}</span>
                    </div>
                    ${window.ENABLE_OPTIMIZER ? `
                    <a href="/compress?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="quick-action-btn" title="Optimieren" onclick="event.stopPropagation()">
                        <span class="material-icons">bolt</span>
                    </a>` : ''}
                </div>
            </div>
            <div class="card-body">
                <h2 class="file-name" title="${fileName}">${fileName}</h2>
                <p class="file-dir" title="${v.FilePath}">${dirName}</p>
                <div class="bitrate-track">
                    <div class="bitrate-fill" style="width: ${barW}%"></div>
                </div>
                <div style="margin-top: 8px; font-size: 0.8rem; display: flex; justify-content: space-between;">
                    <span>${v.Bitrate_Mbps.toFixed(1)} Mbps</span>
                    <span style="color:#888;">${v.Size_MB.toFixed(0)} MB</span>
                </div>
            </div>
            <div class="card-footer">
                <div style="display:flex; align-items:center;">
                    <span class="badge ${v.Status.toLowerCase()}">${v.Status}</span>
                    <span class="badge hevc">${isHevc ? 'HEVC' : (v.codec || 'UNK').toUpperCase()}</span>
                    ${fileName.includes('_opt.') ? '<span class="badge ok">OPTIMIZED</span>' : ''}
                </div>
                <div style="display:flex; gap:8px;">
                    <a href="/reveal?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="btn"><span class="material-icons" style="font-size:18px;">folder_open</span></a>
                    ${window.ENABLE_OPTIMIZER ? `
                    <a href="/compress?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="btn">
                        <span class="material-icons" style="font-size:18px;">bolt</span>
                    </a>` : ''}
                </div>
            </div>
        </div>
    `;
    return container;
}

// --- SCROLL OBSERVER ---
const sentinel = document.getElementById('loadingSentinel');
const scrollObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
        renderNextBatch();
    }
}, { rootMargin: '400px' });
scrollObserver.observe(sentinel);

// --- ACTIONS ---
function toggleHidden(card) {
    const path = card.getAttribute('data-path');
    const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
    if (!video) return;

    video.hidden = !video.hidden;
    fetch(`/hide?path=` + encodeURIComponent(path) + `&state=${video.hidden}`);

    // Update specific card UI instantly
    const btn = card.querySelector('.hide-toggle-btn .material-icons');
    btn.innerText = video.hidden ? 'visibility' : 'visibility_off';

    // Animate out if no longer matching workspace
    const shouldHide = (workspaceMode === 'lobby' && video.hidden) || (workspaceMode === 'vault' && !video.hidden);
    if (shouldHide) {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.8)';
        setTimeout(() => filterAndSort(), 300);
    }
}

function toggleFavorite(card) {
    const path = card.getAttribute('data-path');
    const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
    if (!video) return;

    video.favorite = !video.favorite;
    fetch(`/favorite?path=` + encodeURIComponent(path) + `&state=${video.favorite}`);

    const starBtn = card.querySelector('.favorite-btn');
    const starIcon = starBtn.querySelector('.material-icons');

    if (video.favorite) {
        starBtn.classList.add('active');
        starIcon.innerText = 'star';
        starBtn.title = 'Favorit';
    } else {
        starBtn.classList.remove('active');
        starIcon.innerText = 'star_border';
        starBtn.title = 'Zu Favoriten hinzufügen';
    }

    if (workspaceMode === 'favorites' && !video.favorite) {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.8)';
        setTimeout(() => filterAndSort(), 300);
    }
}

function triggerBatchFavorite(state) {
    const selected = document.querySelectorAll('.video-card-container input[type="checkbox"]:checked');
    if (selected.length === 0) return;

    const paths = Array.from(selected).map(cb => cb.closest('.video-card-container').getAttribute('data-path'));

    // Update Local Data
    paths.forEach(p => {
        const v = window.ALL_VIDEOS.find(vid => vid.FilePath === p);
        if (v) v.favorite = state;
    });

    // Notify Server
    fetch(`/batch_favorite?paths=` + encodeURIComponent(paths.join(',')) + `&state=${state}`);

    // Update UI
    selected.forEach(cb => {
        const card = cb.closest('.video-card-container');
        const starBtn = card.querySelector('.favorite-btn');
        const starIcon = starBtn.querySelector('.material-icons');

        if (state) {
            starBtn.classList.add('active');
            starIcon.innerText = 'star';
            starBtn.title = 'Favorit';
        } else {
            starBtn.classList.remove('active');
            starIcon.innerText = 'star_border';
            starBtn.title = 'Zu Favoriten hinzufügen';
        }
    });

    clearSelection();
    if (workspaceMode === 'favorites' && !state) {
        setTimeout(() => filterAndSort(), 350);
    }
}

function handleMouseEnter(container) {
    // Check global settings
    if (window.userSettings && window.userSettings.enable_previews === false) {
        return;
    }

    const video = container.querySelector('video');
    container.hoverTimeout = setTimeout(() => {
        const src = video.getAttribute('data-src');
        if (src && !video.getAttribute('src')) {
            video.src = src;
            video.load();
            video.play().catch(() => { });
        }
    }, 400);
}

function handleMouseLeave(container) {
    const video = container.querySelector('video');
    clearTimeout(container.hoverTimeout);
    video.pause();
    video.removeAttribute('src');
    video.load();
}

// --- CINEMA ---
// --- CINEMA (VIDEO PLAYER) ---
let currentCinemaPath = null;
let currentCinemaVideo = null;

function openCinema(container) {
    // 1. Try to find path on the clicked container itself (for specific video overrrides)
    let path = container.getAttribute('data-path');

    // 2. If not found, fall back to the main card container (default behavior)
    if (!path) {
        const card = container.closest('.video-card-container');
        if (card) path = card.getAttribute('data-path');
    }

    if (!path) return;

    const fileName = path.split(/[\\\/]/).pop();

    currentCinemaPath = path; // Store for action buttons

    // Find the video object from allVideos
    currentCinemaVideo = window.ALL_VIDEOS.find(v => v.FilePath === path);

    const modal = document.getElementById('cinemaModal');
    const video = document.getElementById('cinemaVideo');
    document.getElementById('cinemaTitle').innerText = fileName;

    video.src = `/stream?path=` + encodeURIComponent(path);
    modal.classList.add('active');
    video.load();
    video.play().catch(() => {
        video.muted = true;
        video.play();
    });

    // Update button states
    updateCinemaButtons();

    // Populate info panel
    updateCinemaInfo();
}

function closeCinema() {
    const modal = document.getElementById('cinemaModal');
    const video = document.getElementById('cinemaVideo');
    const infoPanel = document.getElementById('cinemaInfoPanel');
    modal.classList.remove('active');
    infoPanel.classList.remove('active');
    video.pause();
    video.src = '';
    currentCinemaPath = null;
    currentCinemaVideo = null;
}

function toggleCinemaInfo() {
    const panel = document.getElementById('cinemaInfoPanel');
    panel.classList.toggle('active');
}

function updateCinemaInfo() {
    if (!currentCinemaVideo) {
        console.log('No currentCinemaVideo set');
        return;
    }

    const v = currentCinemaVideo;
    const content = document.getElementById('cinemaInfoContent');

    if (!content) {
        console.log('cinemaInfoContent element not found');
        return;
    }

    console.log('Updating cinema info for:', v.FilePath);

    // Format duration
    const formatDuration = (seconds) => {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        return h > 0 ? `${h}h ${m}m ${s}s` : `${m}m ${s}s`;
    };

    // Format file size
    const formatSize = (mb) => {
        return mb >= 1024 ? `${(mb / 1024).toFixed(2)} GB` : `${mb.toFixed(2)} MB`;
    };

    content.innerHTML = `
        <div class="info-row">
            <span class="info-label">Resolution</span>
            <span class="info-value">${v.Width} × ${v.Height}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Duration</span>
            <span class="info-value">${formatDuration(v.Duration)}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Frame Rate</span>
            <span class="info-value">${v.FrameRate} fps</span>
        </div>
        <div class="info-row">
            <span class="info-label">Codec</span>
            <span class="info-value">${v.Codec}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Bitrate</span>
            <span class="info-value">${v.Bitrate.toLocaleString()} kbps</span>
        </div>
        <div class="info-row">
            <span class="info-label">File Size</span>
            <span class="info-value">${formatSize(v.SizeMB)}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Status</span>
            <span class="info-value" style="color: ${v.Status === 'HIGH' ? '#E3A857' : '#568203'}">${v.Status}</span>
        </div>
    `;

    console.log('Cinema info updated successfully');
}

function updateCinemaButtons() {
    if (!currentCinemaVideo) return;

    // Update Favorite button
    const favBtn = document.querySelector('.cinema-action-btn[onclick="cinemaFavorite()"]');
    if (favBtn) {
        if (currentCinemaVideo.favorite) {
            favBtn.style.opacity = '0.6';
            favBtn.title = 'Already a Favorite';
        } else {
            favBtn.style.opacity = '1';
            favBtn.title = 'Add to Favorites';
        }
    }

    // Update Vault button
    const vaultBtn = document.querySelector('.cinema-action-btn[onclick="cinemaVault()"]');
    if (vaultBtn) {
        if (currentCinemaVideo.hidden) {
            vaultBtn.style.opacity = '0.6';
            vaultBtn.title = 'Already in Vault';
        } else {
            vaultBtn.style.opacity = '1';
            vaultBtn.title = 'Move to Vault';
        }
    }
}

function cinemaFavorite() {
    if (!currentCinemaPath || !currentCinemaVideo) return;

    // Toggle favorite state
    const newState = !currentCinemaVideo.favorite;

    fetch(`/favorite?path=` + encodeURIComponent(currentCinemaPath) + `&state=${newState}`)
        .then(() => {
            // Update local video object
            currentCinemaVideo.favorite = newState;

            // Update in ALL_VIDEOS array
            const videoInArray = window.ALL_VIDEOS.find(v => v.FilePath === currentCinemaPath);
            if (videoInArray) {
                videoInArray.favorite = newState;
            }

            // Update button appearance
            updateCinemaButtons();

            // Re-filter and re-render the grid (this updates the favorites view)
            filterAndSort();
        });
}

function cinemaVault() {
    if (!currentCinemaPath) return;

    fetch(`/hide?path=` + encodeURIComponent(currentCinemaPath) + `&state=true`)
        .then(() => {
            closeCinema();
            location.reload(); // Refresh to update UI
        });
}

function cinemaLocate() {
    if (!currentCinemaPath) return;
    window.open(`/reveal?path=` + encodeURIComponent(currentCinemaPath), 'h_frame');
}

function cinemaOptimize() {
    if (!currentCinemaPath) return;
    window.open(`/compress?path=` + encodeURIComponent(currentCinemaPath), 'h_frame');
}
// ESC handler moved to setupTreemapInteraction section

// --- BATCH ---
function updateBatchSelection() {
    const count = document.querySelectorAll('.video-card-container input:checked').length;
    const bar = document.getElementById('batchBar');
    document.getElementById('batchCount').innerText = count;
    if (count > 0) bar.classList.add('active');
    else bar.classList.remove('active');
}

function clearSelection() {
    document.querySelectorAll('.video-card-container input:checked').forEach(i => i.checked = false);
    updateBatchSelection();
}

function selectAllVisible() {
    // Select all videos in the current filtered list
    filteredVideos.forEach(video => {
        const container = document.querySelector(`.video-card-container[data-path="${CSS.escape(video.FilePath)}"]`);
        if (container) {
            const checkbox = container.querySelector('input[type="checkbox"]');
            if (checkbox) checkbox.checked = true;
        }
    });
    updateBatchSelection();
}

function triggerBatchHide(state) {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));

    fetch(`/batch_hide?paths=` + encodeURIComponent(paths.join(',')) + `&state=${state}`);

    paths.forEach(p => {
        const v = window.ALL_VIDEOS.find(vid => vid.FilePath === p);
        if (v) v.hidden = state;
    });

    filterAndSort();
    clearSelection();
}

function triggerBatchCompress() {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));
    if (confirm(`Möchtest du ${paths.length} Videos nacheinander optimieren?`)) {
        fetch(`/batch_compress?paths=` + encodeURIComponent(paths.join(',')));
        alert("Batch Optimierung gestartet!");
        clearSelection();
    }
}

// --- FOLDER SIDEBAR ---
function toggleFolderSidebar() {
    document.getElementById('folderSidebar').classList.toggle('active');
    renderFolderSidebar();
}

function setFolderFilter(folder) {
    currentFolder = folder;
    filterAndSort();
    renderFolderSidebar();
}

function renderFolderSidebar() {
    const list = document.getElementById('folderList');
    if (!list.parentElement.classList.contains('active')) return;

    list.innerHTML = '';
    const folders = Object.keys(window.FOLDERS_DATA).sort((a, b) => window.FOLDERS_DATA[b].size_mb - window.FOLDERS_DATA[a].size_mb);
    const maxSize = Math.max(...Object.values(window.FOLDERS_DATA).map(f => f.size_mb));

    const allItem = document.createElement('div');
    allItem.className = `folder-item ${currentFolder === 'all' ? 'active' : ''}`;
    allItem.onclick = () => setFolderFilter('all');
    allItem.innerHTML = `<div class="folder-name">ALLE ORDNER</div><div class="folder-meta"><span>Gesamte Bibliothek</span></div>`;
    list.appendChild(allItem);

    folders.forEach(path => {
        const data = window.FOLDERS_DATA[path];
        const item = document.createElement('div');
        item.className = `folder-item ${currentFolder === path ? 'active' : ''}`;
        item.onclick = () => setFolderFilter(path);

        const relWidth = (data.size_mb / maxSize) * 100;
        const folderName = path.split(/[\\\\/]/).pop() || path;

        item.innerHTML = `
            <div class="folder-name" title="${path}">${folderName}</div>
            <div class="folder-meta">
                <span>${data.count} Videos</span>
                <span>${formatSize(data.size_mb)}</span>
            </div>
            <div class="folder-progress"><div class="folder-progress-fill" style="width: ${relWidth}%"></div></div>
        `;
        list.appendChild(item);
    });
}

function resetDashboard() {
    currentFilter = 'all';
    currentCodec = 'all';
    currentSort = 'bitrate';
    currentFolder = 'all';
    searchTerm = '';

    // Reset UI elements
    document.getElementById('searchBar').value = '';
    document.getElementById('codecSelect').value = 'all';
    document.getElementById('sortSelect').value = 'bitrate';

    // Reset internal state and re-render
    setFilter('all');
    setWorkspaceMode('lobby');
    renderFolderSidebar(); // This will refresh the folder list UI
}

// --- TREEMAP VISUALIZATION ---
// State for drill-down navigation
let treemapCurrentFolder = null; // null = show all folders, string = show files in that folder
let treemapUseLog = false; // Log scale toggle

function toggleTreemapScale() {
    treemapUseLog = document.getElementById('treemapLogToggle').checked;
    renderTreemap();
}

function renderTreemap() {
    const container = document.getElementById('treemapContainer');
    if (!container) return;

    // Create or get canvas
    let canvas = document.getElementById('treemapCanvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'treemapCanvas';
        container.appendChild(canvas);
    }

    const ctx = canvas.getContext('2d');
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (filteredVideos.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '20px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Keine Videos gefunden', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Update legend to show current path
    updateTreemapLegend();

    if (treemapCurrentFolder === null) {
        // FOLDER-ONLY VIEW: Show only folder blocks
        renderFolderView(ctx, canvas);
    } else {
        // DRILLED-DOWN VIEW: Show files in selected folder
        renderFileView(ctx, canvas, treemapCurrentFolder);
    }
}

function renderFolderView(ctx, canvas) {
    // Group videos by folder
    const folderMap = new Map();
    filteredVideos.forEach(v => {
        const path = v.FilePath;
        const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        const folder = lastIdx >= 0 ? path.substring(0, lastIdx) : 'Root';

        if (!folderMap.has(folder)) {
            folderMap.set(folder, { items: [], totalSize: 0, highCount: 0, okCount: 0 });
        }
        const f = folderMap.get(folder);
        f.items.push(v);
        f.totalSize += v.Size_MB;
        if (v.Status === 'HIGH') f.highCount++;
        else f.okCount++;
    });

    // Create folder data for squarify
    const folderData = [];
    folderMap.forEach((value, key) => {
        const parts = key.split(/[\\/]/);
        const shortName = parts[parts.length - 1] || 'Root';
        folderData.push({
            folder: key,
            shortName: shortName,
            size: value.totalSize,
            count: value.items.length,
            highCount: value.highCount,
            okCount: value.okCount
        });
    });

    // Sort and layout
    // Sort and layout
    const blocks = squarify(folderData, 0, 0, canvas.width, canvas.height, treemapUseLog);

    // Folder color gradients - darker tones to complement video gradients
    const folderGradients = [
        ['#4c1d95', '#6b21a8'], // Deep purple
        ['#1e3a8a', '#3b82f6'], // Deep to bright blue
        ['#7c2d12', '#dc2626'], // Brown to red
        ['#14532d', '#16a34a'], // Dark to bright green
        ['#78350f', '#d97706'], // Brown to amber
        ['#1f2937', '#4b5563']  // Dark gray to gray
    ];

    // Render folder blocks
    blocks.forEach((block, idx) => {
        // Base folder gradient
        const colors = folderGradients[idx % folderGradients.length];
        const gradient = ctx.createLinearGradient(block.x, block.y, block.x + block.width, block.y + block.height);
        gradient.addColorStop(0, colors[0]);
        gradient.addColorStop(1, colors[1]);
        ctx.fillStyle = gradient;
        ctx.fillRect(block.x, block.y, block.width, block.height);

        // Status indicator bar at bottom (proportional HIGH vs OK)
        const barHeight = Math.min(8, block.height * 0.1);
        if (block.height > 30) {
            const highRatio = block.highCount / block.count;
            const highWidth = block.width * highRatio;

            // Gold gradient for HIGH
            const highGradient = ctx.createLinearGradient(block.x, block.y + block.height - barHeight, block.x + highWidth, block.y + block.height);
            highGradient.addColorStop(0, '#E3A857');
            highGradient.addColorStop(1, '#E0D5A3');
            ctx.fillStyle = highGradient;
            ctx.fillRect(block.x, block.y + block.height - barHeight, highWidth, barHeight);

            // Olive-khaki gradient for OK
            const okGradient = ctx.createLinearGradient(block.x + highWidth, block.y + block.height - barHeight, block.x + block.width, block.y + block.height);
            okGradient.addColorStop(0, '#568203');
            okGradient.addColorStop(1, '#F0E68C');
            ctx.fillStyle = okGradient;
            ctx.fillRect(block.x + highWidth, block.y + block.height - barHeight, block.width - highWidth, barHeight);
        }

        // Border
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 2;
        ctx.strokeRect(block.x, block.y, block.width, block.height);

        // Search highlight - glow effect for folders containing matching files
        if (searchTerm) {
            const hasMatch = filteredVideos.some(v => {
                const vPath = v.FilePath;
                const vLastIdx = Math.max(vPath.lastIndexOf('/'), vPath.lastIndexOf('\\'));
                const vFolder = vLastIdx >= 0 ? vPath.substring(0, vLastIdx) : 'Root';
                return vFolder === block.folder && v.FilePath.toLowerCase().includes(searchTerm.toLowerCase());
            });
            if (hasMatch) {
                ctx.save();
                ctx.strokeStyle = '#00ffff';
                ctx.lineWidth = 4;
                ctx.shadowColor = '#00ffff';
                ctx.shadowBlur = 20;
                ctx.strokeRect(block.x + 2, block.y + 2, block.width - 4, block.height - 4);
                ctx.restore();
            }
        }

        // Labels
        if (block.width > 60 && block.height > 40) {
            ctx.fillStyle = '#fff';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            const centerX = block.x + block.width / 2;
            const centerY = block.y + block.height / 2 - 8;

            // Folder name
            ctx.font = 'bold 13px Inter, sans-serif';

            const maxChars = Math.floor(block.width / 8);
            let displayName = block.shortName;
            if (displayName.length > maxChars && maxChars > 3) {
                displayName = displayName.substring(0, maxChars - 3) + '...';
            }
            ctx.fillText(displayName, centerX, centerY);

            // Count and size
            ctx.font = '11px Inter, sans-serif';
            ctx.fillStyle = '#ccc';
            const sizeText = block.size > 1024
                ? `${(block.size / 1024).toFixed(1)} GB`
                : `${block.size.toFixed(0)} MB`;
            ctx.fillText(`${block.count} Videos • ${sizeText}`, centerX, centerY + 18);
        }
    });

    // Store for interaction
    canvas.treemapBlocks = blocks;
    canvas.treemapMode = 'folders';
}

function renderFileView(ctx, canvas, folderPath) {
    // Get videos in this folder
    const videosInFolder = filteredVideos.filter(v => {
        const path = v.FilePath;
        const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        const folder = lastIdx >= 0 ? path.substring(0, lastIdx) : 'Root';
        return folder === folderPath;
    });

    if (videosInFolder.length === 0) {
        treemapCurrentFolder = null;
        renderTreemap();
        return;
    }

    // Prepare data
    const treemapData = videosInFolder.map(v => ({
        video: v,
        size: v.Size_MB,
        name: v.FilePath.split(/[\\/]/).pop()
    }));

    // Layout
    const blocks = squarify(treemapData, 0, 0, canvas.width, canvas.height, treemapUseLog);

    // Render video tiles with FLAT colors (no gradients)
    blocks.forEach(block => {
        const video = block.video;

        // Color by status - gradient for HIGH, flat for OK
        if (video.Status === 'HIGH') {
            const gradient = ctx.createLinearGradient(block.x, block.y, block.x + block.width, block.y + block.height);
            gradient.addColorStop(0, '#E3A857');
            gradient.addColorStop(1, '#E0D5A3');
            ctx.fillStyle = gradient;
        } else {
            const gradient = ctx.createLinearGradient(block.x, block.y, block.x + block.width, block.y);
            gradient.addColorStop(0, '#568203');
            gradient.addColorStop(1, '#F0E68C');
            ctx.fillStyle = gradient;
        }
        ctx.fillRect(block.x, block.y, block.width, block.height);

        // Border
        ctx.strokeStyle = '#1f2937';
        ctx.lineWidth = 1;
        ctx.strokeRect(block.x, block.y, block.width, block.height);

        // Search highlight - glow effect for matching files
        if (searchTerm && block.name.toLowerCase().includes(searchTerm.toLowerCase())) {
            ctx.save();
            ctx.strokeStyle = '#00ffff';
            ctx.lineWidth = 3;
            ctx.shadowColor = '#00ffff';
            ctx.shadowBlur = 15;
            ctx.strokeRect(block.x + 2, block.y + 2, block.width - 4, block.height - 4);
            ctx.restore();
        }

        // Labels
        if (block.width > 80 && block.height > 50) {
            // Use dark text on bright backgrounds (HIGH/yellow), white on dark (OK/green)
            ctx.fillStyle = video.Status === 'HIGH' ? '#000' : '#fff';

            // Dynamic font size based on tile dimensions - larger tiles get bigger text
            const minDim = Math.min(block.width, block.height);
            const titleFontSize = Math.max(14, Math.min(32, minDim / 4));
            const subFontSize = Math.max(11, Math.min(22, minDim / 6));

            ctx.font = `600 ${titleFontSize}px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            const centerX = block.x + block.width / 2;
            const centerY = block.y + block.height / 2;

            // Calculate max chars based on tile width and font size
            const charWidth = titleFontSize * 0.55;
            const maxChars = Math.floor((block.width - 20) / charWidth);
            const displayName = block.name.length > maxChars
                ? block.name.substring(0, maxChars - 3) + '...'
                : block.name;

            ctx.fillText(displayName, centerX, centerY - titleFontSize * 0.6);
            ctx.font = `400 ${subFontSize}px Inter, sans-serif`;
            ctx.fillStyle = video.Status === 'HIGH' ? 'rgba(0,0,0,0.7)' : 'rgba(255,255,255,0.85)';
            ctx.fillText(`${video.Size_MB.toFixed(0)} MB`, centerX, centerY + subFontSize * 0.8);
        }
    });

    // Store for interaction
    canvas.treemapBlocks = blocks;
    canvas.treemapMode = 'files';
}

function updateTreemapLegend() {
    const legend = document.getElementById('treemapLegend');
    if (!legend) return;

    const titleEl = legend.querySelector('.legend-title');
    const hintEl = legend.querySelector('.legend-hint');
    const backBtn = document.getElementById('treemapBackBtn');

    if (treemapCurrentFolder === null) {
        titleEl.textContent = 'SPEICHER TREEMAP';
        hintEl.textContent = 'Klicken zum Reinzoomen';
        if (backBtn) backBtn.style.display = 'none';
    } else {
        const parts = treemapCurrentFolder.split(/[\\/]/);
        const shortName = parts[parts.length - 1] || 'Root';
        // Count videos in this folder
        const count = filteredVideos.filter(v => {
            const path = v.FilePath;
            const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
            const folder = lastIdx >= 0 ? path.substring(0, lastIdx) : 'Root';
            return folder === treemapCurrentFolder;
        }).length;
        titleEl.innerHTML = `📁 ${shortName} <span style="opacity:0.6; font-size:0.85em;">(${count} Videos)</span>`;
        hintEl.textContent = 'Klicken zum Abspielen';
        if (backBtn) backBtn.style.display = 'inline-flex';
    }
}

function treemapZoomOut() {
    treemapCurrentFolder = null;
    renderTreemap();
    updateURL();
}

function setupTreemapInteraction() {
    const canvas = document.getElementById('treemapCanvas');
    if (!canvas || canvas.hasTreemapListeners) return;

    // Create tooltip if it doesn't exist
    let tooltip = document.getElementById('treemapTooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'treemapTooltip';
        document.body.appendChild(tooltip);
    }

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const block = canvas.treemapBlocks?.find(b =>
            x >= b.x && x <= b.x + b.width &&
            y >= b.y && y <= b.y + b.height
        );

        if (block) {
            canvas.style.cursor = 'pointer';
            tooltip.style.opacity = '1';
            tooltip.style.left = e.clientX + 15 + 'px';
            tooltip.style.top = e.clientY + 15 + 'px';

            if (canvas.treemapMode === 'folders') {
                // Folder tooltip
                const sizeText = block.size > 1024
                    ? `${(block.size / 1024).toFixed(1)} GB`
                    : `${block.size.toFixed(0)} MB`;
                tooltip.innerHTML = `
                    <strong>📁 ${block.shortName}</strong>
                    Videos: ${block.count}<br>
                    Größe: ${sizeText}<br>
                    HIGH: ${block.highCount} • OK: ${block.okCount}
                `;
            } else {
                // File tooltip with thumbnail
                const video = block.video;
                const thumbUrl = `thumbnails/${video.thumb}`;
                const isHevc = (video.codec || '').includes('hevc') || (video.codec || '').includes('h265');
                tooltip.innerHTML = `
                    <div style="display: flex; gap: 12px; align-items: flex-start;">
                        <img src="${thumbUrl}" style="width: 120px; height: 68px; object-fit: cover; border-radius: 4px; background: #333;" onerror="this.style.display='none'">
                        <div>
                            <strong style="display: block; margin-bottom: 6px;">${block.name}</strong>
                            Größe: ${video.Size_MB.toFixed(1)} MB<br>
                            Bitrate: ${video.Bitrate_Mbps.toFixed(1)} Mbps<br>
                            Codec: ${isHevc ? 'HEVC' : (video.codec || 'Unknown').toUpperCase()}<br>
                            Status: <span style="color: ${video.Status === 'HIGH' ? '#f59e0b' : '#10b981'}">${video.Status}</span>
                        </div>
                    </div>
                `;
            }
        } else {
            canvas.style.cursor = 'default';
            tooltip.style.opacity = '0';
        }
    });

    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const block = canvas.treemapBlocks?.find(b =>
            x >= b.x && x <= b.x + b.width &&
            y >= b.y && y <= b.y + b.height
        );

        if (block) {
            if (canvas.treemapMode === 'folders') {
                // Drill down into folder
                treemapCurrentFolder = block.folder;
                renderTreemap();
                updateURL();
            } else {
                // Open cinema for file
                // Open cinema for file
                const mockContainer = {
                    getAttribute: (attr) => attr === 'data-path' ? block.video.FilePath : null,
                    closest: () => null
                };
                openCinema(mockContainer);
            }
        }
    });

    canvas.addEventListener('mouseleave', () => {
        tooltip.style.opacity = '0';
    });

    canvas.hasTreemapListeners = true;

    // Add legend click handler for zoom out
    const legend = document.getElementById('treemapLegend');
    if (legend && !legend.hasClickListener) {
        legend.style.cursor = 'pointer';
        legend.addEventListener('click', () => {
            if (treemapCurrentFolder !== null) {
                treemapZoomOut();
            }
        });
        legend.hasClickListener = true;
    }
}

// ESC key handler for treemap zoom out
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (currentLayout === 'treemap' && treemapCurrentFolder !== null) {
            e.preventDefault();
            treemapZoomOut();
        } else {
            closeCinema();
        }
    }
});

// Debounced resize handler for treemap
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (currentLayout === 'treemap') {
            renderTreemap();
        } else {
            renderUI(true);
        }
    }, 250);
});

// Handle browser back/forward buttons
window.addEventListener('popstate', (event) => {
    if (event.state) {
        currentLayout = event.state.layout || 'grid';
        treemapCurrentFolder = event.state.folder || null;
        setLayout(currentLayout, true);
    } else {
        loadFromURL();
    }
});

// Init
window.onload = () => {
    loadFromURL();
    filterAndSort();

    // Add double-click handler to stats display for quick treemap access
    const statsDisplay = document.querySelector('.stats-display');
    if (statsDisplay) {
        statsDisplay.addEventListener('dblclick', () => {
            setLayout('treemap');
            // Update toggle button icon
            const btn = document.getElementById('toggleView');
            btn.innerHTML = '<span class="material-icons">view_module</span>';
        });
    }

    // Load fresh settings from API to ensure sync
    loadSettings();
};

// --- SETTINGS MODAL ---
async function openSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.add('active');

    try {
        const response = await fetch('/api/settings');
        const data = await response.json();

        // Populate form fields
        document.getElementById('settingsTargets').value = data.scan_targets.join('\n');
        document.getElementById('settingsExcludes').value = data.exclude_paths.join('\n');
        document.getElementById('settingsMinSize').value = data.min_size_mb;
        document.getElementById('settingsMinSize').value = data.min_size_mb;
        document.getElementById('settingsBitrate').value = data.bitrate_threshold_kbps;

        // New Features
        document.getElementById('settingsFunFacts').checked = data.enable_fun_facts !== false;

        // Show default paths hint
        document.getElementById('defaultTargetsHint').textContent =
            `Standard: ${data.default_scan_targets.slice(0, 2).join(', ')}${data.default_scan_targets.length > 2 ? '...' : ''}`;

        // Populate default exclusions with checkboxes
        const container = document.getElementById('defaultExclusionsContainer');
        container.innerHTML = '';

        const disabledDefaults = data.disabled_defaults || [];

        data.default_exclusions.forEach(exc => {
            const isEnabled = !disabledDefaults.includes(exc.path);
            const item = document.createElement('label');
            item.className = 'checkbox-item';
            item.innerHTML = `
                <input type="checkbox" data-path="${exc.path}" ${isEnabled ? 'checked' : ''}>
                <div class="checkbox-item-content">
                    <div class="checkbox-item-title">${exc.path}</div>
                    <div class="checkbox-item-description">${exc.desc}</div>
                </div>
            `;
            container.appendChild(item);
        });

        // Fetch cache statistics
        const statsResponse = await fetch('/api/cache-stats');
        const stats = await statsResponse.json();

        document.getElementById('statThumbnails').textContent = `${stats.thumbnails_mb} MB`;
        document.getElementById('statPreviews').textContent = `${stats.previews_mb} MB`;
        document.getElementById('statTotal').textContent = `${stats.total_mb} MB`;
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

function closeSettings() {
    document.getElementById('settingsModal').classList.remove('active');
}

async function saveSettings() {
    markSettingsSaving();

    const targetsText = document.getElementById('settingsTargets').value;
    const excludesText = document.getElementById('settingsExcludes').value;

    // Collect disabled defaults (unchecked checkboxes)
    const disabledDefaults = [];
    document.querySelectorAll('#defaultExclusionsContainer input[type="checkbox"]').forEach(cb => {
        if (!cb.checked) {
            disabledDefaults.push(cb.dataset.path);
        }
    });

    const settings = {
        scan_targets: targetsText.split('\n').map(s => s.trim()).filter(s => s),
        exclude_paths: excludesText.split('\n').map(s => s.trim()).filter(s => s),
        disabled_defaults: disabledDefaults,
        min_size_mb: parseInt(document.getElementById('settingsMinSize').value) || 100,
        bitrate_threshold_kbps: parseInt(document.getElementById('settingsBitrate').value) || 15000,
        enable_previews: window.userSettings.enable_previews, // Keep existing value (hidden setting)
        enable_fun_facts: document.getElementById('settingsFunFacts').checked
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            markSettingsSaved();

            // Close after brief delay to show success state
            setTimeout(() => {
                closeSettings();
            }, 800);

            // Show success feedback on settings button
            const btn = document.getElementById('settingsBtn');
            btn.style.color = 'var(--gold)';
            setTimeout(() => { btn.style.color = ''; }, 2000);

            // Update local state immediately
            window.userSettings = {
                ...window.userSettings,
                ...settings
            };
        } else {
            alert('Fehler beim Speichern der Einstellungen');
            markSettingsUnsaved();
        }
    } catch (e) {
        console.error('Failed to save settings:', e);
        alert('Fehler beim Speichern der Einstellungen');
        markSettingsUnsaved();
    }
}

async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        if (response.ok) {
            const data = await response.json();
            // Merge with existing to keep any static generated data
            window.userSettings = {
                ...window.userSettings,
                ...data
            };
            console.log("Settings loaded:", window.userSettings);
        }
    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

// === NEW SETTINGS UI NAVIGATION ===

function initSettingsNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const contentSections = document.querySelectorAll('.content-section');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const sectionId = item.dataset.section;

            // Update active nav item
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Show corresponding content
            contentSections.forEach(section => {
                section.classList.remove('active');
            });
            const targetSection = document.getElementById(`content-${sectionId}`);
            if (targetSection) {
                targetSection.classList.add('active');
            }

            // Update header
            updateSettingsHeader(sectionId);
        });
    });
}

function updateSettingsHeader(sectionId) {
    const headers = {
        'scanning': {
            title: 'Scanning',
            subtitle: 'Configure video library scanning behavior'
        },
        'performance': {
            title: 'Performance',
            subtitle: 'Optimize scan performance and file filtering'
        },
        'interface': {
            title: 'Interface',
            subtitle: 'Customize dashboard appearance and features'
        },
        'storage': {
            title: 'Storage',
            subtitle: 'Manage cache and disk space usage'
        }
    };

    const header = headers[sectionId] || { title: sectionId, subtitle: '' };
    const titleEl = document.getElementById('section-title');
    const subtitleEl = document.getElementById('section-subtitle');

    if (titleEl) titleEl.textContent = header.title;
    if (subtitleEl) subtitleEl.textContent = header.subtitle;
}

// Number Input Adjustment for new UI
function adjustSettingsNumber(inputId, delta) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const current = parseInt(input.value) || 0;
    const min = parseInt(input.min) || 0;
    const max = parseInt(input.max) || Infinity;
    const newValue = Math.max(min, Math.min(max, current + delta));
    input.value = newValue;
    markSettingsUnsaved();
}

// Save State Indicator
function markSettingsUnsaved() {
    const indicator = document.querySelector('.save-indicator');
    if (indicator) {
        indicator.className = 'save-indicator unsaved';
        indicator.innerHTML = '<span class="material-icons">warning</span><span>Unsaved changes</span>';
    }
}

function markSettingsSaving() {
    const indicator = document.querySelector('.save-indicator');
    if (indicator) {
        indicator.className = 'save-indicator saving';
        indicator.innerHTML = '<div class="loading-spinner"></div><span>Saving...</span>';
    }
}

function markSettingsSaved() {
    const indicator = document.querySelector('.save-indicator');
    if (indicator) {
        indicator.className = 'save-indicator saved';
        indicator.innerHTML = '<span class="material-icons">check_circle</span><span>All changes saved</span>';
    }
}

// Initialize navigation when settings modal opens
const originalOpenSettings = window.openSettings;
window.openSettings = async function () {
    if (originalOpenSettings) {
        await originalOpenSettings();
    }
    // Initialize navigation after modal is populated
    setTimeout(() => {
        initSettingsNavigation();
    }, 100);
};

// Add change listeners to mark unsaved
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const settingsInputs = document.querySelectorAll('#settingsModal input, #settingsModal textarea');
        settingsInputs.forEach(el => {
            el.addEventListener('input', markSettingsUnsaved);
        });
    }, 500);
});

// Keyboard Shortcuts for Settings Modal
document.addEventListener('keydown', (e) => {
    const settingsModal = document.getElementById('settingsModal');
    const isSettingsOpen = settingsModal && settingsModal.classList.contains('active');

    if (isSettingsOpen) {
        // ESC to close
        if (e.key === 'Escape') {
            e.preventDefault();
            closeSettings();
            showToast('Settings closed', 'info');
        }

        // Cmd+S (Mac) or Ctrl+S (Windows/Linux) to save
        if ((e.metaKey || e.ctrlKey) && e.key === 's') {
            e.preventDefault();
            saveSettings();
            showToast('Saving settings...', 'success');
        }
    }
});

// Toast Notification Helper
function showToast(message, type = 'info') {
    // Remove existing toast if any
    const existingToast = document.querySelector('.settings-toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast
    const toast = document.createElement('div');
    toast.className = `settings-toast toast-${type}`;
    toast.innerHTML = `
        <span class="material-icons">${type === 'success' ? 'check_circle' : 'info'}</span>
        <span>${message}</span>
    `;

    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after 2 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}
// --- RESCAN ---
function rescanLibrary() {
    const btn = document.getElementById('refreshBtn');
    const originalContent = btn.innerHTML;

    btn.innerHTML = '<span class="material-icons spin">sync</span> SCANNEN...';
    btn.style.pointerEvents = 'none';
    document.body.style.opacity = '0.5';

    fetch('/api/rescan')
        .then(response => {
            if (response.ok) return response.json();
            throw new Error('Scan failed');
        })
        .then(data => {
            console.log('Rescan complete', data);
            location.reload();
        })
        .catch(e => {
            console.error(e);
            alert('Fehler beim Scannen: ' + e.message);
            btn.innerHTML = originalContent;
            btn.style.pointerEvents = 'auto';
            document.body.style.opacity = '1';
        });
}

// --- SAVED VIEWS & CUSTOM FILTERS ---

function renderSavedViews() {
    const container = document.getElementById('savedViewsContainer');
    if (!container) return;

    container.innerHTML = '';

    const views = userSettings.saved_views || [];

    views.forEach(view => {
        const chip = document.createElement('button');
        chip.className = 'view-chip';
        // highlight if currently active? (complex to strict match, skip for now)

        chip.innerHTML = `
            <span onclick="loadView('${view.id}')">${view.name}</span>
            <span class="material-icons chip-delete" onclick="deleteView('${view.id}', event)">close</span>
        `;
        container.appendChild(chip);
    });
}

function saveCurrentView() {
    const name = prompt("Name für diese Ansicht:", "");
    if (!name) return;

    if (!userSettings.saved_views) userSettings.saved_views = [];

    const newView = {
        id: 'view_' + Date.now(),
        name: name,
        search: searchTerm,
        filter: currentFilter,
        codec: currentCodec,
        sort: currentSort,
        mode: workspaceMode,
        folder: currentFolder
    };

    userSettings.saved_views.push(newView);
    saveSettingsWithoutReload(); // We need a version that doesn't just print console
    renderSavedViews();
}

function loadView(id) {
    const view = (userSettings.saved_views || []).find(v => v.id === id);
    if (!view) return;

    // Apply settings
    searchTerm = view.search || "";
    document.getElementById('searchBar').value = searchTerm;

    currentFilter = view.filter || "all";
    document.getElementById('statusSelect').value = currentFilter;

    currentCodec = view.codec || "all";
    if (document.getElementById('codecSelect'))
        document.getElementById('codecSelect').value = currentCodec;

    currentSort = view.sort || "bitrate";
    document.getElementById('sortSelect').value = currentSort;

    if (view.mode) {
        setWorkspaceMode(view.mode); // Handles filterAndSort internally if changed
    }

    // If we rely on stored vars, we must call update
    filterAndSort();

    // Update visuals
    updateURL();
}

function deleteView(id, event) {
    if (event) event.stopPropagation();
    if (!confirm("Ansicht löschen?")) return;

    if (userSettings.saved_views) {
        userSettings.saved_views = userSettings.saved_views.filter(v => v.id !== id);
        saveSettingsWithoutReload();
        renderSavedViews();
    }
}

// reusing the logic from closeSettings but without closing UI
function saveSettingsWithoutReload() {
    fetch(`/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userSettings)
    }).then(r => r.json()).then(data => {
        if (data.success) {
            console.log("Settings saved (views)");
        }
    });
}

// --- OPTIMIZATION PANEL LOGIC ---
let currentOptAudio = 'enhanced';

function cinemaOptimize() {
    // Open the panel
    const panel = document.getElementById('optimizePanel');
    const infoContent = document.getElementById('cinemaInfoContent');

    // Check if we are already seeing it
    if (panel.classList.contains('active')) {
        closeOptimize();
        return;
    }

    if (window.ENABLE_OPTIMIZER !== true) return;

    // Populate Initial State
    currentOptAudio = 'enhanced'; // Reset to default
    updateOptAudioUI();
    clearTrim(); // Reset trim

    // Show panel
    panel.classList.add('active');
    document.querySelector('.cinema-actions').style.display = 'none';
}

function closeOptimize() {
    document.getElementById('optimizePanel').classList.remove('active');
    document.querySelector('.cinema-actions').style.display = 'flex';
}

function setOptAudio(mode) {
    currentOptAudio = mode;
    updateOptAudioUI();
}

function updateOptAudioUI() {
    document.getElementById('optAudioEnhanced').classList.toggle('selected', currentOptAudio === 'enhanced');
    document.getElementById('optAudioStandard').classList.toggle('selected', currentOptAudio === 'standard');

    const desc = document.getElementById('optAudioDesc');
    if (currentOptAudio === 'enhanced') desc.innerText = "Smart normalization & noise reduction";
    else desc.innerText = "Standard encoding (no filters)";
}

function setTrimFromHead(type) {
    const video = document.getElementById('cinemaVideo');
    const time = new Date(video.currentTime * 1000).toISOString().substr(11, 8);

    if (type === 'start') {
        document.getElementById('optTrimStart').value = time;
    } else {
        document.getElementById('optTrimEnd').value = time;
    }
}

function clearTrim() {
    document.getElementById('optTrimStart').value = "";
    document.getElementById('optTrimEnd').value = "";
}

function triggerOptimization() {
    if (!currentCinemaPath) return;

    const ss = document.getElementById('optTrimStart').value;
    const to = document.getElementById('optTrimEnd').value;

    // Simple validation
    // (Could add regex check for HH:MM:SS here but backend/ffmpeg handles partials well usually)

    const params = new URLSearchParams();
    params.set('path', currentCinemaPath);
    params.set('audio', currentOptAudio);
    if (ss) params.set('ss', ss);
    if (to) params.set('to', to);

    fetch(`/compress?${params.toString()}`)
        .then(() => {
            closeOptimize();
            // Show feedback?
            alert("Optimization started! Check the console or dashboard for progress.");
        })
        .catch(err => alert("Error starting optimization: " + err));
}

// --- GLOBAL UTILS ---
window.toggleLayout = toggleLayout;
// Expose for HTML access
window.cinemaOptimize = cinemaOptimize;
window.setOptAudio = setOptAudio;
window.setTrimFromHead = setTrimFromHead;
window.clearTrim = clearTrim;
window.closeOptimize = closeOptimize;
window.triggerOptimization = triggerOptimization;

// --- RUN ON LOAD ---
document.addEventListener('DOMContentLoaded', () => {
    // Check optimized status on backend
    // fetch('/status')...

    // Initial Filter
    if (document.getElementById('statusSelect'))
        setFilter(document.getElementById('statusSelect').value);

    // Handle URL Back/Forward
    window.onpopstate = (event) => {
        loadFromURL();
    };

    // Initial Load
    loadFromURL();

    // Render views
    setTimeout(renderSavedViews, 500);
});
