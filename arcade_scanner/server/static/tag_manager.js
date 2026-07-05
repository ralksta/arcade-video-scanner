// tag_manager.js - Extracted from engine.js

// --- BATCH TAGGING (Modern Redesign) ---
let batchTagActions = {}; // { tagName: 'add' | 'remove' | null }
let batchTagSearchTerm = '';
let batchTagFocusIndex = -1;

function openBatchTagModal() {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    if (selected.length === 0) return;

    batchTagActions = {};
    batchTagSearchTerm = '';
    batchTagFocusIndex = -1;

    let modal = document.getElementById('batchTagModal');
    if (!modal) {
        createBatchTagModal();
        modal = document.getElementById('batchTagModal');
    }

    renderBatchTagOptions();
    if (modal) modal.style.display = 'flex';

    // Focus search input
    setTimeout(() => {
        document.getElementById('batchTagSearch')?.focus();
    }, 100);
}

function createBatchTagModal() {
    const modal = document.createElement('div');
    modal.id = 'batchTagModal';
    modal.className = 'fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4';
    modal.style.display = 'none';
    modal.innerHTML = `
        <div class="w-full max-w-md bg-[#1a1a1e] rounded-2xl shadow-2xl border border-white/10 overflow-hidden">
            <!-- Header -->
            <div class="px-5 py-4 border-b border-white/5 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <span class="material-icons text-purple-400 text-xl">sell</span>
                    <div>
                        <h2 class="font-semibold text-white">Batch Tagging</h2>
                        <p class="text-xs text-gray-500">Editing <strong id="batchTagCount" class="text-purple-400">0</strong> items</p>
                    </div>
                </div>
                <button onclick="closeBatchTagModal()" class="text-gray-500 hover:text-white p-1 rounded hover:bg-white/10 transition-colors">
                    <span class="material-icons">close</span>
                </button>
            </div>
            
            <!-- Search Bar -->
            <div class="px-5 py-3 border-b border-white/5">
                <div class="relative">
                    <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-lg">search</span>
                    <input type="text" 
                           id="batchTagSearch" 
                           class="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:border-purple-500 focus:outline-none" 
                           placeholder="Search tags..." 
                           oninput="handleBatchTagSearch(this.value)"
                           onkeydown="handleBatchTagKeyNav(event)">
                </div>
            </div>
            
            <!-- Tag Cloud -->
            <div class="px-5 py-4 flex flex-wrap gap-2 max-h-[200px] overflow-y-auto" id="batchTagOptions">
                <!-- Populated by JS -->
            </div>
            
            <!-- Add New Tag -->
            <div class="px-5 py-3 border-t border-white/5 bg-black/20 flex gap-2">
                <div class="relative flex-1">
                    <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-lg">add</span>
                    <input type="text" 
                           id="batchTagNewInput" 
                           class="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:border-purple-500 focus:outline-none" 
                           placeholder="New tag name..."
                           onkeydown="handleBatchTagNewKeydown(event)">
                </div>
                <button onclick="createAndApplyNewTag()" class="px-4 py-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition-colors">
                    Add
                </button>
            </div>
            
            <!-- Footer -->
            <div class="px-5 py-4 border-t border-white/5 flex gap-3">
                <button onclick="closeBatchTagModal()" class="flex-1 py-2.5 bg-white/5 text-gray-400 border border-white/10 rounded-lg text-sm font-medium hover:bg-white/10 hover:text-white transition-colors">
                    Cancel
                </button>
                <button onclick="applyBatchTags()" class="flex-1 py-2.5 bg-purple-500 text-white rounded-lg text-sm font-semibold hover:bg-purple-400 transition-colors flex items-center justify-center gap-2">
                    <span class="material-icons text-sm">check</span>
                    Save Changes
                </button>
            </div>
        </div>
    `;

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeBatchTagModal();
    });

    document.body.appendChild(modal);
}

function handleBatchTagSearch(value) {
    batchTagSearchTerm = value.toLowerCase();
    batchTagFocusIndex = -1;
    renderBatchTagOptions();
}

