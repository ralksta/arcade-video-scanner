/**
 * Smart Collections Module - Filter-based dynamic collections
 *
 * Features:
 * - Create and edit smart collections with complex filter criteria
 * - Include/exclude filters for status, codec, tags, resolution, etc.
 * - Real-time preview count while editing
 * - Category grouping for organization
 * - Deep linking support (/collections/Name)
 */

// --- COLLECTION STATE ---
let editingCollectionId = null;
let collectionCriteriaNew = null;

// Legacy criteria object for backward compatibility
let collectionCriteria = {
    status: 'all',
    codec: 'all',
    tags: [],
    search: ''
};

// --- MODAL FUNCTIONS ---

/**
 * Open the collection modal for creating or editing a collection
 * @param {string|null} editId - Collection ID to edit, or null for new
 */
function openCollectionModal(editId = null) {
    const modal = document.getElementById('collectionModal');
    if (!modal) return;

    editingCollectionId = editId;

    // Reset form
    document.getElementById('collectionName').value = '';
    document.getElementById('collectionSearch').value = '';
    document.getElementById('collectionDateFilter').value = 'all';
    document.getElementById('collectionMinSize').value = '';
    document.getElementById('collectionMaxSize').value = '';
    document.getElementById('collectionColor').value = '#64FFDA';
    document.getElementById('collectionColorBtn').style.backgroundColor = '#64FFDA';
    document.getElementById('selectedCollectionIcon').innerText = 'folder_special';

    // Initialize new criteria schema
    collectionCriteriaNew = getDefaultCollectionCriteria();

    // Also reset legacy for backward compat
    collectionCriteria = { status: 'all', codec: 'all', tags: [], search: '' };

    // Update UI title
    document.getElementById('collectionModalTitle').innerText = editId ? 'Edit Collection' : 'Smart Collection';
    document.getElementById('deleteCollectionBtn')?.classList.toggle('hidden', !editId);

    // If editing, load existing data
    if (editId) {
        const existing = (userSettings.smart_collections || []).find(c => c.id === editId);
        if (existing) {
            document.getElementById('collectionName').value = existing.name || '';
            document.getElementById('collectionSearch').value = existing.criteria?.search || '';

            // Populate New Fields
            document.getElementById('collectionDateFilter').value = existing.criteria?.date || 'all';
            document.getElementById('collectionMinSize').value = existing.criteria?.size?.min || '';
            document.getElementById('collectionMaxSize').value = existing.criteria?.size?.max || '';

            document.getElementById('collectionColor').value = existing.color || '#64FFDA';
            document.getElementById('collectionColorBtn').style.backgroundColor = existing.color || '#64FFDA';
            document.getElementById('selectedCollectionIcon').innerText = existing.icon || 'folder_special';

            // Check if using new schema
            if (existing.criteria?.include || existing.criteria?.exclude) {
                collectionCriteriaNew = JSON.parse(JSON.stringify(existing.criteria));
            } else {
                // Convert legacy schema to new
                collectionCriteriaNew = getDefaultCollectionCriteria();
                if (existing.criteria?.status && existing.criteria.status !== 'all') {
                    collectionCriteriaNew.include.status = [existing.criteria.status];
                }
                if (existing.criteria?.codec && existing.criteria.codec !== 'all') {
                    collectionCriteriaNew.include.codec = [existing.criteria.codec];
                }
                if (existing.criteria?.tags) {
                    collectionCriteriaNew.include.tags = [...existing.criteria.tags];
                }
                collectionCriteriaNew.search = existing.criteria?.search || '';

                // Preserve new fields if they were mixed in
                if (existing.criteria?.size) collectionCriteriaNew.size = existing.criteria.size;
                if (existing.criteria?.date) collectionCriteriaNew.date = existing.criteria.date;
                if (existing.criteria?.duration) collectionCriteriaNew.duration = existing.criteria.duration;
                if (existing.criteria?.favorites) collectionCriteriaNew.favorites = existing.criteria.favorites;
            }
        }
    }

    // Populate and sync category dropdown
    populateCategoryDropdown(editId ? (userSettings.smart_collections || []).find(c => c.id === editId)?.category : null);
    document.getElementById('newCategoryInput')?.classList.add('hidden');
    document.getElementById('collectionCategory')?.classList.remove('hidden');

    // Sync UI with new criteria
    syncSmartCollectionUI();

    // Reset accordion sections to collapsed state
    const propertiesPanel = document.getElementById('propertiesPanel');
    const metadataPanel = document.getElementById('metadataPanel');
    const propertiesChevron = document.getElementById('propertiesChevron');
    const metadataChevron = document.getElementById('metadataChevron');

    if (propertiesPanel) {
        propertiesPanel.classList.add('hidden');
        if (propertiesChevron) propertiesChevron.style.transform = 'rotate(0deg)';
    }
    if (metadataPanel) {
        metadataPanel.classList.add('hidden');
        if (metadataChevron) metadataChevron.style.transform = 'rotate(0deg)';
    }

    updateAllFilterBadges();
    modal.classList.add('active');
}

