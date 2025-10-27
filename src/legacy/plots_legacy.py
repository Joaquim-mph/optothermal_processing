"""
Complete plotting module for measurement data visualization.

Improvements from original:
- Removed duplicate function definition (plot_its_by_vg_delta was defined twice)
- Extracted common patterns to helper functions
- Added proper constants for magic numbers
- Improved error handling with specific exceptions
- Added complete type hints
- Better documentation
- Consistent code structure throughout
"""

from __future__ import annotations
from pathlib import Path
import io
import numpy as np
from typing import List, Tuple
from scipy.signal import savgol_filter
from src.core.utils import _proc_from_path, _file_index, _read_measurement
import polars as pl
import matplotlib

# Auto-detect environment: use 'Agg' for scripts, keep default for Jupyter
def _setup_matplotlib_backend():
    """Set matplotlib backend based on environment (Jupyter vs script)."""
    try:
        # Check if we're in a Jupyter/IPython environment
        get_ipython()  # This will raise NameError if not in IPython
        # We're in Jupyter - don't force Agg backend
        print("[info] Jupyter environment detected - plots will display inline")
    except NameError:
        # We're in a script - use Agg backend for file saving
        matplotlib.use('Agg')

_setup_matplotlib_backend()
import matplotlib.pyplot as plt
from src.plotting.styles import set_plot_style
set_plot_style("prism_rain")
try:
    import imageio.v3 as iio
except ImportError:
    import imageio as iio

# ========================
# CONSTANTS
# ========================
DEFAULT_DPI = 300
LIGHT_WINDOW_ALPHA = 0.15
PLOT_START_TIME = 20.0
VG_TOLERANCE = 1e-6
WL_TOLERANCE = 1e-6
DEFAULT_BASELINE_TIME = 60.0
DEFAULT_VL_THRESHOLD = 0.0
DEFAULT_XLIM_SECONDS = 180.0

# ========================
# CONFIGURATION
# ========================
BASE_DIR = Path(".")
FIG_DIR = Path("figs")
FIG_DIR.mkdir(exist_ok=True)

# ========================
# JUPYTER HELPERS
# ========================
def set_its_figsize():
    """
    Set figure size for ITS plots in Jupyter notebooks.
    Call this before creating ITS plots in notebooks to override the default (20, 20) size.

    Example in Jupyter:
    >>> from src.plots import set_its_figsize, plot_its_by_vg
    >>> set_its_figsize()
    >>> # Now create your plots
    """
    plt.rcParams['figure.figsize'] = (40, 35)
    print("[info] ITS figure size set to (40, 35)")


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

def sanitize_value_for_filename(value: float, prefix: str = "") -> str:
    """Convert a numeric value to filename-safe string."""
    if not np.isfinite(value):
        return f"{prefix}unknown" if prefix else "unknown"
    
    s = str(value).replace("-", "m").replace(".", "p")
    return f"{prefix}{s}" if prefix else s

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

def sort_time_series(t: np.ndarray, *arrays: np.ndarray) -> tuple[np.ndarray, ...]:
    """Sort time array and corresponding data arrays by time."""
    if t.size == 0:
        return (t,) + arrays

    order = np.argsort(t)
    return (t[order],) + tuple(arr[order] if arr.size == t.size else arr
                                for arr in arrays)

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

def load_trace_data(
    path: Path,
    required_columns: set[str] | None = None
) -> pl.DataFrame | None:
    """Load measurement trace with validation."""
    if not path.exists():
        print(f"[warn] missing file: {path}")
        return None
    
    try:
        data = _read_measurement(path)
        
        if required_columns and not (required_columns <= set(data.columns)):
            missing = required_columns - set(data.columns)
            print(f"[warn] {path.name} missing columns {missing}")
            return None
            
        return data
    except Exception as e:
        print(f"[warn] failed to load {path.name}: {e}")
        return None

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

# -------------------------------
# Plotting
# -------------------------------

def plot_ivg_sequence(df: pl.DataFrame, base_dir: Path, tag: str):
    """Plot all IVg in chronological order (Id vs Vg)."""
    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        return
    plt.figure()
    for row in ivg.iter_rows(named=True):
        path = base_dir / row["source_file"]
        if not path.exists():
            print(f"[warn] missing file: {path}")
            continue
        d = _read_measurement(path)
        # Expect columns: VG, I (standardized)
        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {path} lacks VG/I; got {d.columns}")
            continue
        lbl = f"#{int(row['file_idx'])}  {'light' if row['with_light'] else 'dark'}"
        plt.plot(d["VG"], d["I"]*1e6, label=lbl)
    plt.xlabel("$\\rm{V_g\\ (V)}$")
    plt.ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
    plt.title(f"Encap{int(df['Chip number'][0])} — IVg")
    plt.legend()
    plt.ylim(bottom=0)
    plt.tight_layout()
    out = FIG_DIR / f"Encap{int(df['Chip number'][0])}_IVg_sequence_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")

def segment_voltage_sweep(vg: np.ndarray, i: np.ndarray, min_segment_length: int = 5) -> List[Tuple[np.ndarray, np.ndarray, str]]:
    """
    Segment a voltage sweep into monotonic sections.
    
    Detects direction changes in VG and splits the data accordingly.
    Returns list of (vg_segment, i_segment, direction) tuples.
    
    Parameters
    ----------
    vg : np.ndarray
        Gate voltage array
    i : np.ndarray
        Current array
    min_segment_length : int
        Minimum points required for a valid segment
        
    Returns
    -------
    List[Tuple[np.ndarray, np.ndarray, str]]
        List of (vg, i, direction) for each segment.
        direction is 'forward' (increasing VG) or 'reverse' (decreasing VG)
    """
    if len(vg) < min_segment_length:
        return []
    
    # Calculate voltage differences
    dvg = np.diff(vg)
    
    # Find direction changes (where sign of dvg changes)
    # Use a small threshold to avoid noise-induced false segments
    threshold = np.std(dvg) * 0.1  # 10% of std as threshold
    
    # Determine direction for each point (1 = increasing, -1 = decreasing, 0 = flat)
    directions = np.zeros(len(dvg))
    directions[dvg > threshold] = 1
    directions[dvg < -threshold] = -1
    
    # Find where direction changes
    direction_changes = np.where(np.diff(directions) != 0)[0] + 1
    
    # Add start and end indices
    segment_bounds = np.concatenate([[0], direction_changes, [len(vg)]])
    
    # Extract segments
    segments = []
    for i_start, i_end in zip(segment_bounds[:-1], segment_bounds[1:]):
        if i_end - i_start < min_segment_length:
            continue
            
        vg_seg = vg[i_start:i_end]
        i_seg = i[i_start:i_end]
        
        # Determine overall direction of this segment
        if np.mean(np.diff(vg_seg)) > 0:
            direction = 'forward'
        else:
            direction = 'reverse'
        
        segments.append((vg_seg, i_seg, direction))
    
    return segments

