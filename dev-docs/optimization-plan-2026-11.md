# Optimierungs- & Ausbauplan (Stand: 2026-11-02)

Dieses Dokument hält den aktuellen Stand der Optimierungen (Pakete 1–3, bereits
umgesetzt und getestet) sowie den detaillierten Fahrplan für die offenen Pakete
(Pakete 4–6) fest, damit jederzeit nahtlos weitergearbeitet werden kann.

---

## ✅ Bereits umgesetzt (2026-11-02)

### Paket 1: Backend- & Frontend-Performance („Turbo-Pack“)
- [x] **Lazy-Thumbnails ohne Extra-`ffprobe`:**
  - `FinderHandler._resolve_thumb_info()` in `arcade_scanner/server/api_handler.py`
    liefert jetzt `(file_path, duration_sec)` aus SQLite + LRU-Cache und reicht
    `duration_sec` direkt an `create_thumbnail()` weiter.
- [x] **Kein „Thundering Herd“ mehr bei On-Demand-Thumbnails:**
  - `THUMB_RENDER_SEMAPHORE = threading.BoundedSemaphore(4)` und Pro-Datei-Locks
    (`_get_thumb_lock()`) in `arcade_scanner/core/video_processor.py` verhindern
    parallele Doppel-Renders und CPU-Spitzen beim Scrollen durch neue Ordner.
- [x] **`Cache-Control: immutable` für versionierte Static-Assets & Fonts:**
  - `FinderHandler.do_GET` (`/static/`) setzt bei `?v=<mtime>` (ungleich `0`)
    sowie `.woff2`/`.woff`/`.ttf` den Header
    `Cache-Control: public, max-age=31536000, immutable`.
- [x] **$O(1)$ Pfad-Index & smarter Hover-Preview im Grid:**
  - `window.getVideoByPath()` und `window.rebuildVideoIndex()` in
    `arcade_scanner/server/static/store.js` ersetzen lineare `.find()`-Scans
    über `window.ALL_VIDEOS`.
  - `initHoverPreview()` in `arcade_scanner/server/static/engine.js` nutzt den
    $O(1)$-Lookup, `preload = 'metadata'` und springt per `#t=<10%>` (max. 30 s)
    direkt mitten ins Video.
- [x] **CSS `content-visibility` fürs Grid:**
  - `.video-card-container` in `arcade_scanner/server/static/styles.css` trägt
    `content-visibility: auto; contain-intrinsic-size: auto 260px;`.

### Paket 2: 100 % Self-Hosted & Air-Gapped (Null CDN-Abhängigkeiten)
- [x] **Schriften lokalisiert (`woff2`):**
  - `inter-latin.woff2`, `inter-latin-ext.woff2` und `material-icons.woff2`
    liegen unter `arcade_scanner/server/static/fonts/`.
  - `@font-face` und `:where(.material-icons)` sind in `styles.css`,
    `login.html` und `settings_redesign.html` verdrahtet.
- [x] **Vorkompiliertes `tailwind.css` statt Cloudflare Play-JIT:**
  - `arcade_scanner/server/static/tailwind.css` aus `theme.py` und allen
    Templates/JS-Modulen generiert und in `STYLESHEETS`
    (`arcade_scanner/templates/dashboard_template.py`) eingetragen.
  - Externe `<link>`/`<script>`-Tags aus `arcade_scanner/templates/ui_components.py`
    entfernt.
- [x] **Content-Security-Policy gehärtet:**
  - `FinderHandler._SICHERHEIT` in `arcade_scanner/server/api_handler.py`
    erlaubt nur noch `'self'`.
  - Abgesichert durch `tests/test_external_resources.py` und
    `tests/test_security_headers.py`.

### Paket 3: Docker, Nginx & Repo-Hausputz
- [x] **Healthcheck auf `/api/health` umgestellt:**
  - `Dockerfile` und `docker-compose.yml` prüfen `http://localhost:8000/api/health`
    (inkl. SQLite-Erreichbarkeit).
- [x] **Docker-Compose bereinigt:**
  - Harten `- .:/app`-Mount aus `docker-compose.yml` entfernt und CPU-Limit von
    `0.75` auf `4.0` angehoben.
- [x] **Nginx-Konfiguration (`nginx/arcade-scanner.conf`) gehärtet:**
  - Eigener `location /stream`-Block mit `proxy_buffering off;` und
    `proxy_request_buffering off;`.
  - Security-Header in `location /thumbnails/` explizit wiederholt (verhindert
    den Wegfall der Server-Block-Header durch `add_header Cache-Control`).
- [x] **Altlast-Dateien entfernt:**
  - Verwaiste `._*`, `.DS_Store`, `screenlog.0`, `docker-compose.yml_back2` und
    `arcade_data/settings.json.backuo` gelöscht.

---

## 🔜 Offene Pakete zum Weiterarbeiten (Resume-Guide)

### Paket 4: Scanner- & SQLite-Tiefenoptimierung
1. **`os.scandir()`-Walker statt `os.walk()` + doppeltem `os.stat()`:**
   - **Dateien:** `arcade_scanner/scanner/file_system.py`
   - **Schritte:**
     - [x] In `AsyncFileSystem._walker_worker` einen rekursiven
           `os.scandir()`-Durchlauf nutzen, sodass `entry.stat().st_size` und
           `entry.is_dir(follow_symlinks=False)` direkt aus dem
           Directory-Eintrag wiederverwendet werden.
     - [x] `_is_valid_size(path, size_bytes=...)` nutzt das bereits bekannte
           `size_bytes` ohne zweiten `os.path.getsize()`-Syscall.
     - [x] Bestehende Tests in `tests/test_file_system.py` und
           `tests/test_scanner_manager.py` geprüft.
