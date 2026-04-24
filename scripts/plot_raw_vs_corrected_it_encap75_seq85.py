"""
Raw vs drift-corrected I(t) for Encap75, seq 85.

Fits a stretched exponential on t in [FIT_T_START, FIT_T_END] s of the raw
trace (pre-illumination drift) and subtracts it. Plots raw, drift fit, and
corrected traces on one figure. Corrected trace is anchored to zero at
t = EVAL_T_PRE to match the `delta_i_corrected` convention.

Run from repo root:
    python scripts/plot_raw_vs_corrected_it_encap75_seq85.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style

CHIP = 75
SEQ = 85
FIT_T_START = 0.0  # Encap75 stretched-exp fit needs early-time data
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
PLOT_START_TIME = 0.0

HISTORY_PATH = Path("data/02_stage/chip_histories/Alisson75_history.parquet")
OUTPUT_DIR = Path("figs/compare")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    history = pl.read_parquet(HISTORY_PATH)
    rows = history.filter((pl.col("seq") == SEQ) & (pl.col("proc") == "It"))
    if rows.height == 0:
        raise ValueError(f"no It row for Alisson{CHIP} seq {SEQ}")
    row = rows.to_dicts()[0]

    meas = read_measurement_parquet(Path(row["parquet_path"]))
    t = meas["t (s)"].to_numpy().astype(np.float64)
    i = meas["I (A)"].to_numpy().astype(np.float64)
    finite = np.isfinite(t) & np.isfinite(i)
    t, i = t[finite], i[finite]

    mask = (t >= FIT_T_START) & (t <= FIT_T_END)
    if mask.size:
        mask[0] = False
    fit = fit_stretched_exponential(t[mask], i[mask])
    drift = stretched_exponential(
        t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
    )
    i_corr = i - drift

    idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
    # Anchor each trace to zero at t = EVAL_T_PRE independently so raw and
    # corrected coincide at that point.
    raw_shift = i[idx_pre]
    corr_shift = i_corr[idx_pre]
    i_raw_shifted = i - raw_shift if np.isfinite(raw_shift) else i
    drift_shifted = drift - raw_shift if np.isfinite(raw_shift) else drift
    i_corr = i_corr - corr_shift if np.isfinite(corr_shift) else i_corr

    plt.figure(figsize=config.figsize_timeseries)
    plt.plot(t, i_raw_shifted * 1e6, label="raw")
    plt.plot(t, drift_shifted * 1e6, label="drift fit", linestyle="--")
    plt.plot(t, i_corr * 1e6, label="corrected")
    plt.axvline(EVAL_T_PRE, color="k", linewidth=0.5, linestyle=":", alpha=0.6)

    if "VL (V)" in meas.columns:
        vl = meas["VL (V)"].to_numpy()
        on_idx = np.where(vl > 0.1)[0]
        if on_idx.size:
            plt.axvspan(
                float(t[on_idx[0]]),
                float(t[on_idx[-1]]),
                alpha=config.light_window_alpha,
            )

    T_total = float(t[-1])
    if np.isfinite(T_total) and T_total > 0:
        plt.xlim(PLOT_START_TIME, T_total)

    visible = t >= PLOT_START_TIME
    all_y = np.concatenate([
        (i_raw_shifted * 1e6)[visible],
        (drift_shifted * 1e6)[visible],
        (i_corr * 1e6)[visible],
    ])
    all_y = all_y[np.isfinite(all_y)]
    if all_y.size:
        y_min, y_max = float(all_y.min()), float(all_y.max())
        if y_max > y_min:
            pad = config.padding_fraction * (y_max - y_min)
            plt.ylim(y_min - pad, y_max + pad)

    plt.xlabel(r"$t\ (\mathrm{s})$")
    plt.ylabel(r"$I\ (\mu\mathrm{A})$")
    plt.legend()
    plt.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"alisson{CHIP}_seq{SEQ}_raw_vs_corrected_It.png"
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close()
    print(f"saved {output_path}")
    print(
        f"fit: baseline={fit['baseline']:.3e} A  amplitude={fit['amplitude']:.3e} A  "
        f"tau={fit['tau']:.2f} s  beta={fit['beta']:.3f}  R^2={fit['r_squared']:.4f}"
    )


if __name__ == "__main__":
    main()