def calculate_transconductance_smooth(
    vg: np.ndarray, 
    i: np.ndarray,
    method: str = 'gradient',
    window: int = 5
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate transconductance (dI/dVg) with smoothing.
    
    Parameters
    ----------
    vg : np.ndarray
        Gate voltage (must be monotonic)
    i : np.ndarray
        Current
    method : str
        'gradient' uses np.gradient (recommended)
        'diff' uses centered differences
    window : int
        Smoothing window for moving average (must be odd)
        
    Returns
    -------
    vg_gm : np.ndarray
        VG points where gm is evaluated
    gm : np.ndarray
        Transconductance (dI/dVg) in S
    """
    if len(vg) < 3:
        return np.array([]), np.array([])
    
    # Ensure window is odd
    if window % 2 == 0:
        window += 1
    
    if method == 'gradient':
        # np.gradient handles non-uniform spacing automatically
        gm = np.gradient(i, vg)
        vg_gm = vg
    else:
        # Centered finite differences
        gm = np.zeros(len(i))
        gm[1:-1] = (i[2:] - i[:-2]) / (vg[2:] - vg[:-2])
        # Forward/backward for endpoints
        gm[0] = (i[1] - i[0]) / (vg[1] - vg[0])
        gm[-1] = (i[-1] - i[-2]) / (vg[-1] - vg[-2])
        vg_gm = vg
    
    # Apply moving average smoothing
    if window > 1 and len(gm) >= window:
        from scipy.ndimage import uniform_filter1d
        try:
            gm = uniform_filter1d(gm, size=window, mode='nearest')
        except ImportError:
            # Fallback: simple moving average
            pad = window // 2
            gm_smooth = np.convolve(gm, np.ones(window)/window, mode='valid')
            # Pad to maintain length
            gm = np.pad(gm_smooth, (pad, pad), mode='edge')
    
    return vg_gm, gm

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

    Notes
    -----
    - gm is computed per-segment: gm_seg = np.gradient(i_seg, vg_seg)
    - Duplicate VG values in a segment are removed before gradient to avoid div-by-zero.
    - Output units: gm shown in µS.
    """
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

        d = _read_measurement(path)
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
        base_lbl = f"#{int(row['file_idx'])} {'light' if row.get('with_light', False) else 'dark'}"
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
    chip_label = get_chip_label(df, default="Chip")
    ax.set_title(f"{chip_label} — Transconductance (np.gradient, joined, no sort)")
    ax.legend()
    ax.axhline(y=0, color='k', linestyle=':')

    plt.tight_layout()
    out = FIG_DIR / f"{chip_label}_gm_sequence_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
    plt.close(fig)

def plot_ivg_with_transconductance(
    df: pl.DataFrame,
    base_dir: Path, 
    tag: str,
    file_idx: int | None = None,
    smoothing_window: int = 7
):
    """
    Plot both I-V and transconductance curves side-by-side for a single measurement.
    
    Useful for debugging and understanding the relationship between I-V and gm.
    
    Parameters
    ----------
    df : pl.DataFrame
        Metadata DataFrame
    base_dir : Path
        Base directory
    tag : str
        Output tag
    file_idx : int | None
        If specified, plot only this measurement. If None, plot the first.
    smoothing_window : int
        Smoothing window for gm calculation
    """
    from src.core.utils import _read_measurement
    
    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        print("[info] no IVg measurements")
        return
    
    # Select measurement
    if file_idx is not None:
        row_df = ivg.filter(pl.col("file_idx") == file_idx)
        if row_df.height == 0:
            print(f"[warn] no measurement with file_idx={file_idx}")
            return
        row = row_df.row(0, named=True)
    else:
        row = ivg.row(0, named=True)
    
    # Load data
    path = base_dir / row["source_file"]
    if not path.exists():
        print(f"[warn] missing file: {path}")
        return
    
    d = _read_measurement(path)
    if not {"VG", "I"} <= set(d.columns):
        print(f"[warn] lacks VG/I columns")
        return
    
    vg = d["VG"].to_numpy()
    i = d["I"].to_numpy()
    
    # Segment
    segments = segment_voltage_sweep(vg, i, min_segment_length=5)
    
    if len(segments) == 0:
        print(f"[warn] no valid segments")
        return
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2)

    # Plot I-V
    for seg_idx, (vg_seg, i_seg, direction) in enumerate(segments):
        linestyle = '-' if direction == 'forward' else '--'
        label = f"Seg {seg_idx+1} ({direction})"

        ax1.plot(vg_seg, i_seg * 1e6, linestyle=linestyle, label=label)

    ax1.set_xlabel("VG (V)")
    ax1.set_ylabel("Current (µA)")
    ax1.set_title("I-V Curve (segmented)")
    ax1.legend()
    
    # Plot transconductance
    for seg_idx, (vg_seg, i_seg, direction) in enumerate(segments):
        vg_gm, gm = calculate_transconductance_smooth(
            vg_seg, i_seg,
            method='gradient',
            window=smoothing_window
        )
        
        if vg_gm.size == 0:
            continue

        linestyle = '-' if direction == 'forward' else '--'

        ax2.plot(vg_gm, gm * 1e6, linestyle=linestyle)

    ax2.set_xlabel("VG (V)")
    ax2.set_ylabel("Transconductance gm (µS)")
    ax2.set_title("Transconductance (segmented)")
    ax2.axhline(y=0, color='k', linestyle=':')

    # Overall title
    chip_label = get_chip_label(df)
    file_label = f"#{int(row['file_idx'])}"
    fig.suptitle(f"{chip_label} {file_label} — I-V and Transconductance")

    plt.tight_layout()

    out = FIG_DIR / f"{chip_label}_iv_gm_comparison_{file_label}_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
    plt.close(fig)

