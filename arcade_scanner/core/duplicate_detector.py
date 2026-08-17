"""
Duplicate Media Detection Module.
Finds duplicate videos and images in the media library.
"""
import hashlib
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Optional imagehash for perceptual image hashing
try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False


@dataclass
class DuplicateFile:
    """Represents a single file in a duplicate group."""
    path: str
    size_mb: float
    media_type: str  # video or image
    quality_score: float = 0.0

    # Video metadata
    duration_sec: float = 0.0
    bitrate_mbps: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""

    # Image metadata
    image_hash: str = ""

    # Thumbnail for UI display
    thumb: str = ""


@dataclass
class DuplicateGroup:
    """Represents a group of duplicate files."""
    group_id: str
    match_type: str  # exact, hash, filename
    media_type: str  # video, image, mixed
    confidence: float
    files: List[DuplicateFile] = field(default_factory=list)
    recommended_keep: str = ""
    potential_savings_mb: float = 0.0

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "match_type": self.match_type,
            "media_type": self.media_type,
            "confidence": self.confidence,
            "files": [
                {
                    "path": f.path,
                    "size_mb": f.size_mb,
                    "quality_score": f.quality_score,
                    "duration_sec": f.duration_sec,
                    "bitrate_mbps": f.bitrate_mbps,
                    "width": f.width,
                    "height": f.height,
                    "codec": f.codec,
                    "thumb": f.thumb,
                }
                for f in self.files
            ],
            "recommended_keep": self.recommended_keep,
            "potential_savings_mb": self.potential_savings_mb,
        }


_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _is_hex(value: str) -> bool:
    """Cheap check that a cached string is a parseable hash."""
    return bool(value) and all(c in _HEX_DIGITS for c in value)


def _popcount(value: int) -> int:
    """Count set bits. Uses int.bit_count on 3.10+, else a portable fallback."""
    if hasattr(value, "bit_count"):  # Python 3.10+
        return value.bit_count()
    return bin(value).count("1")


def _hamming(a: int, b: int) -> int:
    """Bit distance between two hashes held as plain ints.

    Equivalent to `imagehash.ImageHash.__sub__` but ~15x faster: that operator
    goes through numpy, which dominates the near-miss pass when there are
    hundreds of thousands of candidate comparisons.
    """
    return _popcount(a ^ b)


class _BandedHashIndex:
    """Candidate index for near-duplicate perceptual hashes (Hamming distance).

    Splits each hash into `threshold + 1` contiguous bands and indexes every
    band separately. Two hashes at distance <= threshold differ in at most
    `threshold` bits, so those bits can touch at most `threshold` bands --
    leaving at least one band identical. Looking a hash up in all of its own
    bands therefore returns every true match (pigeonhole principle), with no
    false negatives, while comparing only a small candidate set.

    This replaces bucketing by a fixed hash *prefix*, which missed any pair
    whose differing bits happened to fall inside that prefix.
    """

    __slots__ = ("_bands", "_bits", "_n_bands", "_exhaustive", "_all")

    # Never go below this many bands: wider bands are more selective, so small
    # thresholds still get few false candidates.
    MIN_BANDS = 8

    def __init__(self, bits: int, threshold: int):
        self._bits = bits
        # threshold + 1 bands is the minimum that guarantees one intact band.
        self._n_bands = max(self.MIN_BANDS, threshold + 1)
        # Degenerate case: more bands than bits leaves nothing to index on.
        self._exhaustive = self._n_bands > bits
        self._bands: List[Dict[int, List[int]]] = [
            defaultdict(list) for _ in range(self._n_bands)
        ]
        self._all: List[int] = []

    def _band_values(self, value: int):
        """Yield (band_number, band_value) for each band of a hash integer."""
        for k in range(self._n_bands):
            start = k * self._bits // self._n_bands
            end = (k + 1) * self._bits // self._n_bands
            yield k, (value >> start) & ((1 << (end - start)) - 1)

    def add(self, idx: int, value: int) -> None:
        self._all.append(idx)
        if self._exhaustive:
            return
        for k, band_value in self._band_values(value):
            self._bands[k][band_value].append(idx)

    def candidates(self, value: int) -> Set[int]:
        """Indices that may be within the threshold. A superset, never a subset."""
        if self._exhaustive:
            return set(self._all)

        found: Set[int] = set()
        for k, band_value in self._band_values(value):
            found.update(self._bands[k].get(band_value, ()))
        return found


