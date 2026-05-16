import logging
from pathlib import Path

import matplotlib.pyplot as plt
import scienceplots  # Register scienceplots styles with matplotlib
from matplotlib import font_manager

logger = logging.getLogger(__name__)

# Fonts bundled under assets/ are auto-registered with matplotlib so plots
# render the same on any machine, no system install required. Drop any .ttf
# in assets/ and it gets picked up.
_ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"
_fonts_registered = False


def _register_bundled_fonts() -> None:
    """Register every .ttf in assets/ with matplotlib (idempotent)."""
    global _fonts_registered
    if _fonts_registered:
        return
    if not _ASSETS_DIR.exists():
        logger.warning("Fonts assets directory not found: %s", _ASSETS_DIR)
        _fonts_registered = True
        return
    for ttf in sorted(_ASSETS_DIR.rglob("*.ttf")):
        font_manager.fontManager.addfont(str(ttf))
    _fonts_registered = True


# ============================================================================
# Common settings across all themes
# ============================================================================
COMMON_RC = {
    "text.usetex": False,
    "lines.markersize": 6,
    "legend.fontsize": 12,
    "axes.grid": False,
    # Project-wide font: Open Sans (bundled in assets/Open_Sans/static/).
    "font.family": "sans-serif",
    "font.sans-serif": [
        "Open Sans",
        "Source Sans Pro",
        "Source Sans 3",
        "DejaVu Sans",
        "sans-serif",
    ],
    "font.weight": "normal",
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
    # Extended classic tones (high contrast, mature, non-vivid)
    "#4f6d7a",  # Slate Blue / Steel (A quiet, muted slate that bridges blue and grey)
    "#b8326b",  # Deep Rose / Raspberry (Replaces hot pink; rich, heavy, and mature)
    "#8a532b",  # Walnut Brown (A clean, rich chocolate-brown that anchors the set)
    "#d49b00",  # Dark Gold / Mustard (Replaces bright yellow; highly visible but matte)
    "#007a87",  # Deep Teal (Replaces the neon cyan; calm, corporate, and distinct)
]

DEEP_RAIN_PALETTE = [
    # Deep accents (maintain contrast)
    "#b2182b",  # crimson
    "#2166ac",  # royal blue
    "#1a9850",  # rich green
    "#762a83",  # deep violet
    "#e08214",  # vivid amber
    # Extended vivid tones (brighter, neon-like accents)
    "#00b3b3",  # aqua-mint
    "#88C0D0",  # cyan-teal
    "#CC78BC",  # pink
    "#EBCB8B",  # bright yellow
    "#BF616A",  # warm brown-orange
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
MINIMAL_PALETTE = [
    "#2E3440",  # Dark gray
    "#5E81AC",  # Blue
    "#88C0D0",  # Light blue
    "#81A1C1",  # Medium blue
    "#BF616A",  # Red
    "#D08770",  # Orange
    "#EBCB8B",  # Yellow
    "#A3BE8C",  # Green
    "#B48EAD",  # Purple
]

# Scientific publication palette (Nature-inspired)
SCIENTIFIC_PALETTE = [
    "#0173B2",  # Blue
    "#DE8F05",  # Orange
    "#029E73",  # Green
    "#CC78BC",  # Purple
    "#b2182b",  # Brown
    "#ECE133",  # Yellow
    "#56B4E9",  # Sky blue
    "#762a83",
]

# Keys match PlotConfig.palette's Literal values in src/plotting/shared/config.py.
PALETTES: dict[str, list[str]] = {
    "prism_rain": PRISM_RAIN_PALETTE,
    "deep_rain": DEEP_RAIN_PALETTE,
    "scientific": SCIENTIFIC_PALETTE,
    "minimal": MINIMAL_PALETTE,
    "vivid": PRISM_RAIN_PALETTE_VIVID,
}

# Maps PlotConfig.font_family Literal values → matplotlib font.sans-serif names.
_FONT_FAMILY_NAMES: dict[str, str] = {
    "source_sans_pro": "Source Sans Pro",
    "open_sans": "Open Sans",
    "source_sans_3": "Source Sans 3",
}

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
            # Typography (font is set globally in COMMON_RC)
            "font.size": 35,
            "axes.labelsize": 55,
            "axes.titlesize": 55,
            "axes.labelweight": "normal",
            # Axes and ticks
            "axes.edgecolor": "#222222",
            "axes.labelcolor": "#222222",
            "axes.linewidth": 3.5,
            "xtick.color": "#333333",
            "ytick.color": "#333333",
            "xtick.major.size": 10.0,
            "ytick.major.size": 10.0,
            "xtick.major.width": 2,
            "ytick.major.width": 2,
            "xtick.labelsize": 55,
            "ytick.labelsize": 55,
            "xtick.major.pad": 20,
            "ytick.major.pad": 20,
            # Lines and markers
            "lines.linewidth": 4,
            "lines.markersize": 22,
            "lines.antialiased": True,
            # Legend
            "legend.frameon": False,
            "legend.fontsize": 30,
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
        },
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
            # Typography - SMALL for publications (font is set globally in COMMON_RC)
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
        },
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
            # Typography - EXTRA LARGE for presentations (font is set globally in COMMON_RC)
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
        },
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
            # Typography - CLEAN sans-serif (font is set globally in COMMON_RC)
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
        },
    },
}


