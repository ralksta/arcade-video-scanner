// shortcuts.js — Globale Tastatur-Shortcuts + Hilfe-Overlay
//
// Das Dashboard hat historisch gewachsen eine Menge Tastenkürzel (Cinema,
// Duplicate-Checker, Command-Palette) — die waren bisher nirgends dokumentiert.
// Diese Datei ist die EINE Stelle, an der die Tastenbelegung beschrieben wird;
// das Overlay rendert sich aus SHORTCUT_SECTIONS, damit Doku und Realität
// nicht auseinanderlaufen.

const SHORTCUT_SECTIONS = [
    {
        title: 'Global',
        icon: 'public',
        items: [
            { keys: ['?'], label: 'Diese Hilfe öffnen / schließen' },
            { keys: ['Ctrl', 'K'], label: 'Command-Palette (⌘K auf Mac)' },
            { keys: ['/'], label: 'Suchfeld fokussieren' },
            { keys: ['1'], label: 'Grid-Ansicht' },
            { keys: ['2'], label: 'Listen-Ansicht' },
            { keys: ['3'], label: 'Treemap-Ansicht' },
            { keys: ['4'], label: 'Ordner-Browser' },
            { keys: ['Esc'], label: 'Panel/Modal schließen, im Ordner-Browser eine Ebene hoch' },
        ],
    },
    {
        title: 'Cinema',
        icon: 'movie',
        items: [
            { keys: ['←'], label: 'Vorheriges Medium' },
            { keys: ['→'], label: 'Nächstes Medium' },
            { keys: ['Space'], label: 'Play / Pause' },
            { keys: ['F'], label: 'Favorit umschalten' },
            { keys: ['V'], label: 'In den Vault verschieben' },
            { keys: ['I'], label: 'Info-Panel' },
            { keys: ['S'], label: 'Ähnliche Medien' },
            { keys: ['G'], label: 'GIF-Export' },
            { keys: ['O'], label: 'Optimizer' },
            { keys: ['A', '…', 'Z'], label: 'Übrige Buchstaben: konfigurierte Tag-Shortcuts' },
            { keys: ['Esc'], label: 'Cinema schließen' },
        ],
    },
    {
        title: 'Duplikat-Prüfung',
        icon: 'content_copy',
        items: [
            { keys: ['1'], label: 'Datei A behalten (auch ←)' },
            { keys: ['2'], label: 'Datei B behalten (auch →)' },
            { keys: ['S'], label: 'Gruppe überspringen (auch Space)' },
            { keys: ['A'], label: '„Egal welche" — Gruppe als erledigt markieren' },
            { keys: ['Esc'], label: 'Prüfung beenden' },
        ],
    },
];

/**
 * True, wenn der Nutzer gerade in ein Eingabefeld tippt.
 * Globale Buchstaben-Shortcuts dürfen dann nicht feuern.
 *
 * @param {EventTarget} target - e.target des Key-Events
 * @returns {boolean}
 */
function isTypingTarget(target) {
    if (!target || !target.tagName) return false;
    const tag = target.tagName.toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    return target.isContentEditable === true;
}

/**
 * True, wenn irgendein Modal/Overlay aktiv ist, das eigene Tasten belegt.
 * Die globalen Shortcuts halten sich dann raus.
 *
 * @returns {boolean}
 */
function isModalActive() {
    const cinema = document.getElementById('cinemaModal');
    if (cinema && cinema.classList.contains('active')) return true;
    if (window.duplicateCheckerState && window.duplicateCheckerState.isActive) return true;
    const blocking = ['settingsModal', 'tagManagerModal', 'collectionModal', 'hiddenPathModal'];
    return blocking.some(id => {
        const el = document.getElementById(id);
        return el && el.classList.contains('active');
    });
}

/**
 * Baut das Overlay-Markup aus SHORTCUT_SECTIONS.
 * @returns {string} HTML
 */
