# Arcade Video Scanner - Roadmap

This document outlines planned features and improvements for the Arcade Video Scanner project.

## Legend
- 🟢 **Planned** - Feature is defined and ready for implementation
- 🟡 **In Progress** - Currently being worked on
- 🔵 **Under Consideration** - Needs further discussion/research
- ✅ **Completed** - Feature has been implemented

---

## Version 5.2.0 (Next Release)

### 🟢 Performance & Optimization
- [ ] Database migration from JSON to SQLite for better performance with large libraries
- [ ] Implement incremental scanning (only scan new/modified files)
- [ ] Add background worker for preview generation to avoid blocking UI

### 🟢 User Experience
- [ ] Dark/Light theme toggle
- [ ] Customizable grid layout (card size, columns)
- [ ] Keyboard shortcuts for common actions (space = play, f = favorite, etc.)
- [ ] Drag-and-drop file organization

### 🟢 Search & Filtering
- [ ] Advanced search with multiple criteria (date range, resolution, duration)
- [ ] Saved search filters/presets
- [ ] Tag system for custom categorization
- [ ] Smart collections (auto-updating based on criteria)

---

## Version 5.3.0

### 🔵 Media Management
- [ ] Duplicate detection (find similar/identical videos)
- [ ] Bulk rename functionality
- [ ] Export/Import favorites and vault lists
- [ ] Video trimming/cutting tool (non-destructive)

### 🔵 Analytics & Insights
- [ ] Storage savings dashboard (before/after optimization)
- [ ] Timeline view (videos by date)
- [ ] Most watched/favorited statistics
- [ ] Codec distribution charts

### 🔵 Integration & Export
- [ ] Export to CSV/JSON for external analysis
- [ ] Webhook support for automation
- [ ] API endpoints for third-party integrations
- [ ] Plex/Jellyfin metadata export

---

## Version 6.0.0 (Major Features)

### 🔵 Multi-User Support
- [ ] User accounts and authentication
- [ ] Per-user favorites and vault
- [ ] Shared libraries with permissions
- [ ] Activity logging

### 🔵 Cloud & Sync
- [ ] Optional cloud backup for metadata
- [ ] Sync settings across multiple machines
- [ ] Remote access (secure web interface)

### 🔵 AI & Machine Learning
- [ ] Auto-tagging based on video content
- [ ] Scene detection and chapter markers
- [ ] Quality assessment (blur detection, noise analysis)
- [ ] Smart recommendations

---

## Future Ideas (No Timeline)

### 🔵 Advanced Features
- [ ] Plugin system for extensibility
- [ ] Custom metadata fields
- [ ] Video playlists
- [ ] Comparison view (side-by-side videos)
- [ ] Mobile app (iOS/Android)
- [ ] Browser extension for quick adds
- [ ] Integration with video editing software
- [ ] Automatic backup scheduling
- [ ] Network share support (SMB/NFS)
- [ ] Docker containerization

### 🔵 Video Processing
- [ ] Batch watermarking
- [ ] Audio normalization
- [ ] Subtitle extraction/embedding
- [ ] Format conversion presets
- [ ] GPU-accelerated filters (denoising, sharpening)

---

## Completed Features

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

*Last updated: 2025-12-19*
