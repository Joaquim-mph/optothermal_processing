"""CLI command for plotting consecutive sweep differences."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.plugin_system import cli_command
from src.plotting.consecutive_sweep_diff import plot_consecutive_sweep_differences

console = Console()


@cli_command(
    name="plot-consecutive-sweep-diff",
    group="plotting",
    description="Plot differences between consecutive IVg/VVg sweeps"
)
def plot_consecutive_sweep_diff_command(
    chip_number: int = typer.Argument(..., help="Chip number"),
    group: str = typer.Option("Alisson", "--group", "-g", help="Chip group prefix"),
    procedure: Optional[str] = typer.Option(
        None,
        "--proc", "-p",
        help="Filter to specific procedure (IVg or VVg)"
    ),
    no_resistance: bool = typer.Option(
        False,
        "--no-resistance",
        help="Skip resistance difference plots"
    ),
    individual_only: bool = typer.Option(
        False,
        "--individual-only",
        help="Only plot individual pairs, skip summary"
    ),
    summary_only: bool = typer.Option(
        False,
        "--summary-only",
        help="Only plot summary, skip individual pairs"
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag", "-t",
        help="Optional tag for output filenames"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir", "-o",
        help="Output directory (default: figs/)"
    ),
):
    """
    Plot consecutive IVg/VVg sweep differences for a chip.

    This command generates plots showing how gate voltage sweeps change between
    consecutive measurements, useful for tracking device evolution after treatments
    like illumination.

    \b
    Generates:
    ----------
    - Individual plots: ΔI(Vg) or ΔV(Vg) for each consecutive pair
    - Summary plot: All differences overlaid for comparison
    - Resistance plots: ΔR(Vg) showing resistance evolution (optional)

    \b
    Examples:
    ---------
    # Plot all IVg differences for chip 67
    $ python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --proc IVg

    # Plot both IVg and VVg differences
    $ python3 process_and_analyze.py plot-consecutive-sweep-diff 67

    # Only summary plot, no individual pairs
    $ python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --summary-only

    # Plot without resistance differences
    $ python3 process_and_analyze.py plot-consecutive-sweep-diff 67 --no-resistance

    \b
    Prerequisites:
    --------------
    1. Run: python3 process_and_analyze.py derive-all-metrics --chip 67
       (This extracts the consecutive sweep differences)
    2. Ensure consecutive IVg or VVg measurements exist (no gaps in seq_num)

    \b
    Output:
    -------
    Individual plots: figs/{ChipGroup}{ChipNumber}/{Procedure}/ConsecutiveSweepDiff/
    Summary plot: Same directory with "_summary" tag
    """

    chip_name = f"{group}{chip_number}"

    console.print()
    console.print(Panel(
        f"[bold cyan]Plotting Consecutive Sweep Differences[/bold cyan]\n"
        f"Chip: {chip_name}\n"
        f"Procedure: {procedure or 'All (IVg, VVg)'}\n"
        f"Resistance plots: {'No' if no_resistance else 'Yes'}",
        title="🔬 Consecutive Sweep Diff Plotter",
        border_style="cyan"
    ))

    # Validate conflicting options
    if individual_only and summary_only:
        console.print("[red]✗[/red] Cannot use both --individual-only and --summary-only")
        raise typer.Exit(1)

    # Determine what to plot
    plot_individual = not summary_only
    plot_summary = not individual_only
    show_resistance = not no_resistance

    try:
        # Generate plots
        with console.status(f"[cyan]Generating plots for {chip_name}...", spinner="dots"):
            generated_plots = plot_consecutive_sweep_differences(
                chip_number=chip_number,
                chip_group=group,
                procedure=procedure,
                output_dir=output_dir,
                show_resistance=show_resistance,
                plot_individual=plot_individual,
                plot_summary=plot_summary,
                tag=tag
            )

        # Success message
        console.print()
        console.print(f"[green]✓[/green] Generated {len(generated_plots)} plots")

        # Show output locations
        if generated_plots:
            console.print("\n[bold]Output files:[/bold]")
            for plot_path in generated_plots[:5]:  # Show first 5
                console.print(f"  • {plot_path}")
            if len(generated_plots) > 5:
                console.print(f"  ... and {len(generated_plots) - 5} more")

            # Show summary location
            output_dir_display = generated_plots[0].parent
            console.print(f"\n[dim]Output directory: {output_dir_display}[/dim]")

    except FileNotFoundError as e:
        console.print(f"\n[red]✗ Error:[/red] {e}")
        console.print("\n[yellow]Hint:[/yellow] Run metrics extraction first:")
        console.print(f"  python3 process_and_analyze.py derive-all-metrics --chip {chip_number}")
        raise typer.Exit(1)

    except ValueError as e:
        console.print(f"\n[red]✗ Error:[/red] {e}")
        console.print("\n[yellow]Possible causes:[/yellow]")
        console.print("  1. No consecutive measurements (seq_num has gaps)")
        console.print("  2. Insufficient Vg overlap between sweeps")
        console.print("  3. Metrics not extracted yet")
        console.print(f"\nCheck chip history:")
        console.print(f"  python3 process_and_analyze.py show-history {chip_number} --proc {procedure or 'IVg'}")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error:[/red] {e}")
        import traceback
        console.print("\n[dim]" + traceback.format_exc() + "[/dim]")
        raise typer.Exit(1)

    console.print()
