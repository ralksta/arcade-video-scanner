"""Papierkorb für ausdrücklich gelöschte Medien.

Duplikat- und Batch-Löschungen waren bisher endgültig: ``os.remove()`` und
danach war die Datei weg. Ein Fehlklick in einer Ansicht mit tausenden
Duplikatgruppen kostete das Original. Jetzt wandert die Datei stattdessen in
einen versteckten Ordner ``.arcade-trash`` und ein Index merkt sich den
ursprünglichen Pfad, den Datenbank-Eintrag und wer gelöscht hat.

Warum nicht ein zentraler Ordner unter ``arcade_data``: Eine 8-GB-Datei auf
eine andere Platte zu *kopieren*, nur um sie in den Papierkorb zu legen,
kostet Zeit und Platz. ``.arcade-trash`` liegt deshalb im obersten passenden
Scan-Ziel — auf derselben Platte wie die Datei, sodass das Verschieben ein
Rename ist. Nur wenn kein Ziel passt, fällt der Korb auf
``arcade_data/trash`` zurück (dann kopiert ``shutil.move`` notfalls).

Der Index ist JSON, nicht SQLite: Er muss auch dann noch lesbar sein, wenn
die Hauptdatenbank gerade neu aufgebaut wird. Die Datei selbst bleibt die
Wahrheit — ein verlorener Index kostet die Bequemlichkeit, nicht das Video.
"""
from __future__ import annotations

import errno
import json
import logging
import os
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

from arcade_scanner.config import TRASH_DIRNAME, TRASH_RETENTION_DAYS, config

logger = logging.getLogger(__name__)

# Die Index-Datei wird von mehreren Threads gleichzeitig gelesen und
# fortgeschrieben. Ohne Sperre gewinnt der letzte Schreiber und verliert die
# Einträge der anderen.
_LOCK = threading.RLock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _index_path(index_path: Optional[str] = None) -> str:
    return index_path or os.path.join(config.hidden_data_dir, "trash_index.json")


