/**
 * Global State Management
 * Replaces loose global variables with a centralized store.
 */

class Store {
    constructor(initialState) {
        this.state = initialState;
        this.listeners = [];
    }

    getState() {
        return this.state;
    }

    /**
     * Update state and notify listeners.
     * @param {Object} partialState - Object to merge into current state.
     * Supports nested updates if partialState structure matches.
     */
    setState(partialState) {
        this.state = this._merge(this.state, partialState);
        this._notify();
    }

    _merge(target, source) {
        if (typeof target !== 'object' || target === null) return source;
        if (typeof source !== 'object' || source === null) return source;

        const result = { ...target };
        for (const key of Object.keys(source)) {
            if (source[key] instanceof Array) {
                result[key] = source[key]; // Arrays are replaced, not merged
            } else if (typeof source[key] === 'object' && source[key] !== null) {
                result[key] = this._merge(target[key], source[key]);
            } else {
                result[key] = source[key];
            }
        }
        return result;
    }

    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    _notify() {
        for (const listener of this.listeners) {
            listener(this.state);
        }
    }
}

// Initial State Definition
const initialState = {
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
        allVideos: [] // Will be populated by API/template
    }
};

window.appStore = new Store(initialState);

// Backwards compatibility proxies
// Objects
Object.defineProperty(window, 'filterState', { get: () => window.appStore.state.filter });
Object.defineProperty(window, 'viewState', { get: () => window.appStore.state.view });
Object.defineProperty(window, 'collectionState', { get: () => window.appStore.state.collection });
Object.defineProperty(window, 'duplicateCheckerState', { get: () => window.appStore.state.duplicateChecker });
Object.defineProperty(window, 'folderBrowserState', { get: () => window.appStore.state.folderBrowser });
Object.defineProperty(window, 'uiState', { get: () => window.appStore.state.ui });

// Legacy aliases (Read/Write)
// Filter Aliases
Object.defineProperty(window, 'currentFilter', {
    get: () => window.appStore.state.filter.status,
    set: (v) => window.appStore.setState({ filter: { status: v } })
});
Object.defineProperty(window, 'currentCodec', {
    get: () => window.appStore.state.filter.codec,
    set: (v) => window.appStore.setState({ filter: { codec: v } })
});
Object.defineProperty(window, 'currentFolder', {
    get: () => window.appStore.state.filter.folder,
    set: (v) => window.appStore.setState({ filter: { folder: v } })
});
Object.defineProperty(window, 'minSizeMB', {
    get: () => window.appStore.state.filter.size.min,
    set: (v) => window.appStore.setState({ filter: { size: { min: v } } })
});
Object.defineProperty(window, 'maxSizeMB', {
    get: () => window.appStore.state.filter.size.max,
    set: (v) => window.appStore.setState({ filter: { size: { max: v } } })
});
Object.defineProperty(window, 'dateFilter', {
    get: () => window.appStore.state.filter.date,
    set: (v) => window.appStore.setState({ filter: { date: v } })
});
Object.defineProperty(window, 'activeTags', {
    get: () => window.appStore.state.filter.tags.active,
    set: (v) => window.appStore.setState({ filter: { tags: { active: v } } })
});
Object.defineProperty(window, 'filterUntaggedOnly', {
    get: () => window.appStore.state.filter.tags.untaggedOnly,
    set: (v) => window.appStore.setState({ filter: { tags: { untaggedOnly: v } } })
});
Object.defineProperty(window, 'searchTerm', {
    get: () => window.appStore.state.filter.search,
    set: (v) => window.appStore.setState({ filter: { search: v } })
});

// View Aliases
Object.defineProperty(window, 'currentLayout', {
    get: () => window.appStore.state.view.layout,
    set: (v) => window.appStore.setState({ view: { layout: v } })
});
Object.defineProperty(window, 'workspaceMode', {
    get: () => window.appStore.state.view.workspace,
    set: (v) => window.appStore.setState({ view: { workspace: v } })
});
Object.defineProperty(window, 'currentSort', {
    get: () => window.appStore.state.view.sort,
    set: (v) => window.appStore.setState({ view: { sort: v } })
});

// Collection Aliases
Object.defineProperty(window, 'activeSmartCollectionCriteria', {
    get: () => window.appStore.state.collection.activeCriteria,
    set: (v) => window.appStore.setState({ collection: { activeCriteria: v } })
});
Object.defineProperty(window, 'activeCollectionId', {
    get: () => window.appStore.state.collection.activeId,
    set: (v) => window.appStore.setState({ collection: { activeId: v } })
});

// UI Aliases
Object.defineProperty(window, 'safeMode', {
    get: () => window.appStore.state.ui.safeMode,
    set: (v) => window.appStore.setState({ ui: { safeMode: v } })
});
Object.defineProperty(window, 'renderedCount', {
    get: () => window.appStore.state.ui.renderedCount,
    set: (v) => window.appStore.setState({ ui: { renderedCount: v } })
});

// Data Aliases
Object.defineProperty(window, 'availableTags', {
    get: () => window.appStore.state.data.availableTags,
    set: (v) => window.appStore.setState({ data: { availableTags: v } })
});
Object.defineProperty(window, 'filteredVideos', {
    get: () => window.appStore.state.data.filteredVideos,
    set: (v) => window.appStore.setState({ data: { filteredVideos: v } })
});

// Folder Browser Aliases
Object.defineProperty(window, 'folderBrowserPath', {
    get: () => window.appStore.state.folderBrowser.currentPath,
    set: (v) => window.appStore.setState({ folderBrowser: { currentPath: v } })
});