def plot_its_by_vg(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    vgs: list[float] | None = None,          # e.g., [-2.0]
    wavelengths: list[float] | None = None,  # e.g., [455.0]
    tol: float = 1e-6,                       # tolerance for Vg match
    wl_tol: float = 1e-6,                    # tolerance for wavelength match
    xlim_seconds: float | None = 180.0,      # None -> autoscale
    vl_threshold: float = 0.0,               # VL > threshold => light ON
):
    """
    Overlay ITS traces grouped by (Vg, wavelength) from metadata.
    Uses VL>vl_threshold to detect light ON; falls back to metadata ON duration if needed.
    """

    its_all = df.filter(pl.col("proc") == "ITS").sort("file_idx")
    if its_all.height == 0:
        print("[warn] no ITS rows in metadata")
        return

    if "VG_meta" not in its_all.columns:
        print("[warn] VG_meta not present in metadata; cannot group by Vg")
        return

    # Determine target Vg values
    if vgs is None:
        vgs = sorted(float(v) for v in its_all.get_column("VG_meta").drop_nulls().unique().to_list())
    else:
        vgs = list(vgs)

    # Determine target wavelengths
    if wavelengths is None:
        if "Laser wavelength" in its_all.columns:
            wavelengths = sorted(
                float(w) for w in its_all.get_column("Laser wavelength").drop_nulls().unique().to_list()
            )
        else:
            wavelengths = [float("nan")]  # no wavelength column → single pass
    else:
        wavelengths = list(wavelengths)

    for VG_target in vgs:
        for WL_target in wavelengths:
            # Build selection mask
            mask = (pl.col("VG_meta") - VG_target).abs() <= tol
            if "Laser wavelength" in its_all.columns and not np.isnan(WL_target):
                mask = mask & ((pl.col("Laser wavelength") - WL_target).abs() <= wl_tol)

            sel = its_all.filter(mask)
            if sel.height == 0:
                msg_wl = f", λ≈{WL_target:g} nm" if not np.isnan(WL_target) else ""
                print(f"[info] no ITS rows for Vg≈{VG_target:g} V{msg_wl}")
                continue

            plt.figure(figsize=(20,16))
            curves_plotted = 0

            # For window/x-lims
            t_totals = []
            starts_vl, ends_vl = [], []
            on_durs_meta = []

            for row in sel.iter_rows(named=True):
                path = base_dir / row["source_file"]
                if not path.exists():
                    print(f"[warn] missing file: {path}")
                    continue

                d = _read_measurement(path)
                if not {"t", "I"} <= set(d.columns):
                    print(f"[warn] {path} lacks t/I; got {d.columns}")
                    continue

                lbl = f"#{int(row['file_idx'])}  VL={row.get('VL_meta', float('nan'))} V"
                #######
                d_clip = d.filter(pl.col("t") >= PLOT_START_TIME)
                plt.plot(d_clip["t"], d_clip["I"]*1e6, label=lbl)
                #plt.plot(d["t"], d["I"], label=lbl)
                curves_plotted += 1

                # total duration
                try:
                    t_totals.append(float(d["t"].max()))
                except Exception:
                    pass

                # VL-based ON detection
                if "VL" in d.columns:
                    try:
                        vl = d["VL"].to_numpy()
                        tt = d["t"].to_numpy()
                        on_idx = np.where(vl > vl_threshold)[0]
                        if on_idx.size:
                            starts_vl.append(float(tt[on_idx[0]]))
                            ends_vl.append(float(tt[on_idx[-1]]))
                    except Exception:
                        pass

                # Metadata ON duration (treat “Laser ON+OFF period” as ON duration for OFF–ON–OFF)
                if "Laser ON+OFF period" in sel.columns:
                    try:
                        on_durs_meta.append(float(row["Laser ON+OFF period"]))
                    except Exception:
                        pass

            if curves_plotted == 0:
                print(f"[warn] no ITS traces plotted for Vg≈{VG_target:g} V, λ≈{WL_target:g} nm; skipping")
                plt.close()
                continue

            # X-limits
            if xlim_seconds is not None:
                plt.xlim(PLOT_START_TIME, float(xlim_seconds))
                T_total = float(xlim_seconds)
            else:
                T_total = float(np.median(t_totals)) if t_totals else None
                if T_total and np.isfinite(T_total) and T_total > 0:
                    plt.xlim(0.0, T_total)

            # ON window
            t0 = t1 = None
            if starts_vl and ends_vl:
                t0 = float(np.median(starts_vl))
                t1 = float(np.median(ends_vl))
            if (t0 is None or t1 is None) and on_durs_meta:
                on_dur = float(np.median(on_durs_meta))
                T_use = float(xlim_seconds) if xlim_seconds is not None else (float(np.median(t_totals)) if t_totals else None)
                if T_use and np.isfinite(T_use) and T_use > 0:
                    pre_off = max(0.0, (T_use - on_dur) / 2.0)
                    t0, t1 = pre_off, pre_off + on_dur
            if (t0 is None or t1 is None):
                T_use = (float(xlim_seconds) if xlim_seconds is not None
                         else (float(np.median(t_totals)) if t_totals else None))
                if T_use and np.isfinite(T_use) and T_use > 0:
                    t0, t1 = T_use/3.0, 2.0*T_use/3.0
            if (t0 is not None) and (t1 is not None) and (t1 > t0):
                plt.axvspan(t0, t1, alpha=LIGHT_WINDOW_ALPHA)

            # Title (use median wavelength in the selection when available)
            if "Laser wavelength" in sel.columns:
                wl_series = sel.get_column("Laser wavelength").cast(pl.Float64, strict=False).drop_nulls()
                if wl_series.len() > 0:
                    wl_used = float(wl_series.median())
                else:
                    wl_used = float("nan")
            else:
                wl_used = float("nan")

            wl_txt = f", λ={wl_used:.0f} nm" if np.isfinite(wl_used) else ""
            plt.title(f"Encap{int(df['Chip number'][0])} — Vg={VG_target:g} V{wl_txt}")
            plt.xlabel("Time (s)")
            plt.ylabel(f"Current (µA)")
            plt.legend()
            plt.tight_layout()

            safe_vg = str(VG_target).replace("-", "m").replace(".", "p")
            safe_wl = (f"{int(round(wl_used))}nm" if np.isfinite(wl_used)
                       else ("allwl"))
            out = FIG_DIR / f"chip{int(df['Chip number'][0])}_ITS_overlay_Vg{safe_vg}_{safe_wl}_{tag}.png"
            plt.savefig(out)
            print(f"saved {out}")

