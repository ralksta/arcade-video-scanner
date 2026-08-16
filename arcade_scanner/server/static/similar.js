// similar.js — „Ähnliche Medien"-Leiste im Cinema
//
// Baut auf dem Embedding-Fundament auf: /api/similar liefert die nächsten
// Nachbarn über die gespeicherten Mittelwert-Vektoren. Ohne Indexlauf gibt es
// keine Vektoren — dieser Fall ist der Normalfall bei einer frischen
// Installation und wird deshalb erklärt statt als Fehler behandelt.

const SIMILAR_LIMIT = 12;

// Beim Durchblättern mit ← / → überholen sich die Anfragen: eine langsame
// Antwort zum vorherigen Medium trifft nach der schnellen zum aktuellen ein und
// überschreibt sie. Gegen den *laufenden* Pfad zu prüfen deckt beides ab — sich
// überholende Anfragen ebenso wie Weiterblättern ohne zweite Anfrage.

/**
 * Leiste auf-/zuklappen.
 */
function toggleCinemaSimilar() {
    const panel = document.getElementById('cinemaSimilarPanel');
    if (!panel) return;

    if (panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
        loadCinemaSimilar();
    } else {
        panel.classList.add('hidden');
    }
}

/**
 * Leiste schließen (beim Schließen des Cinema).
 */
function closeCinemaSimilar() {
    const panel = document.getElementById('cinemaSimilarPanel');
    if (panel) panel.classList.add('hidden');
}

/**
 * Nachbarn zum aktuell laufenden Medium laden und anzeigen.
 */
async function loadCinemaSimilar() {
    const panel = document.getElementById('cinemaSimilarPanel');
    const body = document.getElementById('cinemaSimilarBody');
    if (!panel || !body || panel.classList.contains('hidden')) return;

    const path = window.currentCinemaPath;
    if (!path) return;

    body.innerHTML = '<div class="similar-note">Suche ähnliche Medien …</div>';

    const encoded = safeEncodePath(path);
    if (encoded === null) {
        body.innerHTML = '<div class="similar-note">Dieser Dateiname lässt sich nicht '
            + 'als URL kodieren — die Suche ist dafür nicht möglich.</div>';
        return;
    }

    let payload;
    try {
        const response = await fetch(`/api/similar?path=${encoded}&limit=${SIMILAR_LIMIT}`);
        if (response.status === 404) {
            body.innerHTML = '<div class="similar-note">Dieses Medium ist noch nicht '
                + 'indiziert. Der Indexer holt es beim nächsten Lauf nach.</div>';
            return;
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        payload = await response.json();
    } catch (err) {
        console.error('Ähnlichkeitssuche fehlgeschlagen:', err);
        body.innerHTML = '<div class="similar-note">Ähnliche Medien konnten nicht '
            + 'geladen werden.</div>';
        return;
    }

    // Zwischenzeitlich weitergeblättert — diese Antwort ist überholt.
    if (window.currentCinemaPath !== path) return;

    if (payload.status === 'not_indexed') {
        body.innerHTML = '<div class="similar-note">Noch kein Ähnlichkeits-Index '
            + 'vorhanden. Lege ihn mit <code>scripts/media_indexer.py</code> an — '
            + 'danach erscheinen hier verwandte Aufnahmen.</div>';
        return;
    }

    const results = (payload.results || [])
        .map(entry => ({
            score: entry.score,
            video: (window.ALL_VIDEOS || []).find(v => v.FilePath === entry.file_path),
        }))
        // Treffer außerhalb der eigenen Scan-Ziele kennt ALL_VIDEOS nicht —
        // die dürfen hier auch nicht auftauchen.
        .filter(item => item.video);

    if (results.length === 0) {
        body.innerHTML = '<div class="similar-note">Keine ähnlichen Medien gefunden.</div>';
        return;
    }

    body.innerHTML = results.map(({ video, score }) => {
        const name = video.FilePath.split(/[\\/]/).pop();
        const percent = Math.round(score * 100);
        return `
            <button class="similar-item" data-path="${escapeHtml(video.FilePath)}"
                    onclick="openSimilarItem(this)" title="${escapeHtml(name)} · ${percent}% Übereinstimmung">
                <img src="/thumbnails/${escapeHtml(video.thumb || '')}" alt="" loading="lazy">
                <span class="similar-score">${percent}%</span>
                <span class="similar-name">${escapeHtml(name)}</span>
            </button>`;
    }).join('');
}

/**
 * Einen Treffer im Cinema öffnen.
 *
 * @param {HTMLElement} button - Der geklickte Eintrag mit data-path
 */
function openSimilarItem(button) {
    const path = button.getAttribute('data-path');
    if (!path) return;

    const container = document.createElement('div');
    container.setAttribute('data-path', path);
    openCinema(container);

    // Die Leiste bleibt offen und zeigt jetzt die Nachbarn des neuen Mediums.
    loadCinemaSimilar();
}

// ============================================================================
// EXPOSE TO GLOBAL SCOPE
// ============================================================================

window.toggleCinemaSimilar = toggleCinemaSimilar;
window.closeCinemaSimilar = closeCinemaSimilar;
window.loadCinemaSimilar = loadCinemaSimilar;
window.openSimilarItem = openSimilarItem;