/**
 * Close the collection modal
 */
function closeCollectionModal() {
    const modal = document.getElementById('collectionModal');
    if (modal) modal.classList.remove('active');
    editingCollectionId = null;
    document.getElementById('collectionIconPicker')?.classList.add('hidden');
    document.getElementById('collectionColorPicker')?.classList.add('hidden');
}

// --- ACCORDION & BADGE FUNCTIONS ---

/**
 * Toggle a filter accordion section open/closed
 * @param {string} sectionName - Section identifier (properties, metadata)
 */
function toggleFilterAccordion(sectionName) {
    const panel = document.getElementById(`${sectionName}Panel`);
    const chevron = document.getElementById(`${sectionName}Chevron`);
    const button = chevron?.closest('button');

    if (!panel || !chevron) return;

    if (panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
        chevron.style.transform = 'rotate(180deg)';
        button?.setAttribute('aria-expanded', 'true');
    } else {
        panel.classList.add('hidden');
        chevron.style.transform = 'rotate(0deg)';
        button?.setAttribute('aria-expanded', 'false');
    }
}

/**
 * Update badge count for a filter section
 * @param {string} sectionName - Section identifier
 */
function updateFilterSectionBadge(sectionName) {
    const badge = document.getElementById(`${sectionName}Badge`);
    const panel = document.getElementById(`${sectionName}Panel`);

    if (!badge || !panel) return;

    const activeFilters = panel.querySelectorAll('.filter-chip.active:not([data-filter="favorites"][data-value="null"]), .filter-chip.exclude').length;

    let additionalFilters = 0;
    if (sectionName === 'metadata') {
        const dateFilter = document.getElementById('collectionDateFilter');
        if (dateFilter && dateFilter.value !== 'all') additionalFilters++;

        const minSize = document.getElementById('collectionMinSize');
        const maxSize = document.getElementById('collectionMaxSize');
        if ((minSize && minSize.value) || (maxSize && maxSize.value)) additionalFilters++;

        const searchTerm = document.getElementById('collectionSearch');
        if (searchTerm && searchTerm.value.trim()) additionalFilters++;
    }

    const totalActive = activeFilters + additionalFilters;

    if (totalActive > 0) {
        badge.textContent = `${totalActive} active`;
        badge.classList.remove('hidden');
    } else {
        badge.classList.add('hidden');
    }
}

/**
 * Update all section badges
 */
function updateAllFilterBadges() {
    updateFilterSectionBadge('properties');
    updateFilterSectionBadge('metadata');
}

// --- LEGACY UI SYNC (backward compatibility) ---

function syncCollectionModalUI() {
    document.querySelectorAll('.collection-filter-chip[data-filter="status"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === collectionCriteria.status);
    });
    document.querySelectorAll('.collection-filter-chip[data-filter="codec"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === collectionCriteria.codec);
    });
}

function setCollectionFilter(filterType, value) {
    collectionCriteria[filterType] = value;
    syncCollectionModalUI();
}

function renderCollectionTagsList() {
    const container = document.getElementById('collectionTagsList');
    if (!container) return;

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600 italic">No tags created</span>';
        return;
    }

    container.innerHTML = availableTags.map(tag => `
        <button class="collection-filter-chip ${collectionCriteria.tags.includes(tag.name) ? 'active' : ''}"
                onclick="toggleCollectionTag('${tag.name}')"
                style="border-color: ${collectionCriteria.tags.includes(tag.name) ? tag.color : 'rgba(255,255,255,0.1)'}">
            <span class="tag-dot" style="background-color: ${tag.color}; width: 6px; height: 6px; border-radius: 50%; display: inline-block;"></span>
            ${tag.name}
        </button>
    `).join('');
}

function toggleCollectionTag(tagName) {
    const idx = collectionCriteria.tags.indexOf(tagName);
    if (idx >= 0) {
        collectionCriteria.tags.splice(idx, 1);
    } else {
        collectionCriteria.tags.push(tagName);
    }
    renderCollectionTagsList();
}

// --- ICON & COLOR PICKERS ---

function toggleCollectionIconPicker() {
    document.getElementById('collectionColorPicker')?.classList.add('hidden');
    document.getElementById('collectionIconPicker')?.classList.toggle('hidden');
}

function selectCollectionIcon(icon) {
    document.getElementById('selectedCollectionIcon').innerText = icon;
    document.getElementById('collectionIconPicker')?.classList.add('hidden');
}

function toggleCollectionColorPicker() {
    document.getElementById('collectionIconPicker')?.classList.add('hidden');
    document.getElementById('collectionColorPicker')?.classList.toggle('hidden');
}

