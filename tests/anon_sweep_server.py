"""Hilfsskript für test_anonymous_route_sweep.py — kein Test selbst.

Startet den echten Server gegen ein Temp-Datenverzeichnis (CONFIG_DIR) und
fragt jede Route, die im Quelltext steht, anonym per GET und POST ab. Gibt die
Antwortcodes als JSON auf stdout aus.

Ein eigener Prozess, weil `config` und die Datenbank-Singletons beim Import
ihren Pfad festlegen: Nur so ist sicher, dass eine ungeschützte Route nichts
in `arcade_data/` schreibt.
"""
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

# Alles, was Server und Importe drucken, nach stderr — stdout gehört dem JSON.
sys.stdout = sys.stderr

datadir = sys.argv[1]
os.makedirs(datadir, exist_ok=True)
os.environ["CONFIG_DIR"] = datadir
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from arcade_scanner.config import config  # noqa: E402

assert config.hidden_data_dir == datadir, config.hidden_data_dir
config.save({"setup_complete": True})

source = "".join(open(f, encoding="utf-8").read() for f in
                 glob.glob(os.path.join(root, "arcade_scanner", "server", "**", "*.py"),
                           recursive=True))
# Jede Route, die als Literal im Server-Code steht — nicht nur /api/…:
# /favorite?, /compress?, /batch_… sahen sonst durch die Lücke.
paths = sorted(set(re.findall(r'(?:==|startswith\()\s*"(/[a-z_][^"]*)"', source)))

import socketserver  # noqa: E402
import threading  # noqa: E402

from arcade_scanner.server.api_handler import FinderHandler  # noqa: E402

# Port 0: Das Betriebssystem vergibt einen freien. `start_server()` versucht
# 8000 und fällt dann auf 8001 zurück — dort läuft womöglich der echte Server,
# oder der Port hängt vom letzten Lauf noch in TIME_WAIT.
server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FinderHandler)
server.daemon_threads = True
port = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


opener = urllib.request.build_opener(_NoRedirect)
results = []
for path in paths:
    url = f"http://127.0.0.1:{port}{path}" + ("x" if path.endswith(("/", "?", "=")) else "")
    for method in ("GET", "POST"):
        data = b"{}" if method == "POST" else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            code = opener.open(req, timeout=20).status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception as e:  # noqa: BLE001 — Abbruch ist auch ein Ergebnis
            code = type(e).__name__
        results.append({"method": method, "path": path, "code": code})

server.shutdown()
sys.__stdout__.write(json.dumps(results))