def plot_ivg_last_of_day1_vs_first_of_day2(
    meta_day1: pl.DataFrame,
    meta_day2: pl.DataFrame,
    base_dir_day1: Path,
    base_dir_day2: Path,
    tag: str,
):
    ivg1 = meta_day1.filter(pl.col("proc") == "IVg").sort("file_idx")
    ivg2 = meta_day2.filter(pl.col("proc") == "IVg").sort("file_idx")

    if ivg1.height == 0 or ivg2.height == 0:
        print("[warn] one of the days has no IVg runs")
        return

    r1 = ivg1.tail(1).row(0, named=True)   # last of day 1
    r2 = ivg2.head(1).row(0, named=True)   # first of day 2

    p1 = base_dir_day1 / r1["source_file"]
    p2 = base_dir_day2 / r2["source_file"]

    d1 = _read_measurement(p1)
    d2 = _read_measurement(p2)

    if not {"VG","I"} <= set(d1.columns):
        print(f"[warn] {p1} lacks VG/I; got {d1.columns}")
        return
    if not {"VG","I"} <= set(d2.columns):
        print(f"[warn] {p2} lacks VG/I; got {d2.columns}")
        return

    plt.figure()
    lbl1 = f"Day1 last (#{int(r1['file_idx'])})"
    lbl2 = f"Day2 first (#{int(r2['file_idx'])})"

    # Show wavelength only if Laser toggle is true
    if "Laser toggle" in ivg1.columns and bool(r1.get("Laser toggle", False)):
        if "Laser wavelength" in ivg1.columns and not ivg1["Laser wavelength"].drop_nulls().is_empty():
            wl1 = float(ivg1["Laser wavelength"].drop_nulls().median())
            lbl1 += f", λ={wl1:.0f} nm"

    if "Laser toggle" in ivg2.columns and bool(r2.get("Laser toggle", False)):
        if "Laser wavelength" in ivg2.columns and not ivg2["Laser wavelength"].drop_nulls().is_empty():
            wl2 = float(ivg2["Laser wavelength"].drop_nulls().median())
            lbl2 += f", λ={wl2:.0f} nm"

    plt.plot(d1["VG"], d1["I"]*1e6, label=lbl1)
    plt.plot(d2["VG"], d2["I"]*1e6, label=lbl2)

    chip_txt = f"Chip {int(meta_day1['Chip number'][0])}" if 'Chip number' in meta_day1.columns else "Chip"
    plt.xlabel("VG (V)")
    plt.ylabel("Current (µA)")
    plt.title(f"{chip_txt} — IVg: last (day1) vs first (day2)")
    plt.legend()
    plt.tight_layout()

    out = FIG_DIR / f"{chip_txt.replace(' ','')}_IVg_last_day1_first_day2_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")

