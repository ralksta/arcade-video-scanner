"""
Arcade Scanner Design System — single source of truth for visual tokens.

Ersetzt die frueheren drei Themes (Arcade/Professional/Candy) durch EIN
dark-first Theme mit genau einem Brand-Accent (Magenta) und einer kleinen
Menge semantischer Farben, die ausschliesslich fuer Badges verwendet werden.

Token-Konvention:
    --ds-<name>       fertiger Farbwert (Hex/rgba) fuer handgeschriebenes CSS
    --ds-<name>-rgb   nur die RGB-Kanaele, damit Tailwind Opacity-Modifier
                      (z.B. bg-accent/20) korrekt aufloesen kann
Die Legacy-Variablen (--arcade-*, --text-*) bleiben als Aliase bestehen, damit
noch nicht migrierte Templates/JS-Dateien automatisch die neue Palette erben.
"""

import json

# ==============================================================================
# TOKENS
# ==============================================================================

# Neutrale Flaechenskala: (light, dark)
SURFACES = {
    "bg": ("#f6f6f8", "#0b0b10"),
    "surface": ("#ffffff", "#15151d"),
    "surface-2": ("#ffffff", "#1a1a24"),
    "border": ("#e2e2e6", "#2a2a35"),
    "text": ("#15151d", "#f2f2f5"),
    "text-muted": ("#5c5c66", "#6b6b76"),
    # Fliesstext sitzt zwischen text und text-muted
    "text-body": ("#3a3a44", "#c7c7cf"),
    # Eyebrow/Label-Grau
    "text-label": ("#6b6b76", "#9a9aa6"),
    # Kopfzeile sitzt minimal ueber dem Hintergrund
    "header": ("#ffffff", "#101015"),
    "sidebar": ("#ffffff", "#0e0e13"),
    "card": ("#ffffff", "#14141a"),
}

# Brand + Semantik. Identisch in Light und Dark — nur EIN Accent.
BRAND = {
    "accent": "#c4179f",
    "accent-hover": "#e34fc0",
    "accent-tint": "#e879c6",
    # Semantische Farben ausschliesslich fuer Badges/Readouts:
    "hevc": "#22d3c7",
    "av1": "#a78bfa",
    "bitrate": "#f2b544",
    "optimized": "#4ade80",
    "danger": "#f36969",
}

SPACING = [4, 8, 12, 16, 24, 32, 48]
RADII = {"xs": 4, "sm": 6, "md": 8, "lg": 10}

FONT_SANS = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FONT_MONO = "ui-monospace, 'SF Mono', 'Cascadia Code', Menlo, Consolas, monospace"


def _rgb(hex_color: str) -> str:
    """'#c4179f' -> '196 23 159' (Tailwind-Alpha-kompatibel)."""
    h = hex_color.lstrip("#")
    return " ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


