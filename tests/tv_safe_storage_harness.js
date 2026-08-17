// tests/tv_safe_storage_harness.js
//
// Führt safeStorage.js aus dem TV-Client in einem node-Kontext aus, in dem
// `window.localStorage` je nach Modus funktioniert, wirft oder gar nicht da
// ist.
//
// Die Datei ist ein ES-Modul; hier werden nur die `export`-Schlüsselwörter
// entfernt, der Rumpf bleibt Zeichen für Zeichen derselbe. Ein Bundler steht
// für einen Test nicht zur Verfügung, und ein nachgebauter Rumpf würde prüfen,
// was der Test selbst geschrieben hat.
//
// Aufruf: node tv_safe_storage_harness.js <works|throws|missing>
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const mode = process.argv[2];

function makeStorage() {
    if (mode === 'missing') return undefined;
    if (mode === 'throws') {
        const boom = () => { throw new Error('SecurityError: storage is disabled'); };
        return {getItem: boom, setItem: boom, removeItem: boom};
    }
    const data = {vorhanden: 'ja'};
    return {
        getItem: (k) => (k in data ? data[k] : null),
        setItem: (k, v) => { data[k] = String(v); },
        removeItem: (k) => { delete data[k]; },
    };
}

const src = fs.readFileSync(
    path.join(__dirname, '..', 'tv_client', 'src', 'safeStorage.js'), 'utf8'
).replace(/^export default[\s\S]*$/m, '')
 .replace(/^export /gm, '');

const context = vm.createContext({
    window: {localStorage: makeStorage()},
    console: {log() {}, warn() {}, error() {}},
});

const result = {loaded: false};
try {
    vm.runInContext(src, context);
    result.loaded = true;
} catch (e) {
    result.error = String(e && e.message);
}

if (result.loaded) {
    const get = vm.runInContext('getItem', context);
    const set = vm.runInContext('setItem', context);
    const remove = vm.runInContext('removeItem', context);

    result.get_existing = get('vorhanden');
    result.get_missing = get('gibtsnicht');
    result.get_fallback = get('gibtsnicht', 'ersatz');
    result.set_ok = set('token', 'abc');
    result.roundtrip = get('token');
    result.remove_ok = remove('token');
    result.after_remove = get('token');
}

process.stdout.write(JSON.stringify(result));
