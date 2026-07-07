// batch_operations.js - Extracted from engine.js

// --- BATCH OPERATIONS ---
const BATCH_MIN_SIZE_MB = 50; // Files smaller than this are skipped by optimizer

/**
 * Update the batch action bar UI based on current selection
 * Shows/hides the bar and updates count display including skip warnings
 */
function updateBatchSelection() {
    const selectedCheckboxes = document.querySelectorAll('.video-card-container input:checked');
    const count = selectedCheckboxes.length;
    const bar = document.getElementById('batchBar');

    // Calculate how many will be skipped due to size
    let processableCount = 0;
    let skippedCount = 0;

    selectedCheckboxes.forEach(cb => {
        const container = cb.closest('.video-card-container');
        const path = container.getAttribute('data-path');
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (video) {
            if (video.Size_MB >= BATCH_MIN_SIZE_MB) {
                processableCount++;
            } else {
                skippedCount++;
            }
        }
    });

    // Update display
    const countEl = document.getElementById('batchCount');
    const skipWarning = document.getElementById('batchSkipWarning');

    if (countEl) countEl.innerText = count;

    // Show/create skip warning
    if (skippedCount > 0 && count > 0) {
        if (!skipWarning) {
            // Create warning element if it doesn't exist
            const warningSpan = document.createElement('span');
            warningSpan.id = 'batchSkipWarning';
            warningSpan.className = 'batch-skip-warning';
            warningSpan.style.cssText = 'color: #F4B342; font-size: 0.85rem; display: flex; align-items: center; gap: 4px;';
            const countSpan = document.getElementById('batchCount');
            if (countSpan && countSpan.parentElement) {
                countSpan.parentElement.insertAdjacentElement('afterend', warningSpan);
            }
        }
        const warning = document.getElementById('batchSkipWarning');
        if (warning) {
            warning.innerHTML = `<span class="material-icons" style="font-size: 16px;">warning</span> ${skippedCount} under ${BATCH_MIN_SIZE_MB}MB`;
            warning.title = `${skippedCount} file(s) will be skipped because they are already under ${BATCH_MIN_SIZE_MB}MB`;
        }
    } else if (skipWarning) {
        skipWarning.innerHTML = '';
    }

    if (count > 0) {
        bar.classList.add('active');
        bar.style.transform = 'translateX(-50%) translateY(0)';
    } else {
        bar.classList.remove('active');
        bar.style.transform = 'translateX(-50%) translateY(8rem)';
    }

    // Toggle selection mode class on grid for visual feedback
    const grid = document.getElementById('videoGrid');
    if (grid) {
        if (count > 0) {
            grid.classList.add('selection-mode');
        } else {
            grid.classList.remove('selection-mode');
        }
    }
}


/**
 * Clear all checkbox selections and update the batch bar
 */
function clearSelection() {
    document.querySelectorAll('.video-card-container input:checked').forEach(i => i.checked = false);
    updateBatchSelection();
}

// --- BATCH SELECTION HELPERS ---
let lastCheckedPath = null;

/**
 * Check if selection mode is active (at least one video selected)
 * @returns {boolean} True if any videos are selected
 */
function isSelectionMode() {
    return document.querySelectorAll('.video-card-container input:checked').length > 0;
}

/**
 * Handle card click - either toggle selection (if in selection mode) or open cinema
 * @param {MouseEvent} event - Click event
 * @param {HTMLElement} cardMedia - The card-media element that was clicked
 */
function handleCardClick(event, cardMedia) {
    // If in selection mode, toggle checkbox instead of opening cinema
    if (isSelectionMode()) {
        event.preventDefault();
        event.stopPropagation();
        const container = cardMedia.closest('.video-card-container');
        const checkbox = container.querySelector('input[type="checkbox"]');
        if (checkbox) {
            checkbox.checked = !checkbox.checked;
            const path = container.getAttribute('data-path');
            toggleSelection(checkbox, event, path);
        }
        return;
    }
    // Normal behavior - open cinema
    openCinema(cardMedia);
}

/**
 * Handle checkbox toggle with shift-click range selection support
 *
 * @param {HTMLInputElement} checkbox - The checkbox element
 * @param {MouseEvent} event - Click event to check for shift key
 * @param {string} path - File path of the video
 */
