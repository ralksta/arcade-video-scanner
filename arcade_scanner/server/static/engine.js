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
    // Leer-Zustand zuerst: er hängt nur an filteredVideos/Layout und muss auch
    // dann stimmen, wenn wir gleich in einen der Early-Returns laufen.
    if (typeof updateEmptyState === 'function') updateEmptyState();

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
        // A reset render drops back to a single batch, so the page collapses and
        // the browser snaps to the top. Remember how far we were scrolled and how
        // many batches were on screen, so we can rebuild the same view.
        const prevRendered = renderedCount;
        const prevScrollY = window.scrollY;

        grid.innerHTML = '';
        renderedCount = 0;

        // Only scroll to top when explicitly requested (e.g., workspace change)
        // This prevents scroll-jumping when filtering/sorting/deleting
        if (scrollToTop) {
            window.scrollTo({ top: 0, behavior: 'instant' });
            renderNextBatch();
            return;
        }

        // Restore the previous amount of cards, then the scroll offset.
        const target = Math.min(prevRendered, filteredVideos.length);
        do {
            renderNextBatch();
        } while (renderedCount < target);

        restoreScrollPosition(prevScrollY);
        return;
    }
    renderNextBatch();
}

/**
 * Restore a previously captured vertical scroll offset after a reset render.
 * Runs twice (now + next frame) because card heights settle only after layout.
 *
 * @param {number} y - Scroll offset in pixels
 */
