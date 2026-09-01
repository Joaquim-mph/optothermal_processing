"""
Iteration decay of the photoresponse: hBN vs biotite bottom dielectric.

Repeated It measurements at fixed (lambda, P, Vg) are not exchangeable
replicates on hBN devices -- |I_ph| collapses monotonically as the trap
population fills. Biotite devices do not show this. All clusters compared
here sit at P ~ 6 uW (Phi ~ 60 W/m^2).

Two measurement protocols are kept in separate figures throughout:

    "Vg held"  (lambda = 455 nm) -- gate left biased between iterations
    "Vg reset" (lambda = 365 nm) -- gate returned to 0 V between iterations

Figures (all in figs/iteration_decay_hbn_vs_biotite/):

  iteration_photocurrent_vg_hold_455nm.pdf    |I_ph| (uA) vs iteration
  iteration_photocurrent_vg_reset_365nm.pdf
  iteration_responsivity_vg_hold_455nm.pdf    |R| (A/W) vs iteration
  iteration_responsivity_vg_reset_365nm.pdf
  it_corrected_overlay_vg_hold_455nm.pdf      I_corr(t), all 7 iterations
  it_corrected_overlay_vg_reset_365nm.pdf
  it_sequential_vg_hold_455nm.pdf             raw I_ds(t), segments stitched
  it_sequential_vg_reset_365nm.pdf
  it_sequential_with_overlay_inset_*.pdf      the same, plus an overlay inset

Responsivity is R = I_ph / P_device, with P_device = P_beam * (A_flake /
A_beam); A_flake from config/encap_characteristics.yaml and P_beam
interpolated from the nearest-date LaserCalibration sweep at that
wavelength. This is the same recipe as scripts/power_sweeps/*.

I_ph is recomputed here rather than read from `delta_i_corrected`, so that
the drift-fit retry in `drift_fit()` is reflected everywhere. It reproduces
the stored value exactly on 27 of the 28 traces; the exception is chip 75
seq 229, the first run after gate turn-on, where the pipeline's fixed
[20, 60] s window sits entirely on the settling ramp and diverges. Set
DROP_FIRST_ITERATION = True to re-plot every cluster from its second
iteration instead.

Run from repo root:
    .venv/bin/python scripts/plot_iteration_decay_hbn_vs_biotite.py

Prereq: biotite derive-all-metrics && biotite enrich-history {75,80,81}
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

ENCAP_YAML = Path("config/encap_characteristics.yaml")
HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
MANIFEST_PATH = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
OUTPUT_DIR = Path("figs/iteration_decay_hbn_vs_biotite")

# Beam geometry: the calibrated LED power is the total power over the spot.
# Chip 81 was measured on the older setup, whose beam was slightly larger.
BEAM_AREA_UM2_DEFAULT = 1e5
BEAM_AREA_UM2_BY_CHIP = {81: 1.2e5}

# Drift-correction window for the It overlays. These match
# CorrectedDeltaIExtractor exactly, so the overlays and the I_ph values in the
# iteration figures come from the same recipe: fit a stretched exponential on
# t in [20, 60] s, subtract it, anchor I_corr(60 s) = 0, read I_ph at 120 s.
FIT_T_START = 20.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
PLOT_START_TIME = 50.0

# Retry window for traces whose default fit is degenerate. On a run that is
# still settling at t = 20 s the [20, 60] window sees only the flat tail of
# the ramp, which leaves tau/beta unidentified: beta collapses toward 0 and
# the drift model diverges once extrapolated past 60 s. Starting at t = 1 s
# includes the curvature that pins the shape down. Sweeping the start time
# over 0-50 s on Alisson75 seq 229 showed a sharp cliff between 5 s and 6 s --
# every start <= 5 s converges with beta ~ 0.8 and reproduces the shape of the
# six sibling runs (correlation 0.996 at 1 s), every start >= 6 s diverges.
FIT_T_START_FALLBACK = 1.0

# Below this, the stretched exponential has degenerated into a near power law
# that fits any monotonic ramp and extrapolates wildly.
BETA_MIN = 0.2

# Set True to start every cluster at its second iteration (drops chip 75's
# gate-settling first run, and the equivalent first point elsewhere).
DROP_FIRST_ITERATION = False

# Line/marker/legend weights, matching
# scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py.
# The pairs script uses +2.0; bumped here because these panels carry only two
# series and the legend was the smallest text on the figure (31 pt against
# 55 pt axis labels). 8.0 puts it at ~37 pt.
LEGEND_FONTSIZE_BUMP = 8.0
TRACE_LINEWIDTH = 5.5  # It(t) overlays and sequential traces
LINE_WIDTH = 5.5  # vs-iteration curves
MARKER_SIZE = 30.0  # vs-iteration points
LEGEND_FRAMEALPHA = 0.9

# Overlay-inset placement in host-axes fractions, [x0, y0, w, h]. Per-cluster
# overrides live in CLUSTERS["inset_bbox"]; chip 80's reset panel needs a
# higher inset because its I_ds staircase descends into the default slot.
INSET_BBOX = [0.5, 0.16, 0.40, 0.40]


def _legend_fontsize(relative: str = "small") -> float:
    """Theme-relative "small" plus a fixed bump, as in the pairs script."""
    from matplotlib.font_manager import font_scalings

    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


HBN_COLOR = "#377eb8"
BIOTITE_COLOR = "#e41a1c"

# ---------------------------------------------------------------------------
# Clusters: consecutive It runs at fixed (lambda, VL, Vg) on one date.
# Verified by scanning every enriched history for runs of >= 4 such rows.
# ---------------------------------------------------------------------------
CLUSTERS: list[dict] = [
    {
        "chip": 80,
        "date": "2026-08-28",
        "wavelength_nm": 365.0,
        "laser_voltage_v": 3.8,
        "protocol": "reset",
        "vg_v": -0.5,
        "seqs": [196, 197, 198, 199, 200, 201, 202],
        "color": HBN_COLOR,
        "marker": "o",
        "linestyle": "-",
        "inset_bbox": [0.5, 0.36, 0.40, 0.40],
    },
    {
        "chip": 75,
        "date": "2026-07-08",
        "wavelength_nm": 365.0,
        "laser_voltage_v": 1.06,
        "protocol": "reset",
        "vg_v": -1.0,
        "seqs": [200, 201, 202, 203, 204, 205, 206],
        "color": BIOTITE_COLOR,
        "marker": "o",
        "linestyle": "-",
    },
    {
        "chip": 81,
        "date": "2025-10-28",
        "wavelength_nm": 455.0,
        "laser_voltage_v": 1.25,
        "protocol": "hold",
        "vg_v": -1.7,
        # seq 139 (the 8th run) dropped so every cluster has 7 iterations.
        "seqs": [132, 133, 134, 135, 136, 137, 138],
        "color": HBN_COLOR,
        "marker": "o",
        "linestyle": "-",
    },
    {
        "chip": 75,
        "date": "2026-08-28",
        "wavelength_nm": 455.0,
        "laser_voltage_v": 1.18,
        "protocol": "hold",
        "vg_v": -0.4,
        "seqs": [229, 230, 231, 232, 233, 234, 235],
        "color": BIOTITE_COLOR,
        "marker": "o",
        "linestyle": "-",
    },
]

PROTOCOLS: dict[str, dict] = {
    "hold": {"label": r"$V_g$ held", "wavelength_nm": 455, "stem": "vg_hold_455nm"},
    "reset": {"label": r"$V_g$ reset", "wavelength_nm": 365, "stem": "vg_reset_365nm"},
}


def _encap() -> dict:
    return yaml.safe_load(ENCAP_YAML.read_text()) or {}


def materials() -> dict[int, str]:
    """Per-chip bottom-dielectric tag from config/encap_characteristics.yaml."""
    return {
        int(k): str(v["material"])
        for k, v in _encap().items()
        if isinstance(k, int) and isinstance(v, dict) and "material" in v
    }


def flake_areas_um2() -> dict[int, float]:
    """Per-chip flake area (um^2) from config/encap_characteristics.yaml."""
    return {
        int(k): float(v["flake_area_um2"])
        for k, v in _encap().items()
        if isinstance(k, int) and isinstance(v, dict) and "flake_area_um2" in v
    }


MATERIALS = materials()
FLAKE_AREAS = flake_areas_um2()


def beam_power_w(wavelength_nm: float, when: str, laser_voltage_v: float) -> float:
    """Interpolate LED beam power from the nearest-date calibration sweep.

    Several calibration runs may exist on one date; their interpolated
    powers are averaged.
    """
    cal = pl.read_parquet(MANIFEST_PATH).filter(
        pl.col("proc") == "LaserCalibration",
        pl.col("wavelength_nm") == wavelength_nm,
    )
    if cal.height == 0:
        raise RuntimeError(f"no LaserCalibration at {wavelength_nm:g} nm")

    target = _date.fromisoformat(when)
    dates = sorted({str(d) for d in cal["date_local"].to_list()})
    nearest = min(dates, key=lambda d: abs((_date.fromisoformat(d) - target).days))
    if nearest != when:
        print(
            f"[note] {wavelength_nm:g} nm: no calibration on {when}, "
            f"using nearest ({nearest})"
        )

    powers = []
    for path in cal.filter(pl.col("date_local") == nearest)["path"].to_list():
        sweep = pl.read_parquet(path).sort("VL (V)")
        powers.append(
            float(
                np.interp(
                    laser_voltage_v,
                    sweep["VL (V)"].to_numpy(),
                    sweep["Power (W)"].to_numpy(),
                )
            )
        )
    return float(np.mean(powers))


def device_power_w(cluster: dict) -> float:
    """P_device = P_beam * (A_flake / A_beam)."""
    area = FLAKE_AREAS.get(cluster["chip"])
    if area is None:
        raise RuntimeError(
            f"chip {cluster['chip']} has no flake_area_um2 in {ENCAP_YAML}"
        )
    p_beam = beam_power_w(
        cluster["wavelength_nm"], cluster["date"], cluster["laser_voltage_v"]
    )
    beam_area = BEAM_AREA_UM2_BY_CHIP.get(cluster["chip"], BEAM_AREA_UM2_DEFAULT)
    return p_beam * (area / beam_area)


def cluster_label(cluster: dict) -> str:
    chip = cluster["chip"]
    mat = MATERIALS.get(chip, "?")
    return rf"{chip} ({mat}), $V_g={cluster['vg_v']:g}$ V"


def history(chip: int) -> pl.DataFrame:
    return pl.read_parquet(HISTORY_DIR / f"Alisson{chip}_history.parquet")


def cluster_rows(cluster: dict) -> pl.DataFrame:
    """It rows for a cluster, ordered by acquisition (seq)."""
    rows = (
        history(cluster["chip"])
        .filter(
            pl.col("seq").is_in(cluster["seqs"]),
            pl.col("date_local") == cluster["date"],
            pl.col("proc") == "It",
            pl.col("has_light"),
            pl.col("wavelength_nm") == cluster["wavelength_nm"],
        )
        .sort("seq")
    )
    missing = set(cluster["seqs"]) - set(rows["seq"].to_list())
    if missing:
        print(f"[warn] chip {cluster['chip']}: seqs not found -> {sorted(missing)}")
    return rows


def drift_fit(t: np.ndarray, I: np.ndarray) -> tuple[dict, float]:
    """Fit the pre-illumination drift, retrying from FIT_T_START_FALLBACK.

    Returns (fit, fit_t_start_used). The default window is accepted only if
    the fit converged with a non-degenerate beta; otherwise the earlier
    window is tried, and if that also fails the default result is kept so
    the value still matches the pipeline.
    """
    fallback = None
    for t0 in (FIT_T_START, FIT_T_START_FALLBACK):
        mask = (t >= t0) & (t <= FIT_T_END)
        if mask.sum() < 10:
            continue
        fit = fit_stretched_exponential(t[mask], I[mask])
        if fit["converged"] and fit["beta"] >= BETA_MIN:
            return fit, t0
        if fallback is None:
            fallback = (fit, t0)
    if fallback is None:
        raise RuntimeError("not enough samples in any drift-fit window")
    return fallback


def _trace_cache() -> dict:
    if not hasattr(_trace_cache, "store"):
        _trace_cache.store = {}
    return _trace_cache.store


def cluster_traces(cluster: dict) -> list[dict]:
    """Per-iteration corrected traces and I_ph for one cluster.

    I_ph is recomputed here rather than read from the enriched history so
    that the refit above is reflected everywhere. The recipe is otherwise
    CorrectedDeltaIExtractor's verbatim (delta_mode="max_deviation"), and it
    reproduces the stored `delta_i_corrected` exactly on every trace whose
    default fit was already sound.
    """
    key = (cluster["chip"], cluster["date"], tuple(cluster["seqs"]))
    cache = _trace_cache()
    if key in cache:
        return cache[key]

    out: list[dict] = []
    for row in cluster_rows(cluster).iter_rows(named=True):
        meas = read_measurement_parquet(Path(row["parquet_path"]))
        t = meas["t (s)"].to_numpy().astype(np.float64)
        I = meas["I (A)"].to_numpy().astype(np.float64)
        finite = np.isfinite(t) & np.isfinite(I)
        t, I = t[finite], I[finite]
        if t.size < 2:
            continue

        fit, t0 = drift_fit(t, I)
        drift = stretched_exponential(
            t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
        )
        I_corr = I - drift
        I_corr = I_corr - I_corr[int(np.argmin(np.abs(t - EVAL_T_PRE)))]

        # delta_mode="max_deviation": largest excursion in the lit window.
        lit = (t >= EVAL_T_PRE) & (t <= EVAL_T_POST)
        seg = I_corr[lit]
        i_ph = float(seg[np.argmax(np.abs(seg))]) if seg.size else float("nan")

        stored = row.get("delta_i_corrected")
        out.append(
            {
                "seq": int(row["seq"]),
                "t": t,
                "I_corr": I_corr,
                "i_ph": i_ph,
                "refit": t0 != FIT_T_START,
                "beta": float(fit["beta"]),
                "stored": float(stored) if stored is not None else float("nan"),
            }
        )

    for tr in out:
        if tr["refit"]:
            print(
                f"[refit] chip {cluster['chip']} seq {tr['seq']}: "
                f"drift fit restarted at t={FIT_T_START_FALLBACK:g}s "
                f"(beta={tr['beta']:.2f}); I_ph {tr['stored'] * 1e6:+.2f} -> "
                f"{tr['i_ph'] * 1e6:+.2f} uA"
            )
    cache[key] = out
    return out


def cluster_series(cluster: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (iteration index, signed I_ph in A, refit mask)."""
    traces = cluster_traces(cluster)
    if DROP_FIRST_ITERATION:
        traces = traces[1:]
    i_ph = np.array([tr["i_ph"] for tr in traces], dtype=float)
    refit = np.array([tr["refit"] for tr in traces], dtype=bool)
    return np.arange(1, i_ph.size + 1), i_ph, refit


