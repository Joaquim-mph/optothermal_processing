"""Mean CNP versus calendar time (whole measurement history), any chip set.

Goal
----
Show how the charge-neutrality point drifts across a chip's entire lab life --
roughly one year -- on a true calendar axis. Every usable dark IVg sweep
contributes one marker; no lines are drawn, because consecutive sweeps are often
minutes apart inside a session and days-to-months apart between sessions, so a
connecting line would imply a continuity the data does not have.

Two figures are produced by the two documented invocations below:
  * the biotite pair 74 / 75 (default), and
  * the four-chip hBN-vs-biotite comparison 72 / 74 / 75 / 80, where marker
    shape encodes the bottom dielectric (circle = hBN, square = biotite) and
    colour the individual chip.

Method
------
The plotted quantity is the stored ``cnp_voltage`` metric, which already *is* the
mean CNP of a sweep: ``CNPExtractor(direction="average")`` records
``0.5 * (cnp_forward + cnp_backward)``, the hysteresis midpoint of the two
full-range legs of a looped sweep (see src/derived/extractors/cnp_extractor.py).
No further averaging across sweeps is applied -- one marker per IVg.

Rows are read from the derived metrics table and joined to the staging manifest
on ``run_id`` for the measurement timestamp and the illumination flag. The
metrics table is used rather than the enriched chip history because only it
carries the ``confidence`` column and the ``value_json`` fit details. Timestamps
are converted from UTC to America/Santiago wall time (the lab timezone).

Filters (all defeasible from the command line)
----------------------------------------------
* dark sweeps only (``~has_light``);
* ``confidence >= 0.5``;
* **complete sweeps only** -- ``n_complete_legs == 2``. A single-leg sweep is a
  partial transfer curve that never turned around, so its ``cnp_voltage`` is not
  the mean of anything: the extractor falls back to the one leg it has. These
  produce every volt-scale excursion in the record and are not comparable with
  the rest. The worst offender is chip 74 on 2026-05-25 18:11:42
  (run 00d3136fc06a8536): 129 points over Vg in [-5, 0] that never reach
  positive gate, giving a "CNP" of -4.200 V, while the six full 601-point
  [-5, +5] sweeps taken in the same session over the next two hours read -1.84
  to -1.11 V. Chip 75's -4.64 / -4.33 V points on 2026-08-28 are the same
  failure. ``--keep-single-leg`` puts them back.
* **August 2026 excluded** (``EXCLUDE_MONTHS``) -- drops the 2026-08-28 session.
  ``--exclude-month`` overrides the list; ``--all-history`` clears it.

September 2025 is kept, so the default figure spans 2025-09-08 -> 2026-07-08 on
both chips. There is a genuine ~7-month gap (2025-09-15 -> 2026-04-16) in which
neither chip was measured; a true calendar axis necessarily shows it as empty
space.

Inputs
------
    data/03_derived/_metrics/metrics.parquet
    data/02_stage/raw_measurements/_manifest/manifest.parquet
    config/encap_characteristics.yaml   (material tags for the legend)

Outputs (in figs/cnp_time/)
---------------------------
The file stem is built from the chip list, so each chip set gets its own files:
    cnp_vs_time_74_75.{pdf,png,csv}
    cnp_vs_time_72_74_75_80.{pdf,png,csv}
Non-default runs add to the stem (``_all_history``, ``_zoom``) so they never
overwrite the figures above.

Run from repo root:
    .venv/bin/python scripts/chip_history/plot_cnp_vs_time.py
    .venv/bin/python scripts/chip_history/plot_cnp_vs_time.py \\
        --chips 72,74,75,80 --marker-by material
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import polars as pl
import yaml
from matplotlib.axes import Axes
from rich.console import Console
from rich.table import Table

from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

METRICS_PARQUET = Path("data/03_derived/_metrics/metrics.parquet")
MANIFEST_PARQUET = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
ENCAP_YAML = Path("config/encap_characteristics.yaml")
OUTPUT_DIR = Path("figs/cnp_time")
BASENAME = "cnp_vs_time"

DEFAULT_CHIPS = (74, 75)

# Colour is assigned by position in the chip list, so a given chip set always
# renders the same way and adding a chip never recolours another figure.
# Marker shape is either per-chip (the default, for a set that shares one
# dielectric) or per-material via --marker-by material.
CHIP_MARKERS = ("o", "s", "^", "D", "v", "P")
MATERIAL_MARKERS = {"hBN": "o", "biotite": "s"}

MIN_CONFIDENCE = 0.5

# Sessions dropped wholesale, as "YYYY-MM". 2026-08 is chip 75's 2026-08-28
# session, excluded by request.
EXCLUDE_MONTHS = ("2026-08",)

# Individual (chip, date) sessions dropped because the *device*, not the fit,
# misbehaved -- these pass every structural check, so nothing else catches them.
#   (74, 2026-05-25): 7 sweeps (6 full + 1 partial) with CNP shifted to
#     -1.84 .. -1.11 V, drifting back toward zero over the session. Both chips
#     73 and 74 were measured that day and both showed anomalous negative
#     doping that later recovered -- likely a transient environmental artifact.
#   (80, 2025-10-10): 3 sweeps whose gate modulation collapsed to on/off 2.33
#     against 4.69-5.02 in every other chip-80 session at the same Vds, with
#     I(0 V) doubled (76 uA vs 26-45) and I_max down to 92 uA (vs 119-126).
#     The parabola fits are clean -- 601 points, both legs, confidence 1.0,
#     forward/backward within 0.03 V -- so they report a CNP of -3.6 to -4.0 V
#     with full confidence. The flanking sessions bracket and agree with each
#     other (10-09 ends -0.39 V, 10-13 starts -0.23 V), so a -3.5 V excursion
#     that fully recovers in three days is not credible.
# Note the test has to be per chip: chip 72 runs at on/off ~2.8 throughout, so
# an absolute modulation threshold would wrongly delete all of it.
EXCLUDE_SESSIONS = ((80, "2025-10-10"), (74, "2026-05-25"))

LOCAL_TZ = "America/Santiago"

# Sized against the theme (font.size 35, lines.markersize 22): open markers a
# little under the theme default, so the dense within-session clusters stay
# resolvable rather than merging into a blob.
MARKER_SIZE = 14.0
MARKER_EDGE_WIDTH = 2.5
ZERO_LINE_WIDTH = 2.0
LEGEND_FONTSIZE_BUMP = 2.0

console = Console()


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


def materials() -> dict[int, str]:
    """Bottom-dielectric tag per chip from config/encap_characteristics.yaml."""
    with ENCAP_YAML.open() as f:
        data = yaml.safe_load(f)
    return {
        int(k): (v or {}).get("material")
        for k, v in data.items()
        if isinstance(k, int)
    }


def label_for_chip(chip: int, material: dict[int, str]) -> str:
    """Legend label in the house style: ``74 (biotite)``."""
    mat = material.get(chip)
    if mat is None:
        console.print(
            f"[yellow][warn][/yellow] chip {chip}: no material in "
            f"{ENCAP_YAML}; labelling without a tag"
        )
        return str(chip)
    return f"{chip} ({mat})"


def chip_specs(
    chips: list[int], material: dict[int, str], marker_by: str
) -> list[dict]:
    """Per-chip colour / marker / label, in the order the chips were given."""
    specs = []
    for idx, chip in enumerate(chips):
        if marker_by == "material":
            mat = material.get(chip)
            marker = MATERIAL_MARKERS.get(mat)
            if marker is None:
                console.print(
                    f"[yellow][warn][/yellow] chip {chip}: material {mat!r} has no "
                    "marker; falling back to the per-chip cycle"
                )
                marker = CHIP_MARKERS[idx % len(CHIP_MARKERS)]
        else:
            marker = CHIP_MARKERS[idx % len(CHIP_MARKERS)]
        specs.append({
            "chip": chip,
            "color": f"C{idx}",
            "marker": marker,
            "label": label_for_chip(chip, material),
        })
    return specs


def _n_complete_legs(payload: str | None) -> int | None:
    """Legs used by the CNP fit, from the metric's value_json blob."""
    if not payload:
        return None
    return json.loads(payload).get("n_complete_legs")


