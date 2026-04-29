"""
Comparison plots for encap chips 80 and 81:
  * First IVg sweep overlay (one figure).
  * Drift-corrected It overlay (one figure per chip).
  * Corrected Δi vs wavelength (one figure per chip).
  * Combined corrected Δi vs wavelength comparison (linear and semilogy).

Drift model: stretched exponential fit on t ∈ [fit_t_start, 60] s, subtracted
from the full trace. Δi_corrected = I_corr(120 s) − I_corr(60 s) — same
definition as the `delta_i_corrected` derived metric.

Run from repo root:
    python scripts/compare_80_81_ivg_and_corrected_photoresponse.py

Prereq: `biotite full-pipeline && biotite derive-all-metrics &&
biotite enrich-history 80 && biotite enrich-history 81`.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)
from src.derived.extractors.corrected_delta_i_extractor import CorrectedDeltaIExtractor
from src.plotting.config import PlotConfig
from src.plotting.plot_utils import ensure_standard_columns
from src.plotting.styles import set_plot_style

ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")
OUTPUT_DIR = Path("figs/compare")

DEFAULT_FIT_T_START = 20.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
EVAL_T_POST = 120.0

CHIPS = [
    {"chip_number": 80, "label": "80 (biotite)", "color": "#2ca02c",
     "seqs": [95, 97, 99, 101, 103, 105, 107, 109, 111, 113]},
    {"chip_number": 81, "label": "81 (biotite)", "color": "#1f77b4",
     "seqs": [4, 6, 8, 10, 12, 14, 16, 18, 33, 35]},
]

_FALLBACK_EXTRACTORS: dict[float, CorrectedDeltaIExtractor] = {}


def _get_extractor(fit_t_start: float) -> CorrectedDeltaIExtractor:
    if fit_t_start not in _FALLBACK_EXTRACTORS:
        _FALLBACK_EXTRACTORS[fit_t_start] = CorrectedDeltaIExtractor(
            fit_t_start=fit_t_start, fit_t_end=FIT_T_END,
            eval_t_pre=EVAL_T_PRE, eval_t_post=EVAL_T_POST,
        )
    return _FALLBACK_EXTRACTORS[fit_t_start]


def load_history(chip_number: int) -> pl.DataFrame:
    path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched history missing for chip {chip_number}: {path}. "
            f"Run: biotite enrich-history {chip_number}"
        )
    return pl.read_parquet(path)


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


def load_first_ivg(chip_number: int, label: str) -> tuple[np.ndarray, np.ndarray]:
    history = load_history(chip_number)
    ivg = history.filter(pl.col("proc") == "IVg").sort("seq")
    if ivg.height == 0:
        raise ValueError(f"[{label}] no IVg measurements found in history.")
    first = ivg.row(0, named=True)
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
        f"[{label}] chip={chip_number} seq={first['seq']} n_points={len(vg)} "
        f"Vg_range=[{vg.min():.2f}, {vg.max():.2f}] V "
        f"I_range=[{i_uA.min():.3g}, {i_uA.max():.3g}] µA"
    )
    return vg, i_uA


def corrected_trace(t: np.ndarray, i: np.ndarray, fit_t_start: float) -> np.ndarray:
    finite = np.isfinite(t) & np.isfinite(i)
    t = t[finite]
    i = i[finite]
    mask = (t >= fit_t_start) & (t <= FIT_T_END)
    if mask.size:
        mask[0] = False
    if mask.sum() < 10:
        return np.full_like(i, np.nan)
    fit = fit_stretched_exponential(t[mask], i[mask])
    drift = stretched_exponential(
        t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
    )
    return i - drift


def plot_it_overlay(
    chip_label: str,
    rows: pl.DataFrame,
    output_path: Path,
    config: PlotConfig,
    fit_t_start: float,
    plot_start_time: float = 20.0,
) -> Path:
    set_plot_style(config.theme)
    plt.figure(figsize=config.figsize_timeseries)

    t_totals: list[float] = []
    starts_vl: list[float] = []
    ends_vl: list[float] = []
    all_y: list[float] = []

    for row in rows.iter_rows(named=True):
        parquet_path = Path(row.get("parquet_path") or "")
        if not parquet_path.exists():
            print(f"  [{chip_label}] missing parquet: {parquet_path}")
            continue
        meas = read_measurement_parquet(parquet_path)
        if "t (s)" not in meas.columns or "I (A)" not in meas.columns:
            continue
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)
        i_corr = corrected_trace(t, i, fit_t_start)

        if np.any(np.isfinite(i_corr)):
            idx_pre = int(np.argmin(np.abs(t - EVAL_T_PRE)))
            baseline = i_corr[idx_pre]
            if np.isfinite(baseline):
                i_corr = i_corr - baseline

        wl = row.get("wavelength_nm")
        label = f"{wl:g} nm" if wl is not None else f"#{int(row.get('seq', 0))}"

        plt.plot(t, i_corr * 1e6, label=label)

        visible = t >= plot_start_time
        all_y.extend((i_corr * 1e6)[visible])
        t_totals.append(float(t[-1]))

        if "VL (V)" in meas.columns:
            vl = meas["VL (V)"].to_numpy()
            on_idx = np.where(vl > 0.1)[0]
            if on_idx.size:
                starts_vl.append(float(t[on_idx[0]]))
                ends_vl.append(float(t[on_idx[-1]]))

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            plt.xlim(plot_start_time, T_total)

    if starts_vl and ends_vl:
        plt.axvspan(float(np.median(starts_vl)), float(np.median(ends_vl)),
                    alpha=config.light_window_alpha)

    plt.xlabel(r"$t\ (\mathrm{s})$")
    plt.ylabel(r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$")
    plt.legend(title="Wavelength")

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                plt.ylim(y_min - pad, y_max + pad)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close()
    print(f"saved {output_path}")
    return output_path


def _fallback_delta(row: dict, fit_t_start: float) -> float | None:
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
    metric = _get_extractor(fit_t_start).extract(meas, meta)
    if metric is None or metric.value_float is None:
        return None
    v = metric.value_float
    return v if np.isfinite(v) else None


def get_corrected_curve(rows: pl.DataFrame, fit_t_start: float) -> tuple[np.ndarray, np.ndarray]:
    sub = rows
    if "delta_i_corrected" in sub.columns and sub["delta_i_corrected"].dtype == pl.Utf8:
        sub = sub.with_columns(pl.col("delta_i_corrected").cast(pl.Float64))

    values: list[float | None] = []
    for row in sub.iter_rows(named=True):
        values.append(_fallback_delta(row, fit_t_start))

    sub = sub.with_columns(pl.Series("delta_i_corrected_resolved", values, dtype=pl.Float64))
    sub = sub.filter(
        pl.col("delta_i_corrected_resolved").is_not_null()
        & pl.col("delta_i_corrected_resolved").is_not_nan()
    )
    if sub.height == 0:
        raise ValueError("could not resolve delta_i_corrected for any row")
    wl = sub["wavelength_nm"].to_numpy()
    di_uA = np.abs(sub["delta_i_corrected_resolved"].to_numpy()) * 1e6
    return wl, di_uA


def plot_per_chip_wl(
    chip_label: str,
    wl: np.ndarray,
    di_uA: np.ndarray,
    output_path: Path,
    config: PlotConfig,
) -> Path:
    fig, ax = plt.subplots(figsize=config.figsize_derived)
    ax.plot(wl, di_uA, "o-", color="C0")
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("|Δi_corrected| (µA)")
    ax.set_title(f"Chip {chip_label} — corrected photoresponse vs wavelength")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")
    return output_path


def plot_wl_comparison(
    curves: list[tuple[str, str, np.ndarray, np.ndarray]],
    axtype: str,
    output_path: Path,
    config: PlotConfig,
) -> Path:
    fig, ax = plt.subplots(figsize=config.figsize_derived)
    for label, color, wl, di_uA in curves:
        ax.plot(wl, di_uA, "o-", label=label, color=color)
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("|Δi_corrected| (µA)")
    if axtype == "semilogy":
        ax.set_yscale("log")
    elif axtype != "linear":
        raise ValueError(f"axtype must be 'linear' or 'semilogy', got {axtype!r}")
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")
    return output_path


def plot_ivg_comparison(
    curves: list[tuple[str, str, np.ndarray, np.ndarray]],
    output_path: Path,
    config: PlotConfig,
) -> Path:
    fig, ax = plt.subplots(figsize=(20, 20))
    for label, color, vg, i_uA in curves:
        ax.plot(vg, i_uA, label=label, color=color)
    ax.set_xlabel("Gate Voltage $V_g$ (V)")
    ax.set_ylabel("Drain Current $I_d$ (µA)")
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")
    return output_path


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    ivg_curves: list[tuple[str, str, np.ndarray, np.ndarray]] = []
    wl_curves: list[tuple[str, str, np.ndarray, np.ndarray]] = []

    for chip in CHIPS:
        history = load_history(chip["chip_number"])
        rows = select_its_rows(history, chip["seqs"])
        fit_t_start = float(chip.get("fit_t_start", DEFAULT_FIT_T_START))

        plot_it_overlay(
            chip["label"],
            rows,
            OUTPUT_DIR / f"alisson{chip['chip_number']}_It_corrected_overlay.png",
            config,
            fit_t_start,
        )

        wl, di_uA = get_corrected_curve(rows, fit_t_start)
        plot_per_chip_wl(
            chip["label"],
            wl,
            di_uA,
            OUTPUT_DIR / f"alisson{chip['chip_number']}_corrected_photoresponse_vs_wavelength.png",
            config,
        )
        wl_curves.append((chip["label"], chip["color"], wl, di_uA))
        print(
            f"[{chip['label']}] n={len(wl)} "
            f"wl=[{wl.min():.0f},{wl.max():.0f}] nm "
            f"|Δi_corr|=[{di_uA.min():.3g},{di_uA.max():.3g}] µA"
        )

        vg, i_uA = load_first_ivg(chip["chip_number"], chip["label"])
        ivg_curves.append((chip["label"], chip["color"], vg, i_uA))

    plot_ivg_comparison(
        ivg_curves,
        OUTPUT_DIR / "alisson80_81_IVg_first.png",
        config,
    )

    base = OUTPUT_DIR / "alisson80_81_corrected_photoresponse_vs_wavelength"
    plot_wl_comparison(wl_curves, "linear", base.with_suffix(".png"), config)
    plot_wl_comparison(
        wl_curves,
        "semilogy",
        base.with_name(base.name + "_semilogy").with_suffix(".png"),
        config,
    )


if __name__ == "__main__":
    main()
