#!/usr/bin/env python3
"""
Mac Encoding Worker — Remote encoding queue client.

Polls the Arcade Server for pending encoding jobs, downloads the source file,
encodes it using VideoToolbox, and uploads the result.

Usage:
    python3 mac_worker.py --server http://192.168.1.100:8000 --user admin --password secret

Credentials are mandatory: every /api/queue/* endpoint requires a session.
Server sessions live in memory, so the worker re-authenticates automatically
whenever a request comes back 401 (e.g. after a server restart).

Requirements:
    - macOS with VideoToolbox (Apple Silicon or Intel with T2)
    - ffmpeg installed (brew install ffmpeg)
    - the videocrunch repo checked out next to this one (imported for process_file);
      see arcade_scanner.config.optimizer_path
"""

import argparse
import json
import os
import shutil
import signal
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Add parent (repo root) directory to path so we can import arcade_scanner.config
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

# videocrunch lives in its own repo now; find it the same way the server does.
from arcade_scanner.config import config as _arcade_config  # noqa: E402

_VC_DIR = str(Path(_arcade_config.optimizer_path).parent)
if _VC_DIR not in sys.path:
    sys.path.insert(0, _VC_DIR)

from crunch_utils import battery_from_pmset, is_within_schedule, parse_schedule  # noqa: E402

# Color codes
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
NC = "\033[0m"
B = "\033[1m"

_shutdown = False


def is_on_battery() -> bool:
    """True when a macOS machine is running on battery power (else False)."""
    if sys.platform != "darwin":
        return False
    try:
        import subprocess
        r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5)
        return battery_from_pmset(r.stdout)
    except Exception:
        return False


def _sleep_interruptible(seconds: int) -> None:
    """Sleep in 1s steps so Ctrl-C / SIGTERM shutdown stays responsive."""
    for _ in range(seconds):
        if _shutdown:
            break
        time.sleep(1)


def signal_handler(_sig, _frame):
    global _shutdown
    print(f"\n{Y}⏹ Shutting down gracefully...{NC}")
    _shutdown = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class AuthError(Exception):
    """Raised when the worker cannot (re-)establish a session."""


