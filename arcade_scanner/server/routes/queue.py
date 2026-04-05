"""routes/queue.py — Encoding-Queue- und GIF-Export-Endpunkte.

Extrahiert aus api_handler.py. Die ``convert_to_gif``-Closure wurde zu einer
echten Modul-Level-Funktion aufgewertet (kein verschachteltes ``import``).

GET-Endpunkte:
  /api/queue/status     → alle Queue-Jobs
  /api/queue/next       → nächsten Pending-Job für Worker
  /api/queue/check?     → Job-Abbruch-Status prüfen
  /api/queue/download?  → Quelldatei herunterladen
  /download_gif?        → fertiges GIF herunterladen

POST-Endpunkte:
  /api/queue/add        → Job zur Queue hinzufügen
  /api/queue/cancel     → Job abbrechen
  /api/queue/upload?    → optimierte Datei hochladen
  /api/queue/complete   → Job als erledigt markieren
  /api/export/gif       → GIF-Konvertierung starten
"""
from __future__ import annotations

import json
import mimetypes
import os
import socket
import subprocess
import tempfile
import threading
import traceback
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from arcade_scanner.database import db
from arcade_scanner.security import sanitize_path, SecurityError
from arcade_scanner.server.response_helpers import (
    send_json,
    require_auth,
)


# ---------------------------------------------------------------------------
# GIF-Job-Tracking (in-memory, resets on server restart)
# ---------------------------------------------------------------------------

GIF_JOBS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# GIF-Konvertierung (früher inline Closure in do_POST)
# ---------------------------------------------------------------------------