function handleBatchTagKeyNav(event) {
    const chips = document.querySelectorAll('.batch-tag-chip');
    if (chips.length === 0) return;

    if (event.key === 'ArrowDown') {
        event.preventDefault();
        batchTagFocusIndex = Math.min(batchTagFocusIndex + 1, chips.length - 1);
        chips[batchTagFocusIndex]?.focus();
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        batchTagFocusIndex = Math.max(batchTagFocusIndex - 1, 0);
        chips[batchTagFocusIndex]?.focus();
    } else if (event.key === 'Enter' && batchTagFocusIndex >= 0) {
        event.preventDefault();
        chips[batchTagFocusIndex]?.click();
    }
}

function handleBatchTagChipKeydown(event, tagName) {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleBatchTagOption(tagName);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        handleBatchTagKeyNav(event);
    }
}

function handleBatchTagNewKeydown(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        createAndApplyNewTag();
    }
}

async function createAndApplyNewTag() {
    const input = document.getElementById('batchTagNewInput');
    const name = input?.value.trim();
    if (!name) return;

    // Check if tag already exists
    if (availableTags.some(t => t.name.toLowerCase() === name.toLowerCase())) {
        batchTagActions[name] = 'add';
        input.value = '';
        renderBatchTagOptions();
        return;
    }

    // Create new tag with random color
    const colors = ['#9D5BFF', '#00ffd0', '#F4B342', '#DE1A58', '#22c55e', '#06b6d4', '#ec4899'];
    const randomColor = colors[Math.floor(Math.random() * colors.length)];

    const newTag = { name: name, color: randomColor };
    availableTags.push(newTag);

    userSettings.available_tags = availableTags;
    await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userSettings)
    });

    batchTagActions[name] = 'add';
    input.value = '';
    renderBatchTagOptions();
}

function getSelectedVideoPaths() {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    return Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));
}

function getTagStateForSelection(tagName) {
    const paths = getSelectedVideoPaths();
    if (paths.length === 0) return 'none';

    let hasCount = 0;
    paths.forEach(path => {
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (video && (video.tags || []).includes(tagName)) {
            hasCount++;
        }
    });

    if (hasCount === 0) return 'none';
    if (hasCount === paths.length) return 'all';
    return 'some';
}

function renderBatchTagOptions() {
    const container = document.getElementById('batchTagOptions');
    const countEl = document.getElementById('batchTagCount');

    if (!container) return;

    const paths = getSelectedVideoPaths();
    if (countEl) countEl.textContent = paths.length;

    const filteredTags = availableTags.filter(tag =>
        tag.name.toLowerCase().includes(batchTagSearchTerm)
    );

    if (filteredTags.length === 0 && availableTags.length === 0) {
        container.innerHTML = `
        < div class="batch-tag-empty" >
                <span class="material-icons">label_off</span>
                <p>No tags yet</p>
                <p class="text-xs text-gray-600">Create your first tag below</p>
            </div >
        `;
        return;
    }

    if (filteredTags.length === 0) {
        container.innerHTML = `
        < div class="batch-tag-empty" >
                <span class="material-icons">search_off</span>
                <p>No tags match "${batchTagSearchTerm}"</p>
            </div >
        `;
        return;
    }

    container.innerHTML = filteredTags.map((tag, index) => {
        const currentState = getTagStateForSelection(tag.name);
        const action = batchTagActions[tag.name];

        let displayState = currentState;
        if (action === 'add') displayState = 'all';
        else if (action === 'remove') displayState = 'none';

        const hasAction = action !== undefined && action !== null;

        let checkIcon, bgColor, borderColor, textColor;
        if (displayState === 'all') {
            checkIcon = 'check_box';
            bgColor = 'bg-green-500/15';
            borderColor = 'border-green-500/30';
            textColor = 'text-green-400';
        } else if (displayState === 'some') {
            checkIcon = 'indeterminate_check_box';
            bgColor = 'bg-yellow-500/15';
            borderColor = 'border-yellow-500/30';
            textColor = 'text-yellow-400';
        } else {
            checkIcon = 'check_box_outline_blank';
            bgColor = 'bg-white/5';
            borderColor = 'border-white/10';
            textColor = 'text-gray-400';
        }

        const pendingGlow = hasAction ? 'shadow-[0_0_12px_rgba(168,85,247,0.4)]' : '';

        return `
            <button class="inline-flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all text-sm font-medium ${bgColor} ${borderColor} ${textColor} ${pendingGlow} hover:bg-white/10"
                    onclick="toggleBatchTagOption('${tag.name}')"
                    onkeydown="handleBatchTagChipKeydown(event, '${tag.name}')"
                    tabindex="${index === batchTagFocusIndex ? '0' : '-1'}">
                <span class="material-icons text-lg">${checkIcon}</span>
                <span class="w-2 h-2 rounded-full shrink-0" style="background-color: ${tag.color}"></span>
                <span>${tag.name}</span>
                ${hasAction ? '<span class="text-purple-400 font-bold ml-1">•</span>' : ''}
            </button>
        `;
    }).join('');
}

