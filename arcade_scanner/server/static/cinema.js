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

    // Check if this is an image
    if (currentCinemaVideo && currentCinemaVideo.media_type === 'image') {
        // IMAGE MODE
        video.classList.add('hidden');
        video.pause();
        video.src = '';

        if (image) {
            image.classList.remove('hidden');
            image.src = streamUrl;
        }
    } else {
        // VIDEO MODE
        if (image) {
            image.classList.add('hidden');
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

    currentCinemaPath = null;
    currentCinemaVideo = null;
}

/**
 * Navigate to previous or next item in the filtered list
 * @param {number} direction - -1 for previous, 1 for next
 */
function navigateCinema(direction) {
    if (!currentCinemaPath) return;

    // Find current index in filteredVideos (from engine.js)
    const currentIndex = filteredVideos.findIndex(v => v.FilePath === currentCinemaPath);
    if (currentIndex === -1) return;

    // Calculate new index with wrap-around
    let newIndex = currentIndex + direction;
    if (newIndex < 0) newIndex = filteredVideos.length - 1;
    if (newIndex >= filteredVideos.length) newIndex = 0;

    const newVideo = filteredVideos[newIndex];
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

// --- KEYBOARD HANDLER ---

/**
 * Handle keyboard events in cinema mode
 * @param {KeyboardEvent} e - Keyboard event
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
    } else {
        // Check custom tag shortcuts (A-Z except reserved)
        const reservedKeys = ['f', 'v', ' ', 'escape', 'arrowleft', 'arrowright'];
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
        favBtn.style.opacity = currentCinemaVideo.favorite ? '0.6' : '1';
        favBtn.title = currentCinemaVideo.favorite ? 'Already a Favorite' : 'Add to Favorites';
    }

    const vaultBtn = document.querySelector('.cinema-action-btn[onclick="cinemaVault()"]');
    if (vaultBtn) {
        vaultBtn.style.opacity = currentCinemaVideo.hidden ? '0.6' : '1';
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
                <span class="info-value" style="color: ${v.Status === 'HIGH' ? '#E3A857' : '#568203'}">${v.Status}</span>
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
                <span class="info-value" style="color: ${v.Status === 'HIGH' ? '#E3A857' : '#568203'}">${v.Status}</span>
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

/**
 * Open GIF export modal for current cinema video
 */
function cinemaExportGif() {
    if (!currentCinemaPath || !currentCinemaVideo) return;

    // Only allow GIF export for videos
    if (currentCinemaVideo.media_type === 'image') {
        showCinemaToast('GIF export only available for videos');
        return;
    }

    // Create modal HTML
    const modalHTML = `
        <div id="gifExportModal" class="fixed inset-0 z-[10002] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="bg-[#14141c] rounded-xl border border-white/10 max-w-md w-full p-6 shadow-2xl">
                <div class="flex items-center justify-between mb-6">
                    <h3 class="text-xl font-bold text-white flex items-center gap-2">
                        <span class="material-icons text-arcade-cyan">gif</span>
                        Export as GIF
                    </h3>
                    <button onclick="closeGifExportModal()" class="text-gray-400 hover:text-white">
                        <span class="material-icons">close</span>
                    </button>
                </div>
                
                <div class="space-y-4">
                    <!-- Trim Controls -->
                    <div class="bg-white/5 rounded-lg p-3 border border-white/10">
                        <label class="block text-sm font-semibold text-gray-300 mb-2">Clip Selection</label>
                        <div class="flex items-center gap-2 mb-2">
                            <input type="text" id="gifTrimStart" placeholder="00:00" 
                                   class="flex-1 bg-black/30 border border-white/10 text-white px-2 py-1.5 rounded text-sm font-mono text-center focus:border-arcade-cyan/50 focus:outline-none"
                                   oninput="updateGifEstimate()">
                            <button onclick="setGifTrimFromVideo('start')" 
                                    class="px-2 py-1.5 bg-white/10 hover:bg-white/20 rounded text-xs text-gray-400 hover:text-white border border-white/10 transition-colors"
                                    title="Set to current video time">
                                <span class="material-icons text-sm">arrow_downward</span>
                            </button>
                            <span class="text-gray-500">-</span>
                            <input type="text" id="gifTrimEnd" placeholder="END" 
                                   class="flex-1 bg-black/30 border border-white/10 text-white px-2 py-1.5 rounded text-sm font-mono text-center focus:border-arcade-cyan/50 focus:outline-none"
                                   oninput="updateGifEstimate()">
                            <button onclick="setGifTrimFromVideo('end')" 
                                    class="px-2 py-1.5 bg-white/10 hover:bg-white/20 rounded text-xs text-gray-400 hover:text-white border border-white/10 transition-colors"
                                    title="Set to current video time">
                                <span class="material-icons text-sm">arrow_downward</span>
                            </button>
                        </div>
                        <div class="text-xs text-gray-500">
                            Duration: <span id="gifDuration" class="text-arcade-cyan">${currentCinemaVideo.Duration_Sec ? currentCinemaVideo.Duration_Sec.toFixed(1) : '0.0'}s</span>
                        </div>
                    </div>
                    
                    <!-- Preset Selection -->
                    <div>
                        <label class="block text-sm font-semibold text-gray-300 mb-2">Quality Preset</label>
                        <select id="gifPreset" class="w-full bg-black/30 border border-white/10 text-white px-3 py-2 rounded-lg focus:border-arcade-cyan/50 focus:outline-none"
                                onchange="updateGifEstimate()">
                            <option value="360p">360p (640×360) - Small</option>
                            <option value="480p">480p (854×480) - Medium</option>
                            <option value="720p" selected>720p (1280×720) - High</option>
                            <option value="1080p">1080p (1920×1080) - Very High</option>
                            <option value="original">Original (${currentCinemaVideo.Width}×${currentCinemaVideo.Height})</option>
                        </select>
                    </div>
                    
                    <!-- FPS Slider -->
                    <div>
                        <label class="block text-sm font-semibold text-gray-300 mb-2">
                            Frame Rate: <span id="gifFpsValue" class="text-arcade-cyan">15</span> fps
                        </label>
                        <input type="range" id="gifFps" min="10" max="30" value="15" step="5" 
                               class="w-full" 
                               oninput="document.getElementById('gifFpsValue').textContent = this.value; updateGifEstimate()">
                    </div>
                    
                    <!-- Quality Slider -->
                    <div>
                        <label class="block text-sm font-semibold text-gray-300 mb-2">
                            Quality: <span id="gifQualityValue" class="text-arcade-cyan">80</span>%
                        </label>
                        <input type="range" id="gifQuality" min="50" max="100" value="80" step="10" 
                               class="w-full"
                               oninput="document.getElementById('gifQualityValue').textContent = this.value; updateGifEstimate()">
                    </div>
                    
                    <!-- Estimated Size -->
                    <div class="bg-white/5 rounded-lg p-3 border border-white/10">
                        <div class="text-xs text-gray-400 mb-1">Estimated Size</div>
                        <div id="gifEstimatedSize" class="text-lg font-bold text-arcade-cyan">~5.2 MB</div>
                    </div>
                </div>
                
                <div class="flex gap-3 mt-6">
                    <button onclick="closeGifExportModal()" 
                            class="flex-1 py-2.5 rounded-lg font-semibold text-gray-400 bg-white/5 hover:bg-white/10 hover:text-white transition-all">
                        Cancel
                    </button>
                    <button onclick="startGifExport()" 
                            class="flex-1 py-2.5 rounded-lg font-semibold text-black bg-arcade-cyan hover:bg-cyan-300 transition-all flex items-center justify-center gap-2">
                        <span class="material-icons text-[18px]">download</span>
                        Export GIF
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Initial size estimate
    updateGifEstimate();
}

/**
 * Update GIF size estimation based on current settings
 */
function updateGifEstimate() {
    if (!currentCinemaVideo) return;

    const preset = document.getElementById('gifPreset')?.value || '720p';
    const fps = parseInt(document.getElementById('gifFps')?.value || 15);
    const quality = parseInt(document.getElementById('gifQuality')?.value || 80);

    // Get trim times
    const startInput = document.getElementById('gifTrimStart')?.value || '';
    const endInput = document.getElementById('gifTrimEnd')?.value || '';

    let startTime = 0;
    let endTime = currentCinemaVideo.Duration_Sec || 10;

    // Parse start time (format: MM:SS or SS)
    if (startInput) {
        const parts = startInput.split(':');
        if (parts.length === 2) {
            startTime = parseInt(parts[0]) * 60 + parseInt(parts[1]);
        } else {
            startTime = parseInt(startInput) || 0;
        }
    }

    // Parse end time
    if (endInput) {
        const parts = endInput.split(':');
        if (parts.length === 2) {
            endTime = parseInt(parts[0]) * 60 + parseInt(parts[1]);
        } else {
            endTime = parseInt(endInput) || endTime;
        }
    }

    // Calculate duration
    const duration = Math.max(0.1, endTime - startTime);

    // Update duration display
    const durationEl = document.getElementById('gifDuration');
    if (durationEl) {
        durationEl.textContent = duration.toFixed(1) + 's';
    }

    // Get dimensions based on preset
    const presets = {
        "360p": { w: 640, h: 360 },
        "480p": { w: 854, h: 480 },
        "720p": { w: 1280, h: 720 },
        "1080p": { w: 1920, h: 1080 },
        "original": { w: currentCinemaVideo.Width || 1920, h: currentCinemaVideo.Height || 1080 }
    };

    const dims = presets[preset] || presets["720p"];

    // Estimate size (rough formula)
    const pixelsPerFrame = dims.w * dims.h;
    const frames = fps * duration;
    const qualityFactor = quality / 100;
    const baseBytesPerFrame = (pixelsPerFrame * 0.3) * qualityFactor;
    const headerSize = 1024;
    const totalBytes = (baseBytesPerFrame * frames) + headerSize;
    const sizeMB = totalBytes / (1024 * 1024);

    // Update display
    const sizeEl = document.getElementById('gifEstimatedSize');
    if (sizeEl) {
        sizeEl.textContent = `~${sizeMB.toFixed(1)} MB`;
    }
}

/**
 * Set trim time from current video playback position
 */
function setGifTrimFromVideo(type) {
    const video = document.getElementById('cinemaVideo');
    if (!video) return;

    const currentTime = Math.floor(video.currentTime);
    const minutes = Math.floor(currentTime / 60);
    const seconds = currentTime % 60;
    const timeStr = minutes > 0 ? `${minutes}:${seconds.toString().padStart(2, '0')}` : `${seconds}`;

    if (type === 'start') {
        document.getElementById('gifTrimStart').value = timeStr;
    } else {
        document.getElementById('gifTrimEnd').value = timeStr;
    }

    updateGifEstimate();
}

/**
 * Close GIF export modal
 */
function closeGifExportModal() {
    const modal = document.getElementById('gifExportModal');
    if (modal) modal.remove();
}

/**
 * Start GIF export process
 */
async function startGifExport() {
    if (!currentCinemaPath) return;

    const preset = document.getElementById('gifPreset').value;
    const fps = parseInt(document.getElementById('gifFps').value);
    const quality = parseInt(document.getElementById('gifQuality').value);

    closeGifExportModal();
    showCinemaToast('Starting GIF export...');

    try {
        const response = await fetch('/api/export/gif', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                path: currentCinemaPath,
                preset: preset,
                fps: fps,
                quality: quality
            })
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const result = await response.json();

        // Show success message
        showCinemaToast(`GIF export started! (~${result.estimated_size_mb} MB)`);

        // Wait a bit for processing, then trigger download
        setTimeout(() => {
            window.location.href = result.download_url;
            showCinemaToast('Downloading GIF...');
        }, 3000);

    } catch (error) {
        console.error('GIF export error:', error);
        showCinemaToast('GIF export failed');
    }
}

// --- EXPORTS ---
// Expose functions to global scope for HTML onclick handlers
window.openCinema = openCinema;
window.closeCinema = closeCinema;
window.navigateCinema = navigateCinema;
window.cinemaFavorite = cinemaFavorite;
window.cinemaVault = cinemaVault;
window.cinemaLocate = cinemaLocate;
window.toggleCinemaInfo = toggleCinemaInfo;
window.toggleCinemaTagPanel = toggleCinemaTagPanel;
window.toggleCinemaTag = toggleCinemaTag;
window.updateCinemaTags = updateCinemaTags;
window.cinemaExportGif = cinemaExportGif;
window.closeGifExportModal = closeGifExportModal;
window.startGifExport = startGifExport;
window.updateGifEstimate = updateGifEstimate;
window.setGifTrimFromVideo = setGifTrimFromVideo;

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
