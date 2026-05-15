"""Rough graphene field-effect mobility estimates per encapsulated device.

For every chip in `config/encap_characteristics.yaml`:
  1. Compute gate-stack capacitance per area
        C_ox = eps_0 / (t_top/eps_top + t_bot/eps_bot)
  2. Load the first dark IVg sweep from the chip history.
  3. Compute |gm| = |dI/dVg| (Savitzky-Golay, matches src/plotting/transconductance.py).
  4. Take peak |gm| on hole branch (Vg < CNP) and electron branch (Vg > CNP).
  5. mu_FE = (L/W) * gm_peak / (C_ox * |Vds|)  [m^2 / V s]  -> cm^2 / V s.

Output: a Rich table, a CSV, and a 2-panel figure (mu bars + gm overlays).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from rich.console import Console
from rich.table import Table

from src.core.utils import read_measurement_parquet
from src.derived.algorithms.mobility import (
    EncapConfig,
    chip_geometry,
    cox_per_area,
    load_encap_config,
    mobility_bounds,
    mobility_cm2,
    peak_gm_signed,
    saturation_fraction,
)
from src.plotting.shared.styles import set_plot_style

ENRICHED_HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
STAGE_HISTORY_DIR = Path("data/02_stage/chip_histories")
OUTPUT_DIR = Path("figs/mobility")
DEFAULT_CHIP_GROUP = "Alisson"

# Saturation threshold for picking the first non-clipped dark IVg sweep.
# (The metric extractor uses a separate, configurable threshold; here we just
# want a clean representative sweep for the figures.)
SATURATION_FRAC_THRESHOLD = 0.10

console = Console()


def resolve_history(chip_number: int, group: str = DEFAULT_CHIP_GROUP) -> Optional[Path]:
    for base in (ENRICHED_HISTORY_DIR, STAGE_HISTORY_DIR):
        p = base / f"{group}{chip_number}_history.parquet"
        if p.exists():
            return p
    return None


def first_unsaturated_dark_ivg(history_path: Path) -> Optional[dict]:
    """First dark IVg whose current trace is not clipped by the source-meter limit.

    Falls back to the very first dark IVg if no sweep meets the threshold.
    """
    df = pl.read_parquet(history_path)
    sub = df.filter((pl.col("proc") == "IVg") & (~pl.col("has_light"))).sort("seq")
    if sub.height == 0:
        return None
    fallback = sub.row(0, named=True)
    for row in sub.iter_rows(named=True):
        pq = row.get("parquet_path")
        if not pq or not Path(pq).exists():
            continue
        m = read_measurement_parquet(pq)
        sat = saturation_fraction(m["I (A)"].to_numpy())
        if sat < SATURATION_FRAC_THRESHOLD:
            row["_saturation_fraction"] = sat
            return row
    fallback["_saturation_fraction"] = saturation_fraction(
        read_measurement_parquet(fallback["parquet_path"])["I (A)"].to_numpy()
    )
    return fallback


# ── Per-chip computation ───────────────────────────────────────────────────


@dataclass
class ChipResult:
    chip: int
    material: str  # bottom dielectric
    t_top: float
    t_bot: float
    cox: float  # F/m^2
    vds: float
    gm_h: float  # S
    gm_e: float  # S
    mu_h: float  # cm^2/Vs   (central estimate, also median of MC samples)
    mu_e: float
    # Extreme values over the parameter box (L/W, eps_top, eps_bot ranges):
    mu_h_lo: float   # min mu_h within parameter ranges (cm^2/Vs)
    mu_h_hi: float   # max mu_h
    mu_e_lo: float
    mu_e_hi: float
    cox_lo: float    # F/m^2; min Cox (eps_top_min, eps_bot_min)
    cox_hi: float    # F/m^2; max Cox
    vg: np.ndarray
    i: np.ndarray
    gm: np.ndarray
    cnp: float
    seq: int


def compute_chip(chip: int, cfg: EncapConfig) -> Optional[ChipResult]:
    geom = chip_geometry(cfg, chip)
    if geom is None:
        console.print(f"[skip] chip {chip}: missing geometry/material in YAML")
        return None

    hist = resolve_history(chip)
    if hist is None:
        console.print(f"[skip] chip {chip}: no history parquet")
        return None
    row = first_unsaturated_dark_ivg(hist)
    if row is None:
        console.print(f"[skip] chip {chip}: no dark IVg")
        return None
    sat = row.get("_saturation_fraction", 0.0) or 0.0
    if sat >= SATURATION_FRAC_THRESHOLD:
        console.print(
            f"[warn] chip {chip}: all dark IVg sweeps are current-limited "
            f"(best is seq {row.get('seq')} with {sat*100:.0f}% saturated points); "
            "mobility estimate will be a lower bound."
        )
    elif int(row.get("seq", 1)) != 1:
        console.print(
            f"[info] chip {chip}: skipped seq 1 (clipped); using seq {row.get('seq')}"
        )
    vds = row.get("vds_v")
    if vds is None or not np.isfinite(vds) or vds == 0:
        console.print(f"[skip] chip {chip}: missing/zero Vds (seq {row.get('seq')})")
        return None

    pq = row.get("parquet_path")
    if not pq or not Path(pq).exists():
        console.print(f"[skip] chip {chip}: parquet not found ({pq})")
        return None
    m = read_measurement_parquet(pq)
    vg = m["Vg (V)"].to_numpy()
    i = m["I (A)"].to_numpy()

    gm_h_s, gm_e_s, _vgh, _vge, vg_s, i_s, gm_arr, cnp = peak_gm_signed(vg, i)
    gm_h = abs(gm_h_s)
    gm_e = abs(gm_e_s)
    cox = cox_per_area(
        geom["top_hBN_nm"], geom["eps_top"],
        geom["bottom_dielectric_nm"], geom["eps_bot"],
    )
    mu_h = mobility_cm2(gm_h, cox, vds, geom["LW"])
    mu_e = mobility_cm2(gm_e, cox, vds, geom["LW"])

    mu_h_lo, mu_h_hi = mobility_bounds(
        gm_h, geom["top_hBN_nm"], geom["bottom_dielectric_nm"],
        geom["eps_top_range"], geom["eps_bot_range"], geom["LW_range"], float(vds),
    )
    mu_e_lo, mu_e_hi = mobility_bounds(
        gm_e, geom["top_hBN_nm"], geom["bottom_dielectric_nm"],
        geom["eps_top_range"], geom["eps_bot_range"], geom["LW_range"], float(vds),
    )
    cox_lo = cox_per_area(
        geom["top_hBN_nm"], geom["eps_top_range"][0],
        geom["bottom_dielectric_nm"], geom["eps_bot_range"][0],
    )
    cox_hi = cox_per_area(
        geom["top_hBN_nm"], geom["eps_top_range"][1],
        geom["bottom_dielectric_nm"], geom["eps_bot_range"][1],
    )

    return ChipResult(
        chip=chip,
        material=geom["bottom_material"],
        t_top=geom["top_hBN_nm"],
        t_bot=geom["bottom_dielectric_nm"],
        cox=cox,
        vds=float(vds),
        gm_h=gm_h,
        gm_e=gm_e,
        mu_h=mu_h,
        mu_e=mu_e,
        mu_h_lo=float(mu_h_lo), mu_h_hi=float(mu_h_hi),
        mu_e_lo=float(mu_e_lo), mu_e_hi=float(mu_e_hi),
        cox_lo=float(cox_lo), cox_hi=float(cox_hi),
        vg=vg_s,
        i=i_s,
        gm=gm_arr,
        cnp=cnp,
        seq=int(row.get("seq", -1)),
    )


# ── Reporting ──────────────────────────────────────────────────────────────


def print_table(results: list[ChipResult]) -> None:
    t = Table(title="Rough graphene mobility estimates (first dark IVg per chip)")
    t.add_column("chip", justify="right")
    t.add_column("bot mat")
    t.add_column("t_top [nm]", justify="right")
    t.add_column("t_bot [nm]", justify="right")
    t.add_column("C_ox [nF/cm²]", justify="right")
    t.add_column("Vds [V]", justify="right")
    t.add_column("|gm|_h [µS]", justify="right")
    t.add_column("|gm|_e [µS]", justify="right")
    t.add_column("µ_h [min–max]", justify="right")
    t.add_column("µ_e [min–max]", justify="right")
    t.add_column("flag")
    for r in sorted(results, key=lambda r: r.chip):
        cox_nFcm2 = r.cox * 1e5
        flag = ""
        worst = np.nanmax([r.mu_h, r.mu_e])
        if not np.isfinite(worst) or worst < 10 or worst > 1e5:
            flag = "!"
        t.add_row(
            str(r.chip),
            r.material,
            f"{r.t_top:.0f}",
            f"{r.t_bot:.0f}",
            f"{cox_nFcm2:.1f}",
            f"{r.vds:g}",
            f"{r.gm_h * 1e6:.2f}",
            f"{r.gm_e * 1e6:.2f}",
            f"{r.mu_h:,.0f} [{r.mu_h_lo:,.0f}–{r.mu_h_hi:,.0f}]",
            f"{r.mu_e:,.0f} [{r.mu_e_lo:,.0f}–{r.mu_e_hi:,.0f}]",
            flag,
        )
    console.print(t)


def save_csv(results: list[ChipResult], path: Path) -> None:
    rows = [
        {
            "chip": r.chip,
            "bottom_material": r.material,
            "top_hBN_nm": r.t_top,
            "bottom_dielectric_nm": r.t_bot,
            "cox_F_per_m2": r.cox,
            "cox_nF_per_cm2": r.cox * 1e5,  # F/m^2 * (1 m^2 / 1e4 cm^2) * (1e9 nF / F)
            "vds_v": r.vds,
            "peak_gm_hole_S": r.gm_h,
            "peak_gm_electron_S": r.gm_e,
            "mu_hole_cm2_per_Vs": r.mu_h,
            "mu_hole_min": r.mu_h_lo,
            "mu_hole_max": r.mu_h_hi,
            "mu_electron_cm2_per_Vs": r.mu_e,
            "mu_electron_min": r.mu_e_lo,
            "mu_electron_max": r.mu_e_hi,
            "cox_min_F_per_m2": r.cox_lo,
            "cox_max_F_per_m2": r.cox_hi,
            "seq": r.seq,
        }
        for r in sorted(results, key=lambda r: r.chip)
    ]
    pl.DataFrame(rows).write_csv(path)


def make_per_chip_ivg_gm_plots(results: list[ChipResult], out_dir: Path) -> None:
    """One figure per chip: IVg (top) + signed gm (bottom), shared Vg axis."""
    set_plot_style()
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8,
        }
    )
    color_map = {"hBN": "tab:blue", "biotite": "tab:orange"}
    for r in sorted(results, key=lambda r: r.chip):
        if r.gm.size == 0 or r.i.size == 0:
            continue
        c = color_map.get(r.material, "k")
        fig, (ax_iv, ax_gm) = plt.subplots(
            2, 1, figsize=(6.0, 6.0), sharex=True,
            gridspec_kw={"height_ratios": [1.0, 1.0]},
        )

        i_uA = r.i * 1e6
        gm_uS = r.gm * 1e6  # signed
        ax_iv.plot(r.vg, i_uA, color=c, lw=1.4)
        ax_iv.axvline(r.cnp, color="0.5", lw=0.7, ls=":")
        ax_iv.set_ylabel(r"$\rm{I_{ds}\ (\mu A)}$")
        cox_nFcm2 = r.cox * 1e5
        cox_lo_nFcm2 = r.cox_lo * 1e5
        cox_hi_nFcm2 = r.cox_hi * 1e5
        ax_iv.set_title(
            f"chip {r.chip} ({r.material} bottom, t_top={r.t_top:.0f} nm, "
            f"t_bot={r.t_bot:.0f} nm) — seq {r.seq}\n"
            rf"$\rm{{C_{{ox}}}}$={cox_nFcm2:.1f} [{cox_lo_nFcm2:.1f}–{cox_hi_nFcm2:.1f}]"
            rf" nF/cm², $\rm{{V_{{ds}}}}$={r.vds:g} V"
        )

        # Signed gm
        ax_gm.plot(r.vg, gm_uS, color=c, lw=1.4)
        ax_gm.axhline(0.0, color="0.6", lw=0.6)
        ax_gm.axvline(r.cnp, color="0.5", lw=0.7, ls=":",
                      label=fr"CNP $\approx$ {r.cnp:.2f} V")
        h_mask = r.vg < r.cnp
        e_mask = r.vg > r.cnp
        abs_gm_uS = np.abs(gm_uS)
        if h_mask.any():
            idx_h = np.argmax(abs_gm_uS[h_mask])
            ax_gm.plot(
                r.vg[h_mask][idx_h], gm_uS[h_mask][idx_h],
                "v", color=c, ms=8,
                label=(rf"holes: $\mu$={r.mu_h:,.0f} "
                       rf"[{r.mu_h_lo:,.0f}–{r.mu_h_hi:,.0f}] "
                       rf"cm$^2$ V$^{{-1}}$ s$^{{-1}}$"),
            )
        if e_mask.any():
            idx_e = np.argmax(abs_gm_uS[e_mask])
            ax_gm.plot(
                r.vg[e_mask][idx_e], gm_uS[e_mask][idx_e],
                "^", color=c, ms=8,
                label=(rf"electrons: $\mu$={r.mu_e:,.0f} "
                       rf"[{r.mu_e_lo:,.0f}–{r.mu_e_hi:,.0f}] "
                       rf"cm$^2$ V$^{{-1}}$ s$^{{-1}}$"),
            )
        ax_gm.set_xlabel(r"$\rm{V_g\ (V)}$")
        ax_gm.set_ylabel(r"$\rm{g_m\ (\mu S)}$")
        ax_gm.legend(loc="best")

        fig.tight_layout()
        fig.savefig(out_dir / f"ivg_gm_chip{r.chip}.png", dpi=200)
        plt.close(fig)


def make_plot(results: list[ChipResult], path: Path) -> None:
    set_plot_style()
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8,
            "figure.figsize": (13, 5.2),
        }
    )
    fig, (ax_mu, ax_gm) = plt.subplots(1, 2, figsize=(13, 5.2))

    # ── Left: mu bars per chip ──
    results_sorted = sorted(results, key=lambda r: (r.material, r.chip))
    chips = [str(r.chip) for r in results_sorted]
    mu_h = [r.mu_h for r in results_sorted]
    mu_e = [r.mu_e for r in results_sorted]
    mats = [r.material for r in results_sorted]
    x = np.arange(len(chips))
    w = 0.4
    color_map = {"hBN": "tab:blue", "biotite": "tab:orange"}
    edge = [color_map.get(m, "k") for m in mats]
    err_h = np.array([
        [r.mu_h - r.mu_h_lo for r in results_sorted],
        [r.mu_h_hi - r.mu_h for r in results_sorted],
    ])
    err_e = np.array([
        [r.mu_e - r.mu_e_lo for r in results_sorted],
        [r.mu_e_hi - r.mu_e for r in results_sorted],
    ])
    ax_mu.bar(
        x - w / 2, mu_h, w,
        label="µ_h (holes)",
        color="white", edgecolor=edge, hatch="//", linewidth=1.4,
        yerr=err_h, ecolor="0.3", capsize=2, error_kw={"lw": 0.8},
    )
    ax_mu.bar(
        x + w / 2, mu_e, w,
        label="µ_e (electrons)", color=edge, alpha=0.85,
        yerr=err_e, ecolor="0.3", capsize=2, error_kw={"lw": 0.8},
    )
    ax_mu.set_xticks(x)
    ax_mu.set_xticklabels(chips, rotation=0)
    ax_mu.set_xlabel("chip")
    ax_mu.set_ylabel(r"$\mu_{FE}$ (cm$^2$ V$^{-1}$ s$^{-1}$)")
    ax_mu.set_title("Peak field-effect mobility (bars: central; whiskers: min–max over param ranges)")
    # Material legend (color) + branch legend (hatch/solid)
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor="tab:blue", label="bottom = hBN"),
        Patch(facecolor="tab:orange", label="bottom = biotite"),
        Patch(facecolor="white", edgecolor="0.3", hatch="//", label="holes"),
        Patch(facecolor="0.3", label="electrons"),
    ]
    ax_mu.legend(handles=handles, fontsize=8, loc="upper left")

    # ── Right: |gm|(Vg) overlay ──
    for r in results_sorted:
        if r.gm.size == 0:
            continue
        ax_gm.plot(
            r.vg,
            np.abs(r.gm) * 1e6,
            color=color_map.get(r.material, "k"),
            alpha=0.75,
            lw=1.1,
            label=f"{r.chip} ({r.material})",
        )
    ax_gm.set_xlabel(r"$V_g$ (V)")
    ax_gm.set_ylabel(r"$|g_m|$ (µS)")
    ax_gm.set_title("Transconductance traces (first dark IVg)")
    ax_gm.legend(fontsize=7, ncol=2, loc="best")

    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    cfg = load_encap_config()
    console.print(f"Loaded {len(cfg.chips)} chips; L/W default = {cfg.aspect_ratio_LW}")
    results: list[ChipResult] = []
    for chip in sorted(cfg.chips):
        r = compute_chip(chip, cfg)
        if r is not None:
            results.append(r)
    if not results:
        console.print("[red]No chips produced a mobility estimate.[/red]")
        return

    print_table(results)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "mobility_estimates.csv"
    fig_path = OUTPUT_DIR / "mobility_estimates.png"
    save_csv(results, csv_path)
    make_plot(results, fig_path)
    per_chip_dir = OUTPUT_DIR / "per_chip"
    per_chip_dir.mkdir(parents=True, exist_ok=True)
    make_per_chip_ivg_gm_plots(results, per_chip_dir)
    console.print(f"\nWrote {csv_path}")
    console.print(f"Wrote {fig_path}")
    console.print(f"Wrote {len(results)} per-chip IVg+gm plots to {per_chip_dir}/")


if __name__ == "__main__":
    main()
