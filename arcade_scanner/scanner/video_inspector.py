import os
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

from ..models.media_asset import MediaAsset, MediaType, VideoMetadata
from .inspector import MediaInspector
from .media_probe import MediaProbe  # We'll reuse the internal static helpers for now

class VideoInspector(MediaInspector):
    """
    Inspector for Video Files using FFprobe (via legacy MediaProbe logic).
    """
    def __init__(self, probe_instance: MediaProbe):
        self.probe = probe_instance
        # Extensions could be injected or shared constant
        self.VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts')

    def can_handle(self, filepath: str) -> bool:
        return any(filepath.lower().endswith(ext) for ext in self.VIDEO_EXTENSIONS)

    async def inspect(self, filepath: str) -> Optional[MediaAsset]:
        # Reuse existing logic to get VideoEntry, then convert to MediaAsset
        # Or better: Call the low-level _run_ffprobe and build MediaAsset directly.
        # For Phase 1, let's wrap the existing probe for safety.
        
        legacy_entry = await self.probe.get_metadata(filepath)
        if not legacy_entry:
            return None
            
        # Convert VideoEntry -> MediaAsset
        # This acts as an adapter during the migration phase
        
        # 1. Create specific metadata
        v_meta = VideoMetadata(
            codec=legacy_entry.codec or "unknown",
            duration_sec=legacy_entry.duration_sec or 0.0,
            bitrate_mbps=legacy_entry.bitrate_mbps or 0.0,
            width=legacy_entry.width or 0,
            height=legacy_entry.height or 0,
            audio_codec=legacy_entry.audio_codec or "unknown",
            audio_channels=legacy_entry.audio_channels or 0,
            container=legacy_entry.container_format or "unknown",
            profile=legacy_entry.profile or "",
            level=legacy_entry.level or 0.0,
            pixel_format=legacy_entry.pixel_format or "",
            frame_rate=legacy_entry.frame_rate or 0.0
        )
        
        # 2. Create Asset
        asset = MediaAsset(
            FilePath=legacy_entry.file_path,
            Size_MB=legacy_entry.size_mb,
            media_type=MediaType.VIDEO,
            video_metadata=v_meta,
            status=legacy_entry.status,
            favorite=legacy_entry.favorite,
            hidden=legacy_entry.vaulted,
            tags=legacy_entry.tags,
            thumb=legacy_entry.thumb,
            imported_at=legacy_entry.imported_at,
            mtime=legacy_entry.mtime
        )
        
        return asset
