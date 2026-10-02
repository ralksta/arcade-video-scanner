// home_view.js — Startseite: Titelbild und Reihen, wie in der TV-App.
//
// Vorher landete man nach dem Login in einem flachen Raster der ganzen
// Bibliothek, nach Bitrate sortiert. Die Startseite beantwortet stattdessen
// die Fragen, mit denen man eine Mediathek öffnet: Wo war ich? Was ist neu?
// Die Bibliothek mit allen Filtern bleibt in der Lobby.
//
// Die Reihen ignorieren Suche und Filter (wie Home im TV-Client), respektieren
// aber den abgesicherten Modus.

const HOME_ROW_LIMIT = 24;
const HOME_COLLECTION_ROWS = 4;

// Zufall einmal pro Bibliotheksstand würfeln — sonst springen Titelbild und
// „Zufällige Entdeckungen" bei jedem Schließen des Players.
let _homeShuffleKey = null;
let _homeShuffled = [];

function _homeVisibleMedia() {
    return (window.ALL_VIDEOS || []).filter(v =>
        !(window.safeMode && typeof isSensitive === 'function' && isSensitive(v)));
}

function _homeShuffle(videos) {
    const key = videos.length + ':' + (videos[0] && videos[0].FilePath);
    if (key !== _homeShuffleKey) {
        _homeShuffleKey = key;
        _homeShuffled = [...videos];
        for (let i = _homeShuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [_homeShuffled[i], _homeShuffled[j]] = [_homeShuffled[j], _homeShuffled[i]];
        }
    }
    return _homeShuffled;
}

/** Anzeigename: Dateiname ohne Endung. */
function homeTitle(video) {
    const name = String(video.FilePath || '').split(/[\\/]/).pop();
    return name.replace(/\.[^.]+$/, '') || name;
}

function _homeEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
}

function _homeThumb(video) {
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = '';
    if (video.thumb) img.src = '/thumbnails/' + encodeURIComponent(video.thumb);
    return img;
}

/** Spielt `video` ab; ← / → im Player blättern innerhalb von `list`. */
function homePlay(video, list) {
    if (typeof setCinemaPlaylist === 'function') setCinemaPlaylist(list);
    const holder = document.createElement('div');
    holder.setAttribute('data-path', video.FilePath);
    openCinema(holder);
}

function _homeCard(video, list) {
    const card = _homeEl('button', 'home-card');
    card.type = 'button';
    card.setAttribute('data-path', video.FilePath);
    card.title = homeTitle(video);

    const thumb = _homeEl('div', 'home-card-thumb');
    thumb.appendChild(_homeThumb(video));
    if (video.media_type !== 'image' && video.Duration_Sec) {
        thumb.appendChild(_homeEl('span', 'home-card-duration', formatDuration(video.Duration_Sec)));
    }
    const ratio = typeof watchProgressRatio === 'function' ? watchProgressRatio(video.FilePath) : 0;
    if (ratio > 0) {
        const bar = _homeEl('div', 'home-card-progress');
        const fill = _homeEl('span');
        fill.style.width = (ratio * 100).toFixed(1) + '%';
        bar.appendChild(fill);
        thumb.appendChild(bar);
    }
    card.appendChild(thumb);
    card.appendChild(_homeEl('span', 'home-card-title', homeTitle(video)));

    card.addEventListener('click', () => homePlay(video, list));
    return card;
}

function _homeRow(title, videos, {onShowAll = null} = {}) {
    if (!videos.length) return null;
    const row = _homeEl('section', 'home-row');
    const head = _homeEl('div', 'home-row-head');
    head.appendChild(_homeEl('h2', 'home-row-title', title));
    if (onShowAll) {
        const all = _homeEl('button', 'home-row-all', 'Alle anzeigen');
        all.type = 'button';
        all.addEventListener('click', onShowAll);
        head.appendChild(all);
    }
    row.appendChild(head);

    const track = _homeEl('div', 'home-row-track');
    videos.forEach(v => track.appendChild(_homeCard(v, videos)));
    row.appendChild(track);

    // Blättern mit Pfeilen (Desktop); auf Touch-Geräten wischt man.
    ['chevron_left', 'chevron_right'].forEach((icon, i) => {
        const btn = _homeEl('button', 'home-row-scroll ' + (i ? 'is-next' : 'is-prev'));
        btn.type = 'button';
        btn.setAttribute('aria-label', i ? 'Weiter' : 'Zurück');
        btn.appendChild(_homeEl('span', 'material-icons', icon)).setAttribute('aria-hidden', 'true');
        btn.addEventListener('click', () => {
            track.scrollBy({left: (i ? 1 : -1) * track.clientWidth * 0.85, behavior: 'smooth'});
        });
        row.appendChild(btn);
    });
    return row;
}

