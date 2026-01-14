/**
 * Application State - Grouped globals for better organization
 * TODO: Future refactor should migrate these to a proper state management system
 */

// --- FILTER STATE ---
const filterState = {
    status: 'all',          // Status filter (all, HIGH, OK, optimized_files)
    codec: 'all',           // Codec filter (all, h264, hevc, etc.)
    folder: 'all',          // Folder filter
    search: '',             // Search term
    date: 'all',            // Date filter (all, 1d, 7d, 30d)
    size: {
        min: null,          // Min size in MB
        max: null           // Max size in MB
    },
    tags: {
        active: [],         // Array of tag names currently selected
        untaggedOnly: false // Show only untagged items
    }
};

// --- VIEW STATE ---
const viewState = {
    layout: 'grid',         // Current layout (grid, list, treemap)
    workspace: 'lobby',     // Current workspace (lobby, mixed, vault, favorites, duplicates)
    sort: 'bitrate'         // Sort order (bitrate, size, name, date)
};

// --- COLLECTION STATE ---
const collectionState = {
    activeId: null,         // Currently active collection ID for UI highlighting
    activeCriteria: null    // Stores current smart collection filter rules
};

// --- UI STATE ---
const uiState = {
    safeMode: localStorage.getItem('safe_mode') === 'true',
    renderedCount: 0
};

// --- DATA STATE ---
let availableTags = [];     // Loaded from API
let filteredVideos = [];    // Result of filter/sort
const BATCH_SIZE = 40;

// Legacy variable aliases for backward compatibility
// These will be deprecated in future versions
let currentFilter = filterState.status;
let currentCodec = filterState.codec;
let currentSort = viewState.sort;
let currentLayout = viewState.layout;
let workspaceMode = viewState.workspace;
let currentFolder = filterState.folder;
let minSizeMB = filterState.size.min;
let maxSizeMB = filterState.size.max;
let dateFilter = filterState.date;
let activeTags = filterState.tags.active;
let filterUntaggedOnly = filterState.tags.untaggedOnly;
let searchTerm = filterState.search;
let activeSmartCollectionCriteria = collectionState.activeCriteria;
let activeCollectionId = collectionState.activeId;
let safeMode = uiState.safeMode;
let renderedCount = uiState.renderedCount;

// --- GLOBAL AUTH INTERCEPTOR ---
const originalFetch = window.fetch;
window.fetch = async function (...args) {
    const response = await originalFetch(...args);
    if (response.status === 401) {
        // Redirect to login if unauthorized
        window.location.href = '/login.html';
        return response; // Propagate response but we are leaving
    }
    return response;
};

// --- THEME LOGIC ---

/**
 * Toggle between light and dark theme
 * Persists preference to localStorage and updates theme icon
 */
function toggleTheme() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');

    const icon = document.getElementById('themeIcon');
    if (icon) icon.textContent = isDark ? 'light_mode' : 'dark_mode';
}

// --- SAFE MODE LOGIC ---

/**
 * Check if a video/image should be hidden in Safe Mode
 * Checks against user-configured sensitive tags and directory paths
 *
 * @param {Object} video - Video object to check
 * @returns {boolean} True if the video is considered sensitive
 */
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

/**
 * Handle search input with debouncing to prevent excessive filtering
 * Waits 300ms after user stops typing before triggering filter
 */
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

/**
 * Set the status filter and trigger re-filtering
 * @param {string} f - Filter value ('all', 'HIGH', 'OK', 'optimized_files')
 */
function setFilter(f) {
    currentFilter = f;
    // Reset codec filter when showing all videos
    if (f === 'all') {
        currentCodec = 'all';
        document.getElementById('codecSelect').value = 'all';
    }
    filterAndSort();
}

/**
 * Set the codec filter and trigger re-filtering
 * @param {string} c - Codec value ('all', 'h264', 'hevc', etc.)
 */
function setCodecFilter(c) {
    currentCodec = c;
    filterAndSort();
}

/**
 * Set minimum file size filter
 * @param {string|number|null} val - Minimum size in MB, or null to clear
 */
function setMinSize(val) {
    minSizeMB = val ? parseFloat(val) : null;
    filterAndSort();
}

/**
 * Set maximum file size filter
 * @param {string|number|null} val - Maximum size in MB, or null to clear
 */
function setMaxSize(val) {
    maxSizeMB = val ? parseFloat(val) : null;
    filterAndSort();
}

/**
 * Set date filter for recently imported/modified files
 * @param {string} val - Date filter ('all', '1d', '7d', '30d')
 */
function setDateFilter(val) {
    dateFilter = val;
    // Update active class
    document.querySelectorAll('[data-filter="date"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === val);
        // Update border color
        btn.style.borderColor = btn.dataset.value === val ? 'rgba(0, 255, 208, 0.5)' : 'rgba(255, 255, 255, 0.1)';
        btn.style.background = btn.dataset.value === val ? 'rgba(0, 255, 208, 0.15)' : 'rgba(255, 255, 255, 0.05)';
        btn.style.color = btn.dataset.value === val ? '#00ffd0' : '#9ca3af';
    });
    filterAndSort();
}

/**
 * Set sort order for the video list
 * @param {string} s - Sort key ('bitrate', 'size', 'name', 'date')
 */
function setSort(s) {
    currentSort = s;
    filterAndSort();
}

// --- WORKSPACE & LAYOUT ---

/**
 * Switch between workspace modes (lobby, vault, favorites, duplicates, optimized)
 * Updates UI theming, navigation highlights, and triggers appropriate filtering
 *
 * @param {string} mode - Workspace mode to activate
 * @param {boolean} [preserveCollection=false] - If true, keeps active collection filter
 */
function setWorkspaceMode(mode, preserveCollection = false) {
    try {
        // Debug: console.log("Setting workspace mode:", mode);
        workspaceMode = mode;

        // Clear active smart collection when changing workspace unless executing a collection load
        if (!preserveCollection) {
            activeSmartCollectionCriteria = null;
            activeCollectionId = null; // Clear active visual state
            renderCollections(); // Re-render to remove active class
        }

        // Set workspace data attribute for CSS theming
        document.body.setAttribute('data-workspace', mode);

        // CLEAR SEARCH ON LOBBY RETURN
        if (mode === 'lobby' && !preserveCollection) {
            searchTerm = '';
            document.getElementById('mobileSearchInput').value = '';
            // If the user had a search filter active, simple filter update happens below
            // But we might need to reset 'currentFilter' if it was search-bound?
            // Usually filterAndSort uses 'searchTerm' global.
        }

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
            vault: { accent: '#8F0177', bg: 'rgba(143, 1, 119, 0.05)' },
            duplicates: { accent: '#a855f7', bg: 'rgba(168, 85, 247, 0.05)' }
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

        // Special handling for duplicates mode
        if (mode === 'duplicates') {
            renderDuplicatesView();
        } else {
            filterAndSort(true); // Scroll to top on workspace change
        }
        updateURL();
    } catch (e) {
        alert("Error in setWorkspaceMode: " + e.message + "\\n" + e.stack);
        console.error(e);
    }
}

/**
 * Cycle through layout modes: grid -> list -> treemap -> grid
 * Updates the toggle button icon to indicate the next mode
 */
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

/**
 * Set the display layout mode
 * Handles switching between grid, list, and treemap views with proper
 * show/hide of relevant UI elements and animations
 *
 * @param {string} layout - Layout mode ('grid', 'list', 'treemap')
 * @param {boolean} [skipURLUpdate=false] - If true, don't update browser URL
 */
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

/**
 * Update browser URL to reflect current application state
 * Enables deep linking and browser back/forward navigation
 * Maps workspace modes to paths: /lobby, /favorites, /vault, /duplicates, /review
 */
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
        else if (workspaceMode === 'duplicates') path = '/duplicates';
        else if (path.startsWith('/collections/')) { } // Keep existing path for collections
        else path = '/lobby';

        // Add view param if not grid
        if (currentLayout !== 'grid') {
            path += `?view=${currentLayout}`;
        }
    }

    // Only push if changed (ignoring duplicate slashes etc)
    const currentPath = window.location.pathname + window.location.search;
    if (currentPath !== path) {
        window.history.pushState({ layout: currentLayout, folder: treemapCurrentFolder, mode: workspaceMode }, '', path);
    }
}

/**
 * Initialize application state from current URL on page load
 * Parses path and query params to restore workspace, layout, and collection filters
 * Supports deep links to /favorites, /vault, /duplicates, /review, /treeview, /collections/*
 */
