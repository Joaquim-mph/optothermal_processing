"""
Photoresponse (|Δi_corrected|) vs laser power on log-log axes for Alisson75
at 365 nm, with independent power-law fits for two measurement sessions.

Group A: 2025-09-12, seq 5-9,  Vg = -3.0 V
Group B: 2025-09-15, seq 52-56, Vg = -3.87 V

Powers: 6, 12, 18, 24, 30 µW (same set in both groups).

Correction: stretched-exponential fit on t ∈ [5, 60] s subtracted from the
trace; Δi_corrected = I_corr(120 s) - I_corr(60 s). Absolute value taken so
both signs collapse onto the log axis. A linear fit in log P vs log |Δi|
gives the power-law exponent n with ΔI ∝ P^n.

Run from repo root:
    python scripts/plot_photoresponse_vs_power_loglog_alisson75_two_dates.py
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
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style

FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 365.0
CHIP = 75

GROUPS: list[dict] = [
    {
        "label": r"$V_g=-3.0$ V (Initial)",
        "color": "#377eb8",
        "marker": "o",
        "date": "2025-09-12",
        "seqs": [5, 6, 7, 8, 9],
    },
    {
        "label": r"$V_g=-3.87$ V (Post-illumination)",
        "color": "#e41a1c",
        "marker": "s",
        "date": "2025-09-15",
        "seqs": [52, 53, 54, 55, 56],
    },
]

_EXTRACTOR = CorrectedDeltaIExtractor(
    fit_t_start=FIT_T_START,
    fit_t_end=FIT_T_END,
    eval_t_pre=EVAL_T_PRE,
    eval_t_post=EVAL_T_POST,
)


def delta_i_for_row(row: dict) -> float | None:
    parquet_path = Path(row.get("parquet_path") or "")
    if not parquet_path.exists():
        return None
    meas = read_measurement_parquet(parquet_path)
    meta = {
        "run_id": row["run_id"],
        "chip_number": int(row["chip_number"]),
        "chip_group": str(row.get("chip_group", "Alisson")),
        "procedure": row.get("proc", "It"),
        "extraction_version": "fallback",
    }
    metric = _EXTRACTOR.extract(meas, meta)
    if metric is None or metric.value_float is None:
        return None
    v = metric.value_float
    return v if np.isfinite(v) else None


def rows_for_group(hist: pl.DataFrame, group: dict) -> pl.DataFrame:
    return (
        hist.filter(pl.col("seq").is_in(group["seqs"]))
        .filter(pl.col("date") == group["date"])
        .filter(pl.col("proc") == "It")
        .filter(pl.col("has_light") == True)  # noqa: E712
        .filter(pl.col("wavelength_nm") == WAVELENGTH_NM)
        .sort("irradiated_power_w")
    )


def curve_for_group(hist: pl.DataFrame, group: dict) -> tuple[np.ndarray, np.ndarray]:
    rows = rows_for_group(hist, group)
    powers_uW: list[float] = []
    di_uA: list[float] = []
    for row in rows.iter_rows(named=True):
        v = delta_i_for_row(row)
        p = row.get("irradiated_power_w")
        if v is None or p is None or not np.isfinite(p):
            continue
        powers_uW.append(float(p) * 1e6)
        di_uA.append(abs(v) * 1e6)
    return np.asarray(powers_uW), np.asarray(di_uA)


def plot_it_overlay(config: PlotConfig, hist: pl.DataFrame, group: dict) -> None:
    rows = rows_for_group(hist, group)
    if rows.height == 0:
        print(f"[warn] no It traces for {group['label']}")
        return

    fig, ax = plt.subplots(figsize=(20, 20))
    for row in rows.iter_rows(named=True):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy()
        I = meas["I (A)"].to_numpy()
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]

        # Same drift correction as the |Δi| vs power plot:
        # stretched-exp fit on t ∈ [FIT_T_START, FIT_T_END], anchored at EVAL_T_PRE.
        mask = (t >= FIT_T_START) & (t <= FIT_T_END)
        if mask.sum() >= 10:
            fit = fit_stretched_exponential(t[mask], I[mask])
            drift = stretched_exponential(
                t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
            )
            I_corr = I - drift
            idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
            I_corr = I_corr - I_corr[idx_pre]
        else:
            idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
            I_corr = I - I[idx_pre]

        p_uW = float(row["irradiated_power_w"]) * 1e6
        ax.plot(
            t,
            I_corr * 1e6,
            linewidth=3.0,
            label=f"{p_uW:.1f} µW",
        )

    ax.set_xlabel(r"Time (s)")
    ax.set_ylabel(r"$\Delta I_{ds}$ ($\mu$A)")
    # ax.set_title(group["label"])
    ax.set_xlim(50, 180)
    ax.legend(fontsize="small")
    plt.tight_layout()

    seq_tag = "_".join(str(s) for s in group["seqs"])
    filename = f"Alisson{CHIP}_It_overlay_seq_{seq_tag}"
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


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    hist = pl.read_parquet(
        Path(f"data/03_derived/chip_histories_enriched/Alisson{CHIP}_history.parquet")
    )

    for group in GROUPS:
        plot_it_overlay(config, hist, group)

    fig, ax = plt.subplots(figsize=(20, 20))

    for group in GROUPS:
        p, di = curve_for_group(hist, group)
        if p.size == 0:
            print(f"[warn] no data for {group['label']}")
            continue

        # Power-law fit in log-log space: log(di) = n*log(p) + log(a)
        mask = (p > 0) & (di > 0) & np.isfinite(p) & np.isfinite(di)
        n_fit, log_a = np.polyfit(np.log10(p[mask]), np.log10(di[mask]), 1)
        a_fit = 10.0**log_a
        p_fit = np.logspace(np.log10(p[mask].min()), np.log10(p[mask].max()), 100)
        di_fit = a_fit * p_fit**n_fit

        ax.plot(
            p,
            di,
            marker=group["marker"],
            linestyle="none",
            color=group["color"],
            label=f"{group['label']}, $\\gamma={n_fit:.2f}$",
        )
        ax.plot(p_fit, di_fit, linestyle="-", color=group["color"], linewidth=1.2)

        print(
            f"{group['label']}  n={p.size}  P=[{p.min():.2f},{p.max():.2f}] µW  "
            f"|Δi|=[{di.min():.3g},{di.max():.3g}] µA  "
            f"fit: |Δi| = {a_fit:.3g} * P^{n_fit:.3f}"
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    ax.legend()
    plt.tight_layout()

    filename = "Alisson75_photoresponse_vs_power_loglog_365nm_two_dates"
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
