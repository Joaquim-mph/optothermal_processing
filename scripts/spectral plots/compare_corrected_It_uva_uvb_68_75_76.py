"""
Drift-corrected It wavelength sweeps for the UVA/UVB session, chips 68/75/76/80.

Wavelengths: 280, 300, 365, 385, 405, 455 nm at fixed Vg
  (68/75: -0.65 V, 76: -0.5 V, 80: -0.75 V).
  Chip 68  — 2026-05-18 — complete (6 wavelengths)
  Chip 75  — 2026-05-20 — complete (6 wavelengths)
  Chip 76  — 2026-05-20 — died mid-run: 365/385/405/455 complete, 300 nm
             truncated at ~86 s (died during illumination), 280 nm never taken.
  Chip 80  — 2026-05-25 — complete (6 wavelengths); 455 nm was run twice,
             only the latest run is used (see select_its_rows dedup).

Light protocol: ON 60 -> 120 s, 180 s total trace (same as the older sweeps).

Drift model: stretched-exponential fit on the pre-illumination window
t in [fit_t_start, 60] s, subtracted from the full trace; baseline anchored so
I_corr(60 s) = 0; corrected photoresponse |ΔI| = |I_corr(120 s)|.

Per-chip fit window (fit_t_start):
  68, 75, 80 -> [1, 60] s  (matches the 2026-05-14 power-sweep script; all fit
            cleanly over the full pre-illumination window, residual ~0.1-0.5 µA).
  76     -> [40, 60] s. A single stretched-exponential cannot capture chip 76's
            pre-illumination shape over [1, 60] (leaves a ~1-2 µA baseline hump
            comparable to its own signal). A window scan showed [40, 60] s is the
            best balance: in-window residual minimized (~0.1-0.3 µA) while ΔI is
            still on its stable plateau — starts >=45 s begin eating the small
            (405/455 nm) signals.

Responsivity R = |ΔI| / P_device, with P_device = P_beam · (A_flake / A_beam)
and A_beam = 1.0 mm² (1e6 µm²), except 280 nm which is a double beam and so
covers 2.0 mm² -- this session used different optics from the 2026-05-14/15 power
sweeps and the 67/72/74/75/80/81 spectral runs, whose 1e5/1.2e5 µm² spot
constants do NOT apply here. P_beam comes from the enriched history
(`irradiated_power_w`), falling back to `CalibrationMatcher` -- the same path
`biotite enrich-history` uses. The sweep is constant-irradiance at ~18.3 W/m²
(1.83 mW/cm²) for every wavelength: 280 nm is calibrated at ~36.6 µW but spread
over the doubled spot, the rest at ~18.3 µW over 1.0 mm², with the per-wavelength
laser voltage set to match.

Outputs (figs/uva-uvb/):
  - uva_uvb_68_75_responsivity_vs_wl_4x3.pdf       (68 + 75 only, 4:3 aspect)
  - uva_uvb_68_75_80_corrected_deltaI_vs_wl.png    (without 76)
  - uva_uvb_68_75_76_80_corrected_deltaI_vs_wl.png (with 76; its truncated
                                                    300 nm point auto-omitted)
  - alisson{68,75,76,80}_It_corrected_overlay.png  (corrected I(t) per wavelength;
                                                    76 keeps its truncated 300 nm)

Run from repo root:
    python "scripts/spectral plots/compare_corrected_It_uva_uvb_68_75_76.py"
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml

from src.core.utils import read_measurement_parquet
from src.derived.extractors.calibration_matcher import CalibrationMatcher
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import PRISM_RAIN_PALETTE, set_plot_style

HISTORY_DIR = Path("data/02_stage/chip_histories")
ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")
MANIFEST_PATH = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
OUTPUT_DIR = Path("figs/uva-uvb")
ENCAP_YAML = Path("config/encap_characteristics.yaml")

# Responsivity: R = |ΔI_corr| / P_device, P_device = P_beam · (A_device / A_beam).
# This session used a different optical path from the 2026-05-14/15 power sweeps
# and the 67/72/74/75/80/81 spectral runs: the spot here is 1.0 mm² = 1e6 µm²,
# not the 1e5/1.2e5 µm² spots those scripts assume. Do not copy their constant.
BEAM_AREA_UM2_DEFAULT = 1e6  # 1.0 mm²

# The 280 nm path is a double beam: the calibrated power is spread over twice the
# spot, so its effective area is 2.0 mm². Without this the 280 nm point would be
# charged double the power density it actually delivers, halving its R. With it,
# every wavelength in the session sits at the same ~18.3 W/m² irradiance.
BEAM_AREA_UM2_BY_WL = {280.0: 2e6}


def beam_area_um2(wavelength_nm: float) -> float:
    return BEAM_AREA_UM2_BY_WL.get(float(wavelength_nm), BEAM_AREA_UM2_DEFAULT)

# vs-wavelength curve weights, matching the responsivity figures produced by
# `compare_corrected_It_67_72_74_75_80_81_pairs.py` (theme defaults are lw 4.0 /
# markersize 22).
LINE_WIDTH = 5.5
MARKER_SIZE = 30.0
LEGEND_FONTSIZE_BUMP = 2.0


def _legend_fontsize(relative: str = "small") -> float:
    """Legend size 2 pt above the "small" relative size of the active theme."""
    from matplotlib.font_manager import font_scalings

    return plt.rcParams["font.size"] * font_scalings[relative] + LEGEND_FONTSIZE_BUMP


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


def _label(chip_number: int) -> str:
    mat = _CHIP_MATERIALS.get(chip_number)
    return f"{chip_number} ({mat})" if mat else f"Chip {chip_number}"

DEFAULT_FIT_T_START = 1.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0
PLOT_START_TIME = 50.0
TICK_STEP = 30.0  # ticks at 60, 90, 120, … (multiples of 30)

CHIPS = {
    68: {"label": _label(68), "date": "2026-05-18"},
    75: {"label": _label(75), "date": "2026-05-20"},
    76: {"label": _label(76), "date": "2026-05-20", "fit_t_start": 40.0},
    80: {"label": _label(80), "date": "2026-05-25"},
}

CHIP_COLORS = {68: "C0", 75: "C1", 76: "C3", 80: "C2"}
CHIP_MARKERS = {68: "o", 75: "s", 76: "D", 80: "^"}


def load_history(chip_number: int) -> pl.DataFrame:
    path = HISTORY_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"History missing for chip {chip_number}: {path}. "
            f"Run: biotite full-pipeline"
        )
    return pl.read_parquet(path)


def select_its_rows(history: pl.DataFrame, date: str) -> pl.DataFrame:
    rows = (
        history
        .filter(pl.col("proc") == "It")
        .filter(pl.col("has_light") == True)  # noqa: E712
        .filter(pl.col("date").cast(pl.Utf8) == date)
    )
    if rows.height == 0:
        raise ValueError(f"no It+light rows matched date={date}")
    # Dedup repeated wavelengths (e.g. chip 80's 455 nm run twice): keep latest seq.
    return (
        rows.sort("seq")
        .unique(subset=["wavelength_nm"], keep="last", maintain_order=True)
        .sort("wavelength_nm")
    )


def _window_mask(t: np.ndarray, fit_t_start: float) -> np.ndarray:
    mask = (t >= fit_t_start) & (t <= FIT_T_END)
    if mask.size:
        mask[0] = False
    return mask


def fit_stretched(t: np.ndarray, i: np.ndarray, fit_t_start: float) -> dict:
    """Fit stretched-exp drift on [fit_t_start, 60] s; return the full-trace
    drift array plus the cleaned trace."""
    finite = np.isfinite(t) & np.isfinite(i)
    t = t[finite]
    i = i[finite]
    mask = _window_mask(t, fit_t_start)

    out: dict = {
        "stretched_drift_full": np.full_like(i, np.nan),
        "t_full": t,
        "i_full": i,
    }
    if mask.sum() < 10:
        return out

    try:
        se = fit_stretched_exponential(t[mask], i[mask])
        out["stretched_drift_full"] = stretched_exponential(
            t, se["baseline"], se["amplitude"], se["tau"], se["beta"]
        )
    except Exception as exc:
        print(f"  stretched-exp fit failed: {exc}")
    return out


def corrected_trace(fit_result: dict) -> np.ndarray:
    """Subtract stretched-exp drift across the full trace; anchor I_corr(60 s)=0."""
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


def collect_chip_traces(chip_number: int) -> list[dict]:
    history = load_history(chip_number)
    chip_cfg = CHIPS[chip_number]
    rows = select_its_rows(history, chip_cfg["date"])
    fit_t_start = float(chip_cfg.get("fit_t_start", DEFAULT_FIT_T_START))
    powers = power_by_wavelength(chip_number, chip_cfg["date"])

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

        fit = fit_stretched(t, i, fit_t_start)
        i_corr = corrected_trace(fit)

        wl_f = float(wl) if wl is not None else float("nan")
        traces.append({
            "chip": chip_number,
            "wavelength_nm": wl_f,
            "vg_v": (float(row.get("vg_fixed_v"))
                     if row.get("vg_fixed_v") is not None else None),
            "t": fit["t_full"],
            "i_corr_uA": i_corr * 1e6,
            "light_span": light_window(meas, fit["t_full"]),
            # Responsivity inputs (unused by the |ΔI| figures).
            "power_w": powers.get(wl_f),
            "start_time_utc": row.get("start_time_utc"),
            "laser_voltage_v": row.get("laser_voltage_v"),
        })

    filled = backfill_power(traces)
    if filled:
        print(f"  [chip {chip_number}] backfilled power for {filled}/{len(traces)} traces")
    return traces


def _wavelength_color_map(traces: list[dict]) -> dict[float, str]:
    """Sort wavelengths ascending, assign PRISM_RAIN_PALETTE in order (cycling)."""
    wls = sorted({tr["wavelength_nm"] for tr in traces if np.isfinite(tr["wavelength_nm"])})
    n = len(PRISM_RAIN_PALETTE)
    return {wl: PRISM_RAIN_PALETTE[idx % n] for idx, wl in enumerate(wls)}


def plot_single(
    chip_num: int,
    traces: list[dict],
    config: PlotConfig,
    output_path: Path,
    *,
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
            tr["t"], tr["i_corr_uA"],
            color=color, linestyle="-",
            label=f"{tr['wavelength_nm']:.0f} nm",
        )
        visible = tr["t"] >= plot_start
        all_y.extend(tr["i_corr_uA"][visible])
        t_totals.append(float(tr["t"][-1]))

    spans = [tr["light_span"] for tr in traces if tr.get("light_span")]
    if spans:
        s = float(np.median([sp[0] for sp in spans]))
        e = float(np.median([sp[1] for sp in spans]))
        ax.axvspan(s, e, alpha=config.light_window_alpha)

    vgs = [tr["vg_v"] for tr in traces if tr.get("vg_v") is not None]
    title = CHIPS[chip_num]["label"]
    if vgs:
        vg_repr = float(np.median(vgs))
        title = f"{title}, $V_g = {vg_repr:g}$ V"

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    ax.set_title(title)
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
              fontsize="small", title_fontsize="small")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def device_areas_um2() -> dict[int, float]:
    """Per-chip flake area (µm²) from config/encap_characteristics.yaml."""
    if not ENCAP_YAML.exists():
        return {}
    data = yaml.safe_load(ENCAP_YAML.read_text()) or {}
    return {
        int(k): float(v["flake_area_um2"])
        for k, v in data.items()
        if isinstance(k, int) and isinstance(v, dict) and "flake_area_um2" in v
    }


def power_by_wavelength(chip_number: int, date: str) -> dict[float, float]:
    """Beam power (W) per wavelength, read from the enriched history.

    Returns {} when the enriched history (or its `irradiated_power_w` column) is
    missing; `backfill_power` then resolves the power from the calibration files.
    """
    path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        return {}
    df = pl.read_parquet(path)
    if "irradiated_power_w" not in df.columns:
        return {}
    rows = select_its_rows(df, date)
    return {
        float(r["wavelength_nm"]): float(r["irradiated_power_w"])
        for r in rows.iter_rows(named=True)
        if r.get("wavelength_nm") is not None
        and r.get("irradiated_power_w") is not None
    }


def backfill_power(traces: list[dict], stale_threshold_hours: float = 24.0) -> int:
    """Fill `power_w` for traces the enriched history did not cover, using the
    same CalibrationMatcher path as `biotite enrich-history`. Returns the count."""
    missing = [tr for tr in traces if tr.get("power_w") is None]
    if not missing:
        return 0
    if not MANIFEST_PATH.exists():
        print(f"  [warn] manifest missing ({MANIFEST_PATH}); cannot backfill power")
        return 0

    matcher = CalibrationMatcher(MANIFEST_PATH)
    filled = 0
    for tr in missing:
        start = tr.get("start_time_utc")
        wl = tr.get("wavelength_nm")
        vl = tr.get("laser_voltage_v")
        if start is None or vl is None or wl is None or not np.isfinite(wl):
            continue
        match = matcher.find_calibration(start, float(wl), stale_threshold_hours)
        if match.calibration_path is None:
            print(f"  [chip {tr['chip']}] {wl:.0f} nm: {match.warning}")
            continue
        power = matcher.get_power_from_calibration(match.calibration_path, float(vl))
        if power is None or not np.isfinite(power) or power <= 0:
            continue
        tr["power_w"] = float(power)
        filled += 1
    return filled


def responsivity_at_post(tr: dict, area_um2: float | None) -> float:
    """R = |ΔI_corr(120 s)| / P_device (A/W); P_device = P_beam · A_device/A_beam.

    ΔI is the same quantity the |ΔI| vs wavelength figures plot, so the two
    describe identical traces.
    """
    di_uA = photoresponse_at_post(tr)
    p_w = tr.get("power_w")
    if area_um2 is None or p_w is None or not np.isfinite(p_w) or p_w <= 0:
        return float("nan")
    if not np.isfinite(di_uA):
        return float("nan")
    p_dev_w = p_w * (area_um2 / beam_area_um2(tr["wavelength_nm"]))
    return (di_uA * 1e-6) / p_dev_w


def photoresponse_at_post(tr: dict) -> float:
    """|ΔI corrected| = |I_corr(120 s)| (anchored at I_corr(60 s)=0).
    Returns NaN if the trace died before reaching EVAL_T_POST."""
    t = tr["t"]
    y = tr["i_corr_uA"]
    if t.size == 0 or not np.any(np.isfinite(y)):
        return float("nan")
    if float(t[-1]) < EVAL_T_POST - 1.0:  # truncated trace (e.g. 76 @ 300 nm)
        return float("nan")
    idx = int(np.argmin(np.abs(t - EVAL_T_POST)))
    return abs(float(y[idx]))


def plot_responsivity_vs_wl(
    chip_nums: list[int],
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
    *,
    box_aspect: float = 0.75,
) -> None:
    """R vs wavelength. `box_aspect` is height/width (0.75 -> 4:3 landscape)."""
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / box_aspect, side))

    areas = device_areas_um2()
    for chip_num in chip_nums:
        area = areas.get(chip_num)
        pts = []
        for tr in traces_by_chip[chip_num]:
            wl = tr["wavelength_nm"]
            r = responsivity_at_post(tr, area)
            if np.isfinite(wl) and np.isfinite(r):
                pts.append((wl, r))
        if not pts:
            print(f"  [chip {chip_num}] no responsivity points (area={area})")
            continue
        pts.sort()
        ax.plot(
            [p[0] for p in pts], [p[1] for p in pts],
            color=CHIP_COLORS.get(chip_num, "k"),
            marker=CHIP_MARKERS.get(chip_num, "o"),
            markersize=MARKER_SIZE,
            linestyle="-",
            linewidth=LINE_WIDTH,
            label=CHIPS[chip_num]["label"],
        )

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
    chip_nums: list[int],
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side, side))

    for chip_num in chip_nums:
        pts = []
        for tr in traces_by_chip[chip_num]:
            wl = tr["wavelength_nm"]
            di = photoresponse_at_post(tr)
            if np.isfinite(wl) and np.isfinite(di):
                pts.append((wl, di))
        if not pts:
            continue
        pts.sort()
        wls = np.array([p[0] for p in pts])
        dis = np.array([p[1] for p in pts])
        ax.plot(
            wls, dis,
            color=CHIP_COLORS.get(chip_num, "k"),
            marker=CHIP_MARKERS.get(chip_num, "o"),
            linestyle="-",
            label=CHIPS[chip_num]["label"],
        )

    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(r"$|\Delta I_{\mathrm{corr}}|\ (\mu\mathrm{A})$")
    ax.set_box_aspect(1.0)
    ax.legend(loc="best", framealpha=0.9)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    traces_by_chip: dict[int, list[dict]] = {}
    for chip_num in CHIPS:
        print(f"[chip {chip_num}] collecting traces…")
        traces_by_chip[chip_num] = collect_chip_traces(chip_num)

    plot_responsivity_vs_wl(
        [68, 75], traces_by_chip, config,
        OUTPUT_DIR / "uva_uvb_68_75_responsivity_vs_wl_4x3.pdf",
    )
    plot_photoresponse_vs_wl(
        [68, 75, 80], traces_by_chip, config,
        OUTPUT_DIR / "uva_uvb_68_75_80_corrected_deltaI_vs_wl.png",
    )
    plot_photoresponse_vs_wl(
        [68, 75, 76, 80], traces_by_chip, config,
        OUTPUT_DIR / "uva_uvb_68_75_76_80_corrected_deltaI_vs_wl.png",
    )

    for chip_num, traces in traces_by_chip.items():
        plot_single(
            chip_num, traces, config,
            OUTPUT_DIR / f"alisson{chip_num}_It_corrected_overlay.png",
        )


if __name__ == "__main__":
    main()
