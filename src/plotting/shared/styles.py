import matplotlib.pyplot as plt
import scienceplots  # Register scienceplots styles with matplotlib

# ============================================================================
# Common settings across all themes
# ============================================================================
COMMON_RC = {
    "text.usetex": False,
    "lines.markersize": 6,
    "legend.fontsize": 12,
    "axes.grid": False,
}

# ============================================================================
# Color Palettes
# ============================================================================
PRISM_RAIN_PALETTE = [
    # Primary vibrant colors (classic, high-contrast)
    "#e41a1c",  # red
    "#377eb8",  # blue
    "#4daf4a",  # green
    "#984ea3",  # purple
    "#ff7f00",  # orange

    # Extended vivid tones (brighter, neon-like accents)
    "#00bfc4",  # cyan-teal
    "#f781bf",  # pink
    "#ffd92f",  # bright yellow
    "#a65628",  # warm brown-orange
    "#8dd3c7",  # aqua-mint

]

DEEP_RAIN_PALETTE = [
    # Deep accents (maintain contrast)
    "#b2182b",  # crimson
    "#2166ac",  # royal blue
    "#1a9850",  # rich green
    "#762a83",  # deep violet
    "#e08214",  # vivid amber 
    
    # Extended vivid tones (brighter, neon-like accents)
    "#88C0D0",  # cyan-teal
    "#CC78BC",  # pink
    "#EBCB8B",  # bright yellow
    "#BF616A",  # warm brown-orange
    "#00b3b3",  # aqua-mint
]


PRISM_RAIN_PALETTE_VIVID = [
    
    "#ff0054", 
    "#0099ff", 
    "#00cc66", 
    "#cc33ff", 
    "#ffaa00",
    
    "#00e6e6", 
    "#ff66b2", 
    "#ffe600", 
    "#ff3300", 
    "#00b3b3",
    
    "#3366ff", 
    "#66ff33", 
    "#9933ff", 
    "#ff9933", 
    "#33ccff",
]

# Minimal palette (professional, understated)
MINIMAL_PALETTE= [
    
    '#2E3440',  # Dark gray
    '#5E81AC',  # Blue
    '#88C0D0',  # Light blue
    '#81A1C1',  # Medium blue
    '#BF616A',  # Red
    '#D08770',  # Orange
    '#EBCB8B',  # Yellow
    '#A3BE8C',  # Green
    '#B48EAD',  # Purple
        ]

# Scientific publication palette (Nature-inspired)
SCIENTIFIC_PALETTE = [
    
    '#0173B2',  # Blue
    '#DE8F05',  # Orange
    '#029E73',  # Green
    '#CC78BC',  # Purple
    "#b2182b",  # Brown
    '#ECE133',  # Yellow
    '#56B4E9', # Sky blue
    "#762a83"
    ]

