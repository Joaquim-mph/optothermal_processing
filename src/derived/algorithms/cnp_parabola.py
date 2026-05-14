"""Per-direction CNP extraction helpers.

Given a gate-voltage sweep of the shape

    0 → V_start → V_end → V_start → 0

the data contains two **complete** full-range traversals — one forward
(V_start → V_end) and one backward (V_end → V_start) — plus partial
half-legs at the ends. This module:

1. Splits the sweep into monotonic legs by direction sign-change.
2. Keeps only the legs whose Vg span covers ≥ `full_range_frac` of the
   sweep's total Vg range (default 95%) — these are the full traversals.
3. For each kept leg, locates argmin(|signal|) and fits a quadratic to a
   small window around it. The fit is on the raw signal (I for IVg, V
   for VVg) — no resistance is computed.

Used by `CNPExtractor` (`src/derived/extractors/cnp_extractor.py`).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


def split_full_range_legs(
    vg: np.ndarray,
    signal: np.ndarray,
    full_range_frac: float = 0.95,
) -> List[Tuple[np.ndarray, np.ndarray, str]]:
    """Return monotonic legs spanning ≥ `full_range_frac` of the Vg range.

    Parameters
    ----------
    vg, signal
        1-D arrays of equal length (Vg and the swept signal, e.g. I).
    full_range_frac
        Minimum fraction of the total Vg span a leg must cover to count
        as a full-range traversal.

    Returns
    -------
    list of (vg_leg, signal_leg, direction)
        `direction` is "forward" (Vg increasing) or "backward" (decreasing).
        Empty list if no leg covers the threshold.
    """
    if vg.size < 3:
        return []

    total_range = float(np.max(vg) - np.min(vg))
    if total_range <= 0.0:
        return []

    # Sign-change segmentation on Vg increments.
    dvg = np.diff(vg)
    direction = np.sign(dvg + 1e-12)
    change_idx = np.where(np.diff(direction) != 0)[0] + 1
    segments = np.split(np.arange(vg.size), change_idx)

    out: List[Tuple[np.ndarray, np.ndarray, str]] = []
    threshold = full_range_frac * total_range
    for seg in segments:
        if seg.size < 3:
            continue
        vg_seg = vg[seg]
        if (vg_seg.max() - vg_seg.min()) < threshold:
            continue
        sig_seg = signal[seg]
        leg_dir = "forward" if vg_seg[-1] > vg_seg[0] else "backward"
        out.append((vg_seg, sig_seg, leg_dir))
    return out


def fit_parabola_vertex(
    vg_leg: np.ndarray,
    signal_leg: np.ndarray,
    window_frac: float = 0.01,
    extremum: str = "min",
) -> Optional[dict]:
    """Fit a quadratic to a small window around the leg's extremum.

    Parameters
    ----------
    vg_leg, signal_leg
        1-D arrays of equal length covering one monotonic full-range leg.
    window_frac
        Total window width as a fraction of leg length (default 1%).
        The window is centered on the extremum; minimum total width 3.
    extremum
        "min" → window is centered on argmin(|signal|). Use for IVg where
        |I| dips at CNP.
        "max" → window is centered on argmax(|signal|). Use for VVg where
        |Vds| peaks at CNP.

    Returns
    -------
    dict or None
        On success: `{"v_cnp": float, "i_cnp": float, "a": float,
        "b": float, "c": float, "window_n": int, "argmin_idx": int}`.
        On failure (extremum at edge, degenerate quadratic, vertex outside
        the fit window): None.
    """
    n = vg_leg.size
    if n < 3:
        return None

    abs_sig = np.abs(signal_leg)
    if extremum == "max":
        idx = int(np.argmax(abs_sig))
    else:
        idx = int(np.argmin(abs_sig))

    total_w = max(3, int(round(window_frac * n)))
    h = max(1, total_w // 2)
    if idx - h < 0 or idx + h >= n:
        return None

    vg_w = vg_leg[idx - h : idx + h + 1].astype(float)
    sig_w = signal_leg[idx - h : idx + h + 1].astype(float)

    if not np.all(np.isfinite(vg_w)) or not np.all(np.isfinite(sig_w)):
        return None

    try:
        a, b, c = np.polyfit(vg_w, sig_w, 2)
    except (np.linalg.LinAlgError, ValueError):
        return None

    if not np.isfinite(a) or abs(a) < 1e-30:
        return None

    v_cnp = -b / (2.0 * a)
    if not np.isfinite(v_cnp):
        return None
    if v_cnp < vg_w.min() or v_cnp > vg_w.max():
        return None

    i_cnp = c - (b * b) / (4.0 * a)

    return {
        "v_cnp": float(v_cnp),
        "i_cnp": float(i_cnp),
        "a": float(a),
        "b": float(b),
        "c": float(c),
        "window_n": int(vg_w.size),
        "argmin_idx": idx,
    }
