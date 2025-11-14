"""CLI command for exporting chip histories to organized folders."""

from pathlib import Path
from datetime import datetime
from typing import Optional
import polars as pl
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.plugin_system import cli_command
from src.cli.main import get_config

console = Console()


@cli_command(
    name="export-history",
    group="history",
    description="Export chip history to organized export directory"
)
def export_history(
    chip_number: int = typer.Argument(..., help="Chip number (e.g., 67 for Alisson67)"),
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv, json, parquet, xlsx"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Custom output directory (default: data/04_exports/histories/)"),
    chip_group: str = typer.Option("Alisson", "--group", "-g", help="Chip group name prefix"),
    proc_filter: Optional[str] = typer.Option(None, "--proc", "-p", help="Filter by procedure type (IVg, It, IV, etc.)"),
    light_filter: Optional[str] = typer.Option(None, "--light", "-l", help="Filter by light status: 'light', 'dark', 'unknown'"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Export only last N experiments"),
    mode: str = typer.Option("default", "--mode", "-m", help="Export mode: 'default', 'metrics', 'compact'"),
    timestamp: bool = typer.Option(True, "--timestamp/--no-timestamp", help="Add timestamp to filename"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing file"),
):
    """
    Export chip history to an organized export directory.

    This command exports chip history (standard or enriched) to a properly
    organized directory structure with automatic naming.

    Directory structure:
        data/04_exports/histories/{ChipGroup}{ChipNumber}/
            - Alisson67_history_YYYYMMDD_HHMMSS.csv
            - Alisson67_metrics_YYYYMMDD_HHMMSS.csv
            - Alisson67_its_light_YYYYMMDD_HHMMSS.json
            - etc.

    Examples
    --------
    # Export full enriched history to CSV
    $ python process_and_analyze.py export-history 67

    # Export to JSON with timestamp
    $ python process_and_analyze.py export-history 67 --format json

    # Export only metrics
    $ python process_and_analyze.py export-history 67 --mode metrics

    # Export light ITS experiments only
    $ python process_and_analyze.py export-history 67 --proc It --light light

    # Export to custom directory
    $ python process_and_analyze.py export-history 67 --output-dir ~/my_exports

    # Export without timestamp (cleaner filename)
    $ python process_and_analyze.py export-history 67 --no-timestamp
    """
    # Validate format
    format = format.lower()
    valid_formats = ["csv", "json", "parquet", "xlsx"]
    if format not in valid_formats:
        console.print(f"[red]Error:[/red] Invalid format '{format}'. Must be one of: {', '.join(valid_formats)}")
        raise typer.Exit(1)

    # Determine output directory
    if output_dir is None:
        output_dir = Path("data/04_exports/histories") / f"{chip_group}{chip_number}"
    else:
        output_dir = Path(output_dir)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load chip history
    config = get_config()
    chip_name = f"{chip_group}{chip_number}"

    # Try enriched history first
    enriched_dir = Path("data/03_derived/chip_histories_enriched")
    enriched_file = enriched_dir / f"{chip_name}_history.parquet"

    if enriched_file.exists():
        console.print(f"[green]✓[/green] Loading enriched history from: {enriched_file}")
        history = pl.read_parquet(enriched_file)
        history_type = "enriched"
    else:
        # Fall back to standard history
        history_dir = config.history_dir
        history_file = history_dir / f"{chip_name}_history.parquet"

        if not history_file.exists():
            console.print(
                f"[red]Error:[/red] Chip history file not found: {history_file}\n"
                f"Run 'build-all-histories' command first to generate history files."
            )
            raise typer.Exit(1)

        console.print(f"[yellow]⚠[/yellow]  Loading standard history (enriched not found)")
        console.print(f"[dim]   → To get enriched data with metrics, run: enrich-history {chip_number}[/dim]")
        history = pl.read_parquet(history_file)
        history_type = "standard"

    console.print(f"[dim]   Loaded {history.height} experiments[/dim]\n")

    # Apply filters
    original_count = history.height

    if proc_filter:
        history = history.filter(pl.col("proc") == proc_filter)
        console.print(f"[dim]   Filtered to procedure '{proc_filter}': {history.height} experiments[/dim]")

    if light_filter:
        if light_filter.lower() == "light":
            history = history.filter(pl.col("has_light") == True)
        elif light_filter.lower() == "dark":
            history = history.filter(pl.col("has_light") == False)
        elif light_filter.lower() == "unknown":
            history = history.filter(pl.col("has_light").is_null())
        console.print(f"[dim]   Filtered to light='{light_filter}': {history.height} experiments[/dim]")

    if limit:
        history = history.tail(limit)
        console.print(f"[dim]   Limited to last {limit} experiments[/dim]")

    if history.height == 0:
        console.print(f"[yellow]Warning:[/yellow] No experiments match the filters. Nothing to export.")
        raise typer.Exit(0)

    # Apply mode (column selection)
    if mode == "metrics":
        # Only include metric-focused columns
        metric_cols = [
            "seq", "date", "time_hms", "datetime_local", "proc", "has_light",
            "wavelength_nm", "vg_fixed_v", "laser_voltage_v",
        ]
        # Add enriched columns if available
        if "cnp_voltage" in history.columns:
            metric_cols.append("cnp_voltage")
        if "delta_current" in history.columns:
            metric_cols.append("delta_current")
        if "irradiated_power_w" in history.columns:
            metric_cols.append("irradiated_power_w")
        if "calibration_time_delta_hours" in history.columns:
            metric_cols.append("calibration_time_delta_hours")

        # Filter to available columns
        metric_cols = [col for col in metric_cols if col in history.columns]
        history = history.select(metric_cols)
        console.print(f"[dim]   Metrics mode: using {len(metric_cols)} columns[/dim]")

    elif mode == "compact":
        # Minimal columns for quick overview
        compact_cols = [
            "seq", "date", "time_hms", "proc", "summary", "has_light"
        ]
        compact_cols = [col for col in compact_cols if col in history.columns]
        history = history.select(compact_cols)
        console.print(f"[dim]   Compact mode: using {len(compact_cols)} columns[/dim]")

    # Build filename
    filename_parts = [chip_name]

    # Add mode/filter descriptors
    if mode == "metrics":
        filename_parts.append("metrics")
    elif mode == "compact":
        filename_parts.append("compact")
    else:
        filename_parts.append("history")

    if proc_filter:
        filename_parts.append(proc_filter.lower())

    if light_filter:
        filename_parts.append(light_filter.lower())

    # Add timestamp if requested
    if timestamp:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_parts.append(ts)

    # Add extension
    filename = "_".join(filename_parts) + f".{format}"
    output_file = output_dir / filename

    # Check if file exists
    if output_file.exists() and not overwrite:
        console.print(f"[yellow]Warning:[/yellow] File already exists: {output_file}")
        console.print(f"[dim]   Use --overwrite to replace, or --timestamp to create new file[/dim]")
        raise typer.Exit(1)

    # Export based on format
    console.print(f"\n[cyan]Exporting to {format.upper()}...[/cyan]")

    try:
        if format == "csv":
            history.write_csv(output_file)
        elif format == "json":
            history.write_json(output_file)
        elif format == "parquet":
            history.write_parquet(output_file)
        elif format == "xlsx":
            try:
                # Requires openpyxl or xlsxwriter
                history.write_excel(output_file)
            except Exception as e:
                console.print(f"[red]Error:[/red] Excel export failed. Install openpyxl: pip install openpyxl")
                console.print(f"[dim]   {str(e)}[/dim]")
                raise typer.Exit(1)

        # Success!
        file_size = output_file.stat().st_size
        size_mb = file_size / (1024 * 1024)

        console.print(f"\n[green]✓ Export successful![/green]\n")

        # Display summary
        summary_panel = Panel(
            f"[bold]File:[/bold] {output_file}\n"
            f"[bold]Size:[/bold] {size_mb:.2f} MB ({file_size:,} bytes)\n"
            f"[bold]Format:[/bold] {format.upper()}\n"
            f"[bold]History Type:[/bold] {history_type}\n"
            f"[bold]Experiments:[/bold] {history.height} / {original_count}\n"
            f"[bold]Columns:[/bold] {len(history.columns)}",
            title="Export Summary",
            border_style="green"
        )
        console.print(summary_panel)

        # Show path for easy access
        console.print(f"\n[dim]To view:[/dim]")
        if format == "csv":
            console.print(f"[dim]  Excel/Google Sheets: Open {output_file}[/dim]")
            console.print(f"[dim]  Terminal: head -20 {output_file}[/dim]")
        elif format == "json":
            console.print(f"[dim]  Pretty print: jq '.' {output_file} | less[/dim]")
            console.print(f"[dim]  Python: import json; data = json.load(open('{output_file}'))[/dim]")
        elif format == "xlsx":
            console.print(f"[dim]  Excel: open {output_file}[/dim]")
        elif format == "parquet":
            console.print(f"[dim]  Python: import polars as pl; df = pl.read_parquet('{output_file}')[/dim]")

    except Exception as e:
        console.print(f"\n[red]Error during export:[/red] {str(e)}")
        raise typer.Exit(1)


@cli_command(
    name="export-all-histories",
    group="history",
    description="Export histories for all chips"
)
def export_all_histories(
    format: str = typer.Option("csv", "--format", "-f", help="Export format: csv, json, parquet, xlsx"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Custom output directory"),
    chip_group: str = typer.Option("Alisson", "--group", "-g", help="Chip group name prefix"),
    mode: str = typer.Option("default", "--mode", "-m", help="Export mode: 'default', 'metrics', 'compact'"),
    timestamp: bool = typer.Option(True, "--timestamp/--no-timestamp", help="Add timestamp to filenames"),
):
    """
    Export histories for all available chips.

    This command discovers all chip histories and exports them to organized folders.

    Examples
    --------
    # Export all chips to CSV
    $ python process_and_analyze.py export-all-histories

    # Export all chips to JSON
    $ python process_and_analyze.py export-all-histories --format json

    # Export all chips (metrics only)
    $ python process_and_analyze.py export-all-histories --mode metrics
    """
    # Find all chip histories
    enriched_dir = Path("data/03_derived/chip_histories_enriched")
    standard_dir = Path("data/02_stage/chip_histories")

    # Discover chip numbers from enriched histories first
    chip_numbers = set()

    if enriched_dir.exists():
        for file in enriched_dir.glob(f"{chip_group}*_history.parquet"):
            # Extract chip number from filename
            chip_str = file.stem.replace(f"{chip_group}", "").replace("_history", "")
            if chip_str.isdigit():
                chip_numbers.add(int(chip_str))

    # Also check standard histories
    if standard_dir.exists():
        for file in standard_dir.glob(f"{chip_group}*_history.parquet"):
            chip_str = file.stem.replace(f"{chip_group}", "").replace("_history", "")
            if chip_str.isdigit():
                chip_numbers.add(int(chip_str))

    if not chip_numbers:
        console.print(f"[yellow]Warning:[/yellow] No chip histories found for group '{chip_group}'")
        console.print(f"[dim]   Run 'build-all-histories' to generate chip histories[/dim]")
        raise typer.Exit(0)

    console.print(f"[cyan]Found {len(chip_numbers)} chips:[/cyan] {sorted(chip_numbers)}\n")

    # Export each chip
    success_count = 0
    for chip in sorted(chip_numbers):
        console.print(f"[bold]Exporting chip {chip}...[/bold]")
        try:
            # Call export-history for each chip
            from src.cli.commands.export_history import export_history
            export_history(
                chip_number=chip,
                format=format,
                output_dir=output_dir,
                chip_group=chip_group,
                proc_filter=None,
                light_filter=None,
                limit=None,
                mode=mode,
                timestamp=timestamp,
                overwrite=True  # Allow overwrite in batch mode
            )
            success_count += 1
            console.print()  # Blank line between chips
        except Exception as e:
            console.print(f"[red]Failed to export chip {chip}:[/red] {str(e)}\n")

    # Final summary
    console.print(f"\n[green]✓ Exported {success_count}/{len(chip_numbers)} chips successfully[/green]")
