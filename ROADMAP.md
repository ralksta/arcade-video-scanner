# Arcade Media Scanner - Roadmap

This document outlines planned features and improvements for the Arcade Media Scanner project.

## Legend
- 🟢 **Planned** - Feature is defined and ready for implementation
- 🟡 **In Progress** - Currently being worked on
- 🔵 **Under Consideration** - Needs further discussion/research
- ✅ **Completed** - Feature has been implemented

---

## Version 6.2.0 (Planned)

### 🟢 Performance & Optimization
- [x] Database migration from JSON to SQLite for better performance with large libraries

### 🟢 User Experience
- [ ] Customizable grid layout (card size, columns)
- [x] Keyboard shortcuts for common actions (arrows = navigate in cinema)

---

## Completed Features

### ✅ Version 6.7.0 (2026-01-15)
- **Batch Selection Mode**: Click one checkbox to enter selection mode, then click anywhere on other cards to toggle selection.
- **Selection Visual Feedback**: Checkmark overlay on hover, cyan card highlight, and hidden action buttons during selection.
- **List View Fix**: Fixed thumbnail sizing in list view (was displaying full-size images filling the screen).
- **CSS Media Query Fix**: Fixed malformed media queries that applied mobile styles to desktop grid view.
- **Stylesheet Loading**: Added missing `styles.css` link to dashboard template.

### ✅ Version 6.6.0 (2026-01-14)
- **Binary Search Quality**: Video optimizer now uses binary search to find optimal quality in O(log n) passes instead of linear search.
- **Early Size Abort**: Encoding stops mid-pass if output exceeds 95% of original size, saving time on doomed encodes.
- **Fallback Mode**: When strict targets (20% savings + 0.960 SSIM) can't be met, uses best acceptable result (SSIM >= 0.945).
- **Keep/Discard Fix**: Fixed "Keep" button in Review not replacing original with optimized file (was a Python import shadowing bug).
- **Error Handling**: Added proper error responses and browser alerts for failed file operations.
- **JS Module Extraction**: Refactored monolithic `client.js` into `engine.js`, `cinema.js`, `collections.js`, and `formatters.js`.
- **JSDoc Documentation**: Added comprehensive JSDoc to all major JavaScript functions.

### ✅ Version 6.5.0 (2026-01-14)
- **Cinema Tags Display**: See assigned tags in Cinema overlay with one-click removal.
- **Tag System Stability**: Fixed cache-busting, deletion, and duplicate validation.
- **Docker Dev Experience**: Live code reloading via volume mounts.

### ✅ Version 6.4.1 (2026-01-14)
- **Image Smart Collections**: Filter images by media type and format (JPG, PNG, RAW, etc.) in smart collections.
- **RAW Image Support**: Extended scanner to support 12 RAW formats (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2, PEF, SRW, RAW, RWL).
- **Image-Specific UI**: Removed irrelevant bitrate display from image tiles, added separate image count in header.
- **Enhanced Header Stats**: Top info bar now shows video count, image count (when present), and combined total size.
- **Duplicate Cache Persistence**: Scan results saved to disk, no need to rescan on refresh/restart.
- **Duplicate Rescan Button**: Manual rescan option with cache clearing in duplicate view.
- **Duplicate Group Removal**: Entire duplicate group vanishes after deleting a file (case resolved).
- **Bookmarkable Duplicates**: Added `/duplicates` URL route for direct access and bookmarking.
- **Default Smart Collections**: New users automatically receive 5 curated collections (All Photos, All Videos, Large Files, High Bitrate, Recent Imports).
- **Settings Persistence**: Fixed "Scan Images" toggle resetting on reload.
- **Security Validation**: Fixed path validation error preventing optimization of files in allowed directories.
- **Connection Leak Fix**: Resolved critical "Too many open files" error by properly closing SQLite connections.

