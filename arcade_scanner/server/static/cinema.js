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
    hideCinemaPlaybackError();
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
            // Der übliche Grund ist die Autoplay-Sperre des Browsers: stumm
            // geht es dann doch. Scheitert auch das, liegt es nicht am Ton —
            // dann übernimmt der error-Handler am Element.
            video.muted = true;
            video.play().catch(() => {});
        });
    }

    modal.classList.add('active');

    // Update UI components
    initCinemaErrorReporting();
    initCinemaTransport();
    updateCinemaMeta();
    updateCinemaTransport();
    updateCinemaButtons();
    updateCinemaInfo();
    updateCinemaTags();

    // Offene Ähnlich-Leiste folgt dem neuen Medium (Blättern mit ← / →)
    if (typeof loadCinemaSimilar === 'function') loadCinemaSimilar();

    // Use capturing phase to ensure we catch ESC before video element
    window.addEventListener('keydown', cinemaKeyHandler, true);

    // Focus modal to steal focus from video initially
    if (modal) {
        modal.tabIndex = -1;
        modal.focus();
    }
}

/**
 * Sagt, warum gerade nichts abspielt.
 *
 * Bisher gab es dafür gar nichts: Weder `<video>` noch `<img>` hatten einen
 * error-Handler. Ist die Datei verschoben, gelöscht oder das Laufwerk nicht
 * eingehängt, öffnete sich der Wiedergabe-Dialog mit einem schwarzen Bild und
 * schwieg. Genau der Fall, in dem der Nutzer das Programm für kaputt hält.
 *
 * Der Grund wird nachgeschlagen statt geraten: Ein HEAD auf dieselbe Adresse
 * unterscheidet „Datei nicht da" (404) von „Server sagt nein" (403) und von
 * allem anderen — etwa einem Codec, den der Browser nicht kann.
 */
function showCinemaPlaybackError(path) {
    const box = document.getElementById('cinemaPlaybackError');
    const text = document.getElementById('cinemaPlaybackErrorText');
    const pathBox = document.getElementById('cinemaPlaybackErrorPath');
    if (!box || !text || !pathBox) return;

    text.textContent = 'The file could not be played.';
    pathBox.textContent = path || '';
    box.classList.remove('hidden');
    box.classList.add('flex');

    if (!path) return;

    fetch('/stream?path=' + encodeURIComponent(path), { method: 'HEAD' })
        .then(response => {
            if (response.status === 404) {
                text.textContent = 'This file is no longer where the library '
                    + 'expects it. It may have been moved, renamed or deleted — '
                    + 'or its drive is not mounted right now.';
            } else if (response.status === 403) {
                text.textContent = 'The server refused access to this path.';
            } else if (response.ok) {
                text.textContent = 'The file is there, but this browser cannot '
                    + 'play it — most likely an unsupported codec or container.';
            }
        })
        .catch(() => {
            // Auch der HEAD kommt nicht durch: dann ist die Verbindung das
            // Problem, nicht die Datei. Die allgemeine Meldung bleibt stehen.
        });
}

function hideCinemaPlaybackError() {
    const box = document.getElementById('cinemaPlaybackError');
    if (!box) return;
    box.classList.remove('flex');
    box.classList.add('hidden');
}

/**
 * Hängt die error-Handler an. Zuweisung statt addEventListener, damit ein
 * zweiter Aufruf nicht einen zweiten Handler anhängt.
 */
