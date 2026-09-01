"""
Unified drift-corrected It overlays for chips 67/72/74/75/80/81 + drift-model
comparison.

Layout: three pair-figures with shared y-axis, square per-chip panels.
  Pair 1: (72 hBN | 67 hBN)
  Pair 2: (74 biotite | 75 biotite)
  Pair 3: (80 biotite | 81 biotite)

Each panel overlays one corrected I(t) per wavelength.

Drift model: stretched-exponential fit on t ∈ [30, 60] s, subtracted from the
full trace; baseline anchored so I_corr(60 s) = 0; trace plotted from t = 20 s.

For every chip × wavelength we ALSO fit a linear drift on the same window and
compare RMSE_window (lower wins). Results: LaTeX table on disk + markdown
table printed to stdout.

Run from repo root:
    python scripts/compare_corrected_It_67_72_74_75_80_81_pairs.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.linear_fit import fit_linear, linear_model
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import PRISM_RAIN_PALETTE, set_plot_style

ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_DIR = Path("figs/drift_unified_67_72_74_75_80_81")

# Legend font: 2 pt larger than the "small" relative size, resolved against the
# active theme's base font size so it stays correct regardless of theme.
LEGEND_FONTSIZE_BUMP = 2.0


def _legend_fontsize(relative: str = "small") -> float:
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


# Line/marker weights, matching the heavier styling of
# scripts/power_sweeps/plot_it_sequential_and_powerlaw_67_75may14_365nm.py.
# The theme defaults are lw 4.0 / markersize 22.
TRACE_LINEWIDTH = 5.5      # It(t) overlays
LINE_WIDTH = 5.5           # vs-wavelength curves
MARKER_SIZE = 30.0         # vs-wavelength points (filled, material-coded)

# Shared legend placed under a 1x2 panel figure, styled like the 1x2 overlay in
# the power-sweep script (large type, one row, hung just below the axes).
BELOW_LEGEND_FONTSIZE = 42.0
BELOW_LEGEND_TITLE_FONTSIZE = 46.0
BELOW_LEGEND_HANDLE_LW = 13.0

# Responsivity: R = |ΔI_corr| / P_device, P_device = P_beam · (A_device / A_beam).
# Beam spot area (µm²) is per-chip: chips 67 and 81 were measured with a 1e5 µm²
# spot, the rest with 1.2e5 µm².
BEAM_AREA_UM2_DEFAULT = 1.2e5
BEAM_AREA_UM2_BY_CHIP = {67: 1e5, 81: 1e5}
ENCAP_YAML = Path("config/encap_characteristics.yaml")
RESPONSIVITY_CHIPS = [75, 74, 72, 67]


def beam_area_um2(chip_number: int) -> float:
    return BEAM_AREA_UM2_BY_CHIP.get(chip_number, BEAM_AREA_UM2_DEFAULT)


def chip_materials() -> dict[int, str]:
    """Per-chip bottom-dielectric material from config/encap_characteristics.yaml."""
    import yaml

    if not ENCAP_YAML.exists():
        return {}
    data = yaml.safe_load(ENCAP_YAML.read_text()) or {}
    return {
        int(k): str(v["material"])
        for k, v in data.items()
        if isinstance(k, int) and isinstance(v, dict) and "material" in v
    }

DEFAULT_FIT_T_START = 0.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
PLOT_START_TIME = 50.0
TICK_STEP = 30.0  # ticks at 60, 90, 120, … (multiples of 30)

CHIPS = {
    67: {"seqs": [4, 15, 27, 41, 103, 102, 100, 98, 96, 94]},
    72: {"seqs": [103, 105, 107, 112, 114, 116, 118, 120, 122, 124]},
    74: {"seqs": [5, 7, 9, 11, 13, 17, 20, 22, 24, 28],
         "fit_t_start": 30.0},
    75: {"seqs": [62, 64, 69, 71, 73, 75, 77, 81, 83, 85]},
    80: {"seqs": [95, 97, 99, 101, 103, 105, 107, 109, 111, 113]},
    81: {"seqs": [4, 6, 8, 10, 12, 14, 16, 18, 33, 35]},
}

# Legend/title labels: "{chip} ({material})", material from encap config.
_MATERIALS = chip_materials()
for _chip, _cfg in CHIPS.items():
    _mat = _MATERIALS.get(_chip)
    _cfg["label"] = f"{_chip} ({_mat})" if _mat else str(_chip)

PAIRS = [(72, 67), (74, 75), (80, 81)]

# Chip 80 responsivity re-measurement (2026-07-01): the 365-505 nm points were
# re-taken at Vg = -2.0 V. Longer wavelengths (565-850 nm) are retained from the
# original 2026-04-28 sweep (Vg = 0.0 V), so this curve mixes two gate voltages.
# Repeat runs collapsed to the last (highest-seq) run per wavelength, except
# 505 nm which uses seq 180 (It2026-07-01_11.csv).
#   365:191  385:187  405:185  455:183  505:180  565:103  590:101  625:99
#   680:97   850:95
CHIP80_REMEASURED_SEQS = [95, 97, 99, 101, 103, 180, 183, 185, 187, 191]

# July-only subset (365-505 nm, all Vg = -2.0 V) — single gate voltage, no
# mixing with the retained April long-wavelength points.
CHIP80_REMEASURED_SEQS_JULY_ONLY = [180, 183, 185, 187, 191]


def load_history(chip_number: int) -> pl.DataFrame:
    path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched history missing for chip {chip_number}: {path}. "
            f"Run: biotite build-all-histories && biotite enrich-history {chip_number}"
        )
    return pl.read_parquet(path)


def device_areas_um2() -> dict[int, float]:
    """Per-chip flake area (µm²) from config/encap_characteristics.yaml."""
    import yaml

    if not ENCAP_YAML.exists():
        return {}
    data = yaml.safe_load(ENCAP_YAML.read_text()) or {}
    return {
        int(k): float(v["flake_area_um2"])
        for k, v in data.items()
        if isinstance(k, int) and isinstance(v, dict) and "flake_area_um2" in v
    }


def select_its_rows(history: pl.DataFrame, seqs: list[int]) -> pl.DataFrame:
    rows = (
        history
        .filter(pl.col("seq").is_in(seqs))
        .filter(pl.col("proc") == "It")
        .filter(pl.col("has_light") == True)  # noqa: E712
    )
    if rows.height == 0:
        raise ValueError(f"no It+light rows matched seqs={seqs}")
    return rows.sort("wavelength_nm")


def _window_mask(t: np.ndarray, fit_t_start: float) -> np.ndarray:
    mask = (t >= fit_t_start) & (t <= FIT_T_END)
    if mask.size:
        mask[0] = False
    return mask


def _rmse(residuals: np.ndarray) -> float:
    r = residuals[np.isfinite(residuals)]
    if r.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(r * r)))


def fit_both_models(t: np.ndarray, i: np.ndarray, fit_t_start: float) -> dict:
    """Fit stretched-exp and linear on [fit_t_start, 60] s. Returns dict with
    both fits, window RMSEs, R², and full-trace stretched-exp drift array."""
    finite = np.isfinite(t) & np.isfinite(i)
    t = t[finite]
    i = i[finite]
    mask = _window_mask(t, fit_t_start)

    out: dict = {
        "stretched": {"rmse": float("nan"), "r_squared": float("nan"),
                      "converged": False},
        "linear": {"rmse": float("nan"), "r_squared": float("nan")},
        "stretched_drift_full": np.full_like(i, np.nan),
        "t_full": t,
        "i_full": i,
    }

    if mask.sum() < 10:
        return out

    t_w = t[mask]
    i_w = i[mask]

    try:
        se = fit_stretched_exponential(t_w, i_w)
        se_window_curve = se["fitted_curve"]
        out["stretched"]["rmse"] = _rmse(i_w - se_window_curve)
        out["stretched"]["r_squared"] = float(se["r_squared"])
        out["stretched"]["converged"] = bool(se.get("converged", False))
        out["stretched_drift_full"] = stretched_exponential(
            t, se["baseline"], se["amplitude"], se["tau"], se["beta"]
        )
    except Exception as exc:
        print(f"  stretched-exp fit failed: {exc}")

    try:
        lin = fit_linear(t_w, i_w)
        lin_window_curve = lin["fitted_curve"]
        out["linear"]["rmse"] = _rmse(i_w - lin_window_curve)
        out["linear"]["r_squared"] = float(lin["r_squared"])
        out["linear_drift_full"] = linear_model(t, lin["slope"], lin["intercept"])
    except Exception as exc:
        print(f"  linear fit failed: {exc}")

    return out


def corrected_trace(fit_result: dict) -> np.ndarray:
    """Subtract stretched-exp drift across the full trace; anchor I_corr(60s)=0."""
    t = fit_result["t_full"]
    i = fit_result["i_full"]
    drift = fit_result["stretched_drift_full"]
    if not np.any(np.isfinite(drift)):
        return np.full_like(i, np.nan)
    i_corr = i - drift
    idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
    baseline = i_corr[idx_pre]
    if np.isfinite(baseline):
        i_corr = i_corr - baseline
    return i_corr


def light_window(meas, t: np.ndarray) -> tuple[float, float] | None:
    if "VL (V)" not in meas.columns:
        return None
    vl = meas["VL (V)"].to_numpy()
    on_idx = np.where(vl > 0.1)[0]
    if not on_idx.size:
        return None
    return (float(t[on_idx[0]]), float(t[on_idx[-1]]))


def collect_chip_traces(
    chip_number: int, seqs: list[int] | None = None
) -> list[dict]:
    """Returns list of per-wavelength dicts for one chip. `seqs` overrides the
    default seq selection from CHIPS (used for the chip-80 re-measurement)."""
    history = load_history(chip_number)
    chip_cfg = CHIPS[chip_number]
    rows = select_its_rows(history, seqs if seqs is not None else chip_cfg["seqs"])
    fit_t_start = float(chip_cfg.get("fit_t_start", DEFAULT_FIT_T_START))

    traces: list[dict] = []
    for row in rows.iter_rows(named=True):
        parquet_path = Path(row.get("parquet_path") or "")
        if not parquet_path.exists():
            print(f"  [chip {chip_number}] missing parquet: {parquet_path}")
            continue
        meas = read_measurement_parquet(parquet_path)
        if "t (s)" not in meas.columns or "I (A)" not in meas.columns:
            continue
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)
        wl = row.get("wavelength_nm")

        fit = fit_both_models(t, i, fit_t_start)
        i_corr = corrected_trace(fit)

        # Uncorrected trace: same baseline anchor as `biotite plot-its` —
        # shift so I(EVAL_T_PRE) = 0. No drift subtraction.
        i_raw_full = fit["i_full"]
        t_full = fit["t_full"]
        idx_pre = int(np.argmin(np.abs(t_full - EVAL_T_PRE)))
        baseline_raw = i_raw_full[idx_pre]
        i_uncorr = i_raw_full - baseline_raw if np.isfinite(baseline_raw) else i_raw_full

        traces.append({
            "chip": chip_number,
            "wavelength_nm": float(wl) if wl is not None else float("nan"),
            "vg_v": (float(row.get("vg_fixed_v"))
                     if row.get("vg_fixed_v") is not None else None),
            "power_w": (float(row.get("irradiated_power_w"))
                        if row.get("irradiated_power_w") is not None else None),
            "t": fit["t_full"],
            "i_raw_uA": i_uncorr * 1e6,
            "i_corr_uA": i_corr * 1e6,
            "light_span": light_window(meas, fit["t_full"]),
            "rmse_stretched_uA": fit["stretched"]["rmse"] * 1e6,
            "rmse_linear_uA": fit["linear"]["rmse"] * 1e6,
            "r2_stretched": fit["stretched"]["r_squared"],
            "r2_linear": fit["linear"]["r_squared"],
        })
    return traces


def _wavelength_color_map(traces: list[dict]) -> dict[float, str]:
    """Match `biotite plot-its` convention: sort wavelengths ascending, assign
    PRISM_RAIN_PALETTE colors in order (cycling if more wavelengths than colors)."""
    wls = sorted({tr["wavelength_nm"] for tr in traces if np.isfinite(tr["wavelength_nm"])})
    n = len(PRISM_RAIN_PALETTE)
    return {wl: PRISM_RAIN_PALETTE[idx % n] for idx, wl in enumerate(wls)}


def _annotate_panel_letters(
    axes, letters: list[str], x: float | list[float] = -0.13
) -> None:
    """Stamp bold 'a', 'b', ... outside each axes, above the y-axis label.

    `x` is the axes-fraction offset of the letter; pass a list to shift
    individual panels (a panel that still shows y tick labels needs more
    clearance than one where they were dropped). Mirrors the helper in
    scripts/IVg Analysis/plot_ivg_365nm_triplet_compare.py so multi-panel
    figures across the two scripts carry the same panel labelling.
    """
    flat = np.asarray(axes).ravel()
    xs = [x] * len(flat) if isinstance(x, (int, float)) else list(x)
    for ax, letter, x_off in zip(flat, letters, xs):
        ax.text(
            x_off,
            1.0,
            f"{letter}",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontweight="bold",
            fontsize=56,
        )


def plot_pair(
    pair: tuple[int, int],
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
    *,
    field: str = "i_corr_uA",
    ylabel: str = r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
    plot_start: float = PLOT_START_TIME,
    show_titles: bool = True,
    panel_letters: list[str] | None = None,
    share_y: bool = True,
    box_aspect: float = 1.0,
    legend_columnspacing: float | None = None,
    legend_below: bool = False,
    legend_below_ncol: int | None = None,
    light_span_color: str | None = None,
    legend_below_pad: float | None = None,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, axes = plt.subplots(1, 2, figsize=(2 * side, side), sharey=share_y)

    all_traces = traces_by_chip[pair[0]] + traces_by_chip[pair[1]]
    color_for_wl = _wavelength_color_map(all_traces)

    # Visible y values, kept per panel so the limits can be set either
    # jointly (share_y) or independently.
    y_by_panel: list[list[float]] = [[], []]
    t_totals: list[float] = []

    for idx, (ax, chip_num) in enumerate(zip(axes, pair)):
        traces = traces_by_chip[chip_num]
        for tr in traces:
            color = color_for_wl.get(tr["wavelength_nm"], "k")
            ax.plot(
                tr["t"], tr[field],
                color=color, linestyle="-", linewidth=TRACE_LINEWIDTH,
                label=f"{tr['wavelength_nm']:.0f} nm",
            )
            visible = tr["t"] >= plot_start
            y_by_panel[idx].extend(tr[field][visible])
            t_totals.append(float(tr["t"][-1]))

        spans = [tr["light_span"] for tr in traces if tr.get("light_span")]
        if spans:
            s = float(np.median([sp[0] for sp in spans]))
            e = float(np.median([sp[1] for sp in spans]))
            span_kw = ({"color": light_span_color, "lw": 0}
                       if light_span_color else {})
            ax.axvspan(s, e, alpha=config.light_window_alpha, **span_kw)

        vgs = [tr["vg_v"] for tr in traces if tr.get("vg_v") is not None]
        title = CHIPS[chip_num]["label"]
        if vgs:
            vg_repr = float(np.median(vgs))
            title = f"{title}, $V_g = {vg_repr:g}$ V"

        ax.set_xlabel(r"$t\ (\mathrm{s})$")
        if show_titles:
            ax.set_title(title)
        ax.set_box_aspect(box_aspect)

    if share_y:
        axes[0].set_ylabel(ylabel)
    else:
        for ax in axes:
            ax.set_ylabel(ylabel)

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            for ax in axes:
                ax.set_xlim(plot_start, T_total)

    from matplotlib.ticker import MultipleLocator
    for ax in axes:
        ax.xaxis.set_major_locator(MultipleLocator(TICK_STEP))

    def _apply_ylim(ax, values: list[float]) -> None:
        y = np.array(values, dtype=float)
        y = y[np.isfinite(y)]
        if not y.size:
            return
        y_min, y_max = float(y.min()), float(y.max())
        if y_max > y_min:
            pad = config.padding_fraction * (y_max - y_min)
            ax.set_ylim(y_min - pad, y_max + pad)

    if share_y:
        # sharey ties both axes together, so one call covers the figure.
        _apply_ylim(axes[0], y_by_panel[0] + y_by_panel[1])
    else:
        for ax, values in zip(axes, y_by_panel):
            _apply_ylim(ax, values)

    legend_kw: dict = {}
    if legend_columnspacing is not None:
        legend_kw["columnspacing"] = legend_columnspacing
    if legend_below:
        # One shared block of wavelength swatches hung under both panels, in
        # place of the in-axes legend. Defaults to a single row;
        # legend_below_ncol wraps it onto several.
        from matplotlib.lines import Line2D

        handles = [
            Line2D([0], [0], color=color_for_wl[wl], lw=BELOW_LEGEND_HANDLE_LW,
                   label=f"{wl:.0f} nm")
            for wl in sorted(color_for_wl)
        ]
        if legend_below_ncol and len(handles) % legend_below_ncol == 0:
            # Matplotlib fills legend cells column-major; transpose the handle
            # order so the labels read left-to-right along each row instead.
            ncol = legend_below_ncol
            nrow = len(handles) // ncol
            handles = [handles[r * ncol + c]
                       for c in range(ncol) for r in range(nrow)]
        below_legend = fig.legend(
            handles=handles,
            title="Wavelength",
            # When re-anchored below the axes the anchor is the legend's *top*
            # edge, so it grows downward instead of back over the x labels.
            loc="upper center" if legend_below_pad is not None else "lower center",
            bbox_to_anchor=(0.5, -0.04),
            ncol=legend_below_ncol if legend_below_ncol else len(handles),
            framealpha=0.9,
            fontsize=BELOW_LEGEND_FONTSIZE,
            title_fontsize=BELOW_LEGEND_TITLE_FONTSIZE,
            **legend_kw,
        )
    else:
        axes[1].legend(title="Wavelength", loc="best", framealpha=0.9, ncol=2,
                       fontsize=_legend_fontsize(),
                       title_fontsize=_legend_fontsize(),
                       **legend_kw)

    if panel_letters:
        # With shared y the right panel has no tick labels, so its letter hugs
        # its own spine; with independent y both panels need equal clearance.
        letter_x = [-0.20, -0.07] if share_y else [-0.20, -0.20]
        _annotate_panel_letters(axes, panel_letters, x=letter_x)

    plt.tight_layout()

    if legend_below and legend_below_pad is not None:
        # The fixed -0.04 figure-fraction anchor assumes the axes reach the
        # bottom of the figure; with a forced box aspect they don't, and the
        # legend lands on top of the x labels. Re-anchor it legend_below_pad
        # below whatever the axes (ticks + xlabel included) actually occupy.
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        inv = fig.transFigure.inverted()
        axes_bottom = min(
            inv.transform_bbox(ax.get_tightbbox(renderer)).y0 for ax in axes
        )
        below_legend.set_bbox_to_anchor(
            (0.5, axes_bottom - legend_below_pad), transform=fig.transFigure
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def plot_single(
    chip_num: int,
    traces: list[dict],
    config: PlotConfig,
    output_path: Path,
    *,
    field: str = "i_corr_uA",
    ylabel: str = r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
    plot_start: float = PLOT_START_TIME,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side, side))

    color_for_wl = _wavelength_color_map(traces)

    all_y: list[float] = []
    t_totals: list[float] = []

    for tr in traces:
        color = color_for_wl.get(tr["wavelength_nm"], "k")
        ax.plot(
            tr["t"], tr[field],
            color=color, linestyle="-", linewidth=TRACE_LINEWIDTH,
            label=f"{tr['wavelength_nm']:.0f} nm",
        )
        visible = tr["t"] >= plot_start
        all_y.extend(tr[field][visible])
        t_totals.append(float(tr["t"][-1]))

    spans = [tr["light_span"] for tr in traces if tr.get("light_span")]
    if spans:
        s = float(np.median([sp[0] for sp in spans]))
        e = float(np.median([sp[1] for sp in spans]))
        ax.axvspan(s, e, alpha=config.light_window_alpha)

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(ylabel)
    ax.set_box_aspect(1.0)

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            ax.set_xlim(plot_start, T_total)

    from matplotlib.ticker import MultipleLocator
    ax.xaxis.set_major_locator(MultipleLocator(TICK_STEP))

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                ax.set_ylim(y_min - pad, y_max + pad)

    ax.legend(title="Wavelength", loc="best", framealpha=0.9, ncol=2,
              fontsize=_legend_fontsize(), title_fontsize=_legend_fontsize())

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


CHIP_COLORS = {67: "C0", 72: "C4", 74: "C3", 75: "C1", 80: "C2", 81: "C5"}

# Legend reading order for the 3x2 chip legends: biotite devices first.
LEGEND_ROW_ORDER = [74, 75, 67, 72, 80, 81]

# Marker by material (from encap config), so each material shares one marker.
MATERIAL_MARKERS = {"hBN": "o", "biotite": "s"}


def chip_marker(chip_number: int) -> str:
    return MATERIAL_MARKERS.get(_MATERIALS.get(chip_number, ""), "o")
EVAL_T_POST = 120.0


def photoresponse_at_post(tr: dict) -> float:
    """ΔI corrected = peak drift-corrected deviation over the illuminated window
    t ∈ [EVAL_T_PRE, EVAL_T_POST], relative to the EVAL_T_PRE onset — the "true"
    photoresponse (matches CorrectedDeltaIExtractor delta_mode="max_deviation").
    Since i_corr is anchored at I_corr(EVAL_T_PRE)=0, the deviation is i_corr
    itself; this returns the signed value at the point of maximum |i_corr| in
    the window."""
    t = tr["t"]
    y = tr["i_corr_uA"]
    if t.size == 0 or not np.any(np.isfinite(y)):
        return float("nan")
    win = (t >= EVAL_T_PRE) & (t <= EVAL_T_POST) & np.isfinite(y)
    win_idx = np.flatnonzero(win)
    if win_idx.size == 0:
        return float("nan")
    peak = win_idx[int(np.argmax(np.abs(y[win_idx])))]
    return float(y[peak])


def responsivity_at_post(tr: dict, area_um2: float | None) -> float:
    """R = |ΔI_corr| / P_device (A/W); P_device = P_beam · A_device/A_beam."""
    di_uA = abs(photoresponse_at_post(tr))
    p_w = tr.get("power_w")
    if area_um2 is None or p_w is None or not np.isfinite(p_w) or p_w <= 0:
        return float("nan")
    p_dev_w = p_w * (area_um2 / beam_area_um2(int(tr["chip"])))
    return (di_uA * 1e-6) / p_dev_w


# Square |I_ph| inset dropped into the R vs wavelength panel: box, marker and
# line sizes relative to the main axes (fonts stay at the theme size).
INSET_HEIGHT = 0.44   # fraction of the host axes height
INSET_RIGHT = 0.97    # right edge, in host-axes fraction
INSET_TOP = 0.97      # top edge, in host-axes fraction
INSET_MARKER_SIZE = MARKER_SIZE * 0.6
INSET_LINE_WIDTH = LINE_WIDTH * 0.6


def _square_inset_rect(ax: plt.Axes) -> list[float]:
    """[x0, y0, w, h] in host-axes fraction for a box that renders 1:1.

    set_box_aspect() is useless on an inset: its locator rewrites the position
    on every draw and undoes the aspect adjustment. So the width is scaled by
    the host axes' own drawn aspect (height/width) instead."""
    host_aspect = ax.get_box_aspect()
    if host_aspect is None:
        pos = ax.get_position()
        fig_w, fig_h = ax.figure.get_size_inches()
        host_aspect = (pos.height * fig_h) / (pos.width * fig_w)
    w = INSET_HEIGHT * float(host_aspect)
    return [INSET_RIGHT - w, INSET_TOP - INSET_HEIGHT, w, INSET_HEIGHT]


