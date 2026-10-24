"""Tests for arcade_scanner/core/proxy_resolver.py — proxy selection on stream."""

import os
from pathlib import Path

import pytest

from arcade_scanner.core import proxy_resolver as pr

# ── Path mapping ────────────────────────────────────────────────────────────

def test_proxy_path_mirrors_full_original_path():
    got = pr.proxy_path_for("/library/shoots/2024_01/foo.MOV", proxy_root="/proxies")
    assert got == "/proxies/library/shoots/2024_01/foo.mp4"


def test_proxy_path_always_uses_mp4_extension():
    for src in ("a.MOV", "a.mkv", "a.avi", "a.mp4"):
        got = pr.proxy_path_for(f"/media/{src}", proxy_root="/proxies")
        assert got.endswith(".mp4"), src


def test_files_from_different_mounts_do_not_collide():
    a = pr.proxy_path_for("/library/a/foo.MOV", proxy_root="/proxies")
    b = pr.proxy_path_for("/archive/a/foo.MOV", proxy_root="/proxies")
    assert a != b


def test_no_proxy_of_a_proxy():
    """An original already inside the proxy tree gets no proxy of its own."""
    assert pr.proxy_path_for("/proxies/library/a/foo.mp4", proxy_root="/proxies") == ""


def test_empty_root_disables_mapping():
    assert pr.proxy_path_for("/library/a/foo.MOV", proxy_root="") == ""


def test_empty_original_is_handled():
    assert pr.proxy_path_for("", proxy_root="/proxies") == ""


# ── Location detection ──────────────────────────────────────────────────────

@pytest.mark.parametrize("ip", [
    "192.168.2.10",     # home network
    "10.0.0.5",
    "172.16.0.9",
    "127.0.0.1",        # loopback
    "::1",
    "::ffff:192.168.2.10",  # IPv4-mapped
    "169.254.1.1",      # link-local
])
def test_lan_clients_are_not_remote(ip):
    assert pr.is_remote_client(ip) is False


@pytest.mark.parametrize("ip", [
    "100.121.203.26",   # Tailscale (CGNAT)
    "100.64.0.1",
    "100.127.255.254",
    "fd7a:115c:a1e0::1",  # Tailscale IPv6
    "8.8.8.8",          # public internet
])
def test_remote_clients_are_remote(ip):
    assert pr.is_remote_client(ip) is True


@pytest.mark.parametrize("ip", ["", "not-an-ip", "999.999.999.999"])
def test_unknown_ip_defaults_to_remote(ip):
    """When in doubt, proxy: a 600 Mbit original breaks playback outright."""
    assert pr.is_remote_client(ip) is True


# ── Override parameter ──────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("false", False), ("no", False), ("OFF", False),
    (None, None), ("", None), ("maybe", None),
])
def test_parse_override(raw, expected):
    assert pr.parse_override(raw) is expected


# ── Resolution ──────────────────────────────────────────────────────────────

@pytest.fixture
def library(tmp_path, monkeypatch):
    """An original with an existing proxy; feature enabled."""
    original = tmp_path / "media" / "OD" / "clip.MOV"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"x" * 1000)

    root = tmp_path / "Proxies"
    proxy = root / str(original).lstrip("/").replace(".MOV", ".mp4")
    proxy.parent.mkdir(parents=True)
    proxy.write_bytes(b"x" * 10)

    monkeypatch.setattr(pr, "get_proxy_root", lambda: str(root))
    monkeypatch.setattr(pr, "is_proxy_streaming_enabled", lambda: True)
    return str(original), str(proxy)


def test_remote_client_gets_proxy(library):
    original, proxy = library
    path, variant = pr.resolve_stream_path(original, client_ip="100.121.203.26")
    assert (path, variant) == (proxy, "proxy")


def test_lan_client_gets_original(library):
    original, _ = library
    path, variant = pr.resolve_stream_path(original, client_ip="192.168.2.10")
    assert (path, variant) == (original, "original")


def test_override_true_forces_proxy_even_in_lan(library):
    original, proxy = library
    path, variant = pr.resolve_stream_path(original, client_ip="192.168.2.10", override=True)
    assert (path, variant) == (proxy, "proxy")


