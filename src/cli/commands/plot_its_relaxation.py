"""Plot ITS relaxation fits command."""

import typer
from pathlib import Path
from typing import Optional

from src.cli.plugin_system import cli_command
from src.cli.context import get_context
from src.cli.cache import load_history_cached
from src.cli.helpers import (
    parse_seq_list,
    generate_plot_tag,
    setup_output_dir,
    validate_experiments_exist,
    display_experiment_list,
    display_plot_settings,
    display_plot_success
)
from src.plotting.its_relaxation_fit import plot_its_relaxation_fits
from src.plotting.plot_utils import print_error, print_warning, print_info
import polars as pl


@cli_command(
    name="plot-its-relaxation",
    group="plotting",
    description="Plot ITS relaxation fits (stretched exponential)"
)
def plot_its_relaxation_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '10,15,20' or '10-20'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all It experiments with relaxation metrics"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Custom tag for output filename (default: auto-generated)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for plots (default: from config)"
    ),
    fit_segment: Optional[str] = typer.Option(
        None,
        "--segment",
        help="Filter by fit segment type: 'light', 'dark', or 'both'"
    ),
    dark_only: bool = typer.Option(
        True,
        "--dark-only/--all",
        help="Only plot truly dark It measurements (no laser illumination). Use --all to include illuminated measurements."
    )
):
    """
    Plot It measurements with stretched exponential relaxation fits.

    Visualizes the quality of relaxation time extraction by showing:
    - Raw current vs time data
    - Highlighted fitted segment
    - Overlaid stretched exponential fit curve
    - Fit parameters (τ, β, R², confidence)

    Examples
    --------
    # Plot specific dark experiments
    plot-its-relaxation 81 --seq 50,51,52

    # Plot all dark It experiments with fits (default)
    plot-its-relaxation 81 --auto

    # Include illuminated measurements too
    plot-its-relaxation 81 --auto --all

    # Filter by segment type
    plot-its-relaxation 81 --auto --segment dark
    """
    ctx = get_context()
    base_dir = Path.cwd()

    # Validate input
    if not auto and seq is None:
        print_error("Either --seq or --auto is required")
        raise typer.Exit(1)

    # Setup output directory
    output_dir = setup_output_dir(output_dir, base_dir)

    # Load chip history
    chip_name = f"{chip_group}{chip_number}"
    try:
        history = load_history_cached(
            base_dir / "data/02_stage/chip_histories" / f"{chip_name}_history.parquet"
        )
    except FileNotFoundError:
        print_error(f"Chip history not found for {chip_name}")
        ctx.print("[yellow]Run: [cyan]build-all-histories[/cyan] to generate chip histories[/yellow]")
        raise typer.Exit(1)

    # Filter to It procedures
    its_experiments = history.filter(pl.col("proc") == "It")

    if its_experiments.height == 0:
        print_error(f"No It experiments found for chip {chip_name}")
        raise typer.Exit(1)

    # Filter for dark-only measurements if requested (default behavior)
    if dark_only:
        # Filter by has_light == false or laser_voltage_v == 0.0
        if "has_light" in its_experiments.columns:
            dark_its = its_experiments.filter(pl.col("has_light") == False)
        elif "laser_voltage_v" in its_experiments.columns:
            dark_its = its_experiments.filter(
                (pl.col("laser_voltage_v") == 0.0) | pl.col("laser_voltage_v").is_null()
            )
        else:
            print_warning("Cannot determine light/dark status - plotting all It measurements")
            dark_its = its_experiments

        if dark_its.height == 0:
            print_error(f"No dark It experiments found for chip {chip_name}")
            ctx.print("[yellow]Hint: Use --all to include illuminated measurements[/yellow]")
            raise typer.Exit(1)

        print_info(f"Filtered to {dark_its.height} dark-only measurements (out of {its_experiments.height} total It)")
        its_experiments = dark_its

    # Load metrics
    metrics_path = base_dir / "data/03_derived/_metrics/metrics.parquet"
    if not metrics_path.exists():
        print_error(f"Metrics file not found: {metrics_path}")
        ctx.print("[yellow]Run: [cyan]derive-all-metrics[/cyan] to extract relaxation times[/yellow]")
        raise typer.Exit(1)

    try:
        all_metrics = pl.read_parquet(metrics_path)
    except Exception as e:
        print_error(f"Failed to load metrics: {e}")
        raise typer.Exit(1)

    # Filter to relaxation_time metrics
    relaxation_metrics = all_metrics.filter(
        (pl.col("metric_name") == "relaxation_time") &
        (pl.col("chip_number") == chip_number) &
        (pl.col("chip_group") == chip_group)
    )

    if relaxation_metrics.height == 0:
        print_error(f"No relaxation metrics found for chip {chip_name}")
        ctx.print("[yellow]Run: [cyan]derive-all-metrics[/cyan] to extract relaxation times[/yellow]")
        raise typer.Exit(1)

    # Match metrics to experiments by run_id
    # Add run_id to history if needed (join with manifest or use existing)
    if "run_id" not in its_experiments.columns:
        print_error("History missing run_id column - cannot match metrics")
        ctx.print("[yellow]Rebuild history with: [cyan]build-all-histories --force[/cyan][/yellow]")
        raise typer.Exit(1)

    # Filter experiments to those with metrics
    experiments_with_metrics = its_experiments.filter(
        pl.col("run_id").is_in(relaxation_metrics["run_id"])
    )

    if experiments_with_metrics.height == 0:
        print_error("No It experiments have relaxation metrics")
        ctx.print(f"[yellow]Found {its_experiments.height} It experiments, but none have metrics[/yellow]")
        ctx.print("[yellow]Try running: [cyan]derive-all-metrics --procedures It[/cyan][/yellow]")
        raise typer.Exit(1)

    # Apply segment filter if specified
    if fit_segment is not None:
        import json
        filtered_run_ids = []
        for metric_row in relaxation_metrics.iter_rows(named=True):
            try:
                details = json.loads(metric_row["value_json"])
                segment_type = details.get("segment_type")
                if segment_type == fit_segment or fit_segment == "both":
                    filtered_run_ids.append(metric_row["run_id"])
            except (json.JSONDecodeError, KeyError):
                continue

        if not filtered_run_ids:
            print_error(f"No experiments with segment_type='{fit_segment}'")
            raise typer.Exit(1)

        experiments_with_metrics = experiments_with_metrics.filter(
            pl.col("run_id").is_in(filtered_run_ids)
        )
        relaxation_metrics = relaxation_metrics.filter(
            pl.col("run_id").is_in(filtered_run_ids)
        )

    # Select experiments
    if auto:
        # Use all experiments with metrics
        selected = experiments_with_metrics
        print_info(f"Auto-selected {selected.height} It experiments with relaxation fits")
    else:
        # Parse seq list
        seq_list = parse_seq_list(seq)

        # Validate all requested seq numbers exist
        ctx.print("\n[cyan]Validating experiments...[/cyan]")
        valid, errors = validate_experiments_exist(
            seq_list,
            chip_number,
            chip_group
        )

        if not valid:
            for error in errors:
                print_error(error)
            raise typer.Exit(1)

        # Filter by seq
        selected = experiments_with_metrics.filter(
            pl.col("seq").is_in(seq_list)
        )

    # Filter metrics to selected experiments
    selected_metrics = relaxation_metrics.filter(
        pl.col("run_id").is_in(selected["run_id"])
    )

    # Display experiment list
    ctx.print()
    display_experiment_list(
        selected,
        title=f"It Relaxation Fits - {chip_name}"
    )

    # Display settings
    settings = {
        "Chip": chip_name,
        "Experiments": f"{selected.height} It measurements",
        "Metrics": f"{selected_metrics.height} relaxation fits",
        "Output": str(output_dir)
    }
    if fit_segment:
        settings["Segment filter"] = fit_segment

    display_plot_settings(settings)

    # Generate tag
    if tag is None:
        if auto:
            tag = f"{chip_name}_It_relaxation_all"
        else:
            tag = f"{chip_name}_It_relaxation_{generate_plot_tag(seq_list)}"

    # Generate plot
    try:
        output_file = plot_its_relaxation_fits(
            df=selected,
            metrics_df=selected_metrics,
            base_dir=base_dir,
            tag=tag
        )

        # Display success
        display_plot_success(output_file)

    except Exception as e:
        print_error(f"Failed to generate plot: {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)