function restoreScrollPosition(y) {
    if (!y) return;

    const apply = () => {
        const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
        window.scrollTo({ top: Math.min(y, maxY), behavior: 'instant' });
    };

    apply();
    requestAnimationFrame(apply);
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
    container.className = 'col-span-1 md:col-span-2 relative w-full bg-card rounded-ds-md overflow-hidden border border-[var(--ds-hairline)] hover:border-[var(--ds-hairline-strong)] transition-colors duration-200 video-card-container comparison-card flex flex-col md:flex-row p-4 gap-4';

    // Explicitly set grid span here, though class handles it usually, but existing grid logic might override without it if it was inline style before
    container.style.gridColumn = "span 2";

    // Use shared formatters from formatters.js
    // formatSizeCompact and formatBitrate are available globally

    container.innerHTML = `
        <!-- Original Column -->
        <div class="flex-1 min-w-0 flex flex-col gap-2">
            <div class="text-xs font-bold text-gray-500 uppercase tracking-widest flex justify-between">
                <span>Original</span>
                <span class="text-[9px] bg-[var(--ds-fill-soft)] px-1 rounded">${orig.codec}</span>
            </div>
            
            <div class="relative w-full aspect-video bg-black rounded-lg overflow-hidden cursor-pointer group" onclick="openCinema(this)" data-path="${orig.FilePath}">
                 <img src="/thumbnails/${orig.thumb}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" loading="lazy">
                 <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span class="material-icons text-white text-3xl drop-shadow-lg" aria-hidden="true">play_arrow</span>
                 </div>
                 <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[10px] bg-black/80 text-white font-mono font-bold backdrop-blur">${formatSizeCompact(orig.Size_MB)}</span>
            </div>
            
            <div class="text-[10px] text-gray-400 font-mono flex justify-between px-1">
                <span class="truncate font-medium text-gray-300" title="${orig.FilePath}">${orig.FilePath.split(/[\\\\/]/).pop()}</span>
                <span>${orig.Bitrate_Mbps.toFixed(1)} Mb/s</span>
            </div>
            ${window.IS_LOCAL_ACCESS ? `
            <button class="text-xs text-gray-500 hover:text-text-main flex items-center gap-1 px-1 transition-colors" onclick="revealInFinder('${orig.FilePath.replace(/'/g, "\\'")}')">
                <span class="material-icons text-[12px]" aria-hidden="true">folder_open</span> Reveal
            </button>
            ` : ''}
        </div>

        <!-- Stats Center -->
        <div class="w-full md:w-32 flex flex-col items-center justify-center gap-1 border-y md:border-y-0 md:border-x border-ink/5 py-4 md:py-0 bg-ink/[0.02] rounded-lg md:bg-transparent">
             <div class="text-2xl font-bold ${isSmaller ? 'text-green-400 drop-shadow-[0_0_8px_rgba(76,217,100,0.4)]' : 'text-red-500'} font-mono tracking-tighter">${diffPct.toFixed(1)}%</div>
             <div class="text-xs text-gray-500 font-mono mb-2">${diffMB.toFixed(1)} MB</div>
             
             <button class="ds-btn ds-btn-primary w-full mt-1" onclick="keepOptimized('${encodeURIComponent(orig.FilePath)}', '${encodeURIComponent(opt.FilePath)}')">
                <span class="material-icons text-[14px]" aria-hidden="true">check</span> KEEP
             </button>
             <button class="w-full py-2 rounded-lg bg-[var(--ds-fill-soft)] text-gray-400 hover:bg-[var(--ds-fill)] hover:text-text-main border border-ink/5 text-xs font-bold transition-all flex items-center justify-center gap-1" onclick="discardOptimized('${encodeURIComponent(opt.FilePath)}')">
                <span class="material-icons text-[14px]" aria-hidden="true">delete</span> DISCARD
             </button>
        </div>

        <!-- Optimized Column -->
        <div class="flex-1 min-w-0 flex flex-col gap-2">
            <div class="text-xs font-bold text-arcade-cyan uppercase tracking-widest flex justify-between">
                <span>Optimized</span>
                <span class="text-[9px] bg-arcade-cyan/10 text-arcade-cyan px-1 rounded border border-arcade-cyan/20">${opt.codec}</span>
            </div>
            
             <div class="relative w-full aspect-video bg-black rounded-lg overflow-hidden cursor-pointer group border-[1.5px] border-accent" onclick="openCinema(this)" data-path="${opt.FilePath}">
                 <img src="/thumbnails/${opt.thumb}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" loading="lazy">
                 <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span class="material-icons text-white text-3xl drop-shadow-lg" aria-hidden="true">play_arrow</span>
                 </div>
                 <span class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-[10px] bg-arcade-cyan/20 text-arcade-cyan font-mono font-bold backdrop-blur border border-arcade-cyan/30">${formatSizeCompact(opt.Size_MB)}</span>
            </div>
            
            <div class="text-[10px] text-gray-400 font-mono flex justify-between px-1">
                <span class="truncate font-medium text-gray-300" title="${opt.FilePath}">${opt.FilePath.split(/[\\\\/]/).pop()}</span>
                <span>${opt.Bitrate_Mbps.toFixed(1)} Mb/s</span>
            </div>
             ${window.IS_LOCAL_ACCESS ? `
             <button class="text-xs text-gray-500 hover:text-text-main flex items-center gap-1 px-1 transition-colors" onclick="revealInFinder('${opt.FilePath.replace(/'/g, "\\'")}')">
                <span class="material-icons text-[12px]" aria-hidden="true">folder_open</span> Reveal
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
            const card = document.querySelector(`[data-path="${orig}"]`);
            if (card) {
                card.style.opacity = '0';
                card.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    card.remove();
                    // Update global state and header stats
                    window.ALL_VIDEOS = window.ALL_VIDEOS.filter(v => v.FilePath !== orig && v.FilePath !== opt);
                    updateHeaderStats();
                    filterAndSort();
                }, 300);
            }
        })
        .catch(err => {
            console.error('keepOptimized error:', err);
            showToast('Optimierte Datei konnte nicht übernommen werden: ' + err.message, 'error');
        });
}

function discardOptimized(opt) {
    if (!confirm("Delete the optimized file?")) return;
    apiWrite(`/api/discard_optimized?path=${opt}`, {}, { action: 'Optimierte Datei verwerfen' })
        .then(response => {
            if (!response) return;
            const card = document.querySelector(`[data-path="${opt}"]`);
            if (card) {
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    window.ALL_VIDEOS = window.ALL_VIDEOS.filter(v => v.FilePath !== opt);
                    updateHeaderStats();
                    filterAndSort();
                }, 300);
            }
        });
}

// formatDuration is now defined in formatters.js
// This comment preserves the location for reference

/**
 * Optimize-Button einer Karte.
 *
 * Ausgelagert, weil der Nicht-Docker-Zweig den Pfad in eine URL schreibt und
 * encodeURIComponent auf Dateinamen mit ungültigen UTF-8-Bytes `URIError: URI
 * malformed` wirft (Pythons surrogateescape liefert sie als einzelne Surrogate).
 * Inline in der Kartenvorlage hätte das die gesamte Grid-Ansicht mitgerissen.
 * Lässt sich der Pfad nicht kodieren, wird der Button deaktiviert statt eine URL
 * zu bauen, die der Server ohnehin nicht dekodieren kann.
 *
 * @param {Object} v - Video metadata object
 * @returns {string} HTML für den Button
 */
