"""IVg (current vs gate voltage) plotting functions."""

from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import polars as pl

from src.core.utils import _read_measurement

# Configuration (will be overridden by CLI)
FIG_DIR = Path("figs")


def plot_ivg_sequence(df: pl.DataFrame, base_dir: Path, tag: str):
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
    """
    # Apply plot style (lazy initialization for thread-safety)
    from src.plotting.styles import set_plot_style
    set_plot_style("prism_rain")

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        return

    plt.figure()
    for row in ivg.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue
        d = _read_measurement(path)
        # Expect columns: VG, I (standardized)
        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/I; got {d.columns}")
            continue
        lbl = f"#{int(row['file_idx'])}  {'light' if row['with_light'] else 'dark'}"
        plt.plot(d["VG"], d["I"]*1e6, label=lbl)

    plt.xlabel("$\\rm{V_g\\ (V)}$")
    plt.ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    chipnum = int(df['Chip number'][0])
    plt.title(f"Encap{chipnum} — IVg")
    plt.legend()
    plt.ylim(bottom=0)
    plt.tight_layout()

    out = FIG_DIR / f"encap{chipnum}_IVg_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
