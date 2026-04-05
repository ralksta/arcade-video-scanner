// workspace.js - Extracted from engine.js

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

        // Reset cinema playlist when changing workspace
        if (typeof setCinemaPlaylist === 'function') {
            setCinemaPlaylist(null);
        }

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
            // Ensure grid is visible (might be hidden from treemap mode)
            const videoGrid = document.getElementById('videoGrid');
            const treemapContainer = document.getElementById('treemapContainer');
            const loadingSentinel = document.getElementById('loadingSentinel');
            if (videoGrid) videoGrid.style.display = '';
            if (treemapContainer) treemapContainer.style.display = 'none';
            if (loadingSentinel) loadingSentinel.style.display = 'none';

            renderDuplicatesView();
        } else {
            // Restore sentinel for infinite scroll (may have been hidden by duplicates mode)
            const loadingSentinel = document.getElementById('loadingSentinel');
            if (loadingSentinel) loadingSentinel.style.display = '';

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
    const modes = ['grid', 'list', 'treemap', 'folderbrowser'];
    const icons = {
        grid: 'view_list',         // Shows what's NEXT (list)
        list: 'dashboard',         // Shows what's NEXT (treemap)
        treemap: 'folder',         // Shows what's NEXT (folderbrowser)
        folderbrowser: 'view_module'  // Shows what's NEXT (grid)
    };

    const currentIndex = modes.indexOf(currentLayout);
    const nextIndex = (currentIndex + 1) % modes.length;
    const nextMode = modes[nextIndex];

    setLayout(nextMode);

    // Update button icon to show what's next
    const btn = document.getElementById('toggleView');
    if (btn) btn.innerHTML = `<span class="material-icons">${icons[nextMode]}</span>`;
}

/**
 * Update the CSS variable for grid column min-width
 * @param {string|number} value - The new min-width in pixels
 */
function updateGridScale(value) {
    document.documentElement.style.setProperty('--grid-min-width', `${value}px`);
    // Optionally, save preference
    localStorage.setItem('gridScale', value);
}

// Initialize grid scale from localStorage if available
(function initGridScale() {
    const saved = localStorage.getItem('gridScale');
    if (saved) {
        document.documentElement.style.setProperty('--grid-min-width', `${saved}px`);
        window.addEventListener('DOMContentLoaded', () => {
            const slider = document.getElementById('gridScaleSlider');
            if (slider) slider.value = saved;
        });
    }
})();

