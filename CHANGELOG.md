# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Duplikat-Scan findet re-encodete Videos**: Der bisherige Video-Pass gruppiert
  nach gerundeter Größe + Dauer + Auflösung. Eine transkodierte Kopie (H.264 →
  HEVC, 1080p → 720p, anderer CRF) teilt keinen dieser Werte und landete damit
  nie im selben Bucket — und der visuelle Fallback lief nur *innerhalb* eines
  Buckets, wo alle Dateien ohnehin schon identische Größe und Auflösung haben.
  Genau der häufigste echte Duplikat-Fall in einer transkodierten Bibliothek war
  also unsichtbar. Neuer zweiter Pass: Bucketing nach Dauer (±1,5 s), dann
  Vergleich perceptueller Hashes von drei Frames bei 25/50/75 % der Laufzeit.
  Gruppiert wird nur, wenn *alle* Positionen passen — ein gemeinsamer Vorspann
  reicht nicht, sonst würde eine ganze Serienstaffel zusammenfallen.
  Gruppen erscheinen als `match_type: "reencode"` mit 75 % Confidence.
  Frame-Signaturen werden in `.vframe_cache.json` gecacht; gehasht werden nur
  Videos, die überhaupt einen Dauer-Nachbarn haben. Abschaltbar über
  `find_all_duplicates(..., detect_reencodes=False)`.

### Fixed
- **Bild-Duplikate fielen aus dem Ergebnis, wenn eine Gruppe ihren Partner
  zuerst beanspruchte**: Der Near-Miss-Pass war greedy — wer einmal in einer
  Gruppe steckte, war für alle weiteren Vergleiche verbraucht. Bei A~B und A~C,
  aber B!~C, verschwand je nach Reihenfolge B oder C komplett aus dem Ergebnis
  und wurde als eindeutig gemeldet. Welches von beiden, hing an der
  Iterationsreihenfolge, dieselbe Bibliothek konnte also unterschiedliche
  Antworten liefern. Clustering läuft jetzt über Union-Find: jedes Paar
  innerhalb der Schwelle landet garantiert in derselben Gruppe. Preis dafür ist
  transitives Ketten (A~B, B~C ergibt eine Gruppe, auch wenn A!~C) — bei
  Schwelle 5 über 64 Bit braucht das einen echten Verlauf fast identischer
  Bilder, und die zusammen zu zeigen ist ohnehin die erwartete Antwort.
- **Duplikat-Scan fand keine Duplikate über Batch-Grenzen hinweg**: Die
  Bild-Batches waren echte Slices (`all_images[offset:offset+size]`), und
  verglichen wurde nur *innerhalb* eines Slices. Zwei Kopien desselben Fotos auf
  gegenüberliegenden Seiten einer Grenze — Eintrag 4999 und 5001 — wurden damit
  in keinem einzigen Batch je miteinander verglichen. Zusätzlich überschrieb
  jeder Lauf den Gruppen-Cache mit seinem eigenen Slice-Ergebnis, Batch 2 warf
  also alles weg, was Batch 1 gefunden hatte. Das Limit begrenzt jetzt nur noch,
  wie viele *neue* Hashes ein Lauf berechnet; verglichen wird immer über die
  gesamte Bibliothek. Jeder Lauf liefert damit ein vollständiges Ergebnis, das
  mit jedem weiteren Batch wächst.
- **Nicht dekodierbare Bilder wurden bei jedem Scan neu versucht**: Fehlschläge
  hinterließen keine Spur im Cache. Mit dem neuen Batch-Modell hätte das zu
  einem endlosen "weitere Batches verfügbar" geführt. Sie werden jetzt markiert
  (stat-validiert wie jeder andere Eintrag, eine reparierte Datei wird also
  wieder versucht).
- **Duplikat-Scan empfahl bei Re-Encodes die falsche Datei zum Behalten**:
  `_calculate_video_quality_score` vergibt +20 Punkte für moderne Codecs. Beim
  Abwägen zwischen byte-identischen Kopien ist das richtig, in einer
  Re-Encode-Gruppe genau falsch: die HEVC-Datei ist dort das verkleinerte
  Derivat des H.264-Originals. Der Codec-Bonus entfällt jetzt für
  `reencode`-Gruppen; Auflösung und Bitrate entscheiden.
