"""Field-effect mobility algorithm primitives.

Pure functions shared by `src/derived/extractors/mobility_extractor.py` and
`scripts/estimate_mobility.py`. See `docs/algs/MOBILITY_ESTIMATOR_GUIDE.md`
for derivations.

    mu_FE = (L/W) * |gm|_peak / (C_ox * |Vds|)
    C_ox  = eps_0 / (t_top/eps_top + t_bot/eps_bot)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from src.plotting.shared.plot_utils import (
    _savgol_derivative_corrected,
    segment_voltage_sweep,
)


EPS_0 = 8.8541878128e-12  # F / m


# ── Capacitance & mobility ──────────────────────────────────────────────

def cox_per_area(
    t_top_nm: float, eps_top: float, t_bot_nm: float, eps_bot: float
) -> float:
    """Series-capacitance per area of top hBN + bottom dielectric, in F/m^2."""
    t_top_m = t_top_nm * 1e-9
    t_bot_m = t_bot_nm * 1e-9
    return EPS_0 / (t_top_m / eps_top + t_bot_m / eps_bot)


def mobility_cm2(gm: float, cox: float, vds: float, LW: float) -> float:
    """μ = (L/W) · |gm| / (C_ox · |Vds|), returned in cm^2 / V s."""
    if not np.isfinite(gm) or cox <= 0 or vds == 0:
        return float("nan")
    return float(LW * abs(gm) / (cox * abs(vds)) * 1e4)


def mobility_bounds(
    gm: float,
    t_top_nm: float, t_bot_nm: float,
    eps_top_range: tuple[float, float],
    eps_bot_range: tuple[float, float],
    LW_range: tuple[float, float],
    vds: float,
) -> tuple[float, float]:
    """Exact (μ_min, μ_max) over the parameter box (cm^2/Vs).

    μ is monotonic in each input (linear in L/W, decreasing in eps_top/eps_bot
    via C_ox), so the extremes are at the box corners and we evaluate them
    analytically — no Monte Carlo needed.
    """
    if not np.isfinite(gm) or vds == 0:
        return float("nan"), float("nan")
    cox_min = cox_per_area(t_top_nm, eps_top_range[0], t_bot_nm, eps_bot_range[0])
    cox_max = cox_per_area(t_top_nm, eps_top_range[1], t_bot_nm, eps_bot_range[1])
    mu_max = LW_range[1] * abs(gm) / (cox_min * abs(vds)) * 1e4
    mu_min = LW_range[0] * abs(gm) / (cox_max * abs(vds)) * 1e4
    return float(mu_min), float(mu_max)


# ── Transconductance & saturation ───────────────────────────────────────

def _cnp_vg(vg: np.ndarray, i: np.ndarray) -> float:
    """Coarse charge-neutrality point: Vg at argmin(|I|)."""
    return float(vg[int(np.argmin(np.abs(i)))])


_EMPTY_GM_RESULT = (
    float("nan"), float("nan"),
    float("nan"), float("nan"),
    np.array([]), np.array([]), np.array([]),
    float("nan"),
)


def peak_gm_on_leg(
    vg_leg: np.ndarray, i_leg: np.ndarray
) -> tuple[float, float, float, float, np.ndarray, np.ndarray, np.ndarray, float]:
    """Signed peak gm on each branch of a single monotonic Vg leg.

    Same return tuple as `peak_gm_signed`, but the caller is responsible
    for having already isolated one monotonic traversal (forward
    V_min→V_max or backward V_max→V_min). No internal segmentation is
    performed; the leg is sorted ascending in Vg, gm = dI/dVg is computed
    via the Sav-Gol derivative, the coarse CNP (argmin|I|) splits hole
    (Vg < CNP) and electron (Vg > CNP) branches, and the signed peak gm
    on each branch is returned.
    """
    if vg_leg.size < 3:
        return _EMPTY_GM_RESULT

    order = np.argsort(vg_leg)
    vg_s = vg_leg[order]
    i_s = i_leg[order]

    gm = _savgol_derivative_corrected(vg_s, i_s)
    if gm.size == 0:
        return (
            float("nan"), float("nan"),
            float("nan"), float("nan"),
            vg_s, i_s, gm, float("nan"),
        )

    cnp = _cnp_vg(vg_s, i_s)
    abs_gm = np.abs(gm)
    h_mask = vg_s < cnp
    e_mask = vg_s > cnp

    if h_mask.any():
        idx_h = int(np.argmax(abs_gm[h_mask]))
        gm_h = float(gm[h_mask][idx_h])
        vg_h = float(vg_s[h_mask][idx_h])
    else:
        gm_h, vg_h = float("nan"), float("nan")
    if e_mask.any():
        idx_e = int(np.argmax(abs_gm[e_mask]))
        gm_e = float(gm[e_mask][idx_e])
        vg_e = float(vg_s[e_mask][idx_e])
    else:
        gm_e, vg_e = float("nan"), float("nan")

    return gm_h, gm_e, vg_h, vg_e, vg_s, i_s, gm, cnp


def peak_gm_signed(
    vg: np.ndarray, i: np.ndarray
) -> tuple[float, float, float, float, np.ndarray, np.ndarray, np.ndarray, float]:
    """Compute signed peak gm on each branch from a full IVg sweep.

    Picks the longest monotonic segment via `segment_voltage_sweep` and
    delegates to `peak_gm_on_leg`. Returns NaN-filled tuple if no
    segment can be isolated. Preserved for backward compatibility with
    `scripts/estimate_mobility.py` and any other external callers.
    """
    segs = segment_voltage_sweep(vg, i)
    if not segs:
        return _EMPTY_GM_RESULT
    vg_s, i_s, _ = max(segs, key=lambda s: len(s[0]))
    return peak_gm_on_leg(vg_s, i_s)


def saturation_fraction(i: np.ndarray, tol: float = 0.01) -> float:
    """Fraction of points within `tol` (relative) of the global max|I|.

    A clean sweep gives ~ 1/N (one or two points exactly at the maximum).
    A current-limited sweep clips, producing a plateau at the source-meter
    compliance — fractions of ~0.5+ flag it as unusable for peak-gm.
    """
    if i.size == 0:
        return 0.0
    imax = np.nanmax(np.abs(i))
    if imax == 0 or not np.isfinite(imax):
        return 0.0
    return float(np.mean(np.abs(np.abs(i) - imax) < tol * imax))


# ── Encap-characteristics loader ────────────────────────────────────────

@dataclass
class EncapConfig:
    chips: dict[int, dict]
    materials: dict[str, dict]
    aspect_ratio_LW: float
    aspect_ratio_LW_range: tuple[float, float]


def _resolve_central_range(
    central: Optional[float],
    rng: Optional[list | tuple],
) -> tuple[float, tuple[float, float]]:
    """Reconcile a scalar central and a (lo, hi) range.

    Range, if given, is authoritative — central becomes its midpoint so the
    invariant `lo <= central <= hi` always holds. If only the central is
    given, the range collapses to (central, central). At least one must be
    provided; the caller is responsible for handling None.
    """
    if rng is not None:
        lo, hi = float(rng[0]), float(rng[1])
        return 0.5 * (lo + hi), (lo, hi)
    c = float(central)
    return c, (c, c)


def load_encap_config(
    path: Path = Path("config/encap_characteristics.yaml"),
) -> EncapConfig:
    """Parse the encap-characteristics YAML.

    Top-level integer keys become per-chip entries; `materials:` and
    `geometry:` blocks are pulled out separately. Returns an empty/default
    config if the file is missing so callers don't need to special-case.
    """
    if not path.exists():
        return EncapConfig(chips={}, materials={}, aspect_ratio_LW=2.0,
                           aspect_ratio_LW_range=(2.0, 2.0))
    with path.open("r") as f:
        data = yaml.safe_load(f) or {}
    chips = {int(k): (v or {}) for k, v in data.items() if isinstance(k, int)}
    materials = data.get("materials", {}) or {}
    geometry = data.get("geometry", {}) or {}
    LW, LW_range = _resolve_central_range(
        geometry.get("aspect_ratio_LW", 2.0),
        geometry.get("aspect_ratio_LW_range"),
    )
    return EncapConfig(
        chips=chips, materials=materials,
        aspect_ratio_LW=LW, aspect_ratio_LW_range=LW_range,
    )


def chip_geometry(
    cfg: EncapConfig, chip_number: int
) -> Optional[dict]:
    """Resolve geometry + material properties for a single chip.

    Returns None if the chip is missing from the YAML or lacks the
    required `material`, `top_hBN_nm`, or `bottom_dielectric_nm` fields.
    The dict combines per-chip values with the YAML-level material ε_r
    ranges and global L/W range (per-chip override of `aspect_ratio_LW`
    pins L/W to a single value, removing it from the parameter box).
    """
    chip_cfg = cfg.chips.get(int(chip_number))
    if not chip_cfg:
        return None
    mat = chip_cfg.get("material")
    t_top = chip_cfg.get("top_hBN_nm")
    t_bot = chip_cfg.get("bottom_dielectric_nm")
    if mat is None or t_top is None or t_bot is None:
        return None
    hbn = cfg.materials.get("hBN", {})
    bot = cfg.materials.get(mat, {})
    if hbn.get("epsilon_r") is None and hbn.get("epsilon_r_range") is None:
        return None
    if bot.get("epsilon_r") is None and bot.get("epsilon_r_range") is None:
        return None
    eps_top, eps_top_range = _resolve_central_range(
        hbn.get("epsilon_r"), hbn.get("epsilon_r_range")
    )
    eps_bot, eps_bot_range = _resolve_central_range(
        bot.get("epsilon_r"), bot.get("epsilon_r_range")
    )
    if "aspect_ratio_LW" in chip_cfg or "aspect_ratio_LW_range" in chip_cfg:
        LW, LW_range = _resolve_central_range(
            chip_cfg.get("aspect_ratio_LW"),
            chip_cfg.get("aspect_ratio_LW_range"),
        )
    else:
        LW, LW_range = cfg.aspect_ratio_LW, cfg.aspect_ratio_LW_range
    return {
        "bottom_material": mat,
        "top_hBN_nm": float(t_top),
        "bottom_dielectric_nm": float(t_bot),
        "eps_top": float(eps_top),
        "eps_bot": float(eps_bot),
        "eps_top_range": tuple(eps_top_range),
        "eps_bot_range": tuple(eps_bot_range),
        "LW": LW,
        "LW_range": tuple(LW_range),
    }
