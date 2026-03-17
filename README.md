# Arcade Media Scanner 7.0.0

Arcade Media Scanner is a self-hosted media inventory tool that turns your local video and image library into a searchable, visual dashboard. It is specifically built for users with massive media collections (e.g., recorded gameplay, arcade collections, photo archives) who need to regain disk space without losing track of their files.

### Core Features:
- **Visual Analysis**: Instantly see which videos are "High Bitrate" (candidates for compression) vs. "Optimized".
- **Privacy-First**: No data ever leaves your computer. The scan, database, and web dashboard run 100% locally.
- **Smart Filtering**: Filter by codec (H.264 vs HEVC), bitrate, file size, media type, and image formats.
- **The Vault**: Mark videos as "Archived" to keep your main lobby clean while maintaining a record of all your media.
- **GPU-Powered Optimization**: Cross-platform hardware acceleration (NVIDIA, Apple VideoToolbox, Intel/AMD VAAPI) reduces file sizes by 50-80% with minimal quality loss.

---

## 🚀 Version 7.0.0 Highlights (New!)

This release adds **AV1 Encoding Support** (powered by FFmpeg 8.1) and a **Smart SSIM Skip Optimization** for faster video processing.

### ✅ AV1 Encoding (Experimental)
- **Next-Gen Codec**: Optional AV1 encoding alongside the default HEVC for superior compression ratios.
- **Hardware Accelerated**: Uses `av1_videotoolbox` on Apple Silicon M3/M4 and `av1_nvenc` on NVIDIA RTX 40xx (Lovelace).
- **Automatic Fallback**: If your hardware doesn't support AV1, the optimizer automatically falls back to HEVC.
- **Database Tracked**: Codec preference is stored per-job in the encoding queue (`target_codec` column).
- **UI Selection**: Toggle between HEVC and AV1 directly in the Optimize panel — hidden in Copy mode.

### ⚡ Smart SSIM Skip
- **Faster Passes**: SSIM quality verification is now skipped when preliminary savings are below 10%.
- **No Wasted Time**: If a pass shows poor compression results, the optimizer immediately moves to the next quality level without running the expensive SSIM comparison.
- **Smarter Search**: Both Binary and Linear Search callers handle the new `poor_savings` result correctly.

📖 **[Full Video Optimizer Technical Reference →](dev-docs/video-optimizer.md)**

---

## 🚀 Version 6.8.0 Highlights

### ✅ Visual Timeline & Scrubber
- **Frame-Accurate Seeking**: Professional visual timeline scrubber with real-time thumbnail previews.
- **Trim Handles**: Visual markers for setting export start/end points with frame-perfect precision.
- **Playback Sync**: Scrubber stays in sync with video playback state.

### ✅ GIF Export Panel
- **UX Redesign**: Replaced the intrusive GIF modal with a sleek bottom panel.
- **Production Presets**: Quick buttons for resolution (360p to 1080p) and frame rates (10fps to 30fps).
- **Size Estimation**: Real-time file size calculation based on resolution, FPS, and trim duration.

### ✅ Cinema Mode UX Overhaul
- **Improved Readability**: Redesigned action buttons with always-visible labels.
- **Premium Interaction**: Larger touch targets, backdrop blur, scale-on-hover animations (1.05x).
- **Docker-Aware UI**: Automatically hides "Reveal in Finder" when running in Docker.

---

## 📋 Previous Releases

<details>
<summary>v6.7.x – Fullscreen Duplicate Checker</summary>

### v6.7.1 – Fullscreen Duplicate Checker
- **Immersive Interface**: Dedicated fullscreen mode with side-by-side comparison of duplicate files.
- **Keyboard Shortcuts**: `1`/`←` keep File A, `2`/`→` keep File B, `S`/`Space` skip, `A` auto-keep, `ESC` exit.
- **Smart Recommendations**: Visual highlighting of the recommended file based on quality score.
- **Quality Metrics**: Quality score difference, resolution, file size, and bitrate shown per file.

### v6.7.0 – Batch Selection UX
- **Selection Mode**: Click one video to enter selection mode – click others to add/remove from selection.
- **Visual Feedback**: Large checkmark overlay on hover, cyan highlight on selected cards.
- **List View Fixed**: Properly constrained thumbnail sizes; fixed malformed media queries.

</details>

<details>
<summary>v6.6.0 – Smart Video Optimizer</summary>

- **Binary Search Quality**: Finds optimal quality in O(log n) passes – up to 50% fewer encode passes.
- **Early Size Abort**: Encoding stops mid-pass if output exceeds 95% of original size.
- **Fallback Mode**: When strict targets can't be met, uses best acceptable result (SSIM ≥ 0.945).
- **JavaScript Modules**: Extracted `cinema.js`, `collections.js`, `formatters.js` from monolithic `engine.js`.

</details>

<details>
<summary>v6.4.x – Image Support, Duplicate Detection, First-Run Wizard</summary>