- **Duplikat-Scan ließ temporäre Frame-Dateien liegen**: Schlug der
  ffmpeg-Aufruf in `_get_video_frame_hash` fehl oder lief in den Timeout, blieb
  die per `NamedTemporaryFile(delete=False)` angelegte Datei in `/tmp` zurück —
  über einen langen Scan mit vielen kaputten Dateien summiert sich das. Cleanup
  läuft jetzt im `finally`.
- **Duplikat-Scan: veraltete perceptual Hashes** (`.phash_cache.json`): Der Cache
  war nur nach Dateipfad indiziert, ohne jede Angabe, aus welchem Dateizustand
  der Hash stammt. Wurde ein Bild an Ort und Stelle geändert (Neu-Export,
  Rotation, Rsync über denselben Pfad), lieferte der Cache weiterhin den alten
  Hash — die Datei landete in einer Duplikatgruppe, die es nicht mehr gab, und
  genau diese Gruppen bietet die UI zum Löschen an. Cache-Einträge tragen jetzt
  `mtime_ns` + Dateigröße und werden bei Abweichung neu berechnet (Format v2).
  Alte v1-Caches werden beim ersten Laden übernommen und mit dem aktuellen
  Dateizustand gestempelt, statt eine komplette Neuberechnung zu erzwingen.
  Das Schreiben läuft jetzt über write-then-rename, damit ein Absturz mitten im
  Speichern nicht den ganzen Cache als kaputtes JSON verwirft.
- **Duplikat-Scan brach sofort ab** (`'dict' object has no attribute 'file_path'`):
  Der OOM-Fix hatte `_media_cache` von `db.get_all()` auf `db.get_all_dicts()`
  umgestellt — API-Dicts mit UI-Aliasen (`FilePath`) statt `VideoEntry`-Modellen.
  Der `DuplicateDetector` arbeitet aber durchgängig attributbasiert
  (`v.file_path`, `v.size_mb`, `media_type`), sodass der Scan-Target-Filter
  stolperte, sobald ein Benutzer Scan-Ziele gesetzt hatte. Der Duplikat-Pfad
  holt die Einträge jetzt wieder über `db.get_all()`.
  Der stille Teil war der gefährlichere: `getattr(dict, 'media_type', 'video')`
  liefert **immer** `'video'`, Bilder wären also nie als Bilder erkannt und nie
  verglichen worden — ohne Fehlermeldung. Neuer Contract-Test
  `test_duplicate_scan_entry_contract.py` hält beide Fälle fest.
- **Kandidaten-Ansicht: "URI malformed"**: Dateinamen mit ungültigen UTF-8-Bytes
  (cp1252-Reste wie `ö`, `ü`, `'`) kommen über Pythons `surrogateescape` als
  einzelne Surrogate im JSON an; `encodeURIComponent` wirft darauf `URIError`.
  Da das beim Rendern passierte, riss eine einzige Datei die komplette Ansicht
  mit. `candidates.js` übergibt jetzt den Ergebnis-Index statt des URL-kodierten
  Pfads an die onclick-Handler. Das behebt nebenbei Dateinamen mit `'`, `"` oder
  `<`, die das HTML-Attribut zerlegten — Anzeigetext und `data-path` werden
  jetzt escaped.
- **Optimize-Button (`engine.js`)**: derselbe `encodeURIComponent` steckte in der
  Kartenvorlage und hätte die Grid-Ansicht mitgerissen (bislang verdeckt, weil
  im Docker-Betrieb der `queueForRemoteEncode`-Zweig greift). Der Button ist
  jetzt in `_optimizeButton()` ausgelagert; neu in `utils.js` ist
  `safeEncodePath()`, das `URIError` abfängt und `null` liefert. Ist ein Pfad
  nicht kodierbar, wird der Button deaktiviert samt Erklärung — bewusst kein
  Reparaturversuch, da die Gegenstelle mit `unquote()` ohne
  `errors='surrogateescape'` dekodiert und den Originalpfad ohnehin nicht
  zurückgewinnen könnte.