# ============================================================================
# Helper function to apply theme
# ============================================================================
def set_plot_style(theme_or_config="prism_rain"):
    """Apply a publication-ready matplotlib theme.

    Accepts either a theme name (str) or a ``PlotConfig``. When given a
    ``PlotConfig``, the theme is applied first and then config-derived rc
    overrides (palette, grid, legend) are layered on top.

    Precedence (lowest → highest):
        scienceplots base style(s) → THEMES[name]["rc"] → PlotConfig overrides

    Parameters
    ----------
    theme_or_config : str | PlotConfig, default="prism_rain"
        Theme name, or a ``PlotConfig`` whose ``theme`` field selects the theme.

    Examples
    --------
    >>> set_plot_style("prism_rain")
    >>> from src.plotting.shared.config import PlotConfig
    >>> set_plot_style(PlotConfig(theme="paper", palette="scientific"))
    """
    # Lazy import: config.py doesn't currently import styles, but the lazy
    # form is cheap insurance against future circularity.
    from src.plotting.shared.config import PlotConfig

    if isinstance(theme_or_config, PlotConfig):
        config = theme_or_config
        theme_name = config.theme
    else:
        config = None
        theme_name = theme_or_config

    if theme_name not in THEMES:
        raise ValueError(
            f"Theme '{theme_name}' not found. Available: {list(THEMES.keys())}"
        )

    _register_bundled_fonts()

    theme = THEMES[theme_name]

    # Apply base styles if specified
    for base_style in theme.get("base", []):
        try:
            plt.style.use(base_style)
        except OSError:
            logger.warning("Base style '%s' not found, skipping", base_style)

    # Apply custom rc parameters
    plt.rcParams.update(theme["rc"])

    if config is not None:
        _apply_plot_config_overrides(config)

    logger.debug("Applied '%s' theme", theme_name)


def _apply_plot_config_overrides(config) -> None:
    """Layer ``PlotConfig`` fields on top of the active theme's rcParams.

    Wires the following ``PlotConfig`` fields into matplotlib:
        - ``palette``               → ``axes.prop_cycle``
        - ``show_grid``             → ``axes.grid``
        - ``legend_default_position``→ ``legend.loc``
        - ``legend_framealpha``     → ``legend.framealpha``
        - ``legend_font_scale``     → multiplies the theme's ``legend.fontsize``

    Note: ``show_titles`` is caller-enforced (it gates whether
    ``ax.set_title()`` is called) and is not applied here.
    """
    overrides: dict = {}
    if config.palette in PALETTES:
        overrides["axes.prop_cycle"] = plt.cycler(color=PALETTES[config.palette])
    overrides["axes.grid"] = bool(config.show_grid)
    overrides["legend.loc"] = config.legend_default_position
    overrides["legend.framealpha"] = config.legend_framealpha
    overrides["legend.fontsize"] = (
        plt.rcParams["legend.fontsize"] * config.legend_font_scale
    )
    family_name = _FONT_FAMILY_NAMES[config.font_family]
    overrides["font.sans-serif"] = [family_name, "DejaVu Sans", "sans-serif"]
    overrides["font.weight"] = "bold" if config.font_weight == "bold" else "normal"
    plt.rcParams.update(overrides)
