// tests/cinema_tags_harness.js
//
// Führt updateCinemaTags() aus cinema.js in einem node-Kontext aus und meldet,
// was in den beiden Tag-Behältern landet.
//
// Statt eines echten DOM eine kleine Attrappe: Sie merkt sich, welche Knoten
// angehängt wurden, welchen *Text* sie tragen und welche Attribute gesetzt
// wurden. Genau darauf kommt es an — ein Tag-Name darf als Text ankommen und
// nirgends als Markup oder als Attributinhalt.
//
// Aufruf: node cinema_tags_harness.js <fixtures.json>
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

function makeElement(tag) {
    return {
        tagName: tag,
        className: '',
        title: '',
        _text: '',
        _html: '',
        children: [],
        style: {
            setProperty(name, value) { this[name] = value; },
        },
        listeners: {},
        set textContent(v) { this._text = String(v); },
        get textContent() { return this._text; },
        set innerHTML(v) { this._html = String(v); this.children = []; },
        get innerHTML() { return this._html; },
        setAttribute(name, value) { this[`attr_${name}`] = String(value); },
        addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
        append(...nodes) { this.children.push(...nodes); },
        replaceChildren(...nodes) { this.children = nodes; this._html = ''; },
    };
}

const containers = {
    cinemaAssignedTags: makeElement('div'),
    cinemaTagPicker: makeElement('div'),
};

const document_ = {
    getElementById: (id) => containers[id] || null,
    createElement: makeElement,
    createTextNode: (text) => ({ tagName: '#text', _text: String(text), children: [] }),
    querySelector: () => null,
    addEventListener: () => {},
};

const context = vm.createContext({
    window: { ALL_VIDEOS: [], availableTags: fixtures.availableTags },
    document: document_,
    console: { log() {}, warn() {}, error() {} },
    availableTags: fixtures.availableTags,
    formatSize: (n) => String(n),
    formatDurationLong: (n) => String(n),
    filterAndSort: () => {},
    apiWrite: () => Promise.resolve(null),
    showToast: () => {},
    escapeHtml: (v) => String(v),
    setTimeout: () => {},
    clearTimeout: () => {},
});

vm.runInContext(
    fs.readFileSync(path.join(__dirname, '..', 'arcade_scanner', 'server',
                              'static', 'cinema.js'), 'utf8'),
    context
);

// Den aktuellen Eintrag setzen und rendern.
vm.runInContext('currentCinemaVideo = ' + JSON.stringify(fixtures.video) + ';', context);
vm.runInContext('currentCinemaPath = ' + JSON.stringify(fixtures.video.FilePath) + ';', context);
vm.runInContext('updateCinemaTags();', context);

function describe(el) {
    return {
        html: el.innerHTML,
        // Alles, was als Text ankommt — rekursiv über die angehängten Knoten.
        texts: collectText(el),
        attributes: Object.keys(el).filter((k) => k.startsWith('attr_')),
        hasInlineHandlerMarkup: /onclick=/.test(serialize(el)),
    };
}

function collectText(el, out = []) {
    if (el._text) out.push(el._text);
    (el.children || []).forEach((c) => collectText(c, out));
    return out;
}

function serialize(el) {
    let s = el.innerHTML || '';
    (el.children || []).forEach((c) => { s += serialize(c); });
    return s;
}

process.stdout.write(JSON.stringify({
    assigned: describe(containers.cinemaAssignedTags),
    available: describe(containers.cinemaTagPicker),
}));
