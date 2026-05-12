"""Per-chip distribution of field-effect mobility across all IVg sweeps.

Pulls every `mobility_fe_holes` / `mobility_fe_electrons` row from
`data/03_derived/_metrics/metrics.parquet`, filters out low-confidence rows
(heavily saturated sweeps), and plots the spread per chip so you can see
how much μ moves around for the same device across its measurement history.

Run from repo root: `python3 scripts/plot_mobility_distribution.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.patches import Patch
from rich.console import Console
from rich.table import Table

from src.plotting.styles import set_plot_style

METRICS_PARQUET = Path("data/03_derived/_metrics/metrics.parquet")
OUTPUT_DIR = Path("figs/mobility")

# Drop rows whose extractor confidence is not strictly above this — that
# excludes both heavily-saturated sweeps and the `MU_IN_RANGE` rows
# (always land at exactly 0.5), which would otherwise pull medians off.
MIN_CONFIDENCE = 0.5

# Colors per bottom dielectric (matches scripts/estimate_mobility.py).
COLOR_BY_MATERIAL = {"hBN": "tab:blue", "biotite": "tab:orange"}
DARK_MARKER = "o"
LIGHT_MARKER = "x"

console = Console()


def load_mobility_rows() -> pl.DataFrame:
    """Return tidy rows: one per measurement × branch.

    Columns: chip_number, branch, mu_central, mu_min, mu_max, has_light,
             saturation_fraction, bottom_material, confidence, flags, seq_num.
    """
    df = pl.read_parquet(METRICS_PARQUET)
    mob = df.filter(pl.col("metric_name").str.starts_with("mobility_fe_"))
    if mob.height == 0:
        raise SystemExit("No mobility metrics found — run `biotite derive-all-metrics` first.")

    def _unpack(value_json: str) -> dict:
        d = json.loads(value_json)
        return {
            "mu_min": d.get("mu_min"),
            "mu_max": d.get("mu_max"),
            "has_light": d.get("has_light", False),
            "saturation_fraction": d.get("saturation_fraction"),
            "bottom_material": d.get("geometry", {}).get("bottom_material"),
        }

    extracted = [_unpack(s) for s in mob["value_json"].to_list()]
    extras = pl.DataFrame(extracted)
    return (
        mob.with_columns(
            pl.col("metric_name").str.replace("mobility_fe_", "").alias("branch")
        )
        .rename({"value_float": "mu_central"})
        .hstack(extras)
        .select(
            "chip_number", "seq_num", "branch", "mu_central",
            "mu_min", "mu_max", "has_light", "saturation_fraction",
            "bottom_material", "confidence", "flags",
        )
    )


def per_chip_stats(rows: pl.DataFrame) -> pl.DataFrame:
    """Summary stats per (chip, branch)."""
    return (
        rows.group_by(["chip_number", "bottom_material", "branch"])
        .agg(
            pl.len().alias("n"),
            pl.col("mu_central").median().alias("mu_median"),
            pl.col("mu_central").quantile(0.16).alias("mu_p16"),
            pl.col("mu_central").quantile(0.84).alias("mu_p84"),
            pl.col("mu_central").min().alias("mu_min_obs"),
            pl.col("mu_central").max().alias("mu_max_obs"),
            (pl.col("mu_central").std() / pl.col("mu_central").mean()).alias("cv"),
            pl.col("has_light").sum().alias("n_light"),
        )
        .sort(["bottom_material", "chip_number", "branch"])
    )


def print_summary(stats: pl.DataFrame) -> None:
    t = Table(title=(
        "Per-chip mobility spread "
        f"(rows with confidence > {MIN_CONFIDENCE} only; "
        f"central μ from MobilityExtractor)"
    ))
    t.add_column("chip", justify="right")
    t.add_column("mat")
    t.add_column("branch")
    t.add_column("n", justify="right")
    t.add_column("light", justify="right")
    t.add_column("median μ", justify="right")
    t.add_column("p16–p84", justify="right")
    t.add_column("min–max", justify="right")
    t.add_column("CV", justify="right")
    for r in stats.iter_rows(named=True):
        cv = r["cv"]
        cv_s = f"{cv:.2f}" if cv is not None and np.isfinite(cv) else "—"
        t.add_row(
            str(r["chip_number"]),
            r["bottom_material"] or "?",
            r["branch"],
            str(r["n"]),
            str(r["n_light"]),
            f"{r['mu_median']:,.0f}",
            f"{r['mu_p16']:,.0f}–{r['mu_p84']:,.0f}",
            f"{r['mu_min_obs']:,.0f}–{r['mu_max_obs']:,.0f}",
            cv_s,
        )
    console.print(t)


def plot_distributions(rows: pl.DataFrame, stats: pl.DataFrame, path: Path) -> None:
    """Two stacked panels: μ_h and μ_e. One marker column per chip; box + scatter."""
    set_plot_style()
    plt.rcParams.update({
        "font.size": 10, "axes.labelsize": 11, "axes.titlesize": 11,
        "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 8,
    })
    # Ordering: by material, then chip number.
    chip_order = (
        stats.select(["chip_number", "bottom_material"])
        .unique().sort(["bottom_material", "chip_number"])
    )
    chips = chip_order["chip_number"].to_list()
    mats = chip_order["bottom_material"].to_list()

    fig, axes = plt.subplots(2, 1, figsize=(max(8.0, 0.45 * len(chips) + 4), 8.0), sharex=True)
    branches = ["holes", "electrons"]
    titles = [r"Hole-branch mobility $\mu_h$ per chip",
              r"Electron-branch mobility $\mu_e$ per chip"]

    for ax, branch, title in zip(axes, branches, titles):
        for i, (chip, mat) in enumerate(zip(chips, mats)):
            sub = rows.filter((pl.col("chip_number") == chip) & (pl.col("branch") == branch))
            if sub.height == 0:
                continue
            mu = sub["mu_central"].to_numpy()
            light = sub["has_light"].to_numpy()
            c = COLOR_BY_MATERIAL.get(mat, "0.4")

            # Box: p16 / median / p84 + min/max whiskers.
            stat = stats.filter(
                (pl.col("chip_number") == chip) & (pl.col("branch") == branch)
            ).row(0, named=True)
            ax.vlines(i, stat["mu_min_obs"], stat["mu_max_obs"],
                      color=c, lw=1.0, alpha=0.5)
            ax.vlines(i, stat["mu_p16"], stat["mu_p84"], color=c, lw=4.0, alpha=0.55)
            ax.plot(i, stat["mu_median"], "_", color="k", ms=14, mew=1.6)

            # Jittered scatter on top.
            rng = np.random.default_rng(chip)
            jit = rng.uniform(-0.15, 0.15, size=mu.size)
            ax.plot(i + jit[~light], mu[~light], DARK_MARKER, color=c,
                    ms=4, alpha=0.7, mec="none")
            ax.plot(i + jit[light], mu[light], LIGHT_MARKER, color=c,
                    ms=5, alpha=0.85, mew=1.2)

        ax.set_yscale("log")
        ax.set_ylabel(r"$\mu_{FE}$ (cm$^2$ V$^{-1}$ s$^{-1}$)")
        ax.set_title(title)

    axes[-1].set_xticks(range(len(chips)))
    axes[-1].set_xticklabels([str(c) for c in chips])
    axes[-1].set_xlabel("chip")

    legend = [
        Patch(facecolor="tab:blue", label="bottom = hBN"),
        Patch(facecolor="tab:orange", label="bottom = biotite"),
        plt.Line2D([0], [0], marker=DARK_MARKER, color="0.3", lw=0, ms=5, label="dark IVg"),
        plt.Line2D([0], [0], marker=LIGHT_MARKER, color="0.3", lw=0, ms=6, mew=1.2,
                   label="light IVg"),
        plt.Line2D([0], [0], marker="_", color="k", lw=0, ms=14, mew=1.6, label="median"),
        plt.Line2D([0], [0], color="0.3", lw=4, alpha=0.55, label="p16–p84"),
        plt.Line2D([0], [0], color="0.3", lw=1, alpha=0.5, label="min–max"),
    ]
    axes[0].legend(handles=legend, loc="best", ncol=2, fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    rows = load_mobility_rows()
    n_all = rows.height
    rows = rows.filter(pl.col("confidence") > MIN_CONFIDENCE)
    n_kept = rows.height
    console.print(
        f"Loaded {n_all} mobility rows; kept {n_kept} after "
        f"confidence > {MIN_CONFIDENCE} filter."
    )

    stats = per_chip_stats(rows)
    print_summary(stats)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "mobility_distribution.csv"
    fig_path = OUTPUT_DIR / "mobility_distribution.png"
    stats.write_csv(csv_path)
    plot_distributions(rows, stats, fig_path)
    console.print(f"\nWrote {csv_path}")
    console.print(f"Wrote {fig_path}")


if __name__ == "__main__":
    main()
