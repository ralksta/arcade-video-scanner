// a11y.js — Fokus-Verwaltung für Modals
//
// Alle Dialoge des Dashboards werden über eine `active`- bzw. `hidden`-Klasse
// ein- und ausgeblendet; der Tastaturfokus blieb dabei außen vor. Mit Tab
// wanderte er aus dem offenen Dialog heraus in die Seite dahinter — sichtbar
// nur am Fokusring, der irgendwo hinter dem Overlay auftauchte, und für
// Screenreader-Nutzer praktisch unbedienbar.
//
// Statt jede open/close-Funktion einzeln anzufassen (es sind über ein Dutzend,
// verteilt auf sechs Dateien), beobachtet dieses Modul die Klassenwechsel der
// bekannten Dialoge und hängt den Fokus-Käfig selbst ein und aus.

const TRAPPED_MODALS = [
    'cinemaModal',
    'settingsModal',
    'tagManagerModal',
    'collectionModal',
    'hiddenPathModal',
    'shortcutsModal',
    'duplicateCheckerModal',
    'batchTagModal',
    'setupWizard',
];

const FOCUSABLE = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
].join(',');

// Merkt sich pro Dialog, wohin der Fokus zurückgehört.
const _focusOrigin = new WeakMap();

/**
 * Sichtbare, fokussierbare Elemente eines Containers.
 *
 * `offsetParent === null` filtert alles heraus, was gerade per display:none
 * ausgeblendet ist — sonst landet der Fokus in einem zugeklappten Panel.
 *
 * @param {HTMLElement} container
 * @returns {HTMLElement[]}
 */
function focusableWithin(container) {
    return Array.from(container.querySelectorAll(FOCUSABLE))
        .filter(el => el.offsetParent !== null || el === document.activeElement);
}

/**
 * Hält Tab und Shift+Tab innerhalb des Dialogs.
 *
 * @param {KeyboardEvent} e
 */
function _trapHandler(e) {
    if (e.key !== 'Tab') return;

    const modal = e.currentTarget;
    const items = focusableWithin(modal);
    if (items.length === 0) {
        e.preventDefault();
        modal.focus();
        return;
    }

    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;

    if (e.shiftKey && (active === first || !modal.contains(active))) {
        e.preventDefault();
        last.focus();
    } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
    }
}

/**
 * Fokus im Dialog einsperren und den ersten sinnvollen Punkt anspringen.
 *
 * @param {HTMLElement} modal
 */
function trapFocus(modal) {
    if (!modal || modal.dataset.focusTrapped === '1') return;

    _focusOrigin.set(modal, document.activeElement);
    modal.dataset.focusTrapped = '1';
    modal.addEventListener('keydown', _trapHandler);

    // Cinema behält seinen eigenen Fokus (das Modal selbst, damit die
    // Video-Shortcuts greifen) — sonst auf das erste Bedienelement.
    if (modal.id !== 'cinemaModal') {
        const items = focusableWithin(modal);
        if (items.length > 0) {
            items[0].focus();
        } else {
            modal.tabIndex = -1;
            modal.focus();
        }
    }
}

/**
 * Fokus freigeben und dorthin zurückstellen, wo er beim Öffnen war.
 *
 * @param {HTMLElement} modal
 */
function releaseFocus(modal) {
    if (!modal || modal.dataset.focusTrapped !== '1') return;

    modal.removeEventListener('keydown', _trapHandler);
    delete modal.dataset.focusTrapped;

    const origin = _focusOrigin.get(modal);
    _focusOrigin.delete(modal);

    // Nur zurückspringen, wenn das Ursprungselement noch in der Seite hängt —
    // eine gelöschte Karte darf den Fokus nicht ins Leere ziehen.
    if (origin && document.contains(origin) && typeof origin.focus === 'function') {
        origin.focus();
    }
}

/**
 * Ist der Dialog gerade sichtbar?
 *
 * Die Dialoge nutzen zwei Konventionen nebeneinander: `.active` (Mehrzahl) und
 * das Fehlen von `.hidden` (Setup-Assistent). Beide werden berücksichtigt.
 *
 * @param {HTMLElement} modal
 * @returns {boolean}
 */
function isModalVisible(modal) {
    if (modal.classList.contains('active')) return true;
    return modal.id === 'setupWizard' && !modal.classList.contains('hidden');
}

/**
 * Klassenwechsel der bekannten Dialoge beobachten und den Fokus-Käfig
 * entsprechend ein- oder aushängen.
 */
function initModalFocusTraps() {
    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            const modal = mutation.target;
            if (isModalVisible(modal)) {
                trapFocus(modal);
            } else {
                releaseFocus(modal);
            }
        });
    });

    const attach = id => {
        const modal = document.getElementById(id);
        if (!modal || modal.dataset.focusObserved === '1') return false;

        modal.dataset.focusObserved = '1';
        observer.observe(modal, { attributes: true, attributeFilter: ['class'] });
        if (isModalVisible(modal)) trapFocus(modal);
        return true;
    };

    const pending = TRAPPED_MODALS.filter(id => !attach(id));

    // Manche Dialoge (batchTagModal) baut das JS erst beim ersten Öffnen in den
    // Body — die sind zum Zeitpunkt von DOMContentLoaded noch nicht da.
    if (pending.length > 0) {
        const bodyObserver = new MutationObserver(() => {
            const stillPending = pending.filter(id => !attach(id));
            pending.length = 0;
            pending.push(...stillPending);
            if (pending.length === 0) bodyObserver.disconnect();
        });
        bodyObserver.observe(document.body, { childList: true, subtree: true });
    }

    return observer;
}

document.addEventListener('DOMContentLoaded', initModalFocusTraps);

// ============================================================================
// EXPOSE TO GLOBAL SCOPE
// ============================================================================

window.trapFocus = trapFocus;
window.releaseFocus = releaseFocus;
window.focusableWithin = focusableWithin;
window.initModalFocusTraps = initModalFocusTraps;
window.TRAPPED_MODALS = TRAPPED_MODALS;
