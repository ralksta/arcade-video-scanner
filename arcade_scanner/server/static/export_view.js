// export_view.js — Die aktuelle Ansicht als CSV oder Playlist ausgeben
//
// Das Werkzeug ist ein Medien-*Inventar*: Filtern, Sortieren und Auswerten sind
// der Kern, aber bislang blieb jede Auswertung in der Oberfläche gefangen.
// Exportiert wird genau das, was gerade zu sehen ist — dieselbe Liste, dieselbe
// Reihenfolge, inklusive aller aktiven Filter.

const CSV_COLUMNS = [
    ['Pfad', v => v.FilePath],
    ['Dateiname', v => (v.FilePath || '').split(/[\\/]/).pop()],
    ['Typ', v => v.media_type || 'video'],
    ['Größe_MB', v => (v.Size_MB || 0).toFixed(1)],
    ['Dauer_Sek', v => Math.round(v.Duration_Sec || 0)],
    ['Codec', v => v.codec || ''],
    ['Bitrate_Mbps', v => (v.Bitrate_Mbps || 0).toFixed(2)],
    ['Breite', v => v.Width || 0],
    ['Höhe', v => v.Height || 0],
    ['Status', v => v.Status || ''],
    ['Favorit', v => (v.favorite ? 'ja' : 'nein')],
    ['Tags', v => (v.tags || []).join('; ')],
];

/**
 * Ein Feld für CSV maskieren (RFC 4180).
 *
 * Dateinamen sind hier kein Sonderfall, sondern der Normalfall: sie enthalten
 * Kommas, Anführungszeichen und — auf Unix völlig zulässig — Zeilenumbrüche.
 * Unmaskiert verschiebt ein einziger solcher Name alle folgenden Spalten.
 *
 * @param {*} value - Beliebiger Wert
 * @returns {string} CSV-sicheres Feld
 */
function csvField(value) {
    const text = value === null || value === undefined ? '' : String(value);
    if (/[",\n\r;]/.test(text)) {
        return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
}

/**
 * Die übergebenen Einträge als CSV-Text aufbauen.
 *
 * @param {Array<Object>} videos
 * @returns {string} CSV inklusive Kopfzeile
 */
function buildCsv(videos) {
    const header = CSV_COLUMNS.map(([name]) => csvField(name)).join(',');
    const rows = videos.map(video =>
        CSV_COLUMNS.map(([, read]) => csvField(read(video))).join(',')
    );
    // CRLF: Excel und LibreOffice erwarten es, alles andere verkraftet es.
    return [header, ...rows].join('\r\n') + '\r\n';
}

/**
 * Die übergebenen Einträge als M3U-Playlist aufbauen.
 *
 * Enthält lokale Dateipfade, keine Stream-URLs: ein externer Player hat keine
 * Sitzung und käme an /stream ohnehin nicht heran. Nützlich ist das dort, wo
 * der Player dieselbe Freigabe eingebunden hat — der übliche NAS-Fall.
 *
 * @param {Array<Object>} videos
 * @returns {string} M3U-Text
 */
function buildM3u(videos) {
    const lines = ['#EXTM3U'];
    videos.forEach(video => {
        const name = (video.FilePath || '').split(/[\\/]/).pop();
        const seconds = Math.round(video.Duration_Sec || 0);
        lines.push(`#EXTINF:${seconds},${name}`);
        lines.push(video.FilePath);
    });
    return lines.join('\n') + '\n';
}

/**
 * Dateiname für den Export, mit Workspace und Datum.
 *
 * @param {string} extension - Ohne Punkt
 * @param {Date} [now]
 * @returns {string}
 */
function exportFileName(extension, now = new Date()) {
    const stamp = now.toISOString().slice(0, 10);
    const scope = window.workspaceMode || 'lobby';
    return `arcade-${scope}-${stamp}.${extension}`;
}

/**
 * Text als Datei herunterladen.
 *
 * @param {string} content
 * @param {string} filename
 * @param {string} mime
 */
function downloadText(content, filename, mime) {
    // BOM, damit Excel die Umlaute nicht als Latin-1 liest.
    const blob = new Blob(['﻿', content], { type: `${mime};charset=utf-8` });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();

    // Erst nach dem Klick freigeben, sonst bricht der Download in Safari ab.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Die aktuell gefilterte Ansicht exportieren.
 *
 * @param {string} format - 'csv' oder 'm3u'
 */
function exportCurrentView(format = 'csv') {
    const videos = (window.filteredVideos || []).filter(v => v && v.FilePath);

    if (videos.length === 0) {
        showToast('Nichts zu exportieren — die Ansicht ist leer', 'warning');
        return;
    }

    if (format === 'm3u') {
        downloadText(buildM3u(videos), exportFileName('m3u'), 'audio/x-mpegurl');
    } else {
        downloadText(buildCsv(videos), exportFileName('csv'), 'text/csv');
    }

    showToast(`${videos.length.toLocaleString('de-DE')} Einträge exportiert`, 'success');
}

// ============================================================================
// EXPOSE TO GLOBAL SCOPE
// ============================================================================

window.exportCurrentView = exportCurrentView;
window.buildCsv = buildCsv;
window.buildM3u = buildM3u;
window.csvField = csvField;
window.exportFileName = exportFileName;
