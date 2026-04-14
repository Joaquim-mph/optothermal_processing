"""
Overlay the first IVg sweep of Alisson72 (hBN) and Alisson81 (biotite).

Produces one PNG under figs/compare/:
  * alisson72_vs_81_IVg_first.png  (linear, I in µA vs Vg in V)

Run from the repo root:
    python scripts/compare_ivg_first_72_81.py

Prereq: chip histories have been built (biotite build-all-histories).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig
from src.plotting.plot_utils import ensure_standard_columns
from src.plotting.styles import set_plot_style

HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_PATH = Path("figs/compare/alisson72_vs_81_IVg_first.png")

CHIPS = [
    {"chip_number": 72, "label": "72 (hBN)"},
    {"chip_number": 81, "label": "81 (biotite)"},
]


def load_first_ivg(chip_number: int, label: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (Vg_v, I_uA) for the earliest IVg measurement of a chip."""
    history_path = HISTORY_DIR / f"Alisson{chip_number}_history.parquet"
    if not history_path.exists():
        raise FileNotFoundError(
            f"Enriched history not found for chip {chip_number} at {history_path}. "
            f"Run: biotite enrich-history {chip_number}"
        )

    history = pl.read_parquet(history_path)
    ivg = history.filter(pl.col("proc") == "IVg").sort("seq")

    if ivg.height == 0:
        raise ValueError(f"[{label}] no IVg measurements found in history.")

    first = ivg.row(0, named=True)
    parquet_path = Path(first.get("parquet_path") or first.get("source_file") or "")
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"[{label}] measurement file missing for seq={first['seq']}: {parquet_path}"
        )

    measurement = ensure_standard_columns(read_measurement_parquet(parquet_path))
    if not {"VG", "I"} <= set(measurement.columns):
        raise ValueError(
            f"[{label}] seq={first['seq']} missing VG/I columns. "
            f"Got: {measurement.columns}"
        )

    vg = measurement["VG"].to_numpy()
    i_uA = measurement["I"].to_numpy() * 1e6

    print(
        f"[{label}] chip={chip_number} seq={first['seq']} n_points={len(vg)} "
        f"Vg_range=[{vg.min():.2f}, {vg.max():.2f}] V "
        f"I_range=[{i_uA.min():.3g}, {i_uA.max():.3g}] µA"
    )

    return vg, i_uA


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    curves: list[tuple[str, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        vg, i_uA = load_first_ivg(chip["chip_number"], chip["label"])
        curves.append((chip["label"], vg, i_uA))

    fig, ax = plt.subplots(figsize=config.figsize_voltage_sweep)
    for label, vg, i_uA in curves:
        ax.plot(vg, i_uA, label=label)

    ax.set_xlabel("Gate Voltage $V_g$ (V)")
    ax.set_ylabel("Drain Current $I_d$ (µA)")
    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PATH, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
