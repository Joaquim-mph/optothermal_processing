"""
CLI command for LaserCalibration plotting.

Provides commands to generate laser calibration plots showing the relationship
between laser PSU voltage and measured optical power.
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from src.cli.context import get_context
from src.cli.cache import load_history_cached
from rich.panel import Panel
from rich.table import Table
import polars as pl

from src.cli.plugin_system import cli_command
from src.cli.helpers import (
    parse_seq_list,
    display_plot_success,
)
from src.plotting.laser_calibration import (
    plot_laser_calibration,
    plot_laser_calibration_comparison,
)



def _display_calibration_experiments(df: pl.DataFrame, title: str = "Calibration Experiments"):
    """
    Display calibration experiments in a Rich table.

    Parameters
    ----------
    df : pl.DataFrame
        Filtered calibration history dataframe
    title : str
        Table title
    """
    ctx.print()
    ctx.print(Panel.fit(
        f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan"
    ))

    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    table.add_column("Seq", style="yellow", width=5)
    table.add_column("Date", style="white", width=12)
    table.add_column("Wavelength", style="magenta", width=12)
    table.add_column("Fiber", style="green", width=20)
    table.add_column("Sensor", style="blue", width=20)
    table.add_column("Voltage Range", style="white", width=15)

    for row in df.iter_rows(named=True):
        seq = str(int(row["seq"]))
        date = row.get("date_local", "unknown")
        wavelength = f"{row.get('wavelength_nm', 0):.0f} nm" if row.get('wavelength_nm') else "N/A"
        fiber = row.get("optical_fiber", "unknown")
        sensor = row.get("sensor_model", "unknown")

        # Voltage range from parameters
        v_start = row.get("laser_voltage_start_v")
        v_end = row.get("laser_voltage_end_v")
        if v_start is not None and v_end is not None:
            voltage_range = f"{v_start:.1f} - {v_end:.1f} V"
        else:
            voltage_range = "N/A"

        table.add_row(seq, str(date), wavelength, fiber, sensor, voltage_range)

    ctx.print(table)
    ctx.print(f"[dim]Total: {df.height} calibration(s)[/dim]")
    ctx.print()


@cli_command(
    name="plot-laser-calibration",
    group="plotting",
    description="Generate laser calibration plots (Power vs Voltage)"
)
def plot_laser_calibration_command(
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Comma-separated seq numbers from manifest (e.g., '1,2,3'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        "-a",
        help="Automatically select all LaserCalibration experiments"
    ),
    wavelength: Optional[float] = typer.Option(
        None,
        "--wavelength",
        "-wl",
        help="Filter by laser wavelength (nm)"
    ),
    fiber: Optional[str] = typer.Option(
        None,
        "--fiber",
        "-f",
        help="Filter by optical fiber name"
    ),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        help="Filter by date (YYYY-MM-DD)"
    ),
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Manifest file (default: from config)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: figs/laser_calibrations)"
    ),
    power_unit: str = typer.Option(
        "uW",
        "--power-unit",
        "-u",
        help="Power unit for y-axis: uW, mW, or W (default: uW)"
    ),
    group_by_wavelength: bool = typer.Option(
        True,
        "--group-by-wavelength/--no-group-by-wavelength",
        help="Color-code curves by wavelength (default: True)"
    ),
    show_markers: bool = typer.Option(
        False,
        "--markers/--no-markers",
        help="Show data point markers (default: True)"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Preview mode: show experiments without generating plots"
    ),
    comparison: bool = typer.Option(
        False,
        "--comparison",
        help="Generate comparison plot with subplots per wavelength"
    ),
):
    """
    Generate laser calibration plots.

    Creates calibration curves showing the relationship between laser PSU voltage
    and measured optical power. Useful for characterizing laser output and creating
    lookup tables for power control.

    Note: Laser calibrations are NOT chip-specific - they are global measurements
    loaded from the manifest.

    \b
    Examples:
        # Plot all calibrations
        plot-laser-calibration --auto

        # Plot specific calibrations (by manifest seq)
        plot-laser-calibration --seq 1,2,3

        # Filter by wavelength
        plot-laser-calibration --auto --wavelength 455

        # Filter by fiber
        plot-laser-calibration --auto --fiber "fiber1"

        # Show power in milliwatts instead of microwatts
        plot-laser-calibration --auto --power-unit mW

        # Generate comparison plot (subplots per wavelength)
        plot-laser-calibration --auto --comparison

        # Preview experiments without plotting
        plot-laser-calibration --auto --preview

    \b
    Output:
        Saves plot to: figs/laser_calibrations/laser_calibration_*.png
    """

    if output_dir is None:
        output_dir = ctx.output_dir / "laser_calibrations"
        if ctx.verbose:
            ctx.print(f"[dim]Using output directory: {output_dir}[/dim]")

    if manifest is None:
        manifest = config.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
        if ctx.verbose:
            ctx.print(f"[dim]Using manifest from config: {manifest}[/dim]")

    # Load manifest
    if not manifest.exists():
        ctx.print(f"[red]✗[/red] Manifest file not found: {manifest}")
        ctx.print("[yellow]→[/yellow] Run: [cyan]python process_and_analyze.py stage-all[/cyan]")
        raise typer.Exit(1)

    manifest_df = pl.read_parquet(manifest)

    # Filter to LaserCalibration procedure
    calibrations = manifest_df.filter(pl.col("proc") == "LaserCalibration")
    if calibrations.height == 0:
        ctx.print(f"[red]✗[/red] No LaserCalibration experiments found in manifest")
        available = manifest_df["proc"].unique().to_list()
        ctx.print(f"[yellow]Available procedures:[/yellow] {', '.join(available)}")
        raise typer.Exit(1)

    # Add sequential numbering for selection (sort by start time first)
    # Normalize column name if needed
    time_col = "start_time_utc" if "start_time_utc" in calibrations.columns else "start_dt"
    calibrations = calibrations.sort(time_col)
    calibrations = calibrations.with_row_index(name="seq", offset=1)

    # Ensure we have parquet_path column (normalize name if needed)
    if "path" in calibrations.columns and "parquet_path" not in calibrations.columns:
        calibrations = calibrations.rename({"path": "parquet_path"})

    # Apply filters
    filtered = calibrations

    if wavelength is not None:
        if "wavelength_nm" not in filtered.columns:
            ctx.print("[yellow]⚠[/yellow] Wavelength filter requested but no wavelength data in manifest")
        else:
            before_count = filtered.height
            filtered = filtered.filter(
                (pl.col("wavelength_nm") - wavelength).abs() < 1.0  # 1nm tolerance
            )
            after_count = filtered.height
            if after_count < before_count:
                ctx.print(f"[dim]Filtered by wavelength {wavelength}nm: {before_count} → {after_count} experiments[/dim]")

    if fiber is not None:
        if "optical_fiber" not in filtered.columns:
            ctx.print("[yellow]⚠[/yellow] Fiber filter requested but no fiber data in manifest")
        else:
            before_count = filtered.height
            filtered = filtered.filter(pl.col("optical_fiber") == fiber)
            after_count = filtered.height
            if after_count < before_count:
                ctx.print(f"[dim]Filtered by fiber '{fiber}': {before_count} → {after_count} experiments[/dim]")

    if date is not None:
        if "date_local" not in filtered.columns:
            ctx.print("[yellow]⚠[/yellow] Date filter requested but no date data in manifest")
        else:
            before_count = filtered.height
            filtered = filtered.filter(pl.col("date_local") == date)
            after_count = filtered.height
            if after_count < before_count:
                ctx.print(f"[dim]Filtered by date {date}: {before_count} → {after_count} experiments[/dim]")

    if filtered.height == 0:
        ctx.print("[red]✗[/red] No experiments match the specified filters")
        raise typer.Exit(1)

    # Get seq numbers
    if auto:
        seq_numbers = filtered["seq"].to_list()
    elif seq:
        seq_numbers = parse_seq_list(seq)
    else:
        ctx.print("[red]✗[/red] Must specify --seq or --auto")
        ctx.print("[yellow]→[/yellow] Example: [cyan]plot-laser-calibration --auto[/cyan]")
        raise typer.Exit(1)

    # Validate seq numbers exist in filtered dataframe
    valid_seqs = set(filtered["seq"].to_list())
    invalid_seqs = [s for s in seq_numbers if s not in valid_seqs]
    if invalid_seqs:
        ctx.print(f"[red]✗[/red] Invalid seq numbers: {invalid_seqs}")
        ctx.print(f"[yellow]Available seq numbers:[/yellow] 1-{filtered.height}")
        raise typer.Exit(1)

    # Filter to selected experiments
    selected = filtered.filter(pl.col("seq").is_in(seq_numbers)).sort("seq")

    # Display experiment list
    _display_calibration_experiments(selected, "Laser Calibrations")

    # Preview mode: stop here
    if preview:
        ctx.print("[cyan]📋 Preview mode - no plots generated[/cyan]")
        return

    # Setup output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate plot
    plot_tag = "calibrations"

    # Set output directory for plotting module
    from src.plotting import laser_calibration
    laser_calibration.FIG_DIR = output_dir

    if comparison:
        # Generate comparison plot (subplots)
        ctx.print(f"\n[cyan]📊 Generating LaserCalibration comparison plot...[/cyan]")
        output_file = plot_laser_calibration_comparison(
            selected,
            Path("."),  # Base dir not used (we have parquet_paths)
            plot_tag,
            group_by="wavelength"
        )
    else:
        # Generate standard overlay plot
        ctx.print(f"\n[cyan]📊 Generating LaserCalibration plot...[/cyan]")
        output_file = plot_laser_calibration(
            selected,
            Path("."),  # Base dir not used (we have parquet_paths)
            plot_tag,
            group_by_wavelength=group_by_wavelength,
            show_markers=show_markers,
            power_unit=power_unit,
        )

    if output_file:
        display_plot_success(output_file)
    else:
        ctx.print("[red]✗[/red] Failed to generate plot")
        raise typer.Exit(1)


@cli_command(
    name="plot-laser-calibration-comparison",
    group="plotting",
    description="Generate laser calibration comparison plot (subplots)"
)
def plot_laser_calibration_comparison_command(
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Comma-separated seq numbers (e.g., '1,2,3'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        "-a",
        help="Automatically select all LaserCalibration experiments"
    ),
    group_by: str = typer.Option(
        "wavelength",
        "--group-by",
        help="Grouping variable: 'wavelength' or 'fiber' (default: wavelength)"
    ),
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Manifest file (default: from config)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: figs/laser_calibrations)"
    ),
):
    """
    Generate laser calibration comparison plot with subplots.

    Creates a multi-panel figure with one subplot per wavelength (or fiber),
    making it easy to compare calibration curves side-by-side.

    \b
    Examples:
        # Compare all calibrations by wavelength
        plot-laser-calibration-comparison --auto

        # Compare by fiber instead
        plot-laser-calibration-comparison --auto --group-by fiber

        # Compare specific calibrations
        plot-laser-calibration-comparison --seq 1,2,3,4
    """
    # Call main command with --comparison flag
    plot_laser_calibration_command(
        seq=seq,
        auto=auto,
        wavelength=None,
        fiber=None,
        date=None,
        manifest=manifest,
        output_dir=output_dir,
        power_unit="uW",
        group_by_wavelength=(group_by == "wavelength"),
        show_markers=True,
        preview=False,
        comparison=True,
    )
