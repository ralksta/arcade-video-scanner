let currentFilter = 'all';
let currentCodec = 'all';
let currentSort = 'bitrate';
let currentLayout = 'grid'; // grid, list, or treemap
let workspaceMode = 'lobby'; // lobby, mixed, vault
let currentFolder = 'all';
let searchTerm = '';
let activeSmartCollectionCriteria = null; // Stores current smart collection rules
let activeCollectionId = null; // Stores currently active collection ID for UI highlighting
let safeMode = localStorage.getItem('safe_mode') === 'true'; // Safe Mode State

let filteredVideos = [];
let renderedCount = 0;
const BATCH_SIZE = 40;

// --- THEME LOGIC ---
function toggleTheme() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');

    const icon = document.getElementById('themeIcon');
    if (icon) icon.textContent = isDark ? 'light_mode' : 'dark_mode';
}

// --- SAFE MODE LOGIC ---
// Safe Mode is now toggled via Settings modal

function isSensitive(video) {
    if (!video) return false;

    // 1. Check Tags
    const sensitiveTags = window.userSettings?.sensitive_tags || ['nsfw', 'adult', '18+'];
    if (video.tags && video.tags.some(t => sensitiveTags.includes(t.toLowerCase()))) {
        return true;
    }

    // 2. Check Paths
    const sensitiveDirs = window.userSettings?.sensitive_dirs || [];
    // Normalize paths for comparison (forward slashes)
    const vPath = video.FilePath.replace(/\\/g, '/').toLowerCase();

    for (const dir of sensitiveDirs) {
        if (!dir) continue;
        const cleanDir = dir.replace(/\\/g, '/').toLowerCase();
        if (vPath.startsWith(cleanDir)) {
            return true;
        }
    }

    return false;
}

// Init Theme
(function initTheme() {
    const saved = localStorage.getItem('theme');
    const isDark = saved ? saved === 'dark' : true; // Default to dark

    if (isDark) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }

    // Wait for DOM in case script runs early (though it's at end of body)
    setTimeout(() => {
        const icon = document.getElementById('themeIcon');
        if (icon) icon.textContent = isDark ? 'light_mode' : 'dark_mode';
    }, 0);
})();


// --- DEBOUNCED SEARCH ---
let searchTimeout;
function onSearchInput() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        searchTerm = document.getElementById('mobileSearchInput').value.toLowerCase();

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

// --- SEARCHABLE FOLDER DROPDOWN LOGIC ---


function setWorkspaceMode(mode) {
    try {
        console.log("Setting workspace mode:", mode);
        workspaceMode = mode;

        // Clear active smart collection when changing workspace (unless mode is explicitly 'collection' which we don't use yet)
        activeSmartCollectionCriteria = null;
        activeCollectionId = null; // Clear active visual state
        renderCollections(); // Re-render to remove active class

        // Set workspace data attribute for CSS theming
        document.body.setAttribute('data-workspace', mode);

        // Update nav items with enhanced active states
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.classList.remove('active');
            const indicator = btn.querySelector('.nav-indicator');
            if (indicator) indicator.classList.add('opacity-0');
        });

        const modeBtn = document.getElementById('m-' + mode);
        if (modeBtn) {
            modeBtn.classList.add('active');
            const indicator = modeBtn.querySelector('.nav-indicator');
            if (indicator) indicator.classList.remove('opacity-0');
        }

        // Legacy vault mode class
        if (mode === 'vault') document.body.classList.add('vault-mode');
        else document.body.classList.remove('vault-mode');

        // Update workspace indicator bar with actual colors
        const wsColors = {
            lobby: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
            favorites: { accent: '#F4B342', bg: 'rgba(244, 179, 66, 0.05)' },
            optimized: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
            review: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
            vault: { accent: '#8F0177', bg: 'rgba(143, 1, 119, 0.05)' }
        };
        const colors = wsColors[mode] || wsColors.lobby;
        const wsIndicator = document.querySelector('.workspace-indicator');
        if (wsIndicator) {
            wsIndicator.style.borderBottomColor = colors.accent;
            wsIndicator.style.backgroundColor = colors.bg;
        }

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

        filterAndSort(true); // Scroll to top on workspace change
        updateURL();
    } catch (e) {
        alert("Error in setWorkspaceMode: " + e.message + "\\n" + e.stack);
        console.error(e);
    }
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

    // Check for deep links (navigating back/forward)
    checkDeepLinks();
}

