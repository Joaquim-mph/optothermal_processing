"""
Refactored data pipeline commands using the formal Pipeline builder.

This demonstrates how to use the Pipeline class for better error handling,
rollback, and state management.
"""

import typer
import shutil
from pathlib import Path
from typing import Optional
from rich.console import Console

from src.cli.plugin_system import cli_command
from src.core.pipeline import Pipeline

console = Console()


def create_full_pipeline(
    raw_root: Path,
    stage_root: Path,
    history_dir: Path,
    procedures_yaml: Path,
    chip_group: Optional[str],
    min_experiments: int,
    workers: int,
    force: bool,
    skip_metrics: bool,
    include_calibrations: bool,
) -> Pipeline:
    """
    Factory function to create the full-pipeline definition.

    This separates pipeline definition from execution, enabling:
    - Testing pipeline structure without execution
    - Saving pipeline definitions to YAML
    - Reusing pipeline definitions across commands
    """
    from src.models.parameters import StagingParameters
    from src.core.stage_raw_measurements import run_staging_pipeline
    from src.core.history_builder import generate_all_chip_histories
    from src.derived.metric_pipeline import MetricPipeline

    pipeline = Pipeline(
        name="full-pipeline",
        description="Complete data processing: staging → histories → metrics",
        verbose=False,
    )

    # Auto-detect paths
    manifest_path = stage_root / "_manifest" / "manifest.parquet"
    rejects_dir = stage_root.parent / "_rejects"
    events_dir = stage_root / "_manifest" / "events"

    # Step 1: Stage raw CSVs to Parquet (wrapper function)
    def stage_wrapper():
        # Print step header (matching v1 style)
        from rich.console import Console
        _console = Console()
        _console.print("\n[bold cyan]═══ STEP 1: STAGING ═══[/bold cyan]\n")

        params = StagingParameters(
            raw_root=raw_root,
            stage_root=stage_root,
            procedures_yaml=procedures_yaml,
            rejects_dir=rejects_dir,
            events_dir=events_dir,
            manifest=manifest_path,
            local_tz="America/Santiago",
            workers=workers,
            polars_threads=2,
            force=force,
            only_yaml_data=False,
            strict=False,
        )

        # Use a simple progress callback that suppresses verbose output
        # without creating a nested Progress context
        def progress_callback(current, total, proc, status):
            """Suppress verbose file-by-file output (no-op callback)."""
            pass

        result = run_staging_pipeline(params, progress_callback=progress_callback)

        # Print separator (matching v1 style)
        _console.print("\n" + "="*80 + "\n")
        return result

    pipeline.add_step(
        name="stage-raw-data",
        command=stage_wrapper,
        rollback_fn=lambda: rollback_staging(stage_root) if force else None,
        retry_count=0,
        checkpoint=True,
    )

    # Step 2: Build chip histories (wrapper function)
    def history_wrapper():
        # Print step header (matching v1 style)
        from rich.console import Console
        _console = Console()
        _console.print("\n[bold magenta]═══ STEP 2: CHIP HISTORIES ═══[/bold magenta]\n")

        result = generate_all_chip_histories(
            manifest_path=manifest_path,
            output_dir=history_dir,
            stage_root=stage_root,
            chip_group=chip_group,
            min_experiments=min_experiments,
        )

        # Print separator if not last step
        if not skip_metrics:
            _console.print("\n" + "="*80 + "\n")
        return result

    pipeline.add_step(
        name="build-histories",
        command=history_wrapper,
        rollback_fn=lambda: rollback_histories(history_dir),
        checkpoint=True,
    )

    # Step 3: Extract derived metrics (optional, wrapper function)
    if not skip_metrics:
        def metrics_wrapper():
            import polars as pl
            from rich.console import Console

            # Print step header (matching v1 style)
            _console = Console()
            _console.print("\n[bold green]═══ STEP 3: DERIVED METRICS ═══[/bold green]\n")

            # Initialize metric pipeline
            metric_pipeline = MetricPipeline(
                base_dir=Path("."),
                extraction_version=None  # Auto-detect from git
            )

            # Get chip numbers from chip_group filter if specified
            chip_numbers_list = None
            if chip_group:
                manifest = pl.read_parquet(manifest_path)
                chip_numbers_list = (manifest
                                    .filter(pl.col("chip_group") == chip_group)
                                    .select("chip_number")
                                    .unique()
                                    .to_series()
                                    .to_list())

            # Run extraction (returns path to metrics file)
            metrics_path = metric_pipeline.derive_all_metrics(
                procedures=None,  # Process all applicable procedures
                chip_numbers=chip_numbers_list,
                parallel=(workers > 1),
                workers=workers,
                skip_existing=(not force)
            )

            return metrics_path

        pipeline.add_step(
            name="derive-metrics",
            command=metrics_wrapper,
            skip_on_error=False,
            retry_count=1,
            retry_delay=2.0,
            checkpoint=True,
        )

    return pipeline


