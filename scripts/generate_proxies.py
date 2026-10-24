#!/usr/bin/env python3
"""Generates proxy files for streaming from outside the LAN.

RUNS ON: the scanner host (database, originals and proxy destination live there).
ENCODES ON: the machine reachable via --remote that has an NVIDIA GPU.

Per file:

    original --rsync--> remote --ffmpeg/NVENC--> remote --rsync--> proxy tree

Originals are READ ONLY. Writes happen exclusively below --proxy-root, and only
after a complete transfer back (written under a temporary name, then renamed) —
so an abort never leaves a half file behind that the server would then serve.

The run is resumable: existing proxies are skipped.

Scanner without Docker (database paths are already host paths):

    python3 scripts/generate_proxies.py --remote gpubox --dry-run

Scanner in Docker — the database only knows container paths, so supply one
mapping per mounted media directory:

    python3 scripts/generate_proxies.py --remote gpubox \\
        --mount /media=/srv/media --mount /photos=/srv/photos \\
        --tree /media/clips/ --limit 3
"""

from __future__ import annotations

import argparse
import os
import shlex
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from arcade_scanner.core.master_detect import MASTER, classify, session_of  # noqa: E402
from arcade_scanner.core.proxy_resolver import is_proxy_stale  # noqa: E402

DEFAULT_DB = str(SCRIPT_DIR.parent / "arcade_data" / "media_library.db")

# ANSI-Farben für die Konsolenausgabe
G = "\033[92m"   # grün
Y = "\033[93m"   # gelb
R = "\033[91m"   # rot
C = "\033[96m"   # cyan
B = "\033[1m"    # fett
N = "\033[0m"    # zurücksetzen


def log(msg: str = "") -> None:
    print(msg, flush=True)


