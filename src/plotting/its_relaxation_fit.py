"""ITS relaxation fit visualization.

Plots dark It measurements with overlaid stretched exponential fits
to visualize the quality of relaxation time extraction.
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import polars as pl
import json
from typing import Optional, Dict, Any

from src.core.utils import read_measurement_parquet
from src.derived.algorithms import stretched_exponential
from src.plotting.plot_utils import (
    print_info,
    print_warning,
    print_error
)
from src.plotting.config import PlotConfig


def plot_its_relaxation_fits(
    df: pl.DataFrame,
    metrics_df: pl.DataFrame,
    base_dir: Path,
    tag: str,
    config: Optional[PlotConfig] = None
) -> Path:
    """
    Plot It measurements with stretched exponential fits.

    Creates a multi-panel plot showing:
    - Raw current vs time data
    - Fitted segment highlighted
    - Stretched exponential fit curve overlaid
    - Fit parameters displayed (τ, β, R², confidence)

    Parameters
    ----------
    df : pl.DataFrame
        Filtered history DataFrame containing It experiments to plot
        Must have columns: seq, parquet_path, proc
    metrics_df : pl.DataFrame
        Metrics DataFrame filtered to relaxation_time metrics for these experiments
        Must have columns: run_id, value_float, value_json
    base_dir : Path
        Project base directory
    tag : str
        Tag for output filename
    config : PlotConfig, optional
        Plot configuration (uses defaults if None)

    Returns
    -------
    Path
        Path to generated figure

    Examples
    --------
    >>> # Load history and metrics
    >>> history = pl.read_parquet("data/02_stage/chip_histories/Alisson67_history.parquet")
    >>> metrics = pl.read_parquet("data/03_derived/_metrics/metrics.parquet")
    >>>
    >>> # Filter to It experiments
    >>> its_exps = history.filter(pl.col("proc") == "It")
    >>> its_metrics = metrics.filter(
    ...     (pl.col("metric_name") == "relaxation_time") &
    ...     (pl.col("run_id").is_in(its_exps["run_id"]))
    ... )
    >>>
    >>> # Plot
    >>> plot_its_relaxation_fits(its_exps, its_metrics, Path("."), "Alisson67_It_fits")
    """
    if config is None:
        config = PlotConfig()

    # Validate inputs
    if df.height == 0:
        print_error("No experiments to plot")
        raise ValueError("Empty experiment DataFrame")

    if metrics_df.height == 0:
        print_warning("No relaxation metrics found - cannot plot fits")
        raise ValueError("No relaxation metrics available")

    # Extract chip number if available in df
    chip_number = None
    if "chip_number" in df.columns:
        chip_number = int(df["chip_number"][0])

    # Get output path using PlotConfig with special subcategory for relaxation fits
    filename = f"{tag}"
    output_file = config.get_output_path(
        filename,
        chip_number=chip_number,
        procedure="It",
        special_type="relaxation_fits",  # Special analysis subcategory
        create_dirs=True
    )

    # Determine layout
    n_experiments = df.height
    n_cols = min(2, n_experiments)  # Max 2 columns
    n_rows = (n_experiments + n_cols - 1) // n_cols

    # Create figure
    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(7 * n_cols, 5 * n_rows),
        squeeze=False
    )
    axes = axes.flatten()

    # Match metrics to experiments by run_id
    # Create mapping: run_id -> metric_row
    metrics_map = {}
    for metric_row in metrics_df.iter_rows(named=True):
        metrics_map[metric_row["run_id"]] = metric_row

    # Plot each experiment
    for idx, exp_row in enumerate(df.iter_rows(named=True)):
        ax = axes[idx]

        run_id = exp_row.get("run_id")
        seq = exp_row.get("seq", "?")
        parquet_path = Path(exp_row["parquet_path"])

        # Load measurement data
        try:
            measurement = read_measurement_parquet(parquet_path)
        except Exception as e:
            print_warning(f"seq {seq}: Failed to load measurement: {e}")
            ax.text(0.5, 0.5, f"seq {seq}\nFailed to load data",
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_axis_off()
            continue

        # Get metric for this experiment
        metric = metrics_map.get(run_id)
        if metric is None:
            print_warning(f"seq {seq}: No relaxation metric found")
            ax.text(0.5, 0.5, f"seq {seq}\nNo metric found",
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_axis_off()
            continue

        # Extract data
        if "t (s)" not in measurement.columns or "I (A)" not in measurement.columns:
            print_warning(f"seq {seq}: Missing required columns")
            ax.set_axis_off()
            continue

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
            print_warning(f"seq {seq}: Failed to parse metric JSON: {e}")
            ax.set_axis_off()
            continue

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
            # Generate fit curve for the segment
            t_fit_segment = time[segment_mask] - segment_start  # Reset to t=0
            i_fit = stretched_exponential(t_fit_segment, baseline, amplitude, tau, beta)

            # Map back to original time
            ax.plot(time[segment_mask], i_fit * 1e6,
                   '-', lw=2, color='red', label='Fit', zorder=10)

        # Add fit parameters as text
        param_text = (
            f"τ = {tau:.2f} s\n"
            f"β = {beta:.3f}\n"
            f"R² = {r_squared:.4f}\n"
            f"Conf. = {confidence:.2f}\n"
            f"Segment: {segment_type}"
        )
        ax.text(0.02, 0.98, param_text,
               transform=ax.transAxes,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
               fontsize=9, family='monospace')

        # Labels and title
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Current (μA)")
        ax.set_title(f"seq {seq}", fontsize=11, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        

    # Hide unused subplots
    for idx in range(n_experiments, len(axes)):
        axes[idx].set_axis_off()

    # Overall title
    chip_name = df["chip_group"][0] + str(df["chip_number"][0]) if df.height > 0 else "?"
    fig.suptitle(
        f"{chip_name} - It Relaxation Fits ({n_experiments} measurements)",
        fontsize=14, fontweight='bold', y=0.995
    )

    plt.tight_layout()
    fig.savefig(output_file, dpi=config.dpi, bbox_inches='tight')
    plt.close(fig)

    print_info(f"Saved relaxation fit plot: {output_file}")
    return output_file


def plot_single_its_relaxation_fit(
    measurement: pl.DataFrame,
    metric: Dict[str, Any],
    seq: Optional[int] = None,
    ax: Optional[plt.Axes] = None
) -> plt.Axes:
    """
    Plot a single It measurement with fitted relaxation curve.

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

    Returns
    -------
    plt.Axes
        Axes with plot
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))

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
    segment_end = details.get("segment_end", time[-1])
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
           fontsize=9, family='monospace')

    # Labels
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Current (μA)")
    if seq is not None:
        ax.set_title(f"seq {seq} - It Relaxation Fit", fontsize=11, fontweight='bold')
    else:
        ax.set_title("It Relaxation Fit", fontsize=11, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)

    return ax