def test_override_false_forces_original_even_remote(library):
    original, _ = library
    path, variant = pr.resolve_stream_path(original, client_ip="100.121.203.26", override=False)
    assert (path, variant) == (original, "original")


def test_missing_proxy_falls_back_to_original(library, tmp_path, monkeypatch):
    original, proxy = library
    os.remove(proxy)
    path, variant = pr.resolve_stream_path(original, client_ip="100.121.203.26")
    assert (path, variant) == (original, "original")


def test_disabled_feature_always_serves_original(library, monkeypatch):
    original, _ = library
    monkeypatch.setattr(pr, "is_proxy_streaming_enabled", lambda: False)
    path, variant = pr.resolve_stream_path(original, client_ip="100.121.203.26")
    assert (path, variant) == (original, "original")


def test_override_false_short_circuits_before_config(monkeypatch):
    """?proxy=0 must not depend on the configuration."""
    def boom():
        raise AssertionError("config should not be consulted")
    monkeypatch.setattr(pr, "is_proxy_streaming_enabled", boom)
    assert pr.resolve_stream_path("/a/b.MOV", client_ip="", override=False) == ("/a/b.MOV", "original")


# ── Veraltete Proxys ────────────────────────────────────────────────────────
#
# Bis hierher prüfte die Auflösung nur, *ob* ein Proxy existiert. Wird ein
# Original nachbearbeitet, bleibt der alte Proxy liegen und wurde unterwegs
# stillschweigend ausgeliefert — man sah eine Fassung, die es nicht mehr gibt.

def _touch(path, when):
    os.utime(path, (when, when))


def test_fresh_proxy_is_not_stale(library):
    original, proxy = library
    assert pr.is_proxy_stale(original, proxy) is False


def test_proxy_older_than_the_original_is_stale(library):
    original, proxy = library
    _touch(proxy, 1_700_000_000)
    _touch(original, 1_700_000_600)   # zehn Minuten später nachbearbeitet

    assert pr.is_proxy_stale(original, proxy) is True


def test_stale_proxy_is_not_served_to_a_remote_client(library):
    """Korrektheit vor Bandbreite: lieber das große Original als die alte Fassung."""
    original, proxy = library
    _touch(proxy, 1_700_000_000)
    _touch(original, 1_700_000_600)

    path, variant = pr.resolve_stream_path(original, client_ip="100.121.203.26")
    assert (path, variant) == (original, "original")


def test_override_cannot_force_a_stale_proxy(library):
    """?proxy=1 erzwingt den Proxy — aber keinen, der veraltete Inhalte zeigt."""
    original, proxy = library
    _touch(proxy, 1_700_000_000)
    _touch(original, 1_700_000_600)

    path, variant = pr.resolve_stream_path(original, client_ip="192.168.2.10", override=True)
    assert (path, variant) == (original, "original")


def test_small_mtime_differences_are_tolerated(library):
    """
    FAT rundet mtimes auf zwei Sekunden, rsync und SMB verschieben sie um
    Bruchteile. Ohne Toleranz gälte ein frisch erzeugter Proxy gelegentlich
    als veraltet und würde bei jedem Lauf neu erzeugt.
    """
    original, proxy = library
    _touch(proxy, 1_700_000_000)
    _touch(original, 1_700_000_001)   # eine Sekunde Versatz

    assert pr.is_proxy_stale(original, proxy) is False


def test_unreadable_file_counts_as_stale(library, tmp_path):
    """Im Zweifel das Original: eine falsche Antwort ist teurer als Bandbreite."""
    original, _ = library
    assert pr.is_proxy_stale(original, str(tmp_path / "gibtsnicht.mp4")) is True


def test_generator_regenerates_stale_proxies():
    """
    Der Generator übersprang jeden vorhandenen Proxy — ein veralteter wäre also
    nie erneuert worden, und der Server hätte dauerhaft das Original geliefert.
    """
    source = (Path(__file__).parent.parent / "scripts" / "generate_proxies.py").read_text(
        encoding="utf-8"
    )
    assert "is_proxy_stale(host_src, target)" in source
