// cards.js - Extracted from engine.js

// --- CARD ACTIONS ---

/**
 * Toggle hidden/vault state for a video card
 * Updates local state, sends to server, and animates card out if no longer visible
 *
 * @param {HTMLElement} card - The video card container element
 */
function toggleHidden(card) {
    const path = card.getAttribute('data-path');
    const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
    if (!video) return;

    video.hidden = !video.hidden;
    fetch(`/hide?path=` + encodeURIComponent(path) + `&state=${video.hidden}`);

    // Update specific card UI instantly
    const btn = card.querySelector('.hide-toggle-btn .material-icons');
    btn.innerText = video.hidden ? 'visibility' : 'visibility_off';

    // Animate out if no longer matching workspace
    const shouldHide = (workspaceMode === 'lobby' && video.hidden) || (workspaceMode === 'vault' && !video.hidden);
    if (shouldHide) {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.8)';
        setTimeout(() => {
            filterAndSort();
            renderCollections(); // Update sidebar counts
        }, 300);
    } else {
        renderCollections(); // Update immediately if not animating out
    }
}

/**
 * Toggle favorite state for a video card
 * Updates local state, sends to server, and updates star icon
 *
 * @param {HTMLElement} card - The video card container element
 */
function toggleFavorite(card) {
    const path = card.getAttribute('data-path');
    const video = window.ALL_VIDEOS.find(v => v.FilePath === path);
    if (!video) return;

    video.favorite = !video.favorite;
    fetch(`/favorite?path=` + encodeURIComponent(path) + `&state=${video.favorite}`);

    const starBtn = card.querySelector('.favorite-btn');
    const starIcon = starBtn.querySelector('.material-icons');

    if (video.favorite) {
        starBtn.classList.add('active');
        starIcon.innerText = 'star';
        starBtn.title = 'Favorit';
    } else {
        starBtn.classList.remove('active');
        starIcon.innerText = 'star_border';
        starBtn.title = 'Add to Favorites';
    }

    if (workspaceMode === 'favorites' && !video.favorite) {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.8)';
        setTimeout(() => {
            filterAndSort();
            renderCollections(); // Update sidebar counts
        }, 300);
    } else {
        renderCollections(); // Update immediately
    }
}

/**
 * Set favorite state for all selected videos
 * Batch operation that updates multiple items at once
 *
 * @param {boolean} state - True to favorite, false to unfavorite
 */
function triggerBatchFavorite(state) {
    const selected = document.querySelectorAll('.video-card-container input[type="checkbox"]:checked');
    if (selected.length === 0) return;

    const paths = Array.from(selected).map(cb => cb.closest('.video-card-container').getAttribute('data-path'));

    // Update Local Data
    paths.forEach(p => {
        const v = window.ALL_VIDEOS.find(vid => vid.FilePath === p);
        if (v) v.favorite = state;
    });

    // Notify Server
    fetch(`/batch_favorite?paths=` + encodeURIComponent(paths.join(',')) + `&state=${state}`);

    // Update UI
    selected.forEach(cb => {
        const card = cb.closest('.video-card-container');
        const starBtn = card.querySelector('.favorite-btn');
        const starIcon = starBtn.querySelector('.material-icons');

        if (state) {
            starBtn.classList.add('active');
            starIcon.innerText = 'star';
            starBtn.title = 'Favorit';
        } else {
            starBtn.classList.remove('active');
            starIcon.innerText = 'star_border';
            starBtn.title = 'Add to Favorites';
        }
    });

    clearSelection();
    if (workspaceMode === 'favorites' && !state) {
        setTimeout(() => filterAndSort(), 350);
    }
}

/**
 * Trigger bulk deletion for selected videos
 * Asks for confirmation before sending request to backend
 */
async function triggerBatchDelete() {
    const selected = document.querySelectorAll('.video-card-container input[type="checkbox"]:checked');
    if (selected.length === 0) return;

    if (!confirm(`Are you sure you want to PERMANENTLY delete these ${selected.length} files from disk? This cannot be undone.`)) {
        return;
    }

    const paths = Array.from(selected).map(cb => cb.closest('.video-card-container').getAttribute('data-path'));

    try {
        const response = await fetch('/api/bulk_delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paths: paths })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Successfully deleted ${result.deleted.length} files`, 'success');

            // Update local data
            window.ALL_VIDEOS = window.ALL_VIDEOS.filter(v => !result.deleted.includes(v.FilePath));

            // Clear selection and re-render
            clearSelection();
            filterAndSort();
        } else {
            showToast(`Deletion failed: ${result.error || 'Unknown error'}`, 'error');
        }
    } catch (err) {
        console.error('Bulk delete error:', err);
        showToast('Failed to connect to server for deletion', 'error');
    }
}

