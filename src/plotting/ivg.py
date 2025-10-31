"""IVg (current vs gate voltage) plotting functions."""

from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import polars as pl
import numpy as np

from src.core.utils import read_measurement_parquet

# Configuration (will be overridden by CLI)
FIG_DIR = Path("figs")


def plot_ivg_sequence(df: pl.DataFrame, base_dir: Path, tag: str, show_cnp: bool = False):
    """
    Plot all IVg in chronological order (Id vs Vg).

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
    """
    # Apply plot style (lazy initialization for thread-safety)
    from src.plotting.styles import set_plot_style
    from src.plotting.plot_utils import extract_cnp_for_plotting
    set_plot_style("prism_rain")

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        return

    plt.figure()
    cnp_markers_added = False
    for row in ivg.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue
        d = read_measurement_parquet(path)

        # Normalize column names (handle both formats)
        col_map = {}
        if "VG (V)" in d.columns:
            col_map["VG (V)"] = "VG"
        elif "Vg (V)" in d.columns:
            col_map["Vg (V)"] = "VG"
        if "I (A)" in d.columns:
            col_map["I (A)"] = "I"
        if col_map:
            d = d.rename(col_map)

        # Expect columns: VG, I (standardized)
        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/I; got {d.columns}")
            continue
        lbl = f"#{int(row['file_idx'])}  {'light' if row['has_light'] else 'dark'}"
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
    plt.ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history
    plt.title(f"Encap{chipnum} — IVg")
    plt.legend()
    plt.ylim(bottom=0)
    plt.tight_layout()

    out = FIG_DIR / f"encap{chipnum}_IVg_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
