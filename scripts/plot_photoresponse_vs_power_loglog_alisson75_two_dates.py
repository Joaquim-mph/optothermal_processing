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

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
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
    # Optimized to a single filter operation to prevent intermediate copies in memory
    return hist.filter(
        pl.col("seq").is_in(group["seqs"]),
        pl.col("date") == group["date"],
        pl.col("proc") == "It",
        pl.col("has_light"),  # Implicitly evaluates to True without needing == True
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")


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

    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))

    n = rows.height
    line_color = group.get("color", "#d62728")

    seg_t: list[np.ndarray] = []
    seg_I_corr: list[np.ndarray] = []
    all_y: list[float] = []
    time_offset = 0.0
    label_used = False

    for row in rows.iter_rows(named=True):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size == 0:
            continue

        # Drift-corrected trace for the inset
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

        seg_t.append(t.copy())
        seg_I_corr.append(I_corr * 1e6)

        # Sequential raw trace: zero-base each segment, drop first sample
        # (instrument glitch on It restart), single color per group.
        t_seg = t - t[0]
        y_seg = I * 1e6
        if t_seg.size > 1:
            t_seg = t_seg[1:]
            y_seg = y_seg[1:]

        ax.plot(
            t_seg + time_offset,
            y_seg,
            color=line_color,
            linewidth=2.0,
            label=group["label"] if not label_used else None,
        )
        label_used = True
        all_y.extend(y_seg.tolist())

        time_offset += float(t_seg[-1])

    ax.set_xlabel(r"t (s)")
    ax.set_ylabel(r"$I_{ds}\ (\mu\mathrm{A})$")
    ax.legend(loc="best", framealpha=0.9)

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_xlim(0.0, time_offset)

    # --- inset: drift-corrected overlay, plasma_r by power ---
    inset = ax.inset_axes([0.18, 0.16, 0.3, 0.3])
    cmap = mpl.colormaps["plasma_r"]
    cmap_levels = np.linspace(0.15, 1.0, max(1, n))

    inset_t_totals: list[float] = []

    for i, (t_full, ic_uA) in enumerate(zip(seg_t, seg_I_corr)):
        color = cmap(cmap_levels[i])
        inset.plot(t_full, ic_uA, color=color, linewidth=1.5)
        inset_t_totals.append(float(t_full[-1]))

    inset.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha)

    x_lo = 50.0
    x_hi = None
    if inset_t_totals:
        T_total = float(np.median(inset_t_totals))
        if np.isfinite(T_total) and T_total > 0:
            x_hi = T_total
            inset.set_xlim(x_lo, x_hi)
    inset.set_xticks([60, 120, 180])

    visible_y: list[float] = []
    for t_full, ic_uA in zip(seg_t, seg_I_corr):
        m = t_full >= x_lo
        if x_hi is not None:
            m &= t_full <= x_hi
        visible_y.extend(ic_uA[m].tolist())
    if visible_y:
        y = np.array(visible_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                inset.set_ylim(y_min - pad, y_max + pad)

    inset.set_xlabel(r"$t\ (\mathrm{s})$")
    inset.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")

    y_lo, y_hi = inset.get_ylim()
    arrow_top = y_hi - 0.10 * (y_hi - y_lo)
    arrow_bot = y_lo + 0.10 * (y_hi - y_lo)
    inset.annotate(
        "",
        xy=(90, arrow_bot),
        xytext=(90, arrow_top),
        arrowprops=dict(arrowstyle="->", color="k", lw=1.5),
    )
    inset.text(
        92,
        0.5 * (arrow_top + arrow_bot),
        "P",
        va="center",
        ha="left",
        fontsize="medium",
    )

    plt.tight_layout()

    seq_tag = "_".join(str(s) for s in group["seqs"])
    filename = f"Alisson{CHIP}_It_sequential_with_overlay_seq_{seq_tag}"
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

        # geomspace is a cleaner abstraction than logspace with log10 boundaries
        p_fit = np.geomspace(p[mask].min(), p[mask].max(), 100)
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

    # Apply logarithmic scales
    ax.set_xscale("log")
    ax.set_yscale("log")

    # Definir ticks mayores explícitos en X (mostrarán números)
    ax.set_xticks([6, 18, 30])
    # Definir ticks menores explícitos en X (marcas intermedias sin número)
    ax.set_xticks([12, 24], minor=True)

    # Definir ticks mayores explícitos en Y
    ax.set_yticks([5, 10, 20])

    # Use FuncFormatter to force plain numbers and prevent scientific formatting
    formatter = ticker.FuncFormatter(lambda x, pos: f"{x:g}")
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)

    # Ensure minor ticks don't print messy text
    ax.xaxis.set_minor_formatter(ticker.NullFormatter())
    ax.yaxis.set_minor_formatter(ticker.NullFormatter())

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
