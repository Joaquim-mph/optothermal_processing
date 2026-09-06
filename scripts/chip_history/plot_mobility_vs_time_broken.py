"""Field-effect mobility vs time with a broken x-axis.

Same data points, filters, and exclusions as plot_cnp_vs_time.py, but
plotting the direction-averaged peak field-effect mobility (holes and
electrons) instead of the CNP voltage. Two rows: holes on top, electrons
on bottom.

Outputs (figs/cnp_time/):
    mobility_vs_time_{chips}_broken.{pdf,png}

Run from repo root:
    .venv/bin/python scripts/chip_history/plot_mobility_vs_time_broken.py
    .venv/bin/python scripts/chip_history/plot_mobility_vs_time_broken.py \
        --chips 72,74,75,80 --marker-by material
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.axes import Axes

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_cnp_vs_time import (
    DEFAULT_CHIPS,
    EXCLUDE_MONTHS,
    EXCLUDE_SESSIONS,
    LEGEND_FONTSIZE_BUMP,
    MARKER_EDGE_WIDTH,
    MARKER_SIZE,
    METRICS_PARQUET,
    MANIFEST_PARQUET,
    MIN_CONFIDENCE,
    OUTPUT_DIR,
    chip_specs,
    console,
    load_cnp,
    materials,
)
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

BREAK_START = date(2025, 11, 1)
BREAK_END = date(2026, 4, 1)
LEFT_WEIGHT = 1.0
RIGHT_WEIGHT = 3.0
LOCAL_TZ = "America/Santiago"


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


def load_mobility(
    cnp_rows: pl.DataFrame,
) -> pl.DataFrame:
    """Load mobility metrics for exactly the same run_ids surviving in cnp_rows."""
    run_ids = cnp_rows["run_id"].unique().to_list()

    metrics = pl.read_parquet(METRICS_PARQUET).filter(
        pl.col("metric_name").is_in(["mobility_fe_holes", "mobility_fe_electrons"])
        & pl.col("run_id").is_in(run_ids)
        & pl.col("value_float").is_not_null()
        & pl.col("value_float").is_not_nan())

    time_cols = cnp_rows.select(["run_id", "chip_number", "t_local", "session_date"]).unique(subset=["run_id"])
    rows = metrics.join(time_cols, on=["run_id", "chip_number"], how="inner")

    return (
        rows.select([
            "chip_number", "run_id", "t_local", "session_date",
            "metric_name", "value_float", "confidence",
        ])
        .sort(["chip_number", "metric_name", "t_local"])
    )


def _draw_break_marks(ax_left: Axes, ax_right: Axes, size: float = 0.015) -> None:
    kwargs = dict(
        transform=ax_left.transAxes, color="black", clip_on=False,
        lw=plt.rcParams.get("axes.linewidth", 1.5),
    )
    d = size
    ax_left.plot((1 - d, 1 + d), (-d, +d), **kwargs)
    ax_left.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)
    kwargs["transform"] = ax_right.transAxes
    ax_right.plot((-d, +d), (-d, +d), **kwargs)
    ax_right.plot((-d, +d), (1 - d, 1 + d), **kwargs)


def _set_xlims(ax_left, ax_right, all_dates):
    padding = timedelta(days=5)
    left_dates = [d for d in all_dates if d < BREAK_START]
    right_dates = [d for d in all_dates if d >= BREAK_END]
    if left_dates:
        ax_left.set_xlim(left_dates[0] - padding, left_dates[-1] + padding)
    if right_dates:
        ax_right.set_xlim(right_dates[0] - padding, right_dates[-1] + padding)


def _format_date_axis(ax):
    locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")


def draw_panel_pair(
    ax_left, ax_right, mob_rows, specs, metric_name, ylabel,
    show_legend=False, show_xlabel=True,
):
    sub = mob_rows.filter(pl.col("metric_name") == metric_name)
    all_dates = sorted(set(sub["session_date"]))

    for spec in specs:
        chip_sub = sub.filter(pl.col("chip_number") == spec["chip"])
        if chip_sub.height == 0:
            continue
        values = chip_sub["value_float"].to_numpy() / 1e4
        for ax in (ax_left, ax_right):
            ax.plot(
                chip_sub["t_local"].to_list(),
                values,
                ls="none",
                marker=spec["marker"],
                ms=MARKER_SIZE,
                color=spec["color"],
                mfc="none",
                mew=MARKER_EDGE_WIDTH,
                label=spec["label"] if ax is ax_left else None,
            )

    _set_xlims(ax_left, ax_right, all_dates)
    for ax in (ax_left, ax_right):
        ax.margins(y=0.06)
        _format_date_axis(ax)

    ax_left.spines["right"].set_visible(False)
    ax_right.spines["left"].set_visible(False)
    ax_right.tick_params(left=False, labelleft=False)

    y0 = min(ax_left.get_ylim()[0], ax_right.get_ylim()[0])
    y1 = max(ax_left.get_ylim()[1], ax_right.get_ylim()[1])
    ax_left.set_ylim(max(0, y0), y1)
    ax_right.set_ylim(max(0, y0), y1)

    _draw_break_marks(ax_left, ax_right)
    ax_left.set_ylabel(ylabel)

    if not show_xlabel:
        ax_left.tick_params(labelbottom=False)
        ax_right.tick_params(labelbottom=False)

    if show_legend:
        ax_left.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--chips", type=str, default=",".join(str(c) for c in DEFAULT_CHIPS))
    p.add_argument("--marker-by", choices=("chip", "material"), default="chip")
    p.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    p.add_argument("--include-light", action="store_true")
    p.add_argument("--keep-single-leg", action="store_true")
    p.add_argument("--exclude-month", action="append", default=None, metavar="YYYY-MM")
    p.add_argument("--exclude-session", action="append", default=None, metavar="CHIP:YYYY-MM-DD")
    p.add_argument("--all-history", action="store_true")
    args = p.parse_args()

    if args.all_history:
        exclude_months: tuple[str, ...] = ()
        exclude_sessions: tuple[tuple[int, str], ...] = ()
        require_both_legs = False
    else:
        exclude_months = tuple(
            args.exclude_month if args.exclude_month is not None else EXCLUDE_MONTHS
        )
        if args.exclude_session is None:
            exclude_sessions = EXCLUDE_SESSIONS
        else:
            exclude_sessions = tuple(
                (int(tok.split(":", 1)[0]), tok.split(":", 1)[1])
                for tok in args.exclude_session
            )
        require_both_legs = not args.keep_single_leg

    chips = [int(c) for c in args.chips.split(",") if c.strip()]
    if not chips:
        raise SystemExit("--chips is empty")
    material = materials()
    specs = chip_specs(chips, material, args.marker_by)

    cnp_rows = load_cnp(
        chips, args.min_confidence, args.include_light,
        require_both_legs, exclude_months, exclude_sessions,
    )
    if cnp_rows.height == 0:
        raise SystemExit("no data points survived the filters")

    mob_rows = load_mobility(cnp_rows)
    console.print(f"mobility points: {mob_rows.height} (holes + electrons)")

    config = PlotConfig(
        output_dir=OUTPUT_DIR,
        chip_subdir_enabled=False,
        use_proc_subdirs=False,
        auto_subcategories=False,
    )
    set_plot_style(config)

    height = float(config.figsize_timeseries[1])
    fig, axes = plt.subplots(
        2, 2, sharey="row",
        figsize=(1.6 * height, 2 * height),
        gridspec_kw={
            "width_ratios": [LEFT_WEIGHT, RIGHT_WEIGHT],
            "wspace": 0.04, "hspace": 0.12,
        },
    )

    draw_panel_pair(
        axes[0, 0], axes[0, 1], mob_rows, specs,
        "mobility_fe_holes",
        r"$\mu_h$ ($10^4$ cm$^2$V$^{-1}$s$^{-1}$)",
        show_legend=True, show_xlabel=False,
    )
    draw_panel_pair(
        axes[1, 0], axes[1, 1], mob_rows, specs,
        "mobility_fe_electrons",
        r"$\mu_e$ ($10^4$ cm$^2$V$^{-1}$s$^{-1}$)",
        show_legend=False, show_xlabel=True,
    )

    fig.text(0.5, 0.0, "Date", ha="center", va="bottom",
             fontsize=plt.rcParams["font.size"])
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.10)

    stem = "mobility_vs_time_" + "_".join(str(c) for c in sorted(chips)) + "_broken"
    for name in (stem, f"{stem}.png"):
        out = config.get_output_path(name, create_dirs=True)
        fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
        print(f"saved {out}")
    plt.close(fig)


if __name__ == "__main__":
    main()
