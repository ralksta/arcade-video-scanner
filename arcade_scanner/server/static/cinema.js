/**
 * Cinema Module - Full-screen video/image viewer with keyboard navigation
 *
 * Features:
 * - Video playback and image display
 * - Keyboard navigation (←→ for prev/next, F for favorite, V for vault)
 * - Tag assignment via shortcuts (A-Z keys mapped to tags)
 * - Info panel with media metadata
 * - Tag picker panel
 */

// --- CINEMA STATE ---
let currentCinemaPath = null;
let currentCinemaVideo = null;
let cinemaPlaylist = null; // Overrides filteredVideos if set (e.g. for folder view)

/**
 * Set the playlist for cinema navigation
 * @param {Array|null} playlist - Array of video objects or null to use default filteredVideos
 */
function setCinemaPlaylist(playlist) {
    cinemaPlaylist = playlist;
}

// --- MAIN FUNCTIONS ---

/**
 * Open the cinema modal to play/view a video or image
 * Supports keyboard navigation (←→), favorites (F), and other shortcuts
 *
 * @param {HTMLElement} container - The element containing data-path attribute,
 *                                  or a child of a .video-card-container
 */
function openCinema(container) {
    // 1. Try to find path on the clicked container itself
    let path = container.getAttribute('data-path');

    // 2. If not found, fall back to the main card container
    if (!path) {
        const card = container.closest('.video-card-container');
        if (card) path = card.getAttribute('data-path');
    }

    if (!path) return;

    const fileName = path.split(/[\\\/]/).pop();
    currentCinemaPath = path;

    // Find the video object from allVideos
    currentCinemaVideo = window.ALL_VIDEOS.find(v => v.FilePath === path);

    const modal = document.getElementById('cinemaModal');
    const video = document.getElementById('cinemaVideo');
    const image = document.getElementById('cinemaImage');
    document.getElementById('cinemaTitle').innerText = fileName;

    const streamUrl = `/stream?path=` + encodeURIComponent(path);

    const sourceMsg = document.getElementById('cinemaSourceMessage');

    // Reset visibility
    video.classList.add('hidden');
    if (image) image.classList.add('hidden');
    if (sourceMsg) {
        sourceMsg.classList.remove('flex');
        sourceMsg.classList.add('hidden');
    }

    // Check if this is a source video
    if (currentCinemaVideo && currentCinemaVideo.Status === 'SOURCE') {
        video.pause();
        video.src = '';
        if (image) image.src = '';
        
        if (sourceMsg) {
            sourceMsg.classList.remove('hidden');
            sourceMsg.classList.add('flex');
            const downloadBtn = document.getElementById('cinemaDownloadBtn');
            if (downloadBtn) {
                downloadBtn.href = streamUrl;
                downloadBtn.download = fileName;
            }
        }
    } else if (currentCinemaVideo && currentCinemaVideo.media_type === 'image') {
        // IMAGE MODE
        video.pause();
        video.src = '';

        if (image) {
            image.classList.remove('hidden');
            image.src = streamUrl;
        }
    } else {
        // VIDEO MODE
        if (image) {
            image.src = '';
        }
        video.classList.remove('hidden');

        video.src = streamUrl;
        video.load();
        video.play().catch(() => {
            video.muted = true;
            video.play();
        });
    }

    modal.classList.add('active');

    // Update UI components
    initCinemaTransport();
    updateCinemaMeta();
    updateCinemaTransport();
    updateCinemaButtons();
    updateCinemaInfo();
    updateCinemaTags();

    // Use capturing phase to ensure we catch ESC before video element
    window.addEventListener('keydown', cinemaKeyHandler, true);

    // Focus modal to steal focus from video initially
    if (modal) {
        modal.tabIndex = -1;
        modal.focus();
    }
}

/**
 * Close the cinema modal and clean up resources
 */
function closeCinema() {
    window.removeEventListener('keydown', cinemaKeyHandler, true);

    const modal = document.getElementById('cinemaModal');
    const video = document.getElementById('cinemaVideo');
    const image = document.getElementById('cinemaImage');
    const infoPanel = document.getElementById('cinemaInfoPanel');
    const tagPanel = document.getElementById('cinemaTagPanel');

    modal.classList.remove('active');
    infoPanel.classList.remove('active');
    if (tagPanel) tagPanel.classList.add('hidden');

    video.pause();
    video.src = '';

    if (image) {
        image.src = '';
        image.classList.add('hidden');
    }

    const sourceMsg = document.getElementById('cinemaSourceMessage');
    if (sourceMsg) {
        sourceMsg.classList.remove('flex');
        sourceMsg.classList.add('hidden');
    }

    currentCinemaPath = null;
    currentCinemaVideo = null;

    // Close any open panels
    if (typeof closeOptimize === 'function') closeOptimize();
    if (typeof closeGifExport === 'function') closeGifExport();

    // Note: We do NOT clear cinemaPlaylist here because we might want to 
    // keep browsing the same context if we reopen a file in the same view.
    // The playlist should be managed by the view (engine.js/treemap.js).
}

