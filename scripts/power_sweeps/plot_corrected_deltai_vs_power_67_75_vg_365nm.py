"""
Corrected ΔI vs laser power for Alisson67 (hBN) and Alisson75 (Biotite)
at two gate voltages (positive and negative), wavelength = 365 nm.

Encap67: 2025-10-14, seq 41-49 (Vg = -0.4 V and +0.2 V).
Encap75: 2025-09-12, seq 5-14 (Vg = -3.0 V and +3.0 V).

Four power values per chip (common lowest 4 powers used for Encap75).
Signed (not abs) corrected Δi is plotted. Correction logic matches
scripts/plot_corrected_deltai_vs_wl_alisson74_vg.py.

Run from repo root:
    python scripts/plot_corrected_deltai_vs_power_67_75_vg_365nm.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

FIT_T_START = 20.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 365.0

CHIPS: list[dict] = [
    {
        "chip": 67,
        "label": "67 hBN",
        "color": "#377eb8",
        "date": "2025-10-14",
        "vg_groups": [
            {"vg_v": -0.4, "seqs": [41, 42, 43, 44]},
            {"vg_v": 0.2, "seqs": [46, 47, 48, 49]},
        ],
    },
    {
        "chip": 75,
        "label": "75 Bio",
        "color": "#e41a1c",
        "date": "2025-09-12",
        "vg_groups": [
            {"vg_v": -3.0, "seqs": [5, 6, 7, 8]},
            {"vg_v": 3.0, "seqs": [11, 12, 13, 14]},
        ],
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


def curve_for_group(
    hist: pl.DataFrame, date: str, group: dict
) -> tuple[np.ndarray, np.ndarray]:
    rows = (
        hist.filter(pl.col("seq").is_in(group["seqs"]))
        .filter(pl.col("date") == date)
        .filter(pl.col("proc") == "It")
        .filter(pl.col("has_light") == True)  # noqa: E712
        .filter(pl.col("wavelength_nm") == WAVELENGTH_NM)
        .sort("irradiated_power_w")
    )
    powers_uW: list[float] = []
    di_uA: list[float] = []
    for row in rows.iter_rows(named=True):
        v = delta_i_for_row(row)
        p = row.get("irradiated_power_w")
        if v is None or p is None or not np.isfinite(p):
            continue
        powers_uW.append(float(p) * 1e6)
        di_uA.append(float(v) * 1e6)
    return np.asarray(powers_uW), np.asarray(di_uA)


def power_law_fit(
    p: np.ndarray, di: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    mask = (p > 0) & (di > 0) & np.isfinite(p) & np.isfinite(di)
    if mask.sum() < 2:
        return float("nan"), np.array([]), np.array([])
    gamma, log_a = np.polyfit(np.log10(p[mask]), np.log10(di[mask]), 1)
    a = 10.0**log_a
    p_fit = np.geomspace(p[mask].min(), p[mask].max(), 100)
    return float(gamma), p_fit, a * p_fit**gamma


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    curves: list[tuple[dict, dict, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        hist = pl.read_parquet(
            Path(
                f"data/03_derived/chip_histories_enriched/Alisson{chip['chip']}_history.parquet"
            )
        )
        for group in chip["vg_groups"]:
            p, di = curve_for_group(hist, chip["date"], group)
            if p.size == 0:
                print(f"[warn] no data for Alisson{chip['chip']} Vg={group['vg_v']}")
                continue
            curves.append((chip, group, p, di))

    def _plot(ax: plt.Axes, *, signed: bool) -> None:
        for chip, group, p, di in curves:
            is_electrons = group["vg_v"] >= 0
            marker = "^" if is_electrons else "o"
            di_abs = np.abs(di)
            gamma, p_fit, di_fit = power_law_fit(p, di_abs)
            if signed:
                sign = 1.0 if np.nanmean(di) >= 0 else -1.0
                y = di
                y_fit = sign * di_fit
            else:
                y = di_abs
                y_fit = di_fit
            label = (
                f"{chip['label']}, $V_g$={group['vg_v']:+g} V, $\\gamma={gamma:.2f}$"
            )
            ax.plot(
                p,
                y,
                marker=marker,
                linestyle="none",
                color=chip["color"],
                markersize=25,
                label=label,
            )
            if p_fit.size:
                ax.plot(
                    p_fit,
                    y_fit,
                    linestyle="-",
                    color=chip["color"],
                    linewidth=1.2,
                )
            if not signed:
                print(
                    f"Alisson{chip['chip']} Vg={group['vg_v']:+g} V  n={p.size}  "
                    f"P=[{p.min():.2f},{p.max():.2f}] µW  "
                    f"|Δi_corr|=[{di_abs.min():.3g},{di_abs.max():.3g}] µA  "
                    f"γ={gamma:.3f}"
                )

    # --- semilog-y plot of |Δi_corr| ---
    fig, ax = plt.subplots(figsize=(20, 20))
    _plot(ax, signed=False)
    ax.set_yscale("log")
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    # Legend position in axes fraction (0,0 = bottom-left, 1,1 = top-right).
    # Tweak these to move the box manually.
    legend_xy = (0.52, 0.8)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=legend_xy,
        bbox_transform=ax.transAxes,
        framealpha=0.9,
    )
    plt.tight_layout()

    filename = "Alisson67_75_corrected_deltai_vs_power_365nm_by_Vg"
    out = config.get_output_path(
        filename,
        chip_number=67,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")

    # --- linear plot of signed Δi_corr ---
    fig, ax = plt.subplots(figsize=(20, 20))
    _plot(ax, signed=True)
    ax.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$\Delta i_{\mathrm{corr}}$ ($\mu$A)")
    ax.legend(framealpha=0.9)
    plt.tight_layout()

    filename_lin = "Alisson67_75_corrected_deltai_vs_power_365nm_by_Vg_linear"
    out_lin = config.get_output_path(
        filename_lin,
        chip_number=67,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out_lin, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out_lin}")


if __name__ == "__main__":
    main()
