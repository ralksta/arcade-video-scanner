# Arcade Video Scanner 5.0.0 (Batch & Multi-Platform Edition)

Arcade Video Scanner is a self-hosted media inventory tool that turns your local video library into a searchable, visual dashboard. It is specifically built for users with massive video collections (e.g., recorded gameplay, arcade collections, project archives) who need to regain disk space without losing track of their files.

### Core Features:
- **Visual Analysis**: Instantly see which videos are "High Bitrate" (candidates for compression) vs. "Optimized".
- **Privacy-First**: No data ever leaves your computer. The scan, database, and web dashboard run 100% locally.
- **Smart Filtering**: Filter by codec (H.264 vs HEVC), bitrate, or file size to pinpoint storage hogs.
- **Interactive Previews**: Hover over any video to see a 5-second preview clip, making it easy to identify content without opening multiple video players.
- **The Vault**: Mark videos as "Archived" to keep your main lobby clean while maintaining a record of all your media.
- **GPU-Powered Optimization**: Cross-platform optimization supporting both NVIDIA (Windows) and Apple VideoToolbox (macOS) hardware acceleration, reducing file sizes by 50-80% with minimal quality loss.
- **Batch Operations**: Select and favorite multiple videos at once with the new batch selection feature.

## 🚀 Version 5.0.0 Highlights

### 🎯 Batch Operations
- **Batch Favorites**: Select multiple videos and mark them all as favorites with a single click using the new "FAVORISIEREN" button in the batch selection bar.
- **Streamlined Workflow**: Quickly organize large collections without clicking through individual videos.

### ⚡ Cross-Platform Video Optimizer
- **Multi-Platform Support**: Automatically detects and uses the best hardware encoder for your system:
  - **NVIDIA NVENC** (Windows/Linux with NVIDIA GPUs)
  - **Apple VideoToolbox** (macOS with Apple Silicon or Intel)
  - **Software Fallback** (CPU-based encoding for systems without hardware acceleration)
- **Manual Override**: Use the `--encoder` flag to force a specific encoding method.
- **Enhanced Progress Display**: Progress bar now shows the active encoding method and estimates total processing time.
- **Fun Facts**: Learn gaming trivia while your videos optimize! The optimizer displays random arcade and gaming facts during processing.

### ⚡ Smart UI & Performance Optimization
- **Infinite Scrolling**: The dashboard now uses lazy loading to handle libraries with 2000+ videos without lag.
- **Dynamic Action Buttons**: The "Optimize" buttons now automatically hide if the external optimization script is not found.
- **High-Performance Optimizer**: Integrated support for a dedicated Python optimizer using hardware encoding for blazing-fast transcoding.

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

The tool includes a specialized cross-platform video optimizer (`scripts/video_optimizer.py`) designed to work on both Windows and macOS.

- **Cross-Platform Hardware Acceleration**: 
  - **NVIDIA NVENC** for Windows/Linux systems with NVIDIA GPUs (40-series optimized)
  - **Apple VideoToolbox** for macOS systems (Apple Silicon and Intel)
  - **Software Fallback** for systems without hardware acceleration
- **Automatic Detection**: Intelligently detects your system's capabilities and selects the best encoder.
- **Manual Override**: Use `--encoder nvenc|videotoolbox|software` to force a specific encoding method.
- **Intelligent Transcoding**: Automatically adjusts quality (CQ) and verifies results using **SSIM** (Structural Similarity Index) to ensure significant space savings without visible quality loss.
- **Batch Processing**: Select multiple videos in the dashboard and trigger a sequence of optimization tasks.
- **Interactive Output**: Opens in a separate terminal window, providing real-time progress bars, quality metrics, and estimated completion time.
- **Fun Facts**: Displays random arcade and gaming trivia during the optimization process to keep you entertained!

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
