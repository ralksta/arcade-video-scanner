// folder_browser.js - Extracted from engine.js

// --- FOLDER SIDEBAR ---

/**
 * Toggle the folder sidebar visibility
 */
function toggleFolderSidebar() {
    document.getElementById('folderSidebar').classList.toggle('active');
    renderFolderSidebar();
}

/**
 * Set the folder filter to show only videos from a specific directory
 * @param {string} folder - Folder path or 'all' for no filter
 */
function setFolderFilter(folder) {
    currentFolder = folder;
    filterAndSort();
    renderFolderSidebar();
}

/**
 * Initial render call for folder sidebar
 */
function initialRender() {
    renderFolderSidebar();
}

/**
 * Render the folder sidebar with folder list sorted by size
 */
function buildFoldersData() {
    // Früher kam diese Aggregation fertig aus dem Server-Template. Der
    // HTML-Dump wird aber EINMAL erzeugt und an jeden Nutzer ausgeliefert —
    // damit standen die Ordnerpfade aller Bibliotheken in der Seite, die jeder
    // bekam, obwohl /api/videos anschließend sauber nach Scan-Zielen filtert.
    // ALL_VIDEOS ist bereits pro Nutzer gefiltert, also aggregieren wir hier.
    const data = {};
    (window.ALL_VIDEOS || []).forEach(video => {
        const path = video.FilePath || '';
        const separator = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        const folder = separator > 0 ? path.slice(0, separator) : path;
        if (!folder) return;

        if (!data[folder]) data[folder] = { count: 0, size_mb: 0 };
        data[folder].count += 1;
        data[folder].size_mb += video.Size_MB || 0;
    });
    window.FOLDERS_DATA = data;
    return data;
}

function renderFolderSidebar() {
    const list = document.getElementById('folderList');
    if (!list.parentElement.classList.contains('active')) return;

    const foldersData = buildFoldersData();

    list.innerHTML = '';
    const folders = Object.keys(foldersData).sort((a, b) => foldersData[b].size_mb - foldersData[a].size_mb);
    if (folders.length === 0) return;
    const maxSize = Math.max(...Object.values(foldersData).map(f => f.size_mb));

    const allItem = document.createElement('div');
    allItem.className = `folder-item ${currentFolder === 'all' ? 'active' : ''}`;
    allItem.onclick = () => setFolderFilter('all');
    allItem.innerHTML = `<div class="folder-name">ALLE ORDNER</div><div class="folder-meta"><span>Gesamte Bibliothek</span></div>`;
    list.appendChild(allItem);

    folders.forEach(path => {
        const data = foldersData[path];
        const item = document.createElement('div');
        item.className = `folder-item ${currentFolder === path ? 'active' : ''}`;
        item.onclick = () => setFolderFilter(path);

        const relWidth = (data.size_mb / maxSize) * 100;
        const folderName = path.split(/[\\\\/]/).pop() || path;

        item.innerHTML = `
            <div class="folder-name" title="${escapeHtml(path)}">${escapeHtml(folderName)}</div>
            <div class="folder-meta">
                <span>${data.count} Videos</span>
                <span>${formatSize(data.size_mb)}</span>
            </div>
            <div class="folder-progress"><div class="folder-progress-fill" style="width: ${relWidth}%"></div></div>
        `;
        list.appendChild(item);
    });
}

/**
 * Reset all filters and return to default dashboard view
 */
function resetDashboard() {
    currentFilter = 'all';
    currentCodec = 'all';
    currentSort = 'bitrate';
    currentFolder = 'all';
    searchTerm = '';

    // Reset UI elements
    document.getElementById('mobileSearchInput').value = '';
    const cs = document.getElementById('codecSelect');
    if (cs) cs.value = 'all';
    
    // Reset codec & status chips
    if (typeof setFilterOption === 'function') {
        setFilterOption('codec', 'all');
        setFilterOption('status', 'all');
    }

    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) sortSelect.value = 'bitrate';

    // Reset internal state and re-render
    setFilter('all');
    setWorkspaceMode('lobby');
    renderFolderSidebar(); // This will refresh the folder list UI
}