class _StatValidatedHashCache:
    """Disk-backed `path -> hash` cache that notices when a file changes.

    Each entry carries the mtime and size the hash was computed from, so a file
    replaced in place (re-export, rotation, rsync over the same path) is
    re-hashed instead of silently keeping a hash that no longer describes it.

    The stored value is opaque to this class — the image pass keeps a single
    phash there, the video pass keeps a joined multi-frame signature.
    """

    # Bumped whenever the on-disk layout changes.
    VERSION = 2

    def __init__(self, filename: str, label: str):
        self._filename = filename
        self._label = label
        self._entries: Dict[str, Tuple[str, int, int]] = {}
        self.dirty = False
        self.path: Optional[str] = None  # Resolved lazily on first load

    def __len__(self) -> int:
        return len(self._entries)

    def load(self) -> None:
        """Load from disk on first use; a no-op once `path` is set."""
        if self.path is not None:
            return

        import json

        from ..config import config

        self.path = os.path.join(config.hidden_data_dir, self._filename)
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r') as f:
                    raw = json.load(f)
                self._entries, purged, migrated = self.decode(raw)
                if purged or migrated:
                    self.dirty = True
                notes = []
                if purged:
                    notes.append(f"purged {purged} orphans")
                if migrated:
                    notes.append(f"migrated {migrated} legacy entries")
                print(f"📦 Loaded {len(self._entries)} cached {self._label}" +
                      (f" ({', '.join(notes)})" if notes else ""))
        except Exception as e:
            print(f"⚠️ Could not load {self._label} cache: {e}")
            self._entries = {}

    @staticmethod
    def decode(raw) -> Tuple[Dict[str, Tuple[str, int, int]], int, int]:
        """Parse an on-disk payload into the in-memory form.

        Returns (entries, purged_count, migrated_count). Entries whose file no
        longer exists are dropped here so the cache does not grow forever.

        Version 1 stored a bare `{path: hash}` map with no way to tell whether
        the file had changed since, so an edited-in-place image kept serving the
        old hash — and a wrong hash means a wrong duplicate group, which the UI
        offers to delete. Those legacy entries are stamped with the file's
        *current* mtime/size on first load rather than thrown away: re-hashing a
        six-figure library on upgrade would cost hours, and from that point on
        every further change is caught.
        """
        entries: Dict[str, Tuple[str, int, int]] = {}
        purged = 0
        migrated = 0

        if isinstance(raw, dict) and "entries" in raw:
            items = raw.get("entries") or {}
        else:
            items = raw or {}  # Legacy v1: flat {path: hash}

        for path, value in items.items():
            try:
                st = os.stat(path)
            except OSError:
                purged += 1
                continue

            if isinstance(value, str):
                entries[path] = (value, st.st_mtime_ns, st.st_size)
                migrated += 1
            elif isinstance(value, (list, tuple)) and len(value) == 3:
                entries[path] = (str(value[0]), int(value[1]), int(value[2]))
            else:
                purged += 1

        return entries, purged, migrated

    def save(self) -> None:
        """Persist to disk, unless nothing changed."""
        if not self.dirty or not self.path:
            return

        import json
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            payload = {
                "version": self.VERSION,
                "entries": {p: list(v) for p, v in self._entries.items()},
            }
            # Write-then-rename: a crash mid-write would otherwise leave a
            # truncated JSON file that the next run silently discards whole.
            tmp_path = f"{self.path}.tmp"
            with open(tmp_path, 'w') as f:
                json.dump(payload, f)
            os.replace(tmp_path, self.path)
            print(f"💾 Saved {len(self._entries)} {self._label} to cache")
            self.dirty = False
        except Exception as e:
            print(f"⚠️ Could not save {self._label} cache: {e}")

    def get(self, filepath: str, st: Optional[os.stat_result] = None) -> Optional[str]:
        """Cached hash for a file, or None if absent or stale.

        `st` is the caller's already-taken stat of the file; the hash is only
        reused when mtime and size still match what was hashed.
        """
        entry = self._entries.get(filepath)
        if entry is None:
            return None

        hash_str, mtime_ns, size = entry
        if st is None:
            try:
                st = os.stat(filepath)
            except OSError:
                return None

        if st.st_mtime_ns != mtime_ns or st.st_size != size:
            return None
        return hash_str

    def set(self, filepath: str, hash_str: str, st: Optional[os.stat_result] = None) -> None:
        """Store a hash together with the file identity it was computed from."""
        if st is None:
            try:
                st = os.stat(filepath)
            except OSError:
                return
        self._entries[filepath] = (hash_str, st.st_mtime_ns, st.st_size)
        self.dirty = True


class _UnionFind:
    """Disjoint-set over integer indices, for order-independent clustering."""

    __slots__ = ("_parent",)

    def __init__(self, n: int):
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:  # Path compression
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[max(ra, rb)] = min(ra, rb)

    def clusters(self) -> List[List[int]]:
        """Members grouped by root, each cluster and the whole list sorted."""
        buckets: Dict[int, List[int]] = defaultdict(list)
        for i in range(len(self._parent)):
            buckets[self.find(i)].append(i)
        return [sorted(members) for _, members in sorted(buckets.items())]