class WorkerClient:
    """HTTP client for the Arcade Server queue API."""

    def __init__(self, server_url: str, username: str = "", password: str = ""):
        self.server = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.session_token = None
        self.hostname = socket.gethostname()

        if username:
            self._login()

    def _login(self):
        """Authenticate and store the session token."""
        url = f"{self.server}/api/login"
        data = json.dumps({"username": self.username, "password": self.password}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                cookie_header = resp.headers.get("Set-Cookie", "")
                if "session_token=" in cookie_header:
                    self.session_token = cookie_header.split("session_token=")[1].split(";")[0]
                    print(f"{G}✓ Authenticated as '{self.username}'{NC}")
                    return
                raise AuthError("login succeeded but no session token received")
        except urllib.error.HTTPError as e:
            raise AuthError(f"login failed: {e.code} {e.reason}") from e
        except urllib.error.URLError as e:
            raise AuthError(f"connection failed: {e}") from e

    def _headers(self, extra: dict | None = None) -> dict:
        h = dict(extra or {})
        if self.session_token:
            h["Cookie"] = f"session_token={self.session_token}"
        return h

    def _open(self, url: str, data=None, method: str = "GET", timeout: int = 10,
              headers: dict | None = None):
        """Perform one request, re-authenticating once on 401.

        Sessions are held in the server's memory, so every server restart
        invalidates this worker's token. Without the retry the worker would
        just log 401s forever.
        """
        for attempt in (1, 2):
            req = urllib.request.Request(url, data=data, headers=self._headers(headers),
                                         method=method)
            try:
                return urllib.request.urlopen(req, timeout=timeout)
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt == 1 and self.username:
                    print(f"{Y}⚠ Session expired — re-authenticating...{NC}")
                    self._login()
                    if callable(getattr(data, "seek", None)):
                        data.seek(0)  # rewind a streamed body before the retry
                    continue
                raise
        raise AuthError("unreachable")  # pragma: no cover

    def poll_next_job(self) -> dict | None:
        """Check for next pending job. Returns job dict or None."""
        url = f"{self.server}/api/queue/next?worker_id={self.hostname}"
        try:
            with self._open(url, timeout=10) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return None
            print(f"{R}✗ Poll error: {e.code}{NC}")
            return None
        except AuthError as e:
            print(f"{R}✗ Authentication error: {e}{NC}")
            return None
        except Exception as e:
            print(f"{R}✗ Poll connection error: {e}{NC}")
            return None

    def download_file(self, job_id: int, dest_path: str, on_progress=None) -> bool:
        """Download source file from server."""
        url = f"{self.server}/api/queue/download?job_id={job_id}"
        try:
            with self._open(url, timeout=3600) as resp:
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
                            if on_progress:
                                on_progress(downloaded, total)
                print()  # newline after progress
                return True
        except Exception as e:
            print(f"\n{R}✗ Download failed: {e}{NC}")
            return False

    def upload_file(self, job_id: int, file_path: str) -> bool:
        """Upload optimized file to server.

        The body is streamed straight from the file handle — reading a
        multi-GB encode into memory first would blow up the worker.
        """
        url = f"{self.server}/api/queue/upload?job_id={job_id}"
        file_size = os.path.getsize(file_path)
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": "application/octet-stream",
        }

        try:
            with open(file_path, "rb") as f:
                with self._open(url, data=f, method="POST", timeout=3600,
                                headers=headers) as resp:
                    result = json.loads(resp.read())
                    if not result.get("success", False):
                        print(f"{R}✗ Server rejected upload: {result.get('error', 'unknown')}{NC}")
                    return result.get("success", False)
        except Exception as e:
            print(f"{R}✗ Upload failed: {e}{NC}")
            return False

    def update_status(self, job_id: int, status: str, **kwargs) -> bool:
        """Report job status. False means the server no longer wants this job."""
        url = f"{self.server}/api/queue/complete"
        data = {"job_id": job_id, "status": status}
        data.update(kwargs)
        body = json.dumps(data).encode()

        try:
            with self._open(url, data=body, method="POST", timeout=10,
                            headers={"Content-Type": "application/json"}) as resp:
                result = json.loads(resp.read() or b"{}")
                return bool(result.get("success", True))
        except Exception as e:
            print(f"{Y}⚠ Status update failed: {e}{NC}")
            return True  # a network hiccup is not a cancellation

    def report_progress(self, job_id: int, progress_pct: float, eta_seconds: int,
                        phase: str) -> bool:
        """Heartbeat. False means the job was cancelled or is gone."""
        url = f"{self.server}/api/queue/progress"
        body = json.dumps({
            "job_id": job_id,
            "progress_pct": round(progress_pct, 1),
            "eta_seconds": int(eta_seconds),
            "phase": phase,
        }).encode()

        try:
            with self._open(url, data=body, method="POST", timeout=10,
                            headers={"Content-Type": "application/json"}) as resp:
                result = json.loads(resp.read() or b"{}")
                return not result.get("cancelled", False)
        except Exception as e:
            print(f"{Y}⚠ Heartbeat failed: {e}{NC}")
            return True  # unreachable server != cancelled job

    def check_cancelled(self, job_id: int) -> bool | None:
        """Was the job cancelled? None means 'could not find out'."""
        url = f"{self.server}/api/queue/check?job_id={job_id}"
        try:
            with self._open(url, timeout=5) as resp:
                data = json.loads(resp.read())
                return data.get("cancelled", False)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return True  # job is gone — nothing left to encode for
            print(f"{Y}⚠ Cancel check failed: {e.code}{NC}")
            return None
        except Exception as e:
            print(f"{Y}⚠ Cancel check failed: {e}{NC}")
            return None


class JobReporter:
    """Pushes progress to the server on a timer and watches for cancellation.

    The optimizer's callback runs inside the ffmpeg reader loop, so it may only
    touch local state — this thread does the network I/O, which also gives the
    server a heartbeat during phases the callback never sees (probing, SSIM,
    transfers). A stalled worker is what lets the server requeue the job.
    """

    INTERVAL = 10

    def __init__(self, client: WorkerClient, job_id: int):
        self.client = client
        self.job_id = job_id
        self.cancelled = threading.Event()
        self._state = {"pct": 0.0, "eta": 0, "phase": ""}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def set_phase(self, phase: str, pct: float = 0.0, eta: int = 0):
        with self._lock:
            self._state = {"pct": pct, "eta": eta, "phase": phase}

    def on_encode_progress(self, current: float, total: float, label: str):
        """process_file's progress_callback — local writes only, no I/O."""
        pct = (current * 100.0 / total) if total > 0 else 0.0
        with self._lock:
            self._state = {"pct": min(100.0, pct), "eta": 0, "phase": label}

    def on_transfer_progress(self, done: int, total: int):
        pct = (done * 100.0 / total) if total > 0 else 0.0
        with self._lock:
            self._state["pct"] = min(100.0, pct)

    def _run(self):
        while not self._stop.wait(self.INTERVAL):
            with self._lock:
                state = dict(self._state)
            alive = self.client.report_progress(
                self.job_id, state["pct"], state["eta"], state["phase"])
            if not alive:
                self.cancelled.set()
                return