- **Duplikat-Ansicht: gleiche Ursache**: Der Löschen-Button in `duplicates.js`
  hatte denselben `encodeURIComponent(file.path)` in der Render-Schleife.
  `deleteDuplicate()` nimmt jetzt Gruppen- und Datei-Index und löst sie sofort
  in den Pfad auf, bevor der Request läuft — sonst würde ein zweiter Klick
  während des laufenden `fetch` seinen Index gegen bereits mutierte Daten
  auflösen und die falsche Datei löschen.

### Added — Embedding Foundation (Ähnlichkeit Teil 1)
- **GPU-Indexer** (`scripts/media_indexer.py`): berechnet CLIP-Embeddings
  (Default ViT-B-16, 12 Frames pro Video, Bilder 1 Frame) und schreibt sie in
  die Haupt-DB. Inkrementell (mtime/Modell), `--watch`, `--rebuild`; eigene
  optionale Dependency-Gruppe `pip install -e ".[indexer]"` — der Server
  selbst bleibt ohne ML-Abhängigkeiten.
- **`GET /api/similar`**: nächste Nachbarn über die gespeicherten
  Mean-Vektoren (pures Python, kein NumPy), Session-pflichtig und
  Vault-gefiltert; Cache invalidiert sich bei Indexer-Läufen selbst.

### Added — Scan-Steuerung
- **Scan stoppen aus der UI** (ROADMAP-Punkt): neuer Stop-Button neben dem
  Rescan-Button, `GET /api/scan/stop` signalisiert `ScannerManager.stop()`.
  Teilergebnisse bleiben erhalten (Orphan-Cleanup wird serverseitig
  übersprungen).
- **`/api/rescan` läuft im Hintergrund**: antwortet sofort mit 202 statt den
  Request zu blockieren (Voraussetzung fürs Stoppen), `GET /api/scan/status`
  zum Pollen; das Frontend lädt nach Abschluss automatisch neu. Doppelte
  Scans werden mit 409 abgewiesen.

### Added — Auto-Tagging Rules
- **Auto-Tag-Regeln**: eine Regel = Smart-Collection-Query + Ziel-Tag. Regeln
  laufen serverseitig nach jedem Scan und auf Knopfdruck (Settings →
  Auto-Tagging). Apply-once: ein manuell entferntes Tag wird nie erneut
  vergeben. Anlegen direkt im Collection-Editor ("Als Regel").
- **Server-seitige Query-Auswertung**: Python-Port des Collection-Evaluators,
  per Node-Paritätstest gegen `collections.js` gepinnt.

### Added — Optimizer Candidates View
- **Kandidaten-Ansicht** (`/candidates`): ranks the library by expected re-encode
  savings (bitrate-per-resolution heuristic + codec efficiency), refined by real
  results from `encode_history.jsonl` once a resolution/bitrate class has ≥3
  encodes. Header shows the total possible savings; rows queue directly into the
  existing encoding queue (HEVC/AV1 toggle).
- **`optimized_at` marker**: successful optimizations now stamp the media entry;
  optimized files no longer appear as candidates (rescan-safe).

### Changed — Video Optimizer V2.5
- **Downscaling**: New `--scale-height H` option scales the encode to H pixels height while keeping the source aspect ratio (width `-2`). Upscaling is refused, the SSIM reference is scaled to match so quality checks stay valid, and the constrained-VBR ladder is adjusted to the target resolution (~pixels^0.75) so a downscale actually converts into savings.
- **Sample-Clip Pre-Search**: The quality binary search now runs on a ~24s stream-copied probe clip first, then narrows the full-encode search to predicted ±1 — typically 1-2 full passes instead of 3-4 (files ≥ 120s; `--no-presearch` to disable).
- **Encode History Seeding**: Successful encodes are logged to `encode_history.jsonl`; future runs start the search at the median winning Q for the same encoder/resolution/bitrate class.
- **HDR/10-bit Safety**: HDR and 10-bit sources are detected; VideoToolbox/NVENC/x265 encode main10 with BT.2020/PQ/HLG color passthrough, other encoders skip the file instead of mistagging it as BT.709 (previously colors washed out).
- **Two-Pass Loudnorm**: Audio loudness is measured once per file and normalized in transparent linear mode instead of pumping-prone dynamic mode (moderate/enhanced audio modes).
- **Scene-Aware SSIM Sampling**: Quality checks sample the highest-bitrate parts of the video (packet analysis) instead of fixed 25/50/75% points.
- **Output Integrity Verification**: Every optimized file must pass a duration check and a full error-strict decode before it replaces anything — truncated or corrupt encodes are discarded automatically.
- **Worker Scheduling**: `mac_worker.py` gains `--schedule "01:00-08:00"` (overnight windows supported) and `--pause-on-battery`.
- **Fixed**: `get_video_info()` never populated width/height/codec (missing `codec_type` in the ffprobe query) — now returns real stream metadata.