def human(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def parse_mount(spec: str) -> tuple:
    """--mount /in/container=/on/the/host"""
    if "=" not in spec:
        raise argparse.ArgumentTypeError(
            f"--mount expects CONTAINER=HOST, got: {spec!r}")
    container, host = spec.split("=", 1)
    return container.rstrip("/"), host.rstrip("/")


def to_host(container_path: str, mounts: dict) -> str | None:
    """Translate a container path into the host path.

    Without --mount (scanner not running in Docker) both paths are identical.
    """
    if not mounts:
        return container_path
    for prefix in sorted(mounts, key=len, reverse=True):
        if container_path == prefix or container_path.startswith(prefix + "/"):
            return mounts[prefix] + container_path[len(prefix):]
    return None


def configured_proxy_root() -> str:
    """proxy_root from the scanner settings — the source of truth for it.

    This is a CONTAINER path when the server runs in Docker, so it is translated
    through --mount below.
    """
    try:
        from arcade_scanner.config import config
        return (config.settings.proxy_root or "").strip()
    except Exception:
        return ""


def proxy_host_path(container_path: str, proxy_root: str) -> str:
    """Zielpfad im Proxy-Baum — gleiche Abbildung wie core/proxy_resolver.py.

    Der komplette Original-Pfad wird gespiegelt, damit Dateien aus
    verschiedenen Mounts nicht kollidieren.
    """
    relative = container_path.lstrip("/")
    stem, _ = os.path.splitext(relative)
    return os.path.join(proxy_root, stem + ".mp4")


# ── Candidate selection ─────────────────────────────────────────────────────

def select_candidates(db_path, min_mbps, max_mbps, tree, include_orphans, excludes):
    """Yields (container_path, bitrate, size_mb, duration, reason)."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "select file_path, bitrate_mbps, size_mb, duration_sec from media "
            "where file_path like ? and media_type = 'video'",
            (tree + "%",),
        ).fetchall()
    finally:
        con.close()

    prefix_len = len(tree.rstrip("/")) + 1

    # Sessions that contain anything playable on the road at all.
    playable_sessions = set()
    for path, br, _size, _dur in rows:
        rel = path[prefix_len:]
        if classify(rel)[0] != MASTER or br < min_mbps:
            playable_sessions.add(session_of(rel))

    selected = []
    for path, br, size, dur in rows:
        if path in excludes:
            continue
        if not (min_mbps <= br < max_mbps):
            continue

        rel = path[prefix_len:]
        verdict, _reasons = classify(rel)

        if verdict != MASTER:
            selected.append((path, br, size, dur, "edited version"))
        elif include_orphans and session_of(rel) not in playable_sessions:
            # Raw material, but its session has nothing else playable — without
            # a proxy there would be nothing at all to watch from that shoot.
            selected.append((path, br, size, dur, "raw material, no alternative"))

    selected.sort(key=lambda r: r[2])  # smallest first: visible progress early on
    return selected


# ── Encoding ────────────────────────────────────────────────────────────────

def build_ffmpeg_command(remote_in, remote_out, height, bitrate, ten_bit):
    """ffmpeg invocation for the remote side (as a single shell line)."""
    # Fits the image into a height x height box: landscape becomes 1920x1080,
    # portrait becomes 1080x1920. force_divisible_by=2 because of 4:2:0.
    scale = (f"scale=w={height}:h={height}"
             ":force_original_aspect_ratio=decrease:force_divisible_by=2")

    args = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-hwaccel", "cuda",              # decode on the GPU
        "-i", remote_in,
        "-vf", scale,
        "-c:v", "hevc_nvenc",
        "-preset", "p5",
        "-tune", "hq",
        "-rc", "vbr",
        "-cq", "28",
        "-b:v", f"{bitrate}M",
        "-maxrate", f"{int(bitrate * 1.5)}M",
        "-bufsize", f"{bitrate * 2}M",
        # 10-bit sources stay 10-bit so that HDR is not destroyed.
        "-profile:v", "main10" if ten_bit else "main",
        "-pix_fmt", "p010le" if ten_bit else "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        "-movflags", "+faststart",       # starts without buffering the whole file
        remote_out,
    ]
    return " ".join(shlex.quote(a) for a in args)


def probe_is_ten_bit(path: str) -> bool:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=60,
        ).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return any(tag in out for tag in ("p010", "10le", "10be", "yuv420p10"))


def run(cmd, **kwargs):
    return subprocess.run(cmd, **kwargs)


def process_one(item, args, index, total):
    container_path, br, size_mb, dur, reason = item
    host_src = to_host(container_path, args.mounts)
    name = os.path.basename(container_path)

    log(f"\n{B}[{index}/{total}]{N} {name}")
    log(f"    {size_mb/1024:.2f} GB · {br:.0f} Mbit · {dur/60:.1f} min · {reason}")

    if host_src is None:
        log(f"    {R}✗ no host path for {container_path}{N}")
        return "error"
    if not os.path.isfile(host_src):
        log(f"    {Y}⚠ original missing (renamed? rescan needed) — skipped{N}")
        return "missing"

    target = proxy_host_path(container_path, args.proxy_root)
    if os.path.isfile(target) and not args.force:
        # Vorhandensein allein reicht nicht: wurde das Original nach dem Proxy
        # geändert (neuer Schnitt, andere Tonspur), zeigt der Proxy eine Fassung,
        # die es nicht mehr gibt. Der Server liefert dann ohnehin das Original
        # aus — hier erneuern wir ihn, damit unterwegs wieder die kleine Datei
        # greift.
        if is_proxy_stale(host_src, target):
            log(f"    {Y}→ proxy is older than the original, regenerating{N}")
        else:
            log(f"    {C}→ proxy already exists, skipped{N}")
            return "skipped"

    if args.dry_run:
        log(f"    {C}would create: {target}{N}")
        return "dry"

    remote_in = f"{args.remote_dir}/in_{index}{Path(name).suffix}"
    remote_out = f"{args.remote_dir}/out_{index}.mp4"
    started = time.time()

    try:
        run(["ssh", args.remote, f"mkdir -p {shlex.quote(args.remote_dir)}"], check=True)

        log("    ↑ transferring to the GPU machine")
        run(["rsync", "-a", "--partial", host_src, f"{args.remote}:{remote_in}"], check=True)

        log("    ⚙ encoding (NVENC)")
        cmd = build_ffmpeg_command(remote_in, remote_out, args.height, args.bitrate,
                                   probe_is_ten_bit(host_src))
        result = run(["ssh", args.remote, cmd], capture_output=True, text=True)
        if result.returncode != 0:
            log(f"    {R}✗ ffmpeg failed:{N}")
            for line in (result.stderr or "").splitlines()[:6]:
                log(f"      {line}")
            return "error"

        # Download in full first, then rename into the final place — otherwise
        # the server could serve a half-written file.
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp_target = target + ".part"
        log("    ↓ transferring back")
        run(["rsync", "-a", "--partial", f"{args.remote}:{remote_out}", tmp_target], check=True)

        new_size = os.path.getsize(tmp_target)
        if new_size < 1024:
            os.remove(tmp_target)
            log(f"    {R}✗ result is essentially empty — discarded{N}")
            return "error"

        os.replace(tmp_target, target)

    except subprocess.CalledProcessError as exc:
        log(f"    {R}✗ transfer failed: {exc}{N}")
        return "error"
    finally:
        run(["ssh", args.remote, f"rm -f {shlex.quote(remote_in)} {shlex.quote(remote_out)}"],
            capture_output=True)

    elapsed = time.time() - started
    saved = size_mb * 1024 * 1024 - new_size
    log(f"    {G}✓ {human(new_size)} instead of {human(size_mb*1024*1024)} "
        f"({saved/(size_mb*1024*1024)*100:.0f}% smaller, {elapsed/60:.1f} min){N}")
    return "done"


def main():
    p = argparse.ArgumentParser(
        description="Generates proxy files on a remote GPU machine.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--remote", required=True,
                   help="SSH target of the GPU machine, e.g. user@host or a ~/.ssh/config alias")
    p.add_argument("--remote-dir", default="~/arcade-proxy-work",
                   help="Work directory there (needs room for the largest single file)")
    p.add_argument("--mount", action="append", type=parse_mount, default=[],
                   metavar="CONTAINER=HOST",
                   help="Path mapping when the scanner runs in Docker. "
                        "Repeatable. Without it paths are assumed identical.")
    p.add_argument("--proxy-root", default="",
                   help="Destination for the proxies. Taken from the scanner settings if omitted.")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--tree", default="/",
                   help="Only files below this container path")
    p.add_argument("--min-mbps", type=float, default=20.0)
    p.add_argument("--max-mbps", type=float, default=100.0)
    p.add_argument("--height", type=int, default=1920,
                   help="Longest edge of the proxy (1920 = 1080p both landscape and portrait)")
    p.add_argument("--bitrate", type=int, default=6, help="Target bitrate in Mbit/s")
    p.add_argument("--exclude-file", default=str(SCRIPT_DIR.parent / "arcade_data"
                                                 / "proxy_exclude.txt"),
                   help="File of container paths (one per line) that never get a proxy")
    p.add_argument("--no-orphan-masters", action="store_true",
                   help="Skip raw material even when its session has nothing else")
    p.add_argument("--limit", type=int, default=0, help="Only the first N files (0 = all)")
    p.add_argument("--force", action="store_true", help="Re-create existing proxies")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    args.mounts = dict(args.mount)

    proxy_root = args.proxy_root or configured_proxy_root()
    if not proxy_root:
        p.error("No proxy destination: neither --proxy-root nor 'proxy_root' in the "
                "scanner settings is set.")
    # The value from the settings is a container path; here we need the host
    # path, otherwise the script writes into nowhere.
    args.proxy_root = to_host(proxy_root, args.mounts) or proxy_root

    excludes = set()
    if os.path.isfile(args.exclude_file):
        with open(args.exclude_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    excludes.add(line)

    items = select_candidates(args.db, args.min_mbps, args.max_mbps, args.tree,
                              not args.no_orphan_masters, excludes)
    if args.limit:
        items = items[: args.limit]

    total_gb = sum(i[2] for i in items) / 1024
    total_h = sum(i[3] for i in items) / 3600
    log(f"{B}{C}Proxy generator{N}")
    log(f"  source:   {args.tree} ({args.min_mbps:.0f}-{args.max_mbps:.0f} Mbit)")
    log(f"  target:   {args.proxy_root}")
    log(f"  gpu:      {args.remote}")
    log(f"  selected: {len(items)} files, {total_gb:.1f} GB, {total_h:.1f} h of material")
    if excludes:
        log(f"  excluded: {len(excludes)} path(s) from {os.path.basename(args.exclude_file)}")
    if args.dry_run:
        log(f"  {Y}dry run — nothing will be written{N}")

    if not items:
        log("\nNothing to do.")
        return 0

    tally = {}
    for i, item in enumerate(items, 1):
        outcome = process_one(item, args, i, len(items))
        tally[outcome] = tally.get(outcome, 0) + 1

    log(f"\n{B}Done.{N} " + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))
    return 1 if tally.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