def process_job(client: WorkerClient, job: dict, work_dir: str):
    """Download, encode, and upload a single job."""
    job_id = job["id"]
    file_path = job["file_path"]
    filename = os.path.basename(file_path)
    stem = Path(filename).stem

    print(f"\n{B}{C}═══ Job #{job_id}: {filename} ═══{NC}")

    # One directory per job: two files with the same basename from different
    # library folders would otherwise collide, and a leftover <stem>_opt.mp4
    # would make process_file skip the encode and hand back the stale file.
    job_dir = os.path.join(work_dir, f"job_{job_id}")
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)
    os.makedirs(job_dir, exist_ok=True)

    reporter = JobReporter(client, job_id).start()
    try:
        _run_job(client, job, job_id, filename, stem, job_dir, reporter)
    finally:
        reporter.stop()
        shutil.rmtree(job_dir, ignore_errors=True)


def _is_cancelled(client: WorkerClient, reporter: "JobReporter", job_id: int) -> bool:
    if reporter.cancelled.is_set():
        return True
    # None = the server could not be asked; treat that as "keep going" so a
    # network blip does not throw away a finished encode.
    return client.check_cancelled(job_id) is True


def _run_job(client, job, job_id, filename, stem, job_dir, reporter):
    # 1. Download
    src_path = os.path.join(job_dir, filename)
    print(f"  {C}↓ Downloading...{NC}")
    reporter.set_phase("download")
    client.update_status(job_id, "downloading")

    if not client.download_file(job_id, src_path, on_progress=reporter.on_transfer_progress):
        client.update_status(job_id, "failed", message="Download failed")
        return

    src_size = os.path.getsize(src_path)
    print(f"  {G}✓ Downloaded: {src_size / (1024*1024):.1f} MB{NC}")

    if _is_cancelled(client, reporter, job_id):
        print(f"  {Y}⏹ Job cancelled by user{NC}")
        return

    # 2. Encode
    target_codec = job.get("target_codec", "hevc")
    print(f"  {C}⚡ Encoding with VideoToolbox (codec: {target_codec})...{NC}")
    reporter.set_phase("encode")
    if not client.update_status(job_id, "encoding"):
        print(f"  {Y}⏹ Server dropped the job — stopping{NC}")
        return

    try:
        from videocrunch import ENCODER_PROFILES, detect_encoder, process_file

        encoder_key = detect_encoder()
        if not encoder_key or encoder_key not in ENCODER_PROFILES:
            print(f"  {R}✗ No hardware encoder detected{NC}")
            client.update_status(job_id, "failed", message="No hardware encoder on this Mac")
            return

        # AV1 codec override: map hardware encoder → AV1 variant
        if target_codec == "av1":
            av1_map = {
                "videotoolbox": "av1_software",
                "nvenc": "av1_nvenc",
            }
            av1_key = av1_map.get(encoder_key)
            if av1_key and av1_key in ENCODER_PROFILES:
                print(f"  {Y}🧪 AV1 Experimental: {encoder_key} → {av1_key}{NC}")
                encoder_key = av1_key
            else:
                print(f"  {Y}⚠ AV1 not available for '{encoder_key}', falling back to HEVC{NC}")

        profile = ENCODER_PROFILES[encoder_key]
        print(f"  Using encoder: {profile['name']}")

        opt_path = os.path.join(job_dir, f"{stem}_opt.mp4")

        success, _ = process_file(
            src_path, profile,
            min_size_mb=0,  # No minimum — always encode
            copy_audio=False,
            audio_mode="enhanced",
            video_mode="compress",
            # The job was explicitly queued by a user; skipping it here would
            # surface as a bogus "Encoding failed" upstream.
            force=True,
            progress_callback=reporter.on_encode_progress,
        )

        if not success or not os.path.exists(opt_path):
            print(f"  {R}✗ Encoding failed or no output produced{NC}")
            client.update_status(job_id, "failed", message="Encoding failed")
            return

        opt_size = os.path.getsize(opt_path)
        saved = src_size - opt_size
        print(f"  {G}✓ Encoded: {opt_size/(1024*1024):.1f} MB (saved {saved/(1024*1024):.1f} MB){NC}")

    except ImportError:
        print(f"  {R}✗ videocrunch not found at {_VC_DIR}{NC}")
        client.update_status(job_id, "failed", message="videocrunch not found")
        return
    except Exception as e:
        print(f"  {R}✗ Encoding error: {e}{NC}")
        client.update_status(job_id, "failed", message=f"Encoding error: {e}")
        return

    if _is_cancelled(client, reporter, job_id):
        print(f"  {Y}⏹ Job cancelled by user{NC}")
        return

    # 3. Upload
    print(f"  {C}↑ Uploading optimized file...{NC}")
    reporter.set_phase("upload")
    client.update_status(job_id, "uploading")

    if client.upload_file(job_id, opt_path):
        print(f"  {G}✓ Upload complete!{NC}")
        print(f"{B}{G}═══ Job #{job_id} done ═══{NC}\n")
    else:
        client.update_status(job_id, "failed", message="Upload failed", saved_bytes=saved)


