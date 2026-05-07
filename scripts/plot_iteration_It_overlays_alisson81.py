"""
Per-cluster It overlays + sequential views for Alisson81 iteration decay.

Companion to `scripts/plot_iteration_decay_alisson81.py`. For each Vg cluster
(8/6/5 iterations of It at 455 nm, 6 µW), produces two figures:

  - **Overlay**: drift-corrected I(t) traces, all iterations on a shared time
    axis, colored by iteration index (viridis: early=dark → late=bright).
    Drift correction matches `compare_corrected_It_67_72_74_75_80_81_pairs.py`
    (stretched-exp on t ∈ [FIT_T_START, 60] s, anchored to I_corr(60 s) = 0).

  - **Sequential**: raw I(t) traces concatenated end-to-end on a continuous
    time axis (mirrors `biotite plot-its-suite` sequential mode), colored by
    iteration index, with dashed vertical lines at experiment boundaries and
    light-window shading per segment.

All seqs across the 5 clusters are 455 nm, 6 µW, light=on (verified against the
enriched history); the only varying axis within a cluster is iteration index.

Outputs land under a dedicated folder: figs/Alisson81_iteration_decay/.

Run from repo root:
    python scripts/plot_iteration_It_overlays_alisson81.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.ticker import MultipleLocator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.compare_corrected_It_67_72_74_75_80_81_pairs import (  # noqa: E402
    DEFAULT_FIT_T_START,
    PLOT_START_TIME,
    TICK_STEP,
    corrected_trace,
    fit_both_models,
    light_window,
)
from src.core.utils import read_measurement_parquet  # noqa: E402
from src.plotting.config import PlotConfig  # noqa: E402
from src.plotting.styles import PRISM_RAIN_PALETTE, set_plot_style  # noqa: E402

CHIP_NUMBER = 81
HISTORY_PATH = Path(
    f"data/03_derived/chip_histories_enriched/Alisson{CHIP_NUMBER}_history.parquet"
)
OUTPUT_DIR = Path(f"figs/Alisson{CHIP_NUMBER}_iteration_decay")
WAVELENGTH_NM = 455
POWER_UW = 6
FIT_T_START = DEFAULT_FIT_T_START
SEQUENTIAL_START_TIME = 0.0  # show the full per-iteration cycle (dark → light → dark)

CLUSTERS: list[dict] = [
    {"vg_v": -1.7, "tag": "vg-1p7", "seqs": [132, 133, 134, 135, 136, 137, 138, 139]},
    {"vg_v": -1.5, "tag": "vg-1p5", "seqs": [146, 147, 148, 149, 150, 151, 152, 153]},
    {"vg_v": -1.15, "tag": "vg-1p15_runA", "seqs": [95, 97, 99, 101, 103]},
    {"vg_v": -1.15, "tag": "vg-1p15_runB", "seqs": [117, 120, 121, 122, 123, 126]},
    {"vg_v": 0.0, "tag": "vg0", "seqs": [193, 194, 195, 196, 197, 198, 199, 200]},
]


def collect_cluster_traces(history: pl.DataFrame, seqs: list[int]) -> list[dict]:
    rows = (
        history.filter(pl.col("seq").is_in(seqs))
        .filter(pl.col("proc") == "It")
        .sort("seq")
    )
    if rows.height == 0:
        raise ValueError(f"no It rows matched seqs={seqs}")

    traces: list[dict] = []
    for row in rows.iter_rows(named=True):
        parquet_path = Path(row.get("parquet_path") or "")
        if not parquet_path.exists():
            print(f"  missing parquet for seq {row.get('seq')}: {parquet_path}")
            continue
        meas = read_measurement_parquet(parquet_path)
        if "t (s)" not in meas.columns or "I (A)" not in meas.columns:
            continue
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)

        fit = fit_both_models(t, i, FIT_T_START)
        i_corr = corrected_trace(fit)

        traces.append(
            {
                "seq": int(row["seq"]),
                "t": fit["t_full"],
                "i_raw_uA": fit["i_full"] * 1e6,
                "i_corr_uA": i_corr * 1e6,
                "light_span": light_window(meas, fit["t_full"]),
            }
        )
    return traces


def _save(fig: plt.Figure, filename: str, config: PlotConfig) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{filename}.{config.format}"
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")
    return out


def plot_cluster_overlay(
    cluster: dict,
    traces: list[dict],
    config: PlotConfig,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side, side))

    n = len(traces)
    cmap = mpl.colormaps["viridis"]

    all_y: list[float] = []
    t_totals: list[float] = []
    spans: list[tuple[float, float]] = []

    for k, tr in enumerate(traces):
        color = cmap(k / max(1, n - 1))
        ax.plot(
            tr["t"],
            tr["i_corr_uA"],
            color=color,
            linestyle="-",
            label=f"#{k + 1}",
        )
        visible = tr["t"] >= PLOT_START_TIME
        all_y.extend(tr["i_corr_uA"][visible])
        t_totals.append(float(tr["t"][-1]))
        if tr.get("light_span"):
            spans.append(tr["light_span"])

    if spans:
        s = float(np.median([sp[0] for sp in spans]))
        e = float(np.median([sp[1] for sp in spans]))
        ax.axvspan(s, e, alpha=config.light_window_alpha)

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    ax.set_title(
        f"Alisson{CHIP_NUMBER} (biotite), $V_g = {cluster['vg_v']:g}$ V "
        f"— iteration overlay ({WAVELENGTH_NM} nm, {POWER_UW} µW)"
    )
    ax.set_box_aspect(1.0)

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            ax.set_xlim(PLOT_START_TIME, T_total)
    ax.xaxis.set_major_locator(MultipleLocator(TICK_STEP))

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    ax.legend(
        loc="best", framealpha=0.9, ncol=2, fontsize="small", title_fontsize="small"
    )

    plt.tight_layout()
    _save(fig, f"Alisson{CHIP_NUMBER}_iteration_It_overlay_{cluster['tag']}", config)


def plot_sequential_with_overlay_inset(
    cluster: dict,
    traces: list[dict],
    config: PlotConfig,
) -> None:
    """Sequential raw I(t) (single color) + inset with drift-corrected overlay
    (viridis_r-by-iteration)."""
    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=(20, 20))

    n = len(traces)
    line_color = PRISM_RAIN_PALETTE[0]

    boundaries: list[float] = []
    all_y: list[float] = []
    time_offset = 0.0

    vg_label = rf"$V_g = {cluster['vg_v']:g}$ V"
    label_used = False
    for tr in traces:
        t = tr["t"]
        y = tr["i_raw_uA"]
        mask = t >= SEQUENTIAL_START_TIME
        t_seg = t[mask]
        y_seg = y[mask]
        if t_seg.size == 0:
            continue
        t_seg = t_seg - t_seg[0]
        # Drop first sample of each segment (instrument glitch on It restart).
        if t_seg.size > 1:
            t_seg = t_seg[1:]
            y_seg = y_seg[1:]
        boundaries.append(time_offset)

        ax.plot(
            t_seg + time_offset, y_seg, color=line_color, linewidth=2.0,
            label=vg_label if not label_used else None,
        )
        label_used = True
        all_y.extend(y_seg.tolist())

        time_offset += float(t_seg[-1])

    ax.set_xlabel(r"t (s)")
    ax.set_ylabel(r"$I_{ds}\ (\mu\mathrm{A})$")
    ax.legend(loc="best", framealpha=0.9)
    # ax.set_title(
    #     f"Alisson{CHIP_NUMBER} (biotite), $V_g = {cluster['vg_v']:g}$ V "
    #     f"— sequential It + overlay inset ({WAVELENGTH_NM} nm, {POWER_UW} µW)"
    # )

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_xlim(0.0, time_offset)

    # --- inset: drift-corrected overlay, viridis_r by iteration ---
    inset = ax.inset_axes([0.5, 0.16, 0.40, 0.40])
    cmap = mpl.colormaps["magma_r"]

    inset_y: list[float] = []
    inset_t_totals: list[float] = []
    inset_spans: list[tuple[float, float]] = []

    for k, tr in enumerate(traces):
        color = cmap(k / max(1, n - 1))
        inset.plot(
            tr["t"], tr["i_corr_uA"], color=color, linewidth=1.5, label=f"#{k + 1}"
        )
        visible = tr["t"] >= PLOT_START_TIME
        inset_y.extend(tr["i_corr_uA"][visible])
        inset_t_totals.append(float(tr["t"][-1]))
        if tr.get("light_span"):
            inset_spans.append(tr["light_span"])

    if inset_spans:
        s = float(np.median([sp[0] for sp in inset_spans]))
        e = float(np.median([sp[1] for sp in inset_spans]))
        inset.axvspan(s, e, alpha=config.light_window_alpha)

    if inset_t_totals:
        T_total = float(np.median(inset_t_totals))
        if np.isfinite(T_total) and T_total > 0:
            inset.set_xlim(PLOT_START_TIME, T_total)
    inset.set_xticks([60, 120, 180])

    if inset_y:
        y = np.array(inset_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                inset.set_ylim(y_min - pad, y_max + pad)

    inset.set_xlabel(r"$t\ (\mathrm{s})$")
    inset.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    inset.set_yticks([0, 0.75])

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
        "#",
        va="center",
        ha="left",
        fontsize="medium",
    )

    plt.tight_layout()
    _save(
        fig,
        f"Alisson{CHIP_NUMBER}_iteration_It_sequential_with_overlay_{cluster['tag']}",
        config,
    )


def plot_cluster_sequential(
    cluster: dict,
    traces: list[dict],
    config: PlotConfig,
) -> None:
    """Raw I(t) concatenated on a continuous axis, magma-by-iteration."""
    set_plot_style(config.theme)
    fig, ax = plt.subplots(1, 1, figsize=config.figsize_timeseries)

    n = len(traces)
    cmap = mpl.colormaps["magma_r"]

    boundaries: list[float] = []
    all_y: list[float] = []
    time_offset = 0.0

    for k, tr in enumerate(traces):
        t = tr["t"]
        y = tr["i_raw_uA"]
        mask = t >= SEQUENTIAL_START_TIME
        t_seg = t[mask]
        y_seg = y[mask]
        if t_seg.size == 0:
            continue
        t_seg = t_seg - t_seg[0]
        boundaries.append(time_offset)

        color = cmap(k / max(1, n - 1))
        ax.plot(
            t_seg + time_offset,
            y_seg,
            color=color,
            linewidth=2.0,
            label=f"iter {k + 1} (seq {tr['seq']})",
        )
        all_y.extend(y_seg.tolist())

        span = tr.get("light_span")
        if span is not None:
            s_local = max(span[0] - SEQUENTIAL_START_TIME, 0.0)
            e_local = max(span[1] - SEQUENTIAL_START_TIME, 0.0)
            ax.axvspan(
                s_local + time_offset,
                e_local + time_offset,
                alpha=config.light_window_alpha,
            )

        time_offset += float(t_seg[-1])

    for b in boundaries[1:]:
        ax.axvline(b, color="gray", linestyle="--", linewidth=1.2, alpha=0.5)

    ax.set_xlabel(r"Concatenated time (s)")
    ax.set_ylabel(r"$I_{ds}\ (\mu\mathrm{A})$")
    ax.set_title(
        f"Alisson{CHIP_NUMBER} (biotite), $V_g = {cluster['vg_v']:g}$ V "
        f"— sequential It ({WAVELENGTH_NM} nm, {POWER_UW} µW)"
    )

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_xlim(0.0, time_offset)

    ax.legend(
        loc="best", framealpha=0.9, ncol=2, fontsize="small", title_fontsize="small"
    )

    plt.tight_layout()
    _save(fig, f"Alisson{CHIP_NUMBER}_iteration_It_sequential_{cluster['tag']}", config)


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    history = pl.read_parquet(HISTORY_PATH)

    for cluster in CLUSTERS:
        traces = collect_cluster_traces(history, cluster["seqs"])
        if not traces:
            print(f"[Vg={cluster['vg_v']} {cluster['tag']}] no traces, skipping")
            continue

        def _at(t, y, t_target):
            if t.size == 0 or not np.any(np.isfinite(y)):
                return float("nan")
            idx = int(np.argmin(np.abs(t - t_target)))
            return float(y[idx])

        di_first = _at(traces[0]["t"], traces[0]["i_corr_uA"], 120.0)
        di_last = _at(traces[-1]["t"], traces[-1]["i_corr_uA"], 120.0)
        print(
            f"[Vg={cluster['vg_v']:+g} V {cluster['tag']}] "
            f"n={len(traces)} seqs {traces[0]['seq']}→{traces[-1]['seq']}  "
            f"ΔI_corr(120s) first={di_first:+.3f} µA last={di_last:+.3f} µA"
        )

        plot_cluster_overlay(cluster, traces, config)
        plot_cluster_sequential(cluster, traces, config)

        if cluster["tag"] == "vg-1p7":
            plot_sequential_with_overlay_inset(cluster, traces, config)


if __name__ == "__main__":
    main()
