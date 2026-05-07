"""
Drift-corrected It overlay at 365 nm and 385 nm for chips 72 (hBN), 74
(biotite), and 80 (biotite). One trace per chip on a figure per wavelength.

Drift model: stretched exponential fit on t ∈ [20, 60] s, subtracted from the
full trace. Baseline anchored so I_corr(60 s) = 0.

Run from repo root:
    python scripts/compare_corrected_It_72_74_80_385nm.py
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
TARGET_WAVELENGTHS = (365.0, 385.0)
TICK_STEP = 30.0

# Candidate seqs per chip (from compare_corrected_It_67_72_74_75_80_81_pairs.py).
# We pick the one with wavelength_nm == 385 from the enriched history.
CHIPS = [
    {
        "chip_number": 72,
        "label": "72 (hBN)",
        "color": "C0",
        "candidate_seqs": [103, 105, 107, 112, 114, 116, 118, 120, 122, 124],
    },
    {
        "chip_number": 74,
        "label": "74 (biotite)",
        "color": "C3",
        "candidate_seqs": [5, 7, 9, 11, 13, 17, 20, 22, 24, 28],
    },
    {
        "chip_number": 80,
        "label": "80 (biotite)",
        "color": "C2",
        "candidate_seqs": [95, 97, 99, 101, 103, 105, 107, 109, 111, 113],
    },
]


def load_history(chip_number: int) -> pl.DataFrame:
    path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched history missing for chip {chip_number}: {path}"
        )
    return pl.read_parquet(path)


def find_wavelength_row(
    history: pl.DataFrame, candidate_seqs: list[int], wavelength: float
) -> dict:
    rows = (
        history
        .filter(pl.col("seq").is_in(candidate_seqs))
        .filter(pl.col("proc") == "It")
        .filter(pl.col("has_light") == True)  # noqa: E712
        .filter(pl.col("wavelength_nm") == wavelength)
    )
    if rows.height == 0:
        raise ValueError(
            f"no It+light row with wavelength_nm == {wavelength} found among "
            f"seqs={candidate_seqs}"
        )
    return rows.row(0, named=True)


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


def make_figure(wavelength: float, config: PlotConfig) -> None:
    print(f"\n=== {wavelength:g} nm ===")
    traces: list[dict] = []
    starts_vl: list[float] = []
    ends_vl: list[float] = []

    for chip in CHIPS:
        history = load_history(chip["chip_number"])
        try:
            row = find_wavelength_row(history, chip["candidate_seqs"], wavelength)
        except ValueError as exc:
            print(f"  chip {chip['chip_number']}: {exc}")
            continue
        seq = row["seq"]
        parquet_path = Path(row.get("parquet_path") or "")
        if not parquet_path.exists():
            print(f"  missing parquet for chip {chip['chip_number']} seq {seq}")
            continue
        print(
            f"  chip {chip['chip_number']} seq {seq}: "
            f"wl={row.get('wavelength_nm')} nm  "
            f"Vg={row.get('vg_fixed_v')} V"
        )

        meas = read_measurement_parquet(parquet_path)
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)
        i_corr = corrected_trace(t, i)

        if np.any(np.isfinite(i_corr)):
            idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
            baseline = i_corr[idx_pre]
            if np.isfinite(baseline):
                i_corr = i_corr - baseline

        traces.append({
            "t": t,
            "i_uA": i_corr * 1e6,
            "color": chip["color"],
            "label": chip["label"],
        })

        if "VL (V)" in meas.columns:
            vl = meas["VL (V)"].to_numpy()
            on_idx = np.where(vl > 0.1)[0]
            if on_idx.size:
                starts_vl.append(float(t[on_idx[0]]))
                ends_vl.append(float(t[on_idx[-1]]))

    if not traces:
        print(f"  no traces for {wavelength:g} nm — skipping figure")
        return

    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side, side))
    all_y: list[float] = []
    t_totals: list[float] = []

    for tr in traces:
        ax.plot(tr["t"], tr["i_uA"], color=tr["color"], linestyle="-",
                label=tr["label"])
        visible = tr["t"] >= PLOT_START_TIME
        all_y.extend(tr["i_uA"][visible])
        t_totals.append(float(tr["t"][-1]))

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            ax.set_xlim(PLOT_START_TIME, T_total)

    if starts_vl and ends_vl:
        ax.axvspan(
            float(np.median(starts_vl)),
            float(np.median(ends_vl)),
            alpha=config.light_window_alpha,
        )

    from matplotlib.ticker import MultipleLocator
    ax.xaxis.set_major_locator(MultipleLocator(TICK_STEP))

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    ax.set_box_aspect(1.0)

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()

    output_path = (
        OUTPUT_DIR / f"alisson72_74_80_It_corrected_overlay_{int(wavelength)}nm.png"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)
    for wavelength in TARGET_WAVELENGTHS:
        make_figure(wavelength, config)


if __name__ == "__main__":
    main()
