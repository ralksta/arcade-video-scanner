#!/usr/bin/env bash
# Baut den TV-Client (tv_client/) und packt ihn als .ipk für webOS.
#
# Aufruf aus dem Repo-Wurzelverzeichnis:  scripts/build_tv_ipk.sh
#
# Ergebnis: tv_client/ipk/com.arcade.scanner.tv_<version>_all.ipk
# (von Git ignoriert). Aufspielen danach wie gewohnt, z. B. mit ares-install.
#
# Die Enact-CLI ist keine Projektabhängigkeit; sie kommt per npx in den
# npm-Cache, nicht global. ares-package (webOS CLI) muss installiert sein —
# fehlt es, bleibt der fertige Build in tv_client/dist liegen.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/tv_client"

echo "→ Abhängigkeiten (npm ci)"
npm ci --no-audit --no-fund >/dev/null

echo "→ Produktions-Build (enact pack -p)"
node prebuild.js
npx --yes -p @enact/cli enact pack -p >/dev/null
echo "  fertig: tv_client/dist"

if ! command -v ares-package >/dev/null 2>&1; then
    echo "⚠ ares-package nicht gefunden — .ipk nicht gepackt."
    echo "  webOS CLI installieren (npm install -g @webos-tools/cli), dann erneut aufrufen."
    exit 1
fi

mkdir -p ipk
ares-package dist -o ipk
echo "✓ $(ls -t ipk/*.ipk | head -1)"
