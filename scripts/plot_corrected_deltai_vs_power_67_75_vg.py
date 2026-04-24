"""
Corrected ΔI vs laser power for Alisson67 (hBN) and Alisson75 (Biotite)
at two gate voltages (positive and negative), wavelength = 455 nm.

Encap67: 2025-10-14, seq 4-12 (Vg = -0.35 V and +0.2 V).
Encap75: 2025-09-12, seq 18-28 (Vg = -3.0 V and +3.0 V).

Four power values per chip (common lowest 4 powers used for Encap75).
Signed (not abs) corrected Δi is plotted. Correction logic matches
scripts/plot_corrected_deltai_vs_wl_alisson74_vg.py: stretched-exponential
fit on t ∈ [20, 60] s subtracted from the trace;
Δi_corrected = I_corr(120 s) - I_corr(60 s).

Run from repo root:
    python scripts/plot_corrected_deltai_vs_power_67_75_vg.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style

FIT_T_START = 20.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 455.0

# (chip_number, label, color, history_path, date, vg_groups)
CHIPS: list[dict] = [
    {
        "chip": 67,
        "label": "hBN",
        "color": "#377eb8",
        "date": "2025-10-14",
        "vg_groups": [
            {"vg_v": -0.35, "seqs": [4, 5, 6, 7]},
            {"vg_v": 0.2, "seqs": [9, 10, 11, 12]},
        ],
    },
    {
        "chip": 75,
        "label": "Biotite",
        "color": "#e41a1c",
        "date": "2025-09-12",
        "vg_groups": [
            {"vg_v": -3.0, "seqs": [18, 19, 20, 21]},
            {"vg_v": 3.0, "seqs": [24, 25, 26, 27]},
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
        di_uA.append(v * 1e6)
    return np.asarray(powers_uW), np.asarray(di_uA)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    fig, ax = plt.subplots(figsize=config.figsize_derived)

    for chip in CHIPS:
        hist = pl.read_parquet(
            Path(
                f"data/03_derived/chip_histories_enriched/Alisson{chip['chip']}_history.parquet"
            )
        )
        for i, group in enumerate(chip["vg_groups"]):
            p, di = curve_for_group(hist, chip["date"], group)
            if p.size == 0:
                print(f"[warn] no data for Alisson{chip['chip']} Vg={group['vg_v']}")
                continue
            marker = "o" if group["vg_v"] >= 0 else "s"
            linestyle = "-" if group["vg_v"] >= 0 else "--"
            label = f"{chip['label']}, $V_g$={group['vg_v']:+g} V"
            ax.plot(
                p,
                di,
                marker=marker,
                linestyle=linestyle,
                color=chip["color"],
                label=label,
            )
            print(
                f"Alisson{chip['chip']} Vg={group['vg_v']:+g} V  n={p.size}  "
                f"P=[{p.min():.2f},{p.max():.2f}] µW  "
                f"Δi_corr=[{di.min():.3g},{di.max():.3g}] µA"
            )

    ax.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel(r"Laser power ($\mu$W)")
    ax.set_ylabel(r"$\Delta i_{\mathrm{corrected}}$ ($\mu$A)")
    ax.legend()
    plt.tight_layout()

    filename = "Alisson67_75_corrected_deltai_vs_power_455nm_by_Vg"
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


if __name__ == "__main__":
    main()
