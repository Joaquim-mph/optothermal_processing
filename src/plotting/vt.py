"""Vt (voltage vs time) plotting functions."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.plot_utils import (
    interpolate_baseline,
    ensure_standard_columns,
    get_wavelength_nm,   # kept for backward compatibility / other callers
    get_gate_voltage,    # kept for backward compatibility / other callers
    get_led_voltage,     # kept for backward compatibility / other callers
    ensure_output_directory,
    print_info,
    print_warning,
)

# Constants
LIGHT_WINDOW_ALPHA = 0.15
PLOT_START_TIME = 20.0

# Configuration (will be overridden by CLI)
FIG_DIR = Path("figs")
FIGSIZE: Tuple[float, float] = (24.0, 17.0)


def _calculate_auto_baseline(df: pl.DataFrame, divisor: float = 2.0) -> float:
    """
    Calculate automatic baseline from LED ON+OFF period metadata.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata dataframe containing Vt experiments
    divisor : float
        Divisor for baseline calculation (period / divisor).
        Default: 2.0 (baseline at half the period)

    Returns
    -------
    float
        Calculated baseline time, or 60.0 if period not found
    """
    # Check both old and new column names for backward compatibility
    # New: laser_period_s (manifest column name from procedures.yml)
    # Old: "Laser ON+OFF period" (original parameter name)
    period_col = None
    if "laser_period_s" in df.columns:
        period_col = "laser_period_s"
    elif "Laser ON+OFF period" in df.columns:
        period_col = "Laser ON+OFF period"
    else:
        print("[warn] Could not auto-detect LED period (column missing), using baseline_t=60.0")
        return 60.0

    periods = []
    for row in df.iter_rows(named=True):
        try:
            period = float(row[period_col])
            if np.isfinite(period) and period > 0:
                periods.append(period)
        except Exception:
            pass

    if periods:
        median_period = float(np.median(periods))
        baseline = median_period / divisor
        print(f"[info] Auto baseline: {baseline:.1f}s (median period {median_period:.1f}s / {divisor})")
        return baseline

    print("[warn] Could not auto-detect LED period (no valid values), using baseline_t=60.0")
    return 60.0


def _apply_baseline_zero(tt: np.ndarray, yy: np.ndarray, plot_start_time: float = 0.0) -> np.ndarray:
    """
    Apply t=0 baseline correction (subtract first visible point).

    Parameters
    ----------
    tt : np.ndarray
        Time array
    yy : np.ndarray
        Voltage array
    plot_start_time : float, optional
        Start time for visible plot region. The baseline will be taken
        at the first point >= plot_start_time. Default: 0.0 (use first point)

    Returns
    -------
    np.ndarray
        Baseline-corrected voltage (yy - V0), where V0 is the value
        at the first visible point
    """
    if len(yy) == 0:
        return yy

    # Find first point at or after plot_start_time
    if plot_start_time > 0.0:
        visible_mask = tt >= plot_start_time
        if np.any(visible_mask):
            first_visible_idx = np.where(visible_mask)[0][0]
            V0 = yy[first_visible_idx]
        else:
            # Fallback: no data after plot_start_time, use first point
            V0 = yy[0]
    else:
        # plot_start_time = 0, use first point
        V0 = yy[0]

    return yy - V0


def plot_vt_overlay(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    baseline_t: float | None = 60.0,
    *,
    baseline_mode: str = "fixed",  # "fixed", "auto", or "none"
    baseline_auto_divisor: float = 2.0,  # Used when baseline_mode="auto"
    plot_start_time: float = PLOT_START_TIME,  # Configurable start time
    legend_by: str = "wavelength",  # "wavelength", "vg", "led_voltage", "power", or "datetime"
    padding: float = 0.02,  # fraction of data range to add as padding (0.02 = 2%)
):
    """
    Overlay Vt traces with flexible baseline and preset support.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with Vt experiments
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    baseline_t : float or None, optional
        Time point for baseline correction (used if baseline_mode="fixed").
        Default: 60.0 seconds
    baseline_mode : {"fixed", "auto", "none"}
        Baseline correction mode:
        - "fixed": Use baseline_t value
        - "auto": Calculate from LED ON+OFF period / baseline_auto_divisor
        - "none": No baseline correction (for dark experiments)
        Default: "fixed"
    baseline_auto_divisor : float
        Divisor for auto baseline calculation (period / divisor).
        Default: 2.0 (baseline at half the period)
    plot_start_time : float
        Start time for x-axis in seconds. Default: PLOT_START_TIME constant (20.0s)
    legend_by : {"wavelength","vg","led_voltage","power","datetime"}
        Use wavelength labels like "365 nm" (default), gate voltage labels like "3 V",
        LED/laser voltage labels like "2.5 V", power labels like "1.2 mW", or
        datetime labels like "2025-10-14 15:03".
        Aliases accepted: "wl","lambda" -> wavelength; "gate","vg","vgs" -> vg;
        "led","laser","led_voltage","laser_voltage" -> led_voltage;
        "pow","irradiated_power","led_power" -> power;
        "datetime","date","time","dt" -> datetime.
    padding : float, optional
        Fraction of data range to add as padding on y-axis (default: 0.02 = 2%).
    """
    # Apply plot style (lazy initialization for thread-safety)
    from src.plotting.styles import set_plot_style
    set_plot_style("prism_rain")

    # --- Handle baseline mode ---
    if baseline_mode == "auto":
        # Calculate baseline from LED ON+OFF period
        baseline_t = _calculate_auto_baseline(df, baseline_auto_divisor)
        apply_baseline = "interpolate"
    elif baseline_mode == "none":
        # No baseline correction (raw data mode)
        baseline_t = None
        apply_baseline = False
        print("[info] Baseline correction disabled (RAW DATA mode)")
    else:  # baseline_mode == "fixed"
        # Use provided baseline_t value
        if baseline_t is None:
            baseline_t = 60.0
            print("[warn] baseline_mode='fixed' but baseline_t=None, using 60.0")
        # Check if baseline is exactly 0.0 (special case)
        if baseline_t == 0.0:
            apply_baseline = "zero"
            print("[info] Baseline at t=0: subtracting first point from each trace")
        else:
            apply_baseline = "interpolate"

    # --- normalize legend_by to a canonical value ---
    lb = legend_by.strip().lower()
    if lb in {"wavelength", "wl", "lambda"}:
        lb = "wavelength"
    elif lb in {"vg", "gate", "vgs"}:
        lb = "vg"
    elif lb in {"led", "laser", "led_voltage", "laser_voltage"}:
        lb = "led_voltage"
    elif lb in {"pow", "power", "irradiated_power", "led_power"}:
        lb = "power"
    elif lb in {"datetime", "date", "time", "dt"}:
        lb = "datetime"
    else:
        print(f"[info] legend_by='{legend_by}' not recognized; using wavelength")
        lb = "wavelength"

    # --- Helper functions to extract metadata (upstream block) ---
    def _get_wavelength_nm(row: dict) -> float | None:
        candidates = [
            "Laser wavelength",
            "lambda",
            "lambda_nm",
            "wavelength",
            "wavelength_nm",
            "Wavelength",
            "Wavelength (nm)",
            "Laser wavelength (nm)",
            "Laser λ (nm)",
        ]
        for k in candidates:
            if k in row:
                try:
                    val = float(row[k])
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        return None

    def _get_vg_V(row: dict, d: "pl.DataFrame | dict | None" = None) -> float | None:
        vg_keys = [
            "VG",
            "Vg",
            "VGS",
            "Vgs",
            "Gate voltage",
            "Gate Voltage",
            "VG (V)",
            "Vg (V)",
            "VGS (V)",
            "Gate voltage (V)",
        ]
        for k in vg_keys:
            if k in row:
                try:
                    val = float(row[k])
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        return None

    def _get_led_voltage_V(row: dict) -> float | None:
        led_keys = [
            "Laser voltage",
            "LED voltage",
            "Laser voltage (V)",
            "LED voltage (V)",
        ]
        for k in led_keys:
            if k in row:
                try:
                    val = float(row[k])
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        return None

    def _get_power_formatted(row: dict) -> tuple[float | None, str]:
        """Extract irradiated power from enriched history and format for display."""
        power_keys = [
            "irradiated_power_w",
            "irradiated_power",
            "power_w",
            "power",
        ]

        for k in power_keys:
            if k in row:
                try:
                    power_w = float(row[k])
                    if np.isfinite(power_w) and power_w > 0:
                        # Format nicely: choose appropriate unit (W, mW, µW, nW)
                        if power_w >= 1.0:
                            return power_w, f"{power_w:g} W"
                        elif power_w >= 1e-3:
                            return power_w * 1e3, f"{power_w*1e3:g} mW"
                        elif power_w >= 1e-6:
                            return power_w * 1e6, f"{power_w*1e6:g} µW"
                        elif power_w >= 1e-9:
                            return power_w * 1e9, f"{power_w*1e9:g} nW"
                        else:
                            return power_w, f"{power_w:g} W"
                except (ValueError, TypeError):
                    pass

        return None, "N/A"

    # Filter only Vt rows
    vt = df.filter(pl.col("proc") == "Vt").sort("file_idx")
    if vt.height == 0:
        print("[warn] no Vt rows in metadata")
        return

    # Make sure figs dir exists
    ensure_output_directory(FIG_DIR)

    plt.figure(figsize=FIGSIZE)
    curves_plotted = 0

    t_totals: list[float] = []
    starts_vl: list[float] = []
    ends_vl: list[float] = []
    on_durations_meta: list[float] = []

    # Track y-values for manual limit calculation
    all_y_values: list[float] = []

    for row in vt.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue

        d = read_measurement_parquet(path)

        # Normalize column names (handle both "t" and "t (s)" formats)
        d = ensure_standard_columns(d)

        if not {"t", "VDS"} <= set(d.columns):
            print(f"[warn] {path} lacks t/VDS; got {d.columns}")
            continue

        tt = np.asarray(d["t"])
        yy = np.asarray(d["VDS"])
        if tt.size == 0 or yy.size == 0:
            print(f"[warn] empty/invalid series in {path}")
            continue
        if not np.all(np.diff(tt) >= 0):
            idx = np.argsort(tt)
            tt = tt[idx]
            yy = yy[idx]

        # baseline correction (three modes)
        if apply_baseline == "interpolate":
            # Standard interpolation at baseline_t
            V0 = interpolate_baseline(tt, yy, baseline_t, warn_extrapolation=True)
            yy_corr = yy - V0
        elif apply_baseline == "zero":
            # Subtract first visible point (baseline at t=0)
            yy_corr = _apply_baseline_zero(tt, yy, plot_start_time)
        else:  # apply_baseline == False
            # No baseline correction (raw data)
            yy_corr = yy

        # --- label based on legend_by ---
        if lb == "wavelength":
            wl = _get_wavelength_nm(row) or get_wavelength_nm(row)
            if wl is not None:
                lbl = f"{wl:g} nm"
                legend_title = "Wavelength"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"

        elif lb == "vg":
            # try local helper first, then plotting utils
            vg = _get_vg_V(row, d) or get_gate_voltage(row, d)
            if vg is not None:
                lbl = f"{vg:g} V"
                legend_title = "Vg"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"

        elif lb == "datetime":
            datetime_str = row.get("datetime_local")
            if datetime_str:
                lbl = datetime_str[:16] if len(datetime_str) >= 16 else datetime_str
                legend_title = "Date & Time"
            else:
                lbl = f"#{int(row.get('seq', row.get('file_idx', 0)))}"
                legend_title = "Experiment"

        elif lb == "power":
            power_val, power_str = _get_power_formatted(row)
            if power_val is not None:
                lbl = power_str
                legend_title = "Irradiated Power"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"

        else:  # lb == "led_voltage"
            # prefer the upstream helper (it’s more flexible on names)
            led_v = _get_led_voltage_V(row)
            if led_v is None:
                # fallback to project-wide utility
                led_v = get_led_voltage(row)
            if led_v is not None:
                lbl = f"{led_v:g} V"
                legend_title = "LED Voltage"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"

        # Store y-values ONLY for the visible time window (t >= plot_start_time)
        # Convert to mV for display
        visible_mask = tt >= plot_start_time
        all_y_values.extend((yy_corr * 1e3)[visible_mask])

        plt.plot(tt, yy_corr * 1e3, label=lbl)  # Convert V to mV
        curves_plotted += 1

        try:
            t_totals.append(float(tt[-1]))
        except Exception:
            pass

        # detect light-on window from VL
        if "VL" in d.columns:
            try:
                vl = np.asarray(d["VL"])
                on_idx = np.where(vl > 0)[0]
                if on_idx.size:
                    starts_vl.append(float(tt[on_idx[0]]))
                    ends_vl.append(float(tt[on_idx[-1]]))
            except Exception:
                pass

        # Check both old and new column names for backward compatibility
        period_col = None
        if "laser_period_s" in vt.columns:
            period_col = "laser_period_s"
        elif "Laser ON+OFF period" in vt.columns:
            period_col = "Laser ON+OFF period"

        if period_col is not None:
            try:
                on_durations_meta.append(float(row[period_col]))
            except Exception:
                pass

    if curves_plotted == 0:
        print("[warn] no Vt traces plotted; skipping light-window shading")
        return

    # Set x-axis limits
    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            plt.xlim(plot_start_time, T_total)

            # Enable scientific notation for long-duration measurements (> 1000s)
            if T_total > 1000:
                ax = plt.gca()
                ax.ticklabel_format(style="scientific", axis="x", scilimits=(0, 0))

    # Calculate light window shading
    t0 = t1 = None
    if starts_vl and ends_vl:
        t0 = float(np.median(starts_vl))
        t1 = float(np.median(ends_vl))
    if (t0 is None or t1 is None) and on_durations_meta and t_totals:
        on_dur = float(np.median(on_durations_meta))
        T_total = float(np.median(t_totals))
        if np.isfinite(on_dur) and np.isfinite(T_total) and T_total > 0:
            pre_off = max(0.0, (T_total - on_dur) / 2.0)
            t0 = pre_off
            t1 = pre_off + on_dur
    if (t0 is None or t1 is None) and t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            t0 = T_total / 3.0
            t1 = 2.0 * T_total / 3.0
    if (t0 is not None) and (t1 is not None) and (t1 > t0):
        plt.axvspan(t0, t1, alpha=LIGHT_WINDOW_ALPHA)

    plt.xlabel(r"$t\ (\mathrm{s})$")
    plt.ylabel(r"$\Delta V_{ds}\ (\mathrm{mV})$")

    # Safeguard chip number
    try:
        chipnum = int(df["chip_number"][0])
    except Exception:
        chipnum = 0

    plt.legend(title=legend_title)

    # Auto-adjust y-axis to data range with padding
    if all_y_values and padding >= 0:
        y_vals = np.array(all_y_values)
        y_vals = y_vals[np.isfinite(y_vals)]

        if y_vals.size > 0:
            y_min = float(np.min(y_vals))
            y_max = float(np.max(y_vals))

            if y_max > y_min:
                y_range = y_max - y_min
                y_pad = padding * y_range
                plt.ylim(y_min - y_pad, y_max + y_pad)

    plt.tight_layout()

    # Reapply y-limits after tight_layout
    if all_y_values and padding >= 0:
        y_vals = np.array(all_y_values)
        y_vals = y_vals[np.isfinite(y_vals)]

        if y_vals.size > 0:
            y_min = float(np.min(y_vals))
            y_max = float(np.max(y_vals))

            if y_max > y_min:
                y_range = y_max - y_min
                y_pad = padding * y_range
                plt.ylim(y_min - y_pad, y_max + y_pad)

    # Add _raw suffix if baseline_mode is "none"
    raw_suffix = "_raw" if baseline_mode == "none" else ""
    out = FIG_DIR / f"encap{chipnum}_Vt_{tag}{raw_suffix}.png"
    plt.savefig(out)
    print(f"saved {out}")