function selectCollectionColor(color) {
    document.getElementById('collectionColor').value = color;
    document.getElementById('collectionColorBtn').style.backgroundColor = color;
    document.getElementById('collectionColorPicker')?.classList.add('hidden');
}

// --- SAVE & DELETE ---

/**
 * Save the current collection (create or update)
 */
function saveCollection() {
    const name = document.getElementById('collectionName').value.trim();
    if (!name) {
        alert('Please enter a collection name');
        return;
    }

    const icon = document.getElementById('selectedCollectionIcon').innerText;
    const color = document.getElementById('collectionColor').value;
    const search = document.getElementById('collectionSearch').value.trim();

    const dateVal = document.getElementById('collectionDateFilter').value;
    const sizeMin = document.getElementById('collectionMinSize').value;
    const sizeMax = document.getElementById('collectionMaxSize').value;

    if (collectionCriteriaNew) {
        collectionCriteriaNew.search = search;
        collectionCriteriaNew.date = (dateVal && dateVal !== 'all') ? dateVal : null;
        collectionCriteriaNew.size = {
            min: sizeMin ? parseInt(sizeMin) : null,
            max: sizeMax ? parseInt(sizeMax) : null
        };
    }

    // Get category
    const newCatInput = document.getElementById('newCategoryInput');
    const catSelect = document.getElementById('collectionCategory');
    let category = null;
    if (newCatInput && !newCatInput.classList.contains('hidden') && newCatInput.value.trim()) {
        category = newCatInput.value.trim();
    } else if (catSelect) {
        category = catSelect.value || null;
    }

    const collection = {
        id: editingCollectionId || 'col_' + Date.now(),
        name: name,
        icon: icon,
        color: color,
        category: category,
        criteria: collectionCriteriaNew ? JSON.parse(JSON.stringify(collectionCriteriaNew)) : {
            status: collectionCriteria.status,
            codec: collectionCriteria.codec,
            tags: [...collectionCriteria.tags],
            search: search
        }
    };

    if (!userSettings.smart_collections) userSettings.smart_collections = [];

    if (editingCollectionId) {
        const idx = userSettings.smart_collections.findIndex(c => c.id === editingCollectionId);
        if (idx >= 0) {
            userSettings.smart_collections[idx] = collection;
        }
    } else {
        userSettings.smart_collections.push(collection);
    }

    saveSettingsWithoutReload();
    renderCollections();

    // Re-apply if editing active collection
    if (editingCollectionId && editingCollectionId === activeCollectionId) {
        applyCollection(editingCollectionId);
    }

    closeCollectionModal();
}

/**
 * Delete the currently editing collection
 */
function deleteCurrentCollection() {
    if (!editingCollectionId) return;
    if (!confirm('Delete this collection?')) return;

    if (userSettings.smart_collections) {
        userSettings.smart_collections = userSettings.smart_collections.filter(c => c.id !== editingCollectionId);
        saveSettingsWithoutReload();
        renderCollections();
    }
    closeCollectionModal();
}

// --- DEFAULT CRITERIA ---

/**
 * Get the default criteria structure for new collections
 * @returns {Object} Default criteria object
 */
function getDefaultCollectionCriteria() {
    return {
        tagLogic: 'any',
        include: {
            status: [],
            codec: [],
            tags: [],
            resolution: [],
            orientation: [],
            media_type: [],
            format: []
        },
        exclude: {
            status: [],
            codec: [],
            tags: [],
            resolution: [],
            orientation: [],
            media_type: [],
            format: []
        },
        favorites: null,
        date: {
            type: 'any',
            relative: null,
            from: null,
            to: null
        },
        duration: {
            min: null,
            max: null
        },
        size: {
            min: null,
            max: null
        },
        search: ''
    };
}

// --- HELPER FUNCTIONS ---

/**
 * Get video resolution category
 * @param {Object} video - Video object
 * @returns {string} Resolution category (4k, 1080p, 720p, sd)
 */
function getVideoResolution(video) {
    const width = video.width || video.Width || 0;
    const height = video.height || video.Height || 0;
    const maxDim = Math.max(width, height);

    if (maxDim >= 3840) return '4k';
    if (maxDim >= 1920) return '1080p';
    if (maxDim >= 1280) return '720p';
    return 'sd';
}

/**
 * Get video orientation
 * @param {Object} video - Video object
 * @returns {string} Orientation (landscape, portrait, square, unknown)
 */
function getVideoOrientation(video) {
    const width = video.width || video.Width || 0;
    const height = video.height || video.Height || 0;

    if (width === 0 || height === 0) return 'unknown';

    const ratio = width / height;
    if (ratio > 1.1) return 'landscape';
    if (ratio < 0.9) return 'portrait';
    return 'square';
}

/**
 * Check if video matches date filter
 * @param {Object} video - Video object
 * @param {string|Object} dateFilter - Date filter criteria
 * @returns {boolean} Whether video matches
 */
