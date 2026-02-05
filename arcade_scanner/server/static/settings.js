/**
 * Settings Module
 * Handles settings modal, navigation, saving, and related functionality
 * Extracted from engine.js for modularity
 * 
 * Dependencies:
 * - engine.js (safeMode, userSettings, filterAndSort, renderCollections)
 * - formatters.js (if needed)
 */

// ============================================================================
// SETTINGS MODAL - OPEN/CLOSE
// ============================================================================

/**
 * Open the settings modal and populate with current settings
 */
async function openSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.add('active');

    try {
        const response = await fetch('/api/settings');
        const data = await response.json();

        // Populate form fields
        document.getElementById('settingsTargets').value = data.scan_targets.join('\n');
        document.getElementById('settingsExcludes').value = data.exclude_paths.join('\n');
        document.getElementById('settingsMinSize').value = data.min_size_mb || 100;
        document.getElementById('settingsBitrate').value = data.bitrate_threshold_kbps || 15000;

        // Privacy
        document.getElementById('settingsSafeMode').checked = window.safeMode;
        document.getElementById('settingsSensitiveDirs').value = (data.sensitive_dirs || []).join('\n');
        document.getElementById('settingsSensitiveTags').value = (data.sensitive_tags || []).join(', ');
        document.getElementById('settingsSensitiveCollections').value = (data.sensitive_collections || []).join('\n');

        // New Features
        document.getElementById('settingsTheme').value = data.theme || 'arcade';
        document.getElementById('settingsFunFacts').checked = data.enable_fun_facts ?? true;
        const optimizerCheckbox = document.getElementById('settingsOptimizer');
        if (optimizerCheckbox) optimizerCheckbox.checked = data.enable_optimizer !== false;

        const imageScanCheckbox = document.getElementById('settingsScanImages');
        if (imageScanCheckbox) imageScanCheckbox.checked = data.enable_image_scanning === true;

        // Show default paths hint
        document.getElementById('defaultTargetsHint').textContent =
            `Standard: ${data.default_scan_targets.slice(0, 2).join(', ')}${data.default_scan_targets.length > 2 ? '...' : ''}`;

        // Populate default exclusions with checkboxes
        const container = document.getElementById('defaultExclusionsContainer');
        container.innerHTML = '';

        const disabledDefaults = data.disabled_defaults || [];

        data.default_exclusions.forEach(exc => {
            const isEnabled = !disabledDefaults.includes(exc.path);
            const item = document.createElement('label');
            item.className = 'checkbox-item';
            item.innerHTML = `
                <input type="checkbox" data-path="${exc.path}" ${isEnabled ? 'checked' : ''}>
                <div class="checkbox-item-content">
                    <div class="checkbox-item-title">${exc.path}</div>
                    <div class="checkbox-item-description">${exc.desc}</div>
                </div>
            `;
            container.appendChild(item);
        });

        // Fetch cache statistics
        const statsResponse = await fetch('/api/cache-stats');
        const stats = await statsResponse.json();

        document.getElementById('statThumbnails').textContent = `${stats.thumbnails_mb} MB`;

        document.getElementById('statTotal').textContent = `${stats.total_mb} MB`;
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

/**
 * Close the settings modal
 */
function closeSettings() {
    document.getElementById('settingsModal').classList.remove('active');
}

// ============================================================================
// SETTINGS SAVING
// ============================================================================

/**
 * Save settings to server with UI feedback
 */
async function saveSettings() {
    const saveBtn = document.getElementById('saveSettingsBtn');
    const saveIcon = saveBtn?.querySelector('.save-icon');
    const saveSpinner = saveBtn?.querySelector('.save-spinner');
    const saveText = saveBtn?.querySelector('.save-text');

    // Show loading state
    if (saveBtn) saveBtn.disabled = true;
    if (saveIcon) saveIcon.classList.add('hidden');
    if (saveSpinner) saveSpinner.classList.remove('hidden');
    if (saveText) saveText.textContent = 'Saving...';

    const targetsText = document.getElementById('settingsTargets').value;
    const excludesText = document.getElementById('settingsExcludes').value;

    // Collect disabled defaults (unchecked checkboxes)
    const disabledDefaults = [];
    document.querySelectorAll('#defaultExclusionsContainer input[type="checkbox"]').forEach(cb => {
        if (!cb.checked) {
            disabledDefaults.push(cb.dataset.path);
        }
    });

    const settings = {
        scan_targets: targetsText.split('\n').map(s => s.trim()).filter(s => s),
        exclude_paths: excludesText.split('\n').map(s => s.trim()).filter(s => s),
        disabled_defaults: disabledDefaults,
        saved_views: window.userSettings?.saved_views || [],
        sensitive_dirs: document.getElementById('settingsSensitiveDirs').value.split('\n').map(s => s.trim()).filter(s => s),
        sensitive_tags: document.getElementById('settingsSensitiveTags').value.split(',').map(s => s.trim()).filter(s => s),
        sensitive_collections: document.getElementById('settingsSensitiveCollections').value.split(/[\n,]/).map(s => s.trim()).filter(s => s),
        min_size_mb: parseInt(document.getElementById('settingsMinSize').value) || 100,
        min_image_size_kb: parseInt(document.getElementById('settingsMinImageSize').value) || 100,
        bitrate_threshold_kbps: parseInt(document.getElementById('settingsBitrate').value) || 15000,

        enable_fun_facts: document.getElementById('settingsFunFacts')?.checked || false,
        enable_optimizer: document.getElementById('settingsOptimizer')?.checked ?? true,
        enable_image_scanning: document.getElementById('settingsScanImages')?.checked || false,
        enable_deovr: document.getElementById('settingsDeoVR')?.checked || false,
        theme: document.getElementById('settingsTheme').value || 'arcade'
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        // Reset button state
        if (saveBtn) saveBtn.disabled = false;
        if (saveIcon) saveIcon.classList.remove('hidden');
        if (saveSpinner) saveSpinner.classList.add('hidden');
        if (saveText) saveText.textContent = 'Save';

        if (response.ok) {
            // Hide unsaved indicator
            const unsavedIndicator = document.getElementById('unsavedIndicator');
            if (unsavedIndicator) unsavedIndicator.style.opacity = '0';

            // Update Theme immediately
            const newTheme = document.getElementById('settingsTheme').value;
            if (newTheme) document.documentElement.setAttribute('data-theme', newTheme);


            // Show success toast
            showSettingsToast();

            // Close after brief delay to show success state
            setTimeout(() => {
                closeSettings();
            }, 1200);

            // Update local state immediately
            window.userSettings = {
                ...window.userSettings,
                ...settings
            };

            // Update Safe Mode State separately (localStorage)
            const newSafeMode = document.getElementById('settingsSafeMode').checked;
            if (newSafeMode !== window.safeMode) {
                window.safeMode = newSafeMode;
                localStorage.setItem('safe_mode', window.safeMode);
            }

            // Always refresh content to reflect potential changes in sensitive lists or other settings
            if (typeof filterAndSort === 'function') filterAndSort();
            if (typeof renderCollections === 'function') renderCollections();
        } else {
            showSettingsToast('Error saving settings', true);
        }
    } catch (e) {
        console.error('Failed to save settings:', e);
        // Reset button state
        if (saveBtn) saveBtn.disabled = false;
        if (saveIcon) saveIcon.classList.remove('hidden');
        if (saveSpinner) saveSpinner.classList.add('hidden');
        if (saveText) saveText.textContent = 'Save';

        showSettingsToast('Error saving settings', true);
    }
}

/**
 * Show settings-specific toast notification
 * @param {string} message - Message to display
 * @param {boolean} isError - Whether this is an error message
 */
function showSettingsToast(message = 'Settings saved', isError = false) {
    const toast = document.getElementById('settingsToast');
    if (!toast) return;

    const toastContent = toast.querySelector('div');
    if (toastContent) {
        toastContent.className = isError
            ? 'bg-red-500/95 backdrop-blur text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3'
            : 'bg-green-500/95 backdrop-blur text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3';
        const icon = toastContent.querySelector('.material-icons');
        const text = toastContent.querySelector('span:last-child');
        if (icon) icon.textContent = isError ? 'error' : 'check_circle';
        if (text) text.textContent = message;
    }

    toast.classList.remove('translate-y-20', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');

    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
        toast.classList.remove('translate-y-0', 'opacity-100');
    }, 3000);
}

