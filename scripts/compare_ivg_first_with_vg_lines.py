"""
First-IVg overlay for six Alisson chips (67/72 hBN, 74/75/80/81 biotite),
with the IVg picked from the same calendar day as the chip's wavelength-sweep
It traces (seq lists from scripts/compare_corrected_It_67_72_74_75_80_81_pairs.py).

Outputs (figs/compare/):
    alisson67_72_74_75_80_81_IVg_first.png            (plain I vs Vg)
    alisson67_72_74_75_80_81_IVg_first_with_Vg.png    (+ dashed Vg lines)
    alisson67_72_74_75_80_81_dIdVg_first.png          (Sav-Gol derivative)
    alisson{a}_{b}_IVg_first_with_Vg.png              (per pair, with Vg lines)

Run from repo root:
    python scripts/compare_ivg_first_with_vg_lines.py
"""

from __future__ import annotations

from datetime import datetime, timezone
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
OUTPUT_PATH_PLAIN = Path("figs/compare/alisson67_72_74_75_80_81_IVg_first.png")
OUTPUT_PATH = Path("figs/compare/alisson67_72_74_75_80_81_IVg_first_with_Vg.png")
OUTPUT_PATH_DERIV = Path("figs/compare/alisson67_72_74_75_80_81_dIdVg_first.png")
PAIR_OUTPUT_DIR = Path("figs/compare")
PAIRS = [(67, 72), (74, 75), (80, 81)]

# Vg-line source: It-sweep seqs from the corrected-It comparison script
IT_SEQS = {
    67: [4, 15, 27, 41, 103, 102, 100, 98, 96, 94],
    72: [103, 105, 107, 112, 114, 116, 118, 120, 122, 124],
    74: [5, 7, 9, 11, 13, 17, 20, 22, 24, 28],
    75: [62, 64, 69, 71, 73, 75, 77, 81, 83, 85],
    80: [95, 97, 99, 101, 103, 105, 107, 109, 111, 113],
    81: [4, 6, 8, 10, 12, 14, 16, 18, 33, 35],
}

CHIPS = [
    {"chip_number": 67, "label": "67 (hBN)", "color": "#8B0000"},  # dark red
    {"chip_number": 72, "label": "72 (hBN)", "color": "#ff7f0e"},  # orange
    {"chip_number": 74, "label": "74 (Biotite)", "color": "#08306B"},  # dark blue
    {"chip_number": 75, "label": "75 (Biotite)", "color": "#17becf"},  # cyan
    {"chip_number": 80, "label": "80 (Biotite)", "color": "#2ca02c"},  # green
    {"chip_number": 81, "label": "81 (Biotite)", "color": "#9467bd"},  # purple
]


def _target_date(history: pl.DataFrame, chip_number: int, seqs: list[int]):
    """Day of the earliest It trace among the wavelength-sweep seqs."""
    it = (
        history.filter(pl.col("seq").is_in(seqs))
        .filter(pl.col("proc") == "It")
        .sort("start_time")
    )
    if it.height == 0:
        raise ValueError(f"chip {chip_number}: no It rows for seqs {seqs}")
    t = it["start_time"].to_list()[0]
    return datetime.fromtimestamp(t, tz=timezone.utc).date()


def load_first_ivg(chip_number: int, label: str) -> tuple[np.ndarray, np.ndarray]:
    history_path = HISTORY_DIR / f"Alisson{chip_number}_history.parquet"
    if not history_path.exists():
        raise FileNotFoundError(
            f"Enriched history not found for chip {chip_number} at {history_path}. "
            f"Run: biotite enrich-history {chip_number}"
        )

    history = pl.read_parquet(history_path)
    target = _target_date(history, chip_number, IT_SEQS[chip_number])

    ivg = history.filter(pl.col("proc") == "IVg").sort("start_time")
    if ivg.height == 0:
        raise ValueError(f"[{label}] no IVg measurements found in history.")

    first = None
    for row in ivg.iter_rows(named=True):
        d = datetime.fromtimestamp(row["start_time"], tz=timezone.utc).date()
        if d == target:
            first = row
            break
    if first is None:
        raise ValueError(f"[{label}] no IVg on target date {target}")
    parquet_path = Path(first.get("parquet_path") or first.get("source_file") or "")
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"[{label}] measurement file missing for seq={first['seq']}: {parquet_path}"
        )

    measurement = ensure_standard_columns(read_measurement_parquet(parquet_path))
    if not {"VG", "I"} <= set(measurement.columns):
        raise ValueError(
            f"[{label}] seq={first['seq']} missing VG/I columns. Got: {measurement.columns}"
        )

    vg = measurement["VG"].to_numpy()
    i_uA = measurement["I"].to_numpy() * 1e6
    print(
        f"[{label}] chip={chip_number} seq={first['seq']} date={target} "
        f"n_points={len(vg)} Vg_range=[{vg.min():.2f}, {vg.max():.2f}] V "
        f"I_range=[{i_uA.min():.3g}, {i_uA.max():.3g}] µA"
    )
    return vg, i_uA


