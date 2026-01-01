# Changelog

All notable changes to this project will be documented in this file.

## [6.0.0] - 2026-01-01

### Added
- **Workspace Differentiation**: Context-aware color accents and background tints for Lobby (Cyan), Favorites (Gold), Review (Cyan), and Vault (Magenta).
- **Professional Navigation**: Enhanced sidebar with structural active states, indicator bars, and workspace-specific iconography.
- **Settings UI Redesign**: Modern, sidebar-based configuration interface inspired by modern OS design standards (Apple/Linear/Stripe).
- **State Management**: Integrated toast notifications, loading spinners, and unsaved changes tracking.
- **Video Optimizer Toggle**: UI toggle in settings to enable/disable optimization features.

### Changed
- **Filter Bar Redesign**: Dynamic workspace-sensitive border colors and background tints.
- **Responsive List View**: Improved card layouts and reduced thumbnail sizes to prevent overflow on wide screens.
- **UI Architecture**: Moved away from hybrid inline styles towards a more structured workspace theming system.

### Fixed
- **Search Logic**: Corrected input binding that caused search to fail.
- **Settings Navigation**: Fixed tab-switching logic and content visibility in the settings modal.
- **UI Overflow**: Resolved horizontal scrolling issues in the list view on high-resolution displays.
- **Refresh Button**: Added missing ID to the rescan button to restore functionality.
- **State Persistence**: Improved persistence check for Video Optimizer settings.

## [5.2.0] - 2025-12-29

### Added
- **Saved Views**: Users can now save their current search queries, filters, and sort settings as named presets.
- **Real-time Status**: The video optimizer script now notifies the running server when a file optimization completes, allowing the UI to update instantly.
- **API Endpoints**: New `/api/settings` (POST) for saving user preferences and `/api/mark_optimized` for external status updates.

### Changed
- **Refactoring**: Extracted video scanning logic from `main.py` into a new dedicated module `core/scanner.py`.
- **Optimizer**: Added `--port` argument to `video_optimizer.py` to enable server notifications.

### Fixed
- **Time Parsing**: Fixed `ValueError` in optimizer progress display when `out_time_ms` is invalid.
- **Scan Logic**: Scanner now correctly identifies optimized files regardless of the minimum size threshold.

## [5.1.1] - 2025-12-19

### Added
- **Cinema Mode Enhancements**: Full-screen video player now includes action buttons for Favorite, Vault, Locate, and Optimize.
- **Cinema Info Panel**: Technical details panel in cinema mode showing codec, bitrate, file size, and status.
- **Select All Button**: New "Select All Visible" button in batch mode to quickly select all filtered videos.
- **Cache Statistics**: Settings modal now displays cache size statistics (thumbnails, previews, and total).
- **Enhanced Treemap Gradients**: Improved visual design with gradient colors for both folder and file views.

### Changed
- **Cleaner Console Output**: Removed verbose "Purging broken media" messages, now only shows when files are actually cleaned.
- **Cinema Mode UX**: Favorite and Vault buttons now show visual feedback when already applied (reduced opacity).
- **Settings Modal Width**: Increased max-width to 800px to accommodate cache statistics.

### Fixed
- **Cinema Mode State Sync**: Favorite/Vault actions in cinema mode now properly update the grid view without requiring reload.

## [5.1.0] - 2025-12-19

### Added
- **Settings UI**: New in-app settings modal (gear icon) to configure scan paths and exclusions directly from the dashboard.
- **Default Exclusions Toggles**: Each default exclusion now shows a description and can be enabled/disabled via checkbox.
- **Hardware-Accelerated Preview Generation**: Preview clips now use GPU encoding (NVENC, VideoToolbox, QuickSync) for 5-10x faster initial scans.
- **Dynamic Worker Count**: Auto-detects GPU VRAM and sets optimal parallel workers (1 per 3GB, max 12).
- **Separate Rebuild Commands**: `--rebuild-thumbs` and `--rebuild-previews` to regenerate media independently.
- **Improved Progress Messages**: Shows "thumbnails...", "previews...", or "processed..." based on rebuild mode.

### Changed
- **Configuration**: Migrated from `local_targets.txt`/`local_excludes.txt` to unified `settings.json` format.
- **Thumbnail Generation**: Now uses letterboxing/pillarboxing to preserve aspect ratio for vertical videos.
- **Default Exclusions**: Now stored with descriptions for better UI presentation.

### Fixed
- Fixed distorted thumbnails for vertical (9:16) videos.
- Improved cache handling to preserve favorite and hidden states during rebuilds.

## [5.0.0] - 2025-12-18

### Added
- **Batch Favorites**: Select multiple videos and mark them all as favorites at once.
- **Cross-Platform Video Optimizer**: NVIDIA NVENC, Apple VideoToolbox, and software fallback support.
- **Fun Facts**: Gaming trivia displayed during optimization.

## [4.9.0] - 2025-12-18

### Added
- **UI Performance Optimization**: Implemented lazy loading and infinite scrolling for the video grid, significantly improving performance for large libraries (tested with 2200+ clips).
- **Robust Static Asset Serving**: Transitioned CSS and JavaScript from Python templates to dedicated static files (`/static/styles.css` and `/static/client.js`) with improved path resolution.
- **Auto-Port Detection**: The server now automatically finds the next available port if the default 8000 is occupied.
- **Address Reuse**: Implemented `SO_REUSEADDR` to prevent "Address already in use" errors during quick restarts.

### Changed
- Improved encoding handling for local configuration files (`local_targets.txt`, `local_excludes.txt`) using UTF-8 with BOM support.
- Updated dashboard template to use static asset links instead of inline/templated scripts and styles.
- Refactored server logic to keep the working directory at the project root for better resource management.

### Fixed
- Resolved Python syntax errors related to global variable declarations in `web_server.py`.
- Fixed asset loading issues (404 errors) by implementing more robust static file routing.
- General bug fixes and stability improvements.