function matchesDateFilter(video, dateFilter) {
    if (!dateFilter || dateFilter === 'all' || (dateFilter.type && dateFilter.type === 'all')) return true;

    const timestamp = (video.imported_at > 0 ? video.imported_at : video.mtime) || 0;
    if (timestamp === 0) return false;

    const now = Math.floor(Date.now() / 1000);
    let relativeKey = typeof dateFilter === 'string' ? dateFilter : dateFilter.relative;

    if (relativeKey) {
        const secondsMap = {
            '1d': 24 * 60 * 60,
            '7d': 7 * 24 * 60 * 60,
            '30d': 30 * 24 * 60 * 60,
            '90d': 90 * 24 * 60 * 60,
            '1y': 365 * 24 * 60 * 60
        };
        const cutoff = now - (secondsMap[relativeKey] || 0);
        return timestamp >= cutoff;
    }

    return true;
}

// --- MAIN EVALUATION FUNCTION ---

/**
 * Evaluate if a video matches collection criteria
 * @param {Object} video - Video object to test
 * @param {Object} criteria - Collection criteria
 * @returns {boolean} Whether video matches all criteria
 */
function evaluateCollectionMatch(video, criteria) {
    if (!criteria) return true;

    const matchesAny = (videoVal, arr) => arr.length === 0 || arr.some(v =>
        videoVal?.toLowerCase?.().includes?.(v.toLowerCase()) || videoVal === v
    );

    const isExcluded = (videoVal, arr) => arr.length > 0 && arr.some(v =>
        videoVal?.toLowerCase?.().includes?.(v.toLowerCase()) || videoVal === v
    );

    const status = video.Status || '';
    const codec = (video.codec || '').toLowerCase();
    const videoTags = video.tags || [];
    const resolution = getVideoResolution(video);
    const orientation = getVideoOrientation(video);
    const isHidden = video.hidden || false;
    const isFavorite = video.favorite || false;
    const duration = video.duration || 0;
    const sizeMB = video.Size_MB || 0;
    const mediaType = video.media_type || 'video';

    let format = '';
    if (video.format) {
        format = video.format.toLowerCase();
    } else if (video.FilePath) {
        format = video.FilePath.split('.').pop().toLowerCase();
    }

    // Hidden videos are never included
    if (isHidden) return false;

    // --- EXCLUSIONS ---
    const exc = criteria.exclude || {};

    if (exc.media_type?.length > 0 && exc.media_type.includes(mediaType)) return false;
    if (exc.format?.length > 0 && isExcluded(format, exc.format)) return false;
    if (exc.status?.length > 0 && isExcluded(status, exc.status)) return false;

    if (exc.codec?.length > 0) {
        for (const excCodec of exc.codec) {
            if (codec.includes(excCodec.toLowerCase())) return false;
        }
    }

    if (exc.tags?.length > 0 && exc.tags.some(t => videoTags.includes(t))) return false;
    if (exc.resolution?.length > 0 && exc.resolution.includes(resolution)) return false;
    if (exc.orientation?.length > 0 && exc.orientation.includes(orientation)) return false;

    // --- INCLUSIONS ---
    const inc = criteria.include || {};

    if (inc.media_type?.length > 0 && !inc.media_type.includes(mediaType)) return false;
    if (inc.format?.length > 0 && !matchesAny(format, inc.format)) return false;

    if (inc.status?.length > 0) {
        const statusMatch = inc.status.some(s => {
            if (s === 'optimized_files') return video.FilePath?.includes('_opt');
            return status === s;
        });
        if (!statusMatch) return false;
    }

    if (inc.codec?.length > 0) {
        const codecMatch = inc.codec.some(c => codec.includes(c.toLowerCase()));
        if (!codecMatch) return false;
    }

    if (inc.tags?.length > 0) {
        if (criteria.tagLogic === 'all') {
            if (!inc.tags.every(t => videoTags.includes(t))) return false;
        } else {
            if (!inc.tags.some(t => videoTags.includes(t))) return false;
        }
    }

    if (inc.resolution?.length > 0 && !inc.resolution.includes(resolution)) return false;
    if (inc.orientation?.length > 0 && !inc.orientation.includes(orientation)) return false;

    // --- FAVORITES ---
    const wantOnlyFavorites = criteria.favorites === true || criteria.favorites === 'true';
    const wantExcludeFavorites = criteria.favorites === false || criteria.favorites === 'false';

    if (wantOnlyFavorites || wantExcludeFavorites) {
        const isFav = !!(video.favorite || video.Favorite || video.isFavorite || video.IsFavorite);
        if (wantOnlyFavorites && !isFav) return false;
        if (wantExcludeFavorites && isFav) return false;
    }

    // --- DATE ---
    if (criteria.date && !matchesDateFilter(video, criteria.date)) return false;

    // --- DURATION ---
    if (criteria.duration) {
        if (criteria.duration.min !== null && duration < criteria.duration.min) return false;
        if (criteria.duration.max !== null && duration > criteria.duration.max) return false;
    }

    // --- SIZE ---
    if (criteria.size) {
        if (criteria.size.min !== null && sizeMB < criteria.size.min) return false;
        if (criteria.size.max !== null && sizeMB > criteria.size.max) return false;
    }

    // --- SEARCH ---
    if (criteria.search) {
        const searchLower = criteria.search.toLowerCase();
        const filename = video.FilePath?.split(/[\\/]/).pop()?.toLowerCase() || '';
        if (!filename.includes(searchLower) && !video.FilePath?.toLowerCase()?.includes(searchLower)) {
            return false;
        }
    }

    return true;
}

