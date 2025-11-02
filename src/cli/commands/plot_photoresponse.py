"""CLI commands for photoresponse plotting."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from src.cli.context import get_context
from src.cli.cache import load_history_cached
from rich.panel import Panel

from src.cli.plugin_system import cli_command



@cli_command(
    name="plot-photoresponse",
    group="plotting",
    description="Plot photoresponse vs power, wavelength, gate voltage, or time"
)
def plot_photoresponse_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 81 for Alisson81)"
    ),
    x_variable: str = typer.Argument(
        ...,
        help="X-axis variable: 'power', 'wavelength', 'gate_voltage', or 'time'"
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
    metric: str = typer.Option(
        "delta_current",
        "--metric",
        "-m",
        help="Metric to plot: 'delta_current' (current) or 'delta_voltage' (voltage)"
    ),
    procedures: Optional[str] = typer.Option(
        None,
        "--procedures",
        "--procs",
        help="Comma-separated list of procedures to include (e.g., 'It,Vt,ITt'). Auto-selects based on metric if not specified."
    ),
    wavelength: Optional[float] = typer.Option(
        None,
        "--wavelength",
        "--wl",
        help="Filter to specific wavelength (nm)"
    ),
    gate_voltage: Optional[float] = typer.Option(
        None,
        "--gate-voltage",
        "--vg",
        help="Filter to specific gate voltage (V)"
    ),
    power_min: Optional[float] = typer.Option(
        None,
        "--power-min",
        help="Minimum irradiated power (W)"
    ),
    power_max: Optional[float] = typer.Option(
        None,
        "--power-max",
        help="Maximum irradiated power (W)"
    ),
):
    """
    Plot photoresponse as a function of experimental parameters.

    This shows how the device responds to illumination by plotting:
    - Photoresponse vs Power: Response scaling with irradiance
    - Photoresponse vs Wavelength: Spectral response characteristics
    - Photoresponse vs Gate Voltage: Field-effect modulation of response
    - Photoresponse vs Time: Temporal evolution of device response

    Requires:
    - Photoresponse metrics extracted (run derive-all-metrics first)
    - Laser calibration power extraction (run derive-all-metrics --calibrations)
    - It/Vt/ITt measurements with illumination

    Examples:
        # Plot current change vs irradiated power for all wavelengths
        python process_and_analyze.py plot-photoresponse 81 power

        # Plot response evolution over time
        python process_and_analyze.py plot-photoresponse 81 time

        # Plot response vs wavelength at fixed gate voltage
        python process_and_analyze.py plot-photoresponse 81 wavelength --vg -0.4

        # Plot response vs gate voltage at 660nm wavelength
        python process_and_analyze.py plot-photoresponse 81 gate_voltage --wl 660

        # Plot voltage change from Vt measurements
        python process_and_analyze.py plot-photoresponse 81 power --metric delta_voltage --procs Vt

        # Include both It and Vt measurements (requires delta_current metric)
        python process_and_analyze.py plot-photoresponse 81 time --procs It,ITt

        # Filter to power range
        python process_and_analyze.py plot-photoresponse 81 wavelength --power-min 1e-6 --power-max 1e-3
    """
    ctx = get_context()
    import polars as pl
    from src.plotting.photoresponse import plot_photoresponse

    # Validate x_variable
    valid_x_vars = ["power", "wavelength", "gate_voltage", "time"]
    if x_variable not in valid_x_vars:
        ctx.print(f"[red]Error:[/red] Invalid x_variable '{x_variable}'")
        ctx.print(f"[yellow]Valid options:[/yellow] {', '.join(valid_x_vars)}")
        raise typer.Exit(1)

    # Validate metric
    valid_metrics = ["delta_current", "delta_voltage"]
    if metric not in valid_metrics:
        ctx.print(f"[red]Error:[/red] Invalid metric '{metric}'")
        ctx.print(f"[yellow]Valid options:[/yellow] {', '.join(valid_metrics)}")
        raise typer.Exit(1)

    # Parse procedures
    procs_list = None
    if procedures is not None:
        procs_list = [p.strip() for p in procedures.split(",")]
        valid_procs = ["It", "Vt", "ITt"]
        for proc in procs_list:
            if proc not in valid_procs:
                ctx.print(f"[red]Error:[/red] Invalid procedure '{proc}'")
                ctx.print(f"[yellow]Valid options:[/yellow] {', '.join(valid_procs)}")
                raise typer.Exit(1)

    # Load config
    from src.cli.main import get_config
    config = get_config()

    chip_name = f"{chip_group}{chip_number}"

    # Determine output directory
    if output_dir is None:
        output_dir = ctx.output_dir

    ctx.print()
    ctx.print(Panel.fit(
        f"[bold cyan]Photoresponse Plot - {chip_name}[/bold cyan]\n"
        f"[cyan]X-axis:[/cyan] {x_variable} | [cyan]Metric:[/cyan] {metric}",
        border_style="cyan"
    ))
    ctx.print()

    # Load enriched history from Stage 3
    enriched_history_file = config.stage_dir.parent / "03_derived" / "chip_histories_enriched" / f"{chip_name}_history.parquet"
    metrics_file = config.stage_dir.parent / "03_derived" / "_metrics" / "metrics.parquet"

    ctx.print("[cyan]Loading chip history and metrics...[/cyan]")

    if not enriched_history_file.exists():
        ctx.print(f"[red]Error:[/red] Enriched history not found: {enriched_history_file}")
        ctx.print("[yellow]Hint:[/yellow] Run [cyan]derive-all-metrics --calibrations[/cyan] first")
        raise typer.Exit(1)

    history = pl.read_parquet(enriched_history_file)

    # Join with photoresponse metrics if not already joined
    metric_col = metric  # Metrics use delta_current/delta_voltage names
    if metric_col not in history.columns:
        if not metrics_file.exists():
            ctx.print(f"[red]Error:[/red] No metrics found")
            ctx.print("[yellow]Hint:[/yellow] Run [cyan]derive-all-metrics[/cyan] first")
            raise typer.Exit(1)

        metrics = pl.read_parquet(metrics_file)

        # Filter metrics for this chip and photoresponse only
        photo_metrics = metrics.filter(
            (pl.col("chip_number") == chip_number) &
            (pl.col("chip_group") == chip_group) &
            (pl.col("metric_name") == metric_col)
        )

        if photo_metrics.height == 0:
            ctx.print(f"[red]Error:[/red] No photoresponse data found for {chip_name}")
            ctx.print("[yellow]Hint:[/yellow] Run [cyan]derive-all-metrics[/cyan] to extract photoresponse from It measurements")
            raise typer.Exit(1)

        # Join metrics to history
        metric_df = photo_metrics.select([
            "run_id",
            pl.col("value_float").alias(metric_col)
        ])
        history = history.join(metric_df, on="run_id", how="left")

    # Check if we have photoresponse data with illumination
    photo_count = history.filter(
        (pl.col("proc") == "It") &
        (pl.col("has_light") == True) &
        (pl.col(metric_col).is_not_null()) &
        (pl.col(metric_col).is_not_nan())
    ).height

    if photo_count == 0:
        ctx.print(f"[red]Error:[/red] No It measurements with photoresponse and illumination found for {chip_name}")
        ctx.print("[yellow]Hint:[/yellow] This chip needs It measurements with light to calculate photoresponse")
        raise typer.Exit(1)

    # Check for irradiated power if plotting vs power
    if x_variable == "power":
        has_power = history.filter(
            (pl.col("proc") == "It") &
            (pl.col("has_light") == True) &
            (pl.col("irradiated_power_w").is_not_null())
        ).height > 0

        if not has_power:
            ctx.print(f"[red]Error:[/red] No irradiated power data found")
            ctx.print("[yellow]Hint:[/yellow] Run [cyan]derive-all-metrics --calibrations[/cyan] to extract power from laser calibrations")
            raise typer.Exit(1)

    ctx.print(f"[green]✓[/green] Found {photo_count} It measurements with photoresponse data")

    # Generate plot
    ctx.print(f"[cyan]Generating photoresponse vs {x_variable} plot...[/cyan]")

    # Build power range filter
    power_range = None
    if power_min is not None or power_max is not None:
        power_range = (
            power_min if power_min is not None else 0.0,
            power_max if power_max is not None else float('inf')
        )

    try:
        output_file = plot_photoresponse(
            history=history,
            chip_name=chip_name,
            x_variable=x_variable,
            output_dir=output_dir,
            y_metric=metric,
            procedures=procs_list,
            filter_wavelength=wavelength,
            filter_vg=gate_voltage,
            filter_power_range=power_range,
        )

        ctx.print()
        ctx.print(Panel(
            f"[green]✓ Plot saved successfully[/green]\n"
            f"[cyan]Output:[/cyan] {output_file}\n"
            f"[cyan]X-axis:[/cyan] {x_variable}\n"
            f"[cyan]Y-axis:[/cyan] {metric}\n"
            f"[cyan]Data points:[/cyan] {photo_count}",
            title="[bold]Photoresponse Plot[/bold]",
            border_style="green"
        ))

        # Show applied filters
        filters = []
        if wavelength is not None:
            filters.append(f"Wavelength: {wavelength} nm")
        if gate_voltage is not None:
            filters.append(f"Gate voltage: {gate_voltage} V")
        if power_range is not None:
            filters.append(f"Power: {power_range[0]} - {power_range[1]} W")

        if filters:
            ctx.print()
            ctx.print("[bold]Applied Filters:[/bold]")
            for f in filters:
                ctx.print(f"  • {f}")

    except Exception as e:
        ctx.print(f"[red]Error:[/red] Failed to generate plot: {e}")
        import traceback
        if ctx.verbose:
            ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    ctx.print()
