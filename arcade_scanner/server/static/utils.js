// utils.js - Extracted from engine.js

// --- THEME LOGIC ---

/**
 * Toggle between light and dark theme
 * Persists preference to localStorage and updates theme icon
 */
function toggleTheme() {
    const isDark = document.documentElement.classList.toggle('dark');
    window.safeStorage.set('theme', isDark ? 'dark' : 'light');

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
    //
    // Beide Seiten kleinschreiben. Vorher wurde nur der Tag des Videos
    // normalisiert, die eingestellte Liste nicht — wer "NSFW" in die
    // Einstellungen tippte (die naheliegende Schreibweise), bekam den Vergleich
    // 'NSFW'.includes('nsfw') und damit nie einen Treffer. Die Voreinstellungen
    // sind klein geschrieben, deshalb fiel es nur eigenen Eingaben auf.
    const configuredTags = window.userSettings?.sensitive_tags || ['nsfw', 'adult', '18+'];
    const sensitiveTags = configuredTags.map(t => String(t).trim().toLowerCase());
    if (video.tags && video.tags.some(t => sensitiveTags.includes(String(t).toLowerCase()))) {
        return true;
    }

    // 2. Check Paths
    const sensitiveDirs = window.userSettings?.sensitive_dirs || [];
    // Ohne Pfad lässt sich nur der Tag-Teil beurteilen. Vorher warf die
    // nächste Zeile hier — und zwar mitten in filterAndSort(), womit der
    // gesamte Filter ausfiel und der abgesicherte Modus alles zeigte.
    if (!video.FilePath) return false;
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
    const saved = window.safeStorage.get('theme');
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
        <span class="material-icons" style="font-size:18px;flex-shrink:0" aria-hidden="true">${iconMap[type] || 'info'}</span>
        <span style="flex:1;min-width:0;word-break:break-word">${message}</span>
        <button onclick="this.closest('.settings-toast')._dismiss()" aria-label="Meldung schließen" style="background:none;border:none;color:inherit;cursor:pointer;padding:0;margin-left:4px;opacity:.6;display:flex;align-items:center">
            <span class="material-icons" style="font-size:16px" aria-hidden="true">close</span>
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

/**
 * Escape a string for safe interpolation into HTML markup or attributes.
 * File names may contain &, <, >, " or ' — unescaped they break markup,
 * data-path attributes and onclick handlers.
 * @param {*} value - Value to escape
 * @returns {string} HTML-safe string
 */
function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
window.escapeHtml = escapeHtml;

/**
 * URL-encode a file path, or return null if it cannot be encoded.
 *
 * Dateinamen mit ungültigen UTF-8-Bytes (cp1252-Reste auf dem NAS) liest Python
 * per surrogateescape als einzelne Surrogate U+DC80–U+DCFF ein und reicht sie so
 * ans Frontend. encodeURIComponent wirft darauf `URIError: URI malformed` — in
 * einer Render-Schleife reißt das die komplette Ansicht mit.
 *
 * Bewusst kein Reparaturversuch: die Gegenstelle dekodiert mit `unquote()` ohne
 * errors='surrogateescape' und käme an den Originalpfad ohnehin nicht heran. Der
 * Aufrufer soll die betroffene Aktion deaktivieren, statt eine URL zu bauen, die
 * serverseitig ins Leere läuft.
 *
 * @param {string} path - File path
 * @returns {string|null} Encoded path, or null if it contains lone surrogates
 */
function safeEncodePath(path) {
    try {
        return encodeURIComponent(path);
    } catch (e) {
        if (e instanceof URIError) return null;
        throw e;
    }
}
window.safeEncodePath = safeEncodePath;

/**
 * Wann ein Eintrag in der Bibliothek aufgetaucht ist, in Sekunden.
 *
 * `imported_at` ist der Zeitpunkt des ersten Scans, `mtime` der der letzten
 * Änderung der Datei. Für „neu in meiner Bibliothek" ist das erste die
 * Antwort; das zweite ist der Ersatz für Einträge, die noch aus der Zeit vor
 * dem Feld stammen.
 *
 * Diese Regel stand an vier Stellen ausgeschrieben — im Datumsfilter, in den
 * Sammlungen, in deren Python-Gegenstück und (unvollständig) in der
 * Sortierung. Genau dort war sie dann anders: „Sortieren: Datum" rechnete
 * allein mit `mtime`. Das ist nicht dieselbe Frage. Wer eine alte Aufnahme
 * heute in die Bibliothek legt, steht im Filter „letzte 7 Tage" — und in der
 * Sortierung ganz unten. Umgekehrt schiebt jedes Optimieren einen alten Film
 * nach oben, weil die Datei neu geschrieben wurde.
 *
 * @param {Object} video - Eintrag aus ALL_VIDEOS
 * @returns {number} Unix-Zeit in Sekunden, 0 wenn nichts bekannt ist
 */
function entryDate(video) {
    if (!video) return 0;
    const imported = Number(video.imported_at) || 0;
    if (imported > 0) return imported;
    return Number(video.mtime) || 0;
}
window.entryDate = entryDate;




// =============================================================================
// FILTER PANEL & TAG SYSTEM
// =============================================================================

// Filter state (in addition to existing currentFilter, currentCodec)
// activeTags, filterUntaggedOnly, minSizeMB, maxSizeMB, dateFilter, availableTags are declared at the top of the file.