// --- FOLDER BROWSER ---

/**
 * Get subfolders at a given path based on filteredVideos (respects current filters)
 * @param {string|null} path - Parent path (null for root level)
 * @returns {Array} Array of folder objects: {path, name, count, size_mb, hasSubfolders, thumbnails}
 */
function getSubfoldersAt(path) {
    const normalizePath = (p) => p.replace(/\\/g, '/');
    const normalizedPath = path ? normalizePath(path) : null;

    // Build folder stats from filteredVideos (respects current workspace/filters)
    const folderStats = new Map();

    filteredVideos.forEach(video => {
        const lastIdx = Math.max(video.FilePath.lastIndexOf('/'), video.FilePath.lastIndexOf('\\'));
        if (lastIdx < 0) return;

        const videoDir = video.FilePath.substring(0, lastIdx);
        const normalizedVideoDir = normalizePath(videoDir);

        if (!folderStats.has(normalizedVideoDir)) {
            folderStats.set(normalizedVideoDir, {
                originalPath: videoDir,
                count: 0,
                size_mb: 0
            });
        }
        const stats = folderStats.get(normalizedVideoDir);
        stats.count++;
        stats.size_mb += video.Size_MB || 0;
    });

    const allPaths = Array.from(folderStats.keys());
    const subfolders = new Map();

    // Root und Kind-Ebene laufen über denselben Code: die nächste Ebene wird immer
    // aus den Pfadsegmenten abgeleitet. Wichtig für Zwischenordner, die selbst keine
    // Dateien enthalten (z.B. /media_ralf) — die wären sonst gar keine eigene Ebene.
    const isRoot = normalizedPath === null;
    const prefix = isRoot ? '' : normalizedPath + '/';

    allPaths.forEach(folderPath => {
        if (!folderPath.startsWith(prefix)) return;

        let remainder = folderPath.substring(prefix.length);

        // Auf Root-Ebene den Mount-Slash abtrennen ('/media_ralf/OD' → 'media_ralf/OD'),
        // damit das erste Segment nicht leer ist.
        let leading = '';
        if (isRoot) {
            const match = remainder.match(/^\/+/);
            if (match) {
                leading = match[0];
                remainder = remainder.substring(match[0].length);
            }
        }

        const nextSegment = remainder.split('/')[0];
        if (!nextSegment) return;

        const childPath = isRoot ? leading + nextSegment : normalizedPath + '/' + nextSegment;

        if (!subfolders.has(childPath)) {
            // Original-Schreibweise (Backslashes) rekonstruieren: Normalisierung
            // ersetzt nur '\' durch '/', die Länge bleibt identisch.
            const stats = folderStats.get(folderPath);
            subfolders.set(childPath, {
                path: stats.originalPath.substring(0, childPath.length),
                count: 0,
                size_mb: 0,
                hasSubfolders: false
            });
        }

        const folder = subfolders.get(childPath);
        const stats = folderStats.get(folderPath);
        folder.count += stats.count;
        folder.size_mb += stats.size_mb;

        // Gibt es unterhalb dieses Kindes noch tiefere Ordner?
        if (remainder.includes('/')) {
            folder.hasSubfolders = true;
        }
    });

    // Convert to array, add names, and sort by size
    const result = Array.from(subfolders.values()).map(folder => ({
        ...folder,
        name: folder.path.split(/[\\/]/).pop() || folder.path
    }));

    // Get thumbnails for each folder (from filteredVideos)
    result.forEach(folder => {
        folder.thumbnails = getThumbnailsForFolder(folder.path, 4);
    });

    // Sort by size descending
    result.sort((a, b) => b.size_mb - a.size_mb);

    return result;
}

/**
 * Get videos whose directory exactly matches the given path (not in subfolders)
 * @param {string} path - Folder path
 * @returns {Array} Array of video objects
 */
function getVideosDirectlyIn(path) {
    if (!path) return [];

    const normalizePath = (p) => p.replace(/\\/g, '/');
    const normalizedPath = normalizePath(path);

    return filteredVideos.filter(v => {
        const videoDir = normalizePath(v.FilePath.substring(0, Math.max(
            v.FilePath.lastIndexOf('/'),
            v.FilePath.lastIndexOf('\\')
        )));
        return videoDir === normalizedPath;
    });
}