def rollback_staging(stage_root: Path):
    """Rollback staging step by removing staged data."""
    if stage_root.exists():
        console.print(f"[yellow]Removing staged data: {stage_root}[/yellow]")
        shutil.rmtree(stage_root)


def rollback_histories(history_dir: Path):
    """Rollback history generation by removing history files."""
    if history_dir.exists():
        console.print(f"[yellow]Removing chip histories: {history_dir}[/yellow]")
        shutil.rmtree(history_dir)


@cli_command(
    name="full-pipeline-v2",
    group="pipeline",
    description="[BETA] Run complete pipeline with advanced error handling"
)
def full_pipeline_v2_command(
    raw_root: Optional[Path] = typer.Option(
        None, "--raw-root", "-r", help="Root directory containing raw CSV files"
    ),
    stage_root: Optional[Path] = typer.Option(
        None, "--stage-root", "-s", help="Output directory for staged Parquet files"
    ),
    history_dir: Optional[Path] = typer.Option(
        None, "--history-dir", "-o", help="Output directory for chip history files"
    ),
    procedures_yaml: Path = typer.Option(
        Path("config/procedures.yml"), "--procedures-yaml", "-p"
    ),
    chip_group: Optional[str] = typer.Option(
        None, "--group", "-g", help="Filter by chip group"
    ),
    min_experiments: int = typer.Option(1, "--min", help="Min experiments per chip"),
    workers: int = typer.Option(8, "--workers", "-w", help="Parallel workers"),
    force: bool = typer.Option(False, "--force", "-f", help="Force overwrite"),
    skip_metrics: bool = typer.Option(False, "--skip-metrics", help="Skip metrics extraction"),
    include_calibrations: bool = typer.Option(True, "--calibrations/--no-calibrations"),
    enable_rollback: bool = typer.Option(
        False, "--rollback/--no-rollback", help="Enable automatic rollback on failure"
    ),
    resume: bool = typer.Option(
        False, "--resume", help="Resume from last checkpoint"
    ),
    save_definition: Optional[Path] = typer.Option(
        None, "--save-yaml", help="Save pipeline definition to YAML file"
    ),
):
    """
    Run the complete pipeline with formal Pipeline builder.

    This version provides:
    - Automatic checkpointing (resume with --resume)
    - Retry logic with exponential backoff
    - Optional rollback on failure (--rollback)
    - Pipeline definition export (--save-yaml)

    Examples:
        # Run with rollback enabled
        process_and_analyze full-pipeline-v2 --rollback

        # Resume from checkpoint after failure
        process_and_analyze full-pipeline-v2 --resume

        # Save pipeline definition for reuse
        process_and_analyze full-pipeline-v2 --save-yaml pipelines/full.yml
    """
    from src.cli.main import get_config
    from rich.panel import Panel
    import time

    config = get_config()

    # Use config defaults if not specified
    raw_root = raw_root or config.raw_data_dir
    stage_root = stage_root or config.stage_dir / "raw_measurements"
    history_dir = history_dir or config.history_dir

    # Display initial panel (matching v1 style)
    console.print()
    steps_text = (
        "[bold blue]Complete Data Processing Pipeline[/bold blue]\n"
        "Step 1: Stage raw CSVs → Parquet + Manifest (schema-validated)\n"
        "Step 2: Generate chip histories from manifest"
    )
    if not skip_metrics:
        steps_text += "\nStep 3: Extract derived metrics (CNP, photoresponse, calibration power)"

    console.print(Panel.fit(
        steps_text,
        title="Full Pipeline",
        border_style="blue"
    ))
    console.print()

    start_time = time.time()

    # Create pipeline (without header - we just displayed it)
    pipeline = create_full_pipeline(
        raw_root=raw_root,
        stage_root=stage_root,
        history_dir=history_dir,
        procedures_yaml=procedures_yaml,
        chip_group=chip_group,
        min_experiments=min_experiments,
        workers=workers,
        force=force,
        skip_metrics=skip_metrics,
        include_calibrations=include_calibrations,
    )

    # Customize step display names to match v1
    pipeline.steps[0].name = "STEP 1: STAGING"
    pipeline.steps[1].name = "STEP 2: CHIP HISTORIES"
    if len(pipeline.steps) > 2:
        pipeline.steps[2].name = "STEP 3: DERIVED METRICS"

    # Save definition if requested
    if save_definition:
        pipeline.to_yaml(save_definition)
        if not typer.confirm("Continue with execution?"):
            return

    # Execute pipeline (with custom display disabled since we showed header)
    # Suppress the default pipeline header and summary
    pipeline._display_header = lambda: None
    pipeline._display_summary = lambda result: None  # Suppress default summary

    result = pipeline.execute(
        stop_on_error=True,
        enable_rollback=enable_rollback,
        resume_from="latest" if resume else None,
    )

    elapsed = time.time() - start_time

    # Display summary (matching v1 style)
    manifest_path = stage_root / "_manifest" / "manifest.parquet"

    outputs_text = (
        f"[cyan]Outputs:[/cyan]\n"
        f"  • Staged data: {stage_root}\n"
        f"  • Manifest: {manifest_path}\n"
        f"  • Histories (Stage 2): {history_dir}"
    )

    if not skip_metrics:
        derived_dir = config.stage_dir.parent / "03_derived"
        outputs_text += (
            f"\n  • Metrics: {derived_dir / '_metrics' / 'metrics.parquet'}\n"
            f"  • Enriched histories (Stage 3): {derived_dir / 'chip_histories_enriched'}"
        )

    next_steps_text = (
        "[dim]Next steps:[/dim]\n"
        "  • [cyan]show-history <chip_number>[/cyan] - View chip timeline\n"
        "  • [cyan]plot-its[/cyan], [cyan]plot-ivg[/cyan] - Generate plots"
    )

    if skip_metrics:
        next_steps_text += "\n  • [cyan]derive-all-metrics[/cyan] - Extract derived metrics"
    else:
        next_steps_text += "\n  • [cyan]validate-manifest[/cyan] - Check data quality"

    # Don't print separator here - it's already printed by the last step
    console.print()

    if result.success:
        console.print(Panel.fit(
            f"[bold green]✓ Pipeline Complete![/bold green]\n\n"
            f"Total time: {elapsed:.1f}s\n\n"
            f"{outputs_text}\n\n"
            f"{next_steps_text}",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]✗ Pipeline Failed[/bold red]\n\n"
            f"Total time: {elapsed:.1f}s\n"
            f"Failed steps: {result.failed_steps}/{result.total_steps}",
            border_style="red"
        ))

    # Exit with appropriate code
    if not result.success:
        raise typer.Exit(1)


