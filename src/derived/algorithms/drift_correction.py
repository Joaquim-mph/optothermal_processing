"""
Drift baseline fitting for time-series (It/ITt) measurements.

Fits a slow-drift model (stretched exponential or linear) to a pre-illumination
window of an I(t) trace and evaluates it over the full time axis, so callers can
subtract it and work on the drift-corrected residual.

This is the shared implementation behind `delta_i_corrected`
(`CorrectedDeltaIExtractor`) and the drift-corrected 10-90 rise/fall times
(`ITSRiseFallExtractor(corrected=True)`), so both metrics reference the exact
same corrected trace.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from .linear_fit import fit_linear, linear_model
from .stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential,
)

MODELS = ("stretched_exponential", "linear")

MIN_FIT_POINTS = 10


def fit_drift_baseline(
    t: np.ndarray,
    i: np.ndarray,
    *,
    model: str = "stretched_exponential",
    fit_t_start: float = 20.0,
    fit_t_end: float = 60.0,
    drop_first_sample: bool = True,
) -> Dict[str, Any]:
    """
    Fit a drift baseline on [fit_t_start, fit_t_end] and evaluate it over all `t`.

    Parameters
    ----------
    t, i : np.ndarray
        Time (s) and current (A). Must be the same length. Non-finite samples
        are excluded from the fit window but `fit_full` is still returned with
        the full length of `t`.
    model : str
        'stretched_exponential' (default) or 'linear'.
    fit_t_start, fit_t_end : float
        Fit window bounds in seconds (inclusive).
    drop_first_sample : bool
        Exclude the first sample of the trace from the fit (acquisition
        artifact). Matches the historical `CorrectedDeltaIExtractor` behaviour.

    Returns
    -------
    dict with keys: 'fit_full' (ndarray, len(t)), 'fit_params', 'r_squared',
    'converged', 'model', 'fit_window_s', 'n_fit_points'.

    Raises
    ------
    ValueError
        If `model` is unknown, the arrays are mismatched, or fewer than
        `MIN_FIT_POINTS` usable samples fall inside the window.
    RuntimeError
        Propagated from the underlying fitters.
    """
    if model not in MODELS:
        raise ValueError(f"unknown model: {model!r}")

    t = np.asarray(t, dtype=np.float64)
    i = np.asarray(i, dtype=np.float64)
    if t.shape != i.shape:
        raise ValueError(f"t and i must have the same shape: {t.shape} vs {i.shape}")

    mask = (t >= fit_t_start) & (t <= fit_t_end) & np.isfinite(t) & np.isfinite(i)
    if mask.size and drop_first_sample:
        mask[0] = False  # always exclude first sample (acquisition artifact)

    n_fit_points = int(mask.sum())
    if n_fit_points < MIN_FIT_POINTS:
        raise ValueError(
            f"insufficient fit points in [{fit_t_start}, {fit_t_end}] s: "
            f"{n_fit_points} < {MIN_FIT_POINTS}"
        )

    if model == "stretched_exponential":
        fit = fit_stretched_exponential(t[mask], i[mask])
        fit_full = stretched_exponential(
            t, fit["baseline"], fit["amplitude"], fit["tau"], fit["beta"]
        )
        fit_params: Dict[str, float] = {
            "baseline": fit["baseline"],
            "amplitude": fit["amplitude"],
            "tau": fit["tau"],
            "beta": fit["beta"],
        }
        converged = bool(fit["converged"])
        r_squared = float(fit["r_squared"])
    else:
        fit = fit_linear(t[mask], i[mask])
        fit_full = linear_model(t, fit["slope"], fit["intercept"])
        fit_params = {"slope": fit["slope"], "intercept": fit["intercept"]}
        converged = True
        r_squared = float(fit["r_squared"])

    return {
        "fit_full": fit_full,
        "fit_params": fit_params,
        "r_squared": r_squared,
        "converged": converged,
        "model": model,
        "fit_window_s": [float(fit_t_start), float(fit_t_end)],
        "n_fit_points": n_fit_points,
    }


def drift_flags(
    r_squared: float,
    converged: bool,
    low_r_squared: float = 0.8,
) -> Optional[list]:
    """Standard quality flags for a drift fit (shared wording across metrics)."""
    flags = []
    if not converged:
        flags.append("FIT_DID_NOT_CONVERGE")
    if r_squared < low_r_squared:
        flags.append("LOW_R_SQUARED")
    return flags
