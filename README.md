# Arcade Video Scanner 6.1.0

Arcade Video Scanner is a self-hosted media inventory tool that turns your local video library into a searchable, visual dashboard. It is specifically built for users with massive video collections (e.g., recorded gameplay, arcade collections, project archives) who need to regain disk space without losing track of their files.

### Core Features:
- **Visual Analysis**: Instantly see which videos are "High Bitrate" (candidates for compression) vs. "Optimized".
- **Privacy-First**: No data ever leaves your computer. The scan, database, and web dashboard run 100% locally.
- **Smart Filtering**: Filter by codec (H.264 vs HEVC), bitrate, or file size to pinpoint storage hogs.
- **Interactive Previews**: Hover over any video to see a 5-second preview clip.
- **The Vault**: Mark videos as "Archived" to keep your main lobby clean while maintaining a record of all your media.
- **GPU-Powered Optimization**: Cross-platform hardware acceleration (NVIDIA, Apple VideoToolbox, Intel/AMD VAAPI) reduces file sizes by 50-80% with minimal quality loss.

## 🚀 Version 6.2.0 Highlights (New!)

This release focuses on **Deep Filtering**, **Layout Precision**, and **Workflow Persistence**.

### 🔎 Advanced Filtering
- **Negative Tag Filters**: Click a tag twice to **Exclude** it (marked in red). Search for "HD" but exclude "Project X".
- **Precision Size & Date**: Filter videos by specific file size (e.g., "> 1GB") or import date (Last 24h, 7d, 30d). 
- **Smart Collection Upgrades**: Collections now persist all advanced filters (Size, Date, Exclusions) and apply immediately upon saving.

### 📐 Layout & Workflow
- **Perfect List View**: Fixed thumbnail sizing and layout consistency across desktop and mobile.
- **State Persistence**: Your view preference (Grid/List/Tree) is now saved in the URL (`?view=list`), allowing for easy bookmarking and refreshing.
- **Performance**: Improved initialization sequence to prevent empty dashboards on direct link loads.

---

## 🚀 Version 6.1.0 Highlights

This release introduces a powerful **Query Builder**, **Custom Tags**, and full **Light/Dark Mode** support, powered by a new semantic theming engine.

### 🎨 Global Theming & Light Mode
- **Theme Architecture**: New `theme.py` system decouples styles from logic.
- **Multiple Themes**: 
  - **Arcade**: The classic Neon Dark mode.
  - **Professional**: A clean, high-contrast Light mode.
  - **Candy**: A soft, pastel-colored theme.
- **Theme Switcher**: Instantly toggle themes via the new **Interface Settings**.

### 🏷️ Tags & Smart Collections
- **Tagging System**: Add custom tags (e.g., "Funny", "Project X") to videos.
- **Visual Query Builder**: Create complex filters (e.g., "Include: 4K AND Tag:Space, Exclude: 1080p").
- **Smart Collections**: Save any search query as a sidebar collection for instant access.
- **Batch Tagging**: Apply tags to multiple videos at once.

---

## 🚀 Version 6.0.0 Highlights

This major release combined a complete visual overhaul with enterprise-grade security hardening, a modular architectural refactor, and professional-grade desktop UX enhancements.

### 🎨 UI & Experience Overhaul
- **Workspace Differentiation**: Context-aware color accents and background tints for Lobby (Cyan), Favorites (Gold), Review (Cyan), and Vault (Magenta).
- **Professional Navigation**: Enhanced sidebar with structural active states, indicator bars, and workspace-specific iconography.
- **Settings Redesign**: A completely new, sidebar-based settings interface inspired by modern OS design standards (Apple/Linear/Stripe).
- **Responsive Precision**: Fixed all horizontal overflow issues in list view and optimized grid tile density for high-resolution displays.
- **State Management**: Integrated toast notifications, loading spinners, and unsaved changes tracking.
- **Smooth Transitions**: 500ms GPU-accelerated fade-in animations when switching between workspaces and layouts.
- **Modern Interactions**: iOS-style toggles, number steppers, and keyboard shortcuts (`Cmd+S` to save, `ESC` to close).

