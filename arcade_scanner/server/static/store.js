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
                return { ...state, data: { ...state.data, availableTags: action.payload.tags } };
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
        sort: 'bitrate'
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
        safeMode: localStorage.getItem('safe_mode') === 'true',
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
window.safeMode = localStorage.getItem('safe_mode') === 'true';
window.renderedCount = 0;
window.folderBrowserPath = null;
window.filteredVideos = [];

console.log("🚀 Arcade Scanner State Manager Initialized");
