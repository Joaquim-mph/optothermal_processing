"""Chip statistics command: show experiment counts per chip and procedure."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.cli.context import get_context
import polars as pl


@cli_command(
    name="chip-stats",
    group="utilities",
    description="Show experiment statistics per chip"
)
def chip_stats_command(
    chip_number: Optional[int] = typer.Argument(
        None,
        help="Chip number to show stats for (optional, shows all chips if not specified)"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    history_dir: Optional[Path] = typer.Option(
        None,
        "--history-dir",
        help="Chip history directory (default: from config)"
    ),
    sort_by: str = typer.Option(
        "chip",
        "--sort",
        "-s",
        help="Sort by: 'chip' (chip number), 'total' (total experiments), 'date' (last experiment date)"
    ),
):
    """
    Show experiment statistics per chip.

    Displays a summary table showing the number of experiments per procedure
    for each chip, along with totals and date ranges.

    Examples:
        # Show stats for all chips
        python process_and_analyze.py chip-stats

        # Show stats for specific chip
        python process_and_analyze.py chip-stats 67

        # Sort by total experiments
        python process_and_analyze.py chip-stats --sort total

        # Different chip group
        python process_and_analyze.py chip-stats --group OtherGroup
    """
    ctx = get_context()
    ctx.print()

    if chip_number is not None:
        ctx.print(Panel.fit(
            f"[bold cyan]Chip Statistics: {chip_group}{chip_number}[/bold cyan]",
            border_style="cyan"
        ))
    else:
        ctx.print(Panel.fit(
            f"[bold cyan]Chip Statistics: All {chip_group} Chips[/bold cyan]",
            border_style="cyan"
        ))
    ctx.print()

    # Determine history directory
    if history_dir is None:
        history_dir = Path(ctx.history_dir)

    if not history_dir.exists():
        ctx.print(f"[red]Error:[/red] History directory not found: {history_dir}")
        ctx.print("[yellow]Hint:[/yellow] Run [cyan]build-all-histories[/cyan] first")
        raise typer.Exit(1)

    # Find all chip history files
    if chip_number is not None:
        # Single chip
        history_file = history_dir / f"{chip_group}{chip_number}_history.parquet"
        if not history_file.exists():
            ctx.print(f"[red]Error:[/red] History file not found: {history_file}")
            ctx.print(f"[yellow]Hint:[/yellow] Run [cyan]build-all-histories[/cyan] to generate histories")
            raise typer.Exit(1)
        history_files = [history_file]
    else:
        # All chips in the group
        pattern = f"{chip_group}*_history.parquet"
        history_files = sorted(history_dir.glob(pattern))

        if not history_files:
            ctx.print(f"[red]Error:[/red] No history files found in {history_dir}")
            ctx.print(f"[yellow]Hint:[/yellow] Run [cyan]build-all-histories[/cyan] first")
            raise typer.Exit(1)

    # Collect statistics
    chip_stats = []

    for hist_file in history_files:
        try:
            # Extract chip number from filename (e.g., "Alisson67_history.parquet" -> 67)
            filename = hist_file.stem  # Remove .parquet
            chip_num_str = filename.replace(f"{chip_group}", "").replace("_history", "")
            chip_num = int(chip_num_str)

            # Load history
            df = pl.read_parquet(hist_file)

            if df.height == 0:
                continue

            # Get procedure counts
            proc_counts = df.group_by("proc").agg(pl.count().alias("count")).sort("proc")
            proc_dict = {row["proc"]: row["count"] for row in proc_counts.iter_rows(named=True)}

            # Get date range
            if "date_local" in df.columns:
                dates = df["date_local"].drop_nulls()
                if dates.len() > 0:
                    first_date = dates.min()
                    last_date = dates.max()
                else:
                    first_date = "N/A"
                    last_date = "N/A"
            else:
                first_date = "N/A"
                last_date = "N/A"

            chip_stats.append({
                "chip_number": chip_num,
                "total": df.height,
                "procedures": proc_dict,
                "first_date": first_date,
                "last_date": last_date,
            })

        except Exception as e:
            ctx.print(f"[yellow]Warning:[/yellow] Could not process {hist_file.name}: {e}")
            continue

    if not chip_stats:
        ctx.print("[yellow]No chip statistics found[/yellow]")
        raise typer.Exit(0)

    # Sort results
    if sort_by == "total":
        chip_stats.sort(key=lambda x: x["total"], reverse=True)
    elif sort_by == "date":
        chip_stats.sort(key=lambda x: x["last_date"], reverse=True)
    else:  # chip
        chip_stats.sort(key=lambda x: x["chip_number"])

    # Get all unique procedures across all chips
    all_procedures = set()
    for stat in chip_stats:
        all_procedures.update(stat["procedures"].keys())
    all_procedures = sorted(all_procedures)

    # Create summary table
    table = Table(title=f"[bold]Experiment Statistics[/bold]", show_header=True, header_style="bold cyan")

    # Add columns
    table.add_column("Chip", justify="right", style="cyan")
    table.add_column("Total", justify="right", style="bold green")

    for proc in all_procedures:
        table.add_column(proc, justify="right")

    table.add_column("First Exp", justify="left", style="dim")
    table.add_column("Last Exp", justify="left", style="dim")

    # Add rows
    total_overall = 0
    proc_totals = {proc: 0 for proc in all_procedures}

    for stat in chip_stats:
        row = [
            f"{chip_group}{stat['chip_number']}",
            str(stat['total'])
        ]

        # Add procedure counts
        for proc in all_procedures:
            count = stat['procedures'].get(proc, 0)
            if count > 0:
                row.append(str(count))
                proc_totals[proc] += count
            else:
                row.append("[dim]-[/dim]")

        # Add dates
        row.append(str(stat['first_date']))
        row.append(str(stat['last_date']))

        table.add_row(*row)
        total_overall += stat['total']

    # Add totals row if multiple chips
    if len(chip_stats) > 1:
        total_row = ["[bold]TOTAL[/bold]", f"[bold]{total_overall}[/bold]"]
        for proc in all_procedures:
            total_row.append(f"[bold]{proc_totals[proc]}[/bold]" if proc_totals[proc] > 0 else "[dim]-[/dim]")
        total_row.extend(["", ""])  # Empty date columns
        table.add_row(*total_row)

    ctx.print(table)
    ctx.print()

    # Additional summary
    if len(chip_stats) == 1:
        ctx.print(f"[green]✓[/green] {chip_group}{chip_stats[0]['chip_number']} has {chip_stats[0]['total']} total experiments")
    else:
        ctx.print(f"[green]✓[/green] {len(chip_stats)} chips with {total_overall} total experiments")
        ctx.print(f"[dim]  Average: {total_overall / len(chip_stats):.1f} experiments per chip[/dim]")

    ctx.print()
