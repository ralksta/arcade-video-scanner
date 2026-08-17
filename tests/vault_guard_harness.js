// tests/vault_guard_harness.js
// Führt filterAndSort() aus filter_engine.js in einem node-Kontext aus und
// meldet, was danach im Raster steht.
// Aufruf: node vault_guard_harness.js <fixtures.json>
//
// Der Kontext bildet nur nach, was filterAndSort() tatsächlich anfasst: die
// globalen Filterzustände, `window.ALL_VIDEOS`, ein paar Element-Attrappen und
// die Hilfsfunktionen aus anderen Dateien.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const src = fs.readFileSync(
    path.join(__dirname, '..', 'arcade_scanner', 'server', 'static', 'filter_engine.js'),
    'utf8'
);

function fakeElement() {
    return { innerHTML: '', innerText: '', style: {}, classList: { add() {}, remove() {} } };
}

const elements = {};
const rendered = { calls: 0, errors: [] };

const context = vm.createContext({
    window: { ALL_VIDEOS: fixtures.videos, userDataLoaded: fixtures.userDataLoaded },
    document: {
        getElementById: (id) => (elements[id] = elements[id] || fakeElement()),
        querySelector: () => null,
    },
    console,
    location: { reload() {} },

    // Globale Filterzustände, exakt unter den Namen, die filter_engine.js
    // liest. Ein falscher Name fällt nicht auf: filterAndSort() liegt in einem
    // try/catch, das den ReferenceError in einen Toast verwandelt und ein
    // leeres Ergebnis hinterlässt — genau das ist mir beim ersten Versuch
    // passiert, und es sah aus wie ein Filterfehler.
    workspaceMode: fixtures.workspaceMode || 'lobby',
    currentFilter: 'all',
    currentCodec: 'all',
    currentSort: 'name',
    currentFolder: 'all',
    searchTerm: '',
    minSizeMB: null,
    maxSizeMB: null,
    dateFilter: 'all',
    activeTags: [],
    filterUntaggedOnly: false,
    activeSmartCollectionCriteria: null,
    safeMode: false,
    filteredVideos: [],

    // Hilfsfunktionen aus anderen Dateien
    isSensitive: () => false,
    evaluateCollectionMatch: () => true,
    formatSize: (n) => String(n),
    renderUI: () => { rendered.calls += 1; },

    // filterAndSort() liegt in einem try/catch, das jeden Fehler in einen
    // Toast verwandelt und ein leeres Ergebnis hinterlässt. Ein vergessener
    // globaler Name sähe damit aus wie „alles herausgefiltert" — ein Test
    // wäre grün, ohne etwas geprüft zu haben. Deshalb wird der Toast
    // mitgeschrieben und unten zum Fehler gemacht.
    showToast: (message) => { rendered.errors.push(String(message)); },
});

vm.runInContext(src, context);
vm.runInContext('filterAndSort()', context);

if (rendered.errors.length) {
    process.stderr.write(rendered.errors.join('\n') + '\n');
    process.exit(2);
}

process.stdout.write(JSON.stringify({
    renderCalls: rendered.calls,
    shownCount: vm.runInContext('filteredVideos.length', context),
    shownPaths: vm.runInContext('filteredVideos.map(v => v.FilePath || "")', context),
    gridHtml: (elements.videoGrid && elements.videoGrid.innerHTML) || '',
}));
