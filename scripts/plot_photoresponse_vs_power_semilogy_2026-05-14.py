"""
Photoresponse (|Δi_corrected|) vs laser power on semilog-y axes for the
2026-05-14 365 nm "power law" It sweeps, across six chips.

Chips / fixed gate voltage (all 365 nm, powers 6, 12, 18, 24 µW):
    68  Vg = -0.7  V
    74  Vg = -0.5  V
    75  Vg = -0.5  V
    76  Vg = -0.7  V
    72  Vg = -0.35 V

Correction: stretched-exponential fit on t ∈ [1, 60] s subtracted from the
trace; Δi_corrected = I_corr(120 s) - I_corr(60 s). Absolute value taken so
the response sits on a log y-axis. A linear fit in log P vs log |Δi| gives the
power-law exponent γ with |Δi| ∝ P^γ; the fit curve is drawn on semilog-y axes.

Per chip: one sequential-It figure (raw traces + drift-corrected inset) and one
photoresponse-vs-power figure. Plus one comparison figure overlaying all chips.

Run from repo root:
    python scripts/plot_photoresponse_vs_power_semilogy_2026-05-14.py
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
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style

FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 365.0
DATE = "2026-05-14"

CHIPS: list[dict] = [
    {"chip": 68, "label": r"Encap 68 ($V_g=-0.7$ V)", "color": "#377eb8", "marker": "o"},
    {"chip": 74, "label": r"Encap 74 ($V_g=-0.5$ V)", "color": "#e41a1c", "marker": "s"},
    {"chip": 75, "label": r"Encap 75 ($V_g=-0.5$ V)", "color": "#4daf4a", "marker": "^"},
    {"chip": 76, "label": r"Encap 76 ($V_g=-0.7$ V)", "color": "#984ea3", "marker": "D"},
    {"chip": 72, "label": r"Encap 72 ($V_g=-0.35$ V)", "color": "#a65628", "marker": "P"},
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


def rows_for_chip(hist: pl.DataFrame) -> pl.DataFrame:
    return hist.filter(
        pl.col("date") == DATE,
        pl.col("proc") == "It",
        pl.col("has_light"),
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")


def curve_for_chip(hist: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    rows = rows_for_chip(hist)
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


def power_law_fit(p: np.ndarray, di: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Return (gamma, p_fit, di_fit) from a log-log linear fit."""
    mask = (p > 0) & (di > 0) & np.isfinite(p) & np.isfinite(di)
    gamma, log_a = np.polyfit(np.log10(p[mask]), np.log10(di[mask]), 1)
    a = 10.0**log_a
    p_fit = np.geomspace(p[mask].min(), p[mask].max(), 100)
    return float(gamma), p_fit, a * p_fit**gamma


def plot_it_overlay(config: PlotConfig, hist: pl.DataFrame, chip: dict) -> None:
    rows = rows_for_chip(hist)
    if rows.height == 0:
        print(f"[warn] no It traces for {chip['label']}")
        return

    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))

    n = rows.height
    line_color = chip.get("color", "#d62728")

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
        # (instrument glitch on It restart), single color per chip.
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
            label=chip["label"] if not label_used else None,
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

    filename = f"Alisson{chip['chip']}_It_sequential_with_overlay_{DATE}_365nm"
    out = config.get_output_path(
        filename,
        chip_number=chip["chip"],
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_corrected_overlay_full(config: PlotConfig, hist: pl.DataFrame, chip: dict) -> None:
    """Full-size drift-corrected I_corr overlay (the inset, but as its own figure)
    so the stretched-exponential correction can be inspected per power."""
    rows = rows_for_chip(hist)
    if rows.height == 0:
        print(f"[warn] no It traces for {chip['label']}")
        return

    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))

    n = rows.height
    cmap = mpl.colormaps["plasma_r"]
    cmap_levels = np.linspace(0.15, 1.0, max(1, n))

    all_y: list[float] = []
    for i, row in enumerate(rows.iter_rows(named=True)):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size == 0:
            continue
        # Drop the first sample (instrument glitch on It restart) so it does
        # not dominate the y-scale and hide the corrected-trace detail.
        if t.size > 1:
            t, I = t[1:], I[1:]

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
        I_corr = (I_corr - I_corr[idx_pre]) * 1e6

        p_uW = float(row.get("irradiated_power_w") or 0.0) * 1e6
        ax.plot(
            t,
            I_corr,
            color=cmap(cmap_levels[i]),
            linewidth=2.0,
            label=f"{p_uW:.0f} µW",
        )
        all_y.extend(I_corr.tolist())

    ax.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha)
    ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    ax.set_title(chip["label"])
    ax.legend(loc="best", framealpha=0.9)

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    plt.tight_layout()

    filename = f"Alisson{chip['chip']}_It_corrected_overlay_full_{DATE}_365nm"
    out = config.get_output_path(
        filename,
        chip_number=chip["chip"],
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_photoresponse_vs_power(config: PlotConfig, hist: pl.DataFrame, chip: dict) -> None:
    p, di = curve_for_chip(hist)
    if p.size == 0:
        print(f"[warn] no photoresponse data for {chip['label']}")
        return

    set_plot_style(config.theme)
    fig, ax = plt.subplots(figsize=(20, 20))

    gamma, p_fit, di_fit = power_law_fit(p, di)

    ax.plot(
        p,
        di,
        marker=chip["marker"],
        linestyle="none",
        color=chip["color"],
        markersize=12,
        label=f"{chip['label']}, $\\gamma={gamma:.2f}$",
    )
    ax.plot(p_fit, di_fit, linestyle="-", color=chip["color"], linewidth=1.2)

    ax.set_yscale("log")
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    ax.legend()
    plt.tight_layout()

    print(
        f"{chip['label']}  n={p.size}  P=[{p.min():.2f},{p.max():.2f}] µW  "
        f"|Δi|=[{di.min():.3g},{di.max():.3g}] µA  γ={gamma:.3f}"
    )

    filename = f"Alisson{chip['chip']}_photoresponse_vs_power_semilogy_{DATE}_365nm"
    out = config.get_output_path(
        filename,
        chip_number=chip["chip"],
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

    histories: dict[int, pl.DataFrame] = {}
    for chip in CHIPS:
        path = Path(
            f"data/03_derived/chip_histories_enriched/Alisson{chip['chip']}_history.parquet"
        )
        histories[chip["chip"]] = pl.read_parquet(path)

    for chip in CHIPS:
        hist = histories[chip["chip"]]
        plot_it_overlay(config, hist, chip)
        plot_corrected_overlay_full(config, hist, chip)
        plot_photoresponse_vs_power(config, hist, chip)

    # --- comparison figure: all chips on one semilog-y axes ---
    fig, ax = plt.subplots(figsize=(20, 20))

    for chip in CHIPS:
        p, di = curve_for_chip(histories[chip["chip"]])
        if p.size == 0:
            print(f"[warn] no data for {chip['label']}")
            continue

        gamma, p_fit, di_fit = power_law_fit(p, di)
        ax.plot(
            p,
            di,
            marker=chip["marker"],
            linestyle="none",
            color=chip["color"],
            markersize=12,
            label=f"{chip['label']}, $\\gamma={gamma:.2f}$",
        )
        ax.plot(p_fit, di_fit, linestyle="-", color=chip["color"], linewidth=1.2)

    ax.set_yscale("log")
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    ax.legend()
    plt.tight_layout()

    filename = "Alisson68_72_74_75_76_photoresponse_vs_power_semilogy_2026-05-14_365nm"
    out = config.get_output_path(
        filename,
        chip_number=68,
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
