"""VVg (voltage vs gate voltage) plotting functions."""

from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import polars as pl

from src.core.utils import read_measurement_parquet

# Configuration (will be overridden by CLI)
FIG_DIR = Path("figs")


def plot_vvg_sequence(df: pl.DataFrame, base_dir: Path, tag: str):
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
    """
    # Apply plot style (lazy initialization for thread-safety)
    from src.plotting.styles import set_plot_style
    set_plot_style("prism_rain")

    vvg = df.filter(pl.col("proc") == "VVg").sort("file_idx")
    if vvg.height == 0:
        return

    plt.figure()
    for row in vvg.iter_rows(named=True):
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
        if "VDS (V)" in d.columns:
            col_map["VDS (V)"] = "VDS"
        if col_map:
            d = d.rename(col_map)

        # Expect columns: VG, VDS (standardized)
        if not {"VG", "VDS"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/VDS; got {d.columns}")
            continue
        lbl = f"#{int(row['file_idx'])}  {'light' if row['has_light'] else 'dark'}"
        plt.plot(d["VG"], d["VDS"]*1e3, label=lbl)  # Convert V to mV

    plt.xlabel("$\\rm{V_g\\ (V)}$")
    plt.ylabel("$\\rm{V_{ds}\\ (mV)}$")
    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history
    plt.title(f"Encap{chipnum} — VVg")
    plt.legend()
    plt.tight_layout()
    #plt.ylim(bottom=0)
    out = FIG_DIR / f"encap{chipnum}_VVg_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