def _plot_points(
    ax,
    idx: np.ndarray,
    y: np.ndarray,
    cluster: dict,
    label: str | None,
) -> None:
    """One solid marker-line per cluster, styled like the Alisson81 script."""
    ax.plot(
        idx,
        y,
        marker=cluster["marker"],
        markersize=MARKER_SIZE,
        linestyle=cluster["linestyle"],
        linewidth=LINE_WIDTH,
        color=cluster["color"],
        label=label,
    )


def figure_iteration(config: PlotConfig, protocol: str, quantity: str) -> None:
    """|I_ph| (uA) or |R| (A/W) vs iteration index, one protocol per figure."""
    clusters = [c for c in CLUSTERS if c["protocol"] == protocol]
    fig, ax = plt.subplots(figsize=(20, 20))

    n_max = 0
    for cluster in clusters:
        idx, di_a, _ = cluster_series(cluster)
        if di_a.size == 0:
            continue
        n_max = max(n_max, idx.size)

        if quantity == "responsivity":
            y = np.abs(di_a) / device_power_w(cluster)
            unit = "A/W"
        else:
            y = np.abs(di_a) * 1e6
            unit = "uA"

        _plot_points(ax, idx, y, cluster, cluster_label(cluster))
        print(
            f"  {cluster_label(cluster):<34} n={y.size}  "
            f"first={y[0]:9.4g} {unit}  last={y[-1]:9.4g} {unit}  "
            f"ratio={y[0] / y[-1] if y[-1] else float('inf'):6.1f}x"
        )

    ax.set_xlabel("Iteration index")
    ax.set_ylabel(
        r"$|R|$ (A/W)" if quantity == "responsivity" else r"$|I_{ph}|$ ($\mu$A)"
    )
    ax.set_xticks(np.arange(1, n_max + 1))
    ax.legend(loc="best", fontsize=_legend_fontsize(), framealpha=LEGEND_FRAMEALPHA)

    plt.tight_layout()
    stem = "responsivity" if quantity == "responsivity" else "photocurrent"
    _save(fig, config, f"iteration_{stem}_{PROTOCOLS[protocol]['stem']}")