@cli_command(
    name="run-pipeline-yaml",
    group="pipeline",
    description="Execute pipeline from YAML definition"
)
def run_pipeline_yaml_command(
    yaml_file: Path = typer.Argument(..., help="YAML pipeline definition file"),
    enable_rollback: bool = typer.Option(False, "--rollback/--no-rollback"),
    resume: bool = typer.Option(False, "--resume"),
):
    """
    Load and execute a pipeline from YAML definition.

    This enables:
    - Reusable pipeline definitions
    - Custom pipelines without code changes
    - Team-shared pipeline configurations

    Example YAML:
        ```yaml
        name: quick-staging
        description: Fast staging without metrics
        steps:
          - name: stage-raw-data
            command: stage_all_command
            kwargs:
              raw_root: data/01_raw
              stage_root: data/02_stage/raw_measurements
              workers: 16
            retry_count: 1
        ```

    Usage:
        # Create custom pipeline
        cat > pipelines/quick-staging.yml << EOF
        name: quick-staging
        description: Fast staging for testing
        steps:
          - name: stage
            command: stage_all_command
            kwargs:
              workers: 16
              force: true
        EOF

        # Execute it
        process_and_analyze run-pipeline-yaml pipelines/quick-staging.yml
    """
    from src.cli.commands.stage import stage_all_command
    from src.cli.commands.history import build_all_histories_command
    from src.cli.commands.derived_metrics import derive_all_metrics_command

    # Command registry for YAML loading
    command_registry = {
        "stage_all_command": stage_all_command,
        "build_all_histories_command": build_all_histories_command,
        "derive_all_metrics_command": derive_all_metrics_command,
    }

    # Load and execute
    pipeline = Pipeline.from_yaml(yaml_file, command_registry)
    result = pipeline.execute(
        stop_on_error=True,
        enable_rollback=enable_rollback,
        resume_from="latest" if resume else None,
    )

    if not result.success:
        raise typer.Exit(1)


