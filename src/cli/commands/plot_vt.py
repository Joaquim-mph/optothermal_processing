"""Vt plotting command: plot-vt."""

import typer
from pathlib import Path
from typing import Optional

from src.cli.plugin_system import cli_command


@cli_command(
    name="plot-vt-presets",
    group="plotting",
    description="List available Vt plot presets",
    aliases=["list-vt-presets"]
)
def list_vt_presets_command():
    """List all available Vt plot presets with descriptions."""
    from rich.panel import Panel
    from rich.table import Table

    from src.cli.context import get_context
    from src.plotting.vt_presets import PRESETS

    ctx = get_context()

    ctx.print()
    ctx.print(Panel.fit(
        "[bold cyan]Available Vt Plot Presets[/bold cyan]",
        border_style="cyan"
    ))
    ctx.print()

    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    table.add_column("Preset Name", style="yellow", width=20)
    table.add_column("Description", style="white", width=40)
    table.add_column("Configuration", style="dim", width=50)

    for name, preset in PRESETS.items():
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

    ctx.print(table)
    ctx.print()
    ctx.print("[dim]Usage: [cyan]plot-vt --preset <preset_name>[/cyan][/dim]")
    ctx.print("[dim]Example: [cyan]plot-vt 67 --seq 52,57,58 --preset dark[/cyan][/dim]")
    ctx.print()


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
    legend_by: str = typer.Option(
        "wavelength",
        "--legend",
        "-l",
        help="Legend grouping: 'wavelength' (default), 'vg', 'led_voltage', 'irradiated_power', 'datetime'. Aliases: 'wl'→wavelength, 'gate'→vg, 'led'→led_voltage, 'power'/'pow'→irradiated_power"
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
    preset: Optional[str] = typer.Option(
        None,
        "--preset",
        "-p",
        help="Use preset configuration: dark, light_power_sweep, light_spectral, custom. Run 'plot-vt-presets' to list."
    ),
    baseline_t: Optional[float] = typer.Option(
        None,
        "--baseline",
        help="Baseline time in seconds (overrides preset). If neither --preset nor --baseline is set, defaults to 60.0s with fixed mode."
    ),
    baseline_mode: Optional[str] = typer.Option(
        None,
        "--baseline-mode",
        help="Baseline mode: 'fixed', 'auto', or 'none' (overrides preset)."
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
    resistance: bool = typer.Option(
        False,
        "--resistance",
        "-r",
        help="Plot resistance R=V/I instead of voltage"
    ),
    absolute: bool = typer.Option(
        False,
        "--absolute",
        "-a",
        help="Plot absolute value |R| (only with --resistance)"
    ),
    theme: Optional[str] = typer.Option(
        None,
        "--theme",
        help="Plot theme override (prism_rain, paper, presentation, minimal). Overrides global --plot-theme."
    ),
    format: Optional[str] = typer.Option(
        None,
        "--format",
        help="Output format override (png, pdf, svg, jpg). Overrides global --plot-format."
    ),
    dpi: Optional[int] = typer.Option(
        None,
        "--dpi",
        help="DPI override (72-1200). Overrides global --plot-dpi."
    ),
):
    """
    Generate Vt overlay plots from terminal.

    Plot Vt (drain-source voltage vs time) experiments with baseline correction and
    customizable legend grouping. Prevents overwriting by using unique
    filenames based on the experiments selected.

    Examples:
        # Plot specific experiments with wavelength legend (default)
        python process_and_analyze.py plot-vt 67 --seq 52,57,58

        # Plot resistance R=V/I
        python process_and_analyze.py plot-vt 67 --seq 52,57,58 --resistance

        # Plot absolute resistance |R|
        python process_and_analyze.py plot-vt 67 --seq 52,57,58 --resistance --absolute

        # Auto-select all Vt experiments with resistance
        python process_and_analyze.py plot-vt 67 --auto --resistance

        # Use LED voltage legend
        python process_and_analyze.py plot-vt 67 --auto --legend led_voltage

        # Use irradiated power legend (requires enriched history from derive-all-metrics)
        python process_and_analyze.py plot-vt 67 --auto --legend irradiated_power

        # Filter by gate voltage
        python process_and_analyze.py plot-vt 67 --auto --vg -0.4

        # Custom output location
        python process_and_analyze.py plot-vt 67 --seq 52,57,58 --output results/

        # No baseline correction (raw data)
        python process_and_analyze.py plot-vt 67 --seq 10,11,12 --baseline-mode none

    Note:
        The 'irradiated_power'/'power' legend option requires enriched chip histories
        with calibration data. Run 'derive-all-metrics' to generate these.
    """
    import polars as pl
    from rich.panel import Panel

    from src.cli.context import get_context
    from src.cli.helpers import (
        parse_seq_list,
        generate_plot_tag,
        setup_output_dir,
        auto_select_experiments,
        validate_experiments_exist,
        apply_metadata_filters,
        display_experiment_list,
        display_plot_settings,
        display_plot_success,
        load_history_for_plotting,
    )
    from src.cli.main import get_plot_config
    from src.plotting import vt
    from src.plotting.vt_presets import PRESETS

    ctx = get_context()
    ctx.print()
    ctx.print(Panel.fit(
        f"[bold cyan]Vt Overlay Plot: {chip_group}{chip_number}[/bold cyan]",
        border_style="cyan"
    ))
    ctx.print()

    # Validate flag combinations
    if absolute and not resistance:
        ctx.print("[yellow]Warning:[/yellow] --absolute flag ignored (only valid with --resistance)")
        absolute = False

    if output_dir is None:
        output_dir = ctx.output_dir
        if ctx.verbose:
            ctx.print(f"[dim]Using output directory from config: {output_dir}[/dim]")

    # Auto-detect if we need enriched histories (for power legend)
    needs_enriched = legend_by.lower() in {"pow", "power", "irradiated_power", "led_power"}

    if history_dir is None:
        if needs_enriched:
            # Use enriched histories for power legend
            base_history_dir = Path(ctx.history_dir)
            # Navigate: data/02_stage/chip_histories/ -> data/03_derived/chip_histories_enriched/
            data_dir = base_history_dir.parent.parent
            history_dir = data_dir / "03_derived" / "chip_histories_enriched"

            if not history_dir.exists():
                ctx.print(f"[red]Error:[/red] Enriched histories not found at {history_dir}")
                ctx.print("[yellow]The 'power' legend option requires enriched chip histories.[/yellow]")
                ctx.print("[cyan]Run these commands first:[/cyan]")
                ctx.print("  1. [cyan]python3 process_and_analyze.py full-pipeline[/cyan]")
                ctx.print("  2. [cyan]python3 process_and_analyze.py derive-all-metrics[/cyan]")
                raise typer.Exit(1)

            ctx.print(f"[dim]Using enriched histories for power data: {history_dir}[/dim]")
        else:
            history_dir = ctx.history_dir
            if ctx.verbose:
                ctx.print(f"[dim]Using history directory from config: {history_dir}[/dim]")

    # Step 1: Get seq numbers (manual or auto)
    mode_count = sum([bool(seq), auto])
    if mode_count > 1:
        ctx.print("[red]Error:[/red] Can only use one of: --seq or --auto")
        raise typer.Exit(1)

    if mode_count == 0:
        ctx.print("[red]Error:[/red] Must specify one of: --seq or --auto")
        ctx.print("[yellow]Hint:[/yellow] Use --seq 52,57,58 or --auto")
        raise typer.Exit(1)

    try:
        if auto:
            ctx.print("[cyan]Auto-selecting Vt experiments...[/cyan]")
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
            ctx.print(f"[green]✓[/green] Auto-selected {len(seq_numbers)} Vt experiment(s)")
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
        # Use preset's baseline_mode for filename if --preset is set and --baseline-mode is not
        preview_baseline_mode = baseline_mode
        if preview_baseline_mode is None and preset and preset in PRESETS:
            preview_baseline_mode = PRESETS[preset].baseline_mode
        if preview_baseline_mode is None:
            preview_baseline_mode = "fixed"
        raw_suffix = "_raw" if preview_baseline_mode == "none" else ""
        resistance_suffix = "_R" if resistance else ""
        output_file = output_dir_calc / f"encap{chip_number}_Vt_{plot_tag}{raw_suffix}{resistance_suffix}.png"

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
    if vg is not None or wavelength is not None or date is not None:
        ctx.print("\n[cyan]Applying filters...[/cyan]")
        original_count = history.height
        history = apply_metadata_filters(history, vg=vg, wavelength=wavelength, date=date)

        if history.height == 0:
            ctx.print("[red]Error:[/red] No experiments remain after filtering")
            raise typer.Exit(1)

        ctx.print(f"[green]✓[/green] Filtered: {original_count} → {history.height} experiment(s)")

    # Step 4b: Apply preset configuration (if specified)
    baseline_auto_divisor = 2.0
    plot_start_time: Optional[float] = None  # vt.plot_vt_overlay defaults via PlotConfig if None

    if preset:
        if preset not in PRESETS:
            ctx.print(f"[red]Error:[/red] Unknown preset '{preset}'")
            ctx.print(f"[yellow]Available presets:[/yellow] {', '.join(PRESETS.keys())}")
            ctx.print("[dim]Use 'plot-vt-presets' to see detailed preset information[/dim]")
            raise typer.Exit(1)

        preset_config = PRESETS[preset]
        ctx.print(f"\n[green]✓[/green] Using preset: [bold]{preset_config.name}[/bold]")
        ctx.print(f"[dim]  {preset_config.description}[/dim]\n")

        # Apply preset settings (CLI flags still take precedence)
        if baseline_mode is None:
            baseline_mode = preset_config.baseline_mode
        else:
            ctx.print(f"[dim]  Baseline mode overridden: {baseline_mode} (preset default ignored)[/dim]")

        baseline_auto_divisor = preset_config.baseline_auto_divisor
        plot_start_time = preset_config.plot_start_time

        # baseline_t handling: only apply preset's fixed value if user didn't pass --baseline
        if baseline_t is None and baseline_mode == "fixed":
            baseline_t = preset_config.baseline_value
        elif baseline_t is not None:
            # User passed --baseline: force fixed mode unless explicitly set otherwise
            if baseline_mode is None or baseline_mode == preset_config.baseline_mode:
                baseline_mode = "fixed"
            ctx.print(f"[dim]  Baseline overridden: {baseline_t}s (preset default ignored)[/dim]")

        # Apply legend_by if user kept the default
        if legend_by == "wavelength":  # Default from argument
            legend_by = preset_config.legend_by
            ctx.print(f"[dim]  Legend by: {legend_by} (from preset)[/dim]")

    # Fallbacks if no preset applied
    if baseline_mode is None:
        baseline_mode = "fixed"
    if baseline_t is None:
        baseline_t = 60.0

    # Step 5: Verify all are Vt experiments
    if "proc" in history.columns:
        non_vt = history.filter(pl.col("proc") != "Vt")
        if non_vt.height > 0:
            ctx.print(f"[yellow]Warning:[/yellow] {non_vt.height} non-Vt experiment(s) found and will be skipped")
            ctx.print("[dim]Only Vt experiments will be plotted[/dim]")

    # Step 6: Display selected experiments
    ctx.print()
    display_experiment_list(history, title="Vt Experiments to Plot")

    # Step 7: Display plot settings
    ctx.print()
    plot_mode = "Resistance (R = V/I)" if resistance else "Voltage (ΔVds)"
    if resistance and absolute:
        plot_mode = "Absolute Resistance (|R| = |V/I|)"

    display_plot_settings({
        "Plot type": "Vt overlay (Vds vs t)" if not resistance else "Vt overlay (R vs t)",
        "Y-axis": plot_mode,
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
    resistance_suffix = "_R" if resistance else ""
    output_file = output_dir / f"encap{chip_number}_Vt_{plot_tag}{raw_suffix}{resistance_suffix}.png"

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

    # Step 9: Get plot config and apply command-specific overrides
    ctx.print("\n[cyan]Generating plot...[/cyan]")
    plot_config = get_plot_config()

    # Apply command-specific overrides
    plot_overrides = {}
    if theme is not None:
        plot_overrides["theme"] = theme
    if format is not None:
        plot_overrides["format"] = format
    if dpi is not None:
        plot_overrides["dpi"] = dpi

    # Override output_dir from command line
    if output_dir is not None:
        plot_overrides["output_dir"] = output_dir

    if plot_overrides:
        plot_config = plot_config.copy(**plot_overrides)
        if ctx.verbose:
            overrides_str = ", ".join([f"{k}={v}" for k, v in plot_overrides.items()])
            ctx.print(f"[dim]Plot config overrides: {overrides_str}[/dim]")

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
            baseline_auto_divisor=baseline_auto_divisor,
            plot_start_time=plot_start_time,
            legend_by=legend_by,
            padding=padding,
            resistance=resistance,
            absolute=absolute,
            config=plot_config
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