def figure_overlay(config: PlotConfig, protocol: str) -> None:
    """Drift-corrected I(t), all iterations overlaid, colored by iteration."""
    clusters = [c for c in CLUSTERS if c["protocol"] == protocol]
    fig, axes = plt.subplots(1, len(clusters), figsize=(20 * len(clusters), 20))
    axes = np.atleast_1d(axes)
    cmap = mpl.colormaps["viridis"]

    for ax, cluster in zip(axes, clusters):
        traces = cluster_traces(cluster)
        if DROP_FIRST_ITERATION:
            traces = traces[1:]
        n = len(traces)
        visible: list[float] = []
        t_max = 0.0

        for k, tr in enumerate(traces):
            t = tr["t"]
            y = tr["I_corr"] * 1e6
            ax.plot(
                t,
                y,
                color=cmap(k / max(1, n - 1)),
                linewidth=TRACE_LINEWIDTH,
                label=f"{k + 1}",
                zorder=2,
            )
            t_max = max(t_max, float(t[-1]))
            visible.extend(y[t >= PLOT_START_TIME].tolist())

        # Light-ON window: the correction anchors at EVAL_T_PRE and I_ph is
        # read at EVAL_T_POST, so this is exactly the interval being measured.
        ax.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha, zorder=0)
        ax.axhline(0.0, color="k", linewidth=1.0, alpha=0.4, zorder=1)

        ax.set_xlim(PLOT_START_TIME, t_max)
        if visible:
            v = np.asarray(visible, dtype=float)
            v = v[np.isfinite(v)]
            if v.size:
                lo, hi = float(v.min()), float(v.max())
                if hi > lo:
                    pad = config.padding_fraction * (hi - lo)
                    ax.set_ylim(lo - pad, hi + pad)

        ax.set_xlabel(r"$t$ (s)")
        ax.set_ylabel(r"$I_{corr}$ ($\mu$A)")
        ax.legend(loc="best", fontsize=_legend_fontsize(), framealpha=LEGEND_FRAMEALPHA)
        ax.text(
            0.02,
            0.98,
            cluster_label(cluster),
            transform=ax.transAxes,
            fontsize=_legend_fontsize(),
            va="top",
            ha="left",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=6),
        )

    plt.tight_layout()
    _save(fig, config, f"it_corrected_overlay_{PROTOCOLS[protocol]['stem']}")


