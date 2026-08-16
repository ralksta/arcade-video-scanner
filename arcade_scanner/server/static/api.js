// api.js - Extracted from engine.js

// --- GLOBAL AUTH INTERCEPTOR ---
const originalFetch = window.fetch;
window.fetch = async function (...args) {
    const response = await originalFetch(...args);
    if (response.status === 401) {
        // Redirect to login page.
        // Return a promise that never resolves so no downstream .json()/.text()
        // call can accidentally consume the already-drained response body.
        window.location.href = '/static/login.html';
        return new Promise(() => {});
    }
    return response;
};

// --- SCHREIBENDE API-AUFRUFE ---

/**
 * Führt einen schreibenden API-Aufruf aus und macht Fehler sichtbar.
 *
 * Viele Aktionen im Dashboard aktualisieren die UI optimistisch und feuern
 * danach ein `fetch()` ohne `.catch` ab. Ist der Server weg oder antwortet er
 * mit 500, bleibt die Oberfläche in einem Zustand stehen, den der Server nie
 * gesehen hat — beim nächsten Reload springt alles zurück, ohne dass der Nutzer
 * je einen Hinweis bekommen hätte. Diese Hülle meldet den Fehler und stellt den
 * vorherigen Zustand über `rollback` wieder her.
 *
 * @param {string} url - Ziel-URL
 * @param {RequestInit} [options] - fetch-Optionen
 * @param {Object} [handling]
 * @param {string} [handling.action] - Klartextname der Aktion für die Meldung
 * @param {Function} [handling.rollback] - Macht die optimistische UI-Änderung rückgängig
 * @param {boolean} [handling.silent] - Nur loggen, keine Meldung anzeigen
 * @returns {Promise<Response|null>} Die Antwort, oder null im Fehlerfall
 */
async function apiWrite(url, options = {}, handling = {}) {
    const { action = 'Aktion', rollback = null, silent = false } = handling;

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status} ${response.statusText}`.trim());
        }
        return response;
    } catch (err) {
        console.error(`${action} fehlgeschlagen (${url}):`, err);

        if (typeof rollback === 'function') {
            try {
                rollback();
            } catch (rollbackErr) {
                console.error('Rollback fehlgeschlagen:', rollbackErr);
            }
        }

        if (!silent && typeof showToast === 'function') {
            const reason = err instanceof TypeError ? 'Server nicht erreichbar' : err.message;
            showToast(`${action} fehlgeschlagen: ${reason}`, 'error');
        }
        return null;
    }
}

window.apiWrite = apiWrite;
