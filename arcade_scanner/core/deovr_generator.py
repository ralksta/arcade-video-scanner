"""
DeoVR JSON Generator
Generates DeoVR-compatible JSON files for VR headset viewing.
"""
import json
import re
from typing import List, Dict, Any
from urllib.parse import quote
from arcade_scanner.models.video_entry import VideoEntry


def detect_vr_type(filename: str) -> Dict[str, Any]:
    """
    Detect VR video type from filename patterns.
    
    Returns dict with:
    - is3d: bool
    - screenType: "flat" | "dome" | "sphere"
    - stereoMode: "off" | "sbs" | "ou"
    """
    filename_lower = filename.lower()
    
    # Default to flat 2D
    result = {
        "is3d": False,
        "screenType": "flat",
        "stereoMode": "off"
    }
    
    # Check for 3D indicators
    if any(pattern in filename_lower for pattern in ['_lr', '_sbs', 'side-by-side', 'sidebyside']):
        result["is3d"] = True
        result["stereoMode"] = "sbs"
    elif any(pattern in filename_lower for pattern in ['_tb', '_ou', 'over-under', 'overunder']):
        result["is3d"] = True
        result["stereoMode"] = "ou"
    
    # Check for 180/360 degree videos
    if any(pattern in filename_lower for pattern in ['180', '180vr', '180°']):
        result["screenType"] = "dome"
    elif any(pattern in filename_lower for pattern in ['360', '360vr', '360°']):
        result["screenType"] = "sphere"
    
    return result


def _build_video_obj(video: VideoEntry, idx: int, server_url: str) -> Dict[str, Any]:
    """
    Build a single video object in DeoVR format.
    Helper function used by generate_deovr_json.
    """
    # Extract filename without extension
    filename = video.file_path.split('/')[-1].split('\\')[-1]
    title = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # Detect VR type from filename
    vr_info = detect_vr_type(filename)
    
    # Build video object per DeoVR spec
    video_obj = {
        "id": idx + 1,  # Unique ID required
        "title": title,
        "videoLength": int(video.duration_sec) if video.duration_sec else 0,
        "is3d": vr_info["is3d"],
        "screenType": vr_info["screenType"],
        "stereoMode": vr_info["stereoMode"],
        "encodings": [
            {
                "name": "h264",
                "videoSources": [
                    {
                        "resolution": video.height or 1080,
                        "url": f"{server_url}/stream?path={quote(video.file_path)}"
                    }
                ]
            }
        ]
    }
    
    # Add thumbnail if available
    if video.thumb:
        video_obj["thumbnailUrl"] = f"{server_url}/thumbnails/{video.thumb}"
    
    return video_obj


