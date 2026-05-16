"""
Photoresponse (|Δi_corrected|) vs laser power on semilog-y axes for the
2026-05-15 365 nm "power law" It sweeps — re-measurement at lower powers
(1-6 µW) intended to land below the channel-current saturation seen on
2026-05-14 (6-24 µW).

Chips / fixed gate voltage (all 365 nm):
    68  Vg = -0.9  V   (1-6 µW; one stray Vg=-0.7 trace at 1 µW dropped)
    74  Vg = -0.7  V   (3-6 µW)
    75  Vg = -0.5  V   (3-6 µW)
    76  Vg = -1.0  V   (3-6 µW)
    72  Vg = -0.5  V   (3-5 µW)
        ^ NOTE: raw CSVs for chip 72 on 2026-05-15 are mislabeled as
        Chip number: 67. Until the headers are fixed and the pipeline is
        re-run, the script reads chip 72's traces out of Alisson67_history.

Two comparison figures are produced: one with chip 72 and one without.

Run from repo root:
    python scripts/plot_photoresponse_vs_power_semilogy_2026-05-15.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 365.0
DATE = "2026-05-15"
OUTPUT_DIR = Path(f"figs/photoresponse_power_law_{DATE}_365nm")
ENCAP_YAML = Path("config/encap_characteristics.yaml")


def _load_chip_materials() -> dict[int, str]:
    if not ENCAP_YAML.exists():
        return {}
    with ENCAP_YAML.open("r") as f:
        data = yaml.safe_load(f) or {}
    out: dict[int, str] = {}
    for k, v in data.items():
        if isinstance(k, int) and isinstance(v, dict) and v.get("material"):
            out[k] = str(v["material"])
    return out


_CHIP_MATERIALS = _load_chip_materials()


def label_for_chip(chip: dict, include_material: bool = True) -> str:
    n = chip["chip"]
    mat = _CHIP_MATERIALS.get(n) if include_material else None
    vg = chip.get("vg_filter")
    mat_part = f" ({mat})" if mat else ""
    vg_part = f" $V_g={vg:g}$ V" if vg is not None else ""
    return f"{n}{mat_part}{vg_part}"


# history_chip: which Alisson{N}_history.parquet to read from (defaults to chip).
# vg_filter: required vg_fixed_v value to disambiguate when multiple Vg sweeps
#            exist on the same date.
# gamma_anchor: "left" (default, leftmost point) or "right" (rightmost point).
# gamma_xy_offset: (dx, dy) offset in display points for the gamma annotation.
# gamma_axes_xy: (x, y) in axes-fraction [0, 1] -- absolute position in plot
#                area. If set, overrides gamma_anchor / gamma_xy_offset.
# first_trace_fit_t_start: override FIT_T_START for the chronologically first
#                          It trace of the session (used to dodge degenerate
#                          stretched-exp fits when there's no preceding light
#                          pulse to relax from — see diagnostic on 2026-05-15).
CHIPS: list[dict] = [
    {
        "chip": 68,
        "vg_filter": -0.9,
        # Drop the discarded first attempt (seq 227 @ 1 µW, 228 @ 2 µW,
        # 230 @ 3 µW, 231 @ 4 µW). Keep only the "ahorasi?" retry set
        # 234-237 (3, 4, 5, 6 µW), matching the other chips' range.
        "seq_exclude": [227, 228, 230, 231],
        "color": "#377eb8",
        "marker": "o",
        "gamma_anchor": "left",
        "gamma_xy_offset": (+70, 3),
        "gamma_axes_xy": (0.1, 0.2),
    },
    {
        "chip": 74,
        "vg_filter": -0.7,
        "color": "#e41a1c",
        "marker": "s",
        "gamma_anchor": "left",
        "gamma_xy_offset": (+70, 3),
        "first_trace_fit_t_start": 40.0,
        "gamma_axes_xy": (0.15, 0.72),
    },
    {
        "chip": 75,
        "vg_filter": -0.5,
        "color": "#4daf4a",
        "marker": "^",
        "gamma_anchor": "left",
        "gamma_xy_offset": (+70, 3),
        "first_trace_fit_t_start": 40.0,
        "gamma_axes_xy": (0.15, 0.93),
    },
    {
        "chip": 76,
        "vg_filter": -1.0,
        "color": "#984ea3",
        "marker": "D",
        "gamma_anchor": "left",
        "gamma_xy_offset": (+70, 3),
        "first_trace_fit_t_start": 30.0,
        "gamma_axes_xy": (0.15, 0.45),
    },
    {
        # Mislabeled as chip 67 in the raw CSVs; reading from chip 67 history.
        "chip": 72,
        "history_chip": 67,
        "vg_filter": -0.5,
        "color": "#a65628",
        "marker": "P",
        "gamma_anchor": "left",
        "gamma_xy_offset": (-10, 0),
        "gamma_axes_xy": (0.15, 0.14),
    },
]

_EXTRACTORS: dict[float, CorrectedDeltaIExtractor] = {}


def get_extractor(fit_t_start: float) -> CorrectedDeltaIExtractor:
    if fit_t_start not in _EXTRACTORS:
        _EXTRACTORS[fit_t_start] = CorrectedDeltaIExtractor(
            fit_t_start=fit_t_start,
            fit_t_end=FIT_T_END,
            eval_t_pre=EVAL_T_PRE,
            eval_t_post=EVAL_T_POST,
        )
    return _EXTRACTORS[fit_t_start]


def first_trace_seq(rows: pl.DataFrame) -> int | None:
    if rows.height == 0:
        return None
    return int(rows.select(pl.col("seq").min()).item())


def fit_t_start_for_row(row: dict, chip: dict, first_seq: int | None) -> float:
    if first_seq is not None and int(row["seq"]) == first_seq:
        return float(chip.get("first_trace_fit_t_start", FIT_T_START))
    return FIT_T_START


def delta_i_for_row(row: dict, fit_t_start: float) -> float | None:
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
    metric = get_extractor(fit_t_start).extract(meas, meta)
    if metric is None or metric.value_float is None:
        return None
    v = metric.value_float
    return v if np.isfinite(v) else None


def rows_for_chip(hist: pl.DataFrame, chip: dict) -> pl.DataFrame:
    flt = (
        (pl.col("date") == DATE)
        & (pl.col("proc") == "It")
        & (pl.col("has_light"))
        & (pl.col("wavelength_nm") == WAVELENGTH_NM)
    )
    vg = chip.get("vg_filter")
    if vg is not None:
        flt = flt & (pl.col("vg_fixed_v") == vg)
    seq_exclude = chip.get("seq_exclude")
    if seq_exclude:
        flt = flt & (~pl.col("seq").is_in(seq_exclude))
    return hist.filter(flt).sort("irradiated_power_w")


def curve_for_chip(hist: pl.DataFrame, chip: dict) -> tuple[np.ndarray, np.ndarray]:
    rows = rows_for_chip(hist, chip)
    first_seq = first_trace_seq(rows)
    powers_uW: list[float] = []
    di_uA: list[float] = []
    for row in rows.iter_rows(named=True):
        ts = fit_t_start_for_row(row, chip, first_seq)
        v = delta_i_for_row(row, ts)
        p = row.get("irradiated_power_w")
        if v is None or p is None or not np.isfinite(p):
            continue
        powers_uW.append(float(p) * 1e6)
        di_uA.append(abs(v) * 1e6)
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


def plot_it_overlay(config: PlotConfig, hist: pl.DataFrame, chip: dict) -> None:
    rows = rows_for_chip(hist, chip)
    if rows.height == 0:
        print(f"[warn] no It traces for {label_for_chip(chip)}")
        return
    first_seq = first_trace_seq(rows)

    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))

    n = rows.height
    line_color = chip.get("color", "#d62728")

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

        ts = fit_t_start_for_row(row, chip, first_seq)
        mask = (t >= ts) & (t <= FIT_T_END)
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
            label=label_for_chip(chip) if not label_used else None,
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

    inset = ax.inset_axes([0.18, 0.16, 0.3, 0.3])
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

    inset.set_xlabel(r"$t\ (\mathrm{s})$")
    inset.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")

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

    filename = (
        f"Alisson{chip['chip']}_It_sequential_with_overlay_{DATE}_365nm.{config.format}"
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / filename
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_corrected_overlay_full(
    config: PlotConfig, hist: pl.DataFrame, chip: dict
) -> None:
    rows = rows_for_chip(hist, chip)
    if rows.height == 0:
        print(f"[warn] no It traces for {label_for_chip(chip)}")
        return
    first_seq = first_trace_seq(rows)

    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))

    n = rows.height
    cmap = mpl.colormaps["plasma_r"]
    cmap_levels = np.linspace(0.15, 1.0, max(1, n))

    all_y: list[float] = []
    for i, row in enumerate(rows.iter_rows(named=True)):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size == 0:
            continue
        if t.size > 1:
            t, I = t[1:], I[1:]

        ts = fit_t_start_for_row(row, chip, first_seq)
        mask = (t >= ts) & (t <= FIT_T_END)
        if mask.sum() >= 10:
            fit = fit_stretched_exponential(t[mask], I[mask])
            drift = stretched_exponential(
                t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
            )
            I_corr = I - drift
        else:
            I_corr = I.copy()
        idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
        I_corr = (I_corr - I_corr[idx_pre]) * 1e6

        p_uW = float(row.get("irradiated_power_w") or 0.0) * 1e6
        ax.plot(
            t,
            I_corr,
            color=cmap(cmap_levels[i]),
            linewidth=2.0,
            label=f"{p_uW:.0f} µW",
        )
        all_y.extend(I_corr.tolist())

    ax.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha)
    ax.axhline(0, color="k", linewidth=0.5, alpha=0.5)
    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    ax.set_title(label_for_chip(chip))
    ax.legend(loc="best", framealpha=0.9)

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    plt.tight_layout()

    filename = (
        f"Alisson{chip['chip']}_It_corrected_overlay_full_{DATE}_365nm.{config.format}"
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / filename
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_photoresponse_vs_power(
    config: PlotConfig, hist: pl.DataFrame, chip: dict
) -> None:
    p, di = curve_for_chip(hist, chip)
    if p.size == 0:
        print(f"[warn] no photoresponse data for {label_for_chip(chip)}")
        return

    set_plot_style(config.theme)
    fig, ax = plt.subplots(figsize=(20, 20))

    gamma, p_fit, di_fit = power_law_fit(p, di)

    ax.plot(
        p,
        di,
        marker=chip["marker"],
        linestyle="none",
        color=chip["color"],
        markersize=12,
        label=f"{label_for_chip(chip)}, $\\gamma={gamma:.2f}$",
    )
    if p_fit.size:
        ax.plot(p_fit, di_fit, linestyle="-", color=chip["color"], linewidth=1.2)

    ax.set_yscale("log")
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    ax.legend()
    plt.tight_layout()

    print(
        f"{label_for_chip(chip)}  n={p.size}  P=[{p.min():.2f},{p.max():.2f}] µW  "
        f"|Δi|=[{di.min():.3g},{di.max():.3g}] µA  γ={gamma:.3f}"
    )

    filename = f"Alisson{chip['chip']}_photoresponse_vs_power_semilogy_{DATE}_365nm.{config.format}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / filename
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_comparison(
    config: PlotConfig,
    histories: dict[int, pl.DataFrame],
    chips: list[dict],
    filename: str,
    anchor_chip: int,
) -> None:
    set_plot_style(config.theme)
    fig, ax = plt.subplots(figsize=(20, 20))

    gamma_annotations: list[tuple[dict, float, np.ndarray, np.ndarray]] = []

    for chip in chips:
        p, di = curve_for_chip(histories[chip["chip"]], chip)
        if p.size == 0:
            print(f"[warn] no data for {label_for_chip(chip)}")
            continue

        gamma, p_fit, di_fit = power_law_fit(p, di)
        ax.plot(
            p,
            di,
            marker=chip["marker"],
            linestyle="none",
            color=chip["color"],
            markersize=25,
            label=label_for_chip(chip, include_material=False),
        )
        if p_fit.size:
            ax.plot(p_fit, di_fit, linestyle="-", color=chip["color"], linewidth=1.2)

        gamma_annotations.append((chip, gamma, p, di))

    ax.set_yscale("log")
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    # Park the legend in the empty band between chip 76 and chip 68 traces.
    ax.legend(
        loc="center",
        bbox_to_anchor=(0.8, 0.40),
        framealpha=0.9,
    )

    for chip, gamma, p, di in gamma_annotations:
        axes_xy = chip.get("gamma_axes_xy")
        if axes_xy is not None:
            xy = axes_xy
            xycoords = "axes fraction"
            xytext = (0, 0)
            textcoords = "offset points"
            ha = "left"
        else:
            anchor = chip.get("gamma_anchor", "left")
            idx = int(np.argmin(p)) if anchor == "left" else int(np.argmax(p))
            xy = (p[idx], di[idx])
            xycoords = "data"
            xytext = chip.get("gamma_xy_offset", (-10, 0))
            textcoords = "offset points"
            ha = "right" if anchor == "left" else "left"
        ann = ax.annotate(
            f"$\\gamma={gamma:.2f}$",
            xy=xy,
            xycoords=xycoords,
            xytext=xytext,
            textcoords=textcoords,
            ha=ha,
            va="center",
            color=chip["color"],
            fontsize="large",
            fontweight="bold",
        )
        ann.set_path_effects(
            [
                path_effects.Stroke(linewidth=3.0, foreground="white"),
                path_effects.Normal(),
            ]
        )

    plt.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{filename}.{config.format}"
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comparison-only",
        action="store_true",
        help="Skip per-chip overlays; only generate the two comparison figures.",
    )
    args = parser.parse_args()

    config = PlotConfig()
    set_plot_style(config.theme)

    histories: dict[int, pl.DataFrame] = {}
    for chip in CHIPS:
        # Read from history_chip if specified (used for chip 72 mislabel
        # workaround), otherwise from the chip's own history.
        hist_chip = chip.get("history_chip", chip["chip"])
        path = Path(
            f"data/03_derived/chip_histories_enriched/Alisson{hist_chip}_history.parquet"
        )
        histories[chip["chip"]] = pl.read_parquet(path)

    if not args.comparison_only:
        for chip in CHIPS:
            hist = histories[chip["chip"]]
            plot_it_overlay(config, hist, chip)
            plot_corrected_overlay_full(config, hist, chip)
            plot_photoresponse_vs_power(config, hist, chip)

    # Comparison figure with chip 72
    plot_comparison(
        config,
        histories,
        CHIPS,
        filename=f"Alisson68_72_74_75_76_photoresponse_vs_power_semilogy_{DATE}_365nm",
        anchor_chip=68,
    )

    # Comparison figure without chip 72
    chips_no_72 = [c for c in CHIPS if c["chip"] != 72]
    plot_comparison(
        config,
        histories,
        chips_no_72,
        filename=f"Alisson68_74_75_76_photoresponse_vs_power_semilogy_{DATE}_365nm",
        anchor_chip=68,
    )


if __name__ == "__main__":
    main()
