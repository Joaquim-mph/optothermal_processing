"""
10-90% rise and fall time vs laser power for the 2026-05-14 365 nm sweeps.

Power-sweep companion to
`scripts/power_sweeps/plot_photoresponse_vs_power_semilogy_2026-05-14.py`:
the same measurements, the same chips, colors, markers, Vg filters, irradiance
axis and power-law annotation as that script's comparison figures -- with the
response time on the y axis instead of |delta_i_corrected| or R.

Chips / fixed gate voltage (all 365 nm, powers 6, 12, 18, 24 uW) come straight
from that script's CHIPS table, so the two families of figures always describe
the same traces:
    68  Vg = -0.7  V      76  Vg = -0.7  V
    74  Vg = -0.5  V      72  Vg = -0.35 V
    75  Vg = -0.5  V      80  Vg = -1.2  V

NOTE (inherited): the 6-24 uW range is suspected to be in the channel-current
saturation regime -- the 2026-05-15 re-measurement at 1-6 uW was motivated by
that. Exponents from this date may not reflect the linear-response regime.

Metric: `t_rise_corrected` / `t_fall_corrected` -- the model-free 10-90 rule
applied to the drift-corrected current (`ITSRiseFallExtractor(corrected=True)`).
The default drift-fit window is the extractor's own 20-60 s, so these numbers
match the `t_*_corrected` columns in the enriched histories and the spectral
rise/fall figures. Pass --fit-t-start 1 for strict parity with the sibling
photoresponse figures, which fit their drift from t = 1 s (differences are
under ~3 s except at 6 uW, where the longer window occasionally decides a
recovery is measurable and the shorter one does not). Pass --raw for the
uncorrected `t_rise` / `t_fall`.

A power with no measurable transition is omitted from its curve rather than
plotted as zero; every omission and every point whose 10-90 geometry is
questionable (SIGN_SWITCH, RISE/FALL_ONSET_CLAMPED) is shown in a "problem
cases" figure -- one panel per case with the trace, the light window and the
10-90 overlay, titled with the reason the extractor gave.

Run from repo root:
    .venv/bin/python scripts/power_sweeps/plot_rise_fall_vs_power_semilogy_2026-05-14.py
    .venv/bin/python scripts/power_sweeps/plot_rise_fall_vs_power_semilogy_2026-05-14.py --raw
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.derived.extractors.its_rise_fall_extractor import ITSRiseFallExtractor
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style


def _load_by_path(name: str, path: str):
    """Import a sibling script by path (some live in folders with spaces)."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Chip table, row selection, irradiance conversion and the power-law fit.
pw = _load_by_path(
    "_power_sweep_ref",
    "scripts/power_sweeps/plot_photoresponse_vs_power_semilogy_2026-05-14.py",
)
# Diagnostics panel machinery, shared with the spectral rise/fall figures.
spectral = _load_by_path(
    "_rise_fall_spectral",
    "scripts/spectral plots/plot_rise_fall_vs_wl_67_72_74_75_80_81.py",
)

OUTPUT_DIR = Path("figs/rise_fall_power_law_365nm")
ENRICHED_DIR = Path("data/03_derived/chip_histories_enriched")

MODES = ("rise", "fall")
AXIS_LABELS = {"rise": r"$t_{rise}$ (s)", "fall": r"$t_{fall}$ (s)"}

# LED powers of this sweep, used for the x ticks (as in the sibling figures).
SWEEP_POWERS_UW = [6, 12, 18, 24]


def load_history(chip: dict) -> pl.DataFrame:
    hist_chip = chip.get("history_chip", chip["chip"])
    path = ENRICHED_DIR / f"Alisson{hist_chip}_history.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Enriched history missing for chip {hist_chip}: {path}. "
            f"Run: biotite build-all-histories && biotite enrich-history {hist_chip}"
        )
    return pl.read_parquet(path)


def _meta(row: dict, chip: dict) -> dict:
    return {
        "run_id": row.get("run_id"),
        "chip_number": int(row.get("chip_number", chip["chip"])),
        "chip_group": str(row.get("chip_group", "Alisson")),
        "proc": row.get("proc", "It"),
        "seq_num": row.get("seq"),
        "extraction_version": "rise_fall_vs_power_viz",
    }