### Changed — HTTP Performance Overhaul (Viewing & Streaming)
- **HTTP/1.1 Keep-Alive**: The server now reuses TCP connections instead of opening a new one per request. Thumbnails, static assets, API polling, and video seeking (Range requests) no longer pay a TCP/TLS handshake each time. A safety net guarantees every response either carries a `Content-Length` or closes the connection.
- **gzip Compression**: Dashboard HTML, JS/CSS assets, and JSON API responses (`/api/videos`, settings, tags, duplicates) are gzip-compressed when the client supports it (~75-90% smaller transfers).
- **Browser Caching**: Thumbnails are cached for 7 days (`Cache-Control: public, max-age=604800`); static assets and the dashboard revalidate via `If-Modified-Since` and get cheap `304 Not Modified` answers instead of full re-downloads.
- **Zero-Copy Streaming**: Video streaming uses kernel `sendfile()` (with automatic fallback for SSL and 1 MB chunks instead of 64 KB), plus support for suffix ranges (`bytes=-N`) and correct clamping of over-long ranges.
- **Connection Hygiene**: Idle keep-alive connections time out after 60s; handler threads are daemonized so open connections never block shutdown.

## [6.8.0] - 2026-01-18

### Added
- **Visual Timeline & Scrubber**: Professional visual timeline with frame-accurate seeking and real-time thumbnail previews.
- **Trim Handles**: Visual markers for setting export start/end points.
- **GIF Export Panel**: Replaced modal with a bottom panel UI matching the optimizer workflow.
- **Production Presets**: Resolution (360p-1080p) and FPS (10-30) presets for GIF export.
- **Size Estimation**: Dynamic file size calculation for GIF exports.
- **Current Time Capture**: Buttons to set trim handles to current video time.

### Changed
- **Cinema Mode UX Overhaul**: Redesigned all action buttons with labels, larger touch targets, and backdrop blur.
- **Docker-Aware UI**: Automatically hide "Reveal in Finder" buttons when running in Docker.

## [6.7.1] - 2026-01-16

### Added
- **Fullscreen Duplicate Checker**: Dedicated interface for side-by-side duplicate resolution.
- **Duplicate Shortcuts**: `1`/`←` (Keep A), `2`/`→` (Keep B), `S`/`Space` (Skip), `A` (Auto), `ESC` (Exit).
- **Smart Recommendations**: Green border highlighting for recommended files based on quality score.
- **Progress Tracking**: Group counter (e.g., "47 / 13,771") in duplicate view.

## [6.7.0] - 2026-01-15

### Added
- **Batch Selection Mode**: Click one checkbox to enter selection mode, then click anywhere on cards to toggle.
- **Visual Feedback**: Checkmark overlay on hover and cyan highlights during selection.

### Fixed
- **List View Thumbnails**: Properly constrained thumbnail sizes (fixed full-size image bug).
- **CSS Media Queries**: Fixed desktop grid layout breakage caused by malformed queries.
- **Asset Loading**: Added missing `styles.css` link to dashboard.

## [6.6.0] - 2026-01-14

### Added
- **Binary Search Quality**: O(log n) optimization passes for faster quality targeting.
- **Early Size Abort**: Stop encoding if output exceeds 95% of original size.
- **Fallback Mode**: Use best acceptable result (SSIM >= 0.945) when strict targets fail.

