"""History display and generation commands: show-history, build-history, build-all-histories."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
import polars as pl

from src.core.history_builder import (
    build_chip_history_from_manifest,
    generate_chip_name,
    save_chip_history,
    generate_all_chip_histories,
)
from src.cli.history_utils import (
    filter_history,
    summarize_history,
    HistoryFilterError,
)

console = Console()


@cli_command(
    name="show-history",
    group="history",
    description="Display chip experiment history"
)
def show_history_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number to display (e.g., 67 for Alisson67)"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name prefix"
    ),
    history_dir: Optional[Path] = typer.Option(
        None,
        "--history-dir",
        "-d",
        help="Directory containing chip history CSV files (default: from config)"
    ),
    proc_filter: Optional[str] = typer.Option(
        None,
        "--proc",
        "-p",
        help="Filter by procedure type (IVg, ITS, IV, etc.)"
    ),
    light_filter: Optional[str] = typer.Option(
        None,
        "--light",
        "-l",
        help="Filter by light status: 'light', 'dark', or 'unknown'"
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        "-n",
        help="Show only last N experiments"
    ),
):
    """
    Display the complete experiment history for a specific chip.

    Shows a beautiful, paginated view of all experiments with details
    including date, time, procedure type, and parameters.

    Example:
        python process_and_analyze.py show-history 67
        python process_and_analyze.py show-history 72 --proc ITS --limit 20
    """
    # Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    if history_dir is None:
        history_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    chip_name = f"{chip_group}{chip_number}"
    history_file = history_dir / f"{chip_name}_history.parquet"

    # Check if file exists
    if not history_file.exists():
        console.print(f"[red]Error:[/red] History file not found: {history_file}")
        console.print(f"\n[yellow]Hint:[/yellow] Run [cyan]build-all-histories[/cyan] command first to generate history files.")
        console.print(f"Available files in {history_dir}:")
        if history_dir.exists():
            for f in sorted(history_dir.glob("*_history.parquet")):
                console.print(f"  • {f.name}")
        else:
            console.print(f"  [dim](directory does not exist)[/dim]")
        raise typer.Exit(1)

    # Try to load enriched history from Stage 3 first (has calibration data)
    # If not available, fall back to Stage 2 and try to join with metrics
    enriched_history_file = config.stage_dir.parent / "03_derived" / "chip_histories_enriched" / f"{chip_name}_history.parquet"
    metrics_file = config.stage_dir.parent / "03_derived" / "_metrics" / "metrics.parquet"

    try:
        if enriched_history_file.exists():
            # Load enriched history (has calibration power data)
            history = pl.read_parquet(enriched_history_file)

            # Try to join with metrics for CNP and photoresponse
            if metrics_file.exists():
                metrics = pl.read_parquet(metrics_file)

                # Filter metrics for this chip
                chip_metrics = metrics.filter(
                    (pl.col("chip_number") == chip_number) &
                    (pl.col("chip_group") == chip_group)
                )

                # Pivot metrics to wide format (one column per metric type)
                # Join CNP voltage
                cnp_metrics = chip_metrics.filter(pl.col("metric_name") == "cnp_voltage")
                if cnp_metrics.height > 0:
                    cnp_df = cnp_metrics.select([
                        "run_id",
                        pl.col("value_float").alias("cnp_voltage")
                    ])
                    history = history.join(cnp_df, on="run_id", how="left")

                # Join delta current (photoresponse)
                delta_i_metrics = chip_metrics.filter(pl.col("metric_name") == "delta_current")
                if delta_i_metrics.height > 0:
                    delta_i_df = delta_i_metrics.select([
                        "run_id",
                        pl.col("value_float").alias("delta_current")
                    ])
                    history = history.join(delta_i_df, on="run_id", how="left")

                # Join delta voltage (photoresponse)
                delta_v_metrics = chip_metrics.filter(pl.col("metric_name") == "delta_voltage")
                if delta_v_metrics.height > 0:
                    delta_v_df = delta_v_metrics.select([
                        "run_id",
                        pl.col("value_float").alias("delta_voltage")
                    ])
                    history = history.join(delta_v_df, on="run_id", how="left")

            if config.verbose:
                console.print(f"[dim]Loaded enriched history with derived metrics[/dim]")
        else:
            # Fall back to Stage 2 base history
            history = pl.read_parquet(history_file)
            if config.verbose:
                console.print(f"[dim]Loaded base history (no derived metrics)[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read history file: {e}")
        raise typer.Exit(1)

    try:
        history, applied_filters = filter_history(
            history,
            proc_filter=proc_filter,
            light_filter=light_filter,
            limit=limit,
            strict=True,
        )
    except HistoryFilterError as exc:
        message = str(exc)
        if exc.exit_code == 0:
            console.print(f"[yellow]{message}[/yellow]")
        else:
            console.print(f"[red]Error:[/red] {message}")
        raise typer.Exit(exc.exit_code)

    summary = summarize_history(history)

    # Display header
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]{chip_name} Experiment History[/bold cyan]\n"
        f"Total experiments: [yellow]{summary['total']}[/yellow]",
        border_style="cyan"
    ))
    console.print()

    # Summary statistics
    date_range = summary["date_range"]
    num_days = summary["num_days"]
    proc_counts = summary["proc_counts"]

    # Summary cards
    summary_items = []

    # Date range card
    date_card = Table.grid(padding=(0, 2))
    date_card.add_column(style="cyan", justify="right")
    date_card.add_column(style="yellow")
    date_card.add_row("Date Range:", date_range)
    date_card.add_row("Days:", str(num_days))
    summary_items.append(Panel(date_card, title="[cyan]Timeline[/cyan]", border_style="cyan"))

    # Procedure breakdown card
    proc_table = Table.grid(padding=(0, 2))
    proc_table.add_column(style="magenta", justify="right")
    proc_table.add_column(style="yellow")
    for proc, count in proc_counts:
        proc_table.add_row(f"{proc}:", str(count))
    summary_items.append(Panel(proc_table, title="[magenta]Procedures[/magenta]", border_style="magenta"))

    # Light status breakdown card (if has_light column exists)
    light_counts = summary["light_counts"]
    if light_counts:
        light_table = Table.grid(padding=(0, 2))
        light_table.add_column(style="green", justify="right")
        light_table.add_column(style="yellow")
        has_rows = False
        if light_counts["light"] > 0:
            light_table.add_row("💡 Light:", str(light_counts["light"]))
            has_rows = True
        if light_counts["dark"] > 0:
            light_table.add_row("🌙 Dark:", str(light_counts["dark"]))
            has_rows = True
        if light_counts["unknown"] > 0:
            light_table.add_row("❗ Unknown:", str(light_counts["unknown"]))
            has_rows = True

        if has_rows:
            summary_items.append(Panel(light_table, title="[green]Light Status[/green]", border_style="green"))

    console.print(Columns(summary_items, equal=True, expand=True))
    console.print()

    # Experiment table
    table = Table(
        title=f"Experiments" + (f" (showing last {limit})" if limit else ""),
        box=box.ROUNDED,
        show_lines=False,
        expand=False
    )

    # Check for enriched metric columns
    has_light_col = "has_light" in history.columns
    has_cnp = "cnp_voltage" in history.columns
    has_delta_current = "delta_current" in history.columns
    has_delta_voltage = "delta_voltage" in history.columns
    has_power = "irradiated_power_w" in history.columns

    if has_light_col:
        table.add_column("💡", style="bold", width=3, justify="center")

    table.add_column("Seq", style="dim", width=5, justify="right")
    table.add_column("Date", style="cyan", width=12)
    table.add_column("Time", style="green", width=10)
    table.add_column("Proc", style="yellow", width=6)

    # Add derived metrics columns if they exist
    if has_cnp:
        table.add_column("CNP (V)", style="magenta", width=9, justify="right")
    if has_delta_current:
        table.add_column("ΔI (μA)", style="blue", width=9, justify="right")
    if has_delta_voltage:
        table.add_column("ΔV (mV)", style="blue", width=9, justify="right")
    if has_power:
        table.add_column("Power (μW)", style="bright_yellow", width=10, justify="right")

    table.add_column("Description", style="white")

    # Group by date for visual separation
    current_date = None
    for row in history.iter_rows(named=True):
        date = row.get("date", "unknown")

        # Add separator when date changes
        if date != current_date and current_date is not None:
            table.add_row("", "", "", "", "", end_section=True)

        current_date = date

        # Build description from summary
        summary = row.get("summary", "")
        # Remove chip name and sequence number from summary for cleaner display
        desc = summary
        for prefix in [chip_name, f"{chip_group}{chip_number}"]:
            desc = desc.replace(prefix, "").strip()
        # Remove leading procedure name (already in Proc column)
        proc = row.get("proc", "")
        if desc.startswith(proc):
            desc = desc[len(proc):].strip()

        # Truncate if too long
        has_derived_metrics = (has_cnp or has_delta_current or has_delta_voltage or has_power)
        desc_max_len = 50 if has_derived_metrics else 80
        if len(desc) > desc_max_len:
            desc = desc[:desc_max_len-3] + "..."

        # Build row data
        row_data = []

        # Light indicator
        if has_light_col:
            has_light = row.get("has_light")
            if has_light is True:
                light_icon = "💡"
            elif has_light is False:
                light_icon = "🌙"
            else:
                light_icon = "[red]❗[/red]"
            row_data.append(light_icon)

        # Basic columns
        row_data.extend([
            str(row.get("seq", "?")),
            date,
            row.get("time_hms", "?"),
            proc
        ])

        # Add derived metrics if columns exist
        if has_cnp:
            cnp_val = row.get("cnp_voltage")
            if cnp_val is not None and cnp_val != "":
                try:
                    cnp_float = float(cnp_val) if isinstance(cnp_val, str) else cnp_val
                    if not (cnp_float != cnp_float):  # Check for NaN
                        row_data.append(f"{cnp_float:.3f}")
                    else:
                        row_data.append("—")
                except (ValueError, TypeError):
                    row_data.append("—")
            else:
                row_data.append("—")

        if has_delta_current:
            delta_i = row.get("delta_current")
            if delta_i is not None and delta_i != "":
                try:
                    delta_i_float = float(delta_i) if isinstance(delta_i, str) else delta_i
                    if not (delta_i_float != delta_i_float):  # Check for NaN
                        row_data.append(f"{delta_i_float*1e6:.2f}")  # Convert to μA
                    else:
                        row_data.append("—")
                except (ValueError, TypeError):
                    row_data.append("—")
            else:
                row_data.append("—")

        if has_delta_voltage:
            delta_v = row.get("delta_voltage")
            if delta_v is not None and delta_v != "":
                try:
                    delta_v_float = float(delta_v) if isinstance(delta_v, str) else delta_v
                    if not (delta_v_float != delta_v_float):  # Check for NaN
                        row_data.append(f"{delta_v_float*1e3:.2f}")  # Convert to mV
                    else:
                        row_data.append("—")
                except (ValueError, TypeError):
                    row_data.append("—")
            else:
                row_data.append("—")

        if has_power:
            power = row.get("irradiated_power_w")
            if power is not None and power != "":
                try:
                    power_float = float(power) if isinstance(power, str) else power
                    if not (power_float != power_float):  # Check for NaN
                        row_data.append(f"{power_float*1e6:.2f}")  # Convert to μW
                    else:
                        row_data.append("—")
                except (ValueError, TypeError):
                    row_data.append("—")
            else:
                row_data.append("—")

        # Description
        row_data.append(desc)

        table.add_row(*row_data)

    console.print(table)
    console.print()

    # Footer with file info
    console.print(f"[dim]Data source: {history_file}[/dim]")

    # Show active filters
    applied_filters = [f for f in applied_filters if not f.startswith("limit=")]
    if applied_filters:
        console.print(f"[dim]Filters: {', '.join(applied_filters)}[/dim]")

    if limit:
        console.print(f"[yellow]Note:[/yellow] Showing only last {limit} experiments. Remove --limit to see all.")


@cli_command(
    name="build-history",
    group="history",
    description="Build chip history from staged data"
)
def build_history_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name prefix"
    ),
    manifest_path: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Path to manifest.parquet file (default: from config)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for history files (default: from config)"
    ),
):
    """
    Build chip history from staged manifest data for a specific chip.

    Generates a chronological history CSV file from the manifest.parquet
    created during the staging process.

    Examples:
        # Build history for chip 67
        process_and_analyze build-history 67

        # Build history for chip 72 with custom manifest
        process_and_analyze build-history 72 -m /path/to/manifest.parquet
    """
    # Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    if manifest_path is None:
        manifest_path = config.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
        if config.verbose:
            console.print(f"[dim]Using manifest path from config: {manifest_path}[/dim]")

    if output_dir is None:
        output_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using output directory from config: {output_dir}[/dim]")

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Build Chip History from Staged Data[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    # Check manifest exists
    if not manifest_path.exists():
        console.print(f"[red]Error:[/red] Manifest not found: {manifest_path}")
        console.print(f"\n[yellow]Hint:[/yellow] Run [cyan]stage-all[/cyan] first to create the manifest.")
        raise typer.Exit(1)

    chip_name = f"{chip_group}{chip_number}"

    try:
        # Build history
        console.print(f"[cyan]Building history for:[/cyan] {chip_name}")
        console.print(f"[cyan]Reading manifest:[/cyan] {manifest_path}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Building history...", total=None)

            history = build_chip_history_from_manifest(
                manifest_path,
                chip_number=chip_number,
                chip_group=chip_group,
            )

            progress.update(task, completed=True)

        if len(history) == 0:
            console.print(f"\n[yellow]Warning:[/yellow] No experiments found for {chip_name}")
            console.print()
            raise typer.Exit(0)

        # Save history
        output_path = save_chip_history(history, output_dir, chip_name)

        console.print()
        console.print(Panel.fit(
            f"[bold green]✓ History Built Successfully[/bold green]\n\n"
            f"Chip: {chip_name}\n"
            f"Experiments: {len(history)}\n"
            f"Output: {output_path}",
            border_style="green"
        ))
        console.print()

        # Show preview
        console.print(f"[cyan]Preview (first 10 experiments):[/cyan]")
        preview_table = Table(box=box.SIMPLE)
        preview_table.add_column("Seq", justify="right")
        preview_table.add_column("Date")
        preview_table.add_column("Proc")
        preview_table.add_column("Summary", overflow="fold")

        for row in history.head(10).iter_rows(named=True):
            preview_table.add_row(
                str(row.get("seq", "?")),
                row.get("date", "?"),
                row.get("proc", "?"),
                row.get("summary", "")[:60] + "..." if len(row.get("summary", "")) > 60 else row.get("summary", "")
            )

        console.print(preview_table)
        console.print()

    except Exception as e:
        console.print()
        console.print(Panel.fit(
            f"[bold red]✗ Build Failed[/bold red]\n\n"
            f"Error: {str(e)}",
            border_style="red"
        ))
        console.print()
        raise typer.Exit(1)


@cli_command(
    name="build-all-histories",
    group="history",
    description="Build histories for all chips from staged data"
)
def build_all_histories_command(
    manifest_path: Path = typer.Option(
        Path("data/02_stage/raw_measurements/_manifest/manifest.parquet"),
        "--manifest",
        "-m",
        help="Path to manifest.parquet file"
    ),
    output_dir: Path = typer.Option(
        Path("data/02_stage/chip_histories"),
        "--output",
        "-o",
        help="Output directory for history files"
    ),
    chip_group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Filter by chip group (e.g., 'Alisson')"
    ),
    min_experiments: int = typer.Option(
        1,
        "--min-experiments",
        "-n",
        help="Minimum experiments required to generate history"
    ),
):
    """
    Build histories for all chips found in staged manifest data.

    Automatically discovers all unique chips and creates individual
    history CSV files. Useful for batch processing after staging.

    Examples:
        # Build histories for all chips
        process_and_analyze build-all-histories

        # Build only for Alisson chips with at least 10 experiments
        process_and_analyze build-all-histories -g Alisson -n 10
    """
    # Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    if manifest_path is None:
        manifest_path = config.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
        if config.verbose:
            console.print(f"[dim]Using manifest path from config: {manifest_path}[/dim]")

    if output_dir is None:
        output_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using output directory from config: {output_dir}[/dim]")

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Build All Chip Histories from Staged Data[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    # Check manifest exists
    if not manifest_path.exists():
        console.print(f"[red]Error:[/red] Manifest not found: {manifest_path}")
        console.print(f"\n[yellow]Hint:[/yellow] Run [cyan]stage-all[/cyan] first to create the manifest.")
        raise typer.Exit(1)

    try:
        console.print(f"[cyan]Reading manifest:[/cyan] {manifest_path}")
        if chip_group:
            console.print(f"[cyan]Filtering by group:[/cyan] {chip_group}")
        console.print(f"[cyan]Minimum experiments:[/cyan] {min_experiments}")
        console.print()

        # Generate histories
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Discovering chips and building histories...", total=None)

            histories = generate_all_chip_histories(
                manifest_path,
                output_dir,
                min_experiments=min_experiments,
                chip_group=chip_group,
            )

            progress.update(task, completed=True)

        if not histories:
            console.print(f"[yellow]Warning:[/yellow] No chips found with at least {min_experiments} experiments")
            console.print()
            raise typer.Exit(0)

        # Show results
        console.print(Panel.fit(
            f"[bold green]✓ Histories Built Successfully[/bold green]\n\n"
            f"Chips processed: {len(histories)}\n"
            f"Output directory: {output_dir}",
            border_style="green"
        ))
        console.print()

        # List generated files
        console.print(f"[cyan]Generated history files:[/cyan]")
        result_table = Table(box=box.SIMPLE)
        result_table.add_column("Chip Name", style="yellow")
        result_table.add_column("File Path", style="white")

        for chip_name, file_path in sorted(histories.items()):
            result_table.add_row(chip_name, str(file_path))

        console.print(result_table)
        console.print()

        console.print(f"[dim]Tip: Use [cyan]show-history <chip_number>[/cyan] to view a chip's history[/dim]")
        console.print()

    except Exception as e:
        console.print()
        console.print(Panel.fit(
            f"[bold red]✗ Build Failed[/bold red]\n\n"
            f"Error: {str(e)}",
            border_style="red"
        ))
        console.print()
        raise typer.Exit(1)


@cli_command(
    name="enrich-histories-with-calibrations",
    group="history",
    description="Associate light experiments with laser calibrations"
)
def enrich_histories_command(
    history_dir: Optional[Path] = typer.Option(
        None,
        "--history-dir",
        "-d",
        help="Directory containing chip history Parquet files (default: from config)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory for enriched histories (default: data/03_derived/chip_histories_enriched/)"
    ),
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="Path to manifest.parquet (default: <stage-root>/_manifest/manifest.parquet)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing enriched history files"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview changes without modifying files"
    ),
    stale_threshold: float = typer.Option(
        24.0,
        "--stale-threshold",
        help="Hours beyond which calibration is considered stale (default: 24)"
    ),
    verbose_warnings: bool = typer.Option(
        False,
        "--verbose-warnings",
        help="Show all warnings (default: show first 10 per chip)"
    ),
):
    """
    Enrich chip histories with laser calibration associations.

    Reads chip histories from Stage 2 (data/02_stage/chip_histories/) and
    writes enriched versions to Stage 3 (data/03_derived/chip_histories_enriched/)
    with three new columns:
    - calibration_parquet_path: Path to associated calibration Parquet
    - calibration_time_delta_hours: Time between experiment and calibration
    - irradiated_power_w: Interpolated power from calibration curve

    The matching strategy:
    1. PREFERRED: Most recent calibration BEFORE experiment (same wavelength)
    2. FALLBACK: Nearest calibration AFTER experiment (same wavelength)
    3. WARNING: No calibration found for wavelength

    \\b
    Examples:
        # Enrich all chip histories (writes to Stage 3)
        enrich-histories-with-calibrations

        # Dry run (preview changes)
        enrich-histories-with-calibrations --dry-run

        # Force re-enrichment
        enrich-histories-with-calibrations --force

        # Custom stale threshold (48 hours)
        enrich-histories-with-calibrations --stale-threshold 48

        # Custom paths
        enrich-histories-with-calibrations --history-dir data/02_stage/chip_histories --output-dir data/03_derived/custom

    \\b
    Output:
        - Writes to: data/03_derived/chip_histories_enriched/ (Stage 3)
        - Stage 2 files remain unchanged (immutable)
        - Displays summary report per chip

    \\b
    Notes:
        - Requires LaserCalibration data in manifest
        - Only processes experiments with with_light=True
        - Skips LaserCalibration experiments themselves
        - Wavelength matching is strict (no tolerance)
        - This is a DERIVED METRIC extraction (Stage 3), not raw metadata (Stage 2)
    """
    from src.derived.extractors import CalibrationMatcher, print_enrichment_report

    # Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    if history_dir is None:
        history_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    if output_dir is None:
        # Default: data/03_derived/chip_histories_enriched/ (Stage 3)
        # Derive from stage_dir: data/02_stage -> data/03_derived
        output_dir = config.stage_dir.parent / "03_derived" / "chip_histories_enriched"
        if config.verbose:
            console.print(f"[dim]Using output directory: {output_dir}[/dim]")

    if manifest is None:
        # Default manifest location
        manifest = config.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
        if config.verbose:
            console.print(f"[dim]Using manifest from: {manifest}[/dim]")

    # Validate paths
    if not history_dir.exists():
        console.print(f"[red]✗[/red] History directory not found: {history_dir}")
        console.print("[yellow]→[/yellow] Run: [cyan]python3 process_and_analyze.py build-all-histories[/cyan]")
        raise typer.Exit(1)

    if not manifest.exists():
        console.print(f"[red]✗[/red] Manifest not found: {manifest}")
        console.print("[yellow]→[/yellow] Run: [cyan]python3 process_and_analyze.py stage-all[/cyan]")
        raise typer.Exit(1)

    # Find history files
    history_files = sorted(history_dir.glob("*_history.parquet"))
    if len(history_files) == 0:
        console.print(f"[red]✗[/red] No chip history files found in {history_dir}")
        console.print("[yellow]→[/yellow] Run: [cyan]python3 process_and_analyze.py build-all-histories[/cyan]")
        raise typer.Exit(1)

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Laser Calibration Enrichment[/bold cyan]\n\n"
        f"Input (Stage 2): {history_dir}\n"
        f"Output (Stage 3): {output_dir}\n"
        f"Manifest: {manifest}\n"
        f"Chip histories: {len(history_files)}\n"
        f"Stale threshold: {stale_threshold:.0f} hours",
        border_style="cyan"
    ))

    if dry_run:
        console.print()
        console.print("[yellow]🔍 DRY RUN MODE - No files will be modified[/yellow]")

    # Initialize matcher
    try:
        console.print()
        console.print("[cyan]Loading laser calibrations from manifest...[/cyan]")
        matcher = CalibrationMatcher(manifest)
        console.print(f"[green]✓[/green] Found {matcher.calibrations.height} laser calibrations")
        console.print(f"[dim]Available wavelengths: {', '.join([f'{w:.0f}nm' for w in matcher.available_wavelengths])}[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load calibrations: {str(e)}")
        raise typer.Exit(1)

    # Process each chip history
    console.print()
    console.print(f"[cyan]Processing {len(history_files)} chip histories...[/cyan]")
    console.print()

    all_reports = []
    total_matched = 0
    total_missing = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Enriching histories...", total=len(history_files))

        for history_path in history_files:
            chip_name = history_path.stem.replace("_history", "")
            progress.update(task, description=f"[cyan]Processing {chip_name}...")

            try:
                if not dry_run:
                    report = matcher.enrich_chip_history(
                        history_path,
                        output_dir=output_dir,
                        force=force,
                        stale_threshold_hours=stale_threshold
                    )
                else:
                    # Dry run: just analyze without writing
                    history = pl.read_parquet(history_path)
                    light_col = "has_light" if "has_light" in history.columns else "with_light"
                    light_exps = history.filter(
                        (pl.col(light_col) == True) &
                        (pl.col("proc") != "LaserCalibration")
                    )
                    # Create dummy report
                    from src.derived.extractors import EnrichmentReport
                    report = EnrichmentReport(
                        chip_name=chip_name,
                        total_light_exps=light_exps.height,
                        matched_perfect=0,
                        matched_future=0,
                        matched_stale=0,
                        missing=0,
                        warnings=["[DRY RUN] Analysis not performed"],
                        errors=[]
                    )

                all_reports.append(report)
                total_matched += report.matched_perfect + report.matched_future + report.matched_stale
                total_missing += report.missing

            except Exception as e:
                console.print(f"\n[red]✗[/red] Error processing {chip_name}: {str(e)}")

            progress.advance(task)

    # Display individual reports
    console.print()
    console.print("[bold cyan]═══ Individual Chip Reports ═══[/bold cyan]")

    for report in all_reports:
        if report.total_light_exps > 0:  # Only show chips with light experiments
            print_enrichment_report(report, verbose=verbose_warnings)

    # Display summary
    console.print()
    console.print(Panel.fit(
        f"[bold]Enrichment Summary[/bold]\n\n"
        f"Chips processed: {len(history_files)}\n"
        f"Total light experiments: {sum(r.total_light_exps for r in all_reports)}\n"
        f"Matched: {total_matched}\n"
        f"Missing: {total_missing}\n\n"
        f"{'[yellow]DRY RUN - No changes made[/yellow]' if dry_run else '[green]✓ Enrichment complete[/green]'}",
        border_style="cyan"
    ))

    if not dry_run:
        console.print()
        console.print(f"[dim]💾 Enriched histories written to: {output_dir}[/dim]")
        console.print(f"[dim]📂 Stage 2 files remain unchanged (immutable)[/dim]")
        console.print()


@cli_command(
    name="validate-calibration-links",
    group="history",
    description="Validate calibration links in chip histories"
)
def validate_calibration_links_command(
    history_dir: Optional[Path] = typer.Option(
        None,
        "--history-dir",
        "-d",
        help="Directory containing chip history Parquet files (default: from config)"
    ),
):
    """
    Validate that calibration links in chip histories point to existing files.

    Checks all chip histories for calibration_parquet_path columns and
    verifies that the referenced calibration files exist. Useful for
    detecting missing or moved calibration files.

    \\b
    Examples:
        # Validate all chip histories
        validate-calibration-links

        # Custom history directory
        validate-calibration-links --history-dir data/histories
    """
    from src.cli.main import get_config
    config = get_config()

    if history_dir is None:
        history_dir = config.history_dir

    if not history_dir.exists():
        console.print(f"[red]✗[/red] History directory not found: {history_dir}")
        raise typer.Exit(1)

    history_files = sorted(history_dir.glob("*_history.parquet"))
    if len(history_files) == 0:
        console.print(f"[red]✗[/red] No chip history files found in {history_dir}")
        raise typer.Exit(1)

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Calibration Link Validation[/bold cyan]\n\n"
        f"Checking {len(history_files)} chip histories...",
        border_style="cyan"
    ))
    console.print()

    total_links = 0
    valid_links = 0
    broken_links = 0
    chips_with_issues = []

    for history_path in history_files:
        chip_name = history_path.stem.replace("_history", "")
        history = pl.read_parquet(history_path)

        if "calibration_parquet_path" not in history.columns:
            console.print(f"[yellow]⚠[/yellow] {chip_name}: Not enriched (no calibration column)")
            continue

        # Get all non-null calibration paths
        cal_paths = history.filter(
            pl.col("calibration_parquet_path").is_not_null()
        )["calibration_parquet_path"].unique().to_list()

        if len(cal_paths) == 0:
            continue

        total_links += len(cal_paths)
        chip_broken = []

        for cal_path in cal_paths:
            if not Path(cal_path).exists():
                broken_links += 1
                chip_broken.append(cal_path)
            else:
                valid_links += 1

        if chip_broken:
            chips_with_issues.append((chip_name, chip_broken))
            console.print(f"[red]✗[/red] {chip_name}: {len(chip_broken)} broken link(s)")
            for path in chip_broken[:3]:  # Show first 3
                console.print(f"    [dim]{path}[/dim]")
            if len(chip_broken) > 3:
                console.print(f"    [dim]... and {len(chip_broken)-3} more[/dim]")
        else:
            console.print(f"[green]✓[/green] {chip_name}: All links valid")

    # Summary
    console.print()
    if broken_links == 0:
        console.print(Panel.fit(
            f"[bold green]✓ All Calibration Links Valid[/bold green]\n\n"
            f"Total links checked: {total_links}\n"
            f"Valid: {valid_links}",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]✗ Broken Calibration Links Found[/bold red]\n\n"
            f"Total links: {total_links}\n"
            f"Valid: {valid_links}\n"
            f"Broken: {broken_links}\n\n"
            f"Chips affected: {len(chips_with_issues)}",
            border_style="red"
        ))
        console.print()
        console.print("[yellow]→[/yellow] Re-run enrichment to fix: [cyan]enrich-histories-with-calibrations --force[/cyan]")

    console.print()
