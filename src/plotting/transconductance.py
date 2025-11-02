"""Transconductance (gm = dI/dVg) plotting functions."""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.plot_utils import (
    get_chip_label,
    segment_voltage_sweep,
    _savgol_derivative_corrected,
    _raw_derivative
)

# Configuration (will be overridden by CLI)
FIG_DIR = Path("figs")


def auto_select_savgol_params(
    vg: np.ndarray,
    i: np.ndarray,
    quality: str = "auto"
) -> tuple[int, int]:
    """
    Automatically select Savitzky-Golay window length and polynomial order.

    Uses a hybrid approach combining data point density and SNR estimation
    to select optimal smoothing parameters for transconductance calculation.

    Parameters
    ----------
    vg : np.ndarray
        Gate voltage array
    i : np.ndarray
        Current array
    quality : str, optional
        Quality preset: 'auto' (data-driven, default), 'ultra' (max detail),
        'high' (preserve features), 'medium' (balanced), 'low' (very smooth)

    Returns
    -------
    window_length : int
        Odd integer >= 5, suitable for scipy.signal.savgol_filter
    polyorder : int
        Polynomial order (2-4), always < window_length

    Notes
    -----
    Quality presets:
    - 'ultra': window=5, poly=2 (maximum detail, clean data)
    - 'high': window=7, poly=3 (preserve features, noisy data)
    - 'medium': window=9, poly=3 (balanced)
    - 'low': window=15, poly=3 (very smooth, low noise data)
    - 'auto': Adaptive selection based on data density and SNR

    Auto mode algorithm:
    1. Base window on number of data points (5% rule)
    2. Estimate SNR from signal statistics
    3. Adjust window based on SNR (cleaner → smaller, noisier → larger)
    4. Ensure odd window and valid poly < window

    Examples
    --------
    >>> vg = np.linspace(-1, 1, 100)
    >>> i = 1e-6 * (vg**2 + 0.01 * np.random.randn(100))
    >>> window, poly = auto_select_savgol_params(vg, i, "auto")
    >>> print(f"Selected: window={window}, poly={poly}")
    Selected: window=7, poly=3
    """
    n_points = len(vg)

    # Handle edge cases
    if n_points < 5:
        print(f"[warn] Only {n_points} data points, using minimum window=5")
        return 5, 2

    # Preset quality levels (fixed combinations)
    if quality == "ultra":
        return 5, 2
    elif quality == "high":
        return 7, 3
    elif quality == "medium":
        return 9, 3
    elif quality == "low":
        return 15, 3

    # Auto mode: data-driven selection
    # Step 1: Base window on data point density
    if n_points < 50:
        window, poly = 5, 2
    elif n_points < 100:
        window, poly = 7, 3
    elif n_points < 200:
        window, poly = 9, 3
    elif n_points < 500:
        window, poly = 11, 3
    else:
        # For very large datasets, use ~3% of points
        window = min(15, int(0.03 * n_points))
        if window % 2 == 0:
            window += 1
        poly = min(3, window - 2)

    # Step 2: SNR-based adjustment (optional refinement)
    try:
        # Estimate noise from high-frequency component (first difference)
        noise_estimate = np.std(np.diff(i))

        # Signal range (peak-to-peak)
        signal_range = np.ptp(i)

        if signal_range > 0 and noise_estimate > 0:
            # Approximate SNR (signal range vs noise level)
            # Factor of sqrt(2) accounts for differencing amplifying noise
            snr = signal_range / (noise_estimate * np.sqrt(2))

            # Adjust window based on SNR
            if snr > 100:  # Very clean data - use smaller window
                window = max(5, window - 2)
            elif snr > 50:  # Clean data - slightly smaller window
                window = max(5, window - 1)
            elif snr < 20:  # Noisy data - larger window
                window = min(21, window + 4)
            elif snr < 40:  # Moderately noisy - slightly larger
                window = min(21, window + 2)
            # else: SNR 40-50, use data-point-based default

            # Ensure odd
            if window % 2 == 0:
                window += 1

            # Adjust poly if needed
            poly = min(poly, window - 2)

    except Exception as e:
        # If SNR estimation fails, use data-point-based default
        pass

    # Final validation
    if window < 5:
        window = 5
    if poly < 2:
        poly = 2
    if poly >= window:
        poly = window - 2

    return window, poly