def collect_chip_points(
    hist: pl.DataFrame,
    chip: dict,
    *,
    corrected: bool = True,
    fit_t_start: float | None = None,
) -> dict[str, list[dict]]:
    """
    {"rise": [{"power_uW", "value", "flags"}, ...], "fall": [...]} for one chip.

    Rows come from the sibling photoresponse script's `rows_for_chip`, so the
    date / wavelength / Vg / seq-exclusion filtering is shared. Points whose
    response time is undefined are dropped, not zeroed.
    """
    rows = pw.rows_for_chip(hist, chip)
    kwargs = {} if fit_t_start is None else {"fit_t_start": fit_t_start}
    extractors = {
        mode: ITSRiseFallExtractor(mode=mode, corrected=corrected, **kwargs)
        for mode in MODES
    }

    out: dict[str, list[dict]] = {m: [] for m in MODES}
    for row in rows.iter_rows(named=True):
        p_w = row.get("irradiated_power_w")
        parquet_path = Path(row.get("parquet_path") or "")
        if p_w is None or not np.isfinite(float(p_w)) or not parquet_path.exists():
            continue
        meas = read_measurement_parquet(parquet_path)
        meta = _meta(row, chip)
        for mode in MODES:
            metric = extractors[mode].extract(meas, meta)
            if metric is None or not np.isfinite(metric.value_float):
                print(f"  [chip {chip['chip']}] {float(p_w) * 1e6:.0f} µW: "
                      f"no {mode} time")
                continue
            out[mode].append({
                "power_uW": float(p_w) * 1e6,
                "value": float(metric.value_float),
                "flags": metric.flags or "",
            })
    for mode in MODES:
        out[mode].sort(key=lambda d: d["power_uW"])
    return out


def plot_response_time_vs_power(
    points_by_chip: dict[int, dict[str, list[dict]]],
    mode: str,
    config: PlotConfig,
    output_path: Path,
    *,
    chips: list[dict],
) -> None:
    """
    Response time vs beam irradiance, semilog-y.

    Same layout as pw.plot_responsivity_comparison: irradiance x axis ticked at
    the sweep's LED powers, one marker style per chip, a power-law fit line, the
    exponent in the legend, and hBN references listed first.
    """
    set_plot_style(config.theme)
    fig, ax = plt.subplots(figsize=(21, 15))

    entries: list[tuple[str | None, mpl.lines.Line2D]] = []
    for chip in chips:
        pts = points_by_chip.get(chip["chip"], {}).get(mode, [])
        if not pts:
            print(f"[warn] no {mode} data for {pw.label_for_chip(chip)}")
            continue
        p = np.array([d["power_uW"] for d in pts])
        y = np.array([d["value"] for d in pts])

        # Same power-law machinery as the photoresponse figures: t ∝ P^gamma.
        gamma, p_fit, y_fit = pw.power_law_fit(p, y)
        if abs(gamma) < 5e-3:  # avoid printing "-0.00"
            gamma = 0.0

        (handle,) = ax.plot(
            pw.irradiance_mW_per_cm2(p),
            y,
            marker=chip["marker"],
            linestyle="none",
            color=chip["color"],
            markersize=25,
            label=f"{pw.label_for_chip(chip, include_vg=False)}, "
                  f"$\\gamma={gamma:.2f}$",
        )
        entries.append((pw._CHIP_MATERIALS.get(chip["chip"]), handle))
        if p_fit.size:
            ax.plot(
                pw.irradiance_mW_per_cm2(p_fit),
                y_fit,
                linestyle="-",
                color=chip["color"],
            )

        print(f"{pw.label_for_chip(chip)}  n={p.size}  "
              f"t_{mode}=[{y.min():.3g},{y.max():.3g}] s  gamma={gamma:.3f}")

    ax.set_yscale("log")
    # Response times span well under a decade for most chips, so label the
    # 1-2-5 log steps rather than decades only.
    ax.yaxis.set_major_locator(mpl.ticker.LogLocator(base=10.0, subs=(1.0, 2.0, 5.0)))
    ax.yaxis.set_minor_locator(plt.NullLocator())
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, pos: f"{v:g}"))

    ax.set_xlabel(r"Irradiance (mW/cm$^2$)")
    ax.set_ylabel(AXIS_LABELS[mode])
    _phi = pw.irradiance_mW_per_cm2(SWEEP_POWERS_UW)
    ax.set_xticks(_phi)
    ax.set_xticklabels([f"{v:g}" for v in _phi])
    ax.set_xlim(left=4)

    # hBN references first, then the biotite devices, each in CHIPS order.
    handles = [h for mat, h in entries if mat == "hBN"]
    handles += [h for mat, h in entries if mat != "hBN"]
    ax.legend(handles=handles, loc="best", framealpha=0.9)

    plt.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def collect_problem_cases(
    hist: pl.DataFrame,
    chip: dict,
    *,
    corrected: bool = True,
    fit_t_start: float | None = None,
) -> list[dict]:
    """Powers whose response time is missing or geometrically suspect.

    Same shape as the spectral script's collector, so its panel plotter can
    render these cases unchanged; only the panel `label` differs.
    """
    rows = pw.rows_for_chip(hist, chip)
    kwargs = {} if fit_t_start is None else {"fit_t_start": fit_t_start}
    extractors = {
        mode: ITSRiseFallExtractor(mode=mode, corrected=corrected, **kwargs)
        for mode in MODES
    }

    cases: list[dict] = []
    for row in rows.iter_rows(named=True):
        parquet_path = Path(row.get("parquet_path") or "")
        if not parquet_path.exists():
            continue
        meas = read_measurement_parquet(parquet_path)
        if not {"t (s)", "I (A)", "VL (V)"}.issubset(meas.columns):
            continue
        t = meas["t (s)"].to_numpy().astype(np.float64)
        i = meas["I (A)"].to_numpy().astype(np.float64)
        vl = meas["VL (V)"].to_numpy().astype(np.float64)
        meta = _meta(row, chip)

        metrics: dict[str, object | None] = {}
        problems: list[str] = []
        for mode in MODES:
            metric, reason = spectral._extract_with_reason(
                extractors[mode], meas, meta
            )
            metrics[mode] = metric
            if metric is None:
                problems.append(f"no {mode} time ({reason})")
            else:
                geometric = spectral._geometry_flags(metric.flags or "")
                if geometric:
                    problems.append(f"{mode}: {geometric}")
        if not problems:
            continue

        i_shown = i
        if corrected:
            i_corr = extractors["rise"].corrected_current(t, i, vl, meta["run_id"])
            if i_corr is not None:
                i_shown = i_corr

        p_uw = float(row.get("irradiated_power_w") or 0.0) * 1e6
        material = pw._CHIP_MATERIALS.get(chip["chip"], "?")
        vg = chip.get("vg_filter")
        vg_txt = "" if vg is None else rf", $V_g={vg:g}$ V"
        cases.append({
            "chip": chip["chip"],
            "label": (f"{chip['chip']} ({material}) — {p_uw:.0f} µW"
                      f"  [seq {row.get('seq')}{vg_txt}]"),
            "power_uW": p_uw,
            "seq": row.get("seq"),
            "vg_v": vg,
            "t": t,
            "i": i_shown,
            "vl": vl,
            "metrics": metrics,
            "problems": problems,
        })
    return cases


