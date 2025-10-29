"""ITS plotting command: plot-its."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.plotting import its, plot_utils
from src.plotting.its_presets import PRESETS, get_preset, preset_summary
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
import polars as pl

console = Console()


@cli_command(
    name="plot-its-presets",
    group="plotting",
    description="List available ITS plot presets",
    aliases=["list-its-presets"]
)
def list_presets_command():
    """List all available ITS plot presets with descriptions."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]Available ITS Plot Presets[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    table.add_column("Preset Name", style="yellow", width=20)
    table.add_column("Description", style="white", width=40)
    table.add_column("Configuration", style="dim", width=50)

    for name, preset in PRESETS.items():
        # Build config summary
        config_lines = []
        if preset.baseline_mode == "none":
            config_lines.append("• No baseline correction")
        elif preset.baseline_mode == "auto":
            config_lines.append(f"• Auto baseline (period / {preset.baseline_auto_divisor})")
        else:
            config_lines.append(f"• Fixed baseline: {preset.baseline_value}s")

        config_lines.append(f"• Plot start: {preset.plot_start_time}s")
        config_lines.append(f"• Legend by: {preset.legend_by}")
        if preset.check_duration_mismatch:
            config_lines.append(f"• Duration check: ±{preset.duration_tolerance*100:.0f}%")

        config_str = "\n".join(config_lines)

        table.add_row(name, preset.description, config_str)

    console.print(table)
    console.print()
    console.print("[dim]Usage: [cyan]plot-its --preset <preset_name>[/cyan][/dim]")
    console.print("[dim]Example: [cyan]plot-its 67 --seq 52,57,58 --preset dark[/cyan][/dim]")
    console.print()


def _all_its_are_dark(meta: pl.DataFrame) -> bool:
    """
    Check if all It experiments in metadata are dark (no laser).

    Returns True if ALL experiments have laser toggle = False or laser voltage = 0.
    """
    its = meta.filter(pl.col("proc") == "It")
    if its.height == 0:
        return False

    # Check laser toggle column if available
    if "Laser toggle" in its.columns:
        try:
            # Convert to boolean and check if ALL are False
            laser_toggle_col = its["Laser toggle"]
            # Handle various formats: bool, string "true"/"false", etc.
            toggles = []
            for val in laser_toggle_col.to_list():
                if isinstance(val, bool):
                    toggles.append(val)
                elif isinstance(val, str):
                    toggles.append(val.lower() == "true")
                else:
                    # If unclear, assume it might have light
                    toggles.append(True)

            if all(not t for t in toggles):
                return True
        except Exception:
            pass

    # Check laser voltage column if available
    if "Laser voltage" in its.columns or "VL_meta" in its.columns:
        try:
            col_name = "Laser voltage" if "Laser voltage" in its.columns else "VL_meta"
            voltages = its[col_name].cast(pl.Float64).to_list()
            # If ALL voltages are 0 or NaN/None, it's dark
            if all(v is None or v == 0 or v != v for v in voltages):  # v != v checks for NaN
                return True
        except Exception:
            pass

    return False


