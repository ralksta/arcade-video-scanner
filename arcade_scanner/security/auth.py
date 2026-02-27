import secrets
import time
from typing import Dict, Optional

# Brute-force protection constants
_MAX_ATTEMPTS = 5          # max failed logins before lockout
_WINDOW_SECONDS = 900      # 15-minute sliding window
_LOCKOUT_SECONDS = 900     # 15-minute lockout


class SessionManager:
    """
    In-memory session manager with IP-based brute-force protection.
    """
    def __init__(self):
        self._sessions: Dict[str, dict] = {}   # token -> {username, created_at}
        self.timeout = 86400 * 30              # 30-day session lifetime
        # ip -> {"attempts": [(timestamp), ...], "locked_until": float}
        self._failed: Dict[str, dict] = {}

    # ── Brute-force helpers ────────────────────────────────────────────────────

    def is_locked_out(self, ip: str) -> bool:
        """Returns True if the IP is currently locked out."""
        record = self._failed.get(ip)
        if not record:
            return False
        if record.get("locked_until", 0) > time.time():
            return True
        # Expunge stale lock
        record.pop("locked_until", None)
        return False

    def record_failure(self, ip: str) -> int:
        """Records a failed login attempt. Returns remaining attempts before lockout."""
        now = time.time()
        record = self._failed.setdefault(ip, {"attempts": []})

        # Trim attempts outside the sliding window
        record["attempts"] = [t for t in record["attempts"] if now - t < _WINDOW_SECONDS]
        record["attempts"].append(now)

        count = len(record["attempts"])
        if count >= _MAX_ATTEMPTS:
            record["locked_until"] = now + _LOCKOUT_SECONDS
            print(f"🔒 Login lockout triggered for IP {ip} after {count} failures")
        return max(0, _MAX_ATTEMPTS - count)

    def record_success(self, ip: str) -> None:
        """Clears failure history on successful login."""
        self._failed.pop(ip, None)

    # ── Session helpers ────────────────────────────────────────────────────────

    def create_session(self, username: str) -> str:
        """Creates a new session for the user and returns the token."""
        token = secrets.token_hex(32)
        self._sessions[token] = {
            "username": username,
            "created_at": time.time(),
        }
        return token

    def get_username(self, token: str) -> Optional[str]:
        """Returns the username for a valid token, or None."""
        session = self._sessions.get(token)
        if not session:
            return None
        if time.time() - session["created_at"] > self.timeout:
            del self._sessions[token]
            return None
        return session["username"]

    def revoke_session(self, token: str) -> None:
        """Invalidates a session."""
        self._sessions.pop(token, None)


# Global instance
session_manager = SessionManager()