/**
 * Set the display layout mode
 * Handles switching between grid, list, treemap, and folderbrowser views with proper
 * show/hide of relevant UI elements and animations
 *
 * @param {string} layout - Layout mode ('grid', 'list', 'treemap', 'folderbrowser')
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
    const folderBrowserLegend = document.getElementById('folderBrowserLegend');
    const gridScaleContainer = document.getElementById('gridScaleContainer');

    // Show/hide grid scale slider
    if (gridScaleContainer) {
        gridScaleContainer.style.display = layout === 'grid' ? 'flex' : 'none';
    }

    // Hide all legends first
    if (treemapLegend) treemapLegend.style.display = 'none';
    if (folderBrowserLegend) folderBrowserLegend.style.display = 'none';

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
    } else if (layout === 'folderbrowser') {
        // Folder browser mode
        grid.style.display = '';
        grid.classList.remove('list-view');
        sentinel.style.display = 'none'; // No infinite scroll in folder browser
        treemap.style.display = 'none';

        // Trigger animation
        grid.classList.remove('animating');
        void grid.offsetWidth; // Trigger reflow
        grid.classList.add('animating');

        // Hide batch bar in folder browser (no checkboxes on folder cards)
        if (batchBar) {
            batchBar.style.display = 'none';
        }

        // Show sort dropdown in folder browser view (for sorting files)
        const sortSelect = document.getElementById('sortSelect');
        if (sortSelect) sortSelect.style.display = '';

        // Hide workspace bar, show folder browser legend
        if (workspaceBar) workspaceBar.style.display = 'none';
        if (folderBrowserLegend) folderBrowserLegend.style.display = 'block';

        // Reset treemap drill-down state
        if (typeof setTreemapCurrentFolder === 'function') {
            setTreemapCurrentFolder(null);
        }

        renderFolderBrowser();
    } else {
        // Grid or list mode
        // Toggle list-view class for CSS styling
        if (layout === 'list') {
            grid.classList.add('list-view');
        } else {
            grid.classList.remove('list-view');
        }

        // Ensure display mode is correct (let CSS handle flex/grid details via class)
        grid.style.display = '';

        sentinel.style.display = 'flex';
        treemap.style.display = 'none';

        // Trigger animation
        grid.classList.remove('animating');
        void grid.offsetWidth; // Trigger reflow
        grid.classList.add('animating');

        // Reset treemap drill-down state
        if (typeof setTreemapCurrentFolder === 'function') {
            setTreemapCurrentFolder(null);
        }

        // Reset folder browser state
        folderBrowserState.currentPath = null;
        folderBrowserState.showVideosHere = false;
        folderBrowserPath = null;

        // Restore batch bar display (will show if items are selected)
        if (batchBar) {
            batchBar.style.display = '';
        }

        // Show workspace bar
        if (workspaceBar) workspaceBar.style.display = '';

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
        const treemapFolder = typeof getTreemapCurrentFolder === 'function' ? getTreemapCurrentFolder() : null;
        if (treemapFolder) {
            params.set('folder', encodeURIComponent(treemapFolder));
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

        // Add view params
        const params = new URLSearchParams();
        if (currentLayout !== 'grid') {
            params.set('view', currentLayout);
        }

        // Add folder browser path if in folderbrowser mode
        if (currentLayout === 'folderbrowser' && folderBrowserState.currentPath) {
            params.set('folderPath', encodeURIComponent(folderBrowserState.currentPath));
        }

        const qs = params.toString();
        if (qs) path += `?${qs}`;
    }

    // Only push if changed (ignoring duplicate slashes etc)
    const currentPath = window.location.pathname + window.location.search;
    if (currentPath !== path) {
        const treemapFolder = typeof getTreemapCurrentFolder === 'function' ? getTreemapCurrentFolder() : null;
        window.history.pushState({
            layout: currentLayout,
            folder: treemapFolder,
            folderBrowserPath: folderBrowserState.currentPath,
            mode: workspaceMode
        }, '', path);
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
    if (params.get('view') === 'folderbrowser') layout = 'folderbrowser';
    if (params.get('folder') && typeof setTreemapCurrentFolder === 'function') {
        setTreemapCurrentFolder(decodeURIComponent(params.get('folder')));
    }

    // Restore folder browser path from URL
    if (params.get('folderPath')) {
        folderBrowserState.currentPath = decodeURIComponent(params.get('folderPath'));
        folderBrowserPath = folderBrowserState.currentPath;
    }

    // Check deep links
    if (path.startsWith('/collections/')) {
        // We set mode='lobby' above, but here we MUST preserve the collection we found
        setWorkspaceMode(mode, true);
    } else {
        setWorkspaceMode(mode);
    }

    // Force layout if special view
    if (layout === 'treemap') {
        setLayout('treemap');
    } else if (layout === 'list') {
        setLayout('list');
    } else if (layout === 'folderbrowser') {
        setLayout('folderbrowser');
    }

    // Check for deep links (navigating back/forward)
    checkDeepLinks();
}

// --- EXPORTS ---
window.setWorkspaceMode = setWorkspaceMode;
window.setLayout        = setLayout;
window.toggleLayout     = toggleLayout;
window.updateURL        = updateURL;
window.loadFromURL      = loadFromURL;
window.updateGridScale  = updateGridScale;
