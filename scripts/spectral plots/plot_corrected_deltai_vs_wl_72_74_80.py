"""
Corrected ΔI vs wavelength for chips 72 (hBN), 74 (biotite), 80 (biotite).

Single figure: |ΔI_corr| = |I_corr(120 s) − I_corr(60 s)| vs wavelength,
one curve per chip. Drift correction: stretched-exponential fit on
t ∈ [fit_t_start, 60] s, subtracted from the full trace; baseline anchored
so I_corr(60 s) = 0.

Run from repo root:
    python scripts/plot_corrected_deltai_vs_wl_72_74_80.py
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
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")

DEFAULT_FIT_T_START = 0.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0

CHIPS = {
    72: {
        "label": "72 (hBN)",
        "seqs": [103, 105, 107, 112, 114, 116, 118, 120, 122, 124],
    },
    74: {
        "label": "74 (biotite)",
        "seqs": [5, 7, 9, 11, 13, 17, 20, 22, 24, 28],
        "fit_t_start": 30.0,
    },
    80: {
        "label": "80 (biotite)",
        "seqs": [95, 97, 99, 101, 103, 105, 107, 109, 111, 113],
    },
}

CHIP_COLORS = {72: "C4", 74: "C3", 80: "C2"}
CHIP_MARKERS = {72: "s", 74: "o", 80: "o"}


def load_history(chip_number: int) -> pl.DataFrame:
    path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched history missing for chip {chip_number}: {path}"
        )
    return pl.read_parquet(path)


def select_its_rows(history: pl.DataFrame, seqs: list[int]) -> pl.DataFrame:
    rows = (
        history.filter(pl.col("seq").is_in(seqs))
        .filter(pl.col("proc") == "It")
        .filter(pl.col("has_light") == True)  # noqa: E712
    )
    if rows.height == 0:
        raise ValueError(f"no It+light rows matched seqs={seqs}")
    return rows.sort("wavelength_nm")


def corrected_deltai_uA(t: np.ndarray, i: np.ndarray, fit_t_start: float) -> float:
    finite = np.isfinite(t) & np.isfinite(i)
    t = t[finite]
    i = i[finite]
    mask = (t >= fit_t_start) & (t <= FIT_T_END)
    if mask.size:
        mask[0] = False
    if mask.sum() < 10:
        return float("nan")
    try:
        se = fit_stretched_exponential(t[mask], i[mask])
    except Exception as exc:
        print(f"  stretched-exp fit failed: {exc}")
        return float("nan")
    drift = stretched_exponential(
        t, se["baseline"], se["amplitude"], se["tau"], se["beta"]
    )
    i_corr = i - drift
    idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
    i_corr = i_corr - i_corr[idx_pre]
    idx_post = int(np.argmin(np.abs(t - EVAL_T_POST)))
    return float(i_corr[idx_post]) * 1e6


def collect_chip_points(chip_number: int) -> list[tuple[float, float]]:
    history = load_history(chip_number)
    chip_cfg = CHIPS[chip_number]
    rows = select_its_rows(history, chip_cfg["seqs"])
    fit_t_start = float(chip_cfg.get("fit_t_start", DEFAULT_FIT_T_START))

    pts: list[tuple[float, float]] = []
    for row in rows.iter_rows(named=True):
        parquet_path = Path(row.get("parquet_path") or "")
        if not parquet_path.exists():
            print(f"  [chip {chip_number}] missing parquet: {parquet_path}")
            continue
        meas = read_measurement_parquet(parquet_path)
        if "t (s)" not in meas.columns or "I (A)" not in meas.columns:
            continue
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)
        wl = row.get("wavelength_nm")
        di = corrected_deltai_uA(t, i, fit_t_start)
        if wl is not None and np.isfinite(wl) and np.isfinite(di):
            pts.append((float(wl), di))
    pts.sort()
    return pts


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    points_by_chip: dict[int, list[tuple[float, float]]] = {}
    for chip_num in CHIPS:
        print(f"[chip {chip_num}] collecting points…")
        points_by_chip[chip_num] = collect_chip_points(chip_num)

    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side, side))

    for chip_num, pts in points_by_chip.items():
        if not pts:
            continue
        wls = np.array([p[0] for p in pts])
        dis = np.abs(np.array([p[1] for p in pts]))
        ax.plot(
            wls,
            dis,
            color=CHIP_COLORS.get(chip_num, "k"),
            marker=CHIP_MARKERS.get(chip_num, "o"),
            linestyle="-",
            label=CHIPS[chip_num]["label"],
        )

    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(r"$|\Delta I_{\mathrm{corr}}|\ (\mu\mathrm{A})$")
    ax.set_box_aspect(1.0)
    ax.legend(loc="best", framealpha=0.9, fontsize="small")

    out = config.get_output_path(
        "alisson72_74_80_photoresponse_vs_wl.png",
        chip_number=72,
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.tight_layout()
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
