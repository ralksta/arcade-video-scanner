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
        const optimizerCheckbox = document.getElementById('settingsOptimizer');
        if (optimizerCheckbox) optimizerCheckbox.checked = data.enable_optimizer !== false;

        const imageScanCheckbox = document.getElementById('settingsScanImages');
        if (imageScanCheckbox) imageScanCheckbox.checked = data.enable_image_scanning === true;

        // Encoding preset (fast / balanced / best)
        selectEncodingPreset(data.encoding_preset || 'balanced');

        const precomputeThumbsCheckbox = document.getElementById('settingsPrecomputeThumbs');
        if (precomputeThumbsCheckbox) precomputeThumbsCheckbox.checked = data.precompute_thumbnails !== false;

        const proxyStreamingCheckbox = document.getElementById('settingsProxyStreaming');
        if (proxyStreamingCheckbox) proxyStreamingCheckbox.checked = data.proxy_streaming !== false;

        const proxyRootInput = document.getElementById('settingsProxyRoot');
        if (proxyRootInput) proxyRootInput.value = data.proxy_root || '';

        const verboseScanningCheckbox = document.getElementById('settingsVerboseScanning');
        if (verboseScanningCheckbox) verboseScanningCheckbox.checked = data.verbose_scanning === true;


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

    loadEmbeddingStatus();
}

/**
 * Abdeckung des Ähnlichkeits-Index anzeigen.
 *
 * Ohne diese Auskunft ist von außen nicht zu unterscheiden, ob es zu einem
 * Medium keine ähnlichen gibt oder ob schlicht kein Index existiert — die
 * Leiste im Cinema sieht in beiden Fällen gleich leer aus.
 */
async function loadEmbeddingStatus() {
    const value = document.getElementById('statEmbeddingCoverage');
    const bar = document.getElementById('statEmbeddingBar');
    const hint = document.getElementById('statEmbeddingHint');
    if (!value || !bar || !hint) return;

    try {
        const response = await fetch('/api/similar/status');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        value.textContent = `${data.indexed.toLocaleString('de-DE')} / ${data.total.toLocaleString('de-DE')}`;
        bar.style.width = `${data.coverage}%`;

        if (data.indexed === 0) {
            hint.textContent = 'Kein Index vorhanden — mit scripts/media_indexer.py anlegen.';
        } else if (data.indexed < data.total) {
            const missing = data.total - data.indexed;
            hint.textContent = `${data.coverage}% abgedeckt, ${missing.toLocaleString('de-DE')} Medien fehlen noch`
                + (data.models.length ? ` · Modell: ${data.models.join(', ')}` : '');
        } else {
            hint.textContent = 'Vollständig indiziert'
                + (data.models.length ? ` · Modell: ${data.models.join(', ')}` : '');
        }
    } catch (e) {
        console.error('Index-Status nicht abrufbar:', e);
        value.textContent = '—';
        hint.textContent = 'Status konnte nicht geladen werden.';
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

        enable_optimizer: document.getElementById('settingsOptimizer')?.checked ?? true,
        enable_image_scanning: document.getElementById('settingsScanImages')?.checked || false,
        encoding_preset: document.getElementById('settingsEncodingPreset')?.value || 'balanced',
        precompute_thumbnails: document.getElementById('settingsPrecomputeThumbs')?.checked ?? true,
        proxy_streaming: document.getElementById('settingsProxyStreaming')?.checked ?? true,
        proxy_root: (document.getElementById('settingsProxyRoot')?.value ?? '').trim(),
        verbose_scanning: document.getElementById('settingsVerboseScanning')?.checked || false
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

            // Detect if accessing locally (localhost or 127.0.0.1)
            // Remote access means "Reveal in Finder" can't work
            const hostname = window.location.hostname;
            window.IS_LOCAL_ACCESS = !window.IS_DOCKER &&
                (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1');

            // Hide Locate button in Docker mode or remote access
            if (window.IS_DOCKER || !window.IS_LOCAL_ACCESS) {
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

            // Aktiver Zustand haengt allein an .active — Tint und
            // Accent-Indikator kommen aus der CSS-Regel (styles.css).
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

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

            // Auto-Tagging section loads its rule list lazily
            if (sectionId === 'autotagging' && typeof renderAutoTagRules === 'function') {
                renderAutoTagRules();
            }
        });
    });

    // Der initiale Zustand steht bereits im Markup (.settings-nav-item.active).
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
        },
        'queue': {
            title: 'Remote Queue',
            subtitle: 'Monitor Mac encoding queue'
        },
        'autotagging': {
            title: 'Auto-Tagging',
            subtitle: 'Regeln, die passenden Dateien automatisch Tags geben'
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
        indicator.innerHTML = '<span class="material-icons" aria-hidden="true">check_circle</span><span>All changes saved</span>';
    }
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
    const stopBtn = document.getElementById('stopScanBtn');
    const originalContent = btn.innerHTML;

    btn.innerHTML = '<span class="material-icons spin" aria-hidden="true">sync</span>';
    btn.style.pointerEvents = 'none';
    if (stopBtn) stopBtn.classList.remove('hidden');

    const restore = () => {
        btn.innerHTML = originalContent;
        btn.style.pointerEvents = 'auto';
        if (stopBtn) stopBtn.classList.add('hidden');
    };

    // /api/rescan antwortet 202 und scannt im Hintergrund — Fortschritt pollen,
    // damit /api/scan/stop den laufenden Scan erreichen kann.
    fetch('/api/rescan')
        .then(response => {
            if (response.status === 409) throw new Error('Scan läuft bereits');
            if (!response.ok) throw new Error('Scan failed');
            return response.json();
        })
        .then(() => {
            const poll = setInterval(() => {
                fetch('/api/scan/status')
                    .then(r => r.json())
                    .then(status => {
                        if (!status.is_scanning) {
                            clearInterval(poll);
                            location.reload();
                        }
                    })
                    .catch(() => { clearInterval(poll); restore(); });
            }, 2000);
        })
        .catch(e => {
            console.error(e);
            if (typeof showToast === 'function') showToast(e.message, 'error');
            restore();
        });
}

