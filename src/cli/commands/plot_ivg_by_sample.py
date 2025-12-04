"""CLI command for plotting IVg measurements grouped by sample letter."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.cli.plugin_system import cli_command
from src.plotting.config import PlotConfig


@cli_command(
    name="plot-ivg-by-sample",
    group="plotting",
    description="Plot last IVg for each sample (A-J) of a chip"
)
def plot_ivg_by_sample_command(
    chip_group: str = typer.Argument(..., help="Chip group name (e.g., 'Margarita')"),
    chip_number: int = typer.Argument(..., help="Chip number (e.g., 1)"),
    conductance: bool = typer.Option(False, "--conductance", "-g", help="Plot conductance G=I/V instead of current"),
    raw_root: Optional[Path] = typer.Option(None, "--raw-root", help="Raw data directory (for fallback if no manifest)"),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest", help="Path to manifest.parquet (if available)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory for plots"),
):
    """
    Plot the last IVg measurement for each sample (A-J) of a chip.

    This command finds all IVg measurements for a given chip+group combination,
    groups them by the "Sample" parameter (typically A-J), and plots the LAST
    measurement for each sample in a single figure for comparison.

    Examples:

        # Plot current vs Vg for all samples of Margarita 1
        plot-ivg-by-sample Margarita 1

        # Plot conductance instead
        plot-ivg-by-sample Margarita 1 --conductance

        # Specify raw data location (if manifest doesn't exist)
        plot-ivg-by-sample "Alisson" 67 --raw-root data/01_raw

        # Use custom manifest location
        plot-ivg-by-sample Laika 3 --manifest data/02_stage/_manifest/manifest.parquet

    The command tries to use the staged manifest first (fast), and falls back
    to scanning raw CSV files if the manifest is not available.
    """
    console = Console()

    from src.plotting.ivg_by_sample import plot_ivg_by_sample

    console.print(f"\n[bold cyan]Plotting IVg by Sample[/bold cyan]")
    console.print(f"  Chip: [green]{chip_group} {chip_number}[/green]")
    console.print(f"  Mode: [yellow]{'Conductance (G)' if conductance else 'Current (I)'}[/yellow]\n")

    # Set up paths
    if raw_root is None:
        raw_root = Path("data/01_raw")

    if manifest_path is None:
        manifest_path = Path("data/02_stage/_manifest/manifest.parquet")

    if output_dir is None:
        output_dir = Path("figs")

    # Create plot configuration
    config = PlotConfig()
    if output_dir:
        config.output_dir = output_dir

    # Generate plot
    try:
        output_path = plot_ivg_by_sample(
            chip_group=chip_group,
            chip_number=chip_number,
            raw_root=raw_root if raw_root.exists() else None,
            manifest_path=manifest_path if manifest_path.exists() else None,
            conductance=conductance,
            config=config,
        )

        if output_path:
            console.print(f"\n[bold green]✓ Plot saved:[/bold green] {output_path}")
        else:
            console.print(f"\n[bold red]✗ No data found for {chip_group} {chip_number}[/bold red]")
            console.print("[yellow]Hints:[/yellow]")
            console.print("  • Check that chip group name matches exactly (case-sensitive)")
            console.print("  • Verify chip number is correct")
            console.print("  • Ensure IVg measurements exist with Sample parameter")
            console.print("  • Try providing --raw-root if manifest doesn't exist")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(1)