@cli_command(
    name="plot-its",
    group="plotting",
    description="Generate ITS overlay plots"
)
def plot_its_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '52,57,58' or '89-117' or '89-92,95,100-105'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all ITS experiments"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Launch interactive experiment selector (TUI)"
    ),
    legend_by: str = typer.Option(
        "led_voltage",
        "--legend",
        "-l",
        help="Legend grouping: 'led_voltage', 'wavelength', or 'vg'"
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Custom tag for output filename (default: auto-generated from seq numbers)"
    ),
    output_dir: Path = typer.Option(
        Path("figs"),
        "--output",
        "-o",
        help="Output directory for plots"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    padding: float = typer.Option(
        0.05,
        "--padding",
        help="Y-axis padding (fraction of data range, e.g., 0.05 = 5%)"
    ),
    preset: Optional[str] = typer.Option(
        None,
        "--preset",
        "-p",
        help="Use preset configuration: dark, light_power_sweep, light_spectral, custom"
    ),
    baseline_t: Optional[float] = typer.Option(
        None,
        "--baseline",
        help="Baseline time in seconds (overrides preset). Use --preset for smart defaults."
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
    history_dir: Path = typer.Option(
        Path("data/02_stage/chip_histories"),
        "--history-dir",
        help="Chip history directory (Parquet files)"
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
    Generate ITS overlay plots from terminal.

    Plot ITS (current vs time) experiments with baseline correction and
    customizable legend grouping. Prevents overwriting by using unique
    filenames based on the experiments selected.

    Examples:
        # Plot specific experiments
        python process_and_analyze.py plot-its 67 --seq 52,57,58

        # Interactive selection (TUI)
        python process_and_analyze.py plot-its 67 --interactive

        # Auto-select all ITS with custom legend
        python process_and_analyze.py plot-its 67 --auto --legend wavelength

        # Filter by gate voltage
        python process_and_analyze.py plot-its 67 --auto --vg -0.4

        # Custom output location
        python process_and_analyze.py plot-its 67 --seq 52,57,58 --output results/
    """
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]ITS Overlay Plot: {chip_group}{chip_number}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

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
            console.print("[cyan]Auto-selecting ITS experiments...[/cyan]")
            filters = {}
            if vg is not None:
                filters["vg"] = vg
            if wavelength is not None:
                filters["wavelength"] = wavelength
            if date is not None:
                filters["date"] = date

            seq_numbers = auto_select_experiments(
                chip_number,
                "It",
                history_dir,
                chip_group,
                filters
            )
            console.print(f"[green]✓[/green] Auto-selected {len(seq_numbers)} ITS experiment(s)")
        elif interactive:
            console.print("[red]Error:[/red] Interactive mode not yet updated for Parquet-based pipeline")
            console.print("[yellow]Hint:[/yellow] Use --seq or --auto instead:")
            console.print("  [cyan]--seq 52,57,58[/cyan]   # Specify seq numbers")
            console.print("  [cyan]--auto[/cyan]           # Auto-select all ITS")
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
        history_dir,
        chip_group
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
        output_dir_calc = setup_output_dir(output_dir, chip_number, chip_group)
        plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)
        # Note: Can't detect dark/light in dry-run, assume regular ITS
        output_file = output_dir_calc / f"encap{chip_number}_ITS_{plot_tag}.png"

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
            history_dir,
            chip_group
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

    # Step 5: Apply preset configuration (if specified)
    baseline_mode = "fixed"
    baseline_auto_divisor = 2.0
    plot_start_time = 20.0
    check_duration_mismatch = False
    duration_tolerance = 0.10

    if preset:
        # Validate preset name
        if preset not in PRESETS:
            console.print(f"[red]Error:[/red] Unknown preset '{preset}'")
            console.print(f"[yellow]Available presets:[/yellow] {', '.join(PRESETS.keys())}")
            console.print("[dim]Use 'plot-its-presets' to see detailed preset information[/dim]")
            raise typer.Exit(1)

        preset_config = PRESETS[preset]
        console.print(f"\n[green]✓[/green] Using preset: [bold]{preset_config.name}[/bold]")
        console.print(f"[dim]  {preset_config.description}[/dim]\n")

        # Apply preset settings (can be overridden by CLI flags)
        baseline_mode = preset_config.baseline_mode
        baseline_auto_divisor = preset_config.baseline_auto_divisor
        plot_start_time = preset_config.plot_start_time
        check_duration_mismatch = preset_config.check_duration_mismatch
        duration_tolerance = preset_config.duration_tolerance

        # Apply baseline if not overridden
        if baseline_t is None:
            if baseline_mode == "fixed":
                baseline_t = preset_config.baseline_value
        else:
            # CLI override: force fixed mode
            baseline_mode = "fixed"
            console.print(f"[dim]  Baseline overridden: {baseline_t}s (preset default ignored)[/dim]")

        # Apply legend_by if not explicitly set (check if it's still the default)
        # Note: We can't directly check if user set it, but we can use the preset's recommendation
        if legend_by == "led_voltage":  # Default from argument
            legend_by = preset_config.legend_by
            console.print(f"[dim]  Legend by: {legend_by} (from preset)[/dim]")

    # Fallback: If no preset and no baseline specified, use default
    if baseline_t is None:
        baseline_t = 60.0

    # Step 6: Display selected experiments
    console.print()
    display_experiment_list(history, title="ITS Experiments to Plot")

    # Step 7: Display plot settings
    console.print()
    settings = {
        "Legend by": legend_by,
        "Padding": f"{padding:.2%}",
        "Output directory": str(output_dir)
    }

    if baseline_mode == "none":
        settings["Baseline"] = "None (dark mode)"
    elif baseline_mode == "auto":
        settings["Baseline"] = f"Auto (LED period / {baseline_auto_divisor})"
    else:
        settings["Baseline"] = f"Fixed at {baseline_t} s"

    if check_duration_mismatch:
        settings["Duration check"] = f"Enabled (±{duration_tolerance*100:.0f}% tolerance)"

    if plot_start_time != 20.0:
        settings["Plot start time"] = f"{plot_start_time} s"

    display_plot_settings(settings)

    # Step 7: Setup output directory and generate plot tag
    output_dir = setup_output_dir(output_dir, chip_number, chip_group)

    # Generate unique tag based on seq numbers
    plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

    # Preview output filename (will be updated if dark measurement detected)
    output_file = output_dir / f"encap{chip_number}_ITS_{plot_tag}.png"

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

    # Step 8: Detect if all ITS are dark and choose appropriate plotting function
    all_dark = _all_its_are_dark(history)

    if all_dark:
        console.print("\n[dim]Detected: All ITS experiments are dark (no laser)[/dim]")
        console.print("[dim]Using simplified dark plot (no light window shading)[/dim]")
        # Update output filename for dark plots
        output_file = output_dir / f"encap{chip_number}_ITS_dark_{plot_tag}.png"
        # Adjust legend default for dark plots (vg is more useful than led_voltage)
        if legend_by == "led_voltage":
            console.print("[dim]Tip: For dark measurements, --legend vg might be more useful[/dim]")

    # Step 9: Set FIG_DIR and call plotting function
    console.print("\n[cyan]Generating plot...[/cyan]")
    its.FIG_DIR = output_dir

    # NOTE: Plotting functions expect 'source_file' column which we created by renaming 'parquet_path'
    # The plotting functions now read from staged Parquet files (fast!)
    # base_dir parameter is now ignored since paths are absolute in source_file column
    base_dir = Path(".")  # Not used, but kept for API compatibility

    try:
        if all_dark:
            its.plot_its_dark(
                history,
                base_dir,
                plot_tag,
                baseline_t=baseline_t,
                baseline_mode=baseline_mode,
                baseline_auto_divisor=baseline_auto_divisor,
                plot_start_time=plot_start_time,
                legend_by=legend_by,
                padding=padding,
                check_duration_mismatch=check_duration_mismatch,
                duration_tolerance=duration_tolerance
            )
        else:
            its.plot_its_overlay(
                history,
                base_dir,
                plot_tag,
                baseline_t=baseline_t,
                baseline_mode=baseline_mode,
                baseline_auto_divisor=baseline_auto_divisor,
                plot_start_time=plot_start_time,
                legend_by=legend_by,
                padding=padding,
                check_duration_mismatch=check_duration_mismatch,
                duration_tolerance=duration_tolerance
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


@cli_command(
    name="plot-its-sequential",
    group="plotting",
    description="Generate sequential ITS plots"
)
def plot_its_sequential_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '93,94,95,96' or '89-117' or '89-92,95,100-105'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all ITS experiments"
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Custom tag for output filename (default: auto-generated from seq numbers)"
    ),
    output_dir: Path = typer.Option(
        Path("figs"),
        "--output",
        "-o",
        help="Output directory for plots"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name"
    ),
    plot_start_time: float = typer.Option(
        20.0,
        "--plot-start",
        help="Start time for x-axis in seconds (trimmed from each experiment)"
    ),
    show_boundaries: bool = typer.Option(
        True,
        "--boundaries/--no-boundaries",
        help="Show vertical lines marking experiment boundaries"
    ),
    legend_by: str = typer.Option(
        "datetime",
        "--legend",
        "-l",
        help="Legend grouping: 'datetime' (default), 'wavelength', 'vg', or 'led_voltage'"
    ),
    padding: float = typer.Option(
        0.02,
        "--padding",
        help="Y-axis padding (fraction of data range, e.g., 0.02 = 2%)"
    ),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        help="Filter by date (YYYY-MM-DD)"
    ),
    history_dir: Path = typer.Option(
        Path("data/02_stage/chip_histories"),
        "--history-dir",
        help="Chip history directory (Parquet files)"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Preview mode: show what will be plotted without generating files"
    ),
):
    """
    Generate sequential ITS plots (concatenated in time, not overlaid).

    Plots multiple ITS experiments as a continuous trace where each experiment
    follows the previous one in time, with different colors for each experiment.
    No baseline correction is applied (raw data). Useful for visualizing temporal
    evolution across multiple consecutive experiments.

    Examples:
        # Plot experiments 93-96 sequentially with datetime labels
        python process_and_analyze.py plot-its-sequential 81 --seq 93,94,95,96

        # Use wavelength labels
        python process_and_analyze.py plot-its-sequential 81 --seq 93,94,95,96 -l wavelength

        # Auto-select all ITS experiments with LED voltage labels
        python process_and_analyze.py plot-its-sequential 81 --auto --legend led_voltage

        # With custom settings (no boundaries)
        python process_and_analyze.py plot-its-sequential 81 --seq 93,94,95,96 \\
            --plot-start 10.0 --no-boundaries --legend vg
    """
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]ITS Sequential Plot: {chip_group}{chip_number}[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    # Step 1: Get seq numbers (manual or auto)
    mode_count = sum([bool(seq), auto])
    if mode_count > 1:
        console.print("[red]Error:[/red] Can only use one of: --seq or --auto")
        raise typer.Exit(1)

    if mode_count == 0:
        console.print("[red]Error:[/red] Must specify one of: --seq or --auto")
        console.print("[yellow]Hint:[/yellow] Use --seq 93,94,95 or --auto")
        raise typer.Exit(1)

    try:
        if auto:
            console.print("[cyan]Auto-selecting ITS experiments...[/cyan]")
            filters = {}
            if date is not None:
                filters["date"] = date

            from src.cli.helpers import auto_select_experiments
            seq_numbers = auto_select_experiments(
                chip_number,
                "It",  # ITS experiments
                history_dir,
                chip_group,
                filters
            )
            console.print(f"[green]✓[/green] Auto-selected {len(seq_numbers)} ITS experiment(s)")
        else:
            seq_numbers = parse_seq_list(seq)
            console.print(f"[cyan]Using specified seq numbers:[/cyan] {seq_numbers}")

    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 2: Validate seq numbers exist
    console.print("\n[cyan]Validating experiments...[/cyan]")
    from src.cli.helpers import validate_experiments_exist
    valid, errors = validate_experiments_exist(
        seq_numbers,
        chip_number,
        history_dir,
        chip_group
    )

    if not valid:
        console.print("[red]Validation failed:[/red]")
        for error in errors:
            console.print(f"  • {error}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] All seq numbers valid")

    # Step 3: Load history data
    console.print("\n[cyan]Loading experiment history...[/cyan]")
    try:
        from src.cli.helpers import load_history_for_plotting
        history = load_history_for_plotting(
            seq_numbers,
            chip_number,
            history_dir,
            chip_group
        )
    except Exception as e:
        console.print(f"[red]Error loading history:[/red] {e}")
        raise typer.Exit(1)

    if history.height == 0:
        console.print("[red]Error:[/red] No experiments loaded")
        raise typer.Exit(1)

    # Use parquet_path (staged Parquet) if available
    if "parquet_path" in history.columns:
        history = history.drop("source_file") if "source_file" in history.columns else history
        history = history.rename({"parquet_path": "source_file"})
    elif "source_file" not in history.columns:
        console.print("[red]Error:[/red] History file missing both 'parquet_path' and 'source_file' columns")
        raise typer.Exit(1)

    # Step 4: Display selected experiments
    console.print()
    display_experiment_list(history, title="ITS Experiments (Sequential)")

    # Step 5: Display plot settings
    console.print()
    display_plot_settings({
        "Plot type": "ITS sequential (raw, concatenated in time)",
        "Experiments": f"{history.height} measurement(s)",
        "Plot start time": f"{plot_start_time}s (per experiment)",
        "Legend by": legend_by,
        "Boundaries": "Shown" if show_boundaries else "Hidden",
        "Output directory": str(output_dir)
    })

    # Step 6: Setup output directory and generate plot tag
    output_dir = setup_output_dir(output_dir, chip_number, chip_group)
    plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

    # Preview output filename
    output_file = output_dir / f"encap{chip_number}_ITS_sequential_{plot_tag}.png"

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

    # Step 7: Generate plot
    console.print("\n[cyan]Generating sequential plot...[/cyan]")
    its.FIG_DIR = output_dir
    base_dir = Path(".")  # Not used (parquet_path has absolute paths)

    try:
        its.plot_its_sequential(
            history,
            base_dir,
            plot_tag,
            plot_start_time=plot_start_time,
            show_boundaries=show_boundaries,
            legend_by=legend_by,
            padding=padding
        )
    except Exception as e:
        console.print(f"[red]Error generating plot:[/red] {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # Step 8: Display success
    console.print()
    display_plot_success(output_file)
    console.print()