def generate_deovr_json(
    videos: List[VideoEntry], 
    server_url: str,
    smart_collections: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate DeoVR-compatible JSON for VR headset Selection Scene.
    This format is required for DeoVR's /deovr auto-detection endpoint.
    
    Args:
        videos: List of VideoEntry objects
        server_url: Base server URL (e.g., "http://192.168.1.100:8000")
        smart_collections: Optional list of smart collection configs to add as tabs
    
    Returns:
        DeoVR Selection Scene JSON structure with collections as sidebar tabs
    """
    scenes = []
    
    # First, build the main "All Videos" library scene
    video_list = []
    for idx, video in enumerate(videos):
        if video.vaulted:
            continue
        video_list.append(_build_video_obj(video, idx, server_url))
    
    # Debug: show first few thumbnail URLs
    thumbs_found = sum(1 for v in video_list if v.get("thumbnailUrl"))
    print(f"   📷 Videos with thumbnails: {thumbs_found}/{len(video_list)}")
    if video_list and thumbs_found > 0:
        for v in video_list[:2]:
            if v.get("thumbnailUrl"):
                print(f"   Example: {v.get('thumbnailUrl')}")
                break
    
    scenes.append({
        "name": "All Videos",
        "list": video_list
    })
    
    # Add smart collections as additional scenes (tabs in DeoVR sidebar)
    if smart_collections:
        for collection in smart_collections:
            coll_name = collection.get("name", "Collection")
            criteria = collection.get("criteria", {})
            
            # Filter videos for this collection
            filtered_list = []
            for idx, video in enumerate(videos):
                if video.vaulted:
                    continue
                if _video_matches_criteria(video, criteria):
                    filtered_list.append(_build_video_obj(video, idx, server_url))
            
            # Only add scene if it has videos
            if filtered_list:
                scenes.append({
                    "name": coll_name,
                    "list": filtered_list
                })
    
    return {
        "scenes": scenes,
        "authorized": "1"
    }


def _video_matches_criteria(video: VideoEntry, criteria: Dict[str, Any]) -> bool:
    """Check if a video matches collection filter criteria."""
    # Handle new nested schema with include/exclude
    if "include" in criteria or "exclude" in criteria:
        include = criteria.get("include", {})
        exclude = criteria.get("exclude", {})
        
        # Check exclusions first
        exc_tags = exclude.get("tags", [])
        if exc_tags and video.tags:
            if any(tag in video.tags for tag in exc_tags):
                return False
        
        exc_status = exclude.get("status", [])
        if exc_status and video.status in exc_status:
            return False
        
        # Check inclusions
        inc_tags = include.get("tags", [])
        if inc_tags:
            if not video.tags or not any(tag in video.tags for tag in inc_tags):
                return False
        
        inc_status = include.get("status", [])
        if inc_status and video.status not in inc_status:
            return False
        
        # Favorites filter
        favorites = criteria.get("favorites")
        if favorites is True and not video.favorite:
            return False
        
        return True
    
    # Legacy flat criteria schema
    if "tags" in criteria:
        req_tags = criteria["tags"]
        if not video.tags or not any(t in video.tags for t in req_tags):
            return False
    
    if "status" in criteria:
        req_status = criteria["status"]
        if isinstance(req_status, list):
            if video.status not in req_status:
                return False
        elif video.status != req_status:
            return False
    
    return True




def generate_ios_json(videos: List[VideoEntry], server_url: str) -> Dict[str, Any]:
    """
    Generate simplified JSON for iOS app.
    Uses flat scenes array with videoUrl/duration (different from DeoVR headset format).
    
    Args:
        videos: List of VideoEntry objects
        server_url: Base server URL (e.g., "http://192.168.1.100:8000")
    
    Returns:
        iOS-compatible JSON structure
    """
    scenes = []
    
    for video in videos:
        # Skip hidden/vaulted videos
        if video.vaulted:
            continue
        
        # Extract filename without extension
        filename = video.file_path.split('/')[-1].split('\\')[-1]
        title = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # Detect VR type from filename
        vr_info = detect_vr_type(filename)
        
        # Build scene object (iOS format)
        scene = {
            "title": title,
            "videoUrl": f"{server_url}/stream?path={quote(video.file_path)}",
            "duration": int(video.duration_sec) if video.duration_sec else 0,
            **vr_info
        }
        
        # Add thumbnail if available
        if video.thumb:
            scene["thumbnailUrl"] = f"{server_url}/thumbnails/{video.thumb}"
        
        # Add tags as categories if available
        if video.tags:
            scene["tags"] = video.tags
        
        scenes.append(scene)
    
    return {
        "scenes": scenes,
        "authorized": 1
    }


def generate_collection_deovr_json(
    videos: List[VideoEntry], 
    collection_name: str,
    collection_criteria: Dict[str, Any],
    server_url: str
) -> Dict[str, Any]:
    """
    Generate DeoVR JSON for a specific smart collection.
    
    Args:
        videos: Full video library
        collection_name: Name of the collection
        collection_criteria: Filter criteria from smart collection (supports both old flat and new nested schema)
        server_url: Base server URL
    
    Returns:
        DeoVR JSON structure for the collection
    """
    # Debug logging
    print(f"📱 Collection filter: '{collection_name}'")
    print(f"   Criteria: {collection_criteria}")
    print(f"   Total videos in library: {len(videos)}")
    
    # Filter videos based on collection criteria
    filtered_videos = []
    
    # Detect new vs old criteria schema
    # New schema has "include"/"exclude" nested objects
    is_new_schema = "include" in collection_criteria or "exclude" in collection_criteria
    print(f"   Using {'new' if is_new_schema else 'old'} criteria schema")
    
    for video in videos:
        # Skip vaulted
        if video.vaulted:
            continue
        
        matches = True
        
        if is_new_schema:
            # === NEW NESTED CRITERIA SCHEMA ===
            include = collection_criteria.get("include", {})
            exclude = collection_criteria.get("exclude", {})
            reject_reason = None
            
            # --- Exclusions first (if any match, skip video) ---
            exc_tags = exclude.get("tags", [])
            if exc_tags and video.tags:
                if any(tag in video.tags for tag in exc_tags):
                    matches = False
                    reject_reason = f"excluded tag"
            
            exc_status = exclude.get("status", [])
            if matches and exc_status and video.status in exc_status:
                matches = False
                reject_reason = f"excluded status: {video.status}"
            
            exc_codec = exclude.get("codec", [])
            if matches and exc_codec and video.codec:
                if any(c.lower() in video.codec.lower() for c in exc_codec):
                    matches = False
                    reject_reason = f"excluded codec"
            
            # --- Inclusions (must match if specified) ---
            inc_tags = include.get("tags", [])
            if matches and inc_tags:
                tag_logic = collection_criteria.get("tagLogic", "any")  # Default: any tag matches
                if tag_logic == "all":
                    # All specified tags must be present
                    if not video.tags or not all(tag in video.tags for tag in inc_tags):
                        matches = False
                        reject_reason = f"missing all required tags {inc_tags}, has: {video.tags}"
                else:
                    # Any specified tag matches
                    if not video.tags or not any(tag in video.tags for tag in inc_tags):
                        matches = False
                        reject_reason = f"missing any of tags {inc_tags}, has: {video.tags}"
            
            inc_status = include.get("status", [])
            if matches and inc_status:
                if video.status not in inc_status:
                    matches = False
                    reject_reason = f"status {video.status} not in {inc_status}"
            
            inc_codec = include.get("codec", [])
            if matches and inc_codec:
                if not video.codec or not any(c.lower() in video.codec.lower() for c in inc_codec):
                    matches = False
                    reject_reason = f"codec {video.codec} not in {inc_codec}"
            
            # --- Search filter (check both filename AND full path, like web UI) ---
            search = collection_criteria.get("search", "")
            if matches and search:
                search_lower = search.lower()
                filename = video.file_path.split('/')[-1].split('\\')[-1].lower()
                full_path_lower = video.file_path.lower()
                if search_lower not in filename and search_lower not in full_path_lower:
                    matches = False
                    reject_reason = f"search '{search}' not in filename or path"
            
            # --- Favorites filter ---
            favorites = collection_criteria.get("favorites")
            if matches and favorites is not None:
                if favorites is True or favorites == "true":
                    if not video.favorite:
                        matches = False
                        reject_reason = "not a favorite"
                elif favorites is False or favorites == "false":
                    if video.favorite:
                        matches = False
                        reject_reason = "is a favorite (excluded)"
            
            # --- Duration filter (only if min or max is actually set) ---
            duration_filter = collection_criteria.get("duration", {})
            duration_min = duration_filter.get("min") if duration_filter else None
            duration_max = duration_filter.get("max") if duration_filter else None
            if matches and (duration_min is not None or duration_max is not None):
                duration = video.duration_sec or 0
                if duration_min is not None and duration < duration_min:
                    matches = False
                    reject_reason = f"duration {duration}s < min {duration_min}s"
                if matches and duration_max is not None and duration > duration_max:
                    matches = False
                    reject_reason = f"duration {duration}s > max {duration_max}s"
            
            # --- Size filter (only if min or max is actually set) ---
            size_filter = collection_criteria.get("size", {})
            size_min = size_filter.get("min") if size_filter else None
            size_max = size_filter.get("max") if size_filter else None
            if matches and (size_min is not None or size_max is not None):
                size = video.size_mb or 0
                if size_min is not None and size < size_min:
                    matches = False
                    reject_reason = f"size {size}MB < min {size_min}MB"
                if matches and size_max is not None and size > size_max:
                    matches = False
                    reject_reason = f"size {size}MB > max {size_max}MB"
            
            # Log first few rejections for debugging
            if not matches and filtered_videos == [] and reject_reason:
                filename = video.file_path.split('/')[-1].split('\\')[-1]
                print(f"   ❌ Rejected: {filename[:40]}... - {reject_reason}")
        
        else:
            # === OLD FLAT CRITERIA SCHEMA (legacy support) ===
            # Check tag criteria
            if "tags" in collection_criteria:
                required_tags = collection_criteria["tags"]
                if not video.tags or not any(tag in video.tags for tag in required_tags):
                    matches = False
            
            # Check status criteria
            if matches and "status" in collection_criteria:
                required_status = collection_criteria["status"]
                if isinstance(required_status, list):
                    if video.status not in required_status:
                        matches = False
                elif video.status != required_status:
                    matches = False
            
            # Check codec criteria
            if matches and "codec" in collection_criteria:
                required_codec = collection_criteria["codec"]
                if not video.codec or required_codec.lower() not in video.codec.lower():
                    matches = False
        
        if matches:
            filtered_videos.append(video)
    
    # Debug: show result count
    print(f"   ✅ Filtered result: {len(filtered_videos)} videos match collection criteria")
    
    # Generate iOS-compatible JSON for filtered videos (used by iOS app)
    result = generate_ios_json(filtered_videos, server_url)
    result["title"] = collection_name
    
    return result


def save_deovr_library(output_path: str, videos: List[VideoEntry], server_url: str) -> bool:
    """
    Save DeoVR library JSON to disk.
    
    Args:
        output_path: Path to save JSON file
        videos: List of VideoEntry objects
        server_url: Base server URL
    
    Returns:
        True if successful, False otherwise
    """
    try:
        deovr_data = generate_deovr_json(videos, server_url)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(deovr_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ DeoVR library saved: {output_path} ({len(deovr_data['scenes'])} videos)")
        return True
    except Exception as e:
        print(f"❌ Failed to save DeoVR library: {e}")
        return False
