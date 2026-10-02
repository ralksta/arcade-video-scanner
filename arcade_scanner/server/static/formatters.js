/**
 * Formatters - Utility functions for formatting display values
 * Extracted from engine.js for reusability and maintainability
 */

/**
 * Format file size from megabytes to human-readable string
 * @param {number} mb - Size in megabytes
 * @param {number} [decimals=2] - Number of decimal places
 * @returns {string} Formatted size string (e.g., "1.5 GB", "500 MB", "2.3 TB")
 */
function formatSize(mb, decimals = 2) {
    if (mb == null || isNaN(mb)) return '0 MB';
    if (mb >= 1024 * 1024) return (mb / (1024 * 1024)).toFixed(decimals) + ' TB';
    if (mb >= 1024) return (mb / 1024).toFixed(decimals) + ' GB';
    return mb.toFixed(decimals === 2 ? 0 : decimals) + ' MB';
}

/**
 * Format file size with compact output (1 decimal place)
 * @param {number} mb - Size in megabytes
 * @returns {string} Formatted size string (e.g., "1.5 GB")
 */
function formatSizeCompact(mb) {
    if (mb == null || isNaN(mb)) return '0 MB';
    if (mb >= 1024) return (mb / 1024).toFixed(1) + ' GB';
    return mb.toFixed(1) + ' MB';
}

/**
 * Format duration from seconds to HH:MM:SS or MM:SS
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration string (e.g., "1:23:45" or "5:30")
 */
function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return '';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
}

/**
 * Format duration with full units (e.g., "1h 23m 45s")
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration string with units
 */
function formatDurationLong(seconds) {
    if (!seconds || isNaN(seconds)) return '';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${h}h ${m}m ${s}s`;
    }
    return `${m}m ${s}s`;
}

/**
 * Format bitrate from Mbps to human-readable string
 * @param {number} mbps - Bitrate in megabits per second
 * @param {number} [decimals=1] - Number of decimal places
 * @returns {string} Formatted bitrate string (e.g., "25.5 Mbps")
 */
function formatBitrate(mbps, decimals = 1) {
    if (mbps == null || isNaN(mbps)) return '0 Mbps';
    return mbps.toFixed(decimals) + ' Mbps';
}

/**
 * Format bitrate in kbps
 * @param {number} mbps - Bitrate in megabits per second
 * @returns {string} Formatted bitrate string in kbps (e.g., "25,500 kbps")
 */
function formatBitrateKbps(mbps) {
    if (mbps == null || isNaN(mbps)) return '0 kbps';
    return ((mbps * 1000) | 0).toLocaleString() + ' kbps';
}

/**
 * Format a timestamp to relative time (e.g., "2 hours ago")
 * @param {number} timestamp - Unix timestamp in seconds
 * @returns {string} Relative time string
 */
function formatRelativeTime(timestamp) {
    if (!timestamp) return '';
    const now = Date.now() / 1000;
    const diff = now - timestamp;

    // Auch für negative Abstände: Ein Zeitstempel aus der Zukunft entsteht
    // durch eine falsch gestellte Uhr auf einem entfernten Arbeiter, und
    // „-3 minutes ago" wäre die schlechtere Auskunft.
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} days ago`;
    if (diff < 2592000) return `${Math.floor(diff / 604800)} weeks ago`;
    return `${Math.floor(diff / 2592000)} months ago`;
}

/**
 * Extract filename from full path
 * @param {string} filePath - Full file path
 * @returns {string} Filename without path
 */
function getFileName(filePath) {
    if (!filePath) return '';
    return filePath.split(/[\\/]/).pop() || '';
}

/**
 * Extract directory path from full path
 * @param {string} filePath - Full file path
 * @returns {string} Directory path without filename
 */
function getDirPath(filePath) {
    if (!filePath) return '';
    const lastIdx = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'));
    return lastIdx >= 0 ? filePath.substring(0, lastIdx) : '';
}

/**
 * Truncate text with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text with ellipsis if needed
 */
function truncateText(text, maxLength) {
    if (!text || text.length <= maxLength) return text || '';
    return text.substring(0, maxLength - 3) + '...';
}

