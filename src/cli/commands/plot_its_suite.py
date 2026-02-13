"""ITS suite plotting command: plot-its-suite.

Generates 3 plots in one call: overlay, sequential, and photoresponse.
"""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.panel import Panel

from src.plotting import its, its_photoresponse
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
import polars as pl


@cli_command(
    name="plot-its-suite",
    group="plotting",
    description="Generate ITS suite: overlay + sequential + photoresponse",
)
def plot_its_suite_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)",
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '4-7' or '4,5,6,7'). Required unless --auto is used.",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all ITS experiments",
    ),
    legend_by: str = typer.Option(
        "led_voltage",
        "--legend",
        "-l",
        help="Legend grouping: 'led_voltage' (default), 'wavelength', 'vg', 'irradiated_power', 'datetime'",
    ),
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Custom tag for output filename (default: auto-generated from seq numbers)",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for plots (default: from config)",
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name",
    ),
    padding: float = typer.Option(
        0.05,
        "--padding",
        help="Y-axis padding (fraction of data range, e.g., 0.05 = 5%)",
    ),
    preset: Optional[str] = typer.Option(
        None,
        "--preset",
        "-p",
        help="Use preset configuration: dark, light_power_sweep, light_spectral, custom",
    ),
    baseline_t: Optional[float] = typer.Option(
        None,
        "--baseline",
        help="Baseline time in seconds (overrides preset). Use --preset for smart defaults.",
    ),
    vg: Optional[float] = typer.Option(
        None,
        "--vg",
        help="Filter by gate voltage (V)",
    ),
    wavelength: Optional[float] = typer.Option(
        None,
        "--wavelength",
        help="Filter by wavelength (nm)",
    ),
    date: Optional[str] = typer.Option(
        None,
        "--date",
        help="Filter by date (YYYY-MM-DD)",
    ),
    history_dir: Optional[Path] = typer.Option(
        None,
        "--history-dir",
        help="Chip history directory (default: from config)",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Preview mode: show what will be plotted without generating files",
    ),
    conductance: bool = typer.Option(
        False,
        "--conductance",
        "-c",
        help="Plot conductance G=I/V instead of current",
    ),
    absolute: bool = typer.Option(
        False,
        "--absolute",
        "-a",
        help="Plot absolute value |G| (only with --conductance)",
    ),
    theme: Optional[str] = typer.Option(
        None,
        "--theme",
        help="Plot theme override (prism_rain, paper, presentation, minimal)",
    ),
    format: Optional[str] = typer.Option(
        None,
        "--format",
        help="Output format override (png, pdf, svg, jpg)",
    ),
    dpi: Optional[int] = typer.Option(
        None,
        "--dpi",
        help="DPI override (72-1200)",
    ),
    photoresponse_x: str = typer.Option(
        "power",
        "--photoresponse-x",
        help="X-axis for photoresponse plot: power, wavelength, time, gate_voltage",
    ),
    axtype: Optional[str] = typer.Option(
        None,
        "--axtype",
        help="Axis scaling for photoresponse: loglog, semilogx, semilogy",
    ),
    filter_wavelength: Optional[float] = typer.Option(
        None,
        "--filter-wavelength",
        help="Filter photoresponse by wavelength (nm)",
    ),
    filter_vg: Optional[float] = typer.Option(
        None,
        "--filter-vg",
        help="Filter photoresponse by gate voltage (V)",
    ),
):
    """
    Generate ITS suite: overlay + sequential + photoresponse plots.

    Produces up to 3 plots in one command:
    1. ITS overlay - current vs time, multiple experiments overlaid
    2. ITS sequential - experiments concatenated on continuous time axis
    3. ITS photoresponse - delta current vs power/wavelength (only if light experiments exist)

    Examples:
        biotite plot-its-suite 67 --seq 4-7
        biotite plot-its-suite 67 --seq 4-7 --legend irradiated_power
        biotite plot-its-suite 67 --seq 4-7 --photoresponse-x wavelength
        biotite plot-its-suite 67 --auto --conductance
    """
    ctx = get_context()

    # Validate flag combinations
    if absolute and not conductance:
        ctx.print("[yellow]Warning:[/yellow] --absolute flag ignored (only valid with --conductance)")
        absolute = False

    # Get PlotConfig with command-specific overrides
    from src.cli.main import get_plot_config
    plot_config = get_plot_config()

    plot_overrides = {}
    if theme is not None:
        plot_overrides["theme"] = theme
    if format is not None:
        plot_overrides["format"] = format
    if dpi is not None:
        plot_overrides["dpi"] = dpi
    if plot_overrides:
        plot_config = plot_config.copy(**plot_overrides)

    ctx.print()
    ctx.print(Panel.fit(
        f"[bold cyan]ITS Suite Plot: {chip_group}{chip_number}[/bold cyan]",
        border_style="cyan",
    ))
    ctx.print()

    if output_dir is None:
        output_dir = ctx.output_dir

    # Auto-detect if we need enriched histories (for power legend)
    needs_enriched = legend_by.lower() in {"pow", "power", "irradiated_power", "led_power"}

    if history_dir is None:
        if needs_enriched:
            base_history_dir = Path(ctx.history_dir)
            data_dir = base_history_dir.parent.parent
            history_dir = data_dir / "03_derived" / "chip_histories_enriched"

            if not history_dir.exists():
                ctx.print(f"[red]Error:[/red] Enriched histories not found at {history_dir}")
                ctx.print("[yellow]The 'power' legend option requires enriched chip histories.[/yellow]")
                ctx.print("[cyan]Run:[/cyan] biotite full-pipeline && biotite derive-all-metrics")
                raise typer.Exit(1)

            ctx.print(f"[dim]Using enriched histories for power data: {history_dir}[/dim]")
        else:
            history_dir = ctx.history_dir

    # Step 1: Get seq numbers
    mode_count = sum([bool(seq), auto])
    if mode_count > 1:
        ctx.print("[red]Error:[/red] Can only use one of: --seq or --auto")
        raise typer.Exit(1)
    if mode_count == 0:
        ctx.print("[red]Error:[/red] Must specify one of: --seq or --auto")
        ctx.print("[yellow]Hint:[/yellow] Use --seq 4-7 or --auto")
        raise typer.Exit(1)

    try:
        if auto:
            ctx.print("[cyan]Auto-selecting ITS experiments...[/cyan]")
            filters = {}
            if vg is not None:
                filters["vg"] = vg
            if wavelength is not None:
                filters["wavelength"] = wavelength
            if date is not None:
                filters["date"] = date

            seq_numbers = auto_select_experiments(
                chip_number, "It", chip_group, history_dir, filters
            )
            ctx.print(f"[green]✓[/green] Auto-selected {len(seq_numbers)} ITS experiment(s)")
        else:
            seq_numbers = parse_seq_list(seq)
            ctx.print(f"[cyan]Using specified seq numbers:[/cyan] {seq_numbers}")
    except (ValueError, FileNotFoundError) as e:
        ctx.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 2: Validate seq numbers exist
    ctx.print("\n[cyan]Validating experiments...[/cyan]")
    valid, errors = validate_experiments_exist(
        seq_numbers, chip_number, chip_group, history_dir
    )
    if not valid:
        ctx.print("[red]Validation failed:[/red]")
        for error in errors:
            ctx.print(f"  • {error}")
        raise typer.Exit(1)
    ctx.print(f"[green]✓[/green] All seq numbers valid")

    # Step 3: Load history data
    ctx.print("\n[cyan]Loading experiment history...[/cyan]")
    try:
        history = load_history_for_plotting(
            seq_numbers, chip_number, chip_group, history_dir
        )
    except Exception as e:
        ctx.print(f"[red]Error loading history:[/red] {e}")
        raise typer.Exit(1)

    if history.height == 0:
        ctx.print("[red]Error:[/red] No experiments loaded")
        raise typer.Exit(1)

    # Use parquet_path if available
    if "parquet_path" in history.columns:
        history = history.drop("source_file") if "source_file" in history.columns else history
        history = history.rename({"parquet_path": "source_file"})
    elif "source_file" not in history.columns:
        ctx.print("[red]Error:[/red] History file missing both 'parquet_path' and 'source_file' columns")
        ctx.print("[yellow]Hint:[/yellow] Regenerate history files with: [cyan]build-all-histories[/cyan]")
        raise typer.Exit(1)

    # Step 4: Apply filters
    if vg is not None or wavelength is not None or date is not None:
        ctx.print("\n[cyan]Applying filters...[/cyan]")
        original_count = history.height
        history = apply_metadata_filters(history, vg=vg, wavelength=wavelength, date=date)
        if history.height == 0:
            ctx.print("[red]Error:[/red] No experiments remain after filtering")
            raise typer.Exit(1)
        ctx.print(f"[green]✓[/green] Filtered: {original_count} → {history.height} experiment(s)")

    # Filter for It procedures only
    df_its = history.filter(pl.col("proc") == "It") if "proc" in history.columns else history
    if df_its.height == 0:
        ctx.print("[red]Error:[/red] No It (ITS) experiments found in selection")
        raise typer.Exit(1)

    # Step 5: Apply preset configuration
    baseline_mode = "fixed"
    baseline_auto_divisor = 2.0
    plot_start_time = 20.0

    if preset:
        from src.plotting.its_presets import PRESETS
        if preset not in PRESETS:
            ctx.print(f"[red]Error:[/red] Unknown preset '{preset}'")
            ctx.print(f"[yellow]Available presets:[/yellow] {', '.join(PRESETS.keys())}")
            raise typer.Exit(1)

        preset_config = PRESETS[preset]
        ctx.print(f"\n[green]✓[/green] Using preset: [bold]{preset_config.name}[/bold]")
        baseline_mode = preset_config.baseline_mode
        baseline_auto_divisor = preset_config.baseline_auto_divisor
        plot_start_time = preset_config.plot_start_time

        if baseline_t is None:
            if baseline_mode == "fixed":
                baseline_t = preset_config.baseline_value
        else:
            baseline_mode = "fixed"

        if legend_by == "led_voltage":
            legend_by = preset_config.legend_by

    if baseline_t is None:
        baseline_t = 60.0

    # Step 6: Display info
    ctx.print()
    display_experiment_list(df_its, title="ITS Suite Experiments")

    ctx.print()
    plot_mode = "Conductance (G = I/V)" if conductance else "Current (ΔIds)"
    if conductance and absolute:
        plot_mode = "Absolute Conductance (|G| = |I/V|)"

    display_plot_settings({
        "Plot type": "ITS Suite (overlay + sequential + photoresponse)",
        "Y-axis": plot_mode,
        "Experiments": f"{df_its.height} measurement(s)",
        "Legend by": legend_by,
        "Baseline": f"Fixed at {baseline_t}s" if baseline_mode == "fixed" else baseline_mode,
        "Photoresponse X": photoresponse_x,
        "Output directory": str(output_dir),
    })

    # Step 7: Setup output
    output_dir = setup_output_dir(chip_number, chip_group, output_dir)
    plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

    # Exit in preview mode
    if preview:
        ctx.print()
        ctx.print("[bold green]✓ Preview complete - no files generated[/bold green]")
        ctx.print("[dim]  Run without --preview to generate plot[/dim]")
        raise typer.Exit(0)

    # Step 8: Generate plots
    base_dir = Path(".")
    if output_dir != ctx.output_dir:
        plot_config = plot_config.copy(output_dir=output_dir)

    chip_name = f"{chip_group}{chip_number}"
    plots_generated = 0

    # 1. ITS overlay
    ctx.print("\n[cyan]Generating ITS overlay plot...[/cyan]")
    try:
        its.plot_its_overlay(
            df_its,
            base_dir,
            plot_tag,
            baseline_t=baseline_t,
            baseline_mode=baseline_mode,
            baseline_auto_divisor=baseline_auto_divisor,
            plot_start_time=plot_start_time,
            legend_by=legend_by,
            padding=padding,
            conductance=conductance,
            absolute=absolute,
            config=plot_config,
        )
        plots_generated += 1
        ctx.print(f"[green]✓[/green] ITS overlay plot generated")
    except Exception as e:
        ctx.print(f"[red]Error generating overlay plot:[/red] {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # 2. ITS sequential
    ctx.print("\n[cyan]Generating ITS sequential plot...[/cyan]")
    try:
        its.plot_its_sequential(
            df_its,
            base_dir,
            f"{plot_tag}_seq",
            legend_by=legend_by,
            config=plot_config,
        )
        plots_generated += 1
        ctx.print(f"[green]✓[/green] ITS sequential plot generated")
    except Exception as e:
        ctx.print(f"[red]Error generating sequential plot:[/red] {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # 3. ITS photoresponse (only if light experiments exist)
    df_its_light = df_its.filter(pl.col("has_light") == True) if "has_light" in df_its.columns else df_its
    if df_its_light.height > 0:
        ctx.print("\n[cyan]Generating ITS photoresponse plot...[/cyan]")
        try:
            its_photoresponse.plot_its_photoresponse(
                df_its_light,
                chip_name,
                photoresponse_x,
                filter_wavelength=filter_wavelength,
                filter_vg=filter_vg,
                filter_power_range=None,
                plot_tag=f"{plot_tag}_photoresponse",
                axtype=axtype,
                config=plot_config,
            )
            plots_generated += 1
            ctx.print(f"[green]✓[/green] ITS photoresponse plot generated")
        except Exception as e:
            ctx.print(f"[yellow]Warning:[/yellow] Photoresponse plot skipped: {e}")
    else:
        ctx.print("\n[dim]Skipping photoresponse plot (no light experiments found)[/dim]")

    # Done
    ctx.print()
    ctx.print(Panel.fit(
        f"[bold green]ITS Suite complete: {plots_generated} plot(s) generated[/bold green]",
        border_style="green",
    ))
    ctx.print()