def plot_its_by_vg_delta(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    vgs: list[float] | None = None,          # e.g., [-3.0, +3.0]
    wavelengths: list[float] | None = None,  # e.g., [455.0]
    tol: float = 1e-6,                       # Vg match tolerance
    wl_tol: float = 1e-6,                    # wavelength match tolerance
    xlim_seconds: float | None = 180.0,      # None -> autoscale
    vl_threshold: float = 0.0,               # VL > threshold => light ON
    baseline_t: float = 60.0,                # interpolate I at this t0
    clip_t_min: float = 20.0,                # start plotting from here
):
    """
    Overlay ITS traces grouped by (Vg, wavelength) with baseline subtraction:
    plot t vs (I(t) - I(baseline_t)), in microamps. Baseline is linearly
    interpolated per trace. VL>vl_threshold detects light ON for shading.
    """
    import numpy as np

    its_all = df.filter(pl.col("proc") == "ITS").sort("file_idx")
    if its_all.height == 0:
        print("[warn] no ITS rows in metadata")
        return
    if "VG_meta" not in its_all.columns:
        print("[warn] VG_meta not present in metadata; cannot group by Vg")
        return

    # Target Vg list
    if vgs is None:
        vgs = sorted(float(v) for v in its_all.get_column("VG_meta").drop_nulls().unique().to_list())
    else:
        vgs = list(vgs)

    # Target wavelength list
    if wavelengths is None:
        if "Laser wavelength" in its_all.columns:
            wavelengths = sorted(float(w) for w in its_all.get_column("Laser wavelength").drop_nulls().unique().to_list())
        else:
            wavelengths = [float("nan")]
    else:
        wavelengths = list(wavelengths)

    for VG_target in vgs:
        for WL_target in wavelengths:
            # selection mask
            mask = (pl.col("VG_meta") - VG_target).abs() <= tol
            if "Laser wavelength" in its_all.columns and not np.isnan(WL_target):
                mask = mask & ((pl.col("Laser wavelength") - WL_target).abs() <= wl_tol)
            sel = its_all.filter(mask)
            if sel.height == 0:
                msg_wl = f", λ≈{WL_target:g} nm" if not np.isnan(WL_target) else ""
                print(f"[info] no ITS rows for Vg≈{VG_target:g} V{msg_wl}")
                continue

            plt.figure(figsize=(20,16))
            curves_plotted = 0

            # For window/x-lims and shading
            t_totals = []
            starts_vl, ends_vl = [], []
            on_durs_meta = []

            for row in sel.iter_rows(named=True):
                path = base_dir / row["source_file"]
                if not path.exists():
                    print(f"[warn] missing file: {path}")
                    continue

                d = _read_measurement(path)
                if not {"t", "I"} <= set(d.columns):
                    print(f"[warn] {path} lacks t/I; got {d.columns}")
                    continue

                # Convert to numpy and ensure monotonic t
                t_all = d["t"].to_numpy()
                i_all = d["I"].to_numpy()
                if t_all.size < 2:
                    continue
                order = np.argsort(t_all)
                t_all = t_all[order]
                i_all = i_all[order]

                # Interpolate baseline at baseline_t (if inside range)
                if baseline_t < t_all[0] or baseline_t > t_all[-1]:
                    # Not in range → use nearest-value fallback (or skip)
                    # Here: fallback to nearest
                    idx_near = np.argmin(np.abs(t_all - baseline_t))
                    i0 = float(i_all[idx_near])
                else:
                    i0 = float(np.interp(baseline_t, t_all, i_all))

                # Clip time window for plotting (affects y autoscale)
                m = t_all >= float(clip_t_min)
                t = t_all[m]
                i = i_all[m]
                if t.size == 0:
                    continue

                # Baseline subtraction, then to microamps
                i_delta_uA = (i - i0) * 1e6

                # Label (laser voltage only, like you asked previously)
                lbl = f"VL={row.get('VL_meta', float('nan'))} V"
                plt.plot(t, i_delta_uA, label=lbl)
                curves_plotted += 1

                # Track total (unclipped) duration for axis decisions
                try:
                    t_totals.append(float(t_all[-1]))
                except Exception:
                    pass

                # VL-based ON detection (use full arrays)
                if "VL" in d.columns:
                    try:
                        vl = d["VL"].to_numpy()
                        vl = vl[order] if vl.size == order.size else vl  # best effort align
                        on_idx = np.where(vl > vl_threshold)[0]
                        if on_idx.size:
                            starts_vl.append(float(t_all[on_idx[0]]))
                            ends_vl.append(float(t_all[on_idx[-1]]))
                    except Exception:
                        pass

                # Metadata ON duration
                if "Laser ON+OFF period" in sel.columns:
                    try:
                        on_durs_meta.append(float(row["Laser ON+OFF period"]))
                    except Exception:
                        pass

            if curves_plotted == 0:
                print(f"[warn] no ITS traces plotted for Vg≈{VG_target:g} V; skipping")
                plt.close()
                continue

            # X-limits (start at clip_t_min)
            if xlim_seconds is not None:
                plt.xlim(float(clip_t_min), float(xlim_seconds))
                T_total = float(xlim_seconds)
            else:
                T_total = float(np.median(t_totals)) if t_totals else None
                if T_total and np.isfinite(T_total) and T_total > 0:
                    plt.xlim(float(clip_t_min), T_total)

            # Light ON window shading
            t0 = t1 = None
            if starts_vl and ends_vl:
                t0 = float(np.median(starts_vl))
                t1 = float(np.median(ends_vl))
            if (t0 is None or t1 is None) and on_durs_meta:
                on_dur = float(np.median(on_durs_meta))
                T_use = float(xlim_seconds) if xlim_seconds is not None else (float(np.median(t_totals)) if t_totals else None)
                if T_use and np.isfinite(T_use) and T_use > 0:
                    pre_off = max(0.0, (T_use - on_dur) / 2.0)
                    t0, t1 = pre_off, pre_off + on_dur
            if (t0 is None or t1 is None):
                T_use = (float(xlim_seconds) if xlim_seconds is not None
                         else (float(np.median(t_totals)) if t_totals else None))
                if T_use and np.isfinite(T_use) and T_use > 0:
                    t0, t1 = T_use/3.0, 2.0*T_use/3.0
            if (t0 is not None) and (t1 is not None) and (t1 > t0):
                plt.axvspan(t0, t1, alpha=LIGHT_WINDOW_ALPHA)

            # Title (median wavelength text)
            if "Laser wavelength" in sel.columns:
                wl_series = sel.get_column("Laser wavelength").cast(pl.Float64, strict=False).drop_nulls()
                wl_used = float(wl_series.median()) if wl_series.len() > 0 else float("nan")
            else:
                wl_used = float("nan")
            wl_txt = f", λ={wl_used:.0f} nm" if np.isfinite(wl_used) else ""

            plt.title(f"Encap{int(df['Chip number'][0])} — ΔI(t) @ Vg={VG_target:g} V{wl_txt} (baseline {baseline_t:g}s)")
            plt.xlabel("Time (s)")
            plt.ylabel("ΔCurrent (µA)")
            plt.legend()
            plt.tight_layout()

            safe_vg = str(VG_target).replace("-", "m").replace(".", "p")
            safe_wl = (f"{int(round(wl_used))}nm" if np.isfinite(wl_used) else "allwl")
            out = FIG_DIR / f"chip{int(df['Chip number'][0])}_ITS_dI_Vg{safe_vg}_{safe_wl}_{tag}.png"
            plt.savefig(out)
            print(f"saved {out}")

def _first_chip_label(df: pl.DataFrame) -> str:
    for c in ("Chip number", "chip", "Chip", "CHIP"):
        if c in df.columns and df.height:
            try:
                val = df.select(pl.col(c).first()).item()
                return f"Chip{int(float(val))}"
            except Exception:
                pass
    return "Chip"

