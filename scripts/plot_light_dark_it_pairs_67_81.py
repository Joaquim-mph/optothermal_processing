"""
Concatenated light → dark I(t) plots for Encap81 and Encap67.

For each chip, walks the chip history in seq order, finds every (light It) →
(next dark It) pair with matching `vg_fixed_v` AND a turnover gap <= MAX_GAP_S,
and produces one PNG per pair showing the raw photocurrent ramp followed by the
dark relaxation tail on a continuous real-time axis (gap between the two seqs
preserved from `start_dt`).

The gap filter drops pairs where the dark It started long after the light It
ended (intervening procedures, next-day acquisitions) — those are not a clean
relaxation tail of the preceding illumination.

Run from repo root:

    python scripts/plot_light_dark_it_pairs_67_81.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.shared.config import PlotConfig
from src.plotting.shared.styles import set_plot_style

CHIPS = [81, 67]
VG_TOL = 1e-3  # treat Vg values within this tolerance as equal
MAX_GAP_S = 600.0  # skip pairs where dark It starts > this long after light ends

LIGHT_COLOR = "#1f77b4"
DARK_COLOR = "#444444"


def history_path(chip: int) -> Path:
    return Path(f"data/03_derived/chip_histories_enriched/Alisson{chip}_history.parquet")


def pair_gap_s(light: dict, dark: dict) -> float:
    """Wall-clock seconds between end of light It and start of dark It."""
    return (dark["start_dt"] - light["start_dt"]).total_seconds() - (
        light["laser_period_s"] or 0.0
    )


def find_pairs(history: pl.DataFrame) -> list[tuple[dict, dict]]:
    """Return (light_row, dark_row) pairs matched by Vg and gap, in seq order."""
    its = history.filter(pl.col("proc") == "It").sort("seq").to_dicts()
    pairs: list[tuple[dict, dict]] = []
    for i, row in enumerate(its):
        if not row["has_light"]:
            continue
        for j in range(i + 1, len(its)):
            cand = its[j]
            if cand["has_light"]:
                break  # next light arrived before a dark — skip
            if abs((cand["vg_fixed_v"] or 0.0) - (row["vg_fixed_v"] or 0.0)) > VG_TOL:
                continue  # Vg mismatch — keep looking for a matching dark
            if pair_gap_s(row, cand) <= MAX_GAP_S:
                pairs.append((row, cand))
            break  # first matching-Vg dark decides this light, pass or fail
    return pairs


def print_pair_table(chip: int, pairs: list[tuple[dict, dict]]) -> None:
    print(f"\nEncap{chip}: {len(pairs)} matching-Vg pairs with gap <= {MAX_GAP_S:.0f} s\n")
    print(f"{'seq_L':>5} {'t_L (s)':>9} {'seq_D':>5} {'t_D (s)':>9} "
          f"{'Vg (V)':>7} {'gap (s)':>8} {'wl (nm)':>7} {'date':>10}")
    print("-" * 76)
    for L, D in pairs:
        print(
            f"{L['seq']:>5} {L['laser_period_s']:>9.0f} {D['seq']:>5} "
            f"{D['laser_period_s']:>9.0f} {L['vg_fixed_v']:>+7.2f} "
            f"{pair_gap_s(L, D):>8.1f} {(L['wavelength_nm'] or 0):>7.0f} {L['date']:>10}"
        )
    print()


def plot_pair(chip: int, L: dict, D: dict, config: PlotConfig) -> Path:
    light = read_measurement_parquet(Path(L["parquet_path"]))
    dark = read_measurement_parquet(Path(D["parquet_path"]))

    t_L = light["t (s)"].to_numpy().astype(np.float64)
    i_L = light["I (A)"].to_numpy().astype(np.float64) * 1e6  # µA
    finite_L = np.isfinite(t_L) & np.isfinite(i_L)
    t_L, i_L = t_L[finite_L], i_L[finite_L]

    t_D_raw = dark["t (s)"].to_numpy().astype(np.float64)
    i_D = dark["I (A)"].to_numpy().astype(np.float64) * 1e6  # µA
    finite_D = np.isfinite(t_D_raw) & np.isfinite(i_D)
    t_D_raw, i_D = t_D_raw[finite_D], i_D[finite_D]

    offset = (D["start_dt"] - L["start_dt"]).total_seconds()
    t_D = t_D_raw + offset

    fig, ax = plt.subplots(figsize=config.figsize_timeseries)
    vg = L["vg_fixed_v"] or 0.0
    ax.plot(t_L, i_L, color=LIGHT_COLOR, linewidth=1.0,
            label=f"seq {L['seq']} light, {L['laser_period_s']:.0f} s")
    ax.plot(t_D, i_D, color=DARK_COLOR, linewidth=1.0,
            label=f"seq {D['seq']} dark, {D['laser_period_s']:.0f} s")

    if "VL (V)" in light.columns:
        vl = light["VL (V)"].to_numpy()
        on = np.where(vl > 0.1)[0]
        if on.size:
            ax.axvspan(
                float(t_L[on[0]]), float(t_L[on[-1]]),
                color="gold", alpha=config.light_window_alpha,
            )

    ax.axvline(offset, color="k", linewidth=0.5, linestyle=":", alpha=0.6)

    ax.set_xlabel(r"$t\ (\mathrm{s})$")
    ax.set_ylabel(r"$I\ (\mu\mathrm{A})$")
    wl = L["wavelength_nm"] or 0.0
    ax.set_title(
        f"Alisson{chip}  seq {L['seq']} → {D['seq']}  "
        f"$V_g$={vg:+g} V  $\\lambda$={wl:.0f} nm  ({L['date']})"
    )
    ax.legend()
    fig.tight_layout()

    filename = f"Alisson{chip}_It_concat_seq{L['seq']}_seq{D['seq']}"
    out = config.get_output_path(
        filename,
        chip_number=chip,
        procedure="It",
        metadata={"has_light": True},
        special_type="light_dark_concat",
        create_dirs=True,
    )
    fig.savefig(out, dpi=config.dpi, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    config = PlotConfig(chip_subdir_enabled=True, chip_folder_prefix="Encap")
    set_plot_style(config.theme)

    for chip in CHIPS:
        path = history_path(chip)
        if not path.exists():
            print(f"[warn] no enriched history for Encap{chip} ({path}) — skipping")
            continue
        history = pl.read_parquet(path)
        pairs = find_pairs(history)
        print_pair_table(chip, pairs)
        for L, D in pairs:
            out = plot_pair(chip, L, D, config)
            print(f"saved {out}")


if __name__ == "__main__":
    main()
