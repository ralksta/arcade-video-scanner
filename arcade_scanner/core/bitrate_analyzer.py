"""
Bitrate Analyzer for Arcade Scanner
====================================
Analyzes input video files using ffprobe to determine their bitrate characteristics,
then generates appropriate encoding parameters that never exceed source quality.

Integrates with the existing encoder detection system (detect_hw_encoder / get_best_encoder).
"""

import json
import math
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Codec efficiency ratios – when transcoding *from* one codec *to* another,
# the target codec may be more efficient.  A ratio < 1.0 means the target
# codec can achieve the same perceptual quality at a lower bitrate.
#
# Key = (source_codec, target_codec)   Value = efficiency multiplier
# e.g. H.264 → H.265 typically needs only ~60-70% of the bitrate.
# ---------------------------------------------------------------------------
CODEC_EFFICIENCY: Dict[Tuple[str, str], float] = {
    ("h264", "hevc"):  0.65,
    ("h264", "h265"):  0.65,
    ("h264", "av1"):   0.55,
    ("hevc", "h264"):  1.40,
    ("h265", "h264"):  1.40,
    ("hevc", "av1"):   0.80,
    ("h265", "av1"):   0.80,
    ("av1",  "h264"):  1.70,
    ("av1",  "hevc"):  1.25,
    ("av1",  "h265"):  1.25,
    ("mpeg4", "h264"): 0.60,
    ("mpeg4", "hevc"): 0.45,
    ("mpeg2video", "h264"): 0.50,
    ("mpeg2video", "hevc"): 0.35,
    ("vp8",  "h264"):  0.75,
    ("vp9",  "hevc"):  0.90,
    ("vp9",  "h264"):  1.10,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class BitrateProfile:
    """Result of analysing a video's bitrate characteristics."""
    filepath: str
    source_codec: str = "unknown"
    duration_s: float = 0.0
    avg_bitrate_kbps: float = 0.0
    max_bitrate_kbps: float = 0.0
    min_bitrate_kbps: float = 0.0
    bitrate_variance: float = 0.0       # standard-deviation in kbps
    bitrate_samples: List[float] = field(default_factory=list)  # per-second kbps samples
    resolution: Tuple[int, int] = (0, 0)
    fps: float = 0.0
    has_audio: bool = False
    audio_bitrate_kbps: float = 0.0

    @property
    def is_variable_bitrate(self) -> bool:
        """True when the source has significant bitrate swings."""
        if self.avg_bitrate_kbps == 0:
            return False
        return (self.bitrate_variance / self.avg_bitrate_kbps) > 0.25
    
    @property
    def pixel_count(self) -> int:
        """Total pixels per frame."""
        return self.resolution[0] * self.resolution[1]


@dataclass
class EncodingParams:
    """Recommended encoding parameters derived from a BitrateProfile."""
    target_bitrate_kbps: float = 0.0
    max_bitrate_kbps: float = 0.0
    bufsize_kbps: float = 0.0
    target_codec: str = ""              # e.g. "h264", "hevc"
    encoder_name: str = ""              # e.g. "h264_nvenc", "libx264"
    encoder_options: List[str] = field(default_factory=list)
    codec_efficiency_ratio: float = 1.0
    quality_headroom_pct: float = 0.05  # 5 % margin below source

    def as_ffmpeg_args(self) -> List[str]:
        """Return the list of ffmpeg CLI arguments for the video stream."""
        args: List[str] = []

        # Encoder
        args += ["-c:v", self.encoder_name]

        # Encoder-specific options (preset, tune, device, etc.)
        args += list(self.encoder_options)

        target = int(self.target_bitrate_kbps)
        maxrate = int(self.max_bitrate_kbps)
        bufsize = int(self.bufsize_kbps)

        # ---- Encoder-specific quality / bitrate flags ----
        if self.encoder_name == "libx264":
            # For software x264, use CRF with maxrate cap for best quality-per-bit.
            crf = self._estimate_crf_from_bitrate(target)
            args += [
                "-crf", str(crf),
                "-maxrate", f"{maxrate}k",
                "-bufsize", f"{bufsize}k",
            ]

        elif self.encoder_name in ("h264_nvenc", "hevc_nvenc"):
            # NVENC: use constrained-quality (CQ) mode with bitrate ceiling
            args += [
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", f"{target}k",
                "-maxrate", f"{maxrate}k",
                "-bufsize", f"{bufsize}k",
            ]

        elif self.encoder_name in ("h264_videotoolbox", "hevc_videotoolbox"):
            # VideoToolbox: ABR with max
            args += [
                "-b:v", f"{target}k",
                "-maxrate", f"{maxrate}k",
                "-bufsize", f"{bufsize}k",
            ]

        elif self.encoder_name in ("h264_qsv", "hevc_qsv"):
            # QuickSync: VBR
            args += [
                "-b:v", f"{target}k",
                "-maxrate", f"{maxrate}k",
                "-bufsize", f"{bufsize}k",
            ]

        elif self.encoder_name in ("h264_vaapi", "hevc_vaapi"):
            # VAAPI: bitrate-based
            args += [
                "-b:v", f"{target}k",
                "-maxrate", f"{maxrate}k",
                "-bufsize", f"{bufsize}k",
            ]

        else:
            # Generic fallback
            args += [
                "-b:v", f"{target}k",
                "-maxrate", f"{maxrate}k",
                "-bufsize", f"{bufsize}k",
            ]

        return args

    def _estimate_crf_from_bitrate(self, target_kbps: int) -> int:
        """Rough CRF estimate for libx264 so the encoder starts near our target."""
        if target_kbps > 8000:
            return 18
        elif target_kbps > 4000:
            return 20
        elif target_kbps > 2000:
            return 23
        elif target_kbps > 1000:
            return 26
        elif target_kbps > 500:
            return 28
        else:
            return 30

    def summary(self, profile: "BitrateProfile") -> str:
        """Human-readable comparison of source vs. target."""
        lines = [
            "╔══════════════════════════════════════════════════╗",
            "║          Bitrate Analysis Summary                ║",
            "╠══════════════════════════════════════════════════╣",
            f"║  Source file   : {os.path.basename(profile.filepath):<31s} ║",
            f"║  Source codec  : {profile.source_codec:<31s} ║",
            f"║  Resolution    : {profile.resolution[0]}x{profile.resolution[1]:<25} ║",
            f"║  Duration      : {profile.duration_s:>8.1f}s{'':<21} ║",
            f"║  FPS           : {profile.fps:>8.2f}{'':<22} ║",
            "╠──────────────────────────────────────────────────╣",
            f"║  Source avg    : {profile.avg_bitrate_kbps:>8.0f} kb/s{'':<17} ║",
            f"║  Source max    : {profile.max_bitrate_kbps:>8.0f} kb/s{'':<17} ║",
            f"║  Source min    : {profile.min_bitrate_kbps:>8.0f} kb/s{'':<17} ║",
            f"║  Variance (σ)  : {profile.bitrate_variance:>8.0f} kb/s{'':<17} ║",
            f"║  VBR detected  : {'Yes' if profile.is_variable_bitrate else 'No':<30s} ║",
            "╠──────────────────────────────────────────────────╣",
            f"║  Target codec  : {self.target_codec:<31s} ║",
            f"║  Encoder       : {self.encoder_name:<31s} ║",
            f"║  Efficiency    : {self.codec_efficiency_ratio:>5.2f}x{'':<24} ║",
            f"║  Headroom      : {self.quality_headroom_pct*100:>5.1f}%{'':<24} ║",
            "╠──────────────────────────────────────────────────╣",
            f"║  Target bitrate: {self.target_bitrate_kbps:>8.0f} kb/s{'':<17} ║",
            f"║  Max bitrate   : {self.max_bitrate_kbps:>8.0f} kb/s{'':<17} ║",
            f"║  Buffer size   : {self.bufsize_kbps:>8.0f} kb/s{'':<17} ║",
            "╚══════════════════════════════════════════════════╝",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def analyze_bitrate(filepath: str) -> BitrateProfile:
    """
    Use ffprobe to deeply analyse a video file's bitrate characteristics.
    
    We use per-packet analysis (show_packets) to get accurate min/max/variance
    rather than relying solely on the container-level average.
    """
    profile = BitrateProfile(filepath=filepath)

    # --- 1. Basic stream info (codec, resolution, fps, duration) ---
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate,bit_rate,duration",
            "-show_entries", "format=duration,bit_rate",
            "-of", "json",
            filepath,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        data = json.loads(result.stdout)

        # Stream info
        if data.get("streams"):
            stream = data["streams"][0]
            profile.source_codec = stream.get("codec_name", "unknown")
            w = int(stream.get("width", 0))
            h = int(stream.get("height", 0))
            profile.resolution = (w, h)

            # Parse frame rate (e.g. "30000/1001")
            fps_str = stream.get("r_frame_rate", "0/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                profile.fps = float(num) / float(den) if float(den) else 0
            else:
                profile.fps = float(fps_str)

            # Stream-level bitrate (not always present)
            if stream.get("bit_rate"):
                profile.avg_bitrate_kbps = int(stream["bit_rate"]) / 1000

        # Format-level fallback for duration & bitrate
        fmt = data.get("format", {})
        if fmt.get("duration"):
            profile.duration_s = float(fmt["duration"])
        if profile.avg_bitrate_kbps == 0 and fmt.get("bit_rate"):
            profile.avg_bitrate_kbps = int(fmt["bit_rate"]) / 1000

    except Exception:
        pass

    # --- 2. Per-packet bitrate analysis for accurate max / variance ---
    try:
        cmd_packets = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_packets",
            "-show_entries", "packet=size,duration_time,pts_time",
            "-of", "json",
            filepath,
        ]
        # Dynamic timeout: at least 30s, scaled by duration
        timeout = max(30, int(profile.duration_s * 0.5) + 10)
        result = subprocess.run(cmd_packets, capture_output=True, text=True, check=True, timeout=timeout)
        pkt_data = json.loads(result.stdout)

        packets = pkt_data.get("packets", [])
        if packets:
            # Aggregate packets into 1-second windows for smoother analysis
            window_bits: Dict[int, int] = {}
            for pkt in packets:
                try:
                    pts = float(pkt.get("pts_time", 0))
                    size_bytes = int(pkt.get("size", 0))
                    sec = int(pts)
                    window_bits[sec] = window_bits.get(sec, 0) + size_bytes * 8
                except (ValueError, TypeError):
                    continue

            if window_bits:
                kbps_samples = [bits / 1000 for bits in window_bits.values()]
                profile.bitrate_samples = kbps_samples
                profile.max_bitrate_kbps = max(kbps_samples)
                profile.min_bitrate_kbps = min(kbps_samples)

                mean = sum(kbps_samples) / len(kbps_samples)
                # Use the packet-derived average if we didn't get one from the stream
                if profile.avg_bitrate_kbps == 0:
                    profile.avg_bitrate_kbps = mean

                variance = sum((s - mean) ** 2 for s in kbps_samples) / len(kbps_samples)
                profile.bitrate_variance = math.sqrt(variance)

    except subprocess.TimeoutExpired:
        # For very long videos, fall back to estimated max = 2x average
        if profile.max_bitrate_kbps == 0 and profile.avg_bitrate_kbps > 0:
            profile.max_bitrate_kbps = profile.avg_bitrate_kbps * 2.0
            profile.bitrate_variance = profile.avg_bitrate_kbps * 0.3
    except Exception:
        pass

    # --- 3. Ensure we have sensible fallbacks ---
    if profile.max_bitrate_kbps == 0 and profile.avg_bitrate_kbps > 0:
        profile.max_bitrate_kbps = profile.avg_bitrate_kbps * 1.5
    if profile.min_bitrate_kbps == 0 and profile.avg_bitrate_kbps > 0:
        profile.min_bitrate_kbps = profile.avg_bitrate_kbps * 0.3

    # --- 4. Audio detection ---
    try:
        cmd_audio = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=bit_rate",
            "-of", "json",
            filepath,
        ]
        result = subprocess.run(cmd_audio, capture_output=True, text=True, check=True, timeout=5)
        adata = json.loads(result.stdout)
        if adata.get("streams"):
            profile.has_audio = True
            abr = adata["streams"][0].get("bit_rate")
            if abr:
                profile.audio_bitrate_kbps = int(abr) / 1000
    except Exception:
        pass

    return profile


# ---------------------------------------------------------------------------
# Parameter calculation
# ---------------------------------------------------------------------------
def calculate_encoding_params(
    profile: BitrateProfile,
    encoder_name: str,
    encoder_options: List[str],
    target_codec: Optional[str] = None,
    headroom_pct: float = 0.05,
) -> EncodingParams:
    """
    Given a BitrateProfile and the chosen encoder, calculate encoding parameters
    that will not exceed the source quality.

    Args:
        profile:         Output of analyze_bitrate().
        encoder_name:    e.g. "h264_nvenc", "libx264" — from get_best_encoder().
        encoder_options: Encoder-specific flags       — from get_best_encoder().
        target_codec:    Target codec name (e.g. "h264", "hevc").
                         Auto-derived from encoder_name if None.
        headroom_pct:    Percentage below source average to target (0.05 = 5%).
    """
    params = EncodingParams()
    params.encoder_name = encoder_name
    params.encoder_options = list(encoder_options)
    params.quality_headroom_pct = headroom_pct

    # Derive target codec from encoder name
    if target_codec is None:
        if "hevc" in encoder_name or "h265" in encoder_name:
            target_codec = "hevc"
        elif "av1" in encoder_name:
            target_codec = "av1"
        else:
            target_codec = "h264"
    params.target_codec = target_codec

    # Codec efficiency adjustment
    src = profile.source_codec.lower()
    tgt = target_codec.lower()
    efficiency = CODEC_EFFICIENCY.get((src, tgt), 1.0)
    params.codec_efficiency_ratio = efficiency

    # --- Calculate target bitrate ---
    # Start from source average, apply codec efficiency, then subtract headroom
    base = profile.avg_bitrate_kbps * efficiency
    params.target_bitrate_kbps = base * (1.0 - headroom_pct)

    # --- Calculate max bitrate ---
    # Scale the source peak by efficiency, then add a small margin for VBR spikes
    peak = profile.max_bitrate_kbps * efficiency
    if profile.is_variable_bitrate:
        # Allow more headroom for highly variable content (action, sports)
        params.max_bitrate_kbps = peak * 0.95
    else:
        params.max_bitrate_kbps = peak * 0.90

    # Never let maxrate be lower than target
    params.max_bitrate_kbps = max(params.max_bitrate_kbps, params.target_bitrate_kbps * 1.2)

    # --- Buffer size ---
    # A larger buffer lets the encoder handle bitrate swings more smoothly.
    if profile.is_variable_bitrate:
        params.bufsize_kbps = params.max_bitrate_kbps * 2.0
    else:
        params.bufsize_kbps = params.max_bitrate_kbps * 1.5

    # --- Safety: never exceed source (important for same-codec re-encodes) ---
    if efficiency >= 1.0:
        # Same or less efficient codec — hard-cap at source values
        params.target_bitrate_kbps = min(params.target_bitrate_kbps, profile.avg_bitrate_kbps)
        params.max_bitrate_kbps = min(params.max_bitrate_kbps, profile.max_bitrate_kbps)

    # --- Floor: don't go absurdly low ---
    params.target_bitrate_kbps = max(params.target_bitrate_kbps, 200)
    params.max_bitrate_kbps = max(params.max_bitrate_kbps, 300)
    params.bufsize_kbps = max(params.bufsize_kbps, 500)

    return params


# ---------------------------------------------------------------------------
# Convenience: one-call analyse + recommend
# ---------------------------------------------------------------------------
def get_encoding_params_for_file(
    filepath: str,
    encoder_name: str,
    encoder_options: List[str],
    target_codec: Optional[str] = None,
    headroom_pct: float = 0.05,
    verbose: bool = False,
) -> Tuple[EncodingParams, BitrateProfile]:
    """
    Analyse a file and return recommended encoding parameters.

    Usage:
        from arcade_scanner.core.video_processor import get_best_encoder
        from arcade_scanner.core.bitrate_analyzer import get_encoding_params_for_file

        encoder, opts = get_best_encoder()
        params, profile = get_encoding_params_for_file("video.mp4", encoder, opts, verbose=True)
        ffmpeg_args = params.as_ffmpeg_args()
    """
    profile = analyze_bitrate(filepath)
    params = calculate_encoding_params(profile, encoder_name, encoder_options, target_codec, headroom_pct)

    if verbose:
        print(params.summary(profile))
        print()
        print("FFmpeg video args:")
        print("  " + " ".join(params.as_ffmpeg_args()))

    return params, profile


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze video bitrate and recommend encoding parameters."
    )
    parser.add_argument("input", help="Path to input video file")
    parser.add_argument("--target-codec", default=None,
                        help="Target codec (h264, hevc, av1). Auto-detected from encoder if omitted.")
    parser.add_argument("--headroom", type=float, default=0.05,
                        help="Percentage below source avg to target (default: 0.05 = 5%%)")
    parser.add_argument("--encoder", default=None,
                        help="Force encoder name (e.g. libx264). Auto-detects HW encoder if omitted.")
    parser.add_argument("--execute", action="store_true",
                        help="Actually run ffmpeg with recommended params")
    parser.add_argument("--output", default=None,
                        help="Output path (required if --execute)")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"❌ File not found: {args.input}")
        return 1

    # Encoder detection — use forced or auto-detect
    if args.encoder:
        encoder_name = args.encoder
        encoder_options = []
        if encoder_name == "libx264":
            encoder_options = ["-preset", "ultrafast", "-crf", "28"]
    else:
        # Import from existing codebase
        try:
            from arcade_scanner.core.video_processor import get_best_encoder
            encoder_name, encoder_options = get_best_encoder()
        except ImportError:
            print("⚠️  Could not import get_best_encoder, using libx264 fallback")
            encoder_name = "libx264"
            encoder_options = ["-preset", "medium"]

    params, profile = get_encoding_params_for_file(
        args.input, encoder_name, encoder_options,
        target_codec=args.target_codec,
        headroom_pct=args.headroom,
        verbose=True,
    )

    if args.execute:
        if not args.output:
            print("❌ --output is required with --execute")
            return 1

        ffmpeg_cmd = [
            "ffmpeg", "-i", args.input,
            *params.as_ffmpeg_args(),
        ]
        # Copy audio if present
        if profile.has_audio:
            ffmpeg_cmd += ["-c:a", "aac", "-b:a", f"{min(int(profile.audio_bitrate_kbps), 192)}k"]
        else:
            ffmpeg_cmd += ["-an"]

        ffmpeg_cmd += ["-y", args.output]

        print(f"\n🎬 Executing: {' '.join(ffmpeg_cmd)}\n")
        result = subprocess.run(ffmpeg_cmd)
        return result.returncode

    return 0


if __name__ == "__main__":
    exit(main())
