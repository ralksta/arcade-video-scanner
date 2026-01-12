from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class VideoEntry(BaseModel):
    """
    Represents a single video file in the library.
    Replaces the legacy dictionary structure.
    """
    file_path: str = Field(..., alias="FilePath", description="Absolute path to the video file")
    size_mb: float = Field(..., alias="Size_MB", description="File size in Megabytes")
    bitrate_mbps: float = Field(0.0, alias="Bitrate_Mbps", description="Video bitrate in Mbps")
    status: str = Field("OK", alias="Status", description="Optimization status (OK, HIGH, etc.)")
    media_type: str = Field("video", description="Type of media (video/image)")
    
    # Optional metadata (might be missing in partial scans)
    codec: Optional[str] = Field("unknown", alias="codec")
    duration_sec: Optional[float] = Field(0.0, alias="Duration_Sec")
    width: Optional[int] = Field(0, alias="Width")
    height: Optional[int] = Field(0, alias="Height")
    
    # Extended Technical Details
    audio_codec: Optional[str] = Field("unknown", alias="AudioCodec")
    audio_channels: Optional[int] = Field(0, alias="AudioChannels")
    container_format: Optional[str] = Field("unknown", alias="Container")
    profile: Optional[str] = Field("", alias="Profile")
    level: Optional[float] = Field(0.0, alias="Level")
    pixel_format: Optional[str] = Field("", alias="PixelFormat")
    frame_rate: Optional[float] = Field(0.0, alias="FrameRate")
    
    # User-defined attributes
    favorite: bool = Field(False, description="Is marked as favorite")
    vaulted: bool = Field(False, alias="hidden", description="Is moved to vault/hidden")
    tags: list[str] = Field(default_factory=list, description="User defined tags")
    thumb: str = Field("", description="Thumbnail filename")
    
    # Date Metadata
    imported_at: Optional[int] = Field(0, description="Timestamp when first imported/scanned")
    mtime: Optional[int] = Field(0, description="Last modification timestamp of the file")

    
    class Config:
        populate_by_name = True
        extra = "ignore"  # Robustness against cache mismatch
        
