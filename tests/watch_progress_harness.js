// tests/watch_progress_harness.js
// Führt watch_progress.js mit einem nachgebauten fetch aus und gibt die
// Beobachtungen als JSON aus. Aufruf: node watch_progress_harness.js
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const src = fs.readFileSync(
    path.join(__dirname, '..', 'arcade_scanner', 'server', 'static', 'watch_progress.js'), 'utf8');

const requests = [];
let now = 1000000;
const serverItems = [
    {path: '/lib/old.mp4', position: 50, duration: 600, watched: false, updated_at: 10},
    {path: '/lib/new.mp4', position: 70, duration: 600, watched: false, updated_at: 20},
    {path: '/lib/done.mp4', position: 0, duration: 600, watched: true, updated_at: 30},
    {path: '/lib/foreign.mp4', position: 70, duration: 600, watched: false, updated_at: 40},
];

const context = vm.createContext({
    window: {},
    navigator: {},
    console,
    Map,
    JSON,
    Blob: class {},
    Date: {now: () => now},
    fetch: (url, opts = {}) => {
        requests.push({url, method: opts.method || 'GET', body: opts.body ? JSON.parse(opts.body) : null});
        return Promise.resolve({ok: true, json: () => Promise.resolve({items: serverItems})});
    },
});
vm.runInContext(src, context);
const w = context.window;

(async () => {
    const out = {};
    out.loaded = await w.loadWatchProgress();
    const videos = ['/lib/old.mp4', '/lib/new.mp4', '/lib/done.mp4'].map(p => ({FilePath: p}));
    out.continueOrder = w.continueWatchingList(videos).map(v => v.FilePath);
    out.resumeOld = w.resumePositionFor('/lib/old.mp4');
    out.resumeDone = w.resumePositionFor('/lib/done.mp4');
    out.ratioNew = w.watchProgressRatio('/lib/new.mp4');

    requests.length = 0;
    w.recordWatchProgress('/lib/a.mp4', 10, 600);
    out.shortPeekRequests = requests.length;
    out.shortPeekStored = w.getWatchProgress('/lib/a.mp4');

    now += 1000;
    w.recordWatchProgress('/lib/old.mp4', 300, 600);
    out.postBody = requests[requests.length - 1].body;
    out.continueAfterRecord = w.continueWatchingList(videos).map(v => v.FilePath);

    w.recordWatchProgress('/lib/new.mp4', 590, 600);
    out.finished = w.getWatchProgress('/lib/new.mp4');

    w.clearWatchProgress('/lib/old.mp4');
    out.clearBody = requests[requests.length - 1].body;
    out.afterClear = w.getWatchProgress('/lib/old.mp4');

    process.stdout.write(JSON.stringify(out));
})();