def lookup_it_vg(chip_number: int, seqs: list[int]) -> float | None:
    history_path = HISTORY_DIR / f"Alisson{chip_number}_history.parquet"
    history = pl.read_parquet(history_path)
    rows = history.filter(pl.col("seq").is_in(seqs)).filter(pl.col("proc") == "It")
    if rows.height == 0 or "vg_fixed_v" not in rows.columns:
        return None
    vgs = [v for v in rows["vg_fixed_v"].to_list() if v is not None]
    if not vgs:
        return None
    return float(np.median(vgs))


def _first_half_sweep(vg: np.ndarray) -> slice:
    """0 -> Vgmin -> 0 -> Vgmax -> 0 (first half of the full IVg sweep)."""
    i_max = int(np.argmax(vg))
    tail = vg[i_max:]
    below = np.where(tail <= 0.0)[0]
    end = i_max + int(below[0]) if below.size else len(vg) - 1
    return slice(0, end + 1)


def _plot_chip(
    ax,
    chip: dict,
    vg: np.ndarray,
    i_uA: np.ndarray,
    *,
    with_vg_line: bool,
) -> None:
    ax.plot(vg, i_uA, label=chip["label"], color=chip["color"], linewidth=2.7)
    if not with_vg_line:
        return
    vg_used = lookup_it_vg(chip["chip_number"], IT_SEQS[chip["chip_number"]])
    if vg_used is not None:
        ax.axvline(
            vg_used,
            color=chip["color"],
            linestyle="--",
            linewidth=1.8,
            alpha=0.85,
        )
        print(f"[{chip['label']}] It-sweep Vg = {vg_used:g} V")
    else:
        print(
            f"[{chip['label']}] no Vg found for It seqs {IT_SEQS[chip['chip_number']]}"
        )


def _finalize_iv_axes(ax) -> None:
    ax.set_xlabel("$\\rm{V_g\\ (V)}$")
    ax.set_ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    ax.set_ylim(bottom=0)
    ax.legend(loc="best", framealpha=0.9)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    chip_by_num = {c["chip_number"]: c for c in CHIPS}

    # Load all curves once.
    curves: dict[int, tuple[np.ndarray, np.ndarray]] = {
        chip["chip_number"]: load_first_ivg(chip["chip_number"], chip["label"])
        for chip in CHIPS
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Combined I vs Vg, plain + with-Vg.
    for out_path, with_vg in ((OUTPUT_PATH_PLAIN, False), (OUTPUT_PATH, True)):
        fig, ax = plt.subplots(figsize=(20, 20))
        for chip in CHIPS:
            vg, i_uA = curves[chip["chip_number"]]
            _plot_chip(ax, chip, vg, i_uA, with_vg_line=with_vg)
        _finalize_iv_axes(ax)
        plt.tight_layout()
        plt.savefig(out_path, dpi=config.dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"saved {out_path}")

    # dI/dVg derivative (first-half sweep, Sav-Gol smoothed, per monotonic segment).
    fig, ax = plt.subplots(figsize=(20, 20))
    for chip in CHIPS:
        vg, i_uA = curves[chip["chip_number"]]
        s = _first_half_sweep(vg)
        first = True
        for vg_seg, i_seg, _direction in segment_voltage_sweep(vg[s], i_uA[s]):
            window, polyorder = auto_select_savgol_params(vg_seg, i_seg, "auto")
            gm = _savgol_derivative_corrected(
                vg_seg, i_seg, window_length=window, polyorder=polyorder
            )
            ax.plot(
                vg_seg,
                gm,
                color=chip["color"],
                linewidth=2.7,
                label=chip["label"] if first else None,
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

    # Pair figures (with Vg lines).
    for a, b in PAIRS:
        fig, ax = plt.subplots(figsize=(20, 20))
        for n in (a, b):
            vg, i_uA = curves[n]
            _plot_chip(ax, chip_by_num[n], vg, i_uA, with_vg_line=True)
        _finalize_iv_axes(ax)
        plt.tight_layout()
        out = PAIR_OUTPUT_DIR / f"alisson{a}_{b}_IVg_first_with_Vg.png"
        plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"saved {out}")


if __name__ == "__main__":
    main()
