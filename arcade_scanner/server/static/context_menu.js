/**
 * context_menu.js — Right-Click Context Menu + Command Palette (⌘K)
 * Arcade Video Scanner UX Batch 2
 */

/* ============================================================
   1. CONTEXT MENU
   ============================================================ */

let _cmCurrentVideo = null;
let _cmEl = null;

function _buildContextMenu() {
    if (_cmEl) return;
    _cmEl = document.createElement('div');
    _cmEl.id = 'arcadeContextMenu';
    _cmEl.innerHTML = `
        <div id="arcadeContextMenuInner" class="
            fixed z-[9900] min-w-[200px] py-1.5 rounded-xl
            bg-[#12012a]/95 border border-white/10
            backdrop-blur-xl shadow-2xl shadow-black/60
            text-sm font-medium
            transition-all duration-150
            opacity-0 scale-95 pointer-events-none
        ">
            <div class="px-3 py-1 text-[10px] uppercase tracking-widest text-gray-500 font-bold border-b border-white/5 mb-1" id="ctxFileName">—</div>
            <button class="ctx-item w-full flex items-center gap-2.5 px-3 py-2 text-gray-200 hover:bg-white/8 hover:text-white transition-colors cursor-pointer rounded-lg mx-1" style="width:calc(100% - 8px)" id="ctx-cinema">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                In Cinema öffnen
            </button>
            <button class="ctx-item w-full flex items-center gap-2.5 px-3 py-2 text-gray-200 hover:bg-white/8 hover:text-white transition-colors cursor-pointer rounded-lg mx-1" style="width:calc(100% - 8px)" id="ctx-favorite">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                <span id="ctx-fav-label">Favorit</span>
            </button>
            <button class="ctx-item w-full flex items-center gap-2.5 px-3 py-2 text-gray-200 hover:bg-white/8 hover:text-white transition-colors cursor-pointer rounded-lg mx-1" style="width:calc(100% - 8px)" id="ctx-locate">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                In Finder zeigen
            </button>
            <div class="border-t border-white/5 my-1"></div>
            <button class="ctx-item w-full flex items-center gap-2.5 px-3 py-2 text-arcade-cyan hover:bg-arcade-cyan/10 transition-colors cursor-pointer rounded-lg mx-1 cinema-action-btn-ctx" style="width:calc(100% - 8px)" id="ctx-optimize">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill="currentColor" fill-opacity="0.2"/><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Optimieren
            </button>
            <button class="ctx-item w-full flex items-center gap-2.5 px-3 py-2 text-purple-400 hover:bg-purple-400/10 transition-colors cursor-pointer rounded-lg mx-1 cinema-action-btn-ctx" style="width:calc(100% - 8px)" id="ctx-gif">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M9 12h3v2.5a2.5 2.5 0 0 1-5 0v-5a2.5 2.5 0 0 1 5 0"/><line x1="14" y1="8" x2="14" y2="16"/><line x1="17" y1="8" x2="19" y2="8"/><line x1="17" y1="12" x2="19" y2="12"/></svg>
                Als GIF exportieren
            </button>
            <div class="border-t border-white/5 my-1"></div>
            <button class="ctx-item w-full flex items-center gap-2.5 px-3 py-2 text-red-400 hover:bg-red-400/10 transition-colors cursor-pointer rounded-lg mx-1" style="width:calc(100% - 8px)" id="ctx-vault">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><circle cx="12" cy="16" r="1" fill="currentColor"/></svg>
                Vault
            </button>
        </div>
    `;
    document.body.appendChild(_cmEl);

    const inner = _cmEl.querySelector('#arcadeContextMenuInner');

    // Wire buttons
    _cmEl.querySelector('#ctx-cinema').addEventListener('click', () => {
        if (_cmCurrentVideo) openCinema(_cmCurrentVideo.FilePath || _cmCurrentVideo.file_path || _cmCurrentVideo.id);
        hideCtxMenu();
    });
    _cmEl.querySelector('#ctx-favorite').addEventListener('click', () => {
        if (_cmCurrentVideo) toggleFavorite(_cmCurrentVideo.id || _cmCurrentVideo.FilePath, _cmEl.querySelector('#ctx-favorite'));
        hideCtxMenu();
    });
    _cmEl.querySelector('#ctx-locate').addEventListener('click', () => {
        if (_cmCurrentVideo) {
            const path = _cmCurrentVideo.FilePath || _cmCurrentVideo.file_path;
            if (path) fetch(`/api/locate?path=${encodeURIComponent(path)}`);
        }
        hideCtxMenu();
    });
    _cmEl.querySelector('#ctx-optimize').addEventListener('click', () => {
        if (_cmCurrentVideo) openOptimizerPanel(_cmCurrentVideo);
        hideCtxMenu();
    });
    _cmEl.querySelector('#ctx-gif').addEventListener('click', () => {
        if (_cmCurrentVideo) openGifPanel(_cmCurrentVideo);
        hideCtxMenu();
    });
    _cmEl.querySelector('#ctx-vault').addEventListener('click', () => {
        if (_cmCurrentVideo) toggleHiddenById(_cmCurrentVideo.id || _cmCurrentVideo.FilePath);
        hideCtxMenu();
    });

    // Close on click outside — use mousedown to not interfere with other click handlers
    document.addEventListener('mousedown', (e) => {
        if (_cmEl && !_cmEl.querySelector('#arcadeContextMenuInner').contains(e.target)) {
            hideCtxMenu();
        }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideCtxMenu(); });
}

