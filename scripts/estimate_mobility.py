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
import yaml
from rich.console import Console
from rich.table import Table

from src.core.utils import read_measurement_parquet
from src.plotting.plot_utils import (
    _savgol_derivative_corrected,
    segment_voltage_sweep,
)
from src.plotting.styles import set_plot_style

ENCAP_YAML = Path("config/encap_characteristics.yaml")
ENRICHED_HISTORY_DIR = Path("data/03_derived/chip_histories_enriched")
STAGE_HISTORY_DIR = Path("data/02_stage/chip_histories")
OUTPUT_DIR = Path("figs/mobility")
DEFAULT_CHIP_GROUP = "Alisson"

EPS_0 = 8.8541878128e-12  # F / m
console = Console()


# ── Config loading ─────────────────────────────────────────────────────────


@dataclass
class EncapConfig:
    chips: dict[int, dict]
    materials: dict[str, dict]
    aspect_ratio_LW: float
    aspect_ratio_LW_range: tuple[float, float]


def load_encap_config(path: Path = ENCAP_YAML) -> EncapConfig:
    with path.open("r") as f:
        data = yaml.safe_load(f) or {}
    chips = {int(k): (v or {}) for k, v in data.items() if isinstance(k, int)}
    materials = data.get("materials", {}) or {}
    geometry = data.get("geometry", {}) or {}
    LW = float(geometry.get("aspect_ratio_LW", 2.0))
    LW_range = tuple(geometry.get("aspect_ratio_LW_range", [LW, LW]))
    return EncapConfig(
        chips=chips, materials=materials,
        aspect_ratio_LW=LW, aspect_ratio_LW_range=LW_range,
    )


# ── Physics helpers ────────────────────────────────────────────────────────


def cox_per_area(
    t_top_nm: float, eps_top: float, t_bot_nm: float, eps_bot: float
) -> float:
    """Series capacitance per area, F/m^2."""
    t_top_m = t_top_nm * 1e-9
    t_bot_m = t_bot_nm * 1e-9
    return EPS_0 / (t_top_m / eps_top + t_bot_m / eps_bot)


def _cnp_vg(vg: np.ndarray, i: np.ndarray) -> float:
    """Coarse CNP estimate: Vg at min(|I|)."""
    return float(vg[int(np.argmin(np.abs(i)))])


def peak_gm_branches(
    vg: np.ndarray, i: np.ndarray
) -> tuple[float, float, np.ndarray, np.ndarray, float]:
    """Return (peak |gm| holes, peak |gm| electrons, vg_smooth, gm_smooth, cnp_vg).

    Uses Savgol derivative on the longest monotonic segment of the sweep to avoid
    the turnaround artifact at the sweep apex.
    """
    nan_out = (float("nan"), float("nan"), np.array([]), np.array([]), float("nan"))
    segs = segment_voltage_sweep(vg, i)
    if not segs:
        return nan_out
    vg_s, i_s, _ = max(segs, key=lambda s: len(s[0]))
    order = np.argsort(vg_s)
    vg_s = vg_s[order]
    i_s = i_s[order]

    gm = _savgol_derivative_corrected(vg_s, i_s)
    if gm.size == 0:
        return float("nan"), float("nan"), vg_s, gm, float("nan")

    cnp = _cnp_vg(vg_s, i_s)
    abs_gm = np.abs(gm)
    h_mask = vg_s < cnp
    e_mask = vg_s > cnp
    gm_h = float(abs_gm[h_mask].max()) if h_mask.any() else float("nan")
    gm_e = float(abs_gm[e_mask].max()) if e_mask.any() else float("nan")
    return gm_h, gm_e, vg_s, gm, cnp


def mobility_cm2(gm: float, cox: float, vds: float, LW: float) -> float:
    """mu = (L/W) * gm / (C_ox * |Vds|), returned in cm^2 / V s."""
    if not np.isfinite(gm) or cox <= 0 or vds == 0:
        return float("nan")
    mu_si = LW * gm / (cox * abs(vds))  # m^2 / V s
    return mu_si * 1e4


