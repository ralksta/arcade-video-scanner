# Arcade Video Scanner 5.4.0 (Dev)

Arcade Video Scanner is a self-hosted media inventory tool that turns your local video library into a searchable, visual dashboard. It is specifically built for users with massive video collections (e.g., recorded gameplay, arcade collections, project archives) who need to regain disk space without losing track of their files.

### Core Features:
- **Visual Analysis**: Instantly see which videos are "High Bitrate" (candidates for compression) vs. "Optimized".
- **Privacy-First**: No data ever leaves your computer. The scan, database, and web dashboard run 100% locally.
- **Smart Filtering**: Filter by codec (H.264 vs HEVC), bitrate, or file size to pinpoint storage hogs.
- **Interactive Previews**: Hover over any video to see a 5-second preview clip.
- **The Vault**: Mark videos as "Archived" to keep your main lobby clean while maintaining a record of all your media.
- **GPU-Powered Optimization**: Cross-platform hardware acceleration (NVIDIA, Apple VideoToolbox, Intel/AMD VAAPI) reduces file sizes by 50-80% with minimal quality loss.

## 🚀 Version 5.4.0 (Performance & Visualization)

### 📊 Treemap Logarithmic Scale
- **Toggle View**: Switch between **Linear** (size-accurate) and **Logarithmic** (structure-visible) treemap modes.
- **Fixes Power Laws**: Easily visualize folder structures even when one directory (e.g., "Archive") is 100x larger than others.

### ⚡ Master Optimizer Toggle
- **Resource Control**: Disable the entire optimization suite via `settings.json` (`"enable_optimizer": false`).
- **Clean UI**: Hides all "Optimize" buttons, lightning bolt icons, and batch actions when disabled—perfect for low-power servers.

### 🐧 Linux Hardware Acceleration (VAAPI)
- **Native VAAPI Support**: Now supports hardware transcoding on Linux for Intel and AMD GPUs.
- **Performance Boost**: Uses hardware acceleration for both **startup scanning** (preview generation) and **video optimization**.
- **Smart Detection**: Automatically detects `/dev/dri/renderD128` or `/dev/dri/card0` and provides driver guidance if needed.

### 📱 Mobile Experience Overhaul
- **Mobile-First Layout**: Fully responsive single-column design optimized for mobile devices.
- **Touch Interactions**: "Click-to-Play" interface replaces hover menus on touchscreens.
- **Stability**: Fixed layout shifts and scrolling issues for a buttery-smooth mobile experience.

### ✂️ Advanced Optimization Controls
- **Audio Modes**: Choose between "Standard" (AAC) or "Enhanced" (High-pass + Gate + Norm) audio processing.
- **Video Trimming**: Select specific start and end times directly in the optimization panel.

---

## 🚀 Previous Highlights

### v5.2.0 - Cinema Mode Edition
- **Cinema Player**: Full-featured in-browser player with integrated "Favorite", "Vault", and "Optimize" actions.
- **Deep Linking**: Direct links to specific views (`/treeview`, `/review`) supported.
- **Saved Views**: Create custom presets for "Large Files", "Unoptimized 4K", etc.

### v5.1.0 - Hardware Preview Generation
- **GPU Previews**: Initial scans are 5-10x faster using hardware encoding for thumbnail/preview generation.
- **Settings UI**: Configure scan targets, exclusions, and thresholds directly from the dashboard.

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

### Run the Scanner
```bash
python3 scan_videos_mit_shell.py
```

### Maintenance Commands
```bash
# Cleanup orphan files
python3 scan_videos_mit_shell.py --cleanup

# Force regenerate all thumbnails & previews (Useful after upgrading to VAAPI)
python3 scan_videos_mit_shell.py --rebuild
```
