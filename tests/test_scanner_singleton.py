"""
test_scanner_singleton.py
-------------------------
``get_scanner_manager()`` war ein Lazy-Singleton ohne Sperre::

    if _scanner_instance is None:
        _scanner_instance = ScannerManager()

Der Server startet *vor* dem Scan-Thread (main.py), und das Dashboard pollt
``/api/scan/status`` sofort. Fragen beide zum ersten Mal gleichzeitig, entstehen
zwei Manager — jeder mit eigenem ``_claim()``-Zustand. Der Schutz gegen zwei
gleichzeitige Scans aus Nachtlauf 3 hängt aber genau daran, dass es **einen**
gibt: Die Statusabfrage sähe den falschen Manager („läuft nicht"), und ein
Klick auf „Rescan" startete einen zweiten vollständigen Scan.

Das Fenster ist schmal (der Konstruktor ist schnell); der Test macht es breit.
"""
import threading
import time
from unittest.mock import patch

from arcade_scanner.scanner import manager as manager_module


def test_concurrent_first_calls_share_one_manager():
    created = []

    class SlowManager:
        def __init__(self):
            time.sleep(0.05)
            created.append(self)

    n = 8
    barrier = threading.Barrier(n)
    results = []

    def call():
        barrier.wait()
        results.append(manager_module.get_scanner_manager())

    with patch.object(manager_module, "ScannerManager", SlowManager), \
         patch.object(manager_module, "_scanner_instance", None):
        threads = [threading.Thread(target=call) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(created) == 1, f"{len(created)} Scanner-Manager erzeugt"
    assert all(r is results[0] for r in results)
