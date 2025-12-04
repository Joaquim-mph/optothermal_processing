"""Plotting for consecutive IVg/VVg sweep differences.

This module generates plots showing differences between consecutive gate voltage sweeps,
useful for tracking device evolution after treatments (e.g., illumination).
"""

from __future__ import annotations
import polars as pl
import numpy as np
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

from src.plotting.config import PlotConfig
from src.plotting.styles import set_plot_style


def plot_consecutive_sweep_differences(
    chip_number: int,
    chip_group: str = "Alisson",
    metrics_path: Optional[Path] = None,
    procedure: Optional[str] = None,
    output_dir: Optional[Path] = None,
    show_resistance: bool = True,
    plot_individual: bool = True,
    plot_summary: bool = True,
    tag: Optional[str] = None
) -> List[Path]:
    """
    Generate plots for all consecutive sweep differences for a chip.

    Creates:
    --------
    1. Individual plots for each pair (ΔI or ΔV vs Vg)
    2. Summary plot showing all differences overlaid
    3. Optional resistance difference plots (ΔR vs Vg)

    Parameters
    ----------
    chip_number : int
        Chip number
    chip_group : str
        Chip group prefix (default: "Alisson")
    metrics_path : Optional[Path]
        Path to metrics.parquet. If None, uses default location.
    procedure : Optional[str]
        Filter to specific procedure ("IVg" or "VVg"). If None, plots both.
    output_dir : Optional[Path]
        Output directory. If None, uses PlotConfig default.
    show_resistance : bool
        Include resistance difference plots (default: True)
    plot_individual : bool
        Generate individual plots for each pair (default: True)
    plot_summary : bool
        Generate summary overlay plot (default: True)
    tag : Optional[str]
        Optional tag for output filenames

    Returns
    -------
    List[Path]
        List of generated plot file paths

    Examples
    --------
    >>> # Plot all IVg differences for chip 67
    >>> plot_consecutive_sweep_differences(67, procedure="IVg")

    >>> # Plot both IVg and VVg differences
    >>> plot_consecutive_sweep_differences(67)

    >>> # Only summary plot, no individual plots
    >>> plot_consecutive_sweep_differences(67, plot_individual=False)
    """
    # Apply science style
    set_plot_style("prism_rain")

    # Load metrics
    if metrics_path is None:
        metrics_path = Path("data/03_derived/_metrics/metrics.parquet")

    if not metrics_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {metrics_path}")

    metrics = pl.read_parquet(metrics_path)

    # Filter to consecutive sweep differences for this chip
    pairwise = metrics.filter(
        (pl.col("metric_name") == "consecutive_sweep_difference") &
        (pl.col("chip_number") == chip_number)
    )

    if procedure is not None:
        pairwise = pairwise.filter(pl.col("procedure") == procedure)

    if pairwise.height == 0:
        raise ValueError(
            f"No consecutive sweep differences found for chip {chip_number}"
            + (f" ({procedure})" if procedure else "")
        )

    print(f"Found {pairwise.height} consecutive sweep differences for {chip_group}{chip_number}")

    # Setup PlotConfig
    config = PlotConfig(base_dir=output_dir or Path("."))

    # Group by procedure
    procedures_found = pairwise["procedure"].unique().to_list()
    print(f"Procedures: {', '.join(procedures_found)}")

    generated_plots = []

    for proc in procedures_found:
        proc_metrics = pairwise.filter(pl.col("procedure") == proc)

        print(f"\n{proc}: {proc_metrics.height} pairs")

        # Generate individual plots
        if plot_individual:
            individual_plots = _plot_individual_differences(
                proc_metrics, chip_number, chip_group, proc, config, show_resistance, tag
            )
            generated_plots.extend(individual_plots)

        # Generate summary plot
        if plot_summary:
            summary_plot = _plot_summary_differences(
                proc_metrics, chip_number, chip_group, proc, config, show_resistance, tag
            )
            if summary_plot:
                generated_plots.append(summary_plot)

    print(f"\n✓ Generated {len(generated_plots)} plots")
    return generated_plots


