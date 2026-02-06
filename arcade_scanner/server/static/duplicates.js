/**
 * Duplicates Module
 * Handles duplicate detection, display, and the fullscreen duplicate checker
 * Extracted from engine.js for modularity
 * 
 * Dependencies:
 * - engine.js (workspaceMode, duplicateCheckerState, openCinema, revealInFinder)
 * - formatters.js (formatSize - if needed)
 */

// ============================================================================
// DUPLICATE DETECTION STATE
// ============================================================================
let duplicateData = null;
let duplicatePollInterval = null;

// ============================================================================
// DUPLICATE LOADING & POLLING
// ============================================================================

/**
 * Load duplicate data from API, triggering a scan if no cached results exist
 * @returns {Promise<Object|string|null>} Duplicate data, "scanning" if scan started, or null on error
 */
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

/**
 * Poll the duplicate scan status and update UI
 * @param {HTMLElement} grid - The video grid element for updates
 */
function pollDuplicateStatus(grid) {
    // Clear any existing poll first
    if (duplicatePollInterval) clearInterval(duplicatePollInterval);

    const statusText = document.getElementById('scan-status-text');
    const progressBar = document.getElementById('scan-progress-bar');
    const progressText = document.getElementById('scan-progress-text');

    duplicatePollInterval = setInterval(async () => {
        // Stop polling if we navigated away
        if (window.workspaceMode !== 'duplicates') {
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

// ============================================================================
// DUPLICATE VIEW RENDERING
// ============================================================================

/**
 * Render the duplicates workspace view
 * Handles loading state, empty state, and displaying duplicate groups
 */
function renderDuplicatesView() {
    // Safety check: Don't render if we switched away
    if (window.workspaceMode !== 'duplicates') return;

    const grid = document.getElementById('videoGrid');
    if (!grid) {
        console.error('❌ renderDuplicatesView: videoGrid element not found');
        return;
    }

    console.log('🔍 renderDuplicatesView called, duplicateData:', duplicateData ? 'has data' : 'null');

    // Initial state: Show start screen (no data yet, no scan running)
    if (!duplicateData) {
        grid.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-24 gap-8">
                <!-- Icon -->
                <div class="relative w-24 h-24">
                    <div class="absolute inset-0 rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 border-2 border-purple-500/30 flex items-center justify-center">
                        <span class="material-icons text-5xl text-purple-400">content_copy</span>
                    </div>
                </div>
                
                <!-- Title & Description -->
                <div class="text-center max-w-md">
                    <h2 class="text-2xl font-bold text-white mb-3">Duplicate Finder</h2>
                    <p class="text-gray-400 leading-relaxed">
                        Scan your library to find visually similar or duplicate media files. 
                        This uses perceptual hashing to detect duplicates even with different file sizes or resolutions.
                    </p>
                </div>
                
                <!-- Feature Pills -->
                <div class="flex flex-wrap justify-center gap-3">
                    <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-gray-400">
                        <span class="material-icons text-sm text-cyan-400">movie</span>
                        Videos
                    </div>
                    <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-gray-400">
                        <span class="material-icons text-sm text-pink-400">image</span>
                        Images
                    </div>
                    <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-gray-400">
                        <span class="material-icons text-sm text-purple-400">fingerprint</span>
                        Perceptual Hashing
                    </div>
                </div>
                
                <!-- Scan Button -->
                <button onclick="startDuplicateScan()" class="px-8 py-4 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400 text-white font-bold text-lg shadow-lg shadow-purple-500/30 hover:shadow-purple-500/50 transition-all transform hover:scale-105 flex items-center gap-3">
                    <span class="material-icons text-2xl">search</span>
                    Scan for Duplicates
                </button>
                
                <!-- Hint -->
                <p class="text-xs text-gray-500">Results are cached until you rescan</p>
            </div>
        `;
        return;
    }

    // Empty State Check
    if (duplicateData.groups.length === 0) {
        grid.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-20 text-center">
                <span class="material-icons text-6xl text-gray-600 mb-4">check_circle</span>
                <h3 class="text-xl font-bold text-gray-400 mb-2">No Duplicates Found</h3>
                <p class="text-sm text-gray-500 mb-6">Your library is clean! No duplicate media detected.</p>
                <button onclick="rescanDuplicates()" class="px-5 py-2.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-white text-sm font-medium transition-colors flex items-center gap-2">
                    <span class="material-icons text-[18px]">refresh</span>
                    Rescan for Duplicates
                </button>
            </div>
        `;
        return;
    }

    // Update sidebar count
    const countEl = document.getElementById('count-duplicates');
    if (countEl) countEl.textContent = duplicateData.summary.total_groups;

    // Render summary header
    let html = `
            <div class="col-span-full bg-gradient-to-r from-purple-200 to-pink-200 dark:from-purple-900/20 dark:to-pink-900/20 border border-purple-300 dark:border-purple-500/30 rounded-xl p-6 mb-4">
                <div class="flex items-center justify-between flex-wrap gap-4">
                    <div class="flex items-center gap-4">
                        <div class="w-14 h-14 rounded-xl bg-purple-300 dark:bg-purple-500/20 flex items-center justify-center border border-purple-400 dark:border-purple-500/40">
                            <span class="material-icons text-3xl text-purple-700 dark:text-purple-400">content_copy</span>
                        </div>
                        <div>
                            <h2 class="text-xl font-bold text-gray-900 dark:text-white">Duplicate Media</h2>
                            <p class="text-sm text-gray-700 dark:text-gray-400">
                                Found <span class="text-purple-700 dark:text-purple-400 font-bold">${duplicateData.summary.total_groups}</span> groups
                                (<span class="text-cyan-700 dark:text-cyan-400">${duplicateData.summary.video_groups}</span> videos,
                                <span class="text-pink-700 dark:text-pink-400">${duplicateData.summary.image_groups}</span> images)
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-4">
                        <div class="text-right">
                            <div class="text-2xl font-bold text-green-700 dark:text-green-400">${duplicateData.summary.potential_savings_mb.toFixed(1)} MB</div>
                            <div class="text-xs text-gray-600 dark:text-gray-500 uppercase tracking-wider">Potential Savings</div>
                        </div>
                        <button onclick="deleteAllDuplicates()" class="px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-400 hover:text-white text-sm font-medium transition-colors flex items-center gap-2">
                            <span class="material-icons text-[18px]">delete_sweep</span>
                            Delete All Duplicates
                        </button>
                        <button onclick="openDuplicateChecker()" class="px-4 py-2 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/40 text-purple-400 hover:text-white text-sm font-medium transition-colors flex items-center gap-2">
                            <span class="material-icons text-[18px]">fullscreen</span>
                            Fullscreen Mode
                        </button>
                        <button onclick="rescanDuplicates()" class="px-4 py-2 rounded-lg bg-purple-300 dark:bg-purple-500/20 hover:bg-purple-400 dark:hover:bg-purple-500/30 border border-purple-400 dark:border-purple-500/40 text-purple-900 dark:text-white text-sm font-medium transition-colors flex items-center gap-2">
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

/**
 * Delete a duplicate file
 * @param {string} encodedPath - URL-encoded file path
 */
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

            // Find and update the group containing this file
            if (duplicateData && duplicateData.groups) {
                const groupIndex = duplicateData.groups.findIndex(group =>
                    group.files.some(file => file.path === path)
                );

                if (groupIndex !== -1) {
                    const group = duplicateData.groups[groupIndex];

                    // Remove only the deleted file from the group
                    group.files = group.files.filter(file => file.path !== path);

                    // If the group still has 2+ files, keep it and recalculate savings
                    if (group.files.length >= 2) {
                        // Find the largest file (the one to keep)
                        const largestFile = group.files.reduce((max, file) =>
                            file.size_mb > max.size_mb ? file : max
                        );

                        // Recalculate potential savings (sum of all files except the largest)
                        group.potential_savings_mb = group.files
                            .filter(file => file.path !== largestFile.path)
                            .reduce((sum, file) => sum + file.size_mb, 0);
                    } else {
                        // If fewer than 2 files remain, remove the group entirely
                        duplicateData.groups.splice(groupIndex, 1);
                    }

                    // Update summary counts
                    duplicateData.summary.total_groups = duplicateData.groups.length;

                    // Recalculate total savings
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

/**
 * Rescan for duplicates - clears cache and triggers fresh scan
 */
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

        // Clear client-side data and start a new scan
        duplicateData = null;
        startDuplicateScan();

    } catch (e) {
        console.error('Rescan error:', e);
        alert('Error triggering rescan');
    }
}

/**
 * Delete all duplicate files (keeps the recommended file in each group)
 * This is a bulk operation that processes all groups at once
 */
async function deleteAllDuplicates() {
    if (!duplicateData || !duplicateData.groups || duplicateData.groups.length === 0) {
        alert('No duplicates to delete');
        return;
    }

    // Collect all files to delete (all except recommended in each group)
    const filesToDelete = [];
    let totalSavingsMb = 0;

    duplicateData.groups.forEach(group => {
        const recommendedPath = group.recommended_keep;
        group.files.forEach(file => {
            if (file.path !== recommendedPath) {
                filesToDelete.push(file.path);
                totalSavingsMb += file.size_mb;
            }
        });
    });

    if (filesToDelete.length === 0) {
        alert('No duplicate files to delete');
        return;
    }

    // Confirmation dialog with details
    const confirmation = confirm(
        `⚠️ DELETE ALL DUPLICATES\n\n` +
        `This will permanently delete ${filesToDelete.length} file(s) across ${duplicateData.groups.length} groups.\n\n` +
        `Space to be freed: ${totalSavingsMb.toFixed(1)} MB\n\n` +
        `The best quality file in each group will be kept.\n\n` +
        `This action CANNOT be undone. Continue?`
    );

    if (!confirmation) {
        return;
    }

    try {
        const res = await fetch('/api/duplicates/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: filesToDelete })
        });

        if (res.ok) {
            const result = await res.json();
            console.log(`✅ Bulk delete complete: ${result.deleted.length} files, freed ${result.freed_mb} MB`);

            // Clear all groups since we deleted all duplicates
            duplicateData.groups = [];
            duplicateData.summary.total_groups = 0;
            duplicateData.summary.video_groups = 0;
            duplicateData.summary.image_groups = 0;
            duplicateData.summary.potential_savings_mb = 0;

            // Handle any failed deletions
            if (result.failed && result.failed.length > 0) {
                alert(
                    `Deleted ${result.deleted.length} files (freed ${result.freed_mb.toFixed(1)} MB).\n\n` +
                    `${result.failed.length} file(s) could not be deleted.`
                );
            } else {
                alert(`Successfully deleted ${result.deleted.length} files and freed ${result.freed_mb.toFixed(1)} MB!`);
            }

            // Refresh the view
            renderDuplicatesView();
        } else {
            alert('Failed to delete files');
        }
    } catch (e) {
        console.error('Bulk delete error:', e);
        alert('Error deleting files');
    }
}

/**
 * Show the scanning UI with spinner and progress bar
 */
function showDuplicateScanningUI() {
    const grid = document.getElementById('videoGrid');
    if (!grid) return;

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
}

/**
 * Start a duplicate scan - called when user clicks the scan button
 */
async function startDuplicateScan() {
    const grid = document.getElementById('videoGrid');
    if (!grid) return;

    // Show scanning UI
    showDuplicateScanningUI();

    // Trigger the scan
    const result = await loadDuplicates();

    if (result === "scanning") {
        pollDuplicateStatus(grid);
    } else if (result && result.groups) {
        renderDuplicatesView(); // Render the results
    }
}


// ============================================================================
// DUPLICATE CHECKER FULLSCREEN MODE
// ============================================================================

/**
 * Open the fullscreen duplicate checker mode
 * Shows the first duplicate group in a side-by-side comparison view
 */
function openDuplicateChecker() {
    if (!duplicateData || !duplicateData.groups || duplicateData.groups.length === 0) {
        alert('No duplicate groups to review');
        return;
    }

    // Use the global state from engine.js
    window.duplicateCheckerState.currentGroupIndex = 0;
    window.duplicateCheckerState.isActive = true;

    const modal = document.getElementById('duplicateCheckerModal');
    if (!modal) {
        console.error('Duplicate checker modal not found');
        return;
    }

    // Show modal
    modal.classList.add('opacity-100', 'pointer-events-auto');
    modal.classList.remove('opacity-0', 'pointer-events-none');

    // Attach keyboard handler
    window.addEventListener('keydown', duplicateCheckerKeyHandler, true);

    // Render first group
    renderDuplicateCheckerGroup(0);
}

/**
 * Close the fullscreen duplicate checker mode
 */
function closeDuplicateChecker() {
    window.duplicateCheckerState.isActive = false;

    const modal = document.getElementById('duplicateCheckerModal');
    if (modal) {
        modal.classList.remove('opacity-100', 'pointer-events-auto');
        modal.classList.add('opacity-0', 'pointer-events-none');
    }

    // Remove keyboard handler
    window.removeEventListener('keydown', duplicateCheckerKeyHandler, true);

    // Refresh duplicate view to show updated list
    if (window.workspaceMode === 'duplicates') {
        renderDuplicatesView();
    }
}

/**
 * Render a specific duplicate group in the fullscreen checker
 * @param {number} groupIndex - Index of the group to render
 */
function renderDuplicateCheckerGroup(groupIndex) {
    if (!duplicateData || !duplicateData.groups) return;

    const groups = duplicateData.groups;
    if (groupIndex < 0 || groupIndex >= groups.length) {
        // No more groups - close the checker
        closeDuplicateChecker();
        alert('All duplicate groups reviewed!');
        return;
    }

    const group = groups[groupIndex];
    window.duplicateCheckerState.currentGroupIndex = groupIndex;

    // Update header
    document.getElementById('dupCheckerCurrentGroup').textContent = groupIndex + 1;
    document.getElementById('dupCheckerTotalGroups').textContent = groups.length;

    const qualityDiff = group.files.length >= 2
        ? Math.abs(group.files[0].quality_score - group.files[1].quality_score).toFixed(1)
        : 0;
    document.getElementById('dupCheckerGroupInfo').textContent =
        `${group.files.length} duplicate candidates • Quality diff: ${qualityDiff} pts`;

    // Get the two files to compare (use first two files in group)
    const fileA = group.files[0];
    const fileB = group.files.length > 1 ? group.files[1] : fileA;

    // Determine which is recommended (higher quality score)
    const recommendedPath = group.recommended_keep || fileA.path;

    // Render File A
    renderDuplicateFile('A', fileA, fileA.path === recommendedPath);

    // Render File B
    renderDuplicateFile('B', fileB, fileB.path === recommendedPath);
}

/**
 * Render a single file panel in the duplicate checker
 * @param {string} side - 'A' or 'B'
 * @param {Object} file - File data object
 * @param {boolean} isRecommended - Whether this is the recommended file to keep
 */
function renderDuplicateFile(side, file, isRecommended) {
    const thumbSrc = file.thumb ? `/thumbnails/${file.thumb}` : '/static/placeholder.png';
    const fileName = file.path.split(/[\\/]/).pop();

    // Update thumbnail
    document.getElementById(`dupFile${side}Thumb`).src = thumbSrc;

    // Update filename
    const nameEl = document.getElementById(`dupFile${side}Name`);
    nameEl.textContent = fileName;
    nameEl.title = file.path;

    // Update quality score
    document.getElementById(`dupFile${side}Quality`).textContent = file.quality_score.toFixed(1);

    // Update file size
    document.getElementById(`dupFile${side}Size`).textContent = file.size_mb.toFixed(2) + ' MB';

    // Update resolution
    const resolution = file.width && file.height ? `${file.width}×${file.height}` : '--';
    document.getElementById(`dupFile${side}Res`).textContent = resolution;

    // Update bitrate
    const bitrate = file.bitrate_mbps ? file.bitrate_mbps.toFixed(1) + ' Mbps' : '--';
    document.getElementById(`dupFile${side}Bitrate`).textContent = bitrate;

    // Show/hide recommended badge
    const badge = document.getElementById(`dupFile${side}Badge`);
    if (isRecommended) {
        badge.classList.remove('hidden');
    } else {
        badge.classList.add('hidden');
    }

    // Highlight recommended panel
    const panel = document.getElementById(`dupFile${side}`);
    if (isRecommended) {
        panel.classList.add('border-green-500/50', 'bg-green-500/5');
        panel.classList.remove('border-white/10', 'bg-white/[0.02]');
    } else {
        panel.classList.remove('border-green-500/50', 'bg-green-500/5');
        panel.classList.add('border-white/10', 'bg-white/[0.02]');
    }
}

/**
 * Navigate to next or previous duplicate group
 * @param {number} direction - 1 for next, -1 for previous
 */
function navigateDuplicateGroup(direction) {
    const newIndex = window.duplicateCheckerState.currentGroupIndex + direction;
    renderDuplicateCheckerGroup(newIndex);
}

/**
 * Keep a specific file (A or B) and delete the other(s)
 * @param {string} side - 'A' or 'B'
 */
async function keepDuplicateFile(side) {
    if (!duplicateData || !duplicateData.groups) return;

    const group = duplicateData.groups[window.duplicateCheckerState.currentGroupIndex];
    if (!group) return;

    const fileToKeep = side === 'A' ? group.files[0] : group.files[1];
    const filesToDelete = group.files.filter(f => f.path !== fileToKeep.path);

    if (filesToDelete.length === 0) {
        alert('No files to delete');
        return;
    }

    const fileNames = filesToDelete.map(f => f.path.split(/[\\/]/).pop()).join(', ');
    if (!confirm(`Delete ${filesToDelete.length} file(s)?\n\n${fileNames}\n\nThis cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch('/api/duplicates/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: filesToDelete.map(f => f.path) })
        });

        if (res.ok) {
            // Remove this group from the list
            duplicateData.groups.splice(window.duplicateCheckerState.currentGroupIndex, 1);
            duplicateData.summary.total_groups--;

            // Show next group (same index since we removed current)
            renderDuplicateCheckerGroup(window.duplicateCheckerState.currentGroupIndex);
        } else {
            alert('Failed to delete files');
        }
    } catch (err) {
        console.error('Delete error:', err);
        alert('Error deleting files');
    }
}

/**
 * Skip current duplicate group without taking action
 */
function skipDuplicateGroup() {
    navigateDuplicateGroup(1);
}

/**
 * Mark "any is fine" - keep the recommended file and delete others
 */
async function markAnyIsFine() {
    if (!duplicateData || !duplicateData.groups) return;

    const group = duplicateData.groups[window.duplicateCheckerState.currentGroupIndex];
    if (!group) return;

    const recommendedPath = group.recommended_keep;
    const fileToKeep = group.files.find(f => f.path === recommendedPath) || group.files[0];
    const filesToDelete = group.files.filter(f => f.path !== fileToKeep.path);

    if (filesToDelete.length === 0) {
        // Only one file, just skip
        skipDuplicateGroup();
        return;
    }

    try {
        const res = await fetch('/api/duplicates/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: filesToDelete.map(f => f.path) })
        });

        if (res.ok) {
            // Remove this group from the list
            duplicateData.groups.splice(window.duplicateCheckerState.currentGroupIndex, 1);
            duplicateData.summary.total_groups--;

            // Show next group
            renderDuplicateCheckerGroup(window.duplicateCheckerState.currentGroupIndex);
        } else {
            alert('Failed to delete files');
        }
    } catch (err) {
        console.error('Delete error:', err);
        alert('Error deleting files');
    }
}

/**
 * Preview a duplicate file in cinema mode (optional feature)
 * @param {string} side - 'A' or 'B'
 */
function previewDuplicateFile(side) {
    if (!duplicateData || !duplicateData.groups) return;

    const group = duplicateData.groups[window.duplicateCheckerState.currentGroupIndex];
    if (!group) return;

    const file = side === 'A' ? group.files[0] : group.files[1];

    // Create dummy container with path and open cinema
    const dummyContainer = document.createElement('div');
    dummyContainer.setAttribute('data-path', file.path);
    window.openCinema(dummyContainer);
}

/**
 * Handle keyboard shortcuts in duplicate checker mode
 * @param {KeyboardEvent} e - Keyboard event
 */
function duplicateCheckerKeyHandler(e) {
    // Only handle if duplicate checker is active
    if (!window.duplicateCheckerState.isActive) return;

    // Skip if typing in an input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    const key = e.key.toLowerCase();

    if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        closeDuplicateChecker();
    } else if (key === '1' || e.key === 'ArrowLeft') {
        e.preventDefault();
        e.stopPropagation();
        keepDuplicateFile('A');
    } else if (key === '2' || e.key === 'ArrowRight') {
        e.preventDefault();
        e.stopPropagation();
        keepDuplicateFile('B');
    } else if (key === 's' || key === ' ') {
        e.preventDefault();
        e.stopPropagation();
        skipDuplicateGroup();
    } else if (key === 'a') {
        e.preventDefault();
        e.stopPropagation();
        markAnyIsFine();
    }
}

// ============================================================================
// EXPOSE TO GLOBAL SCOPE
// ============================================================================

// Duplicate detection functions
window.loadDuplicates = loadDuplicates;
window.renderDuplicatesView = renderDuplicatesView;
window.deleteDuplicate = deleteDuplicate;
window.deleteAllDuplicates = deleteAllDuplicates;
window.rescanDuplicates = rescanDuplicates;
window.startDuplicateScan = startDuplicateScan;

// Duplicate checker (fullscreen mode) functions
window.openDuplicateChecker = openDuplicateChecker;
window.closeDuplicateChecker = closeDuplicateChecker;
window.keepDuplicateFile = keepDuplicateFile;
window.skipDuplicateGroup = skipDuplicateGroup;
window.markAnyIsFine = markAnyIsFine;
window.previewDuplicateFile = previewDuplicateFile;
window.navigateDuplicateGroup = navigateDuplicateGroup;
