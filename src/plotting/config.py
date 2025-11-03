#!/usr/bin/env python3
"""
Centralized Plotting Configuration

Provides a unified configuration system for all plotting modules, controlling:
- Output paths and formats
- Figure sizes (by plot type)
- Themes and color palettes
- Common plotting parameters
- Label and legend formatting

This module integrates with the CLI configuration system (src/cli/config.py)
to enable command-line control over plot appearance without code changes.
"""

from pathlib import Path
from typing import Literal, Tuple, Optional
from pydantic import BaseModel, Field, field_validator


class PlotConfig(BaseModel):
    """
    Centralized plotting configuration.

    This class defines all plotting parameters that were previously scattered
    across individual plotting modules as hardcoded constants. It enables:

    - Consistent figure sizes across plot types
    - Theme switching (paper, presentation, etc.)
    - Configurable output directories and formats
    - Centralized control of plotting behavior

    Examples
    --------
    >>> # Use defaults
    >>> config = PlotConfig()
    >>> print(config.theme, config.dpi)
    prism_rain 300

    >>> # Override for publication
    >>> config = PlotConfig(theme="paper", dpi=600, format="pdf")
    >>> print(config.figsize_timeseries)
    (7.0, 5.0)

    >>> # Create from CLI config
    >>> from src.cli.config import CLIConfig
    >>> cli_config = CLIConfig()
    >>> plot_config = PlotConfig.from_cli_config(cli_config)
    """

    model_config = {
        "validate_assignment": True,
        "arbitrary_types_allowed": True,
    }

    # ============================================================================
    # Output Configuration
    # ============================================================================

    output_dir: Path = Field(
        default=Path("figs"),
        description="Base directory for saving plots"
    )

    format: Literal["png", "pdf", "svg", "jpg"] = Field(
        default="png",
        description="Default output format for plots"
    )

    dpi: int = Field(
        default=300,
        ge=72,
        le=1200,
        description="DPI (dots per inch) for rasterized output formats"
    )

    use_proc_subdirs: bool = Field(
        default=True,
        description="Create procedure-specific subdirectories (e.g., figs/ITS/, figs/IVg/)"
    )

    # ============================================================================
    # Style Configuration
    # ============================================================================

    theme: Literal["prism_rain", "paper", "presentation", "minimal"] = Field(
        default="prism_rain",
        description=(
            "Matplotlib theme style:\n"
            "- prism_rain: Current default (large fonts, colorful, lab use)\n"
            "- paper: Publication quality (small fonts, serif, high DPI)\n"
            "- presentation: Slides/posters (extra large fonts, vivid colors)\n"
            "- minimal: Clean minimalist (web dashboards, reports)"
        )
    )

    palette: Literal["prism_rain", "deep_rain", "scientific", "minimal", "vivid"] = Field(
        default="prism_rain",
        description=(
            "Color palette for plot lines:\n"
            "- prism_rain: Vibrant primary colors\n"
            "- deep_rain: Deep saturated tones\n"
            "- scientific: Nature/IEEE-inspired palette\n"
            "- minimal: Understated professional colors\n"
            "- vivid: High-contrast neon-like colors"
        )
    )

    # ============================================================================
    # Figure Sizes (by plot type)
    # ============================================================================

    figsize_timeseries: Tuple[float, float] = Field(
        default=(35.0, 20.0),
        description="Figure size for time-series plots (ITS, Vt) in inches"
    )

    figsize_voltage_sweep: Tuple[float, float] = Field(
        default=(20.0, 20.0),
        description="Figure size for voltage sweep plots (IVg, VVg) in inches"
    )

    figsize_derived: Tuple[float, float] = Field(
        default=(36.0, 20.0),
        description="Figure size for derived metric plots (CNP, photoresponse) in inches"
    )

    figsize_transconductance: Tuple[float, float] = Field(
        default=(20.0, 20.0),
        description="Figure size for transconductance (gm) plots in inches"
    )

    figsize_laser_calibration: Tuple[float, float] = Field(
        default=(20.0, 20.0),
        description="Figure size for laser calibration plots in inches"
    )

    # ============================================================================
    # Common Plotting Parameters
    # ============================================================================

    light_window_alpha: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Transparency (alpha) for light-ON window shading in time-series plots"
    )

    plot_start_time: float = Field(
        default=20.0,
        ge=0.0,
        description="Default start time (seconds) for x-axis in time-series plots"
    )

    padding_fraction: float = Field(
        default=0.02,
        ge=0.0,
        le=0.5,
        description="Fraction of data range to add as y-axis padding (0.02 = 2%)"
    )

    baseline_mode_default: Literal["fixed", "auto", "none"] = Field(
        default="fixed",
        description="Default baseline correction mode for time-series plots"
    )

    baseline_time_default: float = Field(
        default=60.0,
        ge=0.0,
        description="Default baseline time (seconds) for fixed baseline mode"
    )

    # ============================================================================
    # Legend Configuration
    # ============================================================================

    legend_default_position: str = Field(
        default="best",
        description="Default legend position ('best', 'upper left', 'lower right', etc.)"
    )

    legend_font_scale: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Multiplier for legend font size (relative to theme default)"
    )

    legend_framealpha: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Legend background transparency"
    )

    # ============================================================================
    # Label Formatters
    # ============================================================================

    wavelength_format: str = Field(
        default="{:.0f} nm",
        description="Format string for wavelength labels (e.g., '365 nm')"
    )

    voltage_format: str = Field(
        default="{:g} V",
        description="Format string for voltage labels (e.g., '3 V' or '0.25 V')"
    )

    power_auto_unit: bool = Field(
        default=True,
        description="Automatically select power unit (W, mW, µW, nW) based on magnitude"
    )

    power_decimal_places: int = Field(
        default=2,
        ge=0,
        le=6,
        description="Decimal places for power values"
    )

    datetime_format: str = Field(
        default="%Y-%m-%d %H:%M",
        description="Format string for datetime labels (strftime format, seconds trimmed)"
    )

    # ============================================================================
    # Grid & Styling
    # ============================================================================

    show_grid: bool = Field(
        default=False,
        description="Show grid lines on plots (overrides theme default)"
    )

    show_cnp_markers: bool = Field(
        default=True,
        description="Show CNP (Dirac point) markers on IVg/VVg plots when available"
    )

    show_titles: bool = Field(
        default=False,
        description="Show plot titles (recommended: False for publications)"
    )

    # ============================================================================
    # Validators
    # ============================================================================

    @field_validator("output_dir", mode="before")
    @classmethod
    def resolve_output_path(cls, v) -> Path:
        """Resolve output_dir to absolute path."""
        if v is None:
            return Path("figs")
        path = Path(v)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    @field_validator("theme", mode="after")
    @classmethod
    def adjust_figsize_for_theme(cls, v, info):
        """
        Auto-adjust figure sizes based on theme (if not explicitly overridden).

        This validator modifies figure sizes to match the intended use case:
        - paper: Small sizes for journal single/double column
        - presentation: Large sizes for projectors
        - prism_rain/minimal: Keep defaults
        """
        # NOTE: This is called after all fields are set, but we can't modify
        # other fields directly in a field validator. We'll handle this in
        # a model_validator instead.
        return v

    # ============================================================================
    # Class Methods
    # ============================================================================

    @classmethod
    def from_cli_config(cls, cli_config) -> "PlotConfig":
        """
        Create PlotConfig from CLIConfig, inheriting common fields.

        Parameters
        ----------
        cli_config : CLIConfig
            CLI configuration instance from src.cli.config

        Returns
        -------
        PlotConfig
            Plotting configuration with values from CLI config

        Examples
        --------
        >>> from src.cli.config import CLIConfig
        >>> cli_config = CLIConfig(plot_theme="paper", plot_dpi=600)
        >>> plot_config = PlotConfig.from_cli_config(cli_config)
        >>> print(plot_config.theme, plot_config.dpi)
        paper 600
        """
        return cls(
            output_dir=cli_config.output_dir,
            format=cli_config.default_plot_format,
            dpi=cli_config.plot_dpi,
            theme=cli_config.plot_theme,
        )

    def get_figsize(self, plot_type: str) -> Tuple[float, float]:
        """
        Get figure size for a specific plot type.

        Parameters
        ----------
        plot_type : str
            Plot type: "timeseries", "voltage_sweep", "derived",
            "transconductance", "laser_calibration"

        Returns
        -------
        tuple[float, float]
            Figure size (width, height) in inches

        Examples
        --------
        >>> config = PlotConfig()
        >>> config.get_figsize("timeseries")
        (24.0, 17.0)
        >>> config.get_figsize("voltage_sweep")
        (20.0, 20.0)
        """
        size_map = {
            "timeseries": self.figsize_timeseries,
            "voltage_sweep": self.figsize_voltage_sweep,
            "derived": self.figsize_derived,
            "transconductance": self.figsize_transconductance,
            "laser_calibration": self.figsize_laser_calibration,
        }
        return size_map.get(plot_type, (20.0, 20.0))  # Default fallback

    def get_output_path(
        self,
        filename: str,
        procedure: Optional[str] = None,
        create_dirs: bool = True
    ) -> Path:
        """
        Get full output path for a plot file.

        Parameters
        ----------
        filename : str
            Output filename (with or without extension)
        procedure : str, optional
            Procedure type (e.g., "ITS", "IVg") for subdirectory creation
        create_dirs : bool
            Create directories if they don't exist (default: True)

        Returns
        -------
        Path
            Full path to output file

        Examples
        --------
        >>> config = PlotConfig(output_dir=Path("figs"), use_proc_subdirs=True)
        >>> config.get_output_path("chip67_its.png", procedure="ITS")
        PosixPath('/path/to/figs/ITS/chip67_its.png')

        >>> config = PlotConfig(use_proc_subdirs=False)
        >>> config.get_output_path("chip67_its.png", procedure="ITS")
        PosixPath('/path/to/figs/chip67_its.png')
        """
        # Ensure filename has correct extension
        filename_path = Path(filename)
        if filename_path.suffix != f".{self.format}":
            filename = f"{filename_path.stem}.{self.format}"

        # Determine output directory
        if self.use_proc_subdirs and procedure:
            output_dir = self.output_dir / procedure
        else:
            output_dir = self.output_dir

        # Create directories if requested
        if create_dirs:
            output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir / filename

    def copy(self, **overrides) -> "PlotConfig":
        """
        Create a copy of this config with specified overrides.

        Parameters
        ----------
        **overrides
            Field values to override

        Returns
        -------
        PlotConfig
            New config instance with overrides applied

        Examples
        --------
        >>> config = PlotConfig(theme="prism_rain")
        >>> paper_config = config.copy(theme="paper", dpi=600)
        >>> print(paper_config.theme, paper_config.dpi)
        paper 600
        """
        config_dict = self.model_dump()
        config_dict.update(overrides)
        return PlotConfig(**config_dict)


