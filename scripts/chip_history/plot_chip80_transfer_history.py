"""Chip-80 transfer-curve history: evolution over the full measurement record.

Suitability filter
------------------
The CNP is recomputed *in this script* for every dark IVg (reusing the same
parabola algorithm as the derived-metrics pipeline), rather than trusting the
enriched `cnp_voltage` column -- that column is null for the newest session
(2026-07-01), whose run_ids were never added to metrics.parquet (stale
pipeline), even though those curves fit a clean CNP. A curve is deemed
**not suitable** if the CNP fit fails OR |V_cnp| > 1 V (NOT_SUITABLE_ABS_VCNP);
the |V_cnp| > 1 V cases are transfer curves whose extracted neutrality point is
physically implausible for this device and would distort the drift picture.

Three figures, all keyed to the sequence index (`seq`) as the time axis --
never wall-clock time:

  1. chip80_transfer_overlay_seq_gradient.pdf
       Suitable dark IVg forward branches, overlaid. Single-hue blue gradient
       by seq (darkest = oldest), older curves drawn behind newer. Colorbar
       instead of a per-curve legend.

  2. chip80_cnp_vs_seq.pdf
       In-script CNP voltage vs sequence index for the suitable curves --
       shows how far the neutrality point has drifted historically.

  2b. chip80_cnp_vs_time.pdf
       Same CNP values vs *elapsed time* (days, first measurement at t=0), so
       idle gaps show as horizontal spacing -- reveals whether long periods
       without measuring shift the CNP.

  3. chip80_transfer_not_suitable.pdf
       The dark IVg curves flagged not suitable (|V_cnp| > 1 V or no fit),
       same overlay style, for visual inspection.

  4. chip80_rest_effect_dcnp_vs_gap.pdf
       CNP shift across each idle gap vs the rest duration (log days) -- the
       direct test of whether not measuring for a while moves the CNP.

  5. chip80_rest_before_after_pairs.pdf
       One panel per rest gap: last transfer curve before vs first after, with
       both CNPs marked. Isolates the rest effect from ordinary cycling.

Data: data/03_derived/chip_histories_enriched/Alisson80_history.parquet
Reuses read_measurement_parquet (src/core/utils.py), split_full_range_legs and
fit_parabola_vertex (src/derived/algorithms/cnp_parabola.py).

Run from repo root:
    .venv/bin/python "scripts/chip_history/plot_chip80_transfer_history.py"
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.cnp_parabola import (
    fit_parabola_vertex,
    split_full_range_legs,
)
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

CHIP = 80
HISTORY_PATH = Path(
    "data/03_derived/chip_histories_enriched/Alisson80_history.parquet"
)
ENCAP_CONFIG = Path("config/encap_characteristics.yaml")
OUTPUT_DIR = Path("figs/chip80_transfer_history")

# A transfer curve is flagged "not suitable" if its extracted neutrality point
# lies beyond this magnitude (V) -- implausible for this device.
NOT_SUITABLE_ABS_VCNP = 1.4

# Consecutive suitable measurements separated by more than this many days count
# as a "rest gap" for the before/after rest-effect comparison.
GAP_THRESHOLD_DAYS = 3.0

# Before/after colours for the rest-effect pair panels.
_C_BEFORE = "#1f4e79"  # dark blue -- last curve before the rest
_C_AFTER = "#c1440e"   # rust      -- first curve after the rest

# Truncated Blues: skip the near-white low end so the newest curves stay
# visible against the background.
_BLUES = plt.get_cmap("Blues")
CMAP = _BLUES  # normalized manually below via the truncation helper


def _blue(frac: float) -> tuple:
    """Map seq-fraction in [0, 1] onto Blues so OLD (frac=0) is darkest and
    NEW (frac=1) is lightest. Stay in the legible 0.35..1.0 slice."""
    return _BLUES(1.0 - 0.65 * frac)


def material_label(chip: int) -> str:
    """Return e.g. '80 (hBN)' using the bottom-dielectric tag from config."""
    data = yaml.safe_load(ENCAP_CONFIG.read_text())
    entry = data.get(chip)
    if entry and "material" in entry:
        return f"{chip} ({entry['material']})"
    return str(chip)


def forward_branch(vg: np.ndarray, i: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Isolate the forward (Vg increasing) full-range leg of a looped sweep."""
    legs = split_full_range_legs(vg, i)
    for vg_leg, sig_leg, direction in legs:
        if direction == "forward":
            return vg_leg, sig_leg
    # Fallback: no qualifying forward leg -- return the raw trace sorted by Vg.
    order = np.argsort(vg)
    return vg[order], i[order]


