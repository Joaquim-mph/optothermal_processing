"""Photoresponse plotting - analyze device response to illumination."""

from __future__ import annotations
from pathlib import Path
from typing import Literal, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
import polars as pl
import numpy as np

from src.plotting.config import PlotConfig


def plot_photoresponse(
    history: pl.DataFrame,
    chip_name: str,
    x_variable: Literal["power", "wavelength", "gate_voltage", "time"],
    y_metric: Literal["delta_current", "delta_voltage"] = "delta_current",
    procedures: list[str] = None,
    filter_wavelength: float = None,
    filter_vg: float = None,
    filter_power_range: tuple[float, float] = None,
    config: Optional[PlotConfig] = None,
) -> Path:
    """
    Plot photoresponse as a function of power, wavelength, gate voltage, or time.

    Parameters
    ----------
    history : pl.DataFrame
        Chip history with photoresponse metrics and experimental parameters
    chip_name : str
        Name of the chip (e.g., "Alisson81")
    x_variable : {"power", "wavelength", "gate_voltage", "time"}
        Independent variable for x-axis
    y_metric : {"delta_current", "delta_voltage"}, default="delta_current"
        Which photoresponse metric to plot (current or voltage change)
    procedures : list[str], optional
        List of procedures to include (e.g., ["It", "Vt", "ITt"]).
        If None, auto-selects based on y_metric: It/ITt for delta_current, Vt for delta_voltage.
    filter_wavelength : float, optional
        Filter to specific wavelength (nm)
    filter_vg : float, optional
        Filter to specific gate voltage (V)
    filter_power_range : tuple[float, float], optional
        Filter to power range (min, max) in watts
    config : PlotConfig, optional
        Plot configuration (theme, DPI, output paths, etc.)

    Returns
    -------
    Path
        Path to saved figure
    """
    # Initialize config with defaults
    config = config or PlotConfig()

    # Apply plot style from config
    from src.plotting.styles import set_plot_style
    set_plot_style(config.theme)

    # Select metric column name (metrics use delta_current/delta_voltage)
    metric_col = y_metric

    # Auto-select procedures if not specified
    if procedures is None:
        if y_metric == "delta_current":
            procedures = ["It", "ITt"]
        else:
            procedures = ["Vt"]

    # Filter to selected measurements with photoresponse data and illumination
    # delta_current comes from It/ITt, delta_voltage comes from Vt
    photo_data = history.filter(
        pl.col("proc").is_in(procedures) &
        (pl.col("has_light") == True) &
        (pl.col(metric_col).is_not_null()) &
        (pl.col(metric_col).is_not_nan())
    )

    if photo_data.height == 0:
        raise ValueError(
            f"No photoresponse data found for {chip_name}. "
            "Run derive-all-metrics first."
        )

    # Apply filters
    if filter_wavelength is not None:
        photo_data = photo_data.filter(pl.col("wavelength_nm") == filter_wavelength)

    if filter_vg is not None:
        photo_data = photo_data.filter(
            (pl.col("vg_fixed_v").is_not_null()) &
            (pl.col("vg_fixed_v") - filter_vg).abs() < 0.01  # Tolerance for floating point
        )

    if filter_power_range is not None:
        min_power, max_power = filter_power_range
        photo_data = photo_data.filter(
            (pl.col("irradiated_power_w") >= min_power) &
            (pl.col("irradiated_power_w") <= max_power)
        )

    if photo_data.height == 0:
        raise ValueError(f"No data matching filters for {chip_name}")

    # Determine x-axis variable and label
    if x_variable == "power":
        x_col = "irradiated_power_w"
        x_label = "Irradiated Power (W)"
        x_scale = "log"  # Power often spans orders of magnitude
    elif x_variable == "wavelength":
        x_col = "wavelength_nm"
        x_label = "Wavelength (nm)"
        x_scale = "linear"
    elif x_variable == "gate_voltage":
        x_col = "vg_fixed_v"
        x_label = "Gate Voltage (V)"
        x_scale = "linear"
    elif x_variable == "time":
        x_col = "datetime_local"
        x_label = "Date & Time"
        x_scale = "linear"
    else:
        raise ValueError(f"Unknown x_variable: {x_variable}")

    # Filter out nulls in x variable
    photo_data = photo_data.filter(pl.col(x_col).is_not_null())

    if photo_data.height == 0:
        raise ValueError(f"No data with valid {x_col} for {chip_name}")

    # Sort by x variable
    photo_data = photo_data.sort(x_col)

    # Handle datetime conversion for time plots
    if x_variable == "time":
        # Convert datetime_local from string to datetime if needed
        if photo_data[x_col].dtype == pl.Utf8:
            photo_data = photo_data.with_columns(
                pl.col(x_col).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S")
            )
        x_values = photo_data[x_col].to_list()  # Keep as datetime objects for matplotlib
    else:
        x_values = photo_data[x_col].to_numpy()

    y_values = photo_data[metric_col].to_numpy()

    # Determine y-axis label
    if y_metric == "delta_current":
        y_label = "Δ Current (A)"
    else:
        y_label = "Δ Voltage (V)"

    # Create figure
    fig, ax = plt.subplots(figsize=config.figsize_derived)

    # Group by wavelength if plotting vs power/gate (for color coding)
    if x_variable in ["power", "gate_voltage"] and "wavelength_nm" in photo_data.columns:
        wavelengths = photo_data["wavelength_nm"].unique().sort().to_list()

        for wl in wavelengths:
            if wl is None:
                continue
            wl_data = photo_data.filter(pl.col("wavelength_nm") == wl)
            x_wl = wl_data[x_col].to_numpy()
            y_wl = wl_data[metric_col].to_numpy()

            ax.plot(x_wl, y_wl, 'o-', markersize=8, linewidth=2,
                   label=f'{wl:.0f} nm', alpha=0.8)
    else:
        # Single series
        ax.plot(x_values, y_values, 'o-', markersize=8, linewidth=2, alpha=0.8)

    # Set x-axis scale
    if x_scale == "log":
        ax.set_xscale("log")

    # Configure date axis formatting for time plots
    if x_variable == "time":
        locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')

    # Formatting
    ax.set_xlabel(x_label, fontweight='bold')
    ax.set_ylabel(y_label, fontweight='bold')

    # Build title with filter information
    title_parts = [f'{chip_name} - Photoresponse vs {x_variable.replace("_", " ").title()}']
    if len(procedures) > 1:
        title_parts.append(f'({", ".join(procedures)})')
    if filter_wavelength is not None:
        title_parts.append(f'λ={filter_wavelength:.0f}nm')
    if filter_vg is not None:
        title_parts.append(f'Vg={filter_vg:.2f}V')
    ax.set_title(' | '.join(title_parts), fontweight='bold')

    ax.grid(True, alpha=0.3)

    # Add legend if multiple wavelengths
    if x_variable in ["power", "gate_voltage"] and len(wavelengths) > 1:
        ax.legend(loc='best', framealpha=0.9, title='Wavelength')

    # Add statistics text box
    mean_y = np.mean(y_values)
    std_y = np.std(y_values)
    min_y = np.min(y_values)
    max_y = np.max(y_values)

    # Format numbers based on magnitude
    if abs(mean_y) < 1e-6:
        unit_suffix = " nA" if y_metric == "delta_current" else " nV"
        scale = 1e9
    elif abs(mean_y) < 1e-3:
        unit_suffix = " µA" if y_metric == "delta_current" else " µV"
        scale = 1e6
    elif abs(mean_y) < 1:
        unit_suffix = " mA" if y_metric == "delta_current" else " mV"
        scale = 1e3
    else:
        unit_suffix = " A" if y_metric == "delta_current" else " V"
        scale = 1

    stats_text = (
        f'Mean: {mean_y*scale:.3f}{unit_suffix}\n'
        f'Std: {std_y*scale:.3f}{unit_suffix}\n'
        f'Range: [{min_y*scale:.3f}, {max_y*scale:.3f}]{unit_suffix}'
    )
    ax.text(
        0.02, 0.98, stats_text,
        transform=ax.transAxes,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    )

    # Add data point count
    ax.text(
        0.98, 0.02, f'N = {len(y_values)} measurements',
        transform=ax.transAxes,
        horizontalalignment='right',
        verticalalignment='bottom',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8)
    )

    plt.tight_layout()

    # Extract chip number from chip_name (e.g., "Alisson81" -> 81)
    import re
    match = re.search(r'(\d+)$', chip_name)
    chip_number = int(match.group(1)) if match else None

    # Build output filename
    filename_parts = [chip_name.lower(), "photoresponse", y_metric, "vs", x_variable]
    if filter_wavelength is not None:
        filename_parts.append(f"wl{filter_wavelength:.0f}nm")
    if filter_vg is not None:
        filename_parts.append(f"vg{filter_vg:.2f}V".replace(".", "p"))

    filename = "_".join(filename_parts)
    output_file = config.get_output_path(
        filename,
        chip_number=chip_number,
        procedure="Photoresponse",
        # No metadata - Photoresponse is a derived metric
        create_dirs=True
    )
    plt.savefig(output_file, dpi=config.dpi, bbox_inches='tight')
    plt.close()

    return output_file
