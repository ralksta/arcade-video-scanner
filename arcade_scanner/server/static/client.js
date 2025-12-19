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
        filterAndSort();
    }, 250);
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
    filterAndSort();
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
function updateURL() {
    const params = new URLSearchParams();

    // Add view mode
    if (currentLayout !== 'grid') {
        params.set('view', currentLayout);
    }

    // Add treemap folder if drilled down
    if (currentLayout === 'treemap' && treemapCurrentFolder) {
        params.set('folder', encodeURIComponent(treemapCurrentFolder));
    }

    // Build URL
    const url = params.toString() ? `?${params.toString()}` : '/';
    window.history.pushState({ layout: currentLayout, folder: treemapCurrentFolder }, '', url);
}

// Load state from URL on page load
function loadFromURL() {
    const params = new URLSearchParams(window.location.search);

    const viewMode = params.get('view') || 'grid';
    const folder = params.get('folder');

    // Set layout without updating URL (to avoid duplicate history entry)
    if (viewMode === 'treemap') {
        currentLayout = 'treemap';
        if (folder) {
            treemapCurrentFolder = decodeURIComponent(folder);
        }
        setLayout('treemap', true);
    } else if (viewMode === 'list') {
        setLayout('list', true);
    } else {
        setLayout('grid', true);
    }
}

