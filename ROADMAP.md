# Arcade Video Scanner - Roadmap

This document outlines planned features and improvements for the Arcade Video Scanner project.

## Legend
- 🟢 **Planned** - Feature is defined and ready for implementation
- 🟡 **In Progress** - Currently being worked on
- 🔵 **Under Consideration** - Needs further discussion/research
- ✅ **Completed** - Feature has been implemented

---

## Version 6.1.0 (Planned)

### 🟢 Performance & Optimization
- [ ] Database migration from JSON to SQLite for better performance with large libraries
- [ ] Implement incremental scanning (only scan new/modified files)
- [ ] Add background worker for preview generation to avoid blocking UI

### 🟢 User Experience
- [ ] Dark/Light theme toggle
- [ ] Customizable grid layout (card size, columns)
- [ ] Keyboard shortcuts for common actions (space = play, f = favorite, etc.)

### 🟢 Search & Filtering
- [ ] Advanced search with multiple criteria (date range, resolution, duration)
- [ ] Tag system for custom categorization
- [ ] Smart collections (auto-updating based on criteria)

---

## Version 6.2.0

### 🔵 Media Management
- [ ] Duplicate detection (find similar/identical videos)
- [ ] Bulk rename functionality
- [ ] Video trimming/cutting tool (non-destructive)
- [ ] Server-Side File Operations (Move/Rename/Delete via UI)
- [ ] Web Upload (Add files from client device)

### 🔵 Analytics & Insights
- [ ] Timeline view (videos by date)
- [ ] Most watched/favorited statistics

### 🔵 Integration & Export
- [ ] Webhook support for automation
- [ ] API endpoints for third-party integrations
- [ ] Plex/Jellyfin metadata export

---

## Version 7.0.0 (Future Major Features)

### 🔵 Multi-User Support
- [ ] Guest / Read-Only Access
- [ ] Activity logging

### 🔵 Network & Remote Access
- [ ] Optional cloud backup for metadata
- [ ] Reverse Proxy / Tunneled Access Support
- [ ] Bandwidth-aware streaming (Transcoding on-the-fly)

### 🔵 AI & Machine Learning
- [ ] Auto-tagging based on video content
- [ ] Scene detection and chapter markers
- [ ] Smart recommendations

---

## Future Ideas (No Timeline)

### 🔵 Advanced Features
- [ ] Plugin system for extensibility
- [ ] Custom metadata fields
- [ ] Video playlists
- [ ] Comparison view (side-by-side videos)
- [ ] Mobile app (iOS/Android)
- [ ] Integration with video editing software
- [ ] Automatic backup scheduling
- [ ] Network share support (SMB/NFS)
- [ ] Docker containerization

### 🔵 Video Processing
- [ ] Audio normalization
- [ ] Subtitle extraction/embedding
- [ ] Format conversion presets
- [ ] GPU-accelerated filters (denoising, sharpening)

---

## Completed Features

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
- Cinema mode with integrated action buttons
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

*Last updated: 2025-12-31*