def plot_its_wavelength_overlay_delta(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    vg_center: float = -3.0,
    vg_window: float | None = 0.25,       # None -> ignore VG
    ignore_vg: bool = False,              # explicit switch to ignore VG constraint
    wavelengths: list[float] | None = None,
    wl_tol: float = 1e-6,
    baseline_t: float = 60.0,
    clip_t_min: float = 20.0,
    xlim_seconds: float | None = 180.0,
    vl_threshold: float = 0.0,
    include_idx: list[int] | None = None,
    exclude_idx: list[int] | None = None,
    dedup_labels: bool = True,
    title_suffix: str = "",
    filename_suffix: str = "",
):
    """
    Overlay ITS traces (ΔI(t) = I(t) - I(baseline_t)) by wavelength. VG filter can be disabled.
    """
    import numpy as np
    import matplotlib.pyplot as plt

    its = df.filter(pl.col("proc") == "ITS").sort("file_idx")
    if its.height == 0:
        print("[warn] no ITS rows in metadata")
        return

    # Build filter mask (as a Polars expression)
    if not ignore_vg and vg_window is not None:
        if "VG_meta" not in its.columns:
            print("[warn] VG_meta not present; cannot select around vg_center")
            return
        mask = (pl.col("VG_meta") - float(vg_center)).abs() <= float(vg_window)
    else:
        mask = pl.lit(True)

    if include_idx:
        mask = mask & pl.col("file_idx").is_in(include_idx)
    if exclude_idx:
        mask = mask & (~pl.col("file_idx").is_in(exclude_idx))

    if wavelengths is not None and "Laser wavelength" in its.columns:
        wl_set = [float(w) for w in wavelengths]
        mask = mask & pl.any_horizontal([(pl.col("Laser wavelength") - w).abs() <= wl_tol for w in wl_set])

    sel = its.filter(mask)
    if sel.height == 0:
        print("[info] no ITS rows matched filters")
        return

    # Wavelengths to iterate
    if wavelengths is None and "Laser wavelength" in sel.columns:
        wls = sorted(float(w) for w in sel.get_column("Laser wavelength").drop_nulls().unique().to_list())
    else:
        wls = [float(w) for w in (wavelengths or [])] or [float("nan")]

    plt.figure(figsize=(20,16))
    curves_plotted = 0
    seen_labels: set[str] = set()
    t_totals: list[float] = []
    starts_vl: list[float] = []
    ends_vl: list[float] = []

    for WL_target in wls:
        if "Laser wavelength" in sel.columns and not (WL_target != WL_target):  # not NaN
            sub = sel.filter((pl.col("Laser wavelength") - WL_target).abs() <= wl_tol)
            if sub.height == 0:
                continue
        else:
            sub = sel

        for row in sub.iter_rows(named=True):
            path = base_dir / row["source_file"]
            if not path.exists():
                print(f"[warn] missing file: {path}")
                continue

            d = _read_measurement(path)
            if not {"t", "I"} <= set(d.columns):
                print(f"[warn] {path} lacks t/I; got {d.columns}")
                continue

            t_all = d["t"].to_numpy()
            i_all = d["I"].to_numpy()
            if t_all.size < 2:
                continue

            order = t_all.argsort()
            t_all = t_all[order]
            i_all = i_all[order]

            # Baseline interpolation
            if baseline_t < t_all[0] or baseline_t > t_all[-1]:
                idx_near = int(np.argmin(np.abs(t_all - baseline_t)))
                i0 = float(i_all[idx_near])
            else:
                i0 = float(np.interp(baseline_t, t_all, i_all))

            m = t_all >= float(clip_t_min)
            if not np.any(m):
                continue
            t = t_all[m]
            i = i_all[m]
            di_uA = (i - i0) * 1e6

            # Legend label (dedupe repeated λ)
            if "Laser wavelength" in sub.columns and not (WL_target != WL_target):
                lbl_full = f"λ={WL_target:.0f} nm"
            else:
                lbl_full = "λ=?"
            label = "_" + lbl_full if (dedup_labels and lbl_full in seen_labels) else lbl_full
            seen_labels.add(lbl_full)

            plt.plot(t, di_uA, label=label)
            curves_plotted += 1

            # Track global ranges
            t_totals.append(float(t_all[-1]))
            if "VL" in d.columns:
                try:
                    vl = d["VL"].to_numpy()
                    vl = vl[order] if vl.size == order.size else vl
                    on_idx = np.where(vl > vl_threshold)[0]
                    if on_idx.size:
                        starts_vl.append(float(t_all[on_idx[0]]))
                        ends_vl.append(float(t_all[on_idx[-1]]))
                except Exception:
                    pass

    if curves_plotted == 0:
        print("[warn] nothing plotted (check filters)")
        plt.close()
        return

    # Axes and shading
    if xlim_seconds is not None:
        plt.xlim(float(clip_t_min), float(xlim_seconds))
    elif t_totals:
        import numpy as np
        T_total = float(np.median(t_totals))
        if T_total > 0:
            plt.xlim(float(clip_t_min), T_total)

    if starts_vl and ends_vl:
        import numpy as np
        t0 = float(np.median(starts_vl))
        t1 = float(np.median(ends_vl))
        if t1 > t0:
            # why: show average light-on window across runs
            plt.axvspan(t0, t1, alpha=LIGHT_WINDOW_ALPHA)

    chip_txt = _first_chip_label(df)
    plt.title(f"{chip_txt} — ΔI(t) vs wavelength{title_suffix}")
    plt.xlabel("Time (s)")
    plt.ylabel("ΔCurrent (µA)")
    plt.legend(title="Wavelength")
    plt.tight_layout()

    out = FIG_DIR / f"{chip_txt}_ITS_dI_vs_wavelength_{tag}{filename_suffix}.png"
    plt.savefig(out)
    print(f"saved {out}")