def _load(index_path: Optional[str] = None) -> dict:
    path = _index_path(index_path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        # Ein kaputter Index darf den Papierkorb nicht unbenutzbar machen:
        # Die Dateien liegen weiterhin im Korb, nur ohne Beschreibung.
        print(f"⚠️ Papierkorb-Index unlesbar ({e!r}) — behandle ihn als leer")
        return {}
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def _save(entries: dict, index_path: Optional[str] = None) -> None:
    path = _index_path(index_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}-{threading.get_ident()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "entries": entries}, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _parse_time(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _move(src: str, dst: str) -> None:
    """Verschiebt eine Datei, notfalls über Dateisystemgrenzen hinweg."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.replace(src, dst)
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
        # Andere Platte: shutil.move kopiert und löscht die Quelle erst nach
        # erfolgreichem Kopieren — ein Abbruch lässt das Original stehen.
        shutil.move(src, dst)


def _pick_root(abs_path: str, roots: Iterable[str]) -> Optional[str]:
    """Oberstes Scan-Ziel, das den Pfad enthält und auf derselben Platte liegt.

    Nur dann ist das Verschieben ein Rename. Lieber der zentrale Korb mit
    Kopie als ein Rename über eine Dateisystemgrenze, das ohnehin scheitert.
    """
    best = None
    try:
        file_dev = os.stat(abs_path).st_dev
    except OSError:
        return None

    for raw_root in roots or []:
        if not raw_root:
            continue
        root = os.path.realpath(os.path.abspath(os.path.expanduser(raw_root)))
        candidate = os.path.realpath(abs_path)
        if not (candidate == root or candidate.startswith(root.rstrip(os.sep) + os.sep)):
            continue
        if best is not None and len(root) <= len(best):
            continue
        try:
            if os.stat(root).st_dev != file_dev:
                continue
        except OSError:
            continue
        best = root
    return best


def _trash_location(abs_path: str, roots: Iterable[str],
                    fallback_dir: Optional[str]) -> str:
    root = _pick_root(abs_path, roots)
    if root:
        return os.path.join(root, TRASH_DIRNAME)
    if fallback_dir:
        return fallback_dir
    return os.path.join(config.hidden_data_dir, "trash")


def move_to_trash(path: str, *, deleted_by: str, roots: Iterable[str] = (),
                  media_entry: Optional[dict] = None, reason: str = "",
                  index_path: Optional[str] = None,
                  fallback_dir: Optional[str] = None) -> dict:
    """Legt eine Datei in den Papierkorb und gibt ihren Index-Eintrag zurück.

    Der Index wird *vor* dem Verschieben geschrieben. Bricht der Prozess
    dazwischen ab, steht dort ein Eintrag mit fehlender Datei — unschön, aber
    sichtbar. Die umgekehrte Reihenfolge hinterließe eine Datei im Korb, die
    niemand mehr zuordnen kann.

    Raises:
        FileNotFoundError: Die Datei existiert nicht (mehr).
        OSError: Verschieben oder Index-Schreiben ist fehlgeschlagen.
    """
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(abs_path)

    entry_id = f"{_now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    trash_root = _trash_location(abs_path, roots, fallback_dir)
    dest_dir = os.path.join(trash_root, entry_id)
    dest = os.path.join(dest_dir, os.path.basename(abs_path))

    entry = {
        "id": entry_id,
        "original_path": abs_path,
        "trash_path": dest,
        "size": os.path.getsize(abs_path),
        "deleted_at": _now_iso(),
        "deleted_by": deleted_by,
        "reason": reason,
        "media_entry": media_entry,
    }

    with _LOCK:
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as e:
            central = fallback_dir or os.path.join(config.hidden_data_dir, "trash")
            if os.path.abspath(trash_root) == os.path.abspath(central):
                raise
            # Das Scan-Ziel ist nicht beschreibbar (z. B. eine read-only
            # Wurzel, unter der nur die Unterordner offen sind). Lieber in
            # den zentralen Korb kopieren als das Löschen ganz scheitern zu
            # lassen — die Datei bleibt in beiden Fällen erhalten.
            print(f"⚠️ Papierkorb in {trash_root} nicht anlegbar ({e!r}); "
                  f"nutze {central}")
            trash_root = central
            dest_dir = os.path.join(trash_root, entry_id)
            dest = os.path.join(dest_dir, os.path.basename(abs_path))
            entry["trash_path"] = dest
            os.makedirs(dest_dir, exist_ok=True)

        entries = _load(index_path)
        entries[entry_id] = entry
        try:
            _save(entries, index_path)
            _move(abs_path, dest)
        except Exception:
            # Nichts wurde bewegt: Den Index wieder aufräumen, damit kein
            # Geistereintrag zurückbleibt.
            entries.pop(entry_id, None)
            try:
                _save(entries, index_path)
                os.rmdir(dest_dir)
            except OSError as e:
                logger.debug("Leerer Papierkorb-Ordner %s blieb stehen: %s", dest_dir, e)
            raise
    return entry


def restore(entry_id: str, *, index_path: Optional[str] = None) -> dict:
    """Holt eine Datei an ihren ursprünglichen Platz zurück.

    Raises:
        KeyError: Kein Eintrag mit dieser ID.
        FileNotFoundError: Die Datei im Korb fehlt.
        FileExistsError: Am Zielpfad liegt inzwischen eine andere Datei. Sie
            wird nicht überschrieben — welcher von beiden die richtige ist,
            kann der Server nicht entscheiden.
        OSError: Verschieben fehlgeschlagen.
    """
    with _LOCK:
        entries = _load(index_path)
        entry = entries.get(entry_id)
        if not entry:
            raise KeyError(entry_id)

        src = entry["trash_path"]
        dst = entry["original_path"]
        if not os.path.exists(src):
            raise FileNotFoundError(src)
        if os.path.exists(dst):
            raise FileExistsError(dst)

        _move(src, dst)
        try:
            os.rmdir(os.path.dirname(src))
        except OSError as e:
            logger.debug("Leerer Papierkorb-Ordner %s blieb stehen: %s", src, e)

        del entries[entry_id]
        _save(entries, index_path)
        return entry


def _remove_thumbnail(original_path: str) -> None:
    try:
        from arcade_scanner.core.video_processor import remove_thumbnail_for
        remove_thumbnail_for(original_path)
    except Exception as e:  # noqa: BLE001 — Aufräumen darf das Löschen nicht kippen
        print(f"⚠️ Vorschaubild nicht entfernt ({original_path}): {e!r}")


def purge_ids(ids: Iterable[str], *, index_path: Optional[str] = None,
              on_purge: Optional[Callable[[list[str]], None]] = None) -> dict:
    """Löscht die genannten Einträge endgültig (Datei und Vorschaubild)."""
    purged: list[str] = []
    freed = 0

    with _LOCK:
        entries = _load(index_path)
        for entry_id in list(ids):
            entry = entries.get(entry_id)
            if not entry:
                continue
            trash_path = entry.get("trash_path") or ""
            try:
                if trash_path and os.path.exists(trash_path):
                    os.remove(trash_path)
                if trash_path:
                    try:
                        os.rmdir(os.path.dirname(trash_path))
                    except OSError as e:
                        logger.debug("Leerer Papierkorb-Ordner %s blieb stehen: %s",
                                     trash_path, e)
            except OSError as e:
                # Eintrag stehen lassen: Beim nächsten Versuch klappt es
                # vielleicht, und bis dahin ist die Datei noch da.
                print(f"⚠️ Papierkorb-Eintrag nicht gelöscht ({trash_path}): {e!r}")
                continue

            entries.pop(entry_id, None)
            purged.append(entry.get("original_path") or "")
            freed += int(entry.get("size") or 0)

        if purged:
            _save(entries, index_path)

    for original in purged:
        _remove_thumbnail(original)
    if purged and on_purge:
        try:
            on_purge([p for p in purged if p])
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Nutzerzustand nach Papierkorb-Löschung nicht aufgeräumt: {e!r}")

    return {"purged": len(purged), "freed": freed, "paths": purged}


def purge_expired(days: Optional[int] = None, *,
                  index_path: Optional[str] = None,
                  on_purge: Optional[Callable[[list[str]], None]] = None,
                  now: Optional[datetime] = None) -> dict:
    """Löscht Einträge, die älter als die Aufbewahrungsfrist sind.

    Wird beim Start und bei jedem Abruf des Papierkorbs aufgerufen. Einen
    Hintergrund-Scheduler gibt es in dieser Anwendung bewusst nicht.
    """
    retention = TRASH_RETENTION_DAYS if days is None else days
    cutoff = (now or _now()) - timedelta(days=retention)

    with _LOCK:
        entries = _load(index_path)
    expired = []
    for entry_id, entry in entries.items():
        deleted_at = _parse_time(entry.get("deleted_at", ""))
        if deleted_at is not None and deleted_at < cutoff:
            expired.append(entry_id)
    return purge_ids(expired, index_path=index_path, on_purge=on_purge)


def empty(*, index_path: Optional[str] = None,
          on_purge: Optional[Callable[[list[str]], None]] = None) -> dict:
    """Löscht den gesamten Papierkorb endgültig."""
    with _LOCK:
        ids = list(_load(index_path))
    return purge_ids(ids, index_path=index_path, on_purge=on_purge)


def list_entries(*, index_path: Optional[str] = None) -> list[dict]:
    """Alle Einträge, neueste zuerst — mit Restlaufzeit für die Oberfläche."""
    now = _now()
    with _LOCK:
        entries = list(_load(index_path).values())

    result = []
    for entry in entries:
        deleted_at = _parse_time(entry.get("deleted_at", ""))
        days_left = None
        if deleted_at is not None:
            expires = deleted_at + timedelta(days=TRASH_RETENTION_DAYS)
            days_left = max(0, (expires - now).days)
        item = dict(entry)
        item["name"] = os.path.basename(entry.get("original_path") or "")
        item["folder"] = os.path.dirname(entry.get("original_path") or "")
        item["days_left"] = days_left
        result.append(item)

    result.sort(key=lambda e: e.get("deleted_at", ""), reverse=True)
    return result


def forget_user_state(paths: Iterable[str]) -> None:
    """Räumt Favoriten, Tags, Fortschritt und Auto-Tag-Buchführung auf.

    Erst beim *endgültigen* Löschen, nicht beim Verschieben in den Korb: Eine
    zurückgeholte Datei soll ihre Favoriten und Tags behalten. Das ist der
    Unterschied zur alten, sofortigen Löschung.
    """
    cleaned = [p for p in paths if p]
    if not cleaned:
        return
    try:
        from arcade_scanner.database import db, user_db

        removed = user_db.purge_paths_from_user_data(cleaned)
        # Muss mit: Der Auto-Tagger vergibt jeden Tag nur einmal je Pfad.
        # Bliebe seine Buchführung stehen, während die Tags verschwinden,
        # bekäme eine später unter demselben Pfad entstehende Datei nie
        # wieder einen Tag.
        forgotten = db.forget_auto_tag_paths(cleaned)
        if removed or forgotten:
            print(f"🧹 {removed} verwaiste Favoriten/Tags-Einträge entfernt, "
                  f"{forgotten} Auto-Tag-Vermerke vergessen")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Nutzerzustand konnte nicht aufgeräumt werden: {e}")
