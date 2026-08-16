import mimetypes
import os
import re

# 1 MB chunks: fewer syscalls / wfile.write round-trips than the old 64 KB
# when the kernel sendfile fast path is unavailable (e.g. SSL sockets on
# platforms without kTLS).
CHUNK_SIZE = 1024 * 1024

# Matches "bytes=start-end", "bytes=start-" and the suffix form "bytes=-N"
_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


def parse_range_header(range_header, file_size):
    """Parse an HTTP Range header into an inclusive (start, end) byte tuple.

    Returns:
        (start, end) on success,
        None if the header is absent/malformed (caller should serve 200),
        "unsatisfiable" if the requested range lies outside the file (416).
    """
    if not range_header:
        return None
    match = _RANGE_RE.match(range_header.strip())
    if not match:
        return None

    start_s, end_s = match.groups()
    if start_s == "" and end_s == "":
        return None

    if start_s == "":
        # Suffix range: last N bytes (e.g. "bytes=-500")
        suffix_len = int(end_s)
        if suffix_len == 0:
            return "unsatisfiable"
        start = max(0, file_size - suffix_len)
        end = file_size - 1
    else:
        start = int(start_s)
        # Clamp open-ended and over-long ranges to the actual file size,
        # otherwise the announced Content-Length would exceed the bytes sent
        # and a keep-alive client would hang waiting for the rest.
        end = int(end_s) if end_s else file_size - 1
        end = min(end, file_size - 1)

    if start >= file_size or start > end:
        return "unsatisfiable"
    return (start, end)


def _send_file_slice(handler, file_path, start, length):
    """Send `length` bytes of `file_path` starting at `start` to the client.

    Uses zero-copy socket.sendfile() when available (plain sockets get kernel
    sendfile; SSL sockets fall back to an internal send() loop). Falls back to
    a chunked read/write loop for exotic handler objects (e.g. tests).
    On a broken client connection the connection is flagged for close so a
    keep-alive session is never reused in a corrupted state.
    """
    with open(file_path, "rb") as f:
        sendfile = getattr(getattr(handler, "connection", None), "sendfile", None)
        if sendfile is not None:
            try:
                handler.wfile.flush()
                sendfile(f, offset=start, count=length)
            except (ConnectionResetError, BrokenPipeError, OSError, ValueError):
                # Partial send state is unknown — never reuse this connection.
                handler.close_connection = True
            return

        f.seek(start)
        remaining = length
        while remaining > 0:
            data = f.read(min(remaining, CHUNK_SIZE))
            if not data:
                break
            try:
                handler.wfile.write(data)
            except (ConnectionResetError, BrokenPipeError):
                handler.close_connection = True
                break
            remaining -= len(data)


def serve_file_range(handler, file_path, method="GET", extra_headers=None):
    """
    Standard implementation of HTTP Range Requests (Status 206).
    Allows browsers to seek and buffer videos efficiently.

    extra_headers: optional dict of additional response headers, sent on every
    response variant (200/206/416) — used to expose which file was served.
    """
    if not os.path.exists(file_path):
        handler.send_error(404)
        return

    def _send_extra():
        for key, value in (extra_headers or {}).items():
            handler.send_header(key, value)

    stat = os.stat(file_path)
    file_size = stat.st_size
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "video/mp4"

    byte_range = parse_range_header(handler.headers.get("Range"), file_size)

    if byte_range == "unsatisfiable":
        handler.send_response(416)
        handler.send_header("Content-Range", f"bytes */{file_size}")
        handler.send_header("Content-Length", "0")
        _send_extra()
        handler.end_headers()
        return

    if byte_range is not None:
        start, end = byte_range
        length = end - start + 1
        if start == 0:
            print(f"📺 Streaming: {os.path.basename(file_path)}")

        handler.send_response(206)
        handler.send_header("Content-type", mime_type)
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        handler.send_header("Content-Length", str(length))
        handler.send_header("Last-Modified", handler.date_time_string(stat.st_mtime))
        _send_extra()
        handler.end_headers()

        if method == "GET":
            _send_file_slice(handler, file_path, start, length)
        return

    # No Range request
    print(f"📺 Streaming: {os.path.basename(file_path)}")
    handler.send_response(200)
    handler.send_header("Content-type", mime_type)
    handler.send_header("Content-Length", str(file_size))
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Last-Modified", handler.date_time_string(stat.st_mtime))
    _send_extra()
    handler.end_headers()
    if method == "GET":
        _send_file_slice(handler, file_path, 0, file_size)
