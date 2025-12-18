let currentFilter = 'all';
let currentCodec = 'all';
let currentSort = 'bitrate';
let currentLayout = 'grid'; // grid or list
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
    document.querySelectorAll('[id^="f-"]').forEach(b => b.classList.remove('active'));
    document.getElementById('f-' + f).classList.add('active');
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
    currentLayout = currentLayout === 'grid' ? 'list' : 'grid';
    const grid = document.getElementById('videoGrid');
    const btn = document.getElementById('toggleView');

    if (currentLayout === 'list') {
        grid.classList.add('list-view');
        btn.innerHTML = '<span class="material-icons">view_module</span>';
    } else {
        grid.classList.remove('list-view');
        btn.innerHTML = '<span class="material-icons">view_list</span>';
    }
    // Re-render current set to apply layout classes
    renderUI(false);
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
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeCinema(); });

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

// Init
window.onload = () => {
    filterAndSort();
};
