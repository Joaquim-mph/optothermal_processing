"""Per-measurement quality flags computed at staging time.

These flags are written to the manifest's `quality_flags` column (comma-
separated, same convention as `DerivedMetric.flags`). They surface broken
or non-functional acquisitions so downstream extractors can skip them
without re-reading the underlying parquet.

Currently only IVg is handled. Other procedures return an empty list and
can be added later as needed (Vt/It have different "flat" semantics —
intentionally flat time traces during a dark phase are not failures).
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import polars as pl


# ── Tunable thresholds ──────────────────────────────────────────────────

# Modulation = (max|I| - min|I|) / max|I|. Below this, the sweep shows no
# gating response — likely a metallic short, ungated channel, or a sweep
# that ran with no contact. Calibrated against the existing project data:
# the worst working device (chip 69, ~270 cm^2/V/s) sits at modulation
# ≈ 0.32, while chip 67's known-dead IVgs are at 0.07–0.09 — so 0.15 is a
# clean cut.
DEAD_MODULATION_THRESHOLD = 0.15

# Below this peak |I|, the device is below the typical noise floor of the
# sourcemeter setup — we treat that as an open circuit / detached channel.
OPEN_CIRCUIT_AMPS = 1.0e-12  # 1 pA

# Fraction of points within `SATURATION_TOL` (relative) of max|I|. A clean
# sweep gives ~ 1/N (one point exactly at the maximum); a fully clipped
# sweep stays at compliance for the whole range.
SATURATION_TOL = 0.01
STUCK_SATURATED_FRAC = 0.95


# ── Public API ──────────────────────────────────────────────────────────

def assess_measurement(proc: str, df: pl.DataFrame) -> list[str]:
    """Compute per-measurement quality flags. Returns [] for healthy data.

    Currently handles `IVg` only; other procedures return an empty list.
    """
    if proc == "IVg":
        return assess_ivg(df)
    return []


def assess_ivg(df: pl.DataFrame) -> list[str]:
    """Detect dead-sample IVg sweeps.

    Returns a (possibly empty) list of flag strings:

    - ``DEAD_OPEN_CIRCUIT``  — peak |I| below ~1 pA: no current flowing
      at all (open contacts / detached channel / shorted to ground).
    - ``DEAD_FLAT_IVG``      — current modulation across the sweep is
      below ``DEAD_MODULATION_THRESHOLD`` (default 15%): the device shows
      no field-effect response.
    - ``DEAD_STUCK_SATURATED`` — ≥``STUCK_SATURATED_FRAC`` of points are
      within ``SATURATION_TOL`` of max|I|: the sourcemeter is in
      compliance for almost the whole sweep.
    """
    if "I (A)" not in df.columns:
        return []
    i = df["I (A)"].to_numpy()
    if i.size == 0:
        return []

    flags: list[str] = []
    imax = float(np.nanmax(np.abs(i)))
    imin = float(np.nanmin(np.abs(i)))
    if not np.isfinite(imax):
        return []

    if imax < OPEN_CIRCUIT_AMPS:
        # Below noise floor — don't bother with the other checks; everything
        # else will also fire and the diagnosis is unambiguous.
        flags.append("DEAD_OPEN_CIRCUIT")
        return flags

    modulation = (imax - imin) / imax
    if modulation < DEAD_MODULATION_THRESHOLD:
        flags.append("DEAD_FLAT_IVG")

    if saturation_fraction(i) > STUCK_SATURATED_FRAC:
        flags.append("DEAD_STUCK_SATURATED")

    return flags


# ── Building blocks (reusable from derived extractors / scripts) ────────

def saturation_fraction(i: np.ndarray, tol: float = SATURATION_TOL) -> float:
    """Fraction of points within `tol` (relative) of the global max|I|.

    A clean sweep gives ~ 1/N (one point exactly at the maximum). A
    current-limited sweep clips, producing a plateau at the source-meter
    compliance — fractions of ~0.5+ flag it as unusable for peak-gm.
    """
    if i.size == 0:
        return 0.0
    imax = np.nanmax(np.abs(i))
    if imax == 0 or not np.isfinite(imax):
        return 0.0
    return float(np.mean(np.abs(np.abs(i) - imax) < tol * imax))


def join_flags(flags: Iterable[str]) -> str | None:
    """Comma-separate a list of flags; return None when empty."""
    out = [f for f in flags if f]
    return ",".join(out) if out else None


def has_dead_flag(quality_flags: str | None) -> bool:
    """True if `quality_flags` contains any DEAD_* marker."""
    if not quality_flags:
        return False
    return any(f.startswith("DEAD_") for f in quality_flags.split(","))
