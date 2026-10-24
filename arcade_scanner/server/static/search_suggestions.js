// search_suggestions.js — Vorschlagsliste für Suchfelder.
//
// Ein Controller für beide Felder: die Filterleiste (#mobileSearchInput) und
// den Collection-Dialog (#collectionSearch). Er zeigt Ordner, Tags und die
// zuletzt benutzten Suchbegriffe, bedient sich per Pfeiltasten und übernimmt
// einen Vorschlag entweder als Text (Filterleiste) oder als Chip (Collection).
//
// Die Datenquelle liegt in search_query.js (Ordner- und Tag-Index). Der
// Verlauf gehört zum Konto und wird in `userSettings.search_history`
// gespeichert — nicht in localStorage, damit Konten auf demselben Browser
// keine fremden Ordnerpfade sehen.

(function () {
    'use strict';

    const HISTORY_LIMIT = 8;
    const SUGGESTION_LIMIT = 8;
    const HISTORY_SAVE_DELAY_MS = 1200;

    const boundInputs = new WeakSet();
    let historySaveTimer = null;

    // --- Verlauf (pro Konto) ---------------------------------------------

    function historyStore() {
        if (!window.userSettings) window.userSettings = {};
        if (!Array.isArray(window.userSettings.search_history)) {
            window.userSettings.search_history = [];
        }
        return window.userSettings.search_history;
    }

    function getSearchHistory() {
        return historyStore()
            .filter(function (entry) { return typeof entry === 'string' && entry.trim(); })
            .slice(0, HISTORY_LIMIT);
    }

    function scheduleHistorySave() {
        clearTimeout(historySaveTimer);
        historySaveTimer = setTimeout(function () {
            if (typeof window.saveSettingsWithoutReload === 'function') {
                window.saveSettingsWithoutReload();
            }
        }, HISTORY_SAVE_DELAY_MS);
    }

    function addSearchHistory(entry) {
        const text = String(entry == null ? '' : entry).trim();
        if (!text) return;

        const list = historyStore();
        const lower = text.toLowerCase();
        for (let i = list.length - 1; i >= 0; i--) {
            if (String(list[i]).toLowerCase() === lower) list.splice(i, 1);
        }
        list.unshift(text);
        if (list.length > HISTORY_LIMIT) list.length = HISTORY_LIMIT;
        scheduleHistorySave();
    }

    function clearSearchHistory() {
        historyStore().length = 0;
        scheduleHistorySave();
    }

    // --- Begriff am Cursor -----------------------------------------------

    /**
     * Der Begriff, in dem der Cursor steht — inklusive Ausschluss-Minus und
     * Erkennung von #tag. Anführungszeichen werden für die Vorschlagsfrage
     * entfernt.
     */
    function currentToken(input) {
        const value = input.value || '';
        const cursor = (typeof input.selectionStart === 'number' && input.selectionStart >= 0)
            ? input.selectionStart
            : value.length;
        const before = value.slice(0, cursor);

        let start = 0;
        let inQuotes = false;
        for (let i = 0; i < before.length; i++) {
            const ch = before[i];
            if (ch === '"' && before[i - 1] !== '\\') {
                inQuotes = !inQuotes;
            } else if (!inQuotes && /\s/.test(ch)) {
                start = i + 1;
            }
        }

        let payload = before.slice(start);
        let negated = false;
        if (payload.charAt(0) === '-') {
            negated = true;
            payload = payload.slice(1);
        }

        let inner = payload;
        if (inner.charAt(0) === '"') inner = inner.slice(1);
        if (inner.endsWith('"')) inner = inner.slice(0, -1);

        const isTag = inner.charAt(0) === '#';
        return {
            start: start,
            end: cursor,
            negated: negated,
            isTag: isTag,
            value: isTag ? inner.slice(1) : inner,
            rawIsEmpty: before.slice(start) === ''
        };
    }

    // --- Darstellung ------------------------------------------------------

    function groupLabel(item) {
        if (item.type === 'history' || item.type === 'clear-history') return 'Verlauf';
        if (item.type === 'tag') return 'Tags';
        return 'Ordner';
    }

    function itemIcon(item) {
        if (item.type === 'history') return 'history';
        if (item.type === 'clear-history') return 'history_toggle_off';
        if (item.type === 'tag') return 'label';
        return 'folder';
    }

    function itemSubtitle(item) {
        if (item.type === 'history') return 'Zuletzt gesucht';
        if (item.type === 'tag') return 'Tag';
        return item.path || '';
    }

    function buildItem(item, index, idPrefix, onExclude) {
        const row = document.createElement('div');
        row.className = 'search-suggestion' + (item.type === 'clear-history' ? ' search-suggestion-clear' : '');
        // Die ID muss pro Feld eindeutig sein: Filterleiste und Dialog können
        // gleichzeitig im DOM stehen.
        row.id = idPrefix + '-option-' + index;
        row.dataset.suggestionIndex = String(index);
        row.setAttribute('role', 'option');
        row.setAttribute('aria-selected', 'false');

        const icon = document.createElement('span');
        icon.className = 'material-icons search-suggestion-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = itemIcon(item);

        const text = document.createElement('span');
        text.className = 'search-suggestion-text';

        const label = document.createElement('span');
        label.className = 'search-suggestion-label';
        label.textContent = item.label || item.value || '';

        const sub = document.createElement('span');
        sub.className = 'search-suggestion-path';
        sub.textContent = itemSubtitle(item);

        text.appendChild(label);
        text.appendChild(sub);

        row.appendChild(icon);
        row.appendChild(text);

        if (typeof item.count === 'number') {
            const count = document.createElement('span');
            count.className = 'search-suggestion-count';
            count.textContent = String(item.count);
            row.appendChild(count);
        }

        // Sichtbarer Weg zum Ausschließen: Ein Klick auf die Zeile schließt
        // ein, der Minus-Knopf schließt aus. Vorher musste man erst einen
        // Chip anlegen und ihn dann anklicken — das war nicht auffindbar.
        if ((item.type === 'folder' || item.type === 'tag') && typeof onExclude === 'function') {
            const exclude = document.createElement('button');
            exclude.type = 'button';
            exclude.className = 'search-suggestion-action';
            exclude.title = 'Ausschließen';
            exclude.setAttribute('aria-label', (item.label || item.value) + ' ausschließen');

            const icon = document.createElement('span');
            icon.className = 'material-icons';
            icon.setAttribute('aria-hidden', 'true');
            icon.textContent = 'remove_circle_outline';

            exclude.appendChild(icon);
            exclude.addEventListener('mousedown', function (event) {
                event.preventDefault();
                event.stopPropagation();
                onExclude(index);
            });

            row.appendChild(exclude);
        }

        return row;
    }

    // --- Controller -------------------------------------------------------

    /**
     * Bindet ein Suchfeld an Vorschläge und Verlauf.
     *
     * @param {Object} options
     * @param {string} options.inputId
     * @param {string} options.boxId
     * @param {(item: Object, token: Object) => boolean} [options.onSelect]
     *   Rückgabe true = eigener Umgang (z. B. Chip); der Controller fügt dann
     *   keinen Text ein.
     * @param {(query: string) => void} [options.onEnter]
     * @param {() => void} [options.afterChange]
     */
    function bindSearchSuggestions(options) {
        const input = document.getElementById(options.inputId);
        const box = document.getElementById(options.boxId);
        if (!input || !box || boundInputs.has(input)) return;
        boundInputs.add(input);

        const state = {items: [], index: -1};

        function hide() {
            box.classList.add('hidden');
            input.setAttribute('aria-expanded', 'false');
            input.removeAttribute('aria-activedescendant');
            state.items = [];
            state.index = -1;
        }

        function setActive(index) {
            const rows = box.querySelectorAll('[data-suggestion-index]');
            state.index = index;

            rows.forEach(function (row, i) {
                const active = i === index;
                row.classList.toggle('active', active);
                row.setAttribute('aria-selected', active ? 'true' : 'false');
            });

            if (index >= 0 && rows[index]) {
                input.setAttribute('aria-activedescendant', rows[index].id);
                rows[index].scrollIntoView({block: 'nearest'});
            } else {
                input.removeAttribute('aria-activedescendant');
            }
        }

        function afterChange() {
            if (typeof options.afterChange === 'function') options.afterChange();
        }

        function insertText(text, token, prefixNegation) {
            const prefix = (prefixNegation && token.negated && text.charAt(0) !== '-') ? '-' : '';
            const inserted = prefix + text;
            const before = input.value.slice(0, token.start);
            const after = input.value.slice(token.end);
            input.value = before + inserted + after;

            const pos = before.length + inserted.length;
            input.focus();
            if (input.setSelectionRange) input.setSelectionRange(pos, pos);
        }

        function recordPick(item, token) {
            if (item.type === 'history') {
                addSearchHistory(item.value);
            } else if (item.type === 'folder' || item.type === 'tag') {
                const text = window.tokenForSuggestion ? window.tokenForSuggestion(item) : item.value;
                addSearchHistory((token.negated ? '-' : '') + text);
            }
        }

        function select(index, forceNegated) {
            const item = state.items[index];
            if (!item) return;

            if (item.type === 'clear-history') {
                clearSearchHistory();
                hide();
                render();
                return;
            }

            const token = currentToken(input);
            if (forceNegated) token.negated = true;
            let handled = false;
            if (typeof options.onSelect === 'function') {
                handled = options.onSelect(item, token) === true;
            }

            if (!handled) {
                if (item.type === 'history') {
                    insertText(item.value, token, false);
                } else {
                    const text = window.tokenForSuggestion ? window.tokenForSuggestion(item) : item.value;
                    insertText(text, token, true);
                }
                afterChange();
            }

            recordPick(item, token);
            hide();
        }

        function render() {
            const token = currentToken(input);
            const items = [];

            // Verlauf nur am leeren Begriff: mitten in „web le" wäre er im Weg.
            if (!token.negated && !token.isTag && token.value === '' && getSearchHistory().length) {
                getSearchHistory().slice(0, 5).forEach(function (entry) {
                    items.push({type: 'history', value: entry, label: entry});
                });
                items.push({type: 'clear-history', value: '', label: 'Verlauf löschen'});
            }

            const query = token.isTag ? '#' + token.value : token.value;
            const suggestions = (typeof window.getSearchSuggestions === 'function')
                ? window.getSearchSuggestions(query, SUGGESTION_LIMIT)
                : [];

            for (let i = 0; i < suggestions.length && items.length < SUGGESTION_LIMIT; i++) {
                items.push(suggestions[i]);
            }

            state.items = items;
            state.index = -1;
            input.removeAttribute('aria-activedescendant');

            box.textContent = '';
            if (!items.length) {
                hide();
                return;
            }

            let lastGroup = '';
            items.forEach(function (item, index) {
                const group = groupLabel(item);
                if (group !== lastGroup) {
                    const header = document.createElement('div');
                    header.className = 'search-suggestion-group';
                    header.setAttribute('role', 'presentation');
                    header.textContent = group;
                    box.appendChild(header);
                    lastGroup = group;
                }

                box.appendChild(buildItem(item, index, options.boxId, function (i) {
                    select(i, true);
                }));
            });

            box.classList.remove('hidden');
            input.setAttribute('aria-expanded', 'true');

            // Die Filterleiste hat `overflow-x-hidden` und schneidet damit
            // alles ab, was nach unten herausragt. Dort wird die Liste fest
            // am Viewport positioniert; im Collection-Dialog reicht
            // absolutes Positionieren mit Aufklappen nach oben.
            if (options.fixed && typeof window.innerHeight === 'number') {
                const rect = input.getBoundingClientRect();
                const spaceBelow = window.innerHeight - rect.bottom;
                box.style.position = 'fixed';
                box.style.left = rect.left + 'px';
                box.style.right = 'auto';
                box.style.width = rect.width + 'px';
                if (spaceBelow < 220 && rect.top > spaceBelow) {
                    box.style.top = 'auto';
                    box.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
                } else {
                    box.style.top = (rect.bottom + 4) + 'px';
                    box.style.bottom = 'auto';
                }
            } else if (typeof window.innerHeight === 'number') {
                const rect = input.getBoundingClientRect();
                const spaceBelow = window.innerHeight - rect.bottom;
                box.classList.toggle('drop-up', spaceBelow < 220 && rect.top > spaceBelow);
            }
        }

        if (options.fixed) {
            // Beim Scrollen löst sich eine fest positionierte Liste vom Feld.
            window.addEventListener('scroll', hide, true);
            window.addEventListener('resize', hide);
        }

        input.setAttribute('role', 'combobox');
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-controls', options.boxId);

        input.addEventListener('focus', render);
        input.addEventListener('input', render);
        input.addEventListener('blur', function () {
            // Auf Touch-Geräten kommt das (Kompatibilitäts-)mousedown erst
            // nach dem blur. Ohne Verzögerung wäre der Vorschlag schon weg.
            setTimeout(hide, 150);
        });

        input.addEventListener('keydown', function (event) {
            if (box.classList.contains('hidden')) {
                if (event.key === 'Enter') {
                    const query = input.value.trim();
                    if (query) addSearchHistory(query);
                    if (typeof options.onEnter === 'function') options.onEnter(query);
                }
                return;
            }

            const count = state.items.length;
            if (count === 0) return;

            if (event.key === 'ArrowDown') {
                event.preventDefault();
                setActive((state.index + 1) % count);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                setActive(state.index <= 0 ? count - 1 : state.index - 1);
            } else if (event.key === 'Enter' || event.key === 'Tab') {
                if (state.index >= 0) {
                    event.preventDefault();
                    // Shift+Enter = ausschließen, ohne den Minus-Knopf zu treffen.
                    select(state.index, event.key === 'Enter' && event.shiftKey);
                } else if (event.key === 'Enter') {
                    // Nichts markiert: die getippte Suche selbst merken.
                    const query = input.value.trim();
                    if (query) addSearchHistory(query);
                    if (typeof options.onEnter === 'function') options.onEnter(query);
                }
            } else if (event.key === 'Escape') {
                event.preventDefault();
                hide();
            }
        });

        box.addEventListener('mousedown', function (event) {
            const row = event.target.closest('[data-suggestion-index]');
            if (!row) return;
            event.preventDefault();
            select(parseInt(row.dataset.suggestionIndex, 10));
        });

        document.addEventListener('mousedown', function (event) {
            if (box.classList.contains('hidden')) return;
            if (box.contains(event.target)) return;
            if (event.target === input) return;
            hide();
        });
    }

    // --- Verdrahtung der statischen Felder --------------------------------

    function initSearchSuggestions() {
        bindSearchSuggestions({
            inputId: 'mobileSearchInput',
            boxId: 'mobileSearchSuggestions',
            fixed: true,
            afterChange: function () {
                if (typeof window.onSearchInput === 'function') window.onSearchInput();
            }
        });

        bindSearchSuggestions({
            inputId: 'collectionSearch',
            boxId: 'collectionSearchSuggestions',
            onSelect: function (item, token) {
                if (typeof window.handleCollectionSearchSuggestion === 'function') {
                    return window.handleCollectionSearchSuggestion(item, token);
                }
                return false;
            },
            afterChange: function () {
                if (typeof window.onCollectionSearchInput === 'function') window.onCollectionSearchInput();
            }
        });
    }

    window.bindSearchSuggestions = bindSearchSuggestions;
    window.initSearchSuggestions = initSearchSuggestions;
    window.addSearchHistory = addSearchHistory;
    window.getSearchHistory = getSearchHistory;
    window.clearSearchHistory = clearSearchHistory;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSearchSuggestions);
    } else {
        initSearchSuggestions();
    }
})();