def add_photocurrent_inset(
    ax: plt.Axes,
    traces_by_chip: dict[int, list[dict]],
    chips: list[int],
    *,
    wl_max: float = 505.0,
) -> plt.Axes:
    """Square (1:1) inset: |I_ph| vs wavelength over the short-wavelength range
    only (365 nm to wl_max), same chip colors/markers as the host panel."""
    axin = ax.inset_axes(_square_inset_rect(ax))
    for chip_num in chips:
        pts = []
        for tr in traces_by_chip.get(chip_num, []):
            wl = tr["wavelength_nm"]
            di = photoresponse_at_post(tr)
            if np.isfinite(wl) and wl <= wl_max and np.isfinite(di):
                pts.append((wl, abs(di)))
        if not pts:
            continue
        pts.sort()
        axin.plot(
            [p[0] for p in pts], [p[1] for p in pts],
            color=CHIP_COLORS.get(chip_num, "k"),
            marker=chip_marker(chip_num),
            markersize=INSET_MARKER_SIZE,
            linestyle="-",
            linewidth=INSET_LINE_WIDTH,
        )
    axin.set_xlabel(r"Wavelength (nm)")
    axin.set_ylabel(r"$|I_{ph}|\ (\mu\mathrm{A})$")
    axin.set_xticks([400, 500])
    axin.patch.set_alpha(0.9)
    return axin


