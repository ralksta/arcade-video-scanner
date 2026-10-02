import hashlib
import logging
import os
import secrets
import sqlite3
import threading
import time
from typing import Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)

# Brute-force protection constants
_MAX_ATTEMPTS = 5          # max failed logins before lockout
_WINDOW_SECONDS = 900      # 15-minute sliding window
_LOCKOUT_SECONDS = 900     # 15-minute lockout


_MAX_FAILED_RECORDS = 4096  # Obergrenze für die Sperrliste, siehe _prune()


class SessionManager:
    """
    Session manager with IP-based brute-force protection.

    Sitzungen leben im Speicher und — wenn ``store_path`` gesetzt ist — auch
    in einer kleinen SQLite-Datei. Bis 2026-10-02 nur im Speicher: Jeder
    Neustart des Servers (Update, Docker-Neustart) meldete alle Geräte ab,
    obwohl eine Sitzung 30 Tage gelten soll. Am Fernseher hiess das, mit der
    Fernbedienung Benutzername und Passwort neu einzutippen.

    In der Datei steht nur der SHA-256 des Tokens, nie das Token selbst: Wer
    sie liest, kann sich damit nicht anmelden.

    Ohne ``store_path`` (Tests, die einen eigenen Manager bauen) bleibt alles
    im Speicher. Scheitert die Datei (Rechte, volle Platte), läuft der Server
    weiter wie früher — eine Anmeldung darf daran nie scheitern.

    Thread-sicher: Der Server ist ein ``ThreadingTCPServer``, jede Anfrage
    läuft in einem eigenen Thread. Ohne Sperre konnten zwei Threads dieselbe
    abgelaufene Sitzung löschen (``KeyError`` → 500), und das Aufräumen
    iterierte über ein Dict, in das ein anderer Thread gerade schrieb
    (``RuntimeError: dictionary changed size during iteration``).
    """
    def __init__(self, store_path: Union[str, Callable[[], str], None] = None):
        # RLock: create_session() ruft prune_sessions(), begin_attempt() und
        # record_failure() rufen _prune() — alle unter derselben Sperre.
        self._lock = threading.RLock()
        # Pfad der Sitzungsdatei, oder eine Funktion, die ihn liefert (erst
        # beim ersten Zugriff ausgewertet — dann steht CONFIG_DIR fest).
        self._store_path = store_path
        self._store_conn: Optional[sqlite3.Connection] = None
        self._sessions: Dict[str, dict] = {}   # token -> {username, created_at}
        self.timeout = 86400 * 30              # 30-day session lifetime
        # ip -> {"attempts": [(timestamp), ...], "locked_until": float}
        self._failed: Dict[str, dict] = {}

    # ── Brute-force helpers ────────────────────────────────────────────────────

    def is_locked_out(self, ip: str) -> bool:
        """Returns True if the IP is currently locked out."""
        with self._lock:
            return self._is_locked_out(ip, time.time())

    def _is_locked_out(self, key: str, now: float) -> bool:
        record = self._failed.get(key)
        if not record:
            return False
        if record.get("locked_until", 0) > now:
            return True
        # Expunge stale lock
        record.pop("locked_until", None)
        return False

    def begin_attempt(self, *keys: str) -> bool:
        """Prüft die Sperre und zählt den Versuch — in einem Schritt.

        Die Route prüfte erst ``is_locked_out()``, dann das Passwort, und erst
        danach zählte ``record_failure()`` den Fehlschlag. Dazwischen liegt
        PBKDF2 mit 100.000 Runden, und ``hashlib`` gibt dabei die GIL frei.
        Parallele Anfragen sahen also alle „nicht gesperrt", bevor die erste
        mitgezählt war: Gemessen kamen 40 von 40 gleichzeitigen Versuchen
        durch, bei einer Grenze von fünf. Die Sperre galt nur für Angreifer,
        die höflich nacheinander raten.

        Deshalb wird jetzt **vor** der Prüfung gezählt. Ein erfolgreicher
        Versuch löscht seinen Zähler danach über ``record_success()`` — für
        einen Nutzer, der sich nacheinander anmeldet, ändert sich nichts.

        Gibt False zurück, wenn eine der Kennungen gesperrt ist; dann wird
        nichts gezählt.
        """
        with self._lock:
            now = time.time()
            if any(self._is_locked_out(key, now) for key in keys):
                return False
            for key in keys:
                self._count_attempt(key, now)
            return True

    def remaining_attempts(self, *keys: str) -> int:
        """Wie viele Versuche bleiben, bis die strengste Kennung sperrt."""
        with self._lock:
            now = time.time()
            counts = [
                len([t for t in self._failed.get(key, {}).get("attempts", ())
                     if now - t < _WINDOW_SECONDS])
                for key in keys
            ]
            return max(0, _MAX_ATTEMPTS - max(counts, default=0))

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
        with self._lock:
            now = time.time() if now is None else now
            alt = [t for t, s in self._sessions.items()
                   if now - s["created_at"] > self.timeout]
            for token in alt:
                del self._sessions[token]
            self._db_write("DELETE FROM sessions WHERE created_at < ?", (now - self.timeout,))
            return len(alt)

    def _count_attempt(self, key: str, now: float) -> int:
        """Zählt einen Versuch für ``key``. Nur unter ``self._lock`` aufrufen."""
        self._prune(now)
        record = self._failed.setdefault(key, {"attempts": []})

        # Trim attempts outside the sliding window
        record["attempts"] = [t for t in record["attempts"] if now - t < _WINDOW_SECONDS]
        record["attempts"].append(now)

        count = len(record["attempts"])
        if count >= _MAX_ATTEMPTS:
            record["locked_until"] = now + _LOCKOUT_SECONDS
            print(f"🔒 Login lockout triggered for {key} after {count} attempts")
        return count

    def record_failure(self, ip: str) -> int:
        """Records a failed login attempt. Returns remaining attempts before lockout."""
        with self._lock:
            count = self._count_attempt(ip, time.time())
            return max(0, _MAX_ATTEMPTS - count)

    def record_success(self, ip: str) -> None:
        """Clears failure history on successful login."""
        with self._lock:
            self._failed.pop(ip, None)

    # ── Sitzungsdatei ──────────────────────────────────────────────────────────

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _db(self) -> Optional[sqlite3.Connection]:
        """Verbindung zur Sitzungsdatei, oder None (aus / nicht nutzbar).

        Nur unter ``self._lock`` aufrufen.
        """
        if self._store_conn is not None or not self._store_path:
            return self._store_conn
        path = self._store_path() if callable(self._store_path) else self._store_path
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sessions ("
                " token_hash TEXT PRIMARY KEY,"
                " username TEXT NOT NULL,"
                " created_at REAL NOT NULL)")
            conn.commit()
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            self._store_conn = conn
        except (OSError, sqlite3.Error) as e:
            logger.warning("Sitzungsdatei %s nicht nutzbar, nur im Speicher: %s", path, e)
            self._store_path = None
        return self._store_conn

    def _db_write(self, sql: str, args: tuple) -> None:
        """Schreibt in die Sitzungsdatei; Fehler werden geloggt, nie geworfen."""
        conn = self._db()
        if conn is None:
            return
        try:
            conn.execute(sql, args)
            conn.commit()
        except sqlite3.Error as e:
            logger.warning("Sitzungsdatei: %s", e)

    def _db_lookup(self, token: str) -> Optional[dict]:
        conn = self._db()
        if conn is None:
            return None
        try:
            row = conn.execute(
                "SELECT username, created_at FROM sessions WHERE token_hash = ?",
                (self._hash(token),)).fetchone()
        except sqlite3.Error as e:
            logger.warning("Sitzungsdatei: %s", e)
            return None
        return {"username": row[0], "created_at": row[1]} if row else None

    # ── Session helpers ────────────────────────────────────────────────────────

    def create_session(self, username: str) -> str:
        """Creates a new session for the user and returns the token."""
        with self._lock:
            # Beim Anlegen aufräumen: Anmeldungen sind selten, und nur hier
            # wächst die Liste. Abgelaufene Sitzungen verfielen sonst erst,
            # wenn jemand ihr Token noch einmal vorzeigt — was bei einem
            # vergessenen Gerät nie passiert.
            self.prune_sessions()

            token = secrets.token_hex(32)
            now = time.time()
            self._sessions[token] = {
                "username": username,
                "created_at": now,
            }
            self._db_write(
                "INSERT OR REPLACE INTO sessions (token_hash, username, created_at)"
                " VALUES (?, ?, ?)", (self._hash(token), username, now))
            return token

    def get_username(self, token: str) -> Optional[str]:
        """Returns the username for a valid token, or None."""
        with self._lock:
            session = self._sessions.get(token)
            if not session and token:
                # Nach einem Neustart: aus der Datei holen und merken.
                session = self._db_lookup(token)
                if session:
                    self._sessions[token] = session
            if not session:
                return None
            if time.time() - session["created_at"] > self.timeout:
                self.revoke_session(token)
                return None
            return session["username"]

    def revoke_session(self, token: str) -> None:
        """Invalidates a session."""
        with self._lock:
            self._sessions.pop(token, None)
            if token:
                self._db_write("DELETE FROM sessions WHERE token_hash = ?", (self._hash(token),))


def _default_store_path() -> str:
    # Erst beim ersten Zugriff importiert: config liest CONFIG_DIR, und der
    # Testlauf für anonyme Routen setzt es vor dem Start des Servers um.
    from arcade_scanner.config import config
    return os.path.join(config.hidden_data_dir, "sessions.db")


# Global instance — mit Sitzungsdatei, damit ein Neustart niemanden abmeldet.
session_manager = SessionManager(store_path=_default_store_path)