@cli_command(
    name="quick-staging",
    group="pipeline",
    description="Fast staging-only pipeline (no metrics)"
)
def quick_staging_command(
    raw_root: Optional[Path] = typer.Option(None, "--raw-root", "-r"),
    workers: int = typer.Option(16, "--workers", "-w"),
    force: bool = typer.Option(False, "--force", "-f"),
):
    """
    Quick staging pipeline without history or metrics generation.

    Useful for:
    - Testing raw data validity
    - Fast iteration during development
    - Staging new data without full processing

    Example:
        process_and_analyze quick-staging --workers 16 --force
    """
    from src.models.parameters import StagingParameters
    from src.core.stage_raw_measurements import run_staging_pipeline
    from src.cli.main import get_config

    config = get_config()
    raw_root = raw_root or config.raw_data_dir
    stage_root = config.stage_dir / "raw_measurements"

    pipeline = Pipeline(
        name="quick-staging",
        description="Fast staging without downstream processing",
    )

    # Use the underlying staging function with StagingParameters
    from src.models.parameters import StagingParameters
    from src.core.stage_raw_measurements import run_staging_pipeline

    def stage_wrapper():
        # Auto-detect paths
        manifest_path = stage_root / "_manifest" / "manifest.parquet"
        rejects_dir = stage_root.parent / "_rejects"
        events_dir = stage_root / "_manifest" / "events"

        params = StagingParameters(
            raw_root=raw_root,
            stage_root=stage_root,
            procedures_yaml=Path("config/procedures.yml"),
            rejects_dir=rejects_dir,
            events_dir=events_dir,
            manifest=manifest_path,
            local_tz="America/Santiago",
            workers=workers,
            polars_threads=2,
            force=force,
            only_yaml_data=False,
            strict=False,
        )

        # Use a simple progress callback that suppresses verbose output
        # without creating a nested Progress context
        def progress_callback(current, total, proc, status):
            """Suppress verbose file-by-file output (no-op callback)."""
            pass

        return run_staging_pipeline(params, progress_callback=progress_callback)

    pipeline.add_step(
        name="stage-raw-data",
        command=stage_wrapper,
        retry_count=1,
    )

    result = pipeline.execute(stop_on_error=True)

    if not result.success:
        raise typer.Exit(1)


@cli_command(
    name="metrics-only",
    group="pipeline",
    description="Extract metrics from already-staged data"
)
def metrics_only_command(
    chip_group: Optional[str] = typer.Option(None, "--group", "-g"),
    workers: int = typer.Option(8, "--workers", "-w"),
    force: bool = typer.Option(False, "--force", "-f"),
):
    """
    Run only the metrics extraction step.

    Assumes data is already staged and histories are built.
    Useful when adding new metric extractors.

    Example:
        process_and_analyze metrics-only --force --workers 12
    """
    from src.cli.main import get_config
    from src.derived.metric_pipeline import MetricPipeline
    import polars as pl

    config = get_config()
    stage_root = config.stage_dir / "raw_measurements"
    manifest_path = stage_root / "_manifest" / "manifest.parquet"

    pipeline = Pipeline(
        name="metrics-only",
        description="Extract derived metrics from staged data",
    )

    def metrics_wrapper():
        # Initialize metric pipeline
        metric_pipeline = MetricPipeline(
            base_dir=Path("."),
            extraction_version=None  # Auto-detect from git
        )

        # Get chip numbers from chip_group filter if specified
        chip_numbers_list = None
        if chip_group:
            manifest = pl.read_parquet(manifest_path)
            chip_numbers_list = (manifest
                                .filter(pl.col("chip_group") == chip_group)
                                .select("chip_number")
                                .unique()
                                .to_series()
                                .to_list())

        # Run extraction (returns path to metrics file)
        metrics_path = metric_pipeline.derive_all_metrics(
            procedures=None,  # Process all applicable procedures
            chip_numbers=chip_numbers_list,
            parallel=(workers > 1),
            workers=workers,
            skip_existing=(not force)
        )

        return metrics_path

    pipeline.add_step(
        name="derive-metrics",
        command=metrics_wrapper,
        retry_count=2,
        retry_delay=2.0,
    )

    result = pipeline.execute(stop_on_error=True)

    if not result.success:
        raise typer.Exit(1)