// --- SMART COLLECTION MODAL UI ---

function initNewCollectionCriteria() {
    collectionCriteriaNew = getDefaultCollectionCriteria();
    updateCollectionPreviewCount();
}

function toggleSmartFilterChip(chip) {
    const filterType = chip.dataset.filter;
    const value = chip.dataset.value;

    if (!collectionCriteriaNew) initNewCollectionCriteria();

    const includeArr = collectionCriteriaNew.include[filterType];

    chip.classList.toggle('active');
    chip.setAttribute('aria-pressed', chip.classList.contains('active') ? 'true' : 'false');

    if (chip.classList.contains('active')) {
        if (!includeArr.includes(value)) includeArr.push(value);
    } else {
        const idx = includeArr.indexOf(value);
        if (idx > -1) includeArr.splice(idx, 1);
    }

    updateCollectionPreviewCount();

    const section = chip.closest('[id$="Panel"]');
    if (section) {
        const sectionName = section.id.replace('Panel', '');
        updateFilterSectionBadge(sectionName);
    }
}

function toggleTagLogic() {
    if (!collectionCriteriaNew) initNewCollectionCriteria();

    collectionCriteriaNew.tagLogic = collectionCriteriaNew.tagLogic === 'any' ? 'all' : 'any';

    const btn = document.getElementById('tagLogicBtn');
    if (btn) {
        btn.textContent = collectionCriteriaNew.tagLogic.toUpperCase();
    }

    updateCollectionPreviewCount();
}

function setFavoritesFilter(value) {
    if (!collectionCriteriaNew) initNewCollectionCriteria();

    collectionCriteriaNew.favorites = value;

    document.querySelectorAll('[data-filter="favorites"]').forEach(btn => {
        const btnValue = btn.dataset.value === 'null' ? null : btn.dataset.value === 'true';
        btn.classList.toggle('active', btnValue === value);
        btn.setAttribute('aria-pressed', btnValue === value ? 'true' : 'false');
    });

    updateCollectionPreviewCount();
    updateFilterSectionBadge('metadata');
}

function renderSmartCollectionTagsList() {
    const container = document.getElementById('collectionTagsList');
    if (!container) return;

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600 italic">No tags created</span>';
        return;
    }

    const includedTags = collectionCriteriaNew?.include?.tags || [];
    const excludedTags = collectionCriteriaNew?.exclude?.tags || [];

    container.innerHTML = availableTags.map(tag => {
        const isIncluded = includedTags.includes(tag.name);
        const isExcluded = excludedTags.includes(tag.name);

        let style = '';
        let classes = 'filter-chip';

        if (isIncluded) {
            style = `border-color: ${tag.color}; background: ${tag.color}20;`;
            classes += ' active';
        } else if (isExcluded) {
            style = `border-color: #ef4444; background: rgba(239, 68, 68, 0.15); color: #ef4444; text-decoration: line-through; opacity: 0.8;`;
            classes += ' exclude';
        }

        return `
        <button class="${classes}"
                onclick="toggleSmartTagChip('${tag.name}')"
                style="${style}">
            <span class="w-2 h-2 rounded-full shrink-0" style="background-color: ${isExcluded ? '#ef4444' : tag.color}"></span>
            ${tag.name}
        </button>
        `;
    }).join('');
}

/**
 * Toggle tag chip through states: Unselected -> Included -> Excluded -> Unselected
 * @param {string} tagName - Tag name to toggle
 */
function toggleSmartTagChip(tagName) {
    if (!collectionCriteriaNew) initNewCollectionCriteria();

    if (!collectionCriteriaNew.include.tags) collectionCriteriaNew.include.tags = [];
    if (!collectionCriteriaNew.exclude.tags) collectionCriteriaNew.exclude.tags = [];

    const incIdx = collectionCriteriaNew.include.tags.indexOf(tagName);
    const excIdx = collectionCriteriaNew.exclude.tags.indexOf(tagName);

    if (incIdx === -1 && excIdx === -1) {
        collectionCriteriaNew.include.tags.push(tagName);
    } else if (incIdx !== -1) {
        collectionCriteriaNew.include.tags.splice(incIdx, 1);
        collectionCriteriaNew.exclude.tags.push(tagName);
    } else if (excIdx !== -1) {
        collectionCriteriaNew.exclude.tags.splice(excIdx, 1);
    }

    renderSmartCollectionTagsList();
    updateCollectionPreviewCount();
}

