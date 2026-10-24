#!/usr/bin/env python3
"""
Folder Scanner — ranks a directory's videos by expected re-encode savings.

Answers "which of these 150 files is worth optimizing?" without encoding
anything: ffprobe metadata only, a few seconds for a large folder. The ranking
itself is arcade_scanner.core.optimization_advisor.build_candidates — the same
function behind the dashboard's candidate list, including the override from
real past encodes in ~/.arcade-scanner/logs/encode_history.jsonl.

Mark the entries you want (e.g. `1,3,7-10`) and they are handed to
batch_controller.py, which runs the encodes in parallel.
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from arcade_scanner.config import ALLOWED_VIDEO_EXTENSIONS  # noqa: E402
from arcade_scanner.core.optimization_advisor import (  # noqa: E402
    EncodeHistory,
    build_candidates,
)
from arcade_scanner.models.video_entry import VideoEntry  # noqa: E402

# --- COLORS ---
G = '\033[0;32m'
BG = '\033[1;32m'
R = '\033[0;31m'
Y = '\033[0;33m'
CYAN = '\033[0;36m'
DIM = '\033[2m'
NC = '\033[0m'

VIDEO_EXTENSIONS = frozenset(ALLOWED_VIDEO_EXTENSIONS)
PROBE_WORKERS = 8
PROBE_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _as_float(value: Any) -> float:
    """ffprobe writes "N/A" for anything it cannot determine."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def has_optimized_sibling(path: Path) -> bool:
    """True when the optimizer already wrote a `<stem>_opt.mp4` next to it."""
    return (path.parent / f"{path.stem}_opt.mp4").exists()


def find_videos(root: Path) -> list[Path]:
    """All video files under `root`, minus the optimizer's own output.

    `_opt.mp4` results and `._staging_q*` leftovers are skipped: offering to
    re-encode them would just compress an encode of an encode.
    """
    found = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if path.stem.endswith("_opt") or "._staging_q" in path.name:
            continue
        found.append(path)
    return sorted(found)


def entry_from_probe(file_path: str, probe: dict) -> Optional[VideoEntry]:
    """Build a VideoEntry from raw ffprobe JSON, or None if it is not a video.

    Mirrors arcade_scanner/scanner/media_probe.py so a folder scan ranks a file
    exactly like the library scan would, with one addition: when the container
    omits `format.bit_rate` (common in Matroska) it is derived from size and
    duration. Without that the entry would rank as 0 Mbit/s and never appear.
    """
    streams = probe.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        return None

    fmt = probe.get("format", {})
    size_bytes = _as_float(fmt.get("size", 0))
    duration = _as_float(fmt.get("duration", 0))
    bitrate_bps = _as_float(fmt.get("bit_rate", 0))
    if bitrate_bps <= 0 and duration > 0:
        bitrate_bps = size_bytes * 8 / duration

    fps_str = str(video_stream.get("avg_frame_rate", "0/0"))
    if "/" in fps_str:
        numerator, _, denominator = fps_str.partition("/")
        den = _as_float(denominator)
        fps = _as_float(numerator) / den if den > 0 else 0.0
    else:
        fps = _as_float(fps_str)

    return VideoEntry(
        file_path=file_path,
        size_mb=round(size_bytes / (1024 * 1024), 2),
        Bitrate_Mbps=round(bitrate_bps / 1_000_000, 2),
        codec=video_stream.get("codec_name", "unknown"),
        Duration_Sec=round(duration, 2),
        Width=_as_int(video_stream.get("width", 0)),
        Height=_as_int(video_stream.get("height", 0)),
        FrameRate=round(fps, 3),
        media_type="video",
    )


def parse_selection(text: str, count: int) -> list[int]:
    """Parse the selection line into sorted, unique 1-based indices.

    Accepts `1,3,7-10`, `a`/`alle`/`all` for everything, empty for nothing.
    Raises ValueError on anything unparseable or out of range — quietly
    dropping a bad entry would start an encode run that silently differs from
    what the user typed.
    """
    text = text.strip().lower()
    if not text:
        return []
    if text in ("a", "all", "alle"):
        return list(range(1, count + 1))

    selected: set = set()
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            lo_str, _, hi_str = token.partition("-")
            lo, hi = _parse_index(lo_str, count), _parse_index(hi_str, count)
            if lo > hi:
                lo, hi = hi, lo  # "10-7" reads the same as "7-10"
            selected.update(range(lo, hi + 1))
        else:
            selected.add(_parse_index(token, count))
    return sorted(selected)


def _parse_index(token: str, count: int) -> int:
    token = token.strip()
    if not token.isdigit():
        raise ValueError(f"Ungültige Eingabe: '{token}'")
    index = int(token)
    if index < 1 or index > count:
        raise ValueError(f"Nummer {index} gibt es nicht (1–{count})")
    return index


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------

def probe_file(path: Path) -> Optional[VideoEntry]:
    """ffprobe one file. Metadata only — no decoding, so this is fast."""
    cmd = [
        'ffprobe', '-v', 'error', '-print_format', 'json',
        '-show_format', '-show_streams', str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=PROBE_TIMEOUT)
        if result.returncode != 0:
            return None
        return entry_from_probe(str(path), json.loads(result.stdout))
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError, ValueError):
        return None


