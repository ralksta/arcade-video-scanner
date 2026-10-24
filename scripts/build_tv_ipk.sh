#!/usr/bin/env bash
# Baut den TV-Client (tv_client/) und packt ihn als .ipk für webOS.
#
# Aufruf aus dem Repo-Wurzelverzeichnis:  scripts/build_tv_ipk.sh
#
# Ergebnis: tv_client/ipk/com.arcade.scanner.tv_<version>_all.ipk
# (von Git ignoriert). Aufspielen danach wie gewohnt, z. B. mit ares-install.
#
# Die Enact-CLI ist keine Projektabhängigkeit; sie kommt per npx in den
# npm-Cache, nicht global; ebenso ares-package, falls die webOS-CLI nicht
# installiert ist.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/tv_client"

echo "→ Abhängigkeiten (npm ci)"
npm ci --no-audit --no-fund >/dev/null

echo "→ Produktions-Build (enact pack -p)"
node prebuild.js
npx --yes -p @enact/cli enact pack -p >/dev/null
echo "  fertig: tv_client/dist"

# Global installierte webOS-CLI bevorzugen, sonst über npx (npm-Cache).
if command -v ares-package >/dev/null 2>&1; then
    ARES_PACKAGE=(ares-package)
else
    ARES_PACKAGE=(npx --yes -p @webos-tools/cli ares-package)
fi

mkdir -p ipk
"${ARES_PACKAGE[@]}" dist -o ipk >/dev/null
echo "✓ $(ls -t ipk/*.ipk | head -1)"