def _legend_entries_by_row(
    handle_by_chip: dict[int, object], row_order: list[int], ncol: int
) -> tuple[list, list]:
    """Order (handles, labels) so a legend with `ncol` columns reads
    left-to-right along each row in `row_order`. Matplotlib fills legend cells
    column-major, so the row-major grid is transposed here."""
    order = [c for c in row_order if c in handle_by_chip]
    order += [c for c in handle_by_chip if c not in order]
    nrow = -(-len(order) // ncol)
    seq = [order[r * ncol + c]
           for c in range(ncol) for r in range(nrow)
           if r * ncol + c < len(order)]
    return ([handle_by_chip[c] for c in seq],
            [CHIPS[c]["label"] for c in seq])


def plot_responsivity_vs_wl(
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
    *,
    chips: list[int] | None = None,
    logy: bool = False,
    box_aspect: float = 1.0,
    legend_chip_order: list[int] | None = None,
    iph_inset: bool = False,
    iph_inset_wl_max: float = 505.0,
    legend_loc: str = "best",
    legend_bbox_to_anchor: tuple[float, float] | None = None,
    legend_fontsize_extra: float = 0.0,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / box_aspect, side))

    chips = chips if chips is not None else RESPONSIVITY_CHIPS
    areas = device_areas_um2()
    handle_by_chip: dict[int, object] = {}
    for chip_num in chips:
        traces = traces_by_chip.get(chip_num, [])
        area = areas.get(chip_num)
        pts = []
        for tr in traces:
            wl = tr["wavelength_nm"]
            r = responsivity_at_post(tr, area)
            if np.isfinite(wl) and np.isfinite(r):
                pts.append((wl, r))
        if not pts:
            print(f"  [chip {chip_num}] no responsivity points (area={area})")
            continue
        pts.sort()
        wls = np.array([p[0] for p in pts])
        rs = np.array([p[1] for p in pts])
        line, = ax.plot(
            wls, rs,
            color=CHIP_COLORS.get(chip_num, "k"),
            marker=chip_marker(chip_num),
            markersize=MARKER_SIZE,
            linestyle="-",
            linewidth=LINE_WIDTH,
            label=CHIPS[chip_num]["label"],
        )
        handle_by_chip[chip_num] = line

    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(r"$R$ (A/W)")
    ax.set_box_aspect(box_aspect)
    legend_args = ()
    if legend_chip_order is not None:
        legend_args = _legend_entries_by_row(handle_by_chip, legend_chip_order, 2)
    legend_kw: dict = {}
    if legend_bbox_to_anchor is not None:
        legend_kw["bbox_to_anchor"] = legend_bbox_to_anchor
        legend_kw["bbox_transform"] = ax.transAxes
    ax.legend(*legend_args, loc=legend_loc, framealpha=0.9, ncol=2,
              fontsize=_legend_fontsize() + legend_fontsize_extra, **legend_kw)

    if iph_inset:
        add_photocurrent_inset(
            ax, traces_by_chip, chips, wl_max=iph_inset_wl_max
        )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def write_responsivity_csv(
    traces_by_chip: dict[int, list[dict]],
    output_path: Path,
    *,
    chips: list[int] | None = None,
) -> None:
    """Write the responsivity-vs-wavelength points as CSV (same data the
    matching figure plots): one row per wavelength, one column per chip."""
    chips = chips if chips is not None else RESPONSIVITY_CHIPS
    areas = device_areas_um2()

    by_chip: dict[int, dict[float, float]] = {}
    for chip_num in chips:
        area = areas.get(chip_num)
        pts = {}
        for tr in traces_by_chip.get(chip_num, []):
            wl = tr["wavelength_nm"]
            r = responsivity_at_post(tr, area)
            if np.isfinite(wl) and np.isfinite(r):
                pts[float(wl)] = float(r)
        if not pts:
            print(f"  [chip {chip_num}] no responsivity points for CSV (area={area})")
            continue
        by_chip[chip_num] = pts

    wls = sorted({wl for pts in by_chip.values() for wl in pts})
    table = {"wavelength_nm": wls}
    for chip_num, pts in by_chip.items():
        material = _MATERIALS.get(chip_num, "").replace(" ", "_")
        col = f"R_A_per_W_{chip_num}" + (f"_{material}" if material else "")
        table[col] = [pts.get(wl, float("nan")) for wl in wls]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(table).write_csv(output_path)
    print(f"saved {output_path}")


