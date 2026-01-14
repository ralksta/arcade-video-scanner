from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import time

class MediaType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    UNKNOWN = "unknown"

class VideoMetadata(BaseModel):
    """Specific metadata for Video files"""
    codec: str = "unknown"
    duration_sec: float = 0.0
    bitrate_mbps: float = 0.0
    width: int = 0
    height: int = 0
    audio_codec: str = "unknown"
    audio_channels: int = 0
    container: str = "unknown"
    profile: str = ""
    level: float = 0.0
    pixel_format: str = ""
    frame_rate: float = 0.0

class ImageMetadata(BaseModel):
    """Specific metadata for Image files"""
    width: int = 0
    height: int = 0
    format: str = "unknown"  # JPEG, PNG, etc.
    color_space: str = "unknown" # RGB, CMYK
    has_alpha: bool = False
    exif: Dict[str, Any] = Field(default_factory=dict) # Camera model, etc.

class MediaAsset(BaseModel):
    """
    Unified Media Asset Model.
    Replaces the legacy VideoEntry to support multiple media types.
    """
    # Core Identity & File System
    file_path: str = Field(..., alias="FilePath", description="Absolute path to the media file")
    size_mb: float = Field(..., alias="Size_MB", description="File size in Megabytes")
    media_type: MediaType = Field(MediaType.UNKNOWN, description="Type of media (video, image)")
    
    # Metadata Containers (Polymorphic)
    # We keep them optional; a file is either Video or Image (or potentially both if we get crazy?)
    # For now, distinct.
    video_metadata: Optional[VideoMetadata] = None
    image_metadata: Optional[ImageMetadata] = None
    
    # Legacy Flattening Support (To be compatible with current Frontend/API)
    # These fields might duplicate data in sub-models for now, or we use properties.
    # For the immediate migration, we might want to populate these from the sub-models at export time.
    # However, keeping the main model clean is better.
    
    # Status / Workflow
    status: str = Field("OK", alias="Status", description="Processing/Optimization status")
    
    # User User State (Global for now, until full user-db split is finalized)
    favorite: bool = Field(False, description="Is marked as favorite")
    vaulted: bool = Field(False, alias="hidden", description="Is moved to vault/hidden")
    tags: List[str] = Field(default_factory=list, description="User defined tags")
    
    # Assets
    thumb: str = Field("", description="Thumbnail filename")
    
    # Chronology
    imported_at: int = Field(default_factory=lambda: int(time.time()), description="Timestamp when first imported")
    mtime: int = Field(0, description="Last modification timestamp of the file")

    # --- LEGACY COMPATIBILITY PROPERTIES (Snake Case) ---
    @property
    def bitrate_mbps(self) -> float:
        return self.video_metadata.bitrate_mbps if self.video_metadata else 0.0

    @property
    def duration_sec(self) -> float:
        return self.video_metadata.duration_sec if self.video_metadata else 0.0

    @property
    def codec(self) -> str:
        return self.video_metadata.codec if self.video_metadata else "unknown"
    
    # --- LEGACY FLATTENING (Dict Export) ---
    # These properties ensure that when dict() is called (if configured), or when using alias access, 
    # it behaves somewhat like VideoEntry.
    
    @property
    def Duration_Sec(self) -> float:
        return self.duration_sec
    
    @property
    def Bitrate_Mbps(self) -> float:
        return self.bitrate_mbps

    @property
    def Width(self) -> int:
        return self.video_metadata.width if self.video_metadata else (self.image_metadata.width if self.image_metadata else 0)

    @property
    def Height(self) -> int:
        return self.video_metadata.height if self.video_metadata else (self.image_metadata.height if self.image_metadata else 0)
    
    # Allow dict() export to include these flattening fields
    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        # Inject legacy flattened fields for frontend compatibility
        if self.video_metadata:
            d['codec'] = self.video_metadata.codec
            d['Duration_Sec'] = self.video_metadata.duration_sec
            d['Bitrate_Mbps'] = self.video_metadata.bitrate_mbps
            d['Width'] = self.video_metadata.width
            d['Height'] = self.video_metadata.height
        elif self.image_metadata:
             d['Width'] = self.image_metadata.width
             d['Height'] = self.image_metadata.height
             d['format'] = self.image_metadata.format
        return d

    class Config:
        populate_by_name = True
        use_enum_values = True
        extra = "ignore"
