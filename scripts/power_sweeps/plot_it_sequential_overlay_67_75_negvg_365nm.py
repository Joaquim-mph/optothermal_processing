"""
Sequential raw It traces with drift-corrected inset for Alisson67 (hBN) and
Alisson75 (Biotite) at their negative gate voltage, wavelength = 365 nm.

Selection (negative-Vg group, 4 lowest powers) taken from
scripts/power_sweeps/plot_corrected_deltai_vs_power_67_75_vg_365nm.py:

    Alisson67: 2025-10-14, seq 41-44, Vg = -0.4 V
    Alisson75: 2025-09-12, seq 5-8,   Vg = -3.0 V

Powers: 6, 12, 18, 24 µW (365 nm) in both groups.

Each figure stitches the 4 raw It segments end-to-end (single color per chip)
and adds an inset with the drift-corrected overlay: a stretched-exponential
fit on t in [1, 60] s is subtracted from each trace, then the segments are
shown colored by power (plasma_r) with the light window shaded.

Run from repo root:
    python scripts/power_sweeps/plot_it_sequential_overlay_67_75_negvg_365nm.py
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

FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 365.0

GROUPS: list[dict] = [
    {
        "chip": 67,
        "label": r"hBN, $V_g=-0.4$ V",
        "color": "#377eb8",
        "marker": "o",
        "date": "2025-10-14",
        "seqs": [41, 42, 43, 44],
    },
    {
        "chip": 75,
        "label": r"Biotite, $V_g=-3.0$ V",
        "color": "#e41a1c",
        "marker": "s",
        "date": "2025-09-12",
        "seqs": [5, 6, 7, 8],
    },
]


def rows_for_group(hist: pl.DataFrame, group: dict) -> pl.DataFrame:
    return hist.filter(
        pl.col("seq").is_in(group["seqs"]),
        pl.col("date") == group["date"],
        pl.col("proc") == "It",
        pl.col("has_light"),
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")


def plot_it_overlay(config: PlotConfig, hist: pl.DataFrame, group: dict) -> None:
    rows = rows_for_group(hist, group)
    if rows.height == 0:
        print(f"[warn] no It traces for {group['label']}")
        return

    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))

    n = rows.height
    line_color = group.get("color", "#d62728")

    seg_t: list[np.ndarray] = []
    seg_I_corr: list[np.ndarray] = []
    all_y: list[float] = []
    time_offset = 0.0
    label_used = False

    for row in rows.iter_rows(named=True):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size == 0:
            continue

        # Drift-corrected trace for the inset
        mask = (t >= FIT_T_START) & (t <= FIT_T_END)
        if mask.sum() >= 10:
            fit = fit_stretched_exponential(t[mask], I[mask])
            drift = stretched_exponential(
                t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
            )
            I_corr = I - drift
            idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
            I_corr = I_corr - I_corr[idx_pre]
        else:
            idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
            I_corr = I - I[idx_pre]

        seg_t.append(t.copy())
        seg_I_corr.append(I_corr * 1e6)

        # Sequential raw trace: zero-base each segment, drop first sample
        # (instrument glitch on It restart), single color per group.
        t_seg = t - t[0]
        y_seg = I * 1e6
        if t_seg.size > 1:
            t_seg = t_seg[1:]
            y_seg = y_seg[1:]

        ax.plot(
            t_seg + time_offset,
            y_seg,
            color=line_color,
            linewidth=2.0,
            label=group["label"] if not label_used else None,
        )
        label_used = True
        all_y.extend(y_seg.tolist())

        time_offset += float(t_seg[-1])

    ax.set_xlabel(r"t (s)")
    ax.set_ylabel(r"$I_{ds}\ (\mu\mathrm{A})$")
    ax.legend(loc="best", framealpha=0.9)

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_xlim(0.0, time_offset)

    # --- inset: drift-corrected overlay, plasma_r by power ---
    inset = ax.inset_axes([0.12, 0.14, 0.3, 0.3])
    inset.tick_params(axis="both", labelsize="medium")
    cmap = mpl.colormaps["plasma_r"]
    cmap_levels = np.linspace(0.15, 1.0, max(1, n))

    inset_t_totals: list[float] = []

    for i, (t_full, ic_uA) in enumerate(zip(seg_t, seg_I_corr)):
        color = cmap(cmap_levels[i])
        inset.plot(t_full, ic_uA, color=color, linewidth=1.5)
        inset_t_totals.append(float(t_full[-1]))

    inset.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha)

    x_lo = 50.0
    x_hi = None
    if inset_t_totals:
        T_total = float(np.median(inset_t_totals))
        if np.isfinite(T_total) and T_total > 0:
            x_hi = T_total
            inset.set_xlim(x_lo, x_hi)
    inset.set_xticks([60, 120, 180])

    visible_y: list[float] = []
    for t_full, ic_uA in zip(seg_t, seg_I_corr):
        m = t_full >= x_lo
        if x_hi is not None:
            m &= t_full <= x_hi
        visible_y.extend(ic_uA[m].tolist())
    if visible_y:
        y = np.array(visible_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                inset.set_ylim(y_min - pad, y_max + pad)

    inset.set_xlabel(r"$t\ (\mathrm{s})$", fontsize="medium")
    inset.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$", fontsize="medium")

    y_lo, y_hi = inset.get_ylim()
    arrow_top = y_hi - 0.10 * (y_hi - y_lo)
    arrow_bot = y_lo + 0.10 * (y_hi - y_lo)
    inset.annotate(
        "",
        xy=(90, arrow_bot),
        xytext=(90, arrow_top),
        arrowprops=dict(arrowstyle="->", color="k", lw=1.5),
    )
    inset.text(
        92,
        0.5 * (arrow_top + arrow_bot),
        "P",
        va="center",
        ha="left",
        fontsize="medium",
    )

    plt.tight_layout()

    seq_tag = "_".join(str(s) for s in group["seqs"])
    filename = (
        f"Alisson{group['chip']}_It_sequential_with_overlay_365nm_negVg_seq_{seq_tag}"
    )
    out = config.get_output_path(
        filename,
        chip_number=group["chip"],
        procedure="It",
        metadata={"has_light": True},
        special_type="photoresponse",
        create_dirs=True,
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    for group in GROUPS:
        hist = pl.read_parquet(
            Path(
                f"data/03_derived/chip_histories_enriched/Alisson{group['chip']}_history.parquet"
            )
        )
        plot_it_overlay(config, hist, group)


if __name__ == "__main__":
    main()
