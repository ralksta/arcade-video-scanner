// tests/sensitive_eval_harness.js
// Runs isSensitive() from utils.js against a fixture file.
// Usage: node sensitive_eval_harness.js <fixtures.json>  → JSON array of booleans
//
// utils.js führt beim Laden initTheme() aus, das localStorage, document und
// setTimeout anfasst. Die Attrappen unten reichen dafür — sie stehen hier und
// nicht in der Funktion, weil isSensitive() selbst nichts davon braucht.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// safe_storage.js zuerst: utils.js greift beim Laden über `window.safeStorage`
// auf localStorage zu — in derselben Reihenfolge wie die Seite selbst.
const staticDir = path.join(__dirname, '..', 'arcade_scanner', 'server', 'static');
const src = ['safe_storage.js', 'utils.js']
    .map((name) => fs.readFileSync(path.join(staticDir, name), 'utf8'))
    .join('\n');

const noopElement = { classList: { add() {}, remove() {} }, textContent: '', value: '' };
const context = vm.createContext({
    window: { userSettings: fixtures.userSettings },
    document: {
        documentElement: noopElement.classList ? { classList: noopElement.classList } : {},
        getElementById: () => null,
        querySelector: () => null,
        addEventListener: () => {},
    },
    localStorage: { getItem: () => null, setItem: () => {} },
    setTimeout: () => {},
    console,
});

vm.runInContext(src, context);
const isSensitive = vm.runInContext('isSensitive', context);

const results = fixtures.cases.map(c => {
    try {
        return !!isSensitive(c);
    } catch (e) {
        return `THREW: ${e.message}`;
    }
});
process.stdout.write(JSON.stringify(results));
