// GIF Export Panel Functions
// This file contains the refactored GIF export functionality using a panel UI

// GIF Export State
let gifExportState = {
    preset: '720p',
    fps: 15,
    quality: 80
};

/**
 * Open GIF export panel for current cinema video
 */
function cinemaExportGif() {
    if (!window.currentCinemaPath || !window.currentCinemaVideo) return;

    // Only allow GIF export for videos
    if (window.currentCinemaVideo.media_type === 'image') {
        showCinemaToast('GIF export only available for videos');
        return;
    }

    // Reset state to defaults
    gifExportState = {
        preset: '720p',
        fps: 15,
        quality: 80
    };

    // Clear trim inputs
    document.getElementById('gifTrimStart').value = '';
    document.getElementById('gifTrimEnd').value = '';
    document.getElementById('gifQuality').value = '80';

    // Set active preset and FPS
    setGifPreset('720p');
    setGifFps(15);

    // Show panel
    const panel = document.getElementById('gifExportPanel');
    panel.classList.add('active');
    panel.style.transform = 'translateY(0)';

    // Adjust cinema container to make room for panel
    adjustCinemaForPanel(true);

    // Initial estimate
    updateGifEstimate();

    // Initialize timeline scrubber
    setTimeout(() => {
        const videoElement = document.getElementById('cinemaVideo');

        if (videoElement && window.TimelineScrubber) {
            // Destroy existing timeline if any
            // Check for destroy method to avoid errors if instance is corrupted
            if (window.gifTimeline && typeof window.gifTimeline.destroy === 'function') {
                window.gifTimeline.destroy();
            }

            // Create new timeline
            window.gifTimeline = new TimelineScrubber(videoElement, {
                containerSelector: '#gifTimeline',
                onChange: (times) => {
                    // Update trim inputs when handles are dragged
                    const startInput = document.getElementById('gifTrimStart');
                    const endInput = document.getElementById('gifTrimEnd');

                    if (startInput) {
                        startInput.value = formatTimeForInput(times.startTime);
                    }
                    if (endInput) {
                        endInput.value = formatTimeForInput(times.endTime);
                    }

                    // Update GIF size estimate
                    updateGifEstimate();
                }
            });

            window.gifTimeline.init();

            // Sync inputs -> timeline
            const startInput = document.getElementById('gifTrimStart');
            const endInput = document.getElementById('gifTrimEnd');

            const updateTimelineFromInputs = () => {
                if (!window.gifTimeline) return;

                const parse = (val) => {
                    if (!val) return 0;
                    const parts = val.split(':');
                    if (parts.length === 2) return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
                    return parseFloat(val);
                };

                const start = parse(startInput?.value);
                const end = parse(endInput?.value);

                if (!isNaN(start) && !isNaN(end)) {
                    window.gifTimeline.setTimes(start, end);
                }
            };

            if (startInput) startInput.onchange = updateTimelineFromInputs;
            if (endInput) endInput.onchange = updateTimelineFromInputs;
        }
    }, 100);
}

/**
 * Close GIF export panel
 */
function closeGifExport() {
    const panel = document.getElementById('gifExportPanel');
    panel.classList.remove('active');
    panel.style.transform = 'translateY(110%)';

    // Restore cinema container to full height
    adjustCinemaForPanel(false);
}

/**
 * Set GIF preset
 */
function setGifPreset(preset) {
    gifExportState.preset = preset;

    // Update UI - remove active from all
    ['360p', '480p', '720p', '1080p', 'Original'].forEach(p => {
        const el = document.getElementById(`gifPreset${p}`);
        if (el) {
            el.classList.remove('bg-white/10', 'shadow-sm', 'text-white');
            el.classList.add('text-gray-400');
        }
    });

    // Add active to selected
    const activeEl = document.getElementById(`gifPreset${preset}`);
    if (activeEl) {
        activeEl.classList.add('bg-white/10', 'shadow-sm', 'text-white');
        activeEl.classList.remove('text-gray-400');
    }

    // Update description
    const descriptions = {
        '360p': '640×360 - Small',
        '480p': '854×480 - Medium',
        '720p': '1280×720 - High Quality',
        '1080p': '1920×1080 - Very High',
        'original': `${window.currentCinemaVideo?.Width || 1920}×${window.currentCinemaVideo?.Height || 1080} - Original`
    };

    const descEl = document.getElementById('gifPresetDesc');
    if (descEl) {
        descEl.textContent = descriptions[preset] || descriptions['720p'];
    }

    updateGifEstimate();
}

/**
 * Set GIF FPS
 */
function setGifFps(fps) {
    gifExportState.fps = fps;

    // Update UI - remove active from all
    [10, 15, 20, 25, 30].forEach(f => {
        const el = document.getElementById(`gifFps${f}`);
        if (el) {
            el.classList.remove('bg-white/10', 'shadow-sm', 'text-white');
            el.classList.add('text-gray-400');
        }
    });

    // Add active to selected
    const activeEl = document.getElementById(`gifFps${fps}`);
    if (activeEl) {
        activeEl.classList.add('bg-white/10', 'shadow-sm', 'text-white');
        activeEl.classList.remove('text-gray-400');
    }

    updateGifEstimate();
}

/**
 * Set trim time from current video playback position
 */