/**
 * Navigate to previous or next item in the filtered list
 * @param {number} direction - -1 for previous, 1 for next
 */
function navigateCinema(direction) {
    if (!currentCinemaPath) return;

    // Use custom playlist if available, otherwise default to global filtered list
    const sourceList = cinemaPlaylist || filteredVideos;

    // Find current index in sourceList
    const currentIndex = sourceList.findIndex(v => v.FilePath === currentCinemaPath);
    if (currentIndex === -1) return;

    // Calculate new index with wrap-around
    let newIndex = currentIndex + direction;
    if (newIndex < 0) newIndex = sourceList.length - 1;
    if (newIndex >= sourceList.length) newIndex = 0;

    const newVideo = sourceList[newIndex];
    if (newVideo) {
        // Clean up current streams to avoid file handle leak
        const video = document.getElementById('cinemaVideo');
        const image = document.getElementById('cinemaImage');
        if (video) {
            video.pause();
            video.src = '';
            video.load();
        }
        if (image) {
            image.src = '';
        }

        // Create dummy container with path and reopen
        const dummyContainer = document.createElement('div');
        dummyContainer.setAttribute('data-path', newVideo.FilePath);
        openCinema(dummyContainer);
    }
}

// --- TRANSPORT ---
// Eigener Transport statt der nativen Controls, damit die Bedienleiste dem
// Design System folgt (3px-Scrubber mit Accent-Fill, Mono-Timestamps,
// hervorgehobener Play-Button). Die Tastatur-Shortcuts bleiben unveraendert.

let _cinemaTransportReady = false;
let _cinemaScrubbing = false;

/**
 * Format seconds as MM:SS (or H:MM:SS past an hour) for the transport readouts
 * @param {number} sec
 * @returns {string}
 */
