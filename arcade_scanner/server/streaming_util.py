import mimetypes
import os
import re
import shutil

def serve_file_range(handler, file_path, method="GET"):
    """
    Standard implementation of HTTP Range Requests (Status 206).
    Allows browsers to seek and buffer videos efficiently.
    """
    if not os.path.exists(file_path):
        handler.send_error(404)
        return

    file_size = os.path.getsize(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "video/mp4"

    range_header = handler.headers.get("Range")
    
    if range_header:
        match = re.match(r"bytes=(\d+)-(\d+)?", range_header)
        if match:
            start = int(match.group(1))
            end = match.group(2)
            end = int(end) if end else file_size - 1
            
            if start >= file_size:
                handler.send_response(416)
                handler.end_headers()
                return

            length = end - start + 1
            handler.send_response(206)
            handler.send_header("Content-type", mime_type)
            handler.send_header("Accept-Ranges", "bytes")
            handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            handler.send_header("Content-Length", str(length))
            handler.end_headers()

            if method == "GET":
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk_size = min(remaining, 65536)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        try:
                            handler.wfile.write(data)
                        except (ConnectionResetError, BrokenPipeError):
                            break
                        remaining -= len(data)
            return

    # No Range request
    handler.send_response(200)
    handler.send_header("Content-type", mime_type)
    handler.send_header("Content-Length", str(file_size))
    handler.send_header("Accept-Ranges", "bytes")
    handler.end_headers()
    if method == "GET":
        with open(file_path, "rb") as f:
            try:
                shutil.copyfileobj(f, handler.wfile)
            except (ConnectionResetError, BrokenPipeError):
                pass