### 🔒 Enterprise-Grade Security
- **Path whitelisting**: Strict `PathValidator` ensures the scanner *only* accesses directories explicitly allowed in configuration.
- **Directory Traversal Protection**: Active protection against `../` attacks and attempts to access system files.
- **Input Sanitization**: All filenames and API parameters are rigorously validated and sanitized before processing.
- **Safe Media Serving**: Video streaming uses secure byte-range handling with strict bounds checking.

### 🏗️ Modular Architecture
- **Refactored Core**: The monolithic codebase has been split into specialized packages (`core`, `security`, `database`, `server`) for better maintainability and testing.
- **Type Safety**: Enhanced Pydantic models ensure data integrity throughout the application pipeline.

---

## 🚀 Previous Highlights

### v5.4.0 (Performance & Visualization)
- **Treemap Log Scale**: Toggle between Linear and Logarithmic visualization modes.
- **Master Optimizer Toggle**: Completely disable optimization features for read-only setups.
- **Linux VAAPI**: Native hardware acceleration support for Intel/AMD GPUs on Linux.

### v5.2.0 - Cinema Mode Edition
- **Cinema Player**: Full-featured in-browser player with integrated "Favorite", "Vault", and "Optimize" actions.
- **Deep Linking**: Direct links to specific views (`/treeview`, `/review`) supported.
- **Saved Views**: Create custom presets for "Large Files", "Unoptimized 4K", etc.

---

## ⚡Video Optimizer

The tool includes a specialized cross-platform video optimizer (`scripts/video_optimizer.py`).

- **Cross-Platform Hardware Acceleration**: 
  - **NVIDIA NVENC**: Windows/Linux (RTX 40-series optimized)
  - **Apple VideoToolbox**: macOS (Apple Silicon and Intel)
  - **Intel/AMD VAAPI**: Linux (Native hardware support)
  - **Software Fallback**: Robust CPU encoding if no hardware is found.
- **Intelligent Transcoding**: Automatically adjusts quality (CQ) and verifies results using **SSIM** to ensure quality.
- **Batch Processing**: Select multiple videos in the dashboard to queue them up.
- **Interactive Terminal**: Real-time progress bars, quality metrics, and fun facts during processing.

---

## ⚙️ Configuration

All settings can be configured through the **Settings UI** (gear icon) or by editing `arcade_data/settings.json`.

**Settings include:**
- **Scan targets**: Directories to scan.
- **enable_optimizer**: Master toggle for optimization features (true/false).
- **enable_previews**: Toggle hover preview generation (CPU/disk usage).
- **Custom exclusions**: Paths to skip.

### Default Exclusions
| Platform | Excluded Directories |
| :--- | :--- |
| **All** | `@eaDir`, `#recycle`, `Temporary Items` |
| **Windows** | `AppData/Local/Temp`, `Windows/Temp`, `iCloudDrive` |
| **macOS** | `~/Library/CloudStorage/`, `~/Pictures/Photos Library.photoslibrary` |

---

## 🛠 Installation & Usage

### Prerequisites
- **Python 3.10+**
- **FFmpeg & FFprobe**: Required.
  ```bash
  # macOS
  brew install ffmpeg

  # Linux (Ubuntu/Debian) - For VAAPI support
  sudo apt-get install ffmpeg intel-media-va-driver-non-free
  ```

### Run the App
```bash
# Clone the repo
git clone https://github.com/ralksta/arcade-video-scanner.git
cd arcade-video-scanner

# Run the startup script (Handles venv & dependencies automatically)
./run.sh
```

### Manual Usage
```bash
# Scan without starting server
python3 scan_videos_mit_shell.py

# Cleanup orphan files
python3 scan_videos_mit_shell.py --cleanup

# Force regenerate all thumbnails & previews
python3 scan_videos_mit_shell.py --rebuild
```
