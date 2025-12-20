"""ITS photoresponse plotting - analyze delta current from ITS measurements."""

from __future__ import annotations
from pathlib import Path
from typing import Literal, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import polars as pl
import numpy as np

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig


def _extract_delta_current_from_its(measurement: pl.DataFrame, metadata: dict) -> float | None:
    """
    Extract delta current from an ITS measurement on-the-fly.

    Simple algorithm:
    1. Find baseline current (first 20% of measurement before light turns on)
    2. Find peak current (during light-on period)
    3. Return difference

    Parameters
    ----------
    measurement : pl.DataFrame
        ITS measurement data with columns 't' and 'I'
    metadata : dict
        Metadata row containing experimental parameters

    Returns
    -------
    float | None
        Delta current in Amps, or None if extraction fails
    """
    # Ensure standard column names
    from src.plotting.plot_utils import ensure_standard_columns
    measurement = ensure_standard_columns(measurement)

    if not {"t", "I"} <= set(measurement.columns):
        return None

    t = measurement["t"].to_numpy()
    i = measurement["I"].to_numpy()

    if len(t) < 10:  # Need enough points
        return None

    # Strategy: Use VL column if available to detect light window
    if "VL" in measurement.columns:
        vl = measurement["VL"].to_numpy()
        light_on = vl > 0.1  # Light is on when VL > 0.1V

        if not np.any(light_on):
            # No light detected - can't calculate photoresponse
            return None

        # Baseline: mean current when light is off
        baseline_current = np.mean(i[~light_on]) if np.any(~light_on) else i[0]

        # Peak: maximum current when light is on
        peak_current = np.max(i[light_on])

    else:
        # Fallback: assume first 20% is baseline, middle section is light-on
        n_points = len(t)
        baseline_end = int(0.2 * n_points)
        light_start = int(0.3 * n_points)
        light_end = int(0.7 * n_points)

        baseline_current = np.mean(i[:baseline_end])
        peak_current = np.max(i[light_start:light_end])

    delta_current = peak_current - baseline_current

    return delta_current


