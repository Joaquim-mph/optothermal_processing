"""Enrich all chip histories command."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import polars as pl

console = Console()


@cli_command(
    name="enrich-all-histories",
    group="pipeline",
    description="Enrich all chip histories (use 'enrich-history -a' for new unified command)",
    hidden=True
)
def enrich_all_histories_command(
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
    force_derive: bool = typer.Option(
        False,
        "--force-derive",
        help="Force re-extraction of metrics before enrichment"
    ),
    skip_derive: bool = typer.Option(
        False,
        "--skip-derive",
        help="Skip metric extraction, only enrich from existing metrics"
    ),
):
    """
    Enrich all chip histories with derived metrics.

    📦 BATCH PROCESSOR: Orchestrates metric extraction and enrichment for all chips.

    For single chip enrichment, use 'enrich-history <chip_number>' instead.

    This command:
    1. Checks if metrics exist, if not runs derive-all-metrics (unless --skip-derive)
    2. Enriches all chip histories with the derived metrics (CNP, photoresponse, etc.)
    3. Saves enriched histories to data/03_derived/chip_histories_enriched/

    The enriched histories include derived metrics as columns for easy analysis and plotting.

    Pipeline workflow:
        - Quick start: Run this command (handles everything)
        - Manual control: derive-all-metrics → enrich-history (per chip)

    See also:
        - enrich-history: Enrich a single chip
        - derive-all-metrics: Extract metrics only (no enrichment)
        - enrich-histories-with-calibrations: Link laser calibrations

    Examples:
        # Enrich all chip histories (derives metrics if needed)
        python process_and_analyze.py enrich-all-histories

        # Force re-extraction of metrics before enrichment
        python process_and_analyze.py enrich-all-histories --force-derive

        # Only enrich specific chip group
        python process_and_analyze.py enrich-all-histories --group Alisson

        # Only enrich specific chip
        python process_and_analyze.py enrich-all-histories --chip 67

        # Skip metric extraction, only enrich from existing metrics
        python process_and_analyze.py enrich-all-histories --skip-derive
    """
    console.print()

    # Deprecation warning / tip
    console.print(Panel.fit(
        "[bold yellow]💡 TIP: Use the new unified command![/bold yellow]\n\n"
        "Consider using the new unified enrich-history command:\n"
        "[cyan]enrich-history -a[/cyan]  (or [cyan]--all-chips[/cyan])\n\n"
        "It provides the same functionality with more flexibility:\n"
        "• Control calibrations/metrics separately\n"
        "• Filter by specific metrics\n"
        "• Process specific chip ranges",
        border_style="yellow"
    ))
    console.print()

    console.print(Panel.fit(
        "[bold green]Enrich All Chip Histories[/bold green]",
        border_style="green"
    ))
    console.print()

    # Load config
    from src.cli.main import get_config
    config = get_config()

    # Check if metrics exist
    metrics_path = Path("data/03_derived/_metrics/metrics.parquet")

    if not metrics_path.exists() and skip_derive:
        console.print(f"[red]Error:[/red] No metrics found at {metrics_path}")
        console.print("[yellow]Hint:[/yellow] Remove --skip-derive to automatically extract metrics first")
        raise typer.Exit(1)

    # Step 1: Extract metrics if needed
    if not skip_derive:
        if not metrics_path.exists():
            console.print("[yellow]⚠[/yellow] No metrics found - extracting metrics first...")
            console.print()
        elif force_derive:
            console.print("[cyan]ℹ[/cyan] Force derive enabled - re-extracting all metrics...")
            console.print()
        else:
            console.print("[green]✓[/green] Metrics found - using existing metrics")
            console.print(f"[dim]Use --force-derive to re-extract metrics[/dim]")
            console.print()

        if not metrics_path.exists() or force_derive:
            # Run derive-all-metrics
            from src.derived.metric_pipeline import MetricPipeline

            console.print("[cyan]Running metric extraction...[/cyan]")

            pipeline = MetricPipeline(
                base_dir=Path("."),
                extraction_version=None  # Auto-detect from git
            )

            # Prepare filters
            chip_numbers_list = None
            if chip_number:
                chip_numbers_list = [chip_number]
            elif chip_group:
                # Find chip numbers for this group
                manifest_path = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
                if manifest_path.exists():
                    manifest = pl.read_parquet(manifest_path)
                    chip_numbers_list = (manifest
                                        .filter(pl.col("chip_group") == chip_group)
                                        .select("chip_number")
                                        .unique()
                                        .to_series()
                                        .to_list())
                    console.print(f"[dim]Found {len(chip_numbers_list)} chips in group '{chip_group}'[/dim]")

            # Extract metrics
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Extracting metrics...", total=None)

                metrics_path = pipeline.derive_all_metrics(
                    procedures=None,  # All procedures
                    chip_numbers=chip_numbers_list,
                    parallel=True,
                    workers=6,
                    skip_existing=False  # Force re-extraction
                )

                progress.update(task, completed=True)

            console.print(f"[green]✓[/green] Metrics extracted to {metrics_path}")
            console.print()

    # Step 2: Calibration enrichment (add power column)
    console.print("[cyan]Running calibration enrichment...[/cyan]")
    try:
        from src.derived.extractors import CalibrationMatcher

        manifest_path = Path("data/02_stage/raw_measurements/_manifest/manifest.parquet")
        matcher = CalibrationMatcher(manifest_path)

        history_dir = config.history_dir
        output_dir = config.stage_dir.parent / "03_derived" / "chip_histories_enriched"
        history_files = sorted(history_dir.glob("*_history.parquet"))

        # Apply filters
        if chip_group:
            history_files = [f for f in history_files if f.stem.startswith(chip_group)]
        if chip_number:
            chip_name = f"{chip_group if chip_group else 'Alisson'}{chip_number}"
            history_files = [f for f in history_files if f.stem == f"{chip_name}_history"]

        console.print(f"[dim]Adding power data to {len(history_files)} histories...[/dim]")

        for history_path in history_files:
            try:
                matcher.enrich_chip_history(
                    history_path,
                    output_dir=output_dir,
                    force=True  # Always update
                )
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Calibration enrichment warning for {history_path.stem}: {e}")

        console.print(f"[green]✓[/green] Calibration enrichment complete")
        console.print()

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Calibration enrichment failed: {e}")
        if config.verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")

    # Step 3: Metric enrichment (add metric columns to calibration-enriched histories)
    console.print("[cyan]Adding metric columns to enriched histories...[/cyan]")
    try:
        # Load metrics
        metrics_path = Path("data/03_derived/_metrics/metrics.parquet")
        if not metrics_path.exists():
            console.print("[yellow]⚠[/yellow] No metrics found, skipping metric enrichment")
        else:
            metrics = pl.read_parquet(metrics_path)
            enriched_dir = config.stage_dir.parent / "03_derived" / "chip_histories_enriched"
            enriched_files = sorted(enriched_dir.glob("*_history.parquet"))

            # Apply filters
            if chip_group:
                enriched_files = [f for f in enriched_files if f.stem.startswith(chip_group)]
            if chip_number:
                chip_name = f"{chip_group if chip_group else 'Alisson'}{chip_number}"
                enriched_files = [f for f in enriched_files if f.stem == f"{chip_name}_history"]

            if not enriched_files:
                console.print("[yellow]⚠[/yellow] No enriched histories found")
            else:
                console.print(f"[dim]Adding metrics to {len(enriched_files)} enriched histories...[/dim]")

                enriched_count = 0
                error_count = 0
                sample_history = None

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Adding metric columns...", total=len(enriched_files))

                    for enriched_path in enriched_files:
                        chip_name = enriched_path.stem.replace("_history", "")

                        # Extract chip group and number
                        import re
                        match = re.match(r'([A-Za-z]+)(\d+)', chip_name)
                        if not match:
                            console.print(f"\n[yellow]⚠[/yellow] Skipping {chip_name} - invalid format")
                            error_count += 1
                            progress.advance(task)
                            continue

                        extracted_group = match.group(1)
                        extracted_number = int(match.group(2))

                        progress.update(task, description=f"[cyan]{chip_name}...")

                        try:
                            # Read enriched history (already has power column from step 2)
                            history = pl.read_parquet(enriched_path)

                            # Filter metrics for this chip
                            chip_metrics = metrics.filter(
                                (pl.col("chip_number") == extracted_number) &
                                (pl.col("chip_group") == extracted_group)
                            )

                            # Get unique metric names and add them as columns
                            unique_metrics = chip_metrics["metric_name"].unique().to_list()

                            # Drop existing metric columns to avoid duplicates
                            for metric_name in unique_metrics:
                                if metric_name in history.columns:
                                    history = history.drop(metric_name)

                            # Add each metric as a column
                            for metric_name in unique_metrics:
                                metric_df = chip_metrics.filter(pl.col("metric_name") == metric_name)

                                # Select run_id and value (prefer float, then str, then json)
                                metric_df = metric_df.select([
                                    "run_id",
                                    pl.coalesce(["value_float", "value_str", "value_json"]).alias(metric_name)
                                ])

                                # Join to history
                                history = history.join(metric_df, on="run_id", how="left")

                            # Save enriched history (with both power and metrics)
                            history.write_parquet(enriched_path)

                            # Use this as sample if it has any enrichment columns and we don't have one yet
                            if sample_history is None:
                                # Check if this history has enrichment columns
                                power_cols = [col for col in history.columns if 'power' in col.lower()]
                                metric_keywords = ['cnp', 'delta_', 'mobility', 'responsivity']
                                metric_cols = [col for col in history.columns
                                             if any(keyword in col.lower() for keyword in metric_keywords)]
                                if power_cols or metric_cols:
                                    sample_history = history

                            enriched_count += 1

                        except Exception as e:
                            console.print(f"\n[red]✗[/red] Error enriching {chip_name}: {str(e)}")
                            error_count += 1
                            if config.verbose:
                                import traceback
                                console.print(f"[dim]{traceback.format_exc()}[/dim]")

                        progress.advance(task)

                # Display summary
                console.print()
                console.print(Panel(
                    f"[green]✓ Enrichment complete[/green]\n"
                    f"[cyan]Histories processed:[/cyan] {len(enriched_files)}\n"
                    f"[cyan]Successfully enriched:[/cyan] {enriched_count}\n"
                    f"[cyan]Errors:[/cyan] {error_count}\n"
                    f"[cyan]Output:[/cyan] {enriched_dir}",
                    title="[bold]All Histories Enriched[/bold]",
                    border_style="green"
                ))

                # Show sample of what was added
                if sample_history is not None:
                    console.print()
                    console.print("[bold]Sample enriched history columns:[/bold]")

                    # Calibration metadata columns (check first to exclude from metrics)
                    calibration_cols = [col for col in sample_history.columns
                                      if col.startswith('calibration_')]

                    # Power columns from calibration enrichment
                    power_cols = [col for col in sample_history.columns
                                if 'power' in col.lower() and col not in calibration_cols]

                    # Metric columns (cnp, delta_current, delta_voltage, etc.)
                    metric_keywords = ['cnp_', 'delta_current', 'delta_voltage', 'mobility', 'responsivity']
                    metric_cols = [col for col in sample_history.columns
                                 if any(keyword in col.lower() for keyword in metric_keywords)
                                 and col not in calibration_cols]

                    if power_cols:
                        power_count = sum(sample_history[col].drop_nulls().len() for col in power_cols)
                        console.print(f"  [cyan]Power columns:[/cyan] {', '.join(power_cols)} ({power_count} total values)")

                    if metric_cols:
                        metric_count = sum(sample_history[col].drop_nulls().len() for col in metric_cols)
                        console.print(f"  [cyan]Metric columns:[/cyan] {', '.join(sorted(metric_cols))} ({metric_count} total values)")

                    if calibration_cols:
                        console.print(f"  [dim]Calibration metadata:[/dim] {', '.join(calibration_cols)}")

                    if not power_cols and not metric_cols:
                        console.print("  [dim]No enrichment columns added[/dim]")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[yellow]Hint:[/yellow] Run [cyan]build-all-histories[/cyan] first")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        if config.verbose:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    console.print()
