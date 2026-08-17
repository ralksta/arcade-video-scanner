import asyncio
import concurrent.futures
import json
import os
import threading
import time
from typing import AsyncIterator, List, Optional, Set, Tuple

from ..config import config


class AsyncFileSystem:
    """
    Handles asynchronous file system traversal.
    Uses asyncio to prevent blocking the main event loop during long scans.
    """

    VIDEO_EXTENSIONS = frozenset({'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts'})
    IMAGE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic', '.avif'})

    def __init__(self):
        self.allow_images = False # Toggled by ScannerManager based on user settings
        self._last_scan_time = 0.0
        self._scan_time_file = None  # Set lazily when config is available
        self._skipped_dirs = 0

    def _load_settings(self):
        """Reload settings from config (called at scan start)."""
        self.min_size_bytes = config.settings.min_size_mb * 1024 * 1024

        # Ausschlüsse kommen in drei Schreibweisen, und alle drei sind gewollt:
        #
        #   /home/ralf/privat     absoluter Pfad — genau dieser Baum
        #   @eaDir                nackter Name   — jeder Ordner, der so heißt
        #   AppData/Local/Temp    Teilpfad       — jeder Ordner, der so endet
        #
        # Vorher lief alles durch os.path.abspath(). Aus "@eaDir" wurde damit
        # "<Arbeitsverzeichnis des Servers>/@eaDir" — ein Pfad, den es nicht
        # gibt. Sämtliche mitgelieferten Voreinstellungen waren dadurch
        # wirkungslos: @eaDir und #recycle (Synology), Temporary Items und
        # Network Trash Folder, $RECYCLE.BIN und die Temp-Ordner unter Windows.
        # Nachgemessen an einem Baum mit genau diesen Ordnern: alle vier
        # Dateien landeten in der Bibliothek.
        #
        # Auf einem Synology-NAS ist das gut sichtbar — @eaDir enthält zu jeder
        # Mediendatei eine Miniatur, die Bibliothek wäre doppelt so groß.
        self.exclude_abs: Set[str] = set()
        self.exclude_names: Set[str] = set()
        self.exclude_suffixes: Set[str] = set()

        for p in config.active_exclude_paths:
            expanded = os.path.expanduser(p).strip()
            if not expanded:
                continue

            normalized = expanded.replace("\\", os.sep).rstrip(os.sep)

            if os.path.isabs(expanded):
                self.exclude_abs.add(os.path.abspath(expanded))
            elif os.sep in normalized:
                self.exclude_suffixes.add(normalized)
            else:
                self.exclude_names.add(normalized)

        # Load last scan time
        self._scan_time_file = os.path.join(config.hidden_data_dir, ".last_scan_time")
        self._load_last_scan_time()
        self._skipped_dirs = 0

    def _load_last_scan_time(self):
        """Load the timestamp of the last successful scan."""
        try:
            if self._scan_time_file and os.path.exists(self._scan_time_file):
                with open(self._scan_time_file, 'r') as f:
                    data = json.load(f)
                    self._last_scan_time = float(data.get('last_scan_time', 0))
        except Exception:
            self._last_scan_time = 0.0

    def save_last_scan_time(self):
        """Save the current time as last scan timestamp."""
        try:
            if self._scan_time_file:
                os.makedirs(os.path.dirname(self._scan_time_file), exist_ok=True)
                with open(self._scan_time_file, 'w') as f:
                    json.dump({'last_scan_time': time.time()}, f)
        except Exception as e:
            print(f"⚠️ Could not save scan time: {e}")

    async def scan_directories(self, targets: List[str]) -> AsyncIterator[Tuple[str, bool]]:
        """
        Asynchronously yields ``(absolute_path, dir_changed)`` tuples for valid
        media files found in targets.
        """
        # Reload settings fresh (picks up any changes to exclusions/min_size)
        self._load_settings()

        for target in targets:
            abs_target = os.path.abspath(os.path.expanduser(target))
            if not os.path.exists(abs_target):
                print(f"⚠️ Warning: Scan target not found: {abs_target}")
                continue

            excludes = self._exclusions_for_target(abs_target)
            if excludes is None:
                print(f"🔒 Skipping excluded scan target: {target}")
                continue

            # Bounded queue: limits RAM usage to ~500 paths at a time.
            # The walker thread blocks on put() when full → natural backpressure.
            queue: asyncio.Queue = asyncio.Queue(maxsize=500)

            # Lets the walker thread find out that nobody is draining any more.
            # Without it, a consumer that stops early (ScannerManager breaks out
            # of this loop when its stop event fires) leaves the walker blocked
            # on a full queue, holding its executor thread until the event loop
            # dies — one lost worker per abandoned scan.
            cancel = threading.Event()
            walker = asyncio.create_task(
                self._walker_worker(abs_target, queue, cancel, excludes)
            )

            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield item
            finally:
                cancel.set()
                walker.cancel()


        if self._skipped_dirs > 0:
            print(f"\n⚡ Skipped {self._skipped_dirs} unchanged directories (incremental scan)")

    def _matches_name_or_suffix(self, abs_path: str) -> bool:
        """Trifft ein Name-Ausschluss oder ein Teilpfad-Ausschluss auf diesen Ordner?"""
        if self.exclude_names:
            parts = abs_path.split(os.sep)
            if self.exclude_names.intersection(parts):
                return True

        for suffix in self.exclude_suffixes:
            if abs_path == suffix or abs_path.endswith(os.sep + suffix):
                return True

        return False

    def _exclusions_for_target(self, abs_target: str) -> Optional[Set[str]]:
        """Ausschlüsse in der Schreibweise dieses Ziels. None = Ziel ganz überspringen.

        Hintergrund: ``os.walk`` folgt Symlinks nicht, Unterverzeichnisse sind
        also sicher. Das **Ziel selbst** wird aber betreten, egal ob es ein
        Symlink ist — und die Pfade, die dabei entstehen, tragen den Namen des
        Symlinks. Ein Ausschluss auf das echte Verzeichnis passt darauf nie.

        Gemessen am Beispiel: Ziel ``…/alias/p`` (Symlink auf ``…/privat``),
        Ausschluss ``…/privat`` — beide Dateien unter ``privat`` landeten in der
        Bibliothek. Für eine Datenschutz-Funktion ist das die falsche Richtung
        des Fehlers.

        Deshalb werden die Ausschlüsse einmal je Ziel übersetzt, statt bei jedem
        Verzeichnis aufzulösen: ein ``realpath`` pro Ausschluss statt eines pro
        besuchtem Ordner. Die abgelegten Pfade bleiben dabei unverändert — sie
        umzuschreiben würde bestehende Einträge, Favoriten und Tags entwerten.
        """
        real_target = os.path.realpath(abs_target)
        if self._matches_name_or_suffix(abs_target) or self._matches_name_or_suffix(real_target):
            return None

        if real_target == abs_target and not any(
            os.path.realpath(ex) != ex for ex in self.exclude_abs
        ):
            return self.exclude_abs

        translated = set(self.exclude_abs)
        for ex in self.exclude_abs:
            real_ex = os.path.realpath(ex)

            # Das Ziel liegt selbst im ausgeschlossenen Baum.
            if real_target == real_ex or real_target.startswith(real_ex + os.sep):
                return None

            # Der Ausschluss liegt im Ziel — unter dem Namen, den der Walk sieht.
            if real_ex.startswith(real_target + os.sep):
                translated.add(abs_target + real_ex[len(real_target):])

        return translated

    async def _walker_worker(self, root_dir: str, queue: asyncio.Queue,
                             cancel: threading.Event,
                             excludes: Optional[Set[str]] = None) -> None:
        """
        Worker that runs in a thread.
        Uses a bounded queue to prevent memory explosion with 50K+ files.
        Blocking put() inside a thread + run_in_executor provides natural backpressure.

        `cancel` is set when the consumer stops reading; the walker checks it
        while waiting on the queue so an abandoned scan gives its thread back.
        """
        loop = asyncio.get_event_loop()
        exclude_abs = self.exclude_abs if excludes is None else excludes

        def put_blocking(payload) -> bool:
            """Hand one item to the queue. Returns False if the scan was abandoned."""
            future = asyncio.run_coroutine_threadsafe(queue.put(payload), loop)
            while True:
                if cancel.is_set():
                    future.cancel()
                    return False
                try:
                    future.result(timeout=0.2)
                    return True
                except concurrent.futures.TimeoutError:
                    continue  # Queue still full — re-check cancel, then keep waiting.

        def sync_walk():
            try:
                for root, dirs, files in os.walk(root_dir):
                    if cancel.is_set():
                        return
                    abs_root = os.path.abspath(root)

                    # 1. Skip root if it matches any exclusion (O(n_excludes))
                    if self._matches_name_or_suffix(abs_root) or any(
                            abs_root == ex or abs_root.startswith(ex + os.sep)
                            for ex in exclude_abs):
                        dirs.clear()  # Don't descend into excluded subtrees
                        continue

                    # 2. Prune excluded subdirs in-place
                    dirs[:] = [
                        d for d in dirs
                        if os.path.abspath(os.path.join(root, d)) not in exclude_abs
                        and d not in self.exclude_names
                    ]

                    # 3. Incremental scan: skip dirs unchanged since last scan
                    dir_changed = True
                    if self._last_scan_time > 0:
                        try:
                            if os.stat(root).st_mtime < self._last_scan_time:
                                dir_changed = False
                                self._skipped_dirs += 1
                        except OSError:
                            pass  # Can't stat → assume changed

                    for file in files:
                        if not self._is_video(file):
                            continue
                        full_path = os.path.join(root, file)
                        if dir_changed and not self._is_valid_size(full_path):
                            continue
                        # Blocking put provides natural backpressure on the bounded queue
                        if not put_blocking((full_path, dir_changed)):
                            return
            except Exception as e:
                print(f"❌ Error walking {root_dir}: {e}")

        await loop.run_in_executor(None, sync_walk)

        # Skip the sentinel on an abandoned scan: nobody is reading, and the
        # queue may be full, so this put would block forever.
        if not cancel.is_set():
            await queue.put(None)

    def _is_video(self, filename: str) -> bool:
        # Skip macOS resource fork files (e.g., ._video.mp4)
        if filename.startswith("._"):
            return False

        ext = os.path.splitext(filename)[1].lower()
        if ext in self.VIDEO_EXTENSIONS:
            return True
        if self.allow_images and ext in self.IMAGE_EXTENSIONS:
            return True
        return False

    def _is_valid_size(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()

        # Images use KB threshold (configurable, e.g., 500 KB)
        if ext in self.IMAGE_EXTENSIONS:
            try:
                return os.path.getsize(path) >= config.settings.min_image_size_kb * 1024
            except OSError:
                return False

        # Optimization check for videos
        basename = os.path.basename(path)
        if "_opt." in basename or "_trim." in basename:
            return True

        try:
            return os.path.getsize(path) >= self.min_size_bytes
        except OSError:
            return False

# Singleton
fs_scanner = AsyncFileSystem()