function initCinemaErrorReporting() {
    const video = document.getElementById('cinemaVideo');
    const image = document.getElementById('cinemaImage');

    if (video) {
        video.onerror = () => {
            // Ein leeres src ist kein Fehler, sondern das Aufräumen beim
            // Schließen und beim Umschalten auf Bild.
            if (!video.getAttribute('src')) return;
            showCinemaPlaybackError(currentCinemaPath);
        };
    }
    if (image) {
        image.onerror = () => {
            if (!image.getAttribute('src')) return;
            showCinemaPlaybackError(currentCinemaPath);
        };
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
    hideCinemaPlaybackError();

    currentCinemaPath = null;
    currentCinemaVideo = null;

    // Close any open panels
    if (typeof closeOptimize === 'function') closeOptimize();
    if (typeof closeGifExport === 'function') closeGifExport();
    if (typeof closeCinemaSimilar === 'function') closeCinemaSimilar();

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

    } else if (key === 's') {
        // Ähnliche Medien
        e.preventDefault();
        if (typeof toggleCinemaSimilar === 'function') {
            toggleCinemaSimilar();
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
        const reservedKeys = ['f', 'v', 'g', 'o', 'i', 's', ' ', 'escape', 'arrowleft', 'arrowright'];
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

    const path = currentCinemaPath;

    apiWrite(`/favorite?path=` + encodeURIComponent(path) + `&state=${newState}`, {}, {
        action: 'Favorit ändern',
    }).then(response => {
        if (!response) return;   // apiWrite hat den Fehler bereits gemeldet

        currentCinemaVideo.favorite = newState;

        // Update in ALL_VIDEOS array
        const videoInArray = window.ALL_VIDEOS.find(v => v.FilePath === path);
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

    apiWrite(`/hide?path=` + encodeURIComponent(currentCinemaPath) + `&state=true`, {}, {
        action: 'In den Vault verschieben',
    }).then(response => {
        if (!response) return;   // Fehler gemeldet — Cinema bleibt offen
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
                <span class="info-value" style="color: ${v.Status === 'SOURCE' ? 'var(--ds-av1)' : (v.Status === 'HIGH' ? 'var(--ds-bitrate)' : 'var(--ds-optimized)')}">${v.Status}</span>
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
                <span class="info-value" style="color: ${v.Status === 'SOURCE' ? 'var(--ds-av1)' : (v.Status === 'HIGH' ? 'var(--ds-bitrate)' : 'var(--ds-optimized)')}">${v.Status}</span>
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
        // Knoten statt String. Der Tag-Name ist frei eingegeben und stand hier
        // in einem interpolierten `onclick` — ein Apostroph („Ralfs Auswahl")
        // machte den Knopf schon funktionsunfähig, und alles darüber hinaus
        // wäre eingeschleuster Code gewesen.
        //
        // HTML-Maskierung allein genügt an dieser Stelle **nicht**: Der Browser
        // dekodiert Entitäten im Attributwert, bevor der Inhalt als JavaScript
        // gelesen wird — aus `&#39;` würde wieder ein Apostroph. Deshalb der
        // Weg über addEventListener, wie in tag_manager.js.
        assignedContainer.replaceChildren();
        if (videoTags.length > 0) {
            videoTags.forEach(tagName => {
                const tagData = availableTags.find(t => t.name === tagName);
                const color = tagData?.color || '#888';

                const chip = document.createElement('div');
                chip.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-black/60 border border-ink/20 backdrop-blur-sm shadow-xl transition-all hover:scale-105 group/chip select-none';

                const dot = document.createElement('span');
                dot.className = 'w-2 h-2 rounded-full shadow-[0_0_8px_var(--color)]';
                dot.style.backgroundColor = color;
                dot.style.setProperty('--color', color);

                const label = document.createElement('span');
                label.className = 'text-xs text-white font-semibold tracking-wide drop-shadow-md';
                label.textContent = tagName;

                const removeBtn = document.createElement('button');
                removeBtn.className = 'ml-1 text-white/40 hover:text-red-400 hover:bg-ink/10 rounded-full p-0.5 transition-colors';
                removeBtn.title = 'Remove Tag';
                removeBtn.innerHTML = '<span class="material-icons text-[14px] font-bold" aria-hidden="true">close</span>';
                removeBtn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    toggleCinemaTag(tagName);
                });

                chip.append(dot, label, removeBtn);
                assignedContainer.append(chip);
            });
        }
    }

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-white/60 italic">No tags available</span>';
        return;
    }

    // Gleiche Begründung wie oben: Name und Farbe kommen aus der Eingabe des
    // Nutzers und gehören nicht in einen Attributstring.
    container.replaceChildren();
    availableTags.forEach(tag => {
        const button = document.createElement('button');
        button.className = 'cinema-tag-chip' + (videoTags.includes(tag.name) ? ' active' : '');
        button.style.setProperty('--tag-color', tag.color || '');
        button.addEventListener('click', () => toggleCinemaTag(tag.name));

        const dot = document.createElement('span');
        dot.className = 'tag-dot';
        dot.style.backgroundColor = tag.color || '';

        button.append(dot, document.createTextNode(tag.name));
        container.append(button);
    });
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
    toast.className = 'fixed bottom-24 left-1/2 -translate-x-1/2 px-4 py-2 bg-black/80 text-white rounded-lg backdrop-blur border border-ink/20 text-sm font-medium z-[10001] animate-fade-in';
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
