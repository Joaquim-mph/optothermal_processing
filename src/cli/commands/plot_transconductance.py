"""Transconductance plotting command: plot-transconductance."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.console import Console
from src.cli.context import get_context
from src.cli.cache import load_history_cached
from rich.panel import Panel
import polars as pl

from src.plotting import transconductance, plot_utils
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



@cli_command(
    name="plot-transconductance",
    group="plotting",
    description="Generate transconductance (gm = dI/dVg) plots"
)
def plot_transconductance_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers of IVg experiments: comma-separated or ranges (e.g., '2,8,14' or '10-20' or '10-15,20,25-30'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all IVg experiments"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Launch interactive experiment selector (TUI)"
    ),
    method: str = typer.Option(
        "gradient",
        "--method",
        "-m",
        help="Derivative method: 'gradient' (numpy.gradient) or 'savgol' (Savitzky-Golay filter)"
    ),
    window_length: int = typer.Option(
        9,
        "--window",
        help="Savitzky-Golay window length (odd number, only used with --method savgol)"
    ),
    polyorder: int = typer.Option(
        3,
        "--polyorder",
        help="Savitzky-Golay polynomial order (only used with --method savgol)"
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
    vds: Optional[float] = typer.Option(
        None,
        "--vds",
        help="Filter by VDS voltage (V)"
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
    Generate transconductance (gm = dI/dVg) plots from IVg experiments.

    Computes and plots the transconductance for IVg measurements. Two methods available:
    - 'gradient': Uses numpy.gradient (default, matches PyQtGraph behavior)
    - 'savgol': Uses Savitzky-Golay filter for smoother curves

    IMPORTANT: Only IVg experiments can be used for transconductance plots.
    Use 'show-history --proc IVg' to find valid IVg seq numbers.

    Examples:
        # Plot transconductance with default gradient method
        python process_and_analyze.py plot-transconductance 67 --seq 2,8,14

        # Interactive selection (TUI)
        python process_and_analyze.py plot-transconductance 67 --interactive

        # Use Savitzky-Golay filter for smoother curves
        python process_and_analyze.py plot-transconductance 67 --seq 2,8,14 --method savgol

        # Auto-select all IVg with custom window
        python process_and_analyze.py plot-transconductance 67 --auto --method savgol --window 11

        # Filter by date
        python process_and_analyze.py plot-transconductance 67 --auto --date 2025-10-15
    """
    ctx.print()
    ctx.print(Panel.fit(
        f"[bold magenta]Transconductance Plot: {chip_group}{chip_number}[/bold magenta]",
        border_style="magenta"
    ))
    ctx.print()


    if output_dir is None:
        output_dir = ctx.output_dir
        if ctx.verbose:
            ctx.print(f"[dim]Using output directory from config: {output_dir}[/dim]")

    if history_dir is None:
        history_dir = ctx.history_dir
        if ctx.verbose:
            ctx.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    # Validate method
    method = method.lower()
    if method not in ["gradient", "savgol"]:
        ctx.print(f"[red]Error:[/red] Invalid method '{method}'. Must be 'gradient' or 'savgol'")
        raise typer.Exit(1)

    # Step 1: Get seq numbers (manual, auto, or interactive)
    mode_count = sum([bool(seq), auto, interactive])
    if mode_count > 1:
        ctx.print("[red]Error:[/red] Can only use one of: --seq, --auto, or --interactive")
        raise typer.Exit(1)

    if mode_count == 0:
        ctx.print("[red]Error:[/red] Must specify one of: --seq, --auto, or --interactive")
        ctx.print("[yellow]Hint:[/yellow] Use --seq 2,8,14, --auto, or --interactive")
        ctx.print("[yellow]Note:[/yellow] Only IVg experiments can be used for transconductance")
        ctx.print("[dim]      Run: python process_and_analyze.py show-history {chip_number} --proc IVg[/dim]")
        raise typer.Exit(1)

    try:
        if auto:
            ctx.print("[cyan]Auto-selecting IVg experiments...[/cyan]")
            filters = {}
            if vds is not None:
                filters["vds"] = vds
            if date is not None:
                filters["date"] = date

            seq_numbers = auto_select_experiments(
                chip_number,
                "IVg",  # Only select IVg experiments
                chip_group,
                history_dir,
                filters
            )
            ctx.print(f"[green]✓[/green] Auto-selected {len(seq_numbers)} IVg experiment(s)")
        elif interactive:
            ctx.print("[red]Error:[/red] Interactive mode not yet updated for Parquet-based pipeline")
            ctx.print("[yellow]Hint:[/yellow] Use --seq or --auto instead:")
            ctx.print("  [cyan]--seq 2,8,14[/cyan]   # Specify seq numbers")
            ctx.print("  [cyan]--auto[/cyan]         # Auto-select all IVg")
            ctx.print("  [cyan]--auto --vds 0.1[/cyan] # Auto-select with filter")
            raise typer.Exit(1)
        else:
            seq_numbers = parse_seq_list(seq)
            ctx.print(f"[cyan]Using specified seq numbers:[/cyan] {seq_numbers}")

    except (ValueError, FileNotFoundError) as e:
        ctx.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 2: Validate seq numbers exist
    ctx.print("\n[cyan]Validating experiments...[/cyan]")
    valid, errors = validate_experiments_exist(
        seq_numbers,
        chip_number,
        chip_group,
        history_dir
    )

    if not valid:
        ctx.print("[red]Validation failed:[/red]")
        for error in errors:
            ctx.print(f"  • {error}")
        raise typer.Exit(1)

    ctx.print(f"[green]✓[/green] All seq numbers valid")

    # Dry-run mode: exit after validation, before loading metadata
    if dry_run:
        # Calculate output filename (using standardized naming)
        output_dir_calc = setup_output_dir(chip_number, chip_group, output_dir)
        plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

        if method == "gradient":
            output_file = output_dir_calc / f"encap{chip_number}_gm_{plot_tag}.png"
        else:  # savgol
            output_file = output_dir_calc / f"encap{chip_number}_gm_savgol_{plot_tag}.png"

        # Check if file already exists
        file_exists = output_file.exists()
        file_status = "[yellow](file exists - will overwrite)[/yellow]" if file_exists else "[green](new file)[/green]"

        ctx.print()
        ctx.print(Panel(
            f"[cyan]Output file:[/cyan]\n{output_file}\n{file_status}",
            title="[bold]Output File[/bold]",
            border_style="cyan"
        ))
        ctx.print()
        ctx.print("[bold green]✓ Dry run complete - no files generated[/bold green]")
        ctx.print("[dim]  Run without --dry-run to generate plot[/dim]")
        ctx.print("[dim]  Use --preview to see full experiment details[/dim]")
        raise typer.Exit(0)

    # Step 3: Load history data (includes parquet_path to staged measurements)
    ctx.print("\n[cyan]Loading experiment history...[/cyan]")
    try:
        from src.cli.helpers import load_history_for_plotting
        history = load_history_for_plotting(
            seq_numbers,
            chip_number,
            chip_group,
            history_dir
        )
    except Exception as e:
        ctx.print(f"[red]Error loading history:[/red] {e}")
        raise typer.Exit(1)

    if history.height == 0:
        ctx.print("[red]Error:[/red] No experiments loaded")
        raise typer.Exit(1)

    # Use parquet_path (staged Parquet) if available, otherwise fall back to source_file (raw CSV)
    # Plotting functions expect source_file column
    if "parquet_path" in history.columns:
        # Prefer parquet_path - overwrite source_file if it exists, or create it
        history = history.drop("source_file") if "source_file" in history.columns else history
        history = history.rename({"parquet_path": "source_file"})
    elif "source_file" not in history.columns:
        # Neither column exists - error
        ctx.print("[red]Error:[/red] History file missing both 'parquet_path' and 'source_file' columns")
        ctx.print("[yellow]Hint:[/yellow] Regenerate history files with: [cyan]build-all-histories[/cyan]")
        raise typer.Exit(1)

    # Step 4: Apply additional filters (if any)
    if vds is not None or date is not None:
        ctx.print("\n[cyan]Applying filters...[/cyan]")
        original_count = history.height
        history = apply_metadata_filters(history, vds=vds, date=date)

        if history.height == 0:
            ctx.print("[red]Error:[/red] No experiments remain after filtering")
            raise typer.Exit(1)

        ctx.print(f"[green]✓[/green] Filtered: {original_count} → {history.height} experiment(s)")

    # Step 5: CRITICAL - Verify ALL experiments are IVg type
    ctx.print("\n[cyan]Validating experiment types...[/cyan]")
    if "proc" in history.columns:
        non_ivg = history.filter(pl.col("proc") != "IVg")
        if non_ivg.height > 0:
            ctx.print(f"[red]Error:[/red] Found {non_ivg.height} non-IVg experiment(s)")
            ctx.print("[red]Transconductance can only be computed from IVg experiments![/red]")
            ctx.print("\n[yellow]Non-IVg experiments found:[/yellow]")
            for row in non_ivg.iter_rows(named=True):
                seq_num = row.get("seq", "?")
                proc = row.get("proc", "?")
                ctx.print(f"  • Seq {seq_num}: {proc}")
            ctx.print(f"\n[yellow]Hint:[/yellow] Use [cyan]show-history {chip_number} --proc IVg[/cyan] to find valid IVg experiments")
            raise typer.Exit(1)
    else:
        ctx.print("[yellow]Warning:[/yellow] Could not verify experiment types (no 'proc' column)")
        ctx.print("[dim]Proceeding anyway, but results may fail if non-IVg data is present[/dim]")

    ctx.print(f"[green]✓[/green] All {history.height} experiment(s) are IVg type")

    # Step 6: Display selected experiments
    ctx.print()
    display_experiment_list(history, title="IVg Experiments for Transconductance")

    # Step 7: Display plot settings
    ctx.print()
    method_desc = {
        "gradient": "numpy.gradient (central differences)",
        "savgol": f"Savitzky-Golay (window={window_length}, poly={polyorder})"
    }
    display_plot_settings({
        "Plot type": "Transconductance (gm = dI/dVg)",
        "Method": method_desc[method],
        "Curves": f"{history.height} IVg measurement(s)",
        "Output directory": str(output_dir)
    })

    # Step 8: Setup output directory and generate plot tag
    output_dir = setup_output_dir(chip_number, chip_group, output_dir)

    # Generate unique tag based on seq numbers and method
    plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

    # Preview output filename
    if method == "gradient":
        output_file = output_dir / f"encap{chip_number}_gm_{plot_tag}.png"
    else:  # savgol
        output_file = output_dir / f"encap{chip_number}_gm_savgol_{plot_tag}.png"

    ctx.print()
    ctx.print(Panel(
        f"[cyan]Output file:[/cyan]\n{output_file}",
        title="[bold]Output File[/bold]",
        border_style="cyan"
    ))

    # Exit in preview mode
    if preview:
        ctx.print()
        ctx.print("[bold green]✓ Preview complete - no files generated[/bold green]")
        ctx.print("[dim]  Run without --preview to generate plot[/dim]")
        raise typer.Exit(0)

    # Step 9: Set FIG_DIR and call appropriate plotting function
    ctx.print("\n[cyan]Generating transconductance plot...[/cyan]")
    transconductance.FIG_DIR = output_dir

    # NOTE: Plotting functions expect 'source_file' column which we created by renaming 'parquet_path'
    # The plotting functions now read from staged Parquet files (fast!)
    # base_dir parameter is now ignored since paths are absolute in source_file column
    base_dir = Path(".")  # Not used, but kept for API compatibility

    try:
        if method == "gradient":
            transconductance.plot_ivg_transconductance(
                history,
                base_dir,
                plot_tag
            )
        else:  # savgol
            transconductance.plot_ivg_transconductance_savgol(
                history,
                base_dir,
                plot_tag,
                window_length=window_length,
                polyorder=polyorder
            )

    except Exception as e:
        ctx.print(f"[red]Error generating plot:[/red] {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # Step 10: Display success with output file path
    ctx.print()
    display_plot_success(output_file)
    ctx.print()
