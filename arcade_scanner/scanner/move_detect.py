"""
Erkennt Dateien, die zwischen zwei Scans **umgezogen** sind.

Der Nutzerzustand — Favorit, Vault, Tags — hängt in diesem Projekt am Pfad.
Wer eine Datei im Dateimanager umbenennt oder in einen anderen Ordner schiebt,
sieht für die Bibliothek deshalb aus wie zwei Vorgänge: Eine Datei ist weg,
eine neue ist da. Der Aufräumschritt nach dem Scan löscht daraufhin die alte
Zeile, und der Kommentar dort sagt es selbst — dieser Zustand ist „user state
that no rescan can restore".

Hier wird versucht, das Paar wiederzufinden, **bevor** die alte Zeile
verschwindet. Der Fingerabdruck ist das, was ein Umzug nicht verändert:
Dateigröße, Änderungszeitpunkt und Laufzeit. Der Pfad selbst gehört
ausdrücklich nicht dazu.

Vorsichtig heißt hier: nur **eindeutige** Paare. Passt ein Fingerabdruck auf
mehr als eine verschwundene oder mehr als eine neue Datei, bleibt es beim
bisherigen Verhalten. Ein falsch zugeordnetes Paar würde Tags einer fremden
Datei anhängen; ein nicht erkanntes kostet nur das, was ohnehin verloren war.
"""
from typing import Dict, Optional, Tuple

Fingerprint = Tuple[int, int, int]


def fingerprint_of(entry) -> Optional[Fingerprint]:
    """Der Fingerabdruck eines Eintrags — oder None, wenn er nicht taugt.

    Größe und Änderungszeitpunkt müssen gesetzt sein. Ein Eintrag ohne beides
    (etwa aus einem abgebrochenen Scan) würde sonst mit jedem anderen
    unvollständigen Eintrag „übereinstimmen".

    Die Größe wird auf Bytes gerundet, die Laufzeit auf Millisekunden: Beides
    steht als Fließkommazahl in der Datenbank, und zwei Wege zum selben Wert
    müssen denselben Schlüssel ergeben.
    """
    try:
        size_mb = float(getattr(entry, "size_mb", 0) or 0)
        mtime = int(getattr(entry, "mtime", 0) or 0)
        duration = float(getattr(entry, "duration_sec", 0) or 0)
    except (TypeError, ValueError):
        return None

    if size_mb <= 0 or mtime <= 0:
        return None

    return (round(size_mb * 1024 * 1024), mtime, round(duration * 1000))


def detect_moves(gone: Dict[str, object], arrived: Dict[str, object]) -> Dict[str, str]:
    """Ordnet verschwundene Einträge neu aufgetauchten zu.

    `gone` sind die Einträge, die der Scan nicht mehr gefunden hat, `arrived`
    die, die es vorher nicht gab — beide als `{Pfad: Eintrag}`.

    Zurück kommt `{alter Pfad: neuer Pfad}`, und zwar nur für Fingerabdrücke,
    die auf **beiden** Seiten genau einmal vorkommen.
    """
    if not gone or not arrived:
        return {}

    def index(entries):
        buckets: Dict[Fingerprint, list] = {}
        for path, entry in entries.items():
            fp = fingerprint_of(entry)
            if fp is not None:
                buckets.setdefault(fp, []).append(path)
        return buckets

    alte = index(gone)
    neue = index(arrived)

    moves: Dict[str, str] = {}
    for fp, alte_pfade in alte.items():
        neue_pfade = neue.get(fp)
        if not neue_pfade:
            continue
        if len(alte_pfade) != 1 or len(neue_pfade) != 1:
            # Mehrdeutig: zwei gleich große, gleich alte, gleich lange Dateien.
            # Bei Kopien derselben Datei ist das der Normalfall.
            continue
        moves[alte_pfade[0]] = neue_pfade[0]

    return moves
