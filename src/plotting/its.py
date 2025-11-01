"""ITS (current vs time) plotting functions."""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import polars as pl
from typing import Tuple
from src.core.utils import read_measurement_parquet
from src.plotting.plot_utils import interpolate_baseline

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
        Metadata dataframe containing ITS experiments
    divisor : float
        Divisor for baseline calculation (period / divisor).
        Default: 2.0 (baseline at half the period)

    Returns
    -------
    float
        Calculated baseline time, or 60.0 if period not found
    """
    if "Laser ON+OFF period" not in df.columns:
        print("[warn] Could not auto-detect LED period (column missing), using baseline_t=60.0")
        return 60.0

    periods = []
    for row in df.iter_rows(named=True):
        try:
            period = float(row["Laser ON+OFF period"])
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
        Current array
    plot_start_time : float, optional
        Start time for visible plot region. The baseline will be taken
        at the first point >= plot_start_time. Default: 0.0 (use first point)

    Returns
    -------
    np.ndarray
        Baseline-corrected current (yy - I0), where I0 is the value
        at the first visible point

    Notes
    -----
    This avoids using artifacts in the first CSV point by using the
    first point in the visible time window instead.
    """
    if len(yy) == 0:
        return yy

    # Find first point at or after plot_start_time
    if plot_start_time > 0.0:
        visible_mask = tt >= plot_start_time
        if np.any(visible_mask):
            first_visible_idx = np.where(visible_mask)[0][0]
            I0 = yy[first_visible_idx]
        else:
            # Fallback: no data after plot_start_time, use first point
            I0 = yy[0]
    else:
        # plot_start_time = 0, use first point
        I0 = yy[0]

    return yy - I0


def _check_duration_mismatch(
    durations: list[float],
    tolerance: float = 0.10
) -> tuple[bool, str | None]:
    """
    Check if experiment durations vary beyond tolerance.

    Parameters
    ----------
    durations : list[float]
        List of experiment durations in seconds
    tolerance : float
        Maximum allowed variation as fraction (0.10 = 10%)

    Returns
    -------
    has_mismatch : bool
        True if durations vary > tolerance
    warning_msg : str or None
        Warning message with details, or None if OK
    """
    if not durations or len(durations) < 2:
        return False, None

    min_dur = min(durations)
    max_dur = max(durations)
    median_dur = np.median(durations)

    # Calculate variation from median
    variations = [(abs(d - median_dur) / median_dur) for d in durations]
    max_variation = max(variations)

    if max_variation > tolerance:
        warning_msg = (
            f"⚠ Duration mismatch detected!\n"
            f"  Experiments have different durations: {min_dur:.1f}s - {max_dur:.1f}s\n"
            f"  Variation: {max_variation*100:.1f}% (tolerance: {tolerance*100:.1f}%)\n"
            f"  This may cause inconsistent x-axis scaling."
        )
        return True, warning_msg

    return False, None


def _get_experiment_durations(df: pl.DataFrame, base_dir: Path) -> list[float]:
    """
    Extract experiment durations from measurement data.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata dataframe with ITS experiments
    base_dir : Path
        Base directory containing measurement files

    Returns
    -------
    list[float]
        List of experiment durations in seconds
    """
    durations = []
    its = df.filter(pl.col("proc") == "It")

    for row in its.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            continue

        try:
            d = read_measurement_parquet(path)
            if "t" in d.columns:
                tt = np.asarray(d["t"])
                if tt.size > 0:
                    durations.append(float(tt[-1]))
        except Exception:
            pass

    return durations


