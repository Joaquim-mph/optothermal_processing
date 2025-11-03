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
    config: Optional[PlotConfig] = None,
):
    """
    Plot all VVg in chronological order (Vds vs Vg).

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
    config : PlotConfig, optional
        Plot configuration (theme, DPI, output paths, etc.)
    """
    # Initialize config with defaults
    config = config or PlotConfig()

    # Apply plot style from config
    from src.plotting.styles import set_plot_style
    from src.plotting.plot_utils import extract_cnp_for_plotting, ensure_standard_columns
    set_plot_style(config.theme)

    vvg = df.filter(pl.col("proc") == "VVg").sort("file_idx")
    if vvg.height == 0:
        return

    plt.figure(figsize=config.figsize_voltage_sweep)
    cnp_markers_added = False
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
    plt.ylabel("$\\rm{V_{ds}\\ (mV)}$")
    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history
    plt.title(f"Encap{chipnum} — VVg")
    plt.legend()
    plt.tight_layout()
    #plt.ylim(bottom=0)
    filename = f"encap{chipnum}_VVg_{tag}.png"
    out = config.get_output_path(filename, procedure="VVg")
    plt.savefig(out, dpi=config.dpi)
    print(f"saved {out}")
