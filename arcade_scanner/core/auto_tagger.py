# arcade_scanner/core/auto_tagger.py
"""Auto-tagging rule engine — applies Smart-Collection-style rules as tags.

Apply-once semantics: (user, rule, path) triples that were tagged once are
recorded in auto_tag_applied and never re-tagged, so manual tag removal is
final. Runs after every scan (run_post_scan_auto_tagging) and on demand via
POST /api/autotag/run.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .criteria_eval import video_matches

logger = logging.getLogger(__name__)

DEFAULT_TAG_COLOR = "#22c55e"


def _ensure_tag_definition(user: Any, tag: str) -> None:
    if any(t.get("name") == tag for t in user.data.available_tags):
        return
    user.data.available_tags.append({"name": tag, "color": DEFAULT_TAG_COLOR, "shortcut": ""})


def run_auto_tag_rules(username: str, *, user_db: Any, media_db: Any,
                       now: Optional[int] = None) -> dict[str, int]:
    """Apply the user's enabled rules. Returns {rule_id: newly_tagged_count}."""
    if now is None:
        now = int(time.time())

    user = user_db.get_user(username)
    if user is None:
        return {}
    rules = [r for r in user.data.auto_tag_rules if r.get("enabled")]
    if not rules:
        return {}

    videos = media_db.get_all_dicts()
    vaulted = set(user.data.vaulted)
    favorites = set(user.data.favorites)
    counts: dict[str, int] = {}
    changed = False

    for rule in rules:
        rule_id = str(rule.get("id") or "")
        tag = str(rule.get("tag") or "")
        if not rule_id or not tag:
            continue
        applied = media_db.get_auto_tag_applied(username, rule_id)
        newly: list[str] = []
        for video in videos:
            path = str(video.get("FilePath") or "")
            if not path or path in applied:
                continue
            effective = {**video,
                         "tags": user.data.tags.get(path, []),
                         "favorite": path in favorites,
                         "hidden": path in vaulted}
            if not video_matches(effective, rule.get("criteria"), now=now):
                continue
            current = user.data.tags.setdefault(path, [])
            if tag not in current:
                current.append(tag)
            newly.append(path)
        if newly:
            _ensure_tag_definition(user, tag)
            media_db.mark_auto_tag_applied(username, rule_id, newly)
            changed = True
        counts[rule_id] = len(newly)

    if changed:
        # Bewusst `add_user()` und nicht `update_user()`.
        #
        # Der Lauf liest den Nutzer ganz oben, geht dann über die gesamte
        # Bibliothek und schreibt hier zurück. Dieses Fenster mit einer Sperre
        # zu schliessen hiesse, sie über einen kompletten Durchlauf zu halten —
        # jede Anfrage aus dem Browser stünde so lange still.
        #
        # `update_user()` mit einem Änderer, der die Felder aus diesem Objekt
        # in den frisch gelesenen kopiert, sähe nach einer Lösung aus, ist aber
        # keine: Er würde die zwischenzeitliche Änderung eines Nutzers
        # trotzdem überschreiben, nur weniger sichtbar.
        #
        # Was hier stattdessen gilt: Der Lauf startet nach dem Scan, also zu
        # einem Zeitpunkt, an dem üblicherweise niemand zusieht. Und er hängt
        # Tags an, statt Felder zu ersetzen. Wer das sauber lösen will, braucht
        # ein Schreiben pro Pfad statt eines Schreibens pro Lauf.
        user_db.add_user(user)  # upsert; exactly one write per run
    return counts


def run_post_scan_auto_tagging(*, user_db: Any = None, media_db: Any = None) -> None:
    """Run all users' rules after a scan. Defensive: never raises."""
    try:
        if user_db is None:
            from ..database import user_db as _udb
            user_db = _udb
        if media_db is None:
            from ..database import db as _db
            media_db = _db
        for user in user_db.get_all_users():
            if not any(r.get("enabled") for r in user.data.auto_tag_rules):
                continue
            try:
                counts = run_auto_tag_rules(user.username, user_db=user_db, media_db=media_db)
                total = sum(counts.values())
                if total:
                    print(f"🏷️ Auto-Tagging: {total} neue Tags für {user.username}")
            except Exception:
                logger.exception("Auto-tagging failed for user %s", user.username)
    except Exception:
        logger.exception("Auto-tagging post-scan run failed")
