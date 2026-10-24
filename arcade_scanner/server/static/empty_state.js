// empty_state.js — Kontextbezogener Leer-Zustand für das Grid
//
// Bis hierher zeigte das Dashboard bei 0 Treffern schlicht eine weiße Fläche:
// kein Hinweis, ob die Bibliothek leer ist, ein Filter zu eng steht oder die
// Suche nichts findet — und kein Weg zurück außer Raten. updateEmptyState()
// wählt anhand des Zustands die passende Erklärung samt Aktion.

/**
 * Ermittelt, welcher Leer-Zustand gerade zutrifft.
 *
 * Reihenfolge ist Absicht: die spezifischste Ursache gewinnt. Wer sucht UND
 * filtert, bekommt beide Auswege angeboten.
 *
 * @returns {{icon: string, title: string, hint: string, actions: Array<{label: string, fn: string, primary?: boolean}>}}
 */
function describeEmptyState() {
    const total = (window.ALL_VIDEOS || []).length;
    const search = (window.searchTerm || '').trim();
    const filterCount = typeof countActiveFilters === 'function' ? countActiveFilters() : 0;
    const mode = window.workspaceMode || 'lobby';

    // 1. Die Bibliothek selbst ist leer — nichts gescannt, nichts gefunden.
    if (total === 0) {
        return {
            icon: 'video_library',
            title: 'Noch keine Medien in der Bibliothek',
            hint: 'Lege in den Einstellungen mindestens einen Scan-Pfad fest und starte '
                + 'danach einen Scan. Der erste Durchlauf kann bei großen Bibliotheken dauern.',
            actions: [
                { label: 'Einstellungen öffnen', fn: 'openSettings()', primary: true },
                { label: 'Jetzt scannen', fn: 'rescanLibrary()' },
            ],
        };
    }

    // 2. Suche und/oder Filter schneiden alles weg.
    if (search || filterCount > 0) {
        const actions = [];
        if (search) actions.push({ label: 'Suche löschen', fn: 'clearSearchTerm()', primary: true });
        if (filterCount > 0) {
            actions.push({ label: 'Filter zurücksetzen', fn: 'resetFilters()', primary: !search });
        }

        let hint;
        if (search && filterCount > 0) {
            hint = `Weder Suchbegriff „${escapeHtml(search)}" noch die ${filterCount} aktiven `
                + 'Filter passen zusammen auf eine Datei.';
        } else if (search) {
            hint = `Kein Dateiname enthält „${escapeHtml(search)}".`;
        } else {
            hint = `Die ${filterCount} aktiven Filter schließen alle ${total.toLocaleString('de-DE')} `
                + 'Dateien aus.';
        }

        return { icon: 'search_off', title: 'Keine Treffer', hint, actions };
    }

    // 3. Der Workspace ist einfach noch leer.
    const perWorkspace = {
        vault: {
            icon: 'lock',
            title: 'Der Vault ist leer',
            hint: 'Versteckte Dateien landen hier. Im Cinema mit V oder über das '
                + 'Augen-Symbol auf einer Karte verschiebst du etwas hierher.',
        },
        favorites: {
            icon: 'star_border',
            title: 'Noch keine Favoriten',
            hint: 'Markiere Dateien mit dem Stern auf der Karte oder im Cinema mit F.',
        },
        optimized: {
            icon: 'compress',
            title: 'Nichts zum Vergleichen',
            hint: 'Hier stehen Original und optimierte Fassung nebeneinander, sobald ein '
                + 'Encode fertig ist — die Warteschlange füllst du über den Optimizer.',
        },
    };

    const preset = perWorkspace[mode] || {
        icon: 'inbox',
        title: 'Nichts anzuzeigen',
        hint: 'In dieser Ansicht liegt gerade nichts.',
    };
    return { ...preset, actions: [] };
}

/**
 * Blendet den Leer-Zustand ein oder aus.
 *
 * Nur für Grid- und Listen-Layout: Treemap und Ordner-Browser rendern ihre
 * eigenen Container und bringen eigene Hinweise mit.
 */
function updateEmptyState() {
    const box = document.getElementById('emptyState');
    if (!box) return;

    const layout = window.currentLayout || 'grid';
    const inGridLayout = layout === 'grid' || layout === 'list';
    const hasResults = (window.filteredVideos || []).length > 0;
    const isDuplicates = window.workspaceMode === 'duplicates';

    if (!inGridLayout || hasResults || isDuplicates) {
        box.classList.add('hidden');
        box.classList.remove('flex');
        return;
    }

    const state = describeEmptyState();
    const icon = document.getElementById('emptyStateIcon');
    const title = document.getElementById('emptyStateTitle');
    const hint = document.getElementById('emptyStateHint');
    const actions = document.getElementById('emptyStateActions');

    if (icon) icon.textContent = state.icon;
    if (title) title.textContent = state.title;
    if (hint) hint.innerHTML = state.hint;
    if (actions) {
        actions.innerHTML = state.actions.map(a => `
            <button onclick="${a.fn}" class="${a.primary ? 'ds-btn ds-btn-primary' : 'ds-btn ds-btn-secondary'} text-[13px] px-4 py-2">
                ${escapeHtml(a.label)}
            </button>`).join('');
    }

    box.classList.remove('hidden');
    box.classList.add('flex');
}

/**
 * Zählt die aktiven Filter — gleiche Logik wie updateFilterPanelCount(),
 * aber als Wert statt als DOM-Nebenwirkung.
 *
 * @returns {number}
 */
function countActiveFilters() {
    let count = 0;
    if (window.currentFilter && window.currentFilter !== 'all') count++;
    if (window.currentCodec && window.currentCodec !== 'all') count++;
    if (window.minSizeMB !== null && window.minSizeMB !== undefined) count++;
    if (window.maxSizeMB !== null && window.maxSizeMB !== undefined) count++;
    if (window.dateFilter && window.dateFilter !== 'all') count++;
    count += (window.activeTags || []).length;
    if (window.filterUntaggedOnly) count++;
    return count;
}

/**
 * Suchbegriff leeren und neu filtern — Aktion aus dem Leer-Zustand.
 */
function clearSearchTerm() {
    const input = document.getElementById('mobileSearchInput');
    if (input) input.value = '';
    window.searchTerm = '';

    const saveBtn = document.getElementById('saveViewBtn');
    if (saveBtn) saveBtn.style.display = 'none';

    if (typeof filterAndSort === 'function') filterAndSort(true);
}

// ============================================================================
// EXPOSE TO GLOBAL SCOPE
// ============================================================================

window.updateEmptyState = updateEmptyState;
window.describeEmptyState = describeEmptyState;
window.countActiveFilters = countActiveFilters;
window.clearSearchTerm = clearSearchTerm;
