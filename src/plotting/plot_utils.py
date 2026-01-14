from __future__ import annotations
from pathlib import Path
import numpy as np
import polars as pl
from typing import List, Tuple, Optional, Dict, Any
from contextlib import contextmanager
from scipy.signal import savgol_filter
from src.core.utils import _proc_from_path, _file_index

# Lazy import for rich console to avoid circular dependencies
_console = None

def get_console():
    """Get or create rich console singleton."""
    global _console
    if _console is None:
        from rich.console import Console
        _console = Console()
    return _console


DEFAULT_VL_THRESHOLD = 0.0

# ========================
# HELPER FUNCTIONS
# ========================


def detect_light_on_window(
    data: pl.DataFrame,
    time_array: np.ndarray | None = None,
    vl_threshold: float = DEFAULT_VL_THRESHOLD
) -> tuple[float | None, float | None]:
    """Detect light ON period from VL column."""
    if "VL" not in data.columns:
        return None, None
    
    try:
        vl = data["VL"].to_numpy()
        tt = time_array if time_array is not None else data["t"].to_numpy()
        
        if vl.size != tt.size:
            min_size = min(vl.size, tt.size)
            vl = vl[:min_size]
            tt = tt[:min_size]
            
        on_idx = np.where(vl > vl_threshold)[0]
        if on_idx.size > 0:
            return float(tt[on_idx[0]]), float(tt[on_idx[-1]])
    except (TypeError, ValueError, KeyError) as e:
        print(f"[warn] VL detection failed: {e}")
    
    return None, None


def interpolate_baseline(
    t: np.ndarray,
    i: np.ndarray,
    baseline_t: float,
    warn_extrapolation: bool = False
) -> float:
    """Interpolate current at baseline_t, using nearest value if outside range."""
    if t.size == 0 or i.size == 0:
        raise ValueError("Empty time or current array")
    
    if baseline_t < t[0] or baseline_t > t[-1]:
        idx_near = int(np.argmin(np.abs(t - baseline_t)))
        if warn_extrapolation:
            print(f"[info] baseline_t={baseline_t:.3g}s outside data range "
                  f"[{t[0]:.3g}, {t[-1]:.3g}]s; using nearest t={t[idx_near]:.3g}s")
        return float(i[idx_near])
    
    return float(np.interp(baseline_t, t, i))


def get_chip_label(df: pl.DataFrame, default: str = "Chip") -> str:
    """Extract chip number from DataFrame for labeling."""
    for col in ("Chip number", "chip", "Chip", "CHIP"):
        if col in df.columns and df.height > 0:
            try:
                val = df.select(pl.col(col).first()).item()
                return f"Chip{int(float(val))}"
            except (TypeError, ValueError):
                pass
    return default


