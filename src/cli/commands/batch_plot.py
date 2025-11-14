"""
Batch plot command for executing multiple plots from YAML configuration.

This command provides optimized batch plotting with:
- Single process execution (eliminates subprocess overhead)
- Cached chip history loading (load once, reuse for all plots)
- Optional parallelization for large batches
- Integrated data caching for Parquet files

Performance:
- Sequential: 3-5x faster than subprocess execution (best for <10 plots)
- Parallel: 10-15x faster for large batches (>10 plots, 4+ cores)
"""

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.plugin_system import cli_command
from src.plotting.batch import (
    load_batch_config,
    execute_sequential,
    execute_parallel,
    display_summary,
    print_cache_stats,
    CACHE_AVAILABLE,
)


console = Console()


@cli_command(
    name="batch-plot",
    group="plotting",
    description="Execute batch plot generation from YAML configuration",
)
def batch_plot_command(
    config_file: Path = typer.Argument(
        ...,
        help="YAML configuration file (e.g., config/batch_plots/alisson67_plots.yaml)",
        exists=True,
        dir_okay=False,
    ),
    parallel: Optional[int] = typer.Option(
        None,
        "--parallel",
        "-p",
        help="Number of parallel workers (default: sequential). Recommended: 2-4 for CPUs with 4+ cores",
        min=1,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be executed without running",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed execution information",
    ),
):
    """
    Execute batch plot generation from YAML configuration.

    This command reads a YAML file specifying multiple plots to generate and
    executes them efficiently in a single process with optional parallelization.

    YAML Configuration Format:
        chip: 67
        chip_group: "Alisson"
        defaults:
          legend_by: irradiated_power
        plots:
          - type: plot-its
            seq: "4-7"
            tag: "405nm_neg_gate"
          - type: plot-ivg
            seq: 2

    PERFORMANCE TIPS:
      - Sequential mode is fastest for <10 plots (less overhead)
      - Parallel mode is fastest for >10 plots with 4+ core CPU
      - Use --parallel 2-4 on typical laptop/desktop
      - Avoid --parallel > CPU cores (diminishing returns)

    Examples:
        # Sequential execution (best for small batches)
        python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml

        # Parallel execution with 4 workers (best for large batches)
        python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --parallel 4

        # Preview what will be executed
        python3 process_and_analyze.py batch-plot config/batch_plots/alisson67_plots.yaml --dry-run

    See Also:
        - config/batch_plots/ for example configurations
        - docs/BATCH_PLOTTING_GUIDE.md for detailed documentation
    """
    # Load configuration
    console.print(
        Panel(
            f"[cyan]Loading configuration from:[/cyan] {config_file}",
            title="Batch Plot Processor",
            border_style="cyan",
        )
    )

    try:
        chip, chip_group, plot_specs = load_batch_config(config_file)
    except Exception as e:
        console.print(f"[red]Error loading configuration:[/red] {e}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Loaded {len(plot_specs)} plot specifications for {chip_group}{chip}\n")

    # Dry run mode
    if dry_run:
        console.print("[yellow]DRY RUN - Plots that would be generated:[/yellow]\n")
        for i, spec in enumerate(plot_specs, 1):
            console.print(f"{i:3d}. {spec}")
        console.print(f"\n[dim]Total: {len(plot_specs)} plots[/dim]")
        return

    # Display execution mode
    console.print(f"[cyan]Execution mode:[/cyan] {'Parallel' if parallel else 'Sequential'}")
    if parallel:
        console.print(f"[cyan]Workers:[/cyan] {parallel}")
    if CACHE_AVAILABLE:
        console.print(f"[cyan]Caching:[/cyan] Enabled (automatic)")
    console.print()

    # Execute plots
    start_time = time.time()

    try:
        if parallel and parallel > 1:
            results = execute_parallel(plot_specs, chip_group, parallel)
        else:
            results = execute_sequential(plot_specs, chip_group)
    except Exception as e:
        console.print(f"[red]Error during batch execution:[/red] {e}")
        raise typer.Exit(1)

    total_time = time.time() - start_time

    # Display summary
    display_summary(results, total_time, parallel)

    # Display cache statistics if caching is available
    # Note: Stats only meaningful in sequential mode (parallel workers have separate caches)
    if CACHE_AVAILABLE and (not parallel or parallel <= 1):
        print_cache_stats()
    elif CACHE_AVAILABLE and parallel and parallel > 1:
        console.print(
            "\n[dim]Note: Cache statistics not available in parallel mode "
            "(each worker has separate cache)[/dim]"
        )

    # Exit with error code if any plots failed
    failed_count = sum(1 for r in results if not r.success)
    if failed_count > 0:
        raise typer.Exit(1)
