"""Individual ITS relaxation fit plot generation.

Generates one PNG file per It measurement with its relaxation fit,
suitable for automated batch processing and report generation.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import polars as pl
import json
from typing import Optional, List

from src.core.utils import read_measurement_parquet
from src.derived.algorithms import stretched_exponential
from src.plotting.plot_utils import (
    print_info,
    print_warning,
    print_error
)
from src.plotting.config import PlotConfig


def generate_individual_relaxation_plots(
    df: pl.DataFrame,
    metrics_df: pl.DataFrame,
    base_dir: Path,
    output_subdir: str = "individual_fits",
    config: Optional[PlotConfig] = None
) -> List[Path]:
    """
    Generate individual PNG plots for each It measurement with relaxation fit.

    Creates one plot per experiment, saved with descriptive filenames.

    Parameters
    ----------
    df : pl.DataFrame
        Filtered history DataFrame containing It experiments to plot
        Must have columns: seq, parquet_path, proc, chip_group, chip_number, run_id
    metrics_df : pl.DataFrame
        Metrics DataFrame filtered to relaxation_time metrics for these experiments
        Must have columns: run_id, value_float, value_json
    base_dir : Path
        Project base directory
    output_subdir : str, optional
        Subdirectory name under output_dir/its_relaxation_fits/ (default: "individual_fits")
    config : PlotConfig, optional
        Plot configuration (uses defaults if None)

    Returns
    -------
    List[Path]
        List of paths to generated plot files

    Examples
    --------
    >>> # Load history and metrics
    >>> history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")
    >>> metrics = pl.read_parquet("data/03_derived/_metrics/metrics.parquet")
    >>>
    >>> # Filter to It experiments with metrics
    >>> its_exps = history.filter(pl.col("proc") == "It")
    >>> its_metrics = metrics.filter(
    ...     (pl.col("metric_name") == "relaxation_time") &
    ...     (pl.col("run_id").is_in(its_exps["run_id"]))
    ... )
    >>>
    >>> # Generate individual plots
    >>> output_files = generate_individual_relaxation_plots(
    ...     its_exps, its_metrics, Path("."), output_subdir="Alisson67_fits"
    ... )
    >>> print(f"Generated {len(output_files)} plots")
    """
    if config is None:
        config = PlotConfig()

    # Validate inputs
    if df.height == 0:
        print_error("No experiments to plot")
        return []

    if metrics_df.height == 0:
        print_warning("No relaxation metrics found - cannot plot fits")
        return []

    # Get base output directory using PlotConfig (respects global output_dir setting)
    # We'll add the output_subdir to each individual filename
    # This ensures consistency with other plotting modules

    # Match metrics to experiments by run_id
    metrics_map = {}
    for metric_row in metrics_df.iter_rows(named=True):
        metrics_map[metric_row["run_id"]] = metric_row

    # Generate plots
    output_files = []
    skipped = 0
    errors = 0

    for idx, exp_row in enumerate(df.iter_rows(named=True)):
        run_id = exp_row.get("run_id")
        seq = exp_row.get("seq", "?")
        chip_group = exp_row.get("chip_group", "Unknown")
        chip_number = exp_row.get("chip_number", "?")
        chip_name = f"{chip_group}{chip_number}"
        parquet_path = Path(exp_row["parquet_path"])

        # Get metric for this experiment
        metric = metrics_map.get(run_id)
        if metric is None:
            print_warning(f"seq {seq}: No relaxation metric found, skipping")
            skipped += 1
            continue

        # Generate output path using PlotConfig with special subcategory
        output_filename = f"{chip_name}_seq{seq:03d}_It_relaxation"
        output_file = config.get_output_path(
            output_filename,
            chip_number=chip_number,
            procedure="It",
            special_type=output_subdir,  # Use output_subdir as special subcategory (e.g., "individual_fits")
            create_dirs=True
        )

        # Load measurement data
        try:
            measurement = read_measurement_parquet(parquet_path)
        except Exception as e:
            print_warning(f"seq {seq}: Failed to load measurement: {e}")
            errors += 1
            continue

        # Generate plot
        try:
            _plot_single_experiment(
                measurement=measurement,
                metric=metric,
                seq=seq,
                chip_name=chip_name,
                output_file=output_file,
                config=config
            )
            output_files.append(output_file)
        except Exception as e:
            print_warning(f"seq {seq}: Failed to generate plot: {e}")
            errors += 1
            continue

    # Summary
    # Determine output directory from first generated file (if any)
    summary_msg = f"Generated {len(output_files)} individual relaxation plots"
    if output_files:
        # Show the parent directory where files were saved
        output_parent = output_files[0].parent
        print_info(f"{summary_msg} in {output_parent}")
    else:
        print_info(summary_msg)

    if skipped > 0:
        print_warning(f"Skipped {skipped} experiments (no metrics)")
    if errors > 0:
        print_error(f"Failed to plot {errors} experiments (errors)")

    return output_files


def _plot_single_experiment(
    measurement: pl.DataFrame,
    metric: dict,
    seq: int,
    chip_name: str,
    output_file: Path,
    config: Optional[PlotConfig] = None
) -> None:
    """
    Plot a single It measurement with fitted relaxation curve.

    Parameters
    ----------
    measurement : pl.DataFrame
        Measurement data with columns: t (s), I (A), VL (V)
    metric : dict
        Metric dictionary with keys: value_float, value_json, confidence
    seq : int
        Sequence number for title
    chip_name : str
        Chip name (e.g., "Alisson81")
    output_file : Path
        Output file path for PNG
    config : PlotConfig, optional
        Plot configuration (uses defaults if None)
    """
    if config is None:
        config = PlotConfig()
    # Extract data
    if "t (s)" not in measurement.columns or "I (A)" not in measurement.columns:
        raise ValueError("Missing required columns: t (s) and/or I (A)")

    time_full = measurement["t (s)"].to_numpy()
    current_full = measurement["I (A)"].to_numpy()

    # Skip first point (problematic measurement artifact)
    # This matches what the extractor does during fitting
    time = time_full[1:]
    current = current_full[1:]

    # Parse fit details from JSON
    try:
        details = json.loads(metric["value_json"])
    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Failed to parse metric JSON: {e}")

    # Extract fit parameters
    tau = details.get("tau")
    beta = details.get("beta")
    amplitude = details.get("amplitude")
    baseline = details.get("baseline")
    r_squared = details.get("r_squared")
    confidence = metric.get("confidence", 0.0)
    segment_start = details.get("segment_start", 0.0)
    segment_end = details.get("segment_end", time[-1])
    segment_type = details.get("segment_type", "unknown")
    n_points = details.get("n_points_fitted", 0)
    n_iterations = details.get("n_iterations", 0)

    # Create figure
    fig, ax = plt.subplots(figsize=config.figsize_timeseries)

    # Plot raw data
    ax.plot(time, current * 1e6, 'o', ms=4, alpha=0.4,
           color='lightgray', label='Measured', zorder=1)

    # Highlight fitted segment
    segment_mask = (time >= segment_start) & (time <= segment_end)
    if np.any(segment_mask):
        ax.plot(time[segment_mask], current[segment_mask] * 1e6,
               'o', ms=5, color='C0', alpha=0.7, label='Fitted segment', zorder=2)

    # Plot fit curve
    if tau is not None and beta is not None and amplitude is not None and baseline is not None:
        # Generate fit curve for the segment
        t_fit_segment = time[segment_mask] - segment_start  # Reset to t=0
        i_fit = stretched_exponential(t_fit_segment, baseline, amplitude, tau, beta)

        # Map back to original time
        ax.plot(time[segment_mask], i_fit * 1e6,
               '-', lw=3, color='red', label='Stretched exponential fit', zorder=10)

    # Add fit parameters as text box
    param_text = (
        f"[b]Fit Parameters[/b]\n"
        f"τ = {tau:.2f} s\n"
        f"β = {beta:.3f}\n"
        f"Amplitude = {amplitude*1e6:.3f} μA\n"
        f"Baseline = {baseline*1e6:.3f} μA\n"
        f"\n"
        f"[b]Quality Metrics[/b]\n"
        f"R² = {r_squared:.4f}\n"
        f"Confidence = {confidence:.2f}\n"
        f"Iterations = {n_iterations}\n"
        f"\n"
        f"[b]Segment Info[/b]\n"
        f"Type: {segment_type}\n"
        f"Points: {n_points}\n"
        f"Duration: {segment_end - segment_start:.1f} s"
    )

    # Convert markdown-style bold to plain text for matplotlib
    param_text_plain = param_text.replace("[b]", "").replace("[/b]", "")

    ax.text(0.98, 0.97, param_text_plain,
           transform=ax.transAxes,
           verticalalignment='top',
           horizontalalignment='right',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9, pad=0.8),
           family='monospace')

    # Labels and title
    ax.set_xlabel("Time (s)", fontweight='bold')
    ax.set_ylabel("Current (μA)", fontweight='bold')
    ax.set_title(
        f"{chip_name} - seq {seq} - It Relaxation Fit",
        fontweight='bold',
        pad=15
    )
    ax.legend(loc='upper left', framealpha=0.9)

    # Add experiment metadata at bottom
    # Note: metadata columns are single-valued (repeated for all rows in parquet)
    date_local = "Unknown"
    vg = None

    if "date_local" in measurement.columns:
        date_vals = measurement["date_local"].unique().to_list()
        if len(date_vals) > 0 and date_vals[0] is not None:
            date_local = str(date_vals[0])

    if "vg_fixed_v" in measurement.columns:
        vg_vals = measurement["vg_fixed_v"].unique().to_list()
        if len(vg_vals) > 0 and vg_vals[0] is not None:
            vg = float(vg_vals[0])

    metadata_text = f"Date: {date_local}"
    if vg is not None:
        metadata_text += f"  |  Vg = {vg:.2f} V"

    ax.text(0.02, -0.12, metadata_text,
           transform=ax.transAxes,
           color='gray',
           verticalalignment='top')

    plt.tight_layout()
    fig.savefig(output_file, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)


def plot_single_its_relaxation_fit(
    measurement: pl.DataFrame,
    metric: dict,
    seq: Optional[int] = None,
    ax: Optional[plt.Axes] = None,
    config: Optional[PlotConfig] = None
) -> plt.Axes:
    """
    Plot a single It measurement with fitted relaxation curve on existing axes.

    This is a helper function for creating single-panel plots or
    integrating into larger multi-panel figures.

    Parameters
    ----------
    measurement : pl.DataFrame
        Measurement data with columns: t (s), I (A), VL (V)
    metric : dict
        Metric dictionary with keys: value_float, value_json, confidence
    seq : int, optional
        Sequence number for title
    ax : plt.Axes, optional
        Matplotlib axes to plot on. If None, creates new figure.
    config : PlotConfig, optional
        Plot configuration (uses defaults if None)

    Returns
    -------
    plt.Axes
        Axes with plot
    """
    if config is None:
        config = PlotConfig()
    if ax is None:
        fig, ax = plt.subplots(figsize=config.figsize_timeseries)

    # Extract data
    time_full = measurement["t (s)"].to_numpy()
    current_full = measurement["I (A)"].to_numpy()

    # Skip first point (problematic measurement artifact)
    time = time_full[1:]
    current = current_full[1:]

    # Parse fit details
    details = json.loads(metric["value_json"])
    tau = details.get("tau")
    beta = details.get("beta")
    amplitude = details.get("amplitude")
    baseline = details.get("baseline")
    r_squared = details.get("r_squared")
    confidence = metric.get("confidence", 0.0)
    segment_start = details.get("segment_start", 0.0)
    segment_end = details.get("segment_end", time_full[-1])  # Use full array for end check
    segment_type = details.get("segment_type", "unknown")

    # Plot raw data
    ax.plot(time, current * 1e6, 'o', ms=3, alpha=0.5,
           color='gray', label='Measured')

    # Highlight fitted segment
    segment_mask = (time >= segment_start) & (time <= segment_end)
    if np.any(segment_mask):
        ax.plot(time[segment_mask], current[segment_mask] * 1e6,
               'o', ms=4, color='C0', alpha=0.7, label='Fitted segment')

    # Plot fit curve
    if tau is not None and beta is not None:
        t_fit_segment = time[segment_mask] - segment_start
        i_fit = stretched_exponential(t_fit_segment, baseline, amplitude, tau, beta)
        ax.plot(time[segment_mask], i_fit * 1e6,
               '-', lw=2, color='red', label='Fit', zorder=10)

    # Add fit parameters
    param_text = (
        f"τ = {tau:.2f} s\n"
        f"β = {beta:.3f}\n"
        f"R² = {r_squared:.4f}\n"
        f"Confidence = {confidence:.2f}\n"
        f"Segment: {segment_type}"
    )
    ax.text(0.02, 0.98, param_text,
           transform=ax.transAxes,
           verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
           family='monospace')

    # Labels
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (μA)")
    if seq is not None:
        ax.set_title(f"seq {seq} - It Relaxation Fit", fontweight='bold')
    else:
        ax.set_title("It Relaxation Fit", fontweight='bold')
    ax.legend(loc='upper right')

    return ax
