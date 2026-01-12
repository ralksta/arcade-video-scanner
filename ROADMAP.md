# Arcade Video Scanner - Roadmap

This document outlines planned features and improvements for the Arcade Video Scanner project.

## Legend
- 🟢 **Planned** - Feature is defined and ready for implementation
- 🟡 **In Progress** - Currently being worked on
- 🔵 **Under Consideration** - Needs further discussion/research
- ✅ **Completed** - Feature has been implemented

---

## Version 6.2.0 (Planned)

### 🟢 Performance & Optimization
- [x] Database migration from JSON to SQLite for better performance with large libraries
- [ ] Implement incremental scanning (only scan new/modified files)
- [ ] Add background worker for preview generation to avoid blocking UI

### 🟢 User Experience
- [ ] Customizable grid layout (card size, columns)
- [x] Keyboard shortcuts for common actions (arrows = navigate in cinema)

---

## Completed Features

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

*Last updated: 2026-01-12*
