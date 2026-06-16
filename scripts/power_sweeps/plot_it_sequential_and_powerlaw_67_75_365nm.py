"""
Composite 3-panel figure for Alisson67 (hBN) and Alisson75 (Biotite), 365 nm.

Left column (two stacked panels, shared x):
    Sequential raw It traces (4 segments stitched end-to-end) at negative Vg
    (holes), one material per panel. Biotite (chip 75) on top, hBN (chip 67)
    on bottom. No overlay inset.

Right panel:
    |Δi_corrected| vs LED power on a semilog-y axis with independent power-law
    fits, for holes (negative Vg) and electrons (positive Vg) of both
    materials. γ is the power-law exponent (|Δi| ∝ P^γ).

Selection and correction logic come from
scripts/power_sweeps/plot_corrected_deltai_vs_power_67_75_vg_365nm.py.

Figure layout: 40x20 overall; each sequential panel 20x10, power-law 20x20.

Run from repo root:
    python scripts/power_sweeps/plot_it_sequential_and_powerlaw_67_75_365nm.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.lines import Line2D
from matplotlib.transforms import blended_transform_factory

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

FIT_T_START = 20.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 365.0

# All outputs of this script land in this dedicated folder under figs/, with no
# chip/procedure/subcategory hierarchy (these comparisons span two chips).
OUTPUT_SUBDIR = Path("figs/it_sequential_and_powerlaw_67_75_365nm")

# Sequential It panels (holes / negative Vg), drawn top -> bottom.
SEQUENTIAL: list[dict] = [
    {
        "chip": 75,
        "label": r"Biotite, $V_g=-3.0$ V",
        "color": "#e41a1c",
        "date": "2025-09-12",
        "seqs": [5, 6, 7, 8],
    },
    {
        "chip": 67,
        "label": r"hBN, $V_g=-0.4$ V",
        "color": "#377eb8",
        "date": "2025-10-14",
        "seqs": [41, 42, 43, 44],
    },
]

# Power-law panel: both gate polarities for both chips.
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
    rows = hist.filter(
        pl.col("seq").is_in(group["seqs"]),
        pl.col("date") == date,
        pl.col("proc") == "It",
        pl.col("has_light"),
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")
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


def plot_sequential(
    ax: plt.Axes,
    hist: pl.DataFrame,
    group: dict,
    config: PlotConfig,
    annotate_led: bool = True,
) -> float:
    """Stitch the raw It segments end-to-end. When ``annotate_led`` is set,
    shade each LED-on window and label its power. Returns total stitched time."""
    rows = hist.filter(
        pl.col("seq").is_in(group["seqs"]),
        pl.col("date") == group["date"],
        pl.col("proc") == "It",
        pl.col("has_light"),
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")
    if rows.height == 0:
        print(f"[warn] no It traces for {group['label']}")
        return 0.0

    line_color = group["color"]
    all_y: list[float] = []
    time_offset = 0.0
    label_used = False
    led_spans: list[tuple[float, float, float]] = []  # (x_on0, x_on1, power_uW)

    for row in rows.iter_rows(named=True):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        vl = meas["VL (V)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I, vl = t[finite], I[finite], vl[finite]
        if t.size == 0:
            continue

        # LED-on window for this segment (VL >= 0.1 V = illuminated).
        t0 = float(t[0])
        on = vl >= 0.1
        if on.any():
            x_on0 = float(t[on][0]) - t0 + time_offset
            x_on1 = float(t[on][-1]) - t0 + time_offset
            led_spans.append((x_on0, x_on1, float(row["irradiated_power_w"]) * 1e6))

        # Zero-base each segment; drop first sample (instrument glitch on restart).
        t_seg = t - t0
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

    ax.set_ylabel(r"$I_{ds}\ (\mu\mathrm{A})$")
    ax.legend(loc="best", framealpha=0.9)

    y = np.array([v for v in all_y if np.isfinite(v)], dtype=float)
    if y.size:
        y_min, y_max = float(y.min()), float(y.max())
        if y_max > y_min:
            pad = 0.05 * (y_max - y_min)
            ax.set_ylim(y_min - pad, y_max + pad)

    # Shade each LED-on window and label its power above the band.
    if annotate_led:
        blend = blended_transform_factory(ax.transData, ax.transAxes)
        for x0, x1, power in led_spans:
            ax.axvspan(x0, x1, color="0.7", alpha=config.light_window_alpha, lw=0)
            ax.text(
                0.5 * (x0 + x1),
                0.93,
                f"{power:.0f} µW",
                transform=blend,
                ha="center",
                va="top",
                fontsize=22,
                fontweight="bold",
            )
    return time_offset


def plot_power_law(
    ax: plt.Axes, curves: list[tuple[dict, dict, np.ndarray, np.ndarray]]
) -> None:
    for chip, group, p, di in curves:
        is_electrons = group["vg_v"] >= 0
        marker = "+" if is_electrons else "_"
        di_abs = np.abs(di)
        gamma, p_fit, di_fit = power_law_fit(p, di_abs)
        label = f"{chip['label']}, $V_g$={group['vg_v']:+g} V, $\\gamma={gamma:.2f}$"
        ax.plot(
            p,
            di_abs,
            marker=marker,
            linestyle="none",
            color=chip["color"],
            markersize=25,
            markeredgewidth=9,
            label=label,
        )
        if p_fit.size:
            ax.plot(p_fit, di_fit, linestyle="-", color=chip["color"], linewidth=1.2)
        print(
            f"Alisson{chip['chip']} Vg={group['vg_v']:+g} V  n={p.size}  "
            f"P=[{p.min():.2f},{p.max():.2f}] µW  "
            f"|Δi_corr|=[{di_abs.min():.3g},{di_abs.max():.3g}] µA  γ={gamma:.3f}"
        )

    ax.set_yscale("log")
    ax.set_xticks([6, 12, 18, 24])
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    # Legend position in axes fraction (0,0 = bottom-left, 1,1 = top-right).
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0.52, 0.8),
        bbox_transform=ax.transAxes,
        framealpha=0.9,
    )


def annotate_panel_letter(ax: plt.Axes, letter: str) -> None:
    """Stamp a bold panel letter outside the axes, above the y-axis label."""
    ax.text(
        -0.13,
        1.0,
        letter,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontweight="bold",
        fontsize=56,
    )


def build_figure(
    config: PlotConfig,
    histories: dict[int, pl.DataFrame],
    curves: list[tuple[dict, dict, np.ndarray, np.ndarray]],
    *,
    annotate_led: bool,
    filename: str,
) -> None:
    fig = plt.figure(figsize=(40, 20))
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[1, 1])
    ax_bio = fig.add_subplot(gs[0, 0])
    ax_hbn = fig.add_subplot(gs[1, 0], sharex=ax_bio)
    ax_pl = fig.add_subplot(gs[:, 1])

    totals: list[float] = []
    for ax, group in zip([ax_bio, ax_hbn], SEQUENTIAL):
        totals.append(
            plot_sequential(
                ax, histories[group["chip"]], group, config, annotate_led=annotate_led
            )
        )

    ax_bio.tick_params(axis="x", labelbottom=False)
    ax_hbn.set_xlabel(r"t (s)")
    ax_bio.set_xlim(0.0, max([t for t in totals if t > 0], default=1.0))

    plot_power_law(ax_pl, curves)

    annotate_panel_letter(ax_bio, "a")
    annotate_panel_letter(ax_hbn, "b")
    annotate_panel_letter(ax_pl, "c")

    plt.tight_layout()
    out = config.get_output_path(filename, create_dirs=True)
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def build_powerlaw_only_figure(
    config: PlotConfig,
    curves: list[tuple[dict, dict, np.ndarray, np.ndarray]],
    *,
    filename: str,
) -> None:
    """Standalone semilog-y |Δi_corr| vs LED power figure (panel c only)."""
    fig, ax = plt.subplots(figsize=(20, 20))
    plot_power_law(ax, curves)
    plt.tight_layout()
    out = config.get_output_path(filename, create_dirs=True)
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_corrected_overlay(
    ax: plt.Axes, hist: pl.DataFrame, group: dict, config: PlotConfig
) -> list[tuple[float, tuple]]:
    """Drift-corrected I(t) overlay for one chip: stretched-exp fit on
    [FIT_T_START, FIT_T_END] subtracted, re-zeroed at EVAL_T_PRE, traces colored
    by power (plasma). Returns [(power_uW, rgba), ...] for a shared legend."""
    rows = hist.filter(
        pl.col("seq").is_in(group["seqs"]),
        pl.col("date") == group["date"],
        pl.col("proc") == "It",
        pl.col("has_light"),
        pl.col("wavelength_nm") == WAVELENGTH_NM,
    ).sort("irradiated_power_w")
    if rows.height == 0:
        print(f"[warn] no It traces for {group['label']}")
        return []

    seg_t: list[np.ndarray] = []
    seg_I_corr: list[np.ndarray] = []
    seg_power: list[float] = []
    for row in rows.iter_rows(named=True):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size == 0:
            continue

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

        seg_t.append(t)
        seg_I_corr.append(I_corr * 1e6)
        seg_power.append(float(row["irradiated_power_w"]) * 1e6)

    n = len(seg_t)
    cmap = mpl.colormaps["plasma"]
    cmap_levels = np.linspace(0.15, 0.85, max(1, n))

    legend_info: list[tuple[float, tuple]] = []
    t_totals: list[float] = []
    for i, (t_full, ic_uA) in enumerate(zip(seg_t, seg_I_corr)):
        color = cmap(cmap_levels[i])
        ax.plot(t_full, ic_uA, color=color, linewidth=4.0)
        t_totals.append(float(t_full[-1]))
        legend_info.append((seg_power[i], color))

    ax.axvspan(
        EVAL_T_PRE, EVAL_T_POST, color="0.7", alpha=config.light_window_alpha, lw=0
    )

    x_lo = 50.0
    x_hi = None
    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            x_hi = T_total
            ax.set_xlim(x_lo, x_hi)
    ax.set_xticks([60, 120, 180])

    visible_y: list[float] = []
    for t_full, ic_uA in zip(seg_t, seg_I_corr):
        m = t_full >= x_lo
        if x_hi is not None:
            m &= t_full <= x_hi
        visible_y.extend(ic_uA[m].tolist())
    y = np.array([v for v in visible_y if np.isfinite(v)], dtype=float)
    if y.size:
        y_min, y_max = float(y.min()), float(y.max())
        if y_max > y_min:
            pad = config.padding_fraction * (y_max - y_min)
            ax.set_ylim(y_min - pad, y_max + pad)

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    return legend_info


def build_overlay_figure(
    config: PlotConfig, histories: dict[int, pl.DataFrame]
) -> None:
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(40, 20))

    legend_info: list[tuple[float, tuple]] = []
    for ax, group in zip([ax_a, ax_b], SEQUENTIAL):
        info = plot_corrected_overlay(ax, histories[group["chip"]], group, config)
        if info and not legend_info:
            legend_info = info

    annotate_panel_letter(ax_a, "a")
    annotate_panel_letter(ax_b, "b")

    if legend_info:
        handles = [
            Line2D([0], [0], color=color, lw=10.0, label=f"{power:.0f} µW")
            for power, color in legend_info
        ]
        fig.legend(
            handles=handles,
            title="LED power",
            loc="lower center",
            bbox_to_anchor=(0.5, -0.04),
            ncol=len(handles),
            framealpha=0.9,
            fontsize=34,
            title_fontsize=38,
        )
    plt.tight_layout()

    out = config.get_output_path(
        "Alisson67_75_corrected_overlay_holes_365nm_1x2", create_dirs=True
    )
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    # Route all outputs to a dedicated flat folder under figs/, bypassing the
    # default chip/procedure/subcategory hierarchy.
    config = PlotConfig(
        output_dir=OUTPUT_SUBDIR,
        chip_subdir_enabled=False,
        use_proc_subdirs=False,
        auto_subcategories=False,
    )
    set_plot_style(config.theme)

    histories = {
        chip: pl.read_parquet(
            Path(
                f"data/03_derived/chip_histories_enriched/Alisson{chip}_history.parquet"
            )
        )
        for chip in {g["chip"] for g in SEQUENTIAL} | {c["chip"] for c in CHIPS}
    }

    curves: list[tuple[dict, dict, np.ndarray, np.ndarray]] = []
    for chip in CHIPS:
        hist = histories[chip["chip"]]
        for group in chip["vg_groups"]:
            p, di = curve_for_group(hist, chip["date"], group)
            if p.size == 0:
                print(f"[warn] no data for Alisson{chip['chip']} Vg={group['vg_v']}")
                continue
            curves.append((chip, group, p, di))

    # Original (no LED/power annotation) — kept alongside the annotated version.
    build_figure(
        config,
        histories,
        curves,
        annotate_led=False,
        filename="Alisson67_75_It_sequential_holes_and_powerlaw_365nm",
    )
    # Annotated version: shaded LED-on windows + per-segment power labels.
    build_figure(
        config,
        histories,
        curves,
        annotate_led=True,
        filename="Alisson67_75_It_sequential_holes_and_powerlaw_365nm_led",
    )
    # Standalone semilog-y power-law panel only (matches panel c of the composite).
    build_powerlaw_only_figure(
        config,
        curves,
        filename="Alisson67_75_powerlaw_365nm",
    )
    # Standalone 1x2 drift-corrected I(t) overlay (a = Biotite, b = hBN).
    build_overlay_figure(config, histories)


if __name__ == "__main__":
    main()
