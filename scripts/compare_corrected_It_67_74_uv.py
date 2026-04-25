"""
Drift-corrected It overlay comparing chips 67 (hBN) and 74 (biotite) at UV/blue
wavelengths: 365, 385, 405, 455 nm. Eight traces on a single figure.

Drift model: stretched exponential fit on t ∈ [20, 60] s, subtracted from the
full trace. Baseline anchored so I_corr(60 s) = 0.

Run from repo root:
    python scripts/compare_corrected_It_67_74_uv.py
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

ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_DIR = Path("figs/compare")

FIT_T_START = 20.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
PLOT_START_TIME = 20.0

# (chip_number, label, {wavelength_nm: seq})
CHIPS = [
    {
        "chip_number": 67,
        "label": "67 (hBN)",
        "seqs": {365: 41, 385: 27, 405: 15, 455: 4},
    },
    {
        "chip_number": 74,
        "label": "74 (biotite)",
        "seqs": {365: 28, 385: 24, 405: 22, 455: 20},
    },
]
WAVELENGTHS = [365, 385, 405, 455]

# Distinct color per wavelength; linestyle per chip.
WL_COLORS = {365: "C3", 385: "C0", 405: "C2", 455: "C1"}
CHIP_LINESTYLES = {67: "--", 74: "-"}


def load_history(chip_number: int) -> pl.DataFrame:
    path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched history missing for chip {chip_number}: {path}"
        )
    return pl.read_parquet(path)


def corrected_trace(t: np.ndarray, i: np.ndarray) -> np.ndarray:
    finite = np.isfinite(t) & np.isfinite(i)
    t = t[finite]
    i = i[finite]
    mask = (t >= FIT_T_START) & (t <= FIT_T_END)
    if mask.size:
        mask[0] = False
    if mask.sum() < 10:
        return np.full_like(i, np.nan)
    fit = fit_stretched_exponential(t[mask], i[mask])
    drift = stretched_exponential(
        t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
    )
    return i - drift


def _plot(
    config: PlotConfig, traces: list[dict], axtype: str, output_path: Path
) -> None:
    plt.figure(figsize=config.figsize_timeseries)
    all_y: list[float] = []
    t_totals: list[float] = []

    for tr in traces:
        y = tr["i_uA"]
        if axtype == "semilogy":
            y = np.abs(y)
        plt.plot(tr["t"], y, color=tr["color"], linestyle=tr["ls"], label=tr["label"])
        visible = tr["t"] >= PLOT_START_TIME
        all_y.extend(y[visible])
        t_totals.append(float(tr["t"][-1]))

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            plt.xlim(PLOT_START_TIME, T_total)

    if traces and traces[0].get("light_span"):
        s, e = traces[0]["light_span"]
        plt.axvspan(s, e, alpha=config.light_window_alpha)

    plt.xlabel(r"$t\ (\mathrm{s})$")
    if axtype == "semilogy":
        plt.ylabel(r"$|I_{\mathrm{corr}}|\ (\mu\mathrm{A})$")
        plt.yscale("log")
    else:
        plt.ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
        if all_y:
            y = np.array(all_y, dtype=float)
            y = y[np.isfinite(y)]
            if y.size:
                y_min, y_max = float(y.min()), float(y.max())
                if y_max > y_min:
                    pad = config.padding_fraction * (y_max - y_min)
                    plt.ylim(y_min - pad, y_max + pad)

    plt.legend(loc="best", framealpha=0.9, ncol=2)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close()
    print(f"saved {output_path}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    traces: list[dict] = []
    starts_vl: list[float] = []
    ends_vl: list[float] = []

    for chip in CHIPS:
        history = load_history(chip["chip_number"])
        for wl in WAVELENGTHS:
            seq = chip["seqs"][wl]
            row = history.filter(pl.col("seq") == seq).row(0, named=True)
            parquet_path = Path(row.get("parquet_path") or "")
            if not parquet_path.exists():
                print(f"  missing parquet for chip {chip['chip_number']} seq {seq}")
                continue
            meas = read_measurement_parquet(parquet_path)
            t = meas["t (s)"].to_numpy().astype(np.float64)
            i = meas["I (A)"].to_numpy().astype(np.float64)
            i_corr = corrected_trace(t, i)

            if np.any(np.isfinite(i_corr)):
                idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
                baseline = i_corr[idx_pre]
                if np.isfinite(baseline):
                    i_corr = i_corr - baseline

            traces.append(
                {
                    "t": t,
                    "i_uA": i_corr * 1e6,
                    "color": WL_COLORS[wl],
                    "ls": CHIP_LINESTYLES[chip["chip_number"]],
                    "label": f"{chip['label']} — {wl} nm",
                    "wl": wl,
                }
            )

            if "VL (V)" in meas.columns:
                vl = meas["VL (V)"].to_numpy()
                on_idx = np.where(vl > 0.1)[0]
                if on_idx.size:
                    starts_vl.append(float(t[on_idx[0]]))
                    ends_vl.append(float(t[on_idx[-1]]))

    if traces and starts_vl and ends_vl:
        traces[0]["light_span"] = (
            float(np.median(starts_vl)),
            float(np.median(ends_vl)),
        )

    base = OUTPUT_DIR / "alisson67_74_It_corrected_overlay_uv"
    _plot(config, traces, "linear", base.with_suffix(".png"))
    _plot(
        config,
        traces,
        "semilogy",
        base.with_name(base.name + "_semilogy").with_suffix(".png"),
    )
    _plot_linear_with_inset(
        config, traces, base.with_name(base.name + "_with_inset").with_suffix(".png")
    )

    chip_colors_385 = {67: "C0", 74: "C3"}
    traces_385 = []
    for tr in traces:
        if tr["wl"] != 385:
            continue
        chip_num = 67 if "67" in tr["label"] else 74
        traces_385.append({**tr, "color": chip_colors_385[chip_num], "ls": "-"})
    if traces_385 and traces and traces[0].get("light_span"):
        traces_385[0]["light_span"] = traces[0]["light_span"]
    _plot(
        config,
        traces_385,
        "linear",
        base.with_name(base.name + "_385nm").with_suffix(".png"),
    )


def _plot_linear_with_inset(
    config: PlotConfig, traces: list[dict], output_path: Path
) -> None:
    fig, ax = plt.subplots(figsize=config.figsize_timeseries)
    all_y: list[float] = []
    t_totals: list[float] = []

    for tr in traces:
        ax.plot(
            tr["t"],
            tr["i_uA"],
            color=tr["color"],
            linestyle=tr["ls"],
            label=tr["label"],
        )
        visible = tr["t"] >= PLOT_START_TIME
        all_y.extend(tr["i_uA"][visible])
        t_totals.append(float(tr["t"][-1]))

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            ax.set_xlim(PLOT_START_TIME, T_total)

    if traces and traces[0].get("light_span"):
        s, e = traces[0]["light_span"]
        ax.axvspan(s, e, alpha=config.light_window_alpha)

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    ax.legend(loc="lower right", framealpha=0.9, ncol=2)

    # Inset: semilogy in t ∈ [60, 120] — lower left.
    # [x0, y0, width, height] in axes fraction coordinates.
    axins = ax.inset_axes([0.08, 0.12, 0.28, 0.32])
    inset_y: list[float] = []
    for tr in traces:
        mask = (tr["t"] >= 60.0) & (tr["t"] <= 120.0)
        if not mask.any():
            continue
        y_abs = np.abs(tr["i_uA"][mask])
        axins.plot(tr["t"][mask], y_abs, color=tr["color"], linestyle=tr["ls"])
        inset_y.extend(y_abs)
    axins.set_yscale("log")
    axins.set_xlim(60.0, 120.0)
    if inset_y:
        y = np.array(inset_y, dtype=float)
        y = y[np.isfinite(y) & (y > 0)]
        if y.size:
            axins.set_ylim(y.min() * 0.8, y.max() * 1.2)
    axins.tick_params(axis="both", labelsize=27)
    axins.set_xlabel(r"$t\ (\mathrm{s})$", fontsize=32, labelpad=2)
    axins.set_ylabel(r"$|I_{\mathrm{corr}}|\ (\mu\mathrm{A})$", fontsize=32, labelpad=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


if __name__ == "__main__":
    main()
