"""
Duplicate Media Detection Module.
Finds duplicate videos and images in the media library.
"""
import os
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

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


class DuplicateDetector:
    """
    Detects duplicate media files using various strategies.
    
    Videos: Exact match on size + duration + resolution
    Images: Perceptual hash (if imagehash available) or exact size + resolution
    
    Performance:
    - Perceptual hashes are cached to disk across scans
    - Hash bucketing eliminates O(n²) comparisons 
    """
    
    def __init__(self):
        self._group_counter = 0
        self._hash_cache: Dict[str, str] = {}  # filepath -> phash hex string
        self._hash_cache_dirty = False
        self._hash_cache_file = None  # Set lazily

    def _ensure_hash_cache(self):
        """Load hash cache from disk on first use."""
        if self._hash_cache_file is not None:
            return  # Already loaded
        
        from ..config import config
        import json
        
        self._hash_cache_file = os.path.join(config.hidden_data_dir, ".phash_cache.json")
        try:
            if os.path.exists(self._hash_cache_file):
                with open(self._hash_cache_file, 'r') as f:
                    raw = json.load(f)
                    # Validate: only keep entries where file still exists
                    self._hash_cache = {k: v for k, v in raw.items() if os.path.exists(k)}
                    purged = len(raw) - len(self._hash_cache)
                    if purged > 0:
                        self._hash_cache_dirty = True
                    print(f"📦 Loaded {len(self._hash_cache)} cached image hashes" + 
                          (f" (purged {purged} orphans)" if purged else ""))
        except Exception as e:
            print(f"⚠️ Could not load hash cache: {e}")
            self._hash_cache = {}

    def _save_hash_cache(self):
        """Persist hash cache to disk."""
        if not self._hash_cache_dirty or not self._hash_cache_file:
            return
        
        import json
        try:
            os.makedirs(os.path.dirname(self._hash_cache_file), exist_ok=True)
            with open(self._hash_cache_file, 'w') as f:
                json.dump(self._hash_cache, f)
            print(f"💾 Saved {len(self._hash_cache)} image hashes to cache")
            self._hash_cache_dirty = False
        except Exception as e:
            print(f"⚠️ Could not save hash cache: {e}")

    def _get_cached_hash(self, filepath: str) -> Optional[str]:
        """Get a cached phash for a file, or None if not cached."""
        return self._hash_cache.get(filepath)

    def _set_cached_hash(self, filepath: str, hash_str: str):
        """Store a phash in the cache."""
        self._hash_cache[filepath] = hash_str
        self._hash_cache_dirty = True
    
    def _generate_group_id(self) -> str:
        self._group_counter += 1
        return f"dup_{self._group_counter:04d}"
    
    def find_all_duplicates(self, entries: List, progress_callback=None, batch_size: int = 5000, batch_offset: int = 0) -> Tuple[List[DuplicateGroup], bool]:
        """
        Find duplicates in the media library with batching support.
        
        Args:
            entries: List of VideoEntry objects from the database
            progress_callback: Optional callable(str, float) to report status and progress (0-100)
            batch_size: Max number of images to process per batch (default 5000)
            batch_offset: Starting offset for image processing (for pagination)
            
        Returns:
            Tuple of (List of DuplicateGroup objects, has_more: bool indicating if more batches available)
        """
        # Separate by media type
        videos = [e for e in entries if getattr(e, 'media_type', 'video') == 'video']
        all_images = [e for e in entries if getattr(e, 'media_type', 'video') == 'image']
        
        # Apply batching to images (videos are usually fewer and faster to process)
        total_images = len(all_images)
        images = all_images[batch_offset:batch_offset + batch_size]
        has_more = (batch_offset + batch_size) < total_images
        
        if progress_callback:
            batch_info = f" (batch {batch_offset//batch_size + 1}, images {batch_offset+1}-{min(batch_offset+batch_size, total_images)} of {total_images})"
            progress_callback(f"Starting duplicate scan{batch_info}", 5)
        
        groups = []
        
        # Find video duplicates (always process all - usually fewer files)
        if progress_callback:
            progress_callback("Scanning video metadata...", 10)
            
        video_groups = self._find_video_duplicates(videos, progress_callback)
        groups.extend(video_groups)
        
        # Find image duplicates (batched)
        if progress_callback:
            progress_callback(f"Scanning image metadata ({len(images)} images)...", 80)
            
        image_groups = self._find_image_duplicates(images, progress_callback)
        groups.extend(image_groups)
        
        if progress_callback:
            status = "Scan complete" + (" - more batches available" if has_more else "")
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
        Falls back to visual hash for re-encoded videos.
        Returns groups of files that have matching content.
        """
        # Calculate content hashes
        hash_map: Dict[str, List] = defaultdict(list)
        unmatched = []
        
        for f in files:
            path = f.file_path
            content_hash = self._get_content_sample_hash(path)
            if content_hash:
                hash_map[content_hash].append(f)
        
        # Collect exact match groups
        result_groups = [group for group in hash_map.values() if len(group) > 1]
        
        # Collect files that didn't match by content hash
        for group in hash_map.values():
            if len(group) == 1:
                unmatched.append(group[0])
        
        # If we have unmatched files and imagehash is available, try visual matching
        if len(unmatched) >= 2 and IMAGEHASH_AVAILABLE:
            visual_groups = self._verify_by_visual_hash(unmatched)
            result_groups.extend(visual_groups)
        
        return result_groups
    
    def _get_video_frame_hash(self, video_path: str, position_sec: float = 2.0) -> Optional[str]:
        """
        Extract a frame from video and compute its perceptual hash.
        Uses ffmpeg to extract frame, then imagehash for comparison.
        """
        import subprocess
        import tempfile
        
        if not IMAGEHASH_AVAILABLE:
            return None
        
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
            
            # Cleanup
            try:
                os.remove(temp_path)
            except:
                pass
            
            return hash_str
            
        except Exception:
            return None
    
    def _verify_by_visual_hash(self, files: List, threshold: int = 8) -> List[List]:
        """
        Group files by visual similarity using frame extraction + perceptual hash.
        Threshold: max hash difference to consider as duplicate (0=exact, higher=more lenient)
        """
        # Get visual hashes for all files
        hash_data: List[Tuple[any, any]] = []  # (file, phash_obj)
        
        for f in files:
            path = f.file_path
            duration = getattr(f, 'duration_sec', 0) if hasattr(f, 'duration_sec') else 0
            
            # Sample frame from middle of video (or 2s in if short)
            sample_pos = min(duration / 2, 2.0) if duration > 0 else 2.0
            
            hash_str = self._get_video_frame_hash(path, sample_pos)
            if hash_str:
                try:
                    phash_obj = imagehash.hex_to_hash(hash_str)
                    hash_data.append((f, phash_obj))
                except:
                    pass
        
        # Group by similar hashes
        used = set()
        groups = []
        
        for i, (file_a, hash_a) in enumerate(hash_data):
            if i in used:
                continue
            
            similar = [file_a]
            used.add(i)
            
            for j, (file_b, hash_b) in enumerate(hash_data):
                if j in used:
                    continue
                
                # Compare hashes
                diff = hash_a - hash_b
                if diff <= threshold:
                    similar.append(file_b)
                    used.add(j)
            
            if len(similar) > 1:
                groups.append(similar)
        
        return groups
    
    def _create_video_group(self, videos: List) -> DuplicateGroup:
        """Create a DuplicateGroup from a list of matching videos."""
        dup_files = []
        
        for v in videos:
            quality_score = self._calculate_video_quality_score(v)
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
            match_type="exact",
            media_type="video",
            confidence=0.95,
            files=dup_files,
            recommended_keep=dup_files[0].path if dup_files else "",
            potential_savings_mb=round(savings, 2),
        )
    
    def _calculate_video_quality_score(self, video) -> float:
        """
        Calculate a quality score for a video.
        Higher score = better quality = should keep.
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
        codec = getattr(video, 'codec', '').lower()
        if 'hevc' in codec or 'h265' in codec or 'x265' in codec:
            score += 20  # Modern efficient codec
        elif 'h264' in codec or 'avc' in codec or 'x264' in codec:
            score += 15
        else:
            score += 5
        
        return round(score, 2)
    
    def _find_image_duplicates(self, images: List, progress_callback=None) -> List[DuplicateGroup]:
        """
        Find duplicate images.
        Uses perceptual hash if available, otherwise falls back to exact match.
        """
        if IMAGEHASH_AVAILABLE:
            return self._find_image_duplicates_by_hash(images, progress_callback=progress_callback)
        else:
            return self._find_image_duplicates_by_exact(images)
    
    def _find_image_duplicates_by_exact(self, images: List) -> List[DuplicateGroup]:
        """Find duplicate images by exact size + resolution match."""
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
                group = self._create_image_group(files, match_type="exact")
                groups.append(group)
        
        return groups
    
    def _find_image_duplicates_by_hash(self, images: List, threshold: int = 5, progress_callback=None) -> List[DuplicateGroup]:
        """
        Find duplicate images using perceptual hash.
        Images with hash difference <= threshold are considered duplicates.
        
        Performance optimizations:
        - Hash caching: reuses previously computed hashes from disk
        - Hash bucketing: groups by exact hash first (O(n)), then near-miss via prefix buckets
        """
        import gc
        
        # Load hash cache from disk
        self._ensure_hash_cache()
        
        # Phase 1: Compute/retrieve hashes with progress tracking
        hash_data: List[Tuple[str, 'imagehash.ImageHash', any]] = []
        total_images = len(images)
        cache_hits = 0
        cache_misses = 0
        
        for idx, img in enumerate(images):
            if progress_callback and idx % 200 == 0:
                pct = 80 + (idx / total_images) * 10  # 80-90% range
                progress_callback(f"Hashing image {idx}/{total_images} (cache: {cache_hits} hits)", pct)
            
            path = img.file_path
            if not os.path.exists(path):
                continue
            
            # Check cache first
            cached_hash_str = self._get_cached_hash(path)
            if cached_hash_str:
                try:
                    phash = imagehash.hex_to_hash(cached_hash_str)
                    hash_data.append((cached_hash_str, phash, img))
                    cache_hits += 1
                    continue
                except Exception:
                    pass  # Invalid cache entry, recompute
            
            # Cache miss — compute hash
            try:
                with Image.open(path) as pil_img:
                    if pil_img.mode not in ('RGB', 'L'):
                        pil_img = pil_img.convert('RGB')
                    phash = imagehash.phash(pil_img)
                    hash_str = str(phash)
                    hash_data.append((hash_str, phash, img))
                    self._set_cached_hash(path, hash_str)
                    cache_misses += 1
            except Exception:
                continue
            
            # Periodic GC for large libraries
            if cache_misses % 500 == 0 and cache_misses > 0:
                gc.collect()
        
        # Save updated cache to disk
        self._save_hash_cache()
        
        if progress_callback:
            progress_callback(f"Hashed {len(hash_data)} images ({cache_hits} cached, {cache_misses} new)", 92)
        
        # Phase 2: Group by exact hash (O(n) — covers most true duplicates)
        exact_buckets: Dict[str, List] = defaultdict(list)
        for hash_str, phash, img in hash_data:
            exact_buckets[hash_str].append((phash, img))
        
        groups = []
        used_paths = set()
        
        # Exact matches — identical hashes
        for hash_str, bucket in exact_buckets.items():
            if len(bucket) > 1:
                imgs = [img for _, img in bucket]
                group = self._create_image_group(imgs, match_type="hash")
                groups.append(group)
                for img in imgs:
                    used_paths.add(img.file_path)
        
        # Phase 3: Near-miss detection using prefix bucketing
        # Group remaining (ungrouped) images by hash prefix for candidate selection
        # A 16-char hex hash = 64 bits. 4-char prefix = 16 bits → similar images share prefixes
        if threshold > 0:
            remaining = [(h, p, img) for h, p, img in hash_data if img.file_path not in used_paths]
            
            if remaining and progress_callback:
                progress_callback(f"Checking {len(remaining)} images for near-matches...", 95)
            
            # Build prefix buckets (use multiple prefix lengths for broader coverage)
            prefix_buckets: Dict[str, List[int]] = defaultdict(list)
            for idx, (hash_str, phash, img) in enumerate(remaining):
                # Use first 4 chars as bucket key — images with different prefixes
                # have hash distance > 16 bits, so can't match at threshold ≤ 5
                prefix_buckets[hash_str[:4]].append(idx)
            
            used_remaining = set()
            for bucket_indices in prefix_buckets.values():
                if len(bucket_indices) < 2:
                    continue
                
                # Only compare within bucket (small groups)
                for i_pos, i in enumerate(bucket_indices):
                    if i in used_remaining:
                        continue
                    
                    h_i, p_i, img_i = remaining[i]
                    similar = [img_i]
                    used_remaining.add(i)
                    
                    for j in bucket_indices[i_pos + 1:]:
                        if j in used_remaining:
                            continue
                        h_j, p_j, img_j = remaining[j]
                        diff = p_i - p_j
                        if diff <= threshold:
                            similar.append(img_j)
                            used_remaining.add(j)
                    
                    if len(similar) > 1:
                        group = self._create_image_group(similar, match_type="hash")
                        groups.append(group)
        
        return groups
    
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