# ── Parameter-corner bounds ─────────────────────────────────────────────────
#
# mu = (L/W) * gm / (C_ox * |Vds|) is monotonic in each input:
#   - increasing in L/W
#   - decreasing in eps_top and eps_bot (through C_ox = eps_0 / (t_top/eps_top + t_bot/eps_bot))
# So the extreme values of mu within the parameter box are attained at corners:
#   mu_max -> max(L/W), min(eps_top), min(eps_bot)
#   mu_min -> min(L/W), max(eps_top), max(eps_bot)


def mobility_bounds(
    gm: float,
    t_top_nm: float, t_bot_nm: float,
    eps_top_range: tuple[float, float],
    eps_bot_range: tuple[float, float],
    LW_range: tuple[float, float],
    vds: float,
) -> tuple[float, float]:
    """Return (mu_min, mu_max) in cm^2/Vs over the parameter ranges."""
    if not np.isfinite(gm) or vds == 0:
        return float("nan"), float("nan")
    cox_min = cox_per_area(t_top_nm, eps_top_range[0], t_bot_nm, eps_bot_range[0])
    cox_max = cox_per_area(t_top_nm, eps_top_range[1], t_bot_nm, eps_bot_range[1])
    mu_max = LW_range[1] * gm / (cox_min * abs(vds)) * 1e4
    mu_min = LW_range[0] * gm / (cox_max * abs(vds)) * 1e4
    return float(mu_min), float(mu_max)


# ── History resolution ─────────────────────────────────────────────────────


def resolve_history(
    chip_number: int, group: str = DEFAULT_CHIP_GROUP
) -> Optional[Path]:
    for base in (ENRICHED_HISTORY_DIR, STAGE_HISTORY_DIR):
        p = base / f"{group}{chip_number}_history.parquet"
        if p.exists():
            return p
    return None


def first_dark_ivg(history_path: Path) -> Optional[dict]:
    df = pl.read_parquet(history_path)
    sub = df.filter((pl.col("proc") == "IVg") & (~pl.col("has_light"))).sort("seq")
    if sub.height == 0:
        return None
    return sub.row(0, named=True)


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
    gm: np.ndarray
    cnp: float
    seq: int