/**
 * Get videos that are within the given path (including subfolders)
 * @param {string} path - Folder path
 * @returns {Array} Array of video objects
 */
function getVideosUnderPath(path) {
    if (!path) return filteredVideos;

    const normalizePath = (p) => p.replace(/\\/g, '/');
    const normalizedPath = normalizePath(path);

    return filteredVideos.filter(v => {
        const normalizedFilePath = normalizePath(v.FilePath);
        return normalizedFilePath.startsWith(normalizedPath + '/') ||
            normalizePath(v.FilePath.substring(0, Math.max(
                v.FilePath.lastIndexOf('/'),
                v.FilePath.lastIndexOf('\\')
            ))) === normalizedPath;
    });
}

/**
 * Get first N thumbnail paths for videos in a folder (recursive)
 * @param {string} path - Folder path
 * @param {number} count - Number of thumbnails to get
 * @returns {Array} Array of thumbnail paths
 */
function getThumbnailsForFolder(path, count = 4) {
    const videos = getVideosUnderPath(path);
    return videos
        .filter(v => v.thumb)
        .slice(0, count)
        .map(v => v.thumb);
}

/**
 * Get folder statistics (count, size) for all videos under a path
 * @param {string} path - Folder path
 * @returns {Object} {count, size_mb}
 */
function getFolderStats(path) {
    const videos = getVideosUnderPath(path);
    return {
        count: videos.length,
        size_mb: videos.reduce((sum, v) => sum + (v.Size_MB || 0), 0)
    };
}

/**
 * Set the folder browser path and re-render
 * @param {string|null} path - Folder path or null for root
 */
function setFolderBrowserPath(path) {
    folderBrowserState.currentPath = path;
    folderBrowserState.showVideosHere = false;
    folderBrowserPath = path;

    if (currentLayout === 'folderbrowser') {
        renderFolderBrowser();
        updateURL();
    }
}

/**
 * Go up one level in the folder browser
 */
function folderBrowserBack() {
    if (folderBrowserState.showVideosHere) {
        // If showing videos, go back to folder view
        folderBrowserState.showVideosHere = false;
        renderFolderBrowser();
        updateURL();
        return;
    }

    if (!folderBrowserState.currentPath) return; // Already at root

    const normalizePath = (p) => p.replace(/\\/g, '/');
    const normalized = normalizePath(folderBrowserState.currentPath);
    const lastSlash = normalized.lastIndexOf('/');

    if (lastSlash > 0) {
        // Eine Ebene hoch. Der Parent ist immer eine gültige Ebene, auch wenn er
        // selbst keine Dateien enthält — getSubfoldersAt() leitet Ebenen aus den
        // Pfadsegmenten ab.
        const parentPath = folderBrowserState.currentPath.substring(0,
            Math.max(folderBrowserState.currentPath.lastIndexOf('/'),
                folderBrowserState.currentPath.lastIndexOf('\\')));

        setFolderBrowserPath(parentPath);
    } else {
        // Mount-Ebene ('/media_ralf') → zurück zur Übersicht
        setFolderBrowserPath(null);
    }
}

/**
 * Toggle showing videos at current folder path
 */
function toggleFolderBrowserVideos() {
    folderBrowserState.showVideosHere = !folderBrowserState.showVideosHere;
    renderFolderBrowser();
}

/**
 * Build breadcrumb segments from current path
 * @returns {Array} Array of {name, path} objects
 */
