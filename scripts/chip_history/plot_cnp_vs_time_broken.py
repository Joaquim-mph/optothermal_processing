"""CNP vs time with a broken x-axis to close the 7-month measurement gap.

Produces the same scatter as plot_cnp_vs_time.py but splits the calendar
axis into two panels (Sep 2025 | Apr–Sep 2026) connected by diagonal break
marks, so the data fills the figure instead of wasting space on the gap.

Outputs (figs/cnp_time/):
    cnp_vs_time_74_75_broken.{pdf,png}
    cnp_vs_time_72_74_75_80_broken.{pdf,png}

Run from repo root:
    .venv/bin/python scripts/chip_history/plot_cnp_vs_time_broken.py
    .venv/bin/python scripts/chip_history/plot_cnp_vs_time_broken.py \
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
from matplotlib.axes import Axes

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_cnp_vs_time import (
    BASENAME,
    DEFAULT_CHIPS,
    EXCLUDE_MONTHS,
    EXCLUDE_SESSIONS,
    LEGEND_FONTSIZE_BUMP,
    MARKER_EDGE_WIDTH,
    MARKER_SIZE,
    MIN_CONFIDENCE,
    OUTPUT_DIR,
    ZERO_LINE_WIDTH,
    chip_specs,
    console,
    load_cnp,
    materials,
    print_summary,
)
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

BREAK_START = date(2025, 11, 1)
BREAK_END = date(2026, 4, 1)

LEFT_WEIGHT = 1.0
RIGHT_WEIGHT = 3.0


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


def _draw_break_marks(ax_left: Axes, ax_right: Axes, size: float = 0.015) -> None:
    """Draw diagonal break marks at the junction between the two panels."""
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


def draw_broken(ax_left, ax_right, rows, specs) -> None:
    for ax in (ax_left, ax_right):
        ax.axhline(0.0, color="0.6", lw=ZERO_LINE_WIDTH, ls="--", zorder=0)

    for spec in specs:
        sub = rows.filter(rows["chip_number"] == spec["chip"])
        if sub.height == 0:
            continue
        for ax in (ax_left, ax_right):
            ax.plot(
                sub["t_local"].to_list(),
                sub["cnp_v"].to_numpy(),
                ls="none",
                marker=spec["marker"],
                ms=MARKER_SIZE,
                color=spec["color"],
                mfc="none",
                mew=MARKER_EDGE_WIDTH,
                label=spec["label"] if ax is ax_left else None,
            )

    padding = timedelta(days=5)
    all_dates = sorted(set(rows["session_date"]))
    left_dates = [d for d in all_dates if d < BREAK_START]
    right_dates = [d for d in all_dates if d >= BREAK_END]

    if left_dates:
        ax_left.set_xlim(
            left_dates[0] - padding, left_dates[-1] + padding,
        )
    if right_dates:
        ax_right.set_xlim(
            right_dates[0] - padding, right_dates[-1] + padding,
        )

    for ax in (ax_left, ax_right):
        ax.margins(y=0.06)
        locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")

    ax_left.spines["right"].set_visible(False)
    ax_right.spines["left"].set_visible(False)
    ax_right.tick_params(left=False, labelleft=False)

    y0 = min(ax_left.get_ylim()[0], ax_right.get_ylim()[0])
    y1 = max(ax_left.get_ylim()[1], ax_right.get_ylim()[1])
    ax_left.set_ylim(y0, y1)
    ax_right.set_ylim(y0, y1)

    _draw_break_marks(ax_left, ax_right)

    ax_left.set_ylabel(r"$V_{CNP}$ (V)")
    fig = ax_left.get_figure()
    fig.text(0.5, 0.0, "Date", ha="center", va="bottom",
             fontsize=plt.rcParams["font.size"])
    ax_left.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--chips", type=str, default=",".join(str(c) for c in DEFAULT_CHIPS),
    )
    p.add_argument(
        "--marker-by", choices=("chip", "material"), default="chip",
    )
    p.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    p.add_argument("--include-light", action="store_true")
    p.add_argument("--keep-single-leg", action="store_true")
    p.add_argument("--exclude-month", action="append", default=None, metavar="YYYY-MM")
    p.add_argument("--exclude-session", action="append", default=None, metavar="CHIP:YYYY-MM-DD")
    p.add_argument("--all-history", action="store_true")
    p.add_argument("--ylim", type=float, nargs=2, metavar=("LO", "HI"), default=None)
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

    rows = load_cnp(
        chips, args.min_confidence, args.include_light,
        require_both_legs, exclude_months, exclude_sessions,
    )
    if rows.height == 0:
        raise SystemExit("no CNP points survived the filters")
    print_summary(rows, specs)

    config = PlotConfig(
        output_dir=OUTPUT_DIR,
        chip_subdir_enabled=False,
        use_proc_subdirs=False,
        auto_subcategories=False,
    )
    set_plot_style(config)

    height = float(config.figsize_timeseries[1])
    fig, (ax_l, ax_r) = plt.subplots(
        1, 2, sharey=True,
        figsize=(1.6 * height, height),
        gridspec_kw={"width_ratios": [LEFT_WEIGHT, RIGHT_WEIGHT], "wspace": 0.04},
    )
    draw_broken(ax_l, ax_r, rows, specs)
    if args.ylim is not None:
        ax_l.set_ylim(*args.ylim)
        ax_r.set_ylim(*args.ylim)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.18)

    stem = f"{BASENAME}_" + "_".join(str(c) for c in sorted(chips)) + "_broken"
    for name in (stem, f"{stem}.png"):
        out = config.get_output_path(name, create_dirs=True)
        fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
        print(f"saved {out}")
    plt.close(fig)


if __name__ == "__main__":
    main()
