"""VVg (voltage vs gate voltage) plotting functions."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt
import polars as pl
import numpy as np

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig


def plot_vvg_sequence(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    show_cnp: bool = False,
    resistance: bool = False,
    absolute: bool = False,
    inverse: bool = False,
    config: Optional[PlotConfig] = None,
):
    """
    Plot all VVg in chronological order (Vds vs Vg, R vs Vg, or 1/R vs Vg).

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with VVg experiments
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    show_cnp : bool
        If True, overlay detected CNP points in bright yellow
        (disabled when resistance=True or inverse=True)
    resistance : bool, optional
        If True, plot resistance R=V/I instead of voltage. Default: False
    absolute : bool, optional
        If True, plot |R| or |1/R| (absolute values). Only valid with resistance=True.
        Default: False
    inverse : bool, optional
        If True, plot inverse resistance 1/R=I/V to estimate conductance.
        Only valid with resistance=True. Default: False
    config : PlotConfig, optional
        Plot configuration (theme, DPI, output paths, etc.)
    """
    # Initialize config with defaults
    config = config or PlotConfig()

    # Apply plot style from config
    from src.plotting.styles import set_plot_style
    from src.plotting.plot_utils import extract_cnp_for_plotting, ensure_standard_columns
    from src.plotting.transforms import calculate_resistance, calculate_inverse_resistance
    set_plot_style(config.theme)

    # Disable CNP markers when using resistance mode
    if resistance and show_cnp and not inverse:
        from src.plotting.plot_utils import print_warning
        print_warning("CNP markers disabled in resistance mode")
        show_cnp = False

    # Note: CNP markers ARE supported in inverse mode (they will be transformed)

    vvg = df.filter(pl.col("proc") == "VVg").sort("file_idx")
    if vvg.height == 0:
        return

    plt.figure(figsize=config.figsize_voltage_sweep)
    cnp_markers_added = False

    # Track units for resistance plots (will be set in first iteration)
    units = None
    for row in vvg.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue
        d = read_measurement_parquet(path)

        # Normalize column names (handle both formats)
        d = ensure_standard_columns(d)

        # Expect columns: VG, VDS (standardized)
        if not {"VG", "VDS"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/VDS; got {d.columns}")
            continue

        lbl = f"#{int(row['file_idx'])}  {'light' if row['has_light'] else 'dark'}"

        # Plot resistance, inverse resistance, or voltage based on mode
        if resistance:
            # Extract IDS from metadata (check both column naming conventions)
            ids = row.get("ids_a") or row.get("Drain-Source current")

            if ids is None or ids == 0 or not np.isfinite(ids):
                mode_str = "inverse resistance" if inverse else "resistance"
                print(f"[warn] Skipping seq #{int(row['file_idx'])}: IDS={ids}A (cannot calculate {mode_str})")
                continue

            if inverse:
                # Calculate inverse resistance 1/R = I/V (conductance)
                inv_R, ylabel_text, units_temp = calculate_inverse_resistance(d["VDS"], ids, absolute=absolute)

                if inv_R is None:
                    continue  # Skip this curve (already warned in calculate_inverse_resistance)

                # Store units from first successful calculation
                if units is None:
                    units = units_temp

                plt.plot(d["VG"], inv_R, label=lbl)
            else:
                # Calculate resistance R = V/I
                R, ylabel_text, units_temp = calculate_resistance(d["VDS"], ids, absolute=absolute)

                if R is None:
                    continue  # Skip this curve (already warned in calculate_resistance)

                # Store units from first successful calculation
                if units is None:
                    units = units_temp

                plt.plot(d["VG"], R, label=lbl)
        else:
            # Original voltage plot
            plt.plot(d["VG"], d["VDS"]*1e3, label=lbl)  # Convert V to mV

        # Add CNP markers if requested
        if show_cnp:
            # Need to pass un-normalized measurement for CNP extraction
            d_original = read_measurement_parquet(path)
            all_cnp_vgs, all_cnp_vds, avg_cnp_vg, avg_cnp_vds = extract_cnp_for_plotting(d_original, row, "VVg")

            if all_cnp_vgs is not None and all_cnp_vds is not None:
                # Plot all detected CNPs in yellow
                all_label = "All CNPs" if not cnp_markers_added else None
                plt.plot(all_cnp_vgs, np.array(all_cnp_vds)*1e3, 'o', color='yellow',
                         markersize=6, markeredgecolor='black', markeredgewidth=1,
                         label=all_label, zorder=100)

                # Plot average CNP in red diamond
                if avg_cnp_vg is not None and avg_cnp_vds is not None:
                    avg_label = "Average CNP" if not cnp_markers_added else None
                    plt.plot(avg_cnp_vg, avg_cnp_vds*1e3, 'D', color='red',
                             markersize=10, markeredgecolor='black', markeredgewidth=1.5,
                             label=avg_label, zorder=101)

                cnp_markers_added = True

    plt.xlabel("$\\rm{V_g\\ (V)}$")

    # Update axis labels and title based on mode
    if resistance:
        # Use units from first successful calculation
        if inverse:
            # Inverse resistance mode (1/R with conductance units)
            if units is not None:
                ylabel_base = "1/R" if not absolute else "|1/R|"
                plt.ylabel(f"$\\rm{{{ylabel_base}\\ ({units})}}$")
            else:
                # Fallback if no successful calculations (shouldn't happen)
                plt.ylabel("$\\rm{1/R\\ (S)}$" if not absolute else "$\\rm{|1/R|\\ (S)}$")
            title_suffix = " (Inverse Resistance)"
        else:
            # Regular resistance mode
            if units is not None:
                plt.ylabel(f"$\\rm{{R\\ ({units})}}$" if not absolute else f"$\\rm{{|R|\\ ({units})}}$")
            else:
                # Fallback if no successful calculations (shouldn't happen)
                plt.ylabel("$\\rm{R\\ (\\Omega)}$" if not absolute else "$\\rm{|R|\\ (\\Omega)}$")
            title_suffix = " (Resistance)"
        plt.ylim(bottom=0)  # Positive values only for resistance/inverse resistance
    else:
        plt.ylabel("$\\rm{V_{ds}\\ (mV)}$")
        title_suffix = ""
        plt.ylim(bottom=0)  # Positive values only for voltage

    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history
    chip_group = None
    if "chip_group" in df.columns:
        chip_group = df["chip_group"][0]
    prefix = f"{chip_group}{chipnum}" if chip_group else f"encap{chipnum}"
    plt.title(f"{prefix} — VVg{title_suffix}")
    plt.legend()
    plt.tight_layout()

    # Determine illumination status for subcategory
    illumination_metadata = None
    if "has_light" in df.columns:
        has_light_values = df["has_light"].unique().to_list()
        has_light_values = [v for v in has_light_values if v is not None]

        if len(has_light_values) == 1:
            illumination_metadata = {"has_light": has_light_values[0]}
        elif len(has_light_values) > 1:
            from src.plotting.plot_utils import print_warning
            print_warning("Mixed illumination experiments - saving to VVg root folder")

    # Add suffix for resistance and inverse resistance plots
    if resistance and inverse:
        tag_suffix = "_invR"
    elif resistance:
        tag_suffix = "_R"
    else:
        tag_suffix = ""
    filename = f"{prefix}_VVg_{tag}{tag_suffix}"
    out = config.get_output_path(
        filename,
        chip_number=chipnum,
        procedure="VVg",
        metadata=illumination_metadata,
        create_dirs=True
    )
    plt.savefig(out, dpi=config.dpi)
    print(f"saved {out}")
