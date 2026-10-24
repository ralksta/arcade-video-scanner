// confirm_dialog.js — gestylter Ersatz für window.confirm()
//
// Die Papierkorb-Aktionen fragten bisher mit window.confirm() nach. Das ist
// ein Browser-Dialog, der die Design-Sprache verlässt und je nach Browser
// anders aussieht. showConfirmDialog() liefert ein Promise und benutzt den
// einen Dialog aus CONFIRM_DIALOG_COMPONENT für alle Papierkorb-Aktionen.

let _confirmResolver = null;
let _confirmOrigin = null;

function _confirmEls() {
    return {
        dialog: document.getElementById('confirmDialog'),
        title: document.getElementById('confirmDialogTitle'),
        message: document.getElementById('confirmDialogMessage'),
        details: document.getElementById('confirmDialogDetails'),
        icon: document.getElementById('confirmDialogIcon'),
        cancel: document.getElementById('confirmDialogCancel'),
        ok: document.getElementById('confirmDialogOk'),
    };
}

function _closeConfirm(result) {
    const els = _confirmEls();
    if (!els.dialog) return;

    els.dialog.classList.remove('active');
    els.dialog.setAttribute('aria-hidden', 'true');

    const resolve = _confirmResolver;
    _confirmResolver = null;
    const origin = _confirmOrigin;
    _confirmOrigin = null;
    if (resolve) resolve(Boolean(result));

    // a11y.js hängt den Fokus-Käfig an `.active` und stellt ihn beim
    // Ausblenden selbst zurück. Ohne a11y.js bliebe der Fokus im nun
    // versteckten Dialog — deshalb hier der Fallback.
    if (!els.dialog.dataset.focusTrapped
        && origin && document.contains(origin) && typeof origin.focus === 'function') {
        origin.focus();
    }
}

/**
 * Zeigt den Bestätigungsdialog und löst mit true/false auf.
 *
 * @param {Object} [options]
 * @param {string} [options.title] - Überschrift
 * @param {string} [options.message] - Erklärender Satz
 * @param {string[]|string} [options.details] - Optionale Zeilen (z. B. Dateinamen)
 * @param {string} [options.confirmLabel] - Beschriftung des Bestätigen-Knopfs
 * @param {string} [options.cancelLabel] - Beschriftung des Abbrechen-Knopfs
 * @param {boolean} [options.danger] - Roter Bestätigen-Knopf
 * @param {string} [options.icon] - Material-Icon-Name
 * @returns {Promise<boolean>}
 */
function showConfirmDialog(options = {}) {
    const els = _confirmEls();
    if (!els.dialog) {
        // Alter Dashboard-Dump oder Testkontext: lieber der native Dialog
        // als eine Aktion ohne Nachfrage.
        return Promise.resolve(window.confirm(options.message || options.title || ''));
    }

    // Eine bereits offene Nachfrage gehört zur vorigen Aktion.
    if (_confirmResolver) {
        _confirmResolver(false);
        _confirmResolver = null;
    }

    const {
        title = 'Bestätigen',
        message = '',
        details = [],
        confirmLabel = 'Bestätigen',
        cancelLabel = 'Abbrechen',
        danger = false,
        icon = 'help_outline',
    } = options;

    _confirmOrigin = document.activeElement;
    els.title.textContent = title;
    els.message.textContent = message;
    els.cancel.textContent = cancelLabel;
    els.ok.textContent = confirmLabel;
    els.icon.textContent = icon;
    els.icon.classList.toggle('is-danger', Boolean(danger));
    els.ok.classList.toggle('is-danger', Boolean(danger));

    const lines = Array.isArray(details) ? details : String(details || '').split('\n');
    const clean = lines.map(line => String(line)).filter(line => line.trim());
    els.details.replaceChildren();
    if (clean.length) {
        clean.forEach(line => {
            const row = document.createElement('div');
            row.textContent = line;
            els.details.appendChild(row);
        });
        els.details.classList.remove('hidden');
    } else {
        els.details.classList.add('hidden');
    }

    els.dialog.classList.add('active');
    els.dialog.setAttribute('aria-hidden', 'false');

    const promise = new Promise(resolve => { _confirmResolver = resolve; });

    // a11y.js fängt den Fokus beim Öffnen ab und springt auf das erste
    // Bedienelement (Abbrechen). Ohne a11y.js holen wir ihn hier nach.
    setTimeout(() => {
        if (_confirmResolver && !els.dialog.contains(document.activeElement)) {
            els.cancel.focus();
        }
    }, 0);

    return promise;
}

document.addEventListener('DOMContentLoaded', () => {
    const els = _confirmEls();
    if (!els.dialog) return;

    els.cancel.addEventListener('click', () => _closeConfirm(false));
    els.ok.addEventListener('click', () => _closeConfirm(true));
    els.dialog.addEventListener('click', (e) => {
        if (e.target === els.dialog) _closeConfirm(false);
    });
    els.dialog.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            e.stopPropagation();
            _closeConfirm(false);
        }
    });
});

window.showConfirmDialog = showConfirmDialog;
