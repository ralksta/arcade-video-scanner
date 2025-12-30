// Squarified Treemap Layout Algorithm
// Based on the algorithm by Bruls, Huizing, and van Wijk

function squarify(data, x, y, width, height, useLog = false) {
    if (!data || data.length === 0) return [];

    // Helper to get effective size
    const getSize = (item) => useLog ? Math.log(Math.max(item.size, 1)) : item.size;

    // Sort by effective size descending
    const sorted = [...data].sort((a, b) => getSize(b) - getSize(a));
    const totalSize = sorted.reduce((sum, item) => sum + getSize(item), 0);

    if (totalSize === 0) return [];

    const blocks = [];

    // Normalize sizes to area for creating rectangles
    const scale = (width * height) / totalSize;
    const normalized = sorted.map(item => ({
        ...item,
        normalizedSize: getSize(item) * scale,
        // Keep original size for display/metadata if needed, 
        // though ...item should already have it.
    }));

    function worstAspectRatio(row, length) {
        if (row.length === 0 || length <= 0) return Infinity;

        const rowSum = row.reduce((sum, item) => sum + item.normalizedSize, 0);
        if (rowSum <= 0) return Infinity;

        const rowMax = Math.max(...row.map(item => item.normalizedSize));
        const rowMin = Math.min(...row.map(item => item.normalizedSize));

        const ratio1 = (length * length * rowMax) / (rowSum * rowSum);
        const ratio2 = (rowSum * rowSum) / (length * length * rowMin);

        return Math.max(ratio1, ratio2);
    }

    function layoutRow(row, rowX, rowY, rowWidth, rowHeight, isHorizontal) {
        const rowSum = row.reduce((sum, item) => sum + item.normalizedSize, 0);

        if (isHorizontal) {
            // Row fills full height, width based on area
            const actualRowWidth = rowSum / rowHeight;
            let currentY = rowY;

            row.forEach(item => {
                const itemHeight = item.normalizedSize / actualRowWidth;
                blocks.push({
                    ...item,
                    x: Math.round(rowX),
                    y: Math.round(currentY),
                    width: Math.round(actualRowWidth),
                    height: Math.round(itemHeight)
                });
                currentY += itemHeight;
            });

            return {
                x: rowX + actualRowWidth,
                y: rowY,
                width: rowWidth - actualRowWidth,
                height: rowHeight
            };
        } else {
            // Row fills full width, height based on area  
            const actualRowHeight = rowSum / rowWidth;
            let currentX = rowX;

            row.forEach(item => {
                const itemWidth = item.normalizedSize / actualRowHeight;
                blocks.push({
                    ...item,
                    x: Math.round(currentX),
                    y: Math.round(rowY),
                    width: Math.round(itemWidth),
                    height: Math.round(actualRowHeight)
                });
                currentX += itemWidth;
            });

            return {
                x: rowX,
                y: rowY + actualRowHeight,
                width: rowWidth,
                height: rowHeight - actualRowHeight
            };
        }
    }

    function squarifyRecursive(children, currentX, currentY, currentWidth, currentHeight) {
        if (children.length === 0 || currentWidth <= 0 || currentHeight <= 0) return;

        // Only one item left - give it remaining space
        if (children.length === 1) {
            blocks.push({
                ...children[0],
                x: Math.round(currentX),
                y: Math.round(currentY),
                width: Math.round(currentWidth),
                height: Math.round(currentHeight)
            });
            return;
        }

        const isHorizontal = currentWidth >= currentHeight;
        const shortestEdge = isHorizontal ? currentHeight : currentWidth;

        const row = [];
        let remaining = [...children];

        while (remaining.length > 0) {
            const item = remaining[0];

            const newRow = [...row, item];
            const currentWorst = worstAspectRatio(row, shortestEdge);
            const newWorst = worstAspectRatio(newRow, shortestEdge);

            if (row.length === 0 || newWorst <= currentWorst) {
                row.push(item);
                remaining.shift();
            } else {
                // Layout current row and continue with remaining
                const result = layoutRow(row, currentX, currentY, currentWidth, currentHeight, isHorizontal);
                squarifyRecursive(remaining, result.x, result.y, result.width, result.height);
                return;
            }
        }

        // Layout final row
        if (row.length > 0) {
            layoutRow(row, currentX, currentY, currentWidth, currentHeight, isHorizontal);
        }
    }

    squarifyRecursive(normalized, x, y, width, height);
    return blocks;
}