def plot_ivg_transconductance(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    smoothing_window: int = 5,       # kept for signature compatibility (unused here)
    min_segment_length: int = 10,
):
    """
    Plot transconductance (dI/dVg) for all IVg measurements.

    Uses numpy.gradient (same as PyQtGraph) to compute gm.
    Segments are computed to avoid reversal artifacts, then joined
    in original sweep order (no sorting). NaNs separate segments.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with IVg experiments
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    smoothing_window : int
        Kept for signature compatibility (unused in gradient method)
    min_segment_length : int
        Minimum points per segment before computing derivative

    Notes
    -----
    - gm is computed per-segment: gm_seg = np.gradient(i_seg, vg_seg)
    - Duplicate VG values in a segment are removed before gradient to avoid div-by-zero.
    - Output units: gm shown in µS.
    """
    # Apply plot style (lazy initialization for thread-safety)
    from src.plotting.styles import set_plot_style
    set_plot_style("prism_rain")

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        print("[info] no IVg measurements to plot")
        return

    fig, ax = plt.subplots()
    curves_plotted = 0

    for meas_idx, row in enumerate(ivg.iter_rows(named=True)):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue

        d = read_measurement_parquet(path)

        # Normalize column names (handle both formats)
        col_map = {}
        if "VG (V)" in d.columns:
            col_map["VG (V)"] = "VG"
        elif "Vg (V)" in d.columns:
            col_map["Vg (V)"] = "VG"
        if "I (A)" in d.columns:
            col_map["I (A)"] = "I"
        if col_map:
            d = d.rename(col_map)

        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/I; got {d.columns}")
            continue

        vg = d["VG"].to_numpy()
        i = d["I"].to_numpy()

        # Segment to avoid derivative artifacts at reversals
        segments = segment_voltage_sweep(vg, i, min_segment_length)
        if len(segments) == 0:
            print(f"[warn] {path.name}: no valid segments found")
            continue

        # Legend label per measurement
        base_lbl = f"#{int(row['file_idx'])} {'light' if row.get('has_light', False) else 'dark'}"
        if bool(row.get("Laser toggle", False)):
            wl = row.get("Laser wavelength", None)
            if wl is not None and str(wl) != "nan":
                try:
                    base_lbl += f" λ={float(wl):.0f} nm"
                except (TypeError, ValueError):
                    pass

        # Compute gm per segment with numpy.gradient; join in original order
        vg_join = []
        gm_join = []
        for (vg_seg, i_seg, _dir) in segments:
            if vg_seg.size < 2:
                continue

            # Remove consecutive duplicate VG to prevent div-by-zero in gradient
            keep = np.hstack(([True], np.diff(vg_seg) != 0))
            vg_clean = vg_seg[keep]
            i_clean  = i_seg[keep]
            if vg_clean.size < 2:
                continue

            # PyQtGraph-style derivative
            gm_seg = np.gradient(i_clean, vg_clean)  # A/V (Siemens)

            if len(vg_join) > 0:
                vg_join.append(np.array([np.nan])); gm_join.append(np.array([np.nan]))
            vg_join.append(vg_clean)
            gm_join.append(gm_seg)

        if not vg_join:
            continue

        vg_concat = np.concatenate(vg_join)
        gm_concat = np.concatenate(gm_join)

        ax.plot(vg_concat, gm_concat * 1e6, label=base_lbl)  # µS
        curves_plotted += 1

    if curves_plotted == 0:
        print("[warn] no transconductance curves plotted")
        plt.close(fig)
        return

    ax.set_xlabel("VG (V)")
    ax.set_ylabel("Transconductance gm (µS)")
    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history
    ax.set_title(f"Encap{chipnum} — Transconductance (np.gradient, joined, no sort)")
    ax.legend()
    ax.axhline(y=0, color='k', linestyle=':')

    plt.tight_layout()
    out = FIG_DIR / f"encap{chipnum}_gm_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
    plt.close(fig)