/**
 * Load settings from server and initialize app state
 */
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        if (response.ok) {
            const data = await response.json();
            // Merge with existing to keep any static generated data
            window.userSettings = {
                ...window.userSettings,
                ...data
            };

            // Set Docker detection flag
            window.IS_DOCKER = data.is_docker || false;

            // Hide Locate button in Docker mode
            if (window.IS_DOCKER) {
                const locateBtn = document.getElementById('cinemaLocateBtn');
                if (locateBtn) locateBtn.style.display = 'none';
            }

            // Settings loaded successfully

            // Check for deep links (e.g., /collections/Name)
            checkDeepLinks();
        }
    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

/**
 * Check for deep links in URL and apply them
 */
function checkDeepLinks() {
    const path = window.location.pathname;
    if (path.startsWith('/collections/')) {
        const nameEncoded = path.substring('/collections/'.length);
        const name = decodeURIComponent(nameEncoded);

        const collections = window.userSettings.smart_collections || [];
        const collection = collections.find(c => c.name === name);

        if (collection) {
            // Deep link to collection
            if (typeof applyCollection === 'function') {
                applyCollection(collection.id);
            }
        } else {
            console.warn("Deep link collection not found:", name);
            // Default to lobby if not found
            history.replaceState(null, '', '/');
        }
    }
}