def compute_cnp(vg: np.ndarray, i: np.ndarray) -> float | None:
    """CNP for one looped IVg, matching the pipeline's `cnp_voltage` metric.

    Fits a parabola vertex on each full-range leg and averages the forward and
    backward neutrality points (falls back to whichever leg is present).
    Returns None if no leg yields a fittable vertex.
    """
    finite = np.isfinite(vg) & np.isfinite(i)
    vg, i = vg[finite], i[finite]
    legs = split_full_range_legs(vg, i)
    fwd = back = None
    for vg_leg, sig_leg, direction in legs:
        fit = fit_parabola_vertex(vg_leg, sig_leg, extremum="min")
        if fit is None:
            continue
        if direction == "forward" and fwd is None:
            fwd = fit["v_cnp"]
        elif direction == "backward" and back is None:
            back = fit["v_cnp"]
    if fwd is not None and back is not None:
        return 0.5 * (fwd + back)
    return fwd if fwd is not None else back


def load_dark_ivg() -> pl.DataFrame:
    """Dark IVg rows for chip 80, ordered by seq, with an in-script `cnp`
    column (recomputed here -- see module docstring on why we don't rely on the
    enriched `cnp_voltage`)."""
    df = (
        pl.read_parquet(HISTORY_PATH)
        .filter((pl.col("proc") == "IVg") & (~pl.col("has_light")))
        .sort("seq")
    )
    cnps: list[float | None] = []
    for row in df.iter_rows(named=True):
        m = read_measurement_parquet(row["parquet_path"])
        cnps.append(
            compute_cnp(m["Vg (V)"].to_numpy(), m["I (A)"].to_numpy())
        )
    return df.with_columns(pl.Series("cnp", cnps, dtype=pl.Float64))


def plot_overlay(
    rows: pl.DataFrame,
    outfile: Path,
    chip_label: str,
    seq_norm: Normalize,
    config: PlotConfig,
) -> None:
    """Overlay forward transfer branches, blue gradient + z-order by seq."""
    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(figsize=(side, side))
    for row in rows.iter_rows(named=True):
        seq = row["seq"]
        m = read_measurement_parquet(row["parquet_path"])
        vg = m["Vg (V)"].to_numpy()
        i = m["I (A)"].to_numpy()
        vg_f, i_f = forward_branch(vg, i)
        frac = float(seq_norm(seq))
        ax.plot(
            vg_f,
            i_f * 1e6,  # A -> uA
            color=_blue(frac),
            lw=2.0,
            zorder=int(seq),  # older (lower seq) behind newer
        )

    ax.set_xlabel(r"$V_g$ (V)")
    ax.set_ylabel(r"$I$ ($\mu$A)")
    ax.set_box_aspect(1.0)

    # Reversed cmap so the colorbar matches the curves: low seq (old) = dark.
    sm = ScalarMappable(norm=seq_norm, cmap=plt.get_cmap("Blues_r"))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Sequence index")

    ax.text(
        0.04,
        0.94,
        chip_label,
        transform=ax.transAxes,
        va="top",
        ha="left",
        zorder=10_000,  # above all curves (their zorder = seq, up to ~190)
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.9, pad=2.0),
    )
    fig.tight_layout()
    fig.savefig(outfile, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)


def plot_cnp_vs_seq(
    rows: pl.DataFrame, outfile: Path, chip_label: str, config: PlotConfig
) -> None:
    """CNP voltage vs sequence index for the suitable curves."""
    valid = rows.sort("seq")
    seq = valid["seq"].to_numpy()
    cnp = valid["cnp"].to_numpy()

    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(figsize=(side, side))
    ax.plot(seq, cnp, marker="o", ms=8, lw=1.5, color=_BLUES(0.85))
    ax.set_xlabel("Sequence index")
    ax.set_ylabel(r"$V_{CNP}$ (V)")
    ax.set_box_aspect(1.0)
    ax.text(
        0.04,
        0.94,
        chip_label,
        transform=ax.transAxes,
        va="top",
        ha="left",
    )
    fig.tight_layout()
    fig.savefig(outfile, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)


