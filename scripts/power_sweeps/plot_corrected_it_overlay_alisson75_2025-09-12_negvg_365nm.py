"""
Drift-corrected I(t) overlay for Alisson75 (Biotite) at 365 nm, 2025-09-12,
Vg = -3.0 V.

Seqs 5-8, powers 6, 12, 18, 24 µW (365 nm). Selection matches the negative-Vg
group of scripts/power_sweeps/plot_corrected_deltai_vs_power_67_75_vg_365nm.py
and is the standalone version of the inset in
scripts/power_sweeps/plot_it_sequential_overlay_67_75_negvg_365nm.py.

Stretched-exponential drift fit on t in [FIT_T_START, FIT_T_END] is subtracted
from each trace, then the corrected trace is anchored to zero at t = EVAL_T_PRE.
Traces are overlaid on a single axis colored by power (plasma_r), with the
light window shaded between EVAL_T_PRE and EVAL_T_POST.

Run from repo root:
    python scripts/power_sweeps/plot_corrected_it_overlay_alisson75_2025-09-12_negvg_365nm.py
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
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

CHIP = 75
DATE = "2025-09-12"
SEQS = [5, 6, 7, 8]
VG = -3.0
WAVELENGTH_NM = 365.0

FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0

# Laser spot area (µm²). The measured beam power is spread over this spot; the
# effective power on the device is P_eff = P_beam · (A_device / A_beam), with
# A_device read from config/encap_characteristics.yaml.
BEAM_AREA_UM2 = 1e5
ENCAP_YAML = Path("config/encap_characteristics.yaml")

# Dedicated output folder for this script's figure.
OUTPUT_DIR = Path("figs/power_sweeps/corrected_it_overlay_75_negvg_365nm")


def rows_for_chip(hist: pl.DataFrame) -> pl.DataFrame:
    return hist.filter(
        pl.col("seq").is_in(SEQS),
        pl.col("date") == DATE,
        pl.col("proc") == "It",
        pl.col("has_light"),
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")


def device_area_um2(chip: int) -> float | None:
    """Flake area (µm²) for `chip` from config/encap_characteristics.yaml."""
    import yaml

    if not ENCAP_YAML.exists():
        return None
    data = yaml.safe_load(ENCAP_YAML.read_text()) or {}
    entry = data.get(chip)
    if isinstance(entry, dict) and "flake_area_um2" in entry:
        return float(entry["flake_area_um2"])
    return None


def corrected_trace(t: np.ndarray, I: np.ndarray) -> np.ndarray:
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
    return I_corr - I_corr[idx_pre]


def main() -> None:
    # Route the figure into one dedicated folder (no chip/proc/subcategory
    # hierarchy) by overriding output_dir and disabling the subdir levels.
    config = PlotConfig(
        output_dir=OUTPUT_DIR,
        chip_subdir_enabled=False,
        use_proc_subdirs=False,
        auto_subcategories=False,
    )
    set_plot_style(config.theme)

    hist = pl.read_parquet(
        Path(f"data/03_derived/chip_histories_enriched/Alisson{CHIP}_history.parquet")
    )
    rows = rows_for_chip(hist)
    print(rows.select(["seq", "vg_fixed_v", "irradiated_power_w", "wavelength_nm"]))
    if rows.height == 0:
        print("[warn] no matching rows")
        return

    area_um2 = device_area_um2(CHIP)
    if area_um2 is None:
        print(f"[warn] no flake_area_um2 for chip {CHIP}; legend will show beam power")
    # Fraction of beam power that lands on the device.
    p_eff_frac = (area_um2 / BEAM_AREA_UM2) if area_um2 is not None else 1.0

    fig, ax = plt.subplots(figsize=(20, 20))
    n = rows.height
    cmap = mpl.colormaps["plasma_r"]
    cmap_levels = np.linspace(0.15, 1.0, max(1, n))

    seg_t: list[np.ndarray] = []
    seg_I_corr_uA: list[np.ndarray] = []
    powers_uW: list[float] = []

    for i, row in enumerate(rows.iter_rows(named=True)):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size == 0:
            continue

        I_corr_uA = corrected_trace(t, I) * 1e6
        p_uW = float(row["irradiated_power_w"]) * 1e6
        # Effective power on the device, in nW.
        p_eff_nW = p_uW * p_eff_frac * 1e3

        ax.plot(
            t,
            I_corr_uA,
            color=cmap(cmap_levels[i]),
            linewidth=4.0,
            label=f"{p_eff_nW:.1f} nW",
        )
        seg_t.append(t)
        seg_I_corr_uA.append(I_corr_uA)
        powers_uW.append(p_uW)

    ax.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha)
    ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)

    # x range and ticks match the inset style
    x_lo = 50.0
    t_totals = [float(t[-1]) for t in seg_t]
    x_hi = float(np.median(t_totals)) if t_totals else None
    if x_hi is not None and np.isfinite(x_hi) and x_hi > x_lo:
        ax.set_xlim(x_lo, x_hi)
    ax.set_xticks([60, 120, 180])

    # y autoscale to visible window
    visible_y: list[float] = []
    for t, y in zip(seg_t, seg_I_corr_uA):
        m = t >= x_lo
        if x_hi is not None:
            m &= t <= x_hi
        visible_y.extend(y[m].tolist())
    if visible_y:
        y = np.array(visible_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{ph}}\ (\mu\mathrm{A})$")

    legend_fontsize = plt.rcParams["legend.fontsize"] + 2
    ax.legend(
        loc="best",
        framealpha=0.9,
        fontsize=legend_fontsize,
        title=r"$P_{\mathrm{eff}}$",
        title_fontsize=legend_fontsize,
    )
    plt.tight_layout()

    seq_tag = "_".join(str(s) for s in SEQS)
    filename = f"Alisson{CHIP}_It_corrected_overlay_seq_{seq_tag}_{DATE}_365nm"
    out = config.get_output_path(
        filename,
        chip_number=CHIP,
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
