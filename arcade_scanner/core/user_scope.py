"""Welche Pfade darf ein Konto sehen?

Diese Frage wird an mehreren Stellen gestellt — beim Ausliefern der Bibliothek,
beim Duplikat-Scan, bei der Ähnlichkeitssuche und bei den
Optimierungs-Vorschlägen. Sie wurde an jeder Stelle einzeln beantwortet, und
zweimal gar nicht: `/api/similar` und `/api/candidates` lieferten Treffer aus
dem gesamten Bestand, also auch aus den Scan-Zielen anderer Konten — mit vollem
Pfad, Größe und Vorschaubild.

Bei den Vorschlägen wiegt das schwerer als eine Preisgabe: Aus dieser Liste
heraus wird eingereiht, und Einreihen heißt, dass die Datei am Ende **ersetzt**
wird.

Die Regel stammt aus `/api/videos` und wird hier nur zusammengefasst, nicht neu
erfunden::

    Ziele eingerichtet          -> nur Dateien darunter
    keine Ziele, Konto ist Admin -> alles
    keine Ziele, sonst           -> nichts

Der Sonderfall „Einträge im Prüfmodus sind immer sichtbar" bleibt dort, wo er
hingehört (api_handler): Er betrifft die Anzeige der Bibliothek, nicht die
Frage, wessen Dateien ein Konto bearbeiten darf.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from arcade_scanner.security import path_is_within


def visible_path_filter(user: Any) -> Callable[[str], bool]:
    """Prädikat: Darf dieser Nutzer diesen Pfad sehen?

    `user` ist ein `User`-Objekt oder None. **None ergibt ein Prädikat, das
    nichts durchlässt** — wenn der Datensatz nicht lesbar ist, ist weder
    bekannt, was im Vault liegt, noch welche Verzeichnisse dem Konto gehören.
    Beides fiele sonst in die offene Richtung aus.
    """
    if user is None:
        return lambda _path: False

    targets = [os.path.abspath(t) for t in (getattr(user.data, "scan_targets", None) or []) if t]

    if not targets:
        allow_all = bool(getattr(user, "is_admin", False))
        return lambda _path: allow_all

    return lambda path: any(path_is_within(path, t) for t in targets)