def plot_cnp_vs_time(
    rows: pl.DataFrame, outfile: Path, chip_label: str, config: PlotConfig
) -> None:
    """CNP voltage vs elapsed time (days) for the suitable curves.

    Unlike the sequence-index view, the x-axis is real wall-clock time with the
    first measurement at t=0, so long idle gaps show up as horizontal spacing --
    lets us see whether not measuring for a while shifts the CNP.
    """
    valid = rows.sort("start_dt")
    t0 = valid["start_dt"].min()
    days = (
        valid.select(
            ((pl.col("start_dt") - t0).dt.total_seconds() / 86400.0).alias("d")
        )["d"].to_numpy()
    )
    cnp = valid["cnp"].to_numpy()

    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(figsize=(side, side))
    ax.plot(days, cnp, marker="o", ms=8, lw=1.5, color=_BLUES(0.85))
    ax.set_xlabel("Time since first measurement (days)")
    ax.set_ylabel(r"$V_{CNP}$ (V)")
    ax.set_box_aspect(1.0)
    ax.text(
        0.04,
        0.94,
        chip_label,
        transform=ax.transAxes,
        va="top",
        ha="left",
    )
    fig.tight_layout()
    fig.savefig(outfile, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)


def find_rest_gaps(suitable: pl.DataFrame) -> list[dict]:
    """Rest gaps in the suitable set: consecutive-in-time pairs whose spacing
    exceeds GAP_THRESHOLD_DAYS. Each entry pairs the last curve *before* the
    gap with the first curve *after* it -- isolating the rest effect from
    ordinary back-to-back cycling."""
    s = suitable.sort("start_dt")
    t = s["start_dt"].to_numpy()
    dt_days = np.diff(t) / np.timedelta64(1, "D")
    rows = s.to_dicts()
    gaps = []
    for k in range(len(dt_days)):
        if dt_days[k] > GAP_THRESHOLD_DAYS:
            gaps.append(
                {
                    "before": rows[k],
                    "after": rows[k + 1],
                    "gap_days": float(dt_days[k]),
                    "dcnp": rows[k + 1]["cnp"] - rows[k]["cnp"],
                }
            )
    return gaps


def plot_rest_effect_scatter(
    gaps: list[dict], outfile: Path, chip_label: str, config: PlotConfig
) -> None:
    """Rest-induced CNP shift vs rest duration -- the direct test of whether
    long idle periods move the neutrality point. One point per gap."""
    gap_days = np.array([g["gap_days"] for g in gaps])
    dcnp = np.array([g["dcnp"] for g in gaps])

    side = float(config.figsize_timeseries[1])
    fig, ax = plt.subplots(figsize=(side, side))
    ax.axhline(0.0, color="0.6", ls=":", lw=1.5)
    ax.plot(gap_days, dcnp, marker="o", ms=12, ls="none", color=_C_AFTER)
    ax.set_xscale("log")
    ax.set_xlabel("Rest duration (days)")
    ax.set_ylabel(r"$\Delta V_{CNP}$ across rest (V)")
    ax.set_box_aspect(1.0)
    ax.text(
        0.04, 0.94, chip_label, transform=ax.transAxes, va="top", ha="left"
    )
    fig.tight_layout()
    fig.savefig(outfile, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)


