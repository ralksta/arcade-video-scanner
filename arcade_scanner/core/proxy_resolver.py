"""Proxy resolution for streaming.

Idea: next to the original file there may be a smaller, streaming-friendly copy
(a "proxy") — in its own directory tree that is excluded from scans. The library
therefore still shows exactly one entry per video, and the original is never
touched.

On each request the server decides which file to send:

    client on the LAN      -> original (full quality at the desk)
    client via Tailscale   -> proxy, if one exists (on the road)
    no proxy available     -> original

Clients notice none of this: they always request the original path.

Path mapping — the complete original path is mirrored below the proxy root so
that files from different mounts cannot collide:

    original:  /media/shoots/2024_01/foo.MOV
    proxy:     <proxy_root>/media/shoots/2024_01/foo.mp4

Security: the ORIGINAL path from the request is validated by the caller before
anything here runs. The proxy path is derived from it and never comes from the
request, so it needs no second whitelist pass.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Optional, Tuple

# Proxies are always stored as MP4: playable by iOS, Safari and the TV clients
# without another transcode.
PROXY_EXTENSION = ".mp4"

# Tailscale hands out addresses from the CGNAT range (IPv4) and from a fixed ULA
# prefix (IPv6). Either one means: not on the home network.
_TAILSCALE_NETS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fd7a:115c:a1e0::/48"),
)


def get_proxy_root() -> str:
    """Configured proxy root, or "" when the feature is off."""
    try:
        from arcade_scanner.config import config
        return (config.settings.proxy_root or "").strip()
    except Exception:
        return ""


def is_proxy_streaming_enabled() -> bool:
    try:
        from arcade_scanner.config import config
        return bool(config.settings.proxy_streaming) and bool(get_proxy_root())
    except Exception:
        return False


def proxy_path_for(original_path: str, proxy_root: Optional[str] = None) -> str:
    """Path of the proxy file for an original. Does NOT check whether it exists.

    Returns "" when no proxy root is configured, or when the original already
    lives inside the proxy tree (no proxy of a proxy).
    """
    root = proxy_root if proxy_root is not None else get_proxy_root()
    if not root or not original_path:
        return ""

    abs_root = os.path.abspath(root)
    abs_orig = os.path.abspath(original_path)

    if abs_orig == abs_root or abs_orig.startswith(abs_root + os.sep):
        return ""

    # Strip the drive letter (Windows) and any leading separator, otherwise
    # os.path.join treats the path as absolute and discards the root.
    relative = os.path.splitdrive(abs_orig)[1].lstrip("/\\")
    stem, _ = os.path.splitext(relative)
    return os.path.join(abs_root, stem + PROXY_EXTENSION)


def has_proxy(original_path: str, proxy_root: Optional[str] = None) -> bool:
    candidate = proxy_path_for(original_path, proxy_root)
    return bool(candidate) and os.path.isfile(candidate)


def is_remote_client(client_ip: str) -> bool:
    """True when the request does not come from the home network.

    Unknown addresses count as remote on purpose: serving a proxy by mistake
    costs picture quality, serving a 600 Mbit original by mistake costs playback.
    """
    if not client_ip:
        return True

    try:
        ip = ipaddress.ip_address(client_ip.strip().strip("[]"))
    except ValueError:
        return True

    # Unwrap IPv4-mapped IPv6 addresses (::ffff:192.168.2.10).
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped

    if any(ip in net for net in _TAILSCALE_NETS):
        return True

    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return False

    return True


def parse_override(raw: Optional[str]) -> Optional[bool]:
    """Evaluate the `?proxy=` parameter. None = no preference, decide normally."""
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return None


def resolve_stream_path(
    original_path: str,
    client_ip: str = "",
    override: Optional[bool] = None,
) -> Tuple[str, str]:
    """Decide which file to serve.

    Returns (path to serve, variant) where variant is "proxy" or "original" and
    ends up in the response as the `X-Arcade-Variant` header.
    """
    if override is False:
        return original_path, "original"

    if not is_proxy_streaming_enabled():
        return original_path, "original"

    # override is True  -> force the proxy (when one exists)
    # override is None  -> only switch to the proxy for remote clients
    if override is not True and not is_remote_client(client_ip):
        return original_path, "original"

    candidate = proxy_path_for(original_path)
    if candidate and os.path.isfile(candidate):
        return candidate, "proxy"

    return original_path, "original"


def client_ip_from_handler(handler) -> str:
    """Extract the client IP from the request (honouring X-Forwarded-For).

    XFF is forgeable — harmless here, because the worst outcome is a different
    quality tier of a file the caller may already access.
    """
    forwarded = (handler.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    try:
        return handler.client_address[0]
    except (AttributeError, IndexError):
        return ""