function showCtxMenu(e, video) {
    _buildContextMenu();
    _cmCurrentVideo = video;

    const inner = _cmEl.querySelector('#arcadeContextMenuInner');
    const name = (video.FileName || video.file_name || '').replace(/\..+$/, '');
    inner.querySelector('#ctxFileName').textContent = name.length > 26 ? name.slice(0, 26) + '…' : name;
    inner.querySelector('#ctx-fav-label').textContent = video.favorite ? 'Favorit entfernen' : 'Als Favorit markieren';

    // Hide cinema-only buttons for images
    const isVideo = !video.media_type || video.media_type === 'video';
    inner.querySelectorAll('.cinema-action-btn-ctx').forEach(b => b.style.display = isVideo ? '' : 'none');

    // Position
    const vw = window.innerWidth, vh = window.innerHeight;
    const menuW = 210, menuH = 290;
    let x = e.clientX, y = e.clientY;
    if (x + menuW > vw) x = vw - menuW - 8;
    if (y + menuH > vh) y = vh - menuH - 8;

    inner.style.cssText = `position:fixed;left:${x}px;top:${y}px`;
    inner.classList.remove('opacity-0','scale-95','pointer-events-none');
    inner.classList.add('opacity-100','scale-100','pointer-events-auto');
}

function hideCtxMenu() {
    if (!_cmEl) return;
    const inner = _cmEl.querySelector('#arcadeContextMenuInner');
    if (!inner) return;
    inner.classList.add('opacity-0','scale-95','pointer-events-none');
    inner.classList.remove('opacity-100','scale-100','pointer-events-auto');
}

// Attach to video cards via event delegation
document.addEventListener('contextmenu', (e) => {
    const card = e.target.closest('.video-card-container');
    if (!card) return;
    e.preventDefault();
    const videoId = card.dataset.videoId || card.dataset.id;
    const video = window.ALL_VIDEOS && window.ALL_VIDEOS.find(v => 
        String(v.id) === String(videoId) || v.FilePath === videoId
    );
    if (video) showCtxMenu(e, video);
}, false);


/* ============================================================
   2. COMMAND PALETTE (⌘K)
   ============================================================ */

let _cpEl = null;
let _cpOpen = false;

