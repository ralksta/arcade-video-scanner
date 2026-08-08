import hashlib
import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

STATIC_DIR = Path(__file__).parent.parent / "arcade_scanner" / "server" / "static"


# Mock config for tests
@pytest.fixture(autouse=True)
def patch_config(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.sqlite_store.config", mock_config), \
         patch("arcade_scanner.scanner.manager.config", mock_config):
        yield mock_config

@pytest.fixture
def store(patch_config):
    from arcade_scanner.database.sqlite_store import SQLiteStore
    s = SQLiteStore()
    s._ensure_connection()
    return s

def test_sqlite_store_handles_surrogates(store):
    from arcade_scanner.models.video_entry import VideoEntry

    # Path with a surrogate that often causes UnicodeEncodeError
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"

    entry = VideoEntry(
        FilePath=surrogate_path,
        Size_MB=100.0,
        Status="OK"
    )

    # 1. Test upsert (writes to DB)
    store.upsert(entry)
    assert store.count() == 1, "Entry was not inserted"

    # Check what's in the DB directly
    cur = store._conn.execute("SELECT file_path FROM media")
    row = cur.fetchone()
    print(f"DEBUG: stored file_path type: {type(row[0])}")
    print(f"DEBUG: stored file_path: {row[0]}")

    # 2. Test get (reads from DB and matches)
    safe_search_path = store._get_safe_path(surrogate_path)
    print(f"DEBUG: querying for type: {type(safe_search_path)}")
    print(f"DEBUG: querying for: {safe_search_path}")
    print(f"DEBUG: are search bytes equal to stored bytes? {safe_search_path == row[0]}")

    retrieved = store.get(surrogate_path)
    assert retrieved is not None, f"Failed to retrieve path: {surrogate_path}"
    assert retrieved.file_path == surrogate_path

    # 3. Test remove
    try:
        store.remove(surrogate_path)
        assert store.get(surrogate_path) is None
    except UnicodeEncodeError as e:
        pytest.fail(f"remove failed with UnicodeEncodeError: {e}")

def test_manager_hash_generation_handles_surrogates():
    from arcade_scanner.scanner.manager import ScannerManager

    # Constructing the manager must not raise for surrogate-containing paths.
    ScannerManager()
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"

    # Should not raise UnicodeEncodeError
    try:
        file_hash = hashlib.md5(surrogate_path.encode('utf-8', 'surrogateescape')).hexdigest()
        assert file_hash is not None
    except UnicodeEncodeError as e:
        pytest.fail(f"Hash generation failed with UnicodeEncodeError: {e}")

def test_encoding_queue_handles_surrogates(store):
    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"

    # 1. Queue job
    try:
        job_id = store.queue_encode(surrogate_path, size_bytes=1000)
        assert job_id is not None
    except UnicodeEncodeError as e:
        pytest.fail(f"queue_encode failed with UnicodeEncodeError: {e}")

    # 2. Get next pending
    try:
        job = store.get_next_pending(worker_id="test_worker")
        assert job is not None
        assert job["file_path"] == surrogate_path
    except UnicodeEncodeError as e:
        pytest.fail(f"get_next_pending failed with UnicodeEncodeError: {e}")

def test_thumbnail_hashing_handles_surrogates():
    from arcade_scanner.core.video_processor import create_thumbnail

    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"

    # Mock config.thumb_dir
    with patch("arcade_scanner.core.video_processor.config") as mock_cfg, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=1):
        mock_cfg.thumb_dir = "/cache/thumbnails"

        # Should not raise UnicodeEncodeError
        try:
            thumb_name = create_thumbnail(surrogate_path)
            assert thumb_name.startswith("thumb_")
            assert thumb_name.endswith(".jpg")
        except UnicodeEncodeError as e:
            pytest.fail(f"create_thumbnail failed with UnicodeEncodeError: {e}")

# Ein Dateiname mit ungültigen UTF-8-Bytes (cp1252 \xf6 = ö) — Python liest ihn
# per surrogateescape als U+DCF6 ein und reicht ihn so ans Frontend weiter.
SURROGATE_PATH = "/media_nas/Sites/h\udcf6gl.mp4"
# Zeichen, die zusätzlich das HTML-Attribut aufbrechen würden.
QUOTE_PATH = "/media_nas/Sites/Anna's \"Best\" <Video>.mp4"