class Theme:
    """
    Das (einzige) Theme. Die Klasse bleibt als Objekt erhalten, weil
    ui_components/dashboard_template semantische Klassenstrings von ihr beziehen.
    """

    name = "arcade"

    # --- Layout-Konstanten ---
    sidebar_width = "200px"

    # --- Semantische Klassen ---
    app_bg = "bg-arcade-bg min-h-screen font-sans text-text-main antialiased"
    header_container = (
        "fixed top-0 left-0 right-0 z-50 h-[46px] md:h-[52px] flex items-center "
        "justify-between px-3 md:px-[22px] bg-header border-b border-line/60"
    )
    sidebar_container = (
        "hidden md:flex flex-col w-[200px] fixed left-0 top-[52px] bottom-0 "
        "bg-sidebar border-r border-line/60 px-3 py-4 gap-0.5 z-[100]"
    )

    text_primary = "text-text-main"
    text_secondary = "text-text-muted"

    def button_nav(self, active: bool = False) -> str:
        """Nav-Row laut Spec: 9px/10px Padding, 6px Radius, 10px Gap."""
        base = (
            "group relative flex items-center gap-2.5 px-2.5 py-2.5 rounded-md "
            "text-[13px] w-full text-left transition-colors"
        )
        if active:
            return f"{base} bg-accent/[0.12] text-text-main font-semibold"
        return f"{base} text-label font-normal hover:bg-[var(--ds-fill-soft)] hover:text-text-main"

    # --- Rendering ---
    def render_tailwind_config(self) -> str:
        """Tailwind-Config: Farben zeigen auf die RGB-Kanal-Variablen, damit
        Utility-Modifier wie `bg-accent/20` echte Transparenz erzeugen."""

        def c(token: str) -> str:
            return f"rgb(var(--ds-{token}-rgb) / <alpha-value>)"

        colors = {
            # Neue semantische Namen
            "bg": c("bg"),
            "surface": c("surface"),
            "surface-2": c("surface-2"),
            "line": c("border"),
            "card": c("card"),
            "header": c("header"),
            "sidebar": c("sidebar"),
            "body-text": c("text-body"),
            "label": c("text-label"),
            "accent": c("accent"),
            "accent-hover": c("accent-hover"),
            "accent-tint": c("accent-tint"),
            "hevc": c("hevc"),
            "av1": c("av1"),
            "bitrate": c("bitrate"),
            "optimized": c("optimized"),
            "danger": c("danger"),
            # Legacy-Aliase — zeigen bewusst auf den EINEN Accent bzw. die
            # passende semantische Farbe, damit nicht migrierte Dateien
            # automatisch konform werden.
            "arcade-bg": c("bg"),
            "text-main": c("text"),
            "text-muted": c("text-muted"),
            "arcade-cyan": c("accent"),
            "arcade-magenta": c("accent"),
            "arcade-pink": c("accent-hover"),
            "arcade-gold": c("bitrate"),
        }

        config = {
            "darkMode": "class",
            "theme": {
                "extend": {
                    "colors": colors,
                    "fontFamily": {
                        "sans": ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
                        "mono": [
                            "ui-monospace", "SF Mono", "Cascadia Code",
                            "Menlo", "Consolas", "monospace",
                        ],
                    },
                    "borderRadius": {f"ds-{k}": f"{v}px" for k, v in RADII.items()},
                    "spacing": {f"ds-{v}": f"{v}px" for v in SPACING},
                }
            },
        }
        return f"""
        <script>
            tailwind.config = {json.dumps(config)};
        </script>
        """

    def render_css_variables(self) -> str:
        return render_theme_css()


# Aktive Instanz. `BaseTheme` bleibt als Alias erhalten (Type-Hints/Importe).
CURRENT_THEME = Theme()
BaseTheme = Theme


def _var_block(mode_index: int) -> str:
    """Erzeugt alle Custom Properties fuer light (0) bzw. dark (1)."""
    lines = []
    for token, pair in SURFACES.items():
        value = pair[mode_index]
        lines.append(f"    --ds-{token}: {value};")
        lines.append(f"    --ds-{token}-rgb: {_rgb(value)};")
    for token, value in BRAND.items():
        lines.append(f"    --ds-{token}: {value};")
        lines.append(f"    --ds-{token}-rgb: {_rgb(value)};")

    bg, surface, border = (
        SURFACES["bg"][mode_index],
        SURFACES["surface"][mode_index],
        SURFACES["border"][mode_index],
    )
    text, muted = SURFACES["text"][mode_index], SURFACES["text-muted"][mode_index]

    # Hairlines: im Dark-Mode als weisse Low-Opacity-Linien, im Light-Mode schwarz.
    hairline = "rgba(255,255,255,0.08)" if mode_index else "rgba(0,0,0,0.08)"
    hairline_strong = "rgba(255,255,255,0.12)" if mode_index else "rgba(0,0,0,0.12)"
    fill_soft = "rgba(255,255,255,0.05)" if mode_index else "rgba(0,0,0,0.04)"
    fill = "rgba(255,255,255,0.06)" if mode_index else "rgba(0,0,0,0.05)"

    lines += [
        f"    --ds-hairline: {hairline};",
        f"    --ds-hairline-strong: {hairline_strong};",
        f"    --ds-fill-soft: {fill_soft};",
        f"    --ds-fill: {fill};",
        # Legacy-Aliase
        f"    --arcade-bg: {bg};",
        f"    --text-main: {text};",
        f"    --text-muted: {muted};",
        f"    --arcade-magenta: {BRAND['accent']};",
        f"    --arcade-pink: {BRAND['accent-hover']};",
        f"    --arcade-cyan: {BRAND['accent']};",
        f"    --arcade-gold: {BRAND['bitrate']};",
        f"    --arcade-purple: {SURFACES['surface-2'][mode_index]};",
        f"    --surface-glass: {surface};",
        f"    --surface-border: {border};",
    ]
    return "\n".join(lines)


