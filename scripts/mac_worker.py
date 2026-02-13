#!/usr/bin/env python3
"""
Mac Encoding Worker — Remote encoding queue client.

Polls the Arcade Server for pending encoding jobs, downloads the source file,
encodes it using VideoToolbox, and uploads the result.

Usage:
    python3 mac_worker.py --server http://192.168.1.100:8000 --user admin --password secret

Requirements:
    - macOS with VideoToolbox (Apple Silicon or Intel with T2)
    - ffmpeg installed (brew install ffmpeg)
    - video_optimizer.py in the same directory (imported for process_file)
"""

import argparse
import json
import os
import signal
import socket
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Add parent directory to path so we can import video_optimizer
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Color codes
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
NC = "\033[0m"
B = "\033[1m"

_shutdown = False


def signal_handler(sig, frame):
    global _shutdown
    print(f"\n{Y}⏹ Shutting down gracefully...{NC}")
    _shutdown = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class WorkerClient:
    """HTTP client for the Arcade Server queue API."""

    def __init__(self, server_url: str, username: str = "", password: str = ""):
        self.server = server_url.rstrip("/")
        self.session_token = None
        self.hostname = socket.gethostname()

        if username:
            self._login(username, password)

    def _login(self, username: str, password: str):
        """Authenticate and store session token."""
        url = f"{self.server}/api/login"
        data = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                # Extract session cookie
                cookie_header = resp.headers.get("Set-Cookie", "")
                if "session_token=" in cookie_header:
                    token = cookie_header.split("session_token=")[1].split(";")[0]
                    self.session_token = token
                    print(f"{G}✓ Authenticated as '{username}'{NC}")
                else:
                    print(f"{Y}⚠ Login succeeded but no session token received{NC}")
        except urllib.error.HTTPError as e:
            print(f"{R}✗ Login failed: {e.code} {e.reason}{NC}")
            sys.exit(1)
        except Exception as e:
            print(f"{R}✗ Connection failed: {e}{NC}")
            sys.exit(1)

    def _headers(self) -> dict:
        h = {}
        if self.session_token:
            h["Cookie"] = f"session_token={self.session_token}"
        return h

    def poll_next_job(self) -> dict | None:
        """Check for next pending job. Returns job dict or None."""
        url = f"{self.server}/api/queue/next?worker_id={self.hostname}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return None
            print(f"{R}✗ Poll error: {e.code}{NC}")
            return None
        except Exception as e:
            print(f"{R}✗ Poll connection error: {e}{NC}")
            return None

    def download_file(self, job_id: int, dest_path: str) -> bool:
        """Download source file from server."""
        url = f"{self.server}/api/queue/download?job_id={job_id}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(65536)  # 64KB chunks
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded * 100 // total
                            mb = downloaded / (1024 * 1024)
                            print(f"\r  ↓ {mb:.1f}/{total/(1024*1024):.1f} MB ({pct}%)", end="", flush=True)
                print()  # newline after progress
                return True
        except Exception as e:
            print(f"\n{R}✗ Download failed: {e}{NC}")
            return False

    def upload_file(self, job_id: int, file_path: str) -> bool:
        """Upload optimized file to server."""
        url = f"{self.server}/api/queue/upload?job_id={job_id}"
        file_size = os.path.getsize(file_path)

        headers = self._headers()
        headers["Content-Length"] = str(file_size)
        headers["Content-Type"] = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                req = urllib.request.Request(url, data=f.read(), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=3600) as resp:
                    result = json.loads(resp.read())
                    return result.get("success", False)
        except Exception as e:
            print(f"{R}✗ Upload failed: {e}{NC}")
            return False

    def update_status(self, job_id: int, status: str, **kwargs):
        """Report job status to server."""
        url = f"{self.server}/api/queue/complete"
        data = {"job_id": job_id, "status": status}
        data.update(kwargs)
        body = json.dumps(data).encode()

        headers = self._headers()
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as e:
            print(f"{Y}⚠ Status update failed: {e}{NC}")

    def check_cancelled(self, job_id: int) -> bool:
        """Check if a job was cancelled by the user."""
        url = f"{self.server}/api/queue/check?job_id={job_id}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                return data.get("cancelled", False)
        except Exception:
            return False


