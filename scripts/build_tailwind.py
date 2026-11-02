#!/usr/bin/env python3
"""build_tailwind.py — Extrahiert alle Tailwind-Klassen aus Templates & JS.

Prüft standardmäßig (`--check`), ob kritische Design-System-Utility-Klassen in
`arcade_scanner/server/static/tailwind.css` enthalten sind, oder kompiliert
`tailwind.css` neu, wenn eine lokale Tailwind-Standalone-Engine übergeben wird.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from arcade_scanner.templates.theme import CURRENT_THEME  # noqa: E402

TAILWIND_CSS_PATH = os.path.join(
    PROJECT_ROOT, "arcade_scanner", "server", "static", "tailwind.css"
)


def extract_candidate_tokens() -> list[str]:
    """Scannt alle Python-Templates, JS-Module und HTML-Seiten nach CSS-Tokens."""
    files = (
        glob.glob(os.path.join(PROJECT_ROOT, "arcade_scanner", "templates", "*.py"))
        + glob.glob(
            os.path.join(PROJECT_ROOT, "arcade_scanner", "server", "static", "*.js")
        )
        + glob.glob(
            os.path.join(PROJECT_ROOT, "arcade_scanner", "server", "static", "*.html")
        )
    )
    tokens: set[str] = set()
    token_re = re.compile(r"[!a-zA-Z0-9_\-:/.\[\]%#(),]+")
    for path in files:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        for match in token_re.findall(content):
            if 1 <= len(match) <= 80:
                tokens.add(match)
    return sorted(tokens)


def rebuild_with_bundle(bundle_js_path: str) -> None:
    """Kompiliert tailwind.css mithilfe eines Tailwind-3.4-Standalone-JS-Bundles."""
    tokens = extract_candidate_tokens()
    cfg_js = CURRENT_THEME.render_tailwind_config()
    cfg_obj = cfg_js.split("tailwind.config =", 1)[1].strip().rstrip(";")

    node_script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(bundle_js_path)}, 'utf8');
let capturedStyle = '';
const fakeDoc = {{
  createElement: () => ({{
    set textContent(v) {{ capturedStyle = v; }},
    get textContent() {{ return capturedStyle; }},
    sheet: {{}}
  }}),
  head: {{ append: () => {{}}, appendChild: () => {{}} }},
  querySelectorAll: () => [],
  documentElement: {{
    outerHTML: '<div class=' + JSON.stringify({json.dumps(" ".join(tokens))}) + '></div>'
  }},
  readyState: 'complete',
  addEventListener: () => {{}}
}};
const sandbox = {{
  window: {{ tailwind: {{ config: {cfg_obj} }} }},
  document: fakeDoc,
  MutationObserver: class {{ observe() {{}} disconnect() {{}} }},
  console,
  setTimeout: (fn) => fn(),
  requestAnimationFrame: (fn) => fn(),
   location: {{ protocol: 'https:' }},
  navigator: {{ userAgent: 'Mozilla/5.0' }}
}};
sandbox.window.window = sandbox.window;
sandbox.window.document = fakeDoc;
sandbox.window.MutationObserver = sandbox.MutationObserver;
sandbox.globalThis = sandbox.window;
sandbox.self = sandbox.window;
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
process.stdout.write(capturedStyle);
"""
    res = subprocess.run(
        ["node", "-"], input=node_script, capture_output=True, text=True, check=True
    )
    css = res.stdout
    if len(css) < 10000:
        raise RuntimeError(f"Generiertes CSS unerwartet klein ({len(css)} Bytes)")
    with open(TAILWIND_CSS_PATH, "w", encoding="utf-8") as f:
        f.write("/* Precompiled Tailwind CSS v3.4 for Arcade Media Scanner (offline) */\n")
        f.write(css)
    print(f"✅ {TAILWIND_CSS_PATH} erfolgreich neu gebaut ({len(css)} Bytes, {len(tokens)} Tokens).")


def verify_existing_css() -> int:
    """Prüft, ob tailwind.css existiert und alle Kern-Theme-Klassen enthält."""
    if not os.path.isfile(TAILWIND_CSS_PATH):
        print(f"❌ {TAILWIND_CSS_PATH} fehlt!", file=sys.stderr)
        return 1
    with open(TAILWIND_CSS_PATH, encoding="utf-8") as f:
        css = f.read()
    required_Rules = [
        ".bg-bg",
        ".bg-surface",
        ".bg-card",
        ".text-text-main",
        ".text-accent-tint",
        ".rounded-ds-md",
        ".font-mono",
    ]
    missing = [r for r in required_Rules if r not in css]
    if missing:
        print(f"❌ Fehlende Regeln in tailwind.css: {missing}", file=sys.stderr)
        return 1
    tokens = extract_candidate_tokens()
    print(
        f"✅ tailwind.css ({len(css):,} Bytes) verifiziert — {len(tokens):,} Quell-Tokens gescannt."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        help="Pfad zu einer lokalen Tailwind-3.4-Browser-Engine-JS-Datei zum Neubau",
    )
    args = parser.parse_args()
    if args.bundle:
        rebuild_with_bundle(args.bundle)
        return 0
    return verify_existing_css()


if __name__ == "__main__":
    raise SystemExit(main())
