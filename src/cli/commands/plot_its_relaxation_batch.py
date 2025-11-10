"""Batch ITS relaxation fit plotting - generates individual PNG per experiment."""

import typer
from pathlib import Path
from typing import Optional

from src.cli.plugin_system import cli_command
from src.cli.context import get_context
from src.cli.cache import load_history_cached
from src.cli.helpers import parse_seq_list
from src.plotting.its_relaxation_individual import generate_individual_relaxation_plots
from src.plotting.plot_utils import print_error, print_warning, print_info
import polars as pl


@cli_command(
    name="plot-its-relaxation-batch",
    group="plotting",
    description="Generate individual PNG plots for each It relaxation fit",
    aliases=["batch-its-relaxation"]
)
def plot_its_relaxation_batch_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '10,15,20' or '10-20'). If not provided, processes all It experiments with metrics."
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    output_subdir: Optional[str] = typer.Option(
        None,
        "--subdir",
        help="Custom subdirectory name under plots/its_relaxation_fits/ (default: <chip_name>_individual)"
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
    Generate individual PNG files for each It measurement with relaxation fit.

    This command creates one plot per experiment, making it ideal for:
    - Batch processing and automation
    - Report generation
    - Detailed per-experiment analysis
    - Archive/documentation purposes

    Each plot is saved with a descriptive filename:
        <chip_name>_seq<NNN>_It_relaxation.png

    Examples
    --------
    # Generate plots for all dark It measurements (default)
    plot-its-relaxation-batch 81

    # Include illuminated measurements too
    plot-its-relaxation-batch 81 --all

    # Generate plots for specific experiments (dark only)
    plot-its-relaxation-batch 81 --seq 19,20,40,41,42,50

    # Use custom output subdirectory
    plot-its-relaxation-batch 81 --subdir "2025_analysis"

    # Filter by segment type
    plot-its-relaxation-batch 81 --segment dark
    """
    ctx = get_context()
    base_dir = Path.cwd()

    # Setup output directory
    if output_dir is None:
        output_dir = base_dir

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
    if seq is not None:
        # Parse seq list
        seq_list = parse_seq_list(seq)

        # Filter by seq
        selected = experiments_with_metrics.filter(
            pl.col("seq").is_in(seq_list)
        )

        if selected.height == 0:
            print_error(f"No experiments found with seq numbers: {seq}")
            raise typer.Exit(1)

        # Warn if some seq numbers not found
        found_seqs = set(selected["seq"].to_list())
        missing_seqs = set(seq_list) - found_seqs
        if missing_seqs:
            print_warning(f"Some seq numbers not found or missing metrics: {sorted(missing_seqs)}")
    else:
        # Use all experiments with metrics
        selected = experiments_with_metrics
        print_info(f"Processing all {selected.height} It experiments with relaxation fits")

    # Filter metrics to selected experiments
    selected_metrics = relaxation_metrics.filter(
        pl.col("run_id").is_in(selected["run_id"])
    )

    # Display summary
    ctx.print()
    ctx.print(f"[cyan]═══════════════════════════════════════════════════════════[/cyan]")
    ctx.print(f"[bold cyan]  Batch ITS Relaxation Fit Generation - {chip_name}[/bold cyan]")
    ctx.print(f"[cyan]═══════════════════════════════════════════════════════════[/cyan]")
    ctx.print()
    ctx.print(f"[bold]Chip:[/bold] {chip_name}")
    ctx.print(f"[bold]Experiments:[/bold] {selected.height} It measurements")
    if dark_only:
        ctx.print(f"[bold]Filter:[/bold] Dark-only (no laser illumination)")
    ctx.print(f"[bold]Metrics:[/bold] {selected_metrics.height} relaxation fits")

    # Determine output subdirectory
    if output_subdir is None:
        output_subdir = f"{chip_name}_individual"

    ctx.print(f"[bold]Output:[/bold] plots/its_relaxation_fits/{output_subdir}/")
    if fit_segment:
        ctx.print(f"[bold]Segment filter:[/bold] {fit_segment}")
    ctx.print()

    # Generate individual plots
    try:
        output_files = generate_individual_relaxation_plots(
            df=selected,
            metrics_df=selected_metrics,
            base_dir=output_dir,
            output_subdir=output_subdir
        )

        # Display success summary
        ctx.print()
        ctx.print(f"[green]✓ Successfully generated {len(output_files)} individual plots![/green]")
        ctx.print()
        ctx.print(f"[bold]Output directory:[/bold]")
        if len(output_files) > 0:
            output_dir_path = output_files[0].parent
            ctx.print(f"  {output_dir_path}")
            ctx.print()
            ctx.print(f"[bold]Example files:[/bold]")
            for f in output_files[:5]:
                ctx.print(f"  • {f.name}")
            if len(output_files) > 5:
                ctx.print(f"  ... and {len(output_files) - 5} more")
        ctx.print()

    except Exception as e:
        print_error(f"Failed to generate plots: {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)
