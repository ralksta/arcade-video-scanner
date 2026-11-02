/**
 * Application State Manager (Redux-lite)
 * Implements a unidirectional data flow with subscribers.
 */

class Store {
    constructor(initialState) {
        this.state = initialState;
        this.listeners = [];
    }

    getState() {
        return this.state;
    }

    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    dispatch(action) {
        const prevState = { ...this.state };
        this.state = this._reduce(this.state, action);
        
        // Notify listeners if state changed
        if (JSON.stringify(prevState) !== JSON.stringify(this.state)) {
            this.listeners.forEach(listener => listener(this.state, prevState, action));
        }
    }

    _reduce(state, action) {
        switch (action.type) {
            case 'SET_FILTER_STATUS':
                return { ...state, filter: { ...state.filter, status: action.payload } };
            case 'SET_CODEC':
                return { ...state, filter: { ...state.filter, codec: action.payload } };
            case 'SET_SEARCH':
                return { ...state, filter: { ...state.filter, search: action.payload } };
            case 'SET_WORKSPACE':
                return { ...state, view: { ...state.view, workspace: action.payload } };
            case 'SET_LAYOUT':
                return { ...state, view: { ...state.view, layout: action.payload } };
            case 'SET_SORT':
                return { ...state, view: { ...state.view, sort: action.payload } };
            case 'SET_SIZE_FILTER':
                return { ...state, filter: { ...state.filter, size: { min: action.payload.min, max: action.payload.max } } };
            case 'SET_DATE_FILTER':
                return { ...state, filter: { ...state.filter, date: action.payload } };
            case 'SET_DB_STATS':
                const tags = Array.isArray(action.payload) ? action.payload : (action.payload?.tags || []);
                return { ...state, data: { ...state.data, availableTags: tags } };
            // Add other reducers as needed
            default:
                return state;
        }
    }
}

// Global instance
window.AppState = new Store({
    filter: {
        status: 'all',
        codec: 'all',
        folder: 'all',
        search: '',
        date: 'all',
        size: { min: null, max: null },
        tags: { active: [], untaggedOnly: false }
    },
    view: {
        layout: 'grid',
        workspace: 'lobby',
        // Neueste zuerst, wie in jeder Mediathek. Vorher 'bitrate' — eine
        // Wartungsfrage als erster Eindruck der Bibliothek.
        sort: 'date'
    },
    collection: {
        activeId: null,
        activeCriteria: null
    },
    duplicateChecker: {
        currentGroupIndex: 0,
        isActive: false
    },
    folderBrowser: {
        currentPath: null,
        showVideosHere: false
    },
    ui: {
        safeMode: window.safeStorage.get('safe_mode') === 'true',
        renderedCount: 0
    },
    data: {
        availableTags: [],
        filteredVideos: [],
        batchSize: 40
    }
});

// For backward compatibility (Deprecated)
// We use Object.defineProperty to map the old globals to the new StateManager
const mapGlobalToState = (globalName, getPath, setAction) => {
    Object.defineProperty(window, globalName, {
        get: () => {
            const keys = getPath.split('.');
            let val = window.AppState.getState();
            for (let k of keys) val = val[k];
            return val;
        },
        set: (val) => {
            if (setAction) {
                window.AppState.dispatch({ type: setAction, payload: val });
            } else {
                console.warn(`Attempted to set read-only global ${globalName}`);
            }
        }
    });
};

mapGlobalToState('currentFilter', 'filter.status', 'SET_FILTER_STATUS');
mapGlobalToState('currentCodec', 'filter.codec', 'SET_CODEC');
mapGlobalToState('searchTerm', 'filter.search', 'SET_SEARCH');
mapGlobalToState('workspaceMode', 'view.workspace', 'SET_WORKSPACE');
mapGlobalToState('currentLayout', 'view.layout', 'SET_LAYOUT');
mapGlobalToState('currentSort', 'view.sort', 'SET_SORT');
mapGlobalToState('dateFilter', 'filter.date', 'SET_DATE_FILTER');
mapGlobalToState('availableTags', 'data.availableTags', 'SET_DB_STATS');

// Provide these for compatibility until everything is refactored
window.minSizeMB = null;
window.maxSizeMB = null;
window.activeTags = [];
window.filterUntaggedOnly = false;
window.activeSmartCollectionCriteria = null;
window.activeCollectionId = null;
window.safeMode = window.safeStorage.get('safe_mode') === 'true';
window.renderedCount = 0;
window.folderBrowserState = { currentPath: null, showVideosHere: false };
window.folderBrowserPath = null;
window.currentFolder = 'all';
window.filteredVideos = [];

// O(1) Pfad-Index über ALL_VIDEOS. Ersetzt lineare .find()-Läufe über 9000+
// Einträge (z.B. bei jedem mouseover im Grid). Baut sich automatisch neu auf,
// sobald ALL_VIDEOS ausgetauscht oder in der Länge verändert wird.
let _cachedVideosRef = null;
let _cachedVideosLen = -1;
let _videosByPath = new Map();

window.rebuildVideoIndex = function () {
    const arr = window.ALL_VIDEOS;
    _videosByPath = new Map();
    if (Array.isArray(arr)) {
        for (let i = 0; i < arr.length; i++) {
            const v = arr[i];
            if (v && v.FilePath) _videosByPath.set(v.FilePath, v);
        }
        _cachedVideosRef = arr;
        _cachedVideosLen = arr.length;
    } else {
        _cachedVideosRef = null;
        _cachedVideosLen = -1;
    }
    return _videosByPath;
};

window.getVideoByPath = function (path) {
    if (!path) return undefined;
    const arr = window.ALL_VIDEOS;
    if (!Array.isArray(arr)) return undefined;
    if (arr !== _cachedVideosRef || arr.length !== _cachedVideosLen) {
        window.rebuildVideoIndex();
    }
    return _videosByPath.get(path);
};

console.log("🚀 Arcade Scanner State Manager Initialized");
