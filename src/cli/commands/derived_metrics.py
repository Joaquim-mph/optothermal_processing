"""Derived metrics pipeline commands: derive-all-metrics, enrich-history."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import polars as pl

console = Console()


@cli_command(
    name="derive-all-metrics",
    group="pipeline",
    description="Extract derived metrics from all measurements"
)
def derive_all_metrics_command(
    procedures: Optional[str] = typer.Option(
        None,
        "--procedures",
        "-p",
        help="Comma-separated list of procedures to process (e.g., 'IVg,VVg'). Default: all applicable procedures"
    ),
    chip_group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Filter by chip group (e.g., 'Alisson')"
    ),
    chip_number: Optional[int] = typer.Option(
        None,
        "--chip",
        "-c",
        help="Filter by specific chip number"
    ),
    workers: int = typer.Option(
        6,
        "--workers",
        "-w",
        help="Number of parallel worker processes"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-extraction (overwrite existing metrics)"
    ),
    include_calibrations: bool = typer.Option(
        True,
        "--calibrations/--no-calibrations",
        help="Include laser calibration power extraction (default: True)"
    ),
    stale_threshold: float = typer.Option(
        24.0,
        "--stale-threshold",
        help="Hours beyond which calibration is considered stale (default: 24)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be extracted without actually processing"
    ),
):
    """
    Extract derived metrics from staged measurements.

    This command runs metric extractors (CNP, photoresponse, etc.) on all
    applicable measurements and saves results to the derived metrics database.

    Optionally (enabled by default) also performs laser calibration power
    extraction, associating light experiments with calibrations and interpolating
    irradiated power values.

    Examples:
        # Extract all metrics from all measurements (includes calibrations)
        python process_and_analyze.py derive-all-metrics

        # Extract only CNP metrics from IVg/VVg
        python process_and_analyze.py derive-all-metrics --procedures IVg,VVg

        # Extract metrics for specific chip
        python process_and_analyze.py derive-all-metrics --chip 75

        # Skip calibration enrichment
        python process_and_analyze.py derive-all-metrics --no-calibrations

        # Preview without processing
        python process_and_analyze.py derive-all-metrics --dry-run
    """
    console.print()
    console.print(Panel.fit(
        "[bold green]Derived Metrics Extraction Pipeline[/bold green]",
        border_style="green"
    ))
    console.print()

    # Parse procedure list
    procedure_list = None
    if procedures:
        procedure_list = [p.strip() for p in procedures.split(',')]
        console.print(f"[cyan]Filtering procedures:[/cyan] {', '.join(procedure_list)}")

    # Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    # Initialize pipeline
    try:
        from src.derived.metric_pipeline import MetricPipeline

        console.print("[cyan]Initializing metric pipeline...[/cyan]")
        pipeline = MetricPipeline(
            base_dir=Path("."),  # Project root
            extraction_version=None  # Auto-detect from git
        )

        # Prepare chip number filter
        chip_numbers_list = None
        if chip_number:
            chip_numbers_list = [chip_number]

        # Apply filters
        if chip_group or chip_number:
            console.print("[cyan]Applying filters...[/cyan]")
            if chip_group:
                console.print(f"  • Chip group: {chip_group}")
            if chip_number:
                console.print(f"  • Chip number: {chip_number}")

        # Dry run mode
        if dry_run:
            console.print()
            console.print("[bold yellow]DRY RUN MODE[/bold yellow] - Preview only, no metrics will be extracted")
            console.print()

            # Load manifest to show what would be processed
            manifest_path = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest_path}")

            manifest = pl.read_parquet(manifest_path)

            # Apply filters
            if chip_group:
                manifest = manifest.filter(pl.col("chip_group") == chip_group)
            if chip_numbers_list:
                manifest = manifest.filter(pl.col("chip_number").is_in(chip_numbers_list))
            if procedure_list:
                manifest = manifest.filter(pl.col("proc").is_in(procedure_list))

            # Show summary
            console.print(f"[green]✓[/green] Would process {manifest.height} measurements")

            # Group by procedure
            by_proc = manifest.group_by("proc").agg(pl.count().alias("count"))

            table = Table(title="Measurements by Procedure")
            table.add_column("Procedure", style="cyan")
            table.add_column("Count", justify="right", style="green")

            for row in by_proc.iter_rows(named=True):
                table.add_row(row["proc"], str(row["count"]))

            console.print()
            console.print(table)
            console.print()
            console.print("[dim]Run without --dry-run to extract metrics[/dim]")
            raise typer.Exit(0)

        # Note: chip_group filtering requires loading manifest first
        # since MetricPipeline doesn't support chip_group filter
        if chip_group and not chip_numbers_list:
            # Need to find chip numbers for this group
            manifest_path = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
            manifest = pl.read_parquet(manifest_path)
            chip_numbers_list = (manifest
                                .filter(pl.col("chip_group") == chip_group)
                                .select("chip_number")
                                .unique()
                                .to_series()
                                .to_list())
            console.print(f"[dim]Found {len(chip_numbers_list)} chips in group '{chip_group}'[/dim]")

        # Run extraction
        console.print()
        console.print("[cyan]Extracting metrics...[/cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing measurements...", total=None)

            metrics_path = pipeline.derive_all_metrics(
                procedures=procedure_list,
                chip_numbers=chip_numbers_list,
                parallel=(workers > 1),
                workers=workers,
                skip_existing=(not force)
            )

            progress.update(task, completed=True)

        # Load results to show stats
        metrics_df = pl.read_parquet(metrics_path)

        # Display results
        console.print()
        console.print(Panel(
            f"[green]✓ Extracted {metrics_df.height} metrics[/green]\n"
            f"[cyan]Output:[/cyan] {metrics_path}",
            title="[bold]Extraction Complete[/bold]",
            border_style="green"
        ))

        # Show summary by metric type
        if metrics_df.height > 0:
            metric_summary = (metrics_df
                            .group_by("metric_name")
                            .agg(pl.count().alias("count"))
                            .sort("metric_name"))

            table = Table(title="Extracted Metrics Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", justify="right", style="green")

            for row in metric_summary.iter_rows(named=True):
                table.add_row(row["metric_name"], str(row["count"]))

            console.print()
            console.print(table)

        # ══════════════════════════════════════════════════════════════════
        # Step 2: Laser Calibration Power Extraction
        # ══════════════════════════════════════════════════════════════════

        if include_calibrations:
            console.print()
            console.print(Panel.fit(
                "[bold cyan]Laser Calibration Power Extraction[/bold cyan]",
                border_style="cyan"
            ))
            console.print()

            try:
                from src.derived.extractors import CalibrationMatcher, print_enrichment_report

                # Initialize calibration matcher
                manifest_path = config.stage_dir / "raw_measurements" / "_manifest" / "manifest.parquet"
                console.print("[cyan]Loading laser calibrations from manifest...[/cyan]")

                matcher = CalibrationMatcher(manifest_path)
                console.print(f"[green]✓[/green] Found {matcher.calibrations.height} laser calibrations")
                console.print(f"[dim]Available wavelengths: {', '.join([f'{w:.0f}nm' for w in matcher.available_wavelengths])}[/dim]")

                # Get chip history directory
                history_dir = config.history_dir
                output_dir = config.stage_dir.parent / "03_derived" / "chip_histories_enriched"

                # Filter history files if chip filters were specified
                history_files = sorted(history_dir.glob("*_history.parquet"))

                if chip_group:
                    history_files = [f for f in history_files if f.stem.startswith(chip_group)]

                if chip_number:
                    chip_name = f"{chip_group if chip_group else 'Alisson'}{chip_number}"
                    history_files = [f for f in history_files if f.stem == f"{chip_name}_history"]

                if not history_files:
                    console.print("[yellow]⚠[/yellow] No chip histories found (skipping calibration enrichment)")
                else:
                    console.print(f"[cyan]Processing {len(history_files)} chip histories...[/cyan]")
                    console.print()

                    # Process each history
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
                                report = matcher.enrich_chip_history(
                                    history_path,
                                    output_dir=output_dir,
                                    force=force,
                                    stale_threshold_hours=stale_threshold
                                )
                                all_reports.append(report)
                                total_matched += report.matched_perfect + report.matched_future + report.matched_stale
                                total_missing += report.missing
                            except Exception as e:
                                console.print(f"\n[red]✗[/red] Error processing {chip_name}: {str(e)}")

                            progress.advance(task)

                    # Display summary
                    console.print()
                    console.print(Panel(
                        f"[green]✓ Calibration enrichment complete[/green]\n"
                        f"[cyan]Chips processed:[/cyan] {len(history_files)}\n"
                        f"[cyan]Light experiments:[/cyan] {sum(r.total_light_exps for r in all_reports)}\n"
                        f"[cyan]Matched:[/cyan] {total_matched}\n"
                        f"[cyan]Missing:[/cyan] {total_missing}\n"
                        f"[cyan]Output:[/cyan] {output_dir}",
                        title="[bold]Calibration Power Extraction[/bold]",
                        border_style="cyan"
                    ))

                    # Show warning summary if there are missing calibrations
                    if total_missing > 0:
                        console.print()
                        console.print(f"[yellow]⚠[/yellow] {total_missing} experiments missing calibrations")
                        console.print("[dim]Use: enrich-histories-with-calibrations --verbose-warnings for details[/dim]")

            except FileNotFoundError:
                console.print("[yellow]⚠[/yellow] No laser calibrations found in manifest (skipping calibration enrichment)")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Calibration enrichment failed: {str(e)}")
                if config.verbose:
                    import traceback
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[yellow]Hint:[/yellow] Run [cyan]stage-all[/cyan] first to create manifest.parquet")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        if config.verbose:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    console.print()


@cli_command(
    name="enrich-history",
    group="pipeline",
    description="Add derived metrics as columns to chip history"
)
def enrich_history_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number to enrich (e.g., 75 for Alisson75)"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    output_suffix: str = typer.Option(
        "_enriched",
        "--suffix",
        "-s",
        help="Suffix for enriched history filename"
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite original history file instead of creating new file"
    ),
):
    """
    Enrich chip history with derived metrics as columns.

    Joins derived metrics (CNP, photoresponse, etc.) to the chip history,
    adding them as additional columns for easy analysis and plotting.

    Examples:
        # Enrich history for chip 75
        python process_and_analyze.py enrich-history 75

        # Enrich and save as new file
        python process_and_analyze.py enrich-history 75 --suffix _with_metrics

        # Enrich and overwrite original
        python process_and_analyze.py enrich-history 75 --overwrite
    """
    console.print()
    console.print(Panel.fit(
        f"[bold green]Enrich History: {chip_group}{chip_number}[/bold green]",
        border_style="green"
    ))
    console.print()

    # Load config
    from src.cli.main import get_config
    config = get_config()

    try:
        from src.derived.metric_pipeline import MetricPipeline

        console.print("[cyan]Loading metric pipeline...[/cyan]")
        pipeline = MetricPipeline(
            base_dir=Path("."),
            extraction_version=None
        )

        console.print(f"[cyan]Enriching history for {chip_group}{chip_number}...[/cyan]")

        enriched_path = pipeline.enrich_chip_history(
            chip_number=chip_number,
            chip_group=chip_group
        )

        if enriched_path is None:
            console.print(f"[red]Error:[/red] No history found for {chip_group}{chip_number}")
            raise typer.Exit(1)

        # Load enriched history to show stats
        enriched_history = pl.read_parquet(enriched_path)

        # Optionally move to custom location
        chip_name = f"{chip_group}{chip_number}"
        if overwrite or output_suffix != "_enriched":
            history_dir = config.history_dir

            if overwrite:
                final_path = history_dir / f"{chip_name}_history.parquet"
                action = "Updated"
            else:
                final_path = history_dir / f"{chip_name}_history{output_suffix}.parquet"
                action = "Created"

            # Copy to final location
            import shutil
            shutil.copy(enriched_path, final_path)
            output_path = final_path
        else:
            output_path = enriched_path
            action = "Created"

        # Show what was added
        original_cols = set(['run_id', 'chip_number', 'chip_group', 'proc', 'seq',
                            'datetime_local', 'has_light', 'parquet_path'])
        new_cols = [col for col in enriched_history.columns if col not in original_cols]

        console.print()
        console.print(Panel(
            f"[green]✓ {action} enriched history[/green]\n"
            f"[cyan]Output:[/cyan] {output_path}\n"
            f"[cyan]Rows:[/cyan] {enriched_history.height}\n"
            f"[cyan]New columns:[/cyan] {len(new_cols)}",
            title="[bold]Enrichment Complete[/bold]",
            border_style="green"
        ))

        if new_cols:
            console.print()
            console.print("[bold]Added metric columns:[/bold]")
            for col in sorted(new_cols):
                # Show how many non-null values
                non_null = enriched_history[col].drop_nulls().len()
                console.print(f"  • [cyan]{col}[/cyan] ({non_null}/{enriched_history.height} values)")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[yellow]Hint:[/yellow] Make sure you've run:")
        console.print("  1. [cyan]build-all-histories[/cyan] - to create chip history")
        console.print("  2. [cyan]derive-all-metrics[/cyan] - to extract metrics")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        if config.verbose:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    console.print()