- **RAW Format Support**: CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2, PEF, SRW, RAW, RWL.
- **Persistent Duplicate Cache**: Scan results saved to disk.
- **Default Smart Collections**: All Photos, All Videos, Large Files, High Bitrate, Recent Imports.
- **First-Run Setup Wizard**: ASCII terminal wizard for initial configuration.
- **Database Cleanup Tools**: Remove orphan entries and unused thumbnails.

</details>

<details>
<summary>v6.2.0 – Multi-User Support & SQLite Migration</summary>

- **User Accounts**: Multiple accounts with `PBKDF2` password hashing and full data isolation.
- **SQLite Backend**: Migrated from flat JSON files; handles 10,000+ file libraries with instant startup.
- **Negative Tag Filters**: Click a tag twice to exclude it from search results.
- **State Persistence**: View preference (Grid/List/Tree) saved in URL.

</details>

<details>
<summary>v6.1.0 – Query Builder, Tags & Theming</summary>

- **Theme System**: Arcade (dark), Professional (light), Candy (pastel) with live switching.
- **Tagging System**: Custom tags with visual query builder and smart collections.
- **Batch Tagging**: Apply tags to multiple videos at once.

</details>

<details>
<summary>v5.x – Cinema Mode, VAAPI, Treemap</summary>

- **Cinema Player**: Full in-browser player with Favorite, Vault, and Optimize integrated.
- **Linux VAAPI**: Native hardware acceleration for Intel/AMD GPUs.
- **Treemap Log Scale**: Toggle Linear/Logarithmic visualization modes.

</details>

---

## ⚡ Video Optimizer

The tool includes a specialized cross-platform video optimizer (`scripts/video_optimizer.py`).

- **Cross-Platform Hardware Acceleration**:
  - **NVIDIA NVENC**: Windows/Linux (RTX 40-series optimized)
  - **Apple VideoToolbox**: macOS (Apple Silicon and Intel)
  - **Intel/AMD VAAPI**: Linux (Native hardware support)
  - **Software Fallback**: CPU encoding if no hardware is found.
- **AV1 Encoding Support** *(Experimental, FFmpeg 8.1+)*: Requires Apple M3/M4 or NVIDIA RTX 40xx. Falls back to HEVC automatically.
- **Intelligent Transcoding**: Binary search finds optimal quality in O(log n) passes. Savings are checked *before* SSIM — passes with < 10% savings are skipped immediately.
- **Batch Processing**: Select multiple videos in the dashboard to queue them up.

### Codec Selection

```bash
# Default: HEVC (H.265) — best compatibility
.venv/bin/python3 scripts/video_optimizer.py /path/to/video.mp4 --codec hevc

# AV1 — better compression, requires M3/M4 or RTX 40xx
.venv/bin/python3 scripts/video_optimizer.py /path/to/video.mp4 --codec av1
```

📖 **[Full technical reference including SSIM, binary search, staging strategy →](dev-docs/video-optimizer.md)**

---

## ⚙️ Configuration

All settings can be configured through the **Settings UI** (gear icon) or by editing `arcade_data/settings.json`.

**Settings include:**
- **Scan targets**: Directories to scan.
- **enable_optimizer**: Master toggle for optimization features (true/false).
- **Custom exclusions**: Paths to skip.

### Default Exclusions
| Platform | Excluded Directories |
| :--- | :--- |
| **All** | `@eaDir`, `#recycle`, `Temporary Items` |
| **Windows** | `AppData/Local/Temp`, `Windows/Temp`, `iCloudDrive` |
| **macOS** | `~/Library/CloudStorage/`, `~/Pictures/Photos Library.photoslibrary` |

---

## 🐳 Docker Deployment

```bash
# Using Docker Compose (Recommended)
docker-compose up -d

# Access at http://localhost:8000
# Default login: admin/admin (change immediately!)
```

**📖 Full Docker Guide**: See [DOCKER.md](DOCKER.md) for volume configuration, GPU support, environment variables, and troubleshooting.

---

## 👥 User Management

```bash
# List all users
.venv/bin/python3 scripts/manage_users.py list

# Add a new user
.venv/bin/python3 scripts/manage_users.py add john

# Add an admin user
.venv/bin/python3 scripts/manage_users.py add jane --admin

# Change a user's password
.venv/bin/python3 scripts/manage_users.py passwd john
```

**Default admin account**: `admin` / `admin` — ⚠️ change immediately after first login!

---

## 🛠 Installation & Usage

### Prerequisites
- **Python 3.10+**
- **FFmpeg 8.1+ & FFprobe**: Required.
  ```bash
  # macOS
  brew install ffmpeg

  # Linux (Ubuntu/Debian) - For VAAPI support
  sudo apt-get install ffmpeg intel-media-va-driver-non-free
  ```

### Run the App
```bash
git clone https://github.com/ralksta/arcade-video-scanner.git
cd arcade-video-scanner
./run.sh
```