def print_table(
    points_by_chip: dict[int, dict[str, list[dict]]], chips: list[dict]
) -> None:
    print("\n| chip | material | P (uW) | irradiance (mW/cm2) | t_rise (s) | "
          "t_fall (s) | flags |")
    print("|---|---|---|---|---|---|---|")
    for chip in chips:
        n = chip["chip"]
        material = pw._CHIP_MATERIALS.get(n, "?")
        rise = {d["power_uW"]: d for d in points_by_chip.get(n, {}).get("rise", [])}
        fall = {d["power_uW"]: d for d in points_by_chip.get(n, {}).get("fall", [])}
        for p_uw in sorted(set(rise) | set(fall)):
            r, f = rise.get(p_uw), fall.get(p_uw)
            notes = [
                f"{tag}:{spectral._geometry_flags(d['flags'])}"
                for d, tag in ((r, "rise"), (f, "fall"))
                if d is not None and spectral._geometry_flags(d["flags"])
            ]
            phi = float(pw.irradiance_mW_per_cm2([p_uw])[0])
            r_txt = "--" if r is None else f"{r['value']:.2f}"
            f_txt = "--" if f is None else f"{f['value']:.2f}"
            print(
                f"| {n} | {material} | {p_uw:.0f} | {phi:.1f} | "
                f"{r_txt} | {f_txt} | {' '.join(notes)} |"
            )


def main(corrected: bool = True, fit_t_start: float | None = None) -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    points_by_chip: dict[int, dict[str, list[dict]]] = {}
    cases: list[dict] = []
    for chip in pw.CHIPS:
        print(f"[chip {chip['chip']}] collecting response times…")
        hist = load_history(chip)
        points_by_chip[chip["chip"]] = collect_chip_points(
            hist, chip, corrected=corrected, fit_t_start=fit_t_start
        )
        cases.extend(
            collect_problem_cases(
                hist, chip, corrected=corrected, fit_t_start=fit_t_start
            )
        )

    kind = "corrected" if corrected else "raw"
    # A non-default drift-fit window is a different metric definition, so it
    # gets its own filenames rather than overwriting the default figures.
    if corrected and fit_t_start is not None:
        default_start = ITSRiseFallExtractor(mode="rise").fit_t_start
        if float(fit_t_start) != float(default_start):
            kind += f"_fit{float(fit_t_start):g}s"
    chips_tag = "_".join(str(c["chip"]) for c in pw.CHIPS)
    for mode in MODES:
        plot_response_time_vs_power(
            points_by_chip,
            mode,
            config,
            OUTPUT_DIR
            / f"Alisson{chips_tag}_t_{mode}_{kind}_vs_power_semilogy"
              f"_{pw.DATE}_365nm.{config.format}",
            chips=pw.CHIPS,
        )

    print_table(points_by_chip, pw.CHIPS)

    print(f"\n{len(cases)} problem case(s):")
    for c in cases:
        print(f"  chip {c['chip']} @ {c['power_uW']:.0f} µW "
              f"(seq {c['seq']}): {'; '.join(c['problems'])}")
    spectral.plot_problem_cases(
        cases,
        config,
        OUTPUT_DIR
        / f"Alisson{chips_tag}_t_rise_fall_{kind}_problem_cases"
          f"_{pw.DATE}_365nm.{config.format}",
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
    parser.add_argument(
        "--fit-t-start",
        type=float,
        default=None,
        help="drift-fit window start in seconds (default: the extractor's own "
             "20 s, matching the enriched-history columns; pass 1 to match the "
             "sibling photoresponse figures)",
    )
    args = parser.parse_args()
    main(corrected=not args.raw, fit_t_start=args.fit_t_start)
