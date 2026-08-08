// arcade_scanner/server/static/autotag.js
/**
 * Auto-Tagging Rules UI.
 * - saveAutoTagRule(): called from the collection modal — turns the currently
 *   built query (collectionCriteriaNew from collections.js) into a rule.
 * - Settings section: list, toggle, delete, run now.
 */

function saveAutoTagRule() {
    const input = document.getElementById('autoTagName');
    const tag = (input?.value || '').trim().toLowerCase();
    if (!tag) {
        if (typeof showToast === 'function') showToast('Tag-Name fehlt', 'warning');
        return;
    }
    const criteria = (typeof collectionCriteriaNew !== 'undefined' && collectionCriteriaNew)
        ? JSON.parse(JSON.stringify(collectionCriteriaNew)) : null;
    if (!criteria) {
        if (typeof showToast === 'function') showToast('Keine Kriterien gesetzt', 'warning');
        return;
    }
    fetch('/api/autotag/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'create', name: tag, tag: tag, criteria: criteria })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                if (typeof showToast === 'function') showToast(`Auto-Tag-Regel "${tag}" gespeichert`, 'success');
                input.value = '';
            } else {
                if (typeof showToast === 'function') showToast(data.error || 'Speichern fehlgeschlagen', 'error');
            }
        })
        .catch(() => { if (typeof showToast === 'function') showToast('Speichern fehlgeschlagen', 'error'); });
}

function renderAutoTagRules() {
    const list = document.getElementById('autotagRulesList');
    if (!list) return;
    fetch('/api/autotag/rules')
        .then(r => r.json())
        .then(data => {
            const rules = data.rules || [];
            if (!rules.length) {
                list.innerHTML = '<div class="text-sm text-gray-400">Noch keine Regeln — im Collection-Editor eine Query bauen und als Auto-Tag-Regel speichern.</div>';
                return;
            }
            list.innerHTML = rules.map(r => `
                <div id="atrule-${r.id}" class="flex items-center gap-3 p-2 rounded-lg bg-black/5 dark:bg-white/5">
                    <input type="checkbox" ${r.enabled ? 'checked' : ''}
                           onchange="toggleAutoTagRule('${r.id}', this.checked)">
                    <div class="min-w-0 flex-1">
                        <div class="text-sm font-medium truncate">${r.name}</div>
                        <div class="text-xs text-gray-400">Tag: ${r.tag}</div>
                    </div>
                    <button onclick="deleteAutoTagRule('${r.id}')"
                            class="text-xs text-red-400 hover:text-red-300">Löschen</button>
                </div>`).join('');
        })
        .catch(() => { list.innerHTML = '<div class="text-sm text-red-400">Regeln konnten nicht geladen werden.</div>'; });
}

function toggleAutoTagRule(id, enabled) {
    fetch('/api/autotag/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle', id: id, enabled: enabled })
    }).then(() => renderAutoTagRules());
}

function deleteAutoTagRule(id) {
    fetch('/api/autotag/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', id: id })
    }).then(() => renderAutoTagRules());
}

function runAutoTagRules() {
    const btn = document.getElementById('autotagRunBtn');
    if (btn) btn.disabled = true;
    fetch('/api/autotag/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
        .then(r => r.json())
        .then(data => {
            if (typeof showToast === 'function') {
                showToast(data.success ? `${data.total} Tags vergeben` : 'Lauf fehlgeschlagen',
                          data.success ? 'success' : 'error');
            }
        })
        .catch(() => { if (typeof showToast === 'function') showToast('Lauf fehlgeschlagen', 'error'); })
        .finally(() => { if (btn) btn.disabled = false; });
}

window.saveAutoTagRule = saveAutoTagRule;
window.renderAutoTagRules = renderAutoTagRules;
window.toggleAutoTagRule = toggleAutoTagRule;
window.deleteAutoTagRule = deleteAutoTagRule;
window.runAutoTagRules = runAutoTagRules;
