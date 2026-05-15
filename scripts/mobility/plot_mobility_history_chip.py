"""Mobility evolution across the IVg history of a single chip.

Built primarily to visualize chip 79's gate degradation: the user
deliberately swept Vg out to ±20 V on early IVgs, which eventually
broke the gate dielectric. By plotting per-branch μ_FE versus the
chronological IVg index alongside the sweep range used in each
measurement, the slow degradation should become visible.

Usage:
    python3 scripts/plot_mobility_history_chip.py            # defaults to chip 79
    python3 scripts/plot_mobility_history_chip.py --chip 80
    python3 scripts/plot_mobility_history_chip.py --all      # one figure per chip
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.plotting.shared.styles import set_plot_style

METRICS_PARQUET = Path("data/03_derived/_metrics/metrics.parquet")
MANIFEST_PARQUET = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
OUTPUT_DIR = Path("figs/mobility/history")


def load_chip(chip: int) -> pl.DataFrame:
    """Return one row per (IVg, branch) for the chip, sorted chronologically.

    Columns: ivg_idx, start_time_utc, vg_max_abs (= max(|vg_start|,|vg_end|)),
             has_light, branch, mu_central, mu_min, mu_max, confidence, flags,
             quality_flags.
    """
    mdf = pl.read_parquet(METRICS_PARQUET)
    man = pl.read_parquet(MANIFEST_PARQUET)

    mob = (
        mdf.filter(
            (pl.col("chip_number") == chip)
            & (pl.col("metric_name").str.starts_with("mobility_fe_"))
        )
        .with_columns(
            pl.col("metric_name").str.replace("mobility_fe_", "").alias("branch")
        )
        .rename({"value_float": "mu_central"})
    )
    if mob.height == 0:
        raise SystemExit(f"No mobility metrics for chip {chip}.")

    # Pull min/max bounds out of value_json.
    import json
    extracted = [json.loads(s) for s in mob["value_json"].to_list()]
    mu_min = [e.get("mu_min") for e in extracted]
    mu_max = [e.get("mu_max") for e in extracted]
    mob = mob.with_columns(
        pl.Series("mu_min", mu_min),
        pl.Series("mu_max", mu_max),
    )

    man_sub = man.filter(
        (pl.col("chip_number") == chip) & (pl.col("proc") == "IVg")
    ).select(
        "run_id", "start_time_utc", "vg_start_v", "vg_end_v",
        "has_light", "quality_flags",
    )

    joined = mob.join(man_sub, on="run_id").sort(["start_time_utc", "branch"])
    joined = joined.with_columns(
        pl.max_horizontal(pl.col("vg_start_v").abs(), pl.col("vg_end_v").abs())
        .alias("vg_max_abs"),
    )

    # Chronological IVg index — one integer per *measurement*, shared by both
    # branches. Avoids exposing seq numbers (which may be sparse / non-contig).
    times = (
        joined.select("start_time_utc").unique(maintain_order=True)
        .with_row_index("ivg_idx")
    )
    joined = joined.join(times, on="start_time_utc")
    return joined


def plot_history(rows: pl.DataFrame, chip: int, out_path: Path) -> None:
    set_plot_style()
    plt.rcParams.update({
        "font.size": 10, "axes.labelsize": 11, "axes.titlesize": 11,
        "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
    })
    fig, (ax_mu, ax_vg) = plt.subplots(
        2, 1, figsize=(10, 6.5), sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.0]},
    )

    branch_color = {"holes": "tab:purple", "electrons": "tab:green"}
    for branch in ("holes", "electrons"):
        sub = rows.filter(pl.col("branch") == branch).sort("ivg_idx")
        if sub.height == 0:
            continue
        x = sub["ivg_idx"].to_numpy()
        mu = sub["mu_central"].to_numpy()
        mu_lo = sub["mu_min"].to_numpy()
        mu_hi = sub["mu_max"].to_numpy()
        light = sub["has_light"].to_numpy()
        c = branch_color[branch]

        # Min/max band as vertical bars (the parameter-range bound for each IVg).
        ax_mu.vlines(x, mu_lo, mu_hi, color=c, alpha=0.20, lw=2.0)
        # Connect central μ chronologically.
        ax_mu.plot(x, mu, "-", color=c, alpha=0.5, lw=1.0)
        # Dark = filled circle, light = open ×.
        ax_mu.plot(x[~light], mu[~light], "o", color=c, ms=5, mec="none",
                   label=fr"$\mu_{{\rm {branch[0]}}}$ (dark)")
        if light.any():
            ax_mu.plot(x[light], mu[light], "x", color=c, ms=6, mew=1.2,
                       label=fr"$\mu_{{\rm {branch[0]}}}$ (light)")

    ax_mu.set_yscale("log")
    ax_mu.set_ylabel(r"$\mu_{FE}$ (cm$^2$ V$^{-1}$ s$^{-1}$)")
    ax_mu.set_title(
        f"Chip {chip}: field-effect mobility across the IVg history"
    )
    ax_mu.legend(loc="best", ncol=2)

    # Gate-stress panel: max |Vg| applied in each sweep.
    vg_rows = rows.unique("ivg_idx", maintain_order=True).sort("ivg_idx")
    ax_vg.bar(
        vg_rows["ivg_idx"].to_numpy(),
        vg_rows["vg_max_abs"].to_numpy(),
        width=0.7, color="0.55", edgecolor="0.25",
    )
    ax_vg.set_ylabel(r"max $|V_g|$ (V)")
    ax_vg.set_xlabel("IVg index (chronological)")

    # Highlight transitions in max|Vg|: dashed verticals.
    vg_arr = vg_rows["vg_max_abs"].to_numpy()
    if vg_arr.size > 1:
        for i in range(1, len(vg_arr)):
            if vg_arr[i] != vg_arr[i - 1]:
                for ax in (ax_mu, ax_vg):
                    ax.axvline(i - 0.5, color="0.6", lw=0.6, ls=":", alpha=0.6)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _process_one(chip: int) -> Path:
    rows = load_chip(chip)
    out_path = OUTPUT_DIR / f"mobility_history_chip{chip}.png"
    plot_history(rows, chip, out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip", type=int, default=79)
    ap.add_argument("--all", action="store_true",
                    help="Generate one figure per chip in metrics.parquet")
    args = ap.parse_args()

    if args.all:
        mdf = pl.read_parquet(METRICS_PARQUET)
        chips = sorted(
            mdf.filter(pl.col("metric_name").str.starts_with("mobility_fe_"))
            ["chip_number"].unique().to_list()
        )
        print(f"Generating history figures for {len(chips)} chips...")
        for chip in chips:
            try:
                p = _process_one(chip)
                print(f"  chip {chip:>3}: {p}")
            except SystemExit as e:
                print(f"  chip {chip:>3}: skipped ({e})")
        return

    out_path = _process_one(args.chip)
    rows = load_chip(args.chip)
    grouped = (
        rows.group_by(["vg_max_abs", "branch"])
        .agg(
            pl.len().alias("n"),
            pl.col("mu_central").median().alias("mu_median"),
            pl.col("mu_central").min().alias("mu_min"),
            pl.col("mu_central").max().alias("mu_max"),
        )
        .sort(["vg_max_abs", "branch"])
    )
    print(f"Chip {args.chip} — mobility grouped by sweep range max|Vg|:")
    print(grouped)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