/**
 * Update the real-time match count badge
 */
function updateCollectionPreviewCount() {
    const countEl = document.getElementById('matchCountNumber');
    if (!countEl) return;

    if (!collectionCriteriaNew) {
        countEl.textContent = '0';
        return;
    }

    const tempCriteria = JSON.parse(JSON.stringify(collectionCriteriaNew));

    const searchInput = document.getElementById('collectionSearch');
    if (searchInput) tempCriteria.search = searchInput.value.trim();

    const dateInput = document.getElementById('collectionDateFilter');
    if (dateInput) {
        const val = dateInput.value;
        tempCriteria.date = (val && val !== 'all') ? val : null;
    }

    const minSizeInput = document.getElementById('collectionMinSize');
    const maxSizeInput = document.getElementById('collectionMaxSize');
    const minVal = minSizeInput && minSizeInput.value ? parseInt(minSizeInput.value) : null;
    const maxVal = maxSizeInput && maxSizeInput.value ? parseInt(maxSizeInput.value) : null;

    if (minVal !== null || maxVal !== null) {
        tempCriteria.size = { min: minVal, max: maxVal };
    } else {
        tempCriteria.size = null;
    }

    const allVideos = window.ALL_VIDEOS || [];
    const matchingVideos = allVideos.filter(v => evaluateCollectionMatch(v, tempCriteria));
    const count = matchingVideos.length;
    countEl.textContent = count;

    const labelEl = document.getElementById('matchCountLabel');
    const iconEl = document.getElementById('matchCountIcon');
    const mediaTypes = tempCriteria.include?.media_type || [];

    if (labelEl && iconEl) {
        if (mediaTypes.length === 1) {
            if (mediaTypes[0] === 'video') {
                labelEl.textContent = count === 1 ? 'video' : 'videos';
                iconEl.textContent = 'movie';
            } else if (mediaTypes[0] === 'image') {
                labelEl.textContent = count === 1 ? 'image' : 'images';
                iconEl.textContent = 'image';
            }
        } else {
            labelEl.textContent = count === 1 ? 'item' : 'items';
            iconEl.textContent = 'perm_media';
        }
    }

    countEl.closest('.px-3')?.classList.add('animate-pulse');
    setTimeout(() => {
        countEl.closest('.px-3')?.classList.remove('animate-pulse');
    }, 300);
}

/**
 * Sync modal UI with collectionCriteriaNew state
 */
function syncSmartCollectionUI() {
    if (!collectionCriteriaNew) return;

    document.querySelectorAll('[data-filter="media_type"]').forEach(chip => {
        chip.classList.toggle('active', collectionCriteriaNew.include.media_type.includes(chip.dataset.value));
    });

    document.querySelectorAll('[data-filter="format"]').forEach(chip => {
        chip.classList.toggle('active', collectionCriteriaNew.include.format.includes(chip.dataset.value));
    });

    document.querySelectorAll('[data-filter="status"]').forEach(chip => {
        chip.classList.toggle('active', collectionCriteriaNew.include.status.includes(chip.dataset.value));
    });

    document.querySelectorAll('[data-filter="codec"]').forEach(chip => {
        chip.classList.toggle('active', collectionCriteriaNew.include.codec.includes(chip.dataset.value));
    });

    document.querySelectorAll('[data-filter="resolution"]').forEach(chip => {
        chip.classList.toggle('active', collectionCriteriaNew.include.resolution.includes(chip.dataset.value));
    });

    document.querySelectorAll('[data-filter="orientation"]').forEach(chip => {
        chip.classList.toggle('active', collectionCriteriaNew.include.orientation.includes(chip.dataset.value));
    });

    const tagLogicBtn = document.getElementById('tagLogicBtn');
    if (tagLogicBtn) tagLogicBtn.textContent = (collectionCriteriaNew.tagLogic || 'any').toUpperCase();

    document.querySelectorAll('[data-filter="favorites"]').forEach(btn => {
        const btnValue = btn.dataset.value === 'null' ? null : btn.dataset.value === 'true';
        btn.classList.toggle('active', btnValue === collectionCriteriaNew.favorites);
    });

    const searchInput = document.getElementById('collectionSearch');
    if (searchInput) searchInput.value = collectionCriteriaNew.search || '';

    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.setAttribute('aria-pressed', chip.classList.contains('active') ? 'true' : 'false');
    });

    renderSmartCollectionTagsList();
    updateCollectionPreviewCount();
    updateAllFilterBadges();
}

// --- COLLECTION COUNT & RENDERING ---

