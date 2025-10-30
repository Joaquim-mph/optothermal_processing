"""
Laser calibration plotting functions.

Generates calibration curves showing the relationship between laser PSU voltage
and measured optical power for different wavelengths and optical fibers.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import polars as pl
from typing import Optional

from src.core.utils import read_measurement_parquet

# Configuration
FIG_DIR = Path("figs")


def plot_laser_calibration(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    group_by_wavelength: bool = True,
    show_markers: bool = True,
    power_unit: str = "uW",
) -> Path:
    """
    Generate laser calibration plot (Power vs Laser Voltage).

    Creates a calibration curve showing the relationship between laser drive
    voltage and measured optical power. Multiple calibrations (different
    wavelengths, fibers) can be overlaid for comparison.

    Parameters
    ----------
    df : pl.DataFrame
        Chip history DataFrame filtered to LaserCalibration experiments
    base_dir : Path
        Base directory for loading measurement Parquet files (usually not needed
        since we use parquet_path from history)
    tag : str
        Tag for output filename (typically chip identifier)
    group_by_wavelength : bool, optional
        If True, use different colors for different wavelengths (default: True)
    show_markers : bool, optional
        If True, show data point markers (default: True)
    power_unit : str, optional
        Power unit for y-axis: "uW", "mW", or "W" (default: "uW")

    Returns
    -------
    Path
        Path to saved plot file

    Examples
    --------
    >>> history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")
    >>> cal_data = history.filter(pl.col("proc") == "LaserCalibration")
    >>> output = plot_laser_calibration(cal_data, Path("."), "Alisson67")
    >>> print(f"Saved: {output}")

    Notes
    -----
    - Power is converted from W to µW by default for better readability
    - Each calibration (seq number) is plotted as a separate curve
    - Legend includes wavelength, fiber, and seq number for identification
    - Grid is enabled for easy voltage/power reading
    """
    # Load config and apply plot style from config
    from src.cli.main import get_config
    from src.plotting.styles import set_plot_style, THEMES

    config = get_config()
    theme_name = config.plot_theme
    set_plot_style(theme_name)

    # Filter and sort by seq number (chronological order)
    data = df.filter(pl.col("proc") == "LaserCalibration").sort("seq")
    if data.height == 0:
        print("[warn] No LaserCalibration experiments to plot")
        return None

    # Create figure (figsize from theme's rcParams)
    fig, ax = plt.subplots()

    # Determine power conversion factor
    power_factors = {
        "W": 1.0,
        "mW": 1e3,
        "uW": 1e6,
        "µW": 1e6,
    }
    power_factor = power_factors.get(power_unit, 1e6)  # Default to µW

    # Track wavelengths for color grouping
    if group_by_wavelength:
        wavelengths = data["wavelength_nm"].unique().sort() if "wavelength_nm" in data.columns else []
        # Get color palette from theme
        if len(wavelengths) > 0:
            theme = THEMES[theme_name]
            color_cycle = theme["rc"]["axes.prop_cycle"]
            colors = [c['color'] for c in color_cycle]
            wl_colors = {wl: colors[i % len(colors)] for i, wl in enumerate(wavelengths)}
        else:
            wl_colors = {}
    else:
        wl_colors = {}

    curves_plotted = 0

    # Iterate through calibration experiments
    for row in data.iter_rows(named=True):
        # Load measurement data from staged Parquet
        parquet_path = Path(row["parquet_path"])
        if not parquet_path.exists():
            print(f"[warn] Missing file: {parquet_path}")
            continue

        measurement = read_measurement_parquet(parquet_path)

        # Normalize column names (handle case variations and spaces)
        col_map = {}
        for col in measurement.columns:
            col_lower = col.lower().strip()
            if col_lower in ["vl (v)", "laser voltage (v)", "vl"]:
                col_map[col] = "VL"
            elif col_lower in ["power (w)", "power", "p (w)"]:
                col_map[col] = "Power"

        if col_map:
            measurement = measurement.rename(col_map)

        # Verify required columns exist
        required_cols = {"VL", "Power"}
        if not required_cols <= set(measurement.columns):
            missing = required_cols - set(measurement.columns)
            print(f"[warn] Missing columns in {parquet_path.name}: {missing}")
            print(f"       Available columns: {measurement.columns}")
            continue

        # Extract data for plotting
        vl = measurement["VL"].to_numpy()
        power = measurement["Power"].to_numpy()

        # Convert power units
        power_display = power * power_factor

        # Build label from metadata
        seq = int(row["seq"])
        wavelength = row.get("wavelength_nm")
        fiber = row.get("optical_fiber", "unknown fiber")

        # Create descriptive label
        label_parts = [f"seq {seq}"]
        if wavelength is not None and not np.isnan(wavelength):
            label_parts.append(f"{wavelength:.0f}nm")
        if fiber and fiber != "unknown fiber":
            label_parts.append(f"{fiber}")
        label = " - ".join(label_parts)

        # Determine color (group by wavelength if enabled)
        if group_by_wavelength and wavelength is not None and wavelength in wl_colors:
            color = wl_colors[wavelength]
        else:
            color = None  # Let matplotlib auto-assign

        # Plot (using theme's line/marker settings)
        if show_markers:
            ax.plot(vl, power_display,
                   marker='o',
                   linestyle='-',
                   label=label,
                   color=color)
        else:
            ax.plot(vl, power_display,
                   linestyle='-',
                   label=label,
                   color=color)

        curves_plotted += 1

    if curves_plotted == 0:
        print("[error] No valid calibration data found to plot")
        plt.close(fig)
        return None

    # Labels and title (using theme's font settings)
    ax.set_xlabel("Laser Voltage (V)")
    ax.set_ylabel(f"Optical Power ({power_unit})")
    ax.set_title(f"Laser Calibration — {tag}")

    # Legend (using theme's legend settings)
    ax.legend()

    # Grid (if enabled in theme)
    if plt.rcParams.get('axes.grid', False):
        ax.grid(True)

    # Start y-axis at 0 (power can't be negative)
    ax.set_ylim(bottom=0)

    # Tight layout
    plt.tight_layout()

    # Save figure (using config DPI)
    output_dir = FIG_DIR / tag
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"laser_calibration_{tag}.{config.default_plot_format}"

    fig.savefig(output_file, dpi=config.plot_dpi, bbox_inches='tight')
    plt.close(fig)

    print(f"[info] Saved {output_file}")
    return output_file


def plot_laser_calibration_comparison(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    group_by: str = "wavelength",
) -> Path:
    """
    Generate comparison plot with subplots for different wavelengths or fibers.

    Creates a multi-panel figure with one subplot per wavelength (or fiber),
    showing how calibration curves differ across conditions.

    Parameters
    ----------
    df : pl.DataFrame
        Chip history DataFrame filtered to LaserCalibration experiments
    base_dir : Path
        Base directory for loading measurement Parquet files
    tag : str
        Tag for output filename
    group_by : str, optional
        Grouping variable: "wavelength" or "fiber" (default: "wavelength")

    Returns
    -------
    Path
        Path to saved plot file

    Examples
    --------
    >>> history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")
    >>> cal_data = history.filter(pl.col("proc") == "LaserCalibration")
    >>> output = plot_laser_calibration_comparison(cal_data, Path("."), "Alisson67")
    """
    # Load config and apply plot style from config
    from src.cli.main import get_config
    from src.plotting.styles import set_plot_style

    config = get_config()
    theme_name = config.plot_theme
    set_plot_style(theme_name)

    data = df.filter(pl.col("proc") == "LaserCalibration").sort("seq")
    if data.height == 0:
        print("[warn] No LaserCalibration experiments to plot")
        return None

    # Determine grouping
    if group_by == "wavelength":
        group_col = "wavelength_nm"
        group_label = "Wavelength"
        group_unit = "nm"
    elif group_by == "fiber":
        group_col = "optical_fiber"
        group_label = "Fiber"
        group_unit = ""
    else:
        print(f"[error] Unknown group_by value: {group_by}")
        return None

    if group_col not in data.columns:
        print(f"[error] Column '{group_col}' not found in history")
        return None

    # Get unique groups
    groups = data[group_col].unique().sort()
    n_groups = len(groups)

    if n_groups == 0:
        print("[warn] No groups found for comparison")
        return None

    # Create subplots (let theme control figure size)
    n_cols = min(2, n_groups)
    n_rows = (n_groups + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, squeeze=False)
    axes = axes.flatten()

    # Plot each group
    for idx, group_val in enumerate(groups):
        ax = axes[idx]
        group_data = data.filter(pl.col(group_col) == group_val)

        for row in group_data.iter_rows(named=True):
            parquet_path = Path(row["parquet_path"])
            if not parquet_path.exists():
                continue

            measurement = read_measurement_parquet(parquet_path)

            # Column normalization
            col_map = {}
            for col in measurement.columns:
                col_lower = col.lower().strip()
                if "vl" in col_lower or "voltage" in col_lower:
                    col_map[col] = "VL"
                elif "power" in col_lower:
                    col_map[col] = "Power"
            if col_map:
                measurement = measurement.rename(col_map)

            if not {"VL", "Power"} <= set(measurement.columns):
                continue

            vl = measurement["VL"].to_numpy()
            power = measurement["Power"].to_numpy() * 1e6  # µW

            seq = int(row["seq"])
            # Use theme's line/marker settings
            ax.plot(vl, power, marker='o', linestyle='-', label=f"seq {seq}")

        # Subplot styling (using theme settings)
        unit_str = f" {group_unit}" if group_unit else ""
        ax.set_title(f"{group_label}: {group_val}{unit_str}")
        ax.set_xlabel("Laser Voltage (V)")
        ax.set_ylabel("Optical Power (µW)")
        ax.legend()
        if plt.rcParams.get('axes.grid', False):
            ax.grid(True)
        ax.set_ylim(bottom=0)

    # Hide unused subplots
    for idx in range(n_groups, len(axes)):
        axes[idx].axis('off')

    # Overall title
    fig.suptitle(f"Laser Calibration Comparison — {tag}")

    plt.tight_layout()

    # Save figure (using config settings)
    output_dir = FIG_DIR / tag
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"laser_calibration_comparison_{tag}.{config.default_plot_format}"

    fig.savefig(output_file, dpi=config.plot_dpi, bbox_inches='tight')
    plt.close(fig)

    print(f"[info] Saved {output_file}")
    return output_file
