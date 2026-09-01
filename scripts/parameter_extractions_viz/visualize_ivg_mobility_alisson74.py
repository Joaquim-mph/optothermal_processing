"""Standalone Encap 74 mobility panel: signed gm vs Vg with the peak-gm points.

The gm half of visualize_ivg_cnp_mobility_alisson74.py, on its own axes and
styled like visualize_ivg_cnp_alisson74.py (theme fonts, 7:5 panel, PDF).

Signed gm (not |gm|) is plotted: hole-branch peaks sit at negative gm,
electron-branch peaks at positive gm. Forward and backward legs are drawn
separately, with the four peak-gm points marked — holes/electrons ×
forward/backward — and their µ_FE values given in the legend.

Run from repo root:

    python scripts/parameter_extractions_viz/visualize_ivg_mobility_alisson74.py
    python scripts/parameter_extractions_viz/visualize_ivg_mobility_alisson74.py --seq 14
    python scripts/parameter_extractions_viz/visualize_ivg_mobility_alisson74.py --all
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.cnp_parabola import split_full_range_legs
from src.derived.algorithms.mobility import peak_gm_on_leg
from src.derived.extractors.mobility_extractor import MobilityExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

CHIP = 74
HISTORY = Path(f"data/03_derived/chip_histories_enriched/Alisson{CHIP}_history.parquet")
OUTDIR = Path(f"figs/Encap{CHIP}/IVg/Mobility_overlay")

DIR_COLORS = {"forward": "#1f77b4", "backward": "#d62728"}

# Legend font: 4 pt larger than the "small" relative size, resolved against the
# active theme's base font size so it stays correct regardless of theme.
LEGEND_FONTSIZE_BUMP = 4.0


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


# Line/marker weights for the theme's heavier defaults (lw 4.0, markersize 22).
TRACE_LINEWIDTH = 5.5      # gm(Vg) legs
ZERO_LINEWIDTH = 3.0       # gm = 0 guide
MARKER_SIZE = 30.0         # peak-gm points
MARKER_EDGE_LW = 3.0

# Panel shape, following the reference convention: box_aspect = height / width.
BOX_ASPECT = 4.0 / 7.0     # 7:4 (width:height)

# Legend mobilities are written against a fixed 10^4 factor so the four values
# stay directly comparable.
MU_EXPONENT = 4


def _mu_sci(value: float) -> str:
    """µ_FE as a mantissa against a fixed 10^MU_EXPONENT, as a mathtext atom."""
    mantissa = value / 10.0**MU_EXPONENT
    return rf"${mantissa:.2f} \times 10^{{{MU_EXPONENT}}}$"


def _run_mobility(df, metadata):
    out = {}
    for branch in ("holes", "electrons"):
        for direction in ("forward", "backward"):
            out[(branch, direction)] = MobilityExtractor(
                branch=branch,
                direction=direction,
            ).extract(df, metadata)
    return out


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

    vg = df["Vg (V)"].to_numpy()
    i = df["I (A)"].to_numpy()

    mob_metrics = _run_mobility(df, metadata)

    # Per-leg gm traces and their peak-gm points.
    leg_data = {}
    for vg_leg, i_leg, direction in split_full_range_legs(vg, i):
        gm_h, gm_e, vg_h, vg_e, vg_seg, i_seg, gm_seg, cnp = peak_gm_on_leg(
            vg_leg, i_leg
        )
        leg_data[direction] = {
            "vg_seg": vg_seg,
            "gm_seg": gm_seg,
            "gm_h": gm_h,
            "gm_e": gm_e,
            "vg_h": vg_h,
            "vg_e": vg_e,
            "cnp": cnp,
        }

    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / BOX_ASPECT, side))

    for direction, d in leg_data.items():
        ax.plot(
            d["vg_seg"],
            d["gm_seg"] * 1e6,
            color=DIR_COLORS[direction],
            lw=TRACE_LINEWIDTH,
            alpha=0.9,
            label=direction,
        )

    # Mobility-peak markers (signed gm), with µ_FE pulled from MobilityExtractor.
    marker_specs = [
        ("holes", "forward", "o"),
        ("holes", "backward", "o"),
        ("electrons", "forward", "s"),
        ("electrons", "backward", "s"),
    ]
    for branch, direction, marker in marker_specs:
        d = leg_data.get(direction)
        if d is None:
            continue
        gm_signed = d["gm_h"] if branch == "holes" else d["gm_e"]
        vg_at = d["vg_h"] if branch == "holes" else d["vg_e"]
        if not (np.isfinite(gm_signed) and np.isfinite(vg_at)):
            continue
        ax.plot(
            [vg_at],
            [gm_signed * 1e6],
            color=DIR_COLORS[direction],
            markeredgecolor="black",
            markeredgewidth=MARKER_EDGE_LW,
            marker=marker,
            markersize=MARKER_SIZE,
            linestyle="none",
            zorder=5,
        )

    # The figure illustrates *where* µ_FE is extracted, so the legend keys the
    # two encodings (color = sweep direction, shape = branch) instead of listing
    # values; the numbers go to stdout for the methodology text instead.
    for (branch, direction), mob in sorted(mob_metrics.items()):
        if mob is not None:
            print(
                f"    µ_FE {branch:>9} {direction:<8} = "
                f"{mob.value_float:.3e} cm²/V·s"
            )

    handles, labels = ax.get_legend_handles_labels()
    for branch, marker in (("hole", "o"), ("electron", "s")):
        handles.append(
            Line2D(
                [], [],
                color="0.75",
                markeredgecolor="black",
                markeredgewidth=MARKER_EDGE_LW,
                marker=marker,
                markersize=MARKER_SIZE,
                linestyle="none",
            )
        )
        labels.append(f"{branch} peak ($\\mu_{{FE}}$)")

    ax.axhline(0.0, color="0.6", lw=ZERO_LINEWIDTH, zorder=0)
    ax.set_xlabel(r"$V_g\ (\mathrm{V})$")
    ax.set_ylabel(r"$g_m = dI/dV_g\ (\mu\mathrm{S})$")
    ax.set_box_aspect(BOX_ASPECT)
    ax.legend(
        handles, labels,
        loc="upper left", framealpha=0.9, ncol=2,
        fontsize=_legend_fontsize(),
    )

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
        out_path = OUTDIR / f"Encap{CHIP}_IVg_seq{int(row['seq']):03d}_mobility.pdf"
        _plot_one(row, config, out_path)


if __name__ == "__main__":
    main()
