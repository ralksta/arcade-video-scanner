"""
Path validation and sanitization utilities.

Provides security checks to prevent:
- Path traversal attacks
- Arbitrary file access
- Access to hidden/system files
"""

import os
from pathlib import Path
from typing import List, Optional


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


class PathValidator:
    """Validates file paths against a whitelist of allowed directories."""
    
    def __init__(self, allowed_dirs: List[str]):
        """
        Initialize validator with allowed directories.
        
        Args:
            allowed_dirs: List of directory paths to whitelist
        """
        self.allowed_dirs = [os.path.abspath(d) for d in allowed_dirs if d]
    
    def is_allowed(self, path: str) -> bool:
        """
        Check if path is within allowed directories.
        
        Args:
            path: File path to validate
            
        Returns:
            True if path is allowed, False otherwise
        """
        try:
            abs_path = os.path.abspath(path)
            
            # Check if path starts with any allowed directory
            return any(abs_path.startswith(allowed) for allowed in self.allowed_dirs)
        except (ValueError, OSError):
            return False
    
    def validate(self, path: str) -> str:
        """
        Validate and return absolute path if allowed.
        
        Args:
            path: File path to validate
            
        Returns:
            Absolute path if valid
            
        Raises:
            SecurityError: If path is not in whitelist
            ValueError: If path is invalid or doesn't exist
        """
        abs_path = os.path.abspath(path)
        
        # Check whitelist
        if not self.is_allowed(abs_path):
            raise SecurityError(f"Path outside allowed directories: {path}")
        
        # Check if file exists
        if not os.path.exists(abs_path):
            raise ValueError(f"Path does not exist: {path}")
        
        # Must be a file, not a directory
        if not os.path.isfile(abs_path):
            raise ValueError(f"Not a file: {path}")
        
        return abs_path


def sanitize_path(path: str, allowed_dirs: Optional[List[str]] = None) -> str:
    """
    Sanitize and validate a file path.
    
    Args:
        path: Path to sanitize
        allowed_dirs: Optional list of allowed directories. If None, uses config.
        
    Returns:
        Absolute, validated path
        
    Raises:
        SecurityError: If path validation fails
        ValueError: If path is invalid
    """
    # Import here to avoid circular dependency
    from ..config import config
    
    if allowed_dirs is None:
        allowed_dirs = config.active_scan_targets
    
    validator = PathValidator(allowed_dirs)
    return validator.validate(path)


def is_path_allowed(path: str, allowed_dirs: Optional[List[str]] = None) -> bool:
    """
    Check if a path is allowed based on scan targets and security rules.
    
    Args:
        path: Path to check (file or directory)
        allowed_dirs: Optional list of allowed directories. Defaults to config scan targets.
        
    Returns:
        True if path is allowed, False otherwise
    """
    from ..config import config, IS_WIN
    import sys
    
    if not path:
        return False

    if allowed_dirs is None:
        allowed_dirs = config.active_scan_targets
    
    try:
        # 1. Resolve to absolute real path (following symlinks is critical for macOS volumes)
        abs_path = os.path.realpath(os.path.abspath(path))
        allowed_abs = [os.path.realpath(os.path.abspath(d)) for d in allowed_dirs if d]
        
        # 2. Case-insensitive check on Windows/macOS
        platform_norm = lambda p: p.lower() if (IS_WIN or sys.platform == "darwin") else p
        
        path_norm = platform_norm(abs_path)
        is_whitelisted = any(path_norm.startswith(platform_norm(allowed)) for allowed in allowed_abs)
        
        if not is_whitelisted:
            print(f"⚠️ Path not in whitelist: {abs_path}")
            print(f"   Allowed directories: {allowed_abs}")
            return False
        
        # 3. Check for hidden files (starting with .)
        # We check all parts of the path for an exact hidden folder/file
        # Avoid blocking the root '/' or drive letters
        parts = Path(abs_path).parts
        for part in parts:
            if part.startswith('.') and not (IS_WIN and len(part) <= 3 and ':' in part):
                print(f"⚠️ Hidden path rejected: {abs_path}")
                return False
        
        # 4. State Verification (Exist & File)
        # We don't block based on 'isfile' here because it might be a directory we are revealing,
        # or a file that is temporarily busy. We let the actual consumer (streamer/opener) handle it.
        # However, for security, we check if it exists at all.
        if not os.path.exists(abs_path):
            print(f"⚠️ Path does not exist: {abs_path}")
            # We still return True if it's whitelisted but missing? 
            # No, if it doesn't exist, we can't 'allow' access to it.
            return False
            
        return True
        
    except (ValueError, OSError) as e:
        print(f"⚠️ Path validation exception for {path}: {e}")
        return False


def validate_filename(filename: str, prefix: str = "", suffix: str = "") -> bool:
    """
    Validate a filename matches expected pattern.
    
    Args:
        filename: Filename to validate
        prefix: Required prefix (e.g., "thumb_")
        suffix: Required suffix (e.g., ".jpg")
        
    Returns:
        True if filename is valid, False otherwise
    """
    # No path separators
    if '/' in filename or '\\' in filename:
        return False
    
    # No parent directory references
    if '..' in filename:
        return False
    
    # Check prefix/suffix if specified
    if prefix and not filename.startswith(prefix):
        return False
    
    if suffix and not filename.endswith(suffix):
        return False
    
    return True


def is_safe_directory_traversal(base_dir: str, target_path: str) -> bool:
    """
    Check if target_path stays within base_dir (prevents directory traversal).
    
    Args:
        base_dir: Base directory that should contain the target
        target_path: Path to check
        
    Returns:
        True if target is within base, False otherwise
    """
    try:
        base_abs = os.path.abspath(base_dir)
        target_abs = os.path.abspath(target_path)
        
        # Check if target starts with base directory
        return target_abs.startswith(base_abs)
    except (ValueError, OSError):
        return False