def plot_its_overlay(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    baseline_t: float | None = 60.0,
    *,
    baseline_mode: str = "fixed",  # "fixed", "auto", or "none"
    baseline_auto_divisor: float = 2.0,  # Used when baseline_mode="auto"
    plot_start_time: float = PLOT_START_TIME,  # Configurable start time
    legend_by: str = "wavelength",  # "wavelength" (default), "vg", or "led_voltage"
    padding: float = 0.02,  # fraction of data range to add as padding (0.02 = 2%)
    check_duration_mismatch: bool = False,  # Enable duration check
    duration_tolerance: float = 0.10,  # Tolerance for duration warnings (10%)
):
    """
    Overlay ITS traces with flexible baseline and preset support.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with ITS experiments
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
        Set to 0 for no padding, or increase for more whitespace around data.
    check_duration_mismatch : bool
        If True, check for duration mismatches and print warnings.
        Default: False
    duration_tolerance : float
        Maximum allowed variation in durations as fraction (0.10 = 10%).
        Only used if check_duration_mismatch=True.

    Examples
    --------
    >>> # Dark experiments (no baseline)
    >>> plot_its_overlay(df, Path("raw_data"), "dark", baseline_mode="none",
    ...                  plot_start_time=1.0, legend_by="vg")

    >>> # Auto baseline from LED period
    >>> plot_its_overlay(df, Path("raw_data"), "power_sweep", baseline_mode="auto",
    ...                  legend_by="led_voltage", check_duration_mismatch=True)
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

    # --- Check duration mismatch if requested ---
    if check_duration_mismatch:
        durations = _get_experiment_durations(df, base_dir)
        has_mismatch, warning = _check_duration_mismatch(durations, duration_tolerance)
        if has_mismatch:
            print(warning)

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

    # --- small helper to extract wavelength in nm from a metadata row ---
    def _get_wavelength_nm(row: dict) -> float | None:
        candidates = [
            "Laser wavelength", "lambda", "lambda_nm", "wavelength", "wavelength_nm",
            "Wavelength", "Wavelength (nm)", "Laser wavelength (nm)", "Laser λ (nm)"
        ]
        for k in candidates:
            if k in row:
                try:
                    val = float(row[k])
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        # Sometimes wavelength is stored as meters:
        for k in ["Wavelength (m)", "lambda_m"]:
            if k in row:
                try:
                    val = float(row[k]) * 1e9
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        return None

    # --- helper to extract Vg in volts from metadata row or from the data trace if constant ---
    def _get_vg_V(row: dict, d: "pl.DataFrame | dict | None" = None) -> float | None:
        # 1) Try metadata with common key variants
        vg_keys = [
            "VG", "Vg", "VGS", "Vgs", "Gate voltage", "Gate Voltage",
            "VG (V)", "Vg (V)", "VGS (V)", "Gate voltage (V)",
            "VG setpoint", "Vg setpoint", "Gate setpoint (V)", "VG bias (V)"
        ]
        # direct numeric first
        for k in vg_keys:
            if k in row:
                try:
                    val = float(row[k])
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        # permissive: numeric when key contains 'vg' or 'gate'
        for k, v in row.items():
            kl = str(k).lower()
            if ("vg" in kl or "gate" in kl):
                try:
                    val = float(v)
                    if np.isfinite(val):
                        return val
                except Exception:
                    # maybe a string like "VG=3.0 V"
                    try:
                        import re
                        m = re.search(r"([-+]?\d+(\.\d+)?)", str(v))
                        if m:
                            return float(m.group(1))
                    except Exception:
                        pass
        # 2) Try the data trace: if there's a nearly-constant VG column, use its median
        if d is not None and "VG" in d.columns:
            try:
                arr = np.asarray(d["VG"], dtype=float)
                if arr.size:
                    if np.nanstd(arr) < 1e-6:  # basically constant
                        return float(np.nanmedian(arr))
            except Exception:
                pass
        return None

    # --- helper to extract LED/Laser voltage in volts from metadata row ---
    def _get_led_voltage_V(row: dict) -> float | None:
        # Try metadata with common key variants
        led_keys = [
            "Laser voltage", "LED voltage", "Laser voltage (V)", "LED voltage (V)",
            "Laser V", "LED V", "Laser bias", "LED bias", "Laser bias (V)", "LED bias (V)",
            "Laser supply", "LED supply", "Laser supply (V)", "LED supply (V)"
        ]
        # direct numeric first
        for k in led_keys:
            if k in row:
                try:
                    val = float(row[k])
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        # permissive: numeric when key contains 'laser' and 'voltage' or 'led' and 'voltage'
        for k, v in row.items():
            kl = str(k).lower()
            if (("laser" in kl or "led" in kl) and "voltage" in kl):
                try:
                    val = float(v)
                    if np.isfinite(val):
                        return val
                except Exception:
                    # maybe a string like "Laser voltage: 2.5 V"
                    try:
                        import re
                        m = re.search(r"([-+]?\d+(\.\d+)?)", str(v))
                        if m:
                            return float(m.group(1))
                    except Exception:
                        pass
        return None

    # --- helper to extract irradiated power in watts from metadata row and format nicely ---
    def _get_power_formatted(row: dict) -> tuple[float | None, str]:
        """
        Extract irradiated power from enriched history and format for display.

        Returns
        -------
        tuple[float or None, str]
            (power_in_watts, formatted_string)
            e.g., (0.0012, "1.20 mW") or (None, "#seq")
        """
        # Try enriched history column first (from calibration matching)
        power_keys = [
            "irradiated_power_w",
            "irradiated_power",
            "power_w",
            "power"
        ]

        for k in power_keys:
            if k in row:
                try:
                    power_w = float(row[k])
                    if np.isfinite(power_w) and power_w > 0:
                        # Format nicely: choose appropriate unit (W, mW, µW, nW) with 2 decimals
                        if power_w >= 1.0:
                            return power_w, f"{power_w:.2f} W"
                        elif power_w >= 1e-3:
                            return power_w, f"{power_w*1e3:.2f} mW"
                        elif power_w >= 1e-6:
                            return power_w, f"{power_w*1e6:.2f} µW"
                        elif power_w >= 1e-9:
                            return power_w, f"{power_w*1e9:.2f} nW"
                        else:
                            return power_w, f"{power_w:.2f} W"
                except (ValueError, TypeError):
                    pass

        return None, None

    its = df.filter(pl.col("proc") == "It").sort("file_idx")
    if its.height == 0:
        print("[warn] no ITS rows in metadata")
        return

    plt.figure(figsize=FIGSIZE)
    curves_plotted = 0

    t_totals = []
    starts_vl, ends_vl = [], []
    on_durations_meta = []

    # Track y-values for manual limit calculation
    all_y_values = []

    for row in its.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue

        d = read_measurement_parquet(path)

        # Normalize column names (handle both "t" and "t (s)" formats)
        col_map = {}
        if "t (s)" in d.columns:
            col_map["t (s)"] = "t"
        if "I (A)" in d.columns:
            col_map["I (A)"] = "I"
        if col_map:
            d = d.rename(col_map)

        if not {"t", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks t/I; got {d.columns}")
            continue

        tt = np.asarray(d["t"])
        yy = np.asarray(d["I"])
        if tt.size == 0 or yy.size == 0:
            print(f"[warn] empty/invalid series in {path}")
            continue
        if not np.all(np.diff(tt) >= 0):
            idx = np.argsort(tt)
            tt = tt[idx]; yy = yy[idx]

        # baseline correction (three modes)
        if apply_baseline == "interpolate":
            # Standard interpolation at baseline_t
            I0 = interpolate_baseline(tt, yy, baseline_t, warn_extrapolation=True)
            yy_corr = yy - I0
        elif apply_baseline == "zero":
            # Subtract first visible point (baseline at t=0)
            yy_corr = _apply_baseline_zero(tt, yy, plot_start_time)
        else:  # apply_baseline == False
            # No baseline correction (raw data)
            yy_corr = yy

        # --- label based on legend_by ---
        if lb == "wavelength":
            wl = _get_wavelength_nm(row)
            if wl is not None:
                lbl = f"{wl:g} nm"
                legend_title = "Wavelength"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"
        elif lb == "vg":
            vg = _get_vg_V(row, d)
            if vg is not None:
                # Compact formatting: 3.0 → "3 V", 0.25 → "0.25 V"
                # Use :g to avoid trailing zeros, then add unit.
                lbl = f"{vg:g} V"
                legend_title = "Vg"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"
        elif lb == "power":
            power_w, power_str = _get_power_formatted(row)
            if power_str is not None:
                lbl = power_str
                legend_title = "LED Power"
            else:
                lbl = f"#{int(row.get('seq', row.get('file_idx', 0)))}"
                legend_title = "Trace"
        elif lb == "datetime":
            # Use datetime_local column if available
            datetime_str = row.get("datetime_local")
            if datetime_str:
                # Format: "2025-10-14 15:03:53" -> "2025-10-14 15:03" (remove seconds)
                lbl = datetime_str[:16] if len(datetime_str) >= 16 else datetime_str
                legend_title = "Date & Time"
            else:
                # Fallback to seq number if datetime_local not available
                lbl = f"#{int(row.get('seq', row.get('file_idx', 0)))}"
                legend_title = "Experiment"
        else:  # lb == "led_voltage"
            led_v = _get_led_voltage_V(row)
            if led_v is not None:
                # Compact formatting: 2.5 → "2.5 V", 3.0 → "3 V"
                lbl = f"{led_v:g} V"
                legend_title = "LED Voltage"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"

        # Store y-values ONLY for the visible time window (t >= plot_start_time)
        # This ensures padding is calculated from data actually shown in the plot
        visible_mask = tt >= plot_start_time
        all_y_values.extend((yy_corr * 1e6)[visible_mask])

        plt.plot(tt, yy_corr * 1e6, label=lbl)
        curves_plotted += 1

        try:
            t_totals.append(float(tt[-1]))
        except Exception:
            pass

        if "VL" in d.columns:
            try:
                vl = np.asarray(d["VL"])
                on_idx = np.where(vl > 0)[0]
                if on_idx.size:
                    starts_vl.append(float(tt[on_idx[0]]))
                    ends_vl.append(float(tt[on_idx[-1]]))
            except Exception:
                pass

        if "Laser ON+OFF period" in its.columns:
            try:
                on_durations_meta.append(float(row["Laser ON+OFF period"]))
            except Exception:
                pass

    if curves_plotted == 0:
        print("[warn] no ITS traces plotted; skipping light-window shading")
        return

    # Set x-axis limits
    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            plt.xlim(plot_start_time, T_total)

            # Enable scientific notation for long-duration measurements (> 1000s)
            if T_total > 1000:
                ax = plt.gca()
                ax.ticklabel_format(style='scientific', axis='x', scilimits=(0,0))

    # Calculate light window shading
    t0 = t1 = None
    if starts_vl and ends_vl:
        t0 = float(np.median(starts_vl)); t1 = float(np.median(ends_vl))
    if (t0 is None or t1 is None) and on_durations_meta and t_totals:
        on_dur = float(np.median(on_durations_meta))
        T_total = float(np.median(t_totals))
        if np.isfinite(on_dur) and np.isfinite(T_total) and T_total > 0:
            pre_off = max(0.0, (T_total - on_dur) / 2.0)
            t0 = pre_off; t1 = pre_off + on_dur
    if (t0 is None or t1 is None) and t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            t0 = T_total / 3.0; t1 = 2.0 * T_total / 3.0
    if (t0 is not None) and (t1 is not None) and (t1 > t0):
        plt.axvspan(t0, t1, alpha=LIGHT_WINDOW_ALPHA)

    plt.xlabel(r"$t\ (\mathrm{s})$")
    plt.ylabel(r"$\Delta I_{ds}\ (\mu\mathrm{A})$")
    chipnum = int(df["chip_number"][0])  # Use snake_case column name from history
    #plt.title(f"Chip {chipnum} — ITS overlay")
    plt.legend(title=legend_title)

    # Auto-adjust y-axis to data range with padding
    # IMPORTANT: Do this AFTER legend/title but BEFORE tight_layout for Jupyter compatibility
    if all_y_values and padding >= 0:
        y_vals = np.array(all_y_values)
        y_vals = y_vals[np.isfinite(y_vals)]  # Remove NaN/Inf

        if y_vals.size > 0:
            y_min = float(np.min(y_vals))
            y_max = float(np.max(y_vals))

            if y_max > y_min:
                y_range = y_max - y_min
                y_pad = padding * y_range
                plt.ylim(y_min - y_pad, y_max + y_pad)

    plt.tight_layout()

    # Reapply y-limits after tight_layout (which can reset them in Jupyter)
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
    out = FIG_DIR / f"encap{chipnum}_ITS_{tag}{raw_suffix}.png"
    plt.savefig(out)
    print(f"saved {out}")


def plot_its_dark(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    baseline_t: float | None = 60.0,
    *,
    baseline_mode: str = "fixed",
    baseline_auto_divisor: float = 2.0,
    plot_start_time: float = PLOT_START_TIME,
    legend_by: str = "vg",  # "vg" (default for dark), "wavelength", or "led_voltage"
    padding: float = 0.02,  # fraction of data range to add as padding (0.02 = 2%)
    check_duration_mismatch: bool = False,
    duration_tolerance: float = 0.10,
):
    """
    Overlay ITS traces for dark measurements (no laser) with baseline correction.

    This is a simplified version of plot_its_overlay without the light window shading,
    designed for experiments where the laser was never turned on.

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with ITS experiments
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    baseline_t : float or None
        Time point for baseline correction (default: 60.0 seconds)
    baseline_mode : {"fixed", "auto", "none"}
        Baseline correction mode (default: "fixed")
    baseline_auto_divisor : float
        Divisor for auto baseline calculation (default: 2.0)
    plot_start_time : float
        Start time for x-axis (default: PLOT_START_TIME)
    legend_by : {"vg", "wavelength", "led_voltage", "power", "datetime"}
        Legend grouping. Default is "vg" (gate voltage) for dark measurements.
        Can also use "power" for LED power or "datetime" to label by experiment date/time.
    padding : float
        Fraction of data range to add as y-axis padding (default: 0.02 = 2%)
    check_duration_mismatch : bool
        Enable duration mismatch warning (default: False)
    duration_tolerance : float
        Maximum allowed variation in durations (default: 0.10 = 10%)

    Notes
    -----
    - No light window shading is added since these are dark measurements
    - Simpler and cleaner plot for noise characterization experiments
    - Uses same baseline correction as plot_its_overlay
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

    # --- Check duration mismatch if requested ---
    if check_duration_mismatch:
        durations = _get_experiment_durations(df, base_dir)
        has_mismatch, warning = _check_duration_mismatch(durations, duration_tolerance)
        if has_mismatch:
            print(warning)

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
        print(f"[info] legend_by='{legend_by}' not recognized; using vg")
        lb = "vg"

    # --- small helper to extract wavelength in nm from a metadata row ---
    def _get_wavelength_nm(row: dict) -> float | None:
        candidates = [
            "Laser wavelength", "lambda", "lambda_nm", "wavelength", "wavelength_nm",
            "Wavelength", "Wavelength (nm)", "Laser wavelength (nm)", "Laser λ (nm)"
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

    # --- helper to extract Vg in volts from metadata row or from the data trace if constant ---
    def _get_vg_V(row: dict, d: "pl.DataFrame | dict | None" = None) -> float | None:
        # 1) Try metadata with common key variants
        vg_keys = [
            "VG", "Vg", "VGS", "Vgs", "Gate voltage", "Gate Voltage",
            "VG (V)", "Vg (V)", "VGS (V)", "Gate voltage (V)",
            "VG setpoint", "Vg setpoint", "Gate setpoint (V)", "VG bias (V)"
        ]
        # direct numeric first
        for k in vg_keys:
            if k in row:
                try:
                    val = float(row[k])
                    if np.isfinite(val):
                        return val
                except Exception:
                    pass
        # permissive: numeric when key contains 'vg' or 'gate'
        for k, v in row.items():
            kl = str(k).lower()
            if ("vg" in kl or "gate" in kl):
                try:
                    val = float(v)
                    if np.isfinite(val):
                        return val
                except Exception:
                    # maybe a string like "VG=3.0 V"
                    try:
                        import re
                        m = re.search(r"([-+]?\d+(\.\d+)?)", str(v))
                        if m:
                            return float(m.group(1))
                    except Exception:
                        pass
        # 2) Try the data trace: if there's a nearly-constant VG column, use its median
        if d is not None and "VG" in d.columns:
            try:
                arr = np.asarray(d["VG"], dtype=float)
                if arr.size:
                    if np.nanstd(arr) < 1e-6:  # basically constant
                        return float(np.nanmedian(arr))
            except Exception:
                pass
        return None

    # --- helper to extract LED/Laser voltage in volts from metadata row ---
    def _get_led_voltage_V(row: dict) -> float | None:
        led_keys = [
            "Laser voltage", "LED voltage", "Laser voltage (V)", "LED voltage (V)",
            "Laser V", "LED V", "Laser bias", "LED bias", "Laser bias (V)", "LED bias (V)",
            "Laser supply", "LED supply", "Laser supply (V)", "LED supply (V)"
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

    # --- helper to extract irradiated power in watts from metadata row and format nicely ---
    def _get_power_formatted(row: dict) -> tuple[float | None, str]:
        """Extract irradiated power from enriched history and format for display."""
        power_keys = [
            "irradiated_power_w",
            "irradiated_power",
            "power_w",
            "power"
        ]

        for k in power_keys:
            if k in row:
                try:
                    power_w = float(row[k])
                    if np.isfinite(power_w) and power_w > 0:
                        # Format nicely: choose appropriate unit (W, mW, µW, nW) with 2 decimals
                        if power_w >= 1.0:
                            return power_w, f"{power_w:.2f} W"
                        elif power_w >= 1e-3:
                            return power_w, f"{power_w*1e3:.2f} mW"
                        elif power_w >= 1e-6:
                            return power_w, f"{power_w*1e6:.2f} µW"
                        elif power_w >= 1e-9:
                            return power_w, f"{power_w*1e9:.2f} nW"
                        else:
                            return power_w, f"{power_w:.2f} W"
                except (ValueError, TypeError):
                    pass

        return None, None

    its = df.filter(pl.col("proc") == "It").sort("file_idx")
    if its.height == 0:
        print("[warn] no ITS rows in metadata")
        return

    plt.figure(figsize=FIGSIZE)
    curves_plotted = 0

    t_totals = []
    all_y_values = []

    for row in its.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue

        d = read_measurement_parquet(path)

        # Normalize column names (handle both "t" and "t (s)" formats)
        col_map = {}
        if "t (s)" in d.columns:
            col_map["t (s)"] = "t"
        if "I (A)" in d.columns:
            col_map["I (A)"] = "I"
        if col_map:
            d = d.rename(col_map)

        if not {"t", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks t/I; got {d.columns}")
            continue

        tt = np.asarray(d["t"])
        yy = np.asarray(d["I"])
        if tt.size == 0 or yy.size == 0:
            print(f"[warn] empty/invalid series in {path}")
            continue
        if not np.all(np.diff(tt) >= 0):
            idx = np.argsort(tt)
            tt = tt[idx]; yy = yy[idx]

        # baseline correction (three modes)
        if apply_baseline == "interpolate":
            # Standard interpolation at baseline_t
            I0 = interpolate_baseline(tt, yy, baseline_t, warn_extrapolation=True)
            yy_corr = yy - I0
        elif apply_baseline == "zero":
            # Subtract first visible point (baseline at t=0)
            yy_corr = _apply_baseline_zero(tt, yy, plot_start_time)
        else:  # apply_baseline == False
            # No baseline correction (raw data)
            yy_corr = yy

        # --- label based on legend_by ---
        if lb == "wavelength":
            wl = _get_wavelength_nm(row)
            if wl is not None:
                lbl = f"{wl:g} nm"
                legend_title = "Wavelength"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"
        elif lb == "vg":
            vg = _get_vg_V(row, d)
            if vg is not None:
                lbl = f"{vg:g} V"
                legend_title = "Vg"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"
        elif lb == "power":
            power_w, power_str = _get_power_formatted(row)
            if power_str is not None:
                lbl = power_str
                legend_title = "LED Power"
            else:
                lbl = f"#{int(row.get('seq', row.get('file_idx', 0)))}"
                legend_title = "Trace"
        elif lb == "datetime":
            # Use datetime_local column if available
            datetime_str = row.get("datetime_local")
            if datetime_str:
                # Format: "2025-10-14 15:03:53" -> "2025-10-14 15:03" (remove seconds)
                lbl = datetime_str[:16] if len(datetime_str) >= 16 else datetime_str
                legend_title = "Date & Time"
            else:
                # Fallback to seq number if datetime_local not available
                lbl = f"#{int(row.get('seq', row.get('file_idx', 0)))}"
                legend_title = "Experiment"
        else:  # lb == "led_voltage"
            led_v = _get_led_voltage_V(row)
            if led_v is not None:
                lbl = f"{led_v:g} V"
                legend_title = "LED Voltage"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"

        # Store y-values ONLY for the visible time window (t >= plot_start_time)
        visible_mask = tt >= plot_start_time
        all_y_values.extend((yy_corr * 1e6)[visible_mask])

        plt.plot(tt, yy_corr * 1e6, label=lbl)
        curves_plotted += 1

        try:
            t_totals.append(float(tt[-1]))
        except Exception:
            pass

    if curves_plotted == 0:
        print("[warn] no ITS traces plotted")
        return

    # Set x-axis limits
    if t_totals:
        T_total = float(np.median(t_totals))
        if np.isfinite(T_total) and T_total > 0:
            plt.xlim(plot_start_time, T_total)

            # Enable scientific notation for long-duration measurements (> 1000s)
            if T_total > 1000:
                ax = plt.gca()
                ax.ticklabel_format(style='scientific', axis='x', scilimits=(0,0))

    plt.xlabel(r"$t\ (\mathrm{s})$")
    plt.ylabel(r"$\Delta I_{ds}\ (\mu\mathrm{A})$")
    chipnum = int(df["chip_number"][0])  # Use snake_case column name from history
    #plt.title(f"Chip {chipnum} — ITS overlay (dark)")
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
    out = FIG_DIR / f"encap{chipnum}_ITS_dark_{tag}{raw_suffix}.png"
    plt.savefig(out)
    print(f"saved {out}")


def plot_its_sequential(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    plot_start_time: float = PLOT_START_TIME,
    show_boundaries: bool = True,
    legend_by: str = "datetime",
    padding: float = 0.02,
):
    """
    Plot ITS experiments sequentially on a continuous time axis (concatenated, not overlaid).

    Each experiment's data is placed consecutively in time, with different colors for
    each experiment. No baseline correction is applied (raw data).

    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame with ITS experiments (sorted chronologically)
    base_dir : Path
        Base directory containing measurement files
    tag : str
        Tag for output filename
    plot_start_time : float
        Start time to trim from each individual experiment. Default: PLOT_START_TIME (20.0s)
    show_boundaries : bool
        If True, show vertical dashed lines marking experiment boundaries. Default: True
    legend_by : {"datetime","wavelength","vg","led_voltage","power"}
        Legend grouping: datetime (default), wavelength, gate voltage, LED voltage, or LED power.
        Aliases accepted: "wl","lambda" -> wavelength; "gate","vgs" -> vg;
        "led","laser","laser_voltage" -> led_voltage; "pow","irradiated_power","led_power" -> power;
        "date","time","dt" -> datetime.
    padding : float
        Fraction of data range to add as padding on y-axis (default: 0.02 = 2%)

    Examples
    --------
    >>> # Plot experiments sequentially with datetime labels
    >>> plot_its_sequential(history, Path("."), "seq_93_95", legend_by="datetime")

    >>> # Use wavelength labels
    >>> plot_its_sequential(history, Path("."), "power_sweep", legend_by="wavelength")

    Notes
    -----
    - Raw data only (no baseline subtraction)
    - Time axis is continuous (experiment 2 starts where experiment 1 ends)
    - Each experiment gets a different color from the palette
    - Best for visualizing temporal evolution across multiple experiments
    """
    # Apply plot style
    from src.plotting.styles import set_plot_style, PRISM_RAIN_PALETTE
    set_plot_style("prism_rain")

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
        print(f"[info] legend_by='{legend_by}' not recognized; using datetime")
        lb = "datetime"

    # --- Helper functions for label extraction (reused from plot_its_overlay) ---
    def _get_wavelength_nm(row: dict) -> float | None:
        candidates = [
            row.get("Wavelength (nm)"),
            row.get("wavelength_nm"),
            row.get("Wavelength"),
        ]
        for c in candidates:
            if c is not None:
                try:
                    return float(c)
                except (ValueError, TypeError):
                    pass
        return None

    def _get_vg_V(row: dict, d: pl.DataFrame) -> float | None:
        # Try metadata columns first
        vg_meta = row.get("VGS (V)") or row.get("vg_fixed_v")
        if vg_meta is not None:
            try:
                return float(vg_meta)
            except (ValueError, TypeError):
                pass
        # Try data column if available
        if d is not None and "VG" in d.columns:
            try:
                vg_data = d["VG"].to_numpy()
                return float(np.median(vg_data[np.isfinite(vg_data)]))
            except Exception:
                pass
        return None

    def _get_led_voltage_V(row: dict) -> float | None:
        candidates = [
            row.get("Laser voltage"),
            row.get("laser_voltage_V"),
            row.get("VL_meta"),
        ]
        for c in candidates:
            if c is not None:
                try:
                    return float(c)
                except (ValueError, TypeError):
                    pass
        return None

    def _get_power_formatted(row: dict) -> tuple[float | None, str]:
        """Extract irradiated power from enriched history and format for display."""
        power_keys = [
            "irradiated_power_w",
            "irradiated_power",
            "power_w",
            "power"
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
                            return power_w, f"{power_w*1e3:g} mW"
                        elif power_w >= 1e-6:
                            return power_w, f"{power_w*1e6:g} µW"
                        elif power_w >= 1e-9:
                            return power_w, f"{power_w*1e9:g} nW"
                        else:
                            return power_w, f"{power_w:g} W"
                except (ValueError, TypeError):
                    pass

        return None, None

    # Storage for plotting
    all_y_values = []  # For auto y-scaling
    experiment_segments = []  # Store (time_array, current_array, label, color) for each experiment
    experiment_boundaries = []  # Time points where each new experiment starts

    time_offset = 0.0  # Running time offset for concatenation
    legend_title = "Experiment"  # Will be updated based on legend_by

    # Color palette
    colors = PRISM_RAIN_PALETTE
    num_colors = len(colors)

    print(f"[info] Plotting {len(df)} ITS experiments sequentially (raw data, no baseline)")

    for i, row in enumerate(df.iter_rows(named=True)):
        source_file = row.get("source_file")
        if not source_file:
            print(f"[warn] Skipping row {i}: no source_file")
            continue

        fp = Path(source_file)
        if not fp.is_absolute():
            fp = base_dir / fp

        if not fp.exists():
            print(f"[warn] File not found: {fp}")
            continue

        # Load measurement data
        try:
            d = read_measurement_parquet(fp)
        except Exception as e:
            print(f"[warn] Could not read {fp}: {e}")
            continue

        # Normalize column names (handle both "t" and "t (s)" formats)
        col_map = {}
        if "t (s)" in d.columns:
            col_map["t (s)"] = "t"
        if "I (A)" in d.columns:
            col_map["I (A)"] = "I"
        if col_map:
            d = d.rename(col_map)

        # Extract time and current
        if "t" not in d.columns or "I" not in d.columns:
            print(f"[warn] Missing t or I columns in {fp}")
            continue

        tt = np.asarray(d["t"])
        yy = np.asarray(d["I"])

        # Trim to plot_start_time
        mask = tt >= plot_start_time
        tt_trimmed = tt[mask]
        yy_trimmed = yy[mask]

        if len(tt_trimmed) == 0:
            print(f"[warn] No data after trimming to t>={plot_start_time}s for experiment {i}")
            continue

        # Reset time to start at 0 for this experiment
        tt_trimmed = tt_trimmed - tt_trimmed[0]

        # Record boundary for this experiment
        experiment_boundaries.append(time_offset)

        # --- Generate label based on legend_by ---
        if lb == "wavelength":
            wl = _get_wavelength_nm(row)
            if wl is not None:
                lbl = f"{wl:g} nm"
                legend_title = "Wavelength"
            else:
                lbl = f"#{int(row.get('seq', i))}"
                legend_title = "Experiment"
        elif lb == "vg":
            vg = _get_vg_V(row, d)
            if vg is not None:
                lbl = f"{vg:g} V"
                legend_title = "Vg"
            else:
                lbl = f"#{int(row.get('seq', i))}"
                legend_title = "Experiment"
        elif lb == "power":
            power_w, power_str = _get_power_formatted(row)
            if power_str is not None:
                lbl = power_str
                legend_title = "LED Power"
            else:
                lbl = f"#{int(row.get('seq', i))}"
                legend_title = "Experiment"
        elif lb == "datetime":
            datetime_str = row.get("datetime_local")
            if datetime_str:
                lbl = datetime_str[:16] if len(datetime_str) >= 16 else datetime_str
                legend_title = "Date & Time"
            else:
                lbl = f"#{int(row.get('seq', i))}"
                legend_title = "Experiment"
        else:  # lb == "led_voltage"
            led_v = _get_led_voltage_V(row)
            if led_v is not None:
                lbl = f"{led_v:g} V"
                legend_title = "LED Voltage"
            else:
                lbl = f"#{int(row.get('seq', i))}"
                legend_title = "Experiment"

        # Apply time offset for concatenation
        tt_offset = tt_trimmed + time_offset
        yy_ua = yy_trimmed * 1e6  # Convert to µA

        # Choose color from palette (cycle through colors)
        color = colors[i % num_colors]

        # Store segment data
        experiment_segments.append((tt_offset, yy_ua, lbl, color))

        # Store for y-axis scaling
        all_y_values.extend(yy_ua)

        # Update offset for next experiment
        time_offset += tt_trimmed[-1]

    if not experiment_segments:
        print("[error] No data to plot")
        return

    # Create figure
    plt.figure(figsize=FIGSIZE)

    # Plot each experiment segment with its own color
    for tt_seg, yy_seg, label, color in experiment_segments:
        plt.plot(tt_seg, yy_seg, linewidth=4, color=color, label=label)

    # Mark experiment boundaries (optional)
    if show_boundaries and len(experiment_boundaries) > 1:
        for boundary in experiment_boundaries[1:]:
            plt.axvline(boundary, color='gray', linestyle='--', linewidth=1.5, alpha=0.4)

    # Labels and title
    plt.xlabel("Time (s)")
    plt.ylabel(r"$I_{ds}\ (\mu\mathrm{A})$")
    chipnum = int(df["chip_number"][0])

    # Add legend
    plt.legend(title=legend_title, loc='best')

    # Auto-adjust y-axis with padding
    if padding >= 0 and all_y_values:
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

    # Save figure
    out = FIG_DIR / f"encap{chipnum}_ITS_sequential_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")

    # Calculate total time from last segment
    if experiment_segments:
        last_time = experiment_segments[-1][0][-1]  # Last time point of last segment
        print(f"[info] Sequential plot: {len(experiment_segments)} experiments, total time: {last_time:.1f}s")
