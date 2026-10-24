// tests/tv_eval_harness.js
//
// Wertet matchesCollectionCriteria aus dem TV-Client (tv_client/src/
// collectionMatch.js) gegen dieselben Fixtures aus wie js_eval_harness.js für
// den Browser-Client.
//
// Das Modul hat bewusst keine Imports; nur die export-Zeile wird entfernt,
// damit es als Skript in einem vm-Kontext läuft. Date.now ist auf die Zeit
// der Fixtures festgenagelt, wie im Browser-Gerüst.
//
// Usage: node tv_eval_harness.js <fixtures.json>  → JSON-Array von Booleans
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const src = fs.readFileSync(
    path.join(__dirname, '..', 'tv_client', 'src', 'collectionMatch.js'),
    'utf8'
);
const script = src.split('\n').filter(line => !/^\s*export\b/.test(line)).join('\n');

const FIXED_NOW_MS = fixtures.now * 1000;
const context = vm.createContext({console, Date: {now: () => FIXED_NOW_MS}});
vm.runInContext(script, context);

const evaluate = vm.runInContext('matchesCollectionCriteria', context);
const results = fixtures.cases.map(c => !!evaluate(c.video, c.criteria));
process.stdout.write(JSON.stringify(results));