// ============================================================================
// SETTINGS UI NAVIGATION
// ============================================================================

/**
 * Initialize settings modal navigation (tabs/sections)
 */
function initSettingsNavigation() {
    // Use more specific selector to only target settings modal nav items
    const settingsModal = document.getElementById('settingsModal');
    if (!settingsModal) return;

    const navItems = settingsModal.querySelectorAll('.settings-nav-item[data-section]');
    const contentSections = settingsModal.querySelectorAll('.content-section');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const sectionId = item.dataset.section;
            if (!sectionId) return;

            // Update active nav item and indicator
            navItems.forEach(nav => {
                nav.classList.remove('active', 'text-white', 'bg-white/5');
                nav.classList.add('text-gray-400');
                const indicator = nav.querySelector('.active-indicator');
                if (indicator) indicator.classList.add('opacity-0');
            });
            item.classList.add('active', 'text-white', 'bg-white/5');
            item.classList.remove('text-gray-400');
            const activeIndicator = item.querySelector('.active-indicator');
            if (activeIndicator) activeIndicator.classList.remove('opacity-0');

            // Show corresponding content - toggle hidden class
            contentSections.forEach(section => {
                section.classList.add('hidden');
                section.classList.remove('active');
            });
            const targetSection = document.getElementById(`content-${sectionId}`);
            if (targetSection) {
                targetSection.classList.remove('hidden');
                targetSection.classList.add('active');
            }

            // Update header
            updateSettingsHeader(sectionId);
        });
    });

    // Set initial active state
    const initialActive = settingsModal.querySelector('.settings-nav-item.active');
    if (initialActive) {
        const indicator = initialActive.querySelector('.active-indicator');
        if (indicator) indicator.classList.remove('opacity-0');
        initialActive.classList.add('text-white', 'bg-white/5');
        initialActive.classList.remove('text-gray-400');
    }
}

/**
 * Update the settings header based on selected section
 * @param {string} sectionId - ID of the selected section
 */
function updateSettingsHeader(sectionId) {
    const headers = {
        'scanning': {
            title: 'Scanning',
            subtitle: 'Configure video library scanning behavior'
        },
        'performance': {
            title: 'Performance',
            subtitle: 'Optimize scan performance and file filtering'
        },
        'interface': {
            title: 'Interface',
            subtitle: 'Customize dashboard appearance and features'
        },
        'storage': {
            title: 'Storage',
            subtitle: 'Manage cache and disk space usage'
        },
        'privacy': {
            title: 'Privacy & Safety',
            subtitle: 'Configure Safe Mode and hidden content'
        }
    };

    const header = headers[sectionId] || { title: sectionId, subtitle: '' };
    const titleEl = document.getElementById('section-title');
    const subtitleEl = document.getElementById('section-subtitle');

    if (titleEl) titleEl.textContent = header.title;
    if (subtitleEl) subtitleEl.textContent = header.subtitle;
}

