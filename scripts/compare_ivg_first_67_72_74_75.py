"""
Overlay the first IVg sweep of six Alisson chips:
  * 67 (hBN)
  * 72 (hBN)
  * 74 (Biotite)
  * 75 (Biotite)
  * 80 (Biotite)
  * 81 (Biotite)

Produces one PNG under figs/compare/:
  * alisson67_72_74_75_80_81_IVg_first.png  (linear, I in µA vs Vg in V)

Run from the repo root:
    python scripts/compare_ivg_first_67_72_74_75.py

Prereq: enriched chip histories have been built
    (biotite build-all-histories && biotite enrich-history <N>).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig
from src.plotting.plot_utils import (
    _savgol_derivative_corrected,
    ensure_standard_columns,
    segment_voltage_sweep,
)
from src.plotting.styles import set_plot_style
from src.plotting.transconductance import auto_select_savgol_params

HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_PATH = Path("figs/compare/alisson67_72_74_75_80_81_IVg_first.png")
OUTPUT_PATH_DERIV = Path(
    "figs/compare/alisson67_72_74_75_80_81_dIdVg_first.png"
)

CHIPS = [
    # Reds: hBN group
    {"chip_number": 67, "label": "67 (hBN)", "color": "#8B0000"},
    {"chip_number": 72, "label": "72 (hBN)", "color": "#d62728"},
    # Blues: Biotite group A
    {"chip_number": 74, "label": "74 (Biotite)", "color": "#4292c6"},
    {"chip_number": 75, "label": "75 (Biotite)", "color": "#08306B"},
    # Greens: Biotite group B
    {"chip_number": 80, "label": "80 (Biotite)", "color": "#2ca02c"},
    {"chip_number": 81, "label": "81 (Biotite)", "color": "#66bd63"},
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


def _first_half_sweep(vg: np.ndarray) -> slice:
    """0 -> Vgmin -> 0 -> Vgmax -> 0 (first half of the full IVg sweep)."""
    i_max = int(np.argmax(vg))
    tail = vg[i_max:]
    below = np.where(tail <= 0.0)[0]
    end = i_max + int(below[0]) if below.size else len(vg) - 1
    return slice(0, end + 1)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    curves: list[tuple[str, str, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        vg, i_uA = load_first_ivg(chip["chip_number"], chip["label"])
        curves.append((chip["label"], chip["color"], vg, i_uA))

    # --- I vs Vg ---
    fig, ax = plt.subplots(figsize=(20, 20))
    for label, color, vg, i_uA in curves:
        ax.plot(vg, i_uA, label=label, color=color, linewidth=2.7)

    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    ax.set_ylim(bottom=0)
    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PATH, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUTPUT_PATH}")

    # --- dI/dVg vs Vg (first-half sweep, Sav-Gol smoothed) ---
    fig, ax = plt.subplots(figsize=(20, 20))
    for label, color, vg, i_uA in curves:
        s = _first_half_sweep(vg)
        vg_h = vg[s]
        i_h = i_uA[s]

        # Split into monotonic sub-sweeps so gm doesn't flip sign at Vg
        # turning points; each sub-sweep gets its own SG derivative with the
        # correct (signed) Vg spacing.
        first = True
        for vg_seg, i_seg, _direction in segment_voltage_sweep(vg_h, i_h):
            window, polyorder = auto_select_savgol_params(vg_seg, i_seg, "auto")
            gm = _savgol_derivative_corrected(
                vg_seg, i_seg, window_length=window, polyorder=polyorder
            )
            ax.plot(
                vg_seg,
                gm,
                color=color,
                linewidth=2.7,
                label=label if first else None,
            )
            first = False

    ax.axhline(0.0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{dI_{ds}/dV_g\\ (\\mu A/V)}$")
    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(OUTPUT_PATH_DERIV, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {OUTPUT_PATH_DERIV}")


if __name__ == "__main__":
    main()