function _buildCommandPalette() {
    if (_cpEl) return;
    _cpEl = document.createElement('div');
    _cpEl.id = 'arcadeCmdPalette';
    _cpEl.innerHTML = `
        <div id="cmdOverlay" class="fixed inset-0 z-[9999] flex items-start justify-center pt-[15vh]
            bg-black/60 backdrop-blur-sm opacity-0 pointer-events-none transition-opacity duration-200">
            <div id="cmdPanel" class="
                w-full max-w-xl mx-4
                bg-[#0d0120]/95 border border-white/10
                rounded-2xl shadow-2xl shadow-black/80
                backdrop-blur-2xl
                overflow-hidden
                transform scale-95 transition-transform duration-200
            ">
                <!-- Search input -->
                <div class="flex items-center gap-3 px-4 py-3.5 border-b border-white/8">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-500 shrink-0">
                        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                    <input id="cmdInput" type="text" placeholder="Suchen oder Aktion eingeben…"
                        class="flex-1 bg-transparent border-0 outline-none text-white text-base placeholder-gray-600 font-medium"
                        autocomplete="off" spellcheck="false">
                    <kbd class="text-[10px] text-gray-600 border border-white/10 rounded px-1.5 py-0.5 font-mono">ESC</kbd>
                </div>
                <!-- Results -->
                <div id="cmdResults" class="max-h-[380px] overflow-y-auto py-2"></div>
                <!-- Footer -->
                <div class="flex items-center gap-4 px-4 py-2.5 border-t border-white/5 text-[11px] text-gray-600">
                    <span><kbd class="border border-white/10 rounded px-1 py-0.5 font-mono">↑↓</kbd> Navigieren</span>
                    <span><kbd class="border border-white/10 rounded px-1 py-0.5 font-mono">↵</kbd> Auswählen</span>
                    <span><kbd class="border border-white/10 rounded px-1 py-0.5 font-mono">ESC</kbd> Schließen</span>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(_cpEl);

    const overlay = _cpEl.querySelector('#cmdOverlay');
    const input = _cpEl.querySelector('#cmdInput');

    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeCmdPalette(); });
    input.addEventListener('input', _renderCmdResults);
    input.addEventListener('keydown', _cmdKeyNav);
}

const CMD_ACTIONS = [
    { icon: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>', label: 'Alle Favoriten anzeigen', action: () => setWorkspaceMode('favorites'), tags: ['favoriten','stars'] },
    { icon: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><circle cx="12" cy="16" r="1" fill="currentColor"/>', label: 'Vault öffnen', action: () => setWorkspaceMode('vault'), tags: ['vault','archiv'] },
    { icon: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>', label: 'Duplikate anzeigen', action: () => setWorkspaceMode('duplicates'), tags: ['duplikat','kopie'] },
    { icon: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill="currentColor" fill-opacity="0.15"/><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>', label: 'Optimizer öffnen', action: () => { if (typeof openOptimizerPanel === 'function') openOptimizerPanel(null); }, tags: ['optimier','compress'] },
    { icon: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>', label: 'Lobby / Alle Videos', action: () => setWorkspaceMode('lobby'), tags: ['lobby','home','alle'] },
    { icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>', label: 'Einstellungen öffnen', action: () => { if (typeof openSettings === 'function') openSettings(); }, tags: ['settings','einstellungen'] },
    { icon: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>', label: 'Versteckte anzeigen', action: () => { const cb = document.getElementById('showHiddenToggle'); if (cb) { cb.checked = !cb.checked; cb.dispatchEvent(new Event('change')); } }, tags: ['hidden','versteckt'] },
];

let _cmdSelectedIdx = -1;

function _renderCmdResults() {
    const q = (_cpEl.querySelector('#cmdInput').value || '').toLowerCase().trim();
    const results = document.getElementById('cmdResults');
    _cmdSelectedIdx = -1;

    // Video search results
    const videos = (window.ALL_VIDEOS || []).filter(v => {
        if (!q) return false;
        return (v.FileName || '').toLowerCase().includes(q);
    }).slice(0, 6);

    // Action search
    const actions = CMD_ACTIONS.filter(a =>
        !q || a.label.toLowerCase().includes(q) || (a.tags || []).some(t => t.includes(q))
    );

    let html = '';

    if (videos.length) {
        html += `<div class="px-3 py-1 text-[10px] uppercase tracking-widest text-gray-600 font-bold">Videos</div>`;
        videos.forEach((v, i) => {
            const name = v.FileName || '—';
            const size = v.Size_MB ? `${v.Size_MB.toFixed(0)} MB` : '';
            html += `
            <button class="cmd-result w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-white/6 transition-colors cursor-pointer group" data-idx="${i}" data-type="video" data-id="${v.id || v.FilePath}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-500 shrink-0 group-hover:text-arcade-cyan transition-colors">
                    <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
                </svg>
                <div class="flex-1 min-w-0">
                    <div class="text-gray-200 text-sm font-medium truncate group-hover:text-white">${name}</div>
                    <div class="text-gray-600 text-[11px] truncate">${v.DirectoryPath || ''}</div>
                </div>
                <span class="text-[11px] text-gray-600 shrink-0">${size}</span>
            </button>`;
        });
    }

    if (actions.length) {
        html += `<div class="px-3 py-1 text-[10px] uppercase tracking-widest text-gray-600 font-bold ${videos.length ? 'mt-1 border-t border-white/5 pt-2' : ''}">Aktionen</div>`;
        actions.forEach((a, i) => {
            html += `
            <button class="cmd-result w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-white/6 transition-colors cursor-pointer group" data-idx="${videos.length + i}" data-type="action" data-action-idx="${CMD_ACTIONS.indexOf(a)}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-gray-500 shrink-0 group-hover:text-arcade-cyan transition-colors">${a.icon}</svg>
                <span class="text-gray-200 text-sm font-medium group-hover:text-white">${a.label}</span>
            </button>`;
        });
    }

    if (!html) {
        html = `<div class="px-4 py-8 text-center text-gray-600 text-sm">Keine Ergebnisse für „${q}"</div>`;
    }

    results.innerHTML = html;

    // Wire click handlers
    results.querySelectorAll('.cmd-result').forEach(btn => {
        btn.addEventListener('click', () => _executeCmdResult(btn));
    });
}