def plot_responsivity_old_vs_new_chip80(
    config: PlotConfig,
    output_path: Path,
    *,
    wl_max: float = 505.0,
    logy: bool = False,
    box_aspect: float = 1.0,
) -> None:
    """Chip-80 responsivity, old (2026-04-28, Vg = 0 V) vs re-measured
    (2026-07-01, Vg = -2.0 V), restricted to the 365-505 nm range where the
    device shows real above-noise response."""
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / box_aspect, side))

    area = device_areas_um2().get(80)
    series = [
        ("old", collect_chip_traces(80), r"Old ($V_g = 0$ V)", "C3", "o"),
        ("new", collect_chip_traces(80, seqs=CHIP80_REMEASURED_SEQS),
         r"New ($V_g = -2$ V)", "C2", "s"),
    ]

    for _key, traces, label, color, marker in series:
        pts = []
        for tr in traces:
            wl = tr["wavelength_nm"]
            r = responsivity_at_post(tr, area)
            if np.isfinite(wl) and wl <= wl_max and np.isfinite(r):
                pts.append((wl, r))
        if not pts:
            print(f"  [chip 80 {_key}] no responsivity points <= {wl_max} nm")
            continue
        pts.sort()
        wls = np.array([p[0] for p in pts])
        rs = np.array([p[1] for p in pts])
        ax.plot(
            wls, rs, color=color, marker=marker, markersize=MARKER_SIZE,
            linestyle="-", linewidth=LINE_WIDTH, label=label,
        )

    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(r"$R$ (A/W)")
    ax.set_box_aspect(box_aspect)
    ax.legend(loc="best", framealpha=0.9, fontsize=_legend_fontsize())

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def plot_photoresponse_vs_wl(
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
    *,
    chips: list[int] | None = None,
    ylabel: str = r"$|\Delta I_{\mathrm{corr}}|\ (\mu\mathrm{A})$",
    logy: bool = False,
    box_aspect: float = 1.0,
    legend_chip_order: list[int] | None = None,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / box_aspect, side))

    chips = chips if chips is not None else list(traces_by_chip)
    handle_by_chip: dict[int, object] = {}
    for chip_num in chips:
        traces = traces_by_chip.get(chip_num, [])
        pts = []
        for tr in traces:
            wl = tr["wavelength_nm"]
            di = photoresponse_at_post(tr)
            if np.isfinite(wl) and np.isfinite(di):
                pts.append((wl, di))
        if not pts:
            continue
        pts.sort()
        wls = np.array([p[0] for p in pts])
        dis = np.abs(np.array([p[1] for p in pts]))
        line, = ax.plot(
            wls, dis,
            color=CHIP_COLORS.get(chip_num, "k"),
            marker=chip_marker(chip_num),
            markersize=MARKER_SIZE,
            linestyle="-",
            linewidth=LINE_WIDTH,
            label=CHIPS[chip_num]["label"],
        )
        handle_by_chip[chip_num] = line

    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(ylabel)
    ax.set_box_aspect(box_aspect)
    legend_args = ()
    if legend_chip_order is not None:
        legend_args = _legend_entries_by_row(handle_by_chip, legend_chip_order, 2)
    ax.legend(*legend_args, loc="best", framealpha=0.9, ncol=2,
              fontsize=_legend_fontsize())

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def build_comparison_table(
    traces_by_chip: dict[int, list[dict]],
) -> list[dict]:
    rows: list[dict] = []
    for chip_num, traces in traces_by_chip.items():
        for tr in traces:
            rs = tr["rmse_stretched_uA"]
            rl = tr["rmse_linear_uA"]
            if np.isfinite(rs) and np.isfinite(rl):
                if rs <= rl:
                    winner, gap = "stretched", (rl - rs) / rs * 100.0 if rs > 0 else float("nan")
                else:
                    winner, gap = "linear", (rs - rl) / rl * 100.0 if rl > 0 else float("nan")
            elif np.isfinite(rl):
                winner, gap = "linear", float("nan")
            elif np.isfinite(rs):
                winner, gap = "stretched", float("nan")
            else:
                winner, gap = "—", float("nan")
            rows.append({
                "chip": chip_num,
                "label": CHIPS[chip_num]["label"],
                "wavelength_nm": tr["wavelength_nm"],
                "rmse_stretched_uA": rs,
                "rmse_linear_uA": rl,
                "r2_stretched": tr["r2_stretched"],
                "r2_linear": tr["r2_linear"],
                "winner": winner,
                "gap_pct": gap,
            })
    return rows


