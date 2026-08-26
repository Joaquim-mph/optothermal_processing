"""Generate an IVg transfer-curve diagram with a single vertical line at the
minimum-current (Dirac) point.

Uses the same data format as procedure_diags.py (Alisson80/81 chip histories)
but strips the V_start / V_end reference lines and annotates only the
charge-neutrality point.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet

CURVE_COLOR = "crimson"
DIRAC_LINE_COLOR = "black"
REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = REPO_ROOT / "data" / "02_stage" / "chip_histories"


def _style_axes(ax: plt.Axes) -> None:
    ax.grid(True, which="major", axis="both", linewidth=0.6, alpha=0.5)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)


def _load_measurement(chip_name: str, seq: int) -> pl.DataFrame:
    history = pl.read_parquet(HISTORY_DIR / f"{chip_name}_history.parquet")
    row = history.filter(pl.col("seq") == seq).row(0, named=True)
    return read_measurement_parquet(row["parquet_path"])


def draw_ivg_dirac_diagram(
    out_path: Path,
    show: bool,
    chip_name: str = "Alisson81",
    seq: int = 1,
) -> None:
    """IVg transfer curve with a vertical line at the minimum-current V_G."""
    data = _load_measurement(chip_name, seq)

    vg = data["Vg (V)"].to_numpy()
    i = data["I (A)"].to_numpy() * 1e6  # convert to µA

    # Identify the Dirac point as the gate voltage at minimum |current|.
    dirac_idx = int(np.argmin(np.abs(i)))
    vg_dirac = float(vg[dirac_idx])
    i_dirac = float(i[dirac_idx])

    v_start = float(data["vg_start_v"][0])
    v_end = float(data["vg_end_v"][0])

    fig, ax = plt.subplots(figsize=(6.0, 4.5))

    ax.plot(vg, i, color=CURVE_COLOR, lw=2.4)

    # Single vertical line at the Dirac (minimum-current) point.
    ax.axvline(vg_dirac, color=DIRAC_LINE_COLOR, lw=1.0, alpha=0.7,
               linestyle="--", label=r"$V_{\mathrm{Dirac}}$")

    # Optional: mark the Dirac point on the curve.
    #ax.plot(vg_dirac, i_dirac, "o", color=DIRAC_LINE_COLOR, ms=6,
    #        markerfacecolor="white", markeredgewidth=1.5)

    ax.set_xlim(v_start - 0.5, v_end + 0.5)
    # Use actual numeric values for x-axis ticks
    ax.set_xticks([v_start, 0, v_end])
    ax.set_xticklabels(
        [f"{v_start:.0f}", "0", f"{v_end:.0f}"]
    )

    ax.set_xlabel(r"$V_{G}\,(\mathrm{V})$", fontsize=13)
    ax.set_ylabel(r"$I_{DS}\,(\mu\mathrm{A})$", fontsize=13)

    _style_axes(ax)
    ax.grid(False)

    #ax.legend(loc="best", fontsize=11, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Directory to write PDFs into (default: script directory)",
    )
    parser.add_argument(
        "--show", action="store_true", help="Display windows interactively"
    )
    parser.add_argument(
        "--chip", default="Alisson81", help="Chip name (default: Alisson81)"
    )
    parser.add_argument(
        "--seq", type=int, default=1, help="Sequence number (default: 1)"
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    draw_ivg_dirac_diagram(
        args.out_dir / "ivg_dirac_diagram.png",
        args.show,
        chip_name=args.chip,
        seq=args.seq,
    )


if __name__ == "__main__":
    main()
