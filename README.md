# Arcade Video Scanner 4.9.0 (Customization Edition)

A visual analysis tool designed to find large video files on your local disks. It provides a clear overview of which files are consuming the most storage based on file size, bitrate, and older codecs (like H.264), helping you identify candidates for optimization or archival.

## 🎯 What is Arcade Video Scanner?

Arcade Video Scanner is a self-hosted media inventory tool that turns your local video library into a searchable, visual dashboard. It is specifically built for users with massive video collections (e.g., recorded gameplay, arcade collections, project archives) who need to regain disk space without losing track of their files.

### Core Features:
- **Visual Analysis**: Instantly see which videos are "High Bitrate" (candidates for compression) vs. "Optimized".
- **Privacy-First**: No data ever leaves your computer. The scan, database, and web dashboard run 100% locally.
- **Smart Filtering**: Filter by codec (H.264 vs HEVC), bitrate, or file size to pinpoint storage hogs.
- **Interactive Previews**: Hover over any video to see a 5-second preview clip, making it easy to identify content without opening multiple video players.
- **The Vault**: Mark videos as "Archived" to keep your main lobby clean while maintaining a record of all your media.
- **GPU-Powered Optimization**: One-click optimization for Windows users with NVIDIA hardware, reducing file sizes by 50-80% with minimal quality loss.

## 🚀 Version 4.9.0 Highlights

### ⚡ Smart UI & Performance Optimization
- **Infinite Scrolling**: The dashboard now uses lazy loading to handle libraries with 2000+ videos without lag.
- **Dynamic Action Buttons**: The "Optimize" buttons now automatically hide if the external optimization script is not found.
- **High-Performance Optimizer**: Integrated support for a dedicated Python optimizer using NVIDIA hardware encoding (`hevc_nvenc`) for blazing-fast transcoding.

### 🌐 Robust Network Management
- **Auto-Port Detection**: The server intelligently finds the next available port if the default 8000 is occupied.
- **Socket Resilience**: Implemented `SO_REUSEADDR` to prevent "Address already in use" errors during quick restarts.

### 🔒 Private Configuration
- **Local Settings**: Support for `local_excludes.txt` and `local_targets.txt` in the `arcade_data/` directory.
- **Git-Safe**: These files are ignored by Git, allowing for private scan paths and exclusion lists.
- **BOM Support**: Improved handling for configuration files saved with UTF-8 BOM.

---

> [!IMPORTANT]
> **Initial Start Performance**: The first time you scan your library, the process may take some time depending on the number of video files. The tool generates **high-quality thumbnails** and **short video-preview clips** for every file to provide a smooth visual experience. Subsequent starts will be nearly instant as it uses the cached data.

---

## � Visual Overview

| Main Dashboard | The Vault (Archival View) |
| :---: | :---: |
| ![Dashboard](screenshots/dashboard.png) | ![The Vault](screenshots/vault.png) |

---

## �🛠 Installation

### Prerequisites
- **Python 3.10+**
- **FFmpeg & FFprobe**: Required for media analysis and thumbnail generation.
  ```bash
  brew install ffmpeg
  ```

## ⌨️ Usage

### Standard Launch
```bash
python3 scan_videos_mit_shell.py
```

### Maintenance Mode
```bash
# Cleanup old/orphan cache files
python3 scan_videos_mit_shell.py --cleanup

# Force regenerate all thumbnails
python3 scan_videos_mit_shell.py --rebuild
```

---

## ⚡ Video Optimizer

The tool includes a specialized video optimizer (`scripts/video_optimizer.py`) designed for Windows users with NVIDIA GPUs.

- **Hardware Acceleration**: Uses `hevc_nvenc` (NVIDIA 40-series optimized) for high-speed H.265/HEVC encoding.
- **Intelligent Transcoding**: Automatically adjusts quality (CQ) and verifies results using **SSIM** (Structural Similarity Index) to ensure significant space savings without visible quality loss.
- **Batch Processing**: Select multiple videos in the dashboard and trigger a sequence of optimization tasks.
- **Interactive Output**: Opens in a separate terminal window, providing real-time progress bars and quality metrics.

---

## ⚙️ Configuration
All settings (Scan targets, exclusions, thresholds) are centrally managed in `arcade_scanner/app_config.py`.

### 🚫 Default Exclusions
By default, several system and cloud-related directories are excluded to ensure performance, stability, and to prevent unwanted data downloads.

| Platform | Excluded Directories | Reasoning |
| :--- | :--- | :--- |
| **All** | `@eaDir`, `#recycle`, `Temporary Items` | Skips NAS system folders and trash bins. |
| **Windows** | `AppData/Local/Temp`, `Windows/Temp` | Avoids cluttering results with system temporary files. |
| **Windows** | `iCloudDrive`, `Proton Drive` | Prevents triggering massive "on-demand" cloud downloads. |
| **macOS** | `~/Library/CloudStorage/`, `~/Library/Mobile Documents/` | Prevents scanning iCloud/OneDrive sync folders that trigger downloads. |
| **macOS** | `~/Pictures/Photos Library.photoslibrary` | Avoids scanning internal database files of the Photos app. |
| **macOS** | `~/Library/Containers/` | Skips application-specific sandbox folders. |

### 🔒 Private Configuration
If you want to customize your setup without committing changes to GitHub, you can use these files inside the `arcade_data/` directory:

- **`local_excludes.txt`**: Add folders to skip (one per line).
- **`local_targets.txt`**: Add extra directories to scan (one per line).

*Note: Lines starting with `#` are ignored. These files are automatically skipped by Git.*

### Environment Variables
- `ARCADE_OPTIMIZER_PATH`: Override the default path to the video optimizer script (default: `scripts/video_optimizer.py`).

## 📂 Project Structure
- `arcade_scanner/`: The core Python package.
- `arcade_data/`: Internal storage for the database, thumbnails, and previews.
- `scripts/`: Contains the `video_optimizer.py` and other utility scripts.
- `scan_videos_mit_shell.py`: Main entry point wrapper.