def _fmt(x: float, prec: int = 4) -> str:
    if not np.isfinite(x):
        return "—"
    return f"{x:.{prec}g}"


def print_markdown_table(rows: list[dict]) -> None:
    header = (
        "| Chip | λ (nm) | RMSE stretched (µA) | RMSE linear (µA) | "
        "R² stretched | R² linear | Winner | Δ% |"
    )
    sep = "|" + "|".join(["---"] * 8) + "|"
    print()
    print(header)
    print(sep)
    for r in rows:
        print(
            f"| {r['label']} | {r['wavelength_nm']:.0f} | "
            f"{_fmt(r['rmse_stretched_uA'])} | {_fmt(r['rmse_linear_uA'])} | "
            f"{_fmt(r['r2_stretched'])} | {_fmt(r['r2_linear'])} | "
            f"{r['winner']} | {_fmt(r['gap_pct'], 3)} |"
        )

    print()
    print("Per-chip winner summary:")
    by_chip: dict[int, list[str]] = {}
    for r in rows:
        by_chip.setdefault(r["chip"], []).append(r["winner"])
    for chip_num, winners in by_chip.items():
        n = len(winners)
        n_se = sum(w == "stretched" for w in winners)
        n_lin = sum(w == "linear" for w in winners)
        print(f"  chip {chip_num} ({CHIPS[chip_num]['label']}): "
              f"stretched {n_se}/{n}, linear {n_lin}/{n}")


