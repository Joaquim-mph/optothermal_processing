"""Two diagnostic figures for the trapping-hypothesis investigation.

(1) Encap 74 — context-split of µ_back/µ_fwd vs hysteresis_v.

    For Encap 74 specifically, separate the looped IVgs by context:
      - date (encodes illumination history: 2026-04-21 had laser cycles)
      - has_light (illumination during the sweep itself; only 4 of 47)
    and fit slope+r within each (date, has_light) subset.

    Goal: reveal whether the "two clusters" in the simple correlation
    figure correspond to dark-baseline IVgs vs post-illumination IVgs.

(2) Cross-chip — µ-deficit (= 1 − median µ_back/µ_fwd) vs photoresponsivity
    (median |Δ_I_corrected|). Tests prediction #4 of the trapping note:
    chips with bigger responsivity should show bigger µ-deficit.

Outputs:
    figs/cross_chip/mobility_deficit_vs_hysteresis/
        Encap74_context_split.png
        deficit_vs_responsivity_cross_chip.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy import stats

METRICS = Path("data/03_derived/_metrics/metrics.parquet")
HIST_DIR = Path("data/03_derived/chip_histories_enriched")
OUTDIR = Path("figs/cross_chip/mobility_deficit_vs_hysteresis")

NEEDED_METRICS = [
    "cnp_forward",
    "cnp_backward",
    "mobility_fe_holes_forward",
    "mobility_fe_holes_backward",
    "mobility_fe_electrons_forward",
    "mobility_fe_electrons_backward",
]


# ── data ────────────────────────────────────────────────────────────────


def load_wide_with_context() -> pl.DataFrame:
    """Wide metrics joined with per-IVg history context (date, has_light, etc.)."""
    raw = pl.read_parquet(METRICS).filter(pl.col("metric_name").is_in(NEEDED_METRICS))
    wide = raw.pivot(
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
        (
            pl.col("mobility_fe_holes_backward") / pl.col("mobility_fe_holes_forward")
        ).alias("mu_ratio_h"),
        (
            pl.col("mobility_fe_electrons_backward")
            / pl.col("mobility_fe_electrons_forward")
        ).alias("mu_ratio_e"),
    )

    # Join in history context per chip.
    hist_pieces = []
    for path in sorted(HIST_DIR.glob("Alisson*_history.parquet")):
        h = (
            pl.read_parquet(path)
            .filter(pl.col("proc") == "IVg")
            .select(
                [
                    "run_id",
                    "date",
                    "has_light",
                    "wavelength_nm",
                    "laser_voltage_v",
                    "vds_v",
                    "vg_step_v",
                    "vg_start_v",
                    "vg_end_v",
                ]
            )
        )
        hist_pieces.append(h)
    history = pl.concat(hist_pieces, how="vertical_relaxed")
    return wide.join(history, on="run_id", how="left")


def chip_responsivity() -> dict[int, float]:
    raw = pl.read_parquet(METRICS).filter(pl.col("metric_name") == "delta_i_corrected")
    if raw.height == 0:
        return {}
    agg = raw.group_by("chip_number").agg(
        pl.col("value_float").abs().median().alias("med_abs_delta_i")
    )
    return {
        int(r["chip_number"]): float(r["med_abs_delta_i"])
        for r in agg.iter_rows(named=True)
        if r["med_abs_delta_i"] is not None
    }


# ── stats ───────────────────────────────────────────────────────────────


def linfit(x, y):
    mask = np.isfinite(x) & np.isfinite(y) & (y > 0) & (y < 10)
    if mask.sum() < 3:
        return None
    fit = stats.linregress(x[mask], y[mask])
    return {
        "n": int(mask.sum()),
        "slope": float(fit.slope),
        "intercept": float(fit.intercept),
        "r": float(fit.rvalue),
        "p": float(fit.pvalue),
        "x_min": float(x[mask].min()),
        "x_max": float(x[mask].max()),
    }


# ── (1) Encap 74 context split ──────────────────────────────────────────


def plot_encap74_context_split(wide: pl.DataFrame) -> None:
    df = wide.filter(pl.col("chip_number") == 74)
    df = df.filter(
        pl.col("cnp_forward").is_not_null() & pl.col("cnp_backward").is_not_null()
    )
    print(f"Encap 74 looped IVgs: {df.height}")
    dates = sorted(df["date"].unique().drop_nulls().to_list())
    print(f"  dates: {dates}")
    print(
        f"  has_light counts: {dict(df.group_by('has_light').agg(pl.len()).iter_rows())}"
    )

    fig, axes = plt.subplots(
        1, 2, figsize=(11.5, 4.8), constrained_layout=True, sharey=False
    )

    date_colors = {d: cm.tab10(i) for i, d in enumerate(dates)}
    light_marker = {True: "o", False: "s"}  # circle = light, square = dark

    for ax, (branch, col, title) in zip(
        axes,
        [
            ("holes", "mu_ratio_h", "Hole branch"),
            ("electrons", "mu_ratio_e", "Electron branch"),
        ],
    ):
        # Per-date scatter + per-date regression
        per_date_fits = {}
        for d in dates:
            sub = df.filter(pl.col("date") == d)
            x = sub["hysteresis_v"].to_numpy()
            y = sub[col].to_numpy()
            has_light = sub["has_light"].to_numpy()

            # Per-illum-state scatter, single date color, different marker.
            for state in (True, False):
                mask = has_light == state
                if not mask.any():
                    continue
                ax.scatter(
                    x[mask],
                    y[mask],
                    color=date_colors[d],
                    marker=light_marker[state],
                    s=36,
                    alpha=0.85,
                    edgecolor="black",
                    linewidth=0.5,
                    label=(
                        f"{d} {'light' if state else 'dark'}"
                        if state or sub.height >= 3
                        else None
                    ),
                )
            fit = linfit(x, y)
            per_date_fits[d] = fit
            if fit is not None and fit["n"] >= 3:
                xs = np.linspace(fit["x_min"], fit["x_max"], 100)
                ax.plot(
                    xs,
                    fit["intercept"] + fit["slope"] * xs,
                    color=date_colors[d],
                    lw=1.4,
                    alpha=0.9,
                    ls="-",
                )

        # Overall fit (gray dashed, for reference)
        overall = linfit(df["hysteresis_v"].to_numpy(), df[col].to_numpy())
        if overall is not None:
            xs = np.linspace(overall["x_min"], overall["x_max"], 100)
            ax.plot(
                xs,
                overall["intercept"] + overall["slope"] * xs,
                color="0.4",
                lw=1.0,
                ls="--",
                label=f"all (slope {overall['slope']:+.2f}, r={overall['r']:+.2f})",
            )

        # Annotate per-date slopes
        txt_lines = []
        for d, fit in per_date_fits.items():
            if fit is None or fit["n"] < 3:
                txt_lines.append(f"{d}: n={(fit['n'] if fit else 0)}")
            else:
                txt_lines.append(
                    f"{d}: n={fit['n']}, slope={fit['slope']:+.2f}, r={fit['r']:+.2f}"
                )
        ax.text(
            0.02,
            0.05,
            "\n".join(txt_lines),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", alpha=0.9),
        )

        ax.axhline(1.0, color="0.6", lw=0.8, ls="--")
        ax.axvline(0.0, color="0.6", lw=0.8, ls="--")
        ax.set_xlabel("hysteresis V$_g$ = CNP$_{back}$ − CNP$_{fwd}$ (V)")
        ax.set_title(title)
        ax.legend(loc="best", fontsize=7, framealpha=0.85, ncol=1)

    axes[0].set_ylabel("µ$_{back}$ / µ$_{fwd}$")
    fig.suptitle(
        "Encap 74 — µ_back/µ_fwd vs hysteresis, split by date (color) "
        "and illumination-during-sweep (marker)\n"
        "(circles = light on, squares = dark; constant V$_{ds}$, "
        "ΔV$_g$ step, range across all)",
        fontsize=10,
    )

    out = OUTDIR / "Encap74_context_split.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  wrote {out}")


# ── (2) Cross-chip deficit vs responsivity ──────────────────────────────


def plot_cross_chip_deficit_vs_responsivity(
    wide: pl.DataFrame,
    responsivity: dict[int, float],
    n_min: int = 5,
) -> None:
    looped = wide.filter(
        pl.col("cnp_forward").is_not_null() & pl.col("cnp_backward").is_not_null()
    )

    per_chip = []
    for chip in sorted(looped["chip_number"].unique().to_list()):
        sub = looped.filter(pl.col("chip_number") == chip)
        if sub.height < n_min:
            continue
        ratio_h = sub["mu_ratio_h"].drop_nulls().to_numpy()
        ratio_e = sub["mu_ratio_e"].drop_nulls().to_numpy()
        ratio_h = ratio_h[np.isfinite(ratio_h) & (ratio_h > 0) & (ratio_h < 10)]
        ratio_e = ratio_e[np.isfinite(ratio_e) & (ratio_e > 0) & (ratio_e < 10)]
        if ratio_h.size == 0 and ratio_e.size == 0:
            continue
        per_chip.append(
            {
                "chip": int(chip),
                "n": int(sub.height),
                "responsivity": responsivity.get(int(chip)),
                "deficit_h_med": float(1.0 - np.median(ratio_h))
                if ratio_h.size
                else None,
                "deficit_h_iqr_lo": float(1.0 - np.quantile(ratio_h, 0.75))
                if ratio_h.size
                else None,
                "deficit_h_iqr_hi": float(1.0 - np.quantile(ratio_h, 0.25))
                if ratio_h.size
                else None,
                "deficit_e_med": float(1.0 - np.median(ratio_e))
                if ratio_e.size
                else None,
                "deficit_e_iqr_lo": float(1.0 - np.quantile(ratio_e, 0.75))
                if ratio_e.size
                else None,
                "deficit_e_iqr_hi": float(1.0 - np.quantile(ratio_e, 0.25))
                if ratio_e.size
                else None,
            }
        )

    fig, axes = plt.subplots(
        1, 2, figsize=(11, 4.6), constrained_layout=True, sharey=True
    )

    for ax, (branch, key_med, lo, hi, title) in zip(
        axes,
        [
            (
                "holes",
                "deficit_h_med",
                "deficit_h_iqr_lo",
                "deficit_h_iqr_hi",
                "Hole branch",
            ),
            (
                "electrons",
                "deficit_e_med",
                "deficit_e_iqr_lo",
                "deficit_e_iqr_hi",
                "Electron branch",
            ),
        ],
    ):
        xs, ys, los, his, labels = [], [], [], [], []
        for r in per_chip:
            if r["responsivity"] is None or r[key_med] is None:
                continue
            xs.append(r["responsivity"])
            ys.append(r[key_med])
            los.append(r[lo])
            his.append(r[hi])
            labels.append((r["chip"], r["n"]))
        xs = np.array(xs)
        ys = np.array(ys)
        los = np.array(los)
        his = np.array(his)

        ax.errorbar(
            xs,
            ys,
            yerr=[ys - los, his - ys],
            fmt="none",
            ecolor="0.6",
            elinewidth=0.8,
            capsize=2,
        )
        ax.scatter(
            xs, ys, s=70, c="#1f77b4", edgecolor="black", linewidth=0.6, zorder=5
        )
        for (chip, n), x, y in zip(labels, xs, ys):
            ax.annotate(
                f" {chip}",
                (x, y),
                fontsize=9,
                color="0.2",
                xytext=(4, 0),
                textcoords="offset points",
            )

        # Linear fit on log10(responsivity) vs deficit
        log_x = np.log10(xs)
        fit = linfit(log_x, ys)
        if fit is not None:
            xfit = np.linspace(log_x.min(), log_x.max(), 100)
            ax.plot(
                10**xfit,
                fit["intercept"] + fit["slope"] * xfit,
                color="#d62728",
                lw=1.6,
                label=f"linear fit on log₁₀(resp)\n"
                f"slope={fit['slope']:+.2f}, "
                f"r={fit['r']:+.2f}, p={fit['p']:.2g}",
            )
            ax.legend(loc="upper left", fontsize=8)

        ax.axhline(0.0, color="0.6", lw=0.8, ls="--")
        ax.set_xscale("log")
        ax.set_xlabel("median |ΔI$_{corrected}$| (A)  —  photoresponsivity proxy")
        ax.set_title(f"{title} (median µ-deficit per chip, ± IQR)")
    axes[0].set_ylabel("1 − µ$_{back}$ / µ$_{fwd}$")

    fig.suptitle(
        "Cross-chip: mobility deficit vs photoresponsivity "
        f"(chips with ≥ {n_min} looped IVgs)",
        fontsize=11,
    )

    out = OUTDIR / "deficit_vs_responsivity_cross_chip.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  wrote {out}")

    # Console summary
    print()
    print(f"{'chip':>5} {'n':>4} {'resp':>10} {'def_h':>9} {'def_e':>9}")
    print("-" * 50)
    for r in per_chip:
        resp = f"{r['responsivity']:.2e}" if r["responsivity"] is not None else "—"
        dh = f"{r['deficit_h_med']:+.3f}" if r["deficit_h_med"] is not None else "—"
        de = f"{r['deficit_e_med']:+.3f}" if r["deficit_e_med"] is not None else "—"
        print(f"{r['chip']:>5} {r['n']:>4} {resp:>10} {dh:>9} {de:>9}")


# ── main ────────────────────────────────────────────────────────────────


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    wide = load_wide_with_context()
    responsivity = chip_responsivity()
    plot_encap74_context_split(wide)
    plot_cross_chip_deficit_vs_responsivity(wide, responsivity)


if __name__ == "__main__":
    main()
