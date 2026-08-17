import secrets
import time
from typing import Dict, Optional

# Brute-force protection constants
_MAX_ATTEMPTS = 5          # max failed logins before lockout
_WINDOW_SECONDS = 900      # 15-minute sliding window
_LOCKOUT_SECONDS = 900     # 15-minute lockout


_MAX_FAILED_RECORDS = 4096  # Obergrenze für die Sperrliste, siehe _prune()


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

    def _prune(self, now: float) -> None:
        """Wirft weg, was abgelaufen ist — und deckelt den Rest.

        Beide Schlüssel der Sperrliste kommen aus der Anfrage: die IP aus
        ``X-Forwarded-For`` und der Kontoschlüssel aus dem eingetippten
        Benutzernamen. Ein Eintrag entstand bei jedem Fehlversuch und
        verschwand nur, wenn **derselbe** Schlüssel später eine erfolgreiche
        Anmeldung hatte. Für erfundene Werte passiert das nie.

        Damit konnte jeder, der den Anmeldeport erreicht, den Arbeitsspeicher
        des Servers unbegrenzt wachsen lassen — ohne Konto, mit gewöhnlichen
        Anfragen. Nichts an dieser Liste war je dafür gedacht, länger als eine
        Viertelstunde zu leben; sie wurde nur nie aufgeräumt.

        Zuerst fliegt raus, was ohnehin wirkungslos ist: kein Versuch mehr im
        Zeitfenster und keine laufende Sperre. Reicht das nicht, werden
        **nicht gesperrte** Einträge zuerst verworfen — sie sind bloße Zähler.
        Eine laufende Sperre wegzuwerfen wäre das Loch, das die Sperre
        schließen soll, deshalb kommen sie zuletzt und nach Ablaufzeitpunkt.
        """
        if len(self._failed) < _MAX_FAILED_RECORDS:
            return

        for key in [k for k, r in self._failed.items()
                    if r.get("locked_until", 0) <= now
                    and not [t for t in r.get("attempts", ()) if now - t < _WINDOW_SECONDS]]:
            del self._failed[key]

        if len(self._failed) < _MAX_FAILED_RECORDS:
            return

        # Bis auf drei Viertel herunter, nicht bis genau an die Grenze: Sonst
        # liefe dieser Durchlauf ab jetzt bei **jedem** Fehlversuch, und das
        # wäre eine zweite Art, den Server zu beschäftigen.
        ziel = (_MAX_FAILED_RECORDS * 3) // 4

        def rang(item):
            _, record = item
            gesperrt = record.get("locked_until", 0) > now
            return (gesperrt, record.get("locked_until", 0) or max(
                record.get("attempts") or [0]))

        for key, _ in sorted(self._failed.items(), key=rang)[:len(self._failed) - ziel]:
            del self._failed[key]

    def prune_sessions(self, now: Optional[float] = None) -> int:
        """Entfernt abgelaufene Sitzungen. Zurück kommt ihre Zahl.

        Sitzungen verfielen bisher nur beim nächsten Zugriff auf **ihr**
        Token — ein Token, das niemand mehr benutzt, blieb bis zum Neustart
        liegen. Das ist kein Sicherheitsloch (abgelaufen ist abgelaufen), aber
        es wächst mit.
        """
        now = time.time() if now is None else now
        alt = [t for t, s in self._sessions.items()
               if now - s["created_at"] > self.timeout]
        for token in alt:
            del self._sessions[token]
        return len(alt)

    def record_failure(self, ip: str) -> int:
        """Records a failed login attempt. Returns remaining attempts before lockout."""
        now = time.time()
        self._prune(now)
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
        # Beim Anlegen aufräumen: Anmeldungen sind selten, und nur hier wächst
        # die Liste. Abgelaufene Sitzungen verfielen sonst erst, wenn jemand
        # ihr Token noch einmal vorzeigt — was bei einem vergessenen Gerät nie
        # passiert.
        self.prune_sessions()

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