def plot_ivg_transconductance_savgol(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    min_segment_length: int = 10,
    window_length: int = 9,
    polyorder: int = 3,
    show_raw: bool = True,
    raw_alpha: float = 0.5,
):
    """
    Plot transconductance (dI/dVg) using Savitzky-Golay derivative.

    Shows both raw (transparent) and filtered (solid) transconductance.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag to append to filename
    min_segment_length : int
        Minimum points per segment (before derivative)
    window_length : int
        Sav-Gol window length (odd, >=3). Auto-adjusted if too large.
    polyorder : int
        Sav-Gol polynomial order (>=1, < window_length)
    show_raw : bool
        If True, show raw derivative as transparent background
    raw_alpha : float
        Transparency for raw derivative (0-1)
    """
    # Apply plot style (lazy initialization for thread-safety)
    from src.plotting.styles import set_plot_style
    set_plot_style("prism_rain")

    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        print("[info] no IVg measurements to plot")
        return

    fig, ax = plt.subplots()
    curves_plotted = 0

    # Let matplotlib handle colors (respects your color cycle configuration)
    # We'll use prop_cycle to get default colors
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']

    for meas_idx, row in enumerate(ivg.iter_rows(named=True)):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue

        d = read_measurement_parquet(path)

        # Normalize column names (handle both formats)
        col_map = {}
        if "VG (V)" in d.columns:
            col_map["VG (V)"] = "VG"
        elif "Vg (V)" in d.columns:
            col_map["Vg (V)"] = "VG"
        if "I (A)" in d.columns:
            col_map["I (A)"] = "I"
        if col_map:
            d = d.rename(col_map)

        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/I; got {d.columns}")
            continue

        vg = d["VG"].to_numpy()
        i = d["I"].to_numpy()

        segments = segment_voltage_sweep(vg, i, min_segment_length)
        if len(segments) == 0:
            print(f"[warn] {path.name}: no valid segments found")
            continue

        # Build label
        base_lbl = f"#{int(row['file_idx'])} {'light' if row.get('has_light', False) else 'dark'}"
        if bool(row.get("Laser toggle", False)):
            wl = row.get("Laser wavelength", None)
            if wl is not None and str(wl) != "nan":
                try:
                    base_lbl += f" λ={float(wl):.0f} nm"
                except (TypeError, ValueError):
                    pass

        # Lists to collect segments
        vg_raw_parts = []
        gm_raw_parts = []
        vg_filt_parts = []
        gm_filt_parts = []

        for (vg_seg, i_seg, _dir) in segments:
            if vg_seg.size < 3:
                continue

            # Calculate raw derivative
            gm_raw = _raw_derivative(vg_seg, i_seg)

            # Calculate filtered derivative (CORRECTED)
            gm_filt = _savgol_derivative_corrected(
                vg_seg, i_seg,
                window_length=window_length,
                polyorder=polyorder
            )

            if gm_filt.size == 0:
                continue

            # Add NaN separator between segments (creates gaps in plot)
            if len(vg_raw_parts) > 0:
                vg_raw_parts.append(np.array([np.nan]))
                gm_raw_parts.append(np.array([np.nan]))
                vg_filt_parts.append(np.array([np.nan]))
                gm_filt_parts.append(np.array([np.nan]))

            vg_raw_parts.append(vg_seg)
            gm_raw_parts.append(gm_raw)
            vg_filt_parts.append(vg_seg)
            gm_filt_parts.append(gm_filt)

        if not vg_raw_parts:
            continue

        # Concatenate all segments
        vg_concat = np.concatenate(vg_raw_parts)
        gm_raw_concat = np.concatenate(gm_raw_parts)
        gm_filt_concat = np.concatenate(gm_filt_parts)

        # Get color for this measurement
        color = color_cycle[meas_idx % len(color_cycle)]

        # Plot raw (transparent background) if requested
        if show_raw:
            ax.plot(
                vg_concat, gm_raw_concat * 1e6,  # µS
                linestyle=':',
                label=None  # Don't add to legend
            )

        # Plot filtered (solid foreground)
        ax.plot(
            vg_concat, gm_filt_concat * 1e6,  # µS
            label=base_lbl
        )

        curves_plotted += 1

    if curves_plotted == 0:
        print("[warn] no transconductance curves plotted")
        plt.close(fig)
        return

    ax.set_xlabel("VG (V)")
    ax.set_ylabel("Transconductance gm (µS)")

    chipnum = int(df['chip_number'][0])  # Use snake_case column name from history

    ax.legend()

    plt.tight_layout()

    out = FIG_DIR / f"encap{chipnum}_gm_savgol_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
    plt.close(fig)
