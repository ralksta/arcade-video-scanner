// tests/js_eval_harness.js
// Runs evaluateCollectionMatch from collections.js against a fixture file.
// Usage: node js_eval_harness.js <fixtures.json>   → prints JSON array of booleans
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

// collections.js benutzt entryDate() aus utils.js — dieselbe Regel, die auch
// der Datumsfilter und die Sortierung verwenden. In derselben Reihenfolge
// laden wie die Seite selbst; safe_storage.js zuerst, weil utils.js beim Laden
// über window.safeStorage auf localStorage zugreift.
const staticDir = path.join(__dirname, '..', 'arcade_scanner', 'server', 'static');
const src = ['safe_storage.js', 'utils.js', 'collections.js']
    .map((name) => fs.readFileSync(path.join(staticDir, name), 'utf8'))
    .join('\n');

const FIXED_NOW_MS = fixtures.now * 1000;
const PinnedDate = { now: () => FIXED_NOW_MS };

const noop = { classList: { add() {}, remove() {} }, textContent: '', value: '' };
const context = vm.createContext({
    window: {},
    document: {
        documentElement: { classList: noop.classList },
        getElementById: () => null,
        querySelector: () => null,
        addEventListener: () => {},
    },
    localStorage: { getItem: () => null, setItem: () => {} },
    setTimeout: () => {},
    console,
    Date: PinnedDate,
    Math,
});
vm.runInContext(src, context);

const evaluate = vm.runInContext('evaluateCollectionMatch', context);
const results = fixtures.cases.map(c => !!evaluate(c.video, c.criteria));
process.stdout.write(JSON.stringify(results));
