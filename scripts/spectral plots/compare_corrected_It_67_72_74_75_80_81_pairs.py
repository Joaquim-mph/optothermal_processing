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

DEFAULT_FIT_T_START = 0.0
FIT_T_END = 60.0
EVAL_T_PRE = 60.0
PLOT_START_TIME = 50.0
TICK_STEP = 30.0  # ticks at 60, 90, 120, … (multiples of 30)

CHIPS = {
    67: {"label": "67 (hBN)",
         "seqs": [4, 15, 27, 41, 103, 102, 100, 98, 96, 94]},
    72: {"label": "72 (hBN)",
         "seqs": [103, 105, 107, 112, 114, 116, 118, 120, 122, 124]},
    74: {"label": "74 (biotite)",
         "seqs": [5, 7, 9, 11, 13, 17, 20, 22, 24, 28],
         "fit_t_start": 30.0},
    75: {"label": "75 (biotite)",
         "seqs": [62, 64, 69, 71, 73, 75, 77, 81, 83, 85]},
    80: {"label": "80 (biotite)",
         "seqs": [95, 97, 99, 101, 103, 105, 107, 109, 111, 113]},
    81: {"label": "81 (biotite)",
         "seqs": [4, 6, 8, 10, 12, 14, 16, 18, 33, 35]},
}

PAIRS = [(72, 67), (74, 75), (80, 81)]


def load_history(chip_number: int) -> pl.DataFrame:
    path = ENRICHED_DIR / f"Alisson{chip_number}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched history missing for chip {chip_number}: {path}. "
            f"Run: biotite build-all-histories && biotite enrich-history {chip_number}"
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


def collect_chip_traces(chip_number: int) -> list[dict]:
    """Returns list of per-wavelength dicts for one chip."""
    history = load_history(chip_number)
    chip_cfg = CHIPS[chip_number]
    rows = select_its_rows(history, chip_cfg["seqs"])
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


def plot_pair(
    pair: tuple[int, int],
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
    *,
    field: str = "i_corr_uA",
    ylabel: str = r"$I_{\mathrm{corr}}\ (\mu\mathrm{A})$",
    plot_start: float = PLOT_START_TIME,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, axes = plt.subplots(1, 2, figsize=(2 * side, side), sharey=True)

    all_traces = traces_by_chip[pair[0]] + traces_by_chip[pair[1]]
    color_for_wl = _wavelength_color_map(all_traces)

    all_y: list[float] = []
    t_totals: list[float] = []

    for ax, chip_num in zip(axes, pair):
        traces = traces_by_chip[chip_num]
        for tr in traces:
            color = color_for_wl.get(tr["wavelength_nm"], "k")
            ax.plot(
                tr["t"], tr[field],
                color=color, linestyle="-",
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

        vgs = [tr["vg_v"] for tr in traces if tr.get("vg_v") is not None]
        title = CHIPS[chip_num]["label"]
        if vgs:
            vg_repr = float(np.median(vgs))
            title = f"{title}, $V_g = {vg_repr:g}$ V"

        ax.set_xlabel(r"$t\ (\mathrm{s})$")
        ax.set_title(title)
        ax.set_box_aspect(1.0)

    axes[0].set_ylabel(ylabel)

    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            for ax in axes:
                ax.set_xlim(plot_start, T_total)

    from matplotlib.ticker import MultipleLocator
    for ax in axes:
        ax.xaxis.set_major_locator(MultipleLocator(TICK_STEP))

    if all_y:
        y = np.array(all_y, dtype=float)
        y = y[np.isfinite(y)]
        if y.size:
            y_min, y_max = float(y.min()), float(y.max())
            if y_max > y_min:
                pad = config.padding_fraction * (y_max - y_min)
                axes[0].set_ylim(y_min - pad, y_max + pad)

    axes[1].legend(title="Wavelength", loc="best", framealpha=0.9, ncol=2)

    plt.tight_layout()
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
            color=color, linestyle="-",
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

    vgs = [tr["vg_v"] for tr in traces if tr.get("vg_v") is not None]
    title = CHIPS[chip_num]["label"]
    if vgs:
        vg_repr = float(np.median(vgs))
        title = f"{title}, $V_g = {vg_repr:g}$ V"

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(ylabel)
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


CHIP_COLORS = {67: "C0", 72: "C4", 74: "C3", 75: "C1", 80: "C2", 81: "C5"}
CHIP_MARKERS = {67: "o", 72: "s", 74: "o", 75: "s", 80: "o", 81: "s"}
EVAL_T_POST = 120.0


def photoresponse_at_post(tr: dict) -> float:
    """ΔI corrected = I_corr(EVAL_T_POST) − I_corr(EVAL_T_PRE).
    Since i_corr is anchored at I_corr(EVAL_T_PRE)=0, this is i_corr at t=120 s."""
    t = tr["t"]
    y = tr["i_corr_uA"]
    if t.size == 0 or not np.any(np.isfinite(y)):
        return float("nan")
    idx = int(np.argmin(np.abs(t - EVAL_T_POST)))
    return float(y[idx])


def plot_photoresponse_vs_wl(
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
) -> None:
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side, side))

    for chip_num, traces in traces_by_chip.items():
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
        ax.plot(
            wls, dis,
            color=CHIP_COLORS.get(chip_num, "k"),
            marker=CHIP_MARKERS.get(chip_num, "o"),
            linestyle="-",
            label=CHIPS[chip_num]["label"],
        )

    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(
        r"$|\Delta I_{\mathrm{corr}}|\ (\mu\mathrm{A})$"
    )
    ax.set_box_aspect(1.0)
    ax.legend(loc="best", framealpha=0.9, ncol=2, fontsize="small")

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

    plot_photoresponse_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson67_72_74_75_80_81_photoresponse_vs_wl.pdf",
    )

    rows = build_comparison_table(traces_by_chip)
    print_markdown_table(rows)
    write_latex_table(
        rows,
        OUTPUT_DIR / "drift_model_comparison_67_72_74_75_80_81.tex",
    )


if __name__ == "__main__":
    main()