function getFolderBreadcrumbs() {
    const breadcrumbs = [{ name: 'All Folders', path: null }];

    if (!folderBrowserState.currentPath) return breadcrumbs;

    // Direkt aus den Pfadsegmenten aufbauen — jede Ebene ist anklickbar, auch
    // Zwischenordner ohne eigene Dateien.
    const original = folderBrowserState.currentPath;
    const normalized = original.replace(/\\/g, '/');

    // Führenden Slash als Teil des ersten Segments behalten ('/media_ralf')
    const leading = (normalized.match(/^\/+/) || [''])[0];
    const segments = normalized.substring(leading.length).split('/').filter(Boolean);

    // Jede Ebene ist ein Präfix des Originalpfads — dadurch bleibt die
    // Original-Schreibweise (Backslashes unter Windows) automatisch erhalten.
    let end = leading.length;
    segments.forEach((segment, idx) => {
        end += segment.length + (idx === 0 ? 0 : 1);
        breadcrumbs.push({ name: segment, path: original.substring(0, end) });
    });

    return breadcrumbs;
}

/**
 * Create a folder card element
 * @param {Object} folder - Folder data {path, name, count, size_mb, hasSubfolders, thumbnails}
 * @returns {HTMLElement} DOM element for the folder card
 */
function createFolderCard(folder) {
    const container = document.createElement('div');
    container.className = 'group relative w-full bg-card rounded-ds-md overflow-hidden border border-[var(--ds-hairline)] hover:border-[var(--ds-hairline-strong)] transition-colors duration-200 folder-card cursor-pointer';
    container.setAttribute('data-path', folder.path);

    // Create 2x2 mosaic of thumbnails
    const thumbs = folder.thumbnails || [];
    let mosaicHtml = '';
    for (let i = 0; i < 4; i++) {
        if (thumbs[i]) {
            mosaicHtml += `<div class="bg-black overflow-hidden"><img src="/thumbnails/${thumbs[i]}" class="w-full h-full object-cover opacity-70 group-hover:opacity-90 transition-opacity" loading="lazy"></div>`;
        } else {
            mosaicHtml += `<div class="bg-gray-900/50 flex items-center justify-center"><span class="material-icons text-gray-700 text-2xl" aria-hidden="true">folder</span></div>`;
        }
    }

    container.innerHTML = `
        <!-- Thumbnail Mosaic -->
        <div class="folder-card-mosaic aspect-video grid grid-cols-2 grid-rows-2 gap-0.5 bg-black/50">
            ${mosaicHtml}
        </div>

        <!-- Folder Info Overlay -->
        <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none"></div>

        <!-- Folder Icon Badge -->
        <div class="absolute top-3 left-3 w-10 h-10 rounded-lg bg-arcade-cyan/20 backdrop-blur flex items-center justify-center border border-arcade-cyan/30">
            <span class="material-icons text-arcade-cyan" aria-hidden="true">${folder.hasSubfolders ? 'folder' : 'folder_open'}</span>
        </div>

        <!-- Subfolder Indicator -->
        ${folder.hasSubfolders ? `
        <div class="absolute top-3 right-3 px-2 py-1 rounded-md bg-ink/10 backdrop-blur text-[10px] font-bold text-gray-300 flex items-center gap-1">
            <span class="material-icons text-xs" aria-hidden="true">subdirectory_arrow_right</span>
            HAS SUBFOLDERS
        </div>
        ` : ''}

        <!-- Content -->
        <div class="absolute bottom-0 left-0 right-0 p-4">
            <h3 class="text-base font-bold text-text-main truncate group-hover:text-arcade-cyan transition-colors" title="${escapeHtml(folder.path)}">${escapeHtml(folder.name)}</h3>
            <div class="flex items-center gap-3 mt-1 text-xs text-gray-400">
                <span class="flex items-center gap-1">
                    <span class="material-icons text-sm" aria-hidden="true">video_library</span>
                    ${folder.count} videos
                </span>
                <span class="flex items-center gap-1">
                    <span class="material-icons text-sm" aria-hidden="true">storage</span>
                    ${formatSize(folder.size_mb)}
                </span>
            </div>
        </div>

        <!-- Hover Action Indicator -->
        <div class="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
            <div class="w-14 h-14 rounded-full bg-arcade-cyan/20 border border-arcade-cyan/50 flex items-center justify-center backdrop-blur">
                <span class="material-icons text-arcade-cyan text-3xl" aria-hidden="true">${folder.hasSubfolders ? 'folder_open' : 'play_arrow'}</span>
            </div>
        </div>
    `;

    // Click handler
    container.addEventListener('click', () => {
        setFolderBrowserPath(folder.path);
    });

    return container;
}