def _run_view_js(js_files, body, paths):
    """Führt Frontend-JS in einer node-VM aus und gibt zurück, was `out()` meldet.

    Die Pfade kommen über den VM-Kontext als `PATHS` herein, nicht per
    String-Ersetzung im Quelltext: sie enthalten Surrogate und Anführungszeichen,
    die beim Einsetzen in Code nur neue Fehlerquellen wären.
    """
    if not shutil.which("node"):
        pytest.skip("node not on PATH")
    srcs = []
    for name in js_files:
        path = STATIC_DIR / name
        if not path.exists():
            pytest.skip(f"{name} does not exist")
        srcs.append(path.read_text(encoding="utf-8"))

    harness = textwrap.dedent("""
        const vm = require('vm');
        const [srcJson, bodyJson, pathsJson] = process.argv.slice(1);
        let result = null;
        const grid = { innerHTML: '' };
        const stub = () => ({ textContent: '', innerHTML: '', style: {},
                              classList: { add(){}, remove(){}, toggle(){} } });
        // utils.js ruft beim Laden initTheme() auf — daher Browser-Globals stubben.
        const ctx = {
            document: {
                getElementById: id => (id === 'videoGrid' ? grid : stub()),
                documentElement: stub(),
                body: stub(),
                addEventListener(){},
                querySelectorAll: () => [],
            },
            window: {
                workspaceMode: 'duplicates',
                matchMedia: () => ({ matches: false, addEventListener(){} }),
                addEventListener(){},
            },
            localStorage: { getItem: () => null, setItem(){}, removeItem(){} },
            setTimeout: fn => fn(), clearTimeout(){},
            setInterval(){}, clearInterval(){},
            fetch: () => Promise.reject(new Error('kein Netz im Test')),
            IntersectionObserver: class { observe(){} unobserve(){} disconnect(){} },
            ResizeObserver: class { observe(){} unobserve(){} disconnect(){} },
            MutationObserver: class { observe(){} disconnect(){} },
            console: { log(){}, error(){}, warn(){} },
            grid,
            out: r => { result = r; },
            PATHS: JSON.parse(pathsJson),
        };
        ctx.globalThis = ctx;
        vm.createContext(ctx);
        vm.runInContext(JSON.parse(srcJson).join('\\n') + '\\n' + JSON.parse(bodyJson), ctx);
        process.stdout.write(JSON.stringify(result));
    """)

    proc = subprocess.run(
        ["node", "-e", harness, json.dumps(srcs), json.dumps(body), json.dumps(paths)],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, f"Rendern brach ab:\n{proc.stderr}"
    return json.loads(proc.stdout)


def test_candidates_view_renders_surrogate_paths():
    """Die Kandidaten-Ansicht darf an einem Surrogate-Pfad nicht sterben.

    Die Serverseite ist oben schon abgesichert — der Pfad kommt also heil im
    JSON an und landet als einzelnes Surrogate (\\udcf6) im JS-String. Genau
    darauf wirft encodeURIComponent `URIError: URI malformed`. Weil das beim
    Rendern der Liste passierte, riss eine einzige Datei die komplette Ansicht
    mit ("Kandidaten-Analyse fehlgeschlagen: URI malformed"). candidates.js
    reicht deshalb den Ergebnis-Index an die onclick-Handler, nicht den
    URL-kodierten Pfad.
    """
    result = _run_view_js(["candidates.js"], """
        const mk = p => ({ file_path: p, codec: 'h264', height: 1080,
            bitrate_mbps: 8.5, size_mb: 2048, reason: 'test',
            estimated_saved_mb: 900, estimated_saved_pct: 44,
            confidence: 'high', source: 'estimate', thumb: null });
        candState.results = PATHS.map(mk);
        candState.summary = { total_files: PATHS.length,
            total_estimated_saved_mb: 1, history_based: 0 };
        _renderCandidates(grid);
        toggleCandidateSelect(0);
        out({ rendered: grid.innerHTML.length > 0, html: grid.innerHTML,
              selected: [...candState.selected][0] });
    """, [SURROGATE_PATH, QUOTE_PATH])

    assert result["rendered"], "Kandidatenliste blieb leer"
    # Der Pfad muss unverfälscht zurückkommen — sonst geht /api/queue/add ins Leere.
    assert result["selected"] == SURROGATE_PATH
    # Und Sonderzeichen dürfen das Markup nicht aufbrechen.
    assert "Anna&#39;s" in result["html"]
    assert "&lt;Video&gt;" in result["html"]
    assert "Anna's" not in result["html"]


def test_duplicates_view_renders_surrogate_paths():
    """Dieselbe Absicherung für die Duplikat-Ansicht.

    duplicates.js hatte `encodeURIComponent(file.path)` im Löschen-Button
    innerhalb der Render-Schleife — gleiche Bug-Klasse wie in candidates.js.
    Adressiert wird jetzt über (Gruppen-Index, Datei-Index); deleteDuplicate
    löst das sofort in den Pfad auf, bevor es etwas awaited.
    """
    result = _run_view_js(["utils.js", "duplicates.js"], """
        const mkFile = p => ({ path: p, thumb: null, size_mb: 100, width: 1920,
            height: 1080, bitrate_mbps: 8.5, quality_score: 50 });
        duplicateData = {
            groups: [{ media_type: 'video', match_type: 'exact', confidence: 1.0,
                       potential_savings_mb: 100, recommended_keep: PATHS[0],
                       files: PATHS.map(mkFile) }],
            summary: { total_groups: 1, potential_savings_mb: 100,
                       video_groups: 1, image_groups: 0 },
        };
        renderDuplicatesView();
        // Auflösung Index → Pfad prüfen, ohne wirklich zu löschen: confirm sagt Nein.
        let gefragt = null;
        globalThis.confirm = msg => { gefragt = msg; return false; };
        deleteDuplicate(0, 0);
        out({ rendered: grid.innerHTML.length > 0, html: grid.innerHTML,
              gefragt });
    """, [SURROGATE_PATH, QUOTE_PATH])

    assert result["rendered"], "Duplikatliste blieb leer"
    # Der Löschen-Dialog muss den Dateinamen aus dem Surrogate-Pfad zeigen —
    # Beweis, dass der Index korrekt aufgelöst wurde.
    assert result["gefragt"] is not None, "confirm() wurde nie erreicht"
    assert "h\udcf6gl.mp4" in result["gefragt"]
    # Buttons adressieren per Index, nicht per kodiertem Pfad.
    assert "deleteDuplicate(0, 0)" in result["html"]
    assert "Anna&#39;s" in result["html"]


def test_optimize_button_handles_surrogate_path():
    """Der Optimize-Button in engine.js darf die Grid-Ansicht nicht mitreißen.

    Der Nicht-Docker-Zweig schreibt den Pfad in eine URL. Bei Surrogate-Pfaden
    ist das nicht möglich (und der Server dekodiert sie mit `unquote()` ohne
    errors='surrogateescape' ohnehin nicht), also wird der Button deaktiviert —
    statt dass encodeURIComponent beim Rendern wirft.
    """
    result = _run_view_js(["utils.js", "engine.js"], """
        const mk = p => ({ FilePath: p, codec: 'h264', hidden: false });
        window.IS_DOCKER = false;
        const kaputt = _optimizeButton(mk(PATHS[0]));
        const heil = _optimizeButton(mk('/media_nas/Sites/sauber.mp4'));
        window.IS_DOCKER = true;
        const docker = _optimizeButton(mk(PATHS[0]));
        out({ kaputt, heil, docker });
    """, [SURROGATE_PATH])

    # Surrogate-Pfad: Button da, aber deaktiviert und ohne URL.
    assert "disabled" in result["kaputt"]
    assert "/compress?path=" not in result["kaputt"]
    assert "ungültige UTF-8-Bytes" in result["kaputt"]
    # Normaler Pfad: unverändert funktionsfähig.
    assert "disabled" not in result["heil"]
    assert "/compress?path=%2Fmedia_nas%2FSites%2Fsauber.mp4" in result["heil"]
    # Docker-Zweig baut keine URL und funktioniert auch mit Surrogaten.
    assert "queueForRemoteEncode" in result["docker"]
    assert "disabled" not in result["docker"]


def test_safe_encode_path_returns_null_on_lone_surrogate():
    """safeEncodePath fängt genau URIError ab und verschluckt nichts anderes."""
    result = _run_view_js(["utils.js"], """
        out({ kaputt: safeEncodePath(PATHS[0]),
              heil: safeEncodePath('/a/b c.mp4') });
    """, [SURROGATE_PATH])
    assert result["kaputt"] is None
    assert result["heil"] == "%2Fa%2Fb%20c.mp4"


def test_vr_gallery_quoting_handles_surrogates():
    from urllib.parse import quote as url_quote

    surrogate_path = "/media_nas/Sites/h\udcf6gl.mp4"

    # Should not raise UnicodeEncodeError
    try:
        quoted = url_quote(surrogate_path, errors='surrogateescape')
        assert "%F6" in quoted  # \udcf6 encoded as %F6
    except UnicodeEncodeError as e:
        pytest.fail(f"url_quote failed with UnicodeEncodeError: {e}")
