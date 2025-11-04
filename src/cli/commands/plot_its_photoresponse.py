"""ITS photoresponse plotting command: plot-its-photoresponse."""

import typer
from src.cli.plugin_system import cli_command
from pathlib import Path
from typing import Optional, Literal
from rich.console import Console
from src.cli.context import get_context
from rich.panel import Panel
import polars as pl

from src.plotting import its_photoresponse
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
    name="plot-its-photoresponse",
    group="plotting",
    description="Plot ITS photoresponse (Δcurrent) vs power/wavelength/time/gate"
)
def plot_its_photoresponse_command(
    chip_number: int = typer.Argument(
        ...,
        help="Chip number (e.g., 67 for Alisson67)"
    ),
    x_axis: Literal["power", "wavelength", "time", "gate_voltage"] = typer.Argument(
        ...,
        help="X-axis variable: power, wavelength, time, or gate_voltage"
    ),
    seq: Optional[str] = typer.Option(
        None,
        "--seq",
        "-s",
        help="Seq numbers: comma-separated or ranges (e.g., '4-7' or '4,5,6,7'). Required unless --auto is used."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Automatically select all ITS light experiments"
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
    filter_wavelength: Optional[float] = typer.Option(
        None,
        "--filter-wavelength",
        "--wl",
        help="Filter to specific wavelength (nm). Example: --wl 405"
    ),
    filter_vg: Optional[float] = typer.Option(
        None,
        "--filter-vg",
        "--vg",
        help="Filter to specific gate voltage (V). Example: --vg -0.4"
    ),
    filter_power_min: Optional[float] = typer.Option(
        None,
        "--filter-power-min",
        help="Minimum irradiated power (W) for filtering"
    ),
    filter_power_max: Optional[float] = typer.Option(
        None,
        "--filter-power-max",
        help="Maximum irradiated power (W) for filtering"
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
    Plot ITS photoresponse: delta current vs power/wavelength/time/gate voltage.

    Extracts photoresponse (Δcurrent) from ITS measurements and plots against
    the specified independent variable. Perfect for analyzing how photoresponse
    changes with experimental conditions.

    Uses enriched history if available (fast!), otherwise extracts delta_current
    on-the-fly from ITS measurements.

    Examples:
        # Delta current vs irradiated power (seq 4-7)
        python process_and_analyze.py plot-its-photoresponse 67 power --seq 4-7

        # Delta current vs wavelength (auto-select all ITS)
        python process_and_analyze.py plot-its-photoresponse 67 wavelength --auto

        # Delta current vs time (chronological)
        python process_and_analyze.py plot-its-photoresponse 67 time --seq 4-7

        # Filter to specific wavelength
        python process_and_analyze.py plot-its-photoresponse 67 power --seq 4-10 --wl 405

        # Publication quality
        python process_and_analyze.py plot-its-photoresponse 67 power --seq 4-7 \\
            --theme paper --dpi 600 --format pdf
    """
    ctx = get_context()
    ctx.print()
    ctx.print(Panel.fit(
        f"[bold green]ITS Photoresponse: {chip_group}{chip_number}[/bold green]\n"
        f"[cyan]X-axis: {x_axis}[/cyan]",
        border_style="green"
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

    # Step 1: Get seq numbers (manual or auto)
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
            ctx.print("[cyan]Auto-selecting It light experiments...[/cyan]")
            filters = {"has_light": True}  # Only light experiments for photoresponse

            if filter_wavelength is not None:
                filters["wavelength"] = filter_wavelength
            if filter_vg is not None:
                filters["vg"] = filter_vg

            seq_numbers = auto_select_experiments(
                chip_number,
                "It",  # Procedure name is "It" in manifest, not "ITS"
                chip_group,
                history_dir,
                filters
            )
            ctx.print(f"[green]✓[/green] Auto-selected {len(seq_numbers)} It light experiment(s)")
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

    # Dry-run mode: exit after validation
    if dry_run:
        output_dir_calc = setup_output_dir(chip_number, chip_group, output_dir)
        plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

        # Build filename following ITS naming convention
        # Pattern: encap{chip_number}_ITS_photoresponse_vs_{x_variable}[_filters]_{plot_tag}.png
        filename_parts = [f"encap{chip_number}", "ITS_photoresponse", "vs", x_axis]
        if filter_wavelength is not None:
            filename_parts.append(f"wl{filter_wavelength:.0f}nm")
        if filter_vg is not None:
            filename_parts.append(f"vg{filter_vg:.2f}V".replace(".", "p"))
        filename_parts.append(plot_tag)

        output_file = output_dir_calc / ("_".join(filename_parts) + ".png")

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
        raise typer.Exit(0)

    # Step 3: Load history data (prefer enriched if available)
    ctx.print("\n[cyan]Loading experiment history...[/cyan]")

    # Try enriched history first (has irradiated_power_w from calibrations)
    from pathlib import Path
    enriched_dir = Path("data/03_derived/chip_histories_enriched")
    chip_name = f"{chip_group}{chip_number}"
    enriched_file = enriched_dir / f"{chip_name}_history.parquet"

    try:
        from src.cli.helpers import load_history_for_plotting

        if enriched_file.exists():
            if ctx.verbose:
                ctx.print(f"[dim]Loading enriched history from: {enriched_file}[/dim]")
            history = load_history_for_plotting(
                seq_numbers,
                chip_number,
                chip_group,
                enriched_dir
            )
            ctx.print("[green]✓[/green] Using enriched history (with calibrated power)")
        else:
            if ctx.verbose:
                ctx.print(f"[dim]Enriched history not found, using standard history[/dim]")
            history = load_history_for_plotting(
                seq_numbers,
                chip_number,
                chip_group,
                history_dir
            )
            ctx.print("[yellow]Note:[/yellow] Using standard history (run [cyan]derive-all-metrics --calibrations[/cyan] for calibrated power)")
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

    # Step 4: Verify all are It experiments
    if "proc" in history.columns:
        non_its = history.filter(pl.col("proc") != "It")
        if non_its.height > 0:
            ctx.print(f"[yellow]Warning:[/yellow] {non_its.height} non-It experiment(s) found and will be skipped")
            ctx.print("[dim]Only It experiments will be plotted[/dim]")

    # Filter to It experiments (current vs time measurements)
    # Note: Procedure name is "It" in manifest, not "ITS"
    its_history = history.filter(pl.col("proc") == "It")

    if its_history.height == 0:
        ctx.print("[red]Error:[/red] No It experiments found in selected seq numbers")
        ctx.print("[yellow]Hint:[/yellow] This command plots photoresponse from It (current-time) measurements")
        ctx.print("[yellow]Hint:[/yellow] Check your history with: [cyan]show-history {chip_number} --proc It[/cyan]")
        raise typer.Exit(1)

    # Step 5: Display selected experiments
    ctx.print()
    display_experiment_list(its_history, title="It Experiments for Photoresponse Analysis")

    # Step 6: Display plot settings
    settings = {
        "Plot type": f"ITS Photoresponse (Δcurrent vs {x_axis})",
        "Measurements": f"{its_history.height} ITS experiment(s)",
        "Output directory": str(output_dir)
    }

    if filter_wavelength is not None:
        settings["Filter wavelength"] = f"{filter_wavelength:.0f} nm"
    if filter_vg is not None:
        settings["Filter Vg"] = f"{filter_vg:.2f} V"
    if filter_power_min is not None or filter_power_max is not None:
        power_range = f"[{filter_power_min or '∞'}, {filter_power_max or '∞'}] W"
        settings["Filter power range"] = power_range

    ctx.print()
    display_plot_settings(settings)

    # Exit in preview mode
    if preview:
        ctx.print()
        ctx.print("[bold green]✓ Preview complete - no files generated[/bold green]")
        ctx.print("[dim]  Run without --preview to generate plot[/dim]")
        raise typer.Exit(0)

    # Step 7: Get plot config and apply overrides
    from src.cli.main import get_plot_config
    plot_config = get_plot_config()

    plot_overrides = {}
    if theme is not None:
        plot_overrides["theme"] = theme
    if format is not None:
        plot_overrides["format"] = format
    if dpi is not None:
        plot_overrides["dpi"] = dpi
    if output_dir is not None:
        plot_overrides["output_dir"] = output_dir

    if plot_overrides:
        plot_config = plot_config.copy(**plot_overrides)
        if ctx.verbose:
            overrides_str = ", ".join([f"{k}={v}" for k, v in plot_overrides.items()])
            ctx.print(f"[dim]Plot config overrides: {overrides_str}[/dim]")

    # Step 8: Generate plot tag and call plotting function
    plot_tag = generate_plot_tag(seq_numbers, custom_tag=tag)

    ctx.print("\n[cyan]Generating photoresponse plot...[/cyan]")

    # Build filter_power_range tuple
    filter_power_range = None
    if filter_power_min is not None or filter_power_max is not None:
        filter_power_range = (
            filter_power_min or 0.0,
            filter_power_max or float('inf')
        )

    chip_name = f"{chip_group}{chip_number}"

    try:
        output_file = its_photoresponse.plot_its_photoresponse(
            its_history,
            chip_name,
            x_axis,
            filter_wavelength=filter_wavelength,
            filter_vg=filter_vg,
            filter_power_range=filter_power_range,
            plot_tag=plot_tag,
            config=plot_config
        )
    except Exception as e:
        ctx.print(f"[red]Error generating plot:[/red] {e}")
        import traceback
        ctx.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)

    # Step 9: Display success
    ctx.print()
    display_plot_success(output_file)
    ctx.print()