function _executeCmdResult(btn) {
    const type = btn.dataset.type;
    if (type === 'video') {
        const id = btn.dataset.id;
        const v = (window.ALL_VIDEOS || []).find(v => String(v.id) === String(id) || v.FilePath === id);
        if (v) openCinema(v.FilePath || v.file_path || v.id);
    } else if (type === 'action') {
        const ai = parseInt(btn.dataset.actionIdx, 10);
        if (CMD_ACTIONS[ai]) CMD_ACTIONS[ai].action();
    }
    closeCmdPalette();
}

function _cmdKeyNav(e) {
    const results = _cpEl.querySelectorAll('.cmd-result');
    if (!results.length) return;
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        _cmdSelectedIdx = Math.min(_cmdSelectedIdx + 1, results.length - 1);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _cmdSelectedIdx = Math.max(_cmdSelectedIdx - 1, 0);
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (_cmdSelectedIdx >= 0) _executeCmdResult(results[_cmdSelectedIdx]);
        return;
    }
    results.forEach((r, i) => r.classList.toggle('bg-white/6', i === _cmdSelectedIdx));
    if (_cmdSelectedIdx >= 0) results[_cmdSelectedIdx].scrollIntoView({ block: 'nearest' });
}

function openCmdPalette() {
    _buildCommandPalette();
    _cpOpen = true;
    const overlay = _cpEl.querySelector('#cmdOverlay');
    const panel = _cpEl.querySelector('#cmdPanel');
    overlay.classList.remove('pointer-events-none', 'opacity-0');
    overlay.classList.add('opacity-100');
    panel.classList.remove('scale-95');
    panel.classList.add('scale-100');
    const input = _cpEl.querySelector('#cmdInput');
    input.value = '';
    _renderCmdResults();
    requestAnimationFrame(() => input.focus());
}

function closeCmdPalette() {
    if (!_cpEl) return;
    _cpOpen = false;
    const overlay = _cpEl.querySelector('#cmdOverlay');
    const panel = _cpEl.querySelector('#cmdPanel');
    overlay.classList.add('opacity-0', 'pointer-events-none');
    overlay.classList.remove('opacity-100');
    panel.classList.add('scale-95');
    panel.classList.remove('scale-100');
}

// ⌘K / Ctrl+K global shortcut
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        _cpOpen ? closeCmdPalette() : openCmdPalette();
    }
    if (e.key === 'Escape' && _cpOpen) closeCmdPalette();
});