### Changed
- **JS Refactoring**: Extracted `cinema.js`, `collections.js`, and `formatters.js` from `engine.js`.
- **Documentation**: Added JSDoc to major JavaScript functions.

### Fixed
- **Keep/Discard**: Fixed "Keep" button not replacing original file (import shadowing fix).

## [6.5.0] - 2026-01-14

### Added
- **Cinema Tag Display**: View and remove assigned tags directly in the cinema overlay.
- **Docker Live Reload**: Volume mount support for instant code updates in production.

### Fixed
- **Tag System**: Resolved cache-busting and validation issues during tag creation/deletion.

## [6.4.1] - 2026-01-14

### Added
- **RAW Image Support**: Support for 12 RAW formats (CR2, NEF, ARW, DNG, etc.).
- **Smart Image Collections**: Pre-defined filters for Photos, Recent Imports, and Large Files.
- **Persistent Duplicate Cache**: Scan results saved to disk to prevent redundant scans.
- **Rescan Button**: Manual duplicate analysis trigger.

### Fixed
- **Connection Leaks**: Fixed "Too many open files" error with proper SQLite connection management.

## [6.4.0] - 2026-01-14

### Added
- **Duplicate Detection**: Smart metadata + content sampling (512KB start/end) verification.
- **Setup Wizard**: ASCII-based terminal walkthrough for first-run configuration.
- **Database Maintenance**: Tools to purge orphan entries and thumbnails.

## [6.3.0] - 2026-01-12

### Added
- **Unified Media Library**: Full support for scanning and viewing images alongside videos.
- **Cinema Modal Navigation**: Use Arrow keys to navigate through library items.
- **Visual Badges**: Purple "IMG" badge for image cards.

## [6.2.0] - 2026-01-12

### Added
- **Multi-User Accounts**: Secure login with isolated targets, favorites, and tags.
- **SQLite Backend**: Replaced JSON storage for massive library performance.
- **Negative Tag Filters**: Exclude specific tags from search results.
- **Smart Collections**: Save any complex query as a sidebar shortcut.

## [6.1.0] - 2026-01-05

### Added
- **Theme Engine**: Support for multiple themes (Arcade, Professional, Candy).
- **Custom Tagging**: Batch apply custom tags to any media.
- **Search Polish**: Redesigned unified search and filter sidebar.

## [6.0.0] - 2026-01-01

### Added
- **Workspace Differentiation**: Context-aware color accents and background tints for Lobby (Cyan), Favorites (Gold), Review (Cyan), and Vault (Magenta).
- **Professional Navigation**: Enhanced sidebar with structural active states, indicator bars, and workspace-specific iconography.
- **Settings UI Redesign**: Modern, sidebar-based configuration interface inspired by modern OS design standards (Apple/Linear/Stripe).
- **State Management**: Integrated toast notifications, loading spinners, and unsaved changes tracking.
- **Video Optimizer Toggle**: UI toggle in settings to enable/disable optimization features.

### Changed
- **Filter Bar Redesign**: Dynamic workspace-sensitive border colors and background tints.
- **Responsive List View**: Improved card layouts and reduced thumbnail sizes to prevent overflow on wide screens.
- **UI Architecture**: Moved away from hybrid inline styles towards a more structured workspace theming system.

### Fixed
- **Search Logic**: Corrected input binding that caused search to fail.
- **Settings Navigation**: Fixed tab-switching logic and content visibility in the settings modal.
- **UI Overflow**: Resolved horizontal scrolling issues in the list view on high-resolution displays.
- **Refresh Button**: Added missing ID to the rescan button to restore functionality.
- **State Persistence**: Improved persistence check for Video Optimizer settings.

## [5.2.0] - 2025-12-29

### Added
- **Saved Views**: Users can now save their current search queries, filters, and sort settings as named presets.
- **Real-time Status**: The video optimizer script now notifies the running server when a file optimization completes, allowing the UI to update instantly.
- **API Endpoints**: New `/api/settings` (POST) for saving user preferences and `/api/mark_optimized` for external status updates.

