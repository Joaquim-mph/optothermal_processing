"""Test of the trapping hypothesis — does µ_back/µ_fwd anti-correlate
with the IVg hysteresis voltage (cnp_backward − cnp_forward)?

For every looped IVg (one with both `cnp_forward` and `cnp_backward`),
this script computes:

    hysteresis_v = cnp_backward − cnp_forward
    mu_ratio_h   = mobility_fe_holes_backward / mobility_fe_holes_forward
    mu_ratio_e   = mobility_fe_electrons_backward / mobility_fe_electrons_forward

Within each chip with ≥ N_MIN looped IVgs, it fits a linear regression
of `mu_ratio` vs `hysteresis_v` per branch and reports slope, Pearson r,
p-value, and number of points. Two figures are produced:

  figs/cross_chip/mobility_deficit_vs_hysteresis/
      per_chip/Encap{N}_mobility_deficit_vs_hysteresis.png
      cross_chip_overlay.png

The cross-chip overlay draws one fitted line per chip colored by that
chip's median |delta_i_corrected| (photoresponsivity proxy). A monotonic
anti-correlation on the electron branch — concentrated on the
high-responsivity chips — supports the trapping picture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy import stats

METRICS = Path("data/03_derived/_metrics/metrics.parquet")
OUTDIR = Path("figs/cross_chip/mobility_deficit_vs_hysteresis")
N_MIN = 5  # min looped IVgs per chip to draw a per-chip plot or fit a slope

NEEDED_METRICS = [
    "cnp_forward", "cnp_backward",
    "mobility_fe_holes_forward", "mobility_fe_holes_backward",
    "mobility_fe_electrons_forward", "mobility_fe_electrons_backward",
]


# ── data ────────────────────────────────────────────────────────────────

def load_wide() -> pl.DataFrame:
    """One row per (run_id, chip) with the six required metrics pivoted
    into columns plus hysteresis_v and per-branch ratios."""
    raw = pl.read_parquet(METRICS)
    sub = raw.filter(pl.col("metric_name").is_in(NEEDED_METRICS))
    wide = sub.pivot(
        on="metric_name",
        index=["run_id", "chip_number", "chip_group", "seq_num"],
        values="value_float",
        aggregate_function="first",
    )

    for col in NEEDED_METRICS:
        if col not in wide.columns:
            wide = wide.with_columns(pl.lit(None).cast(pl.Float64).alias(col))

    wide = wide.with_columns(
        (pl.col("cnp_backward") - pl.col("cnp_forward")).alias("hysteresis_v"),
        (pl.col("mobility_fe_holes_backward")
         / pl.col("mobility_fe_holes_forward")).alias("mu_ratio_h"),
        (pl.col("mobility_fe_electrons_backward")
         / pl.col("mobility_fe_electrons_forward")).alias("mu_ratio_e"),
    )
    return wide


def chip_responsivity() -> dict[int, float]:
    """Median |delta_i_corrected| per chip — photoresponsivity proxy."""
    raw = pl.read_parquet(METRICS).filter(
        pl.col("metric_name") == "delta_i_corrected"
    )
    if raw.height == 0:
        return {}
    agg = raw.group_by("chip_number").agg(
        pl.col("value_float").abs().median().alias("med_abs_delta_i")
    )
    return {int(r["chip_number"]): float(r["med_abs_delta_i"])
            for r in agg.iter_rows(named=True)
            if r["med_abs_delta_i"] is not None}


# ── statistics ──────────────────────────────────────────────────────────

def fit_branch(df: pl.DataFrame, branch: str) -> Optional[dict]:
    """Linregress mu_ratio_{h,e} on hysteresis_v with NaN filtering."""
    col = "mu_ratio_h" if branch == "holes" else "mu_ratio_e"
    pts = df.select(["hysteresis_v", col]).drop_nulls()
    if pts.height < 3:
        return None
    x = pts["hysteresis_v"].to_numpy()
    y = pts[col].to_numpy()
    mask = np.isfinite(x) & np.isfinite(y) & (y > 0) & (y < 10)
    if mask.sum() < 3:
        return None
    x, y = x[mask], y[mask]
    fit = stats.linregress(x, y)
    return {
        "n": int(mask.sum()),
        "slope": float(fit.slope),
        "intercept": float(fit.intercept),
        "r": float(fit.rvalue),
        "p": float(fit.pvalue),
        "x_min": float(x.min()),
        "x_max": float(x.max()),
        "x": x, "y": y,
    }


# ── plotting ────────────────────────────────────────────────────────────

def _annotate(ax, fit: dict | None) -> None:
    if fit is None:
        ax.text(0.5, 0.5, "n < 3", ha="center", va="center",
                transform=ax.transAxes, fontsize=10, color="0.5")
        return
    txt = (f"n = {fit['n']}\n"
           f"slope = {fit['slope']:+.3f} V⁻¹\n"
           f"r = {fit['r']:+.3f}   p = {fit['p']:.2g}")
    ax.text(0.02, 0.05, txt, transform=ax.transAxes,
            ha="left", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", alpha=0.9))


def plot_per_chip(chip: int, df: pl.DataFrame, outdir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3),
                             constrained_layout=True, sharey=True)
    for ax, (branch, col, title) in zip(axes, [
        ("holes", "mu_ratio_h", "Hole branch"),
        ("electrons", "mu_ratio_e", "Electron branch"),
    ]):
        pts = df.select(["hysteresis_v", col]).drop_nulls()
        if pts.height:
            x = pts["hysteresis_v"].to_numpy()
            y = pts[col].to_numpy()
            ax.scatter(x, y, s=22, color="#1f77b4", alpha=0.75,
                       edgecolor="black", linewidth=0.4)
        fit = fit_branch(df, branch)
        if fit is not None:
            xs = np.linspace(fit["x_min"], fit["x_max"], 100)
            ax.plot(xs, fit["intercept"] + fit["slope"] * xs,
                    color="#d62728", lw=1.6,
                    label=f"linear fit (slope {fit['slope']:+.3f})")
            ax.legend(loc="upper right", fontsize=8)
        _annotate(ax, fit)

        ax.axhline(1.0, color="0.6", lw=0.8, ls="--")
        ax.axvline(0.0, color="0.6", lw=0.8, ls="--")
        ax.set_xlabel("hysteresis V$_g$ = CNP$_{back}$ − CNP$_{fwd}$ (V)")
        ax.set_title(title)
    axes[0].set_ylabel("µ$_{back}$ / µ$_{fwd}$")

    fig.suptitle(f"Encap{chip} — mobility-deficit vs hysteresis "
                 f"({df.height} looped IVgs)",
                 fontsize=11)

    out = outdir / f"Encap{chip}_mobility_deficit_vs_hysteresis.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  wrote {out}")


def plot_cross_chip(per_chip: dict[int, pl.DataFrame],
                    responsivity: dict[int, float], outdir: Path) -> None:
    chips = sorted(per_chip.keys())
    resps = np.array([responsivity.get(c, np.nan) for c in chips], float)
    if np.isfinite(resps).any():
        log_r = np.log10(np.where(resps > 0, resps, np.nan))
        norm = mcolors.Normalize(
            vmin=np.nanmin(log_r), vmax=np.nanmax(log_r),
        )
        cmap = cm.get_cmap("plasma")
        def color_for(c):
            r = responsivity.get(c)
            if r is None or r <= 0:
                return "0.5"
            return cmap(norm(np.log10(r)))
    else:
        norm = None
        cmap = None
        def color_for(_c):
            return "0.5"

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6),
                             constrained_layout=True, sharey=True)
    for ax, (branch, col, title) in zip(axes, [
        ("holes", "mu_ratio_h", "Hole branch"),
        ("electrons", "mu_ratio_e", "Electron branch"),
    ]):
        for c in chips:
            fit = fit_branch(per_chip[c], branch)
            if fit is None:
                continue
            xs = np.linspace(fit["x_min"], fit["x_max"], 100)
            ax.plot(xs, fit["intercept"] + fit["slope"] * xs,
                    color=color_for(c), lw=1.6, alpha=0.9,
                    label=f"{c} (r={fit['r']:+.2f}, n={fit['n']})")
            ax.scatter(fit["x"], fit["y"], s=10, alpha=0.35,
                       color=color_for(c), edgecolor="none")

        ax.axhline(1.0, color="0.6", lw=0.8, ls="--")
        ax.axvline(0.0, color="0.6", lw=0.8, ls="--")
        ax.set_xlabel("hysteresis V$_g$ = CNP$_{back}$ − CNP$_{fwd}$ (V)")
        ax.set_title(title)
        ax.legend(loc="best", fontsize=7, ncol=2, framealpha=0.85)
    axes[0].set_ylabel("µ$_{back}$ / µ$_{fwd}$")

    if norm is not None and cmap is not None:
        sm = cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=axes, shrink=0.85,
                            pad=0.02, location="right")
        cbar.set_label("log₁₀ median |ΔI$_{corrected}$| (A)", fontsize=9)

    fig.suptitle("Across-chip mobility deficit vs hysteresis "
                 "— colored by photoresponsivity", fontsize=11)
    out = outdir / "cross_chip_overlay.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  wrote {out}")


# ── main ────────────────────────────────────────────────────────────────

def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    wide = load_wide()
    responsivity = chip_responsivity()

    # Group per chip — only keep IVgs with both fwd+back CNPs (true loops).
    looped = wide.filter(
        pl.col("cnp_forward").is_not_null()
        & pl.col("cnp_backward").is_not_null()
    )

    print(f"Total looped IVgs (with both CNPs): {looped.height}")
    print(f"Chips with looped IVgs: "
          f"{looped['chip_number'].n_unique()}")
    print()
    print(f"{'chip':>5} {'n_loop':>7} {'resp':>10} | "
          f"{'h_slope':>9} {'h_r':>6} {'h_p':>8} | "
          f"{'e_slope':>9} {'e_r':>6} {'e_p':>8}")
    print("-" * 80)

    per_chip: dict[int, pl.DataFrame] = {}
    for chip in sorted(looped["chip_number"].unique().to_list()):
        df = looped.filter(pl.col("chip_number") == chip)
        if df.height < N_MIN:
            print(f"{chip:>5} {df.height:>7}  (skipped, n < {N_MIN})")
            continue
        per_chip[chip] = df
        h_fit = fit_branch(df, "holes")
        e_fit = fit_branch(df, "electrons")
        r = responsivity.get(chip)
        r_s = f"{r:>10.2e}" if r is not None else f"{'—':>10}"
        h_s = (f"{h_fit['slope']:>+9.3f} {h_fit['r']:>+6.2f} "
               f"{h_fit['p']:>8.2g}" if h_fit else f"{'—':>9} {'—':>6} {'—':>8}")
        e_s = (f"{e_fit['slope']:>+9.3f} {e_fit['r']:>+6.2f} "
               f"{e_fit['p']:>8.2g}" if e_fit else f"{'—':>9} {'—':>6} {'—':>8}")
        print(f"{chip:>5} {df.height:>7} {r_s} | {h_s} | {e_s}")
        plot_per_chip(chip, df, OUTDIR / "per_chip")

    if per_chip:
        print()
        plot_cross_chip(per_chip, responsivity, OUTDIR)
    else:
        print("\n(No chips with ≥ N_MIN looped IVgs.)")


if __name__ == "__main__":
    main()
