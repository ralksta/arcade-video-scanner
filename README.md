# Arcade Video Scanner 4.8.1 (Customization Edition)

A visual analysis tool designed to find large video files on your local disks. It provides a clear overview of which files are consuming the most storage based on file size, bitrate, and older codecs (like H.264), helping you identify candidates for optimization or archival.

## 🚀 Version 4.8.1 Highlights

### 🔒 Private Configuration
- **Local Settings**: Support for `local_excludes.txt` and `local_targets.txt` in the `arcade_data/` directory.
- **Git-Safe**: These files are ignored by Git, allowing for private scan paths and exclusion lists.
- **Flexible Path Discovery**: The scanner now checks both the project root and the internal data folder for configuration.

### ⚡ Smart UI Optimization
- **Dynamic Action Buttons**: The "Optimize" buttons now automatically hide if the external optimization script is not found, ensuring a cleaner experience for open-source users.
- **Improved Feedback**: Better terminal logging for configuration loading and system status.

### 🌐 Smart Network Management
- **Auto-Port Detection**: The server intelligently finds the next available port if the default 8000 is occupied.
- **Socket Resilience**: Implemented `SO_REUSEADDR` to prevent "Address already in use" errors.

---

> [!IMPORTANT]
> **Initial Start Performance**: The first time you scan your library, the process may take some time depending on the number of video files. The tool generates **high-quality thumbnails** and **short video-preview clips** for every file to provide a smooth visual experience. Subsequent starts will be nearly instant as it uses the cached data.

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

### 🔒 Private Configuration
If you want to customize your setup without committing changes to GitHub, you can use these files inside the `arcade_data/` directory:

- **`local_excludes.txt`**: Add folders to skip (one per line).
- **`local_targets.txt`**: Add extra directories to scan (one per line).

*Note: Lines starting with `#` are ignored. These files are automatically skipped by Git.*

### Environment Variables
- `ARCADE_OPTIMIZER_PATH`: Override the default path to the video optimizer shell script (default: `~/scripts/video_optimizer.sh`).

## 📂 Project Structure
- `arcade_scanner/`: The core Python package.
- `arcade_data/`: Internal storage for the database, thumbnails, and previews.
- `scan_videos_mit_shell.py`: Main entry point wrapper.