def figure_sequential(config: PlotConfig, protocol: str, inset: bool = False) -> None:
    """Raw I_ds(t) with each cluster's It segments stitched end to end.

    With inset=True each panel also carries a small drift-corrected overlay
    (the same traces as figure_overlay), following the inset convention of
    scripts/plot_iteration_It_overlays_alisson81.py.
    """
    clusters = [c for c in CLUSTERS if c["protocol"] == protocol]
    fig, axes = plt.subplots(1, len(clusters), figsize=(20 * len(clusters), 20))
    axes = np.atleast_1d(axes)

    for ax, cluster in zip(axes, clusters):
        rows = cluster_rows(cluster)
        if DROP_FIRST_ITERATION:
            rows = rows.slice(1)

        time_offset = 0.0
        all_y: list[float] = []

        for i, row in enumerate(rows.iter_rows(named=True)):
            meas = read_measurement_parquet(Path(row["parquet_path"]))
            t = meas["t (s)"].to_numpy().astype(np.float64)
            I = meas["I (A)"].to_numpy().astype(np.float64)
            finite = np.isfinite(t) & np.isfinite(I)
            t, I = t[finite], I[finite]
            if t.size < 2:
                continue

            # Zero-base each segment and drop the first sample (instrument
            # glitch on It restart), as in the power_sweeps sequential plots.
            t_seg = (t - t[0])[1:]
            y_seg = (I * 1e6)[1:]

            ax.plot(
                t_seg + time_offset,
                y_seg,
                color=cluster["color"],
                linewidth=TRACE_LINEWIDTH,
                label=cluster_label(cluster) if i == 0 else None,
            )
            all_y.extend(y_seg.tolist())

            time_offset += float(t_seg[-1])

        if all_y:
            y = np.asarray(all_y, dtype=float)
            y_min, y_max = float(y.min()), float(y.max())
            pad = config.padding_fraction * (y_max - y_min)
            ax.set_ylim(y_min - pad, y_max + pad)

        ax.set_xlim(0.0, time_offset)
        ax.set_xlabel(r"$t$ (s)")
        ax.set_ylabel(r"$I_{ds}$ ($\mu$A)")
        ax.legend(loc="best", fontsize=_legend_fontsize(), framealpha=LEGEND_FRAMEALPHA)

        if inset:
            _overlay_inset(ax, cluster, config)

    plt.tight_layout()
    stem = "it_sequential" + ("_with_overlay_inset" if inset else "")
    _save(fig, config, f"{stem}_{PROTOCOLS[protocol]['stem']}")


