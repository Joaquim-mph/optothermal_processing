"""
Corrected Δi vs wavelength for Alisson74 at 3 gate voltages.

Vg = -0.5 V data is from 2026-04-16; Vg = +0.5 V and +2.5 V are from
2026-04-21. Only wavelengths present on 2026-04-21 are plotted
(365, 385, 405, 455, 505 nm).

Drift model matches `compare_corrected_photoresponse_72_74_75_81.py`:
stretched-exponential fit on t ∈ [20, 60] s subtracted from the trace;
|Δi_corrected| = |I_corr(120 s) − I_corr(60 s)|.

Run from repo root:
    python scripts/plot_corrected_deltai_vs_wl_alisson74_vg.py
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

CHIP_NUMBER = 74
HISTORY_PATH = Path(
    f"data/02_stage/chip_histories/Alisson{CHIP_NUMBER}_history.parquet"
)

FIT_T_START = 20.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0

WAVELENGTHS_NM = [365.0, 385.0, 405.0, 455.0, 505.0]

VG_GROUPS: list[dict] = [
    {"vg_v": -0.5, "date": "2026-04-16", "seqs": [28, 24, 22, 20, 17]},
    {"vg_v": 0.5, "date": "2026-04-21", "seqs": [43, 41, 39, 36, 34]},
    {"vg_v": 2.5, "date": "2026-04-21", "seqs": [53, 51, 49, 47, 45]},
]

_EXTRACTORS: dict[float, CorrectedDeltaIExtractor] = {}


def _get_extractor(fit_t_start: float) -> CorrectedDeltaIExtractor:
    if fit_t_start not in _EXTRACTORS:
        _EXTRACTORS[fit_t_start] = CorrectedDeltaIExtractor(
            fit_t_start=fit_t_start,
            fit_t_end=FIT_T_END,
            eval_t_pre=EVAL_T_PRE,
            eval_t_post=EVAL_T_POST,
        )
    return _EXTRACTORS[fit_t_start]


def delta_i_for_row(row: dict, fit_t_start: float) -> float | None:
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
    metric = _get_extractor(fit_t_start).extract(meas, meta)
    if metric is None or metric.value_float is None:
        return None
    v = metric.value_float
    return v if np.isfinite(v) else None


def curve_for_group(hist: pl.DataFrame, group: dict) -> tuple[np.ndarray, np.ndarray]:
    rows = (
        hist.filter(pl.col("seq").is_in(group["seqs"]))
        .filter(pl.col("date") == group["date"])
        .filter(pl.col("proc") == "It")
        .filter(pl.col("has_light") == True)  # noqa: E712
        .filter(pl.col("wavelength_nm").is_in(WAVELENGTHS_NM))
        .sort("wavelength_nm")
    )
    fit_t_start = float(group.get("fit_t_start", FIT_T_START))
    wls: list[float] = []
    di_uA: list[float] = []
    for row in rows.iter_rows(named=True):
        v = delta_i_for_row(row, fit_t_start)
        if v is None:
            continue
        wls.append(float(row["wavelength_nm"]))
        di_uA.append(abs(v) * 1e6)
    return np.asarray(wls), np.asarray(di_uA)


def corrected_trace(
    t: np.ndarray, i: np.ndarray, fit_t_start: float = FIT_T_START
) -> np.ndarray:
    finite = np.isfinite(t) & np.isfinite(i)
    t = t[finite]
    i = i[finite]
    mask = (t >= fit_t_start) & (t <= FIT_T_END)
    if mask.size:
        mask[0] = False
    if mask.sum() < 10:
        return np.full_like(i, np.nan)
    fit = fit_stretched_exponential(t[mask], i[mask])
    drift = stretched_exponential(
        t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
    )
    out = i - drift
    idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
    baseline = out[idx_pre]
    if np.isfinite(baseline):
        out = out - baseline
    return out


def plot_it_grid(hist: pl.DataFrame, config: PlotConfig) -> None:
    set_plot_style(config.theme)
    fig, axes = plt.subplots(2, 3, figsize=(45, 25))

    for ax, wl_target in zip(axes.flat, WAVELENGTHS_NM):
        starts_vl: list[float] = []
        ends_vl: list[float] = []
        for group in VG_GROUPS:
            rows = (
                hist.filter(pl.col("seq").is_in(group["seqs"]))
                .filter(pl.col("date") == group["date"])
                .filter(pl.col("proc") == "It")
                .filter(pl.col("wavelength_nm") == wl_target)
            )
            if rows.height == 0:
                continue
            row = rows.row(0, named=True)
            meas = read_measurement_parquet(Path(row["parquet_path"]))
            t = meas["t (s)"].to_numpy().astype(np.float64)
            i = meas["I (A)"].to_numpy().astype(np.float64)
            fit_t_start = float(group.get("fit_t_start", FIT_T_START))
            i_corr = corrected_trace(t, i, fit_t_start)
            visible = t >= 20.0
            ax.plot(t[visible], (i_corr * 1e6)[visible], label=f"{group['vg_v']:+g} V")
            if "VL (V)" in meas.columns:
                vl = meas["VL (V)"].to_numpy()
                on_idx = np.where(vl > 0.1)[0]
                if on_idx.size:
                    starts_vl.append(float(t[on_idx[0]]))
                    ends_vl.append(float(t[on_idx[-1]]))

        if starts_vl and ends_vl:
            ax.axvspan(
                float(np.median(starts_vl)),
                float(np.median(ends_vl)),
                alpha=config.light_window_alpha,
            )
        ax.relim()
        ax.autoscale_view()
        ax.set_xticks([60, 120, 180])
        ax.set_title(f"{int(wl_target)} nm")

    for ax in axes.flat[len(WAVELENGTHS_NM) :]:
        ax.set_visible(False)

    for ax in axes.flat:
        if ax.get_visible():
            ax.set_xlabel(r"$t\ (\mathrm{s})$")
            ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        ncol=3,
        bbox_to_anchor=(0.5, 1.0),
        frameon=False,
        title=r"$V_g$",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    filename = f"Alisson{CHIP_NUMBER}_It_corrected_overlay_by_wavelength_Vg_grid"
    out = config.get_output_path(
        filename,
        chip_number=CHIP_NUMBER,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    hist = pl.read_parquet(HISTORY_PATH)

    fig, ax = plt.subplots(figsize=config.figsize_derived)
    for group in VG_GROUPS:
        wl, di = curve_for_group(hist, group)
        if wl.size == 0:
            print(f"[warn] no data for Vg = {group['vg_v']} V")
            continue
        ax.plot(wl, di, "o-", label=f"{group['vg_v']:+g} V")
        print(
            f"Vg={group['vg_v']:+g} V  n={wl.size}  "
            f"wl=[{wl.min():.0f},{wl.max():.0f}] nm  "
            f"|Δi_corr|=[{di.min():.3g},{di.max():.3g}] µA"
        )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corrected}}|\ (\mu\mathrm{A})$")
    ax.legend(title=r"$V_g$")
    plt.tight_layout()

    filename = f"Alisson{CHIP_NUMBER}_corrected_deltai_vs_wavelength_by_Vg"
    out = config.get_output_path(
        filename,
        chip_number=CHIP_NUMBER,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")

    plot_it_grid(hist, config)


if __name__ == "__main__":
    main()