// --- PERFORMANCE ENGINE: FILTER & SORT ---
function filterAndSort() {
    let vCount = 0; let tSize = 0;

    filteredVideos = window.ALL_VIDEOS.filter(v => {
        const name = v.FilePath.split(/[\\\\/]/).pop().toLowerCase();
        const status = v.Status;
        const codec = v.codec || 'unknown';
        const isHidden = v.hidden || false;
        const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
        const folder = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';

        const matchesFilter = (currentFilter === 'all' || status === currentFilter);
        const matchesCodec = (currentCodec === 'all' || codec.includes(currentCodec));
        const matchesSearch = name.includes(searchTerm) || v.FilePath.toLowerCase().includes(searchTerm);
        const matchesFolder = (currentFolder === 'all' || folder === currentFolder);

        let matchesWorkspace = true;
        if (workspaceMode === 'lobby') matchesWorkspace = !isHidden;
        else if (workspaceMode === 'vault') matchesWorkspace = isHidden;
        else if (workspaceMode === 'favorites') matchesWorkspace = v.favorite || false;

        const ok = matchesFilter && matchesCodec && matchesSearch && matchesWorkspace && matchesFolder;
        if (ok) { vCount++; tSize += v.Size_MB; }
        return ok;
    });

    // Sort
    filteredVideos.sort((a, b) => {
        if (currentSort === 'bitrate') return b.Bitrate_Mbps - a.Bitrate_Mbps;
        if (currentSort === 'size') return b.Size_MB - a.Size_MB;
        if (currentSort === 'name') return a.FilePath.localeCompare(b.FilePath);
        return 0;
    });

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

    nextBatch.forEach(video => {
        const card = createVideoCard(video);
        fragment.appendChild(card);
    });

    grid.appendChild(fragment);
    renderedCount += BATCH_SIZE;

    if (renderedCount < filteredVideos.length) {
        document.getElementById('loadingSentinel').style.opacity = '1';
    } else {
        document.getElementById('loadingSentinel').style.opacity = '0';
    }
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
                       data-src="http://localhost:${window.SERVER_PORT}/preview?name=${v.preview}">
                </video>
                <div class="quick-actions-overlay">
                    <a href="http://localhost:${window.SERVER_PORT}/reveal?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="quick-action-btn" title="Im Finder zeigen" onclick="event.stopPropagation()">
                        <span class="material-icons">visibility</span>
                    </a>
                    <div class="quick-action-btn" title="Wiedergeben" onclick="event.stopPropagation(); openCinema(this.closest('.card-media'))">
                        <span class="material-icons">play_arrow</span>
                    </div>
                    <div class="quick-action-btn hide-toggle-btn" title="Status ändern" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))">
                        <span class="material-icons">${v.hidden ? 'visibility' : 'visibility_off'}</span>
                    </div>
                    ${window.OPTIMIZER_AVAILABLE ? `
                    <a href="http://localhost:${window.SERVER_PORT}/compress?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="quick-action-btn" title="Optimieren" onclick="event.stopPropagation()">
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
                    <span class="badge ${v.Status}">${v.Status}</span>
                    <span class="badge hevc">${isHevc ? 'HEVC' : (v.codec || 'UNK').toUpperCase()}</span>
                </div>
                <div style="display:flex; gap:8px;">
                    <a href="http://localhost:${window.SERVER_PORT}/reveal?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="btn"><span class="material-icons" style="font-size:18px;">visibility</span></a>
                    ${window.OPTIMIZER_AVAILABLE ? `
                    <a href="http://localhost:${window.SERVER_PORT}/compress?path=${encodeURIComponent(v.FilePath)}" target="h_frame" class="btn">
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
    fetch(`http://localhost:${window.SERVER_PORT}/hide?path=` + encodeURIComponent(path) + `&state=${video.hidden}`);

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
    fetch(`http://localhost:${window.SERVER_PORT}/favorite?path=` + encodeURIComponent(path) + `&state=${video.favorite}`);

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
    fetch(`http://localhost:${window.SERVER_PORT}/batch_favorite?paths=` + encodeURIComponent(paths.join(',')) + `&state=${state}`);

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
function openCinema(container) {
    const card = container.closest('.video-card-container');
    const path = card.getAttribute('data-path');
    const fileName = path.split(/[\\\\/]/).pop();

    const modal = document.getElementById('cinemaModal');
    const video = document.getElementById('cinemaVideo');
    document.getElementById('cinemaTitle').innerText = fileName;

    video.src = `http://localhost:${window.SERVER_PORT}/stream?path=` + encodeURIComponent(path);
    modal.classList.add('active');
    video.load();
    video.play().catch(() => {
        video.muted = true;
        video.play();
    });
}

function closeCinema() {
    const modal = document.getElementById('cinemaModal');
    const video = document.getElementById('cinemaVideo');
    modal.classList.remove('active');
    video.pause();
    video.src = '';
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

function triggerBatchHide(state) {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));

    fetch(`http://localhost:${window.SERVER_PORT}/batch_hide?paths=` + encodeURIComponent(paths.join(',')) + `&state=${state}`);

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
        fetch(`http://localhost:${window.SERVER_PORT}/batch_compress?paths=` + encodeURIComponent(paths.join(',')));
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
    const blocks = squarify(folderData, 0, 0, canvas.width, canvas.height);

    // Folder color palette
    const folderColors = [
        '#581c87', '#1e3a8a', '#7f1d1d', '#14532d', '#78350f', '#374151'
    ];

    // Render folder blocks
    blocks.forEach((block, idx) => {
        // Base folder color
        ctx.fillStyle = folderColors[idx % folderColors.length];
        ctx.fillRect(block.x, block.y, block.width, block.height);

        // Status indicator bar at bottom (proportional HIGH vs OK)
        const barHeight = Math.min(8, block.height * 0.1);
        if (block.height > 30) {
            const highRatio = block.highCount / block.count;
            const highWidth = block.width * highRatio;

            // Orange for HIGH
            ctx.fillStyle = '#f59e0b';
            ctx.fillRect(block.x, block.y + block.height - barHeight, highWidth, barHeight);

            // Green for OK
            ctx.fillStyle = '#10b981';
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
    const blocks = squarify(treemapData, 0, 0, canvas.width, canvas.height);

    // Render video tiles with FLAT colors (no gradients)
    blocks.forEach(block => {
        const video = block.video;

        // Flat color by status
        ctx.fillStyle = video.Status === 'HIGH' ? '#f59e0b' : '#10b981';
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
                const mockContainer = {
                    closest: () => ({
                        getAttribute: () => block.video.FilePath
                    })
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
        document.getElementById('settingsBitrate').value = data.bitrate_threshold_kbps;

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
            item.className = 'exclusion-item';
            item.innerHTML = `
                <input type="checkbox" data-path="${exc.path}" ${isEnabled ? 'checked' : ''}>
                <div class="exclusion-info">
                    <div class="exclusion-path">${exc.path}</div>
                    <div class="exclusion-desc">${exc.desc}</div>
                </div>
            `;
            container.appendChild(item);
        });
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

function closeSettings() {
    document.getElementById('settingsModal').classList.remove('active');
}

async function saveSettings() {
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
        bitrate_threshold_kbps: parseInt(document.getElementById('settingsBitrate').value) || 15000
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            closeSettings();
            // Show success feedback
            const btn = document.getElementById('settingsBtn');
            btn.style.color = 'var(--gold)';
            setTimeout(() => { btn.style.color = ''; }, 2000);
        } else {
            alert('Fehler beim Speichern der Einstellungen');
        }
    } catch (e) {
        console.error('Failed to save settings:', e);
        alert('Fehler beim Speichern der Einstellungen');
    }
}

// Close settings modal on ESC
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('settingsModal').classList.contains('active')) {
        closeSettings();
    }
});
