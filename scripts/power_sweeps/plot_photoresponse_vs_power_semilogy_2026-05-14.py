"""
Photoresponse (|Δi_corrected|) vs laser power on semilog-y axes for the
2026-05-14 365 nm "power law" It sweeps, across five chips.

Chips / fixed gate voltage (all 365 nm, powers 6, 12, 18, 24 µW):
    68  Vg = -0.7  V
    74  Vg = -0.5  V
    75  Vg = -0.5  V
    76  Vg = -0.7  V
    72  Vg = -0.35 V

Correction: stretched-exponential fit on t ∈ [1, 60] s subtracted from the
trace. The photoresponse Δi_corrected is the peak drift-corrected deviation
over the illuminated window t ∈ [60, 120] s relative to the 60 s onset, i.e.
max |I_corr(t) - I_corr(60 s)| (the "true" response, not the 120 s endpoint;
see CorrectedDeltaIExtractor delta_mode="max_deviation"). Absolute value taken
so the response sits on a log y-axis. A linear fit in log P vs log |Δi| gives
the power-law exponent γ with |Δi| ∝ P^γ; the fit curve is drawn on semilog-y
axes.

NOTE: the 6-24 µW range is suspected to be in the channel-current saturation
regime — the 2026-05-15 re-measurement at 1-6 µW was motivated by that. γ
values from this date may not reflect the linear-response exponent.

Per chip: one sequential-It figure (raw traces + drift-corrected inset), one
full-size drift-corrected overlay, one photoresponse-vs-power figure, and its
responsivity twin (same data and same power-law fit, R = |Δi| / P_incident,
without the γ annotation). Plus
two comparison figures overlaying all chips with γ annotations: |Δi| vs power,
and responsivity R = |Δi| / P_incident vs power (A/W), where the incident power
is the flake-area fraction of the beam, P_incident = P_LED · A_flake / A_beam
with A_beam = 1.2e5 µm² and A_flake from the encap YAML.

Run from repo root:
    python scripts/power_sweeps/plot_photoresponse_vs_power_semilogy_2026-05-14.py
"""

from __future__ import annotations

import argparse
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
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
WAVELENGTH_NM = 365.0
DATE = "2026-05-14"
OUTPUT_DIR = Path("figs/photoresponse_power_law_365nm")
ENCAP_YAML = Path("config/encap_characteristics.yaml")

# Responsivity: R = |Δi| / P_incident, where P_incident is the fraction of the
# LED beam that actually lands on the device flake, P_incident = P_LED ·
# A_flake / A_beam. Flake areas come from `flake_area_um2` in the encap YAML.
BEAM_AREA_UM2 = 1.2e5
_BEAM_AREA_M2 = BEAM_AREA_UM2 * 1e-12  # 1 µm² = 1e-12 m²


def irradiance_W_per_m2(p_uW: np.ndarray) -> np.ndarray:
    """LED power (µW) -> beam irradiance (W/m²) over the full beam spot."""
    return (np.asarray(p_uW, dtype=float) * 1e-6) / _BEAM_AREA_M2


# Beam area in cm² (1 µm² = 1e-8 cm²).
_BEAM_AREA_CM2 = BEAM_AREA_UM2 * 1e-8


def irradiance_mW_per_cm2(p_uW: np.ndarray) -> np.ndarray:
    """LED power (µW) -> beam irradiance (mW/cm²) over the full beam spot."""
    return (np.asarray(p_uW, dtype=float) * 1e-3) / _BEAM_AREA_CM2


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


def _load_chip_flake_areas() -> dict[int, float]:
    """Flake area (µm²) per chip from the encap YAML's `flake_area_um2` field."""
    if not ENCAP_YAML.exists():
        return {}
    with ENCAP_YAML.open("r") as f:
        data = yaml.safe_load(f) or {}
    out: dict[int, float] = {}
    for k, v in data.items():
        if isinstance(k, int) and isinstance(v, dict) and v.get("flake_area_um2"):
            out[k] = float(v["flake_area_um2"])
    return out


_CHIP_MATERIALS = _load_chip_materials()
_CHIP_FLAKE_AREAS = _load_chip_flake_areas()