function formatCinemaTime(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    const mm = String(m).padStart(2, '0');
    const ss = String(s).padStart(2, '0');
    return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/**
 * Bind the transport controls to the video element. Idempotent — the listeners
 * are attached once and survive src changes when navigating the playlist.
 */
function initCinemaTransport() {
    if (_cinemaTransportReady) return;

    const video = document.getElementById('cinemaVideo');
    const scrub = document.getElementById('cinemaScrub');
    if (!video || !scrub) return;

    video.addEventListener('timeupdate', () => {
        if (!_cinemaScrubbing) updateCinemaTransport();
    });
    video.addEventListener('loadedmetadata', updateCinemaTransport);
    video.addEventListener('play', updateCinemaTransport);
    video.addEventListener('pause', updateCinemaTransport);
    video.addEventListener('volumechange', updateCinemaTransport);

    // Waehrend des Ziehens nicht gegen den Nutzer zurueckschreiben
    scrub.addEventListener('pointerdown', () => { _cinemaScrubbing = true; });
    scrub.addEventListener('input', () => {
        if (!isFinite(video.duration) || !video.duration) return;
        video.currentTime = (scrub.value / 1000) * video.duration;
        const cur = document.getElementById('cinemaTimeCur');
        if (cur) cur.textContent = formatCinemaTime(video.currentTime);
        const pct = (scrub.value / 10).toFixed(2);
        scrub.style.background =
            `linear-gradient(90deg, var(--ds-accent-tint) ${pct}%, rgba(255,255,255,0.25) ${pct}%)`;
    });
    const endScrub = () => { _cinemaScrubbing = false; };
    scrub.addEventListener('pointerup', endScrub);
    scrub.addEventListener('change', endScrub);

    _cinemaTransportReady = true;
}

/**
 * Push the current playback state into the transport UI
 */
function updateCinemaTransport() {
    const video = document.getElementById('cinemaVideo');
    const bar = document.getElementById('cinemaBottomBar');
    if (!video || !bar) return;

    // Bilder und SOURCE-Dateien haben keine Wiedergabe — Leiste ausblenden
    const playable = !video.classList.contains('hidden');
    bar.style.display = playable ? 'flex' : 'none';
    if (!playable) return;

    const dur = isFinite(video.duration) ? video.duration : 0;
    const scrub = document.getElementById('cinemaScrub');
    if (scrub) {
        if (!_cinemaScrubbing) {
            scrub.value = dur ? Math.round((video.currentTime / dur) * 1000) : 0;
        }
        // Ein natives range-Input faerbt den zurueckgelegten Teil nicht selbst —
        // der Fill kommt als harter Farbstopp im Track-Hintergrund.
        const pct = (scrub.value / 10).toFixed(2);
        scrub.style.background =
            `linear-gradient(90deg, var(--ds-accent-tint) ${pct}%, rgba(255,255,255,0.25) ${pct}%)`;
    }

    const cur = document.getElementById('cinemaTimeCur');
    if (cur) cur.textContent = formatCinemaTime(video.currentTime);
    const total = document.getElementById('cinemaTimeDur');
    if (total) total.textContent = formatCinemaTime(dur);

    const playIcon = document.querySelector('#cinemaPlayBtn .material-icons');
    if (playIcon) playIcon.textContent = video.paused ? 'play_arrow' : 'pause';

    const muteIcon = document.querySelector('#cinemaMuteBtn .material-icons');
    if (muteIcon) muteIcon.textContent = (video.muted || video.volume === 0) ? 'volume_off' : 'volume_up';
}

/**
 * Fill the mono metadata line under the filename (resolution, codec, bitrate)
 */
function updateCinemaMeta() {
    const meta = document.getElementById('cinemaMeta');
    if (!meta) return;

    const v = currentCinemaVideo;
    if (!v) { meta.textContent = ''; return; }

    const parts = [];
    if (v.Width && v.Height) parts.push(`${v.Width}x${v.Height}`);
    if (v.codec) parts.push(String(v.codec).toUpperCase());
    if (v.media_type === 'video' && v.Bitrate_Mbps) parts.push(`${v.Bitrate_Mbps.toFixed(1)} Mbps`);
    else if (v.Size_MB) parts.push(`${v.Size_MB.toFixed(0)} MB`);
    meta.textContent = parts.join('  ·  ');
}

/**
 * Toggle playback of the current video
 */
function cinemaTogglePlay() {
    const video = document.getElementById('cinemaVideo');
    if (!video || video.classList.contains('hidden')) return;
    if (video.paused) video.play(); else video.pause();
}

/**
 * Toggle mute on the current video
 */
function cinemaToggleMute() {
    const video = document.getElementById('cinemaVideo');
    if (!video) return;
    video.muted = !video.muted;
}

/**
 * Toggle fullscreen for the cinema modal
 */
function cinemaToggleFullscreen() {
    const modal = document.getElementById('cinemaModal');
    if (!modal) return;
    if (document.fullscreenElement) {
        document.exitFullscreen();
    } else if (modal.requestFullscreen) {
        modal.requestFullscreen();
    }
}

// --- KEYBOARD HANDLER ---

/**
 * Handle keyboard events in cinema mode
 *
 * Shortcuts:
 *   Escape       – Close cinema
 *   ← / →        – Previous / Next in playlist
 *   Space        – Play / Pause video
 *   F            – Toggle Favorite
 *   V            – Move to Vault
 *   G            – Toggle GIF Export panel
 *   O            – Toggle Optimizer panel
 *   I            – Toggle Info panel
 *   A–Z          – Tag shortcuts (configured in Settings)
 *
 * @param {KeyboardEvent} e
 */
function cinemaKeyHandler(e) {
    // Skip if typing in an input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    const key = e.key.toLowerCase();

    if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        closeCinema();

    } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        navigateCinema(-1);

    } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        navigateCinema(1);

    } else if (e.key === ' ' || e.code === 'Space') {
        // Play / Pause
        e.preventDefault();
        const video = document.getElementById('cinemaVideo');
        if (video && !video.classList.contains('hidden')) {
            const wasPaused = video.paused;
            cinemaTogglePlay();
            showCinemaToast(wasPaused ? '▶ Play' : '⏸ Pause');
        }

    } else if (key === 'f') {
        e.preventDefault();
        if (currentCinemaPath) {
            cinemaFavorite();
            showCinemaToast('Favorite toggled');
        }

    } else if (key === 'v') {
        e.preventDefault();
        if (currentCinemaPath) {
            cinemaVault();
            showCinemaToast('Moved to Vault');
        }

    } else if (key === 'g') {
        // GIF Export panel toggle
        e.preventDefault();
        if (typeof cinemaExportGif === 'function') {
            cinemaExportGif();
            showCinemaToast('GIF Export [G]');
        }

    } else if (key === 'o') {
        // Optimizer panel toggle
        e.preventDefault();
        if (typeof cinemaOptimize === 'function') {
            cinemaOptimize();
        }

    } else if (key === 'i') {
        // Info panel toggle
        e.preventDefault();
        if (typeof toggleCinemaInfo === 'function') {
            toggleCinemaInfo();
            showCinemaToast('Info [I]');
        }

    } else {
        // Check custom tag shortcuts (A-Z except reserved)
        const reservedKeys = ['f', 'v', 'g', 'o', 'i', ' ', 'escape', 'arrowleft', 'arrowright'];
        if (key.length === 1 && /[a-z]/i.test(key) && !reservedKeys.includes(key)) {
            const tags = window.userSettings?.available_tags || [];
            const matchingTag = tags.find(t => t.shortcut && t.shortcut.toLowerCase() === key);
            if (matchingTag && currentCinemaPath) {
                e.preventDefault();
                toggleCinemaTag(matchingTag.name);
                showCinemaToast(`Tag: ${matchingTag.name}`);
            }
        }
    }
}


