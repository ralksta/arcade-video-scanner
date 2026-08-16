// tests/tv_eval_harness.js
//
// Wertet matchesCollectionCriteria aus dem TV-Client gegen dieselben Fixtures
// aus wie js_eval_harness.js für den Browser-Client.
//
// MainPanel.js ist ein React-Modul mit Imports und JSX; hier wird nur die
// Matcher-Funktion herausgeschnitten und einzeln ausgeführt. Sie hängt an
// nichts außer ihren beiden Argumenten — genau das macht diese Prüfung
// überhaupt möglich.
//
// Usage: node tv_eval_harness.js <fixtures.json>  → JSON-Array von Booleans
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const src = fs.readFileSync(
    path.join(__dirname, '..', 'tv_client', 'src', 'views', 'MainPanel.js'),
    'utf8'
);

const START = 'const matchesCollectionCriteria = (v, criteria) => {';
const startIndex = src.indexOf(START);
if (startIndex === -1) {
    throw new Error('matchesCollectionCriteria nicht gefunden — Signatur geändert?');
}

// Bis zur schließenden Klammer der Zuweisung: Klammern zählen ab dem ersten `{`.
let depth = 0;
let endIndex = -1;
for (let i = startIndex + START.length - 1; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') {
        depth--;
        if (depth === 0) { endIndex = i + 1; break; }
    }
}
if (endIndex === -1) {
    throw new Error('Ende von matchesCollectionCriteria nicht gefunden');
}

const fnSource = src.slice(startIndex, endIndex) + ';';

const context = vm.createContext({ console });
vm.runInContext(fnSource, context);

const evaluate = vm.runInContext('matchesCollectionCriteria', context);
const results = fixtures.cases.map(c => !!evaluate(c.video, c.criteria));
process.stdout.write(JSON.stringify(results));
