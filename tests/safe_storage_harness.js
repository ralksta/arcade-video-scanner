// tests/safe_storage_harness.js
//
// Lädt store.js in einen node-Kontext, in dem `localStorage` je nach Modus
// funktioniert, wirft oder beschädigten Inhalt trägt — und meldet, was
// `window.safeStorage` daraus macht.
//
// Aufruf: node safe_storage_harness.js <works|throws|safe_mode_on|broken_json>
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const mode = process.argv[2];

function makeStorage() {
    if (mode === 'throws') {
        // Ein gesperrtes localStorage wirft schon beim Lesen — nicht erst
        // beim Schreiben. Genau das macht es beim Laden gefährlich.
        const boom = () => { throw new Error('SecurityError: storage is disabled'); };
        return { getItem: boom, setItem: boom, removeItem: boom };
    }

    const data = {};
    if (mode === 'safe_mode_on') data['safe_mode'] = 'true';
    if (mode === 'broken_json') data['kaputt'] = '{nicht wirklich json';
    if (mode === 'works') data['json'] = JSON.stringify({ a: 1 });

    return {
        getItem: (k) => (k in data ? data[k] : null),
        setItem: (k, v) => { data[k] = String(v); },
        removeItem: (k) => { delete data[k]; },
    };
}

const windowObj = { localStorage: makeStorage() };

// store.js schreibt beim Laden eine Zeile nach stdout. Die Ausgabe dieses
// Harness ist JSON — also alles, was das Skript sagt, nach stderr umleiten.
const quietConsole = {
    log: (...a) => process.stderr.write(a.join(' ') + '\n'),
    warn: (...a) => process.stderr.write(a.join(' ') + '\n'),
    error: (...a) => process.stderr.write(a.join(' ') + '\n'),
};
const context = vm.createContext({ window: windowObj, console: quietConsole, document: {} });

const result = { loaded: false };

try {
    const dir = path.join(__dirname, '..', 'arcade_scanner', 'server', 'static');
    // In der Reihenfolge, in der die Seite sie lädt.
    for (const name of ['safe_storage.js', 'store.js']) {
        vm.runInContext(fs.readFileSync(path.join(dir, name), 'utf8'), context);
    }
    result.loaded = true;
} catch (e) {
    result.error = String(e && e.message);
}

if (result.loaded) {
    const s = windowObj.safeStorage;
    result.safeMode = windowObj.safeMode === true;
    result.get_missing = s.get('gibtsnicht');
    result.get_with_fallback = s.get('gibtsnicht', 'hell');
    result.set_ok = s.set('theme', 'dunkel');
    result.roundtrip = s.get('theme');
    result.json_roundtrip = s.getJSON('json', null);
    result.json_fallback = s.getJSON('kaputt', { ersatz: true });
}

process.stdout.write(JSON.stringify(result));