// --- ACTION BUTTONS ---

/**
 * Toggle favorite status for current cinema item
 */
function cinemaFavorite() {
    if (!currentCinemaPath || !currentCinemaVideo) return;

    const newState = !currentCinemaVideo.favorite;

    fetch(`/favorite?path=` + encodeURIComponent(currentCinemaPath) + `&state=${newState}`)
        .then(() => {
            currentCinemaVideo.favorite = newState;

            // Update in ALL_VIDEOS array
            const videoInArray = window.ALL_VIDEOS.find(v => v.FilePath === currentCinemaPath);
            if (videoInArray) {
                videoInArray.favorite = newState;
            }

            updateCinemaButtons();
            filterAndSort();
        });
}

/**
 * Move current cinema item to vault (hide)
 */
function cinemaVault() {
    if (!currentCinemaPath) return;

    fetch(`/hide?path=` + encodeURIComponent(currentCinemaPath) + `&state=true`)
        .then(() => {
            closeCinema();
            location.reload();
        });
}

/**
 * Reveal current cinema item in system file browser
 */
function cinemaLocate() {
    if (!currentCinemaPath) return;
    revealInFinder(currentCinemaPath);
}

// --- UI UPDATE FUNCTIONS ---

/**
 * Update cinema action button states (favorite, vault indicators)
 */
function updateCinemaButtons() {
    if (!currentCinemaVideo) return;

    const favBtn = document.querySelector('.cinema-action-btn[onclick="cinemaFavorite()"]');
    if (favBtn) {
        favBtn.classList.toggle('is-active', !!currentCinemaVideo.favorite);
        favBtn.title = currentCinemaVideo.favorite ? 'Already a Favorite' : 'Add to Favorites';
        const icon = document.getElementById('cinemaFavIcon');
        if (icon) icon.textContent = currentCinemaVideo.favorite ? 'star' : 'star_border';
    }

    const vaultBtn = document.querySelector('.cinema-action-btn[onclick="cinemaVault()"]');
    if (vaultBtn) {
        vaultBtn.classList.toggle('is-active', !!currentCinemaVideo.hidden);
        vaultBtn.title = currentCinemaVideo.hidden ? 'Already in Vault' : 'Move to Vault';
    }
}

/**
 * Update the cinema info panel with current media metadata
 */