def calculate_transconductance(vg: np.ndarray, i: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate transconductance (dI/dVg) using central differences.

    Returns:
        vg_gm: Gate voltage points for transconductance
        gm: Transconductance values in S (Siemens)
    """
    if vg.size < 2 or i.size < 2:
        return np.array([]), np.array([])

    # Ensure sorted by VG
    order = np.argsort(vg)
    vg_sorted = vg[order]
    i_sorted = i[order]

    # Remove duplicate VG values by averaging current at duplicate points
    # This prevents division by zero in gradient calculation
    unique_vg, inverse_indices = np.unique(vg_sorted, return_inverse=True)

    if len(unique_vg) < 2:
        # All VG values are the same, can't compute derivative
        return np.array([]), np.array([])

    # Average current values at duplicate VG points
    unique_i = np.zeros_like(unique_vg)
    for idx in range(len(unique_vg)):
        mask = (inverse_indices == idx)
        unique_i[idx] = np.mean(i_sorted[mask])

    # Calculate discrete derivative using numpy gradient (central differences)
    # This is more robust than np.diff as it handles the boundaries better
    with np.errstate(divide='ignore', invalid='ignore'):
        gm = np.gradient(unique_i, unique_vg)

    # Filter out any NaN or Inf values that may have occurred
    valid_mask = np.isfinite(gm)

    return unique_vg[valid_mask], gm[valid_mask]


def calculate_light_window(
    starts_vl: list[float],
    ends_vl: list[float],
    on_durs_meta: list[float],
    t_totals: list[float],
    xlim_seconds: float | None
) -> tuple[float | None, float | None]:
    """Calculate light ON window for shading, using multiple data sources."""
    # Priority 1: VL-based detection
    if starts_vl and ends_vl:
        t0 = float(np.median(starts_vl))
        t1 = float(np.median(ends_vl))
        return t0, t1
    
    # Priority 2: Metadata ON duration
    if on_durs_meta and t_totals:
        on_dur = float(np.median(on_durs_meta))
        T_use = float(xlim_seconds) if xlim_seconds is not None else float(np.median(t_totals))
        if np.isfinite(T_use) and T_use > 0:
            pre_off = max(0.0, (T_use - on_dur) / 2.0)
            return pre_off, pre_off + on_dur
    
    # Priority 3: Fallback estimate
    if t_totals:
        T_use = float(xlim_seconds) if xlim_seconds is not None else float(np.median(t_totals))
        if np.isfinite(T_use) and T_use > 0:
            return T_use / 3.0, 2.0 * T_use / 3.0
    
    return None, None


def combine_metadata_by_seq(
    metadata_dir: Path,
    raw_data_dir: Path,
    chip: float,
    seq_numbers: list[int],
    chip_group_name: str = "Alisson"
) -> pl.DataFrame:
    """
    Combine experiments from multiple days using seq numbers from chip history.

    This is the CORRECT way to select cross-day experiments. Use seq numbers
    from print_chip_history() output, NOT file_idx (which repeats across days).

    Parameters
    ----------
    metadata_dir : Path
        Directory containing all metadata CSV files (e.g., Path("metadata"))
    raw_data_dir : Path
        Root directory for raw data files (e.g., Path("."))
    chip : float
        Chip number to filter
    seq_numbers : list[int]
        List of seq values from chip history (the first column in history output)
    chip_group_name : str
        Chip group name prefix. Default: "Alisson"

    Returns
    -------
    pl.DataFrame
        Combined metadata containing only the specified experiments

    Example
    -------
    >>> # Step 1: View chip history
    >>> from src.timeline import print_chip_history
    >>> print_chip_history(Path("metadata"), Path("."), 67, "Alisson", proc_filter="ITS")
    >>>
    >>> # Output shows:
    >>> # seq  date        time     proc  summary
    >>> #  52  2025-10-15  10:47:50  ITS  ... #1   ← Use seq=52
    >>> #  57  2025-10-16  12:03:23  ITS  ... #1   ← Use seq=57 (NOT file_idx #1!)
    >>>
    >>> # Step 2: Select by seq numbers
    >>> meta = combine_metadata_by_seq(
    ...     Path("metadata"),
    ...     Path("."),
    ...     chip=67.0,
    ...     seq_numbers=[52, 57, 58],  # Use seq from history
    ...     chip_group_name="Alisson"
    ... )
    >>>
    >>> # Step 3: Plot
    >>> plot_its_overlay(meta, Path("."), "cross_day", legend_by="led_voltage")
    """
    from src.core.timeline import build_chip_history

    # Build complete chip history
    history = build_chip_history(
        metadata_dir,
        raw_data_dir,
        int(chip),
        chip_group_name
    )

    if history.height == 0:
        print(f"[warn] no history found for {chip_group_name}{int(chip)}")
        return pl.DataFrame()

    # Filter history by requested seq numbers
    selected = history.filter(pl.col("seq").is_in(seq_numbers))

    if selected.height == 0:
        print(f"[warn] no experiments found with seq numbers: {seq_numbers}")
        return pl.DataFrame()

    # Group by day_folder to process each day's metadata
    day_groups = selected.group_by("day_folder").agg([
        pl.col("source_file").alias("source_files"),
        pl.col("seq").alias("seqs")
    ])

    all_meta = []

    for row in day_groups.iter_rows(named=True):
        day_folder = row["day_folder"]
        source_files = row["source_files"]

        # Find metadata file for this day
        possible_paths = [
            metadata_dir / day_folder / "metadata.csv",
            metadata_dir / f"{day_folder}_metadata.csv",
        ]

        meta_path = None
        for p in possible_paths:
            if p.exists():
                meta_path = p
                break

        if meta_path is None:
            print(f"[warn] could not find metadata for {day_folder}")
            continue

        # Load metadata for this day
        try:
            day_meta = load_and_prepare_metadata(str(meta_path), chip)

            # Filter by source files (most reliable way to match)
            day_meta_filtered = day_meta.filter(
                pl.col("source_file").is_in(source_files)
            )

            if day_meta_filtered.height > 0:
                all_meta.append(day_meta_filtered)

        except Exception as e:
            print(f"[warn] failed to load {meta_path}: {e}")

    if not all_meta:
        print("[warn] no metadata could be loaded")
        return pl.DataFrame()

    # Find common columns across all days
    common_cols = set(all_meta[0].columns)
    for df in all_meta[1:]:
        common_cols &= set(df.columns)

    common_cols = sorted(list(common_cols))

    # Align and concatenate
    aligned = [df.select(common_cols) for df in all_meta]
    combined = pl.concat(aligned, how="vertical")

    # Sort by start_time if available for chronological order
    if "start_time" in combined.columns:
        combined = combined.sort("start_time")

    print(f"[info] combined {combined.height} experiment(s) from {len(all_meta)} day(s)")
    print(f"[info] using {len(common_cols)} common column(s)")

    return combined


def load_and_prepare_metadata(meta_csv: str, chip: float) -> pl.DataFrame:
    df = pl.read_csv(meta_csv, infer_schema_length=1000)
    # Normalize column names we will use often
    df = df.rename({"Chip number": "Chip number",
                    "Laser voltage": "Laser voltage",
                    "Laser toggle": "Laser toggle",
                    "source_file": "source_file"})

    # Filter chip
    df = df.filter(pl.col("Chip number") == chip)

    # Infer procedure and index
    df = df.with_columns([
        pl.col("source_file").map_elements(_proc_from_path).alias("proc"),
        pl.col("source_file").map_elements(_file_index).alias("file_idx"),
        pl.when(pl.col("Laser toggle").cast(pl.Utf8).str.to_lowercase() == "true")
          .then(pl.lit(True))
          .otherwise(pl.lit(False))
          .alias("with_light"),
        pl.col("Laser voltage").cast(pl.Float64).alias("VL_meta"),
        pl.col("VG").cast(pl.Float64).alias("VG_meta").fill_null(strategy="zero")
    ]).sort("file_idx")

    # Build sessions = [IVg → ITS… → IVg] blocks
    # We'll assign the *closing* IVg to the same session as the preceding ITS.
    session_id = 0
    seen_any_ivg = False
    seen_its_since_ivg = False
    ids = []
    roles = []

    for proc in df["proc"].to_list():
        if proc == "IVg":
            if not seen_any_ivg:
                # first IVg starts session
                session_id += 1
                seen_any_ivg = True
                seen_its_since_ivg = False
                roles.append("pre_ivg")
                ids.append(session_id)
            else:
                if seen_its_since_ivg:
                    # this IVg closes the existing session
                    roles.append("post_ivg")
                    ids.append(session_id)
                    # next block will start on the next IVg or ITS as needed
                    seen_its_since_ivg = False
                    seen_any_ivg = False  # force new session on next IVg/ITS
                else:
                    # back-to-back IVg → treat as a new session pre_ivg
                    session_id += 1
                    roles.append("pre_ivg")
                    ids.append(session_id)
                    seen_its_since_ivg = False
        elif proc == "ITS":
            if not seen_any_ivg:
                # ITS without a prior IVg — start a new session
                session_id += 1
                seen_any_ivg = True
            roles.append("its")
            ids.append(session_id)
            seen_its_since_ivg = True
        else:
            roles.append("other")
            ids.append(session_id)

    df = df.with_columns([
        pl.Series("session", ids),
        pl.Series("role", roles),
    ])
    return df


def segment_voltage_sweep(vg: np.ndarray, i: np.ndarray, min_segment_length: int = 5) -> List[Tuple[np.ndarray, np.ndarray, str]]:
    """Segment a voltage sweep into monotonic sections."""
    if len(vg) < min_segment_length:
        return []
    
    dvg = np.diff(vg)
    threshold = np.std(dvg) * 0.1
    directions = np.zeros(len(dvg))
    directions[dvg > threshold] = 1
    directions[dvg < -threshold] = -1
    
    direction_changes = np.where(np.diff(directions) != 0)[0] + 1
    segment_bounds = np.concatenate([[0], direction_changes, [len(vg)]])
    
    segments = []
    for i_start, i_end in zip(segment_bounds[:-1], segment_bounds[1:]):
        if i_end - i_start < min_segment_length:
            continue
            
        vg_seg = vg[i_start:i_end]
        i_seg = i[i_start:i_end]
        direction = 'forward' if np.mean(np.diff(vg_seg)) > 0 else 'reverse'
        
        segments.append((vg_seg, i_seg, direction))
    
    return segments


def _savgol_derivative_corrected(
    vg: np.ndarray,
    i: np.ndarray,
    window_length: int = 9,
    polyorder: int = 3
) -> np.ndarray:
    """
    Calculate dI/dVg using Savitzky-Golay filter (CORRECTED).
    
    Key correction: Uses median spacing as delta, preserving sign for correct derivatives.
    """
    if len(vg) < 3:
        return np.array([])
    
    # Auto-adjust window if needed
    max_window = len(vg) if len(vg) % 2 == 1 else len(vg) - 1
    window_length = min(window_length, max_window)
    if window_length < polyorder + 2:
        window_length = polyorder + 2
    if window_length % 2 == 0:
        window_length += 1
    if window_length > len(vg):
        window_length = len(vg) if len(vg) % 2 == 1 else len(vg) - 1
    
    # Check polynomial order
    if polyorder >= window_length:
        polyorder = window_length - 1
    
    # CRITICAL FIX: Use median spacing WITH SIGN preserved
    # Don't use abs() - we need the sign for correct derivative!
    delta = np.median(np.diff(vg))  # <-- REMOVED np.abs()
    
    # Use savgol_filter with deriv=1 to get first derivative
    gm = savgol_filter(
        i,
        window_length=window_length,
        polyorder=polyorder,
        deriv=1,           # First derivative
        delta=delta,       # Now preserves sign for reverse sweeps
        mode='interp'      # Interpolate at boundaries
    )
    
    return gm


def _raw_derivative(vg: np.ndarray, i: np.ndarray) -> np.ndarray:
    """
    Calculate raw derivative using np.gradient for comparison.

    This is what you'd get without filtering - noisy but unbiased.
    """
    return np.gradient(i, vg)


def extract_cnp_for_plotting(
    measurement: pl.DataFrame,
    row_metadata: dict,
    procedure: str = "IVg"
) -> tuple[list[float] | None, list[float] | None, float | None, float | None]:
    """
    Extract CNP (charge neutrality point) for a measurement to overlay on plots.

    Parameters
    ----------
    measurement : pl.DataFrame
        Measurement data (from read_measurement_parquet)
    row_metadata : dict
        Row metadata from history (includes vds_v for IVg or ids_a for VVg)
    procedure : str
        Procedure type ("IVg" or "VVg")

    Returns
    -------
    tuple[list[float] | None, list[float] | None, float | None, float | None]
        (all_cnp_vgs, all_cnp_values, avg_cnp_vg, avg_cnp_value) where:
        - all_cnp_vgs: List of all detected CNP Vg values
        - all_cnp_values: List of corresponding I (IVg) or V (VVg) values at each CNP
        - avg_cnp_vg: The averaged CNP voltage
        - avg_cnp_value: The I/V value at the average CNP
        Returns (None, None, None, None) if CNP extraction fails

    Examples
    --------
    >>> all_vg, all_i, avg_vg, avg_i = extract_cnp_for_plotting(measurement, row, "IVg")
    >>> if all_vg is not None:
    ...     # Plot all detected CNPs
    ...     plt.plot(all_vg, np.array(all_i)*1e6, 'o', color='yellow', markersize=6)
    ...     # Plot average CNP
    ...     plt.plot(avg_vg, avg_i*1e6, 'D', color='red', markersize=10)
    """
    try:
        from src.derived.extractors.cnp_extractor import CNPExtractor

        # Prepare metadata for CNP extractor
        metadata = {
            'run_id': row_metadata.get('run_id', 'unknown'),
            'chip_number': row_metadata.get('chip_number', 0),
            'chip_group': row_metadata.get('chip_group', 'Unknown'),
            'procedure': procedure,
            'seq_num': row_metadata.get('seq', 0),
            'extraction_version': 'plot_overlay'
        }

        # Add procedure-specific parameters
        if procedure == "IVg":
            metadata['vds_v'] = row_metadata.get('vds_v')
        elif procedure == "VVg":
            # For VVg, need fixed current
            # Try to get from metadata, or use default
            metadata['ids_a'] = row_metadata.get('ids_a', 1e-5)  # Default 10 µA

        # Extract CNP
        extractor = CNPExtractor()
        result = extractor.extract(measurement, metadata)

        if result is None or result.value_float is None:
            return None, None, None, None

        avg_cnp_vg = result.value_float

        # Parse JSON to get all detected CNPs
        import json
        cnp_data = json.loads(result.value_json) if result.value_json else {}
        all_cnps_data = cnp_data.get("all_cnps", [])

        # Extract just the Vg values from the CNP dictionaries
        if all_cnps_data and isinstance(all_cnps_data[0], dict):
            # all_cnps is list of dicts with 'vg', 'r', 'direction', etc.
            all_cnps = [cnp['vg'] for cnp in all_cnps_data]
        elif all_cnps_data:
            # Already a list of floats
            all_cnps = all_cnps_data
        else:
            # Fallback: if no detailed data, just use the average
            all_cnps = [avg_cnp_vg]

        # Find Vg column
        vg_col = None
        for col in ["Vg (V)", "VG (V)"]:
            if col in measurement.columns:
                vg_col = col
                break

        if vg_col is None:
            return None, None, None, None

        vg_array = measurement[vg_col].to_numpy()

        # Get data column based on procedure
        if procedure == "IVg":
            # Get current column
            data_col = None
            for col in ["I (A)", "Ids (A)"]:
                if col in measurement.columns:
                    data_col = col
                    break

            if data_col is None:
                return None, None, None, None

            data_array = measurement[data_col].to_numpy()

        elif procedure == "VVg":
            # Get voltage column
            data_col = None
            for col in ["VDS (V)", "Vds (V)"]:
                if col in measurement.columns:
                    data_col = col
                    break

            if data_col is None:
                return None, None, None, None

            data_array = measurement[data_col].to_numpy()
        else:
            return None, None, None, None

        # Find values at all CNP points
        all_cnp_values = []
        for cnp_vg in all_cnps:
            idx = np.argmin(np.abs(vg_array - cnp_vg))
            all_cnp_values.append(data_array[idx])

        # Find value at average CNP
        avg_idx = np.argmin(np.abs(vg_array - avg_cnp_vg))
        avg_cnp_value = data_array[avg_idx]

        return all_cnps, all_cnp_values, avg_cnp_vg, avg_cnp_value

    except Exception as e:
        # Silently fail - CNP extraction is optional for plotting
        print(f"[debug] CNP extraction failed: {e}")
        return None, None, None, None


# ========================
# COLUMN NORMALIZATION
# ========================

def ensure_standard_columns(
    data: pl.DataFrame,
    column_mapping: Optional[Dict[str, str]] = None
) -> pl.DataFrame:
    """
    Normalize column names to standard format, removing the need for repeated col_map blocks.

    Parameters
    ----------
    data : pl.DataFrame
        Measurement data with potentially non-standard column names
    column_mapping : dict, optional
        Custom mapping of {actual_column_name: standard_name}.
        If None, uses sensible defaults for common patterns.

    Returns
    -------
    pl.DataFrame
        Data with normalized column names

    Examples
    --------
    >>> # Automatic normalization (handles common variants)
    >>> data = ensure_standard_columns(data)
    >>> # Now use "t", "I", "VG", "VDS" consistently

    >>> # Custom mapping
    >>> data = ensure_standard_columns(data, {"Time (s)": "t", "Current": "I"})

    Notes
    -----
    Standard column names used throughout plotting modules:
    - "t": time in seconds
    - "I": current in amperes
    - "VG": gate voltage in volts
    - "VDS": drain-source voltage in volts
    - "VL": laser/LED voltage in volts
    """
    if column_mapping is None:
        # Default mapping for common variants
        column_mapping = {}

        # Time column variants
        if "t (s)" in data.columns:
            column_mapping["t (s)"] = "t"

        # Current column variants
        if "I (A)" in data.columns:
            column_mapping["I (A)"] = "I"
        elif "Ids (A)" in data.columns:
            column_mapping["Ids (A)"] = "I"

        # Gate voltage variants
        if "VG (V)" in data.columns:
            column_mapping["VG (V)"] = "VG"
        elif "Vg (V)" in data.columns:
            column_mapping["Vg (V)"] = "VG"

        # Drain-source voltage variants
        if "VDS (V)" in data.columns:
            column_mapping["VDS (V)"] = "VDS"
        elif "Vds (V)" in data.columns:
            column_mapping["Vds (V)"] = "VDS"

        # Laser voltage variants
        if "VL (V)" in data.columns:
            column_mapping["VL (V)"] = "VL"

    # Apply mapping if we have any
    if column_mapping:
        return data.rename(column_mapping)

    return data


# ========================
# METADATA EXTRACTORS
# ========================

def get_wavelength_nm(row: dict) -> Optional[float]:
    """
    Extract wavelength in nanometers from metadata row.

    Handles various column name formats and units (nm or m).

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))

    Returns
    -------
    float or None
        Wavelength in nanometers, or None if not found/invalid
    """
    # Try common column names
    candidates = [
        "Laser wavelength", "lambda", "lambda_nm", "wavelength", "wavelength_nm",
        "Wavelength", "Wavelength (nm)", "Laser wavelength (nm)", "Laser λ (nm)"
    ]

    for k in candidates:
        if k in row:
            try:
                val = float(row[k])
                if np.isfinite(val) and val > 0:
                    return val
            except (ValueError, TypeError):
                pass

    # Try wavelength in meters (convert to nm)
    for k in ["Wavelength (m)", "lambda_m"]:
        if k in row:
            try:
                val = float(row[k]) * 1e9
                if np.isfinite(val) and val > 0:
                    return val
            except (ValueError, TypeError):
                pass

    return None


def get_gate_voltage(row: dict, data: Optional[pl.DataFrame] = None) -> Optional[float]:
    """
    Extract gate voltage in volts from metadata row or constant data column.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))
    data : pl.DataFrame, optional
        Measurement data. If provided and has constant VG column, uses that.

    Returns
    -------
    float or None
        Gate voltage in volts, or None if not found/invalid
    """
    # Try metadata with common key variants
    vg_keys = [
        "VG", "Vg", "VGS", "Vgs", "Gate voltage", "Gate Voltage",
        "VG (V)", "Vg (V)", "VGS (V)", "Gate voltage (V)",
        "VG setpoint", "Vg setpoint", "Gate setpoint (V)", "VG bias (V)",
        "vg_fixed_v"  # From chip history
    ]

    # Try direct numeric first
    for k in vg_keys:
        if k in row:
            try:
                val = float(row[k])
                if np.isfinite(val):
                    return val
            except (ValueError, TypeError):
                pass

    # Try permissive search (any key containing 'vg' or 'gate')
    for k, v in row.items():
        kl = str(k).lower()
        if ("vg" in kl or "gate" in kl):
            try:
                val = float(v)
                if np.isfinite(val):
                    return val
            except (ValueError, TypeError):
                # Maybe it's a string like "VG=3.0 V"
                try:
                    import re
                    m = re.search(r"([-+]?\d+(\.\d+)?)", str(v))
                    if m:
                        return float(m.group(1))
                except Exception:
                    pass

    # Try data trace: if there's a nearly-constant VG column, use its median
    if data is not None and "VG" in data.columns:
        try:
            arr = np.asarray(data["VG"], dtype=float)
            if arr.size:
                if np.nanstd(arr) < 1e-6:  # basically constant
                    return float(np.nanmedian(arr))
        except Exception:
            pass

    return None


def get_led_voltage(row: dict) -> Optional[float]:
    """
    Extract LED/laser voltage in volts from metadata row.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))

    Returns
    -------
    float or None
        LED/laser voltage in volts, or None if not found/invalid
    """
    led_keys = [
        "Laser voltage", "LED voltage", "Laser voltage (V)", "LED voltage (V)",
        "Laser V", "LED V", "Laser bias", "LED bias", "Laser bias (V)", "LED bias (V)",
        "Laser supply", "LED supply", "Laser supply (V)", "LED supply (V)",
        "laser_voltage_v"  # From chip history
    ]

    # Try direct numeric first
    for k in led_keys:
        if k in row:
            try:
                val = float(row[k])
                if np.isfinite(val):
                    return val
            except (ValueError, TypeError):
                pass

    # Try permissive search
    for k, v in row.items():
        kl = str(k).lower()
        if (("laser" in kl or "led" in kl) and "voltage" in kl):
            try:
                val = float(v)
                if np.isfinite(val):
                    return val
            except (ValueError, TypeError):
                # Maybe it's a string like "Laser voltage: 2.5 V"
                try:
                    import re
                    m = re.search(r"([-+]?\d+(\.\d+)?)", str(v))
                    if m:
                        return float(m.group(1))
                except Exception:
                    pass

    return None


def get_irradiated_power(row: dict, format_display: bool = True) -> tuple[Optional[float], Optional[str]]:
    """
    Extract irradiated power from enriched history and optionally format for display.

    Parameters
    ----------
    row : dict
        Metadata row (from iter_rows(named=True))
    format_display : bool
        If True, returns formatted string with appropriate units (W, mW, µW, nW).
        If False, returns just the value in watts.

    Returns
    -------
    tuple[float or None, str or None]
        (power_in_watts, formatted_string)
        If format_display=False, formatted_string is None.
        If power not found, returns (None, None).

    Examples
    --------
    >>> power_w, power_str = get_irradiated_power(row, format_display=True)
    >>> if power_str:
    ...     label = power_str  # e.g., "5.98 µW"

    >>> power_w, _ = get_irradiated_power(row, format_display=False)
    >>> if power_w is not None:
    ...     # Use raw value for calculations
    ...     normalized = signal / power_w
    """
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
                    if format_display:
                        # Format with 2 decimals and appropriate unit
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
                    else:
                        return power_w, None
            except (ValueError, TypeError):
                pass

    has_light = row.get("has_light")
    if has_light is False:
        return 0.0, ("0 W" if format_display else None)

    return None, None


# ========================
# PLOT CONTEXT MANAGER
# ========================

@contextmanager
def plot_context(
    theme: Optional[str] = None,
    output_dir: Optional[Path] = None,
    figure_name: Optional[str] = None,
    auto_save: bool = True,
    verbose: bool = False
):
    """
    Context manager for plotting with configurable theme and output.

    Handles theme setup, output directory creation, and automatic figure saving.
    Replaces hardcoded set_plot_style("prism_rain") and FIG_DIR patterns.

    Parameters
    ----------
    theme : str, optional
        Theme name. If None, uses "prism_rain" default.
    output_dir : Path, optional
        Output directory. If None, uses "figs/" default.
    figure_name : str, optional
        Figure filename. If provided and auto_save=True, saves to output_dir/figure_name.
    auto_save : bool
        If True, automatically saves figure at context exit.
    verbose : bool
        If True, prints status messages.

    Yields
    ------
    dict
        Context dictionary with keys:
        - "output_dir": Path to output directory
        - "figure_path": Full path to figure (if figure_name provided)
        - "console": Rich console instance

    Examples
    --------
    >>> with plot_context(theme="prism_rain", output_dir=Path("figs/chip67")) as ctx:
    ...     plt.figure()
    ...     plt.plot([1, 2, 3], [1, 4, 9])
    ...     plt.savefig(ctx["output_dir"] / "my_plot.png")

    >>> # Auto-save mode
    >>> with plot_context(figure_name="output.png", auto_save=True) as ctx:
    ...     plt.figure()
    ...     plt.plot([1, 2, 3], [1, 4, 9])
    ...     # Figure automatically saved at context exit

    >>> # Use console for rich output
    >>> with plot_context() as ctx:
    ...     ctx["console"].print("[cyan]Plotting...[/cyan]")
    ...     # ... plotting code ...
    """
    import matplotlib.pyplot as plt
    from src.plotting.styles import set_plot_style

    # Set defaults
    if theme is None:
        theme = "prism_rain"
    if output_dir is None:
        output_dir = Path("figs")

    console = get_console()

    # Apply theme
    try:
        set_plot_style(theme)
        if verbose:
            console.print(f"[dim]✓ Applied '{theme}' theme[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Could not apply theme '{theme}': {e}[/yellow]")

    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare context
    ctx = {
        "output_dir": output_dir,
        "console": console
    }

    if figure_name:
        ctx["figure_path"] = output_dir / figure_name

    try:
        yield ctx
    finally:
        # Auto-save if requested
        if auto_save and figure_name:
            try:
                fig_path = output_dir / figure_name
                plt.savefig(fig_path)
                if verbose:
                    console.print(f"[green]✓ Saved {fig_path}[/green]")
            except Exception as e:
                console.print(f"[red]Error saving figure: {e}[/red]")


# ========================
# FILESYSTEM UTILITIES
# ========================

def ensure_output_directory(path: Path, verbose: bool = False) -> Path:
    """
    Ensure output directory exists, creating it if necessary.

    Standardizes filesystem handling across plotting modules.

    Parameters
    ----------
    path : Path
        Directory path to ensure exists
    verbose : bool
        If True, prints creation message

    Returns
    -------
    Path
        The path (guaranteed to exist)

    Examples
    --------
    >>> out_dir = ensure_output_directory(Path("figs/chip67"))
    >>> plt.savefig(out_dir / "plot.png")  # No need to worry about directory existing
    """
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        if verbose:
            get_console().print(f"[dim]Created directory: {path}[/dim]")
    return path


# ========================
# PARQUET CACHING
# ========================

class ParquetCache:
    """
    Simple in-memory cache for parquet files to avoid re-reading in overlay operations.

    Usage
    -----
    >>> cache = ParquetCache()
    >>> for row in experiments:
    ...     data = cache.read(row["parquet_path"])
    ...     # Use data... cache automatically stores it
    """

    def __init__(self):
        self._cache: Dict[str, pl.DataFrame] = {}
        self._hits = 0
        self._misses = 0

    def read(self, path: Path | str) -> pl.DataFrame:
        """Read parquet file, using cache if available."""
        path_str = str(path)

        if path_str in self._cache:
            self._hits += 1
            return self._cache[path_str]

        # Cache miss - read from disk
        self._misses += 1
        from src.core.utils import read_measurement_parquet
        data = read_measurement_parquet(Path(path_str))
        self._cache[path_str] = data
        return data

    def clear(self):
        """Clear cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "cached_files": len(self._cache)
        }

    def __repr__(self) -> str:
        stats = self.stats()
        return (f"ParquetCache(hits={stats['hits']}, misses={stats['misses']}, "
                f"hit_rate={stats['hit_rate']:.1%}, cached={stats['cached_files']})")


# ========================
# RICH CONSOLE WRAPPERS
# ========================

def print_info(message: str):
    """Print info message with rich formatting."""
    get_console().print(f"[cyan]{message}[/cyan]")


def print_warning(message: str):
    """Print warning message with rich formatting."""
    get_console().print(f"[yellow]Warning: {message}[/yellow]")


def print_error(message: str):
    """Print error message with rich formatting."""
    get_console().print(f"[red]Error: {message}[/red]")


def print_success(message: str):
    """Print success message with rich formatting."""
    get_console().print(f"[green]✓ {message}[/green]")
