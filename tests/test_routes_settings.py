# tests/test_routes_settings.py
"""Characterization tests for arcade_scanner/server/routes/settings.py.

Written during the 2026-08-08 night hardening run. These pin CURRENT behavior;
one xfail documents a real security gap (see below) without fixing it blind.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fake_user_store import make_fake_user_db

from arcade_scanner.server.routes import settings


class FakeRFile:
    def __init__(self, payload=b""):
        self._payload = payload
        self._pos = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._payload) - self._pos
        chunk = self._payload[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


class FakeHandler:
    def __init__(self, path, user="alice", body=None):
        self.path = path
        self._user = user
        payload = json.dumps(body).encode() if body is not None else b""
        self.rfile = FakeRFile(payload)
        self.headers = {"Content-Length": str(len(payload))}
        self.wfile = MagicMock()
        self.status = None
        self.error = None
        self.server = MagicMock()
        self.server.server_address = ("", 8000)

    def get_current_user(self):
        return self._user

    def send_response(self, code):
        self.status = code

    def send_error(self, code, message=""):
        self.error = code

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass

    def body(self):
        raw = b"".join(c.args[0] for c in self.wfile.write.call_args_list)
        return json.loads(raw)


def _singletons(save_result=True):
    config = MagicMock()
    config.settings.model_dump.return_value = {"bitrate_threshold_kbps": 8000}
    config.save.return_value = save_result
    # Die Attrappe muss `update_user()` wirklich ausführen — siehe
    # tests/fake_user_store.py.
    user_db, _user = make_fake_user_db()
    debouncer = MagicMock()
    return config, user_db, debouncer, 1024 * 1024


def run(handler, singletons=None, post=False):
    singletons = singletons or _singletons()
    with patch.object(settings, "_get_singletons", return_value=singletons):
        handled = settings.handle_post(handler) if post else settings.handle_get(handler)
    return handled, singletons


def test_get_settings_rejects_anonymous_callers():
    # Bis Nachtlauf 4 bekam eine anonyme Anfrage den globalen Dump:
    # gespeicherte Ansichten, proxy_root, review_dir, ffmpeg-Pfade. Kein Client
    # fragt vor der Anmeldung (test_anonymous_route_sweep.py).
    h = FakeHandler("/api/settings", user=None)
    handled, _ = run(h)
    assert handled is True
    assert h.error == 401
    h.wfile.write.assert_not_called()


def test_get_settings_merges_user_fields_for_session():
    h = FakeHandler("/api/settings")
    singletons = _singletons()
    singletons[1].get_user.return_value.data.smart_collections = [{"id": "c1"}]
    handled, _ = run(h, singletons)
    assert handled is True
    assert h.body()["smart_collections"] == [{"id": "c1"}]


def test_post_settings_anonymous_is_rejected():
    """Behoben. Der Mangel stand hier seit einem früheren Nachtlauf als xfail:

        "POST /api/settings hat keinen Session-Check — config.save() läuft
         auch für anonyme Requests"

    Er stimmte: Die Prüfung stand hinter `config.save()`, eine anonyme Anfrage
    konnte also Scan-Schwellen, ffmpeg-Pfade, `proxy_root` und `review_dir`
    schreiben und scheiterte erst danach still am fehlenden Nutzer. Die Prüfung
    steht jetzt vor dem Lesen des Rumpfes.
    """
    h = FakeHandler("/api/settings", user=None, body={"bitrate_threshold_kbps": 1})
    handled, singletons = run(h, post=True)
    assert handled is True
    assert h.error == 401
    singletons[0].save.assert_not_called()


def test_post_settings_splits_user_fields_from_global_config():
    h = FakeHandler("/api/settings", body={
        "bitrate_threshold_kbps": 9000,
        "smart_collections": [{"id": "c1"}],
        "scan_targets": ["/lib"],
    })
    handled, singletons = run(h, post=True)
    assert handled is True
    config, user_db = singletons[0], singletons[1]
    saved = config.save.call_args.args[0]
    assert "smart_collections" not in saved
    assert "scan_targets" not in saved
    assert saved["bitrate_threshold_kbps"] == 9000
    user_db.add_user.assert_called_once()


def test_post_settings_oversized_body_rejected():
    h = FakeHandler("/api/settings", body={})
    h.headers = {"Content-Length": str(10 * 1024 * 1024)}
    handled, singletons = run(h, post=True)
    assert handled is True
    assert h.error == 413
    singletons[0].save.assert_not_called()


# --- /api/restore: Sitzung und Admin ---
#
# Die Route hatte **gar keine** Prüfung. Am echten Server belegt: eine
# anonyme Anfrage überschrieb proxy_root und review_dir. Unter den
# Einstellungen steht auch ffprobe_path — das Programm, das der Scanner
# ausführt. Derselbe Fehler war für POST /api/settings schon einmal behoben
# worden (siehe dort); die Nachbar-Route hatte ihn behalten.
#
# Admin, nicht nur angemeldet: Restore ersetzt Einstellungen, die alle Konten
# betreffen (UMSETZUNGSPLAN, Phase 5).

def _restore(user, is_admin=False):
    handler = FakeHandler("/api/restore", user=user,
                          body={"proxy_root": "/tmp/angreifer"})
    config = MagicMock()
    config.save.return_value = True
    account = MagicMock()
    account.is_admin = is_admin
    user_db = MagicMock()
    user_db.get_user.return_value = account if user else None
    with patch.object(settings, "_get_singletons",
                      return_value=(config, user_db, MagicMock(), 10_000)):
        settings.handle_post(handler)
    return handler, config


def test_restore_rejects_anonymous_callers():
    handler, config = _restore(user=None)
    assert handler.error == 401
    config.save.assert_not_called()


def test_restore_rejects_non_admins():
    handler, config = _restore(user="kim", is_admin=False)
    assert handler.error == 403
    config.save.assert_not_called()


def test_restore_works_for_admins():
    handler, config = _restore(user="boss", is_admin=True)
    assert handler.error is None
    config.save.assert_called_once_with({"proxy_root": "/tmp/angreifer"})


# --- Globale Einstellungen nur für Admins (Entscheidung 2026-10-02) ---
#
# POST /api/settings ließ jedes angemeldete Konto die *globalen* Schlüssel
# schreiben — Scan-Schwellen, proxy_root, review_dir, ffprobe_path/ffmpeg_path,
# also auch, welches Programm der Server ausführt. Nicht-Admins behalten ihre
# eigenen Felder; globale werden verworfen und in der Antwort genannt. Ein 403
# ginge nicht: Der Dialog schickt bei jedem Speichern alles mit.

def _as(is_admin):
    singletons = _singletons()
    singletons[1].get_user.return_value.is_admin = is_admin
    return singletons


def test_a_non_admin_cannot_write_global_keys():
    h = FakeHandler("/api/settings", user="kim", body={
        "ffprobe_path": "/tmp/boese",
        "proxy_root": "/tmp/x",
        "min_size_mb": 1,
        "scan_targets": ["/media/kim"],
    })
    singletons = _as(is_admin=False)
    run(h, singletons, post=True)

    config, user_db = singletons[0], singletons[1]
    saved = config.save.call_args[0][0] if config.save.called else {}
    assert "ffprobe_path" not in saved and "proxy_root" not in saved and "min_size_mb" not in saved
    assert user_db.get_user.return_value.data.scan_targets == ["/media/kim"], (
        "Die eigenen Felder müssen trotzdem gespeichert werden"
    )
    body = h.body()
    assert body["success"] is True
    assert body["ignored"] == ["ffprobe_path", "min_size_mb", "proxy_root"]


def test_a_non_admin_may_still_save_views():
    """Gespeicherte Ansichten legt jeder an; nutzereigen werden sie mit Phase 2."""
    h = FakeHandler("/api/settings", user="kim", body={"saved_views": [{"name": "Urlaub"}]})
    singletons = _as(is_admin=False)
    run(h, singletons, post=True)
    singletons[0].save.assert_called_once_with({"saved_views": [{"name": "Urlaub"}]})


def test_an_admin_writes_global_keys():
    h = FakeHandler("/api/settings", user="boss", body={"proxy_root": "/srv/p", "min_size_mb": 5})
    singletons = _as(is_admin=True)
    run(h, singletons, post=True)
    singletons[0].save.assert_called_once_with({"proxy_root": "/srv/p", "min_size_mb": 5})
    assert h.body()["ignored"] == []


@pytest.mark.parametrize("is_admin", [True, False])
def test_get_settings_reports_the_admin_flag(is_admin):
    h = FakeHandler("/api/settings")
    run(h, _as(is_admin=is_admin))
    assert h.body()["is_admin"] is is_admin