### Changed
- **Refactoring**: Extracted video scanning logic from `main.py` into a new dedicated module `core/scanner.py`.
- **Optimizer**: Added `--port` argument to `video_optimizer.py` to enable server notifications.

### Fixed
- **Time Parsing**: Fixed `ValueError` in optimizer progress display when `out_time_ms` is invalid.
- **Scan Logic**: Scanner now correctly identifies optimized files regardless of the minimum size threshold.

## [5.1.1] - 2025-12-19

### Added
- **Cinema Mode Enhancements**: Full-screen video player now includes action buttons for Favorite, Vault, Locate, and Optimize.
- **Cinema Info Panel**: Technical details panel in cinema mode showing codec, bitrate, file size, and status.
- **Select All Button**: New "Select All Visible" button in batch mode to quickly select all filtered videos.
- **Cache Statistics**: Settings modal now displays cache size statistics (thumbnails, previews, and total).
- **Enhanced Treemap Gradients**: Improved visual design with gradient colors for both folder and file views.

### Changed
- **Cleaner Console Output**: Removed verbose "Purging broken media" messages, now only shows when files are actually cleaned.
- **Cinema Mode UX**: Favorite and Vault buttons now show visual feedback when already applied (reduced opacity).
- **Settings Modal Width**: Increased max-width to 800px to accommodate cache statistics.

### Fixed
- **Cinema Mode State Sync**: Favorite/Vault actions in cinema mode now properly update the grid view without requiring reload.

## [5.1.0] - 2025-12-19

### Added
- **Settings UI**: New in-app settings modal (gear icon) to configure scan paths and exclusions directly from the dashboard.
- **Default Exclusions Toggles**: Each default exclusion now shows a description and can be enabled/disabled via checkbox.
- **Hardware-Accelerated Preview Generation**: Preview clips now use GPU encoding (NVENC, VideoToolbox, QuickSync) for 5-10x faster initial scans.
- **Dynamic Worker Count**: Auto-detects GPU VRAM and sets optimal parallel workers (1 per 3GB, max 12).
- **Separate Rebuild Commands**: `--rebuild-thumbs` and `--rebuild-previews` to regenerate media independently.
- **Improved Progress Messages**: Shows "thumbnails...", "previews...", or "processed..." based on rebuild mode.

### Changed
- **Configuration**: Migrated from `local_targets.txt`/`local_excludes.txt` to unified `settings.json` format.
- **Thumbnail Generation**: Now uses letterboxing/pillarboxing to preserve aspect ratio for vertical videos.
- **Default Exclusions**: Now stored with descriptions for better UI presentation.

### Fixed
- Fixed distorted thumbnails for vertical (9:16) videos.
- Improved cache handling to preserve favorite and hidden states during rebuilds.

## [5.0.0] - 2025-12-18

### Added
- **Batch Favorites**: Select multiple videos and mark them all as favorites at once.
- **Cross-Platform Video Optimizer**: NVIDIA NVENC, Apple VideoToolbox, and software fallback support.
- **Fun Facts**: Gaming trivia displayed during optimization.

## [4.9.0] - 2025-12-18

### Added
- **UI Performance Optimization**: Implemented lazy loading and infinite scrolling for the video grid, significantly improving performance for large libraries (tested with 2200+ clips).
- **Robust Static Asset Serving**: Transitioned CSS and JavaScript from Python templates to dedicated static files (`/static/styles.css` and `/static/client.js`) with improved path resolution.
- **Auto-Port Detection**: The server now automatically finds the next available port if the default 8000 is occupied.
- **Address Reuse**: Implemented `SO_REUSEADDR` to prevent "Address already in use" errors during quick restarts.

### Changed
- Improved encoding handling for local configuration files (`local_targets.txt`, `local_excludes.txt`) using UTF-8 with BOM support.
- Updated dashboard template to use static asset links instead of inline/templated scripts and styles.
- Refactored server logic to keep the working directory at the project root for better resource management.

### Fixed
- Resolved Python syntax errors related to global variable declarations in `web_server.py`.
- Fixed asset loading issues (404 errors) by implementing more robust static file routing.
- General bug fixes and stability improvements.
