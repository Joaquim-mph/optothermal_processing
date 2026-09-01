"""Visualize an IVg sweep from Encap 74 with the three CNPs overlaid.

For a chosen IVg seq (or the first available one) load the staged
Parquet, run the CNPExtractor three times (forward / backward /
average), and plot I vs Vg with the forward and backward parabolic
fits drawn and the three CNP voltages marked as dashed vertical lines.

Styling (fonts, axis labels, legend size, square panel, PDF output)
follows scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py.

Run from repo root:

    python scripts/parameter_extractions_viz/visualize_ivg_cnp_alisson74.py
    python scripts/parameter_extractions_viz/visualize_ivg_cnp_alisson74.py --seq 14
    python scripts/parameter_extractions_viz/visualize_ivg_cnp_alisson74.py --all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.extractors.cnp_extractor import CNPExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

CHIP = 74
HISTORY = Path(f"data/03_derived/chip_histories_enriched/Alisson{CHIP}_history.parquet")
OUTDIR = Path(f"figs/Encap{CHIP}/IVg/CNP_overlay")

# Legend font: 4 pt larger than the "small" relative size, resolved against the
# active theme's base font size so it stays correct regardless of theme.
LEGEND_FONTSIZE_BUMP = 4.0


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


# Line weights matching the heavier styling of the spectral-plot reference
# (theme default is lw 4.0).
TRACE_LINEWIDTH = 5.5      # measured IVg sweep
FIT_LINEWIDTH = 8.0        # parabolic fits (drawn on top of the trace)
CNP_LINEWIDTH = 4.0        # dashed vertical CNP markers

# Panel shape, following the reference convention: box_aspect = height / width.
BOX_ASPECT = 4.0 / 7.0     # 7:4 (width:height)


def _run_three_extractors(df: pl.DataFrame, metadata: dict):
    out = {}
    for direction in ("forward", "backward", "average"):
        metric = CNPExtractor(direction=direction).extract(df, metadata)
        out[direction] = metric
    return out


def _parabola_curve(coeffs: dict, vg_leg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sample the fitted parabola across a span centered on its vertex."""
    a, b, c = coeffs["a"], coeffs["b"], coeffs["c"]
    v_cnp = -b / (2.0 * a)
    span = 0.05 * (vg_leg.max() - vg_leg.min())
    xs = np.linspace(v_cnp - span, v_cnp + span, 200)
    ys = a * xs * xs + b * xs + c
    return xs, ys


def _plot_one(row: dict, config: PlotConfig, out_path: Path) -> None:
    parquet_path = Path(row["parquet_path"])
    df = read_measurement_parquet(parquet_path)
    if "Vg (V)" not in df.columns or "I (A)" not in df.columns:
        print(f"  skipped seq {row['seq']}: missing Vg/I columns")
        return

    metadata = {
        "run_id": row["run_id"],
        "chip_number": row["chip_number"],
        "chip_group": row["chip_group"],
        "proc": "IVg",
        "seq_num": int(row["seq"]),
        "vds_v": float(row["vds_v"]) if row["vds_v"] is not None else None,
        "extraction_version": "visualizer",
    }

    metrics = _run_three_extractors(df, metadata)
    vg = df["Vg (V)"].to_numpy()
    i_uA = df["I (A)"].to_numpy() * 1e6

    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / BOX_ASPECT, side))
    ax.plot(
        vg,
        i_uA,
        lw=TRACE_LINEWIDTH,
        color="black",
        alpha=0.85,
        label="IVg",
    )

    # Pull fit details from whichever row exists (they all share the same JSON).
    details_carrier = next((m for m in metrics.values() if m is not None), None)
    if details_carrier is not None:
        details = json.loads(details_carrier.value_json)

        # Draw fitted parabolas — convert vertex-equation back to µA for the axis.
        if details.get("parabola_fwd") is not None:
            xs, ys = _parabola_curve(details["parabola_fwd"], vg)
            ax.plot(
                xs,
                ys * 1e6,
                color="#1f77b4",
                lw=FIT_LINEWIDTH,
                label="forward fit",
            )
        if details.get("parabola_back") is not None:
            xs, ys = _parabola_curve(details["parabola_back"], vg)
            ax.plot(
                xs,
                ys * 1e6,
                color="#d62728",
                lw=FIT_LINEWIDTH,
                label="backward fit",
            )

    # Vertical lines for the three CNPs.
    colors = {"forward": "#1f77b4", "backward": "#d62728", "average": "#2ca02c"}
    for direction, metric in metrics.items():
        if metric is None:
            continue
        ax.axvline(
            metric.value_float,
            color=colors[direction],
            ls="--",
            lw=CNP_LINEWIDTH,
            alpha=0.9,
            label=f"CNP {direction}: {metric.value_float:.3f} V",
        )

    ax.set_xlabel(r"$V_g\ (\mathrm{V})$")
    ax.set_ylabel(r"$I\ (\mu\mathrm{A})$")
    ax.set_box_aspect(BOX_ASPECT)
    ax.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--seq",
        type=int,
        default=None,
        help="IVg seq to plot. Defaults to the first available.",
    )
    ap.add_argument(
        "--all", action="store_true", help="Plot every IVg in the chip history."
    )
    args = ap.parse_args()

    if not HISTORY.exists():
        raise FileNotFoundError(f"History not found: {HISTORY}")

    hist = pl.read_parquet(HISTORY).filter(pl.col("proc") == "IVg")
    if hist.height == 0:
        raise RuntimeError(f"No IVg sweeps in {HISTORY}")

    if args.all:
        rows = hist.to_dicts()
    elif args.seq is not None:
        rows = hist.filter(pl.col("seq") == args.seq).to_dicts()
        if not rows:
            raise ValueError(f"seq {args.seq} not found among IVg rows")
    else:
        rows = [hist.row(0, named=True)]

    config = PlotConfig()
    set_plot_style(config.theme)

    print(f"Plotting {len(rows)} IVg sweep(s) for Encap{CHIP}")
    for row in rows:
        out_path = OUTDIR / f"Encap{CHIP}_IVg_seq{int(row['seq']):03d}_CNP.pdf"
        _plot_one(row, config, out_path)


if __name__ == "__main__":
    main()
