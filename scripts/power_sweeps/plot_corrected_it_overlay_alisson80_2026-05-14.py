"""
Drift-corrected I(t) overlay for Alisson80 at 365 nm, 2026-05-14, Vg = -1.2 V.

Seqs 147-150, powers 6, 12, 18, 24 µW.

Stretched-exponential drift fit on t in [FIT_T_START, FIT_T_END] is subtracted
from each trace, then the corrected trace is anchored to zero at t = EVAL_T_PRE.
Traces are overlaid on a single axis colored by power (plasma_r), with the
light window shaded between EVAL_T_PRE and EVAL_T_POST. Format mirrors the
inset from plot_photoresponse_vs_power_loglog_alisson75_two_dates.py.

Run from repo root:
    python scripts/power_sweeps/plot_corrected_it_overlay_alisson80_2026-05-14.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

CHIP = 80
DATE = "2026-05-14"
SEQS = [147, 148, 149, 150]
VG = -1.2
WAVELENGTH_NM = 365.0

FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0


def rows_for_chip(hist: pl.DataFrame) -> pl.DataFrame:
    return hist.filter(
        pl.col("seq").is_in(SEQS),
        pl.col("date") == DATE,
        pl.col("proc") == "It",
        pl.col("has_light"),
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")


def corrected_trace(t: np.ndarray, I: np.ndarray) -> np.ndarray:
    mask = (t >= FIT_T_START) & (t <= FIT_T_END)
    if mask.sum() >= 10:
        fit = fit_stretched_exponential(t[mask], I[mask])
        drift = stretched_exponential(
            t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
        )
        I_corr = I - drift
    else:
        I_corr = I.copy()
    idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
    return I_corr - I_corr[idx_pre]


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    hist = pl.read_parquet(
        Path(f"data/03_derived/chip_histories_enriched/Alisson{CHIP}_history.parquet")
    )
    rows = rows_for_chip(hist)
    print(rows.select(["seq", "vg_fixed_v", "irradiated_power_w", "wavelength_nm"]))
    if rows.height == 0:
        print("[warn] no matching rows")
        return

    fig, ax = plt.subplots(figsize=(20, 20))
    n = rows.height
    cmap = mpl.colormaps["plasma_r"]
    cmap_levels = np.linspace(0.15, 1.0, max(1, n))

    seg_t: list[np.ndarray] = []
    seg_I_corr_uA: list[np.ndarray] = []
    powers_uW: list[float] = []

    for i, row in enumerate(rows.iter_rows(named=True)):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size == 0:
            continue

        I_corr_uA = corrected_trace(t, I) * 1e6
        p_uW = float(row["irradiated_power_w"]) * 1e6

        ax.plot(
            t,
            I_corr_uA,
            color=cmap(cmap_levels[i]),
            linewidth=2.0,
            label=f"{p_uW:.0f} µW",
        )
        seg_t.append(t)
        seg_I_corr_uA.append(I_corr_uA)
        powers_uW.append(p_uW)

    ax.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha)
    ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)

    # x range and ticks match the inset style
    x_lo = 50.0
    t_totals = [float(t[-1]) for t in seg_t]
    x_hi = float(np.median(t_totals)) if t_totals else None
    if x_hi is not None and np.isfinite(x_hi) and x_hi > x_lo:
        ax.set_xlim(x_lo, x_hi)
    ax.set_xticks([60, 120, 180])

    # y autoscale to visible window
    visible_y: list[float] = []
    for t, y in zip(seg_t, seg_I_corr_uA):
        m = t >= x_lo
        if x_hi is not None:
            m &= t <= x_hi
        visible_y.extend(y[m].tolist())
    if visible_y:
        y = np.array(visible_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")

    y_lo, y_hi = ax.get_ylim()
    arrow_top = y_hi - 0.10 * (y_hi - y_lo)
    arrow_bot = y_lo + 0.10 * (y_hi - y_lo)
    ax.annotate(
        "",
        xy=(90, arrow_bot),
        xytext=(90, arrow_top),
        arrowprops=dict(arrowstyle="->", color="k", lw=1.5),
    )
    ax.text(
        92,
        0.5 * (arrow_top + arrow_bot),
        "P",
        va="center",
        ha="left",
        fontsize="medium",
    )

    ax.legend(loc="best", framealpha=0.9, title=f"$V_g={VG:g}$ V")
    plt.tight_layout()

    seq_tag = "_".join(str(s) for s in SEQS)
    filename = f"Alisson{CHIP}_It_corrected_overlay_seq_{seq_tag}_{DATE}_365nm"
    out = config.get_output_path(
        filename,
        chip_number=CHIP,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