/**
 * Stop a running library scan (partial results are kept; orphan cleanup is
 * skipped server-side to protect existing entries).
 */
function stopScan() {
    fetch('/api/scan/stop')
        .then(r => {
            if (r.status === 409) throw new Error('Kein Scan aktiv');
            if (!r.ok) throw new Error('Stop fehlgeschlagen');
            if (typeof showToast === 'function') showToast('Scan wird gestoppt…', 'info');
        })
        .catch(e => {
            if (typeof showToast === 'function') showToast(e.message, 'warning');
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

    // Der Container war fest `hidden md:flex` verdrahtet: auf dem Desktop nahm er
    // auch ohne gespeicherte Ansichten Platz weg, auf dem Handy war er gar nicht
    // erreichbar. Sichtbarkeit hängt jetzt am Inhalt, nicht an der Bildschirmbreite.
    container.classList.toggle('hidden', views.length === 0);
    container.classList.toggle('flex', views.length > 0);

    views.forEach(view => {
        const chip = document.createElement('button');
        chip.className = 'view-chip flex-shrink-0';

        // Ansichtsnamen sind frei eingegeben. Ein Apostroph im Namen zerlegte den
        // interpolierten onclick-Handler und machte den Chip unklickbar — und
        // escapeHtml hilft hier nicht: der HTML-Parser macht aus &#39; wieder ein
        // Apostroph, bevor der JS-Parser die Zeile sieht. Also gar nicht erst
        // interpolieren, sondern Knoten bauen und Listener anhängen.
        const label = document.createElement('span');
        label.textContent = view.name;
        label.addEventListener('click', () => loadView(view.id));

        const remove = document.createElement('span');
        remove.className = 'material-icons chip-delete';
        remove.setAttribute('aria-hidden', 'true');
        remove.textContent = 'close';
        remove.addEventListener('click', (event) => deleteView(view.id, event));

        chip.append(label, remove);
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
    // Speichert Views/Collections im Hintergrund. Schlägt das fehl, ist die
    // Ansicht nur scheinbar gespeichert — deshalb hier eine sichtbare Meldung.
    apiWrite(`/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(window.userSettings)
    }, { action: 'Einstellungen speichern' });
}

// ============================================================================
// BACKUP & RESTORE
// ============================================================================

/**
 * Export current settings as JSON file download
 */
function exportSettings() {
    // '/api/user/export' gab es nie. Der Knopf wurde zusammen mit der
    // Beschriftung „Saves as arcade_settings_backup.json" eingebaut — und
    // genau diesen Dateinamen liefert '/api/backup', die einzige
    // Sicherungsroute, die der Server tatsächlich hat. Sie hatte bis hierher
    // keinen einzigen Aufrufer.
    window.location.href = '/api/backup';
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


// Toast is defined in utils.js — do not re-export here.

// Hidden path modal
window.showHiddenPathModal = showHiddenPathModal;
window.closeHiddenPathModal = closeHiddenPathModal;
window.copyHiddenPath = copyHiddenPath;
window.revealInFinder = revealInFinder;

// Rescan
window.rescanLibrary = rescanLibrary;
window.stopScan = stopScan;

// Saved views
window.renderSavedViews = renderSavedViews;
window.saveCurrentView = saveCurrentView;
window.loadView = loadView;
window.deleteView = deleteView;
window.saveSettingsWithoutReload = saveSettingsWithoutReload;

// Backup & Restore
window.exportSettings = exportSettings;
window.importSettings = importSettings;

// --- REMOTE QUEUE STATUS ---
let _queuePollInterval = null;
let _queuePollMs = 0;

const QUEUE_ACTIVE_STATES = ['pending', 'downloading', 'encoding', 'uploading'];

async function loadQueueStatus() {
    try {
        const r = await fetch('/api/queue/status');
        if (!r.ok) return;
        const jobs = await r.json();
        const tbody = document.getElementById('queueTableBody');
        if (!tbody) return;

        if (!jobs.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-gray-600">No jobs yet</td></tr>';
            _retuneQueuePolling(false);
            return;
        }

        _retuneQueuePolling(jobs.some(j => QUEUE_ACTIVE_STATES.includes(j.status)));

        const statusBadge = (s) => {
            const map = {
                pending: 'bg-yellow-500/20 text-yellow-300',
                downloading: 'bg-blue-500/20 text-blue-300',
                encoding: 'bg-purple-500/20 text-purple-300',
                uploading: 'bg-cyan-500/20 text-cyan-300',
                done: 'bg-green-500/20 text-green-300',
                failed: 'bg-red-500/20 text-red-300',
                cancelled: 'bg-gray-500/20 text-gray-300'
            };
            return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${map[s] || 'bg-ink/10 text-gray-400'}">${s}</span>`;
        };

        const timeAgo = (ts) => {
            if (!ts) return '—';
            const diff = Math.floor(Date.now() / 1000 - ts);
            if (diff < 60) return `${diff}s ago`;
            if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
            return `${Math.floor(diff / 3600)}h ago`;
        };

        const eta = (secs) => {
            if (!secs || secs <= 0) return '';
            if (secs < 60) return ` · ${secs}s left`;
            if (secs < 3600) return ` · ${Math.round(secs / 60)}m left`;
            return ` · ${(secs / 3600).toFixed(1)}h left`;
        };

        // Percentages are per encode pass — the quality search restarts the bar
        // several times, which is what the phase label explains.
        const progressCell = (j) => {
            if (!QUEUE_ACTIVE_STATES.includes(j.status)) {
                return j.saved_bytes > 0
                    ? `<span class="text-xs text-green-400">−${(j.saved_bytes / (1024 * 1024)).toFixed(1)}MB</span>`
                    : '<span class="text-xs text-gray-600">—</span>';
            }
            const pct = Math.max(0, Math.min(100, Number(j.progress_pct) || 0));
            const phase = j.phase || j.status;
            return `<div class="min-w-[120px]">
                        <div class="h-1.5 rounded-full bg-ink/10 overflow-hidden">
                            <div class="h-full bg-accent transition-all" style="width: ${pct}%"></div>
                        </div>
                        <div class="text-[10px] text-gray-500 mt-1 truncate">${escapeHtml(phase)} ${Math.round(pct)}%${eta(j.eta_seconds)}</div>
                    </div>`;
        };

        tbody.innerHTML = jobs.map(j => `
            <tr class="border-b border-ink/5 hover:bg-ink/5 transition-colors">
                <td class="px-4 py-3">${statusBadge(j.status)}</td>
                <td class="px-4 py-3 text-text-main text-xs font-mono truncate max-w-[200px]" title="${escapeHtml(j.file_path)}">${escapeHtml(j.file_path.split(/[\\/]/).pop())}</td>
                <td class="px-4 py-3">${progressCell(j)}</td>
                <td class="px-4 py-3 text-gray-500 text-xs hidden lg:table-cell">${escapeHtml(j.worker_id || '—')}</td>
                <td class="px-4 py-3 text-gray-500 text-xs hidden md:table-cell">${timeAgo(j.created_at)}</td>
                <td class="px-4 py-3 text-gray-400 text-xs hidden md:table-cell">${escapeHtml(j.result_message || (j.saved_bytes > 0 ? `Saved ${(j.saved_bytes / (1024 * 1024)).toFixed(1)}MB` : '—'))}</td>
                <td class="px-4 py-3 text-right">${QUEUE_ACTIVE_STATES.includes(j.status) ? `<button onclick="cancelQueueJob(${j.id})" class="text-xs text-red-400 hover:text-red-300 transition-colors">Cancel</button>` : ''}</td>
            </tr>
        `).join('');
    } catch (e) {
        console.error('Queue status error:', e);
    }
}

async function cancelQueueJob(jobId) {
    try {
        await fetch('/api/queue/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: jobId })
        });
        loadQueueStatus();
    } catch (e) {
        console.error('Cancel error:', e);
    }
}

// Fast enough to watch a progress bar move, slow enough to stay quiet when
// nothing is running.
function _retuneQueuePolling(hasActiveJobs) {
    if (!_queuePollInterval) return;
    const wanted = hasActiveJobs ? 2000 : 10000;
    if (wanted === _queuePollMs) return;
    clearInterval(_queuePollInterval);
    _queuePollMs = wanted;
    _queuePollInterval = setInterval(loadQueueStatus, wanted);
}

// Start polling when queue section is visible
function startQueuePolling() {
    if (_queuePollInterval) return;
    _queuePollMs = 2000;
    _queuePollInterval = setInterval(loadQueueStatus, _queuePollMs);
    loadQueueStatus();
}

function stopQueuePolling() {
    if (_queuePollInterval) clearInterval(_queuePollInterval);
    _queuePollInterval = null;
    _queuePollMs = 0;
}

// Hook into settings nav to start/stop polling
document.addEventListener('click', (e) => {
    const navItem = e.target.closest('.settings-nav-item[data-section]');
    if (navItem) {
        if (navItem.dataset.section === 'queue') startQueuePolling();
        else stopQueuePolling();
    }
});

window.loadQueueStatus = loadQueueStatus;
window.cancelQueueJob = cancelQueueJob;

// ============================================================================
// INCLUDE PHOTOS TOGGLE + CONFIRMATION MODAL
// ============================================================================

/**
 * Called when the "Include Photos" checkbox changes.
 * If the user is DISABLING photos, show the confirmation modal.
 * If the user is ENABLING photos, just mark settings as unsaved.
 * @param {HTMLInputElement} checkbox
 */
function onIncludePhotosChange(checkbox) {
    if (!checkbox.checked) {
        // Temporarily restore checked state until user confirms
        checkbox.checked = true;
        // Show the confirmation modal
        const modal = document.getElementById('removePhotosModal');
        if (modal) modal.classList.remove('hidden');
    } else {
        markSettingsUnsaved();
    }
}

/**
 * Handle user choice in the "Remove Photos" modal.
 * @param {boolean} removeFromDb - true = remove, false = keep
 */
async function confirmRemovePhotos(removeFromDb) {
    const modal = document.getElementById('removePhotosModal');
    const checkbox = document.getElementById('settingsScanImages');

    if (modal) modal.classList.add('hidden');

    if (!removeFromDb) {
        // User chose to keep photos → toggle stays OFF (user wanted to disable)
        if (checkbox) checkbox.checked = false;
        markSettingsUnsaved();
        return;
    }

    // User confirmed removal → uncheck, save setting, then purge DB
    if (checkbox) checkbox.checked = false;
    markSettingsUnsaved();

    try {
        const resp = await fetch('/api/settings/remove-photos', { method: 'POST' });
        if (resp.ok) {
            const data = await resp.json();
            showSettingsToast(`Removed ${data.deleted} photo(s) from library`, false);
        } else {
            showSettingsToast('Could not remove photos', true);
        }
    } catch (e) {
        console.error('Remove photos error:', e);
        showSettingsToast('Error removing photos', true);
    }
}

window.onIncludePhotosChange = onIncludePhotosChange;
window.confirmRemovePhotos = confirmRemovePhotos;

// Encoding quality preset selection
function selectEncodingPreset(value) {
    const presets = ['fast', 'balanced', 'best'];
    presets.forEach(p => {
        const btn = document.querySelector(`.encoding-preset-btn[data-value="${p}"]`);
        if (btn) btn.classList.toggle('active', p === value);
    });
    const hidden = document.getElementById('settingsEncodingPreset');
    if (hidden) hidden.value = value;
}
window.selectEncodingPreset = selectEncodingPreset;
window.loadEmbeddingStatus = loadEmbeddingStatus;
