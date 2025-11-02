"""
Cache management commands for CLI.

Provides commands for viewing, clearing, and managing the data cache.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from src.cli.cache import get_cache, clear_cache
from src.cli.plugin_system import cli_command


console = Console()


@cli_command(
    name="cache-stats",
    group="utilities",
    description="Display cache statistics and performance metrics"
)
def cache_stats_command():
    """Display cache statistics and performance metrics"""
    cache = get_cache()
    stats = cache.get_stats()
    info = cache.get_info()

    # Create stats table
    table = Table(title="Cache Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Cache Hits", str(stats.hits))
    table.add_row("Cache Misses", str(stats.misses))
    table.add_row("Hit Rate", f"{stats.hit_rate():.1%}")
    table.add_row("Evictions", str(stats.evictions))
    table.add_row("Invalidations", str(stats.invalidations))
    table.add_row("", "")  # Separator
    table.add_row("Cached Items", str(info['item_count']))
    table.add_row("Cache Size", f"{info['total_size_mb']:.1f} MB")
    table.add_row("Max Size", f"{info['max_size_mb']:.1f} MB")
    table.add_row("Utilization", f"{info['utilization']:.1%}")

    console.print(table)

    # Performance tip
    if stats.hit_rate() < 0.5 and stats.hits + stats.misses > 10:
        console.print(
            "\n[yellow]💡 Tip:[/yellow] Low hit rate. Consider increasing "
            "cache_ttl in config for better performance."
        )


@cli_command(
    name="cache-clear",
    group="utilities",
    description="Clear all cached data"
)
def cache_clear_command(
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt"
    )
):
    """Clear all cached data"""
    if not yes:
        if not Confirm.ask("Clear all cached data?"):
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    cache = get_cache()
    stats_before = cache.get_stats()

    clear_cache()

    console.print(
        f"[green]✓[/green] Cache cleared "
        f"({stats_before.hits + stats_before.misses} operations cached)"
    )


@cli_command(
    name="cache-info",
    group="utilities",
    description="Show detailed cache information"
)
def cache_info_command():
    """Show detailed cache information"""
    cache = get_cache()
    info = cache.get_info()

    lines = [
        f"[cyan]Status:[/cyan] {'Enabled' if True else 'Disabled'}",
        f"[cyan]Items Cached:[/cyan] {info['item_count']}",
        f"[cyan]Memory Used:[/cyan] {info['total_size_mb']:.1f} MB / {info['max_size_mb']:.1f} MB",
        f"[cyan]Utilization:[/cyan] {info['utilization']:.1%}",
        "",
        info['stats']
    ]

    panel = Panel(
        "\n".join(lines),
        title="Cache Information",
        border_style="cyan"
    )
    console.print(panel)


@cli_command(
    name="cache-warmup",
    group="utilities",
    description="Pre-load chip histories into cache"
)
def cache_warmup_command(
    chips: str = typer.Argument(..., help="Chip numbers (comma-separated)"),
    chip_group: str = typer.Option("Alisson", "--chip-group", "-g", help="Chip group prefix"),
):
    """Pre-load chip histories into cache"""
    from src.cli.config import get_config
    from src.cli.cache import load_history_cached

    config = get_config()
    cache = get_cache()

    # Parse chip numbers
    chip_numbers = [int(c.strip()) for c in chips.split(",")]

    console.print(f"[cyan]Warming up cache for {len(chip_numbers)} chips...[/cyan]")

    success_count = 0
    for chip in chip_numbers:
        history_file = config.history_dir / f"{chip_group}{chip}_history.parquet"

        if not history_file.exists():
            console.print(f"  [yellow]⚠[/yellow] Chip {chip}: history not found")
            continue

        try:
            load_history_cached(history_file)
            console.print(f"  [green]✓[/green] Chip {chip}: loaded")
            success_count += 1
        except Exception as e:
            console.print(f"  [red]✗[/red] Chip {chip}: {e}")

    console.print(
        f"\n[green]✓[/green] Cache warmed up: "
        f"{success_count}/{len(chip_numbers)} chips loaded"
    )

    # Show stats
    cache_stats_command()