def process_job(client: WorkerClient, job: dict, work_dir: str):
    """Download, encode, and upload a single job."""
    job_id = job["id"]
    file_path = job["file_path"]
    filename = os.path.basename(file_path)
    stem = Path(filename).stem

    print(f"\n{B}{C}═══ Job #{job_id}: {filename} ═══{NC}")

    # 1. Download
    src_path = os.path.join(work_dir, filename)
    print(f"  {C}↓ Downloading...{NC}")
    client.update_status(job_id, "downloading")

    if not client.download_file(job_id, src_path):
        client.update_status(job_id, "failed", message="Download failed")
        return

    src_size = os.path.getsize(src_path)
    print(f"  {G}✓ Downloaded: {src_size / (1024*1024):.1f} MB{NC}")

    # Check for cancellation before encoding
    if client.check_cancelled(job_id):
        print(f"  {Y}⏹ Job cancelled by user{NC}")
        _cleanup(src_path)
        return

    # 2. Encode
    print(f"  {C}⚡ Encoding with VideoToolbox...{NC}")
    client.update_status(job_id, "encoding")

    try:
        from video_optimizer import process_file, detect_encoder, ENCODER_PROFILES

        encoder_key = detect_encoder()
        if not encoder_key or encoder_key not in ENCODER_PROFILES:
            print(f"  {R}✗ No hardware encoder detected{NC}")
            client.update_status(job_id, "failed", message="No hardware encoder on this Mac")
            _cleanup(src_path)
            return

        profile = ENCODER_PROFILES[encoder_key]
        print(f"  Using encoder: {profile['name']}")

        opt_path = os.path.join(work_dir, f"{stem}_opt.mp4")

        success, saved_bytes = process_file(
            src_path, profile,
            min_size_mb=0,  # No minimum — always encode
            copy_audio=False,
            audio_mode="enhanced",
            video_mode="compress"
        )

        # Check if output exists
        if not success or not os.path.exists(opt_path):
            # process_file puts output next to input. Check for it.
            expected_opt = os.path.join(work_dir, f"{stem}_opt.mp4")
            if os.path.exists(expected_opt):
                opt_path = expected_opt
                success = True
            else:
                print(f"  {R}✗ Encoding failed or no output produced{NC}")
                client.update_status(job_id, "failed", message="Encoding failed")
                _cleanup(src_path)
                return

        opt_size = os.path.getsize(opt_path)
        saved = src_size - opt_size
        print(f"  {G}✓ Encoded: {opt_size/(1024*1024):.1f} MB (saved {saved/(1024*1024):.1f} MB){NC}")

    except ImportError:
        print(f"  {R}✗ video_optimizer.py not found in {SCRIPT_DIR}{NC}")
        client.update_status(job_id, "failed", message="video_optimizer.py not found")
        _cleanup(src_path)
        return
    except Exception as e:
        print(f"  {R}✗ Encoding error: {e}{NC}")
        client.update_status(job_id, "failed", message=f"Encoding error: {e}")
        _cleanup(src_path)
        return

    # Check for cancellation before upload
    if client.check_cancelled(job_id):
        print(f"  {Y}⏹ Job cancelled by user{NC}")
        _cleanup(src_path, opt_path)
        return

    # 3. Upload
    print(f"  {C}↑ Uploading optimized file...{NC}")
    client.update_status(job_id, "uploading")

    if client.upload_file(job_id, opt_path):
        print(f"  {G}✓ Upload complete!{NC}")
    else:
        client.update_status(job_id, "failed", message="Upload failed",
                           saved_bytes=saved)

    # 4. Cleanup
    _cleanup(src_path, opt_path)
    print(f"  {G}✓ Temp files cleaned up{NC}")
    print(f"{B}{G}═══ Job #{job_id} done ═══{NC}\n")


def _cleanup(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Mac Encoding Worker — processes remote encoding queue jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 mac_worker.py --server http://192.168.1.100:8000 --user admin --password secret
  python3 mac_worker.py --server http://nas:8000 --poll-interval 60
        """
    )
    parser.add_argument("--server", required=True, help="Arcade server URL (e.g. http://192.168.1.100:8000)")
    parser.add_argument("--user", default="", help="Username for authentication")
    parser.add_argument("--password", default="", help="Password for authentication")
    parser.add_argument("--poll-interval", type=int, default=30, help="Seconds between polls (default: 30)")
    parser.add_argument("--work-dir", default=os.path.expanduser("~/encoding-queue"),
                       help="Temp directory for downloads (default: ~/encoding-queue)")

    args = parser.parse_args()

    # Ensure work dir exists
    os.makedirs(args.work_dir, exist_ok=True)

    print(f"\n{B}{C}╔══════════════════════════════════════╗{NC}")
    print(f"{B}{C}║   Mac Encoding Worker v1.0           ║{NC}")
    print(f"{B}{C}╚══════════════════════════════════════╝{NC}")
    print(f"  Server:    {args.server}")
    print(f"  Worker:    {socket.gethostname()}")
    print(f"  Work Dir:  {args.work_dir}")
    print(f"  Poll:      every {args.poll_interval}s")
    print()

    # Auth
    client = WorkerClient(args.server, args.user, args.password)

    # Main loop
    print(f"{C}Polling for jobs...{NC}")
    while not _shutdown:
        job = client.poll_next_job()

        if job:
            process_job(client, job, args.work_dir)
        else:
            # Wait before polling again
            for _ in range(args.poll_interval):
                if _shutdown:
                    break
                time.sleep(1)

    print(f"{G}Worker stopped.{NC}")


if __name__ == "__main__":
    main()
