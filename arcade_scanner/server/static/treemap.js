/**
 * Treemap Visualization UI Module
 *
 * Handles rendering and interaction for the treemap view.
 * Uses squarify algorithm from treemap_layout.js for layout calculations.
 *
 * Dependencies:
 * - treemap_layout.js (squarify function)
 * - engine.js (filteredVideos, searchTerm, openCinema, updateURL, currentLayout)
 */

// --- STATE ---
let treemapCurrentFolder = null; // null = show all folders, string = show files in that folder
let treemapUseLog = false; // Log scale toggle

/**
 * Get current folder for treemap drill-down
 * @returns {string|null} Current folder path or null for folder view
 */
function getTreemapCurrentFolder() {
    return treemapCurrentFolder;
}

/**
 * Set current folder for treemap drill-down
 * @param {string|null} folder - Folder path or null for folder view
 */
function setTreemapCurrentFolder(folder) {
    treemapCurrentFolder = folder;
}

/**
 * Toggle between linear and logarithmic scale for treemap sizing
 */
function toggleTreemapScale() {
    treemapUseLog = document.getElementById('treemapLogToggle').checked;
    renderTreemap();
}

/**
 * Render the treemap visualization
 * Shows either folder view (all folders) or file view (files in selected folder)
 * Uses canvas for efficient rendering of potentially thousands of items
 */