/**
 * Adjust a numeric settings input by a delta
 * @param {string} inputId - ID of the input element
 * @param {number} delta - Amount to add/subtract
 */
function adjustSettingsNumber(inputId, delta) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const current = parseInt(input.value) || 0;
    const min = parseInt(input.min) || 0;
    const max = parseInt(input.max) || Infinity;
    const newValue = Math.max(min, Math.min(max, current + delta));
    input.value = newValue;
    markSettingsUnsaved();
}

// ============================================================================
// SAVE STATE INDICATORS
// ============================================================================

/**
 * Mark settings as having unsaved changes
 */
function markSettingsUnsaved() {
    const indicator = document.getElementById('unsavedIndicator');
    if (indicator) {
        indicator.style.opacity = '1';
    }
}

/**
 * Show saving state indicator
 */
function markSettingsSaving() {
    const indicator = document.querySelector('.save-indicator');
    if (indicator) {
        indicator.className = 'save-indicator saving';
        indicator.innerHTML = '<div class="loading-spinner"></div><span>Saving...</span>';
    }
}

/**
 * Show saved state indicator
 */
function markSettingsSaved() {
    const indicator = document.querySelector('.save-indicator');
    if (indicator) {
        indicator.className = 'save-indicator saved';
        indicator.innerHTML = '<span class="material-icons">check_circle</span><span>All changes saved</span>';
    }
}

// ============================================================================
// GENERAL TOAST NOTIFICATION
// ============================================================================

/**
 * Show a toast notification message
 * @param {string} message - Message to display
 * @param {string} [type='info'] - Toast type ('info', 'success', 'error')
 */