function toggleBatchTagOption(tagName) {
    const currentState = getTagStateForSelection(tagName);
    const currentAction = batchTagActions[tagName];

    if (currentAction === 'add') {
        batchTagActions[tagName] = 'remove';
    } else if (currentAction === 'remove') {
        batchTagActions[tagName] = null;
    } else {
        if (currentState === 'all') {
            batchTagActions[tagName] = 'remove';
        } else {
            batchTagActions[tagName] = 'add';
        }
    }

    renderBatchTagOptions();
}

function closeBatchTagModal() {
    const modal = document.getElementById('batchTagModal');
    if (modal) modal.style.display = 'none';
    batchTagActions = {};
    batchTagSearchTerm = '';
}

async function applyBatchTags() {
    const actions = Object.entries(batchTagActions).filter(([_, action]) => action === 'add' || action === 'remove');

    if (actions.length === 0) {
        closeBatchTagModal();
        return;
    }

    const tagsToAdd = actions.filter(([_, a]) => a === 'add').map(([name]) => name);
    const tagsToRemove = actions.filter(([_, a]) => a === 'remove').map(([name]) => name);

    const paths = getSelectedVideoPaths();
    let successCount = 0;

    const saveBtn = document.querySelector('.batch-tag-save');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="material-icons animate-spin text-sm">refresh</span> Saving...';
    }

    for (const path of paths) {
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (!video) continue;

        let currentTags = [...(video.tags || [])];

        tagsToAdd.forEach(t => {
            if (!currentTags.includes(t)) currentTags.push(t);
        });

        currentTags = currentTags.filter(t => !tagsToRemove.includes(t));

        try {
            const res = await fetch('/api/video/tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path, tags: currentTags })
            });
            if (res.ok) {
                video.tags = currentTags;
                successCount++;
            }
        } catch (err) {
            console.error('Failed to update tags:', path, err);
        }
    }

    closeBatchTagModal();
    clearSelection();

    filterAndSort(true);
    renderCollections();

    const addedStr = tagsToAdd.length > 0 ? `+ ${tagsToAdd.join(', ')} ` : '';
    const removedStr = tagsToRemove.length > 0 ? `- ${tagsToRemove.join(', ')} ` : '';
    console.log(`✅ Updated ${successCount}/${paths.length} videos: ${addedStr} ${removedStr}`.trim());
}

// --- TAG MANAGEMENT ---
function loadAvailableTags() {
    fetch(`/api/tags?t=${new Date().getTime()}`)
        .then(res => res.json())
        .then(tags => {
            availableTags = tags || [];
            // Tags loaded
            try {
                renderFilterTagsList();
            } catch (e) {
                console.error("Error rendering filters:", e);
            }
            try {
                renderExistingTagsList();
            } catch (e) {
                console.error("Error rendering existing tags:", e);
            }
        })
        .catch(err => {
            console.error('Failed to load tags:', err);
            availableTags = [];
        });
}