def convert_to_gif(
    video_path: str,
    output_path: str,
    palette_path: str,
    job_id: str,
    fps: int,
    width: int,
    height: int,
    quality: int,
    start_time: float | None,
    end_time: float | None,
    loop: int = 0,
    speed: float = 1.0,
) -> None:
    """Führt die FFmpeg-GIF-Konvertierung in einem Worker-Thread durch.

    Separiert aus ``do_POST``-Closure für bessere Testbarkeit.
    """
    GIF_JOBS[job_id] = {"status": "processing", "progress": "Starting..."}
    try:
        print(f"🎞️ Starting GIF conversion: {os.path.basename(output_path)}", flush=True)

        gif_export_dir = os.path.dirname(output_path)
        input_args = ["ffmpeg", "-y"]
        if start_time is not None:
            input_args.extend(["-ss", str(start_time)])
        if end_time is not None:
            input_args.extend(["-to", str(end_time)])
        input_args.extend(["-i", video_path])

        GIF_JOBS[job_id]["progress"] = "Generating color palette..."
        # Step 1: Palette erzeugen
        # Apply speed filter before scaling if speed != 1.0
        speed_filter = f"setpts={1/speed:.4f}*PTS," if speed != 1.0 else ""
        palette_vf = f"{speed_filter}fps={fps},scale={width}:{height}:flags=lanczos,palettegen=stats_mode=diff"
        palette_cmd = input_args + [
            "-vf", palette_vf,
            palette_path,
        ]
        result = subprocess.run(palette_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Palette generation failed: {result.stderr}", flush=True)
            GIF_JOBS[job_id] = {"status": "error", "error": "Palette generation failed"}
            return

        GIF_JOBS[job_id]["progress"] = "Rendering GIF..."
        # Step 2: GIF mit Palette erzeugen
        bayer_scale = int((quality / 100) * 5)
        gif_input_args = ["ffmpeg", "-y"]
        if start_time is not None:
            gif_input_args.extend(["-ss", str(start_time)])
        if end_time is not None:
            gif_input_args.extend(["-to", str(end_time)])
        speed_filter2 = f"setpts={1/speed:.4f}*PTS," if speed != 1.0 else ""
        gif_vf = f"{speed_filter2}fps={fps},scale={width}:{height}:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale={bayer_scale}"
        gif_cmd = gif_input_args + [
            "-i", video_path,
            "-i", palette_path,
            "-lavfi", gif_vf,
            "-loop", str(loop),
            output_path,
        ]
        result = subprocess.run(gif_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"GIF conversion failed: {result.stderr}", flush=True)
            GIF_JOBS[job_id] = {"status": "error", "error": "GIF rendering failed"}
            return

        if os.path.exists(palette_path):
            os.remove(palette_path)

        actual_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        output_filename = os.path.basename(output_path)
        GIF_JOBS[job_id] = {
            "status": "done",
            "size_mb": round(actual_size_mb, 1),
            "download_url": f"/download_gif?file={output_filename}",
            "filename": output_filename,
        }
        print(f"GIF created: {output_filename} ({actual_size_mb:.1f} MB)", flush=True)

    except Exception as e:
        print(f"Error in GIF conversion: {e}", flush=True)
        GIF_JOBS[job_id] = {"status": "error", "error": str(e)}
        traceback.print_exc()



# ---------------------------------------------------------------------------
# GET handler
# ---------------------------------------------------------------------------

def handle_get(handler) -> bool:
    path = handler.path

    # GET /api/export/gif/status/<job_id>
    if path.startswith("/api/export/gif/status/"):
        user_name = require_auth(handler)
        if user_name is None:
            return True
        job_id = path.split("/api/export/gif/status/")[1].split("?")[0]
        job = GIF_JOBS.get(job_id)
        if job is None:
            handler.send_error(404, "Job not found")
        else:
            send_json(handler, job)
        return True

    # GET /download_gif?file=...
    if path.startswith("/download_gif?"):
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            params = parse_qs(urlparse(path).query)
            filename = params.get("file", [None])[0]
            if not filename:
                handler.send_error(400, "Missing file parameter")
                return True
            if "/" in filename or "\\" in filename or ".." in filename:
                handler.send_error(403, "Invalid filename")
                return True

            gif_export_dir = os.path.join(tempfile.gettempdir(), "arcade_gif_exports")
            file_path = os.path.join(gif_export_dir, filename)

            if not os.path.exists(file_path):
                handler.send_error(404, "GIF file not found or still processing")
                return True

            file_size = os.path.getsize(file_path)
            handler.send_response(200)
            handler.send_header("Content-Type", "image/gif")
            handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            handler.send_header("Content-Length", str(file_size))
            handler.end_headers()
            with open(file_path, "rb") as f:
                handler.wfile.write(f.read())
            print(f"📥 Downloaded GIF: {filename} ({file_size / (1024*1024):.1f} MB)")
        except Exception as e:
            print(f"❌ Error downloading GIF: {e}")
            handler.send_error(500, str(e))
        return True

    # GET /api/queue/status
    if path == "/api/queue/status":
        try:
            jobs = db.get_queue_status()
            send_json(handler, jobs)
        except Exception as e:
            print(f"❌ Error in queue/status: {e}")
            handler.send_error(500, str(e))
        return True

    # GET /api/queue/next
    if path.startswith("/api/queue/next"):
        try:
            params = parse_qs(urlparse(path).query)
            worker_id = params.get("worker_id", [socket.gethostname()])[0]
            job = db.get_next_pending(worker_id=worker_id)
            if job:
                send_json(handler, job)
            else:
                handler.send_response(204)
                handler.end_headers()
        except Exception as e:
            print(f"❌ Error in queue/next: {e}")
            handler.send_error(500, str(e))
        return True

    # GET /api/queue/check?job_id=...
    if path.startswith("/api/queue/check?"):
        try:
            params = parse_qs(urlparse(path).query)
            job_id = int(params.get("job_id", [0])[0])
            cancelled = db.is_job_cancelled(job_id) if job_id else False
            send_json(handler, {"cancelled": cancelled})
        except Exception as e:
            handler.send_error(500, str(e))
        return True

    # GET /api/queue/download?job_id=...
    if path.startswith("/api/queue/download?"):
        try:
            params = parse_qs(urlparse(path).query)
            job_id = int(params.get("job_id", [0])[0])
            if not job_id:
                handler.send_error(400, "Missing job_id")
                return True

            jobs = db.get_queue_status(limit=100)
            job = next((j for j in jobs if j["id"] == job_id), None)
            if not job:
                handler.send_error(404, "Job not found")
                return True

            file_path = job["file_path"]
            if not os.path.exists(file_path):
                db.update_job_status(job_id, "failed", result_message="Source file not found")
                handler.send_error(404, "Source file not found")
                return True

            file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path)
            mime, _ = mimetypes.guess_type(file_path)

            handler.send_response(200)
            handler.send_header("Content-Type", mime or "application/octet-stream")
            handler.send_header("Content-Length", str(file_size))
            handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            handler.send_header("X-Original-Path", file_path)
            handler.end_headers()

            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)

            print(f"📤 Queue download: {filename} ({file_size / (1024*1024):.1f} MB) for job {job_id}")
        except Exception as e:
            print(f"❌ Error in queue/download: {e}")
            handler.send_error(500, str(e))
        return True

    return False


