"""
External quantum efficiency vs wavelength for chips 67/72/74/75/80/81.

EQE companion to the responsivity-vs-wavelength figure produced by
`scripts/spectral plots/compare_corrected_It_67_72_74_75_80_81_pairs.py`.
All data selection, drift correction and responsivity machinery is imported
from that script, so the two figures are guaranteed to describe the same
traces; the only thing added here is the photon-energy conversion

    EQE = R * (h c / q) / lambda = R[A/W] * 1239.84 / lambda[nm]

Because the response is photogating-dominated, EQE greatly exceeds unity --
it is a photoconductive gain (electrons collected per incident photon), not a
photodiode efficiency. Both the percentage and the gain are the same number;
the y-axis is labelled EQE (%).

The reference figure being replicated is
    alisson67_72_74_75_80_81_responsivity_vs_wl_80remeasured_2026-07-01_4x3.pdf
i.e. the chip-80 re-measured (2026-07-01) variant at 4:3 aspect ratio.

Power provenance: `irradiated_power_w` is read from the enriched history when
present. When that column is absent (histories enriched without the
calibration step), the power is resolved on the fly with `CalibrationMatcher`
-- the same code path `biotite enrich-history` uses, so the numbers are
identical either way.

Run from repo root:
    .venv/bin/python "scripts/spectral plots/plot_eqe_vs_wl_67_72_74_75_80_81.py"
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.derived.extractors.calibration_matcher import CalibrationMatcher
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

OUTPUT_DIR = Path("figs/eqe_spectral")
MANIFEST_PATH = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")

# h*c/q in eV*nm -- EQE = R[A/W] * HC_OVER_Q_NM / lambda[nm].
HC_OVER_Q_NM = 1239.84198

# Same chip set and chip-80 seq override as the reference 4x3 figure.
ALL_CHIPS = [67, 72, 74, 75, 80, 81]


def backfill_power(traces: list[dict], stale_threshold_hours: float = 24.0) -> int:
    """Fill `power_w` for traces whose history lacked `irradiated_power_w`.

    Uses the same CalibrationMatcher path as `biotite enrich-history`, keyed on
    the measurement's UTC start time and wavelength. Returns the number of
    traces filled.
    """
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


def collect_traces_with_power(chip_number: int, seqs: list[int] | None = None) -> list[dict]:
    """`ref.collect_chip_traces` plus the fields needed to backfill power."""
    history = ref.load_history(chip_number)
    traces = ref.collect_chip_traces(chip_number, seqs=seqs)

    # collect_chip_traces drops the timestamp/laser-voltage columns; re-attach
    # them by wavelength so backfill_power can find a calibration.
    rows = ref.select_its_rows(history, seqs if seqs is not None else ref.CHIPS[chip_number]["seqs"])
    by_wl = {
        float(r["wavelength_nm"]): r
        for r in rows.iter_rows(named=True)
        if r.get("wavelength_nm") is not None
    }
    for tr in traces:
        row = by_wl.get(tr["wavelength_nm"])
        if row is None:
            continue
        tr["start_time_utc"] = row.get("start_time_utc")
        tr["laser_voltage_v"] = row.get("laser_voltage_v")

    filled = backfill_power(traces)
    if filled:
        print(f"  [chip {chip_number}] backfilled power for {filled}/{len(traces)} traces")
    return traces


def eqe_percent(tr: dict, area_um2: float | None) -> float:
    """EQE (%) = R * (hc/q) / lambda * 100, with R from the reference script."""
    r = ref.responsivity_at_post(tr, area_um2)
    wl = tr["wavelength_nm"]
    if not np.isfinite(r) or not np.isfinite(wl) or wl <= 0:
        return float("nan")
    return r * HC_OVER_Q_NM / wl * 100.0


def plot_eqe_vs_wl(
    traces_by_chip: dict[int, list[dict]],
    config: PlotConfig,
    output_path: Path,
    *,
    chips: list[int] | None = None,
    logy: bool = False,
    box_aspect: float = 1.0,
) -> None:
    """EQE vs wavelength -- same layout as ref.plot_responsivity_vs_wl."""
    set_plot_style(config.theme)
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(1, 1, figsize=(side / box_aspect, side))

    chips = chips if chips is not None else ALL_CHIPS
    areas = ref.device_areas_um2()
    for chip_num in chips:
        traces = traces_by_chip.get(chip_num, [])
        area = areas.get(chip_num)
        pts = []
        for tr in traces:
            wl = tr["wavelength_nm"]
            e = eqe_percent(tr, area)
            if np.isfinite(wl) and np.isfinite(e):
                pts.append((wl, e))
        if not pts:
            print(f"  [chip {chip_num}] no EQE points (area={area})")
            continue
        pts.sort()
        wls = np.array([p[0] for p in pts])
        es = np.array([p[1] for p in pts])
        ax.plot(
            wls, es,
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
    ax.set_ylabel(r"EQE (\%)" if plt.rcParams.get("text.usetex") else "EQE (%)")
    ax.set_box_aspect(box_aspect)
    ax.legend(loc="best", framealpha=0.9, ncol=2, fontsize=ref._legend_fontsize())

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {output_path}")


def print_eqe_table(traces_by_chip: dict[int, list[dict]], chips: list[int]) -> None:
    """Markdown table of R and EQE per chip x wavelength."""
    areas = ref.device_areas_um2()
    print("\n| chip | material | lambda (nm) | P_dev (nW) | |dI| (uA) | R (A/W) | EQE (%) | gain (e-/ph) |")
    print("|---|---|---|---|---|---|---|---|")
    for chip_num in chips:
        area = areas.get(chip_num)
        material = ref._MATERIALS.get(chip_num, "?")
        for tr in sorted(traces_by_chip.get(chip_num, []), key=lambda t: t["wavelength_nm"]):
            r = ref.responsivity_at_post(tr, area)
            e = eqe_percent(tr, area)
            di = abs(ref.photoresponse_at_post(tr))
            p_w = tr.get("power_w")
            p_dev_nw = (
                p_w * (area / ref.beam_area_um2(chip_num)) * 1e9
                if (p_w is not None and area is not None) else float("nan")
            )
            print(
                f"| {chip_num} | {material} | {tr['wavelength_nm']:.0f} | {p_dev_nw:.3g} | "
                f"{di:.4g} | {r:.4g} | {e:.4g} | {e / 100:.4g} |"
            )


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)

    traces_by_chip: dict[int, list[dict]] = {}
    for chip_num in ALL_CHIPS:
        print(f"[chip {chip_num}] collecting traces…")
        traces_by_chip[chip_num] = collect_traces_with_power(chip_num)

    # Chip-80 re-measurement (2026-07-01), matching the reference 4x3 figure.
    print("[chip 80] collecting re-measured (2026-07-01) traces…")
    traces_by_chip[80] = collect_traces_with_power(80, seqs=ref.CHIP80_REMEASURED_SEQS)

    plot_eqe_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR / "alisson67_72_74_75_80_81_eqe_vs_wl_80remeasured_2026-07-01_4x3.pdf",
        chips=ALL_CHIPS,
        box_aspect=3.0 / 4.0,
    )
    plot_eqe_vs_wl(
        traces_by_chip,
        config,
        OUTPUT_DIR
        / "alisson67_72_74_75_80_81_eqe_vs_wl_semilogy_80remeasured_2026-07-01_4x3.pdf",
        chips=ALL_CHIPS,
        logy=True,
        box_aspect=3.0 / 4.0,
    )

    print_eqe_table(traces_by_chip, ALL_CHIPS)


if __name__ == "__main__":
    main()
