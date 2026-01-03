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


def generate_deovr_json(videos: List[VideoEntry], server_url: str) -> Dict[str, Any]:
    """
    Generate DeoVR-compatible JSON from video library.
    
    Args:
        videos: List of VideoEntry objects
        server_url: Base server URL (e.g., "http://192.168.1.100:8000")
    
    Returns:
        DeoVR JSON structure
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
        
        # Build scene object
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
        collection_criteria: Filter criteria from smart collection
        server_url: Base server URL
    
    Returns:
        DeoVR JSON structure for the collection
    """
    # Filter videos based on collection criteria
    filtered_videos = []
    
    for video in videos:
        # Skip vaulted
        if video.vaulted:
            continue
        
        # Check tag criteria
        if "tags" in collection_criteria:
            required_tags = collection_criteria["tags"]
            if not video.tags or not any(tag in video.tags for tag in required_tags):
                continue
        
        # Check status criteria
        if "status" in collection_criteria:
            required_status = collection_criteria["status"]
            if isinstance(required_status, list):
                if video.status not in required_status:
                    continue
            elif video.status != required_status:
                continue
        
        # Check codec criteria
        if "codec" in collection_criteria:
            required_codec = collection_criteria["codec"]
            if not video.codec or required_codec.lower() not in video.codec.lower():
                continue
        
        filtered_videos.append(video)
    
    # Generate DeoVR JSON for filtered videos
    result = generate_deovr_json(filtered_videos, server_url)
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