def _overlay_inset(ax, cluster: dict, config: PlotConfig) -> None:
    """Drift-corrected overlay, colored by iteration, inset into a panel."""
    traces = cluster_traces(cluster)
    if DROP_FIRST_ITERATION:
        traces = traces[1:]
    n = len(traces)
    if n == 0:
        return

    axin = ax.inset_axes(cluster.get("inset_bbox", INSET_BBOX))
    # Sit above the host axes so the segment-boundary lines do not show through.
    axin.set_zorder(5)
    axin.patch.set_facecolor("white")
    axin.patch.set_alpha(1.0)
    cmap = mpl.colormaps["viridis"]

    visible: list[float] = []
    t_max = 0.0
    for k, tr in enumerate(traces):
        t, y = tr["t"], tr["I_corr"] * 1e6
        axin.plot(t, y, color=cmap(k / max(1, n - 1)), linewidth=TRACE_LINEWIDTH)
        t_max = max(t_max, float(t[-1]))
        visible.extend(y[t >= PLOT_START_TIME].tolist())

    axin.axvspan(EVAL_T_PRE, EVAL_T_POST, alpha=config.light_window_alpha, zorder=0)
    axin.axhline(0.0, color="k", linewidth=0.8, alpha=0.4, zorder=1)
    axin.set_xlim(PLOT_START_TIME, t_max)
    if visible:
        v = np.asarray(visible, dtype=float)
        v = v[np.isfinite(v)]
        if v.size:
            lo, hi = float(v.min()), float(v.max())
            if hi > lo:
                pad = config.padding_fraction * (hi - lo)
                axin.set_ylim(lo - pad, hi + pad)
    axin.set_xticks([60, 120, 180])
    axin.set_xlabel(r"$t$ (s)")
    axin.set_ylabel(r"$I_{corr}$ ($\mu$A)")


def _save(fig, config: PlotConfig, stem: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{stem}.{config.format}"
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    for protocol, meta in PROTOCOLS.items():
        print(f"\n{meta['label']} — {meta['wavelength_nm']} nm")
        for quantity in ("photocurrent", "responsivity"):
            figure_iteration(config, protocol, quantity)
        figure_overlay(config, protocol)
        figure_sequential(config, protocol)
        figure_sequential(config, protocol, inset=True)


if __name__ == "__main__":
    main()
