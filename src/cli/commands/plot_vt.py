"""Vt plotting command: plot-vt."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
import polars as pl

from src.plotting import vt
from src.cli.helpers import (
    parse_seq_list,
    generate_plot_tag,
    setup_output_dir,
    auto_select_experiments,
    validate_experiments_exist,
    apply_metadata_filters,
    display_experiment_list,
    display_plot_settings,
    display_plot_success
)

console = Console()


@cli_command(
    name="plot-vt",
    group="plotting",
    description="Generate Vt overlay plots"
)
def plot_vt_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '52,57,58' or '89-117'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all Vt experiments"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Launch interactive experiment selector (TUI)"
    ),
    legend_by: str = typer.Option(
        "wavelength",
        "--legend",
        "-l",
        help="Legend grouping: 'wavelength', 'vg', 'led_voltage', or 'datetime'"
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Custom tag for output filename (default: auto-generated from seq numbers)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for plots (default: from config)"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    padding: float = typer.Option(
        0.02,
        "--padding",
        help="Y-axis padding (fraction of data range, e.g., 0.02 = 2%)"
    ),
    baseline_t: Optional[float] = typer.Option(
        60.0,
        "--baseline",
        help="Baseline time in seconds (default: 60.0). Use 0 for t=0 baseline, or --baseline-mode none for no correction."
    ),
    baseline_mode: str = typer.Option(
        "fixed",
        "--baseline-mode",
        help="Baseline mode: 'fixed', 'auto', or 'none' (default: fixed)"
    ),
    vg: Optional[float] = typer.Option(
        None,
        "--vg",
        help="Filter by gate voltage (V)"
    ),
    wavelength: Optional[float] = typer.Option(
        None,
        "--wavelength",
        help="Filter by wavelength (nm)"
    ),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        help="Filter by date (YYYY-MM-DD)"
    ),
    history_dir: Optional[Path] = typer.Option(
        None,
        "--history-dir",
        help="Chip history directory (default: from config)"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Preview mode: show what will be plotted without generating files"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Dry run mode: validate experiments and show output filename only (fastest)"
    ),
):
    """
    Generate Vt overlay plots from terminal.

    Plot Vt (drain-source voltage vs time) experiments with baseline correction and
    customizable legend grouping. Prevents overwriting by using unique
    filenames based on the experiments selected.

    Examples:
        # Plot specific experiments
        python process_and_analyze.py plot-vt 67 --seq 52,57,58

        # Interactive selection (TUI)
        python process_and_analyze.py plot-vt 67 --interactive

        # Auto-select all Vt with custom legend
        python process_and_analyze.py plot-vt 67 --auto --legend wavelength

        # Filter by gate voltage
        python process_and_analyze.py plot-vt 67 --auto --vg -0.4

        # Custom output location
        python process_and_analyze.py plot-vt 67 --seq 52,57,58 --output results/

        # No baseline correction (raw data)
        python process_and_analyze.py plot-vt 67 --seq 10,11,12 --baseline-mode none
    """
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Vt Overlay Plot: {chip_group}{chip_number}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    # Load config for defaults
    from src.cli.main import get_config
    config = get_config()

    if output_dir is None:
        output_dir = config.output_dir
        if config.verbose:
            console.print(f"[dim]Using output directory from config: {output_dir}[/dim]")

    if history_dir is None:
        history_dir = config.history_dir
        if config.verbose:
            console.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    # Step 1: Get seq numbers (manual, auto, or interactive)
    mode_count = sum([bool(seq), auto, interactive])
    if mode_count > 1:
        console.print("[red]Error:[/red] Can only use one of: --seq, --auto, or --interactive")
        raise typer.Exit(1)

    if mode_count == 0:
        console.print("[red]Error:[/red] Must specify one of: --seq, --auto, or --interactive")
        console.print("[yellow]Hint:[/yellow] Use --seq 52,57,58, --auto, or --interactive")
        raise typer.Exit(1)

    try:
        if auto:
            console.print("[cyan]Auto-selecting Vt experiments...[/cyan]")
            filters = {}
            if vg is not None:
                filters["vg"] = vg
            if wavelength is not None:
                filters["wavelength"] = wavelength
            if date is not None:
                filters["date"] = date

            seq_numbers = auto_select_experiments(
                chip_number,
                "Vt",
                chip_group,
                history_dir,
                filters
            )
            console.print(f"[green]✓[/green] Auto-selected {len(seq_numbers)} Vt experiment(s)")
        elif interactive:
            console.print("[red]Error:[/red] Interactive mode not yet updated for Parquet-based pipeline")
            console.print("[yellow]Hint:[/yellow] Use --seq or --auto instead:")
            console.print("  [cyan]--seq 52,57,58[/cyan]   # Specify seq numbers")
            console.print("  [cyan]--auto[/cyan]           # Auto-select all Vt")
            console.print("  [cyan]--auto --vg -0.4[/cyan] # Auto-select with filter")
            raise typer.Exit(1)
        else:
            seq_numbers = parse_seq_list(seq)
            console.print(f"[cyan]Using specified seq numbers:[/cyan] {seq_numbers}")

    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 2: Validate seq numbers exist
    console.print("\n[cyan]Validating experiments...[/cyan]")
    valid, errors = validate_experiments_exist(
        seq_numbers,
        chip_number,
        chip_group,
        history_dir
    )

    if not valid:
        console.print("[red]Validation failed:[/red]")
        for error in errors:
            console.print(f"  • {error}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] All seq numbers valid")

    # Dry-run mode: exit after validation, before loading metadata
    if dry_run:
        # Calculate output filename (using standardized naming)
        output_dir_calc = setup_output_dir(chip_number, chip_group, output_dir)
        plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)
        output_file = output_dir_calc / f"encap{chip_number}_Vt_{plot_tag}.png"

        # Check if file already exists
        file_exists = output_file.exists()
        file_status = "[yellow](file exists - will overwrite)[/yellow]" if file_exists else "[green](new file)[/green]"

        console.print()
        console.print(Panel(
            f"[cyan]Output file:[/cyan]\n{output_file}\n{file_status}",
            title="[bold]Output File[/bold]",
            border_style="cyan"
        ))
        console.print()
        console.print("[bold green]✓ Dry run complete - no files generated[/bold green]")
        console.print("[dim]  Run without --dry-run to generate plot[/dim]")
        console.print("[dim]  Use --preview to see full experiment details[/dim]")
        raise typer.Exit(0)

    # Step 3: Load history data (includes parquet_path to staged measurements)
    console.print("\n[cyan]Loading experiment history...[/cyan]")
    try:
        from src.cli.helpers import load_history_for_plotting
        history = load_history_for_plotting(
            seq_numbers,
            chip_number,
            chip_group,
            history_dir
        )
    except Exception as e:
        console.print(f"[red]Error loading history:[/red] {e}")
        raise typer.Exit(1)

    if history.height == 0:
        console.print("[red]Error:[/red] No experiments loaded")
        raise typer.Exit(1)

    # Use parquet_path (staged Parquet) if available, otherwise fall back to source_file (raw CSV)
    # Plotting functions expect source_file column
    if "parquet_path" in history.columns:
        # Prefer parquet_path - overwrite source_file if it exists, or create it
        history = history.drop("source_file") if "source_file" in history.columns else history
        history = history.rename({"parquet_path": "source_file"})
    elif "source_file" not in history.columns:
        # Neither column exists - error
        console.print("[red]Error:[/red] History file missing both 'parquet_path' and 'source_file' columns")
        console.print("[yellow]Hint:[/yellow] Regenerate history files with: [cyan]build-all-histories[/cyan]")
        raise typer.Exit(1)

    # Step 4: Apply additional filters (if any)
    if vg is not None or wavelength is not None or date is not None:
        console.print("\n[cyan]Applying filters...[/cyan]")
        original_count = history.height
        history = apply_metadata_filters(history, vg=vg, wavelength=wavelength, date=date)

        if history.height == 0:
            console.print("[red]Error:[/red] No experiments remain after filtering")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Filtered: {original_count} → {history.height} experiment(s)")

    # Step 5: Verify all are Vt experiments
    if "proc" in history.columns:
        non_vt = history.filter(pl.col("proc") != "Vt")
        if non_vt.height > 0:
            console.print(f"[yellow]Warning:[/yellow] {non_vt.height} non-Vt experiment(s) found and will be skipped")
            console.print("[dim]Only Vt experiments will be plotted[/dim]")

    # Step 6: Display selected experiments
    console.print()
    display_experiment_list(history, title="Vt Experiments to Plot")

    # Step 7: Display plot settings
    console.print()
    display_plot_settings({
        "Plot type": "Vt overlay (Vds vs t)",
        "Curves": f"{history.height} measurement(s)",
        "Baseline mode": baseline_mode,
        "Baseline time": f"{baseline_t}s" if baseline_mode == "fixed" else "auto" if baseline_mode == "auto" else "none",
        "Legend by": legend_by,
        "Output directory": str(output_dir)
    })

    # Step 8: Setup output directory and generate plot tag
    output_dir = setup_output_dir(chip_number, chip_group, output_dir)

    # Generate unique tag based on seq numbers
    plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

    # Preview output filename
    raw_suffix = "_raw" if baseline_mode == "none" else ""
    output_file = output_dir / f"encap{chip_number}_Vt_{plot_tag}{raw_suffix}.png"

    console.print()
    console.print(Panel(
        f"[cyan]Output file:[/cyan]\n{output_file}",
        title="[bold]Output File[/bold]",
        border_style="cyan"
    ))

    # Exit in preview mode
    if preview:
        console.print()
        console.print("[bold green]✓ Preview complete - no files generated[/bold green]")
        console.print("[dim]  Run without --preview to generate plot[/dim]")
        raise typer.Exit(0)

    # Step 9: Set FIG_DIR and call plotting function
    console.print("\n[cyan]Generating plot...[/cyan]")
    vt.FIG_DIR = output_dir

    # NOTE: Plotting functions expect 'source_file' column which we created by renaming 'parquet_path'
    # The plotting functions now read from staged Parquet files (fast!)
    # base_dir parameter is now ignored since paths are absolute in source_file column
    base_dir = Path(".")  # Not used, but kept for API compatibility

    try:
        vt.plot_vt_overlay(
            history,
            base_dir,
            plot_tag,
            baseline_t=baseline_t,
            baseline_mode=baseline_mode,
            legend_by=legend_by,
            padding=padding
        )
    except Exception as e:
        console.print(f"[red]Error generating plot:[/red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # Step 10: Display success with output file path
    console.print()
    display_plot_success(output_file)
    console.print()
