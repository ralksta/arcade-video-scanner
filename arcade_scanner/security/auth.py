import secrets
import time
from typing import Dict, Optional

class SessionManager:
    """
    Simple in-memory session manager.
    """
    def __init__(self):
        self._sessions: Dict[str, dict] = {} # token -> {username, created_at}
        self.timeout = 86400 * 30 # 30 days session

    def create_session(self, username: str) -> str:
        """Creates a new session for the user and returns the token."""
        token = secrets.token_hex(32)
        self._sessions[token] = {
            "username": username,
            "created_at": time.time()
        }
        return token

    def get_username(self, token: str) -> Optional[str]:
        """Returns the username for a valid token, or None."""
        session = self._sessions.get(token)
        if not session:
            return None
        
        # Check timeout
        if time.time() - session["created_at"] > self.timeout:
            del self._sessions[token]
            return None
            
        return session["username"]

    def revoke_session(self, token: str):
        """Invalidates a session."""
        if token in self._sessions:
            del self._sessions[token]

# Global instance
session_manager = SessionManager()