/**
 * Count videos matching collection criteria
 * @param {Object} collection - Collection object
 * @returns {number} Count of matching videos
 */
function getCollectionCount(collection) {
    if (!window.ALL_VIDEOS || !collection.criteria) return 0;

    const isNewSchema = collection.criteria.include || collection.criteria.exclude;

    if (isNewSchema) {
        return window.ALL_VIDEOS.filter(v => evaluateCollectionMatch(v, collection.criteria)).length;
    }

    // Legacy compatibility
    return window.ALL_VIDEOS.filter(v => {
        const name = v.FilePath.split(/[\\\\/]/).pop().toLowerCase();
        const status = v.Status;
        const codec = v.codec || 'unknown';
        const videoTags = v.tags || [];
        const isHidden = v.hidden || false;

        if (isHidden) return false;

        if (collection.criteria.status && collection.criteria.status !== 'all') {
            if (collection.criteria.status === 'optimized_files') {
                if (!v.FilePath.includes('_opt')) return false;
            } else if (status !== collection.criteria.status) {
                return false;
            }
        }

        if (collection.criteria.codec && collection.criteria.codec !== 'all') {
            if (!codec.includes(collection.criteria.codec)) return false;
        }

        if (collection.criteria.tags && collection.criteria.tags.length > 0) {
            const hasMatchingTag = collection.criteria.tags.some(t => videoTags.includes(t));
            if (!hasMatchingTag) return false;
        }

        if (collection.criteria.search) {
            const searchLower = collection.criteria.search.toLowerCase();
            if (!name.includes(searchLower) && !v.FilePath.toLowerCase().includes(searchLower)) {
                return false;
            }
        }

        return true;
    }).length;
}

/**
 * Render the collections sidebar
 */
