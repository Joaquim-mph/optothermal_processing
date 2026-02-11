"""Unified enrich-history command - consolidates calibration and metric enrichment."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
import polars as pl
import re

console = Console()


@cli_command(
    name="enrich-history",
    group="pipeline",
    description="Enrich chip histories with calibrations and/or metrics"
)
def enrich_history_unified_command(
    chip_number: Optional[str] = typer.Argument(
        None,
        help="Chip number(s): 67, 67,81, or 67-75. Omit to use --all-chips"
    ),
    all_chips: bool = typer.Option(
        False,
        "--all-chips",
        "-a",
        help="Process all chips found in history directory"
    ),
    chip_group: Optional[str] = typer.Option(
        None,
        "--chip-group",
        "-g",
        help="Filter by chip group (e.g., Alisson)"
    ),
    calibrations_only: bool = typer.Option(
        False,
        "--calibrations-only",
        help="Only add power data (skip metrics)"
    ),
    metrics_only: bool = typer.Option(
        False,
        "--metrics-only",
        help="Only add derived metrics (skip calibrations)"
    ),
    metrics: str = typer.Option(
        "all",
        "--metrics",
        "-m",
        help="Metrics to add: cnp, photoresponse, all (comma-separated)"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Re-enrich even if already enriched"
    ),
    skip_derive: bool = typer.Option(
        False,
        "--skip-derive",
        help="Skip metric extraction (use existing metrics.parquet)"
    ),
    derive_first: bool = typer.Option(
        False,
        "--derive-first",
        help="Force metric extraction before enrichment"
    ),
    workers: int = typer.Option(
        6,
        "--workers",
        "-w",
        help="Parallel workers for processing"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview changes without writing files"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Custom output directory (default: data/03_derived/chip_histories_enriched/)"
    ),
    stale_threshold: float = typer.Option(
        24.0,
        "--stale-threshold",
        help="Hours beyond which calibration is considered stale (default: 24)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output"
    ),
):
    """
    Enrich chip histories with calibrations and/or derived metrics.

    ✨ UNIFIED COMMAND: Replaces enrich-all-histories, enrich-histories-with-calibrations,
    and the old single-chip enrich-history.

    This command can:
    - Add calibration power data (irradiated_power_w column)
    - Add derived metrics (CNP, photoresponse, etc.)
    - Process single chip, multiple chips, or all chips
    - Filter by chip group or specific metrics

    Default behavior: Adds both calibrations and metrics to all enrichments.

    Examples:
        # Most common: enrich everything for all chips
        enrich-history -a

        # Single chip with everything (calibrations + metrics)
        enrich-history 67

        # Multiple specific chips
        enrich-history 67,81,75

        # Chip range
        enrich-history 67-75

        # Only add calibration power data (fast, no metric extraction)
        enrich-history -a --calibrations-only

        # Only add metrics (assumes calibrations already added)
        enrich-history 67 --metrics-only

        # Only specific metric
        enrich-history 67 --metrics cnp

        # Multiple metrics
        enrich-history -a --metrics cnp,photoresponse

        # Force fresh metric extraction
        enrich-history -a --derive-first

        # Dry run to preview changes
        enrich-history -a --dry-run

    See also:
        - derive-all-metrics: Extract metrics from raw measurements first
        - show-history: View enriched history after processing
    """
    from src.cli.main import get_config

    config = get_config()

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Unified History Enrichment[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    # Step 1: Validate flag combinations
    if calibrations_only and metrics_only:
        console.print("[red]Error:[/red] Cannot specify both --calibrations-only and --metrics-only")
        console.print("[yellow]Hint:[/yellow] Omit both flags to add both calibrations and metrics")
        raise typer.Exit(1)

    if not chip_number and not all_chips:
        console.print("[red]Error:[/red] Must specify chip number(s) or --all-chips/-a")
        console.print("[yellow]Examples:[/yellow]")
        console.print("  [cyan]enrich-history 67[/cyan]           # Single chip")
        console.print("  [cyan]enrich-history 67,81,75[/cyan]    # Multiple chips")
        console.print("  [cyan]enrich-history -a[/cyan]          # All chips")
        raise typer.Exit(1)

    # Step 2: Parse chip selection
    console.print("[cyan]Parsing chip selection...[/cyan]")
    try:
        chip_numbers = _parse_chip_selection(chip_number, all_chips, chip_group, config)
        console.print(f"[green]✓[/green] Selected {len(chip_numbers)} chip(s): {', '.join(map(str, chip_numbers))}")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 3: Determine enrichment type
    do_calibrations = not metrics_only
    do_metrics = not calibrations_only

    enrichment_types = []
    if do_calibrations:
        enrichment_types.append("calibrations (power data)")
    if do_metrics:
        enrichment_types.append("metrics (CNP, photoresponse, etc.)")

    console.print(f"[cyan]Enrichment types:[/cyan] {' + '.join(enrichment_types)}")

    # Step 4: Parse metric selection
    metric_list = _parse_metric_selection(metrics)
    if do_metrics and metric_list != ["all"]:
        console.print(f"[cyan]Specific metrics:[/cyan] {', '.join(metric_list)}")

    # Step 5: Setup paths
    history_dir = Path(config.history_dir)
    if output_dir is None:
        output_dir = config.stage_dir.parent / "03_derived" / "chip_histories_enriched"
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[dim]Input: {history_dir}[/dim]")
    console.print(f"[dim]Output: {output_dir}[/dim]")

    if dry_run:
        console.print("[yellow]🔍 DRY RUN MODE - No files will be modified[/yellow]")

    console.print()

    # Step 6: Check prerequisites
    if do_metrics and not skip_derive:
        metrics_path = Path("data/03_derived/_metrics/metrics.parquet")
        if not metrics_path.exists() or derive_first:
            if derive_first:
                console.print("[yellow]⚠[/yellow] --derive-first specified: Running metric extraction...")
            else:
                console.print("[yellow]⚠[/yellow] Metrics not found: Running metric extraction first...")

            if not dry_run:
                _run_derive_all_metrics(chip_numbers, chip_group, workers, console)
            else:
                console.print("[dim]  [DRY RUN] Would run: derive-all-metrics[/dim]")
            console.print()

    # Step 7: Run enrichment pipeline
    success_count = 0
    error_count = 0
    skipped_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Enriching {len(chip_numbers)} chip(s)...",
            total=len(chip_numbers)
        )

        for chip_num in chip_numbers:
            chip_name = f"{chip_group or 'Alisson'}{chip_num}"
            progress.update(task, description=f"[cyan]Processing {chip_name}...")

            try:
                # Check if history exists
                history_file = history_dir / f"{chip_name}_history.parquet"
                if not history_file.exists():
                    console.print(f"\n[yellow]⚠[/yellow] Skipping {chip_name}: history file not found")
                    skipped_count += 1
                    progress.advance(task)
                    continue

                # Run calibrations enrichment
                if do_calibrations:
                    _enrich_calibrations(
                        chip_name,
                        history_file,
                        output_dir,
                        stale_threshold,
                        force,
                        dry_run,
                        console,
                        verbose
                    )

                # Run metrics enrichment
                if do_metrics:
                    _enrich_metrics(
                        chip_name,
                        chip_num,
                        chip_group or "Alisson",
                        output_dir,
                        metric_list,
                        force,
                        dry_run,
                        console,
                        verbose
                    )

                success_count += 1

            except Exception as e:
                console.print(f"\n[red]✗[/red] Error processing {chip_name}: {str(e)}")
                if verbose:
                    import traceback
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
                error_count += 1

            progress.advance(task)

    # Step 8: Summary
    console.print()
    console.print(Panel.fit(
        f"[bold]Enrichment Summary[/bold]\n\n"
        f"[green]✓ Success:[/green] {success_count} chip(s)\n"
        f"[yellow]⚠ Skipped:[/yellow] {skipped_count} chip(s)\n"
        f"[red]✗ Errors:[/red] {error_count} chip(s)\n\n"
        f"[cyan]Output directory:[/cyan] {output_dir}",
        title="[bold]Results[/bold]",
        border_style="cyan"
    ))

    if dry_run:
        console.print("\n[yellow]🔍 DRY RUN COMPLETE - No files were modified[/yellow]")
        console.print("[dim]Remove --dry-run to perform actual enrichment[/dim]")

    console.print()


def _parse_chip_selection(
    chip_number: Optional[str],
    all_chips: bool,
    chip_group: Optional[str],
    config
) -> List[int]:
    """
    Parse chip number argument into list of chip numbers.

    Supports:
    - Single: 67
    - Multiple: 67,81,75
    - Range: 67-75
    - All: --all-chips (finds from history directory)
    """
    if all_chips:
        # Find all chips in history directory
        history_dir = Path(config.history_dir)
        if not history_dir.exists():
            raise ValueError(f"History directory not found: {history_dir}")

        history_files = sorted(history_dir.glob("*_history.parquet"))
        if not history_files:
            raise ValueError(f"No chip history files found in {history_dir}")

        chip_numbers = []
        for file in history_files:
            # Extract chip number from filename: Alisson67_history.parquet -> 67
            stem = file.stem.replace("_history", "")
            match = re.match(r'([A-Za-z]+)(\d+)', stem)
            if match:
                group, num = match.groups()
                if chip_group is None or group == chip_group:
                    chip_numbers.append(int(num))

        if not chip_numbers:
            if chip_group:
                raise ValueError(f"No chips found for group '{chip_group}'")
            else:
                raise ValueError("No chips found in history directory")

        return sorted(chip_numbers)

    elif chip_number:
        # Parse: 67, 67,81,75, or 67-75
        chip_number = chip_number.strip()

        if "," in chip_number:
            # Multiple: 67,81,75
            return [int(x.strip()) for x in chip_number.split(",")]
        elif "-" in chip_number:
            # Range: 67-75
            parts = chip_number.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid range format: '{chip_number}'. Use format: 67-75")
            start, end = parts
            return list(range(int(start.strip()), int(end.strip()) + 1))
        else:
            # Single: 67
            return [int(chip_number)]
    else:
        raise ValueError("Must specify chip number or --all-chips")


def _parse_metric_selection(metrics: str) -> List[str]:
    """Parse metrics string into list of metric names."""
    if metrics.lower() == "all":
        return ["all"]
    return [m.strip().lower() for m in metrics.split(",")]


def _run_derive_all_metrics(
    chip_numbers: List[int],
    chip_group: Optional[str],
    workers: int,
    console: Console
):
    """Run metric extraction for specified chips."""
    from src.derived.metric_pipeline import MetricPipeline

    console.print("[cyan]Running metric extraction pipeline...[/cyan]")

    pipeline = MetricPipeline(
        base_dir=Path("."),
        extraction_version=None  # Auto-detect from git
    )

    # Extract metrics
    metrics_path = pipeline.derive_all_metrics(
        procedures=None,  # All procedures
        chip_numbers=chip_numbers if chip_numbers else None,
        parallel=True,
        workers=workers,
        skip_existing=False
    )

    console.print(f"[green]✓[/green] Metrics extracted to {metrics_path}")


def _enrich_calibrations(
    chip_name: str,
    history_file: Path,
    output_dir: Path,
    stale_threshold: float,
    force: bool,
    dry_run: bool,
    console: Console,
    verbose: bool
):
    """Add calibration power columns using CalibrationMatcher."""
    from src.derived.extractors import CalibrationMatcher

    manifest_path = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
    if not manifest_path.exists():
        console.print(f"[yellow]⚠[/yellow] Manifest not found, skipping calibration enrichment for {chip_name}")
        return

    try:
        matcher = CalibrationMatcher(manifest_path)

        if not dry_run:
            report = matcher.enrich_chip_history(
                history_file,
                output_dir=output_dir,
                force=force,
                stale_threshold_hours=stale_threshold
            )

            if verbose and report:
                console.print(f"  [dim]{chip_name}: {report.matched_perfect} perfect, "
                            f"{report.matched_future} future, {report.matched_stale} stale, "
                            f"{report.missing} missing[/dim]")
    except Exception as e:
        if verbose:
            console.print(f"  [yellow]⚠[/yellow] Calibration enrichment warning for {chip_name}: {e}")


def _enrich_metrics(
    chip_name: str,
    chip_num: int,
    chip_group: str,
    output_dir: Path,
    metric_list: List[str],
    force: bool,
    dry_run: bool,
    console: Console,
    verbose: bool
):
    """Add derived metric columns by joining with metrics.parquet."""
    metrics_path = Path("data/03_derived/_metrics/metrics.parquet")

    if not metrics_path.exists():
        console.print(f"[yellow]⚠[/yellow] Metrics not found, skipping metric enrichment for {chip_name}")
        console.print("[dim]  Run 'derive-all-metrics' first or use --derive-first[/dim]")
        return

    if dry_run:
        console.print(f"  [dim]{chip_name}: Would add metric columns[/dim]")
        return

    try:
        # Load metrics
        all_metrics = pl.read_parquet(metrics_path)

        # Filter by chip if needed
        chip_metrics = all_metrics.filter(
            (pl.col("chip_number") == chip_num) &
            (pl.col("chip_group") == chip_group)
        )

        # Filter by metric type if not "all"
        if metric_list != ["all"]:
            chip_metrics = chip_metrics.filter(
                pl.col("metric_name").is_in(metric_list)
            )

        if chip_metrics.height == 0:
            if verbose:
                console.print(f"  [dim]{chip_name}: No metrics found[/dim]")
            return

        # Load enriched history (may already have calibrations)
        enriched_path = output_dir / f"{chip_name}_history.parquet"
        if enriched_path.exists():
            history = pl.read_parquet(enriched_path)
        else:
            # Load from base directory
            from src.cli.main import get_config
            config = get_config()
            base_path = Path(config.history_dir) / f"{chip_name}_history.parquet"
            if not base_path.exists():
                console.print(f"[yellow]⚠[/yellow] History not found for {chip_name}")
                return
            history = pl.read_parquet(base_path)

        # Pivot metrics to columns
        # Group by run_id and create columns for each metric
        # Use value_float directly to preserve numeric dtype (coalesce with string cols casts to String)
        metric_cols = {}
        for metric_name in chip_metrics["metric_name"].unique().to_list():
            metric_data = chip_metrics.filter(pl.col("metric_name") == metric_name)
            metric_cols[metric_name] = metric_data.select([
                "run_id",
                pl.col("value_float").alias(metric_name)
            ])

        # Join metrics to history
        for metric_name, metric_df in metric_cols.items():
            history = history.join(metric_df, on="run_id", how="left")

        # Save enriched history
        enriched_path.parent.mkdir(parents=True, exist_ok=True)
        history.write_parquet(enriched_path)

        if verbose:
            console.print(f"  [dim]{chip_name}: Added {len(metric_cols)} metric column(s)[/dim]")

    except Exception as e:
        if verbose:
            console.print(f"  [yellow]⚠[/yellow] Metric enrichment warning for {chip_name}: {e}")
