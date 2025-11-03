"""CNP vs time plotting - track Dirac point evolution over experiments."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
import polars as pl
import numpy as np
from datetime import datetime

from src.plotting.config import PlotConfig


def plot_cnp_vs_time(
    history: pl.DataFrame,
    chip_name: str,
    show_light: bool = True,
    config: Optional[PlotConfig] = None,
) -> Path:
    """
    Plot CNP voltage vs time to track Dirac point evolution.

    Parameters
    ----------
    history : pl.DataFrame
        Chip history with CNP and time columns (must include 'cnp_voltage' and datetime)
    chip_name : str
        Name of the chip (e.g., "Alisson81")
    show_light : bool
        If True, show different markers for light/dark measurements
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

    # Filter to only IVg measurements with CNP values
    cnp_data = history.filter(
        (pl.col("proc") == "IVg") &
        (pl.col("cnp_voltage").is_not_null()) &
        (pl.col("cnp_voltage").is_not_nan())
    )

    if cnp_data.height == 0:
        raise ValueError(f"No CNP data found for {chip_name}. Run derive-all-metrics first.")

    # Sort by time and convert datetime_local to proper datetime type
    cnp_data = cnp_data.sort("datetime_local")

    # Convert datetime_local from string to datetime if needed
    if cnp_data["datetime_local"].dtype == pl.Utf8:
        cnp_data = cnp_data.with_columns(
            pl.col("datetime_local").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S")
        )

    # Extract data
    times = cnp_data["datetime_local"].to_list()
    cnp_values = cnp_data["cnp_voltage"].to_numpy()
    seqs = cnp_data["seq"].to_list()

    # Check if we have light information
    has_light = "has_light" in cnp_data.columns

    # Create figure
    fig, ax = plt.subplots(figsize=config.figsize_derived)

    if has_light and show_light:
        # Split by light status
        light_mask = cnp_data["has_light"].to_numpy()

        # Plot dark measurements
        dark_indices = np.where(~light_mask)[0]
        if len(dark_indices) > 0:
            ax.plot(
                [times[i] for i in dark_indices],
                cnp_values[dark_indices],
                'o-',
                label='Dark',
            )

        # Plot light measurements
        light_indices = np.where(light_mask)[0]
        if len(light_indices) > 0:
            ax.plot(
                [times[i] for i in light_indices],
                cnp_values[light_indices],
                's-',
                label='Light',
            )
    else:
        # Plot all together
        ax.plot(times, cnp_values)

    # Formatting
    ax.set_xlabel('Date & Time', fontweight='bold')
    ax.set_ylabel('CNP Voltage (V)', fontweight='bold')
    ax.set_title(f'{chip_name} - Dirac Point Evolution', fontweight='bold')
    ax.grid(True, alpha=0.3)

    # Add horizontal line at V=0
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5, zorder=0)

    # Configure date axis formatting for clarity
    # Use AutoDateLocator to automatically choose optimal tick positions
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    # Rotate labels for readability
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')

    # Add legend if we have light/dark
    if has_light and show_light:
        ax.legend(loc='best', framealpha=0.9)

    # Add statistics text box
    mean_cnp = np.mean(cnp_values)
    std_cnp = np.std(cnp_values)
    min_cnp = np.min(cnp_values)
    max_cnp = np.max(cnp_values)

    stats_text = f'Mean: {mean_cnp:.3f} V\nStd: {std_cnp:.3f} V\nRange: [{min_cnp:.3f}, {max_cnp:.3f}] V'
    ax.text(
        0.02, 0.98, stats_text,
        transform=ax.transAxes,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    )

    # Add data point count
    ax.text(
        0.98, 0.02, f'N = {len(cnp_values)} measurements',
        transform=ax.transAxes,
        horizontalalignment='right',
        verticalalignment='bottom',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8)
    )

    plt.tight_layout()

    # Save figure
    filename = f"{chip_name}_cnp_vs_time.png"
    output_file = config.get_output_path(filename, procedure="CNP")
    plt.savefig(output_file, dpi=config.dpi, bbox_inches='tight')
    plt.close()

    return output_file