function renderCollections() {
    const container = document.getElementById('collectionsNav');
    if (!container) return;

    const allCollections = userSettings.smart_collections || [];

    // Filter sensitive collections in safe mode
    let collections = allCollections;
    if (safeMode) {
        let sensitiveCols = window.userSettings?.sensitive_collections || [];
        sensitiveCols = sensitiveCols.map(s => s.trim().toLowerCase()).filter(s => s);

        collections = allCollections.filter(c => {
            const name = (c.name || '').trim().toLowerCase();
            return !sensitiveCols.includes(name);
        });
    }

    if (collections.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-600 italic px-3 py-2">No collections yet</p>';
        return;
    }

    // Group by category
    const groups = {};
    collections.forEach(col => {
        const cat = col.category || 'Uncategorized';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(col);
    });

    const collapsed = JSON.parse(localStorage.getItem('collapsedCategories') || '{}');

    const sortedCategories = Object.keys(groups).sort((a, b) => {
        if (a === 'Uncategorized') return 1;
        if (b === 'Uncategorized') return -1;
        return a.localeCompare(b);
    });

    if (sortedCategories.length === 1 && sortedCategories[0] === 'Uncategorized') {
        container.innerHTML = groups['Uncategorized'].map(col => renderCollectionItem(col)).join('');
        return;
    }

    let html = '';
    sortedCategories.forEach(category => {
        const isCollapsed = collapsed[category] || false;
        const catCollections = groups[category];
        const safeKey = category.replace(/[^a-zA-Z0-9]/g, '_');

        html += `
            <div class="category-group mb-1">
                <button onclick="toggleCategoryCollapse('${category}')"
                        class="w-full flex items-center gap-1.5 px-2 py-1.5 text-[10px] font-bold text-gray-500 uppercase tracking-widest hover:text-gray-300 transition-colors rounded hover:bg-white/5">
                    <span class="material-icons text-[14px] transition-transform duration-200 ${isCollapsed ? '-rotate-90' : ''}"
                          id="cat-arrow-${safeKey}">expand_more</span>
                    <span class="flex-1 text-left">${category}</span>
                    <span class="text-gray-600 font-mono">${catCollections.length}</span>
                </button>
                <div id="cat-items-${safeKey}"
                     class="space-y-0.5 overflow-hidden transition-all duration-200 ${isCollapsed ? 'max-h-0' : 'max-h-[2000px]'}">
                    ${catCollections.map(col => renderCollectionItem(col)).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Render a single collection item for the sidebar
 * @param {Object} col - Collection object
 * @returns {string} HTML string for collection item
 */
function renderCollectionItem(col) {
    const count = getCollectionCount(col);
    const isActive = col.id === activeCollectionId;

    return `
        <div class="collection-nav-item group flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all w-full cursor-pointer ${isActive ? 'bg-arcade-cyan/25 text-arcade-cyan border border-arcade-cyan/50 shadow-lg shadow-arcade-cyan/10 font-bold' : 'text-gray-600 dark:text-gray-300 hover:bg-black/5 dark:hover:bg-white/5 border border-transparent'}"
                onclick="applyCollection('${col.id}')"
                ondblclick="openCollectionModal('${col.id}')">
            <span class="material-icons text-[18px]" style="color: ${col.color}">${col.icon}</span>
            <span class="flex-1 text-left truncate">${col.name}</span>

            <button onclick="event.stopPropagation(); openCollectionModal('${col.id}')"
                    class="${isActive ? 'opacity-100' : 'opacity-0'} group-hover:opacity-100 p-1 text-gray-400 dark:text-gray-500 hover:text-black dark:hover:text-white transition-opacity"
                    title="Edit Collection">
                <span class="material-icons text-[14px]">edit</span>
            </button>

            <span class="text-[10px] px-1.5 py-0.5 rounded-full ${isActive ? 'bg-black/40 text-arcade-cyan border border-arcade-cyan/30' : 'bg-black/5 dark:bg-white/5 text-gray-400 dark:text-gray-500'} font-mono">${count}</span>
        </div>
    `;
}

/**
 * Toggle category collapse state
 * @param {string} category - Category name
 */
function toggleCategoryCollapse(category) {
    const collapsed = JSON.parse(localStorage.getItem('collapsedCategories') || '{}');
    collapsed[category] = !collapsed[category];
    localStorage.setItem('collapsedCategories', JSON.stringify(collapsed));

    const safeKey = category.replace(/[^a-zA-Z0-9]/g, '_');
    const items = document.getElementById('cat-items-' + safeKey);
    const arrow = document.getElementById('cat-arrow-' + safeKey);

    if (items) {
        items.classList.toggle('max-h-0');
        items.classList.toggle('max-h-[2000px]');
    }
    if (arrow) arrow.classList.toggle('-rotate-90');
}

// --- APPLY COLLECTION ---

/**
 * Apply a collection's filter criteria
 * @param {string} collectionId - Collection ID to apply
 */
function applyCollection(collectionId) {
    const collection = (userSettings.smart_collections || []).find(c => c.id === collectionId);
    if (!collection || !collection.criteria) return;

    // Reset to lobby workspace first
    setWorkspaceMode('lobby');

    let criteria = collection.criteria;
    const isNewSchema = criteria.include || criteria.exclude;

    if (!isNewSchema) {
        // Convert legacy schema
        const converted = getDefaultCollectionCriteria();

        if (criteria.status && criteria.status !== 'all') {
            converted.include.status = [criteria.status];
        }
        if (criteria.codec && criteria.codec !== 'all') {
            converted.include.codec = [criteria.codec];
        }
        if (criteria.tags) {
            converted.include.tags = [...criteria.tags];
        }
        converted.search = criteria.search || '';

        if (criteria.size) converted.size = criteria.size;
        if (criteria.date) converted.date = criteria.date;
        if (criteria.duration) converted.duration = criteria.duration;
        if (criteria.favorites) converted.favorites = criteria.favorites;

        criteria = converted;
    }

    // Update URL for deep linking
    const newUrl = '/collections/' + encodeURIComponent(collection.name);
    if (window.location.pathname !== newUrl) {
        history.pushState({ id: collectionId }, '', newUrl);
    }

    // Set active collection
    activeSmartCollectionCriteria = criteria;
    activeCollectionId = collectionId;

    // Sync search UI
    if (criteria.search) {
        searchTerm = criteria.search;
        document.getElementById('mobileSearchInput').value = searchTerm;
    } else {
        searchTerm = '';
        document.getElementById('mobileSearchInput').value = '';
    }

    filterAndSort(true);
    renderCollections();

    showToast(`Applied collection: ${collection.name}`, 'info');
}

// --- EXPORTS ---
window.openCollectionModal = openCollectionModal;
window.closeCollectionModal = closeCollectionModal;
window.saveCollection = saveCollection;
window.deleteCurrentCollection = deleteCurrentCollection;
window.applyCollection = applyCollection;
window.renderCollections = renderCollections;
window.toggleFilterAccordion = toggleFilterAccordion;
window.toggleCollectionIconPicker = toggleCollectionIconPicker;
window.selectCollectionIcon = selectCollectionIcon;
window.toggleCollectionColorPicker = toggleCollectionColorPicker;
window.selectCollectionColor = selectCollectionColor;
window.toggleSmartFilterChip = toggleSmartFilterChip;
window.toggleSmartTagChip = toggleSmartTagChip;
window.toggleTagLogic = toggleTagLogic;
window.setFavoritesFilter = setFavoritesFilter;
window.updateCollectionPreviewCount = updateCollectionPreviewCount;
window.setCollectionFilter = setCollectionFilter;
window.toggleCollectionTag = toggleCollectionTag;
window.toggleCategoryCollapse = toggleCategoryCollapse;
window.evaluateCollectionMatch = evaluateCollectionMatch;
window.getDefaultCollectionCriteria = getDefaultCollectionCriteria;