function renderTreemap() {
    const container = document.getElementById('treemapContainer');
    if (!container) return;

    // Create or get canvas
    let canvas = document.getElementById('treemapCanvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'treemapCanvas';
        container.appendChild(canvas);
    }

    const ctx = canvas.getContext('2d');
    const rect = container.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Access filtered videos from engine.js
    const videos = window.filteredVideos || [];

    if (videos.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '20px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Keine Videos gefunden', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Update legend to show current path
    updateTreemapLegend();

    if (treemapCurrentFolder === null) {
        // FOLDER-ONLY VIEW: Show only folder blocks
        renderFolderView(ctx, canvas, videos);
    } else {
        // DRILLED-DOWN VIEW: Show files in selected folder
        renderFileView(ctx, canvas, treemapCurrentFolder, videos);
    }
}

/**
 * Render folder-level treemap view
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} videos - Filtered video list
 */
function renderFolderView(ctx, canvas, videos) {
    // Group videos by folder
    const folderMap = new Map();
    videos.forEach(v => {
        const path = v.FilePath;
        const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        const folder = lastIdx >= 0 ? path.substring(0, lastIdx) : 'Root';

        if (!folderMap.has(folder)) {
            folderMap.set(folder, { items: [], totalSize: 0, highCount: 0, okCount: 0 });
        }
        const f = folderMap.get(folder);
        f.items.push(v);
        f.totalSize += v.Size_MB;
        if (v.Status === 'HIGH') f.highCount++;
        else f.okCount++;
    });

    // Create folder data for squarify
    const folderData = [];
    folderMap.forEach((value, key) => {
        const parts = key.split(/[\\/]/);
        const shortName = parts[parts.length - 1] || 'Root';
        folderData.push({
            folder: key,
            shortName: shortName,
            size: value.totalSize,
            count: value.items.length,
            highCount: value.highCount,
            okCount: value.okCount
        });
    });

    // Sort and layout
    const blocks = squarify(folderData, 0, 0, canvas.width, canvas.height, treemapUseLog);

    // Folder color gradients - darker tones to complement video gradients
    const folderGradients = [
        ['#4c1d95', '#6b21a8'], // Deep purple
        ['#1e3a8a', '#3b82f6'], // Deep to bright blue
        ['#7c2d12', '#dc2626'], // Brown to red
        ['#14532d', '#16a34a'], // Dark to bright green
        ['#78350f', '#d97706'], // Brown to amber
        ['#1f2937', '#4b5563']  // Dark gray to gray
    ];

    // Get search term from engine.js
    const searchTerm = window.searchTerm || '';

    // Render folder blocks
    blocks.forEach((block, idx) => {
        // Base folder gradient
        const colors = folderGradients[idx % folderGradients.length];
        const gradient = ctx.createLinearGradient(block.x, block.y, block.x + block.width, block.y + block.height);
        gradient.addColorStop(0, colors[0]);
        gradient.addColorStop(1, colors[1]);
        ctx.fillStyle = gradient;
        ctx.fillRect(block.x, block.y, block.width, block.height);

        // Status indicator bar at bottom (proportional HIGH vs OK)
        const barHeight = Math.min(8, block.height * 0.1);
        if (block.height > 30) {
            const highRatio = block.highCount / block.count;
            const highWidth = block.width * highRatio;

            // Gold gradient for HIGH
            const highGradient = ctx.createLinearGradient(block.x, block.y + block.height - barHeight, block.x + highWidth, block.y + block.height);
            highGradient.addColorStop(0, '#E3A857');
            highGradient.addColorStop(1, '#E0D5A3');
            ctx.fillStyle = highGradient;
            ctx.fillRect(block.x, block.y + block.height - barHeight, highWidth, barHeight);

            // Olive-khaki gradient for OK
            const okGradient = ctx.createLinearGradient(block.x + highWidth, block.y + block.height - barHeight, block.x + block.width, block.y + block.height);
            okGradient.addColorStop(0, '#568203');
            okGradient.addColorStop(1, '#F0E68C');
            ctx.fillStyle = okGradient;
            ctx.fillRect(block.x + highWidth, block.y + block.height - barHeight, block.width - highWidth, barHeight);
        }

        // Border
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 2;
        ctx.strokeRect(block.x, block.y, block.width, block.height);

        // Search highlight - glow effect for folders containing matching files
        if (searchTerm) {
            const hasMatch = videos.some(v => {
                const vPath = v.FilePath;
                const vLastIdx = Math.max(vPath.lastIndexOf('/'), vPath.lastIndexOf('\\'));
                const vFolder = vLastIdx >= 0 ? vPath.substring(0, vLastIdx) : 'Root';
                return vFolder === block.folder && v.FilePath.toLowerCase().includes(searchTerm.toLowerCase());
            });
            if (hasMatch) {
                ctx.save();
                ctx.strokeStyle = '#00ffff';
                ctx.lineWidth = 4;
                ctx.shadowColor = '#00ffff';
                ctx.shadowBlur = 20;
                ctx.strokeRect(block.x + 2, block.y + 2, block.width - 4, block.height - 4);
                ctx.restore();
            }
        }

        // Labels
        if (block.width > 60 && block.height > 40) {
            ctx.fillStyle = '#fff';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            const centerX = block.x + block.width / 2;
            const centerY = block.y + block.height / 2 - 8;

            // Folder name
            ctx.font = 'bold 13px Inter, sans-serif';

            const maxChars = Math.floor(block.width / 8);
            let displayName = block.shortName;
            if (displayName.length > maxChars && maxChars > 3) {
                displayName = displayName.substring(0, maxChars - 3) + '...';
            }
            ctx.fillText(displayName, centerX, centerY);

            // Count and size
            ctx.font = '11px Inter, sans-serif';
            ctx.fillStyle = '#ccc';
            const sizeText = block.size > 1024
                ? `${(block.size / 1024).toFixed(1)} GB`
                : `${block.size.toFixed(0)} MB`;
            ctx.fillText(`${block.count} Videos • ${sizeText}`, centerX, centerY + 18);
        }
    });

    // Store for interaction
    canvas.treemapBlocks = blocks;
    canvas.treemapMode = 'folders';
}

/**
 * Render file-level treemap view (drilled into a folder)
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {string} folderPath - Path of folder to show files for
 * @param {Array} videos - Filtered video list
 */
function renderFileView(ctx, canvas, folderPath, videos) {
    // Get videos in this folder
    const videosInFolder = videos.filter(v => {
        const path = v.FilePath;
        const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        const folder = lastIdx >= 0 ? path.substring(0, lastIdx) : 'Root';
        return folder === folderPath;
    });

    if (videosInFolder.length === 0) {
        treemapCurrentFolder = null;
        renderTreemap();
        return;
    }

    // Prepare data
    const treemapData = videosInFolder.map(v => ({
        video: v,
        size: v.Size_MB,
        name: v.FilePath.split(/[\\/]/).pop()
    }));

    // Layout
    const blocks = squarify(treemapData, 0, 0, canvas.width, canvas.height, treemapUseLog);

    // Get search term from engine.js
    const searchTerm = window.searchTerm || '';

    // Render video tiles with gradients
    blocks.forEach(block => {
        const video = block.video;

        // Color by status - gradient for HIGH, flat for OK
        if (video.Status === 'HIGH') {
            const gradient = ctx.createLinearGradient(block.x, block.y, block.x + block.width, block.y + block.height);
            gradient.addColorStop(0, '#E3A857');
            gradient.addColorStop(1, '#E0D5A3');
            ctx.fillStyle = gradient;
        } else {
            const gradient = ctx.createLinearGradient(block.x, block.y, block.x + block.width, block.y);
            gradient.addColorStop(0, '#568203');
            gradient.addColorStop(1, '#F0E68C');
            ctx.fillStyle = gradient;
        }
        ctx.fillRect(block.x, block.y, block.width, block.height);

        // Border
        ctx.strokeStyle = '#1f2937';
        ctx.lineWidth = 1;
        ctx.strokeRect(block.x, block.y, block.width, block.height);

        // Search highlight - glow effect for matching files
        if (searchTerm && block.name.toLowerCase().includes(searchTerm.toLowerCase())) {
            ctx.save();
            ctx.strokeStyle = '#00ffff';
            ctx.lineWidth = 3;
            ctx.shadowColor = '#00ffff';
            ctx.shadowBlur = 15;
            ctx.strokeRect(block.x + 2, block.y + 2, block.width - 4, block.height - 4);
            ctx.restore();
        }

        // Labels
        if (block.width > 80 && block.height > 50) {
            // Use dark text on bright backgrounds (HIGH/yellow), white on dark (OK/green)
            ctx.fillStyle = video.Status === 'HIGH' ? '#000' : '#fff';

            // Dynamic font size based on tile dimensions - larger tiles get bigger text
            const minDim = Math.min(block.width, block.height);
            const titleFontSize = Math.max(14, Math.min(32, minDim / 4));
            const subFontSize = Math.max(11, Math.min(22, minDim / 6));

            ctx.font = `600 ${titleFontSize}px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            const centerX = block.x + block.width / 2;
            const centerY = block.y + block.height / 2;

            // Calculate max chars based on tile width and font size
            const charWidth = titleFontSize * 0.55;
            const maxChars = Math.floor((block.width - 20) / charWidth);
            const displayName = block.name.length > maxChars
                ? block.name.substring(0, maxChars - 3) + '...'
                : block.name;

            ctx.fillText(displayName, centerX, centerY - titleFontSize * 0.6);
            ctx.font = `400 ${subFontSize}px Inter, sans-serif`;
            ctx.fillStyle = video.Status === 'HIGH' ? 'rgba(0,0,0,0.7)' : 'rgba(255,255,255,0.85)';
            ctx.fillText(`${video.Size_MB.toFixed(0)} MB`, centerX, centerY + subFontSize * 0.8);
        }
    });

    // Store for interaction
    canvas.treemapBlocks = blocks;
    canvas.treemapMode = 'files';
}

/**
 * Update treemap legend to show current navigation state
 */
function updateTreemapLegend() {
    const legend = document.getElementById('treemapLegend');
    if (!legend) return;

    const titleEl = legend.querySelector('.legend-title');
    const hintEl = legend.querySelector('.legend-hint');
    const backBtn = document.getElementById('treemapBackBtn');

    const videos = window.filteredVideos || [];

    if (treemapCurrentFolder === null) {
        titleEl.textContent = 'SPEICHER TREEMAP';
        hintEl.textContent = 'Klicken zum Reinzoomen';
        if (backBtn) backBtn.style.display = 'none';
    } else {
        const parts = treemapCurrentFolder.split(/[\\/]/);
        const shortName = parts[parts.length - 1] || 'Root';
        // Count videos in this folder
        const count = videos.filter(v => {
            const path = v.FilePath;
            const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
            const folder = lastIdx >= 0 ? path.substring(0, lastIdx) : 'Root';
            return folder === treemapCurrentFolder;
        }).length;
        titleEl.innerHTML = `📁 ${shortName} <span style="opacity:0.6; font-size:0.85em;">(${count} Videos)</span>`;
        hintEl.textContent = 'Klicken zum Abspielen';
        if (backBtn) backBtn.style.display = 'inline-flex';
    }
}

/**
 * Zoom out from file view to folder view
 */
function treemapZoomOut() {
    treemapCurrentFolder = null;
    renderTreemap();
    // Call updateURL from engine.js if available
    if (typeof updateURL === 'function') {
        updateURL();
    }
}

/**
 * Set up mouse interaction handlers for treemap canvas
 */
function setupTreemapInteraction() {
    const canvas = document.getElementById('treemapCanvas');
    if (!canvas || canvas.hasTreemapListeners) return;

    // Create tooltip if it doesn't exist
    let tooltip = document.getElementById('treemapTooltip');
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = 'treemapTooltip';
        document.body.appendChild(tooltip);
    }

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const block = canvas.treemapBlocks?.find(b =>
            x >= b.x && x <= b.x + b.width &&
            y >= b.y && y <= b.y + b.height
        );

        if (block) {
            canvas.style.cursor = 'pointer';
            tooltip.style.opacity = '1';
            tooltip.style.left = e.clientX + 15 + 'px';
            tooltip.style.top = e.clientY + 15 + 'px';

            if (canvas.treemapMode === 'folders') {
                // Folder tooltip
                const sizeText = block.size > 1024
                    ? `${(block.size / 1024).toFixed(1)} GB`
                    : `${block.size.toFixed(0)} MB`;
                tooltip.innerHTML = `
                    <strong>📁 ${block.shortName}</strong>
                    Videos: ${block.count}<br>
                    Größe: ${sizeText}<br>
                    HIGH: ${block.highCount} • OK: ${block.okCount}
                `;
            } else {
                // File tooltip with thumbnail
                const video = block.video;
                const thumbUrl = `thumbnails/${video.thumb}`;
                const isHevc = (video.codec || '').includes('hevc') || (video.codec || '').includes('h265');
                tooltip.innerHTML = `
                    <div style="display: flex; gap: 12px; align-items: flex-start;">
                        <img src="${thumbUrl}" style="width: 120px; height: 68px; object-fit: cover; border-radius: 4px; background: #333;" onerror="this.style.display='none'">
                        <div>
                            <strong style="display: block; margin-bottom: 6px;">${block.name}</strong>
                            Größe: ${video.Size_MB.toFixed(1)} MB<br>
                            Bitrate: ${video.Bitrate_Mbps.toFixed(1)} Mbps<br>
                            Codec: ${isHevc ? 'HEVC' : (video.codec || 'Unknown').toUpperCase()}<br>
                            Status: <span style="color: ${video.Status === 'HIGH' ? '#f59e0b' : '#10b981'}">${video.Status}</span>
                        </div>
                    </div>
                `;
            }
        } else {
            canvas.style.cursor = 'default';
            tooltip.style.opacity = '0';
        }
    });

    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const block = canvas.treemapBlocks?.find(b =>
            x >= b.x && x <= b.x + b.width &&
            y >= b.y && y <= b.y + b.height
        );

        if (block) {
            if (canvas.treemapMode === 'folders') {
                // Drill down into folder
                treemapCurrentFolder = block.folder;
                renderTreemap();
                if (typeof updateURL === 'function') {
                    updateURL();
                }
            } else {
                // Open cinema for file
                const mockContainer = {
                    getAttribute: (attr) => attr === 'data-path' ? block.video.FilePath : null,
                    closest: () => null
                };
                if (typeof openCinema === 'function') {
                    openCinema(mockContainer);
                }
            }
        }
    });

    canvas.addEventListener('mouseleave', () => {
        tooltip.style.opacity = '0';
    });

    canvas.hasTreemapListeners = true;

    // Add legend click handler for zoom out
    const legend = document.getElementById('treemapLegend');
    if (legend && !legend.hasClickListener) {
        legend.style.cursor = 'pointer';
        legend.addEventListener('click', () => {
            if (treemapCurrentFolder !== null) {
                treemapZoomOut();
            }
        });
        legend.hasClickListener = true;
    }
}

/**
 * Handle ESC key for treemap zoom out
 * Called from engine.js keydown handler
 * @returns {boolean} True if handled, false otherwise
 */
function handleTreemapEscape() {
    const currentLayout = window.currentLayout || 'grid';
    if (currentLayout === 'treemap' && treemapCurrentFolder !== null) {
        treemapZoomOut();
        return true;
    }
    return false;
}

/**
 * Handle window resize for treemap
 * Called from engine.js resize handler
 */
function handleTreemapResize() {
    const currentLayout = window.currentLayout || 'grid';
    if (currentLayout === 'treemap') {
        renderTreemap();
    }
}

// --- GLOBAL EXPORTS ---
// Expose functions needed by engine.js and HTML onclick handlers
window.toggleTreemapScale = toggleTreemapScale;
window.renderTreemap = renderTreemap;
window.setupTreemapInteraction = setupTreemapInteraction;
window.treemapZoomOut = treemapZoomOut;
window.getTreemapCurrentFolder = getTreemapCurrentFolder;
window.setTreemapCurrentFolder = setTreemapCurrentFolder;
window.handleTreemapEscape = handleTreemapEscape;
window.handleTreemapResize = handleTreemapResize;
