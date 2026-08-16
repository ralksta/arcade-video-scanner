# Proxy Streaming — Technical Deep-Dive

> `arcade_scanner/core/proxy_resolver.py` · `core/master_detect.py` · `scripts/generate_proxies.py`

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Path Mapping](#path-mapping)
4. [Location Detection](#location-detection)
5. [Master Detection](#master-detection)
6. [Configuration](#configuration)
7. [CLI Reference — generate_proxies.py](#cli-reference--generate_proxiespy)
8. [Known Limitations](#known-limitations)

---

## Overview

Camera source files are unstreamable over a mobile link. A 4K clip straight out of a
Leica or an iPhone runs at 60–600 Mbit/s; no cellular connection plays that, and a
weak server cannot transcode it on the fly either.

Proxy streaming solves this without touching the library: a smaller copy of a video
may live in a separate directory tree, and `/stream` decides **per request** which
file to send.

**Key design goals:**

- **Originals are never modified.** The generator only reads them. Nothing in the
  serving path writes.
- **No duplicate entries.** The proxy tree is excluded from scans automatically, so
  every video stays a single row in the library.
- **Invisible to clients.** Browser, TV and iOS clients keep requesting the original
  path. No client change was needed.
- **Fail safe.** No proxy, unreadable config, feature off → the original is served,
  exactly as before.
- **Zero cost when unused.** Leaving `proxy_root` empty short-circuits the resolver
  before it touches the filesystem.

---

## Architecture

```
GET /stream?path=/media/shoots/2024_01/clip.MOV
      │
      ├─ authentication                       (unchanged)
      ├─ is_path_allowed(path)                (unchanged — checks the ORIGINAL)
      │
      ├─ resolve_stream_path(path, client_ip, override)
      │     │
      │     ├─ override is False ──────────────────────────► original
      │     ├─ feature disabled (no proxy_root) ───────────► original
      │     ├─ override is not True and client is on LAN ──► original
      │     ├─ proxy file does not exist ──────────────────► original
      │     └─ otherwise ──────────────────────────────────► proxy
      │
      └─ serve_file_range(chosen, extra_headers={"X-Arcade-Variant": …})
             HTTP 200 / 206 with byte ranges — seeking works on either file
```

The security check runs on the path **from the request**. The proxy path is derived
from that already-validated path and never comes from user input, so it needs no
second whitelist pass.

`do_GET` and `do_HEAD` must make the identical decision — a HEAD reporting the
original's size followed by a GET serving the proxy breaks `AVPlayer` and several TV
media pipelines. Both call the same resolver.

---

## Path Mapping

The **complete** original path is mirrored below the proxy root, so files from
different mounts cannot collide. The extension always becomes `.mp4`.

| Original | Proxy (`proxy_root` = `/proxies`) |
|---|---|
| `/media/shoots/2024_01/clip.MOV` | `/proxies/media/shoots/2024_01/clip.mp4` |
| `/archive/shoots/2024_01/clip.MOV` | `/proxies/archive/shoots/2024_01/clip.mp4` |
| `/proxies/media/…/clip.mp4` | *(none — no proxy of a proxy)* |

---

## Location Detection

`is_remote_client()` classifies the requesting address:

| Address range | Verdict | Rationale |
|---|---|---|
| `10/8`, `172.16/12`, `192.168/16`, loopback, link-local | **local** | home network — full quality |
| `100.64.0.0/10` | **remote** | Tailscale CGNAT |
| `fd7a:115c:a1e0::/48` | **remote** | Tailscale IPv6 |
| any other public address | **remote** | |
| empty or unparseable | **remote** | see below |

IPv4-mapped IPv6 addresses (`::ffff:192.168.2.10`) are unwrapped first.

Unknown addresses deliberately fall to **remote**. The error costs are asymmetric: a
wrongly served proxy costs picture quality, a wrongly served 600 Mbit original costs
playback entirely.

The address is taken from `X-Forwarded-For` when present, otherwise from the socket.
XFF is forgeable — harmless here, since the worst outcome is a different quality tier
of a file the caller may already access.

Manual override per request: `?proxy=1` forces the proxy, `?proxy=0` forces the
original. `?proxy=0` short-circuits before the configuration is consulted.

---

## Master Detection

`generate_proxies.py` skips camera source files: they are the bulk of the storage and
are not what you watch on the road. Filenames alone are not reliable in a grown
library, so `core/master_detect.py` combines several signals and detects raw material
**positively**:

| Signal | Examples |
|---|---|
| Folder name | `source/`, `originals/`, `raw/`, `src/`, `master/`, `source videos/` |
| Keyword in the name | `source`, `master`, `untouched`, `unbearbeitet` — including concatenations like `Fujisource.MOV` |
| Camera filename scheme | `IMG_1234`, `DSCF0480`, `L1000689`, `GX010740`, `A001_01021446_C006`, `MVI_`, `DJI_`, `C0012`, iOS UUID names |
| Device-only name | `iphone.MOV`, `iphone2.MOV`, `gopro.mp4` |

Everything else counts as an edit. The reasoning: cameras assign schematic names, so a
descriptive name was typed by a human — and humans name what they exported, not what
fell out of the camera.

Precedence rules:

- A master signal **in the filename** beats an edit keyword. `source_fullclip_4k60.mov`
  is raw material; the name was chosen deliberately.
- A master signal from the **folder only**, combined with an edit keyword, yields
  `unclear` — `source/fullclip_4k60.mov` needs a human decision.
- Separators are normalised before matching, because `\b` does not match between `_`
  and a letter. Without that, `05_2025_Session_Final.mov` would look unlabelled.

Sessions are grouped by their dated project folder, so `originals/`, `hdr final/` and
`sdr/` count as one shoot. That matters for `--no-orphan-masters`: raw material whose
session contains nothing else playable still gets a proxy by default, otherwise there
would be nothing to watch from that shoot at all.

---

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `proxy_streaming` | `true` | Master switch for the substitution |
| `proxy_root` | `""` | Directory holding the proxies. **Empty disables the feature.** |

Both are settable in the UI (Settings → Proxy Streaming), in `settings.json`, or via
the environment (`ARCADE_PROXY_STREAMING`, `ARCADE_PROXY_ROOT`).

`proxy_root` is added to the scan exclusions automatically in
`config.active_exclude_paths`, so the proxies never enter the library.

Response header `X-Arcade-Variant: proxy|original` reports what was served — useful
for verifying the behaviour from a phone.

---

## CLI Reference — `generate_proxies.py`

Runs on the scanner host, encodes on a remote machine with an NVIDIA GPU:

```
Original --rsync--> remote --ffmpeg/NVENC--> remote --rsync--> proxy tree
```

Originals are only read. Writes happen below `--proxy-root` and only after a complete
transfer (download to `.part`, then rename), so an abort never leaves a truncated file
that the server would then serve.

The run is resumable — existing proxies are skipped.

```bash
# Scanner without Docker: database paths are already host paths
python3 scripts/generate_proxies.py --remote gpubox --dry-run

# Scanner in Docker: map each mounted media directory
python3 scripts/generate_proxies.py --remote gpubox \
    --mount /media=/srv/media --mount /photos=/srv/photos \
    --tree /media/clips/ --limit 3
```

| Flag | Default | Purpose |
|---|---|---|
| `--remote` | *required* | SSH target of the GPU machine |
| `--remote-dir` | `~/arcade-proxy-work` | Work directory there; needs room for the largest file |
| `--mount CONTAINER=HOST` | *(none)* | Path translation, repeatable. Without it paths are assumed identical. |
| `--proxy-root` | from settings | Destination tree |
| `--tree` | `/` | Only files below this container path |
| `--min-mbps` / `--max-mbps` | `20` / `100` | Bitrate window of the candidates |
| `--height` | `1920` | Longest edge; landscape becomes 1920×1080, portrait 1080×1920 |
| `--bitrate` | `6` | Target bitrate in Mbit/s |
| `--exclude-file` | `arcade_data/proxy_exclude.txt` | Container paths that never get a proxy |
| `--no-orphan-masters` | off | Skip raw material even when its session has no alternative |
| `--limit` / `--force` / `--dry-run` | | Partial runs, re-encode, preview |

Encoding: `hevc_nvenc`, preset `p5`, VBR with `-cq 28`, CUDA decode, AAC 128k stereo,
`+faststart`. 10-bit sources stay 10-bit (`main10`/`p010le`) so HDR survives.

---

## Known Limitations

1. **"LAN means home"** — on a VPS there is no private network, so every request
   would be classified remote and get the proxy.
2. **Unreadable addresses downgrade silently.** A malformed `X-Forwarded-For` yields a
   proxy without any warning. Deliberate (see above), but worth knowing when the
   server sits behind a reverse proxy.
3. **`generate_proxies.py` requires a *remote* GPU.** A local GPU has no code path yet;
   a `--local` mode would be the obvious addition.
4. **No automatic invalidation.** Replacing an original does not refresh its proxy —
   re-run with `--force` for those files.

---

*Last updated: proxy streaming v1 — resolver, master detection, remote NVENC generator.*
