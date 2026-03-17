# Video Optimizer — Technical Deep-Dive

> `scripts/video_optimizer.py` · V2.4 · Multi-Platform Hardware Encoder

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Hardware Encoder Profiles](#hardware-encoder-profiles)
4. [Quality Search Strategy](#quality-search-strategy)
   - [Binary Search (default)](#binary-search-default)
   - [Linear Search (fallback)](#linear-search-fallback)
5. [SSIM Quality Verification](#ssim-quality-verification)
   - [Multi-Point Sampling](#multi-point-sampling)
   - [MS-SSIM vs SSIM Auto-Detection](#ms-ssim-vs-ssim-auto-detection)
   - [SSIM Skip Optimization (v7.0)](#ssim-skip-optimization-v70)
6. [AV1 Encoding (Experimental)](#av1-encoding-experimental)
7. [Staging & Atomic Replace Strategy](#staging--atomic-replace-strategy)
8. [Bitrate Analyzer Integration](#bitrate-analyzer-integration)
9. [Configuration Constants](#configuration-constants)
10. [CLI Reference](#cli-reference)

---

## Overview

The Video Optimizer converts `H.264` source files into `HEVC (H.265)` or `AV1` using hardware-accelerated encoding. It doesn't just blindly encode — it runs a **quality-controlled search** to find the highest-compression quality setting that still passes a strict SSIM verification gate.

**Key design goals:**
- Minimize file size while preserving perceptual quality (SSIM ≥ 0.960)
- Use hardware encoders (VideoToolbox, NVENC, VAAPI) for speed
- Never store a corrupt or degraded file — atomic staging ensures the original is only replaced after full verification
- Fail gracefully: if no acceptable quality is found, the original file is kept untouched

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    optimize_single_file()                    │
│                                                              │
│  1. Probe source (ffprobe → duration, resolution, codec)    │
│  2. Determine maxrate cap (BitרateAnalyzer or heuristic)    │
│  3. Pick search strategy: Binary (default) or Linear        │
│                                                              │
│        ┌────────────────────────────────────────────┐       │
│        │         run_encode_pass(quality, ...)       │       │
│        │                                             │       │
│        │  a. ffmpeg encode → staging file            │       │
│        │  b. Check: size_after < EARLY_ABORT_RATIO   │       │
│        │  c. Check: savings >= MIN_SAVINGS_FOR_SSIM  │  ◄── NEW v7.0  │
│        │  d. get_multi_ssim() → score                │       │
│        │  e. Return (success, size, ssim, error)     │       │
│        └────────────────────────────────────────────┘       │
│                                                              │
│  4. If pass succeeds → atomic replace (staging → original)  │
│  5. Update last_encode_result for logging/notification      │
└─────────────────────────────────────────────────────────────┘
```

---

## Hardware Encoder Profiles

Each encoder is wrapped in a **profile dict** that gives the optimizer a unified interface regardless of platform.

| Profile Key | Encoder | Platform | Quality Flag | Quality Range | Direction |
|:---|:---|:---|:---|:---|:---|
| `videotoolbox` | `hevc_videotoolbox` | macOS (Apple Silicon + Intel) | `-q:v` | 75–45 | ↓ worse |
| `nvenc` | `hevc_nvenc` | Windows/Linux (NVIDIA) | `-cq` | 24–44 | ↑ worse |
| `qsv` | `hevc_qsv` | Windows/Linux (Intel) | `-global_quality` | 20–32 | ↑ worse |
| `vaapi` | `hevc_vaapi` | Linux (Intel/AMD) | `-qp` | 24–34 | ↑ worse |
| `libx265` | `libx265` | Any (CPU fallback) | `-crf` | 24–32 | ↑ worse |
| `av1_videotoolbox` | `av1_videotoolbox` | macOS M3/M4 only | `-q:v` | 60–35 | ↓ worse |
| `av1_nvenc` | `av1_nvenc` | NVIDIA RTX 40xx (Lovelace) | `-cq` | 28–48 | ↑ worse |

**`quality_direction`** abstracts the difference: `+1` means "increase number = worse quality", `-1` means "decrease number = worse quality". The search algorithms use this to stay direction-agnostic.

### Apple VideoToolbox specifics

```python
'-allow_sw': '0'        # Force hardware-only — abort if hardware unavailable
'-realtime': '0'        # Allow encoder more time → better compression on M4 Max
'-profile:v': 'main'    # HEVC Main Profile — widest compatibility
```

### NVIDIA NVENC specifics

```python
'-preset': 'p5',          # Quality-focused preset (p1=fastest, p7=best)
'-tune': 'hq',            # High Quality tuning
'-rc': 'vbr',             # Variable Bitrate with CQ floor
'-multipass': 'fullres',  # Two-pass at full resolution (vs. quarter-res)
'-tier': 'high',          # High Tier lifts bitrate ceiling 6x vs Main — critical for 4K
'-spatial-aq': '1',       # Adaptive Quantization: spatial (protects textures)
'-temporal-aq': '1',      # Adaptive Quantization: temporal (smooth gradients)
'-aq-strength': '15',     # Max AQ strength — protects fine detail in dark areas
'-weighted_pred': '1',    # Better motion compensation for UI/text elements
```

---

## Quality Search Strategy

### Binary Search (default)

The Binary Search finds the optimal quality setting in **O(log n) passes** — typically 3–5 encodes instead of trying every quality step sequentially.

```
Example: VideoToolbox, quality range 75→45, step -10

Pass 1: q=60 (midpoint)  → SSIM 0.978, saved 35%  ✓ → try worse quality
Pass 2: q=50 (lower half) → SSIM 0.962, saved 47%  ✓ → try worse quality  
Pass 3: q=45 (lower half) → SSIM 0.941, saved 53%  ✗ (below threshold) → stop
Result: best accepted = q=50
```

**Early exit conditions:**
- `EXCELLENT_SAVINGS_PCT = 50.0` — if savings ≥ 50%, stop immediately (diminishing returns)
- `EARLY_ABORT_RATIO = 0.95` — abort mid-encode if output reaches 95% of source size
- `poor_savings` — skip SSIM entirely if preliminary savings < 10% (see SSIM Skip below)

### Linear Search (fallback)

When Binary Search can't find an acceptable result, Linear Search tries each quality step from worst-to-best compression. It acts as a safety net that exhausts all options before giving up.

The fallback also handles the case where a strict quality target is unreachable — it accepts the best SSIM it found (≥ `SSIM_ACCEPTABLE = 0.945`) to avoid completely failing on difficult source material.

---

## SSIM Quality Verification

### Multi-Point Sampling

Instead of comparing the entire video (too slow) or a single segment (potentially unrepresentative), the optimizer samples **3 points at 25%, 50%, and 75%** of the video duration in a **single FFmpeg pass**.

```
Timeline position:  |──25%──|──50%──|──75%──|
                         ↑       ↑       ↑
                       5 sec   5 sec   5 sec   ← SAMPLE_DURATION
                    (all trimmed and concatenated into one comparison)
```

The `filter_complex` pipeline:
```
[orig] trim@25% → oa0    [optim] trim@25% → na0
[orig] trim@50% → oa1    [optim] trim@50% → na1
[orig] trim@75% → oa2    [optim] trim@75% → na2

[oa0][oa1][oa2] concat → [ocat]
[na0][na1][na2] concat → [ncat]

[ocat][ncat] ssim → All:0.9789 ← extracted by regex
```

**Why one pass?** Three separate FFmpeg processes would each seek and decode from the start, making the total time ~3x longer. Concatenating within a single filter_complex is dramatically faster.

### MS-SSIM vs SSIM Auto-Detection

On startup, the optimizer queries `ffmpeg -filters` and checks if `mssim` (Multi-Scale SSIM) is available:

```python
_QUALITY_FILTER = 'mssim' if 'mssim' in result.stdout else 'ssim'
```

**MS-SSIM** (Multi-Scale SSIM) is preferred when available because it evaluates quality at multiple resolution scales simultaneously. This is more perceptually accurate for:
- Fast motion (arcade gameplay footage)
- High-frequency detail (UI elements, text overlays)
- Large resolution differences between samples

Standard **SSIM** is used as a fallback on older FFmpeg builds.

### SSIM Skip Optimization (v7.0)

**Problem**: Previously, SSIM was computed after every encode, even when the file barely shrank. A 2% savings is not worth 10–20 seconds of SSIM computation.

**Solution**: A preliminary savings check runs *before* calling `get_multi_ssim()`:

```python
# Inside run_encode_pass(), after size check:
MIN_SAVINGS_FOR_SSIM = 10.0

saved_pct = (1.0 - size_after / size_to_compare) * 100
if saved_pct < MIN_SAVINGS_FOR_SSIM:
    # Not worth checking quality — skip SSIM
    os.unlink(staging_path)        # Clean up staging file
    return (False, size_after, 0.0, 'poor_savings')
```

**Threshold rationale**: `10%` is below the final acceptance threshold (`MIN_SAVINGS = 20%`), so no good result is ever skipped. It only saves time on clearly inadequate quality settings.

**Caller behavior on `poor_savings`:**

| Caller | Action |
|:---|:---|
| Binary Search | Pushes toward more compression (same direction as `too_large`/`early_abort`) |
| Linear Search | Advances to next quality step (`quality += step`) |

Both discard the staged file and move on without wasting time on SSIM.

---

## AV1 Encoding (Experimental)

AV1 is the next-generation codec offering **20–30% better compression than HEVC** at equivalent visual quality.

### Hardware Requirements

| Platform | Requirement |
|:---|:---|
| Apple Silicon | M3 or M4 chip (M1/M2 lack AV1 hardware encode) |
| NVIDIA | RTX 40xx (Ada Lovelace) or newer |
| Intel/AMD | Not currently supported in this optimizer |

### Codec Selection

```bash
# CLI: explicit codec selection
python3 video_optimizer.py video.mp4 --codec av1

# Default (when --codec is omitted): HEVC
python3 video_optimizer.py video.mp4
```

When `av1` is requested but the hardware doesn't support it (e.g., M2 Mac), the optimizer automatically falls back to the default HEVC profile.

### Profile Details

**`av1_videotoolbox`** (Apple):
- Quality range: `q:v 60` (start, high quality) → `35` (max compression)
- Step size: `-10` per pass
- Uses same VideoToolbox flags as HEVC (`-allow_sw 0`, `-realtime 0`)

**`av1_nvenc`** (NVIDIA RTX 40xx):
- Quality range: `CQ 28` (start) → `48` (max compression)  
- Full NVENC feature set: multipass, spatial/temporal AQ, lookahead
- High Tier encoding for 4K content bitrate headroom

### UI Integration

In the Optimize panel in the web UI:
- A **Codec selector** (HEVC / AV1) appears when `video-mode = compress` or `encode`
- The selector is hidden automatically in `copy` mode (no encoding happens)
- The selection is stored in the `encoding_queue` table as `target_codec`

---

## Staging & Atomic Replace Strategy

The optimizer never writes directly to the source file. Instead:

1. **Encode to a staging path**: e.g., `video.mp4.staging` in the same directory
2. **Verify**: size check, then SSIM check
3. **Atomic replace**: only on full success:
   ```python
   staging_path.rename(source_path)  # atomic on same filesystem
   ```
4. **On failure**: `os.unlink(staging_path)` — source file is untouched

This guarantees that a power failure, disk error, or failed encode can never corrupt or delete the original file.

---

## Bitrate Analyzer Integration

The optimizer imports `bitrate_analyzer.py` from `arcade_scanner/core/` to determine a **maxrate cap** for each file:

```python
from bitrate_analyzer import analyze_bitrate, BitrateProfile

profile = analyze_bitrate(source_path)
maxrate = profile.peak_bitrate * 1.1  # Allow 10% headroom
```

This ensures the re-encoded file never exceeds the source's original peak bitrate (which would be wasteful and potentially larger than the source).

If the analyzer import fails, the optimizer uses a conservative heuristic based on resolution.

---

## Configuration Constants

All tuning constants are defined at the top of `video_optimizer.py`:

| Constant | Default | Purpose |
|:---|:---|:---|
| `MIN_SAVINGS` | `20.0` | Minimum % savings to accept a result |
| `MIN_QUALITY` | `0.960` | Minimum SSIM score to accept (strict gate) |
| `SSIM_ACCEPTABLE` | `0.945` | SSIM floor for fallback selection |
| `SSIM_MIN` | `0.940` | Absolute hard lower bound — reject anything below |
| `SAMPLE_DURATION` | `5` | Seconds per sample segment for SSIM |
| `EXCELLENT_SAVINGS_PCT` | `50.0` | Early exit threshold in binary search |
| `EARLY_ABORT_RATIO` | `0.95` | Abort encode if output reaches this % of source |
| `MIN_SAVINGS_FOR_SSIM` | `10.0` | Skip SSIM when savings below this % *(v7.0)* |
| `DEFAULT_MIN_SIZE_MB` | `0` | No minimum file size — process all files |

---

## CLI Reference

```bash
python3 scripts/video_optimizer.py <input_file> [options]

Options:
  --port PORT           Notification port for UI integration (default: 8000)
  --audio-mode MODE     audio handling: standard | copy | strip
  --video-mode MODE     encode mode: compress | encode | copy
  --q VALUE             Starting quality value (overrides auto-detect)
  --codec CODEC         Target codec: hevc (default) | av1
  --no-fun-facts        Suppress fun facts during encoding
  --debug               Enable verbose debug output

Examples:
  # Standard compression (HEVC, auto quality)
  python3 scripts/video_optimizer.py '/path/to/video.mp4'

  # AV1 encoding, starting at quality 55
  python3 scripts/video_optimizer.py '/path/to/video.mp4' --codec av1 --q 55

  # Compress with strip audio (maximum size reduction)
  python3 scripts/video_optimizer.py '/path/to/video.mp4' --audio-mode strip
```

---

*Last updated: v7.0.0 — AV1 support + SSIM Skip Optimization*