def render_theme_css() -> str:
    """Generiert den <style>-Block mit allen Design-Tokens."""
    spacing_vars = "\n".join(f"    --ds-space-{v}: {v}px;" for v in SPACING)
    radius_vars = "\n".join(f"    --ds-radius-{k}: {v}px;" for k, v in RADII.items())

    return f"""<style>
:root {{
{_var_block(0)}
{spacing_vars}
{radius_vars}
    --ds-font-sans: {FONT_SANS};
    --ds-font-mono: {FONT_MONO};
    color-scheme: light;
}}

.dark {{
{_var_block(1)}
    color-scheme: dark;
}}

html, body {{
    background-color: var(--ds-bg);
    color: var(--ds-text);
    font-family: var(--ds-font-sans);
}}

/* Alle Zahlen-/Pfad-/Codec-Readouts laufen im System-Mono mit tabular-nums */
.font-mono, code, kbd, pre, [style*="tabular-nums"] {{
    font-family: var(--ds-font-mono);
    font-variant-numeric: tabular-nums;
}}

/* --- Design-System Utilities --- */
.ds-eyebrow {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--ds-text-label);
}}

/* Badge-Pattern: bg 16%, Text voll, Border 35% */
.ds-badge {{
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 3px 7px;
    border-radius: 4px;
    font-size: 9.5px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: 0.02em;
    color: rgb(var(--ds-badge-rgb));
    background: rgb(var(--ds-badge-rgb) / 0.17);
    border: 1px solid rgb(var(--ds-badge-rgb) / 0.35);
    backdrop-filter: blur(4px);
}}
.ds-badge-accent {{ --ds-badge-rgb: var(--ds-accent-tint-rgb); }}
.ds-badge-hevc {{ --ds-badge-rgb: var(--ds-hevc-rgb); }}
.ds-badge-av1 {{ --ds-badge-rgb: var(--ds-av1-rgb); }}
.ds-badge-bitrate {{ --ds-badge-rgb: var(--ds-bitrate-rgb); }}
.ds-badge-optimized {{ --ds-badge-rgb: var(--ds-optimized-rgb); }}
.ds-badge-danger {{ --ds-badge-rgb: var(--ds-danger-rgb); }}
.ds-badge-neutral {{
    color: #fff;
    background: rgba(0,0,0,0.6);
    border-color: rgba(255,255,255,0.1);
}}

/* Buttons */
.ds-btn {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-family: var(--ds-font-sans);
    font-size: 13px;
    font-weight: 600;
    padding: 9px 16px;
    border-radius: 6px;
    border: 1px solid transparent;
    cursor: pointer;
    transition: background-color .15s ease, border-color .15s ease, color .15s ease;
}}
.ds-btn-primary {{ background: var(--ds-accent); color: #fff; }}
.ds-btn-primary:hover {{ background: var(--ds-accent-hover); }}
.ds-btn-secondary {{
    background: var(--ds-fill);
    border-color: var(--ds-hairline-strong);
    color: var(--ds-text);
}}
.ds-btn-secondary:hover {{ background: var(--ds-hairline-strong); }}
.ds-btn-danger {{
    background: transparent;
    border-color: rgb(var(--ds-danger-rgb) / 0.4);
    color: var(--ds-danger);
}}
.ds-btn-danger:hover {{ background: rgb(var(--ds-danger-rgb) / 0.12); }}
.ds-btn-ghost {{
    background: transparent;
    color: var(--ds-text-muted);
    padding: 9px 12px;
}}
.ds-btn-ghost:hover {{ color: var(--ds-text); }}

/* Filter-Chips */
.ds-chip {{
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 500;
    background: var(--ds-fill-soft);
    border: 1px solid var(--ds-hairline-strong);
    color: var(--ds-text-body);
    cursor: pointer;
    white-space: nowrap;
    transition: background-color .15s ease, color .15s ease;
}}
.ds-chip:hover {{ background: var(--ds-fill); color: var(--ds-text); }}
.ds-chip.active {{
    background: var(--ds-accent);
    border-color: var(--ds-accent);
    color: #fff;
    font-weight: 600;
}}

/* Toggle-Switch (38x22) */
.ds-switch {{
    position: relative;
    width: 38px;
    height: 22px;
    border-radius: 11px;
    background: var(--ds-hairline-strong);
    border: none;
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color .18s ease;
}}
.ds-switch::after {{
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #8a8a94;
    transition: transform .18s ease, background-color .18s ease;
}}
.ds-switch[aria-checked="true"] {{ background: var(--ds-accent); }}
.ds-switch[aria-checked="true"]::after {{ transform: translateX(16px); background: #fff; }}

/* Fokus: ein Accent-Ring, keine Multi-Color-Glows mehr */
:focus-visible {{
    outline: 2px solid rgb(var(--ds-accent-rgb) / 0.7);
    outline-offset: 2px;
}}
</style>"""