def load_cnp(
    chips: list[int],
    min_confidence: float,
    include_light: bool,
    require_both_legs: bool,
    exclude_months: tuple[str, ...],
    exclude_sessions: tuple[tuple[int, str], ...],
) -> pl.DataFrame:
    """One row per surviving IVg sweep: chip, local timestamp, mean CNP."""
    metrics = pl.read_parquet(METRICS_PARQUET).filter(
        (pl.col("metric_name") == "cnp_voltage")
        & (pl.col("chip_number").is_in(chips))
        & (pl.col("value_float").is_not_null())
        & (pl.col("value_float").is_not_nan())
    )
    manifest = pl.read_parquet(MANIFEST_PARQUET).with_columns(
        pl.col("start_time_utc")
        .str.to_datetime(
            format="%Y-%m-%d %H:%M:%S%.f%z", strict=False, time_zone="UTC"
        )
        .alias("t_utc")
    )

    rows = metrics.join(
        manifest.select(["run_id", "t_utc", "has_light"]), on="run_id", how="inner"
    ).with_columns(
        pl.col("value_json")
        .map_elements(_n_complete_legs, return_dtype=pl.Int64)
        .alias("n_complete_legs")
    )

    if not include_light:
        rows = rows.filter(~pl.col("has_light"))
    rows = rows.filter(pl.col("confidence") >= min_confidence)
    if require_both_legs:
        # Single-leg sweeps never turned around: cnp_voltage is then the one
        # available leg, not a forward/backward mean. See the module docstring.
        rows = rows.filter(pl.col("n_complete_legs") == 2)

    rows = rows.with_columns(
        pl.col("t_utc").dt.convert_time_zone(LOCAL_TZ).alias("t_local")
    ).with_columns(
        pl.col("t_local").dt.date().alias("session_date"),
        pl.col("t_local").dt.strftime("%Y-%m").alias("session_month"),
    )
    if exclude_months:
        rows = rows.filter(~pl.col("session_month").is_in(list(exclude_months)))
    for chip, day in exclude_sessions:
        hit = rows.filter(
            (pl.col("chip_number") == chip)
            & (pl.col("session_date").cast(pl.Utf8) == day)
        ).height
        if hit:
            console.print(
                f"[yellow][drop][/yellow] chip {chip} {day}: {hit} sweeps "
                "(session excluded, see EXCLUDE_SESSIONS)"
            )
        rows = rows.filter(
            ~(
                (pl.col("chip_number") == chip)
                & (pl.col("session_date").cast(pl.Utf8) == day)
            )
        )

    return (
        rows.rename({"value_float": "cnp_v"})
        .select(
            [
                "chip_number",
                "run_id",
                "t_local",
                "session_date",
                "cnp_v",
                "confidence",
                "n_complete_legs",
                "has_light",
                "flags",
            ]
        )
        .sort(["chip_number", "t_local"])
    )


