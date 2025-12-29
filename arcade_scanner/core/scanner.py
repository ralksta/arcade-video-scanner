import os
from typing import List, Optional
from arcade_scanner.app_config import VIDEO_EXTENSIONS, MIN_SIZE_MB

class VideoScanner:
    def __init__(self, targets: List[str], exclude_paths: List[str]):
        """
        Initialize the scanner with target directories and exclusion paths.
        
        Args:
            targets: List of absolute or relative paths to scan.
            exclude_paths: List of absolute or relative paths to exclude.
        """
        self.targets = [os.path.abspath(os.path.expanduser(t)) for t in targets]
        self.exclude_paths = exclude_paths
        
        # Pre-calculate absolute exclusion paths for efficiency
        self.exclude_abs = [os.path.abspath(os.path.expanduser(p)) for p in exclude_paths]

    def scan(self) -> List[str]:
        """
        Perform the scan and return a list of valid video file paths.
        """
        video_files = []
        
        print(f"🔍 Scanner initialized with {len(self.targets)} targets and {len(self.exclude_paths)} exclusions.")

        for target in self.targets:
            if not os.path.exists(target):
                print(f"⚠️ Warning: Scan target not found: {target}")
                continue
                
            print(f"Scanning directory: {target}")
            
            for root, dirs, files in os.walk(target):
                # 1. Prune excluded directories
                # modify dirs in-place to skip descending into excluded folders
                dirs[:] = [
                    d for d in dirs 
                    if not d.startswith(".") 
                    and self._is_allowed_dir(root, d)
                ]
                
                # 2. Check if current root itself is excluded (substring check for some patterns)
                if self._is_excluded_root(root):
                    continue

                # 3. Scan files
                for file in files:
                    if self._is_video_file(file):
                        filepath = os.path.join(root, file)
                        if self._is_valid_size(filepath):
                            video_files.append(filepath)

        return video_files

    def _is_allowed_dir(self, parent_root: str, dirname: str) -> bool:
        """Check if a directory should be traversed."""
        full_path = os.path.abspath(os.path.join(parent_root, dirname))
        
        # Exact match
        if full_path in self.exclude_abs:
            return False
            
        # Substring match for robust exclusion (e.g., handles different mount points or partial matches if desired)
        # The original code had: any(ex in ... if "/" in ex)
        # We will replicate the logic:
        # "and not any(ex in os.path.join(root, d) for ex in exclude_abs if "/" in ex)"
        for ex in self.exclude_abs:
            if "/" in ex and ex in full_path:
                return False
                
        return True

    def _is_excluded_root(self, root: str) -> bool:
        """Check if the current root directory matches any exclusion patterns."""
        # Original logic: if any(ex in root for ex in EXCLUDE_PATHS if not ex.startswith("~")):
        # We use strict self.exclude_paths for this check to match original behavior
        for ex in self.exclude_paths:
            if not ex.startswith("~") and ex in root:
                return True
        return False

    def _is_video_file(self, filename: str) -> bool:
        """Check if file has a valid video extension."""
        return any(filename.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)

    def _is_valid_size(self, filepath: str) -> bool:
        """Check if file meets minimum size requirements."""
        # Always include optimized files regardless of size
        filename = os.path.basename(filepath)
        if "_opt." in filename:
            return True

        try:
            sz = os.path.getsize(filepath)
            return sz >= (MIN_SIZE_MB * 1024 * 1024)
        except OSError:
            return False
