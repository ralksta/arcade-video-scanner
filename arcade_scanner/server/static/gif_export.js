// GIF Export Panel — v2
// Improvements: Job polling (no blind timeout), Loop/Speed controls, Share Sheet

// GIF Export State
let gifExportState = {
    preset: '720p',
    fps: 15,
    quality: 80,
    loop: 0,       // 0 = infinite, 1 = once, 3 = three times
    speed: 1.0     // 0.5 = slow-mo, 1.0 = normal, 2.0 = fast
};

// Polling config
const GIF_POLL_INTERVAL_MS = 1500;
const GIF_POLL_MAX_ATTEMPTS = 80; // 80 × 1.5s = 2 minutes max

/**
 * Open GIF export panel for current cinema video
 */
function cinemaExportGif() {
    if (!window.currentCinemaPath || !window.currentCinemaVideo) return;

    if (window.currentCinemaVideo.media_type === 'image') {
        showCinemaToast('GIF export only available for videos');
        return;
    }

    // Reset state
    gifExportState = { preset: '720p', fps: 15, quality: 80, loop: 0, speed: 1.0 };

    document.getElementById('gifTrimStart').value = '';
    document.getElementById('gifTrimEnd').value = '';
    document.getElementById('gifQuality').value = '80';

    setGifPreset('720p');
    setGifFps(15);
    setGifLoop(0);
    setGifSpeed(1.0);

    const panel = document.getElementById('gifExportPanel');
    panel.classList.add('active');
    panel.style.transform = 'translateY(0)';

    adjustCinemaForPanel(true);
    updateGifEstimate();

    // Initialize timeline scrubber
    setTimeout(() => {
        const videoElement = document.getElementById('cinemaVideo');
        if (videoElement && window.TimelineScrubber) {
            if (window.gifTimeline && typeof window.gifTimeline.destroy === 'function') {
                window.gifTimeline.destroy();
            }
            window.gifTimeline = new TimelineScrubber(videoElement, {
                containerSelector: '#gifTimeline',
                onChange: (times) => {
                    const s = document.getElementById('gifTrimStart');
                    const e = document.getElementById('gifTrimEnd');
                    if (s) s.value = formatTimeForInput(times.startTime);
                    if (e) e.value = formatTimeForInput(times.endTime);
                    updateGifEstimate();
                }
            });
            window.gifTimeline.init();

            const startInput = document.getElementById('gifTrimStart');
            const endInput   = document.getElementById('gifTrimEnd');
            const syncInputsToTimeline = () => {
                if (!window.gifTimeline) return;
                const parse = (val) => {
                    if (!val) return 0;
                    const parts = val.split(':');
                    if (parts.length === 2) return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
                    return parseFloat(val);
                };
                const s = parse(startInput?.value);
                const e = parse(endInput?.value);
                if (!isNaN(s) && !isNaN(e)) window.gifTimeline.setTimes(s, e);
            };
            if (startInput) startInput.onchange = syncInputsToTimeline;
            if (endInput)   endInput.onchange   = syncInputsToTimeline;
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
    adjustCinemaForPanel(false);
}

// ─────────────────────────────────────────────────────────────────────────────
// PRESET / FPS / QUALITY SELECTORS
// ─────────────────────────────────────────────────────────────────────────────

function setGifPreset(preset) {
    gifExportState.preset = preset;
    ['360p', '480p', '720p', '1080p', 'Original'].forEach(p => {
        const el = document.getElementById(`gifPreset${p}`);
        if (el) {
            el.classList.remove('bg-white/10', 'shadow-sm', 'text-white');
            el.classList.add('text-gray-400');
        }
    });
    const activeEl = document.getElementById(`gifPreset${preset}`);
    if (activeEl) {
        activeEl.classList.add('bg-white/10', 'shadow-sm', 'text-white');
        activeEl.classList.remove('text-gray-400');
    }
    const descriptions = {
        '360p':     '640×360 — Small',
        '480p':     '854×480 — Medium',
        '720p':     '1280×720 — High Quality',
        '1080p':    '1920×1080 — Very High',
        'original': `${window.currentCinemaVideo?.Width || 1920}×${window.currentCinemaVideo?.Height || 1080} — Original`
    };
    const descEl = document.getElementById('gifPresetDesc');
    if (descEl) descEl.textContent = descriptions[preset] || descriptions['720p'];
    updateGifEstimate();
}

function setGifFps(fps) {
    gifExportState.fps = fps;
    [10, 15, 20, 25, 30].forEach(f => {
        const el = document.getElementById(`gifFps${f}`);
        if (el) {
            el.classList.remove('bg-white/10', 'shadow-sm', 'text-white');
            el.classList.add('text-gray-400');
        }
    });
    const activeEl = document.getElementById(`gifFps${fps}`);
    if (activeEl) {
        activeEl.classList.add('bg-white/10', 'shadow-sm', 'text-white');
        activeEl.classList.remove('text-gray-400');
    }
    updateGifEstimate();
}

/**
 * Set loop count: 0 = infinite, 1 = once, 3 = three times
 */
function setGifLoop(loopVal) {
    gifExportState.loop = loopVal;
    const loopOptions = [0, 1, 3];
    loopOptions.forEach(v => {
        const el = document.getElementById(`gifLoop${v}`);
        if (el) {
            el.classList.remove('bg-white/10', 'shadow-sm', 'text-white');
            el.classList.add('text-gray-400');
        }
    });
    const activeEl = document.getElementById(`gifLoop${loopVal}`);
    if (activeEl) {
        activeEl.classList.add('bg-white/10', 'shadow-sm', 'text-white');
        activeEl.classList.remove('text-gray-400');
    }
}

/**
 * Set playback speed multiplier for GIF
 */
function setGifSpeed(speed) {
    gifExportState.speed = speed;
    const speedOptions = [0.5, 1.0, 2.0];
    speedOptions.forEach(v => {
        const el = document.getElementById(`gifSpeed${v.toString().replace('.', '_')}`);
        if (el) {
            el.classList.remove('bg-white/10', 'shadow-sm', 'text-white');
            el.classList.add('text-gray-400');
        }
    });
    const key = speed.toString().replace('.', '_');
    const activeEl = document.getElementById(`gifSpeed${key}`);
    if (activeEl) {
        activeEl.classList.add('bg-white/10', 'shadow-sm', 'text-white');
        activeEl.classList.remove('text-gray-400');
    }
    updateGifEstimate();
}

/**
 * Set trim time from current playback position
 */
function setGifTrimFromHead(type) {
    const video = document.getElementById('cinemaVideo');
    if (!video) return;
    const ct = video.currentTime;
    const h  = Math.floor(ct / 3600);
    const m  = Math.floor((ct % 3600) / 60);
    const s  = Math.floor(ct % 60);
    const timeStr = h > 0
        ? `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
        : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    if (type === 'start') document.getElementById('gifTrimStart').value = timeStr;
    else                  document.getElementById('gifTrimEnd').value   = timeStr;
    updateGifEstimate();
}

function clearGifTrim() {
    document.getElementById('gifTrimStart').value = '';
    document.getElementById('gifTrimEnd').value   = '';
    updateGifEstimate();
}

// ─────────────────────────────────────────────────────────────────────────────
// SIZE ESTIMATION
// ─────────────────────────────────────────────────────────────────────────────

function updateGifEstimate() {
    if (!window.currentCinemaVideo) return;
    const quality = parseInt(document.getElementById('gifQuality')?.value || 80);
    gifExportState.quality = quality;

    const parseTrim = (val) => {
        if (!val) return null;
        const parts = val.split(':').map(p => parseInt(p) || 0);
        if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
        if (parts.length === 2) return parts[0] * 60 + parts[1];
        return parts[0];
    };

    const startTime = parseTrim(document.getElementById('gifTrimStart')?.value) ?? 0;
    const rawEnd    = parseTrim(document.getElementById('gifTrimEnd')?.value);
    const endTime   = rawEnd ?? (window.currentCinemaVideo.Duration_Sec || 10);

    // Clamp effective duration by speed
    const rawDuration = Math.max(0.1, endTime - startTime);
    const effectiveDuration = rawDuration / (gifExportState.speed || 1.0);

    const durationEl = document.getElementById('gifDuration');
    if (durationEl) durationEl.textContent = effectiveDuration.toFixed(1) + 's';

    const presets = {
        '360p':     { w: 640,  h: 360  },
        '480p':     { w: 854,  h: 480  },
        '720p':     { w: 1280, h: 720  },
        '1080p':    { w: 1920, h: 1080 },
        'original': { w: window.currentCinemaVideo.Width || 1920, h: window.currentCinemaVideo.Height || 1080 }
    };
    const dims = presets[gifExportState.preset] || presets['720p'];
    const sizeMB = (dims.w * dims.h * gifExportState.fps * effectiveDuration * (quality / 100) * 0.3) / (1024 * 1024);

    const sizeEl = document.getElementById('gifEstimatedSize');
    if (sizeEl) sizeEl.textContent = `~${sizeMB.toFixed(1)} MB`;
}

// ─────────────────────────────────────────────────────────────────────────────
// EXPORT + POLLING
// ─────────────────────────────────────────────────────────────────────────────

async function triggerGifExport() {
    if (!window.currentCinemaPath) return;

    const parseTrim = (val) => {
        if (!val) return null;
        const parts = val.split(':').map(p => parseInt(p) || 0);
        if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
        if (parts.length === 2) return parts[0] * 60 + parts[1];
        return parts[0];
    };

    const startTime = parseTrim(document.getElementById('gifTrimStart')?.value);
    const endTime   = parseTrim(document.getElementById('gifTrimEnd')?.value);

    closeGifExport();
    showCinemaToast('Starting GIF export...');

    try {
        const payload = {
            path:    window.currentCinemaPath,
            preset:  gifExportState.preset,
            fps:     gifExportState.fps,
            quality: gifExportState.quality,
            loop:    gifExportState.loop,
            speed:   gifExportState.speed,
        };
        if (startTime !== null) payload.start_time = startTime;
        if (endTime   !== null) payload.end_time   = endTime;

        const response = await fetch('/api/export/gif', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Export request failed');

        const result = await response.json();
        showCinemaToast(`GIF rendering... (~${result.estimated_size_mb} MB)`);

        // Start polling instead of blind timeout
        pollGifJob(result.job_id);

    } catch (error) {
        console.error('GIF export error:', error);
        showCinemaToast('GIF export failed');
    }
}

/**
 * Poll /api/export/gif/status/<job_id> until done or error.
 * Max GIF_POLL_MAX_ATTEMPTS attempts with GIF_POLL_INTERVAL_MS delay.
 */
async function pollGifJob(jobId) {
    let attempts = 0;

    const progressToasts = ['Still rendering...', 'Almost there...', 'Finalizing GIF...'];

    const poll = async () => {
        attempts++;

        try {
            const res = await fetch(`/api/export/gif/status/${jobId}`);

            if (!res.ok) {
                showCinemaToast('GIF export failed (server error)');
                return;
            }

            const job = await res.json();

            if (job.status === 'done') {
                showCinemaToast(`GIF ready! ${job.size_mb} MB — Downloading...`);
                _downloadAndShareGif(job.download_url, job.filename);
                return;
            }

            if (job.status === 'error') {
                showCinemaToast(`GIF failed: ${job.error || 'Unknown error'}`);
                return;
            }

            // Still processing
            if (attempts >= GIF_POLL_MAX_ATTEMPTS) {
                showCinemaToast('GIF export timed out after 2 minutes');
                return;
            }

            // Show rotating progress hints every 10 polls
            if (attempts % 10 === 0) {
                const hint = progressToasts[Math.floor(attempts / 10) % progressToasts.length];
                showCinemaToast(hint);
            }

            setTimeout(poll, GIF_POLL_INTERVAL_MS);

        } catch (err) {
            console.error('Polling error:', err);
            showCinemaToast('GIF export failed (network error)');
        }
    };

    setTimeout(poll, GIF_POLL_INTERVAL_MS);
}

/**
 * Trigger browser download and optionally open native Share Sheet
 */
async function _downloadAndShareGif(downloadUrl, filename) {
    // Trigger download
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename || 'export.gif';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    // Offer native Share (only if supported and on HTTPS/localhost)
    if (navigator.share && navigator.canShare) {
        try {
            // Fetch the file as a Blob to share natively
            const response = await fetch(downloadUrl);
            const blob     = await response.blob();
            const file     = new File([blob], filename || 'export.gif', { type: 'image/gif' });

            if (navigator.canShare({ files: [file] })) {
                await navigator.share({
                    files:  [file],
                    title:  'Arcade GIF Export',
                    text:   `Exported from Arcade Scanner`,
                });
            }
        } catch (shareErr) {
            // Share was cancelled or not available — silent fail
            console.log('Share cancelled or unsupported:', shareErr.message);
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// LAYOUT HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function adjustCinemaForPanel(isPanelOpen) {
    const video       = document.getElementById('cinemaVideo');
    const image       = document.getElementById('cinemaImage');
    const cinemaModal = document.getElementById('cinemaModal');
    if (!video || !cinemaModal) return;

    if (isPanelOpen) {
        video.style.maxHeight   = '45vh';
        video.style.marginTop   = '8vh';
        video.style.marginBottom = 'auto';
        if (image) {
            image.style.maxHeight   = '45vh';
            image.style.marginTop   = '8vh';
            image.style.marginBottom = 'auto';
        }
    } else {
        video.style.maxHeight    = '80vh';
        video.style.marginTop    = '';
        video.style.marginBottom = '';
        if (image) {
            image.style.maxHeight    = '80vh';
            image.style.marginTop    = '';
            image.style.marginBottom = '';
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// EXPORTS
// ─────────────────────────────────────────────────────────────────────────────

window.cinemaExportGif    = cinemaExportGif;
window.closeGifExport     = closeGifExport;
window.setGifPreset       = setGifPreset;
window.setGifFps          = setGifFps;
window.setGifLoop         = setGifLoop;
window.setGifSpeed        = setGifSpeed;
window.setGifTrimFromHead = setGifTrimFromHead;
window.clearGifTrim       = clearGifTrim;
window.updateGifEstimate  = updateGifEstimate;
window.triggerGifExport   = triggerGifExport;
window.adjustCinemaForPanel = adjustCinemaForPanel;