# Abbreviations for the bottom dielectric in the stack tag. The top encapsulant
# is always hBN (see config/encap_characteristics.yaml), so the tag is
# "hBN/<bottom>", e.g. "hBN/Bio" for a biotite-bottom chip.
_MATERIAL_ABBREV = {"biotite": "Bio", "hBN": "hBN"}


def material_stack_for_chip(chip_number: int) -> str | None:
    """Top/bottom dielectric stack tag, e.g. "hBN/Bio". None if unknown."""
    mat = _CHIP_MATERIALS.get(chip_number)
    if not mat:
        return None
    bottom = _MATERIAL_ABBREV.get(mat, mat)
    return f"hBN/{bottom}"


def label_for_chip(
    chip: dict,
    include_material: bool = True,
    stack: bool = False,
    include_vg: bool = True,
) -> str:
    n = chip["chip"]
    vg = chip.get("vg_filter") if include_vg else None
    if stack:
        if include_material:
            mat = _CHIP_MATERIALS.get(n)
            bottom = _MATERIAL_ABBREV.get(mat, mat) if mat else None
        else:
            bottom = None
        mat_part = f" {bottom}" if bottom else ""
        vg_part = f", $V_g={vg:g}$ V" if vg is not None else ""
        return f"{n}{mat_part}{vg_part}"
    mat = _CHIP_MATERIALS.get(n) if include_material else None
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
#                          pulse to relax from).
CHIPS: list[dict] = [
    {
        "chip": 68,
        "vg_filter": -0.7,
        "color": "#377eb8",
        "marker": "o",
        "gamma_anchor": "left",
        "gamma_xy_offset": (0, 0),
        "gamma_axes_xy": (0.4, 0.22),
    },
    {
        "chip": 74,
        "vg_filter": -0.5,
        "color": "#e41a1c",
        "marker": "s",
        "gamma_anchor": "left",
        "gamma_xy_offset": (0, 0),
        "gamma_axes_xy": (0.75, 0.55),
    },
    {
        "chip": 75,
        "vg_filter": -0.5,
        "color": "#4daf4a",
        "marker": "^",
        "gamma_anchor": "left",
        "gamma_xy_offset": (0, 0),
        "gamma_axes_xy": (0.25, 0.93),
    },
    {
        "chip": 76,
        "vg_filter": -0.7,
        "color": "#984ea3",
        "marker": "D",
        "gamma_anchor": "left",
        "gamma_xy_offset": (0, 0),
        "gamma_axes_xy": (0.8, 0.8),
    },
    {
        "chip": 72,
        "vg_filter": -0.35,
        "color": "#a65628",
        "marker": "P",
        "gamma_anchor": "left",
        "gamma_xy_offset": (0, 0),
        "gamma_axes_xy": (0.75, 0.1),
    },
    {
        "chip": 80,
        "vg_filter": -1.2,
        "color": "#ff7f00",
        "marker": "v",
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


def responsivity_curve_for_chip(
    hist: pl.DataFrame, chip: dict
) -> tuple[np.ndarray, np.ndarray]:
    """LED power (µW) and responsivity R = |Δi| / P_incident (A/W).

    |Δi| is the peak drift-corrected deviation over the illuminated window
    (delta_mode="max_deviation"; see module docstring). P_incident = P_LED ·
    A_flake / A_beam. Returns empty arrays if the chip's flake area is unknown.
    Since |Δi| and P_LED carry the same µ-prefix, the ratio |Δi[µA]| / P_LED[µW]
    is already in A/W; dividing by the beam-fill fraction A_flake/A_beam gives
    the on-flake responsivity.
    """
    flake_area = _CHIP_FLAKE_AREAS.get(chip["chip"])
    if flake_area is None:
        return np.array([]), np.array([])
    p, di = curve_for_chip(hist, chip)
    mask = p > 0
    p, di = p[mask], di[mask]
    fill_fraction = flake_area / BEAM_AREA_UM2
    responsivity = (di / p) / fill_fraction
    return p, responsivity


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


def plot_responsivity_vs_power(
    config: PlotConfig,
    hist: pl.DataFrame,
    chip: dict,
    x_mode: str = "irradiance",
) -> None:
    """Per-chip responsivity vs power, semilog-y.

    Responsivity twin of plot_photoresponse_vs_power: same points and same
    power-law fit, divided by P_incident (see responsivity_curve_for_chip).
    The fit line is kept; γ is not annotated (dividing by P only shifts the
    exponent by a constant -1, so the photocurrent figure already reports it).

    x_mode selects the x axis: "irradiance" (default) plots beam irradiance in
    mW/cm², "led_power" plots raw LED power in µW. Only the x scaling and the
    filename differ -- same y data, same fit.
    """
    if x_mode not in ("irradiance", "led_power"):
        raise ValueError(f"x_mode must be 'irradiance' or 'led_power', got {x_mode!r}")
    to_x = irradiance_mW_per_cm2 if x_mode == "irradiance" else np.asarray
    flake_area = _CHIP_FLAKE_AREAS.get(chip["chip"])
    if flake_area is None:
        print(f"[warn] no flake area for {label_for_chip(chip)}; skipping R")
        return

    p, r = responsivity_curve_for_chip(hist, chip)
    if p.size == 0:
        print(f"[warn] no responsivity data for {label_for_chip(chip)}")
        return

    set_plot_style(config.theme)
    fig, ax = plt.subplots(figsize=(20, 20))

    fill_fraction = flake_area / BEAM_AREA_UM2

    ax.plot(
        to_x(p),
        r,
        marker=chip["marker"],
        linestyle="none",
        color=chip["color"],
        markersize=12,
        label=label_for_chip(chip),
    )

    # Convert the |Δi| power-law fit into responsivity so the drawn curve is
    # the same fit as on the photocurrent figure.
    p_all, di_all = curve_for_chip(hist, chip)
    _gamma, p_fit, di_fit = power_law_fit(p_all, di_all)
    if p_fit.size:
        r_fit = (di_fit / p_fit) / fill_fraction
        ax.plot(
            to_x(p_fit),
            r_fit,
            linestyle="-",
            color=chip["color"],
            linewidth=1.2,
        )

    ax.set_yscale("log")
    # R spans well under a decade for some chips, so label the 1-2-5 log steps.
    ax.yaxis.set_major_locator(mpl.ticker.LogLocator(base=10.0, subs=(1.0, 2.0, 5.0)))
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, pos: f"{v:g}"))

    _xt = to_x([6, 12, 18, 24])
    ax.set_xticks(_xt)
    ax.set_xticklabels([f"{v:g}" for v in _xt])

    if x_mode == "irradiance":
        ax.set_xlabel(r"Irradiance (mW/cm$^2$)")
    else:
        ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$R$ (A/W)")
    ax.legend()
    plt.tight_layout()

    print(
        f"{label_for_chip(chip)}  A_flake={flake_area:g} µm²  "
        f"R=[{r.min():.3g},{r.max():.3g}] A/W"
    )

    x_tag = "power" if x_mode == "irradiance" else "led_power"
    filename = (
        f"Alisson{chip['chip']}_responsivity_vs_{x_tag}_semilogy_{DATE}_365nm."
        f"{config.format}"
    )
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
            label=f"{label_for_chip(chip, stack=True)}, $\\gamma={gamma:.2f}$",
        )
        if p_fit.size:
            ax.plot(p_fit, di_fit, linestyle="-", color=chip["color"], linewidth=1.2)

    ax.set_yscale("log")
    ax.set_xlabel(r"LED power ($\mu$W)")
    ax.set_ylabel(r"$|\Delta i_{\mathrm{corr}}|$ ($\mu$A)")
    ax.set_xticks([6, 12, 18, 24])
    ax.set_xticklabels(["6", "12", "18", "24"])
    ax.set_yticks([5, 10, 20, 40])
    ax.set_yticklabels(["5", "10", "20", "40"])
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{filename}.{config.format}"
    plt.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")


