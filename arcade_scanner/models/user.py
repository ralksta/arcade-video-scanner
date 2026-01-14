from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
import time

import uuid

def _default_criteria():
    return {
        "tagLogic": "any",
        "include": {
            "status": [], "codec": [], "tags": [], 
            "resolution": [], "orientation": [], 
            "media_type": [], "format": []
        },
        "exclude": {
            "status": [], "codec": [], "tags": [], 
            "resolution": [], "orientation": [], 
            "media_type": [], "format": []
        },
        "favorites": None,
        "date": {"type": "any", "relative": None, "from": None, "to": None},
        "size": {"min": None, "max": None},
        "duration": {"min": None, "max": None},
        "search": ""
    }

DEFAULT_SMART_COLLECTIONS = [
    {
        "id": "col_apps_all_photos",
        "name": "All Photos",
        "icon": "photo_library",
        "color": "#a855f7", # Purple
        "category": "Library Overview",
        "criteria": {**_default_criteria(), **{"include": {**_default_criteria()["include"], "media_type": ["image"]}}}
    },
    {
        "id": "col_apps_all_videos",
        "name": "All Videos",
        "icon": "movie",
        "color": "#00ffd0", # Cyan
        "category": "Library Overview",
        "criteria": {**_default_criteria(), **{"include": {**_default_criteria()["include"], "media_type": ["video"]}}}
    },
    {
        "id": "col_apps_large_files",
        "name": "Large Files (>1GB)",
        "icon": "sd_storage",
        "color": "#eab308", # Gold/Yellow - wait, user asked for Red. Let's stick to user request Red? User said "Large Files (Red)".
        "color": "#ef4444", # Red
        "category": "Library Overview",
        "criteria": {**_default_criteria(), "size": {"min": 1000, "max": None}}
    },
    {
        "id": "col_apps_high_bitrate",
        "name": "High Bitrate",
        "icon": "diamond",
        "color": "#eab308", # Gold
        "category": "Library Overview",
        "criteria": {**_default_criteria(), "include": {**_default_criteria()["include"], "status": ["HIGH"]}}
    },
    {
        "id": "col_apps_recent",
        "name": "Recent Imports",
        "icon": "calendar_today",
        "color": "#22c55e", # Green
        "category": "Library Overview",
        "criteria": {**_default_criteria(), "date": {"type": "relative", "relative": "7d", "from": None, "to": None}}
    }
]

import copy

def _get_default_smart_collections():
    return copy.deepcopy(DEFAULT_SMART_COLLECTIONS)

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
    smart_collections: List[Dict[str, Any]] = Field(default_factory=_get_default_smart_collections, description="User defined smart collections")
    
    # Scan Paths
    scan_targets: List[str] = Field(default_factory=list, description="User specific scan directories")
    exclude_paths: List[str] = Field(default_factory=list, description="User specific exclusion patterns")
    scan_images: bool = Field(False, description="Enable scanning of image files (jpg, png, etc.)")
    
    # Setup Status
    setup_complete: bool = Field(True, description="Whether first-run setup wizard has been completed")
    
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
