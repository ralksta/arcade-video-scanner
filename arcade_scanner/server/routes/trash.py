"""Papierkorb-Routen.

GET  /api/trash          → Einträge, Größe, Restlaufzeit
POST /api/trash/restore  ← {"ids": [...]}
POST /api/trash/empty    ← {"ids": [...]} oder {"all": true}

Löschen aus Duplikat- und Batch-Ansicht landet seit dem Papierkorb hier,
statt endgültig zu verschwinden. Der Papierkorb ist nutzerspezifisch: Ein
Konto sieht nur, was es selbst gelöscht hat; Admins sehen alles.
"""
import json
import os
from typing import Optional

from arcade_scanner.core import trash as trash_core
from arcade_scanner.server.response_helpers import (
    require_auth,
    send_json,
    send_json_error,
)


def _get_deps():
    from arcade_scanner.config import MAX_REQUEST_SIZE
    from arcade_scanner.server.api_handler import db
    from arcade_scanner.server.routes.duplicates import _deletable_scope
    return db, MAX_REQUEST_SIZE, _deletable_scope


def _path_in_scope(path: str, scope: Optional[list[str]]) -> bool:
    """Liegt `path` in einem der erlaubten Verzeichnisse — auch wenn er fehlt?

    Bewusst nicht `is_path_allowed()`: Die Prüfung verlangt, dass der Pfad
    **existiert**. Im Papierkorb ist genau das nicht mehr der Fall — die Datei
    liegt unter `.arcade-trash`, der Eintrag zeigt auf den alten Platz. Mit
    `is_path_allowed` sähe ein normales Konto den eigenen Papierkorb leer.
    Die Zugehörigkeit wurde beim Löschen geprüft, als die Datei noch da war;
    hier genügt die Verzeichnisgrenze.
    """
    if not path or scope is None:
        return True
    from arcade_scanner.security import path_is_within

    candidate = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    return any(
        path_is_within(candidate, os.path.normcase(os.path.realpath(os.path.abspath(root))))
        for root in scope if root
    )


def _read_json_body(handler, max_size: int) -> dict:
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length <= 0:
        raise ValueError("Leerer Request")
    if content_length > max_size:
        raise OverflowError("Request zu groß")
    return json.loads(handler.rfile.read(content_length).decode("utf-8"))


def _visible_entries(user_name: str) -> list[dict]:
    """Einträge, die dieses Konto sehen und zurückholen darf.

    Admins verwalten die Installation und sehen den ganzen Korb. Alle anderen
    sehen nur ihre eigenen Löschungen — die Datei gehört zu ihrem Scan-Ziel,
    alles andere ginge sie nichts an.
    """
    _, _, deletable_scope = _get_deps()
    entries = trash_core.list_entries()
    scope = deletable_scope(user_name)
    if scope is None:
        return entries
    return [
        e for e in entries
        if e.get("deleted_by") == user_name
        and _path_in_scope(e.get("original_path", ""), scope)
    ]


def handle_get(handler) -> bool:
    if not (handler.path == "/api/trash"
            or handler.path.startswith("/api/trash?")):
        return False

    user_name = require_auth(handler)
    if user_name is None:
        return True

    # Abgelaufene Einträge werden beim Zugriff endgültig entfernt — einen
    # Hintergrund-Scheduler gibt es in dieser Anwendung nicht, und beim Start
    # darf die Platte nicht blockieren.
    trash_core.purge_expired(on_purge=trash_core.forget_user_state)

    entries = _visible_entries(user_name)
    for entry in entries:
        # Die vollständige Medienzeile braucht die Oberfläche nicht; sie wird
        # beim Zurückholen serverseitig wieder eingesetzt.
        entry.pop("media_entry", None)

    send_json(handler, {
        "entries": entries,
        "count": len(entries),
        "size": sum(int(e.get("size") or 0) for e in entries),
        "retention_days": trash_core.TRASH_RETENTION_DAYS,
    })
    return True


def handle_post(handler) -> bool:
    if handler.path not in ("/api/trash/restore", "/api/trash/empty"):
        return False

    user_name = require_auth(handler)
    if user_name is None:
        return True

    db, max_size, _ = _get_deps()
    try:
        body = _read_json_body(handler, max_size)
    except OverflowError:
        send_json_error(handler, 413, "Request zu groß")
        return True
    except (ValueError, json.JSONDecodeError) as e:
        send_json_error(handler, 400, f"Ungültiger Request: {e}")
        return True

    visible = {e["id"]: e for e in _visible_entries(user_name)}

    if handler.path == "/api/trash/restore":
        ids = body.get("ids") or []
        if not isinstance(ids, list) or not ids:
            send_json_error(handler, 400, "Keine Einträge angegeben")
            return True

        restored, failed = [], []
        for entry_id in ids:
            entry = visible.get(entry_id)
            if entry is None:
                failed.append({"id": entry_id, "error": "Nicht gefunden"})
                continue

            original = entry.get("original_path", "")
            try:
                trash_core.restore(entry_id)
            except FileNotFoundError:
                failed.append({"id": entry_id, "error": "Datei fehlt im Papierkorb"})
                continue
            except FileExistsError:
                failed.append({"id": entry_id, "error": "Zielpfad ist bereits belegt"})
                continue
            except (KeyError, OSError) as e:
                failed.append({"id": entry_id, "error": str(e)})
                continue

            # Medienzeile aus dem Schnappschuss zurückholen, damit die Datei
            # sofort wieder in der Bibliothek steht statt erst nach einem Scan.
            snapshot = entry.get("media_entry")
            if snapshot:
                try:
                    from arcade_scanner.models.video_entry import VideoEntry
                    db.upsert(VideoEntry(**snapshot))
                except Exception as e:  # noqa: BLE001
                    print(f"⚠️ Medienzeile nach Restore nicht angelegt ({original}): {e!r}")

            restored.append(original)
            print(f"♻️ Aus dem Papierkorb zurückgeholt: {os.path.basename(original)}")

        send_json(handler, {
            "restored": restored,
            "failed": failed,
            "count": len(restored),
        })
        return True

    # /api/trash/empty
    ids = body.get("ids")
    if body.get("all"):
        ids = list(visible)
    if not isinstance(ids, list) or not ids:
        send_json_error(handler, 400, "Keine Einträge angegeben")
        return True

    allowed_ids = []
    rejected = []
    for entry_id in ids:
        entry = visible.get(entry_id)
        if entry is None:
            rejected.append(entry_id)
            continue
        allowed_ids.append(entry_id)

    result = trash_core.purge_ids(
        allowed_ids, on_purge=trash_core.forget_user_state
    )
    print(f"🗑️ Papierkorb geleert: {result['purged']} Datei(en), "
          f"{result['freed'] / (1024 * 1024):.1f} MB")
    send_json(handler, {
        "purged": result["purged"],
        "freed": result["freed"],
        "rejected": rejected,
    })
    return True