def plot_responsivity_comparison(
    config: PlotConfig,
    histories: dict[int, pl.DataFrame],
    chips: list[dict],
    filename: str,
    fmt: str | None = None,
) -> None:
    """Multi-chip responsivity (A/W) vs beam irradiance on semilog-y axes.

    Mirrors plot_comparison but plots R = |Δi| / P_incident, with P_incident the
    flake-area fraction of the beam (A_flake / A_beam, beam = 1.2e5 µm²). Chips
    without a known flake area are skipped with a warning.
    """
    set_plot_style(config.theme)
    fig, ax = plt.subplots(figsize=(21, 15))

    # (material, handle) per plotted chip, for the hBN-first legend below.
    entries: list[tuple[str | None, mpl.lines.Line2D]] = []

    for chip in chips:
        flake_area = _CHIP_FLAKE_AREAS.get(chip["chip"])
        if flake_area is None:
            print(f"[warn] no flake area for {label_for_chip(chip)}; skipping R")
            continue
        p, di = curve_for_chip(histories[chip["chip"]], chip)
        mask = p > 0
        p, di = p[mask], di[mask]
        if p.size == 0:
            print(f"[warn] no responsivity data for {label_for_chip(chip)}")
            continue
        fill_fraction = flake_area / BEAM_AREA_UM2
        r = (di / p) / fill_fraction

        # The power law is fitted on the photoresponse itself,
        # |Δi_corr| ∝ P^gamma, exactly as on the sibling photoresponse figures;
        # the fitted curve is then divided by P (and the beam-fill fraction) to
        # be drawn in responsivity units.
        gamma, p_fit, di_fit = power_law_fit(p, di)
        if abs(gamma) < 5e-3:  # avoid printing "-0.00"
            gamma = 0.0
        r_fit = (di_fit / p_fit) / fill_fraction if p_fit.size else di_fit

        (handle,) = ax.plot(
            irradiance_mW_per_cm2(p),
            r,
            marker=chip["marker"],
            linestyle="none",
            color=chip["color"],
            markersize=25,
            label=f"{label_for_chip(chip, include_vg=False)}, $\\gamma={gamma:.2f}$",
        )
        entries.append((_CHIP_MATERIALS.get(chip["chip"]), handle))
        if p_fit.size:
            # Same line weight as the connecting lines this figure used before
            # the fit replaced them (theme default).
            ax.plot(
                irradiance_mW_per_cm2(p_fit),
                r_fit,
                linestyle="-",
                color=chip["color"],
            )

        print(
            f"{label_for_chip(chip)}  A_flake={flake_area:g} µm²  "
            f"R=[{r.min():.3g},{r.max():.3g}] A/W  gamma={gamma:.3f}"
        )

    ax.set_yscale("log")
    # Breathing room under the lowest curve: extend the (log) y-range 10% down.
    _lo, _hi = ax.get_ylim()
    ax.set_ylim(10 ** (np.log10(_lo) - 0.10 * (np.log10(_hi) - np.log10(_lo))), _hi)
    ax.set_xlabel(r"Irradiance (mW/cm$^2$)")
    ax.set_ylabel(r"$R\ (\mathrm{A/W})$")
    _phi = irradiance_mW_per_cm2([6, 12, 18, 24])
    ax.set_xticks(_phi)
    ax.set_xticklabels([f"{v:g}" for v in _phi])
    ax.set_xlim(left=4)

    # hBN references first, then the biotite devices, each in CHIPS order.
    handles = [h for mat, h in entries if mat == "hBN"]
    handles += [h for mat, h in entries if mat != "hBN"]
    ax.legend(handles=handles, loc="best", framealpha=0.9)

    plt.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{filename}.{fmt or config.format}"
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
            plot_responsivity_vs_power(config, hist, chip)
            plot_responsivity_vs_power(config, hist, chip, x_mode="led_power")

    plot_comparison(
        config,
        histories,
        CHIPS,
        filename=f"Alisson68_72_74_75_76_photoresponse_vs_power_semilogy_{DATE}_365nm",
        anchor_chip=68,
    )

    responsivity_filename = (
        f"Alisson68_72_74_75_76_responsivity_vs_power_semilogy_{DATE}_365nm"
    )
    plot_responsivity_comparison(config, histories, CHIPS, filename=responsivity_filename)
    plot_responsivity_comparison(
        config, histories, CHIPS, filename=responsivity_filename, fmt="png"
    )


if __name__ == "__main__":
    main()
