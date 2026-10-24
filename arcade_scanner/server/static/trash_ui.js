/**
 * trash_ui.js — Papierkorb in den Einstellungen (Storage).
 *
 * Gelöschte Dateien bleiben 30 Tage wiederherstellbar. Die Liste wird erst
 * geladen, wenn der Storage-Abschnitt geöffnet wird; danach nach jeder
 * Aktion neu. Die Inhalte kommen ausschließlich über textContent in das DOM —
 * Dateinamen dürfen keine HTML-Struktur erzeugen.
 */

function formatTrashSize(bytes) {
    const value = Number(bytes) || 0;
    if (value < 1024) return `${value} B`;
    const units = ['KB', 'MB', 'GB', 'TB'];
    let size = value / 1024;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) {
        size /= 1024;
        unit += 1;
    }
    return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unit]}`;
}

function formatTrashDate(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString('de-DE', {
        day: '2-digit', month: 'short', year: 'numeric',
    });
}

function _trashEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
}

function renderTrash(data) {
    const list = document.getElementById('trashList');
    const summary = document.getElementById('trashSummary');
    const emptyHint = document.getElementById('trashEmptyHint');
    if (!list) return;

    const entries = data.entries || [];
    if (summary) {
        summary.textContent = entries.length
            ? `${entries.length} ${entries.length === 1 ? 'Datei' : 'Dateien'} · ${formatTrashSize(data.size)}`
            : 'Papierkorb ist leer';
    }
    if (emptyHint) emptyHint.classList.toggle('hidden', entries.length > 0);

    list.replaceChildren();
    entries.forEach(entry => {
        const row = _trashEl('li', 'flex items-center gap-3 py-2');

        const icon = _trashEl('span', 'material-icons text-gray-500 text-lg', 'movie');
        icon.setAttribute('aria-hidden', 'true');
        row.appendChild(icon);

        const info = _trashEl('div', 'min-w-0 flex-1');
        const name = _trashEl('div', 'text-sm text-text-main truncate', entry.name || entry.original_path);
        name.title = entry.original_path || '';
        info.appendChild(name);

        const metaParts = [];
        if (entry.folder) metaParts.push(entry.folder);
        metaParts.push(formatTrashSize(entry.size));
        const deleted = formatTrashDate(entry.deleted_at);
        if (deleted) metaParts.push(`gelöscht ${deleted}`);
        if (entry.deleted_by) metaParts.push(`von ${entry.deleted_by}`);
        if (entry.days_left !== null && entry.days_left !== undefined) {
            metaParts.push(`noch ${entry.days_left} ${entry.days_left === 1 ? 'Tag' : 'Tage'}`);
        }
        const meta = _trashEl('div', 'text-[11px] text-gray-500 truncate', metaParts.join(' · '));
        meta.title = entry.original_path || '';
        info.appendChild(meta);
        row.appendChild(info);

        const restore = _trashEl('button', 'shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium border border-accent/30 text-accent hover:bg-accent/10 transition-colors', 'Zurückholen');
        restore.type = 'button';
        restore.addEventListener('click', () => restoreTrashEntry(entry.id, restore));
        row.appendChild(restore);

        list.appendChild(row);
    });
}

async function loadTrash() {
    const summary = document.getElementById('trashSummary');
    if (summary && !summary.textContent.startsWith('Papierkorb wird')) {
        summary.textContent = 'Papierkorb wird geladen …';
    }
    try {
        const res = await fetch('/api/trash');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderTrash(await res.json());
    } catch (e) {
        console.error('Papierkorb konnte nicht geladen werden:', e);
        if (summary) summary.textContent = 'Papierkorb konnte nicht geladen werden';
    }
}

async function restoreTrashEntry(id, button) {
    if (button) button.disabled = true;
    try {
        const res = await fetch('/api/trash/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: [id] }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

        if (data.failed && data.failed.length) {
            if (typeof showSettingsToast === 'function') {
                showSettingsToast(data.failed[0].error || 'Zurückholen fehlgeschlagen', true);
            }
        } else if (typeof showSettingsToast === 'function') {
            showSettingsToast('Datei zurückgeholt', false);
        }
        await loadTrash();
    } catch (e) {
        console.error('Restore error:', e);
        if (typeof showSettingsToast === 'function') {
            showSettingsToast('Zurückholen fehlgeschlagen', true);
        }
        if (button) button.disabled = false;
    }
}

async function emptyTrash() {
    const confirmed = typeof showConfirmDialog === 'function'
        ? await showConfirmDialog({
            title: 'Papierkorb endgültig leeren?',
            message: 'Alle Dateien im Papierkorb werden endgültig gelöscht. Das lässt sich nicht rückgängig machen.',
            confirmLabel: 'Endgültig löschen',
            danger: true,
            icon: 'delete_forever',
        })
        : confirm('Alle Dateien im Papierkorb endgültig löschen? Das lässt sich nicht rückgängig machen.');
    if (!confirmed) {
        return;
    }
    try {
        const res = await fetch('/api/trash/empty', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ all: true }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        if (typeof showSettingsToast === 'function') {
            showSettingsToast(
                data.purged
                    ? `${data.purged} Datei(en) endgültig gelöscht, ${formatTrashSize(data.freed)} frei`
                    : 'Papierkorb war bereits leer',
                false
            );
        }
        await loadTrash();
    } catch (e) {
        console.error('Empty trash error:', e);
        if (typeof showSettingsToast === 'function') {
            showSettingsToast('Papierkorb konnte nicht geleert werden', true);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const storageNav = document.querySelector('.settings-nav-item[data-section="storage"]');
    if (storageNav) storageNav.addEventListener('click', loadTrash);
});

window.loadTrash = loadTrash;
window.restoreTrashEntry = restoreTrashEntry;
window.emptyTrash = emptyTrash;