function loadFromURL() {
    const path = window.location.pathname;
    const params = new URLSearchParams(window.location.search);

    // Default
    let mode = 'lobby';
    let layout = params.get('view') || 'grid';

    if (path === '/favorites') mode = 'favorites';
    else if (path === '/review') mode = 'optimized';
    else if (path === '/vault') mode = 'vault';
    else if (path === '/duplicates') mode = 'duplicates';
    else if (path === '/treeview') {
        mode = 'lobby';
        layout = 'treemap';
    }
    else if (path.startsWith('/collections/')) {
        mode = 'lobby'; // Start in lobby mode but with filter
        const collectionName = decodeURIComponent(path.substring('/collections/'.length));

        // Wait for settings to be loaded? NO, userSettings is global and loaded in main block.
        // Assuming userSettings is available.
        if (userSettings && userSettings.smart_collections) {
            const col = userSettings.smart_collections.find(c => c.name === collectionName);
            if (col) {
                activeSmartCollectionCriteria = col.criteria;
                activeCollectionId = col.id;
                // We'll rely on renderUI -> renderFolderSidebar/renderCollections to highlight it?
                // Actually filterAndSort uses activeSmartCollectionCriteria.
            }
        }
    }

    // Overrides from params
    if (params.get('view') === 'treemap') layout = 'treemap';
    if (params.get('folder')) treemapCurrentFolder = decodeURIComponent(params.get('folder'));

    // Check deep links
    if (path.startsWith('/collections/')) {
        // We set mode='lobby' above, but here we MUST preserve the collection we found
        setWorkspaceMode(mode, true);
    } else {
        setWorkspaceMode(mode);
    }

    // Force layout if treeview
    if (layout === 'treemap') {
        setLayout('treemap');
    }

    // Check for deep links (navigating back/forward)
    checkDeepLinks();
}

// --- PERFORMANCE ENGINE: FILTER & SORT ---

/**
 * Main filtering and sorting pipeline for the video library
 * Applies all active filters (status, codec, search, tags, size, date, workspace)
 * and sorts the result according to the current sort order.
 *
 * @param {boolean} [scrollToTop=false] - Whether to scroll to top after filtering
 *
 * Flow:
 * 1. If in 'optimized' workspace, finds original/optimized file pairs
 * 2. Otherwise, filters ALL_VIDEOS based on all active criteria
 * 3. Applies smart collection criteria if active
 * 4. Sorts the filtered results
 * 5. Updates UI counts and triggers re-render
 */
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
                // Extract common values once
                const name = v.FilePath.split(/[\\/]/).pop().toLowerCase();
                const codec = v.codec || 'unknown';
                const isHidden = v.hidden || false;
                const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
                const folder = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';
                const videoTags = v.tags || [];

                // --- EARLY RETURNS (fail fast) ---

                // Smart Collection filter
                if (activeSmartCollectionCriteria && !evaluateCollectionMatch(v, activeSmartCollectionCriteria)) {
                    return false;
                }

                // Safe Mode filter
                if (safeMode && isSensitive(v)) {
                    return false;
                }

                // Workspace filter (lobby/vault/favorites)
                if (workspaceMode === 'lobby' && isHidden) return false;
                if (workspaceMode === 'vault' && !isHidden) return false;
                if (workspaceMode === 'favorites' && !v.favorite) return false;

                // Status filter
                if (currentFilter !== 'all') {
                    if (currentFilter === 'optimized_files') {
                        if (!v.FilePath.includes('_opt') && !v.FilePath.includes('_trim')) return false;
                    } else if (v.Status !== currentFilter) {
                        return false;
                    }
                }

                // Codec filter
                if (currentCodec !== 'all' && !codec.includes(currentCodec)) {
                    return false;
                }

                // Search filter
                if (searchTerm && !name.includes(searchTerm) && !v.FilePath.toLowerCase().includes(searchTerm)) {
                    return false;
                }

                // Folder filter
                if (currentFolder !== 'all' && folder !== currentFolder) {
                    return false;
                }

                // Size filter
                if (minSizeMB !== null && v.Size_MB < minSizeMB) return false;
                if (maxSizeMB !== null && v.Size_MB > maxSizeMB) return false;

                // Date filter
                if (dateFilter !== 'all') {
                    const now = Date.now() / 1000;
                    const fileTime = v.imported_at > 0 ? v.imported_at : (v.mtime || 0);
                    const ageSec = now - fileTime;
                    const maxAge = { '1d': 86400, '7d': 7 * 86400, '30d': 30 * 86400 }[dateFilter];
                    if (maxAge && ageSec > maxAge) return false;
                }

                // Tag filter (with tri-state include/exclude support)
                if (filterUntaggedOnly) {
                    if (videoTags.length > 0) return false;
                } else if (activeTags.length > 0) {
                    const positiveTags = activeTags.filter(t => !t.startsWith('!'));
                    const negativeTags = activeTags.filter(t => t.startsWith('!')).map(t => t.substring(1));

                    // Must have ALL positive tags
                    if (positiveTags.length > 0 && !positiveTags.every(pt => videoTags.includes(pt))) {
                        return false;
                    }
                    // Must have NONE of the negative tags
                    if (negativeTags.length > 0 && negativeTags.some(nt => videoTags.includes(nt))) {
                        return false;
                    }
                }

                // Passed all filters - count and include
                vCount++;
                tSize += v.Size_MB;
                return true;
            });
        }

        // Sort
        if (workspaceMode !== 'optimized') {
            filteredVideos.sort((a, b) => {
                if (currentSort === 'bitrate') return (b.Bitrate_Mbps || 0) - (a.Bitrate_Mbps || 0);
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

// formatSize is now defined in formatters.js
// This comment preserves the location for reference

// --- PERFORMANCE ENGINE: INFINITE SCROLL ---

/**
 * Main render function that manages the video grid/list display
 * Uses batch rendering for performance with large libraries
 *
 * @param {boolean} reset - If true, clears existing content and starts fresh
 * @param {boolean} [scrollToTop=false] - If true, scrolls viewport to top
 */
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

/**
 * Render the next batch of video cards using document fragment for performance
 * Called by IntersectionObserver when user scrolls near the bottom
 * Uses BATCH_SIZE constant to limit DOM operations per call
 */
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

/**
 * Create a side-by-side comparison card for original vs optimized video pairs
 * Used in the 'optimized' workspace to help users decide which version to keep
 *
 * @param {Object} pair - Object containing original and optimized video data
 * @param {Object} pair.original - Original video metadata
 * @param {Object} pair.optimized - Optimized video metadata
 * @returns {HTMLElement} DOM element for the comparison card
 */
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

    // Use shared formatters from formatters.js
    // formatSizeCompact and formatBitrate are available globally

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
                 <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[10px] bg-black/80 text-white font-mono font-bold backdrop-blur">${formatSizeCompact(orig.Size_MB)}</span>
            </div>
            
            <div class="text-[10px] text-gray-400 font-mono flex justify-between px-1">
                <span class="truncate font-medium text-gray-300" title="${orig.FilePath}">${orig.FilePath.split(/[\\\\/]/).pop()}</span>
                <span>${orig.Bitrate_Mbps.toFixed(1)} Mb/s</span>
            </div>
            ${!window.IS_DOCKER ? `
            <button class="text-xs text-gray-500 hover:text-white flex items-center gap-1 px-1 transition-colors" onclick="revealInFinder('${orig.FilePath.replace(/'/g, "\\'")}')">
                <span class="material-icons text-[12px]">folder_open</span> Reveal
            </button>
            ` : ''}
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
                 <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[10px] bg-arcade-cyan/20 text-arcade-cyan font-mono font-bold backdrop-blur border border-arcade-cyan/30">${formatSizeCompact(opt.Size_MB)}</span>
            </div>
            
            <div class="text-[10px] text-gray-400 font-mono flex justify-between px-1">
                <span class="truncate font-medium text-gray-300" title="${opt.FilePath}">${opt.FilePath.split(/[\\\\/]/).pop()}</span>
                <span>${opt.Bitrate_Mbps.toFixed(1)} Mb/s</span>
            </div>
             ${!window.IS_DOCKER ? `
             <button class="text-xs text-gray-500 hover:text-white flex items-center gap-1 px-1 transition-colors" onclick="revealInFinder('${opt.FilePath.replace(/'/g, "\\'")}')">
                <span class="material-icons text-[12px]">folder_open</span> Reveal
            </button>
            ` : ''}
        </div>
    `;

    // Store data for interactions
    container.setAttribute('data-path', orig.FilePath); // Proxy original
    return container;
}

function keepOptimized(orig, opt) {
    if (!confirm("Replace original with optimized version? This cannot be undone.")) return;
    fetch(`/api/keep_optimized?original=${orig}&optimized=${opt}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            // Remove from view
            setTimeout(() => {
                location.reload(); // Simplest way to refresh state
            }, 500);
        })
        .catch(err => {
            console.error('keepOptimized error:', err);
            alert('Failed to keep optimized file: ' + err.message);
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

// formatDuration is now defined in formatters.js
// This comment preserves the location for reference

/**
 * Create a video/image card element for the grid or list view
 * Includes thumbnail, metadata badges, action buttons, and tag display
 *
 * @param {Object} v - Video/image metadata object
 * @param {string} v.FilePath - Full path to the file
 * @param {number} v.Size_MB - File size in megabytes
 * @param {number} v.Bitrate_Mbps - Video bitrate in Mbps
 * @param {string} v.Status - Quality status ('HIGH' or 'OK')
 * @param {string} v.codec - Video codec name
 * @param {string} v.thumb - Thumbnail filename
 * @param {string} [v.media_type] - Type of media ('video' or 'image')
 * @param {boolean} [v.favorite] - Whether item is favorited
 * @param {boolean} [v.hidden] - Whether item is in vault
 * @param {string[]} [v.tags] - Array of tag names
 * @returns {HTMLElement} DOM element for the video card
 */
function createVideoCard(v) {
    const container = document.createElement('div');
    // Using utility classes for the card wrapper
    // group relative w-full bg-[#14141c] rounded-xl overflow-hidden border border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container
    container.className = 'group relative w-full bg-[#14141c] rounded-xl overflow-hidden border border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container flex flex-col';
    // Debug layout
    if (window.debugLayout) console.log('Created card with classes:', container.className);
    container.setAttribute('data-path', v.FilePath); // Keep this for JS logic

    const isHevc = (v.codec || '').includes('hevc') || (v.codec || '').includes('h265');
    const barW = Math.min(100, ((v.Bitrate_Mbps || 0) / 25) * 100);
    const fileName = v.FilePath.split(/[\\\\/]/).pop();
    const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
    const dirName = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';

    container.innerHTML = `
        <!-- Thumbnail (Card Media) -->
        <div class="card-media relative aspect-video bg-black overflow-hidden group cursor-pointer" 
             onclick="openCinema(this)">
             
             <!-- Image Type Indicator -->
             ${v.media_type === 'image' ? `
                 <div class="absolute top-2 left-10 z-20 bg-purple-900/80 backdrop-blur rounded px-1.5 py-0.5 text-[10px] font-bold text-purple-300 border border-purple-500/30 flex items-center gap-1">
                     <span class="material-icons text-[12px]">image</span>
                     IMG
                 </div>
             ` : ''}

             <!-- Corner Checkbox -->
             <div class="absolute top-2 left-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                <input type="checkbox" class="w-4 h-4 rounded border-gray-600 bg-black/50 text-arcade-cyan focus:ring-0 cursor-pointer" aria-label="Select" onclick="event.stopPropagation(); toggleSelection(this, event, '${v.FilePath.replace(/'/g, "\\'")}')">
             </div>

             <!-- Favorite Star -->
             <button class="favorite-btn absolute top-2 right-2 z-20 w-8 h-8 rounded-full bg-black/40 backdrop-blur hover:bg-black/60 flex items-center justify-center transition-all ${v.favorite ? 'text-arcade-gold active scale-110' : 'text-gray-400 opacity-0 group-hover:opacity-100'}"
                onclick="event.stopPropagation(); toggleFavorite(this.closest('.video-card-container'))">
                <span class="material-icons text-lg">${v.favorite ? 'star' : 'star_border'}</span>
             </button>

             <img src="/thumbnails/${v.thumb}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" loading="lazy">

             
             <!-- Quick Actions Overlay -->
             <div class="hidden md:flex absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity items-center justify-center gap-3">
                 ${!window.IS_DOCKER ? `
                 <button class="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="Reveal" onclick="event.stopPropagation(); revealInFinder('${v.FilePath.replace(/'/g, "\\'")}')">
                    <span class="material-icons">folder_open</span>
                 </button>
                 ` : ''}
                 <button class="w-12 h-12 rounded-full bg-arcade-cyan/20 hover:bg-arcade-cyan text-arcade-cyan hover:text-black border border-arcade-cyan/50 flex items-center justify-center backdrop-blur transition-all transform hover:scale-110 shadow-[0_0_15px_rgba(0,255,208,0.3)]" title="Play" onclick="event.stopPropagation(); openCinema(this.closest('.card-media'))">
                    <span class="material-icons text-3xl">play_arrow</span>
                 </button>
                 <button class="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="${v.hidden ? 'Restore' : 'Move to Vault'}" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))">
                    <span class="material-icons">${v.hidden ? 'unarchive' : 'archive'}</span>
                 </button>
                  ${(window.userSettings?.enable_optimizer !== false && window.ENABLE_OPTIMIZER !== false) ? `
                 <button class="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="Optimize" onclick="event.stopPropagation(); window.open('/compress?path=${encodeURIComponent(v.FilePath)}&audio=standard', 'h_frame')">
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
        <div class="card-body p-3 flex flex-col gap-1">
            <h3 class="text-sm font-medium text-gray-200 line-clamp-1 group-hover:text-arcade-cyan transition-colors" title="${fileName}">${fileName}</h3>
            <p class="text-[11px] text-gray-500 truncate" title="${v.FilePath}">${dirName}</p>
            
            ${renderVideoCardTags(v.tags || [])}
            
            <div class="flex items-center justify-between mt-1 text-xs font-mono text-gray-400">
                <div class="flex items-center gap-2">
                    <span class="bg-white/5 px-1.5 py-0.5 rounded text-[10px]">${v.Size_MB.toFixed(0)} MB</span>
                    ${v.media_type === 'video' ? `<span>${v.Bitrate_Mbps.toFixed(1)} Mb/s</span>` : ''}
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

// --- CARD ACTIONS ---

/**
 * Toggle hidden/vault state for a video card
 * Updates local state, sends to server, and animates card out if no longer visible
 *
 * @param {HTMLElement} card - The video card container element
 */
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

/**
 * Toggle favorite state for a video card
 * Updates local state, sends to server, and updates star icon
 *
 * @param {HTMLElement} card - The video card container element
 */
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
        starBtn.title = 'Add to Favorites';
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

/**
 * Set favorite state for all selected videos
 * Batch operation that updates multiple items at once
 *
 * @param {boolean} state - True to favorite, false to unfavorite
 */
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
            starBtn.title = 'Add to Favorites';
        }
    });

    clearSelection();
    if (workspaceMode === 'favorites' && !state) {
        setTimeout(() => filterAndSort(), 350);
    }
}