function _homeHero(video, list) {
    const hero = _homeEl('section', 'home-hero');
    const backdrop = document.createElement('img');
    backdrop.className = 'home-hero-backdrop';
    backdrop.alt = '';
    // Großes Standbild wie im TV-Client; das Vorschaubild ist nur der Notnagel.
    backdrop.src = '/poster?path=' + encodeURIComponent(video.FilePath);
    backdrop.addEventListener('error', () => {
        if (video.thumb && !backdrop.dataset.fallback) {
            backdrop.dataset.fallback = '1';
            backdrop.src = '/thumbnails/' + encodeURIComponent(video.thumb);
        }
    });
    hero.appendChild(backdrop);

    const body = _homeEl('div', 'home-hero-body');
    const resumeAt = typeof resumePositionFor === 'function' ? resumePositionFor(video.FilePath) : 0;
    body.appendChild(_homeEl('div', 'home-hero-kicker', resumeAt ? 'Weiterschauen' : 'Entdecken'));
    body.appendChild(_homeEl('h1', 'home-hero-title', homeTitle(video)));
    const meta = [];
    if (video.Duration_Sec) meta.push(formatDuration(video.Duration_Sec));
    if (typeof entryDate === 'function' && entryDate(video)) {
        meta.push(new Date(entryDate(video) * 1000).toLocaleDateString('de-DE',
            {day: 'numeric', month: 'short', year: 'numeric'}));
    }
    if (meta.length) body.appendChild(_homeEl('div', 'home-hero-meta', meta.join(' · ')));

    const actions = _homeEl('div', 'home-hero-actions');
    const play = _homeEl('button', 'home-hero-play');
    play.type = 'button';
    play.appendChild(_homeEl('span', 'material-icons', 'play_arrow')).setAttribute('aria-hidden', 'true');
    play.appendChild(document.createTextNode(
        resumeAt ? `Fortsetzen bei ${formatDuration(resumeAt)}` : 'Abspielen'));
    play.addEventListener('click', () => homePlay(video, list));
    actions.appendChild(play);

    const library = _homeEl('button', 'home-hero-secondary', 'Zur Bibliothek');
    library.type = 'button';
    library.addEventListener('click', () => setWorkspaceMode('lobby'));
    actions.appendChild(library);
    body.appendChild(actions);
    hero.appendChild(body);
    return hero;
}

function _homeCollectionRows(media) {
    const all = (window.userSettings && window.userSettings.smart_collections) || [];
    const hidden = window.safeMode
        ? (window.userSettings.sensitive_collections || []).map(s => String(s).trim().toLowerCase())
        : [];
    return all
        // Die mitgelieferten Collections („High Bitrate", „Large Files" …) sind
        // Wartungsansichten, keine Reihen für die Startseite.
        .filter(c => c.criteria && (c.criteria.include || c.criteria.exclude)
            && !String(c.id || '').startsWith('col_apps_')
            && !hidden.includes(String(c.name || '').trim().toLowerCase()))
        .map(c => ({
            collection: c,
            items: media.filter(v => evaluateCollectionMatch(v, c.criteria))
                .sort((a, b) => entryDate(b) - entryDate(a)),
        }))
        .filter(x => x.items.length > 0)
        .slice(0, HOME_COLLECTION_ROWS);
}

/** Baut die Startseite neu auf. */
function renderHome() {
    const root = document.getElementById('homeView');
    if (!root) return;

    const media = _homeVisibleMedia();
    const videos = media.filter(v => (v.media_type || 'video') === 'video');
    const images = media.filter(v => v.media_type === 'image');
    const byNewest = (list) => [...list].sort((a, b) => entryDate(b) - entryDate(a));

    root.replaceChildren();

    if (!media.length) {
        const empty = _homeEl('div', 'home-empty');
        empty.appendChild(_homeEl('span', 'material-icons', 'video_library')).setAttribute('aria-hidden', 'true');
        empty.appendChild(_homeEl('h2', null, 'Noch nichts in der Bibliothek'));
        empty.appendChild(_homeEl('p', null,
            'Lege in den Einstellungen fest, welche Ordner gescannt werden.'));
        root.appendChild(empty);
        return;
    }

    const continueList = typeof continueWatchingList === 'function'
        ? continueWatchingList(videos).slice(0, HOME_ROW_LIMIT) : [];
    const recent = byNewest(videos).slice(0, HOME_ROW_LIMIT);
    const favorites = byNewest(videos.filter(v => v.favorite)).slice(0, HOME_ROW_LIMIT);
    const shuffled = _homeShuffle(videos);

    const heroVideo = continueList[0] || shuffled[0];
    if (heroVideo) root.appendChild(_homeHero(heroVideo, continueList.length ? continueList : shuffled));

    const rows = [
        _homeRow('Weiterschauen', continueList),
        _homeRow('Neu hinzugefügt', recent, {onShowAll: () => {
            setWorkspaceMode('lobby');
            setSort('date');
        }}),
        _homeRow('Deine Favoriten', favorites, {onShowAll: () => setWorkspaceMode('favorites')}),
        ..._homeCollectionRows(videos).map(({collection, items}) =>
            _homeRow(collection.name, items.slice(0, HOME_ROW_LIMIT),
                {onShowAll: () => applyCollection(collection.id)})),
        _homeRow('Zufällige Entdeckungen', shuffled.slice(1, HOME_ROW_LIMIT + 1)),
        _homeRow('Neue Bilder', byNewest(images).slice(0, HOME_ROW_LIMIT)),
    ];
    rows.filter(Boolean).forEach(row => root.appendChild(row));
    requestAnimationFrame(_homeMarkScrollableRows);
}

/** Pfeile nur an Reihen, die über den Rand reichen. */
function _homeMarkScrollableRows() {
    document.querySelectorAll('#homeView .home-row').forEach(row => {
        const track = row.querySelector('.home-row-track');
        row.classList.toggle('is-scrollable', track.scrollWidth > track.clientWidth + 1);
    });
}

let _homeResizeTimer = null;
if (typeof window.addEventListener === 'function') {
    window.addEventListener('resize', () => {
        clearTimeout(_homeResizeTimer);
        _homeResizeTimer = setTimeout(_homeMarkScrollableRows, 150);
    });
}

window.renderHome = renderHome;
window.homePlay = homePlay;