/**
 * Breakpoint check — unterhalb von md (768px) wird die kompakte Listendarstellung
 * benutzt. Muss zum `md:`-Breakpoint der Templates passen.
 * @returns {boolean} True auf schmalen Viewports
 */
function isCompactFolderView() {
    return window.innerWidth < 768;
}

/**
 * Create a compact folder row for mobile — ein Ordner pro Zeile statt
 * bildschirmfüllender Karte, damit man sich durch Ebenen klicken kann.
 * @param {Object} folder - Folder data {path, name, count, size_mb, hasSubfolders, thumbnails}
 * @returns {HTMLElement} DOM element for the folder row
 */
function createFolderRow(folder) {
    const row = document.createElement('div');
    row.className = 'folder-row folder-card flex items-center gap-3 w-full bg-card rounded-ds-md border border-[var(--ds-hairline)] active:border-[var(--ds-hairline-strong)] transition-colors cursor-pointer';
    row.setAttribute('data-path', folder.path);

    const thumb = (folder.thumbnails || [])[0];
    const thumbHtml = thumb
        ? `<img src="/thumbnails/${thumb}" class="w-full h-full object-cover" loading="lazy">`
        : `<span class="material-icons text-gray-600 text-xl" aria-hidden="true">folder</span>`;

    row.innerHTML = `
        <div class="folder-row-thumb flex items-center justify-center bg-black/40 rounded-ds-sm overflow-hidden flex-shrink-0">
            ${thumbHtml}
        </div>
        <div class="min-w-0 flex-1">
            <div class="text-sm font-bold text-text-main truncate" title="${escapeHtml(folder.path)}">${escapeHtml(folder.name)}</div>
            <div class="text-xs text-text-muted truncate">${folder.count} · ${formatSize(folder.size_mb)}</div>
        </div>
        <span class="material-icons text-text-muted flex-shrink-0" aria-hidden="true">${folder.hasSubfolders ? 'chevron_right' : 'play_arrow'}</span>
    `;

    row.addEventListener('click', () => {
        setFolderBrowserPath(folder.path);
    });

    return row;
}

/**
 * Render the folder browser view
 */
