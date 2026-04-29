"""Clean processed data stages while preserving raw inputs."""

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from src.cli.plugin_system import cli_command

console = Console()

# Stage roots cleared by this command. data/01_raw is intentionally excluded.
STAGE_DIRS = [
    Path("data/02_stage"),
    Path("data/03_derived"),
    Path("data/04_exports"),
]


def _dir_size_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PiB"


@cli_command(
    name="clean-data",
    group="utilities",
    description="Delete processed stages (02_stage, 03_derived, 04_exports) but keep 01_raw",
    aliases=["clean-stages"],
)
def clean_data_command(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip the confirmation prompt",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without deleting",
    ),
):
    """Wipe derived data stages. data/01_raw is never touched."""
    table = Table(title="Stages to clear", show_lines=False)
    table.add_column("Path")
    table.add_column("Exists")
    table.add_column("Size", justify="right")
    table.add_column("Files", justify="right")

    targets = []
    for stage in STAGE_DIRS:
        if stage.exists():
            n_files = sum(1 for f in stage.rglob("*") if f.is_file())
            size = _dir_size_bytes(stage)
            table.add_row(str(stage), "yes", _format_size(size), str(n_files))
            targets.append(stage)
        else:
            table.add_row(str(stage), "[dim]no[/dim]", "-", "-")

    console.print(table)
    console.print(Panel.fit(
        "[bold]data/01_raw is preserved.[/bold]",
        border_style="green",
    ))

    if not targets:
        console.print("[yellow]Nothing to delete.[/yellow]")
        return

    if dry_run:
        console.print("[cyan]Dry run — no files removed.[/cyan]")
        return

    if not yes:
        if not Confirm.ask(
            f"[bold red]Delete {len(targets)} stage director{'y' if len(targets) == 1 else 'ies'}?[/bold red]",
            default=False,
        ):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(1)

    for stage in targets:
        shutil.rmtree(stage)
        console.print(f"[green]✓[/green] Removed {stage}")

    console.print("[bold green]Done.[/bold green]")
