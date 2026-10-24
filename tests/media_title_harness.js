// tests/media_title_harness.js
// Wendet titleFromFileName aus Browser (static/formatters.js) und TV-Client
// (tv_client/src/displayName.js) auf die Fixtures an.
// Aufruf: node media_title_harness.js <fixtures.json> → {"browser": [...], "tv": [...]}
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const root = path.join(__dirname, '..');

function load(file, stripExports) {
    let src = fs.readFileSync(path.join(root, file), 'utf8');
    if (stripExports) src = src.split('\n').filter(l => !/^\s*export\b/.test(l)).join('\n');
    const context = vm.createContext({console});
    vm.runInContext(src, context);
    return vm.runInContext('titleFromFileName', context);
}

const browser = load('arcade_scanner/server/static/formatters.js', false);
const tv = load('tv_client/src/displayName.js', true);
process.stdout.write(JSON.stringify({
    browser: cases.map(([name]) => browser(name)),
    tv: cases.map(([name]) => tv(name)),
}));
