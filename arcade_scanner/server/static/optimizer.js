// optimizer.js - Extracted from engine.js
// Handles the Cinema Optimizer panel: settings, UI state, trim controls,
// local optimization trigger, and Docker remote-encode queue.

// --- OPTIMIZER STATE ---
let currentOptAudio = 'standard';
let currentOptVideo = 'compress';
let currentOptCodec = 'hevc'; // 'hevc' or 'av1' (experimental)

// --- HELPERS ---

/**
 * Format seconds to HH:MM:SS for trim input fields
 * @param {number} seconds
 * @returns {string}
 */
function formatTimeForInput(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// --- PANEL OPEN / CLOSE ---

/**
 * Open the video optimization panel in cinema mode
 * Shows compression options, quality settings, and trim controls
 */
function cinemaOptimize() {
    const panel = document.getElementById('optimizePanel');
    const infoContent = document.getElementById('cinemaInfoContent');

    // Toggle off if already open
    if (panel.classList.contains('active')) {
        closeOptimize();
        return;
    }

    if (window.ENABLE_OPTIMIZER !== true || window.userSettings?.enable_optimizer === false) return;

    // Docker mode: queue for remote encoding instead of opening local optimizer
    if (window.IS_DOCKER) {
        if (currentCinemaPath) {
            queueForRemoteEncode(currentCinemaPath);
        }
        return;
    }

    // Reset state
    currentOptAudio = 'standard';
    updateOptAudioUI();
    clearTrim();

    // Reset Q Factor with per-video suggestion
    const qInput = document.getElementById('optQuality');
    const qSugg = document.getElementById('optQualitySuggestion');
    if (qInput) {
        qInput.value = 75;
        if (typeof currentCinemaPath !== 'undefined') {
            const video = window.ALL_VIDEOS?.find(v => v.FilePath === currentCinemaPath);
            if (video && video.Bitrate_Mbps) {
                let sugg = 75;
                let reason = 'Standard';
                if (video.Bitrate_Mbps > 20) { sugg = 65; reason = 'High Bitrate'; }
                else if (video.Bitrate_Mbps < 5) { sugg = 80; reason = 'Low Bitrate'; }
                if (qSugg) qSugg.innerText = `Suggested: ${sugg} (${reason})`;
            } else if (qSugg) {
                qSugg.innerText = '';
            }
        }
    }

    // Show panel
    panel.classList.add('active');
    const actions = document.getElementById('cinemaActions');
    if (actions) actions.style.display = 'none';

    if (typeof adjustCinemaForPanel === 'function') {
        adjustCinemaForPanel(true);
    }

    // Initialize timeline scrubber
    setTimeout(() => {
        const videoElement = document.getElementById('cinemaVideo');
        if (videoElement && window.TimelineScrubber) {
            if (window.optimizeTimeline && typeof window.optimizeTimeline.destroy === 'function') {
                window.optimizeTimeline.destroy();
            }

            window.optimizeTimeline = new TimelineScrubber(videoElement, {
                containerSelector: '#optimizeTimeline',
                onChange: (times) => {
                    const startInput = document.getElementById('optTrimStart');
                    const endInput   = document.getElementById('optTrimEnd');
                    if (startInput) startInput.value = formatTimeForInput(times.startTime);
                    if (endInput)   endInput.value   = formatTimeForInput(times.endTime);
                }
            });

            window.optimizeTimeline.init();

            const startInput = document.getElementById('optTrimStart');
            const endInput   = document.getElementById('optTrimEnd');

            const updateTimelineFromInputs = () => {
                if (!window.optimizeTimeline) return;
                const parse = (val) => {
                    if (!val) return 0;
                    const parts = val.split(':');
                    if (parts.length === 2) return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
                    if (parts.length === 3) return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2]);
                    return parseFloat(val);
                };
                const start = parse(startInput?.value);
                const end   = parse(endInput?.value);
                if (!isNaN(start) && !isNaN(end)) {
                    window.optimizeTimeline.setTimes(start, end);
                }
            };

            if (startInput) startInput.onchange = updateTimelineFromInputs;
            if (endInput)   endInput.onchange   = updateTimelineFromInputs;
        }
    }, 100);
}

