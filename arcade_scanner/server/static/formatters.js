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
        truncateText
    };
}
