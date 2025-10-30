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
):
    """
    Run the complete pipeline: stage raw data AND generate chip histories.

    This modern pipeline uses the staging system (CSV → Parquet + manifest)
    and builds histories from the authoritative manifest.parquet file.

    Steps:
      1. Stage all raw CSVs → Parquet with schema validation
      2. Generate chip histories from manifest

    Examples:
        # Basic pipeline with defaults
        process_and_analyze full-pipeline

        # Custom paths with 16 workers
        process_and_analyze full-pipeline -r data/01_raw -s data/02_stage/raw_measurements -w 16

        # Force re-staging and filter histories
        process_and_analyze full-pipeline --force -g Alisson --min 10
    """
    from src.cli.commands.stage import stage_all_command
    from src.cli.commands.history import build_all_histories_command

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
    console.print(Panel.fit(
        "[bold blue]Complete Data Processing Pipeline[/bold blue]\n"
        "Step 1: Stage raw CSVs → Parquet + Manifest (schema-validated)\n"
        "Step 2: Generate chip histories from manifest",
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

    elapsed = time.time() - start_time

    console.print("\n" + "="*80 + "\n")
    console.print(Panel.fit(
        f"[bold green]✓ Pipeline Complete![/bold green]\n\n"
        f"Total time: {elapsed:.1f}s\n\n"
        f"[cyan]Outputs:[/cyan]\n"
        f"  • Staged data: {stage_root}\n"
        f"  • Manifest: {manifest_path}\n"
        f"  • Histories: {history_dir}\n\n"
        f"[dim]Next steps:[/dim]\n"
        f"  • [cyan]show-history <chip_number>[/cyan] - View chip timeline\n"
        f"  • [cyan]plot-its[/cyan], [cyan]plot-ivg[/cyan] - Generate plots\n"
        f"  • [cyan]validate-manifest[/cyan] - Check data quality",
        border_style="green"
    ))
