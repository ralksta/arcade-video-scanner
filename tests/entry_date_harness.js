// tests/entry_date_harness.js
//
// Wertet entryDate() aus utils.js gegen eine Fixture-Datei aus.
//
// utils.js führt beim Laden initTheme() aus, das localStorage, document und
// setTimeout anfasst — deshalb dieselben Attrappen wie in
// sensitive_eval_harness.js, und safe_storage.js davor, in der Reihenfolge der
// Seite.
//
// Aufruf: node entry_date_harness.js <fixtures.json>  → JSON-Array von Zahlen
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

const staticDir = path.join(__dirname, '..', 'arcade_scanner', 'server', 'static');
const src = ['safe_storage.js', 'utils.js']
    .map((name) => fs.readFileSync(path.join(staticDir, name), 'utf8'))
    .join('\n');

const noopClassList = { add() {}, remove() {} };
const context = vm.createContext({
    window: {},
    document: {
        documentElement: { classList: noopClassList },
        getElementById: () => null,
        querySelector: () => null,
        addEventListener: () => {},
    },
    localStorage: { getItem: () => null, setItem: () => {} },
    setTimeout: () => {},
    console,
});

vm.runInContext(src, context);
const entryDate = vm.runInContext('entryDate', context);

process.stdout.write(JSON.stringify(fixtures.cases.map((c) => entryDate(c))));
