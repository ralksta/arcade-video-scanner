"""Server-side integrity check + atomic replace for uploaded encodes.

Deliberate twin of ``verify_output_integrity`` / ``promote_staging`` in
``scripts/video_optimizer.py`` (~line 385). That script is standalone: it runs
on a remote Mac without this package installed, so it cannot import from here,
and importing *it* from the server would need a sys.path hack. Keep both in
sync when the verification rules change.
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


class TargetCollision(RuntimeError):
    """Der Zielname gehört bereits einer anderen Datei."""


def check_target_collision(original: Path, target: Path) -> None:
    """Verhindert, dass ein Encode eine *fremde* Datei überschreibt.

    Der Optimierer schreibt immer ``.mp4``. Aus ``film.mkv`` wird also
    ``film.mp4`` — und wenn daneben schon eine ``film.mp4`` liegt, ist das eine
    andere Datei mit anderem Inhalt. ``os.replace`` und ``os.rename``
    überschreiben sie auf POSIX wortlos.

    Zwei Wege dorthin, beide in einer Mediensammlung nicht ausgefallen:

      * dieselbe Aufnahme in zwei Behältern (``film.mkv`` neben ``film.mp4``) —
        wer die mkv optimiert, verliert die mp4
      * zwei Quellen mit gleichem Stamm (``film.mkv``, ``film.avi``), beide in
        der Warteschlange — die zweite fertige Umwandlung überschreibt die erste,
        und beide Originale sind zu dem Zeitpunkt schon gelöscht

    Deshalb wird hier abgebrochen statt umbenannt: Ein selbst gewählter
    Ausweichname (``film_opt.mp4``) wäre stillschweigend etwas anderes als das,
    was der Nutzer angestoßen hat. Welche der beiden Dateien er behalten will,
    kann nur er entscheiden.
    """
    original, target = Path(original), Path(target)
    if original == target:
        return
    if target.exists():
        raise TargetCollision(
            f"'{target.name}' existiert bereits und gehört nicht zu "
            f"'{original.name}' — die Umwandlung würde sie überschreiben"
        )


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