def write_latex_table(rows: list[dict], output_path: Path) -> None:
    lines: list[str] = []
    lines.append("% Drift-model comparison on t ∈ [30, 60] s. RMSE on fit window.")
    lines.append("\\begin{tabular}{llrrrrll}")
    lines.append("\\toprule")
    lines.append("Chip & $\\lambda$ (nm) & RMSE$_\\mathrm{str}$ ($\\mu$A) & "
                 "RMSE$_\\mathrm{lin}$ ($\\mu$A) & $R^2_\\mathrm{str}$ & "
                 "$R^2_\\mathrm{lin}$ & Winner & $\\Delta$\\% \\\\")
    lines.append("\\midrule")
    for r in rows:
        lines.append(
            f"{r['label']} & {r['wavelength_nm']:.0f} & "
            f"{_fmt(r['rmse_stretched_uA'])} & {_fmt(r['rmse_linear_uA'])} & "
            f"{_fmt(r['r2_stretched'])} & {_fmt(r['r2_linear'])} & "
            f"{r['winner']} & {_fmt(r['gap_pct'], 3)} \\\\"
        )
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")
    print(f"saved {output_path}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    traces_by_chip: dict[int, list[dict]] = {}
    for chip_num in CHIPS:
        print(f"[chip {chip_num}] collecting traces…")
        traces_by_chip[chip_num] = collect_chip_traces(chip_num)

    for pair in PAIRS:
        a, b = pair
        plot_pair(
            pair, traces_by_chip, config,
            OUTPUT_DIR / f"alisson{a}_{b}_It_corrected_overlay_pair.pdf",
            field="i_corr_uA",
            ylabel=r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
            plot_start=PLOT_START_TIME,
        )
        plot_pair(
            pair, traces_by_chip, config,
            OUTPUT_DIR / f"alisson{a}_{b}_It_uncorrected_overlay_pair.pdf",
            field="i_raw_uA",
            ylabel=r"$I\ (\mu\mathrm{A})$",
            plot_start=20.0,
        )

    for chip_num, traces in traces_by_chip.items():
        plot_single(
            chip_num, traces, config,
            OUTPUT_DIR / f"alisson{chip_num}_It_corrected_overlay.pdf",
            field="i_corr_uA",
            ylabel=r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
            plot_start=PLOT_START_TIME,
        )

    # Standalone 1x2 panel figure: 72 (left) | 75 (right), corrected It
    # overlay. Styled after the 1x2 grids in
    # scripts/IVg Analysis/plot_ivg_365nm_triplet_compare.py — no panel titles,
    # bold 'a'/'b' panel letters, square boxes, shared y with the right panel's
    # tick labels dropped.
    plot_pair(
        (72, 75), traces_by_chip, config,
        OUTPUT_DIR / "alisson72_75_It_corrected_overlay_pair_panels.pdf",
        field="i_corr_uA",
        ylabel=r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
        plot_start=40.0,
        show_titles=False,
        panel_letters=["a", "b"],
        share_y=False,
        box_aspect=6.0 / 7.0,  # 7:6 (width:height) panels
        legend_columnspacing=0.8,  # default is 2.0 font-size units
        legend_below=True,
    )
    # Same figure with chip 74 in place of 75.
    plot_pair(
        (72, 74), traces_by_chip, config,
        OUTPUT_DIR / "alisson72_74_It_corrected_overlay_pair_panels.pdf",
        field="i_corr_uA",
        ylabel=r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
        plot_start=50.0,
        show_titles=False,
        panel_letters=["a", "b"],
        share_y=False,
        box_aspect=1.0,  # square panels
        legend_columnspacing=0.8,  # default is 2.0 font-size units
        legend_below=True,
        legend_below_ncol=5,  # 10 wavelengths -> 2 rows
        # Same neutral gray as the LED-on bands in
        # scripts/power_sweeps/plot_it_sequential_and_powerlaw_67_75may14_365nm.py
        light_span_color="0.7",
        legend_below_pad=-0.01,  # negative: tuck it up closer to the x labels
    )

    plot_photoresponse_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson67_72_74_75_80_81_photoresponse_vs_wl.pdf",
    )

    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson75_74_72_67_responsivity_vs_wl.pdf",
    )
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson75_74_72_67_responsivity_vs_wl_semilogy.pdf",
        logy=True,
    )

    # All six chips from the original photoresponse plot.
    all_chips = list(CHIPS)
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson67_72_74_75_80_81_responsivity_vs_wl.pdf",
        chips=all_chips,
    )
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson67_72_74_75_80_81_responsivity_vs_wl.png",
        chips=all_chips,
    )
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson67_72_74_75_80_81_responsivity_vs_wl_semilogy.pdf",
        chips=all_chips,
        logy=True,
    )

    # Chip-80 re-measurement variant (2026-07-01): swap only chip 80's traces
    # for the re-measured 365-505 nm points; all other chips and outputs are
    # untouched. New files carry the "_80remeasured_2026-07-01" suffix.
    traces_by_chip_v2 = dict(traces_by_chip)
    traces_by_chip_v2[80] = collect_chip_traces(80, seqs=CHIP80_REMEASURED_SEQS)
    plot_responsivity_vs_wl(
        traces_by_chip_v2,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_responsivity_vs_wl_80remeasured_2026-07-01.pdf",
        chips=all_chips,
        legend_chip_order=LEGEND_ROW_ORDER,
    )
    plot_responsivity_vs_wl(
        traces_by_chip_v2,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_responsivity_vs_wl_80remeasured_2026-07-01.png",
        chips=all_chips,
        legend_chip_order=LEGEND_ROW_ORDER,
    )
    plot_responsivity_vs_wl(
        traces_by_chip_v2,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_responsivity_vs_wl_semilogy_80remeasured_2026-07-01.pdf",
        chips=all_chips,
        logy=True,
        legend_chip_order=LEGEND_ROW_ORDER,
    )
    # 4:3 (horizontal:vertical) aspect-ratio variant of the linear plot.
    plot_responsivity_vs_wl(
        traces_by_chip_v2,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_responsivity_vs_wl_80remeasured_2026-07-01_4x3.pdf",
        chips=all_chips,
        box_aspect=3.0 / 4.0,
        legend_chip_order=LEGEND_ROW_ORDER,
    )
    # Plotted values as a table, alongside the figure.
    write_responsivity_csv(
        traces_by_chip_v2,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_responsivity_vs_wl_80remeasured_2026-07-01.csv",
        chips=all_chips,
    )
    # Photocurrent twin of the same figure: |I_ph| instead of R, same chips,
    # same chip-80 re-measured traces.
    plot_photoresponse_vs_wl(
        traces_by_chip_v2,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_photocurrent_vs_wl_80remeasured_2026-07-01.pdf",
        chips=all_chips,
        ylabel=r"$|I_{ph}|\ (\mu\mathrm{A})$",
        legend_chip_order=LEGEND_ROW_ORDER,
    )
    # 4:3 R panel carrying a square (1:1) |I_ph| inset over 365-505 nm.
    plot_responsivity_vs_wl(
        traces_by_chip_v2,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_responsivity_vs_wl_80remeasured_2026-07-01"
          "_4x3_iph_inset.pdf",
        chips=all_chips,
        box_aspect=3.0 / 4.0,
        legend_chip_order=LEGEND_ROW_ORDER,
        iph_inset=True,
        legend_loc="upper left",  # inset owns the upper right
        # Dropped just below the chip-74 peak so the legend clears its marker.
        legend_bbox_to_anchor=(0.10, 0.93),
        legend_fontsize_extra=2.0,
    )
    # 4:3 (horizontal:vertical) aspect-ratio variant of the photocurrent plot.
    plot_photoresponse_vs_wl(
        traces_by_chip_v2,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_photocurrent_vs_wl_80remeasured_2026-07-01_4x3.pdf",
        chips=all_chips,
        ylabel=r"$|I_{ph}|\ (\mu\mathrm{A})$",
        box_aspect=3.0 / 4.0,
        legend_chip_order=LEGEND_ROW_ORDER,
    )

    # Chip-80 It corrected overlay for the re-measured data (single chip only).
    # (a) mixed: July 365-505 nm (Vg = -2 V) + retained April 565-850 nm (Vg = 0).
    plot_single(
        80, traces_by_chip_v2[80], config,
        OUTPUT_DIR / "alisson80_It_corrected_overlay_remeasured_mixed_2026-07-01.pdf",
        field="i_corr_uA",
        ylabel=r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
        plot_start=PLOT_START_TIME,
    )
    # (b) July-only: 365-505 nm at a single gate voltage (Vg = -2 V).
    plot_single(
        80, collect_chip_traces(80, seqs=CHIP80_REMEASURED_SEQS_JULY_ONLY), config,
        OUTPUT_DIR / "alisson80_It_corrected_overlay_remeasured_365-505nm_2026-07-01.pdf",
        field="i_corr_uA",
        ylabel=r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
        plot_start=PLOT_START_TIME,
    )

    # Chip-80 old-vs-new responsivity, 365-505 nm only (longer wavelengths sit
    # at the noise floor, so no real response there regardless of power).
    plot_responsivity_old_vs_new_chip80(
        config,
        OUTPUT_DIR / "alisson80_responsivity_old_vs_new_365-505nm_2026-07-01.pdf",
    )
    plot_responsivity_old_vs_new_chip80(
        config,
        OUTPUT_DIR / "alisson80_responsivity_old_vs_new_365-505nm_2026-07-01.png",
    )
    plot_responsivity_old_vs_new_chip80(
        config,
        OUTPUT_DIR
        / "alisson80_responsivity_old_vs_new_365-505nm_semilogy_2026-07-01.pdf",
        logy=True,
    )

    # Subset comparison: encaps 74, 75, 81, 67.
    subset_chips = [74, 75, 81, 67]
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson74_75_81_67_responsivity_vs_wl.pdf",
        chips=subset_chips,
    )
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson74_75_81_67_responsivity_vs_wl.png",
        chips=subset_chips,
    )
    # 2:3 (vertical:horizontal) aspect-ratio variant.
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson74_75_81_67_responsivity_vs_wl_2x3.pdf",
        chips=subset_chips,
        box_aspect=2.0 / 3.0,
    )
    plot_responsivity_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson74_75_81_67_responsivity_vs_wl_semilogy.pdf",
        chips=subset_chips,
        logy=True,
    )

    rows = build_comparison_table(traces_by_chip)
    print_markdown_table(rows)
    write_latex_table(
        rows,
        OUTPUT_DIR / "drift_model_comparison_67_72_74_75_80_81.tex",
    )


if __name__ == "__main__":
    main()