function renderFilterTagsList() {
    const container = document.getElementById('filterTagsList');
    if (!container) return;

    if (availableTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-gray-600 italic">No tags created yet</span>';
        return;
    }

    container.innerHTML = availableTags.map(tag => {
        const isPos = activeTags.includes(tag.name);
        const isNeg = activeTags.includes('!' + tag.name);
        let classes = 'tag-filter-chip';
        let style = 'border-color: rgba(255,255,255,0.15)';

        if (isPos) {
            classes += ' active';
            style = `border-color: ${tag.color}`;
        } else if (isNeg) {
            classes += ' negative';
            style = `border-color: rgba(239, 68, 68, 0.5)`;
        }

        return `
        <button class="${classes}" 
                onclick="toggleTagFilter('${tag.name}')"
                style="${style}">
            <span class="tag-dot" style="background-color: ${isNeg ? '#ef4444' : tag.color}"></span>
            ${tag.name}
        </button>
        `;
    }).join('');
}

// --- VIDEO CARD TAG CHIPS ---
function renderVideoCardTags(tags) {
    if (!tags || tags.length === 0) return '';

    const maxShow = 3;
    const visibleTags = tags.slice(0, maxShow);
    const remaining = tags.length - maxShow;

    let html = '<div class="video-card-tags flex flex-wrap gap-1 mt-1">';

    visibleTags.forEach(tagName => {
        const tagData = availableTags.find(t => t.name === tagName);
        const color = tagData?.color || '#888';
        html += `<span class="video-card-tag" style="background-color: ${color}20; border-color: ${color}40; color: ${color}">
            <span class="tag-dot-small" style="background-color: ${color}"></span>
            ${tagName}
        </span>`;
    });

    if (remaining > 0) {
        html += `<span class="video-card-tag overflow-tag">+${remaining}</span>`;
    }

    html += '</div>';
    return html;
}

// Cinema tag functions are now in cinema.js
// (toggleCinemaTagPanel, updateCinemaTags, toggleCinemaTag)

// --- TAG MANAGER MODAL ---
function openTagManager() {
    const modal = document.getElementById('tagManagerModal');
    if (modal) {
        modal.classList.add('active');
        loadAvailableTags();
    }
}

function closeTagManager() {
    const modal = document.getElementById('tagManagerModal');
    if (modal) {
        modal.classList.remove('active');
    }
    // Also close color picker
    document.getElementById('tagColorPicker')?.classList.add('hidden');
}

function toggleTagColorPicker() {
    const picker = document.getElementById('tagColorPicker');
    if (picker) picker.classList.toggle('hidden');
}

function selectTagColor(color) {
    document.getElementById('newTagColor').value = color;
    document.getElementById('tagColorBtn').style.backgroundColor = color;
    document.getElementById('tagColorPicker')?.classList.add('hidden');
}

function createNewTag() {
    const nameInput = document.getElementById('newTagName');
    const colorInput = document.getElementById('newTagColor');
    const shortcutInput = document.getElementById('newTagShortcut');

    const name = nameInput?.value?.trim();
    const color = colorInput?.value || '#00ffd0';
    let shortcut = shortcutInput?.value?.trim().toUpperCase() || '';

    if (!name) {
        alert('Please enter a tag name');
        return;
    }

    // Validate shortcut
    const reservedKeys = ['F', 'V'];
    if (shortcut && reservedKeys.includes(shortcut)) {
        alert(`Shortcut "${shortcut}" is reserved. Please use a different letter.`);
        return;
    }
    if (shortcut && !/^[A-Z]$/.test(shortcut)) {
        alert('Shortcut must be a single letter A-Z');
        return;
    }

    fetch('/api/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, color, shortcut: shortcut || null })
    })
        .then(res => {
            if (res.status === 409) {
                alert('Tag already exists');
                return null;
            }
            return res.json();
        })
        .then(data => {
            if (data) {
                // Clear inputs
                nameInput.value = '';
                if (shortcutInput) shortcutInput.value = '';
                // Refresh lists
                loadAvailableTags();
            }
        })
        .catch(err => {
            console.error('Error creating tag:', err);
            alert('Failed to create tag');
        });
}