def plot_its_photoresponse(
    history: pl.DataFrame,
    chip_name: str,
    x_variable: Literal["power", "wavelength", "time", "gate_voltage"],
    filter_wavelength: float | None = None,
    filter_vg: float | None = None,
    filter_power_range: tuple[float, float] | None = None,
    plot_tag: str | None = None,
    axtype: str | None = None,
    config: Optional[PlotConfig] = None,
) -> Path:
    """
    Plot ITS photoresponse (delta current) vs power, wavelength, time, or gate voltage.

    Extracts photoresponse from ITS measurements and plots against the specified
    independent variable. Uses enriched history if available, otherwise extracts
    delta_current on-the-fly from ITS measurements.

    Parameters
    ----------
    history : pl.DataFrame
        Chip history filtered to ITS experiments (from --seq selection)
    chip_name : str
        Name of the chip (e.g., "Alisson67")
    x_variable : {"power", "wavelength", "time", "gate_voltage"}
        Independent variable for x-axis
    filter_wavelength : float, optional
        Filter to specific wavelength (nm)
    filter_vg : float, optional
        Filter to specific gate voltage (V)
    filter_power_range : tuple[float, float], optional
        Filter to power range (min, max) in watts
    plot_tag : str, optional
        Unique tag for filename (e.g., "seq_4_5_6_7"). If None, no tag added.
    axtype : str, optional
        Axis scale type: "linear" (default), "loglog", "semilogx", or "semilogy"
    config : PlotConfig, optional
        Plot configuration (theme, DPI, output paths, etc.)

    Returns
    -------
    Path
        Path to saved figure

    Examples
    --------
    >>> # Plot delta current vs power for seq 4-7
    >>> history = load_history_for_plotting([4,5,6,7], 67, "Alisson", history_dir)
    >>> its_data = history.filter(pl.col("proc") == "ITS")
    >>> output = plot_its_photoresponse(its_data, "Alisson67", "power")

    Notes
    -----
    - Automatically detects if enriched history is available (has delta_current column)
    - Falls back to on-the-fly extraction if delta_current not present
    - Only plots light experiments (has_light == True)
    - Supports same filtering as plot_photoresponse
    """
    # Initialize config with defaults
    config = config or PlotConfig()

    # Apply plot style from config
    from src.plotting.styles import set_plot_style
    set_plot_style(config.theme)

    # Filter to only It measurements with light
    # Note: Procedure name is "It" in manifest (not "ITS")
    its_data = history.filter(
        (pl.col("proc") == "It") &
        (pl.col("has_light") == True)
    )

    if its_data.height == 0:
        raise ValueError(
            f"No It light measurements found in history. "
            "Make sure you selected It experiments with illumination."
        )

    # Check if enriched history with delta_current exists
    has_enriched = "delta_current" in its_data.columns

    if has_enriched:
        # Use pre-computed delta_current from enriched history
        print("[info] Using delta_current from enriched history (fast!)")

        # Cast delta_current to float if it's stored as string
        if its_data["delta_current"].dtype == pl.Utf8:
            its_data = its_data.with_columns(
                pl.col("delta_current").cast(pl.Float64)
            )

        # Filter out null/nan delta_current values
        its_data = its_data.filter(
            (pl.col("delta_current").is_not_null()) &
            (pl.col("delta_current").is_not_nan())
        )

        if its_data.height == 0:
            raise ValueError(
                f"No valid delta_current values found in enriched history. "
                "Run 'derive-all-metrics' to extract photoresponse metrics."
            )
    else:
        # Extract delta_current on-the-fly from ITS measurements
        print("[info] Extracting delta_current on-the-fly from ITS measurements...")

        delta_currents = []
        valid_indices = []

        for idx, row in enumerate(its_data.iter_rows(named=True)):
            # Load measurement
            parquet_path = Path(row.get("parquet_path") or row.get("source_file"))
            if not parquet_path.exists():
                print(f"[warn] Missing file: {parquet_path}")
                continue

            measurement = read_measurement_parquet(parquet_path)

            # Extract delta_current
            delta_i = _extract_delta_current_from_its(measurement, row)

            if delta_i is not None:
                delta_currents.append(delta_i)
                valid_indices.append(idx)

        if len(delta_currents) == 0:
            raise ValueError(
                f"Could not extract delta_current from any ITS measurements. "
                "Make sure measurements have 't' and 'I' columns."
            )

        # Add delta_current column to history
        # Create a new column with nulls, then fill valid indices
        delta_current_col = [None] * its_data.height
        for idx, delta_i in zip(valid_indices, delta_currents):
            delta_current_col[idx] = delta_i

        its_data = its_data.with_columns(
            pl.Series("delta_current", delta_current_col)
        )

        # Filter out nulls
        its_data = its_data.filter(pl.col("delta_current").is_not_null())

        print(f"[info] Extracted delta_current from {its_data.height} measurements")

    # Apply filters
    if filter_wavelength is not None:
        its_data = its_data.filter(pl.col("wavelength_nm") == filter_wavelength)

    if filter_vg is not None:
        its_data = its_data.filter(
            (pl.col("vg_fixed_v").is_not_null()) &
            ((pl.col("vg_fixed_v") - filter_vg).abs() < 0.01)
        )

    if filter_power_range is not None:
        min_power, max_power = filter_power_range
        its_data = its_data.filter(
            (pl.col("irradiated_power_w") >= min_power) &
            (pl.col("irradiated_power_w") <= max_power)
        )

    if its_data.height == 0:
        raise ValueError(f"No data matching filters for {chip_name}")

    # Determine x-axis variable and label
    if x_variable == "power":
        # Check if irradiated_power_w is available (from laser calibration matching)
        if "irradiated_power_w" in its_data.columns:
            x_col = "irradiated_power_w"
            x_label = "Irradiated Power (μW)"
            x_unit_conversion = 1e6  # W to μW
        elif "laser_voltage_v" in its_data.columns:
            # Fallback: use laser voltage as proxy for power
            print("[warn] Column 'irradiated_power_w' not found. Using 'laser_voltage_v' as fallback.")
            print("[info] Run 'derive-all-metrics --calibrations' to get calibrated power values.")
            x_col = "laser_voltage_v"
            x_label = "Laser Voltage (V)"
            x_unit_conversion = 1.0  # No conversion
        else:
            raise ValueError(
                f"Cannot plot vs power: neither 'irradiated_power_w' nor 'laser_voltage_v' found in history. "
                f"Run 'derive-all-metrics --calibrations' to extract irradiated power from laser calibrations."
            )
    elif x_variable == "wavelength":
        x_col = "wavelength_nm"
        x_label = "Wavelength (nm)"
        x_unit_conversion = 1.0  # No conversion
    elif x_variable == "gate_voltage":
        x_col = "vg_fixed_v"
        x_label = "Gate Voltage (V)"
        x_unit_conversion = 1.0  # No conversion
    elif x_variable == "time":
        x_col = "datetime_local"
        x_label = "Date & Time"
        x_unit_conversion = 1.0  # No conversion (datetime handled separately)
    else:
        raise ValueError(f"Unknown x_variable: {x_variable}")

    # Check if x_col exists before filtering
    if x_col not in its_data.columns:
        available_cols = ", ".join(its_data.columns)
        raise ValueError(
            f"Cannot plot: column '{x_col}' not found in history. "
            f"Available columns: {available_cols}"
        )

    # Cast numeric columns to float if stored as string
    if x_variable in ["power", "wavelength", "gate_voltage"]:
        if its_data[x_col].dtype == pl.Utf8:
            its_data = its_data.with_columns(
                pl.col(x_col).cast(pl.Float64)
            )

    # Filter out nulls in x variable
    its_data = its_data.filter(pl.col(x_col).is_not_null())

    if its_data.height == 0:
        raise ValueError(f"No data with valid {x_col} for {chip_name}")

    # Sort by x variable
    its_data = its_data.sort(x_col)

    # Handle datetime conversion for time plots
    if x_variable == "time":
        if its_data[x_col].dtype == pl.Utf8:
            its_data = its_data.with_columns(
                pl.col(x_col).str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S")
            )
        x_values = its_data[x_col].to_list()
    else:
        x_values = its_data[x_col].to_numpy()
        # Apply unit conversion (e.g., W to μW)
        if x_unit_conversion != 1.0:
            x_values = x_values * x_unit_conversion

    y_values = its_data["delta_current"].to_numpy()

    # Create figure
    fig, ax = plt.subplots(figsize=config.figsize_derived)

    # Group by wavelength if plotting vs power/gate (for color coding)
    if x_variable in ["power", "gate_voltage"] and "wavelength_nm" in its_data.columns:
        wavelengths = its_data["wavelength_nm"].unique().sort().to_list()

        for wl in wavelengths:
            if wl is None:
                continue
            wl_data = its_data.filter(pl.col("wavelength_nm") == wl)

            if x_variable == "time":
                x_wl = wl_data[x_col].to_list()
            else:
                x_wl = wl_data[x_col].to_numpy()
                # Apply unit conversion (e.g., W to μW)
                if x_unit_conversion != 1.0:
                    x_wl = x_wl * x_unit_conversion

            y_wl = wl_data["delta_current"].to_numpy()

            ax.plot(x_wl, np.abs(y_wl) * 1e6, 'o-',
                   label=f'{wl:.0f} nm')
    else:
        # Single series
        ax.plot(x_values, np.abs(y_values) * 1e6, 'o-')

    # Set axis scales based on axtype parameter
    if axtype is None:
        axtype = "linear"  # Default to linear

    axtype = axtype.lower()

    if axtype == "loglog":
        ax.set_xscale("log")
        ax.set_yscale("log")
    elif axtype == "semilogx":
        ax.set_xscale("log")
        ax.set_yscale("linear")
    elif axtype == "semilogy":
        ax.set_xscale("linear")
        ax.set_yscale("log")
    elif axtype == "linear":
        ax.set_xscale("linear")
        ax.set_yscale("linear")
    else:
        raise ValueError(f"Invalid axtype: {axtype}. Must be 'linear', 'loglog', 'semilogx', or 'semilogy'")

    # Configure date axis formatting for time plots
    if x_variable == "time":
        locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')

    # Labels and title
    ax.set_xlabel(x_label, fontweight='bold')
    ax.set_ylabel("Δ Current (µA)", fontweight='bold')

    # Configure scientific notation formatting (like plot_its does)
    # Note: ticklabel_format only works with linear scales, not log scales
    if x_variable != "time":
        # Only apply for linear X-axis (not log)
        if axtype in ["linear", "semilogy", None]:
            ax.ticklabel_format(style='scientific', axis='x', scilimits=(0, 0), useMathText=True)

    # Only apply for linear Y-axis (not log)
    if axtype in ["linear", "semilogx", None]:
        ax.ticklabel_format(style='scientific', axis='y', scilimits=(0, 0), useMathText=True)

    # Build title with filter information
    title_parts = [f'{chip_name} - ITS Photoresponse vs {x_variable.replace("_", " ").title()}']
    if filter_wavelength is not None:
        title_parts.append(f'λ={filter_wavelength:.0f}nm')
    if filter_vg is not None:
        title_parts.append(f'Vg={filter_vg:.2f}V')
    ax.set_title(' | '.join(title_parts), fontweight='bold')

    # Add legend if multiple wavelengths
    if x_variable in ["power", "gate_voltage"] and "wavelength_nm" in its_data.columns:
        wavelengths_count = its_data["wavelength_nm"].n_unique()
        if wavelengths_count > 1:
            ax.legend(loc='best', framealpha=0.9, title='Wavelength')

    # # Add statistics text box
    # mean_y = np.mean(y_values)
    # std_y = np.std(y_values)
    # min_y = np.min(y_values)
    # max_y = np.max(y_values)

    # stats_text = (
    #     f'Mean: {mean_y*1e6:.3f} µA\n'
    #     f'Std: {std_y*1e6:.3f} µA\n'
    #     f'Range: [{min_y*1e6:.3f}, {max_y*1e6:.3f}] µA'
    # )
    # ax.text(
    #     0.02, 0.98, stats_text,
    #     transform=ax.transAxes,
    #     verticalalignment='top',
    #     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    # )

    # Add data point count
    # ax.text(
    #     0.98, 0.02, f'N = {len(y_values)} measurements',
    #     transform=ax.transAxes,
    #     horizontalalignment='right',
    #     verticalalignment='bottom',
    #     bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8)
    # )

    plt.tight_layout()

    # Build output filename following ITS naming convention
    # Pattern: encap{chip_number}_ITS_photoresponse_vs_{x_variable}[_filters]_{plot_tag}.png
    # Extract chip number from chip_name (e.g., "Alisson67" -> "67")
    import re
    chip_match = re.search(r'(\d+)$', chip_name)
    chip_number = chip_match.group(1) if chip_match else chip_name

    filename_parts = [f"encap{chip_number}", "ITS_photoresponse", "vs", x_variable]

    # Add filter suffixes
    if filter_wavelength is not None:
        filename_parts.append(f"wl{filter_wavelength:.0f}nm")
    if filter_vg is not None:
        filename_parts.append(f"vg{filter_vg:.2f}V".replace(".", "p"))

    # Add plot tag (seq numbers hash)
    if plot_tag:
        filename_parts.append(plot_tag)

    filename = "_".join(filename_parts) + ".png"

    # Extract chip number for path construction
    chip_num = int(chip_number) if chip_number.isdigit() else None

    # Build metadata for automatic subcategory detection
    # Photoresponse plots are always from light experiments
    metadata = {"has_light": True}

    # Use correct procedure name ("It" not "ITS") and pass metadata for Light_It/ subfolder
    output_file = config.get_output_path(
        filename,
        chip_number=chip_num,
        procedure="It",
        metadata=metadata,
        create_dirs=True  # Create directory if it doesn't exist
    )

    plt.savefig(output_file, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)

    print(f"saved {output_file}")

    return output_file
