"""IVg (current vs gate voltage) plotting functions."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt
import polars as pl
import numpy as np

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig


def plot_ivg_sequence(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    show_cnp: bool = False,
    conductance: bool = False,
    absolute: bool = False,
    inverse: bool = False,
    config: Optional[PlotConfig] = None,
):
    """
    Plot all IVg in chronological order (Id vs Vg, G vs Vg, or 1/G vs Vg).

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with IVg experiments
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    show_cnp : bool
        If True, overlay detected CNP points in bright yellow
        (disabled when conductance=True or inverse=True)
    conductance : bool, optional
        If True, plot conductance G=I/V instead of current. Default: False
    absolute : bool, optional
        If True, plot |G| or |1/G| (absolute values). Only valid with conductance=True.
        Default: False
    inverse : bool, optional
        If True, plot inverse conductance 1/G=V/I to estimate resistance.
        Only valid with conductance=True. Default: False
    config : PlotConfig, optional
        Plot configuration (theme, DPI, output paths, etc.)
    """
    # Initialize config with defaults
    config = config or PlotConfig()

    # Apply plot style from config
    from src.plotting.styles import set_plot_style
    from src.plotting.plot_utils import extract_cnp_for_plotting, ensure_standard_columns
    from src.plotting.transforms import calculate_conductance, calculate_inverse_conductance
    set_plot_style(config.theme)

    # Disable CNP markers when using conductance mode
    if conductance and show_cnp and not inverse:
        from src.plotting.plot_utils import print_warning
        print_warning("CNP markers disabled in conductance mode")
        show_cnp = False

    # Note: CNP markers ARE supported in inverse mode (they will be transformed)

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        return

    plt.figure(figsize=config.figsize_voltage_sweep)
    cnp_markers_added = False

    # Track units for conductance plots (will be set in first iteration)
    units = None
    for row in ivg.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue
        d = read_measurement_parquet(path)

        # Normalize column names (handle both formats)
        d = ensure_standard_columns(d)

        # Expect columns: VG, I (standardized)
        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/I; got {d.columns}")
            continue

        lbl = f"#{int(row['file_idx'])}  {'light' if row['has_light'] else 'dark'}"

        # Plot conductance, inverse conductance, or current based on mode
        if conductance:
            # Extract VDS from metadata (check both column naming conventions)
            vds = row.get("vds_v") or row.get("VDS")

            if vds is None or vds == 0 or not np.isfinite(vds):
                mode_str = "inverse conductance" if inverse else "conductance"
                print(f"[warn] Skipping seq #{int(row['file_idx'])}: VDS={vds}V (cannot calculate {mode_str})")
                continue

            if inverse:
                # Calculate inverse conductance 1/G = V/I (resistance)
                inv_G, ylabel_text, units_temp = calculate_inverse_conductance(d["I"], vds, absolute=absolute)

                if inv_G is None:
                    continue  # Skip this curve (already warned in calculate_inverse_conductance)

                # Store units from first successful calculation
                if units is None:
                    units = units_temp

                plt.plot(d["VG"], inv_G, label=lbl)
            else:
                # Calculate conductance G = I/V
                G, ylabel_text, units_temp = calculate_conductance(d["I"], vds, absolute=absolute)

                if G is None:
                    continue  # Skip this curve (already warned in calculate_conductance)

                # Store units from first successful calculation
                if units is None:
                    units = units_temp

                plt.plot(d["VG"], G, label=lbl)
        else:
            # Original current plot
            plt.plot(d["VG"], d["I"]*1e6, label=lbl)

        # Add CNP markers if requested
        if show_cnp:
            # Need to pass un-normalized measurement for CNP extraction
            d_original = read_measurement_parquet(path)
            all_cnp_vgs, all_cnp_is, avg_cnp_vg, avg_cnp_i = extract_cnp_for_plotting(d_original, row, "IVg")

            if all_cnp_vgs is not None and all_cnp_is is not None:
                # Plot all detected CNPs in yellow
                all_label = "All CNPs" if not cnp_markers_added else None
                plt.plot(all_cnp_vgs, np.array(all_cnp_is)*1e6, 'o', color='yellow',
                         markersize=6, markeredgecolor='black', markeredgewidth=1,
                         label=all_label, zorder=100)

                # Plot average CNP in red diamond
                if avg_cnp_vg is not None and avg_cnp_i is not None:
                    avg_label = "Average CNP" if not cnp_markers_added else None
                    plt.plot(avg_cnp_vg, avg_cnp_i*1e6, 'D', color='red',
                             markersize=10, markeredgecolor='black', markeredgewidth=1.5,
                             label=avg_label, zorder=101)

                cnp_markers_added = True

    plt.xlabel("$\\rm{V_g\\ (V)}$")

    # Update axis labels and title based on mode
    if conductance:
        # Use units from first successful calculation
        if inverse:
            # Inverse conductance mode (1/G with resistance units)
            if units is not None:
                ylabel_base = "1/G" if not absolute else "|1/G|"
                plt.ylabel(f"$\\rm{{{ylabel_base}\\ ({units})}}$")
            else:
                # Fallback if no successful calculations (shouldn't happen)
                plt.ylabel("$\\rm{1/G\\ (\\Omega)}$" if not absolute else "$\\rm{|1/G|\\ (\\Omega)}$")
            title_suffix = " (Inverse Conductance)"
        else:
            # Regular conductance mode
            if units is not None:
                plt.ylabel(f"$\\rm{{G\\ ({units})}}$" if not absolute else f"$\\rm{{|G|\\ ({units})}}$")
            else:
                # Fallback if no successful calculations (shouldn't happen)
                plt.ylabel("$\\rm{G\\ (S)}$" if not absolute else "$\\rm{|G|\\ (S)}$")
            title_suffix = " (Conductance)"
        plt.ylim(bottom=0)  # Positive values only for conductance/inverse conductance
    else:
        plt.ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
        title_suffix = ""
        plt.ylim(bottom=0)  # Positive values for current

    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history
    plt.title(f"Encap{chipnum} — IVg{title_suffix}")
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
            print_warning("Mixed illumination experiments - saving to IVg root folder")

    # Add suffix for conductance and inverse conductance plots
    if conductance and inverse:
        tag_suffix = "_invG"
    elif conductance:
        tag_suffix = "_G"
    else:
        tag_suffix = ""
    filename = f"encap{chipnum}_IVg_{tag}{tag_suffix}"
    out = config.get_output_path(
        filename,
        chip_number=chipnum,
        procedure="IVg",
        metadata=illumination_metadata,
        create_dirs=True
    )
    plt.savefig(out, dpi=config.dpi)
    print(f"saved {out}")
