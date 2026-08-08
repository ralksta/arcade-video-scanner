// tests/js_eval_harness.js
// Runs evaluateCollectionMatch from collections.js against a fixture file.
// Usage: node js_eval_harness.js <fixtures.json>   → prints JSON array of booleans
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const src = fs.readFileSync(
    path.join(__dirname, '..', 'arcade_scanner', 'server', 'static', 'collections.js'),
    'utf8'
);

const FIXED_NOW_MS = fixtures.now * 1000;
const PinnedDate = { now: () => FIXED_NOW_MS };

const context = vm.createContext({ window: {}, console, Date: PinnedDate, Math });
vm.runInContext(src, context);

const evaluate = vm.runInContext('evaluateCollectionMatch', context);
const results = fixtures.cases.map(c => !!evaluate(c.video, c.criteria));
process.stdout.write(JSON.stringify(results));
