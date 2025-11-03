"""CLI commands for CNP (Dirac point) plotting."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from src.cli.context import get_context
from src.cli.cache import load_history_cached
from rich.panel import Panel

from src.cli.plugin_system import cli_command



@cli_command(
    name="plot-cnp-time",
    group="plotting",
    description="Plot CNP voltage evolution over time"
)
def plot_cnp_time_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 81 for Alisson81)"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for plots (default: figs/)"
    ),
    show_light: bool = typer.Option(
        True,
        "--light/--no-light",
        help="Distinguish light/dark measurements (default: True)"
    ),
    theme: Optional[str] = typer.Option(
        None,
        "--theme",
        help="Plot theme override (prism_rain, paper, presentation, minimal). Overrides global --plot-theme."
    ),
    format: Optional[str] = typer.Option(
        None,
        "--format",
        help="Output format override (png, pdf, svg, jpg). Overrides global --plot-format."
    ),
    dpi: Optional[int] = typer.Option(
        None,
        "--dpi",
        help="DPI override (72-1200). Overrides global --plot-dpi."
    ),
):
    """
    Plot CNP (Charge Neutrality Point / Dirac point) voltage vs time.

    This shows how the Dirac point evolves over the experiment timeline,
    which is useful for tracking:
    - Material degradation
    - Doping changes
    - Device stability
    - Environmental effects

    Requires:
    - CNP metrics extracted (run derive-all-metrics first)
    - IVg measurements in the chip history

    Examples:
        # Plot CNP evolution for chip 81
        python process_and_analyze.py plot-cnp-time 81

        # Save to custom directory
        python process_and_analyze.py plot-cnp-time 81 --output plots/cnp/

        # Don't distinguish light/dark
        python process_and_analyze.py plot-cnp-time 81 --no-light

        # Custom figure size (width, height in inches)
        python process_and_analyze.py plot-cnp-time 81 --figsize 16,8
    """
    ctx = get_context()
    import polars as pl
    from src.plotting.cnp_time import plot_cnp_vs_time

    # Load config
    from src.cli.main import get_config
    config = get_config()

    chip_name = f"{chip_group}{chip_number}"


    # Determine output directory
    if output_dir is None:
        output_dir = ctx.output_dir

    ctx.print()
    ctx.print(Panel.fit(
        f"[bold cyan]CNP vs Time Plot - {chip_name}[/bold cyan]",
        border_style="cyan"
    ))
    ctx.print()

    # Try to load enriched history from Stage 3 (has CNP joined)
    enriched_history_file = config.stage_dir.parent / "03_derived" / "chip_histories_enriched" / f"{chip_name}_history.parquet"
    metrics_file = config.stage_dir.parent / "03_derived" / "_metrics" / "metrics.parquet"

    # Load history with CNP data
    ctx.print("[cyan]Loading chip history and CNP metrics...[/cyan]")

    if enriched_history_file.exists():
        history = pl.read_parquet(enriched_history_file)
    else:
        # Fall back to Stage 2 base history
        history_file = ctx.history_dir / f"{chip_name}_history.parquet"
        if not history_file.exists():
            ctx.print(f"[red]Error:[/red] History file not found: {history_file}")
            ctx.print("[yellow]Hint:[/yellow] Run [cyan]build-all-histories[/cyan] first")
            raise typer.Exit(1)

        history = pl.read_parquet(history_file)

    # Join with CNP metrics if not already joined
    if "cnp_voltage" not in history.columns:
        if not metrics_file.exists():
            ctx.print(f"[red]Error:[/red] No CNP metrics found")
            ctx.print("[yellow]Hint:[/yellow] Run [cyan]derive-all-metrics[/cyan] first to extract CNP values")
            raise typer.Exit(1)

        metrics = pl.read_parquet(metrics_file)

        # Filter metrics for this chip and CNP only
        cnp_metrics = metrics.filter(
            (pl.col("chip_number") == chip_number) &
            (pl.col("chip_group") == chip_group) &
            (pl.col("metric_name") == "cnp_voltage")
        )

        if cnp_metrics.height == 0:
            ctx.print(f"[red]Error:[/red] No CNP data found for {chip_name}")
            ctx.print("[yellow]Hint:[/yellow] Run [cyan]derive-all-metrics[/cyan] first to extract CNP from IVg measurements")
            raise typer.Exit(1)

        # Join CNP to history
        cnp_df = cnp_metrics.select([
            "run_id",
            pl.col("value_float").alias("cnp_voltage")
        ])
        history = history.join(cnp_df, on="run_id", how="left")

    # Check if we have any CNP data
    cnp_count = history.filter(
        (pl.col("proc") == "IVg") &
        (pl.col("cnp_voltage").is_not_null()) &
        (pl.col("cnp_voltage").is_not_nan())
    ).height

    if cnp_count == 0:
        ctx.print(f"[red]Error:[/red] No IVg measurements with CNP data found for {chip_name}")
        ctx.print("[yellow]Hint:[/yellow] This chip needs IVg measurements to calculate CNP")
        raise typer.Exit(1)

    ctx.print(f"[green]✓[/green] Found {cnp_count} IVg measurements with CNP data")

    # Get plot config and apply command-specific overrides
    from src.cli.main import get_plot_config
    plot_config = get_plot_config()

    # Apply command-specific overrides
    plot_overrides = {}
    if theme is not None:
        plot_overrides["theme"] = theme
    if format is not None:
        plot_overrides["format"] = format
    if dpi is not None:
        plot_overrides["dpi"] = dpi

    if plot_overrides:
        plot_config = plot_config.copy(**plot_overrides)
        if ctx.verbose:
            overrides_str = ", ".join([f"{k}={v}" for k, v in plot_overrides.items()])
            ctx.print(f"[dim]Plot config overrides: {overrides_str}[/dim]")

    # Generate plot
    ctx.print("[cyan]Generating CNP vs time plot...[/cyan]")

    try:
        output_file = plot_cnp_vs_time(
            history=history,
            chip_name=chip_name,
            show_light=show_light,
            config=plot_config,
        )

        ctx.print()
        ctx.print(Panel(
            f"[green]✓ Plot saved successfully[/green]\n"
            f"[cyan]Output:[/cyan] {output_file}\n"
            f"[cyan]CNP measurements:[/cyan] {cnp_count}",
            title="[bold]CNP Time Evolution[/bold]",
            border_style="green"
        ))

        # Show CNP statistics
        cnp_data = history.filter(
            (pl.col("proc") == "IVg") &
            (pl.col("cnp_voltage").is_not_null()) &
            (pl.col("cnp_voltage").is_not_nan())
        )
        cnp_values = cnp_data["cnp_voltage"].to_numpy()

        ctx.print()
        ctx.print("[bold]CNP Statistics:[/bold]")
        ctx.print(f"  • Mean: {cnp_values.mean():.3f} V")
        ctx.print(f"  • Std:  {cnp_values.std():.3f} V")
        ctx.print(f"  • Min:  {cnp_values.min():.3f} V")
        ctx.print(f"  • Max:  {cnp_values.max():.3f} V")
        ctx.print(f"  • Range: {cnp_values.max() - cnp_values.min():.3f} V")

    except Exception as e:
        ctx.print(f"[red]Error:[/red] Failed to generate plot: {e}")
        import traceback
        if ctx.verbose:
            ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    ctx.print()