2. **Thread-lokale Read-Only-Connections für SQLite (WAL-Parallelität):**
   - **Datei:** `arcade_scanner/database/sqlite_store.py`
   - **Schritte:**
     - [x] Neben `self._conn` (Writer unter `self._write_lock`) über
           `threading.local()` eine Read-Connection pro Thread
           (`_get_read_connection()` mit `PRAGMA query_only=ON`) angelegt.
     - [x] Lese-Methoden (`get()`, `get_by_thumb()`, `get_all()`,
           `get_all_dicts()`) über die Thread-lokale Connection ausgeführt,
           damit API-Requests während eines laufenden `bulk_upsert` niemals auf
           den Writer-Lock warten müssen.
     - [x] Mit `tests/test_sqlite_store.py` gegengeprüft.
3. **Optionales Nginx `X-Accel-Redirect` für Zero-Copy-Streaming:**
   - **Dateien:** `arcade_scanner/server/streaming_util.py`,
     `nginx/arcade-scanner.conf`, `tests/test_streaming_util.py`
   - **Schritte:**
     - [x] Wenn Request-Header `X-Accel-Support: 1` (von Nginx gesetzt) anliegt,
           beantwortet `serve_file_range()` nach Auth- und
           `resolve_stream_path()`-Prüfung die Anfrage mit
           `X-Accel-Redirect: /_internal_media/<path>` und `Content-Length: 0`.
     - [x] Passende `internal;`-Location in `nginx/arcade-scanner.conf`
           ergänzt.

---

### Paket 5: UX- & Feature-Ausbau (Cinema, Live-Events & TV-Client)
1. **Synchronisierter A/B-Qualitätsvergleich im Cinema-Player (Review-Mode):**
   - **Dateien:** `arcade_scanner/server/static/cinema.js`,
     `arcade_scanner/server/static/engine.js`,
     `arcade_scanner/server/static/shortcuts.js`,
     `arcade_scanner/templates/components.py`
   - **Schritte:**
     - [x] Beim Öffnen eines Videos aus einer `createComparisonCard`
           (`data-compare-original` + `data-compare-optimized`) beide Pfade an
           `openCinema()` übergeben.
     - [x] Im Cinema-Modal einen A/B-Umschalter (`#cinemaCompareBtn` + Shortcut
           `Tab`) eingebaut, der bei exakt gleichem `currentTime` und
           Play/Pause-Zustand nahtlos zwischen Original und Encode wechselt
           (inkl. Badge `A/B: Original` vs. `A/B: Optimiert`).
     - [x] Contract-Tests (`test_dom_contract.py`, `test_js_syntax.py`,
           `test_shortcuts_overlay.py`) verifiziert.
2. **Server-Sent Events (`GET /api/events`) statt Polling-Schleifen (Optional):**
   - **Dateien:** `arcade_scanner/server/api_handler.py`,
     `arcade_scanner/server/static/settings.js`,
     `arcade_scanner/server/static/duplicates.js`
   - **Schritte:**
     - [ ] Leichtgewichtigen SSE-Endpunkt `/api/events` implementieren, der
           Scan-Fortschritt, Duplikat-Scan-Status und abgeschlossene
           Queue-Jobs pusht.
     - [ ] Im Frontend `EventSource('/api/events')` mit automatischem Fallback
           auf das bestehende Polling verbinden.
3. **webOS TV-Client: Tag-Sichtprüfung & Neubau der `.ipk` (Optional):**
   - **Dateien:** `tv_client/`, `scripts/build_tv_ipk.sh` (siehe auch
     `tasks/todo.md`, Task 21)
   - **Schritte:**
     - [ ] In `tv_client/` prüfen, dass die neuen Tags (`OD-Pro-Web`,
           `OD-Pro-Self` usw.) als Filter-Chips wählbar sind.
     - [ ] `npm run pack` & `./scripts/build_tv_ipk.sh` ausführen, um
           `com.arcade.scanner.tv_1.0.0_all.ipk` auf den aktuellen Code-Stand zu
           bringen.

---

### Paket 6: Tailwind-Wartbarkeit (Re-Build-Helfer)
- **Hintergrund:** Da `arcade_scanner/server/static/tailwind.css` jetzt statisch
  eingecheckt ist, steht für zukünftige UI-Änderungen ein Helfer-Skript bereit.
- **Schritte:**
  - [x] Hilfsskript `scripts/build_tailwind.py` angelegt, das die
        Token-Konfiguration aus `arcade_scanner/templates/theme.py` liest und
        `arcade_scanner/server/static/tailwind.css` verifiziert bzw. mit
        `--bundle` neu generiert.

---

## 🛠️ Schnellstart beim nächsten Mal

```bash
# 1. Status & Tests prüfen
.venv/bin/pytest -q
.venv/bin/ruff check .

# 2. Dashboard-Dump nach Template-Änderungen frisch schreiben
.venv/bin/python3 scripts/regenerate_report.py
```