### ✅ Version 6.4.0 (2026-01-14)
- **Duplicate Detection**: Find and manage duplicate videos/images with content-verified matching.
- **Quality Scoring**: Smart recommendations for which file to keep (bitrate, resolution, codec).
- **Content Sampling**: Hash-based verification eliminates false positives.
- **First-Run Wizard**: Interactive ASCII terminal setup for new users.
- **Database Cleanup**: Remove entries for files deleted from Finder.
- **Maintenance Tools**: Purge orphan thumbnails and unused previews.

### ✅ Version 6.3.0 (2026-01-12)
- **Image Support**: Unified media scanner supporting both videos and images.
- **Image Viewer**: Dedicated image display in cinema modal (not video player).
- **Visual Badges**: Purple "IMG" indicator on image cards.
- **Image Metadata**: Appropriate metadata display for images (no duration/bitrate).
- **Keyboard Navigation**: Left/Right arrow keys to navigate in cinema mode.
- **Media Type Model**: New `media_type` field on `VideoEntry` model.
- **MediaAsset Conversion**: Proper conversion from scanner output to database storage.

### ✅ Version 6.2.0 (2026-01-12)
- **Multi-User Support**: Individual accounts with isolated scan targets, favorites, tags, and collections.
- **SQLite Database**: Migrated from JSON for performance and scalability.
- **Data Isolation**: Complete privacy between users.
- **User Management Tools**: CLI scripts for managing users.
- **Deep Filtering**: Negative tag filters, precision size/date filters.
- **Layout Precision**: Desktop/Mobile list view parity.
- **State Persistence**: URL-based view state (`?view=list`).
- **Tagging System**: Custom metadata tags for any video.
- **Smart Collections**: Save complex search queries (Tags + Filters) as dynamic sidebar collections.
- **Advanced Query Builder**: Visual builder for "Include/Exclude" criteria.
- **Search & Filter Polish**: Unified search bar and responsive sidebar improvements.

### ✅ Version 6.0.0 (2026-01-01)
- UI & Experience Overhaul (Settings, Transitions, Typography)
- Professional Desktop UX (Workspace differentiation, Sidebar indicator bars)
- Enterprise-Grade Security (Path validation, Sanitization)
- Modular Architecture (Refactored Core, Type Safety)
- Responsive Precision (List view overflow fixes)
- Integrated State Feedback (Toast notifications, Loading spinners)
- Keyboard Shortcuts (`Cmd+S`, `ESC`)
- Fixed core functionality (Search logic, Settings navigation, Rescan button)

### ✅ Version 5.2.0 (2025-12-29)
- Saved search filters and presets
- Real-time video optimization status updates
- New core scanner module
- API endpoints for settings and status

### ✅ Version 5.1.1 (2025-12-19)
- Cinema Mode with integrated action buttons
- Technical info panel in video player
- Cache statistics in settings
- Enhanced treemap gradients
- Select all visible videos in batch mode

### ✅ Version 5.1.0 (2025-12-19)
- Settings UI with in-app configuration
- Hardware-accelerated preview generation
- Dynamic worker count based on GPU VRAM
- Separate rebuild commands for thumbnails/previews 

### ✅ Version 5.0.0 (2025-12-18)
- Batch favorites functionality
- Cross-platform video optimizer (NVENC, VideoToolbox, software fallback)
- Fun facts during optimization

### ✅ Version 4.9.0 (2025-12-18)
- Lazy loading and infinite scrolling for large libraries
- Robust static asset serving
- Auto-port detection

---

## How to Contribute Ideas

Have a feature request? Here's how to suggest it:

1. **Check this roadmap** to see if it's already planned
2. **Open a GitHub Issue** with the `enhancement` label
3. **Describe the use case** - why would this feature be valuable?
4. **Provide examples** - mockups, screenshots, or similar implementations

---

## Priority Guidelines

Features are prioritized based on:
- **Impact** - How many users benefit?
- **Effort** - Development time required
- **Dependencies** - Does it unlock other features?
- **User requests** - Community feedback

---

*Last updated: 2026-01-15*