function showToast(message, type = 'info') {
    // Remove existing toast if any
    const existingToast = document.querySelector('.settings-toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast
    const toast = document.createElement('div');
    toast.className = `settings-toast toast-${type}`;
    toast.innerHTML = `
        <span class="material-icons">${type === 'success' ? 'check_circle' : 'info'}</span>
        <span>${message}</span>
    `;

    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after 2 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// ============================================================================
// HIDDEN PATH MODAL
// ============================================================================

let currentHiddenPath = '';

/**
 * Show modal with path info when file is in a hidden folder
 * Provides copy-to-clipboard functionality as an alternative to reveal
 * @param {string} path - Full path to the file
 */
function showHiddenPathModal(path) {
    currentHiddenPath = path;
    const modal = document.getElementById('hiddenPathModal');
    const pathDisplay = document.getElementById('hiddenPathDisplay');

    if (modal && pathDisplay) {
        pathDisplay.textContent = path;
        // Reset copy button state
        const copyIcon = document.getElementById('copyPathIcon');
        const copyText = document.getElementById('copyPathText');
        if (copyIcon) copyIcon.textContent = 'content_copy';
        if (copyText) copyText.textContent = 'Copy Path to Clipboard';

        modal.classList.add('active');
    }
}

/**
 * Close the hidden path modal
 */
function closeHiddenPathModal() {
    const modal = document.getElementById('hiddenPathModal');
    if (modal) modal.classList.remove('active');
    currentHiddenPath = '';
}

/**
 * Copy the current hidden path to clipboard
 */
async function copyHiddenPath() {
    if (!currentHiddenPath) return;

    try {
        await navigator.clipboard.writeText(currentHiddenPath);
        // Update button to show success
        const copyIcon = document.getElementById('copyPathIcon');
        const copyText = document.getElementById('copyPathText');
        if (copyIcon) copyIcon.textContent = 'check';
        if (copyText) copyText.textContent = 'Copied!';

        // Reset after 2 seconds
        setTimeout(() => {
            if (copyIcon) copyIcon.textContent = 'content_copy';
            if (copyText) copyText.textContent = 'Copy Path to Clipboard';
        }, 2000);
    } catch (err) {
        console.error('Failed to copy path:', err);
        showToast('Failed to copy path', 'error');
    }
}

/**
 * Reveal a file in the system file browser (Finder/Explorer)
 * Handles hidden folders by showing a modal with the path instead
 * @param {string} path - Full path to reveal
 */
async function revealInFinder(path) {
    try {
        const response = await fetch(`/reveal?path=${encodeURIComponent(path)}`);

        if (response.status === 204) {
            // Success - file was revealed
            return;
        }

        if (response.ok) {
            const data = await response.json();
            if (data.status === 'hidden_folder') {
                // Show helpful modal for hidden folder
                showHiddenPathModal(data.path);
                return;
            }
        }

        // Other errors
        console.error('Reveal failed:', response.status);
        showToast('Could not reveal file', 'error');
    } catch (err) {
        console.error('Reveal error:', err);
        showToast('Could not reveal file', 'error');
    }
}

// ============================================================================
// RESCAN
// ============================================================================

/**
 * Trigger a full library rescan
 * Shows loading state and reloads page when complete
 */
function rescanLibrary() {
    const btn = document.getElementById('refreshBtn');
    const originalContent = btn.innerHTML;

    btn.innerHTML = '<span class="material-icons spin">sync</span> SCANNEN...';
    btn.style.pointerEvents = 'none';
    document.body.style.opacity = '0.5';

    fetch('/api/rescan')
        .then(response => {
            if (response.ok) return response.json();
            throw new Error('Scan failed');
        })
        .then(() => {
            location.reload();
        })
        .catch(e => {
            console.error(e);
            alert('Scan error: ' + e.message);
            btn.innerHTML = originalContent;
            btn.style.pointerEvents = 'auto';
            document.body.style.opacity = '1';
        });
}

// ============================================================================
// SAVED VIEWS
// ============================================================================

/**
 * Render saved views in the UI
 */
function renderSavedViews() {
    const container = document.getElementById('savedViewsContainer');
    if (!container) return;

    container.innerHTML = '';

    const views = window.userSettings?.saved_views || [];

    views.forEach(view => {
        const chip = document.createElement('button');
        chip.className = 'view-chip';
        // highlight if currently active? (complex to strict match, skip for now)

        chip.innerHTML = `
            <span onclick="loadView('${view.id}')">${view.name}</span>
            <span class="material-icons chip-delete" onclick="deleteView('${view.id}', event)">close</span>
        `;
        container.appendChild(chip);
    });
}

/**
 * Save the current view state
 */
function saveCurrentView() {
    const name = prompt("Name for this view:", "");
    if (!name) return;

    if (!window.userSettings.saved_views) window.userSettings.saved_views = [];

    const newView = {
        id: 'view_' + Date.now(),
        name: name,
        search: window.searchTerm,
        filter: window.currentFilter,
        codec: window.currentCodec,
        sort: window.currentSort,
        mode: window.workspaceMode,
        folder: window.currentFolder
    };

    window.userSettings.saved_views.push(newView);
    saveSettingsWithoutReload(); // We need a version that doesn't just print console
    renderSavedViews();
}

/**
 * Load a saved view by ID
 * @param {string} id - View ID to load
 */
function loadView(id) {
    const view = (window.userSettings?.saved_views || []).find(v => v.id === id);
    if (!view) return;

    // Apply settings
    window.searchTerm = view.search || "";
    document.getElementById('mobileSearchInput').value = window.searchTerm;

    window.currentFilter = view.filter || "all";
    document.getElementById('statusSelect').value = window.currentFilter;

    window.currentCodec = view.codec || "all";
    if (document.getElementById('codecSelect'))
        document.getElementById('codecSelect').value = window.currentCodec;

    window.currentSort = view.sort || "bitrate";
    document.getElementById('sortSelect').value = window.currentSort;

    if (view.mode && typeof setWorkspaceMode === 'function') {
        setWorkspaceMode(view.mode); // Handles filterAndSort internally if changed
    }

    // If we rely on stored vars, we must call update
    if (typeof filterAndSort === 'function') filterAndSort();

    // Update visuals
    if (typeof updateURL === 'function') updateURL();
}

/**
 * Delete a saved view
 * @param {string} id - View ID to delete
 * @param {Event} [event] - Click event to stop propagation
 */
function deleteView(id, event) {
    if (event) event.stopPropagation();
    if (!confirm("Delete this view?")) return;

    if (window.userSettings?.saved_views) {
        window.userSettings.saved_views = window.userSettings.saved_views.filter(v => v.id !== id);
        saveSettingsWithoutReload();
        renderSavedViews();
    }
}

/**
 * Save current settings to server without closing UI or reloading
 * Used for background saves (views, collections, etc.)
 */
function saveSettingsWithoutReload() {
    fetch(`/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(window.userSettings)
    }).then(r => r.json()).then(data => {
        if (data.success) {
            // Views saved
        }
    });
}

// ============================================================================
// BACKUP & RESTORE
// ============================================================================

/**
 * Export current settings as JSON file download
 */
function exportSettings() {
    window.location.href = '/api/user/export';
}

/**
 * Import settings from a JSON file
 */
function importSettings() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';

    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
            try {
                const data = JSON.parse(event.target.result);

                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/user/import', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    showToast('Settings imported! Reloading...', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showToast(result.error || 'Import failed', 'error');
                }
            } catch (err) {
                console.error('Import error:', err);
                showToast('Invalid file format', 'error');
            }
        };
        reader.readAsText(file);
    };

    input.click();
}

// ============================================================================
// INITIALIZATION & EVENT LISTENERS
// ============================================================================

// Initialize navigation when settings modal opens - wrap original function
const _originalOpenSettings = openSettings;
window.openSettings = async function () {
    await _originalOpenSettings();
    // Initialize navigation after modal is populated
    setTimeout(() => {
        initSettingsNavigation();
    }, 100);
};

// Add change listeners to mark unsaved on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        const settingsInputs = document.querySelectorAll('#settingsModal input, #settingsModal textarea');
        settingsInputs.forEach(el => {
            el.addEventListener('input', markSettingsUnsaved);
        });
    }, 500);
});

// Keyboard Shortcuts for Settings Modal and Collection Modal
document.addEventListener('keydown', (e) => {
    const settingsModal = document.getElementById('settingsModal');
    const isSettingsOpen = settingsModal && settingsModal.classList.contains('active');

    const collectionModal = document.getElementById('collectionModal');
    const isCollectionOpen = collectionModal && collectionModal.classList.contains('active');

    // ESC to close modals (collection modal takes priority if both somehow open)
    if (e.key === 'Escape') {
        if (isCollectionOpen) {
            e.preventDefault();
            if (typeof closeCollectionModal === 'function') closeCollectionModal();
            return;
        }
        if (isSettingsOpen) {
            e.preventDefault();
            closeSettings();
            showToast('Settings closed', 'info');
            return;
        }
    }

    if (isSettingsOpen) {
        // Cmd+S (Mac) or Ctrl+S (Windows/Linux) to save
        if ((e.metaKey || e.ctrlKey) && e.key === 's') {
            e.preventDefault();
            saveSettings();
            showToast('Saving settings...', 'success');
        }
    }
});

// ============================================================================
// EXPOSE TO GLOBAL SCOPE
// ============================================================================

// Settings modal functions
window.openSettings = window.openSettings; // Already wrapped above
window.closeSettings = closeSettings;
window.saveSettings = saveSettings;
window.loadSettings = loadSettings;
window.showSettingsToast = showSettingsToast;

// Settings UI navigation
window.initSettingsNavigation = initSettingsNavigation;
window.adjustSettingsNumber = adjustSettingsNumber;
window.markSettingsUnsaved = markSettingsUnsaved;
window.markSettingsSaving = markSettingsSaving;
window.markSettingsSaved = markSettingsSaved;

// Toast
window.showToast = showToast;

// Hidden path modal
window.showHiddenPathModal = showHiddenPathModal;
window.closeHiddenPathModal = closeHiddenPathModal;
window.copyHiddenPath = copyHiddenPath;
window.revealInFinder = revealInFinder;

// Rescan
window.rescanLibrary = rescanLibrary;

// Saved views
window.renderSavedViews = renderSavedViews;
window.saveCurrentView = saveCurrentView;
window.loadView = loadView;
window.deleteView = deleteView;
window.saveSettingsWithoutReload = saveSettingsWithoutReload;

// Backup & Restore
window.exportSettings = exportSettings;
window.importSettings = importSettings;