# ---------------------------------------------------------------------------
# POST handler
# ---------------------------------------------------------------------------

def handle_post(handler) -> bool:
    path = handler.path

    # POST /api/export/gif
    if path == "/api/export/gif":
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            from arcade_scanner.config import MAX_REQUEST_SIZE
            content_length = int(handler.headers.get("Content-Length", 0))
            if content_length > MAX_REQUEST_SIZE:
                handler.send_error(413, "Request Entity Too Large")
                return True

            raw = handler.rfile.read(content_length)
            data = json.loads(raw)

            video_path = data.get("path")
            preset = data.get("preset", "720p")
            fps = int(data.get("fps", 15))
            quality = int(data.get("quality", 80))
            start_time = data.get("start_time")
            end_time = data.get("end_time")
            loop = int(data.get("loop", 0))
            speed = float(data.get("speed", 1.0))

            if not video_path:
                handler.send_error(400, "Missing video path")
                return True

            try:
                video_path = sanitize_path(video_path)
            except (SecurityError, ValueError) as e:
                print(f"🚨 Security violation in GIF export: {e}")
                handler.send_error(403, "Forbidden - Invalid path")
                return True

            if not os.path.exists(video_path):
                handler.send_error(404, "Video file not found")
                return True

            video_entry = db.get(os.path.abspath(video_path))
            if not video_entry:
                handler.send_error(404, "Video not in database")
                return True

            presets = {
                "original": (video_entry.width or 1920, video_entry.height or 1080),
                "1080p": (1920, 1080),
                "720p": (1280, 720),
                "480p": (854, 480),
                "360p": (640, 360),
            }
            width, height = presets.get(preset, presets["720p"])

            duration = video_entry.duration_sec or 10
            if start_time is not None and end_time is not None:
                duration = max(0.1, end_time - start_time)
            elif start_time is not None:
                duration = max(0.1, duration - start_time)
            elif end_time is not None:
                duration = min(duration, end_time)

            estimated_size_mb = (width * height * fps * duration * (quality / 100) * 0.3) / (1024 * 1024)

            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_filename = f"{base_name}_{preset}_{fps}fps.gif"
            gif_export_dir = os.path.join(tempfile.gettempdir(), "arcade_gif_exports")
            os.makedirs(gif_export_dir, exist_ok=True)
            output_path = os.path.join(gif_export_dir, output_filename)

            job_id = str(uuid.uuid4())[:8]
            palette_path = os.path.join(gif_export_dir, f"palette_{job_id}.png")

            t = threading.Thread(
                target=convert_to_gif,
                args=(video_path, output_path, palette_path, job_id, fps, width, height, quality, start_time, end_time, loop, speed),
                daemon=True,
            )

            t.start()

            send_json(handler, {
                "status": "processing",
                "job_id": job_id,
                "output_filename": output_filename,
                "output_path": output_path,
                "estimated_size_mb": round(estimated_size_mb, 2),
                "download_url": f"/download_gif?file={output_filename}",
            })

        except json.JSONDecodeError:
            handler.send_error(400, "Invalid JSON")
        except Exception as e:
            print(f"❌ Error in GIF export: {e}")
            traceback.print_exc()
            handler.send_error(500, str(e))
        return True

    # POST /api/queue/add
    if path == "/api/queue/add":
        try:
            content_len = int(handler.headers.get("Content-Length", 0))
            data = json.loads(handler.rfile.read(content_len))
            file_path = data.get("file_path", "")
            if not file_path:
                handler.send_error(400, "Missing file_path")
                return True
            target_codec = data.get("codec", "hevc")
            if target_codec not in ("hevc", "av1"):
                target_codec = "hevc"
            size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            job_id = db.queue_encode(file_path, size_bytes, target_codec=target_codec)
            if job_id:
                print(f"📋 Queued for remote encoding: {os.path.basename(file_path)} (job {job_id})")
                send_json(handler, {"success": True, "job_id": job_id})
            else:
                send_json(handler, {"success": False, "error": "Already queued"})
        except Exception as e:
            print(f"❌ Error in queue/add: {e}")
            handler.send_error(500, str(e))
        return True

    # POST /api/queue/cancel
    if path == "/api/queue/cancel":
        try:
            content_len = int(handler.headers.get("Content-Length", 0))
            data = json.loads(handler.rfile.read(content_len))
            job_id = int(data.get("job_id", 0))
            if db.cancel_job(job_id):
                print(f"🗑️ Cancelled queue job {job_id}")
                send_json(handler, {"success": True})
            else:
                send_json(handler, {"success": False, "error": "Job not cancellable"})
        except Exception as e:
            print(f"❌ Error in queue/cancel: {e}")
            handler.send_error(500, str(e))
        return True

    # POST /api/queue/upload?job_id=...
    if path.startswith("/api/queue/upload?"):
        try:
            params = parse_qs(urlparse(path).query)
            job_id = int(params.get("job_id", [0])[0])
            if not job_id:
                handler.send_error(400, "Missing job_id")
                return True

            jobs = db.get_queue_status(limit=100)
            job = next((j for j in jobs if j["id"] == job_id), None)
            if not job:
                handler.send_error(404, "Job not found")
                return True

            original_path = job["file_path"]
            orig_stem = Path(original_path).stem
            orig_dir = os.path.dirname(original_path)
            opt_path = os.path.join(orig_dir, f"{orig_stem}_opt.mp4")

            content_len = int(handler.headers.get("Content-Length", 0))
            with open(opt_path, "wb") as out:
                remaining = content_len
                while remaining > 0:
                    chunk = handler.rfile.read(min(8192, remaining))
                    if not chunk:
                        break
                    out.write(chunk)
                    remaining -= len(chunk)

            opt_size = os.path.getsize(opt_path)
            orig_size = os.path.getsize(original_path) if os.path.exists(original_path) else 0
            saved = orig_size - opt_size

            db.update_job_status(
                job_id, "done", saved_bytes=saved,
                result_message=f"Optimized: {opt_size/(1024*1024):.1f}MB (saved {saved/(1024*1024):.1f}MB)"
            )
            print(f"✅ Upload received for job {job_id}: {os.path.basename(opt_path)} ({opt_size/(1024*1024):.1f} MB)")

            # Report nach Upload neu generieren
            try:
                from arcade_scanner.server.api_handler import report_debouncer
                current_port = handler.server.server_address[1]
                report_debouncer.schedule(current_port)
            except Exception as e:
                print(f"⚠️ Report scheduling after upload failed: {e}")

            send_json(handler, {"success": True, "opt_path": opt_path, "saved_bytes": saved})

        except Exception as e:
            print(f"❌ Error in queue/upload: {e}")
            handler.send_error(500, str(e))
        return True

    # POST /api/queue/complete
    if path == "/api/queue/complete":
        try:
            content_len = int(handler.headers.get("Content-Length", 0))
            data = json.loads(handler.rfile.read(content_len))
            job_id = int(data.get("job_id", 0))
            status = data.get("status", "done")
            message = data.get("message", "")
            saved_bytes = int(data.get("saved_bytes", 0))
            db.update_job_status(job_id, status, result_message=message, saved_bytes=saved_bytes)
            print(f"📋 Job {job_id} completed: {status} — {message}")
            send_json(handler, {"success": True})
        except Exception as e:
            print(f"❌ Error in queue/complete: {e}")
            handler.send_error(500, str(e))
        return True

    return False