# ============================================================================
# Theme Definitions
# ============================================================================
THEMES = {
    "prism_rain": {
        "base": ["science"],
        "rc": {
            **COMMON_RC,
            
            # Background colors
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",
            
            # Typography - FIXED SIZES FOR BETTER BALANCE
            "font.family": "serif",  # ← FIXED (was "serif")
            "font.sans-serif": ["Source Sans Pro Black", "Source Sans 3"],
            "font.size": 35,              # ← REDUCED from 35
            
            "axes.labelsize": 55,         # ← REDUCED from 55 (axis labels)
            "axes.titlesize": 55,         # ← REDUCED from 55 (title)
            "axes.labelweight": "normal",
            
            # Axes and ticks
            "axes.edgecolor": "#222222",
            "axes.labelcolor": "#222222",
            "axes.linewidth": 3.5,        # ← REDUCED from 3.5
            
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "xtick.major.size": 10.0,      # ← REDUCED from 10.0
            "ytick.major.size": 10.0,      # ← REDUCED from 10.0
            "xtick.major.width": 2,
            "ytick.major.width": 2,
            "xtick.labelsize": 55,        # ← REDUCED from 55 (tick numbers!)
            "ytick.labelsize": 55,        # ← REDUCED from 55 (tick numbers!)
            "xtick.major.pad": 20,        # ← REDUCED from 20
            "ytick.major.pad": 20,        # ← REDUCED from 20
            
            # Grid
            "grid.color": "#cccccc",
            "grid.linestyle": "--",
            "grid.linewidth": 0.4,
            "grid.alpha": 0.6,
            
            # Lines and markers
            "lines.linewidth": 4,         # ← REDUCED from 6
            "lines.markersize": 22,       # ← REDUCED from 22
            "lines.antialiased": True,
            
            # Legend
            "legend.frameon": False,
            "legend.fontsize": 30,        # ← REDUCED from 35
            "legend.loc": "best",
            "legend.fancybox": True,
            
            # Figure size (optimized for papers)
            "figure.figsize": (20, 20),
            "figure.dpi": 100,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,
            
            # Color cycle
            "axes.prop_cycle": plt.cycler(color=PRISM_RAIN_PALETTE),
        }
    },

    # ========================================================================
    # PAPER THEME - Publication quality (journals, conferences)
    # ========================================================================
    "paper": {
        "base": ["science", "ieee"],
        "rc": {
            **COMMON_RC,

            # Background colors
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",

            # Typography - SMALL for publications
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
            "font.size": 10,

            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "axes.labelweight": "normal",

            # Axes and ticks - THIN for publications
            "axes.edgecolor": "#000000",
            "axes.labelcolor": "#000000",
            "axes.linewidth": 1.0,

            "xtick.color": "#000000",
            "ytick.color": "#000000",
            "xtick.major.size": 4.0,
            "ytick.major.size": 4.0,
            "xtick.major.width": 1.0,
            "ytick.major.width": 1.0,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "xtick.major.pad": 4,
            "ytick.major.pad": 4,

            # Grid - SUBTLE for publications
            "grid.color": "#cccccc",
            "grid.linestyle": "--",
            "grid.linewidth": 0.3,
            "grid.alpha": 0.4,

            # Lines and markers - THIN for publications
            "lines.linewidth": 1.5,
            "lines.markersize": 4,
            "lines.antialiased": True,

            # Legend - SMALL for publications
            "legend.frameon": True,
            "legend.fontsize": 9,
            "legend.loc": "best",
            "legend.fancybox": False,
            "legend.framealpha": 0.9,
            "legend.edgecolor": "#000000",

            # Figure size - SMALL for single-column journals
            "figure.figsize": (3.5, 2.5),
            "figure.dpi": 100,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,

            # Color cycle - SCIENTIFIC palette
            "axes.prop_cycle": plt.cycler(color=SCIENTIFIC_PALETTE),
        }
    },

    # ========================================================================
    # PRESENTATION THEME - Conference slides and posters
    # ========================================================================
    "presentation": {
        "base": ["science"],
        "rc": {
            **COMMON_RC,

            # Background colors
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",

            # Typography - EXTRA LARGE for presentations
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "font.size": 18,

            "axes.labelsize": 24,
            "axes.titlesize": 28,
            "axes.labelweight": "bold",

            # Axes and ticks - THICK for visibility
            "axes.edgecolor": "#222222",
            "axes.labelcolor": "#222222",
            "axes.linewidth": 2.5,

            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "xtick.major.size": 8.0,
            "ytick.major.size": 8.0,
            "xtick.major.width": 2.0,
            "ytick.major.width": 2.0,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "xtick.major.pad": 8,
            "ytick.major.pad": 8,

            # Grid - VISIBLE for presentations
            "grid.color": "#cccccc",
            "grid.linestyle": "-",
            "grid.linewidth": 0.8,
            "grid.alpha": 0.3,

            # Lines and markers - THICK for visibility
            "lines.linewidth": 3.5,
            "lines.markersize": 10,
            "lines.antialiased": True,

            # Legend - LARGE for presentations
            "legend.frameon": True,
            "legend.fontsize": 18,
            "legend.loc": "best",
            "legend.fancybox": True,
            "legend.framealpha": 0.9,

            # Figure size - LARGE for projectors
            "figure.figsize": (10, 7),
            "figure.dpi": 100,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,

            # Color cycle - VIVID palette
            "axes.prop_cycle": plt.cycler(color=PRISM_RAIN_PALETTE_VIVID),
        }
    },

    # ========================================================================
    # MINIMAL THEME - Clean minimalist for web dashboards
    # ========================================================================
    "minimal": {
        "base": ["science", "no-latex"],
        "rc": {
            **COMMON_RC,

            # Background colors
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",

            # Typography - CLEAN sans-serif
            "font.family": "sans-serif",
            "font.sans-serif": ["Source Sans Pro", "Arial", "Helvetica", "sans-serif"],
            "font.size": 12,

            "axes.labelsize": 13,
            "axes.titlesize": 14,
            "axes.labelweight": "normal",

            # Axes and ticks - SUBTLE
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#333333",
            "axes.linewidth": 1.5,

            "xtick.color": "#444444",
            "ytick.color": "#444444",
            "xtick.major.size": 5.0,
            "ytick.major.size": 5.0,
            "xtick.major.width": 1.5,
            "ytick.major.width": 1.5,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "xtick.major.pad": 6,
            "ytick.major.pad": 6,

            # Grid - LIGHT
            "grid.color": "#dddddd",
            "grid.linestyle": "-",
            "grid.linewidth": 0.5,
            "grid.alpha": 0.5,

            # Lines and markers - MEDIUM
            "lines.linewidth": 2.0,
            "lines.markersize": 6,
            "lines.antialiased": True,

            # Legend - CLEAN
            "legend.frameon": False,
            "legend.fontsize": 11,
            "legend.loc": "best",
            "legend.fancybox": False,

            # Figure size - MEDIUM for web
            "figure.figsize": (8, 6),
            "figure.dpi": 100,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,

            # Color cycle - MINIMAL palette
            "axes.prop_cycle": plt.cycler(color=MINIMAL_PALETTE),
        }
    },
}

# ============================================================================
# Helper function to apply theme
# ============================================================================
def set_plot_style(theme_name="prism_rain"):
    """Apply a publication-ready matplotlib theme.
    
    Parameters
    ----------
    theme_name : str, default="prism_rain"
        Name of the theme to apply
        
    Example
    -------
    >>> set_plot_style("prism_rain")
    >>> plt.plot([1, 2, 3], [1, 4, 9])
    >>> plt.show()
    """
    if theme_name not in THEMES:
        raise ValueError(f"Theme '{theme_name}' not found. Available: {list(THEMES.keys())}")
    
    theme = THEMES[theme_name]
    
    # Apply base styles if specified
    if "base" in theme:
        for base_style in theme["base"]:
            try:
                plt.style.use(base_style)
            except OSError:
                print(f"Warning: Base style '{base_style}' not found, skipping...")
    
    # Apply custom rc parameters
    plt.rcParams.update(theme["rc"])
    print(f"✓ Applied '{theme_name}' theme")