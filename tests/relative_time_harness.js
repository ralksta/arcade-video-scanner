// tests/relative_time_harness.js
//
// Wertet formatRelativeTime() aus formatters.js gegen eine Fixture-Datei aus,
// mit festgenageltem Jetzt — sonst hinge das Ergebnis an der Laufzeit des
// Tests.
//
// Aufruf: node relative_time_harness.js <fixtures.json>  → JSON-Array von Texten
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

const src = fs.readFileSync(
    path.join(__dirname, '..', 'arcade_scanner', 'server', 'static', 'formatters.js'),
    'utf8'
);

const context = vm.createContext({
    window: {},
    console,
    Date: { now: () => fixtures.now * 1000 },
    Math,
});

vm.runInContext(src, context);
const formatRelativeTime = vm.runInContext('formatRelativeTime', context);

process.stdout.write(JSON.stringify(fixtures.cases.map((ts) => formatRelativeTime(ts))));