function renderShortcutSections() {
    return SHORTCUT_SECTIONS.map(section => `
        <section class="mb-5 last:mb-0">
            <h3 class="flex items-center gap-2 text-[12px] uppercase tracking-wider text-text-muted mb-2">
                <span class="material-icons text-[15px]" aria-hidden="true">${section.icon}</span>
                ${section.title}
            </h3>
            <dl class="space-y-1.5">
                ${section.items.map(item => `
                <div class="flex items-start gap-3">
                    <dt class="flex items-center gap-1 flex-shrink-0 min-w-[110px]">
                        ${item.keys.map(k => `<kbd class="shortcut-key">${k}</kbd>`).join('<span class="text-text-muted text-[11px]">+</span>')}
                    </dt>
                    <dd class="text-[13px] text-text-main leading-6">${item.label}</dd>
                </div>`).join('')}
            </dl>
        </section>`).join('');
}

/**
 * Shortcut-Hilfe öffnen (rendert den Inhalt beim ersten Öffnen).
 */
function openShortcutsHelp() {
    const modal = document.getElementById('shortcutsModal');
    if (!modal) return;

    const body = document.getElementById('shortcutsBody');
    if (body && !body.dataset.rendered) {
        body.innerHTML = renderShortcutSections();
        body.dataset.rendered = '1';
    }

    modal.classList.remove('hidden');
    modal.classList.add('active');

    const closeBtn = document.getElementById('shortcutsCloseBtn');
    if (closeBtn) closeBtn.focus();
}

/**
 * Shortcut-Hilfe schließen.
 */
function closeShortcutsHelp() {
    const modal = document.getElementById('shortcutsModal');
    if (!modal) return;
    modal.classList.remove('active');
    modal.classList.add('hidden');
}

/**
 * Hilfe auf-/zuklappen.
 */
function toggleShortcutsHelp() {
    const modal = document.getElementById('shortcutsModal');
    if (!modal) return;
    if (modal.classList.contains('active')) {
        closeShortcutsHelp();
    } else {
        openShortcutsHelp();
    }
}

/**
 * Suchfeld fokussieren und Inhalt selektieren.
 */
function focusSearchInput() {
    const input = document.getElementById('mobileSearchInput');
    if (!input) return;
    input.focus();
    input.select();
}

// --- GLOBALER KEY-HANDLER ---
document.addEventListener('keydown', (e) => {
    // ESC schließt die Hilfe — auch wenn ein Eingabefeld den Fokus hat.
    const modal = document.getElementById('shortcutsModal');
    if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
        e.preventDefault();
        e.stopPropagation();
        closeShortcutsHelp();
        return;
    }

    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isTypingTarget(e.target)) return;

    // '?' ist auf vielen Layouts Shift+irgendwas — auf e.key prüfen, nicht auf Code.
    if (e.key === '?') {
        e.preventDefault();
        toggleShortcutsHelp();
        return;
    }

    // Bei offener Hilfe schluckt sie den Rest (außer '?' und ESC oben).
    if (modal && modal.classList.contains('active')) return;

    // Cinema / Duplicate-Checker haben eigene Handler — nicht dazwischenfunken.
    if (isModalActive()) return;

    if (e.key === '/') {
        e.preventDefault();
        focusSearchInput();
        return;
    }

    const layoutByKey = { '1': 'grid', '2': 'list', '3': 'treemap', '4': 'folderbrowser' };
    if (layoutByKey[e.key] && typeof setLayout === 'function') {
        e.preventDefault();
        setLayout(layoutByKey[e.key]);
    }
});

// ============================================================================
// EXPOSE TO GLOBAL SCOPE
// ============================================================================

window.openShortcutsHelp = openShortcutsHelp;
window.closeShortcutsHelp = closeShortcutsHelp;
window.toggleShortcutsHelp = toggleShortcutsHelp;
window.focusSearchInput = focusSearchInput;
window.SHORTCUT_SECTIONS = SHORTCUT_SECTIONS;