def _plot_individual_differences(
    metrics: pl.DataFrame,
    chip_number: int,
    chip_group: str,
    procedure: str,
    config: PlotConfig,
    show_resistance: bool,
    tag: Optional[str]
) -> List[Path]:
    """Generate individual plots for each consecutive pair."""

    plots = []

    for row in metrics.iter_rows(named=True):
        details = json.loads(row["value_json"])

        seq_1 = details["seq_1"]
        seq_2 = details["seq_2"]

        # Extract arrays
        vg = np.array(details["vg_array"])

        if procedure == "IVg":
            delta_y = np.array(details["delta_i_array"])
            y_label = "ΔI"
            y_unit = "A"
            y_scale = 1e6  # Convert to µA
            y_unit_plot = "µA"
        else:  # VVg
            delta_y = np.array(details["delta_vds_array"])
            y_label = "ΔVds"
            y_unit = "V"
            y_scale = 1e3  # Convert to mV
            y_unit_plot = "mV"

        # Create figure
        if show_resistance and "delta_resistance_array" in details:
            fig = plt.figure(figsize=(12, 5))
            gs = GridSpec(1, 2, figure=fig, wspace=0.3)
            ax1 = fig.add_subplot(gs[0])
            ax2 = fig.add_subplot(gs[0, 1])
        else:
            fig, ax1 = plt.subplots(figsize=(10, 6))
            ax2 = None

        # Plot ΔI or ΔV
        ax1.plot(vg, delta_y * y_scale, 'b-', linewidth=2)
        ax1.axhline(0, color='k', linestyle='--', linewidth=1, alpha=0.5)
        ax1.set_xlabel("Gate Voltage (V)", fontsize=14)
        ax1.set_ylabel(f"{y_label} ({y_unit_plot})", fontsize=14)
        ax1.set_title(
            f"{procedure} Difference: Seq {seq_1} → {seq_2}\n"
            f"{chip_group}{chip_number}",
            fontsize=16
        )

        # Add CNP shift annotation if available
        if details.get("delta_cnp") is not None:
            delta_cnp = details["delta_cnp"]
            ax1.text(
                0.02, 0.98,
                f"ΔCNP = {delta_cnp:+.3f} V",
                transform=ax1.transAxes,
                fontsize=12,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            )

        # Plot ΔR if requested
        if ax2 is not None and "delta_resistance_array" in details:
            delta_r = np.array(details["delta_resistance_array"])

            # Handle inf/nan values
            finite_mask = np.isfinite(delta_r)
            vg_finite = vg[finite_mask]
            delta_r_finite = delta_r[finite_mask]

            if len(vg_finite) > 0:
                # Auto-scale resistance
                max_r = np.max(np.abs(delta_r_finite))
                if max_r > 1e6:  # MΩ
                    r_scale = 1e-6
                    r_unit = "MΩ"
                elif max_r > 1e3:  # kΩ
                    r_scale = 1e-3
                    r_unit = "kΩ"
                else:  # Ω
                    r_scale = 1.0
                    r_unit = "Ω"

                ax2.plot(vg_finite, delta_r_finite * r_scale, 'r-', linewidth=2)
                ax2.axhline(0, color='k', linestyle='--', linewidth=1, alpha=0.5)
                ax2.set_xlabel("Gate Voltage (V)", fontsize=14)
                ax2.set_ylabel(f"ΔR ({r_unit})", fontsize=14)
                ax2.set_title("Resistance Difference", fontsize=16)

        plt.tight_layout()

        # Save plot
        pair_tag = f"seq{seq_1}_to_{seq_2}"
        if tag:
            pair_tag = f"{tag}_{pair_tag}"

        output_path = config.get_output_path(
            chip_number=chip_number,
            chip_group=chip_group,
            procedure=procedure,
            plot_type="ConsecutiveSweepDiff",
            tag=pair_tag,
            create_dirs=True
        )

        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)

        plots.append(output_path)
        print(f"  ✓ Seq {seq_1}→{seq_2}: {output_path.name}")

    return plots


