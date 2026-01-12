from typing import Protocol, Optional
from ..models.media_asset import MediaAsset, MediaType

class MediaInspector(Protocol):
    """
    Protocol for media analysis tools.
    Implementations (VideoInspector, ImageInspector) must provide this interface.
    """
    
    def can_handle(self, filepath: str) -> bool:
        """Return True if this inspector can process the file."""
        ...

    async def inspect(self, filepath: str) -> Optional[MediaAsset]:
        """
        Analyze the file and return a fully populated MediaAsset.
        Should return None if analysis fails or file is invalid.
        """
        ...
