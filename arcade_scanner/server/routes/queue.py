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
  /api/queue/progress   → Worker-Heartbeat (Fortschritt/Phase/ETA)
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
from urllib.parse import parse_qs, urlparse

from arcade_scanner.config import MAX_UPLOAD_SIZE, config
from arcade_scanner.core.media_replace import atomic_replace, verify_media_integrity
from arcade_scanner.database import db
from arcade_scanner.security import SecurityError, is_path_allowed, sanitize_path
from arcade_scanner.server.api_handler import _media_cache
from arcade_scanner.server.response_helpers import (
    require_auth,
    send_json,
)

# ---------------------------------------------------------------------------
# GIF-Job-Tracking (in-memory, resets on server restart)
# ---------------------------------------------------------------------------

GIF_JOBS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Upload-Helfer für den Remote-Worker
# ---------------------------------------------------------------------------

def _unlink_quiet(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _receive_upload(handler, dest_path: str, content_len: int) -> int:
    """Stream the request body to disk. Returns the number of bytes written.

    A short count means the connection died mid-upload — the caller must not
    treat that as a finished encode.
    """
    written = 0
    with open(dest_path, "wb") as out:
        while written < content_len:
            chunk = handler.rfile.read(min(8192, content_len - written))
            if not chunk:
                break
            out.write(chunk)
            written += len(chunk)
    return written


def _replace_media_entry(original_path: str, new_path: str, codec: str) -> None:
    """Carry the original's metadata over to the file that replaced it.

    Mirrors the review-mode bookkeeping below: the path is the primary key, so
    the old row has to go before the new one can be written.
    """
    import time

    orig_entry = db.get(original_path)
    if not orig_entry:
        return

    entry_dict = orig_entry.model_dump(by_alias=True)
    db.remove(original_path)

    entry_dict["FilePath"] = new_path
    entry_dict["Size_MB"] = os.path.getsize(new_path) / (1024 * 1024)
    entry_dict["Status"] = "OK"
    entry_dict["Bitrate_Mbps"] = 0  # Rescan/analyze fills this in again
    entry_dict["codec"] = codec
    entry_dict["optimized_at"] = int(time.time())
    entry_dict["OriginalPath"] = None

    from arcade_scanner.models.video_entry import VideoEntry
    db.upsert(VideoEntry(**entry_dict))


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
        gif_job_id = path.split("/api/export/gif/status/")[1].split("?")[0]
        job = GIF_JOBS.get(gif_job_id)
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
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            jobs = db.get_queue_status()
            send_json(handler, jobs)
        except Exception as e:
            print(f"❌ Error in queue/status: {e}")
            handler.send_error(500, str(e))
        return True

    # GET /api/queue/next
    if path.startswith("/api/queue/next"):
        user_name = require_auth(handler)
        if user_name is None:
            return True
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
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            params = parse_qs(urlparse(path).query)
            job_id = int(params.get("job_id", [0])[0])
            # A job that no longer exists counts as cancelled — otherwise the
            # worker keeps encoding for a row the user already deleted.
            cancelled = (db.is_job_cancelled(job_id) or db.get_job(job_id) is None) if job_id else False
            send_json(handler, {"cancelled": cancelled})
        except Exception as e:
            handler.send_error(500, str(e))
        return True

    # GET /api/queue/download?job_id=...
    if path.startswith("/api/queue/download?"):
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            params = parse_qs(urlparse(path).query)
            job_id = int(params.get("job_id", [0])[0])
            if not job_id:
                handler.send_error(400, "Missing job_id")
                return True

            job = db.get_job(job_id)
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

            gif_job_id = str(uuid.uuid4())[:8]
            palette_path = os.path.join(gif_export_dir, f"palette_{gif_job_id}.png")

            t = threading.Thread(
                target=convert_to_gif,
                args=(video_path, output_path, palette_path, gif_job_id, fps, width, height, quality, start_time, end_time, loop, speed),
                daemon=True,
            )

            t.start()

            send_json(handler, {
                "status": "processing",
                # Wire key stays "job_id" — gif_export.js reads result.job_id to poll status.
                "job_id": gif_job_id,
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
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            content_len = int(handler.headers.get("Content-Length", 0))
            data = json.loads(handler.rfile.read(content_len))
            file_path = data.get("file_path", "")
            if not file_path:
                handler.send_error(400, "Missing file_path")
                return True
            # Only library files may be queued: the job's path is what
            # /api/queue/download later streams and /api/queue/upload writes
            # back, so an unchecked path here reaches straight into the host.
            if not is_path_allowed(file_path):
                print(f"🚨 Rejected queue/add outside scan directories: {file_path}")
                handler.send_error(403, "Forbidden - Path not in scan directories")
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
        user_name = require_auth(handler)
        if user_name is None:
            return True
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
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            params = parse_qs(urlparse(path).query)
            job_id = int(params.get("job_id", [0])[0])
            if not job_id:
                handler.send_error(400, "Missing job_id")
                return True

            job = db.get_job(job_id)
            if not job:
                handler.send_error(404, "Job not found")
                return True

            original_path = job["file_path"]
            orig_stem = Path(original_path).stem
            orig_ext = Path(original_path).suffix
            orig_dir = os.path.dirname(original_path)

            content_len = int(handler.headers.get("Content-Length", 0))
            if content_len <= 0:
                handler.send_error(400, "Missing Content-Length")
                return True
            # An encode should never exceed its source by much; the hard cap
            # keeps a bogus header from filling the media disk.
            limit = min(int(job.get("size_bytes") or 0) * 2 or MAX_UPLOAD_SIZE, MAX_UPLOAD_SIZE)
            if content_len > limit:
                db.update_job_status(job_id, "failed",
                                     result_message=f"Upload too large ({content_len} > {limit})")
                handler.send_error(413, "Upload too large")
                return True

            # Receive next to the original so the later os.replace stays atomic.
            part_path = os.path.join(orig_dir, f".{orig_stem}.job{job_id}.part")
            received = _receive_upload(handler, part_path, content_len)
            if received != content_len:
                _unlink_quiet(part_path)
                db.update_job_status(
                    job_id, "failed",
                    result_message=f"Upload truncated ({received}/{content_len} bytes)")
                handler.send_error(400, "Upload truncated")
                return True

            # Never let a corrupt encode replace or shadow the original.
            #
            # expected_duration = 0 schaltet die Laufzeitprüfung in
            # verify_media_integrity ab. Das ist der Fallback, wenn wir die
            # Solldauer nicht kennen — er darf aber nicht stillschweigend
            # eintreten: dann liefe die schärfste Prüfung gegen einen
            # abgeschnittenen Encode ins Leere, ohne eine Zeile Ausgabe.
            expected_duration = 0.0
            try:
                orig_meta = db.get(original_path)
                expected_duration = float(getattr(orig_meta, "duration_sec", 0) or 0)
            except Exception as e:
                print(f"⚠️ Solldauer für {original_path} nicht ermittelbar ({e!r}) — "
                      "Laufzeitprüfung des Uploads entfällt")
            ok, reason = verify_media_integrity(Path(part_path), expected_duration)
            if not ok:
                _unlink_quiet(part_path)
                db.update_job_status(job_id, "failed",
                                     result_message=f"Integrity check failed: {reason}")
                print(f"❌ Upload for job {job_id} rejected: {reason}")
                send_json(handler, {"success": False, "error": reason})
                return True

            orig_size = os.path.getsize(original_path) if os.path.exists(original_path) else 0

            if config.settings.enable_review_mode:
                # Review Mode: Move both files to a dedicated folder
                # Smart Storage: Try to use .review folder next to original file to save space on system disk
                review_job_dir = os.path.join(orig_dir, ".review", f"job_{job_id}_{orig_stem}")
                try:
                    os.makedirs(review_job_dir, exist_ok=True)
                except Exception as e:
                    # Fallback to global review directory if media directory is read-only
                    print(f"⚠️ Could not create relative review dir ({e}), falling back to global {config.review_dir}")
                    review_job_dir = os.path.join(config.review_dir, f"job_{job_id}_{orig_stem}")
                    os.makedirs(review_job_dir, exist_ok=True)

                target_orig_path = os.path.join(review_job_dir, f"{orig_stem}_original{orig_ext}")
                opt_path = os.path.join(review_job_dir, f"{orig_stem}_optimized.mp4")

                # 1. Move the verified upload into the review folder
                import shutil
                shutil.move(part_path, opt_path)

                # 2. Move original file
                if os.path.exists(original_path):
                    shutil.move(original_path, target_orig_path)

                    # 3. Update Database for original
                    # We need to preserve metadata, so we get the old entry, update it, and upsert
                    orig_entry = db.get(original_path)
                    if orig_entry:
                        old_entry_dict = orig_entry.model_dump(by_alias=True)
                        # Remove old record (since path is PK)
                        db.remove(original_path)

                        # Update fields
                        old_entry_dict["FilePath"] = target_orig_path
                        old_entry_dict["Status"] = "REVIEW"
                        old_entry_dict["OriginalPath"] = original_path

                        from arcade_scanner.models.video_entry import VideoEntry
                        db.upsert(VideoEntry(**old_entry_dict))

                        # 4. Create database entry for optimized file
                        # We use the original entry as a template for metadata
                        opt_entry_dict = old_entry_dict.copy()
                        opt_entry_dict["FilePath"] = opt_path
                        opt_entry_dict["Size_MB"] = os.path.getsize(opt_path) / (1024 * 1024)
                        opt_entry_dict["Status"] = "REVIEW"
                        # Reset some props for the optimized version
                        opt_entry_dict["Bitrate_Mbps"] = 0 # Will be updated by scanner/analyzed later

                        db.upsert(VideoEntry(**opt_entry_dict))
                else:
                    print(f"⚠️ Original file not found at {original_path}, skipping move.")
            else:
                # Standard Mode: the optimized file takes the original's place.
                opt_path = str(Path(original_path).with_suffix(".mp4"))
                atomic_replace(Path(part_path), Path(opt_path))
                # A .mkv source becomes .mp4, so the old file survives the replace.
                if opt_path != original_path:
                    _unlink_quiet(original_path)
                _replace_media_entry(original_path, opt_path, job.get("target_codec") or "hevc")

            opt_size = os.path.getsize(opt_path)
            if config.settings.enable_review_mode and os.path.exists(target_orig_path):
                orig_size = os.path.getsize(target_orig_path)
            saved = orig_size - opt_size

            db.update_job_status(
                job_id, "done", saved_bytes=saved,
                result_message=f"Optimized: {opt_size/(1024*1024):.1f}MB (saved {saved/(1024*1024):.1f}MB)"
            )
            print(f"✅ Upload received for job {job_id}: {os.path.basename(opt_path)} ({opt_size/(1024*1024):.1f} MB)")

            # Flush media cache so UI sees new entries (REVIEW status) immediately
            _media_cache.invalidate()

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

    # POST /api/queue/progress
    if path == "/api/queue/progress":
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            content_len = int(handler.headers.get("Content-Length", 0))
            data = json.loads(handler.rfile.read(content_len))
            job_id = int(data.get("job_id", 0))
            alive = db.update_job_progress(
                job_id,
                progress_pct=float(data.get("progress_pct", 0) or 0),
                eta_seconds=int(data.get("eta_seconds", 0) or 0),
                phase=str(data.get("phase", "")),
            )
            # Doubles as the cancel channel: no row updated means the job is
            # cancelled or gone, and the worker should stop.
            send_json(handler, {"success": alive, "cancelled": not alive})
        except Exception as e:
            print(f"❌ Error in queue/progress: {e}")
            handler.send_error(500, str(e))
        return True

    # POST /api/queue/complete
    if path == "/api/queue/complete":
        user_name = require_auth(handler)
        if user_name is None:
            return True
        try:
            content_len = int(handler.headers.get("Content-Length", 0))
            data = json.loads(handler.rfile.read(content_len))
            job_id = int(data.get("job_id", 0))
            status = data.get("status", "done")
            message = data.get("message", "")
            extra = {"result_message": message}
            # Intermediate reports carry no savings — writing a default 0 here
            # would wipe the real number on every status change.
            if "saved_bytes" in data:
                extra["saved_bytes"] = int(data.get("saved_bytes") or 0)
            applied = db.update_job_status(job_id, status, guard_active=True, **extra)
            print(f"📋 Job {job_id} completed: {status} — {message}")
            send_json(handler, {"success": applied, "cancelled": not applied})
        except Exception as e:
            print(f"❌ Error in queue/complete: {e}")
            handler.send_error(500, str(e))
        return True

    return False