// --- PERFORMANCE ENGINE: FILTER & SORT ---
function filterAndSort(scrollToTop = false) {
    try {
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
                if (key.endsWith('_opt') || key.endsWith('_trim')) {
                    const suffixLen = key.endsWith('_opt') ? 4 : 5;
                    const baseKey = key.substring(0, key.length - suffixLen); // Strip _opt or _trim

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
                // 0. Smart Collection Override
                let matchesCollection = true;
                if (activeSmartCollectionCriteria) {
                    matchesCollection = evaluateCollectionMatch(v, activeSmartCollectionCriteria);
                }

                if (!matchesCollection) return false;

                const name = v.FilePath.split(/[\\/]/).pop().toLowerCase();
                const status = v.Status;
                const codec = v.codec || 'unknown';
                const isHidden = v.hidden || false;
                const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
                const folder = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';
                const videoTags = v.tags || [];

                // --- SAFE MODE CHECK ---
                if (safeMode && isSensitive(v)) {
                    return false;
                }

                let matchesFilter = false;
                if (currentFilter === 'all') matchesFilter = true;
                else if (currentFilter === 'optimized_files') matchesFilter = v.FilePath.includes('_opt') || v.FilePath.includes('_trim');
                else matchesFilter = (status === currentFilter);

                const matchesCodec = (currentCodec === 'all' || codec.includes(currentCodec));
                const matchesSearch = name.includes(searchTerm) || v.FilePath.toLowerCase().includes(searchTerm);
                const matchesFolder = (currentFolder === 'all' || folder === currentFolder);

                let matchesWorkspace = true;
                // Note: When in a Collection (activeSmartCollectionCriteria is set), 
                // typically workspaceMode is still 'lobby' or whatever was active.
                // Should collection override workspace mode rules? 
                // User expects collection contents. Usually collections span the whole library (except hidden/vault)?
                // Let's assume collection contents respect vault hiding unless collection specifically asks for hidden.
                // EXISTING BEHAVIOR: standard workspace rules apply. 

                if (workspaceMode === 'lobby') matchesWorkspace = !isHidden;
                else if (workspaceMode === 'vault') matchesWorkspace = isHidden;
                else if (workspaceMode === 'favorites') matchesWorkspace = v.favorite || false;

                // Tag filtering: if activeTags is not empty, video must have ALL selected tags
                let matchesTags = true;
                if (activeTags.length > 0) {
                    matchesTags = activeTags.every(tag => videoTags.includes(tag));
                }

                // Untagged filter: show only videos with no tags
                if (filterUntaggedOnly) {
                    matchesTags = videoTags.length === 0;
                }

                const ok = matchesFilter && matchesCodec && matchesSearch && matchesWorkspace && matchesFolder && matchesTags;
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

        const countEl = document.getElementById('count-total');
        if (countEl) countEl.innerText = vCount;

        const sizeEl = document.getElementById('size-total');
        if (sizeEl) sizeEl.innerText = formatSize(tSize);

        renderUI(true, scrollToTop);
    } catch (e) {
        alert("Error in filterAndSort: " + e.message + "\\n" + e.stack);
        console.error(e);
    }
}

function formatSize(mb) {
    if (mb > 1024 * 1024) return (mb / (1024 * 1024)).toFixed(2) + " TB";
    if (mb > 1024) return (mb / 1024).toFixed(2) + " GB";
    return mb.toFixed(0) + " MB";
}

// --- PERFORMANCE ENGINE: INFINITE SCROLL ---
function renderUI(reset, scrollToTop = false) {
    // If in treemap mode, re-render treemap instead
    if (currentLayout === 'treemap') {
        renderTreemap();
        return;
    }

    const grid = document.getElementById('videoGrid');
    if (reset) {
        grid.innerHTML = '';
        renderedCount = 0;
        // Only scroll to top when explicitly requested (e.g., workspace change)
        // This prevents scroll-jumping when filtering/sorting
        if (scrollToTop) {
            window.scrollTo({ top: 0, behavior: 'instant' });
        }
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
    // col-span-1 md:col-span-2 relative w-full bg-[#14141c] rounded-xl overflow-hidden border border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container comparison-card flex flex-col md:flex-row p-4 gap-4
    container.className = 'col-span-1 md:col-span-2 relative w-full bg-[#14141c] rounded-xl overflow-hidden border border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container comparison-card flex flex-col md:flex-row p-4 gap-4';

    // Explicitly set grid span here, though class handles it usually, but existing grid logic might override without it if it was inline style before
    container.style.gridColumn = "span 2";

    // Format Display Stats
    const formatSize = (mb) => mb.toFixed(1) + " MB";
    const formatBitrate = (mbps) => mbps.toFixed(1) + " Mbps";

    container.innerHTML = `
        <!-- Original Column -->
        <div class="flex-1 min-w-0 flex flex-col gap-2">
            <div class="text-xs font-bold text-gray-500 uppercase tracking-widest flex justify-between">
                <span>Original</span>
                <span class="text-[9px] bg-white/5 px-1 rounded">${orig.codec}</span>
            </div>
            
            <div class="relative w-full aspect-video bg-black rounded-lg overflow-hidden cursor-pointer group" onclick="openCinema(this)" data-path="${orig.FilePath}">
                 <img src="/thumbnails/${orig.thumb}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" loading="lazy">
                 <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span class="material-icons text-white text-3xl drop-shadow-lg">play_arrow</span>
                 </div>
                 <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[10px] bg-black/80 text-white font-mono font-bold backdrop-blur">${formatSize(orig.Size_MB)}</span>
            </div>
            
            <div class="text-[10px] text-gray-400 font-mono flex justify-between px-1">
                <span class="truncate font-medium text-gray-300" title="${orig.FilePath}">${orig.FilePath.split(/[\\\\/]/).pop()}</span>
                <span>${orig.Bitrate_Mbps.toFixed(1)} Mb/s</span>
            </div>
            
            <button class="text-xs text-gray-500 hover:text-white flex items-center gap-1 px-1 transition-colors" onclick="window.open('/reveal?path=${encodeURIComponent(orig.FilePath)}', 'h_frame')">
                <span class="material-icons text-[12px]">folder_open</span> Reveal
            </button>
        </div>

        <!-- Stats Center -->
        <div class="w-full md:w-32 flex flex-col items-center justify-center gap-1 border-y md:border-y-0 md:border-x border-white/5 py-4 md:py-0 bg-white/[0.02] rounded-lg md:bg-transparent">
             <div class="text-2xl font-bold ${isSmaller ? 'text-green-400 drop-shadow-[0_0_8px_rgba(76,217,100,0.4)]' : 'text-red-500'} font-mono tracking-tighter">${diffPct.toFixed(1)}%</div>
             <div class="text-xs text-gray-500 font-mono mb-2">${diffMB.toFixed(1)} MB</div>
             
             <button class="w-full py-2 rounded-lg bg-arcade-cyan/20 text-arcade-cyan hover:bg-arcade-cyan hover:text-black border border-arcade-cyan/30 hover:shadow-[0_0_10px_rgba(0,255,208,0.3)] text-xs font-bold transition-all flex items-center justify-center gap-1 mt-1" onclick="keepOptimized('${encodeURIComponent(orig.FilePath)}', '${encodeURIComponent(opt.FilePath)}')">
                <span class="material-icons text-[14px]">check</span> KEEP
             </button>
             <button class="w-full py-2 rounded-lg bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5 text-xs font-bold transition-all flex items-center justify-center gap-1" onclick="discardOptimized('${encodeURIComponent(opt.FilePath)}')">
                <span class="material-icons text-[14px]">delete</span> DISCARD
             </button>
        </div>

        <!-- Optimized Column -->
        <div class="flex-1 min-w-0 flex flex-col gap-2">
            <div class="text-xs font-bold text-arcade-cyan uppercase tracking-widest flex justify-between">
                <span>Optimized</span>
                <span class="text-[9px] bg-arcade-cyan/10 text-arcade-cyan px-1 rounded border border-arcade-cyan/20">${opt.codec}</span>
            </div>
            
             <div class="relative w-full aspect-video bg-black rounded-lg overflow-hidden cursor-pointer group border border-arcade-cyan/30 shadow-[0_0_10px_rgba(0,255,208,0.05)]" onclick="openCinema(this)" data-path="${opt.FilePath}">
                 <img src="/thumbnails/${opt.thumb}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" loading="lazy">
                 <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span class="material-icons text-white text-3xl drop-shadow-lg">play_arrow</span>
                 </div>
                 <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[10px] bg-arcade-cyan/20 text-arcade-cyan font-mono font-bold backdrop-blur border border-arcade-cyan/30">${formatSize(opt.Size_MB)}</span>
            </div>
            
            <div class="text-[10px] text-gray-400 font-mono flex justify-between px-1">
                <span class="truncate font-medium text-gray-300" title="${opt.FilePath}">${opt.FilePath.split(/[\\\\/]/).pop()}</span>
                <span>${opt.Bitrate_Mbps.toFixed(1)} Mb/s</span>
            </div>
             <button class="text-xs text-gray-500 hover:text-white flex items-center gap-1 px-1 transition-colors" onclick="window.open('/reveal?path=${encodeURIComponent(opt.FilePath)}', 'h_frame')">
                <span class="material-icons text-[12px]">folder_open</span> Reveal
            </button>
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

// Helper for duration formatting
function formatDuration(seconds) {
    if (!seconds) return '';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return h > 0 ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}` : `${m}:${s.toString().padStart(2, '0')}`;
}

function createVideoCard(v) {
    const container = document.createElement('div');
    // Using utility classes for the card wrapper
    // group relative w-full bg-[#14141c] rounded-xl overflow-hidden border border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container
    container.className = 'group relative w-full bg-[#14141c] rounded-xl overflow-hidden border border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container flex flex-col';
    container.setAttribute('data-path', v.FilePath); // Keep this for JS logic

    const isHevc = (v.codec || '').includes('hevc') || (v.codec || '').includes('h265');
    const barW = Math.min(100, (v.Bitrate_Mbps / 25) * 100);
    const fileName = v.FilePath.split(/[\\\\/]/).pop();
    const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
    const dirName = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';

    container.innerHTML = `
        <!-- Thumbnail (Card Media) -->
        <div class="card-media relative w-full aspect-video bg-black overflow-hidden group cursor-pointer" 
             onclick="openCinema(this)">
             
             <!-- Corner Checkbox -->
             <div class="absolute top-2 left-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                <input type="checkbox" class="w-4 h-4 rounded border-gray-600 bg-black/50 text-arcade-cyan focus:ring-0 cursor-pointer" aria-label="Select" onclick="event.stopPropagation(); toggleSelection(this, event, '${v.FilePath.replace(/'/g, "\\'")}')">
             </div>

             <!-- Favorite Star -->
             <button class="favorite-btn absolute top-2 right-2 z-20 w-8 h-8 rounded-full bg-black/40 backdrop-blur hover:bg-black/60 flex items-center justify-center transition-all ${v.favorite ? 'text-arcade-gold active scale-110' : 'text-gray-400 opacity-0 group-hover:opacity-100'}"
                onclick="event.stopPropagation(); toggleFavorite(this.closest('.video-card-container'))">
                <span class="material-icons text-lg">${v.favorite ? 'star' : 'star_border'}</span>
             </button>

             <img src="/thumbnails/${v.thumb}" class="w-full h-full object-cover transform transition-transform duration-700 group-hover:scale-110" loading="lazy">

             
             <!-- Quick Actions Overlay -->
             <div class="hidden md:flex absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity items-center justify-center gap-3">
                 <button class="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="Reveal" onclick="event.stopPropagation(); window.open('/reveal?path=${encodeURIComponent(v.FilePath)}', 'h_frame')">
                    <span class="material-icons">folder_open</span>
                 </button>
                 <button class="w-12 h-12 rounded-full bg-arcade-cyan/20 hover:bg-arcade-cyan text-arcade-cyan hover:text-black border border-arcade-cyan/50 flex items-center justify-center backdrop-blur transition-all transform hover:scale-110 shadow-[0_0_15px_rgba(0,255,208,0.3)]" title="Play" onclick="event.stopPropagation(); openCinema(this.closest('.card-media'))">
                    <span class="material-icons text-3xl">play_arrow</span>
                 </button>
                 <button class="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="${v.hidden ? 'Restore' : 'Move to Vault'}" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))">
                    <span class="material-icons">${v.hidden ? 'unarchive' : 'archive'}</span>
                 </button>
                  ${(window.userSettings?.enable_optimizer !== false && window.ENABLE_OPTIMIZER !== false) ? `
                 <button class="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="Optimize" onclick="event.stopPropagation(); window.open('/compress?path=${encodeURIComponent(v.FilePath)}', 'h_frame')">
                    <span class="material-icons">bolt</span>
                 </button>` : ''}
             </div>
             
             <!-- Badges -->
             <div class="absolute bottom-2 left-2 flex gap-1 flex-wrap pr-12 pointer-events-none">
                 <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-black/60 text-white backdrop-blur border border-white/10">${v.Status}</span>
                 ${isHevc ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-arcade-cyan/20 text-arcade-cyan backdrop-blur border border-arcade-cyan/30">HEVC</span>' : ''}
                 ${fileName.includes('_opt.') ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-500/20 text-green-400 backdrop-blur border border-green-500/30">OPT</span>' : ''}
             </div>
             
             <!-- Duration -->
             <span class="absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-black/80 text-white backdrop-blur pointer-events-none">
                ${v.Duration_Sec ? formatDuration(v.Duration_Sec) : ''}
             </span>
        </div>

        <!-- Content -->
        <div class="p-3 flex flex-col gap-1">
            <h3 class="text-sm font-medium text-gray-200 line-clamp-1 group-hover:text-arcade-cyan transition-colors" title="${fileName}">${fileName}</h3>
            <p class="text-[11px] text-gray-500 truncate" title="${v.FilePath}">${dirName}</p>
            
            ${renderVideoCardTags(v.tags || [])}
            
            <div class="flex items-center justify-between mt-1 text-xs font-mono text-gray-400">
                <div class="flex items-center gap-2">
                    <span class="bg-white/5 px-1.5 py-0.5 rounded text-[10px]">${v.Size_MB.toFixed(0)} MB</span>
                    <span>${v.Bitrate_Mbps.toFixed(1)} Mb/s</span>
                </div>
                
                <button class="text-gray-600 hover:text-white transition-colors hide-toggle-btn" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))">
                    <span class="material-icons text-[16px]">${v.hidden ? 'visibility' : 'visibility_off'}</span>
                </button>
            </div>
            
            <!-- Progress Bar -->
            <div class="mt-2 h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-arcade-cyan to-blue-500" style="width: ${barW}%"></div>
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
        setTimeout(() => {
            filterAndSort();
            renderCollections(); // Update sidebar counts
        }, 300);
    } else {
        renderCollections(); // Update immediately if not animating out
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
        setTimeout(() => {
            filterAndSort();
            renderCollections(); // Update sidebar counts
        }, 300);
    } else {
        renderCollections(); // Update immediately
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

    // Populate tag picker
    updateCinemaTags();
}

function closeCinema() {
    const modal = document.getElementById('cinemaModal');
    const video = document.getElementById('cinemaVideo');
    const infoPanel = document.getElementById('cinemaInfoPanel');
    const tagPanel = document.getElementById('cinemaTagPanel');
    modal.classList.remove('active');
    infoPanel.classList.remove('active');
    if (tagPanel) tagPanel.classList.add('hidden');
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
            <span class="info-label">Format</span>
            <span class="info-value">${v.Container || 'unknown'}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Resolution</span>
            <span class="info-value">${v.Width} × ${v.Height}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Duration</span>
            <span class="info-value">${formatDuration(v.Duration_Sec)}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Frame Rate</span>
            <span class="info-value">${v.FrameRate || '?'} fps</span>
        </div>
        <div class="info-row">
            <span class="info-label">Video Codec</span>
            <span class="info-value">${v.codec} ${(v.Profile) ? `(${v.Profile})` : ''}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Pixel Format</span>
            <span class="info-value">${v.PixelFormat || '-'}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Audio Codec</span>
            <span class="info-value">${v.AudioCodec || '-'}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Channels</span>
            <span class="info-value">${v.AudioChannels || '-'}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Bitrate</span>
            <span class="info-value">${(v.Bitrate_Mbps * 1000).toLocaleString()} kbps</span>
        </div>
        <div class="info-row">
            <span class="info-label">File Size</span>
            <span class="info-value">${formatSize(v.Size_MB)}</span>
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

// --- BATCH SELECTION HELPERS ---
let lastCheckedPath = null;

function toggleSelection(checkbox, event, path) {
    if (event.shiftKey && lastCheckedPath) {
        // Shift+Click Logic
        const currentIndex = filteredVideos.findIndex(v => v.FilePath === path);
        const lastIndex = filteredVideos.findIndex(v => v.FilePath === lastCheckedPath);

        if (currentIndex !== -1 && lastIndex !== -1) {
            const start = Math.min(currentIndex, lastIndex);
            const end = Math.max(currentIndex, lastIndex);

            const targetState = checkbox.checked;

            // Apply to range
            for (let i = start; i <= end; i++) {
                const video = filteredVideos[i];
                const container = document.querySelector(`.video-card-container[data-path="${CSS.escape(video.FilePath)}"]`);
                if (container) {
                    const cb = container.querySelector('input[type="checkbox"]');
                    if (cb) cb.checked = targetState;
                }
            }
        }
    }

    // Update state
    if (checkbox.checked) {
        lastCheckedPath = path;
    } else {
        lastCheckedPath = null; // Reset if unchecked? Or keep last checked? Keeping enables complex patterns.
        // Usually shift-selection anchors on the last *interaction*.
        lastCheckedPath = path;
    }

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

// --- BATCH TAGGING (Modern Redesign) ---
let batchTagActions = {}; // { tagName: 'add' | 'remove' | null }
let batchTagSearchTerm = '';
let batchTagFocusIndex = -1;

function openBatchTagModal() {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    if (selected.length === 0) return;

    batchTagActions = {};
    batchTagSearchTerm = '';
    batchTagFocusIndex = -1;

    let modal = document.getElementById('batchTagModal');
    if (!modal) {
        createBatchTagModal();
        modal = document.getElementById('batchTagModal');
    }

    renderBatchTagOptions();
    if (modal) modal.style.display = 'flex';

    // Focus search input
    setTimeout(() => {
        document.getElementById('batchTagSearch')?.focus();
    }, 100);
}

function createBatchTagModal() {
    const modal = document.createElement('div');
    modal.id = 'batchTagModal';
    modal.className = 'fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4';
    modal.style.display = 'none';
    modal.innerHTML = `
        <div class="w-full max-w-md bg-[#1a1a1e] rounded-2xl shadow-2xl border border-white/10 overflow-hidden">
            <!-- Header -->
            <div class="px-5 py-4 border-b border-white/5 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <span class="material-icons text-purple-400 text-xl">sell</span>
                    <div>
                        <h2 class="font-semibold text-white">Batch Tagging</h2>
                        <p class="text-xs text-gray-500">Editing <strong id="batchTagCount" class="text-purple-400">0</strong> items</p>
                    </div>
                </div>
                <button onclick="closeBatchTagModal()" class="text-gray-500 hover:text-white p-1 rounded hover:bg-white/10 transition-colors">
                    <span class="material-icons">close</span>
                </button>
            </div>
            
            <!-- Search Bar -->
            <div class="px-5 py-3 border-b border-white/5">
                <div class="relative">
                    <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-lg">search</span>
                    <input type="text" 
                           id="batchTagSearch" 
                           class="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:border-purple-500 focus:outline-none" 
                           placeholder="Search tags..." 
                           oninput="handleBatchTagSearch(this.value)"
                           onkeydown="handleBatchTagKeyNav(event)">
                </div>
            </div>
            
            <!-- Tag Cloud -->
            <div class="px-5 py-4 flex flex-wrap gap-2 max-h-[200px] overflow-y-auto" id="batchTagOptions">
                <!-- Populated by JS -->
            </div>
            
            <!-- Add New Tag -->
            <div class="px-5 py-3 border-t border-white/5 bg-black/20 flex gap-2">
                <div class="relative flex-1">
                    <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-lg">add</span>
                    <input type="text" 
                           id="batchTagNewInput" 
                           class="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:border-purple-500 focus:outline-none" 
                           placeholder="New tag name..."
                           onkeydown="handleBatchTagNewKeydown(event)">
                </div>
                <button onclick="createAndApplyNewTag()" class="px-4 py-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition-colors">
                    Add
                </button>
            </div>
            
            <!-- Footer -->
            <div class="px-5 py-4 border-t border-white/5 flex gap-3">
                <button onclick="closeBatchTagModal()" class="flex-1 py-2.5 bg-white/5 text-gray-400 border border-white/10 rounded-lg text-sm font-medium hover:bg-white/10 hover:text-white transition-colors">
                    Cancel
                </button>
                <button onclick="applyBatchTags()" class="flex-1 py-2.5 bg-purple-500 text-white rounded-lg text-sm font-semibold hover:bg-purple-400 transition-colors flex items-center justify-center gap-2">
                    <span class="material-icons text-sm">check</span>
                    Save Changes
                </button>
            </div>
        </div>
    `;

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeBatchTagModal();
    });

    document.body.appendChild(modal);
}

function handleBatchTagSearch(value) {
    batchTagSearchTerm = value.toLowerCase();
    batchTagFocusIndex = -1;
    renderBatchTagOptions();
}

function handleBatchTagKeyNav(event) {
    const chips = document.querySelectorAll('.batch-tag-chip');
    if (chips.length === 0) return;

    if (event.key === 'ArrowDown') {
        event.preventDefault();
        batchTagFocusIndex = Math.min(batchTagFocusIndex + 1, chips.length - 1);
        chips[batchTagFocusIndex]?.focus();
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        batchTagFocusIndex = Math.max(batchTagFocusIndex - 1, 0);
        chips[batchTagFocusIndex]?.focus();
    } else if (event.key === 'Enter' && batchTagFocusIndex >= 0) {
        event.preventDefault();
        chips[batchTagFocusIndex]?.click();
    }
}

function handleBatchTagChipKeydown(event, tagName) {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleBatchTagOption(tagName);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        handleBatchTagKeyNav(event);
    }
}

function handleBatchTagNewKeydown(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        createAndApplyNewTag();
    }
}

async function createAndApplyNewTag() {
    const input = document.getElementById('batchTagNewInput');
    const name = input?.value.trim();
    if (!name) return;

    // Check if tag already exists
    if (availableTags.some(t => t.name.toLowerCase() === name.toLowerCase())) {
        batchTagActions[name] = 'add';
        input.value = '';
        renderBatchTagOptions();
        return;
    }

    // Create new tag with random color
    const colors = ['#9D5BFF', '#00ffd0', '#F4B342', '#DE1A58', '#22c55e', '#06b6d4', '#ec4899'];
    const randomColor = colors[Math.floor(Math.random() * colors.length)];

    const newTag = { name: name, color: randomColor };
    availableTags.push(newTag);

    userSettings.available_tags = availableTags;
    await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userSettings)
    });

    batchTagActions[name] = 'add';
    input.value = '';
    renderBatchTagOptions();
}

function getSelectedVideoPaths() {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    return Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));
}

function getTagStateForSelection(tagName) {
    const paths = getSelectedVideoPaths();
    if (paths.length === 0) return 'none';

    let hasCount = 0;
    paths.forEach(path => {
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (video && (video.tags || []).includes(tagName)) {
            hasCount++;
        }
    });

    if (hasCount === 0) return 'none';
    if (hasCount === paths.length) return 'all';
    return 'some';
}

function renderBatchTagOptions() {
    const container = document.getElementById('batchTagOptions');
    const countEl = document.getElementById('batchTagCount');

    if (!container) return;

    const paths = getSelectedVideoPaths();
    if (countEl) countEl.textContent = paths.length;

    const filteredTags = availableTags.filter(tag =>
        tag.name.toLowerCase().includes(batchTagSearchTerm)
    );

    if (filteredTags.length === 0 && availableTags.length === 0) {
        container.innerHTML = `
        < div class="batch-tag-empty" >
                <span class="material-icons">label_off</span>
                <p>No tags yet</p>
                <p class="text-xs text-gray-600">Create your first tag below</p>
            </div >
        `;
        return;
    }

    if (filteredTags.length === 0) {
        container.innerHTML = `
        < div class="batch-tag-empty" >
                <span class="material-icons">search_off</span>
                <p>No tags match "${batchTagSearchTerm}"</p>
            </div >
        `;
        return;
    }

    container.innerHTML = filteredTags.map((tag, index) => {
        const currentState = getTagStateForSelection(tag.name);
        const action = batchTagActions[tag.name];

        let displayState = currentState;
        if (action === 'add') displayState = 'all';
        else if (action === 'remove') displayState = 'none';

        const hasAction = action !== undefined && action !== null;

        let checkIcon, bgColor, borderColor, textColor;
        if (displayState === 'all') {
            checkIcon = 'check_box';
            bgColor = 'bg-green-500/15';
            borderColor = 'border-green-500/30';
            textColor = 'text-green-400';
        } else if (displayState === 'some') {
            checkIcon = 'indeterminate_check_box';
            bgColor = 'bg-yellow-500/15';
            borderColor = 'border-yellow-500/30';
            textColor = 'text-yellow-400';
        } else {
            checkIcon = 'check_box_outline_blank';
            bgColor = 'bg-white/5';
            borderColor = 'border-white/10';
            textColor = 'text-gray-400';
        }

        const pendingGlow = hasAction ? 'shadow-[0_0_12px_rgba(168,85,247,0.4)]' : '';

        return `
            <button class="inline-flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all text-sm font-medium ${bgColor} ${borderColor} ${textColor} ${pendingGlow} hover:bg-white/10"
                    onclick="toggleBatchTagOption('${tag.name}')"
                    onkeydown="handleBatchTagChipKeydown(event, '${tag.name}')"
                    tabindex="${index === batchTagFocusIndex ? '0' : '-1'}">
                <span class="material-icons text-lg">${checkIcon}</span>
                <span class="w-2 h-2 rounded-full shrink-0" style="background-color: ${tag.color}"></span>
                <span>${tag.name}</span>
                ${hasAction ? '<span class="text-purple-400 font-bold ml-1">•</span>' : ''}
            </button>
        `;
    }).join('');
}

function toggleBatchTagOption(tagName) {
    const currentState = getTagStateForSelection(tagName);
    const currentAction = batchTagActions[tagName];

    if (currentAction === 'add') {
        batchTagActions[tagName] = 'remove';
    } else if (currentAction === 'remove') {
        batchTagActions[tagName] = null;
    } else {
        if (currentState === 'all') {
            batchTagActions[tagName] = 'remove';
        } else {
            batchTagActions[tagName] = 'add';
        }
    }

    renderBatchTagOptions();
}

function closeBatchTagModal() {
    const modal = document.getElementById('batchTagModal');
    if (modal) modal.style.display = 'none';
    batchTagActions = {};
    batchTagSearchTerm = '';
}

async function applyBatchTags() {
    const actions = Object.entries(batchTagActions).filter(([_, action]) => action === 'add' || action === 'remove');

    if (actions.length === 0) {
        closeBatchTagModal();
        return;
    }

    const tagsToAdd = actions.filter(([_, a]) => a === 'add').map(([name]) => name);
    const tagsToRemove = actions.filter(([_, a]) => a === 'remove').map(([name]) => name);

    const paths = getSelectedVideoPaths();
    let successCount = 0;

    const saveBtn = document.querySelector('.batch-tag-save');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="material-icons animate-spin text-sm">refresh</span> Saving...';
    }

    for (const path of paths) {
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (!video) continue;

        let currentTags = [...(video.tags || [])];

        tagsToAdd.forEach(t => {
            if (!currentTags.includes(t)) currentTags.push(t);
        });

        currentTags = currentTags.filter(t => !tagsToRemove.includes(t));

        try {
            const res = await fetch('/api/video/tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path, tags: currentTags })
            });
            if (res.ok) {
                video.tags = currentTags;
                successCount++;
            }
        } catch (err) {
            console.error('Failed to update tags:', path, err);
        }
    }

    closeBatchTagModal();
    clearSelection();

    filterAndSort(true);
    renderCollections();

    const addedStr = tagsToAdd.length > 0 ? `+ ${tagsToAdd.join(', ')} ` : '';
    const removedStr = tagsToRemove.length > 0 ? `- ${tagsToRemove.join(', ')} ` : '';
    console.log(`✅ Updated ${successCount}/${paths.length} videos: ${addedStr} ${removedStr}`.trim());
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
    document.getElementById('mobileSearchInput').value = '';
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
        document.getElementById('settingsMinSize').value = data.min_size_mb || 100;
        document.getElementById('settingsBitrate').value = data.bitrate_threshold_kbps || 15000;

        // Privacy
        document.getElementById('settingsSafeMode').checked = safeMode;
        document.getElementById('settingsSensitiveDirs').value = (data.sensitive_dirs || []).join('\n');
        document.getElementById('settingsSensitiveTags').value = (data.sensitive_tags || []).join(', ');
        document.getElementById('settingsSensitiveCollections').value = (data.sensitive_collections || []).join('\n');

        // New Features
        document.getElementById('settingsTheme').value = data.theme || 'arcade';
        document.getElementById('settingsFunFacts').checked = data.enable_fun_facts ?? true;
        const optimizerCheckbox = document.getElementById('settingsOptimizer');
        if (optimizerCheckbox) optimizerCheckbox.checked = data.enable_optimizer !== false;

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

        document.getElementById('statTotal').textContent = `${stats.total_mb} MB`;
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

function closeSettings() {
    document.getElementById('settingsModal').classList.remove('active');
}

async function saveSettings() {
    const saveBtn = document.getElementById('saveSettingsBtn');
    const saveIcon = saveBtn?.querySelector('.save-icon');
    const saveSpinner = saveBtn?.querySelector('.save-spinner');
    const saveText = saveBtn?.querySelector('.save-text');

    // Show loading state
    if (saveBtn) saveBtn.disabled = true;
    if (saveIcon) saveIcon.classList.add('hidden');
    if (saveSpinner) saveSpinner.classList.remove('hidden');
    if (saveText) saveText.textContent = 'Saving...';

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
        saved_views: window.userSettings?.saved_views || [],
        sensitive_dirs: document.getElementById('settingsSensitiveDirs').value.split('\n').map(s => s.trim()).filter(s => s),
        sensitive_tags: document.getElementById('settingsSensitiveTags').value.split(',').map(s => s.trim()).filter(s => s),
        sensitive_collections: document.getElementById('settingsSensitiveCollections').value.split(/[\n,]/).map(s => s.trim()).filter(s => s),
        min_size_mb: parseInt(document.getElementById('settingsMinSize').value) || 100,
        bitrate_threshold_kbps: parseInt(document.getElementById('settingsBitrate').value) || 15000,

        enable_fun_facts: document.getElementById('settingsFunFacts')?.checked || false,
        enable_optimizer: document.getElementById('settingsOptimizer')?.checked ?? true,
        enable_deovr: document.getElementById('settingsDeoVR')?.checked || false,
        theme: document.getElementById('settingsTheme').value || 'arcade'
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        // Reset button state
        if (saveBtn) saveBtn.disabled = false;
        if (saveIcon) saveIcon.classList.remove('hidden');
        if (saveSpinner) saveSpinner.classList.add('hidden');
        if (saveText) saveText.textContent = 'Save';

        if (response.ok) {
            // Hide unsaved indicator
            const unsavedIndicator = document.getElementById('unsavedIndicator');
            if (unsavedIndicator) unsavedIndicator.style.opacity = '0';

            // Update Theme immediately
            const newTheme = document.getElementById('settingsTheme').value;
            if (newTheme) document.documentElement.setAttribute('data-theme', newTheme);


            // Show success toast
            showSettingsToast();

            // Close after brief delay to show success state
            setTimeout(() => {
                closeSettings();
            }, 1200);

            // Update local state immediately
            window.userSettings = {
                ...window.userSettings,
                ...settings
            };

            // Update Safe Mode State separately (localStorage)
            const newSafeMode = document.getElementById('settingsSafeMode').checked;
            if (newSafeMode !== safeMode) {
                safeMode = newSafeMode;
                localStorage.setItem('safe_mode', safeMode);
            }

            // Always refresh content to reflect potential changes in sensitive lists or other settings
            filterAndSort();
            renderCollections();
        } else {
            showSettingsToast('Error saving settings', true);
        }
    } catch (e) {
        console.error('Failed to save settings:', e);
        // Reset button state
        if (saveBtn) saveBtn.disabled = false;
        if (saveIcon) saveIcon.classList.remove('hidden');
        if (saveSpinner) saveSpinner.classList.add('hidden');
        if (saveText) saveText.textContent = 'Save';

        showSettingsToast('Error saving settings', true);
    }
}

function showSettingsToast(message = 'Settings saved', isError = false) {
    const toast = document.getElementById('settingsToast');
    if (!toast) return;

    const toastContent = toast.querySelector('div');
    if (toastContent) {
        toastContent.className = isError
            ? 'bg-red-500/95 backdrop-blur text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3'
            : 'bg-green-500/95 backdrop-blur text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3';
        const icon = toastContent.querySelector('.material-icons');
        const text = toastContent.querySelector('span:last-child');
        if (icon) icon.textContent = isError ? 'error' : 'check_circle';
        if (text) text.textContent = message;
    }

    toast.classList.remove('translate-y-20', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');

    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
        toast.classList.remove('translate-y-0', 'opacity-100');
    }, 3000);
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

            // Check for deep links (e.g., /collections/Name)
            checkDeepLinks();
        }
    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

function checkDeepLinks() {
    const path = window.location.pathname;
    if (path.startsWith('/collections/')) {
        const nameEncoded = path.substring('/collections/'.length);
        const name = decodeURIComponent(nameEncoded);

        const collections = window.userSettings.smart_collections || [];
        const collection = collections.find(c => c.name === name);

        if (collection) {
            console.log("Deep link to collection:", collection.name);
            applyCollection(collection.id);
        } else {
            console.warn("Deep link collection not found:", name);
            // Default to lobby if not found
            // setWorkspaceMode('lobby'); // Standard default
            history.replaceState(null, '', '/');
        }
    }
}

// === NEW SETTINGS UI NAVIGATION ===

function initSettingsNavigation() {
    // Use more specific selector to only target settings modal nav items
    const settingsModal = document.getElementById('settingsModal');
    if (!settingsModal) return;

    const navItems = settingsModal.querySelectorAll('.settings-nav-item[data-section]');
    const contentSections = settingsModal.querySelectorAll('.content-section');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const sectionId = item.dataset.section;
            if (!sectionId) return;

            // Update active nav item and indicator
            navItems.forEach(nav => {
                nav.classList.remove('active', 'text-white', 'bg-white/5');
                nav.classList.add('text-gray-400');
                const indicator = nav.querySelector('.active-indicator');
                if (indicator) indicator.classList.add('opacity-0');
            });
            item.classList.add('active', 'text-white', 'bg-white/5');
            item.classList.remove('text-gray-400');
            const activeIndicator = item.querySelector('.active-indicator');
            if (activeIndicator) activeIndicator.classList.remove('opacity-0');

            // Show corresponding content - toggle hidden class
            contentSections.forEach(section => {
                section.classList.add('hidden');
                section.classList.remove('active');
            });
            const targetSection = document.getElementById(`content-${sectionId}`);
            if (targetSection) {
                targetSection.classList.remove('hidden');
                targetSection.classList.add('active');
            }

            // Update header
            updateSettingsHeader(sectionId);
        });
    });

    // Set initial active state
    const initialActive = settingsModal.querySelector('.settings-nav-item.active');
    if (initialActive) {
        const indicator = initialActive.querySelector('.active-indicator');
        if (indicator) indicator.classList.remove('opacity-0');
        initialActive.classList.add('text-white', 'bg-white/5');
        initialActive.classList.remove('text-gray-400');
    }
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
        },
        'privacy': {
            title: 'Privacy & Safety',
            subtitle: 'Configure Safe Mode and hidden content'
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
    const indicator = document.getElementById('unsavedIndicator');
    if (indicator) {
        indicator.style.opacity = '1';
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
    document.getElementById('mobileSearchInput').value = searchTerm;

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

// --- SMART COLLECTIONS ---
let editingCollectionId = null;
let collectionCriteria = {
    status: 'all',
    codec: 'all',
    tags: [],
    search: ''
};

// DEBUG FUNCTION
window.runDeepDebug = function () {
    console.log('🔍 --- DEEP DEBUG START ---');
    console.log('Criteria:', JSON.parse(JSON.stringify(collectionCriteriaNew)));

    const all = window.ALL_VIDEOS || [];
    console.log(`Total Videos: ${all.length}`);

    // Check favorites specifically
    const favs = all.filter(v => v.favorite || v.Favorite || v.isFavorite || v.IsFavorite);
    console.log(`Expected Favorites Count: ${favs.length}`);

    if (favs.length > 0) {
        console.log('Sample Favorite Video:', favs[0]);
        console.log('Sample Favorite Keys:', Object.keys(favs[0]));

        // Test evaluation on sample
        const match = evaluateCollectionMatch(favs[0], collectionCriteriaNew);
        console.log('Does sample match current criteria?', match);
    } else {
        console.warn('⚠️ NO FAVORITES FOUND IN ALL_VIDEOS!');
    }
    console.log('🔍 --- DEEP DEBUG END ---');
    alert('Debug info logged to console! Please check output.');
};

function openCollectionModal(editId = null) {
    const modal = document.getElementById('collectionModal');
    if (!modal) return;

    editingCollectionId = editId;

    // Reset form
    document.getElementById('collectionName').value = '';
    document.getElementById('collectionSearch').value = '';
    document.getElementById('collectionColor').value = '#64FFDA';
    document.getElementById('collectionColorBtn').style.backgroundColor = '#64FFDA';
    document.getElementById('selectedCollectionIcon').innerText = 'folder_special';

    // Initialize new criteria schema
    collectionCriteriaNew = getDefaultCollectionCriteria();

    // Also reset legacy for backward compat
    collectionCriteria = { status: 'all', codec: 'all', tags: [], search: '' };

    // Update UI title
    document.getElementById('collectionModalTitle').innerText = editId ? 'Edit Collection' : 'Smart Collection';
    document.getElementById('deleteCollectionBtn')?.classList.toggle('hidden', !editId);

    // If editing, load existing data
    if (editId) {
        const existing = (userSettings.smart_collections || []).find(c => c.id === editId);
        if (existing) {
            document.getElementById('collectionName').value = existing.name || '';
            document.getElementById('collectionSearch').value = existing.criteria?.search || '';
            document.getElementById('collectionColor').value = existing.color || '#64FFDA';
            document.getElementById('collectionColorBtn').style.backgroundColor = existing.color || '#64FFDA';
            document.getElementById('selectedCollectionIcon').innerText = existing.icon || 'folder_special';

            // Check if using new schema
            if (existing.criteria?.include || existing.criteria?.exclude) {
                // Deep copy the criteria
                collectionCriteriaNew = JSON.parse(JSON.stringify(existing.criteria));
            } else {
                // Convert legacy schema to new
                collectionCriteriaNew = getDefaultCollectionCriteria();
                if (existing.criteria?.status && existing.criteria.status !== 'all') {
                    collectionCriteriaNew.include.status = [existing.criteria.status];
                }
                if (existing.criteria?.codec && existing.criteria.codec !== 'all') {
                    collectionCriteriaNew.include.codec = [existing.criteria.codec];
                }
                if (existing.criteria?.tags) {
                    collectionCriteriaNew.include.tags = [...existing.criteria.tags];
                }
                collectionCriteriaNew.search = existing.criteria?.search || '';
            }
        }
    }

    // Sync UI with new criteria
    syncSmartCollectionUI();

    modal.classList.add('active');
}

function closeCollectionModal() {
    const modal = document.getElementById('collectionModal');
    if (modal) modal.classList.remove('active');
    editingCollectionId = null;
    document.getElementById('collectionIconPicker')?.classList.add('hidden');
    document.getElementById('collectionColorPicker')?.classList.add('hidden');
}

function syncCollectionModalUI() {
    // Sync filter chips with current criteria
    document.querySelectorAll('.collection-filter-chip[data-filter="status"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === collectionCriteria.status);
    });
    document.querySelectorAll('.collection-filter-chip[data-filter="codec"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === collectionCriteria.codec);
    });
}

function setCollectionFilter(filterType, value) {
    collectionCriteria[filterType] = value;
    syncCollectionModalUI();
}

function renderCollectionTagsList() {
    const container = document.getElementById('collectionTagsList');
    if (!container) return;

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600 italic">No tags created</span>';
        return;
    }

    container.innerHTML = availableTags.map(tag => `
        <button class="collection-filter-chip ${collectionCriteria.tags.includes(tag.name) ? 'active' : ''}" 
                onclick="toggleCollectionTag('${tag.name}')"
                style="border-color: ${collectionCriteria.tags.includes(tag.name) ? tag.color : 'rgba(255,255,255,0.1)'}">
            <span class="tag-dot" style="background-color: ${tag.color}; width: 6px; height: 6px; border-radius: 50%; display: inline-block;"></span>
            ${tag.name}
        </button>
    `).join('');
}

function toggleCollectionTag(tagName) {
    const idx = collectionCriteria.tags.indexOf(tagName);
    if (idx >= 0) {
        collectionCriteria.tags.splice(idx, 1);
    } else {
        collectionCriteria.tags.push(tagName);
    }
    renderCollectionTagsList();
}

function toggleCollectionIconPicker() {
    document.getElementById('collectionColorPicker')?.classList.add('hidden');
    document.getElementById('collectionIconPicker')?.classList.toggle('hidden');
}

function selectCollectionIcon(icon) {
    document.getElementById('selectedCollectionIcon').innerText = icon;
    document.getElementById('collectionIconPicker')?.classList.add('hidden');
}

function toggleCollectionColorPicker() {
    document.getElementById('collectionIconPicker')?.classList.add('hidden');
    document.getElementById('collectionColorPicker')?.classList.toggle('hidden');
}

function selectCollectionColor(color) {
    document.getElementById('collectionColor').value = color;
    document.getElementById('collectionColorBtn').style.backgroundColor = color;
    document.getElementById('collectionColorPicker')?.classList.add('hidden');
}

function saveCollection() {
    const name = document.getElementById('collectionName').value.trim();
    if (!name) {
        alert('Please enter a collection name');
        return;
    }

    const icon = document.getElementById('selectedCollectionIcon').innerText;
    const color = document.getElementById('collectionColor').value;
    const search = document.getElementById('collectionSearch').value.trim();

    // Update search in criteria
    if (collectionCriteriaNew) {
        collectionCriteriaNew.search = search;
    }

    const collection = {
        id: editingCollectionId || 'col_' + Date.now(),
        name: name,
        icon: icon,
        color: color,
        criteria: collectionCriteriaNew ? JSON.parse(JSON.stringify(collectionCriteriaNew)) : {
            status: collectionCriteria.status,
            codec: collectionCriteria.codec,
            tags: [...collectionCriteria.tags],
            search: search
        }
    };

    if (!userSettings.smart_collections) userSettings.smart_collections = [];

    if (editingCollectionId) {
        // Update existing
        const idx = userSettings.smart_collections.findIndex(c => c.id === editingCollectionId);
        if (idx >= 0) {
            userSettings.smart_collections[idx] = collection;
        }
    } else {
        // Add new
        userSettings.smart_collections.push(collection);
    }

    saveSettingsWithoutReload();
    renderCollections();
    closeCollectionModal();
}

function deleteCurrentCollection() {
    if (!editingCollectionId) return;
    if (!confirm('Delete this collection?')) return;

    if (userSettings.smart_collections) {
        userSettings.smart_collections = userSettings.smart_collections.filter(c => c.id !== editingCollectionId);
        saveSettingsWithoutReload();
        renderCollections();
    }
    closeCollectionModal();
}

// --- SMART COLLECTION QUERY BUILDER ---

// Default criteria structure for new collections
function getDefaultCollectionCriteria() {
    return {
        tagLogic: 'any', // 'any' (OR) or 'all' (AND)
        include: {
            status: [],
            codec: [],
            tags: [],
            resolution: [],
            orientation: []
        },
        exclude: {
            status: [],
            codec: [],
            tags: [],
            resolution: [],
            orientation: []
        },
        favorites: null, // true = only, false = exclude, null = any
        date: {
            type: 'any', // 'any', 'relative', 'absolute'
            relative: null, // '24h', '7d', '30d', '90d'
            from: null,
            to: null
        },
        duration: {
            min: null, // seconds
            max: null
        },
        size: {
            min: null, // bytes
            max: null
        },
        search: ''
    };
}

// Get video resolution category
function getVideoResolution(video) {
    // Check both lowercase and uppercase (model alias may differ)
    const width = video.width || video.Width || 0;
    const height = video.height || video.Height || 0;
    const maxDim = Math.max(width, height);

    if (maxDim >= 3840) return '4k';
    if (maxDim >= 1920) return '1080p';
    if (maxDim >= 1280) return '720p';
    return 'sd';
}

// Get video orientation
function getVideoOrientation(video) {
    const width = video.width || video.Width || 0;
    const height = video.height || video.Height || 0;

    if (width === 0 || height === 0) return 'unknown';

    const ratio = width / height;
    if (ratio > 1.1) return 'landscape';
    if (ratio < 0.9) return 'portrait';
    return 'square';
}

// Check if video matches date filter
function matchesDateFilter(video, dateFilter) {
    if (!dateFilter || dateFilter.type === 'any' || dateFilter.type === 'all') return true;

    const videoDate = video.CreatedDate ? new Date(video.CreatedDate) : null;
    if (!videoDate) return false;

    const now = new Date();

    if (dateFilter.type === 'relative' && dateFilter.relative) {
        const msMap = {
            '24h': 24 * 60 * 60 * 1000,
            '7d': 7 * 24 * 60 * 60 * 1000,
            '30d': 30 * 24 * 60 * 60 * 1000,
            '90d': 90 * 24 * 60 * 60 * 1000
        };
        const cutoff = now.getTime() - (msMap[dateFilter.relative] || 0);
        return videoDate.getTime() >= cutoff;
    }

    if (dateFilter.type === 'absolute') {
        if (dateFilter.from && videoDate < new Date(dateFilter.from)) return false;
        if (dateFilter.to && videoDate > new Date(dateFilter.to)) return false;
    }

    return true;
}

// Main evaluation function for Smart Collection matching
function evaluateCollectionMatch(video, criteria) {
    if (!criteria) return true;

    // Utility: check if video matches any value in array
    const matchesAny = (videoVal, arr) => arr.length === 0 || arr.some(v =>
        videoVal?.toLowerCase?.().includes?.(v.toLowerCase()) || videoVal === v
    );

    // Utility: check if excluded
    const isExcluded = (videoVal, arr) => arr.length > 0 && arr.some(v =>
        videoVal?.toLowerCase?.().includes?.(v.toLowerCase()) || videoVal === v
    );

    const status = video.Status || '';
    const codec = (video.codec || '').toLowerCase();
    const videoTags = video.tags || [];
    const resolution = getVideoResolution(video);
    const orientation = getVideoOrientation(video);
    const isHidden = video.hidden || false;
    const isFavorite = video.favorite || false;
    const duration = video.duration || 0;
    const size = video.SizeBytes || 0;

    // Hidden videos are never included
    if (isHidden) return false;

    // --- EXCLUSIONS (if ANY match, reject) ---
    const exc = criteria.exclude || {};

    // Status exclusion
    if (exc.status?.length > 0 && isExcluded(status, exc.status)) return false;

    // Codec exclusion
    if (exc.codec?.length > 0) {
        for (const excCodec of exc.codec) {
            if (codec.includes(excCodec.toLowerCase())) return false;
        }
    }

    // Tags exclusion
    if (exc.tags?.length > 0) {
        if (exc.tags.some(t => videoTags.includes(t))) return false;
    }

    // Resolution exclusion
    if (exc.resolution?.length > 0 && exc.resolution.includes(resolution)) return false;

    // Orientation exclusion
    if (exc.orientation?.length > 0 && exc.orientation.includes(orientation)) return false;

    // --- INCLUSIONS (must satisfy all that are set) ---
    const inc = criteria.include || {};

    // Status inclusion
    if (inc.status?.length > 0) {
        const statusMatch = inc.status.some(s => {
            if (s === 'optimized_files') return video.FilePath?.includes('_opt');
            return status === s;
        });
        if (!statusMatch) return false;
    }

    // Codec inclusion
    if (inc.codec?.length > 0) {
        const codecMatch = inc.codec.some(c => codec.includes(c.toLowerCase()));
        if (!codecMatch) return false;
    }

    // Tags inclusion
    if (inc.tags?.length > 0) {
        if (criteria.tagLogic === 'all') {
            // ALL must match
            if (!inc.tags.every(t => videoTags.includes(t))) return false;
        } else {
            // ANY must match
            if (!inc.tags.some(t => videoTags.includes(t))) return false;
        }
    }

    // Resolution inclusion
    if (inc.resolution?.length > 0 && !inc.resolution.includes(resolution)) return false;

    // Orientation inclusion
    if (inc.orientation?.length > 0 && !inc.orientation.includes(orientation)) return false;

    // --- FAVORITES ---
    // Check both boolean True and string "true"
    const wantOnlyFavorites = criteria.favorites === true || criteria.favorites === 'true';
    const wantExcludeFavorites = criteria.favorites === false || criteria.favorites === 'false';

    if (wantOnlyFavorites || wantExcludeFavorites) {
        // Robust check for favorite property in video object (case-insensitive)
        const isFav = !!(video.favorite || video.Favorite || video.isFavorite || video.IsFavorite);

        if (wantOnlyFavorites && !isFav) return false;
        if (wantExcludeFavorites && isFav) return false;
    }

    // --- DATE FILTER ---
    if (!matchesDateFilter(video, criteria.date)) return false;

    // --- DURATION FILTER ---
    if (criteria.duration) {
        if (criteria.duration.min !== null && duration < criteria.duration.min) return false;
        if (criteria.duration.max !== null && duration > criteria.duration.max) return false;
    }

    // --- SIZE FILTER ---
    if (criteria.size) {
        if (criteria.size.min !== null && size < criteria.size.min) return false;
        if (criteria.size.max !== null && size > criteria.size.max) return false;
    }

    // --- SEARCH ---
    if (criteria.search) {
        const searchLower = criteria.search.toLowerCase();
        const filename = video.FilePath?.split(/[\\/]/).pop()?.toLowerCase() || '';
        if (!filename.includes(searchLower) && !video.FilePath?.toLowerCase()?.includes(searchLower)) {
            return false;
        }
    }

    return true;
}

// --- SMART COLLECTION MODAL UI FUNCTIONS ---

// State variable for new collection criteria
let collectionCriteriaNew = null;

// Initialize new criteria state when opening modal
function initNewCollectionCriteria() {
    collectionCriteriaNew = getDefaultCollectionCriteria();
    updateCollectionPreviewCount();
}

// Toggle filter chip active state (include mode)
function toggleSmartFilterChip(chip) {
    const filterType = chip.dataset.filter;
    const value = chip.dataset.value;

    if (!collectionCriteriaNew) initNewCollectionCriteria();

    const includeArr = collectionCriteriaNew.include[filterType];

    chip.classList.toggle('active');

    if (chip.classList.contains('active')) {
        if (!includeArr.includes(value)) includeArr.push(value);
    } else {
        const idx = includeArr.indexOf(value);
        if (idx > -1) includeArr.splice(idx, 1);
    }

    updateCollectionPreviewCount();
}

// Toggle tag chip for new collection
function toggleSmartTagChip(tagName) {
    if (!collectionCriteriaNew) initNewCollectionCriteria();

    const includeArr = collectionCriteriaNew.include.tags;
    const idx = includeArr.indexOf(tagName);

    if (idx > -1) {
        includeArr.splice(idx, 1);
    } else {
        includeArr.push(tagName);
    }

    renderSmartCollectionTagsList();
    updateCollectionPreviewCount();
}

// Toggle tag logic between ANY and ALL
function toggleTagLogic() {
    if (!collectionCriteriaNew) initNewCollectionCriteria();

    collectionCriteriaNew.tagLogic = collectionCriteriaNew.tagLogic === 'any' ? 'all' : 'any';

    const btn = document.getElementById('tagLogicBtn');
    if (btn) {
        btn.textContent = collectionCriteriaNew.tagLogic.toUpperCase();
    }

    updateCollectionPreviewCount();
}

// Set favorites filter (true = only, false = exclude, null = any)
function setFavoritesFilter(value) {
    if (!collectionCriteriaNew) initNewCollectionCriteria();

    collectionCriteriaNew.favorites = value;

    // Update UI
    document.querySelectorAll('[data-filter="favorites"]').forEach(btn => {
        const btnValue = btn.dataset.value === 'null' ? null : btn.dataset.value === 'true';
        btn.classList.toggle('active', btnValue === value);
    });

    updateCollectionPreviewCount();
}

// Render tags list for smart collection modal
function renderSmartCollectionTagsList() {
    const container = document.getElementById('collectionTagsList');
    if (!container) return;

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600 italic">No tags created</span>';
        return;
    }

    const selectedTags = collectionCriteriaNew?.include?.tags || [];

    container.innerHTML = availableTags.map(tag => `
        <button class="filter-chip ${selectedTags.includes(tag.name) ? 'active' : ''}" 
                onclick="toggleSmartTagChip('${tag.name}')"
                style="${selectedTags.includes(tag.name) ? `border-color: ${tag.color}; background: ${tag.color}20;` : ''}">
            <span class="w-2 h-2 rounded-full shrink-0" style="background-color: ${tag.color}"></span>
            ${tag.name}
        </button>
    `).join('');
}

// Update the real-time match count badge
function updateCollectionPreviewCount() {
    const countEl = document.getElementById('matchCountNumber');
    if (!countEl) return;

    if (!collectionCriteriaNew) {
        countEl.textContent = '0';
        return;
    }

    // Include search term from input
    const searchInput = document.getElementById('collectionSearch');
    if (searchInput) {
        collectionCriteriaNew.search = searchInput.value.trim();
    }

    // Count matching videos
    const allVideos = window.ALL_VIDEOS || [];
    const matchingVideos = allVideos.filter(v => evaluateCollectionMatch(v, collectionCriteriaNew));
    const count = matchingVideos.length;
    countEl.textContent = count;

    // Debug logging
    if (collectionCriteriaNew.favorites === true) {
        const favVideos = allVideos.filter(v => v.favorite);
        console.log(`🎬 Favorites filter: ${favVideos.length} videos have favorite=true out of ${allVideos.length}`);
    }
    if (collectionCriteriaNew.include?.resolution?.length > 0) {
        const sample = allVideos.slice(0, 3).map(v => ({ w: v.width || v.Width, h: v.height || v.Height }));
        console.log('📐 Sample video dimensions:', sample);
    }

    // Animate if changed
    countEl.closest('.px-3')?.classList.add('animate-pulse');
    setTimeout(() => {
        countEl.closest('.px-3')?.classList.remove('animate-pulse');
    }, 300);
}

// Sync modal UI with collectionCriteriaNew state
function syncSmartCollectionUI() {
    if (!collectionCriteriaNew) return;

    // Sync status chips
    document.querySelectorAll('[data-filter="status"]').forEach(chip => {
        const value = chip.dataset.value;
        chip.classList.toggle('active', collectionCriteriaNew.include.status.includes(value));
    });

    // Sync codec chips
    document.querySelectorAll('[data-filter="codec"]').forEach(chip => {
        const value = chip.dataset.value;
        chip.classList.toggle('active', collectionCriteriaNew.include.codec.includes(value));
    });

    // Sync resolution chips
    document.querySelectorAll('[data-filter="resolution"]').forEach(chip => {
        const value = chip.dataset.value;
        chip.classList.toggle('active', collectionCriteriaNew.include.resolution.includes(value));
    });

    // Sync orientation chips
    document.querySelectorAll('[data-filter="orientation"]').forEach(chip => {
        const value = chip.dataset.value;
        chip.classList.toggle('active', collectionCriteriaNew.include.orientation.includes(value));
    });

    // Sync tag logic button
    const tagLogicBtn = document.getElementById('tagLogicBtn');
    if (tagLogicBtn) tagLogicBtn.textContent = (collectionCriteriaNew.tagLogic || 'any').toUpperCase();

    // Sync favorites
    document.querySelectorAll('[data-filter="favorites"]').forEach(btn => {
        const btnValue = btn.dataset.value === 'null' ? null : btn.dataset.value === 'true';
        btn.classList.toggle('active', btnValue === collectionCriteriaNew.favorites);
    });

    // Sync search
    const searchInput = document.getElementById('collectionSearch');
    if (searchInput) searchInput.value = collectionCriteriaNew.search || '';

    renderSmartCollectionTagsList();
    updateCollectionPreviewCount();
}

// Count videos matching collection criteria (updated for new schema)
function getCollectionCount(collection) {
    if (!window.ALL_VIDEOS || !collection.criteria) return 0;

    // Check if using new schema (has include/exclude) vs legacy (status/codec/tags)
    const isNewSchema = collection.criteria.include || collection.criteria.exclude;

    if (isNewSchema) {
        return window.ALL_VIDEOS.filter(v => evaluateCollectionMatch(v, collection.criteria)).length;
    }

    // Legacy compatibility for old collections
    return window.ALL_VIDEOS.filter(v => {
        const name = v.FilePath.split(/[\\\\/]/).pop().toLowerCase();
        const status = v.Status;
        const codec = v.codec || 'unknown';
        const videoTags = v.tags || [];
        const isHidden = v.hidden || false;

        // Must be visible (not in vault)
        if (isHidden) return false;

        // Status filter
        if (collection.criteria.status && collection.criteria.status !== 'all') {
            if (collection.criteria.status === 'optimized_files') {
                if (!v.FilePath.includes('_opt')) return false;
            } else if (status !== collection.criteria.status) {
                return false;
            }
        }

        // Codec filter
        if (collection.criteria.codec && collection.criteria.codec !== 'all') {
            if (!codec.includes(collection.criteria.codec)) return false;
        }

        // Tags filter (match ANY)
        if (collection.criteria.tags && collection.criteria.tags.length > 0) {
            const hasMatchingTag = collection.criteria.tags.some(t => videoTags.includes(t));
            if (!hasMatchingTag) return false;
        }

        // Search filter
        if (collection.criteria.search) {
            const searchLower = collection.criteria.search.toLowerCase();
            if (!name.includes(searchLower) && !v.FilePath.toLowerCase().includes(searchLower)) {
                return false;
            }
        }

        return true;
    }).length;
}

function renderCollections() {
    const container = document.getElementById('collectionsNav');
    if (!container) return;

    const allCollections = userSettings.smart_collections || [];

    // Filter out sensitive collections if Safe Mode is ON
    let collections = allCollections;
    if (safeMode) {
        let sensitiveCols = window.userSettings?.sensitive_collections || [];
        // Normalize sensitive list: trim and lowercase
        sensitiveCols = sensitiveCols.map(s => s.trim().toLowerCase()).filter(s => s);

        collections = allCollections.filter(c => {
            const name = (c.name || '').trim().toLowerCase();
            return !sensitiveCols.includes(name);
        });
    }

    if (collections.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-600 italic px-3 py-2">No collections yet</p>';
        return;
    }

    container.innerHTML = collections.map(col => {
        const count = getCollectionCount(col);
        const isActive = col.id === activeCollectionId;

        return `
            <div class="collection-nav-item group flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all w-full cursor-pointer ${isActive ? 'bg-arcade-cyan/25 text-arcade-cyan border border-arcade-cyan/50 shadow-lg shadow-arcade-cyan/10 font-bold' : 'text-gray-600 dark:text-gray-300 hover:bg-black/5 dark:hover:bg-white/5 border border-transparent'}" 
                    onclick="applyCollection('${col.id}')"
                    ondblclick="openCollectionModal('${col.id}')">
                <span class="material-icons text-[18px]" style="color: ${col.color}">${col.icon}</span>
                <span class="flex-1 text-left truncate">${col.name}</span>
                
                <button onclick="event.stopPropagation(); openCollectionModal('${col.id}')" 
                        class="${isActive ? 'opacity-100' : 'opacity-0'} group-hover:opacity-100 p-1 text-gray-400 dark:text-gray-500 hover:text-black dark:hover:text-white transition-opacity"
                        title="Edit Collection">
                    <span class="material-icons text-[14px]">edit</span>
                </button>
                
                <span class="text-[10px] px-1.5 py-0.5 rounded-full ${isActive ? 'bg-black/40 text-arcade-cyan border border-arcade-cyan/30' : 'bg-black/5 dark:bg-white/5 text-gray-400 dark:text-gray-500'} font-mono">${count}</span>
            </div>
        `;
    }).join('');
}

function applyCollection(collectionId) {
    const collection = (userSettings.smart_collections || []).find(c => c.id === collectionId);
    if (!collection || !collection.criteria) return;

    // Reset to lobby workspace first (this clears any previous active collection)
    setWorkspaceMode('lobby');

    // CONVERT LEGACY TO NEW SCHEMA IF NEEDED
    let criteria = collection.criteria;

    // Check if using new schema (has include/exclude)
    const isNewSchema = criteria.include || criteria.exclude;

    if (!isNewSchema) {
        // Convert legacy schema to new format on the fly for viewing
        const converted = getDefaultCollectionCriteria();

        if (criteria.status && criteria.status !== 'all') {
            converted.include.status = [criteria.status];
        }
        if (criteria.codec && criteria.codec !== 'all') {
            converted.include.codec = [criteria.codec];
        }
        if (criteria.tags) {
            converted.include.tags = [...criteria.tags];
        }
        converted.search = criteria.search || '';

        criteria = converted;
    }

    // Update URL history for deep linking
    const newUrl = '/collections/' + encodeURIComponent(collection.name);
    // Don't push duplicate state
    if (window.location.pathname !== newUrl) {
        history.pushState({ id: collectionId }, '', newUrl);
    }

    // Set the active smart collection criteria and ID
    activeSmartCollectionCriteria = criteria;
    activeCollectionId = collectionId;

    // Update search UI to match (visual only)
    if (criteria.search) {
        searchTerm = criteria.search;
        document.getElementById('mobileSearchInput').value = searchTerm;
    } else {
        searchTerm = '';
        document.getElementById('mobileSearchInput').value = '';
    }

    // Execute filter
    filterAndSort(true);
    renderCollections(); // Update sidebar UI to show active state

    // Show toast
    showToast(`Applied collection: ${collection.name}`, 'info');
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

    if (window.ENABLE_OPTIMIZER !== true || window.userSettings?.enable_optimizer === false) return;

    // Populate Initial State
    currentOptAudio = 'enhanced'; // Reset to default
    updateOptAudioUI();
    clearTrim(); // Reset trim

    // Show panel
    panel.classList.add('active');
    const actions = document.getElementById('cinemaActions');
    if (actions) actions.style.display = 'none';
}

function closeOptimize() {
    document.getElementById('optimizePanel').classList.remove('active');
    const actions = document.getElementById('cinemaActions');
    if (actions) actions.style.display = 'flex';
}

function setOptAudio(mode) {
    currentOptAudio = mode;
    updateOptAudioUI();
}

let currentOptVideo = 'compress';

function setOptVideo(mode) {
    currentOptVideo = mode;
    updateOptVideoUI();
}

function updateOptVideoUI() {
    const compressBtn = document.getElementById('optVideoCompress');
    const copyBtn = document.getElementById('optVideoCopy');

    // Check if elements exist (safety)
    if (!compressBtn || !copyBtn) return;

    const activeClasses = ['text-white', 'bg-white/10', 'shadow-sm'];
    const inactiveClasses = ['text-gray-400', 'hover:text-white'];

    if (currentOptVideo === 'compress') {
        compressBtn.classList.add(...activeClasses);
        compressBtn.classList.remove(...inactiveClasses);

        copyBtn.classList.remove(...activeClasses);
        copyBtn.classList.add(...inactiveClasses);

        document.getElementById('optVideoDesc').innerText = "Optimize to efficient HEVC/H.265";
    } else {
        compressBtn.classList.remove(...activeClasses);
        compressBtn.classList.add(...inactiveClasses);

        copyBtn.classList.add(...activeClasses);
        copyBtn.classList.remove(...inactiveClasses);

        document.getElementById('optVideoDesc').innerText = "Copy video stream (Passthrough)";
    }
}

function updateOptAudioUI() {
    const enhancedBtn = document.getElementById('optAudioEnhanced');
    const standardBtn = document.getElementById('optAudioStandard');

    const activeClasses = ['text-white', 'bg-white/10', 'shadow-sm'];
    const inactiveClasses = ['text-gray-400', 'hover:text-white'];

    if (currentOptAudio === 'enhanced') {
        enhancedBtn.classList.add(...activeClasses);
        enhancedBtn.classList.remove(...inactiveClasses);

        standardBtn.classList.remove(...activeClasses);
        standardBtn.classList.add(...inactiveClasses);

        document.getElementById('optAudioDesc').innerText = "Smart normalization & noise reduction";
    } else {
        enhancedBtn.classList.remove(...activeClasses);
        enhancedBtn.classList.add(...inactiveClasses);

        standardBtn.classList.add(...activeClasses);
        standardBtn.classList.remove(...inactiveClasses);

        document.getElementById('optAudioDesc').innerText = "Standard encoding (no filters)";
    }
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
    params.set('video', currentOptVideo);
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

// --- BACKUP & RESTORE ---
function exportSettings() {
    window.location.href = '/api/backup';
}

function importSettings() {
    const fileInput = document.getElementById('settingsImportFile');
    const file = fileInput.files[0];
    if (!file) {
        alert("Please select a file to restore.");
        return;
    }

    if (!confirm("Are you sure? This will overwrite your current settings, collections, and tags.")) {
        return;
    }

    const reader = new FileReader();
    reader.onload = async function (e) {
        const jsonContent = e.target.result;
        try {
            // Validate JSON client-side briefly
            JSON.parse(jsonContent);

            const response = await fetch('/api/restore', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: jsonContent
            });

            if (response.ok) {
                alert("Settings restored successfully! Reloading...");
                window.location.reload();
            } else {
                const err = await response.text();
                alert("Failed to restore settings: " + err);
            }
        } catch (err) {
            alert("Invalid JSON file: " + err);
        }
    };
    reader.readAsText(file);
}

// --- GLOBAL UTILS ---
window.toggleLayout = toggleLayout;
// Expose for HTML access
window.cinemaOptimize = cinemaOptimize;
window.setOptAudio = setOptAudio;
window.setOptVideo = setOptVideo;
window.setTrimFromHead = setTrimFromHead;
window.clearTrim = clearTrim;
window.closeOptimize = closeOptimize;
window.triggerOptimization = triggerOptimization;
window.toggleSelection = toggleSelection;
window.exportSettings = exportSettings;
window.importSettings = importSettings;


// =============================================================================
// FILTER PANEL & TAG SYSTEM
// =============================================================================

// Filter state (in addition to existing currentFilter, currentCodec)
let activeTags = [];      // Array of tag names currently selected for filtering
let filterUntaggedOnly = false;
let availableTags = [];   // Loaded from API

// --- FILTER PANEL CONTROLS ---
function openFilterPanel() {
    const panel = document.getElementById('filterPanel');
    if (panel) {
        panel.classList.add('active');
        loadAvailableTags();
        syncFilterPanelState();
    }
}

function closeFilterPanel() {
    const panel = document.getElementById('filterPanel');
    if (panel) {
        panel.classList.remove('active');
    }
}

function syncFilterPanelState() {
    // Sync status chips
    document.querySelectorAll('[data-filter="status"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === currentFilter);
    });

    // Sync codec chips
    document.querySelectorAll('[data-filter="codec"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === currentCodec);
    });

    // Sync untagged checkbox
    const untaggedCheck = document.getElementById('filterUntaggedOnly');
    if (untaggedCheck) untaggedCheck.checked = filterUntaggedOnly;

    updateFilterPanelCount();
}

function setFilterOption(type, value) {
    if (type === 'status') {
        currentFilter = value;
    } else if (type === 'codec') {
        currentCodec = value;
    }

    // Update chip visual state
    document.querySelectorAll(`[data-filter="${type}"]`).forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === value);
    });

    updateFilterPanelCount();
}

function toggleTagFilter(tagName) {
    const idx = activeTags.indexOf(tagName);
    if (idx > -1) {
        activeTags.splice(idx, 1);
    } else {
        activeTags.push(tagName);
    }

    // Update visual state
    renderFilterTagsList();
    updateFilterPanelCount();
}

function toggleUntaggedFilter() {
    filterUntaggedOnly = document.getElementById('filterUntaggedOnly')?.checked || false;
    updateFilterPanelCount();
}

function updateFilterPanelCount() {
    let count = 0;
    if (currentFilter !== 'all') count++;
    if (currentCodec !== 'all') count++;
    count += activeTags.length;
    if (filterUntaggedOnly) count++;

    // Update panel header count
    const panelCount = document.getElementById('filterPanelCount');
    if (panelCount) panelCount.textContent = `(${count} active)`;

    // Update button badge
    const badge = document.getElementById('filterBadge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }
}

function applyFilters() {
    closeFilterPanel();

    // Filters are already set via setFilterOption, just need to run filterAndSort
    filterAndSort(true);

    // Update active filters row
    renderActiveFiltersRow();
}

function resetFilters() {
    currentFilter = 'all';
    currentCodec = 'all';
    activeTags = [];
    filterUntaggedOnly = false;

    // Sync UI
    syncFilterPanelState();
    renderFilterTagsList();

    // Clear active filters row
    const row = document.getElementById('activeFiltersRow');
    if (row) row.classList.add('hidden');

    // Update badge
    updateFilterPanelCount();

    // Refresh grid
    filterAndSort(true);
}

function renderActiveFiltersRow() {
    const row = document.getElementById('activeFiltersRow');
    const chipsContainer = document.getElementById('activeFilterChips');

    if (!row || !chipsContainer) return;

    const chips = [];

    if (currentFilter !== 'all') {
        chips.push({ label: `Status: ${currentFilter}`, type: 'status' });
    }
    if (currentCodec !== 'all') {
        chips.push({ label: `Codec: ${currentCodec.toUpperCase()}`, type: 'codec' });
    }
    activeTags.forEach(tag => {
        const tagData = availableTags.find(t => t.name === tag);
        chips.push({ label: tag, type: 'tag', color: tagData?.color || '#888' });
    });
    if (filterUntaggedOnly) {
        chips.push({ label: 'Untagged only', type: 'untagged' });
    }

    if (chips.length === 0) {
        row.classList.add('hidden');
        return;
    }

    row.classList.remove('hidden');
    chipsContainer.innerHTML = chips.map(c => `
        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-white/10 text-gray-300 border border-white/10">
            ${c.type === 'tag' ? `<span class="w-2 h-2 rounded-full" style="background: ${c.color}"></span>` : ''}
            ${c.label}
            <button class="hover:text-arcade-pink" onclick="removeActiveFilter('${c.type}', '${c.label}')">×</button>
        </span>
    `).join('');
}

function removeActiveFilter(type, label) {
    if (type === 'status') {
        currentFilter = 'all';
    } else if (type === 'codec') {
        currentCodec = 'all';
    } else if (type === 'tag') {
        activeTags = activeTags.filter(t => t !== label);
    } else if (type === 'untagged') {
        filterUntaggedOnly = false;
    }

    syncFilterPanelState();
    renderFilterTagsList();
    updateFilterPanelCount();
    renderActiveFiltersRow();
    filterAndSort(true);
}

// --- TAG MANAGEMENT ---
function loadAvailableTags() {
    fetch('/api/tags')
        .then(res => res.json())
        .then(tags => {
            availableTags = tags || [];
            renderFilterTagsList();
            renderExistingTagsList();
        })
        .catch(err => {
            console.error('Failed to load tags:', err);
            availableTags = [];
        });
}

function renderFilterTagsList() {
    const container = document.getElementById('filterTagsList');
    if (!container) return;

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600 italic">No tags created yet</span>';
        return;
    }

    container.innerHTML = availableTags.map(tag => `
        <button class="tag-filter-chip ${activeTags.includes(tag.name) ? 'active' : ''}" 
                onclick="toggleTagFilter('${tag.name}')"
                style="border-color: ${activeTags.includes(tag.name) ? tag.color : 'rgba(255,255,255,0.15)'}">
            <span class="tag-dot" style="background-color: ${tag.color}"></span>
            ${tag.name}
        </button>
    `).join('');
}

// --- VIDEO CARD TAG CHIPS ---
function renderVideoCardTags(tags) {
    if (!tags || tags.length === 0) return '';

    const maxShow = 3;
    const visibleTags = tags.slice(0, maxShow);
    const remaining = tags.length - maxShow;

    let html = '<div class="video-card-tags flex flex-wrap gap-1 mt-1">';

    visibleTags.forEach(tagName => {
        const tagData = availableTags.find(t => t.name === tagName);
        const color = tagData?.color || '#888';
        html += `<span class="video-card-tag" style="background-color: ${color}20; border-color: ${color}40; color: ${color}">
            <span class="tag-dot-small" style="background-color: ${color}"></span>
            ${tagName}
        </span>`;
    });

    if (remaining > 0) {
        html += `<span class="video-card-tag overflow-tag">+${remaining}</span>`;
    }

    html += '</div>';
    return html;
}

// --- CINEMA MODAL TAG PICKER ---
function toggleCinemaTagPanel() {
    const panel = document.getElementById('cinemaTagPanel');
    if (panel) {
        panel.classList.toggle('hidden');
        // Ensure tags are populated when opening
        if (!panel.classList.contains('hidden')) {
            updateCinemaTags();
        }
    }
}

function updateCinemaTags() {
    const container = document.getElementById('cinemaTagPicker');
    if (!container || !currentCinemaVideo) return;

    const videoTags = currentCinemaVideo.tags || [];

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600 italic">No tags available</span>';
        return;
    }

    container.innerHTML = availableTags.map(tag => `
        <button class="cinema-tag-chip ${videoTags.includes(tag.name) ? 'active' : ''}" 
                onclick="toggleCinemaTag('${tag.name}')"
                style="--tag-color: ${tag.color}">
            <span class="tag-dot" style="background-color: ${tag.color}"></span>
            ${tag.name}
        </button>
    `).join('');
}

function toggleCinemaTag(tagName) {
    if (!currentCinemaPath || !currentCinemaVideo) return;

    const currentTags = currentCinemaVideo.tags || [];
    let newTags;

    if (currentTags.includes(tagName)) {
        newTags = currentTags.filter(t => t !== tagName);
    } else {
        newTags = [...currentTags, tagName];
    }

    // Optimistic UI update
    currentCinemaVideo.tags = newTags;
    updateCinemaTags();

    // Update in ALL_VIDEOS array
    const videoInArray = window.ALL_VIDEOS.find(v => v.FilePath === currentCinemaPath);
    if (videoInArray) {
        videoInArray.tags = newTags;
    }

    // Save to server
    fetch('/api/video/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            path: currentCinemaPath,
            tags: newTags
        })
    })
        .then(res => res.json())
        .then(data => {
            console.log('Tags updated:', data.tags);
            // Re-render the grid to show updated tags on cards
            filterAndSort();
        })
        .catch(err => {
            console.error('Failed to update tags:', err);
            // Revert on error
            currentCinemaVideo.tags = currentTags;
            if (videoInArray) videoInArray.tags = currentTags;
            updateCinemaTags();
        });
}

// --- TAG MANAGER MODAL ---
function openTagManager() {
    const modal = document.getElementById('tagManagerModal');
    if (modal) {
        modal.classList.add('active');
        loadAvailableTags();
    }
}

function closeTagManager() {
    const modal = document.getElementById('tagManagerModal');
    if (modal) {
        modal.classList.remove('active');
    }
    // Also close color picker
    document.getElementById('tagColorPicker')?.classList.add('hidden');
}

function toggleTagColorPicker() {
    const picker = document.getElementById('tagColorPicker');
    if (picker) picker.classList.toggle('hidden');
}

function selectTagColor(color) {
    document.getElementById('newTagColor').value = color;
    document.getElementById('tagColorBtn').style.backgroundColor = color;
    document.getElementById('tagColorPicker')?.classList.add('hidden');
}

function createNewTag() {
    const nameInput = document.getElementById('newTagName');
    const colorInput = document.getElementById('newTagColor');

    const name = nameInput?.value?.trim();
    const color = colorInput?.value || '#00ffd0';

    if (!name) {
        alert('Please enter a tag name');
        return;
    }

    fetch('/api/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, color })
    })
        .then(res => {
            if (res.status === 409) {
                alert('Tag already exists');
                return null;
            }
            return res.json();
        })
        .then(data => {
            if (data) {
                // Clear input
                nameInput.value = '';
                // Refresh lists
                loadAvailableTags();
            }
        })
        .catch(err => {
            console.error('Error creating tag:', err);
            alert('Failed to create tag');
        });
}

function deleteTag(tagName) {
    if (!confirm(`Delete tag "${tagName}"? This will remove it from all videos.`)) return;

    fetch(`/api/tags?action=delete&name=${encodeURIComponent(tagName)}`)
        .then(res => res.json())
        .then(() => {
            // Remove from active filters
            activeTags = activeTags.filter(t => t !== tagName);
            // Refresh
            loadAvailableTags();
            updateFilterPanelCount();
        })
        .catch(err => {
            console.error('Error deleting tag:', err);
            alert('Failed to delete tag');
        });
}

function renderExistingTagsList() {
    const container = document.getElementById('existingTagsList');
    if (!container) return;

    if (availableTags.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-600 italic">No tags created yet</p>';
        return;
    }

    container.innerHTML = availableTags.map(tag => `
        <div class="flex items-center justify-between p-2 rounded-lg bg-white/5 border border-white/5">
            <div class="flex items-center gap-2">
                <span class="w-4 h-4 rounded-full" style="background-color: ${tag.color}"></span>
                <span class="text-sm text-white">${tag.name}</span>
            </div>
            <button onclick="deleteTag('${tag.name}')" class="text-gray-500 hover:text-arcade-pink transition-colors">
                <span class="material-icons text-sm">delete</span>
            </button>
        </div>
    `).join('');
}

// --- VIDEO TAG ASSIGNMENT ---
function setVideoTags(videoPath, tags) {
    return fetch('/api/video/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: videoPath, tags })
    })
        .then(res => res.json())
        .then(data => {
            // Update local cache
            const video = window.ALL_VIDEOS.find(v => v.FilePath === videoPath);
            if (video) {
                video.tags = data.tags || [];
            }
            return data.tags;
        });
}

// --- KEYBOARD SHORTCUTS FOR FILTER PANEL ---
document.addEventListener('keydown', (e) => {
    // ESC closes filter panel
    if (e.key === 'Escape') {
        const filterPanel = document.getElementById('filterPanel');
        if (filterPanel?.classList.contains('active')) {
            closeFilterPanel();
            e.preventDefault();
            return;
        }

        const tagManager = document.getElementById('tagManagerModal');
        if (tagManager?.classList.contains('active')) {
            closeTagManager();
            e.preventDefault();
            return;
        }
    }
});

// =============================================================================
// END FILTER PANEL & TAG SYSTEM
// =============================================================================

// --- RUN ON LOAD ---
document.addEventListener('DOMContentLoaded', () => {
    // Initialize workspace theming
    const initialWorkspace = workspaceMode || 'lobby';
    document.body.setAttribute('data-workspace', initialWorkspace);

    // Apply initial workspace colors
    const wsColors = {
        lobby: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
        favorites: { accent: '#F4B342', bg: 'rgba(244, 179, 66, 0.05)' },
        optimized: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
        vault: { accent: '#8F0177', bg: 'rgba(143, 1, 119, 0.05)' }
    };
    const colors = wsColors[initialWorkspace] || wsColors.lobby;
    const wsIndicator = document.querySelector('.workspace-indicator');
    if (wsIndicator) {
        wsIndicator.style.borderBottomColor = colors.accent;
        wsIndicator.style.backgroundColor = colors.bg;
    }

    // Load available tags for filtering
    if (typeof loadAvailableTags === 'function') {
        loadAvailableTags();
    }

    // Handle URL Back/Forward
    window.onpopstate = (event) => {
        loadFromURL();
    };

    // Initial Load
    loadFromURL();

    // Render views and collections
    setTimeout(() => {
        renderSavedViews();
        renderCollections();
    }, 500);
});
