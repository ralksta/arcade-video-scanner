// tests/cinema_error_harness.js
//
// Führt showCinemaPlaybackError() aus cinema.js aus und meldet, was der Kasten
// danach anzeigt.
//
// Der Statuscode der HEAD-Anfrage wird vorgegeben: Genau daran hängt die
// Aussage der Meldung. "reject" steht für eine Anfrage, die gar nicht
// durchkommt.
//
// Aufruf: node cinema_error_harness.js <404|403|200|reject>
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const modus = process.argv[2];

function makeElement() {
    return {
        _text: '',
        classes: new Set(['hidden']),
        set textContent(v) { this._text = String(v); },
        get textContent() { return this._text; },
        classList: {
            add(c) { this._owner.classes.add(c); },
            remove(c) { this._owner.classes.delete(c); },
        },
        style: { setProperty() {} },
        append() {},
        replaceChildren() {},
        addEventListener() {},
    };
}

function element() {
    const el = makeElement();
    el.classList._owner = el;
    return el;
}

const elemente = {
    cinemaPlaybackError: element(),
    cinemaPlaybackErrorText: element(),
    cinemaPlaybackErrorPath: element(),
};

const context = vm.createContext({
    window: { ALL_VIDEOS: [] },
    document: {
        getElementById: (id) => elemente[id] || null,
        createElement: () => element(),
        createTextNode: () => ({}),
        querySelector: () => null,
        addEventListener: () => {},
    },
    console: { log() {}, warn() {}, error() {} },
    availableTags: [],
    escapeHtml: (v) => String(v),
    setTimeout: (fn) => fn && fn(),
    clearTimeout: () => {},
    fetch: (url, opts) => {
        if (modus === 'reject') return Promise.reject(new Error('offline'));
        const status = Number(modus);
        return Promise.resolve({ status, ok: status >= 200 && status < 300, url, opts });
    },
});

vm.runInContext(
    fs.readFileSync(path.join(__dirname, '..', 'arcade_scanner', 'server',
                              'static', 'cinema.js'), 'utf8'),
    context
);

vm.runInContext('showCinemaPlaybackError("/media/urlaub.mp4");', context);

// Der Statuscode kommt aus einem Promise — eine Runde warten.
setTimeout(() => {
    process.stdout.write(JSON.stringify({
        sichtbar: !elemente.cinemaPlaybackError.classes.has('hidden'),
        text: elemente.cinemaPlaybackErrorText.textContent,
        pfad: elemente.cinemaPlaybackErrorPath.textContent,
    }));
}, 10);