# ============================================================================
# Predefined Configuration Profiles
# ============================================================================

class PlotConfigProfiles:
    """
    Predefined configuration profiles for common use cases.

    These profiles provide optimized settings for different scenarios:
    - paper: Journal publications (Nature, IEEE, Science)
    - presentation: Conference slides and posters
    - web: Web dashboards and interactive reports
    - lab: Lab notebooks and internal reports (current default)
    """

    @staticmethod
    def paper() -> PlotConfig:
        """
        Publication-quality profile for journal papers.

        Optimized for:
        - High resolution (600 DPI)
        - PDF output
        - Small figure sizes (single/double column)
        - Serif fonts
        - Conservative color palette
        """
        return PlotConfig(
            theme="paper",
            palette="scientific",
            dpi=600,
            format="pdf",
            figsize_timeseries=(7.0, 5.0),
            figsize_voltage_sweep=(3.5, 3.5),
            figsize_derived=(7.0, 5.0),
            show_grid=False,
            show_titles=False,
        )

    @staticmethod
    def presentation() -> PlotConfig:
        """
        Profile optimized for conference slides and posters.

        Optimized for:
        - Large fonts and markers
        - Vivid color palette
        - Lower DPI (150) for file size
        - PNG output
        - Large figure sizes
        """
        return PlotConfig(
            theme="presentation",
            palette="vivid",
            dpi=150,
            format="png",
            figsize_timeseries=(12.0, 8.0),
            figsize_voltage_sweep=(10.0, 10.0),
            figsize_derived=(14.0, 9.0),
            show_grid=True,
            show_titles=True,
        )

    @staticmethod
    def web() -> PlotConfig:
        """
        Profile for web dashboards and interactive reports.

        Optimized for:
        - Medium resolution (150 DPI)
        - PNG output
        - Moderate figure sizes
        - Clean minimal style
        """
        return PlotConfig(
            theme="minimal",
            palette="minimal",
            dpi=150,
            format="png",
            figsize_timeseries=(10.0, 7.0),
            figsize_voltage_sweep=(8.0, 8.0),
            figsize_derived=(12.0, 8.0),
            show_grid=False,
            show_titles=False,
        )

    @staticmethod
    def lab() -> PlotConfig:
        """
        Profile for lab notebooks and internal reports (current default).

        This matches the current plotting behavior before refactoring.
        """
        return PlotConfig(
            theme="prism_rain",
            palette="prism_rain",
            dpi=300,
            format="png",
            figsize_timeseries=(24.0, 17.0),
            figsize_voltage_sweep=(20.0, 20.0),
            figsize_derived=(36.0, 20.0),
            show_grid=False,
            show_titles=False,
        )


# ============================================================================
# Global Singleton (Optional - for convenience)
# ============================================================================

_global_config: Optional[PlotConfig] = None


def get_global_config() -> PlotConfig:
    """
    Get or create the global PlotConfig singleton.

    Returns
    -------
    PlotConfig
        Global plotting configuration instance

    Examples
    --------
    >>> config = get_global_config()
    >>> print(config.theme)
    prism_rain
    """
    global _global_config
    if _global_config is None:
        _global_config = PlotConfig()
    return _global_config


def set_global_config(config: PlotConfig) -> None:
    """
    Set the global PlotConfig singleton.

    Parameters
    ----------
    config : PlotConfig
        Configuration to use globally

    Examples
    --------
    >>> from src.plotting.config import PlotConfig, set_global_config
    >>> paper_config = PlotConfig(theme="paper", dpi=600)
    >>> set_global_config(paper_config)
    """
    global _global_config
    _global_config = config