def print_summary(rows: pl.DataFrame, specs: list[dict]) -> None:
    t = Table(title="Mean CNP per IVg sweep")
    for col in (
        "chip", "material", "markers", "sessions", "span (d)",
        "first (V)", "last (V)", "min (V)", "max (V)",
    ):
        t.add_column(col, justify="left" if col == "material" else "right")

    for spec in specs:
        sub = rows.filter(pl.col("chip_number") == spec["chip"])
        if sub.height == 0:
            continue
        span = (sub["t_local"].max() - sub["t_local"].min()).total_seconds() / 86400.0
        t.add_row(
            str(spec["chip"]),
            spec["label"].partition("(")[2].rstrip(")") or "?",
            str(sub.height),
            str(sub["session_date"].n_unique()),
            f"{span:.0f}",
            f"{sub['cnp_v'][0]:+.3f}",
            f"{sub['cnp_v'][-1]:+.3f}",
            f"{sub['cnp_v'].min():+.3f}",
            f"{sub['cnp_v'].max():+.3f}",
        )
    console.print(t)


def draw(ax: Axes, rows: pl.DataFrame, specs: list[dict]) -> None:
    # CNP = 0 reference, behind the data.
    ax.axhline(0.0, color="0.6", lw=ZERO_LINE_WIDTH, ls="--", zorder=0)

    for spec in specs:
        sub = rows.filter(pl.col("chip_number") == spec["chip"])
        if sub.height == 0:
            console.print(f"[yellow][warn][/yellow] chip {spec['chip']}: no points")
            continue
        ax.plot(
            sub["t_local"].to_list(),
            sub["cnp_v"].to_numpy(),
            ls="none",
            marker=spec["marker"],
            ms=MARKER_SIZE,
            color=spec["color"],
            mfc="none",
            mew=MARKER_EDGE_WIDTH,
            label=spec["label"],
        )

    # Keep the first and last sessions off the spines.
    ax.margins(x=0.04, y=0.06)

    locator = mdates.AutoDateLocator(minticks=5, maxticks=9)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")

    # ConciseDateFormatter parks its offset ("2026-Sep") in the bottom-right
    # corner, where it collides with the axis label. When every session falls in
    # one calendar year the year belongs in the label instead.
    years = sorted({d.year for d in rows["session_date"]})
    if len(years) == 1:
        formatter.show_offset = False
        ax.set_xlabel(f"Date ({years[0]})")
    else:
        ax.set_xlabel("Date")

    ax.set_ylabel(r"$V_{CNP}$ (V)")
    ax.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument(
        "--chips", type=str, default=",".join(str(c) for c in DEFAULT_CHIPS),
        help="comma-separated chip numbers, in plot order "
             f"(default {','.join(str(c) for c in DEFAULT_CHIPS)})",
    )
    p.add_argument(
        "--marker-by", choices=("chip", "material"), default="chip",
        help="marker shape encodes the chip (default) or the bottom dielectric "
             "(circle = hBN, square = biotite) -- use 'material' for mixed sets",
    )
    p.add_argument(
        "--min-confidence", type=float, default=MIN_CONFIDENCE,
        help=f"drop CNP fits below this confidence (default {MIN_CONFIDENCE})",
    )
    p.add_argument(
        "--include-light", action="store_true",
        help="also plot illuminated IVgs (only a handful exist)",
    )
    p.add_argument(
        "--keep-single-leg", action="store_true",
        help="keep partial sweeps whose CNP comes from one leg only "
             "(these are the volt-scale excursions; excluded by default)",
    )
    p.add_argument(
        "--exclude-month", action="append", default=None, metavar="YYYY-MM",
        help=f"drop a whole month, repeatable (default {' '.join(EXCLUDE_MONTHS)})",
    )
    p.add_argument(
        "--exclude-session", action="append", default=None, metavar="CHIP:YYYY-MM-DD",
        help="drop one chip's session, repeatable (default "
             + " ".join(f"{c}:{d}" for c, d in EXCLUDE_SESSIONS) + ")",
    )
    p.add_argument(
        "--all-history", action="store_true",
        help="no month/session exclusions and no completeness filter",
    )
    p.add_argument(
        "--ylim", type=float, nargs=2, metavar=("LO", "HI"), default=None,
        help="clamp the CNP axis, e.g. --ylim -1 0.6",
    )
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
        chips,
        args.min_confidence,
        args.include_light,
        require_both_legs,
        exclude_months,
        exclude_sessions,
    )
    if rows.height == 0:
        raise SystemExit("no CNP points survived the filters")

    console.print(
        f"filters: dark={not args.include_light} "
        f"confidence>={args.min_confidence} "
        f"both_legs={require_both_legs} "
        f"excluded_months={list(exclude_months) or 'none'} "
        f"excluded_sessions="
        f"{[f'{c}:{d}' for c, d in exclude_sessions] or 'none'}"
    )
    print_summary(rows, specs)

    config = PlotConfig(
        output_dir=OUTPUT_DIR,
        chip_subdir_enabled=False,
        use_proc_subdirs=False,
        auto_subcategories=False,
    )
    set_plot_style(config)

    # A year of dates needs a wider box than the square timeseries default.
    height = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(1.6 * height, height))
    draw(ax, rows, specs)
    if args.ylim is not None:
        ax.set_ylim(*args.ylim)
    fig.tight_layout()

    # The chip set owns the stem, so each set gets its own files; non-default
    # runs add a further suffix and never clobber the standard figures.
    stem = f"{BASENAME}_" + "_".join(str(c) for c in sorted(chips))
    if args.all_history:
        stem = f"{stem}_all_history"
    if args.ylim is not None:
        stem = f"{stem}_zoom"
    for name in (stem, f"{stem}.png"):
        out = config.get_output_path(name, create_dirs=True)
        fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
        print(f"saved {out}")
    plt.close(fig)

    csv_out = config.get_output_path(f"{stem}.csv", create_dirs=True)
    rows.write_csv(csv_out)
    print(f"saved {csv_out}")


if __name__ == "__main__":
    main()
