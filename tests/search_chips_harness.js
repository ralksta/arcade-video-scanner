// tests/search_chips_harness.js
//
// Prüft die Chip-Darstellung im Collection-Dialog ohne Browser: Ein
// gespeicherter Suchtext wird in Ordner-/Tag-Chips und freien Text zerlegt
// und beim Speichern wieder zusammengesetzt.
//
// Usage: node search_chips_harness.js  → JSON mit Testergebnissen
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const staticDir = path.join(__dirname, '..', 'arcade_scanner', 'server', 'static');

function fakeClassList() {
    return {
        add() {},
        remove() {},
        toggle() {},
        contains() { return false; }
    };
}

function fakeNode() {
    return {
        className: '',
        textContent: '',
        id: '',
        title: '',
        type: '',
        dataset: {},
        style: {},
        classList: fakeClassList(),
        setAttribute() {},
        appendChild() {},
        addEventListener() {}
    };
}

const input = {
    value: '',
    selectionStart: 0,
    setAttribute() {},
    addEventListener() {},
    focus() {},
    setSelectionRange() {}
};

const chipsBox = {
    textContent: '',
    classList: fakeClassList(),
    appendChild() {},
    querySelectorAll() { return []; },
    contains() { return false; }
};

const context = vm.createContext({
    window: {},
    document: {
        readyState: 'complete',
        documentElement: {classList: fakeClassList()},
        getElementById(id) {
            if (id === 'collectionSearch') return input;
            if (id === 'collectionSearchChips') return chipsBox;
            return null;
        },
        querySelector() { return null; },
        querySelectorAll() { return []; },
        createElement() { return fakeNode(); },
        addEventListener() {}
    },
    localStorage: {getItem() { return null; }, setItem() {}},
    setTimeout() {},
    clearTimeout() {},
    console,
    Math,
    Date: {now: () => 0}
});

const src = ['safe_storage.js', 'utils.js', 'search_query.js', 'collections.js']
    .map((name) => fs.readFileSync(path.join(staticDir, name), 'utf8'))
    .join('\n');
vm.runInContext(src, context);

const setFromText = vm.runInContext('setCollectionSearchFromText', context);
const getText = vm.runInContext('getCollectionSearchText', context);
const getChips = vm.runInContext('window.getCollectionSearchChips', context);

setFromText('/media/ralf/OD "#Lady Sinister" web -trailer');
const mixed = {
    input: input.value,
    chips: getChips(),
    composed: getText()
};

setFromText('web -trailer');
const freeOnly = {
    input: input.value,
    chips: getChips(),
    composed: getText()
};

setFromText('');
const empty = {
    input: input.value,
    chips: getChips(),
    composed: getText()
};

process.stdout.write(JSON.stringify({mixed, freeOnly, empty}));