def plot_its_wavelength_overlay_delta_for_chip(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    chip: int | float,
    vg_center: float = -3.0,
    vg_window: float | None = None,   # default None -> IGNORE VG
    ignore_vg: bool = True,          # default True for your use case
    wavelengths: list[float] | None = None,
    wl_tol: float = 1e-6,
    baseline_t: float = 60.0,
    clip_t_min: float = 20.0,
    xlim_seconds: float | None = 180.0,
    vl_threshold: float = 0.0,
    include_idx: list[int] | None = None,
    exclude_idx: list[int] | None = None,
    dedup_labels: bool = False,
    title_suffix: str = "",
    filename_suffix: str = "",
):
    """
    Convenience wrapper: filter to one chip, then call overlay plotter.
    Defaults chosen to IGNORE VG as you requested.
    """
    df_chip = df.filter(
        (pl.col("proc") == "ITS") &
        (pl.col("Chip number").cast(pl.Float64, strict=False) == float(chip))
    )
    if df_chip.height == 0:
        print(f"[info] no ITS rows for chip {chip}")
        return

    plot_its_wavelength_overlay_delta(
        df_chip,
        base_dir,
        tag,
        vg_center=vg_center,
        vg_window=vg_window,
        ignore_vg=ignore_vg,
        wavelengths=wavelengths,
        wl_tol=wl_tol,
        baseline_t=baseline_t,
        clip_t_min=clip_t_min,
        xlim_seconds=xlim_seconds,
        vl_threshold=vl_threshold,
        include_idx=include_idx,
        exclude_idx=exclude_idx,
        dedup_labels=dedup_labels,
        title_suffix=title_suffix,
        filename_suffix=filename_suffix,
    )

def ivg_sequence_gif(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    *,
    fps: float = 2.0,            # frames per second
    cumulative: bool = False,    # False = one curve per frame; True = overlay grows
    y_unit_uA: bool = True,      # plot in µA
    show_grid: bool = True
):
    """Create an animated GIF from all IVg curves in the DataFrame (fixed version)."""
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    
    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        print("[warn] no IVg rows to animate")
        return

    # -------- load & cache all curves; compute global limits --------
    curves = []
    xs_min, xs_max = +np.inf, -np.inf
    ys_min, ys_max = +np.inf, -np.inf

    for row in ivg.iter_rows(named=True):
        p = base_dir / row["source_file"]
        if not p.exists():
            print(f"[warn] missing file: {p}")
            continue
        d = _read_measurement(p)
        if not {"VG", "I"} <= set(d.columns):
            print(f"[warn] {p} lacks VG/I; got {d.columns}")
            continue

        x = d["VG"].to_numpy()
        y = d["I"].to_numpy()
        if y_unit_uA:
            y = y * 1e6

        # legend label: "#idx  light/dark  [λ=… nm]"
        label = f"#{int(row['file_idx'])}  {'light' if row.get('with_light', False) else 'dark'}"
        # show λ only if Laser toggle is true
        if bool(row.get("Laser toggle", False)):
            wl = row.get("Laser wavelength", None)
            if wl is not None and str(wl) != "nan":
                try:
                    label += f"  λ={float(wl):.0f} nm"
                except Exception:
                    pass

        curves.append({"x": x, "y": y, "label": label})

        # update global limits
        if x.size and y.size:
            xs_min = min(xs_min, np.nanmin(x))
            xs_max = max(xs_max, np.nanmax(x))
            ys_min = min(ys_min, np.nanmin(y))
            ys_max = max(ys_max, np.nanmax(y))

    if not curves:
        print("[warn] nothing loadable to animate")
        return

    # pad y limits a bit to avoid touching edges
    yr = ys_max - ys_min if np.isfinite(ys_max - ys_min) else 1.0
    ys_min_pad = ys_min - 0.05 * yr
    ys_max_pad = ys_max + 0.05 * yr

    # -------- render frames to memory using PIL instead of matplotlib canvas --------
    frames = []
    chip_txt = f"Encap{int(df['Chip number'][0])}" if "Chip number" in df.columns else "Chip"

    for i in range(len(curves)):
        plt.close("all")
        fig, ax = plt.subplots()

        if cumulative:
            rng = range(0, i + 1)
        else:
            rng = [i]

        for j in rng:
            ax.plot(curves[j]["x"], curves[j]["y"], label=curves[j]["label"])

        ax.set_xlim(xs_min, xs_max)
        ax.set_ylim(ys_min_pad, ys_max_pad)
        ax.set_xlabel("VG (V)")
        ax.set_ylabel("Current (µA)" if y_unit_uA else "Current (A)")
        ax.set_title(f"{chip_txt} — IVg sequence ({i+1}/{len(curves)})")
        if show_grid:
            ax.grid(True)

        # Save to temporary buffer and convert to PIL Image
        import io
        from PIL import Image

        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        img = Image.open(buf)
        frames.append(np.array(img))
        buf.close()
        plt.close(fig)

    # -------- write GIF --------
    out = FIG_DIR / f"{chip_txt}_IVg_sequence_{tag}.gif"
    out.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Try with imageio
        iio.imwrite(out, frames, duration=1.0 / fps, loop=0)
        print(f"saved {out}")
    except Exception as e:
        print(f"[warn] GIF save failed with imageio: {e}")
        # Fallback: save individual frames as PNGs
        for i, frame in enumerate(frames):
            frame_out = FIG_DIR / f"{chip_txt}_IVg_sequence_{tag}_frame_{i:03d}.png"
            iio.imwrite(frame_out, frame)
        print(f"[info] saved {len(frames)} individual frames instead")

        
