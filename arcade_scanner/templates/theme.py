import json

class BaseTheme:
    """
    Base Semantic Theme defining the contract and common properties.
    """
    name = "base"
    
    # --- CSS Variables Map ---
    # These will be injected into :root and .dark
    # Format: {'var-name': ('light-value', 'dark-value')}
    css_variables = {
        '--arcade-bg': ('#ffffff', '#000000'),
        '--text-main': ('#000000', '#ffffff'),
        '--text-muted': ('#666666', '#999999'),
        '--arcade-cyan': ('#06b6d4', '#00ffd0'), # Defaults
        '--arcade-gold': ('#d97706', '#F4B342'),
        '--arcade-magenta': ('#be185d', '#8F0177'),
    }

    # --- Tailwind Config Colors ---
    # These map semantic names to CSS variables or raw values
    tailwind_colors = {
        'arcade-bg': 'var(--arcade-bg)',
        'text-main': 'var(--text-main)',
        'text-muted': 'var(--text-muted)',
        'arcade-cyan': 'var(--arcade-cyan)',
        'arcade-gold': 'var(--arcade-gold)',
        'arcade-magenta': 'var(--arcade-magenta)',
    }

    # --- Semantic Classes ---
    app_bg = "bg-arcade-bg min-h-screen transition-colors duration-300 font-sans text-text-main"
    header_container = "fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6 backdrop-blur transition-all duration-300"
    sidebar_container = "hidden md:flex flex-col w-64 fixed left-0 top-16 bottom-0 p-4 gap-1 z-[100] transition-colors duration-300"
    
    # Typography
    text_primary = "text-text-main"
    text_secondary = "text-text-muted"
    
    def button_nav(self, active=False):
        base = "group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all w-full text-left"
        if active:
            return f"{base} bg-black/5 dark:bg-white/5 font-medium text-black dark:text-white"
        return f"{base} text-text-muted hover:bg-black/5 dark:hover:bg-white/5 hover:text-black dark:hover:text-white"

    def render_css_variables(self):
        """Generates the <style> block for CSS variables."""
        light_vars = []
        dark_vars = []
        
        for name, (light, dark) in self.css_variables.items():
            light_vars.append(f"{name}: {light};")
            dark_vars.append(f"{name}: {dark};")
            
        return f"""
        <style>
            :root {{
                {chr(10).join(light_vars)}
            }}
            .dark {{
                {chr(10).join(dark_vars)}
            }}
            body {{
                background-color: var(--arcade-bg);
                color: var(--text-main);
                transition: background-color 0.3s ease, color 0.3s ease;
            }}
        </style>
        """

    def render_tailwind_config(self):
        """Generates the Tailwind config script."""
        config = {
            "darkMode": "class",
            "theme": {
                "extend": {
                    "colors": self.tailwind_colors,
                    "fontFamily": {
                        "sans": ["Inter", "sans-serif"],
                        "mono": ["SF Mono", "monospace"]
                    }
                }
            }
        }
        return f"""
        <script>
            tailwind.config = {json.dumps(config)};
        </script>
        """


class ArcadeTheme(BaseTheme):
    name = "arcade"
    
    css_variables = {
        '--arcade-bg': ('#f8f9fa', '#090012'),
        '--text-main': ('#1a202c', '#ffffff'),
        '--text-muted': ('#64748b', '#9ca3af'),
        
        # Brand Colors
        '--arcade-purple': ('#e2e8f0', '#1a0530'),
        '--arcade-magenta': ('#be185d', '#8F0177'),
        '--arcade-pink': ('#db2777', '#DE1A58'),
        '--arcade-gold': ('#d97706', '#F4B342'),
        '--arcade-cyan': ('#0d9488', '#00ffd0'),
        
        # Surfaces
        '--surface-glass': ('rgba(255, 255, 255, 0.7)', 'rgba(20, 20, 30, 0.6)'),
        '--surface-border': ('rgba(0, 0, 0, 0.1)', 'rgba(255, 255, 255, 0.08)'),
    }
    
    # Semantic overrides
    header_container = "fixed top-0 left-0 right-0 z-50 h-[34px] md:h-16 flex items-center justify-between px-3 md:px-6 pt-safe-top transition-all duration-300 bg-arcade-bg/95 backdrop-blur border-b border-black/5 dark:border-white/5"
    sidebar_container = "hidden md:flex flex-col w-64 fixed left-0 top-16 bottom-0 bg-arcade-bg/50 border-r border-black/5 dark:border-white/5 p-4 gap-1 z-[100]"


class ProfessionalTheme(BaseTheme):
    name = "professional"
    
    css_variables = {
        '--arcade-bg': ('#f3f4f6', '#0f172a'), # Slate-100 / Slate-900
        '--text-main': ('#111827', '#f9fafb'), # Gray-900 / Gray-50
        '--text-muted': ('#6b7280', '#9ca3af'), # Gray-500 / Gray-400
        
        # Re-map semantic colors to Professional Palette (Blue/Teal)
        '--arcade-purple': ('#e0e7ff', '#1e1b4b'), # Indigo
        '--arcade-magenta': ('#be185d', '#831843'), # Pink (Accents)
        '--arcade-pink': ('#db2777', '#be185d'),
        '--arcade-gold': ('#b45309', '#f59e0b'), # Amber
        '--arcade-cyan': ('#0284c7', '#38bdf8'), # Sky Blue (Primary)
        
        '--surface-glass': ('rgba(255, 255, 255, 0.9)', 'rgba(15, 23, 42, 0.9)'),
        '--surface-border': ('#e5e7eb', '#1e293b'),
    }
    
    # Cleaner, solid headers
    header_container = "fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6 bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700 shadow-sm"
    sidebar_container = "hidden md:flex flex-col w-64 fixed left-0 top-16 bottom-0 bg-white dark:bg-slate-800 border-r border-gray-200 dark:border-slate-700 p-4 gap-1 z-[100]"

    def button_nav(self, active=False):
        # Professional buttons are simpler, less neon
        base = "group flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors w-full"
        if active:
            return f"{base} bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
        return f"{base} text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-slate-700 hover:text-gray-900 dark:hover:text-white"


# Active Theme Instance
CURRENT_THEME = ArcadeTheme()
