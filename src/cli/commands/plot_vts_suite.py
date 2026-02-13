"""Vt suite plotting command: plot-vts-suite.

Generates 3 plots in one call: overlay, sequential, and photoresponse.
"""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional
from rich.panel import Panel

from src.plotting import vt, photoresponse
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
    name="plot-vts-suite",
    group="plotting",
    description="Generate Vt suite: overlay + sequential + photoresponse",
)
def plot_vts_suite_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 81 for Alisson81)",
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '239-240' or '10,11,12'). Required unless --auto is used.",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all Vt experiments",
    ),
    legend_by: str = typer.Option(
        "wavelength",
        "--legend",
        "-l",
        help="Legend grouping: 'wavelength' (default), 'vg', 'led_voltage', 'irradiated_power', 'datetime'",
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
    padding: Optional[float] = typer.Option(
        None,
        "--padding",
        help="Y-axis padding (fraction of data range, e.g., 0.02 = 2%)",
    ),
    baseline_t: float = typer.Option(
        60.0,
        "--baseline",
        help="Baseline time in seconds (default: 60.0)",
    ),
    baseline_mode: str = typer.Option(
        "fixed",
        "--baseline-mode",
        help="Baseline mode: 'fixed', 'auto', or 'none' (default: fixed)",
    ),
    plot_start_time: Optional[float] = typer.Option(
        None,
        "--plot-start",
        help="Start time for x-axis in seconds",
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
    resistance: bool = typer.Option(
        False,
        "--resistance",
        "-r",
        help="Plot resistance R=V/I instead of voltage",
    ),
    absolute: bool = typer.Option(
        False,
        "--absolute",
        "-a",
        help="Plot absolute value |R| (only with --resistance)",
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
    filter_power_range: Optional[str] = typer.Option(
        None,
        "--filter-power-range",
        help="Filter photoresponse by power range: 'min,max' (e.g., '0.1,10.0')",
    ),
):
    """
    Generate Vt suite: overlay + sequential + photoresponse plots.

    Produces up to 3 plots in one command:
    1. Vt overlay - voltage vs time, multiple experiments overlaid
    2. Vt sequential - experiments concatenated on continuous time axis
    3. Vt photoresponse - delta voltage vs power/wavelength (wrapped in try/except)

    Examples:
        biotite plot-vts-suite 81 --seq 239-240
        biotite plot-vts-suite 81 --seq 239-240 --legend vg
        biotite plot-vts-suite 81 --auto --resistance
        biotite plot-vts-suite 81 --seq 10-15 --photoresponse-x wavelength
    """
    ctx = get_context()

    # Validate flag combinations
    if absolute and not resistance:
        ctx.print("[yellow]Warning:[/yellow] --absolute flag ignored (only valid with --resistance)")
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
        f"[bold cyan]Vt Suite Plot: {chip_group}{chip_number}[/bold cyan]",
        border_style="cyan",
    ))
    ctx.print()

    if output_dir is None:
        output_dir = ctx.output_dir

    # Auto-detect if we need enriched histories
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
        ctx.print("[yellow]Hint:[/yellow] Use --seq 239-240 or --auto")
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
                chip_number, "Vt", chip_group, history_dir, filters
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

    # Filter for Vt procedures only
    df_vt = history.filter(pl.col("proc") == "Vt") if "proc" in history.columns else history
    if df_vt.height == 0:
        ctx.print("[red]Error:[/red] No Vt experiments found in selection")
        raise typer.Exit(1)

    # Step 5: Display info
    ctx.print()
    display_experiment_list(df_vt, title="Vt Suite Experiments")

    ctx.print()
    plot_mode = "Resistance (R = V/I)" if resistance else "Voltage (ΔVds)"
    if resistance and absolute:
        plot_mode = "Absolute Resistance (|R| = |V/I|)"

    display_plot_settings({
        "Plot type": "Vt Suite (overlay + sequential + photoresponse)",
        "Y-axis": plot_mode,
        "Experiments": f"{df_vt.height} measurement(s)",
        "Baseline mode": baseline_mode,
        "Baseline time": f"{baseline_t}s" if baseline_mode == "fixed" else baseline_mode,
        "Legend by": legend_by,
        "Photoresponse X": photoresponse_x,
        "Output directory": str(output_dir),
    })

    # Step 6: Setup output
    output_dir = setup_output_dir(chip_number, chip_group, output_dir)
    plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

    # Exit in preview mode
    if preview:
        ctx.print()
        ctx.print("[bold green]✓ Preview complete - no files generated[/bold green]")
        ctx.print("[dim]  Run without --preview to generate plot[/dim]")
        raise typer.Exit(0)

    # Step 7: Generate plots
    base_dir = Path(".")
    plot_overrides_output = {}
    if output_dir != ctx.output_dir:
        plot_overrides_output["output_dir"] = output_dir
    if plot_overrides_output:
        plot_config = plot_config.copy(**plot_overrides_output)

    chip_name = f"{chip_group}{chip_number}"
    plots_generated = 0

    # Parse power range if provided
    parsed_power_range = None
    if filter_power_range:
        try:
            parts = filter_power_range.split(",")
            parsed_power_range = (float(parts[0]), float(parts[1]))
        except (ValueError, IndexError):
            ctx.print(f"[red]Error:[/red] Invalid --filter-power-range format. Use 'min,max' (e.g., '0.1,10.0')")
            raise typer.Exit(1)

    # 1. Vt overlay
    ctx.print("\n[cyan]Generating Vt overlay plot...[/cyan]")
    try:
        vt.plot_vt_overlay(
            df_vt,
            base_dir,
            plot_tag,
            baseline_t=baseline_t,
            baseline_mode=baseline_mode,
            plot_start_time=plot_start_time,
            legend_by=legend_by,
            padding=padding,
            resistance=resistance,
            absolute=absolute,
            config=plot_config,
        )
        plots_generated += 1
        ctx.print(f"[green]✓[/green] Vt overlay plot generated")
    except Exception as e:
        ctx.print(f"[red]Error generating overlay plot:[/red] {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # 2. Vt sequential
    ctx.print("\n[cyan]Generating Vt sequential plot...[/cyan]")
    try:
        vt.plot_vt_sequential(
            df_vt,
            base_dir,
            f"{plot_tag}_seq",
            plot_start_time=plot_start_time,
            legend_by=legend_by,
            padding=padding,
            resistance=resistance,
            absolute=absolute,
            config=plot_config,
        )
        plots_generated += 1
        ctx.print(f"[green]✓[/green] Vt sequential plot generated")
    except Exception as e:
        ctx.print(f"[red]Error generating sequential plot:[/red] {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # 3. Vt photoresponse (delta voltage)
    ctx.print("\n[cyan]Generating Vt photoresponse plot...[/cyan]")
    try:
        photoresponse.plot_photoresponse(
            df_vt,
            chip_name,
            x_variable=photoresponse_x,
            y_metric="delta_voltage",
            procedures=["Vt"],
            filter_wavelength=filter_wavelength,
            filter_vg=filter_vg,
            filter_power_range=parsed_power_range,
            plot_tag=f"{plot_tag}_photoresponse",
            output_procedure="Vt",
            output_metadata={"has_light": True},
            filename_prefix=f"{chip_name.lower()}_Vt_photoresponse",
            config=plot_config,
        )
        plots_generated += 1
        ctx.print(f"[green]✓[/green] Vt photoresponse plot generated")
    except Exception as e:
        ctx.print(f"[yellow]Warning:[/yellow] Photoresponse plot skipped: {e}")

    # Done
    ctx.print()
    ctx.print(Panel.fit(
        f"[bold green]Vt Suite complete: {plots_generated} plot(s) generated[/bold green]",
        border_style="green",
    ))
    ctx.print()