/**
 * Close the optimization panel and restore cinema layout
 */
function closeOptimize() {
    document.getElementById('optimizePanel').classList.remove('active');
    const actions = document.getElementById('cinemaActions');
    if (actions) actions.style.display = 'flex';
    if (typeof adjustCinemaForPanel === 'function') {
        adjustCinemaForPanel(false);
    }
}

// --- AUDIO / VIDEO / CODEC MODE ---

/** @param {string} mode - 'standard' | 'enhanced' */
function setOptAudio(mode) {
    currentOptAudio = mode;
    updateOptAudioUI();
}

/** @param {string} codec - 'hevc' | 'av1' */
function setOptCodec(codec) {
    currentOptCodec = codec;
    updateOptCodecUI();
}

/** @param {string} mode - 'compress' | 'copy' */
function setOptVideo(mode) {
    currentOptVideo = mode;
    updateOptVideoUI();
}

function updateOptCodecUI() {
    document.querySelectorAll('[data-codec-btn]').forEach(btn => {
        const isActive = btn.dataset.codecBtn === currentOptCodec;
        btn.classList.toggle('text-white',  isActive);
        btn.classList.toggle('bg-white/10', isActive);
        btn.classList.toggle('shadow-sm',   isActive);
        btn.classList.toggle('text-gray-400',   !isActive);
        btn.classList.toggle('hover:text-white', !isActive);
    });
    const desc = document.getElementById('optCodecDesc');
    if (desc) {
        desc.textContent = currentOptCodec === 'av1'
            ? '🧪 Experimental – requires M3/M4 or RTX 40xx'
            : 'Efficient HEVC/H.265 encoding';
    }
}

function updateOptVideoUI() {
    const compressBtn = document.getElementById('optVideoCompress');
    const copyBtn     = document.getElementById('optVideoCopy');
    if (!compressBtn || !copyBtn) return;

    const active   = ['text-white', 'bg-white/10', 'shadow-sm'];
    const inactive = ['text-gray-400', 'hover:text-white'];

    if (currentOptVideo === 'compress') {
        compressBtn.classList.add(...active);
        compressBtn.classList.remove(...inactive);
        copyBtn.classList.remove(...active);
        copyBtn.classList.add(...inactive);
        document.getElementById('optVideoDesc').innerText = 'Optimize to efficient HEVC/H.265';
        const codecRow = document.getElementById('optCodecRow');
        if (codecRow) codecRow.style.display = '';
    } else {
        compressBtn.classList.remove(...active);
        compressBtn.classList.add(...inactive);
        copyBtn.classList.add(...active);
        copyBtn.classList.remove(...inactive);
        document.getElementById('optVideoDesc').innerText = 'Copy video stream (Passthrough)';
        const codecRow = document.getElementById('optCodecRow');
        if (codecRow) codecRow.style.display = 'none';
    }
}

function updateOptAudioUI() {
    const enhancedBtn = document.getElementById('optAudioEnhanced');
    const standardBtn = document.getElementById('optAudioStandard');

    const active   = ['text-white', 'bg-white/10', 'shadow-sm'];
    const inactive = ['text-gray-400', 'hover:text-white'];

    if (currentOptAudio === 'enhanced') {
        enhancedBtn.classList.add(...active);
        enhancedBtn.classList.remove(...inactive);
        standardBtn.classList.remove(...active);
        standardBtn.classList.add(...inactive);
        document.getElementById('optAudioDesc').innerText = 'Smart normalization & noise reduction';
    } else {
        enhancedBtn.classList.remove(...active);
        enhancedBtn.classList.add(...inactive);
        standardBtn.classList.add(...active);
        standardBtn.classList.remove(...inactive);
        document.getElementById('optAudioDesc').innerText = 'Standard encoding (no filters)';
    }
}

