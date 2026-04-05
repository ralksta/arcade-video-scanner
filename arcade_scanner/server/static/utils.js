// utils.js - Extracted from engine.js

// --- THEME LOGIC ---

/**
 * Toggle between light and dark theme
 * Persists preference to localStorage and updates theme icon
 */
function toggleTheme() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');

    const icon = document.getElementById('themeIcon');
    if (icon) icon.textContent = isDark ? 'light_mode' : 'dark_mode';
}

// --- SAFE MODE LOGIC ---

/**
 * Check if a video/image should be hidden in Safe Mode
 * Checks against user-configured sensitive tags and directory paths
 *
 * @param {Object} video - Video object to check
 * @returns {boolean} True if the video is considered sensitive
 */
function isSensitive(video) {
    if (!video) return false;

    // 1. Check Tags
    const sensitiveTags = window.userSettings?.sensitive_tags || ['nsfw', 'adult', '18+'];
    if (video.tags && video.tags.some(t => sensitiveTags.includes(t.toLowerCase()))) {
        return true;
    }

    // 2. Check Paths
    const sensitiveDirs = window.userSettings?.sensitive_dirs || [];
    // Normalize paths for comparison (forward slashes)
    const vPath = video.FilePath.replace(/\\/g, '/').toLowerCase();

    for (const dir of sensitiveDirs) {
        if (!dir) continue;
        const cleanDir = dir.replace(/\\/g, '/').toLowerCase();
        if (vPath.startsWith(cleanDir)) {
            return true;
        }
    }

    return false;
}

// Init Theme
(function initTheme() {
    const saved = localStorage.getItem('theme');
    const isDark = saved ? saved === 'dark' : true; // Default to dark

    if (isDark) {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }

    // Wait for DOM in case script runs early (though it's at end of body)
    setTimeout(() => {
        const icon = document.getElementById('themeIcon');
        if (icon) icon.textContent = isDark ? 'light_mode' : 'dark_mode';
    }, 0);
})();



// --- GLOBAL UTILS ---
// Note: all functions in the static JS modules are global by default.
// Explicit window.* assignments are handled in the respective module files
// after all scripts are loaded. No premature references here.


// =============================================================================
// TOAST QUEUE (Stacked notifications — max 4 simultaneous)
// =============================================================================

const _toastQueue = [];
const _TOAST_MAX = 4;

/**
 * Show a queued, stacked toast notification
 * @param {string} message  - Message to display
 * @param {string} [type]   - 'info' | 'success' | 'error' | 'warning'
 * @param {number} [duration] - ms before auto-dismiss (default 2800)
 */
function showToast(message, type = 'info', duration = 2800) {
    const iconMap = { success: 'check_circle', error: 'error', warning: 'warning_amber', info: 'info' };

    // Evict oldest if at max capacity
    if (_toastQueue.length >= _TOAST_MAX) {
        const oldest = _toastQueue.shift();
        oldest?.remove();
        _repositionToasts();
    }

    const toast = document.createElement('div');
    toast.className = `settings-toast toast-${type}`;
    toast.innerHTML = `
        <span class="material-icons" style="font-size:18px;flex-shrink:0">${iconMap[type] || 'info'}</span>
        <span style="flex:1;min-width:0;word-break:break-word">${message}</span>
        <button onclick="this.closest('.settings-toast')._dismiss()" style="background:none;border:none;color:inherit;cursor:pointer;padding:0;margin-left:4px;opacity:.6;display:flex;align-items:center">
            <span class="material-icons" style="font-size:16px">close</span>
        </button>
        <div class="toast-progress" style="position:absolute;bottom:0;left:0;height:2px;background:currentColor;opacity:.4;width:100%;transform-origin:left;animation:toast-shrink ${duration}ms linear forwards"></div>
    `;

    // Dismiss helper
    toast._dismiss = () => {
        toast.classList.remove('show');
        const idx = _toastQueue.indexOf(toast);
        if (idx !== -1) _toastQueue.splice(idx, 1);
        setTimeout(() => {
            toast.remove();
            _repositionToasts();
        }, 280);
    };

    document.body.appendChild(toast);
    _toastQueue.push(toast);
    _repositionToasts();

    requestAnimationFrame(() => {
        requestAnimationFrame(() => toast.classList.add('show'));
    });

    // Auto-dismiss
    setTimeout(() => toast._dismiss?.(), duration);
}

function _repositionToasts() {
    const base = 20; // px from bottom
    const gap  = 8;   // gap between toasts
    let offset = base;
    // Walk queue from oldest (bottom) to newest (top)
    [..._toastQueue].reverse().forEach(t => {
        t.style.bottom = `${offset}px`;
        offset += (t.offsetHeight || 52) + gap;
    });
}

window.showToast = showToast;




// =============================================================================
// FILTER PANEL & TAG SYSTEM
// =============================================================================

// Filter state (in addition to existing currentFilter, currentCodec)
// activeTags, filterUntaggedOnly, minSizeMB, maxSizeMB, dateFilter, availableTags are declared at the top of the file.
