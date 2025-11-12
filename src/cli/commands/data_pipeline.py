"""Data processing pipeline commands: full-pipeline (modern staging-based pipeline)."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
import time

console = Console()

# Legacy commands have been removed (parse-all, chip-histories, quick-stats)
# Use the modern pipeline instead:
#   - parse-all → stage-all (CSV → Parquet with schema validation)
#   - chip-histories → build-all-histories (from manifest.parquet)
#   - quick-stats → inspect-manifest or staging-stats


@cli_command(
    name="full-pipeline",
    group="pipeline",
    description="Run complete data processing pipeline"
)
def full_pipeline_command(
    raw_root: Optional[Path] = typer.Option(
        None,
        "--raw-root",
        "-r",
        help="Root directory containing raw CSV files (default: from config)"
    ),
    stage_root: Optional[Path] = typer.Option(
        None,
        "--stage-root",
        "-s",
        help="Output directory for staged Parquet files (default: from config)"
    ),
    history_dir: Optional[Path] = typer.Option(
        None,
        "--history-dir",
        "-o",
        help="Output directory for chip history Parquet files (default: from config)"
    ),
    procedures_yaml: Path = typer.Option(
        Path("config/procedures.yml"),
        "--procedures-yaml",
        "-p",
        help="YAML schema file defining procedures"
    ),
    chip_group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Filter chip histories by group (e.g., 'Alisson')"
    ),
    min_experiments: int = typer.Option(
        1,
        "--min",
        help="Minimum experiments per chip for history generation"
    ),
    workers: int = typer.Option(
        8,
        "--workers",
        "-w",
        help="Number of parallel worker processes for staging"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force overwrite existing Parquet files"
    ),
    skip_metrics: bool = typer.Option(
        False,
        "--skip-metrics",
        help="Skip derived metrics extraction (Step 3)"
    ),
    skip_enrichment: bool = typer.Option(
        False,
        "--skip-enrichment",
        help="Skip history enrichment (Step 4)"
    ),
    include_calibrations: bool = typer.Option(
        True,
        "--calibrations/--no-calibrations",
        help="Include laser calibration power extraction in metrics step (default: True)"
    ),
):
    """
    Run the complete pipeline: stage → histories → derive metrics → enrich.

    This modern pipeline uses the staging system (CSV → Parquet + manifest),
    builds histories from the authoritative manifest.parquet, extracts
    derived analytical metrics including laser calibration power, and enriches
    chip histories with the derived metrics and calibration data.

    Steps:
      1. Stage all raw CSVs → Parquet with schema validation
      2. Generate chip histories from manifest
      3. Extract derived metrics (CNP, photoresponse, calibration power)
      4. Enrich chip histories with metrics and calibrations

    Examples:
        # Complete pipeline with all steps (stage → histories → metrics → enrich)
        process_and_analyze full-pipeline

        # Custom paths with 16 workers
        process_and_analyze full-pipeline -r data/01_raw -s data/02_stage/raw_measurements -w 16

        # Force re-processing everything
        process_and_analyze full-pipeline --force

        # Skip metrics extraction and enrichment (only stage + histories)
        process_and_analyze full-pipeline --skip-metrics

        # Skip only enrichment (stage + histories + metrics)
        process_and_analyze full-pipeline --skip-enrichment

        # Filter by chip group
        process_and_analyze full-pipeline -g Alisson --min 10
    """
    from src.cli.commands.stage import stage_all_command
    from src.cli.commands.history import build_all_histories_command
    from src.cli.commands.derived_metrics import derive_all_metrics_command
    from src.cli.commands.enrich_unified import enrich_history_unified_command

    # Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    if raw_root is None:
        raw_root = config.raw_data_dir
        if config.verbose:
            console.print(f"[dim]Using raw data directory from config: {raw_root}[/dim]")

    if stage_root is None:
        stage_root = config.stage_dir / "raw_measurements"
        if config.verbose:
            console.print(f"[dim]Using stage directory from config: {stage_root}[/dim]")

    if history_dir is None:
        history_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    console.print()
    steps_text = (
        "[bold blue]Complete Data Processing Pipeline[/bold blue]\n"
        "Step 1: Stage raw CSVs → Parquet + Manifest (schema-validated)\n"
        "Step 2: Generate chip histories from manifest"
    )
    if not skip_metrics:
        steps_text += "\nStep 3: Extract derived metrics (CNP, photoresponse, calibration power)"
        if not skip_enrichment:
            steps_text += "\nStep 4: Enrich chip histories with metrics and calibrations"

    console.print(Panel.fit(
        steps_text,
        title="Full Pipeline",
        border_style="blue"
    ))
    console.print()

    start_time = time.time()

    # Step 1: Stage all raw data
    console.print("[bold cyan]═══ STEP 1: STAGING ═══[/bold cyan]\n")
    try:
        stage_all_command(
            raw_root=raw_root,
            stage_root=stage_root,
            procedures_yaml=procedures_yaml,
            rejects_dir=None,  # Auto-detect
            events_dir=None,   # Auto-detect
            manifest=None,     # Auto-detect
            local_tz="America/Santiago",
            workers=workers,
            polars_threads=2,
            force=force,
            only_yaml_data=False,
            strict=False,
            verbose=False,
        )
    except SystemExit as e:
        if e.code != 0:
            console.print("[red]✗ Staging failed, aborting pipeline[/red]\n")
            raise typer.Exit(1)

    console.print("\n" + "="*80 + "\n")

    # Step 2: Build all chip histories
    console.print("[bold magenta]═══ STEP 2: CHIP HISTORIES ═══[/bold magenta]\n")

    # Determine manifest path (same auto-detection logic as stage_all)
    manifest_path = stage_root / "_manifest" / "manifest.parquet"

    try:
        build_all_histories_command(
            manifest_path=manifest_path,
            output_dir=history_dir,
            chip_group=chip_group,
            min_experiments=min_experiments,
        )
    except SystemExit as e:
        if e.code != 0:
            console.print("[red]✗ History generation failed[/red]\n")
            raise typer.Exit(1)

    # Step 3: Derive all metrics (CNP, photoresponse, calibration power)
    if not skip_metrics:
        console.print("\n" + "="*80 + "\n")
        console.print("[bold green]═══ STEP 3: DERIVED METRICS ═══[/bold green]\n")

        try:
            derive_all_metrics_command(
                procedures=None,  # Process all applicable procedures
                chip_group=chip_group,
                chip_number=None,
                workers=workers,
                force=force,
                include_calibrations=include_calibrations,
                stale_threshold=24.0,
                dry_run=False,
            )
        except SystemExit as e:
            if e.code != 0:
                console.print("[red]✗ Metrics extraction failed[/red]\n")
                raise typer.Exit(1)

        # Step 4: Enrich chip histories with metrics and calibrations
        if not skip_enrichment:
            console.print("\n" + "="*80 + "\n")
            console.print("[bold yellow]═══ STEP 4: HISTORY ENRICHMENT ═══[/bold yellow]\n")

            try:
                enrich_history_unified_command(
                    chip_number=None,  # Will use --all-chips
                    all_chips=True,  # Process all chips
                    chip_group=chip_group,
                    calibrations_only=False,  # Add both calibrations and metrics
                    metrics_only=False,
                    metrics="all",  # Add all available metrics
                    force=force,
                    skip_derive=True,  # We just ran derive-all-metrics in Step 3
                    derive_first=False,
                    workers=workers,
                    dry_run=False,
                    output_dir=None,  # Use default
                    stale_threshold=24.0,
                    verbose=False,
                )
            except SystemExit as e:
                if e.code != 0:
                    console.print("[red]✗ History enrichment failed[/red]\n")
                    raise typer.Exit(1)

    elapsed = time.time() - start_time

    # Build output summary
    outputs_text = (
        f"[cyan]Outputs:[/cyan]\n"
        f"  • Staged data: {stage_root}\n"
        f"  • Manifest: {manifest_path}\n"
        f"  • Histories (Stage 2): {history_dir}"
    )

    if not skip_metrics:
        derived_dir = config.stage_dir.parent / "03_derived"
        outputs_text += (
            f"\n  • Metrics: {derived_dir / '_metrics' / 'metrics.parquet'}"
        )

        if not skip_enrichment:
            outputs_text += (
                f"\n  • [bold]Enriched histories (Stage 3): {derived_dir / 'chip_histories_enriched'}[/bold]"
            )
        else:
            outputs_text += (
                f"\n  • Enriched histories: [dim](skipped)[/dim]"
            )

    next_steps_text = (
        "[dim]Next steps:[/dim]\n"
        "  • [cyan]show-history <chip_number>[/cyan] - View chip timeline\n"
        "  • [cyan]plot-its[/cyan], [cyan]plot-ivg[/cyan] - Generate plots"
    )

    if skip_metrics:
        next_steps_text += "\n  • [cyan]derive-all-metrics[/cyan] - Extract derived metrics"
    elif skip_enrichment:
        next_steps_text += "\n  • [cyan]enrich-history -a[/cyan] - Enrich chip histories with metrics"
    else:
        next_steps_text += "\n  • [cyan]plot-cnp-time[/cyan], [cyan]plot-photoresponse[/cyan] - Plot derived metrics"

    console.print("\n" + "="*80 + "\n")
    console.print(Panel.fit(
        f"[bold green]✓ Pipeline Complete![/bold green]\n\n"
        f"Total time: {elapsed:.1f}s\n\n"
        f"{outputs_text}\n\n"
        f"{next_steps_text}",
        border_style="green"
    ))
