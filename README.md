# Arcade Video Scanner 4.8 (Reliability Edition)

A professional-grade media management and video analysis tool designed for high-performance scanning and library maintenance.

## 🚀 Version 4.8 Highlights

### 🔒 Robust Vault Persistence
- **State Synchronization**: Videos moved to the **Vault** now stay there reliably across restarts.
- **Path Normalization**: Uses absolute path resolution to bridge the gap between file system representations and web browser requests.
- **Atomic Cache Updates**: Improved cache manager ensuring that your "reviewed" status is never lost during re-scans.
- **Diagnostic Logging**: Get real-time feedback in the terminal when the database is loaded or updated.

### 🌐 Smart Network Management
- **Auto-Port Detection**: The server intelligently finds the next available port if the default 8000 is occupied.
- **Socket Resilience**: Implemented `SO_REUSEADDR` to prevent the "Address already in use" errors during quick restarts.

### 🕹 Workspace Modes (Lobby vs. Vault)
- **Lobby**: A clean, focused workspace showing only active videos.
- **The Vault**: A dedicated archival view with a **Cyber Cyan** theme.

### 📦 Modular & Robust Architecture
- **Smart Seeking**: Adapts thumbnail extraction to video duration.
- **Auto-Repair**: Automatically detects and regenerates corrupted thumbnails.
- **Native Streaming**: Implementation of HTTP Range Requests for smooth playback.
- **Cinema Mode**: Premium video player with `ESC` to close functionality.

---

## 🛠 Installation

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

### Environment Variables
- `ARCADE_OPTIMIZER_PATH`: Override the default path to the video optimizer shell script (default: `~/scripts/video_optimizer.sh`).

## 📂 Project Structure
- `arcade_scanner/`: The core Python package.
- `arcade_data/`: Internal storage for the database, thumbnails, and previews.
- `scan_videos_mit_shell.py`: Main entry point wrapper.
