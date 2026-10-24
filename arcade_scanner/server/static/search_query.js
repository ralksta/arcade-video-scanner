// search_query.js — eine Suchsprache für Filterleiste und Collections.
//
// Warum eine eigene Datei:
//   Die Suche wird an vier Stellen ausgewertet (filter_engine.js, treemap.js,
//   collections.js und serverseitig in core/criteria_eval.py). Vorher stand in
//   jeder Kopie derselbe Einzeiler `path.includes(term)`. Damit eine
//   Verbesserung nicht dreimal getippt werden muss, liegt das Parsen und
//   Prüfen hier — der Server und der TV-Client spiegeln dieselbe Regel.
//
// Syntax (alles optional, alte Suchbegriffe funktionieren unverändert):
//   web lena        → beide Begriffe müssen passen (UND)
//   "Lady Sinister" → Phrase mit Leerzeichen
//   -trailer        → Dateien mit „trailer" ausschließen
//   /media/ralf/OD  → Pfadsuche auf Ordnergrenze (trifft nicht /media/ralf/ODX)
//   #urlaub         → Tag-Suche; "#Lady Sinister" für Tags mit Leerzeichen
//
// Mehrere Pfade sind ODER-verknüpft: „/a /b" findet alles unter /a *oder* /b.
// Das entspricht dem, was man beim Anklicken mehrerer Ordner-Chips erwartet;
// Zeigen mehrere Pfade auf denselben Unterbaum, wäre UND immer leer.
// Begriffe, Tags und Pfade zusammen bleiben UND:
//   "/a /b" web  → (unter /a oder /b) und enthält „web"
//
// Groß-/Kleinschreibung und deutsche Umlaute sind egal: „Müller" findet auch
// „muller", „Straße" auch „strasse".

