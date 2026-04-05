/**
 * Application State - Grouped globals for better organization
 * TODO: Future refactor should migrate these to a proper state management system
 */

// --- STATE MANAGEMENT ---
// Global state is now handled by StateManager in store.js
// Legacy aliases (currentFilter, etc.) are implemented as window property getters/setters in store.js
const BATCH_SIZE = 40;

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

    // If in duplicates mode, don't render the standard grid
    if (workspaceMode === 'duplicates') {
        return;
    }

    const grid = document.getElementById('videoGrid');

    // Reset cinema playlist to use global filter
    // We do this here (even if not resetting) to ensure that if we are in the main grid,
    // we strictly use the filteredVideos list, not a stale folder list.
    if (typeof setCinemaPlaylist === 'function') {
        setCinemaPlaylist(null);
    }

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
    container.className = 'col-span-1 md:col-span-2 relative w-full bg-arcade-bg dark:bg-[#14141c] rounded-xl overflow-hidden border border-black/8 dark:border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container comparison-card flex flex-col md:flex-row p-4 gap-4';

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
            ${window.IS_LOCAL_ACCESS ? `
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
             ${window.IS_LOCAL_ACCESS ? `
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
    container.className = 'group relative w-full bg-arcade-bg dark:bg-[#14141c] rounded-xl overflow-hidden border border-black/8 dark:border-white/5 hover:border-arcade-cyan/50 transition-all duration-300 hover:shadow-[0_0_20px_rgba(0,255,208,0.1)] video-card-container flex flex-col';
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
             onclick="handleCardClick(event, this)">
             
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

             <button class="favorite-btn absolute top-2 right-2 z-20 w-8 h-8 rounded-full bg-black/40 backdrop-blur hover:bg-black/60 flex items-center justify-center transition-all ${v.favorite ? 'text-arcade-gold active scale-110' : 'text-gray-400 opacity-0 group-hover:opacity-100'}"
                onclick="event.stopPropagation(); toggleFavorite(this.closest('.video-card-container'))">
                <span class="material-icons text-lg">${v.favorite ? 'star' : 'star_border'}</span>
             </button>

             <!-- Thumbnail with Skeleton Loader -->
             <div class="skeleton skeleton-thumbnail absolute inset-0">
                 <img src="/thumbnails/${v.thumb}" 
                      class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" 
                      style="object-position:${(v.Height && v.Width && v.Height > v.Width) ? 'center top' : 'center center'}"
                      loading="lazy"
                      onload="this.parentElement.classList.add('loaded'); this.parentElement.classList.remove('skeleton')"
                      onerror="this.parentElement.classList.add('loaded'); this.parentElement.classList.remove('skeleton')">
             </div>

             
             <!-- Quick Actions Overlay -->
             <div class="hidden md:flex absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity items-center justify-center gap-3">
                 ${window.IS_LOCAL_ACCESS ? `
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
                 <button class="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="${window.IS_DOCKER ? 'Queue for Mac' : 'Optimize'}" onclick="event.stopPropagation(); ${window.IS_DOCKER ? `queueForRemoteEncode('${v.FilePath.replace(/'/g, "\\\\'")}')` : `window.open('/compress?path=${encodeURIComponent(v.FilePath)}&audio=standard', 'h_frame')`}">
                    <span class="material-icons">${window.IS_DOCKER ? 'cloud_upload' : 'bolt'}</span>
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
            <h3 class="text-sm font-medium text-text-main dark:text-gray-200 line-clamp-1 group-hover:text-arcade-cyan transition-colors" title="${fileName}">${fileName}</h3>
            <p class="text-[11px] text-text-muted dark:text-gray-500 truncate" title="${v.FilePath}">${dirName}</p>
            
            ${renderVideoCardTags(v.tags || [])}
            
            <div class="flex items-center justify-between mt-1 text-xs font-mono text-text-muted dark:text-gray-400" style="font-variant-numeric:tabular-nums">
                <div class="flex items-center gap-2">
                    <span class="bg-black/6 dark:bg-white/5 px-1.5 py-0.5 rounded text-[10px]">${v.Size_MB.toFixed(0)} MB</span>
                    ${v.media_type === 'video' ? `<span style="color:${(v.Bitrate_Mbps||0)>=10?'#00ffd0':(v.Bitrate_Mbps||0)>=3?'#fbbf24':'#f87171'}">${v.Bitrate_Mbps.toFixed(1)} Mb/s</span>` : ''}
                </div>
                <button class="text-gray-600 hover:text-white transition-colors hide-toggle-btn cursor-pointer" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))" title="${v.hidden ? 'Restore' : 'Move to Vault'}">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${v.hidden ? '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>' : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'}</svg>
                </button>
            </div>

            
            <!-- Progress Bar (semantic bitrate color) -->
            <div class="mt-2 h-0.5 w-full bg-black/8 dark:bg-white/5 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500" style="width: ${barW}%; background: ${(v.Bitrate_Mbps || 0) >= 10 ? 'linear-gradient(90deg,#00ffd0,#0ea5e9)' : (v.Bitrate_Mbps || 0) >= 3 ? 'linear-gradient(90deg,#fbbf24,#f59e0b)' : 'linear-gradient(90deg,#f87171,#ef4444)'}"></div>
            </div>
        </div>
    `;
    return container;
}

// --- HOVER VIDEO PREVIEW ---
// Delegated from #videoGrid — one listener, zero per-card overhead.
// Starts a 600ms timer on mouseenter; cancels on mouseleave.
// Skips images, skips if prefers-reduced-motion is set.
(function initHoverPreview() {
    let _hoverTimer = null;
    let _activePreview = null;

    const motionOK = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    document.addEventListener('mouseover', (e) => {
        if (!motionOK) return;
        const card = e.target.closest('.video-card-container');
        if (!card || card === _activePreview) return;

        const path = card.getAttribute('data-path');
        if (!path) return;

        // Skip images
        const video = window.ALL_VIDEOS?.find(v => v.FilePath === path);
        if (!video || video.media_type === 'image') return;

        clearTimeout(_hoverTimer);
        _hoverTimer = setTimeout(() => {
            // Cancel any previous preview
            _clearPreview(_activePreview);

            const mediaEl = card.querySelector('.card-media');
            if (!mediaEl) return;

            const previewVid = document.createElement('video');
            previewVid.className = 'hover-preview-video';
            previewVid.src    = `/stream?path=${encodeURIComponent(path)}`;
            previewVid.muted  = true;
            previewVid.loop   = true;
            previewVid.autoplay = true;
            previewVid.playsInline = true;
            previewVid.preload = 'auto';
            previewVid.style.cssText = `
                position:absolute;inset:0;width:100%;height:100%;
                object-fit:cover;z-index:5;opacity:0;
                transition:opacity .25s ease;pointer-events:none;
            `;
            mediaEl.appendChild(previewVid);

            previewVid.play().catch(() => {});
            requestAnimationFrame(() => {
                requestAnimationFrame(() => { previewVid.style.opacity = '1'; });
            });

            card._previewEl = previewVid;
            _activePreview  = card;
        }, 600);
    });

    document.addEventListener('mouseout', (e) => {
        const card = e.target.closest('.video-card-container');
        if (!card) return;
        clearTimeout(_hoverTimer);
        if (card === _activePreview) {
            _clearPreview(card);
            _activePreview = null;
        }
    });

    function _clearPreview(card) {
        if (!card?._previewEl) return;
        const v = card._previewEl;
        v.style.opacity = '0';
        v.pause();
        v.src = '';
        setTimeout(() => v.remove(), 260);
        delete card._previewEl;
    }
})();


const sentinel = document.getElementById('loadingSentinel');
const scrollObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
        renderNextBatch();
    }
}, { rootMargin: '400px' });
scrollObserver.observe(sentinel);

// --- CINEMA MODULE ---
// Cinema functionality has been extracted to cinema.js
// Functions available: openCinema, closeCinema, navigateCinema, cinemaFavorite,
// cinemaVault, cinemaLocate, toggleCinemaInfo, toggleCinemaTagPanel, toggleCinemaTag

// --- TREEMAP VISUALIZATION ---
// UI code moved to treemap.js
// Export state variables for treemap.js to access
// Expose state for treemap.js
// These properties are now managed by store.js and global window context.

// Initialise duplicate checker shared state (used by duplicates.js)
window.duplicateCheckerState = window.duplicateCheckerState || { currentGroupIndex: 0, isActive: false };

// ESC key handler - delegates to treemap.js for treemap-specific handling
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

        // Delegate treemap ESC handling to treemap.js
        if (typeof handleTreemapEscape === 'function' && handleTreemapEscape()) {
            e.preventDefault();
            return;
        }

        // Handle folder browser ESC - go up one level
        if (currentLayout === 'folderbrowser' && (folderBrowserState.currentPath || folderBrowserState.showVideosHere)) {
            folderBrowserBack();
            e.preventDefault();
            return;
        }
    }
});

// Debounced resize handler - delegates to treemap.js
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        if (typeof handleTreemapResize === 'function') {
            handleTreemapResize();
        }
    }, 250);
});

// Handle browser back/forward buttons
window.addEventListener('popstate', (event) => {
    if (event.state) {
        currentLayout = event.state.layout || 'grid';
        if (typeof setTreemapCurrentFolder === 'function') {
            setTreemapCurrentFolder(event.state.folder || null);
        }
        // Restore folder browser path
        if (event.state.folderBrowserPath !== undefined) {
            folderBrowserState.currentPath = event.state.folderBrowserPath;
            folderBrowserPath = event.state.folderBrowserPath;
        }
        setLayout(currentLayout, true);
    } else {
        loadFromURL();
    }
});

// Init handled in DOMContentLoaded below

// --- SETTINGS MODULE ---
// Settings functionality has been extracted to settings.js
// Functions available: openSettings, closeSettings, saveSettings, loadSettings,
// showSettingsToast, initSettingsNavigation, adjustSettingsNumber,
// markSettingsUnsaved, markSettingsSaving, markSettingsSaved, showToast,
// showHiddenPathModal, closeHiddenPathModal, copyHiddenPath, revealInFinder,
// rescanLibrary, renderSavedViews, saveCurrentView, loadView, deleteView,
// saveSettingsWithoutReload, exportSettings, importSettings

// --- SMART COLLECTIONS MODULE ---
// Smart Collections functionality has been extracted to collections.js
// Functions available: openCollectionModal, closeCollectionModal, saveCollection,
// deleteCurrentCollection, applyCollection, renderCollections, evaluateCollectionMatch,
// getDefaultCollectionCriteria, toggleFilterAccordion, and related UI functions


// --- OPTIMIZATION PANEL ---
// Extracted to optimizer.js
// Functions available: cinemaOptimize, closeOptimize, setOptAudio, setOptCodec,
// setOptVideo, updateOptCodecUI, updateOptVideoUI, updateOptAudioUI,
// setTrimFromHead, clearTrim, triggerOptimization,
// queueForRemoteEncode, queueBatchForRemoteEncode

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
// DUPLICATE DETECTION MODULE
// ============================================================================
// Duplicate detection functionality has been extracted to duplicates.js
// Functions available: loadDuplicates, renderDuplicatesView, deleteDuplicate,
// rescanDuplicates, openDuplicateChecker, closeDuplicateChecker,
// keepDuplicateFile, skipDuplicateGroup, markAnyIsFine, previewDuplicateFile,
// navigateDuplicateGroup

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

// Duplicate Checker Fullscreen Mode has been moved to duplicates.js
// See duplicates.js for: openDuplicateChecker, closeDuplicateChecker,
// renderDuplicateCheckerGroup, renderDuplicateFile, navigateDuplicateGroup,
// keepDuplicateFile, skipDuplicateGroup, markAnyIsFine, previewDuplicateFile,
// duplicateCheckerKeyHandler


document.addEventListener('DOMContentLoaded', () => {
    setTimeout(checkSetupRequired, 500);
});
