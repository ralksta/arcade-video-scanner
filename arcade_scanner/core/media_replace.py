"""Server-side integrity check + atomic replace for uploaded encodes.

Deliberate twin of ``verify_output_integrity`` / ``promote_staging`` in
videocrunch's ``videocrunch.py``. That engine is standalone and lives in its
own repo: it runs on a remote Mac without this package installed, so it
cannot import from here, and importing *it* from the server would need a
sys.path hack. Keep both in sync when the verification rules change.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def verify_media_integrity(path: Path, expected_duration: float,
                           tolerance: float = 1.5) -> Tuple[bool, str]:
    """Cheap insurance before an atomic replace: correct duration + clean decode.

    Catches truncated moov atoms and half-transferred uploads, which a plain
    byte-count check on the request body cannot distinguish from a short encode.
    Pass ``expected_duration <= 0`` to skip the duration comparison.
    """
    path = Path(path)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        out_duration = float(probe.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError) as e:
        return (False, f"ffprobe failed: {e}")

    if expected_duration > 0 and abs(out_duration - expected_duration) > tolerance:
        return (False, f"duration mismatch: {out_duration:.1f}s vs expected {expected_duration:.1f}s")

    try:
        decode = subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
             "-an", "-sn", "-f", "null", "-"],
            capture_output=True, text=True, timeout=1800,
        )
    except (subprocess.SubprocessError, OSError) as e:
        return (False, f"decode check failed to run: {e}")

    if decode.returncode != 0:
        return (False, f"decode errors: {decode.stderr.strip()[:200]}")
    return (True, "ok")


def atomic_replace(staging: Path, target: Path) -> None:
    """Move `staging` onto `target` atomically.

    ``os.replace`` is only atomic within one filesystem; across a mount it
    silently degrades to copy+delete, which would leave a half-written file
    where the original used to be. Refuse that case instead.
    """
    staging, target = Path(staging), Path(target)
    anchor = target if target.exists() else target.parent
    try:
        same_fs = os.stat(staging).st_dev == os.stat(anchor).st_dev
    except OSError as e:
        raise RuntimeError(f"cannot stat replace endpoints: {e}") from e
    if not same_fs:
        raise RuntimeError(
            f"refusing non-atomic replace across filesystems: {staging} → {target}"
        )
    os.replace(staging, target)
    logger.info("Replaced %s", target)