def probe_all(paths: list[Path]) -> list[VideoEntry]:
    """Probe every file in parallel, with a progress counter."""
    entries: list[VideoEntry] = []
    done = 0
    total = len(paths)
    with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as executor:
        for entry in executor.map(probe_file, paths):
            done += 1
            sys.stdout.write(f"\r{Y}Lese Metadaten...{NC} {done}/{total}")
            sys.stdout.flush()
            if entry is not None:
                entries.append(entry)
    sys.stdout.write("\r" + " " * 40 + "\r")
    return entries


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _files(n: int) -> str:
    return "Datei" if n == 1 else "Dateien"


def format_size(mb: float) -> str:
    return f"{mb/1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def print_table(candidates: list[dict], name_width: int = 46) -> None:
    print(f"\n{BG}{'#':>3}  {'Ersparnis':>10}  {'%':>4}  "
          f"{'Datei':<{name_width}}  Info{NC}")
    print(DIM + "─" * (name_width + 40) + NC)
    for i, c in enumerate(candidates, start=1):
        name = Path(c['file_path']).name
        if len(name) > name_width:
            name = name[:name_width - 1] + "…"
        conf = {"high": G, "medium": Y, "low": DIM}.get(c['confidence'], NC)
        print(f"{CYAN}{i:>3}{NC}  {G}{format_size(c['estimated_saved_mb']):>10}{NC}  "
              f"{c['estimated_saved_pct']:>3.0f}%  {name:<{name_width}}  "
              f"{conf}{c['reason']}{NC}")


def run_batch(paths: list[str], audio_mode: str, port: Optional[int]) -> int:
    """Hand the marked files to batch_controller.py for parallel encoding."""
    cmd = [sys.executable, str(Path(__file__).parent / "batch_controller.py"),
           '--files', ",".join(paths), '--audio-mode', audio_mode]
    if port:
        cmd.extend(['--port', str(port)])
    return subprocess.run(cmd).returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description='Rank a folder\'s videos by expected re-encode savings')
    parser.add_argument('folder', help='Folder to scan (searched recursively)')
    parser.add_argument('--codec', choices=['hevc', 'av1'], default='hevc',
                        help='Target codec for the estimate (default: hevc)')
    parser.add_argument('--limit', type=int, default=30,
                        help='Show at most N candidates (default: 30)')
    parser.add_argument('--audio-mode', choices=['enhanced', 'standard'],
                        default='enhanced', help='Audio mode for the encode run')
    parser.add_argument('--port', type=int, help='Port of a running Arcade Server')
    parser.add_argument('--no-encode', action='store_true',
                        help='Only print the ranking, never ask to encode')
    args = parser.parse_args()

    root = Path(args.folder).expanduser()
    if not root.is_dir():
        print(f"{R}Kein Ordner: {root}{NC}")
        return 1

    print(f"{BG}═══════════════════════════════════════════{NC}")
    print(f"{BG}  🔍 Arcade Folder Scanner{NC}")
    print(f"{BG}═══════════════════════════════════════════{NC}")
    print(f"{G}Ordner:{NC} {root}")

    paths = find_videos(root)
    if not paths:
        print(f"{Y}Keine Videodateien gefunden.{NC}")
        return 0
    print(f"{G}Gefunden:{NC} {len(paths)} Videodateien\n")

    entries = probe_all(paths)
    if not entries:
        print(f"{R}Keine lesbaren Videodateien.{NC}")
        return 1

    # Files that already have an _opt.mp4 next to them are done.
    exclude = {str(p) for p in paths if has_optimized_sibling(p)}

    result = build_candidates(entries, args.codec, EncodeHistory(), exclude,
                              limit=args.limit)
    # `results` is already truncated to `limit`; `summary` counts them all.
    candidates = result['results']
    summary = result['summary']

    if not candidates:
        print(f"{Y}Kein Kandidat über der 10%-Schwelle — hier ist nichts zu holen.{NC}")
        return 0

    print_table(candidates)

    hidden = len(entries) - len(exclude) - summary['total_files']
    print(DIM + f"\n{summary['total_files']} Kandidaten, zusammen ~"
          f"{format_size(summary['total_estimated_saved_mb'])} Ersparnis erwartet."
          + NC)
    if hidden > 0:
        print(DIM + f"{hidden} {_files(hidden)} unter 10% erwarteter Ersparnis "
              f"ausgeblendet." + NC)
    if exclude:
        n = len(exclude)
        print(DIM + f"{n} {_files(n)} {'hat' if n == 1 else 'haben'} bereits "
              f"ein _opt.mp4." + NC)
    if summary.get('history_based'):
        print(DIM + f"{summary['history_based']} Schätzungen beruhen auf echten "
              f"früheren Encodes (grün), der Rest ist Heuristik." + NC)

    if args.no_encode:
        return 0

    shown = candidates
    print(f"\n{Y}Welche encodieren?{NC} z.B. {CYAN}1,3,7-10{NC} · "
          f"{CYAN}a{NC} = alle · {CYAN}Enter{NC} = keine")
    try:
        raw = input("  Auswahl: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

    try:
        picked = parse_selection(raw, len(shown))
    except ValueError as e:
        print(f"{R}{e}{NC}")
        return 1

    if not picked:
        print(f"{Y}Nichts ausgewählt.{NC}")
        return 0

    selected = [shown[i - 1]['file_path'] for i in picked]
    total_mb = sum(shown[i - 1]['estimated_saved_mb'] for i in picked)
    print(f"\n{G}{len(selected)} {_files(len(selected))}{NC}, erwartete Ersparnis "
          f"~{format_size(total_mb)}:")
    for path in selected:
        print(f"  {DIM}·{NC} {Path(path).name}")

    return run_batch(selected, args.audio_mode, args.port)


if __name__ == "__main__":
    sys.exit(main())
