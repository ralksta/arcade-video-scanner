"""
test_cache_invalidation_race.py
-------------------------------
Eine Änderung, die während einer laufenden Anfrage passiert, ging verloren.

`_MediaCache.get()` liest die Datenbank **außerhalb** des Locks — richtig so,
sonst stünde jede andere Anfrage währenddessen. Das Ergebnis wurde danach aber
bedingungslos abgelegt:

    Anfrage A: get() → Cache leer → liest die Datenbank
    Anfrage B: löscht eine Datei → invalidate()
    Anfrage A: schreibt das *alte* Ergebnis in den Cache

Die Invalidierung dazwischen war damit wirkungslos. Für den Medien-Cache hieß
das bis zu 30 Sekunden alte Daten. Für den daraus abgeleiteten
`/api/videos`-Cache hieß es **für immer**: Der hat keine Verfallszeit, er lebt
allein von der Invalidierung — bis zum nächsten Schreibvorgang bekamen alle
Clients mit demselben Ziel-Satz die überholte Bibliothek.

Der Haushalt ist genau die Umgebung, in der das passiert: Der Fernseher fragt
regelmäßig `/api/videos` ab, während im Browser gelöscht, getaggt oder
optimiert wird.

Ein Zähler macht es entscheidbar. Er wird bei jeder Invalidierung erhöht; wer
außerhalb des Locks gelesen hat, legt nur ab, wenn er unverändert ist. Die
Antwort selbst geht trotzdem hinaus — sie ist dann so alt wie der Augenblick,
in dem sie begonnen wurde, und das ist unvermeidlich.
"""
import gzip
import json
import threading
from unittest.mock import patch

import pytest

from arcade_scanner.server.api_handler import _MediaCache, _VideosResponseCache


@pytest.fixture
def cache():
    return _MediaCache()


# --- Der Fund ---

def test_a_change_during_the_read_is_not_overwritten(cache):
    """
    Der Kern: Wer beim Lesen überholt wurde, legt nichts ab.
    """
    def liest_und_wird_ueberholt():
        cache.invalidate()          # B löscht, während A liest
        return [{"FilePath": "/media/alt.mp4"}]

    with patch("arcade_scanner.server.api_handler.db.get_all_dicts",
               side_effect=liest_und_wird_ueberholt):
        cache.get()

    assert cache._data is None, "Der überholte Stand liegt im Cache"


def test_the_next_request_reads_fresh_again(cache):
    """
    Die Folge, auf die es ankommt: Der nächste Aufruf geht wieder an die
    Datenbank, statt den überholten Stand auszuliefern.
    """
    aufrufe = []

    def erster_lauf():
        aufrufe.append(1)
        if len(aufrufe) == 1:
            cache.invalidate()
            return [{"FilePath": "/media/alt.mp4"}]
        return [{"FilePath": "/media/neu.mp4"}]

    with patch("arcade_scanner.server.api_handler.db.get_all_dicts",
               side_effect=erster_lauf):
        cache.get()
        zweite = cache.get()

    assert zweite == [{"FilePath": "/media/neu.mp4"}]
    assert len(aufrufe) == 2


def test_an_undisturbed_read_is_cached(cache):
    """Die Gegenprobe — ohne Störung muss der Cache weiterhin greifen."""
    with patch("arcade_scanner.server.api_handler.db.get_all_dicts",
               return_value=[{"FilePath": "/media/a.mp4"}]) as gelesen:
        cache.get()
        cache.get()

    assert gelesen.call_count == 1


def test_the_answer_is_still_returned(cache):
    """
    Nicht abzulegen heißt nicht, nichts zu antworten. Der Aufrufer bekommt,
    was er gelesen hat.
    """
    with patch("arcade_scanner.server.api_handler.db.get_all_dicts",
               side_effect=lambda: (cache.invalidate(),
                                    [{"FilePath": "/media/a.mp4"}])[1]):
        ergebnis = cache.get()

    assert ergebnis == [{"FilePath": "/media/a.mp4"}]


# --- Der Zähler ---

def test_every_invalidation_advances_the_version(cache):
    vorher = cache.version()

    cache.invalidate()
    cache.invalidate()

    assert cache.version() == vorher + 2


def test_the_version_comes_back_with_the_data(cache):
    with patch("arcade_scanner.server.api_handler.db.get_all_dicts",
               return_value=[]):
        version, _ = cache.get_with_version()

    assert version == cache.version()


# --- Der abgeleitete Cache ---

def test_a_response_from_an_outdated_state_is_not_served():
    """
    Der schwerere Teil des Fundes: Dieser Cache hat keine Verfallszeit. Ein
    Eintrag aus einem überholten Stand bliebe bis zum nächsten Schreibvorgang
    stehen — beliebig lange.
    """
    antworten = _VideosResponseCache()
    roh = json.dumps([{"FilePath": "/media/alt.mp4"}]).encode()

    antworten.put(("ziel",), roh, gzip.compress(roh), version=3)

    assert antworten.get(("ziel",), 3) is not None
    assert antworten.get(("ziel",), 4) is None


def test_without_a_version_everything_is_served():
    """Für Aufrufer, die keinen Stand mitgeben — das Verhalten von vorher."""
    antworten = _VideosResponseCache()
    roh = b"[]"

    antworten.put(("ziel",), roh, gzip.compress(roh), version=3)

    assert antworten.get(("ziel",)) is not None


def test_invalidating_still_clears_everything():
    antworten = _VideosResponseCache()
    antworten.put(("ziel",), b"[]", b"", version=1)

    antworten.invalidate()

    assert antworten.get(("ziel",), 1) is None


def test_the_endpoint_passes_the_version_through():
    """
    Der Zähler nützt nichts, wenn ihn die Route nicht durchreicht — dann
    prüft der Cache gegen einen Wert, den niemand setzt.
    """
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "server"
              / "api_handler.py").read_text(encoding="utf-8")

    assert "_videos_response_cache.get(cache_key, _media_cache.version())" in quelle
    assert "media_version, all_entries = _media_cache.get_with_version()" in quelle
    assert "_videos_response_cache.put(cache_key, raw, gzipped, media_version)" in quelle


# --- Unter echten Threads ---

def test_it_holds_up_with_real_threads(cache):
    """
    Nicht nur die nachgestellte Verschränkung: zehn Leser, zehn Schreiber,
    gleichzeitig. Danach darf im Cache nichts liegen, was älter ist als die
    letzte Invalidierung.
    """
    stand = {"wert": [{"FilePath": "/media/a.mp4"}]}

    def liest():
        with patch("arcade_scanner.server.api_handler.db.get_all_dicts",
                   side_effect=lambda: list(stand["wert"])):
            for _ in range(20):
                cache.get()

    def schreibt():
        for i in range(20):
            stand["wert"] = [{"FilePath": f"/media/{i}.mp4"}]
            cache.invalidate()

    threads = [threading.Thread(target=liest) for _ in range(5)]
    threads += [threading.Thread(target=schreibt) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Was jetzt im Cache liegt, muss zum aktuellen Zähler passen.
    with patch("arcade_scanner.server.api_handler.db.get_all_dicts",
               side_effect=lambda: list(stand["wert"])):
        version, daten = cache.get_with_version()

    assert version == cache.version()
    assert daten == stand["wert"]