function toggleSelection(checkbox, event, path) {
    if (event.shiftKey && lastCheckedPath) {
        // Shift+Click Logic
        const currentIndex = filteredVideos.findIndex(v => v.FilePath === path);
        const lastIndex = filteredVideos.findIndex(v => v.FilePath === lastCheckedPath);

        if (currentIndex !== -1 && lastIndex !== -1) {
            const start = Math.min(currentIndex, lastIndex);
            const end = Math.max(currentIndex, lastIndex);

            const targetState = checkbox.checked;

            // Apply to range
            for (let i = start; i <= end; i++) {
                const video = filteredVideos[i];
                const container = document.querySelector(`.video-card-container[data-path="${CSS.escape(video.FilePath)}"]`);
                if (container) {
                    const cb = container.querySelector('input[type="checkbox"]');
                    if (cb) cb.checked = targetState;
                }
            }
        }
    }

    // Update state
    if (checkbox.checked) {
        lastCheckedPath = path;
    } else {
        lastCheckedPath = null; // Reset if unchecked? Or keep last checked? Keeping enables complex patterns.
        // Usually shift-selection anchors on the last *interaction*.
        lastCheckedPath = path;
    }

    updateBatchSelection();
}

/**
 * Select all videos currently visible in the filtered list
 */
function selectAllVisible() {
    // Select all videos in the current filtered list
    filteredVideos.forEach(video => {
        const container = document.querySelector(`.video-card-container[data-path="${CSS.escape(video.FilePath)}"]`);
        if (container) {
            const checkbox = container.querySelector('input[type="checkbox"]');
            if (checkbox) checkbox.checked = true;
        }
    });
    updateBatchSelection();
}

/**
 * Set hidden/vault state for all selected videos
 *
 * @param {boolean} state - True to hide (move to vault), false to restore
 */
function triggerBatchHide(state) {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));

    fetch(`/batch_hide?paths=` + encodeURIComponent(paths.join(',')) + `&state=${state}`);

    paths.forEach(p => {
        const v = window.ALL_VIDEOS.find(vid => vid.FilePath === p);
        if (v) v.hidden = state;
    });

    filterAndSort();
    clearSelection();
}

/**
 * Start batch compression for all selected videos
 * Filters out files under BATCH_MIN_SIZE_MB and shows confirmation dialog
 * with details about which files will be processed vs skipped
 */
function triggerBatchCompress() {
    const selected = document.querySelectorAll('.video-card-container input:checked');
    const paths = Array.from(selected).map(i => i.closest('.video-card-container').getAttribute('data-path'));

    if (paths.length === 0) return;

    // Categorize files by processable vs skipped
    const processable = [];
    const skipped = [];

    paths.forEach(path => {
        const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
        if (video) {
            const filename = path.split(/[\\/]/).pop();
            if (video.Size_MB >= BATCH_MIN_SIZE_MB) {
                processable.push({ path, filename, size: video.Size_MB });
            } else {
                skipped.push({ path, filename, size: video.Size_MB });
            }
        }
    });

    // Build detailed confirmation message
    let message = `Batch Compression Summary\n${'─'.repeat(40)}\n`;
    message += `Will process: ${processable.length} file(s)\n`;

    if (skipped.length > 0) {
        message += `Will skip: ${skipped.length} file(s) (under ${BATCH_MIN_SIZE_MB}MB)\n`;
        message += `\nSkipped files (already compact):\n`;
        skipped.slice(0, 5).forEach(f => {
            const shortName = f.filename.length > 40 ? f.filename.substring(0, 37) + '...' : f.filename;
            message += `   • ${shortName} (${f.size.toFixed(1)} MB)\n`;
        });
        if (skipped.length > 5) {
            message += `   ... and ${skipped.length - 5} more\n`;
        }
    }

    if (processable.length === 0) {
        alert(`No files to process!\n\nAll ${skipped.length} selected file(s) are under ${BATCH_MIN_SIZE_MB}MB and will be skipped.\n\nThese files are already compact and don't need optimization.`);
        return;
    }

    message += `\n${'─'.repeat(40)}\nProceed with ${processable.length} file(s)?`;

    if (confirm(message)) {
        if (window.IS_DOCKER) {
            // Docker mode: queue all files for remote Mac encoding
            queueBatchForRemoteEncode(processable.map(f => f.path));
        } else {
            // Local mode: use batch_compress endpoint
            // Use ||| as separator to avoid issues with commas in filenames
            fetch(`/batch_compress?paths=` + encodeURIComponent(paths.join('|||')));
            alert(`Batch Optimierung gestartet!\n\n${processable.length} file(s) will be processed.\n${skipped.length} file(s) skipped (under ${BATCH_MIN_SIZE_MB}MB).`);
        }
        clearSelection();
    }
}