// Hierarchical Squarified Treemap - Groups by folder path
function squarifyHierarchical(data, x, y, width, height, useLog = false) {
    if (!data || data.length === 0) return { folders: [], blocks: [] };

    // Group by parent folder
    const folderMap = new Map();
    data.forEach(item => {
        const path = item.video.FilePath;
        const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        const folder = lastIdx >= 0 ? path.substring(0, lastIdx) : 'Root';

        if (!folderMap.has(folder)) {
            folderMap.set(folder, { items: [], totalSize: 0, totalLogSize: 0 });
        }
        const fEntry = folderMap.get(folder);
        fEntry.items.push(item);
        fEntry.totalSize += item.size;
        // For hierarchical log scale, we need to sum the log sizes of items? 
        // Or log the total folder size? 
        // Usually, treemap area corresponds to sum of children areas.
        // So we should sum Math.log(item.size).
        fEntry.totalLogSize += Math.log(Math.max(item.size, 1));
    });

    // Create folder data for layout
    const folderData = [];
    folderMap.forEach((value, key) => {
        // Extract short folder name (last segment)
        const parts = key.split(/[\\\/]/);
        const shortName = parts[parts.length - 1] || 'Root';

        folderData.push({
            folder: key,
            shortName: shortName,
            size: value.totalSize,
            effectiveSize: useLog ? value.totalLogSize : value.totalSize,
            items: value.items,
            count: value.items.length
        });
    });

    // Sort folders by effective size descending
    folderData.sort((a, b) => b.effectiveSize - a.effectiveSize);
    const totalEffectiveSize = folderData.reduce((sum, f) => sum + f.effectiveSize, 0);

    if (totalEffectiveSize === 0) return { folders: [], blocks: [] };

    const folderBlocks = [];
    const videoBlocks = [];

    // Calculate folder block layout
    function layoutFolders(folders, fx, fy, fw, fh) {
        if (folders.length === 0 || fw <= 0 || fh <= 0) return;

        let currentX = fx;
        let currentY = fy;
        let remainingWidth = fw;
        let remainingHeight = fh;

        folders.forEach((folder, idx) => {
            const ratio = folder.effectiveSize / totalEffectiveSize;
            let blockWidth, blockHeight;

            // Re-calculate remaining scale based on remaining items
            const remainingEffectiveSize = folders.slice(idx).reduce((s, f) => s + f.effectiveSize, 0);
            const currentShare = folder.effectiveSize / remainingEffectiveSize;

            // Alternate between horizontal and vertical splits
            if (remainingWidth >= remainingHeight) {
                blockWidth = remainingWidth * currentShare;
                blockHeight = remainingHeight;
                if (idx === folders.length - 1) blockWidth = remainingWidth;
            } else {
                blockWidth = remainingWidth;
                blockHeight = remainingHeight * currentShare;
                if (idx === folders.length - 1) blockHeight = remainingHeight;
            }

            // Store folder block
            folderBlocks.push({
                folder: folder.folder,
                shortName: folder.shortName,
                x: Math.round(currentX),
                y: Math.round(currentY),
                width: Math.round(blockWidth),
                height: Math.round(blockHeight),
                totalSize: folder.size, // Always keep real size for display
                count: folder.count
            });

            // Layout videos inside folder with padding for label
            const labelHeight = folder.count > 1 ? 22 : 0;
            const padding = 3;
            const innerX = currentX + padding;
            const innerY = currentY + labelHeight + padding;
            const innerW = blockWidth - padding * 2;
            const innerH = blockHeight - labelHeight - padding * 2;

            if (innerW > 0 && innerH > 0) {
                // Pass useLog down to children
                const innerBlocks = squarify(folder.items, innerX, innerY, innerW, innerH, useLog);
                innerBlocks.forEach(b => {
                    b.folderPath = folder.folder;
                    b.folderIdx = folderBlocks.length - 1;
                    videoBlocks.push(b);
                });
            }

            // Update position
            if (remainingWidth >= remainingHeight) {
                currentX += blockWidth;
                remainingWidth -= blockWidth;
            } else {
                currentY += blockHeight;
                remainingHeight -= blockHeight;
            }
        });
    }

    layoutFolders(folderData, x, y, width, height);

    return { folders: folderBlocks, blocks: videoBlocks };
}

// Export for use in client.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { squarify, squarifyHierarchical };
}