class DuplicateDetector:
    """
    Detects duplicate media files using various strategies.

    Videos: Exact match on size + duration + resolution, plus a second pass that
            catches re-encodes (same content, different size/codec/resolution)
    Images: Perceptual hash (if imagehash available) or exact size + resolution

    Performance:
    - Perceptual hashes are cached to disk across scans
    - Hash bucketing eliminates O(n²) comparisons
    """

    # Frame positions sampled for the re-encode pass, as fractions of duration.
    # Spread out on purpose: a single early frame is often a black frame or a
    # studio logo, which matches across completely unrelated videos.
    REENCODE_FRAME_POSITIONS = (0.25, 0.5, 0.75)
    # How far two durations may drift and still be considered the same content.
    # Re-encodes land within a frame or two; container padding adds a bit more.
    REENCODE_DURATION_TOLERANCE_SEC = 1.5
    # Max per-frame Hamming distance. Every sampled position must be within it.
    REENCODE_FRAME_THRESHOLD = 8
    # Cache marker for a file that could not be decoded, so it is not retried
    # on every scan. Not a valid hex hash, so it can never match a real one.
    UNHASHABLE = "!"

    def __init__(self):
        self._group_counter = 0
        self._image_hashes = _StatValidatedHashCache(".phash_cache.json", "image hashes")
        self._video_hashes = _StatValidatedHashCache(
            ".vframe_cache.json", "video frame signatures"
        )

    @staticmethod
    def _hash_worker_count(pending: int) -> int:
        """Threads for the image hashing pool.

        Decoding is CPU-bound but runs mostly outside the GIL, so the useful
        ceiling is core count — measured throughput on a 4-core box peaks at 4
        threads and drifts back down past it. Capped at 8 so a large server does
        not spawn a pool that only adds contention and memory.
        """
        return max(1, min(pending, os.cpu_count() or 1, 8))

    @staticmethod
    def _phash_file(path: str) -> Optional[str]:
        """Perceptual hash of one image file, or None if it cannot be decoded.

        Runs on pool threads: it touches no detector state, so the only shared
        thing is the file system.
        """
        try:
            with Image.open(path) as pil_img:
                hash_img = (
                    pil_img.convert('RGB')
                    if pil_img.mode not in ('RGB', 'L')
                    else pil_img
                )
                return str(imagehash.phash(hash_img))
        except Exception:
            return None

    def _generate_group_id(self) -> str:
        self._group_counter += 1
        return f"dup_{self._group_counter:04d}"

    def find_all_duplicates(self, entries: List, progress_callback=None, batch_size: int = 5000, batch_offset: int = 0, detect_reencodes: bool = True) -> Tuple[List[DuplicateGroup], bool]:
        """
        Find duplicates in the media library with batching support.

        Args:
            entries: List of VideoEntry objects from the database
            progress_callback: Optional callable(str, float) to report status and progress (0-100)
            batch_size: Max number of images to *hash* per run (default 5000).
                Comparison always covers the whole library — see below.
            batch_offset: Legacy pagination cursor. Kept so existing callers and
                the frontend's "scan next batch" button keep working; it no
                longer slices the input, since batch progress is now tracked by
                what the hash cache already holds.
            detect_reencodes: Also look for re-encoded copies of the same video
                (different size/codec, same content). Costs ffmpeg frame
                extractions on first run; cached afterwards.

        Returns:
            Tuple of (List of DuplicateGroup objects, has_more: bool indicating if more batches available)

        Batching note: this used to slice the image list
        (`all_images[offset:offset + size]`) and compare only within the slice.
        Two copies of the same photo that happened to land on opposite sides of
        a boundary — entries 4999 and 5001 — were therefore never compared to
        each other, in any batch, ever. Worse, each run overwrote the group
        cache with its own slice's results, so finishing batch 2 discarded
        everything batch 1 had found.

        Now the cap applies only to how many *new* hashes are computed per run.
        Comparison always runs over every image whose hash is already known, so
        each run returns a complete, global result that grows as more of the
        library gets hashed.
        """
        # Separate by media type
        videos = [e for e in entries if getattr(e, 'media_type', 'video') == 'video']
        images = [e for e in entries if getattr(e, 'media_type', 'video') == 'image']

        if progress_callback:
            progress_callback(f"Starting duplicate scan ({len(images)} images)", 5)

        groups = []

        # Find video duplicates (always process all - usually fewer files)
        if progress_callback:
            progress_callback("Scanning video metadata...", 10)

        video_groups = self._find_video_duplicates(videos, progress_callback)
        groups.extend(video_groups)

        # Second video pass: copies that were re-encoded, so no metadata matches
        if detect_reencodes:
            already_grouped = {f.path for g in video_groups for f in g.files}
            groups.extend(
                self._find_reencoded_video_duplicates(
                    videos, already_grouped, progress_callback
                )
            )

        # Find image duplicates (hashing capped per run, comparison global)
        if progress_callback:
            progress_callback(f"Scanning image metadata ({len(images)} images)...", 80)

        image_groups, deferred = self._find_image_duplicates(
            images, progress_callback, hash_budget=batch_size
        )
        groups.extend(image_groups)
        has_more = deferred > 0

        if progress_callback:
            status = "Scan complete" + (
                f" - {deferred} images still to hash" if has_more else ""
            )
            progress_callback(status, 100)

        return groups, has_more

    def _find_video_duplicates(self, videos: List, progress_callback=None) -> List[DuplicateGroup]:
        """
        Find duplicate videos using exact match strategy.
        Groups by: size + duration + resolution, then verified by content sampling.
        """
        # Build signature -> files mapping
        signature_map: Dict[str, List] = defaultdict(list)

        for video in videos:
            # Create signature from key metadata
            size_mb = round(getattr(video, 'size_mb', 0), 1)
            duration = round(getattr(video, 'duration_sec', 0), 0)
            width = getattr(video, 'width', 0)
            height = getattr(video, 'height', 0)

            # Skip if missing key metadata
            if size_mb <= 0 or duration <= 0:
                continue

            signature = f"v:{size_mb}:{duration}:{width}x{height}"
            signature_map[signature].append(video)

        # Convert to DuplicateGroups with content verification
        groups = []
        total_signatures = len(signature_map)
        processed_signatures = 0

        for signature, files in signature_map.items():
            processed_signatures += 1
            if len(files) > 1:
                # Update progress if callback provided
                if progress_callback:
                    # Map progress to 10-80% range
                    pct = 10 + (processed_signatures / total_signatures) * 70
                    progress_callback(f"Verifying group {processed_signatures}/{total_signatures}", pct)

                # Verify with content sampling to avoid false positives
                verified_groups = self._verify_by_content_sample(files)
                for verified_files in verified_groups:
                    if len(verified_files) > 1:
                        group = self._create_video_group(verified_files)
                        groups.append(group)

        return groups

    def _get_content_sample_hash(self, file_path: str, sample_size: int = 512 * 1024) -> str:
        """
        Get a hash of content samples from a file.
        Samples first and last N bytes for quick verification.
        """
        try:
            if not os.path.exists(file_path):
                return ""

            file_size = os.path.getsize(file_path)
            hasher = hashlib.md5()

            with open(file_path, 'rb') as f:
                # Read first chunk
                first_chunk = f.read(sample_size)
                hasher.update(first_chunk)

                # Read last chunk if file is large enough
                if file_size > sample_size * 2:
                    f.seek(-sample_size, 2)  # Seek from end
                    last_chunk = f.read(sample_size)
                    hasher.update(last_chunk)

            return hasher.hexdigest()
        except Exception:
            return ""

    def _verify_by_content_sample(self, files: List) -> List[List]:
        """
        Verify potential duplicates by comparing content samples.
        Returns groups of files whose sampled bytes match.

        Files that fail this check are simply not grouped here. They are not
        lost: `_find_reencoded_video_duplicates` picks up everything the exact
        pass left ungrouped and compares it by picture instead of by bytes.
        That subsumes the single-frame fallback this method used to run inline
        (`_verify_by_visual_hash`), which only ever saw files that already had
        matching size, duration and resolution, sampled one frame instead of
        three, and cached nothing between scans.
        """
        hash_map: Dict[str, List] = defaultdict(list)

        for f in files:
            content_hash = self._get_content_sample_hash(f.file_path)
            if content_hash:
                hash_map[content_hash].append(f)

        return [group for group in hash_map.values() if len(group) > 1]

    def _get_video_frame_hash(self, video_path: str, position_sec: float = 2.0) -> Optional[str]:
        """
        Extract a frame from video and compute its perceptual hash.
        Uses ffmpeg to extract frame, then imagehash for comparison.
        """
        import subprocess
        import tempfile

        if not IMAGEHASH_AVAILABLE:
            return None

        temp_path = None
        try:
            # Create temp file for extracted frame
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                temp_path = tmp.name

            # Use ffmpeg to extract a frame
            cmd = [
                'ffmpeg', '-y', '-ss', str(position_sec),
                '-i', video_path,
                '-frames:v', '1',
                '-q:v', '2',
                temp_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0 or not os.path.exists(temp_path):
                return None

            # Compute perceptual hash
            with Image.open(temp_path) as img:
                phash = imagehash.phash(img)
                hash_str = str(phash)

            return hash_str

        except Exception:
            return None
        finally:
            # Always clean up: on an ffmpeg failure or timeout the old code left
            # the (empty) temp file behind, filling /tmp over a long scan.
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # -- Re-encode detection --------------------------------------------------
    #
    # The exact pass above buckets videos by rounded size + duration +
    # resolution. A re-encoded copy (H.264 -> HEVC, 1080p -> 720p, different
    # CRF) shares none of those, so it never reaches the same bucket.
    # Re-encodes, the single most common kind of real duplicate in a transcoded
    # library, were therefore invisible.
    #
    # What does survive re-encoding is the picture itself and, to within about
    # a frame, the duration. So: bucket by duration, then compare perceptual
    # hashes of frames sampled at the same *relative* positions.

    def _video_frame_signature(self, video) -> Optional[str]:
        """Perceptual hashes of several frames of one video, ':'-joined.

        Cached on disk keyed by path + mtime + size, because each miss costs one
        ffmpeg invocation per sampled position.
        """
        path = getattr(video, 'file_path', '')
        try:
            st = os.stat(path)
        except OSError:
            return None

        cached = self._video_hashes.get(path, st)
        if cached:
            return cached

        duration = getattr(video, 'duration_sec', 0) or 0
        if duration <= 0:
            return None

        hashes = []
        for fraction in self.REENCODE_FRAME_POSITIONS:
            hash_str = self._get_video_frame_hash(path, duration * fraction)
            if not hash_str:
                return None  # A partial signature would compare unequal lengths
            hashes.append(hash_str)

        signature = ":".join(hashes)
        self._video_hashes.set(path, signature, st)
        return signature

    @staticmethod
    def _signatures_match(sig_a: str, sig_b: str, threshold: int) -> bool:
        """True when *every* sampled frame is within the Hamming threshold.

        Requiring all positions rather than a majority is what keeps episodes of
        the same series apart: they share an intro, not a whole runtime.
        """
        frames_a = sig_a.split(":")
        frames_b = sig_b.split(":")
        if len(frames_a) != len(frames_b):
            return False
        try:
            return all(
                _hamming(int(a, 16), int(b, 16)) <= threshold
                for a, b in zip(frames_a, frames_b)
            )
        except ValueError:
            return False

    def _duration_candidate_pairs(self, videos: List) -> List[Tuple[int, int]]:
        """Index pairs whose durations are close enough to be the same content.

        Sweeps the duration-sorted list, so this is O(n log n) plus the pairs
        actually emitted -- not an all-pairs comparison.
        """
        order = sorted(
            range(len(videos)),
            key=lambda i: (getattr(videos[i], 'duration_sec', 0) or 0, videos[i].file_path),
        )
        tolerance = self.REENCODE_DURATION_TOLERANCE_SEC

        pairs = []
        for a in range(len(order)):
            dur_a = getattr(videos[order[a]], 'duration_sec', 0) or 0
            if dur_a <= 0:
                continue
            for b in range(a + 1, len(order)):
                dur_b = getattr(videos[order[b]], 'duration_sec', 0) or 0
                if dur_b - dur_a > tolerance:
                    break  # Sorted: everything further out is further away
                pairs.append((order[a], order[b]))
        return pairs

    def _find_reencoded_video_duplicates(
        self, videos: List, skip_paths: Set[str], progress_callback=None
    ) -> List[DuplicateGroup]:
        """Group videos that hold the same content at different encodings."""
        if not IMAGEHASH_AVAILABLE:
            return []

        candidates = [
            v for v in videos
            if v.file_path not in skip_paths and (getattr(v, 'duration_sec', 0) or 0) > 0
        ]
        if len(candidates) < 2:
            return []

        pairs = self._duration_candidate_pairs(candidates)
        if not pairs:
            return []

        # Only videos that actually have a duration neighbour get hashed; a file
        # with a unique runtime can have no re-encode twin, so paying for three
        # ffmpeg seeks on it would be pure waste.
        needed = sorted({i for pair in pairs for i in pair})
        self._video_hashes.load()

        signatures: Dict[int, str] = {}
        for done, idx in enumerate(needed):
            if progress_callback and done % 25 == 0:
                pct = 55 + (done / len(needed)) * 20  # 55-75% range
                progress_callback(
                    f"Checking video {done}/{len(needed)} for re-encoded copies", pct
                )
            signature = self._video_frame_signature(candidates[idx])
            if signature:
                signatures[idx] = signature
        self._video_hashes.save()

        # Union-Find: whether A and B end up together must not depend on the
        # order the pairs happen to be visited in.
        uf = _UnionFind(len(candidates))
        for i, j in pairs:
            sig_i, sig_j = signatures.get(i), signatures.get(j)
            if sig_i and sig_j and self._signatures_match(
                sig_i, sig_j, self.REENCODE_FRAME_THRESHOLD
            ):
                uf.union(i, j)

        groups = []
        for members in uf.clusters():
            if len(members) > 1:
                groups.append(
                    self._create_video_group(
                        [candidates[i] for i in members],
                        match_type="reencode",
                        confidence=0.75,
                    )
                )
        return groups

    def _create_video_group(
        self, videos: List, match_type: str = "exact", confidence: float = 0.95
    ) -> DuplicateGroup:
        """Create a DuplicateGroup from a list of matching videos."""
        dup_files = []

        # Within a re-encode group the codec says nothing about which copy is
        # the source — the HEVC file is usually the *lossy* derivative of the
        # H.264 original, so its +20 codec bonus would recommend keeping exactly
        # the copy the user wants to drop. Resolution and bitrate still do carry
        # that signal, so only the codec term is dropped.
        codec_bonus = match_type != "reencode"

        for v in videos:
            quality_score = self._calculate_video_quality_score(v, codec_bonus=codec_bonus)
            dup_file = DuplicateFile(
                path=v.file_path,
                size_mb=v.size_mb,
                media_type="video",
                quality_score=quality_score,
                duration_sec=getattr(v, 'duration_sec', 0),
                bitrate_mbps=getattr(v, 'bitrate_mbps', 0),
                width=getattr(v, 'width', 0),
                height=getattr(v, 'height', 0),
                codec=getattr(v, 'codec', ''),
                thumb=getattr(v, 'thumb', ''),
            )
            dup_files.append(dup_file)

        # Sort by quality (best first)
        dup_files.sort(key=lambda f: f.quality_score, reverse=True)

        # Calculate savings (sum of all but the best)
        total_size = sum(f.size_mb for f in dup_files)
        keep_size = dup_files[0].size_mb if dup_files else 0
        savings = total_size - keep_size

        return DuplicateGroup(
            group_id=self._generate_group_id(),
            match_type=match_type,
            media_type="video",
            confidence=confidence,
            files=dup_files,
            recommended_keep=dup_files[0].path if dup_files else "",
            potential_savings_mb=round(savings, 2),
        )

    def _calculate_video_quality_score(self, video, codec_bonus: bool = True) -> float:
        """
        Calculate a quality score for a video.
        Higher score = better quality = should keep.

        `codec_bonus` rewards modern codecs — right when picking between
        byte-identical copies, wrong when picking between re-encodes, where the
        efficient codec marks the lossy derivative rather than the source.
        """
        score = 0.0

        # Bitrate contribution (0-50 points)
        bitrate = getattr(video, 'bitrate_mbps', 0)
        score += min(bitrate * 2, 50)

        # Resolution contribution (0-30 points)
        width = getattr(video, 'width', 0)
        height = getattr(video, 'height', 0)
        pixels = width * height
        if pixels >= 3840 * 2160:  # 4K
            score += 30
        elif pixels >= 1920 * 1080:  # 1080p
            score += 25
        elif pixels >= 1280 * 720:  # 720p
            score += 15
        else:
            score += 5

        # Codec contribution (0-20 points)
        codec = getattr(video, 'codec', '').lower() if codec_bonus else ''
        if 'hevc' in codec or 'h265' in codec or 'x265' in codec:
            score += 20  # Modern efficient codec
        elif 'h264' in codec or 'avc' in codec or 'x264' in codec:
            score += 15
        else:
            score += 5

        return round(score, 2)

    def _find_image_duplicates(
        self, images: List, progress_callback=None, hash_budget: Optional[int] = None
    ) -> Tuple[List[DuplicateGroup], int]:
        """
        Find duplicate images.
        Uses perceptual hash if available, otherwise falls back to exact match.

        Returns (groups, deferred) where `deferred` counts images left unhashed
        because the budget ran out. The exact-match fallback needs no hashing,
        so it always defers nothing.
        """
        if IMAGEHASH_AVAILABLE:
            return self._find_image_duplicates_by_hash(
                images, progress_callback=progress_callback, hash_budget=hash_budget
            )
        return self._find_image_duplicates_by_exact(images), 0

    def _find_image_duplicates_by_exact(self, images: List) -> List[DuplicateGroup]:
        """Find duplicate images by size + resolution, dann inhaltlich geprüft.

        Die Signatur allein reicht nicht. `round(size_mb, 2)` fasst alles
        zusammen, was innerhalb von rund 10 KB gleich groß ist — zwei
        verschiedene Aufnahmen derselben Kamera mit derselben Auflösung landen
        mühelos im selben Fach. Die Gruppe hiess trotzdem ``"exact"`` und kam
        mit Konfidenz 0,95 in eine Oberfläche, die das Löschen anbietet.

        Der Video-Zweig hat diese Lehre längst gezogen — er filtert mit der
        Signatur nur vor und prüft danach die Bytes („Verify with content
        sampling to avoid false positives", Zeile 515). Hier fehlte derselbe
        Schritt, obwohl `_verify_by_content_sample()` medienneutral ist: Bei
        Bildern unter 1 MB liest sie die Datei ganz, der Vergleich ist dann
        exakt.

        Dieser Zweig läuft nur, wenn `imagehash` nicht verfügbar ist — also
        selten, aber ausgerechnet dann, wenn schon etwas nicht stimmt.
        """
        signature_map: Dict[str, List] = defaultdict(list)

        for img in images:
            size_mb = round(getattr(img, 'size_mb', 0), 2)
            width = getattr(img, 'width', 0)
            height = getattr(img, 'height', 0)

            if size_mb <= 0:
                continue

            signature = f"i:{size_mb}:{width}x{height}"
            signature_map[signature].append(img)

        groups = []
        for signature, files in signature_map.items():
            if len(files) > 1:
                for verified_files in self._verify_by_content_sample(files):
                    if len(verified_files) > 1:
                        groups.append(
                            self._create_image_group(verified_files, match_type="exact")
                        )

        return groups

    def _find_image_duplicates_by_hash(
        self,
        images: List,
        threshold: int = 5,
        progress_callback=None,
        hash_budget: Optional[int] = None,
    ) -> Tuple[List[DuplicateGroup], int]:
        """
        Find duplicate images using perceptual hash.
        Images with hash difference <= threshold are considered duplicates.

        `hash_budget` caps how many *new* hashes this run computes; images past
        it keep their place in the library and are simply not compared yet.
        Comparison itself always covers every image with a known hash, so a
        budget bounds one run's cost without ever splitting the search space.

        Returns (groups, deferred_count).

        Performance optimizations:
        - Hash caching: reuses previously computed hashes from disk
        - Hash bucketing: groups by exact hash first (O(n)), then near-miss via
          a banded candidate index
        """
        import gc

        # Load hash cache from disk
        self._image_hashes.load()

        # Phase 1a: resolve every image against the cache. Cheap and sequential
        # — one stat and one dict lookup each — and it decides which files
        # actually have to be decoded.
        hashes_by_path: Dict[str, str] = {}
        pending: List[Tuple[Any, os.stat_result]] = []
        total_images = len(images)
        cache_hits = 0
        deferred = 0
        budget = total_images if hash_budget is None else max(hash_budget, 0)

        for img in images:
            path = img.file_path
            # One stat serves both the existence check and cache validation.
            try:
                st = os.stat(path)
            except OSError:
                continue

            cached_hash_str = self._image_hashes.get(path, st)
            if cached_hash_str == self.UNHASHABLE:
                # Known-undecodable, and unchanged since we found that out.
                # Without this the same broken files would be retried on every
                # run, burning the budget and leaving `deferred` permanently
                # above zero — an endless "more batches available".
                continue
            # A corrupt entry is treated as a miss and recomputed. Validating
            # the hex here rather than parsing it keeps cache hits cheap; the
            # comparison phases read `int(hash_str, 16)`, so garbage would raise
            # there instead of quietly costing one image its match.
            if cached_hash_str and _is_hex(cached_hash_str):
                hashes_by_path[path] = cached_hash_str
                cache_hits += 1
                continue

            if budget <= 0:
                deferred += 1
                continue
            budget -= 1
            pending.append((img, st))

        # Phase 1b: decode and hash the misses across a thread pool. Decoding is
        # the whole cost here, and PIL and numpy both drop the GIL while they
        # work, so this scales with cores: measured 3.1x on 4 cores at 1600x1200
        # (5.9s -> 1.9s for 300 images), with byte-identical hashes.
        cache_misses = 0
        if pending:
            workers = self._hash_worker_count(len(pending))
            # Chunked so progress keeps moving and the periodic GC that large
            # libraries rely on still happens between chunks rather than never.
            chunk_size = max(workers * 8, 100)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for start in range(0, len(pending), chunk_size):
                    chunk = pending[start:start + chunk_size]
                    if progress_callback:
                        pct = 80 + (start / len(pending)) * 10  # 80-90% range
                        progress_callback(
                            f"Hashing image {start}/{len(pending)} "
                            f"({cache_hits} from cache, {workers} threads)",
                            pct,
                        )

                    for (img, st), hash_str in zip(
                        chunk, pool.map(self._phash_file, (i.file_path for i, _ in chunk))
                    ):
                        if hash_str:
                            hashes_by_path[img.file_path] = hash_str
                            self._image_hashes.set(img.file_path, hash_str, st)
                            cache_misses += 1
                        else:
                            self._image_hashes.set(img.file_path, self.UNHASHABLE, st)

                    gc.collect()

        # Phase 1c: assemble in input order, so the result never depends on how
        # the pool happened to interleave.
        #
        # Only the hex string is carried. The old code also built an
        # `imagehash.ImageHash` per image here and threaded it through both
        # grouping phases, where nothing ever read it -- comparison runs on
        # `int(hash_str, 16)`. Each of those cost a numpy array construction.
        hash_data: List[Tuple[str, Any]] = [
            (hashes_by_path[img.file_path], img)
            for img in images
            if img.file_path in hashes_by_path
        ]

        # Save updated cache to disk
        self._image_hashes.save()

        if progress_callback:
            progress_callback(
                f"Hashed {len(hash_data)} images ({cache_hits} cached, {cache_misses} new"
                + (f", {deferred} deferred" if deferred else "") + ")",
                92,
            )

        # Phase 2: Group by exact hash (O(n) — covers most true duplicates)
        exact_buckets: Dict[str, List] = defaultdict(list)
        for hash_str, img in hash_data:
            exact_buckets[hash_str].append(img)

        groups = []
        used_paths = set()

        # Exact matches — identical hashes
        for hash_str, imgs in exact_buckets.items():
            if len(imgs) > 1:
                group = self._create_image_group(imgs, match_type="hash")
                groups.append(group)
                for img in imgs:
                    used_paths.add(img.file_path)

        # Phase 3: Near-miss detection via banded candidate index
        # A previous version bucketed by the first 4 hex chars and only compared
        # within a bucket, on the assumption that differing prefixes implied a
        # distance above the threshold. That is false: two hashes one bit apart
        # land in different buckets whenever that bit falls in the leading 16,
        # and were never compared. Banding indexes every part of the hash, so
        # recall no longer depends on *where* the images differ.
        remaining = [
            (h, img) for h, img in hash_data if img.file_path not in used_paths
        ] if threshold > 0 else []

        if remaining:
            if progress_callback:
                progress_callback(f"Checking {len(remaining)} images for near-matches...", 95)

            # A hex phash is 4 bits per character (16 chars = the usual 64 bits).
            index = _BandedHashIndex(bits=len(remaining[0][0]) * 4, threshold=threshold)
            values = []
            for idx, (hash_str, img) in enumerate(remaining):
                value = int(hash_str, 16)
                values.append(value)
                index.add(idx, value)

            # Union-Find rather than the greedy "claim and move on" pass this
            # replaces. Greedy consumed a match into the first group that
            # reached it, so a third image near *that* one but not near the
            # group's anchor was left ungrouped and reported as unique: with
            # A~B and A~C but B!~C, whichever of B/C lost the race simply
            # vanished from the results. Which one lost depended on iteration
            # order, so the same library could yield different answers.
            #
            # The trade-off is that near-duplicates now chain transitively (A~B,
            # B~C puts A and C in one group even if A!~C). At threshold 5 over
            # 64 bits that needs a genuine gradient of near-identical images,
            # and grouping those together is the answer a user expects anyway —
            # unlike silently dropping one.
            uf = _UnionFind(len(remaining))
            for i in range(len(remaining)):
                # Sorted for deterministic grouping across runs.
                for j in sorted(index.candidates(values[i])):
                    if j <= i:
                        continue  # Each pair once; union is symmetric
                    # Banding only narrows the field; the real distance decides.
                    if _hamming(values[i], values[j]) <= threshold:
                        uf.union(i, j)

            for members in uf.clusters():
                if len(members) > 1:
                    group = self._create_image_group(
                        [remaining[i][1] for i in members], match_type="hash"
                    )
                    groups.append(group)

        return groups, deferred

    def _create_image_group(self, images: List, match_type: str) -> DuplicateGroup:
        """Create a DuplicateGroup from a list of matching images."""
        dup_files = []

        for img in images:
            quality_score = self._calculate_image_quality_score(img)
            dup_file = DuplicateFile(
                path=img.file_path,
                size_mb=img.size_mb,
                media_type="image",
                quality_score=quality_score,
                width=getattr(img, 'width', 0),
                height=getattr(img, 'height', 0),
                thumb=getattr(img, 'thumb', ''),
            )
            dup_files.append(dup_file)

        # Sort by quality (best first)
        dup_files.sort(key=lambda f: f.quality_score, reverse=True)

        # Calculate savings
        total_size = sum(f.size_mb for f in dup_files)
        keep_size = dup_files[0].size_mb if dup_files else 0
        savings = total_size - keep_size

        confidence = 0.95 if match_type == "exact" else 0.85

        return DuplicateGroup(
            group_id=self._generate_group_id(),
            match_type=match_type,
            media_type="image",
            confidence=confidence,
            files=dup_files,
            recommended_keep=dup_files[0].path if dup_files else "",
            potential_savings_mb=round(savings, 2),
        )

    def _calculate_image_quality_score(self, image) -> float:
        """Calculate quality score for an image. Higher = keep."""
        score = 0.0

        # Resolution (0-50 points)
        width = getattr(image, 'width', 0)
        height = getattr(image, 'height', 0)
        megapixels = (width * height) / 1_000_000
        score += min(megapixels * 5, 50)

        # File size as proxy for quality (0-50 points)
        size_mb = getattr(image, 'size_mb', 0)
        score += min(size_mb * 10, 50)

        return round(score, 2)


# Singleton instance
duplicate_detector = DuplicateDetector()
