from __future__ import annotations
from pathlib import Path
import numpy as np
from typing import List, Tuple
from scipy.signal import savgol_filter
from src.core.utils import _proc_from_path, _file_index
import polars as pl

from src.plotting.styles import set_plot_style
# Note: set_plot_style() is now called at the start of each plotting function
# instead of at module import time for thread-safety in TUI applications


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