def _plot_summary_differences(
    metrics: pl.DataFrame,
    chip_number: int,
    chip_group: str,
    procedure: str,
    config: PlotConfig,
    show_resistance: bool,
    tag: Optional[str]
) -> Optional[Path]:
    """Generate summary plot with all differences overlaid."""

    if metrics.height == 0:
        return None

    # Create figure
    if show_resistance:
        fig = plt.figure(figsize=(14, 6))
        gs = GridSpec(1, 2, figure=fig, wspace=0.3)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[0, 1])
    else:
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax2 = None

    # Determine units
    if procedure == "IVg":
        y_label = "ΔI"
        y_scale = 1e6
        y_unit_plot = "µA"
    else:  # VVg
        y_label = "ΔVds"
        y_scale = 1e3
        y_unit_plot = "mV"

    # Color map for different pairs
    colors = plt.cm.viridis(np.linspace(0, 0.9, metrics.height))

    # Plot all pairs
    for idx, row in enumerate(metrics.iter_rows(named=True)):
        details = json.loads(row["value_json"])

        seq_1 = details["seq_1"]
        seq_2 = details["seq_2"]
        vg = np.array(details["vg_array"])

        if procedure == "IVg":
            delta_y = np.array(details["delta_i_array"])
        else:
            delta_y = np.array(details["delta_vds_array"])

        # Plot ΔI or ΔV
        ax1.plot(
            vg, delta_y * y_scale,
            color=colors[idx],
            linewidth=1.5,
            label=f"Seq {seq_1}→{seq_2}",
            alpha=0.7
        )

        # Plot ΔR if requested
        if ax2 is not None and "delta_resistance_array" in details:
            delta_r = np.array(details["delta_resistance_array"])

            # Handle inf/nan
            finite_mask = np.isfinite(delta_r)
            vg_finite = vg[finite_mask]
            delta_r_finite = delta_r[finite_mask]

            if len(vg_finite) > 0:
                ax2.plot(
                    vg_finite, delta_r_finite,
                    color=colors[idx],
                    linewidth=1.5,
                    label=f"Seq {seq_1}→{seq_2}",
                    alpha=0.7
                )

    # Format main plot
    ax1.axhline(0, color='k', linestyle='--', linewidth=1, alpha=0.5)
    ax1.set_xlabel("Gate Voltage (V)", fontsize=14)
    ax1.set_ylabel(f"{y_label} ({y_unit_plot})", fontsize=14)
    ax1.set_title(
        f"{procedure} Consecutive Differences - {chip_group}{chip_number}\n"
        f"{metrics.height} pairs",
        fontsize=16
    )
    ax1.legend(loc='best', fontsize=10, framealpha=0.9)

    # Format resistance plot
    if ax2 is not None:
        ax2.axhline(0, color='k', linestyle='--', linewidth=1, alpha=0.5)
        ax2.set_xlabel("Gate Voltage (V)", fontsize=14)
        ax2.set_ylabel("ΔR (Ω)", fontsize=14)
        ax2.set_title("Resistance Differences", fontsize=16)
        ax2.legend(loc='best', fontsize=10, framealpha=0.9)

    plt.tight_layout()

    # Save plot
    summary_tag = "summary"
    if tag:
        summary_tag = f"{tag}_{summary_tag}"

    output_path = config.get_output_path(
        chip_number=chip_number,
        chip_group=chip_group,
        procedure=procedure,
        plot_type="ConsecutiveSweepDiff",
        tag=summary_tag,
        create_dirs=True
    )

    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    print(f"  ✓ Summary: {output_path.name}")

    return output_path
