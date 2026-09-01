"""
10-90% rise and fall time vs wavelength for chips 67/72/74/75/80/81.

Response-time companion to the responsivity-vs-wavelength figure produced by
`scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py`. Chip
selection, seq lists, colors, markers and layout are imported from that script,
so these figures describe exactly the same It measurements as

    alisson67_72_74_75_80_81_responsivity_vs_wl_80remeasured_2026-07-01_4x3.pdf

i.e. the chip-80 re-measured (2026-07-01) variant at 4:3 aspect ratio, with the
same "{chip} ({material})" legend labels.

Two figures are produced: t_rise vs wavelength and t_fall vs wavelength.

Wavelength range: 365-455 nm only. Beyond 455 nm these devices show no
above-noise photoresponse, so a "response time" there is fitted to noise and
carries no meaning.

Metric provenance: `t_rise_corrected` / `t_fall_corrected` from
`ITSRiseFallExtractor` -- the model-free 10-90 rule applied to the
drift-corrected current (stretched-exponential drift fitted on 20-60 s and
subtracted), matching the drift-corrected basis of the responsivity figure.
Values are read from the enriched chip history when present; when the columns
are absent the extractor is run on the staged parquet directly, so the numbers
are identical either way. Pass --raw to plot the uncorrected `t_rise` / `t_fall`
instead (separate output files; the corrected figures are unaffected).

A wavelength with no measurable transition (e.g. a relaxation that never
recovers, so the fall is undefined) is omitted from its curve rather than
plotted as zero. Every such omission, plus every point whose 10-90 geometry is
questionable (SIGN_SWITCH, RISE/FALL_ONSET_CLAMPED), is shown in a third
"problem cases" figure: one panel per case with the measured trace, the light
window and the 10-90 overlay, titled with the reason the extractor gave.

Run from repo root:
    .venv/bin/python "scripts/spectral plots/plot_rise_fall_vs_wl_67_72_74_75_80_81.py"
    .venv/bin/python "scripts/spectral plots/plot_rise_fall_vs_wl_67_72_74_75_80_81.py" --raw
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.extractors.its_rise_fall_extractor import ITSRiseFallExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

# ── Reuse the responsivity script wholesale ────────────────────────────
# Imported by path because the containing folder has a space in its name.
_REF_PATH = Path("scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py")
_spec = importlib.util.spec_from_file_location("_spectral_pairs_ref", _REF_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot import reference script: {_REF_PATH}")
ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ref)

OUTPUT_DIR = Path("figs/rise_fall_spectral")
METRICS_PATH = Path("data/03_derived/_metrics/metrics.parquet")

# Same chip set and chip-80 seq override as the reference 4x3 figure.
ALL_CHIPS = [67, 72, 74, 75, 80, 81]

# Only the UV-blue end responds; longer wavelengths sit in the noise.
WL_MIN_NM = 365.0
WL_MAX_NM = 455.0

MODES = ("rise", "fall")
AXIS_LABELS = {"rise": r"$t_{rise}$ (s)", "fall": r"$t_{fall}$ (s)"}


def metric_column(mode: str, corrected: bool) -> str:
    base = "t_rise" if mode == "rise" else "t_fall"
    return f"{base}_corrected" if corrected else base


def load_metric_flags(corrected: bool) -> dict[tuple[str, str], str]:
    """{(run_id, metric_name): flags} from metrics.parquet, for the table."""
    if not METRICS_PATH.exists():
        return {}
    names = [metric_column(m, corrected) for m in MODES]
    df = pl.read_parquet(METRICS_PATH).filter(pl.col("metric_name").is_in(names))
    return {
        (r["run_id"], r["metric_name"]): (r["flags"] or "")
        for r in df.iter_rows(named=True)
    }


def _extract_from_parquet(row: dict, mode: str, corrected: bool) -> float:
    """Run ITSRiseFallExtractor on one staged measurement (column fallback)."""
    parquet_path = Path(row.get("parquet_path") or "")
    if not parquet_path.exists():
        return float("nan")
    meas = read_measurement_parquet(parquet_path)
    metric = ITSRiseFallExtractor(mode=mode, corrected=corrected).extract(
        meas,
        {
            "run_id": row.get("run_id"),
            "chip_number": row.get("chip_number"),
            "chip_group": row.get("chip_group"),
            "proc": row.get("proc"),
            "seq_num": row.get("seq"),
            "extraction_version": "rise_fall_vs_wl_viz",
        },
    )
    return float("nan") if metric is None else float(metric.value_float)


def collect_response_times(
    chip_number: int,
    *,
    seqs: list[int] | None = None,
    corrected: bool = True,
    flags_by_run: dict[tuple[str, str], str] | None = None,
) -> dict[str, list[dict]]:
    """
    Return {"rise": [{"wl", "value", "flags"}, ...], "fall": [...]} for one
    chip, restricted to WL_MIN_NM..WL_MAX_NM and sorted by wavelength.

    Non-finite / missing response times are dropped: they mean the 10-90 rule
    found no measurable transition, not a zero-second one.
    """
    history = ref.load_history(chip_number)
    rows = ref.select_its_rows(
        history, seqs if seqs is not None else ref.CHIPS[chip_number]["seqs"]
    ).filter(
        pl.col("wavelength_nm").is_between(WL_MIN_NM, WL_MAX_NM)
    )
    flags_by_run = flags_by_run or {}

    out: dict[str, list[dict]] = {m: [] for m in MODES}
    for mode in MODES:
        column = metric_column(mode, corrected)
        have_column = column in rows.columns
        if not have_column:
            print(f"  [chip {chip_number}] '{column}' absent from history; "
                  f"extracting from staged parquet")
        for row in rows.iter_rows(named=True):
            wl = row.get("wavelength_nm")
            if wl is None or not np.isfinite(float(wl)):
                continue
            value = row.get(column) if have_column else _extract_from_parquet(
                row, mode, corrected
            )
            if value is None or not np.isfinite(float(value)):
                print(f"  [chip {chip_number}] {float(wl):.0f} nm: no {mode} time")
                continue
            out[mode].append({
                "wl": float(wl),
                "value": float(value),
                "flags": flags_by_run.get((row.get("run_id"), column), ""),
            })
        out[mode].sort(key=lambda p: p["wl"])
    return out


def plot_response_time_vs_wl(
    times_by_chip: dict[int, dict[str, list[dict]]],
    mode: str,
    config: PlotConfig,
    output_path: Path,
    *,
    chips: list[int] | None = None,
    logy: bool = False,
    box_aspect: float = 1.0,
) -> None:
    """Response time vs wavelength -- same layout as ref.plot_responsivity_vs_wl."""
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / box_aspect, side))

    chips = chips if chips is not None else ALL_CHIPS
    seen_wls: set[float] = set()
    for chip_num in chips:
        pts = times_by_chip.get(chip_num, {}).get(mode, [])
        if not pts:
            print(f"  [chip {chip_num}] no {mode} points in "
                  f"{WL_MIN_NM:.0f}-{WL_MAX_NM:.0f} nm")
            continue
        wls = np.array([p["wl"] for p in pts])
        ts = np.array([p["value"] for p in pts])
        seen_wls.update(wls.tolist())
        ax.plot(
            wls, ts,
            color=ref.CHIP_COLORS.get(chip_num, "k"),
            marker=ref.chip_marker(chip_num),
            markersize=ref.MARKER_SIZE,
            linestyle="-",
            linewidth=ref.LINE_WIDTH,
            label=ref.CHIPS[chip_num]["label"],
        )

    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(r"Wavelength (nm)")
    ax.set_ylabel(AXIS_LABELS[mode])
    # Only four wavelengths are measured in this window; tick the real ones
    # rather than letting matplotlib invent intermediate values.
    if seen_wls:
        ax.set_xticks(sorted(seen_wls))
    ax.set_box_aspect(box_aspect)
    ax.legend(loc="best", framealpha=0.9, ncol=2, fontsize=ref._legend_fontsize())

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


# Flags that question the 10-90 geometry itself (as opposed to the drift fit,
# whose LOW_R_SQUARED / FIT_DID_NOT_CONVERGE mostly say "there was little drift
# to fit", not "the response time is wrong").
GEOMETRY_FLAGS = ("SIGN_SWITCH", "RISE_ONSET_CLAMPED", "FALL_ONSET_CLAMPED")


def _geometry_flags(flags: str) -> str:
    hit = [f for f in GEOMETRY_FLAGS if f in (flags or "")]
    return ",".join(hit) if hit else ""


def print_response_time_table(
    times_by_chip: dict[int, dict[str, list[dict]]],
    chips: list[int],
) -> None:
    """Markdown table of rise and fall times per chip x wavelength."""
    print("\n| chip | material | lambda (nm) | t_rise (s) | t_fall (s) | flags |")
    print("|---|---|---|---|---|---|")
    for chip_num in chips:
        material = ref._MATERIALS.get(chip_num, "?")
        rise = {p["wl"]: p for p in times_by_chip.get(chip_num, {}).get("rise", [])}
        fall = {p["wl"]: p for p in times_by_chip.get(chip_num, {}).get("fall", [])}
        for wl in sorted(set(rise) | set(fall)):
            r, f = rise.get(wl), fall.get(wl)
            notes = [
                f"{tag}:{_geometry_flags(p['flags'])}"
                for p, tag in ((r, "rise"), (f, "fall"))
                if p is not None and _geometry_flags(p["flags"])
            ]
            r_txt = "--" if r is None else f"{r['value']:.2f}"
            f_txt = "--" if f is None else f"{f['value']:.2f}"
            print(
                f"| {chip_num} | {material} | {wl:.0f} | {r_txt} | {f_txt} | "
                f"{' '.join(notes)} |"
            )


# ══════════════════════════════════════════════════════════════════════
# Diagnostics: the traces behind the missing and flagged points
# ══════════════════════════════════════════════════════════════════════

RISE_COLOR = "#377eb8"
FALL_COLOR = "#e41a1c"

# Type scale for the multi-panel diagnostic figure, applied via rc_context.
DIAGNOSTIC_RCPARAMS = {
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "lines.linewidth": 1.4,
    "lines.markersize": 8,
}


class _SkipReasonCapture(logging.Handler):
    """Collect the `reason` the extractor logs when it declines a trace."""

    LOGGER_NAME = "src.derived.extractors.its_rise_fall_extractor"

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.reasons: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        reason = getattr(record, "reason", None)
        if reason:
            self.reasons.append(str(reason))

    def __enter__(self) -> "_SkipReasonCapture":
        self._logger = logging.getLogger(self.LOGGER_NAME)
        self._prev_level = self._logger.level
        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(self)
        return self

    def __exit__(self, *exc) -> None:
        self._logger.removeHandler(self)
        self._logger.setLevel(self._prev_level)


def _extract_with_reason(extractor, meas, meta) -> tuple[object | None, str]:
    """extract(), plus the skip reason when it returns None."""
    with _SkipReasonCapture() as cap:
        metric = extractor.extract(meas, meta)
    if metric is not None:
        return metric, ""
    return None, cap.reasons[-1] if cap.reasons else "UNKNOWN"


def collect_problem_cases(
    chip_number: int,
    *,
    seqs: list[int] | None = None,
    corrected: bool = True,
) -> list[dict]:
    """
    Every (chip, wavelength) in the plotted window whose response time is
    missing or geometrically suspect, with the trace needed to see why.

    A case is a problem when a mode returns no value (the point is absent from
    the vs-wavelength curve) or carries a flag that questions the 10-90
    geometry itself -- SIGN_SWITCH or an onset clamped at the phase boundary.
    """
    history = ref.load_history(chip_number)
    rows = ref.select_its_rows(
        history, seqs if seqs is not None else ref.CHIPS[chip_number]["seqs"]
    ).filter(pl.col("wavelength_nm").is_between(WL_MIN_NM, WL_MAX_NM))

    extractors = {
        mode: ITSRiseFallExtractor(mode=mode, corrected=corrected)
        for mode in MODES
    }

    cases: list[dict] = []
    for row in rows.iter_rows(named=True):
        parquet_path = Path(row.get("parquet_path") or "")
        if not parquet_path.exists():
            print(f"  [chip {chip_number}] missing parquet: {parquet_path}")
            continue
        meas = read_measurement_parquet(parquet_path)
        if not {"t (s)", "I (A)", "VL (V)"}.issubset(meas.columns):
            continue
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)
        vl = meas["VL (V)"].to_numpy().astype(np.float64)
        meta = {
            "run_id": row.get("run_id"),
            "chip_number": row.get("chip_number"),
            "chip_group": row.get("chip_group"),
            "proc": row.get("proc"),
            "seq_num": row.get("seq"),
            "extraction_version": "rise_fall_vs_wl_diagnostics",
        }

        metrics: dict[str, object | None] = {}
        problems: list[str] = []
        for mode in MODES:
            metric, reason = _extract_with_reason(extractors[mode], meas, meta)
            metrics[mode] = metric
            if metric is None:
                problems.append(f"no {mode} time ({reason})")
            else:
                geometric = _geometry_flags(metric.flags or "")
                if geometric:
                    problems.append(f"{mode}: {geometric}")

        if not problems:
            continue

        # The trace the extractor actually measured on.
        i_shown = i
        if corrected:
            i_corr = extractors["rise"].corrected_current(t, i, vl, meta["run_id"])
            if i_corr is not None:
                i_shown = i_corr

        material = ref._MATERIALS.get(chip_number, "?")
        vg = row.get("vg_fixed_v")
        vg_txt = "" if vg is None else rf", $V_g={float(vg):+g}$ V"
        cases.append({
            "chip": chip_number,
            "label": (f"{chip_number} ({material}) — "
                      f"{float(row['wavelength_nm']):.0f} nm"
                      f"  [seq {row.get('seq')}{vg_txt}]"),
            "wavelength_nm": float(row["wavelength_nm"]),
            "seq": row.get("seq"),
            "date": row.get("date"),
            "vg_v": row.get("vg_fixed_v"),
            "t": t,
            "i": i_shown,
            "vl": vl,
            "metrics": metrics,
            "problems": problems,
        })
    return cases


def _draw_metric(ax, t, i, metric, color, name) -> None:
    """Overlay 10/90 levels, first-crossing markers and the response interval.

    Mirrors the panel overlay in
    scripts/parameter_extractions_viz/plot_rise_fall_1090_alisson74_365nm.py.
    """
    if metric is None:
        ax.plot([], [], " ", label=f"{name}: none")
        return
    details = json.loads(metric.value_json)
    for sec in details["sections"]:
        ax.axhline(sec["level_10"] * 1e6, color=color, linewidth=1.2,
                   linestyle=":", alpha=0.7)
        ax.axhline(sec["level_90"] * 1e6, color=color, linewidth=1.2,
                   linestyle=":", alpha=0.7)
        t10, t90 = sec["t_10"], sec["t_90"]
        ax.axvspan(min(t10, t90), max(t10, t90), color=color, alpha=0.12)
        ax.plot(
            [t10, t90],
            [i[sec["idx_10"]] * 1e6, i[sec["idx_90"]] * 1e6],
            "o", color=color, markersize=12, zorder=5,
        )
    times = " + ".join(f"{s['response_time']:.1f}" for s in details["sections"])
    suffix = "  (sign switch)" if details["sign_switch"] else ""
    ax.plot([], [], "o", color=color, label=f"{name} = {times} s{suffix}")


def plot_problem_cases(
    cases: list[dict],
    config: PlotConfig,
    output_path: Path,
    *,
    corrected: bool = True,
    ncols: int = 3,
) -> None:
    """One panel per problem case: the measured trace and the 10-90 overlay.

    Each case needs "t", "i", "vl", "metrics" (a rise/fall dict), "problems"
    and a ready-made panel "label". The sweep variable lives in that label, so
    scripts/power_sweeps/plot_rise_fall_vs_power_semilogy_2026-05-14.py reuses
    this for its power sweep.
    """
    if not cases:
        print("no problem cases to plot")
        return

    set_plot_style(config.theme)
    nrows = int(np.ceil(len(cases) / ncols))
    fit_t_start = ITSRiseFallExtractor(mode="rise").fit_t_start

    # The theme sizes type for 35-inch publication figures. Rescale inside an
    # rc_context -- before the axes are built, so tick labels pick it up too --
    # and leave the global rcParams untouched for anything plotted after.
    with plt.rc_context(DIAGNOSTIC_RCPARAMS):
        fig, axes = plt.subplots(
            nrows, ncols, figsize=(9.0 * ncols, 6.0 * nrows), squeeze=False
        )
        flat = axes.ravel()
        for ax, case in zip(flat, cases):
            t, i, vl = case["t"], case["i"], case["vl"]
            ax.plot(t, i * 1e6, color="0.25", linewidth=1.4,
                    label=r"$I_{corr}(t)$" if corrected else "$I(t)$")
            if corrected:
                ax.axhline(0.0, color="0.6", linewidth=0.8, linestyle="--",
                           zorder=0)

            on_idx = np.where(vl > 0.1)[0]
            if on_idx.size:
                ax.axvspan(float(t[on_idx[0]]), float(t[on_idx[-1]]),
                           color="0.85", alpha=config.light_window_alpha,
                           zorder=0)

            _draw_metric(ax, t, i, case["metrics"]["rise"], RISE_COLOR, "rise")
            _draw_metric(ax, t, i, case["metrics"]["fall"], FALL_COLOR, "fall")

            ax.set_title(case["label"] + "\n" + "; ".join(case["problems"]))
            ax.set_xlabel(r"$t\ (\mathrm{s})$")
            ax.set_ylabel(r"$I_{corr}\ (\mu\mathrm{A})$" if corrected
                          else r"$I\ (\mu\mathrm{A})$")
            ax.legend(loc="best", framealpha=0.9)
            if t.size:
                ax.set_xlim(float(t[0]), float(t[-1]))
            if corrected:
                # Ignore the pre-window extrapolation transient when scaling y.
                settled = t >= fit_t_start
                if np.any(settled):
                    lo = float(np.min(i[settled]))
                    hi = float(np.max(i[settled]))
                    pad = 0.08 * max(hi - lo, 1e-12)
                    ax.set_ylim((lo - pad) * 1e6, (hi + pad) * 1e6)

        for ax in flat[len(cases):]:
            ax.axis("off")

        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def main(corrected: bool = True) -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    flags_by_run = load_metric_flags(corrected)
    times_by_chip: dict[int, dict[str, list[dict]]] = {}
    for chip_num in ALL_CHIPS:
        print(f"[chip {chip_num}] collecting response times…")
        seqs = ref.CHIP80_REMEASURED_SEQS if chip_num == 80 else None
        if chip_num == 80:
            print("  using the re-measured (2026-07-01) seqs, as in the "
                  "reference 4x3 figure")
        times_by_chip[chip_num] = collect_response_times(
            chip_num, seqs=seqs, corrected=corrected, flags_by_run=flags_by_run
        )

    kind = "corrected" if corrected else "raw"
    for mode in MODES:
        plot_response_time_vs_wl(
            times_by_chip,
            mode,
            config,
            OUTPUT_DIR
            / f"alisson67_72_74_75_80_81_t_{mode}_{kind}_vs_wl"
              f"_80remeasured_2026-07-01_4x3.pdf",
            chips=ALL_CHIPS,
            box_aspect=3.0 / 4.0,
        )

    print_response_time_table(times_by_chip, ALL_CHIPS)

    # Diagnostics: the traces behind every point the curves could not show or
    # had to show with a caveat.
    cases: list[dict] = []
    for chip_num in ALL_CHIPS:
        seqs = ref.CHIP80_REMEASURED_SEQS if chip_num == 80 else None
        cases.extend(
            collect_problem_cases(chip_num, seqs=seqs, corrected=corrected)
        )
    print(f"\n{len(cases)} problem case(s):")
    for c in cases:
        print(f"  chip {c['chip']} @ {c['wavelength_nm']:.0f} nm "
              f"(seq {c['seq']}): {'; '.join(c['problems'])}")
    plot_problem_cases(
        cases,
        config,
        OUTPUT_DIR
        / f"alisson67_72_74_75_80_81_t_rise_fall_{kind}_problem_cases"
          f"_80remeasured_2026-07-01.pdf",
        corrected=corrected,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        action="store_true",
        help="plot the uncorrected t_rise / t_fall (default: the "
             "drift-corrected t_rise_corrected / t_fall_corrected)",
    )
    args = parser.parse_args()
    main(corrected=not args.raw)