def load_env(env_path=".env"):
    """Minimal .env loader to avoid dependencies."""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception as e:
        print(f"⚠ Failed to load .env: {e}")


def main():
    # Load .env if it exists in current dir, script dir, or project root
    load_env()
    load_env(str(SCRIPT_DIR / ".env"))
    load_env(str(SCRIPT_DIR.parent / ".env"))

    parser = argparse.ArgumentParser(
        description="Mac Encoding Worker — processes remote encoding queue jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 mac_worker.py --server http://192.168.1.100:8000 --user admin --password secret
  python3 mac_worker.py --server http://nas:8000 --poll-interval 60

Environment Variables:
  ARCADE_SERVER, ARCADE_USER, ARCADE_PASSWORD
        """
    )

    env_server = os.environ.get("ARCADE_SERVER")

    parser.add_argument("--server",
                       default=env_server,
                       required=not env_server,
                       help="Arcade server URL (e.g. http://192.168.1.100:8000)")
    parser.add_argument("--user",
                       default=os.environ.get("ARCADE_USER", ""),
                       help="Username for authentication")
    parser.add_argument("--password",
                       default=os.environ.get("ARCADE_PASSWORD", ""),
                       help="Password for authentication")
    parser.add_argument("--poll-interval", type=int, default=30, help="Seconds between polls (default: 30)")
    parser.add_argument("--work-dir", default=os.path.expanduser("~/encoding-queue"),
                       help="Temp directory for downloads (default: ~/encoding-queue)")
    parser.add_argument("--schedule", default=None,
                       help='Only work within this time window, e.g. "01:00-08:00" (overnight windows OK)')
    parser.add_argument("--pause-on-battery", action="store_true",
                       help="Pause polling while the machine runs on battery power (macOS)")

    args = parser.parse_args()

    schedule_window = None
    if args.schedule:
        schedule_window = parse_schedule(args.schedule)
        if schedule_window is None:
            print(f'{R}Invalid --schedule "{args.schedule}" — expected HH:MM-HH:MM{NC}')
            sys.exit(2)

    # Ensure work dir exists
    os.makedirs(args.work_dir, exist_ok=True)

    print(f"\n{B}{C}╔══════════════════════════════════════╗{NC}")
    print(f"{B}{C}║   Mac Encoding Worker v1.0           ║{NC}")
    print(f"{B}{C}╚══════════════════════════════════════╝{NC}")
    print(f"  Server:    {args.server}")
    print(f"  Worker:    {socket.gethostname()}")
    print(f"  Work Dir:  {args.work_dir}")
    print(f"  Poll:      every {args.poll_interval}s")
    if schedule_window:
        print(f"  Schedule:  {args.schedule}")
    if args.pause_on_battery:
        print("  Battery:   pause when unplugged")
    print()

    # Auth — every /api/queue/* endpoint requires a session, so there is no
    # anonymous mode to fall back to.
    if not args.user:
        print(f"{R}✗ No username given. Use --user/--password (or ARCADE_USER/"
              f"ARCADE_PASSWORD) — the queue API rejects anonymous workers.{NC}")
        sys.exit(2)

    try:
        client = WorkerClient(args.server, args.user, args.password)
    except AuthError as e:
        print(f"{R}✗ {e}{NC}")
        sys.exit(1)

    # Main loop
    print(f"{C}Polling for jobs...{NC}")
    while not _shutdown:
        if schedule_window and not is_within_schedule(schedule_window):
            print(f"{Y}⏸  Outside schedule window ({args.schedule}) — sleeping...{NC}", end="\r")
            _sleep_interruptible(args.poll_interval)
            continue
        if args.pause_on_battery and is_on_battery():
            print(f"{Y}🔋 On battery power — paused...{NC}", end="\r")
            _sleep_interruptible(args.poll_interval)
            continue

        job = client.poll_next_job()

        if job:
            process_job(client, job, args.work_dir)
        else:
            # Wait before polling again
            _sleep_interruptible(args.poll_interval)

    print(f"{G}Worker stopped.{NC}")


if __name__ == "__main__":
    main()
