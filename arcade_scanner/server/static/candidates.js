/**
 * Candidates View — ranks the library by expected re-encode savings.
 * Data: GET /api/candidates (see routes/candidates.py). Queueing reuses
 * POST /api/queue/add like optimizer.js does.
 */

let candState = {
    codec: 'hevc',
    results: [],
    summary: null,
    selected: new Set(),   // file paths
    loading: false,
};

function renderCandidatesView() {
    const grid = document.getElementById('videoGrid');
    if (!grid) return;
    grid.innerHTML = '<div class="p-8 text-center text-gray-400">Analysiere Bibliothek…</div>';
    candState.loading = true;

    fetch(`/api/candidates?codec=${candState.codec}&limit=200`)
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
        })
        .then(data => {
            candState.results = data.results || [];
            candState.summary = data.summary || null;
            candState.selected.clear();
            candState.loading = false;
            _renderCandidates(grid);
        })
        .catch(err => {
            candState.loading = false;
            grid.innerHTML = `<div class="p-8 text-center text-red-400">Kandidaten-Analyse fehlgeschlagen: ${err.message}</div>`;
        });
}

function _fmtGB(mb) {
    return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}

function _candHeader() {
    const s = candState.summary || { total_files: 0, total_estimated_saved_mb: 0, history_based: 0 };
    const codecBtn = (c, label) => `
        <button onclick="setCandidatesCodec('${c}')"
                class="px-3 py-1 rounded text-xs font-bold ${candState.codec === c
                    ? 'bg-arcade-cyan text-black'
                    : 'bg-white/10 text-gray-300 hover:bg-white/20'}">${label}</button>`;
    return `
    <div id="candidatesHeader" class="col-span-full p-4 rounded-xl bg-white/5 mb-2">
        <div class="flex flex-wrap items-center gap-4">
            <div>
                <div class="text-2xl font-bold text-arcade-cyan">~${_fmtGB(s.total_estimated_saved_mb)}</div>
                <div class="text-xs text-gray-400">bis zu ${_fmtGB(s.total_estimated_saved_mb)} Ersparnis möglich (Schätzung) · ${s.total_files} Kandidaten
                     · ${s.history_based} mit echter Encode-Historie</div>
            </div>
            <div class="flex items-center gap-2 ml-auto">
                ${codecBtn('hevc', 'HEVC')}${codecBtn('av1', 'AV1')}
                <button id="candQueueSelectedBtn" onclick="queueSelectedCandidates()"
                        class="px-3 py-1 rounded text-xs font-bold bg-arcade-cyan/20 text-arcade-cyan hover:bg-arcade-cyan/30">
                    Auswahl in Queue (${candState.selected.size})
                </button>
            </div>
        </div>
    </div>`;
}

function _candRow(r, idx) {
    const name = r.file_path.split(/[/\\]/).pop();
    const checked = candState.selected.has(r.file_path) ? 'checked' : '';
    const confColors = { high: 'text-green-400', medium: 'text-yellow-400', low: 'text-gray-400' };
    const confLabel = r.source === 'history' ? 'Historie' : 'Schätzung';
    const thumb = r.thumb ? `<img src="/thumbnails/${r.thumb}" class="w-24 h-14 object-cover rounded" loading="lazy">`
                          : '<div class="w-24 h-14 rounded bg-white/10"></div>';
    return `
    <div id="cand-${idx}" class="col-span-full flex items-center gap-3 p-2 rounded-lg bg-white/5 hover:bg-white/10">
        <input type="checkbox" ${checked} onclick="toggleCandidateSelect(${idx})">
        <div class="cursor-pointer" onclick="openCinema(this)" data-path="${escapeHtml(r.file_path)}">${thumb}</div>
        <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium">${escapeHtml(name)}</div>
            <div class="text-xs text-gray-400">${r.codec.toUpperCase()} · ${r.height}p · ${r.bitrate_mbps.toFixed(1)} Mbit/s · ${_fmtGB(r.size_mb)}</div>
            <div class="text-[11px] text-gray-500">${escapeHtml(r.reason)}</div>
        </div>
        <div class="text-right shrink-0">
            <div class="text-sm font-bold text-arcade-cyan">−${_fmtGB(r.estimated_saved_mb)}</div>
            <div class="text-[11px] ${confColors[r.confidence] || ''}">${r.estimated_saved_pct}% · ${confLabel}</div>
        </div>
        <button onclick="queueCandidate(${idx})"
                class="shrink-0 px-3 py-1.5 rounded text-xs font-bold bg-white/10 hover:bg-arcade-cyan/30">
            In Queue
        </button>
    </div>`;
}

function _renderCandidates(grid) {
    if (!candState.results.length) {
        grid.innerHTML = _candHeader() +
            '<div class="col-span-full p-8 text-center text-gray-400">Keine Kandidaten — Bibliothek sieht gut optimiert aus. 🎉</div>';
        return;
    }
    grid.innerHTML = _candHeader() + candState.results.map(_candRow).join('');
}

function setCandidatesCodec(codec) {
    candState.codec = codec;
    renderCandidatesView();
}

// Übergeben wird der Index in candState.results, nicht der Pfad. Der Umweg über
// encodeURIComponent(pfad) im onclick-Attribut war die Ursache für
// "Kandidaten-Analyse fehlgeschlagen: URI malformed": Dateinamen mit ungültigen
// UTF-8-Bytes kommen aus Pythons surrogateescape als einzelne Surrogate (\udc80–
// \udcff) im JSON an, und encodeURIComponent wirft darauf URIError. Das passierte
// beim Rendern, also riss eine einzige Datei die komplette Ansicht mit.
function toggleCandidateSelect(idx) {
    const r = candState.results[idx];
    if (!r) return;
    const p = r.file_path;
    if (candState.selected.has(p)) candState.selected.delete(p);
    else candState.selected.add(p);
    const btn = document.getElementById('candQueueSelectedBtn');
    if (btn) btn.textContent = `Auswahl in Queue (${candState.selected.size})`;
}

function _queuePaths(paths) {
    let queued = 0, skipped = 0;
    const requests = paths.map(p =>
        fetch('/api/queue/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: p, codec: candState.codec })
        }).then(r => r.json())
          .then(d => { if (d.success) queued++; else skipped++; })
          .catch(() => { skipped++; })
    );
    Promise.all(requests).then(() => {
        if (typeof showToast === 'function') {
            showToast(`${queued} eingereiht${skipped ? `, ${skipped} übersprungen` : ''}`,
                      skipped ? 'warning' : 'success');
        }
        renderCandidatesView();  // queued files drop out server-side
    });
}

function queueCandidate(idx) {
    const r = candState.results[idx];
    if (r) _queuePaths([r.file_path]);
}

function queueSelectedCandidates() {
    if (!candState.selected.size) {
        if (typeof showToast === 'function') showToast('Nichts ausgewählt', 'warning');
        return;
    }
    _queuePaths([...candState.selected]);
}

// Explizite window-Exports (Konvention wie duplicates.js/optimizer.js)
window.renderCandidatesView = renderCandidatesView;
window.setCandidatesCodec = setCandidatesCodec;
window.toggleCandidateSelect = toggleCandidateSelect;
window.queueCandidate = queueCandidate;
window.queueSelectedCandidates = queueSelectedCandidates;