// --- CINEMA MODULE ---
// Cinema functionality has been extracted to cinema.js
// Functions available: openCinema, closeCinema, navigateCinema, cinemaFavorite,
// cinemaVault, cinemaLocate, toggleCinemaInfo, toggleCinemaTagPanel, toggleCinemaTag

// --- BATCH OPERATIONS ---
const BATCH_MIN_SIZE_MB = 50; // Files smaller than this are skipped by optimizer

/**
 * Update the batch action bar UI based on current selection
 * Shows/hides the bar and updates count display including skip warnings
 */
function updateBatchSelection() {
    const selectedCheckboxes = document.querySelectorAll('.video-card-container input:checked');
    const count = selectedCheckboxes.length;
    const bar = document.getElementById('batchBar');

    // Calculate how many will be skipped due to size
    let processableCount = 0;
    let skippedCount = 0;

    selectedCheckboxes.forEach(cb => {
        const container = cb.closest('.video-card-container');
        const path = container.getAttribute('data-path');
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (video) {
            if (video.Size_MB >= BATCH_MIN_SIZE_MB) {
                processableCount++;
            } else {
                skippedCount++;
            }
        }
    });

    // Update display
    const countEl = document.getElementById('batchCount');
    const skipWarning = document.getElementById('batchSkipWarning');

    if (countEl) countEl.innerText = count;

    // Show/create skip warning
    if (skippedCount > 0 && count > 0) {
        if (!skipWarning) {
            // Create warning element if it doesn't exist
            const warningSpan = document.createElement('span');
            warningSpan.id = 'batchSkipWarning';
            warningSpan.className = 'batch-skip-warning';
            warningSpan.style.cssText = 'color: #F4B342; font-size: 0.85rem; display: flex; align-items: center; gap: 4px;';
            const countSpan = document.getElementById('batchCount');
            if (countSpan && countSpan.parentElement) {
                countSpan.parentElement.insertAdjacentElement('afterend', warningSpan);
            }
        }
        const warning = document.getElementById('batchSkipWarning');
        if (warning) {
            warning.innerHTML = `<span class="material-icons" style="font-size: 16px;">warning</span> ${skippedCount} under ${BATCH_MIN_SIZE_MB}MB`;
            warning.title = `${skippedCount} file(s) will be skipped because they are already under ${BATCH_MIN_SIZE_MB}MB`;
        }
    } else if (skipWarning) {
        skipWarning.innerHTML = '';
    }

    if (count > 0) bar.classList.add('active');
    else bar.classList.remove('active');
}


/**
 * Clear all checkbox selections and update the batch bar
 */
function clearSelection() {
    document.querySelectorAll('.video-card-container input:checked').forEach(i => i.checked = false);
    updateBatchSelection();
}