// --- TRIM CONTROLS ---

/** Set trim start or end from current video playback position */
function setTrimFromHead(type) {
    const video = document.getElementById('cinemaVideo');
    const time  = new Date(video.currentTime * 1000).toISOString().substr(11, 8);
    if (type === 'start') {
        document.getElementById('optTrimStart').value = time;
    } else {
        document.getElementById('optTrimEnd').value = time;
    }
}

/** Clear trim start and end inputs */
function clearTrim() {
    document.getElementById('optTrimStart').value = '';
    document.getElementById('optTrimEnd').value   = '';
}

// --- TRIGGER OPTIMIZATION ---

/**
 * Start the optimization process for the current cinema video
 */
function triggerOptimization() {
    if (!currentCinemaPath) return;

    const ss   = document.getElementById('optTrimStart').value;
    const to   = document.getElementById('optTrimEnd').value;
    const qVal = document.getElementById('optQuality')?.value;

    if (window.IS_DOCKER) {
        queueForRemoteEncode(currentCinemaPath);
        closeOptimize();
        return;
    }

    const params = new URLSearchParams();
    params.set('path',  currentCinemaPath);
    params.set('audio', currentOptAudio);
    params.set('video', currentOptVideo);
    if (ss)   params.set('ss', ss);
    if (to)   params.set('to', to);
    if (qVal) params.set('q',  qVal);

    fetch(`/compress?${params.toString()}`)
        .then(() => {
            closeOptimize();
            showToast('Optimization started! 🚀', 'success');
        })
        .catch(err => showToast(`Optimization failed: ${err}`, 'error'));
}

// --- REMOTE ENCODING QUEUE ---

/**
 * Queue a single file for remote encoding on the Mac worker.
 * Used in Docker mode where local Terminal optimization isn't available.
 */
function queueForRemoteEncode(filePath) {
    fetch('/api/queue/add', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ file_path: filePath, codec: currentOptCodec })
    })
        .then(r => r.json())
        .then(data => {
            const name       = filePath.split(/[/\\]/).pop();
            const codecLabel = currentOptCodec === 'av1' ? 'AV1' : 'HEVC';
            if (data.success) {
                showToast(`Queued [${codecLabel}]: ${name}`, 'success');
            } else {
                showToast(`${data.error || 'Already queued'}: ${name}`, 'warning');
            }
        })
        .catch(err => {
            console.error('Queue error:', err);
            showToast('Failed to queue file', 'error');
        });
}

/**
 * Queue multiple files for remote encoding in Docker mode.
 */
async function queueBatchForRemoteEncode(paths) {
    let queued = 0;
    let skipped = 0;
    for (const p of paths) {
        try {
            const r    = await fetch('/api/queue/add', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ file_path: p, codec: currentOptCodec })
            });
            const data = await r.json();
            if (data.success) queued++; else skipped++;
        } catch (e) {
            console.error('Batch queue error:', e);
            skipped++;
        }
    }
    const codecLabel = currentOptCodec === 'av1' ? '🧪 AV1' : 'HEVC';
    showToast(`☁️ Queued ${queued} file(s) [${codecLabel}]${skipped > 0 ? ` (${skipped} skipped)` : ''}`, 'success');
}

// --- EXPORTS ---
window.cinemaOptimize         = cinemaOptimize;
window.closeOptimize          = closeOptimize;
window.setOptAudio            = setOptAudio;
window.setOptCodec            = setOptCodec;
window.setOptVideo            = setOptVideo;
window.updateOptCodecUI       = updateOptCodecUI;
window.updateOptVideoUI       = updateOptVideoUI;
window.updateOptAudioUI       = updateOptAudioUI;
window.setTrimFromHead        = setTrimFromHead;
window.clearTrim              = clearTrim;
window.triggerOptimization    = triggerOptimization;
window.queueForRemoteEncode   = queueForRemoteEncode;
window.queueBatchForRemoteEncode = queueBatchForRemoteEncode;