function setGifTrimFromHead(type) {
    const video = document.getElementById('cinemaVideo');
    if (!video) return;

    const currentTime = video.currentTime;
    const hours = Math.floor(currentTime / 3600);
    const minutes = Math.floor((currentTime % 3600) / 60);
    const seconds = Math.floor(currentTime % 60);

    let timeStr;
    if (hours > 0) {
        timeStr = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } else {
        timeStr = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    if (type === 'start') {
        document.getElementById('gifTrimStart').value = timeStr;
    } else {
        document.getElementById('gifTrimEnd').value = timeStr;
    }

    updateGifEstimate();
}

/**
 * Clear GIF trim inputs
 */
function clearGifTrim() {
    document.getElementById('gifTrimStart').value = '';
    document.getElementById('gifTrimEnd').value = '';
    updateGifEstimate();
}

/**
 * Update GIF size estimation based on current settings
 */
function updateGifEstimate() {
    if (!window.currentCinemaVideo) return;

    const quality = parseInt(document.getElementById('gifQuality')?.value || 80);
    gifExportState.quality = quality;

    // Get trim times
    const startInput = document.getElementById('gifTrimStart')?.value || '';
    const endInput = document.getElementById('gifTrimEnd')?.value || '';

    let startTime = 0;
    let endTime = window.currentCinemaVideo.Duration_Sec || 10;

    // Parse start time (format: HH:MM:SS or MM:SS or SS)
    if (startInput) {
        const parts = startInput.split(':').map(p => parseInt(p) || 0);
        if (parts.length === 3) {
            startTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
        } else if (parts.length === 2) {
            startTime = parts[0] * 60 + parts[1];
        } else {
            startTime = parts[0] || 0;
        }
    }

    // Parse end time
    if (endInput) {
        const parts = endInput.split(':').map(p => parseInt(p) || 0);
        if (parts.length === 3) {
            endTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
        } else if (parts.length === 2) {
            endTime = parts[0] * 60 + parts[1];
        } else {
            endTime = parts[0] || endTime;
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
        "original": { w: window.currentCinemaVideo.Width || 1920, h: window.currentCinemaVideo.Height || 1080 }
    };

    const dims = presets[gifExportState.preset] || presets["720p"];

    // Estimate size (rough formula)
    const pixelsPerFrame = dims.w * dims.h;
    const frames = gifExportState.fps * duration;
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
 * Trigger GIF export
 */
async function triggerGifExport() {
    if (!window.currentCinemaPath) return;

    // Get trim times
    const startInput = document.getElementById('gifTrimStart')?.value || '';
    const endInput = document.getElementById('gifTrimEnd')?.value || '';

    let startTime = null;
    let endTime = null;

    if (startInput) {
        const parts = startInput.split(':').map(p => parseInt(p) || 0);
        if (parts.length === 3) {
            startTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
        } else if (parts.length === 2) {
            startTime = parts[0] * 60 + parts[1];
        } else {
            startTime = parts[0];
        }
    }

    if (endInput) {
        const parts = endInput.split(':').map(p => parseInt(p) || 0);
        if (parts.length === 3) {
            endTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
        } else if (parts.length === 2) {
            endTime = parts[0] * 60 + parts[1];
        } else {
            endTime = parts[0];
        }
    }

    closeGifExport();
    showCinemaToast('Starting GIF export...');

    try {
        const payload = {
            path: window.currentCinemaPath,
            preset: gifExportState.preset,
            fps: gifExportState.fps,
            quality: gifExportState.quality
        };

        if (startTime !== null) payload.start_time = startTime;
        if (endTime !== null) payload.end_time = endTime;

        const response = await fetch('/api/export/gif', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
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
        }, 5000);  // Increased to 5 seconds for FFmpeg processing

    } catch (error) {
        console.error('GIF export error:', error);
        showCinemaToast('GIF export failed');
    }
}

/**
 * Adjust cinema container height when panel is open
 */
function adjustCinemaForPanel(isPanelOpen) {
    const video = document.getElementById('cinemaVideo');
    const image = document.getElementById('cinemaImage');
    const cinemaModal = document.getElementById('cinemaModal');

    if (!video || !cinemaModal) return;

    if (isPanelOpen) {
        // Make video much smaller to ensure controls are always visible
        video.style.maxHeight = '50vh'; // Fixed smaller size
        video.style.transition = 'max-height 0.3s ease';

        if (image) {
            image.style.maxHeight = '50vh';
            image.style.transition = 'max-height 0.3s ease';
        }

        // Change alignment from center to start (top)
        cinemaModal.classList.remove('justify-center');
        cinemaModal.classList.add('justify-start');
        cinemaModal.style.paddingTop = '60px';
        cinemaModal.style.transition = 'padding-top 0.3s ease';
    } else {
        // Restore to full height
        video.style.maxHeight = '80vh';
        if (image) {
            image.style.maxHeight = '80vh';
        }

        // Restore center alignment
        cinemaModal.classList.remove('justify-start');
        cinemaModal.classList.add('justify-center');
        cinemaModal.style.paddingTop = '0';
    }
}

// Expose functions to global scope
window.cinemaExportGif = cinemaExportGif;
window.closeGifExport = closeGifExport;
window.setGifPreset = setGifPreset;
window.setGifFps = setGifFps;
window.setGifTrimFromHead = setGifTrimFromHead;
window.clearGifTrim = clearGifTrim;
window.updateGifEstimate = updateGifEstimate;
window.triggerGifExport = triggerGifExport;
window.adjustCinemaForPanel = adjustCinemaForPanel;