function updateCinemaInfo() {
    if (!currentCinemaVideo) return;

    const v = currentCinemaVideo;
    const content = document.getElementById('cinemaInfoContent');
    if (!content) return;

    if (v.media_type === 'image') {
        content.innerHTML = `
            <div class="info-row">
                <span class="info-label">Type</span>
                <span class="info-value">Image (${(v.Container || v.FilePath.split('.').pop()).toUpperCase()})</span>
            </div>
            <div class="info-row">
                <span class="info-label">Resolution</span>
                <span class="info-value">${v.Width || '?'} × ${v.Height || '?'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">File Size</span>
                <span class="info-value">${formatSize(v.Size_MB)}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Status</span>
                <span class="info-value" style="color: ${v.Status === 'SOURCE' ? '#A855F7' : (v.Status === 'HIGH' ? '#E3A857' : '#568203')}">${v.Status}</span>
            </div>
        `;
    } else {
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
                <span class="info-value">${formatDurationLong(v.Duration_Sec)}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Frame Rate</span>
                <span class="info-value">${v.FrameRate || '?'} fps</span>
            </div>
            <div class="info-row">
                <span class="info-label">Video Codec</span>
                <span class="info-value">${v.codec} ${v.Profile ? `(${v.Profile})` : ''}</span>
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
                <span class="info-value">${formatBitrateKbps(v.Bitrate_Mbps)}</span>
            </div>
            <div class="info-row">
                <span class="info-label">File Size</span>
                <span class="info-value">${formatSize(v.Size_MB)}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Status</span>
                <span class="info-value" style="color: ${v.Status === 'SOURCE' ? '#A855F7' : (v.Status === 'HIGH' ? '#E3A857' : '#568203')}">${v.Status}</span>
            </div>
        `;
    }
}

/**
 * Toggle the cinema info panel visibility
 */
function toggleCinemaInfo() {
    const panel = document.getElementById('cinemaInfoPanel');
    panel.classList.toggle('active');
}

// --- TAG PANEL ---

/**
 * Toggle the cinema tag panel visibility
 */
function toggleCinemaTagPanel() {
    const panel = document.getElementById('cinemaTagPanel');
    if (panel) {
        panel.classList.toggle('hidden');
        if (!panel.classList.contains('hidden')) {
            updateCinemaTags();
        }
    }
}

/**
 * Update the cinema tag picker UI
 */
function updateCinemaTags() {
    const container = document.getElementById('cinemaTagPicker');
    if (!container || !currentCinemaVideo) return;

    const videoTags = currentCinemaVideo.tags || [];

    // Update assigned tags display
    const assignedContainer = document.getElementById('cinemaAssignedTags');
    if (assignedContainer) {
        if (videoTags.length === 0) {
            assignedContainer.innerHTML = '';
        } else {
            assignedContainer.innerHTML = videoTags.map(tagName => {
                const tagData = availableTags.find(t => t.name === tagName);
                const color = tagData?.color || '#888';
                return `
                 <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-black/60 border border-white/20 backdrop-blur-sm shadow-xl transition-all hover:scale-105 group/chip select-none">
                     <span class="w-2 h-2 rounded-full shadow-[0_0_8px_var(--color)]" style="background-color: ${color}; --color: ${color}"></span>
                     <span class="text-xs text-white font-semibold tracking-wide drop-shadow-md">${tagName}</span>
                     <button onclick="event.stopPropagation(); toggleCinemaTag('${tagName}')" class="ml-1 text-white/40 hover:text-red-400 hover:bg-white/10 rounded-full p-0.5 transition-colors" title="Remove Tag">
                         <span class="material-icons text-[14px] font-bold">close</span>
                     </button>
                 </div>
                 `;
            }).join('');
        }
    }

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

/**
 * Toggle a tag on the current cinema item
 * @param {string} tagName - Name of the tag to toggle
 */
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
        .then(() => {
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

// --- TOAST NOTIFICATIONS ---

/**
 * Show a brief toast notification in cinema mode
 * @param {string} message - Message to display
 */
function showCinemaToast(message) {
    let toast = document.getElementById('cinemaToast');
    if (toast) toast.remove();

    toast = document.createElement('div');
    toast.id = 'cinemaToast';
    toast.className = 'fixed bottom-24 left-1/2 -translate-x-1/2 px-4 py-2 bg-black/80 text-white rounded-lg backdrop-blur border border-white/20 text-sm font-medium z-[10001] animate-fade-in';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 1500);
}

// --- GIF EXPORT ---
// Handled by gif_export.js — cinemaExportGif() is overwritten at load time.
// See: /static/gif_export.js

// --- EXPORTS ---
// Expose core cinema functions to global scope for HTML onclick handlers.
// GIF-related exports (cinemaExportGif, updateGifEstimate, etc.) are registered
// by gif_export.js which loads after this file.
window.openCinema         = openCinema;
window.closeCinema        = closeCinema;
window.navigateCinema     = navigateCinema;
window.cinemaFavorite     = cinemaFavorite;
window.cinemaVault        = cinemaVault;
window.cinemaLocate       = cinemaLocate;
window.toggleCinemaInfo   = toggleCinemaInfo;
window.toggleCinemaTagPanel = toggleCinemaTagPanel;
window.toggleCinemaTag    = toggleCinemaTag;
window.updateCinemaTags   = updateCinemaTags;
window.setCinemaPlaylist  = setCinemaPlaylist;

// Expose state for other modules that need it (e.g., optimizer panel)
// Using defineProperty to create live bindings
Object.defineProperty(window, 'currentCinemaPath', {
    get: () => currentCinemaPath,
    set: (val) => { currentCinemaPath = val; }
});
Object.defineProperty(window, 'currentCinemaVideo', {
    get: () => currentCinemaVideo,
    set: (val) => { currentCinemaVideo = val; }
});