function deleteTag(tagName) {
    if (!confirm(`Delete tag "${tagName}"? This will remove it from all videos.`)) return;

    fetch(`/api/tags?action=delete&name=${encodeURIComponent(tagName)}`)
        .then(res => res.json())
        .then(() => {
            // Remove from active filters
            activeTags = activeTags.filter(t => t !== tagName);
            // Refresh
            loadAvailableTags();
            updateFilterPanelCount();
        })
        .catch(err => {
            console.error('Error deleting tag:', err);
            alert('Failed to delete tag');
        });
}

function renderExistingTagsList() {
    const container = document.getElementById('existingTagsList');
    if (!container) return;

    // Use global availableTags which is updated by loadAvailableTags()
    const tags = availableTags || [];
    // Rendering existing tags

    const header = document.getElementById('manageTagsHeader');

    if (header) {
        header.textContent = `Manage Existing Tags (${tags.length})`;
        header.style.color = '';
    } else {
        // Fallback to find header if id is missing
        const h3s = container.parentElement.querySelectorAll('h3');
        if (h3s.length > 0) {
            h3s[0].textContent = `Manage Existing Tags (${tags.length})`;
            h3s[0].id = 'manageTagsHeader';
        }
    }

    if (tags.length === 0) {
        container.innerHTML = '<div class="text-gray-500 text-sm italic py-4">No tags yet</div>';
        return;
    }

    container.innerHTML = tags.map(t => {
        const shortcutValue = t.shortcut ? t.shortcut.toUpperCase() : '';
        const shortcutDisplay = shortcutValue
            ? `<span class="text-xs px-1.5 py-0.5 rounded bg-white/10 text-gray-400 cursor-pointer hover:bg-white/20" onclick="editTagShortcut('${t.name}', '${shortcutValue}')" title="Click to edit">(${shortcutValue})</span>`
            : `<span class="text-xs text-gray-600 cursor-pointer hover:text-gray-400" onclick="editTagShortcut('${t.name}', '')" title="Click to add shortcut">+ key</span>`;
        return `
        <div class="flex items-center justify-between py-2 px-3 bg-black/30 rounded-lg border border-white/5 group" id="tag-row-${t.name}">
            <div class="flex items-center gap-3">
                <span class="w-4 h-4 rounded-full" style="background-color: ${t.color}"></span>
                <span class="text-white text-sm">${t.name}</span>
                ${shortcutDisplay}
            </div>
            <button onclick="deleteTag('${t.name}')" class="text-gray-500 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100">
                <span class="material-icons text-lg">delete</span>
            </button>
        </div>
    `;
    }).join('');
}

function editTagShortcut(tagName, currentShortcut) {
    const newShortcut = prompt(`Enter shortcut key for "${tagName}" (A-Z, or leave empty to remove):`, currentShortcut);

    if (newShortcut === null) return; // Cancelled

    const shortcut = newShortcut.trim().toUpperCase();

    // Validate
    if (shortcut && !/^[A-Z]$/.test(shortcut)) {
        alert('Shortcut must be a single letter A-Z');
        return;
    }
    if (['F', 'V'].includes(shortcut)) {
        alert(`"${shortcut}" is reserved. Please use a different letter.`);
        return;
    }

    // Update tag
    fetch('/api/tags/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: tagName, shortcut: shortcut || null })
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadAvailableTags();
            }
        })
        .catch(err => console.error('Failed to update tag:', err));
}

// --- VIDEO TAG ASSIGNMENT ---
function setVideoTags(videoPath, tags) {
    return fetch('/api/video/tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: videoPath, tags })
    })
        .then(res => res.json())
        .then(data => {
            // Update local cache
            const video = window.ALL_VIDEOS.find(v => v.FilePath === videoPath);
            if (video) {
                video.tags = data.tags || [];
            }
            return data.tags;
        });
}