(function () {
    'use strict';

    // --- Normalisierung ---------------------------------------------------

    function foldSearchText(value) {
        return String(value == null ? '' : value)
            .toLowerCase()
            .normalize('NFD')
            // Kombinierende Akzente (U+0300–U+036F) entfernen: ü → u
            .replace(/[̀-ͯ]/g, '')
            // In NFD bleibt ß ein eigener Buchstabe.
            .replace(/ß/g, 'ss');
    }

    /**
     * Pfad-Muster zu einer Regex: `*` steht für beliebig viele Zeichen —
     * auch für `/`. Damit trifft `*<<slash>>web*` jeden Pfad, in dem ein
     * Verzeichnis mit „web" beginnt (web, Web, web_videos, web/Fist …).
     */
    function globToRegExp(pattern) {
        let source = '^';
        for (let i = 0; i < pattern.length; i++) {
            const ch = pattern[i];
            if (ch === '*') {
                source += '.*';
            } else {
                source += ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            }
        }
        return new RegExp(source + '$');
    }

    // --- Parser -----------------------------------------------------------

    /**
     * Zerlegt den Suchtext in Begriffe.
     *
     * @param {string} text
     * @returns {{raw: string, terms: Array, noTerms: boolean}}
     *   `noTerms` ist true, wenn der Text nur aus Leerraum (oder einem
     *   einzelnen „-") besteht. Dann gilt weiterhin die alte Regel: der Text
     *   wird als ein einziger Teilstring gesucht. Das ist wichtig für
     *   Auto-Tag-Regeln — ein versehentlich eingetragenes Leerzeichen darf
     *   nicht plötzlich auf die ganze Bibliothek passen.
     */
    function parseSearchQuery(text) {
        const raw = String(text == null ? '' : text);
        const terms = [];
        let i = 0;

        while (i < raw.length) {
            while (i < raw.length && /\s/.test(raw[i])) i++;
            if (i >= raw.length) break;

            let negated = false;
            if (raw[i] === '-') {
                negated = true;
                i++;
            }

            let value = '';
            if (raw[i] === '"') {
                i++;
                while (i < raw.length) {
                    const ch = raw[i];
                    if (ch === '\\' && (raw[i + 1] === '"' || raw[i + 1] === '\\')) {
                        value += raw[i + 1];
                        i += 2;
                        continue;
                    }
                    if (ch === '"') {
                        i++;
                        break;
                    }
                    value += ch;
                    i++;
                }
            } else {
                const start = i;
                while (i < raw.length && !/\s/.test(raw[i])) i++;
                value = raw.slice(start, i);
            }

            if (!value) continue;

            // "#tag" — ein einzelnes "#" bleibt ein normaler Suchbegriff.
            let isTag = value.charAt(0) === '#';
            let searchValue = isTag ? value.slice(1) : value;
            if (isTag && !searchValue) {
                isTag = false;
                searchValue = value;
            }

            const isPath = !isTag && (searchValue.indexOf('/') !== -1 || searchValue.indexOf('\\') !== -1);
            const folded = foldSearchText(searchValue);
            terms.push({
                value: searchValue,
                folded: folded,
                negated: negated,
                isTag: isTag,
                isPath: isPath,
                glob: (isPath && searchValue.indexOf('*') !== -1)
                    ? globToRegExp(folded.replace(/\\/g, '/'))
                    : null
            });
        }

        return {raw: raw, terms: terms, noTerms: terms.length === 0};
    }

    // --- Pfadvergleich ----------------------------------------------------

    /**
     * Präfix-Vergleich auf Ordnergrenzen. `/a/OD` trifft `/a/OD/x.mp4`, aber
     * weder `/a/ODX/x.mp4` noch `/a/odyssee/x.mp4`.
     *
     * Beide Argumente sind bereits gefaltet.
     */
    function foldedPathMatches(foldedFile, foldedPrefix) {
        const file = foldedFile.replace(/\\/g, '/');
        let prefix = foldedPrefix.replace(/\\/g, '/');
        while (prefix.length > 1 && prefix.endsWith('/')) prefix = prefix.slice(0, -1);
        if (!prefix || prefix === '/') return true;

        let from = 0;
        while (from <= file.length) {
            const idx = file.indexOf(prefix, from);
            if (idx === -1) return false;
            const beforeOk = idx === 0 || file[idx - 1] === '/';
            const after = idx + prefix.length;
            const afterOk = after === file.length || file[after] === '/';
            if (beforeOk && afterOk) return true;
            from = idx + 1;
        }
        return false;
    }

    function pathMatches(filePath, prefix) {
        return foldedPathMatches(foldSearchText(filePath), foldSearchText(prefix));
    }

    // --- Matcher ----------------------------------------------------------
    //
    // Die gefalteten Pfade werden pro Video in WeakMaps gehalten: filterAndSort
    // läuft bei jeder Eingabe über alle Einträge, und normalize() ist der
    // teuerste Teil davon. WeakMap statt Feld am Video, damit wir keine
    // fremden Objekte beschreiben (die Einträge kommen aus JSON und könnten
    // eingefroren sein).

    const pathFoldCache = new WeakMap();
    const nameFoldCache = new WeakMap();

    function foldedFilePath(video) {
        if (!video || typeof video !== 'object') return foldSearchText(video);
        let value = pathFoldCache.get(video);
        if (value === undefined) {
            value = foldSearchText(video.FilePath || '');
            pathFoldCache.set(video, value);
        }
        return value;
    }

    function foldedFileName(video) {
        if (!video || typeof video !== 'object') return '';
        let value = nameFoldCache.get(video);
        if (value === undefined) {
            const path = String(video.FilePath || '');
            const idx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
            value = foldSearchText(idx >= 0 ? path.slice(idx + 1) : path);
            nameFoldCache.set(video, value);
        }
        return value;
    }

    /**
     * Baut eine Prüffunktion für einen Suchtext. Der Text wird genau einmal
     * geparst, nicht einmal pro Video.
     *
     * @param {string} text
     * @returns {(video: Object) => boolean}
     */
    function createSearchMatcher(text) {
        const parsed = parseSearchQuery(text);

        if (parsed.noTerms) {
            if (!parsed.raw) return function () { return true; };
            // Nur Leerraum/„-": alte Teilstring-Regel beibehalten.
            const literal = foldSearchText(parsed.raw);
            return function (video) {
                return foldedFilePath(video).indexOf(literal) !== -1 ||
                    foldedFileName(video).indexOf(literal) !== -1;
            };
        }

        // Positive Pfade sind eine ODER-Gruppe (siehe Kopfkommentar).
        const hasPositivePath = parsed.terms.some(function (term) {
            return term.isPath && !term.negated;
        });

        return function (video) {
            const path = foldedFilePath(video);
            const name = foldedFileName(video);

            const tags = Array.isArray(video.tags) ? video.tags : [];
            let pathHit = !hasPositivePath;

            for (let i = 0; i < parsed.terms.length; i++) {
                const term = parsed.terms[i];
                let hit;
                if (term.isTag) {
                    hit = tags.some(function (tag) {
                        return foldSearchText(tag) === term.folded;
                    });
                } else if (term.glob) {
                    hit = term.glob.test(path.replace(/\\/g, '/'));
                } else if (term.isPath) {
                    hit = foldedPathMatches(path, term.folded);
                } else {
                    hit = name.indexOf(term.folded) !== -1 || path.indexOf(term.folded) !== -1;
                }

                if (term.negated) {
                    if (hit) return false;
                } else if (term.isPath) {
                    if (hit) pathHit = true;
                } else if (!hit) {
                    return false;
                }
            }
            return pathHit;
        };
    }

    // Kleiner Cache, damit evaluateCollectionMatch() pro Video nicht neu parst
    // (Collections werden in Schleifen über die ganze Bibliothek ausgewertet).
    const matcherCache = new Map();
    const MATCHER_CACHE_LIMIT = 8;

    function matcherFor(text) {
        const key = String(text == null ? '' : text);
        let matcher = matcherCache.get(key);
        if (!matcher) {
            if (matcherCache.size >= MATCHER_CACHE_LIMIT) matcherCache.clear();
            matcher = createSearchMatcher(key);
            matcherCache.set(key, matcher);
        }
        return matcher;
    }

    function matchesSearchQuery(video, text) {
        return matcherFor(text)(video);
    }

    // --- Ordner-Vorschläge ------------------------------------------------

    let folderIndexCache = null;
    let folderIndexVideos = null;

    /**
     * Alle bekannten Ordner inklusive Elternpfaden aus ALL_VIDEOS ableiten.
     * Die Datei selbst zählt jeweils in jeden ihrer Elternordner, damit eine
     * Auswahl „/media/ralf/OD" die Anzahl der Dateien im ganzen Unterbaum
     * zeigt.
     *
     * @returns {Array<{path: string, label: string, count: number}>}
     */
    function buildFolderIndex() {
        const videos = window.ALL_VIDEOS || [];
        if (folderIndexCache && folderIndexVideos === videos) return folderIndexCache;

        const map = new Map();
        videos.forEach(function (video) {
            const path = String(video.FilePath || '');
            const sep = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
            if (sep <= 0) return;

            let dir = path.slice(0, sep);
            while (dir) {
                let entry = map.get(dir);
                if (!entry) {
                    entry = {path: dir, count: 0};
                    map.set(dir, entry);
                }
                entry.count++;
                const idx = Math.max(dir.lastIndexOf('/'), dir.lastIndexOf('\\'));
                dir = idx > 0 ? dir.slice(0, idx) : '';
            }
        });

        folderIndexCache = Array.from(map.values()).map(function (entry) {
            const segments = entry.path.split(/[\\/]/).filter(Boolean);
            return {
                path: entry.path,
                label: segments.length ? segments[segments.length - 1] : entry.path,
                count: entry.count,
                folded: foldSearchText(entry.path.replace(/\\/g, '/')),
                foldedLabel: foldSearchText(segments.length ? segments[segments.length - 1] : entry.path)
            };
        });
        folderIndexVideos = videos;
        return folderIndexCache;
    }

    function folderRank(folder, query) {
        if (!query) return 1;
        const q = query.replace(/\\/g, '/');
        if (folder.folded === q || folder.folded.indexOf(q + '/') === 0) return 5;
        if (folder.foldedLabel.indexOf(q) === 0) return 4;
        if (folder.folded.split('/').some(function (segment) {
            return segment.indexOf(q) === 0;
        })) return 3;
        if (folder.folded.indexOf(q) !== -1) return 2;
        return 0;
    }

    /**
     * Ordner, deren Pfad oder Name zum (letzten) Suchbegriff passt.
     *
     * @param {string} query
     * @param {number} [limit=8]
     * @returns {Array<{path: string, label: string, count: number}>}
     */
    function folderSuggestions(query, limit) {
        const max = limit || 8;
        const q = foldSearchText(query || '');
        const items = [];

        buildFolderIndex().forEach(function (folder) {
            const rank = folderRank(folder, q);
            if (rank > 0) items.push({folder: folder, rank: rank});
        });

        items.sort(function (a, b) {
            return (b.rank - a.rank) ||
                (b.folder.count - a.folder.count) ||
                a.folder.path.localeCompare(b.folder.path);
        });

        return items.slice(0, max).map(function (item) {
            return {
                path: item.folder.path,
                label: item.folder.label,
                count: item.folder.count
            };
        });
    }

    /**
     * Nur die obersten Treffer einer Ordnerfrage: Liegt ein Ordner bereits
     * unter einem anderen Treffer, fällt er weg. So liefert „web" fünf
     * Web-Ordner statt zusätzlich noch deren Unterordner (web/Fist usw.).
     * Das ist die Menge für „alle passenden einschließen/ausschließen".
     */
    function getTopLevelFolderSuggestions(query, limit) {
        const all = folderSuggestions(query, limit || 500);
        const kept = [];

        all.forEach(function (item) {
            const path = item.path.replace(/\\/g, '/').replace(/\/+$/, '');
            const covered = kept.some(function (parent) {
                const parentPath = parent.path.replace(/\\/g, '/').replace(/\/+$/, '');
                return path === parentPath || path.indexOf(parentPath + '/') === 0;
            });
            if (!covered) kept.push(item);
        });

        return kept;
    }

    /** Setzt einen Ordnerpfad als Suchbegriff — mit Anführungszeichen, wenn nötig. */
    function quoteSearchTerm(value) {
        const text = String(value == null ? '' : value);
        if (!/\s/.test(text) && text.indexOf('"') === -1) return text;
        return '"' + text.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
    }

    /** Setzt einen Tag als Suchbegriff: #tag bzw. "#tag mit Leerzeichen". */
    function quoteTagTerm(value) {
        return quoteSearchTerm('#' + String(value == null ? '' : value));
    }

    // --- Tag-Vorschläge ---------------------------------------------------

    /**
     * Tags aus den (bereits pro Nutzer gefilterten) Einträgen.
     *
     * Bewusst ohne Cache: Ein Tag lässt sich im Player und in der
     * Mehrfachauswahl ändern, ohne dass ALL_VIDEOS ersetzt wird. Die Suche
     * über ein paar tausend Einträge kostet weniger als eine falsche Liste.
     */
    function tagSuggestions(query, limit) {
        const max = limit || 8;
        const q = foldSearchText(query || '');
        const map = new Map();

        (window.ALL_VIDEOS || []).forEach(function (video) {
            const tags = Array.isArray(video.tags) ? video.tags : [];
            tags.forEach(function (tag) {
                const key = foldSearchText(tag);
                if (!key) return;
                let entry = map.get(key);
                if (!entry) {
                    entry = {value: String(tag), count: 0};
                    map.set(key, entry);
                }
                entry.count++;
            });
        });

        const items = [];
        map.forEach(function (entry, key) {
            let rank = 0;
            if (!q) rank = 1;
            else if (key.indexOf(q) === 0) rank = 2;
            else if (key.indexOf(q) !== -1) rank = 1;
            if (rank > 0) items.push({entry: entry, rank: rank});
        });

        items.sort(function (a, b) {
            return (b.rank - a.rank) ||
                (b.entry.count - a.entry.count) ||
                a.entry.value.localeCompare(b.entry.value);
        });

        return items.slice(0, max).map(function (item) {
            return {
                type: 'tag',
                value: item.entry.value,
                label: '#' + item.entry.value,
                count: item.entry.count
            };
        });
    }

    /**
     * Einheitliche Vorschlagsliste für Filterleiste und Collection-Dialog.
     *
     * Ein führendes „#" schaltet auf Tags um; sonst werden Ordner
     * vorgeschlagen. Der Aufrufer reicht den aktuellen Begriff (ohne
     * Ausschluss-Minus) herein.
     */
    function getSearchSuggestions(query, limit) {
        const text = String(query == null ? '' : query);
        if (text.charAt(0) === '#') {
            return tagSuggestions(text.slice(1), limit);
        }
        return folderSuggestions(text, limit).map(function (item) {
            return {
                type: 'folder',
                value: item.path,
                label: item.label,
                path: item.path,
                count: item.count
            };
        });
    }

    /** Suchtext, der aus einem Vorschlag im Feld landet. */
    function tokenForSuggestion(item) {
        if (!item) return '';
        if (item.type === 'tag') return quoteTagTerm(item.value);
        if (item.type === 'folder') return quoteSearchTerm(item.value);
        return String(item.value || '');
    }

    // --- Exporte (die Seite hat keinen Bundler) ---------------------------

    window.foldSearchText = foldSearchText;
    window.parseSearchQuery = parseSearchQuery;
    window.createSearchMatcher = createSearchMatcher;
    window.matchesSearchQuery = matchesSearchQuery;
    window.pathMatches = pathMatches;
    window.getFolderSuggestions = folderSuggestions;
    window.getSearchSuggestions = getSearchSuggestions;
    window.getTopLevelFolderSuggestions = getTopLevelFolderSuggestions;
    window.tokenForSuggestion = tokenForSuggestion;
    window.quoteSearchTerm = quoteSearchTerm;
    window.quoteTagTerm = quoteTagTerm;
})();