// --- ANZEIGETITEL ---
// Was auf Karten, Startseite und im Player steht. Der Dateiname bleibt im
// Tooltip und in den Werkstatt-Ansichten sichtbar.
//
// Dieselbe Logik steht in tv_client/src/displayName.js — beide werden in
// tests/test_media_titles.py gegen dieselben Beispiele geprüft.

const TITLE_MONTHS = ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.',
    'Sept.', 'Okt.', 'Nov.', 'Dez.'];

// Was der Optimierer anhängt: film_opt.mp4, film__h265__h265_0.mp4, …
const TITLE_ENCODE_SUFFIX = /(?:[ _.-]+(?:opt|optimized|h265|hevc|x265|av1|trim|trimmed)(?:[_-]\d+)?)+$/i;

// Kamera- und Handy-Namen: VID_20251025_121813_115, PXL_20240512_131415123,
// IMG_20240512_131415, 20251025_121813, 2025-10-25 12.18.13 (1), …
const TITLE_CAMERA = new RegExp(
    '^(?:(?:VID|IMG|PXL|MVIMG|MOV|DSC|DJI|PANO|LV|signal|video|Screen[ _-]?Recording|Screenrecorder)[ _-]*)?' +
    '(\\d{4})[-_.]?(\\d{2})[-_.]?(\\d{2})' +
    '(?:[-_ T.]*(\\d{2})[-_.:]?(\\d{2})(?:[-_.:]?(\\d{2}))?)?' +
    '(?:[-_ .~]*(?:WA)?\\(?\\d+\\)?)*$', 'i');

/**
 * Lesbarer Titel aus einem Dateinamen.
 *
 * - Endung und Optimierer-Anhängsel fallen weg.
 * - Kamera-Namen werden zum Aufnahmezeitpunkt: „25. Okt. 2025 · 12:18“.
 * - Sonst werden Unterstriche (und bei Namen ohne Leerzeichen Punkte) zu
 *   Leerzeichen.
 *
 * @param {string} fileName - Dateiname mit oder ohne Endung
 * @returns {string}
 */
function titleFromFileName(fileName) {
    const original = String(fileName || '');
    const dot = original.lastIndexOf('.');
    let name = dot > 0 ? original.slice(0, dot) : original;
    name = name.replace(TITLE_ENCODE_SUFFIX, '');

    const m = TITLE_CAMERA.exec(name);
    if (m) {
        const year = +m[1], month = +m[2], day = +m[3];
        const hasTime = m[4] !== undefined;
        const hour = +m[4], minute = +m[5];
        const plausible = year >= 1990 && year <= 2100 && month >= 1 && month <= 12
            && day >= 1 && day <= 31 && (!hasTime || (hour <= 23 && minute <= 59));
        if (plausible) {
            const date = `${day}. ${TITLE_MONTHS[month - 1]} ${year}`;
            return hasTime ? `${date} · ${m[4]}:${m[5]}` : date;
        }
    }

    let title = name.replace(/_+/g, ' ');
    if (!/\s/.test(title)) title = title.replace(/\.+/g, ' ');
    title = title.replace(/\s+/g, ' ').replace(/^[\s.-]+|[\s.-]+$/g, '');
    return title || original;
}

/**
 * Anzeigetitel eines Mediums.
 * @param {Object|string} videoOrPath - Eintrag aus ALL_VIDEOS oder ein Pfad
 * @returns {string}
 */
function mediaTitle(videoOrPath) {
    const path = typeof videoOrPath === 'string' ? videoOrPath : (videoOrPath && videoOrPath.FilePath);
    return titleFromFileName(getFileName(path));
}

if (typeof window !== 'undefined') {
    window.titleFromFileName = titleFromFileName;
    window.mediaTitle = mediaTitle;
}

// Export for ES modules (if supported)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatSize,
        formatSizeCompact,
        formatDuration,
        formatDurationLong,
        formatBitrate,
        formatBitrateKbps,
        formatRelativeTime,
        getFileName,
        getDirPath,
        truncateText,
        titleFromFileName,
        mediaTitle
    };
}