function _optimizeButton(v) {
    const cls = 'w-10 h-10 rounded-full bg-ink/10 hover:bg-ink/20 flex items-center ' +
                'justify-center backdrop-blur text-white transition-all transform hover:scale-110';

    if (window.IS_DOCKER) {
        // Der Docker-Pfad reicht den Pfad als JS-String weiter, nicht als URL —
        // hier gibt es kein Encoding-Problem.
        return `
                 <button class="${cls}" title="Queue for Mac" onclick="event.stopPropagation(); queueForRemoteEncode('${v.FilePath.replace(/'/g, "\\'")}')">
                    <span class="material-icons" aria-hidden="true">cloud_upload</span>
                 </button>`;
    }

    const enc = safeEncodePath(v.FilePath);
    if (enc === null) {
        return `
                 <button class="${cls} opacity-40 cursor-not-allowed" disabled
                         title="Optimieren nicht möglich: Der Dateiname enthält ungültige UTF-8-Bytes. Datei nach UTF-8 umbenennen.">
                    <span class="material-icons" aria-hidden="true">bolt</span>
                 </button>`;
    }
    return `
                 <button class="${cls}" title="Optimize" onclick="event.stopPropagation(); window.open('/compress?path=${enc}&audio=standard', 'h_frame')">
                    <span class="material-icons" aria-hidden="true">bolt</span>
                 </button>`;
}

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
    // Design System: Card = bg surface, 1px hairline, 8px radius, ruhiger Hover
    // (Border-Lift statt Multi-Color-Glow).
    container.className = 'group relative w-full bg-card rounded-ds-md overflow-hidden border border-[var(--ds-hairline)] hover:border-[var(--ds-hairline-strong)] transition-colors duration-200 video-card-container flex flex-col';
    // Debug layout
    if (window.debugLayout) console.log('Created card with classes:', container.className);
    container.setAttribute('data-path', v.FilePath); // Keep this for JS logic

    const isHevc = (v.codec || '').includes('hevc') || (v.codec || '').includes('h265');
    const isAv1  = (v.codec || '').includes('av1') || (v.codec || '').includes('av01');
    const barW = Math.min(100, ((v.Bitrate_Mbps || 0) / 25) * 100);
    const rate = v.Bitrate_Mbps || 0;
    // Bitrate-Tier -> semantische Farbe (nur diese drei, kein Farb-Freistil)
    const rateColor = rate >= 10 ? 'var(--ds-bitrate)'
                    : rate >= 3  ? 'var(--ds-hevc)'
                                 : 'var(--ds-optimized)';
    const fileName = v.FilePath.split(/[\\\\/]/).pop();
    const lastIdx = Math.max(v.FilePath.lastIndexOf('/'), v.FilePath.lastIndexOf('\\'));
    const dirName = lastIdx >= 0 ? v.FilePath.substring(0, lastIdx) : '';

    container.innerHTML = `
        <!-- Thumbnail (Card Media) -->
        <div class="card-media relative aspect-video bg-black overflow-hidden group cursor-pointer"
             onclick="handleCardClick(event, this)">
             
             <!-- Corner Checkbox -->
             <div class="absolute top-1.5 left-1.5 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                <input type="checkbox" class="w-4 h-4 rounded-[4px] border-ink/30 bg-black/50 text-accent focus:ring-0 cursor-pointer" aria-label="Select" onclick="event.stopPropagation(); toggleSelection(this, event, '${v.FilePath.replace(/'/g, "\\'")}')">
             </div>

             <button class="favorite-btn absolute top-1.5 right-1.5 z-20 w-7 h-7 rounded-full bg-black/45 flex items-center justify-center transition-all ${v.favorite ? 'text-bitrate active' : 'text-white/70 opacity-0 group-hover:opacity-100'}"
                onclick="event.stopPropagation(); toggleFavorite(this.closest('.video-card-container'))"
                aria-label="${v.favorite ? 'Favorit entfernen' : 'Als Favorit markieren'}"
                title="${v.favorite ? 'Favorit' : 'Add to Favorites'}">
                <span class="material-icons text-lg" aria-hidden="true">${v.favorite ? 'star' : 'star_border'}</span>
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
                 <button class="w-10 h-10 rounded-full bg-ink/10 hover:bg-ink/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="Reveal" onclick="event.stopPropagation(); revealInFinder('${v.FilePath.replace(/'/g, "\\'")}')">
                    <span class="material-icons" aria-hidden="true">folder_open</span>
                 </button>
                 ` : ''}
                 <button class="w-11 h-11 rounded-full bg-accent/[0.18] hover:bg-accent text-accent-tint hover:text-white border border-accent/[0.45] flex items-center justify-center backdrop-blur transition-colors" title="Play" onclick="event.stopPropagation(); openCinema(this.closest('.card-media'))">
                    <span class="material-icons text-3xl" aria-hidden="true">play_arrow</span>
                 </button>
                 <button class="w-10 h-10 rounded-full bg-ink/10 hover:bg-ink/20 flex items-center justify-center backdrop-blur text-white transition-all transform hover:scale-110" title="${v.hidden ? 'Restore' : 'Move to Vault'}" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))">
                    <span class="material-icons" aria-hidden="true">${v.hidden ? 'unarchive' : 'archive'}</span>
                 </button>
                  ${(window.userSettings?.enable_optimizer !== false && window.ENABLE_OPTIMIZER !== false) ? _optimizeButton(v) : ''}
             </div>
             
             <!-- Badge-Cluster: Status + Codec, 4px Gap, 6px Inset -->
             <div class="absolute bottom-1.5 left-1.5 flex gap-1 flex-wrap pr-12 pointer-events-none">
                 ${v.media_type === 'image'
                    ? `<span class="ds-badge ds-badge-accent">IMG</span>`
                    : `<span class="ds-badge ${v.Status === 'HIGH' ? 'ds-badge-bitrate' : 'ds-badge-neutral'}">${v.Status}</span>`
                 }
                 ${isHevc ? '<span class="ds-badge ds-badge-hevc">HEVC</span>' : ''}
                 ${isAv1  ? '<span class="ds-badge ds-badge-av1">AV1</span>' : ''}
                 ${fileName.includes('_opt.') ? '<span class="ds-badge ds-badge-optimized">OPT</span>' : ''}
             </div>

             <!-- Duration -->
             <span class="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded-[4px] text-[10px] font-mono font-semibold bg-black/70 text-white pointer-events-none">
                ${v.Duration_Sec ? formatDuration(v.Duration_Sec) : ''}
             </span>
        </div>

        <!-- Content -->
        <div class="card-body px-[11px] py-2.5 flex flex-col gap-0.5">
            <h3 class="text-[12.5px] font-medium text-text-main truncate" title="${fileName}">${fileName}</h3>
            <p class="text-[10.5px] text-text-muted truncate" title="${v.FilePath}">${dirName}</p>

            ${renderVideoCardTags(v.tags || [])}

            <div class="flex items-center justify-between mt-2 text-[11px] font-mono text-label">
                <div class="flex items-center gap-2">
                    <span class="bg-[var(--ds-fill-soft)] text-label px-1.5 py-0.5 rounded-[4px]">${v.Size_MB.toFixed(0)} MB</span>
                    ${v.media_type === 'video' ? `<span style="color:${rateColor}">${v.Bitrate_Mbps.toFixed(1)} Mbps</span>` : ''}
                </div>
                <button class="text-text-muted hover:text-text-main transition-colors hide-toggle-btn cursor-pointer" onclick="event.stopPropagation(); toggleHidden(this.closest('.video-card-container'))" title="${v.hidden ? 'Restore' : 'Move to Vault'}">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${v.hidden ? '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>' : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'}</svg>
                </button>
            </div>

            
            <!-- Bitrate-Bar: 3px, Track white/6, Fill in Tier-Farbe -->
            <div class="mt-2 h-[3px] w-full bg-[var(--ds-fill)] rounded-[2px] overflow-hidden">
                <div class="h-full rounded-[2px] transition-all duration-500" style="width: ${barW}%; background: ${rateColor}"></div>
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
        <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-[var(--ds-hairline-strong)] text-gray-300 border border-[var(--ds-hairline-strong)] ${c.isNeg ? 'line-through decoration-red-500 decoration-2 text-red-200' : ''}">
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
    // Design System: alle Workspaces teilen sich EINEN Accent — der Indikator
    // wird komplett ueber CSS-Tokens gestylt, kein Inline-Farb-Mapping mehr.

    // Load available tags for filtering
    if (typeof loadAvailableTags === 'function') {
        loadAvailableTags();
    }

    // Back/Forward wird von genau EINEM Handler bedient — dem
    // addEventListener('popstate', ...) weiter oben in dieser Datei. Ein zweiter
    // Handler hier hat den wiederhergestellten State direkt wieder überschrieben.

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
    window.getAvailableCategories = getAvailableCategories;

    function populateCategoryDropdown(selectedCategory = null) {
        const select = document.getElementById('collectionCategory');
        if (!select) return;

        const categories = getAvailableCategories();

        select.innerHTML = '<option value="">Uncategorized</option>' +
            categories.map(cat =>
                `<option value="${cat}" ${cat === selectedCategory ? 'selected' : ''}>${cat}</option>`
            ).join('');
    }
    window.populateCategoryDropdown = populateCategoryDropdown;

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
            btn.innerHTML = '<span class="material-icons text-sm" aria-hidden="true">close</span>';
            btn.title = "Cancel";
        } else {
            // Hide input, show select
            select.classList.remove('hidden');
            input.classList.add('hidden');
            input.value = '';
            btn.innerHTML = '<span class="material-icons text-sm" aria-hidden="true">add</span>';
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
                window.userSettings.smart_collections = data.smart_collections || [];

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
            if (btn) btn.innerHTML = '<span class="material-icons" aria-hidden="true">view_module</span>';
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
            const data = await res.json();
            
            // Pre-calculate metadata for faster filtering/rendering
            data.forEach(v => {
                const path = v.FilePath;
                const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
                v._fileName = path.substring(lastIdx + 1);
                v._fileNameLower = v._fileName.toLowerCase();
                v._folder = lastIdx >= 0 ? path.substring(0, lastIdx) : '';
                v._codecLower = (v.codec || 'unknown').toLowerCase();
            });

            window.ALL_VIDEOS = data;
            console.log(`✅ Loaded ${window.ALL_VIDEOS.length} videos from API (Pre-processed)`);
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
        })
        // Reine Statusabfrage beim Start: schlägt sie fehl, bleibt es beim
        // normalen Dashboard — kein Toast, aber auch keine stille Rejection.
        .catch(err => console.error('Setup-Status nicht abrufbar:', err));
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
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        })
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
                            <span class="material-icons text-arcade-cyan" aria-hidden="true">${dir.is_root ? 'folder_open' : 'folder'}</span>
                            <div><div class="text-text-main font-medium">${displayName}</div>
                            <div class="text-xs text-gray-500">${sizeGB} GB • ${dir.file_count.toLocaleString()} files</div></div>
                        </div>
                        <div class="setup-dir-checkbox hidden"><span class="material-icons text-arcade-cyan" aria-hidden="true">check_circle</span></div>
                    </div>
                </div>`;
            }).join('');
        })
        .catch(err => {
            // Ohne diesen Zweig bleibt der Einrichtungs-Assistent bei einem
            // Serverfehler dauerhaft leer — ohne jeden Hinweis.
            console.error('Verzeichnisse nicht abrufbar:', err);
            const listEl = document.getElementById('setupDirectoryList');
            if (listEl) {
                listEl.innerHTML = '<div class="text-center py-8 text-danger">'
                    + 'Verzeichnisse konnten nicht geladen werden. '
                    + '<button onclick="loadSetupDirectories()" class="underline">Erneut versuchen</button>'
                    + '</div>';
            }
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

    apiWrite('/api/setup/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            scan_targets: selectedSetupDirectories,
            scan_images: document.getElementById('setupScanImages')?.checked || false
        })
    }, { action: 'Einrichtung abschließen' })
        .then(res => (res ? res.json() : null))
        .then(data => {
            if (data && data.success) {
                hideSetupWizard();
                location.reload();
            }
        });
}

function skipSetup() {
    apiWrite('/api/setup/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_targets: ['/media'], scan_images: false })
    }, { action: 'Einrichtung überspringen' })
        .then(res => { if (res) location.reload(); });
}

// Duplicate Checker Fullscreen Mode has been moved to duplicates.js
// See duplicates.js for: openDuplicateChecker, closeDuplicateChecker,
// renderDuplicateCheckerGroup, renderDuplicateFile, navigateDuplicateGroup,
// keepDuplicateFile, skipDuplicateGroup, markAnyIsFine, previewDuplicateFile,
// duplicateCheckerKeyHandler


document.addEventListener('DOMContentLoaded', () => {
    setTimeout(checkSetupRequired, 500);
});
