// filter_engine.js - Extracted from engine.js

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

    // If in folder browser mode, re-render the folder browser to apply sorting
    if (currentLayout === 'folderbrowser') {
        renderFolderBrowser();
    } else {
        filterAndSort();
    }
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
        // Duplicates mode has its own rendering logic
        if (workspaceMode === 'duplicates') {
            return;
        }

        let vCount = 0; let tSize = 0;

        // Standard Filtering
        if (workspaceMode === 'optimized') {
            const pairs = [];
            const map = new Map();

            // 1. Map all files by stem (filename without extension)
            window.ALL_VIDEOS.forEach(v => {
                const fileName = v.FilePath.split(/[\\/]/).pop();
                const lastDot = fileName.lastIndexOf('.');
                const stem = lastDot > 0 ? fileName.substring(0, lastDot) : fileName;

                // Normalize path to directory to ensure we only pair in same folder
                const lastSlash = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
                const dir = v.FilePath.substring(0, lastSlash);

                const key = dir + '|' + stem;
                map.set(key, v);
            });

            // 2. Find pairs (files ending in _opt or _trim)
            map.forEach((vOpt, key) => {
                if (key.endsWith('_opt') || key.endsWith('_trim')) {
                    const suffixLen = key.endsWith('_opt') ? 4 : 5;
                    const baseKey = key.substring(0, key.length - suffixLen);

                    if (map.has(baseKey)) {
                        const vOrig = map.get(baseKey);
                        pairs.push({
                            type: 'pair',
                            original: vOrig,
                            optimized: vOpt,
                            diff: (vOpt.Size_MB || 0) - (vOrig.Size_MB || 0)
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
                tSize += (v.Size_MB || 0);
                return true;
            });
        }

        // Sort
        if (workspaceMode !== 'optimized') {
            filteredVideos.sort((a, b) => {
                if (currentSort === 'bitrate') return (b.Bitrate_Mbps || 0) - (a.Bitrate_Mbps || 0);
                if (currentSort === 'size') return (b.Size_MB || 0) - (a.Size_MB || 0);
                if (currentSort === 'runtime') return (b.Duration_Sec || 0) - (a.Duration_Sec || 0);
                if (currentSort === 'name') return a.FilePath.localeCompare(b.FilePath);
                if (currentSort === 'date') return (b.mtime || 0) - (a.mtime || 0);
                return 0;
            });
        } else {
            filteredVideos.sort((a, b) => a.original.FilePath.localeCompare(b.original.FilePath));
        }

        const countEl = document.getElementById('count-total');
        if (countEl) countEl.innerText = vCount;

        const sizeEl = document.getElementById('size-total');
        if (sizeEl) sizeEl.innerText = formatSize(tSize);

        // Update Quick Stats Ribbon
        _updateQuickStats(filteredVideos, workspaceMode);

        renderUI(true, scrollToTop);
    } catch (e) {
        if (typeof showToast === 'function') {
            showToast('Filter error: ' + e.message, 'error');
        }
        console.error(e);
    }
}

/**
 * Update the Quick Stats Ribbon above the grid with live stats for the
 * current filtered result set.
 *
 * @param {Array}  videos        – current filteredVideos array
 * @param {string} workspaceMode – current workspace ('lobby', 'favorites', …)
 */
function _updateQuickStats(videos, workspaceMode) {
    const ribbon = document.getElementById('quickStatsRibbon');
    if (!ribbon) return;

    // Skip in Optimized-pairs mode (array items have different shape)
    if (workspaceMode === 'optimized' || workspaceMode === 'duplicates') {
        ribbon.style.display = 'none';
        return;
    }

    ribbon.style.display = 'flex';

    const total      = videos.length;
    const videoItems = videos.filter(v => (v.media_type || 'video') === 'video');
    const imageItems = videos.filter(v => v.media_type === 'image');
    const totalSizeMB= videos.reduce((s, v) => s + (v.Size_MB || 0), 0);
    const under50    = videoItems.filter(v => v.Size_MB < 50).length;
    const pctSmall   = videoItems.length > 0 ? Math.round((under50 / videoItems.length) * 100) : 0;
    const avgBitrate = videoItems.length > 0
        ? (videoItems.reduce((s, v) => s + (v.Bitrate_Mbps || 0), 0) / videoItems.length).toFixed(1)
        : '–';
    const sizeLabel  = totalSizeMB >= 1024
        ? (totalSizeMB / 1024).toFixed(1) + ' GB'
        : totalSizeMB.toFixed(0) + ' MB';

    const parts = [
        `<span class="qs-stat"><span class="qs-val">${videoItems.length}</span> Videos</span>`,
    ];
    if (imageItems.length > 0) {
        parts.push(`<span class="qs-stat"><span class="qs-val">${imageItems.length}</span> Images</span>`);
    }
    parts.push(`<span class="qs-stat"><span class="qs-val">${sizeLabel}</span> total</span>`);

    if (videoItems.length > 0) {
        const potColor = pctSmall > 50 ? '#4ade80' : pctSmall > 20 ? '#fbbf24' : '#f87171';
        parts.push(`<span class="qs-stat" title="${under50} files under 50 MB">
            <span class="qs-val" style="color:${potColor}">${pctSmall}%</span>
            <span class="qs-sub">&lt;50&#8239;MB</span>
        </span>`);
        parts.push(`<span class="qs-stat">
            <span class="qs-val">${avgBitrate}</span>
            <span class="qs-sub">Mb/s avg</span>
        </span>`);
    }

    ribbon.innerHTML = parts.join('<span class="qs-divider">·</span>');
}

// --- EXPORTS ---
window.filterAndSort  = filterAndSort;
window.onSearchInput  = onSearchInput;
window.setFilter      = setFilter;
window.setCodecFilter = setCodecFilter;
window.setSort        = setSort;
window.setMinSize     = setMinSize;
window.setMaxSize     = setMaxSize;
window.setDateFilter  = setDateFilter;