def plot_its_overlay(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    baseline_t: float = 60.0,
    *,
    legend_by: str = "wavelength",  # "wavelength" (default), "vg", or "led_voltage"
    padding: float = 0.02,  # fraction of data range to add as padding (0.02 = 2%)
):
    """
    Overlay ITS traces baseline-corrected at `baseline_t`.
    Parameters
    ----------
    legend_by : {"wavelength","vg","led_voltage"}
        Use wavelength labels like "365 nm" (default), gate voltage labels like "3 V",
        or LED/laser voltage labels like "2.5 V".
        Aliases accepted: "wl","lambda" -> wavelength; "gate","vg","vgs" -> vg;
        "led","laser","led_voltage","laser_voltage" -> led_voltage.
    padding : float, optional
        Fraction of data range to add as padding on y-axis (default: 0.02 = 2%).
        Set to 0 for no padding, or increase for more whitespace around data.
        X-axis uses PLOT_START_TIME constant to avoid noisy data at the start.
    """
    import numpy as np
    # import matplotlib.pyplot as plt  # uncomment if not imported elsewhere

    # --- normalize legend_by to a canonical value ---
    lb = legend_by.strip().lower()
    if lb in {"wavelength", "wl", "lambda"}:
        lb = "wavelength"
    elif lb in {"vg", "gate", "vgs"}:
        lb = "vg"
    elif lb in {"led", "laser", "led_voltage", "laser_voltage"}:
        lb = "led_voltage"
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

    its = df.filter(pl.col("proc") == "ITS").sort("file_idx")
    if its.height == 0:
        print("[warn] no ITS rows in metadata")
        return

    plt.figure(figsize=(22,14))
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

        d = _read_measurement(path)
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

        # baseline @ baseline_t
        if tt[0] <= baseline_t <= tt[-1]:
            I0 = float(np.interp(baseline_t, tt, yy))
        else:
            nearest_idx = int(np.argmin(np.abs(tt - baseline_t)))
            I0 = float(yy[nearest_idx])
            print(f"[info] {path.name}: baseline_t={baseline_t:g}s outside [{tt[0]:.3g},{tt[-1]:.3g}]s; "
                  f"used nearest t={tt[nearest_idx]:.3g}s")
        yy_corr = yy - I0

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
        else:  # lb == "led_voltage"
            led_v = _get_led_voltage_V(row)
            if led_v is not None:
                # Compact formatting: 2.5 → "2.5 V", 3.0 → "3 V"
                lbl = f"{led_v:g} V"
                legend_title = "LED Voltage"
            else:
                lbl = f"#{int(row['file_idx'])}"
                legend_title = "Trace"

        # Store y-values ONLY for the visible time window (t >= PLOT_START_TIME)
        # This ensures padding is calculated from data actually shown in the plot
        visible_mask = tt >= PLOT_START_TIME
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
            plt.xlim(PLOT_START_TIME, T_total)

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

    plt.xlabel("t (s)")
    plt.ylabel("ΔCurrent (µA)")
    chipnum = int(df["Chip number"][0])  # keep your original pattern
    plt.title(f"Chip {chipnum} — ITS overlay")
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

    out = FIG_DIR / f"chip{chipnum}_ITS_overlay_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
    
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
    from src.core.utils import _read_measurement

    
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
        
        d = _read_measurement(path)
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
        base_lbl = f"#{int(row['file_idx'])} {'light' if row.get('with_light', False) else 'dark'}"
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

    chip_label = get_chip_label(df, default="Chip")

    ax.legend()

    plt.tight_layout()

    out = FIG_DIR / f"{chip_label}_gm_savgol_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
    plt.close(fig)

def plot_savgol_comparison(
    df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    file_idx: int | None = None,
    window_length: int = 9,
    polyorder: int = 3
):
    """
    Compare raw vs Savitzky-Golay filtered transconductance for debugging.
    
    Creates a detailed comparison plot for a single measurement.
    """
    
    ivg = df.filter(pl.col("proc") == "IVg").sort("file_idx")
    if ivg.height == 0:
        print("[info] no IVg measurements")
        return
    
    # Select measurement
    if file_idx is not None:
        row_df = ivg.filter(pl.col("file_idx") == file_idx)
        if row_df.height == 0:
            print(f"[warn] no measurement with file_idx={file_idx}")
            return
        row = row_df.row(0, named=True)
    else:
        row = ivg.row(0, named=True)
    
    path = base_dir / row["source_file"]
    if not path.exists():
        print(f"[warn] missing file: {path}")
        return
    
    d = _read_measurement(path)
    if not {"VG", "I"} <= set(d.columns):
        print(f"[warn] lacks VG/I columns")
        return
    
    vg = d["VG"].to_numpy()
    i = d["I"].to_numpy()
    
    segments = segment_voltage_sweep(vg, i, min_segment_length=5)
    if len(segments) == 0:
        print(f"[warn] no valid segments")
        return
    
    # Create figure with 3 subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1)

    # Plot 1: I-V curve (segmented)
    for seg_idx, (vg_seg, i_seg, direction) in enumerate(segments):
        linestyle = '-' if direction == 'forward' else '--'
        label = f"Seg {seg_idx+1} ({direction})"
        ax1.plot(vg_seg, i_seg * 1e6, linestyle=linestyle, label=label)

    ax1.set_xlabel("VG (V)")
    ax1.set_ylabel("Current (µA)")
    ax1.set_title("I-V Curve (segmented)")
    ax1.legend()

    # Plot 2: Raw derivative
    for seg_idx, (vg_seg, i_seg, direction) in enumerate(segments):
        gm_raw = _raw_derivative(vg_seg, i_seg)
        linestyle = '-' if direction == 'forward' else '--'
        ax2.plot(vg_seg, gm_raw * 1e6, linestyle=linestyle)

    ax2.set_xlabel("VG (V)")
    ax2.set_ylabel("gm (µS) - Raw")
    ax2.set_title("Raw Transconductance (np.gradient)")
    ax2.axhline(y=0, color='k', linestyle=':')

    # Plot 3: Filtered derivative
    for seg_idx, (vg_seg, i_seg, direction) in enumerate(segments):
        gm_filt = _savgol_derivative_corrected(
            vg_seg, i_seg,
            window_length=window_length,
            polyorder=polyorder
        )

        if gm_filt.size == 0:
            continue

        linestyle = '-' if direction == 'forward' else '--'
        ax3.plot(vg_seg, gm_filt * 1e6, linestyle=linestyle)

    ax3.set_xlabel("VG (V)")
    ax3.set_ylabel("gm (µS) - Filtered")
    ax3.set_title(f"Savitzky-Golay Filtered (window={window_length}, poly={polyorder})")
    ax3.axhline(y=0, color='k', linestyle=':')

    # Overall title
    chip_label = get_chip_label(df)
    file_label = f"#{int(row['file_idx'])}"
    fig.suptitle(f"{chip_label} {file_label} — Raw vs Filtered Transconductance Comparison")

    plt.tight_layout()

    out = FIG_DIR / f"{chip_label}_gm_comparison_{file_label}_{tag}.png"
    plt.savefig(out)
    print(f"saved {out}")
    plt.close(fig)