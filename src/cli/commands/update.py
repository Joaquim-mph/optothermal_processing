"""Incremental refresh command: stage → histories → calibration enrichment only."""

from pathlib import Path
from typing import Optional

import typer

from src.cli.plugin_system import cli_command


@cli_command(
    name="update",
    group="pipeline",
    description="Stage new CSVs, rebuild histories, and attach calibration power. Skips heavy metric extractors.",
)
def update_command(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Re-stage all CSVs and re-enrich every chip even if nothing is new.",
    ),
    chip_group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Restrict history build + enrichment to a single chip group (e.g. 'Alisson').",
    ),
    chip_number: Optional[int] = typer.Option(
        None,
        "--chip",
        "-c",
        help="Restrict enrichment to a single chip number.",
    ),
):
    """
    Minimal incremental refresh for the It-with-power workflow.

    Pipeline:
      1. stage-all (skips CSVs already staged unless --force)
      2. build-all-histories (only if new measurements were staged, or --force)
      3. CalibrationMatcher.enrich_chip_history per chip (adds irradiated_power_w)

    The CNP / Photoresponse / CorrectedDeltaI extractors and the metric-column
    join performed by `enrich-all-histories` are deliberately skipped — this
    command exists to surface new raw data with optical power attached, fast.

    Use `enrich-all-histories` when you actually need the derived metric columns.
    """
    import polars as pl
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from src.cli.main import get_config
    from src.core import run_staging_pipeline
    from src.core.history_builder import generate_all_chip_histories
    from src.derived.extractors import CalibrationMatcher
    from src.models.parameters import StagingParameters

    console = Console()
    config = get_config()

    raw_root = config.raw_data_dir
    stage_root = config.stage_dir / "raw_measurements"
    manifest_path = stage_root / "_manifest" / "manifest.parquet"
    history_dir = config.history_dir
    enriched_dir = config.stage_dir.parent / "03_derived" / "chip_histories_enriched"
    procedures_yaml = Path("config/procedures.yml")

    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]biotite update[/bold cyan]\n"
            "stage → histories → calibration power (no metric extraction)",
            border_style="cyan",
        )
    )
    console.print()

    if not raw_root.exists():
        console.print(f"[bold red]Error:[/bold red] Raw root does not exist: {raw_root}")
        raise typer.Exit(1)
    if not procedures_yaml.exists():
        console.print(f"[bold red]Error:[/bold red] Procedures YAML not found: {procedures_yaml}")
        raise typer.Exit(1)

    # --- Step 1: stage (snapshot manifest row count to detect new files) ---
    before_count = 0
    if manifest_path.exists():
        try:
            before_count = pl.read_parquet(manifest_path, columns=["run_id"]).height
        except Exception:
            before_count = 0

    console.print("[cyan]Staging raw CSVs...[/cyan]")
    params = StagingParameters(
        raw_root=raw_root,
        stage_root=stage_root,
        procedures_yaml=procedures_yaml,
        force=force,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TextColumn("•"),
        TextColumn("[cyan]{task.fields[status]}"),
        console=console,
        transient=False,
        refresh_per_second=10,
    ) as progress:
        task = progress.add_task("Staging files", total=None, status="discovering...")

        def _on_progress(current, total, proc, status_str):
            progress.update(task, status=f"{current}/{total} • {proc} ({status_str})")

        run_staging_pipeline(params, progress_callback=_on_progress)
        progress.update(task, status="✓ done")

    after_count = 0
    if manifest_path.exists():
        after_count = pl.read_parquet(manifest_path, columns=["run_id"]).height

    new_count = max(0, after_count - before_count)

    if new_count == 0 and not force:
        console.print()
        console.print(
            Panel.fit(
                "[bold green]✓ Already up to date[/bold green]\n"
                f"No new measurements found in {raw_root}.\n\n"
                "[dim]Pass --force to rebuild histories and re-enrich anyway.[/dim]",
                border_style="green",
            )
        )
        console.print()
        return

    if new_count > 0:
        console.print(f"[green]✓[/green] {new_count} new measurement(s) staged.")
    else:
        console.print("[yellow]--force set:[/yellow] rebuilding even though no new measurements were staged.")
    console.print()

    # --- Step 2: rebuild histories ---
    console.print("[cyan]Rebuilding chip histories...[/cyan]")
    histories = generate_all_chip_histories(
        manifest_path=manifest_path,
        output_dir=history_dir,
        stage_root=stage_root,
        chip_group=chip_group,
    )
    console.print(f"[green]✓[/green] Built {len(histories)} chip histor{'y' if len(histories) == 1 else 'ies'}.")
    console.print()

    # --- Step 3: calibration enrichment only (adds irradiated_power_w) ---
    console.print("[cyan]Attaching calibration power...[/cyan]")

    enriched_dir.mkdir(parents=True, exist_ok=True)
    matcher = CalibrationMatcher(manifest_path)

    history_files = sorted(history_dir.glob("*_history.parquet"))
    if chip_group:
        history_files = [f for f in history_files if f.stem.startswith(chip_group)]
    if chip_number is not None:
        chip_name = f"{chip_group if chip_group else 'Alisson'}{chip_number}"
        history_files = [f for f in history_files if f.stem == f"{chip_name}_history"]

    if not history_files:
        console.print("[yellow]⚠[/yellow] No matching history files found to enrich.")
        return

    enriched_count = 0
    warned_count = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Enriching with power", total=len(history_files))
        for history_path in history_files:
            progress.update(task, description=f"[cyan]{history_path.stem}")
            try:
                matcher.enrich_chip_history(history_path, output_dir=enriched_dir, force=True)
                enriched_count += 1
            except Exception as e:
                warned_count += 1
                console.print(f"[yellow]⚠[/yellow] {history_path.stem}: {e}")
            progress.advance(task)

    console.print()
    console.print(
        Panel.fit(
            f"[bold green]✓ Update complete[/bold green]\n\n"
            f"New measurements staged: {new_count}\n"
            f"Histories rebuilt:       {len(histories)}\n"
            f"Histories enriched:      {enriched_count}"
            + (f"\nWarnings:                {warned_count}" if warned_count else ""),
            border_style="green",
        )
    )
    console.print()