function renderFolderBrowser() {
    const grid = document.getElementById('videoGrid');
    const legend = document.getElementById('folderBrowserLegend');
    const backBtn = document.getElementById('folderBrowserBackBtn');
    const breadcrumbEl = document.getElementById('folderBreadcrumb');
    const videosHereLink = document.getElementById('folderVideosHereLink');
    const videosHereCount = document.getElementById('folderVideosHereCount');

    // Get subfolders at current path
    const subfolders = getSubfoldersAt(folderBrowserState.currentPath);
    const videosHere = folderBrowserState.currentPath ? getVideosDirectlyIn(folderBrowserState.currentPath) : [];

    // Update legend visibility
    if (legend) {
        legend.style.display = 'block';
        legend.classList.remove('hidden');
    }

    // Update back button visibility
    if (backBtn) {
        if (folderBrowserState.currentPath || folderBrowserState.showVideosHere) {
            backBtn.style.display = 'inline-flex';
            backBtn.classList.remove('hidden');
        } else {
            backBtn.style.display = 'none';
        }
    }

    // Update breadcrumb
    if (breadcrumbEl) {
        const breadcrumbs = getFolderBreadcrumbs();
        // Der Pfad steckte in einem interpolierten onclick, abgesichert nur
        // gegen einfache Anführungszeichen. Ein Ordner namens
        // `a"onmouseover=...` bricht damit aus dem Attribut aus — das
        // Anführungszeichen begrenzt es, nicht das Apostroph. Knoten bauen
        // löst beide Ebenen auf einmal.
        breadcrumbEl.innerHTML = '';

        breadcrumbs.forEach((crumb, idx) => {
            const isLast = idx === breadcrumbs.length - 1;

            const item = document.createElement('span');
            item.className = 'flex-shrink-0 ' + (isLast
                ? 'text-text-main font-bold'
                : 'text-arcade-cyan hover:text-text-main cursor-pointer transition-colors');
            item.textContent = crumb.name;
            if (!isLast) {
                item.addEventListener('click', () => setFolderBrowserPath(crumb.path));
            }
            breadcrumbEl.appendChild(item);

            if (!isLast) {
                const separator = document.createElement('span');
                separator.className = 'text-gray-600 mx-1 flex-shrink-0';
                separator.textContent = '/';
                breadcrumbEl.appendChild(separator);
            }
        });

        // Bei tiefen Pfaden ans Ende scrollen, damit der aktuelle Ordner sichtbar ist
        const scroller = breadcrumbEl.parentElement;
        if (scroller) scroller.scrollLeft = scroller.scrollWidth;
    }

    // Update "videos here" link
    if (videosHereLink && videosHereCount) {
        if (videosHere.length > 0 && subfolders.length > 0 && !folderBrowserState.showVideosHere) {
            videosHereLink.style.display = 'flex';
            videosHereLink.classList.remove('hidden');
            videosHereCount.textContent = `${videosHere.length} video${videosHere.length !== 1 ? 's' : ''} here`;
        } else {
            videosHereLink.style.display = 'none';
        }
    }

    // Clear the grid
    grid.innerHTML = '';
    grid.classList.remove('list-view');
    grid.classList.remove('folder-list');

    // Decide what to render
    if (folderBrowserState.showVideosHere || (subfolders.length === 0 && folderBrowserState.currentPath)) {
        // Show videos at current path
        const videosToShow = folderBrowserState.showVideosHere ? videosHere : getVideosUnderPath(folderBrowserState.currentPath);

        if (videosToShow.length === 0) {
            // Empty folder
            grid.innerHTML = `
                <div class="col-span-full flex flex-col items-center justify-center py-20 text-gray-500">
                    <span class="material-icons text-6xl mb-4" aria-hidden="true">folder_off</span>
                    <p class="text-lg font-medium">No videos in this folder</p>
                    <button class="mt-4 px-4 py-2 rounded-lg bg-arcade-cyan/20 text-arcade-cyan hover:bg-arcade-cyan/30 transition-colors" onclick="folderBrowserBack()">
                        Go Back
                    </button>
                </div>
            `;
        } else {
            // Render video cards using existing function
            const fragment = document.createDocumentFragment();
            videosToShow.forEach(video => {
                fragment.appendChild(createVideoCard(video));
            });
            grid.appendChild(fragment);

            // Set playlist for cinema navigation
            if (typeof setCinemaPlaylist === 'function') {
                setCinemaPlaylist(videosToShow);
            }
        }
    } else if (subfolders.length === 0 && !folderBrowserState.currentPath) {
        // No folders at root level
        grid.innerHTML = `
            <div class="col-span-full flex flex-col items-center justify-center py-20 text-gray-500">
                <span class="material-icons text-6xl mb-4" aria-hidden="true">folder_off</span>
                <p class="text-lg font-medium">No folders found</p>
                <p class="text-sm mt-2">Videos are not organized in folders</p>
            </div>
        `;
    } else {
        // Render folder cards — auf schmalen Viewports als kompakte Liste
        const compact = isCompactFolderView();
        grid.classList.toggle('folder-list', compact);

        const fragment = document.createDocumentFragment();
        subfolders.forEach(folder => {
            fragment.appendChild(compact ? createFolderRow(folder) : createFolderCard(folder));
        });
        grid.appendChild(fragment);
    }
}

// Beim Wechsel über den Breakpoint (Rotation, Resize) neu rendern —
// sonst bleiben Karten/Zeilen in der falschen Darstellung stehen.
let lastCompactFolderView = null;
window.addEventListener('resize', () => {
    const compact = isCompactFolderView();
    if (lastCompactFolderView === compact) return;
    lastCompactFolderView = compact;
    if (currentLayout === 'folderbrowser') renderFolderBrowser();
});

/**
 * Update the folder browser legend state
 */
function updateFolderBrowserLegend() {
    // This is called by renderFolderBrowser, but exposed for external use if needed
    renderFolderBrowser();
}

