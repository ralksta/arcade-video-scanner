// tests/search_query_harness.js
//
// Prüft die browser-seitige Suchsprache (static/search_query.js) ohne DOM:
// Parser, Pfadgrenzen und die Ordner-Vorschläge.
//
// Usage: node search_query_harness.js  → JSON mit Testergebnissen
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const source = fs.readFileSync(
    path.join(__dirname, '..', 'arcade_scanner', 'server', 'static', 'search_query.js'),
    'utf8'
);

const context = vm.createContext({window: {}, console});
vm.runInContext(source, context);

// Die Vorschläge werden aus ALL_VIDEOS abgeleitet — erst nach dem Laden setzen,
// damit die Cache-Invalidierung über die Array-Identität greift.
context.window.ALL_VIDEOS = [
    {FilePath: '/media/ralf/OD/ProSessions/Lady Sinister/a.mp4', tags: ['Urlaub', 'Web']},
    {FilePath: '/media/ralf/OD/ProSessions/Lena/b.mp4', tags: ['urlaub']},
    {FilePath: '/media/ralf/OD/web/c.mp4', tags: []},
    {FilePath: '/media/ralf/ODX/d.mp4', tags: []},
    {FilePath: '/media/ralf/Reface/e.mp4', tags: []}
];

const parse = context.window.parseSearchQuery;
const matcher = context.window.createSearchMatcher;
const suggestions = context.window.getFolderSuggestions;
const allSuggestions = context.window.getSearchSuggestions;
const quote = context.window.quoteSearchTerm;
const tokenFor = context.window.tokenForSuggestion;

const boundaryVideo = {FilePath: '/media/ralf/OD/ProSessions/Lena/b.mp4'};
const siblingVideo = {FilePath: '/media/ralf/ODX/d.mp4'};

const result = {
    terms: parse('web lena -trailer "/a b"').terms.map(t => ({
        value: t.value,
        negated: t.negated,
        isPath: t.isPath
    })),
    whitespace: parse('   ').noTerms,
    folderOdBoundary: matcher('/media/ralf/OD')(boundaryVideo),
    folderOdSibling: matcher('/media/ralf/OD')(siblingVideo),
    umlaut: matcher('muller')({FilePath: '/media/Müller/clip.mp4'}),
    andTerms: matcher('prosessions lena')(boundaryVideo),
    andTermsMissing: matcher('prosessions lena')(siblingVideo),
    orPaths: matcher('"/media/ralf/OD" "/media/ralf/Reface"')(boundaryVideo),
    orPathsMiss: matcher('"/media/ralf/NoSuchFolder" "/media/ralf/Reface"')(boundaryVideo),
    orPathsWithKeyword: matcher('"/media/ralf/OD" "/media/ralf/Reface" lena')(boundaryVideo),
    globMatch: matcher('*/web*')({FilePath: '/media/a/web/Fist/x.mp4'}),
    globUnderscore: matcher('*/web*')({FilePath: '/media/a/Lena/web_videos/x.mp4'}),
    globNoSegment: matcher('*/web*')({FilePath: '/media/a/cobweb/x.mp4'}),
    excluded: matcher('-lena')(boundaryVideo),
    suggestionsOd: suggestions('OD', 10).map(s => ({path: s.path, count: s.count})),
    suggestionsPro: suggestions('pro', 10).map(s => s.path),
    suggestionsLady: suggestions('lady', 10).map(s => s.path),
    topFolderCount: suggestions('', 1)[0].count,
    quoteWithSpace: quote('/media/ralf/OD/ProSessions/Lady Sinister'),
    quotePlain: quote('/media/ralf/OD'),
    tagTerms: parse('#urlaub -#web').terms.map(t => ({
        value: t.value,
        isTag: t.isTag,
        isPath: t.isPath,
        negated: t.negated
    })),
    tagSuggestions: allSuggestions('#ur', 8).map(s => ({
        type: s.type,
        value: s.value,
        label: s.label,
        count: s.count
    })),
    tagToken: tokenFor({type: 'tag', value: 'Lady Sinister'}),
    folderToken: tokenFor({type: 'folder', value: '/media/ralf/OD/Pro Sessions'})
};

// Zweite Bibliothek für die Sammel-Aktion: Der Ordner-Cache hängt an der
// Array-Identität, deshalb wird er mit dem neuen Array neu gebaut.
context.window.ALL_VIDEOS = [
    {FilePath: '/media/ralf/OD/ProSessions/Miss Blossom/web/x.mp4'},
    {FilePath: '/media/ralf/OD/ProSessions/Miss Blossom/web/Fist/y.mp4'},
    {FilePath: '/media/ralf/OD/ProSessions/Lena/web_videos/z.mp4'},
    {FilePath: '/media/ralf/OD/ProSessions/Lena/own.mp4'},
    {FilePath: '/media/ralf/OD/ProSessions/One time Sessions/Lady Jenna/Web/w.mp4'}
];
result.topLevelWeb = context.window.getTopLevelFolderSuggestions('web', 10).map(s => s.path);

process.stdout.write(JSON.stringify(result));