def plot_rest_before_after_pairs(
    gaps: list[dict], outfile: Path, chip_label: str, config: PlotConfig
) -> None:
    """One panel per rest gap: the last transfer curve before the rest and the
    first one after it (forward branch), with each CNP marked. Panels ordered
    by increasing rest duration."""
    gaps = sorted(gaps, key=lambda g: g["gap_days"])
    n = len(gaps)
    ncol = 3
    nrow = int(np.ceil(n / ncol))
    side = float(config.figsize_timeseries[1])
    panel = side * 0.55
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(ncol * panel, nrow * panel), squeeze=False
    )

    for idx, ax in enumerate(axes.flat):
        if idx >= n:
            ax.axis("off")
            continue
        g = gaps[idx]
        for role, color in (("before", _C_BEFORE), ("after", _C_AFTER)):
            row = g[role]
            m = read_measurement_parquet(row["parquet_path"])
            vg_f, i_f = forward_branch(
                m["Vg (V)"].to_numpy(), m["I (A)"].to_numpy()
            )
            ax.plot(
                vg_f, i_f * 1e6, color=color, lw=2.0,
                label=f"{role} (seq {row['seq']})",
            )
            ax.axvline(row["cnp"], color=color, ls=":", lw=1.5)
        ax.set_box_aspect(1.0)
        ax.text(
            0.04, 0.96,
            f"{g['gap_days']:.0f} d rest\n"
            rf"$\Delta V_{{CNP}}={g['dcnp']:+.2f}$ V",
            transform=ax.transAxes, va="top", ha="left",
        )
        ax.legend(loc="lower right", fontsize=_legend_fontsize())

    fig.supxlabel(r"$V_g$ (V)")
    fig.supylabel(r"$I$ ($\mu$A)")
    fig.suptitle("")  # keep matplotlib from reserving title space
    fig.text(
        0.01, 0.99, chip_label, va="top", ha="left",
        fontsize=plt.rcParams["axes.labelsize"],
    )
    fig.tight_layout()
    fig.savefig(outfile, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)


def _legend_fontsize(relative: str = "small") -> float:
    """Theme legend size + 2 pt, per the project's publication convention."""
    from matplotlib.font_manager import font_scalings
    return plt.rcParams["font.size"] * font_scalings[relative] + 2.0


def main() -> None:
    config = PlotConfig()
    set_plot_style(config.theme)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    chip_label = material_label(CHIP)
    dark = load_dark_ivg()

    # Suitable = a CNP was fitted AND it is physically plausible (|V_cnp| <= 1 V).
    suitable = dark.filter(
        pl.col("cnp").is_not_null()
        & (pl.col("cnp").abs() <= NOT_SUITABLE_ABS_VCNP)
    )
    not_suitable = dark.filter(
        pl.col("cnp").is_null()
        | (pl.col("cnp").abs() > NOT_SUITABLE_ABS_VCNP)
    )

    print(f"dark IVg: {dark.height}")
    print(f"  suitable (|V_cnp| <= {NOT_SUITABLE_ABS_VCNP} V): {suitable.height}")
    print(f"  not suitable (|V_cnp| > {NOT_SUITABLE_ABS_VCNP} V or no fit): "
          f"{not_suitable.height}")
    print(f"  not-suitable seqs: {not_suitable['seq'].to_list()}")
    print("  not-suitable (seq, V_cnp): "
          f"{list(zip(not_suitable['seq'].to_list(), not_suitable['cnp'].to_list()))}")

    # Shared normalization across the full dark-seq range so gradient meaning
    # is consistent between the main and inspection overlays.
    seq_all = dark["seq"].to_numpy()
    seq_norm = Normalize(vmin=float(seq_all.min()), vmax=float(seq_all.max()))

    plot_overlay(
        suitable,
        OUTPUT_DIR / "chip80_transfer_overlay_seq_gradient.pdf",
        chip_label,
        seq_norm,
        config,
    )
    plot_cnp_vs_seq(
        suitable,
        OUTPUT_DIR / "chip80_cnp_vs_seq.pdf",
        chip_label,
        config,
    )
    plot_cnp_vs_time(
        suitable,
        OUTPUT_DIR / "chip80_cnp_vs_time.pdf",
        chip_label,
        config,
    )
    plot_overlay(
        not_suitable,
        OUTPUT_DIR / "chip80_transfer_not_suitable.pdf",
        chip_label,
        seq_norm,
        config,
    )

    # Rest-effect analysis: isolate the CNP shift across idle gaps.
    gaps = find_rest_gaps(suitable)
    print(f"rest gaps (> {GAP_THRESHOLD_DAYS} d): {len(gaps)}")
    for g in sorted(gaps, key=lambda x: x["gap_days"]):
        print(f"  seq {g['before']['seq']:>3} -> {g['after']['seq']:>3} : "
              f"{g['gap_days']:6.1f} d   dCNP={g['dcnp']:+.3f} V")
    plot_rest_effect_scatter(
        gaps,
        OUTPUT_DIR / "chip80_rest_effect_dcnp_vs_gap.pdf",
        chip_label,
        config,
    )
    plot_rest_before_after_pairs(
        gaps,
        OUTPUT_DIR / "chip80_rest_before_after_pairs.pdf",
        chip_label,
        config,
    )

    print(f"Wrote 6 figures to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
