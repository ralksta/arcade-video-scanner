// tests/tv_sort_harness.js
//
// Führt sortVideos() aus dem TV-Client aus. Gleiche Machart wie
// tv_eval_harness.js: MainPanel.js ist ein React-Modul mit Imports und JSX,
// hier wird nur die reine Funktion samt ihrer Hilfsfunktion herausgeschnitten
// und einzeln ausgeführt.
//
// Usage: node tv_sort_harness.js <fixtures.json>  → JSON-Array von Dateinamen
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const src = fs.readFileSync(
    path.join(__dirname, '..', 'tv_client', 'src', 'views', 'MainPanel.js'),
    'utf8'
);

function slice(startMarker, endMarker, label) {
    const start = src.indexOf(startMarker);
    if (start === -1) {
        throw new Error(`${label} nicht gefunden — Signatur geändert?`);
    }
    const end = src.indexOf(endMarker, start);
    if (end === -1) {
        throw new Error(`Ende von ${label} nicht gefunden`);
    }
    return src.slice(start, end + endMarker.length);
}

const helper = slice('const entryDate = (v) =>', ';', 'entryDate');
const sorter = slice('const sortVideos = (list, sortKey) => {', '\n};', 'sortVideos');

const context = vm.createContext({console});
vm.runInContext(`${helper}\n${sorter}`, context);

const sortVideos = vm.runInContext('sortVideos', context);
const result = sortVideos(fixtures.videos, fixtures.sortKey);

process.stdout.write(JSON.stringify(result.map(v => v._fileName)));