def compute_chip(chip: int, chip_cfg: dict, cfg: EncapConfig) -> Optional[ChipResult]:
    mat = chip_cfg.get("material")
    t_top = chip_cfg.get("top_hBN_nm")
    t_bot = chip_cfg.get("bottom_dielectric_nm")
    if mat is None or t_top is None or t_bot is None:
        console.print(f"[skip] chip {chip}: missing geometry in YAML")
        return None
    eps_top = cfg.materials.get("hBN", {}).get("epsilon_r")
    eps_bot = cfg.materials.get(mat, {}).get("epsilon_r")
    if eps_top is None or eps_bot is None:
        console.print(f"[skip] chip {chip}: missing epsilon_r for hBN/{mat}")
        return None

    hist = resolve_history(chip)
    if hist is None:
        console.print(f"[skip] chip {chip}: no history parquet")
        return None
    row = first_dark_ivg(hist)
    if row is None:
        console.print(f"[skip] chip {chip}: no dark IVg")
        return None
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

    gm_h, gm_e, vg_s, gm_arr, cnp = peak_gm_branches(vg, i)
    cox = cox_per_area(t_top, eps_top, t_bot, eps_bot)
    LW = float(chip_cfg.get("aspect_ratio_LW", cfg.aspect_ratio_LW))
    mu_h = mobility_cm2(gm_h, cox, vds, LW)
    mu_e = mobility_cm2(gm_e, cox, vds, LW)

    # Parameter-corner bounds on mu and Cox over the YAML-declared ranges.
    eps_top_range = tuple(
        cfg.materials.get("hBN", {}).get("epsilon_r_range", [eps_top, eps_top])
    )
    eps_bot_range = tuple(
        cfg.materials.get(mat, {}).get("epsilon_r_range", [eps_bot, eps_bot])
    )
    LW_range = cfg.aspect_ratio_LW_range
    if "aspect_ratio_LW" in chip_cfg and "aspect_ratio_LW_range" not in chip_cfg:
        LW_range = (float(chip_cfg["aspect_ratio_LW"]),) * 2  # chip override pins L/W
    mu_h_lo, mu_h_hi = mobility_bounds(
        gm_h, float(t_top), float(t_bot),
        eps_top_range, eps_bot_range, LW_range, float(vds),
    )
    mu_e_lo, mu_e_hi = mobility_bounds(
        gm_e, float(t_top), float(t_bot),
        eps_top_range, eps_bot_range, LW_range, float(vds),
    )
    cox_lo = cox_per_area(float(t_top), eps_top_range[0], float(t_bot), eps_bot_range[0])
    cox_hi = cox_per_area(float(t_top), eps_top_range[1], float(t_bot), eps_bot_range[1])

    return ChipResult(
        chip=chip,
        material=mat,
        t_top=float(t_top),
        t_bot=float(t_bot),
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


def make_per_chip_gm_plots(results: list[ChipResult], out_dir: Path) -> None:
    """One small figure per chip showing |gm|(Vg) with peak markers."""
    set_plot_style()
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
        }
    )
    color_map = {"hBN": "tab:blue", "biotite": "tab:orange"}
    for r in sorted(results, key=lambda r: r.chip):
        if r.gm.size == 0:
            continue
        fig, ax = plt.subplots(figsize=(6.0, 4.2))
        c = color_map.get(r.material, "k")
        abs_gm_uS = np.abs(r.gm) * 1e6
        ax.plot(r.vg, abs_gm_uS, color=c, lw=1.4)
        h_mask = r.vg < r.cnp
        e_mask = r.vg > r.cnp
        ax.axvline(r.cnp, color="0.5", lw=0.7, ls=":", label=f"CNP ≈ {r.cnp:.2f} V")
        if h_mask.any():
            idx_h = np.argmax(abs_gm_uS[h_mask])
            vg_h = r.vg[h_mask][idx_h]
            gm_h = abs_gm_uS[h_mask][idx_h]
            ax.plot(
                vg_h,
                gm_h,
                "v",
                color=c,
                ms=8,
                label=rf"holes: $\mu$={r.mu_h:,.0f} [{r.mu_h_lo:,.0f}–{r.mu_h_hi:,.0f}] cm$^2$/Vs",
            )
        if e_mask.any():
            idx_e = np.argmax(abs_gm_uS[e_mask])
            vg_e = r.vg[e_mask][idx_e]
            gm_e = abs_gm_uS[e_mask][idx_e]
            ax.plot(
                vg_e,
                gm_e,
                "^",
                color=c,
                ms=8,
                label=rf"electrons: $\mu$={r.mu_e:,.0f} [{r.mu_e_lo:,.0f}–{r.mu_e_hi:,.0f}] cm$^2$/Vs",
            )
        ax.set_xlabel(r"$V_g$ (V)")
        ax.set_ylabel(r"$|g_m|$ (µS)")
        cox_nFcm2 = r.cox * 1e5
        cox_lo_nFcm2 = r.cox_lo * 1e5
        cox_hi_nFcm2 = r.cox_hi * 1e5
        ax.set_title(
            f"chip {r.chip} ({r.material} bottom, t_top={r.t_top:.0f} nm, "
            f"t_bot={r.t_bot:.0f} nm)\n"
            f"C_ox={cox_nFcm2:.1f} [{cox_lo_nFcm2:.1f}–{cox_hi_nFcm2:.1f}] nF/cm², "
            f"Vds={r.vds:g} V, seq {r.seq}",
            fontsize=9,
        )
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / f"gm_chip{r.chip}.png", dpi=200)
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
    for chip, chip_cfg in sorted(cfg.chips.items()):
        r = compute_chip(chip, chip_cfg, cfg)
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
    make_per_chip_gm_plots(results, per_chip_dir)
    console.print(f"\nWrote {csv_path}")
    console.print(f"Wrote {fig_path}")
    console.print(f"Wrote {len(results)} per-chip gm plots to {per_chip_dir}/")


if __name__ == "__main__":
    main()
