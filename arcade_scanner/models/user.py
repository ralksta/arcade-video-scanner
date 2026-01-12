from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
import time

class UserVideoData(BaseModel):
    """
    User-specific data for videos.
    Separates user preferences from global file metadata.
    """
    favorites: List[str] = Field(default_factory=list, description="List of absolute file paths marked as favorite")
    vaulted: List[str] = Field(default_factory=list, description="List of absolute file paths marked as hidden/vaulted")
    # tags mapping: path -> list of tags
    tags: Dict[str, List[str]] = Field(default_factory=dict, description="User specific tags per video path")

    # Smart Collections
    # Smart Collections
    smart_collections: List[Dict[str, Any]] = Field(default_factory=list, description="User defined smart collections")
    
    # Scan Paths
    scan_targets: List[str] = Field(default_factory=list, description="User specific scan directories")
    exclude_paths: List[str] = Field(default_factory=list, description="User specific exclusion patterns")
    
    # Available Tags (Definitions)
    available_tags: List[Dict[str, str]] = Field(default_factory=list, description="User specific tag definitions")

    # Sensitive / Safe Mode Settings
    sensitive_dirs: List[str] = Field(default_factory=list, description="Directories considered sensitive/NSFW")
    sensitive_tags: List[str] = Field(default_factory=list, description="Tags considered sensitive/NSFW")
    sensitive_collections: List[str] = Field(default_factory=list, description="Collections considered sensitive")

class User(BaseModel):
    """
    Represents a registered user.
    """
    username: str
    password_hash: str
    salt: str
    created_at: int = Field(default_factory=lambda: int(time.time()))
    is_admin: bool = False
    
    # Embed user data directly for simplicity in JSON store
    data: UserVideoData = Field(default_factory=UserVideoData)
