// watch_progress.js — „Weiterschauen" im Browser.
//
// Der Stand liegt pro Konto auf dem Server (/api/progress) und gilt für alle
// Geräte: Was am Fernseher angefangen wurde, setzt der Browser fort und
// umgekehrt. Hier liegt nur eine Kopie, damit Player und Startseite ohne
// Rundreise wissen, wo man war.
//
// Die Schwellen stehen maßgeblich im Server (UserStore.save_progress); hier
// werden sie nur gespiegelt, damit die Kopie bis zur nächsten Antwort dasselbe
// zeigt.

const WATCH_PROGRESS_MIN_SECONDS = 20;
const WATCH_PROGRESS_FINISHED_RATIO = 0.95;

window.WATCH_PROGRESS = new Map();

/**
 * Lädt den Stand des Kontos vom Server.
 * @returns {Promise<boolean>} false, wenn der Server nicht antwortete
 */
async function loadWatchProgress() {
    try {
        const res = await fetch('/api/progress');
        if (!res.ok) return false;
        const data = await res.json();
        window.WATCH_PROGRESS.clear();
        (data.items || []).forEach(item => window.WATCH_PROGRESS.set(item.path, item));
        return true;
    } catch (e) {
        console.warn('Wiedergabefortschritt nicht geladen:', e);
        return false;
    }
}

/** Gespeicherter Stand für `path`, oder null. */
function getWatchProgress(path) {
    return window.WATCH_PROGRESS.get(path) || null;
}

/** Position zum Fortsetzen in Sekunden, oder 0. */
function resumePositionFor(path) {
    const entry = getWatchProgress(path);
    return entry && entry.position > 0 ? entry.position : 0;
}

/** Anteil 0..1 für den Fortschrittsbalken, oder 0. */
function watchProgressRatio(path) {
    const entry = getWatchProgress(path);
    if (!entry || !(entry.position > 0) || !(entry.duration > 0)) return 0;
    return Math.min(1, entry.position / entry.duration);
}

/**
 * Angefangene Medien aus `videos`, zuletzt gesehenes zuerst.
 * @param {Array} videos - die Medien, die gezeigt werden dürfen
 */
function continueWatchingList(videos) {
    const byPath = new Map(videos.map(v => [v.FilePath, v]));
    return [...window.WATCH_PROGRESS.values()]
        .filter(entry => entry.position > 0 && byPath.has(entry.path))
        .sort((a, b) => b.updated_at - a.updated_at)
        .map(entry => byPath.get(entry.path));
}

/**
 * Meldet die Position an den Server.
 *
 * `beacon` für das Schließen der Seite: Ein gewöhnlicher fetch wird beim
 * Entladen abgebrochen, sendBeacon nicht.
 */
function recordWatchProgress(path, position, duration, {beacon = false} = {}) {
    if (!path || !(duration > 0) || !isFinite(duration) || !(position >= 0)) return;
    const finished = position / duration >= WATCH_PROGRESS_FINISHED_RATIO;
    if (!finished && position < WATCH_PROGRESS_MIN_SECONDS) return;

    const previous = getWatchProgress(path);
    window.WATCH_PROGRESS.set(path, {
        path,
        position: finished ? 0 : position,
        duration,
        watched: finished || Boolean(previous && previous.watched),
        updated_at: Date.now() / 1000,
    });

    const body = JSON.stringify({path, position, duration});
    if (beacon && navigator.sendBeacon) {
        navigator.sendBeacon('/api/progress', new Blob([body], {type: 'application/json'}));
        return;
    }
    fetch('/api/progress', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body,
        keepalive: true,
    }).catch(() => {});
}

/** Nimmt `path` aus „Weiterschauen" („gesehen" bleibt). */
function clearWatchProgress(path) {
    const entry = getWatchProgress(path);
    if (entry && entry.watched) {
        window.WATCH_PROGRESS.set(path, {...entry, position: 0});
    } else {
        window.WATCH_PROGRESS.delete(path);
    }
    fetch('/api/progress', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({path, clear: true}),
    }).catch(() => {});
}

window.loadWatchProgress = loadWatchProgress;
window.getWatchProgress = getWatchProgress;
window.resumePositionFor = resumePositionFor;
window.watchProgressRatio = watchProgressRatio;
window.continueWatchingList = continueWatchingList;
window.recordWatchProgress = recordWatchProgress;
window.clearWatchProgress = clearWatchProgress;