// --- BATCH SELECTION HELPERS ---
let lastCheckedPath = null;

/**
 * Handle checkbox toggle with shift-click range selection support
 *
 * @param {HTMLInputElement} checkbox - The checkbox element
 * @param {MouseEvent} event - Click event to check for shift key
 * @param {string} path - File path of the video
 */
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

/**
 * Select all videos currently visible in the filtered list
 */
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

/**
 * Set hidden/vault state for all selected videos
 *
 * @param {boolean} state - True to hide (move to vault), false to restore
 */
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

/**
 * Start batch compression for all selected videos
 * Filters out files under BATCH_MIN_SIZE_MB and shows confirmation dialog
 * with details about which files will be processed vs skipped
 */
function triggerBatchCompress() {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));

    if (paths.length === 0) return;

    // Categorize files by processable vs skipped
    const processable = [];
    const skipped = [];

    paths.forEach(path => {
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (video) {
            const filename = path.split(/[\\/]/).pop();
            if (video.Size_MB >= BATCH_MIN_SIZE_MB) {
                processable.push({ path, filename, size: video.Size_MB });
            } else {
                skipped.push({ path, filename, size: video.Size_MB });
            }
        }
    });

    // Build detailed confirmation message
    let message = `🎬 Batch Compression Summary\n${'─'.repeat(40)}\n`;
    message += `✅ Will process: ${processable.length} file(s)\n`;

    if (skipped.length > 0) {
        message += `⚠️ Will skip: ${skipped.length} file(s) (under ${BATCH_MIN_SIZE_MB}MB)\n`;
        message += `\n📦 Skipped files (already compact):\n`;
        skipped.slice(0, 5).forEach(f => {
            const shortName = f.filename.length > 40 ? f.filename.substring(0, 37) + '...' : f.filename;
            message += `   • ${shortName} (${f.size.toFixed(1)} MB)\n`;
        });
        if (skipped.length > 5) {
            message += `   ... and ${skipped.length - 5} more\n`;
        }
    }

    if (processable.length === 0) {
        alert(`⚠️ No files to process!\n\nAll ${skipped.length} selected file(s) are under ${BATCH_MIN_SIZE_MB}MB and will be skipped.\n\nThese files are already compact and don't need optimization.`);
        return;
    }

    message += `\n${'─'.repeat(40)}\nProceed with ${processable.length} file(s)?`;

    if (confirm(message)) {
        // Use ||| as separator to avoid issues with commas in filenames
        fetch(`/batch_compress?paths=` + encodeURIComponent(paths.join('|||')));
        alert(`🚀 Batch Optimierung gestartet!\n\n${processable.length} file(s) will be processed.\n${skipped.length} file(s) skipped (under ${BATCH_MIN_SIZE_MB}MB).`);
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

/**
 * Toggle the folder sidebar visibility
 */
function toggleFolderSidebar() {
    document.getElementById('folderSidebar').classList.toggle('active');
    renderFolderSidebar();
}

/**
 * Set the folder filter to show only videos from a specific directory
 * @param {string} folder - Folder path or 'all' for no filter
 */
function setFolderFilter(folder) {
    currentFolder = folder;
    filterAndSort();
    renderFolderSidebar();
}

/**
 * Initial render call for folder sidebar
 */
function initialRender() {
    renderFolderSidebar();
}

/**
 * Render the folder sidebar with folder list sorted by size
 */
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

/**
 * Reset all filters and return to default dashboard view
 */
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

/**
 * Toggle between linear and logarithmic scale for treemap sizing
 */
function toggleTreemapScale() {
    treemapUseLog = document.getElementById('treemapLogToggle').checked;
    renderTreemap();
}

/**
 * Render the treemap visualization
 * Shows either folder view (all folders) or file view (files in selected folder)
 * Uses canvas for efficient rendering of potentially thousands of items
 */
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
// ESC key handler for treemap zoom out
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const cinemaModal = document.getElementById('cinemaModal');
        const filterPanel = document.getElementById('filterPanel');

        if (cinemaModal && cinemaModal.classList.contains('active')) {
            // Cinema has priority
            e.preventDefault();
            e.stopPropagation();
            closeCinema();
            return;
        }

        if (filterPanel && filterPanel.classList.contains('active')) {
            closeFilterPanel();
            return;
        }

        if (currentLayout === 'treemap' && treemapCurrentFolder !== null) {
            e.preventDefault();
            treemapZoomOut();
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

// Init handled in DOMContentLoaded below

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

        const imageScanCheckbox = document.getElementById('settingsScanImages');
        if (imageScanCheckbox) imageScanCheckbox.checked = data.enable_image_scanning === true;

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
        min_image_size_kb: parseInt(document.getElementById('settingsMinImageSize').value) || 100,
        bitrate_threshold_kbps: parseInt(document.getElementById('settingsBitrate').value) || 15000,

        enable_fun_facts: document.getElementById('settingsFunFacts')?.checked || false,
        enable_optimizer: document.getElementById('settingsOptimizer')?.checked ?? true,
        enable_image_scanning: document.getElementById('settingsScanImages')?.checked || false,
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

            // Set Docker detection flag
            window.IS_DOCKER = data.is_docker || false;

            // Hide Locate button in Docker mode
            if (window.IS_DOCKER) {
                const locateBtn = document.getElementById('cinemaLocateBtn');
                if (locateBtn) locateBtn.style.display = 'none';
            }

            // Settings loaded successfully

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
            // Deep link to collection
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

// Keyboard Shortcuts for Settings Modal and Collection Modal
document.addEventListener('keydown', (e) => {
    const settingsModal = document.getElementById('settingsModal');
    const isSettingsOpen = settingsModal && settingsModal.classList.contains('active');

    const collectionModal = document.getElementById('collectionModal');
    const isCollectionOpen = collectionModal && collectionModal.classList.contains('active');

    // ESC to close modals (collection modal takes priority if both somehow open)
    if (e.key === 'Escape') {
        if (isCollectionOpen) {
            e.preventDefault();
            closeCollectionModal();
            return;
        }
        if (isSettingsOpen) {
            e.preventDefault();
            closeSettings();
            showToast('Settings closed', 'info');
            return;
        }
    }

    if (isSettingsOpen) {
        // Cmd+S (Mac) or Ctrl+S (Windows/Linux) to save
        if ((e.metaKey || e.ctrlKey) && e.key === 's') {
            e.preventDefault();
            saveSettings();
            showToast('Saving settings...', 'success');
        }
    }
});

/**
 * Show a toast notification message
 * @param {string} message - Message to display
 * @param {string} [type='info'] - Toast type ('info', 'success', 'error')
 */
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

// --- HIDDEN PATH MODAL ---
let currentHiddenPath = '';

/**
 * Show modal with path info when file is in a hidden folder
 * Provides copy-to-clipboard functionality as an alternative to reveal
 * @param {string} path - Full path to the file
 */
function showHiddenPathModal(path) {
    currentHiddenPath = path;
    const modal = document.getElementById('hiddenPathModal');
    const pathDisplay = document.getElementById('hiddenPathDisplay');

    if (modal && pathDisplay) {
        pathDisplay.textContent = path;
        // Reset copy button state
        const copyIcon = document.getElementById('copyPathIcon');
        const copyText = document.getElementById('copyPathText');
        if (copyIcon) copyIcon.textContent = 'content_copy';
        if (copyText) copyText.textContent = 'Copy Path to Clipboard';

        modal.classList.add('active');
    }
}

/**
 * Close the hidden path modal
 */
function closeHiddenPathModal() {
    const modal = document.getElementById('hiddenPathModal');
    if (modal) modal.classList.remove('active');
    currentHiddenPath = '';
}

/**
 * Copy the current hidden path to clipboard
 */
async function copyHiddenPath() {
    if (!currentHiddenPath) return;

    try {
        await navigator.clipboard.writeText(currentHiddenPath);
        // Update button to show success
        const copyIcon = document.getElementById('copyPathIcon');
        const copyText = document.getElementById('copyPathText');
        if (copyIcon) copyIcon.textContent = 'check';
        if (copyText) copyText.textContent = 'Copied!';

        // Reset after 2 seconds
        setTimeout(() => {
            if (copyIcon) copyIcon.textContent = 'content_copy';
            if (copyText) copyText.textContent = 'Copy Path to Clipboard';
        }, 2000);
    } catch (err) {
        console.error('Failed to copy path:', err);
        showToast('Failed to copy path', 'error');
    }
}

/**
 * Reveal a file in the system file browser (Finder/Explorer)
 * Handles hidden folders by showing a modal with the path instead
 * @param {string} path - Full path to reveal
 */
async function revealInFinder(path) {
    try {
        const response = await fetch(`/reveal?path=${encodeURIComponent(path)}`);

        if (response.status === 204) {
            // Success - file was revealed
            return;
        }

        if (response.ok) {
            const data = await response.json();
            if (data.status === 'hidden_folder') {
                // Show helpful modal for hidden folder
                showHiddenPathModal(data.path);
                return;
            }
        }

        // Other errors
        console.error('Reveal failed:', response.status);
        showToast('Could not reveal file', 'error');
    } catch (err) {
        console.error('Reveal error:', err);
        showToast('Could not reveal file', 'error');
    }
}

// --- RESCAN ---

/**
 * Trigger a full library rescan
 * Shows loading state and reloads page when complete
 */
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
        .then(() => {
            location.reload();
        })
        .catch(e => {
            console.error(e);
            alert('Scan error: ' + e.message);
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
    const name = prompt("Name for this view:", "");
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

/**
 * Delete a saved view
 * @param {string} id - View ID to delete
 * @param {Event} [event] - Click event to stop propagation
 */
function deleteView(id, event) {
    if (event) event.stopPropagation();
    if (!confirm("Delete this view?")) return;

    if (userSettings.saved_views) {
        userSettings.saved_views = userSettings.saved_views.filter(v => v.id !== id);
        saveSettingsWithoutReload();
        renderSavedViews();
    }
}

/**
 * Save current settings to server without closing UI or reloading
 * Used for background saves (views, collections, etc.)
 */
function saveSettingsWithoutReload() {
    fetch(`/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userSettings)
    }).then(r => r.json()).then(data => {
        if (data.success) {
            // Views saved
        }
    });
}

// --- SMART COLLECTIONS MODULE ---
// Smart Collections functionality has been extracted to collections.js
// Functions available: openCollectionModal, closeCollectionModal, saveCollection,
// deleteCurrentCollection, applyCollection, renderCollections, evaluateCollectionMatch,
// getDefaultCollectionCriteria, toggleFilterAccordion, and related UI functions


// --- OPTIMIZATION PANEL LOGIC ---
let currentOptAudio = 'standard';

/**
 * Open the video optimization panel in cinema mode
 * Shows compression options, quality settings, and trim controls
 */
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
    currentOptAudio = 'standard'; // Reset to default (audio enhancement off)
    updateOptAudioUI();
    clearTrim(); // Reset trim

    // Reset Q Factor
    const qInput = document.getElementById('optQuality');
    const qSugg = document.getElementById('optQualitySuggestion');
    if (qInput) {
        qInput.value = 75; // Default start
        // Update suggestion based on current video
        if (typeof currentCinemaPath !== 'undefined') {
            const video = window.ALL_VIDEOS?.find(v => v.FilePath === currentCinemaPath);
            if (video && video.Bitrate_Mbps) {
                let sugg = 75;
                let reason = "Standard";

                if (video.Bitrate_Mbps > 20) {
                    sugg = 65;
                    reason = "High Bitrate";
                } else if (video.Bitrate_Mbps < 5) {
                    sugg = 80;
                    reason = "Low Bitrate";
                }

                if (qSugg) qSugg.innerText = `Suggested: ${sugg} (${reason})`;
            } else if (qSugg) {
                qSugg.innerText = "";
            }
        }
    }

    // Show panel
    panel.classList.add('active');
    const actions = document.getElementById('cinemaActions');
    if (actions) actions.style.display = 'none';
}

/**
 * Close the optimization panel
 */
function closeOptimize() {
    document.getElementById('optimizePanel').classList.remove('active');
    const actions = document.getElementById('cinemaActions');
    if (actions) actions.style.display = 'flex';
}

/**
 * Set audio optimization mode
 * @param {string} mode - 'standard' (passthrough) or 'enhanced' (normalize/denoise)
 */
function setOptAudio(mode) {
    currentOptAudio = mode;
    updateOptAudioUI();
}

let currentOptVideo = 'compress';

/**
 * Set video optimization mode
 * @param {string} mode - 'compress' (HEVC encode) or 'copy' (passthrough)
 */
function setOptVideo(mode) {
    currentOptVideo = mode;
    updateOptVideoUI();
}

/**
 * Update video mode button UI to reflect current selection
 */
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
    const qVal = document.getElementById('optQuality')?.value;

    // Simple validation
    // (Could add regex check for HH:MM:SS here but backend/ffmpeg handles partials well usually)

    const params = new URLSearchParams();
    params.set('path', currentCinemaPath);
    params.set('audio', currentOptAudio);
    params.set('video', currentOptVideo);
    if (ss) params.set('ss', ss);
    if (to) params.set('to', to);
    if (qVal) params.set('q', qVal);

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
// activeTags, filterUntaggedOnly, minSizeMB, maxSizeMB, dateFilter, availableTags are declared at the top of the file.

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

    // Sync size inputs
    const minSizeInput = document.getElementById('filterMinSize');
    if (minSizeInput) minSizeInput.value = minSizeMB !== null ? minSizeMB : '';
    const maxSizeInput = document.getElementById('filterMaxSize');
    if (maxSizeInput) maxSizeInput.value = maxSizeMB !== null ? maxSizeMB : '';

    // Sync date chips
    document.querySelectorAll('[data-filter="date"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === dateFilter);
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
    } else if (type === 'minSize') {
        minSizeMB = value === '' ? null : parseInt(value);
    } else if (type === 'maxSize') {
        maxSizeMB = value === '' ? null : parseInt(value);
    } else if (type === 'date') {
        dateFilter = value;
    }

    // Update chip visual state (for status, codec, date)
    if (type === 'status' || type === 'codec' || type === 'date') {
        document.querySelectorAll(`[data-filter="${type}"]`).forEach(btn => {
            btn.classList.toggle('active', btn.dataset.value === value);
        });
    }

    updateFilterPanelCount();
}

function toggleTagFilter(tagName) {
    const idxPos = activeTags.indexOf(tagName);
    const idxNeg = activeTags.indexOf('!' + tagName);

    // Tri-state: Inactive -> Positive -> Negative -> Inactive

    if (idxPos > -1) {
        // Was Positive -> Change to Negative
        activeTags.splice(idxPos, 1);
        activeTags.push('!' + tagName);
    } else if (idxNeg > -1) {
        // Was Negative -> Change to Inactive
        activeTags.splice(idxNeg, 1);
    } else {
        // Was Inactive -> Change to Positive
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
    if (minSizeMB !== null) count++;
    if (maxSizeMB !== null) count++;
    if (dateFilter !== 'all') count++;
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
    minSizeMB = null;
    maxSizeMB = null;
    dateFilter = 'all';

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

    // Size Chips
    if (minSizeMB !== null) chips.push({ label: `> ${minSizeMB} MB`, type: 'minSize' });
    if (maxSizeMB !== null) chips.push({ label: `< ${maxSizeMB} MB`, type: 'maxSize' });

    // Date Chips
    if (dateFilter !== 'all') {
        let label = 'Date';
        if (dateFilter === '1d') label = 'Last 24h';
        if (dateFilter === '7d') label = 'Last 7 Days';
        if (dateFilter === '30d') label = 'Last 30 Days';
        chips.push({ label: label, type: 'date' });
    }

    activeTags.forEach(tag => {
        // Handle negative tags
        const isNeg = tag.startsWith('!');
        const realName = isNeg ? tag.substring(1) : tag;

        const tagData = availableTags.find(t => t.name === realName);
        // Note: For display in the active filters row, we show them distinctively
        chips.push({
            label: realName,
            type: 'tag',
            color: isNeg ? '#ef4444' : (tagData?.color || '#888'),
            isNeg: isNeg
        });
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
        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-white/10 text-gray-300 border border-white/10 ${c.isNeg ? 'line-through decoration-red-500 decoration-2 text-red-200' : ''}">
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
    } else if (type === 'minSize') {
        minSizeMB = null;
        document.getElementById('filterMinSize').value = '';
    } else if (type === 'maxSize') {
        maxSizeMB = null;
        document.getElementById('filterMaxSize').value = '';
    } else if (type === 'date') {
        setDateFilter('all');
    } else if (type === 'tag') {
        // Handle removal of both normal and negative tags
        activeTags = activeTags.filter(t => t !== label && t !== '!' + label);
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
    fetch(`/api/tags?t=${new Date().getTime()}`)
        .then(res => res.json())
        .then(tags => {
            availableTags = tags || [];
            // Tags loaded
            try {
                renderFilterTagsList();
            } catch (e) {
                console.error("Error rendering filters:", e);
            }
            try {
                renderExistingTagsList();
            } catch (e) {
                console.error("Error rendering existing tags:", e);
            }
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

    container.innerHTML = availableTags.map(tag => {
        const isPos = activeTags.includes(tag.name);
        const isNeg = activeTags.includes('!' + tag.name);
        let classes = 'tag-filter-chip';
        let style = 'border-color: rgba(255,255,255,0.15)';

        if (isPos) {
            classes += ' active';
            style = `border-color: ${tag.color}`;
        } else if (isNeg) {
            classes += ' negative';
            style = `border-color: rgba(239, 68, 68, 0.5)`;
        }

        return `
        <button class="${classes}" 
                onclick="toggleTagFilter('${tag.name}')"
                style="${style}">
            <span class="tag-dot" style="background-color: ${isNeg ? '#ef4444' : tag.color}"></span>
            ${tag.name}
        </button>
        `;
    }).join('');
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

// Cinema tag functions are now in cinema.js
// (toggleCinemaTagPanel, updateCinemaTags, toggleCinemaTag)

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
    const shortcutInput = document.getElementById('newTagShortcut');

    const name = nameInput?.value?.trim();
    const color = colorInput?.value || '#00ffd0';
    let shortcut = shortcutInput?.value?.trim().toUpperCase() || '';

    if (!name) {
        alert('Please enter a tag name');
        return;
    }

    // Validate shortcut
    const reservedKeys = ['F', 'V'];
    if (shortcut && reservedKeys.includes(shortcut)) {
        alert(`Shortcut "${shortcut}" is reserved. Please use a different letter.`);
        return;
    }
    if (shortcut && !/^[A-Z]$/.test(shortcut)) {
        alert('Shortcut must be a single letter A-Z');
        return;
    }

    fetch('/api/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, color, shortcut: shortcut || null })
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
                // Clear inputs
                nameInput.value = '';
                if (shortcutInput) shortcutInput.value = '';
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

    // Use global availableTags which is updated by loadAvailableTags()
    const tags = availableTags || [];
    // Rendering existing tags

    const header = document.getElementById('manageTagsHeader');

    if (header) {
        header.textContent = `Manage Existing Tags (${tags.length})`;
        header.style.color = '';
    } else {
        // Fallback to find header if id is missing
        const h3s = container.parentElement.querySelectorAll('h3');
        if (h3s.length > 0) {
            h3s[0].textContent = `Manage Existing Tags (${tags.length})`;
            h3s[0].id = 'manageTagsHeader';
        }
    }

    if (tags.length === 0) {
        container.innerHTML = '<div class="text-gray-500 text-sm italic py-4">No tags yet</div>';
        return;
    }

    container.innerHTML = tags.map(t => {
        const shortcutValue = t.shortcut ? t.shortcut.toUpperCase() : '';
        const shortcutDisplay = shortcutValue
            ? `<span class="text-xs px-1.5 py-0.5 rounded bg-white/10 text-gray-400 cursor-pointer hover:bg-white/20" onclick="editTagShortcut('${t.name}', '${shortcutValue}')" title="Click to edit">(${shortcutValue})</span>`
            : `<span class="text-xs text-gray-600 cursor-pointer hover:text-gray-400" onclick="editTagShortcut('${t.name}', '')" title="Click to add shortcut">+ key</span>`;
        return `
        <div class="flex items-center justify-between py-2 px-3 bg-black/30 rounded-lg border border-white/5 group" id="tag-row-${t.name}">
            <div class="flex items-center gap-3">
                <span class="w-4 h-4 rounded-full" style="background-color: ${t.color}"></span>
                <span class="text-white text-sm">${t.name}</span>
                ${shortcutDisplay}
            </div>
            <button onclick="deleteTag('${t.name}')" class="text-gray-500 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100">
                <span class="material-icons text-lg">delete</span>
            </button>
        </div>
    `;
    }).join('');
}

function editTagShortcut(tagName, currentShortcut) {
    const newShortcut = prompt(`Enter shortcut key for "${tagName}" (A-Z, or leave empty to remove):`, currentShortcut);

    if (newShortcut === null) return; // Cancelled

    const shortcut = newShortcut.trim().toUpperCase();

    // Validate
    if (shortcut && !/^[A-Z]$/.test(shortcut)) {
        alert('Shortcut must be a single letter A-Z');
        return;
    }
    if (['F', 'V'].includes(shortcut)) {
        alert(`"${shortcut}" is reserved. Please use a different letter.`);
        return;
    }

    // Update tag
    fetch('/api/tags/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: tagName, shortcut: shortcut || null })
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadAvailableTags();
            }
        })
        .catch(err => console.error('Failed to update tag:', err));
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
        // ESC for filter panel is now handled by the main global handler.
        // This block is kept for other potential shortcuts or modal handlers.

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
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize workspace theming
    const initialWorkspace = workspaceMode || 'lobby';
    document.body.setAttribute('data-workspace', initialWorkspace);

    // Apply initial workspace colors
    const wsColors = {
        lobby: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
        favorites: { accent: '#F4B342', bg: 'rgba(244, 179, 66, 0.05)' },
        optimized: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
        review: { accent: '#00ffd0', bg: 'rgba(0, 255, 208, 0.05)' },
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

    // --- CATEGORY MANAGEMENT FUNCTIONS ---
    function getAvailableCategories() {
        const collections = userSettings.smart_collections || [];
        const categories = new Set();
        collections.forEach(c => {
            if (c.category && c.category !== 'Uncategorized') {
                categories.add(c.category);
            }
        });
        return Array.from(categories).sort();
    }

    function populateCategoryDropdown(selectedCategory = null) {
        const select = document.getElementById('collectionCategory');
        if (!select) return;

        const categories = getAvailableCategories();

        select.innerHTML = '<option value="">Uncategorized</option>' +
            categories.map(cat =>
                `<option value="${cat}" ${cat === selectedCategory ? 'selected' : ''}>${cat}</option>`
            ).join('');
    }

    function handleCategoryChange(selectEl) {
        // Just track changes - saving happens in saveCollection
    }

    function toggleNewCategoryInput() {
        const select = document.getElementById('collectionCategory');
        const input = document.getElementById('newCategoryInput');
        const btn = document.getElementById('addCategoryBtn');

        if (!select || !input || !btn) return;

        const isHidden = input.classList.contains('hidden');

        if (isHidden) {
            // Show input, hide select
            select.classList.add('hidden');
            input.classList.remove('hidden');
            input.focus();
            btn.innerHTML = '<span class="material-icons text-sm">close</span>';
            btn.title = "Cancel";
        } else {
            // Hide input, show select
            select.classList.remove('hidden');
            input.classList.add('hidden');
            input.value = '';
            btn.innerHTML = '<span class="material-icons text-sm">add</span>';
            btn.title = "Add new category";
        }
    }

    // Expose to window
    window.toggleCategoryCollapse = toggleCategoryCollapse;
    window.populateCategoryDropdown = populateCategoryDropdown;
    window.handleCategoryChange = handleCategoryChange;
    window.toggleNewCategoryInput = toggleNewCategoryInput;

    // --- USER DATA HYDRATION ---
    async function loadUserData() {
        try {
            console.log("Hydrating user data...");
            const res = await fetch('/api/user/data');
            if (res.ok) {
                const data = await res.json();
                const favSet = new Set(data.favorites || []);
                const vaultSet = new Set(data.vaulted || []);
                const tagMap = data.tags || {};

                // Hydrate Sensitive Settings (Safe Mode) - Migrated from global config
                if (!window.userSettings) window.userSettings = {};
                window.userSettings.sensitive_dirs = data.sensitive_dirs || [];
                window.userSettings.sensitive_tags = data.sensitive_tags || [];
                window.userSettings.sensitive_collections = data.sensitive_collections || [];

                // Apply to global ALL_VIDEOS
                if (window.ALL_VIDEOS) {
                    window.ALL_VIDEOS.forEach(v => {
                        v.favorite = favSet.has(v.FilePath);
                        v.hidden = vaultSet.has(v.FilePath);
                        v.tags = tagMap[v.FilePath] || [];
                    });
                }
                console.log(`✅ User data loaded: ${favSet.size} favs, ${vaultSet.size} vaulted.`);
            } else {
                console.warn("User data load failed:", res.status);
                // If unauthorized (session expired?), reload to trigger login check
                if (res.status === 401 || res.status === 403) window.location.reload();
            }
        } catch (e) {
            console.error("Error loading user data:", e);
        }
    }

    // 1. Load Settings FIRST (async)
    // This ensures userSettings.smart_collections is populated before we parse URL
    await loadSettings();

    // 1a. Load Videos for this user (Isolation)
    await loadVideoData();

    // 1b. Load User Data (Hydrate Global Video List)
    await loadUserData();

    // 2. Initial Render (Sidebar etc)
    initialRender();

    // 3. Parse URL and set initial state
    loadFromURL();

    // Add double-click handler to stats display for quick treemap access
    const statsDisplay = document.querySelector('.stats-display');
    if (statsDisplay) {
        statsDisplay.addEventListener('dblclick', () => {
            setLayout('treemap');
            // Update toggle button icon
            const btn = document.getElementById('toggleView');
            if (btn) btn.innerHTML = '<span class="material-icons">view_module</span>';
        });
    }

    // Render views and collections
    setTimeout(() => {
        renderSavedViews();
        renderCollections();
        // Force one last filter execution to ensure everything is matched
        filterAndSort();
    }, 500);
});

async function loadVideoData() {
    try {
        const res = await fetch('/api/videos');
        if (res.ok) {
            window.ALL_VIDEOS = await res.json();
            console.log(`✅ Loaded ${window.ALL_VIDEOS.length} videos from API`);
            updateHeaderStats();
        } else {
            console.error("Failed to load videos", res.status);
        }
    } catch (e) {
        console.error("Error loading videos:", e);
    }
}

function updateHeaderStats() {
    if (!window.ALL_VIDEOS) return;

    // Count videos and images
    let videoCount = 0;
    let imageCount = 0;
    let totalSize = 0;

    window.ALL_VIDEOS.forEach(item => {
        const mediaType = item.media_type || 'video';
        if (mediaType === 'video') {
            videoCount++;
        } else if (mediaType === 'image') {
            imageCount++;
        }
        totalSize += item.Size_MB || 0;
    });

    // Update video count
    const videoCountEl = document.getElementById('header-video-count');
    if (videoCountEl) {
        videoCountEl.textContent = videoCount;
    }

    // Update image count and show section if there are images
    const imageCountEl = document.getElementById('header-image-count');
    const imageSection = document.getElementById('image-count-section');
    const imageSeparator = document.getElementById('image-separator');

    if (imageCount > 0) {
        if (imageCountEl) imageCountEl.textContent = imageCount;
        if (imageSection) imageSection.style.display = 'flex';
        if (imageSeparator) imageSeparator.style.display = 'block';
    } else {
        if (imageSection) imageSection.style.display = 'none';
        if (imageSeparator) imageSeparator.style.display = 'none';
    }

    // Update total size (including both videos and images)
    const sizeEl = document.getElementById('header-size');
    if (sizeEl) {
        const sizeGB = (totalSize / 1024).toFixed(1);
        sizeEl.textContent = sizeGB + ' GB';
    }
}

async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        window.location.reload();
    } catch (e) {
        console.error("Logout failed", e);
        window.location.reload();
    }
}

// ============================================================================
// DUPLICATE DETECTION
// ============================================================================
let duplicateData = null;
let duplicatePollInterval = null;

async function loadDuplicates() {
    try {
        // 1. Check if we already have results cached
        const res = await fetch('/api/duplicates');
        if (res.ok) {
            const data = await res.json();
            if (data.summary && data.summary.scan_run) {
                duplicateData = data;
                console.log(`🔍 Found cached results: ${duplicateData.summary.total_groups} groups`);
                return duplicateData;
            }
        }

        // 2. If no cache, trigger a new scan
        console.log("No cached results, triggering scan...");
        const scanRes = await fetch('/api/duplicates/scan', { method: 'POST' });
        if (scanRes.status === 202 || scanRes.status === 409) {
            // Scan started or already running
            return "scanning";
        }

    } catch (e) {
        console.error("Error loading duplicates:", e);
    }
    return null;
}

function pollDuplicateStatus(grid) {
    // Clear any existing poll first
    if (duplicatePollInterval) clearInterval(duplicatePollInterval);

    const statusText = document.getElementById('scan-status-text');
    const progressBar = document.getElementById('scan-progress-bar');
    const progressText = document.getElementById('scan-progress-text');

    duplicatePollInterval = setInterval(async () => {
        // Stop polling if we navigated away
        if (workspaceMode !== 'duplicates') {
            clearInterval(duplicatePollInterval);
            duplicatePollInterval = null;
            return;
        }

        try {
            const res = await fetch('/api/duplicates/status');
            if (!res.ok) return;

            const status = await res.json();

            if (status.is_running) {
                // Update UI
                if (statusText) statusText.textContent = status.message || "Scanning...";
                if (progressBar) progressBar.style.width = `${status.progress}%`;
                if (progressText) progressText.textContent = `${status.progress}%`;
            } else {
                // Scan finished
                clearInterval(duplicatePollInterval);
                duplicatePollInterval = null;

                // Fetch final results
                const finalRes = await fetch('/api/duplicates');
                if (finalRes.ok) {
                    duplicateData = await finalRes.json();
                    renderDuplicatesView(); // Re-render with data
                }
            }
        } catch (e) {
            console.error("Polling error:", e);
            clearInterval(duplicatePollInterval);
        }
    }, 500);
}

function renderDuplicatesView() {
    // Safety check: Don't render if we switched away
    if (workspaceMode !== 'duplicates') return;

    const grid = document.getElementById('videoGrid');
    if (!grid) return;

    // Initial state or Loading state
    if (!duplicateData) {
        grid.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-24 gap-6">
                <!-- Spinner -->
                <div class="relative w-20 h-20">
                    <div class="absolute inset-0 rounded-full border-4 border-purple-500/20"></div>
                    <div class="absolute inset-0 rounded-full border-4 border-t-purple-500 border-r-transparent border-b-transparent border-l-transparent animate-spin"></div>
                </div>
                
                <!-- Status Text -->
                <div class="text-center">
                    <h3 class="text-xl font-bold text-white mb-2" id="scan-status-text">Starting visual analysis...</h3>
                    <p class="text-sm text-gray-400">This may take a minute for large libraries.</p>
                </div>
                
                <!-- Progress Bar -->
                <div class="w-full max-w-md bg-white/5 rounded-full h-4 overflow-hidden relative border border-white/5">
                    <div id="scan-progress-bar" class="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-300" style="width: 0%"></div>
                </div>
                <div class="text-xs text-gray-500 font-mono" id="scan-progress-text">0%</div>
            </div>
        `;

        loadDuplicates().then(result => {
            if (result === "scanning") {
                pollDuplicateStatus(grid);
            } else if (result && result.groups) {
                renderDuplicatesView(); // Recursively call to render data
            }
        });
        return;
    }

    // Empty State Check
    if (duplicateData.groups.length === 0) {
        grid.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-20 text-center">
                <span class="material-icons text-6xl text-gray-600 mb-4">check_circle</span>
                <h3 class="text-xl font-bold text-gray-400 mb-2">No Duplicates Found</h3>
                <p class="text-sm text-gray-500">Your library is clean! No duplicate media detected.</p>
            </div>
        `;
        return;
    }

    // Update sidebar count
    const countEl = document.getElementById('count-duplicates');
    if (countEl) countEl.textContent = duplicateData.summary.total_groups;

    // Render summary header
    let html = `
            <div class="col-span-full bg-gradient-to-r from-purple-900/20 to-pink-900/20 border border-purple-500/30 rounded-xl p-6 mb-4">
                <div class="flex items-center justify-between flex-wrap gap-4">
                    <div class="flex items-center gap-4">
                        <div class="w-14 h-14 rounded-xl bg-purple-500/20 flex items-center justify-center border border-purple-500/40">
                            <span class="material-icons text-3xl text-purple-400">content_copy</span>
                        </div>
                        <div>
                            <h2 class="text-xl font-bold text-white">Duplicate Media</h2>
                            <p class="text-sm text-gray-400">
                                Found <span class="text-purple-400 font-bold">${duplicateData.summary.total_groups}</span> groups
                                (<span class="text-cyan-400">${duplicateData.summary.video_groups}</span> videos,
                                <span class="text-pink-400">${duplicateData.summary.image_groups}</span> images)
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-4">
                        <div class="text-right">
                            <div class="text-2xl font-bold text-green-400">${duplicateData.summary.potential_savings_mb.toFixed(1)} MB</div>
                            <div class="text-xs text-gray-500 uppercase tracking-wider">Potential Savings</div>
                        </div>
                        <button onclick="rescanDuplicates()" class="px-4 py-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-white text-sm font-medium transition-colors flex items-center gap-2">
                            <span class="material-icons text-[18px]">refresh</span>
                            Rescan
                        </button>
                    </div>
                </div>
            </div>
        `;

    // Render each duplicate group
    duplicateData.groups.forEach((group, idx) => {
        const isVideo = group.media_type === 'video';
        const icon = isVideo ? 'movie' : 'image';
        const color = isVideo ? 'cyan' : 'pink';

        html += `
                <div class="col-span-full bg-[#14141c] rounded-xl border border-white/5 hover:border-${color}-500/30 overflow-hidden mb-4 transition-all">
                    <!-- Group Header -->
                    <div class="p-4 border-b border-white/5 flex items-center justify-between flex-wrap gap-2 bg-white/[0.02]">
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-${color}-400">${icon}</span>
                            <span class="text-xs font-bold text-gray-400 uppercase tracking-wide">
                                Group ${idx + 1} • ${group.match_type} match • ${group.files.length} files
                            </span>
                        </div>
                        <div class="flex items-center gap-4">
                            <span class="text-sm font-mono text-green-400">
                                +${group.potential_savings_mb.toFixed(0)} MB
                            </span>
                            <span class="text-xs text-gray-500 px-2 py-1 rounded bg-white/5">
                                ${Math.round(group.confidence * 100)}% match
                            </span>
                        </div>
                    </div>
                    
                    <!-- Files Grid -->
                    <div class="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-${Math.min(group.files.length, 4)} gap-4">
                        ${group.files.map((file, fIdx) => {
            const isKeep = file.path === group.recommended_keep;
            const thumbSrc = file.thumb ? `/thumbnails/${file.thumb}` : '/static/placeholder.png';
            return `
                                <div class="relative rounded-lg border ${isKeep ? 'border-green-500/50 bg-green-500/5' : 'border-white/10 bg-white/[0.02]'} overflow-hidden flex flex-col">
                                    ${isKeep ? `
                                        <div class="absolute top-2 right-2 z-10 px-2 py-0.5 rounded text-[10px] font-bold bg-green-500 text-black uppercase tracking-wider">
                                            Keep
                                        </div>
                                    ` : ''}
                                    
                                    <!-- Thumbnail -->
                                    <div class="relative aspect-video bg-black cursor-pointer group" onclick="openCinema(this)" data-path="${file.path}">
                                        <img src="${thumbSrc}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" loading="lazy">
                                        <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                            <span class="material-icons text-white text-3xl drop-shadow-lg">play_arrow</span>
                                        </div>
                                    </div>
                                    
                                    <div class="p-3 flex flex-col gap-2">
                                        <div class="text-sm font-medium text-gray-200 truncate" title="${file.path}">
                                            ${file.path.split(/[\\/]/).pop()}
                                        </div>
                                        
                                        <div class="text-xs text-gray-500 truncate" title="${file.path}">
                                            ${file.path.split(/[\\/]/).slice(-3, -1).join('/')}
                                        </div>
                                        
                                        <div class="flex items-center gap-2 text-[10px] text-gray-400 font-mono flex-wrap">
                                            <span class="bg-white/5 px-1.5 py-0.5 rounded">${file.size_mb.toFixed(0)} MB</span>
                                            ${file.width && file.height ? `<span class="bg-white/5 px-1.5 py-0.5 rounded">${file.width}×${file.height}</span>` : ''}
                                            ${file.bitrate_mbps ? `<span class="bg-white/5 px-1.5 py-0.5 rounded">${file.bitrate_mbps.toFixed(1)} Mbps</span>` : ''}
                                            <span class="ml-auto bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded">Q: ${file.quality_score.toFixed(0)}</span>
                                        </div>
                                        
                                        ${!window.IS_DOCKER ? `
                                        <!-- Reveal in Finder Button -->
                                        <button onclick="revealInFinder('${file.path.replace(/'/g, "\\'")}')"
                                                class="w-full py-1.5 rounded-lg bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/10 text-xs transition-all flex items-center justify-center gap-1">
                                            <span class="material-icons text-sm">folder_open</span>
                                            Reveal in Finder
                                        </button>
                                        ` : ''}
                                    </div>    
                                        ${!isKeep ? `
                                            <button onclick="deleteDuplicate('${encodeURIComponent(file.path)}')" 
                                                    class="w-full py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 border border-red-500/30 text-xs font-bold transition-all flex items-center justify-center gap-1">
                                                <span class="material-icons text-sm">delete</span>
                                                Delete
                                            </button>
                                        ` : `
                                            <div class="w-full py-2 rounded-lg bg-green-500/10 text-green-400 border border-green-500/30 text-xs font-bold text-center flex items-center justify-center gap-1">
                                                <span class="material-icons text-sm">verified</span>
                                                Best Quality
                                            </div>
                                        `}
                                    </div>
                            `;
        }).join('')}
                    </div>
                </div>
            `;
    });

    grid.innerHTML = html;
}

async function deleteDuplicate(encodedPath) {
    const path = decodeURIComponent(encodedPath);
    const filename = path.split(/[\\/]/).pop();

    if (!confirm(`Delete "${filename}"?\n\nThis cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch('/api/duplicates/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: [path] })
        });

        if (res.ok) {
            const result = await res.json();
            console.log(`✅ Deleted: ${result.deleted.length} files, freed ${result.freed_mb} MB`);

            // Find and remove the group containing this file
            if (duplicateData && duplicateData.groups) {
                const groupIndex = duplicateData.groups.findIndex(group =>
                    group.files.some(file => file.path === path)
                );

                if (groupIndex !== -1) {
                    // Remove the entire group since the duplicate case is resolved
                    duplicateData.groups.splice(groupIndex, 1);

                    // Update summary counts
                    duplicateData.summary.total_groups = duplicateData.groups.length;

                    // Recalculate savings
                    duplicateData.summary.potential_savings_mb = duplicateData.groups.reduce(
                        (sum, group) => sum + group.potential_savings_mb, 0
                    );

                    // Recalculate video/image group counts
                    duplicateData.summary.video_groups = duplicateData.groups.filter(
                        g => g.media_type === 'video'
                    ).length;
                    duplicateData.summary.image_groups = duplicateData.groups.filter(
                        g => g.media_type === 'image'
                    ).length;
                }
            }

            // Refresh view with updated data
            renderDuplicatesView();
        } else {
            alert('Failed to delete file');
        }
    } catch (e) {
        console.error('Delete error:', e);
        alert('Error deleting file');
    }
}

async function rescanDuplicates() {
    if (!confirm('This will clear the cached duplicate results and perform a fresh scan. Continue?')) {
        return;
    }

    try {
        // Clear the cache
        const clearRes = await fetch('/api/duplicates/clear', {
            method: 'POST'
        });

        if (!clearRes.ok) {
            alert('Failed to clear cache');
            return;
        }

        // Clear client-side data
        duplicateData = null;

        // Trigger a new scan by re-rendering (which will auto-start scan if no data)
        renderDuplicatesView();

    } catch (e) {
        console.error('Rescan error:', e);
        alert('Error triggering rescan');
    }
}

// =============================================================================
// FIRST-RUN SETUP WIZARD
// =============================================================================

let selectedSetupDirectories = [];

function checkSetupRequired() {
    fetch('/api/setup/status')
        .then(res => res.json())
        .then(data => {
            if (!data.setup_complete) {
                showSetupWizard();
            }
        });
}

function showSetupWizard() {
    const wizard = document.getElementById('setupWizard');
    if (wizard) {
        wizard.classList.remove('hidden');
        wizard.classList.add('active');
        loadSetupDirectories();
    }
}

function hideSetupWizard() {
    const wizard = document.getElementById('setupWizard');
    if (wizard) {
        wizard.classList.remove('active');
        setTimeout(() => wizard.classList.add('hidden'), 300);
    }
}

function loadSetupDirectories() {
    fetch('/api/setup/directories')
        .then(res => res.json())
        .then(data => {
            const listEl = document.getElementById('setupDirectoryList');
            if (!listEl) return;

            if (!data.directories || data.directories.length === 0) {
                listEl.innerHTML = '<div class="text-center py-8 text-gray-500">No directories found</div>';
                return;
            }

            listEl.innerHTML = data.directories.map(dir => {
                const sizeGB = (dir.size_bytes / (1024 * 1024 * 1024)).toFixed(2);
                const displayName = dir.name || dir.path;
                return `<div class="setup-dir-card" data-path="${dir.path}" onclick="toggleSetupDirectory('${dir.path}')">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-arcade-cyan">${dir.is_root ? 'folder_open' : 'folder'}</span>
                            <div><div class="text-white font-medium">${displayName}</div>
                            <div class="text-xs text-gray-500">${sizeGB} GB • ${dir.file_count.toLocaleString()} files</div></div>
                        </div>
                        <div class="setup-dir-checkbox hidden"><span class="material-icons text-arcade-cyan">check_circle</span></div>
                    </div>
                </div>`;
            }).join('');
        });
}

function toggleSetupDirectory(path) {
    const card = document.querySelector(`.setup-dir-card[data-path="${path}"]`);
    if (!card) return;

    const isSelected = card.classList.contains('selected');
    if (isSelected) {
        card.classList.remove('selected');
        card.querySelector('.setup-dir-checkbox').classList.add('hidden');
        selectedSetupDirectories = selectedSetupDirectories.filter(p => p !== path);
    } else {
        card.classList.add('selected');
        card.querySelector('.setup-dir-checkbox').classList.remove('hidden');
        selectedSetupDirectories.push(path);
    }

    document.getElementById('setupCompleteBtn').disabled = selectedSetupDirectories.length === 0;
}

function completeSetup() {
    if (selectedSetupDirectories.length === 0) return;

    fetch('/api/setup/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            scan_targets: selectedSetupDirectories,
            scan_images: document.getElementById('setupScanImages')?.checked || false
        })
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                hideSetupWizard();
                location.reload();
            }
        });
}

function skipSetup() {
    fetch('/api/setup/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_targets: ['/media'], scan_images: false })
    })
        .then(() => location.reload());
}

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(checkSetupRequired, 500);
});
