"""CLI command for exporting chip histories to LaTeX tables with color-coded procedures."""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import polars as pl
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.plugin_system import cli_command
from src.cli.context import get_context

console = Console()

# ============================================
# COLOR SCHEME FOR PROCEDURES
# ============================================
PROCEDURE_COLORS = {
    "IVg": {"rgb": (200, 230, 255), "name": "lightblue"},      # Light blue
    "It": {"rgb": (255, 240, 200), "name": "lightorange"},     # Light orange
    "IVgT": {"rgb": (230, 255, 230), "name": "lightgreen"},    # Light green
    "LaserCalibration": {"rgb": (255, 230, 255), "name": "lightpurple"},  # Light purple
    "IV": {"rgb": (255, 255, 200), "name": "lightyellow"},     # Light yellow
    "Vt": {"rgb": (255, 220, 220), "name": "lightred"},        # Light red
    "VVg": {"rgb": (220, 255, 255), "name": "lightcyan"},      # Light cyan
    "Tt": {"rgb": (240, 240, 240), "name": "lightgray"},       # Light gray
}

# Default color for unknown procedures
DEFAULT_COLOR = {"rgb": (245, 245, 245), "name": "defaultgray"}


def generate_latex_preamble() -> str:
    """Generate LaTeX preamble with packages and color definitions."""
    preamble = r"""\documentclass[10pt,letterpaper,landscape]{article}

% ============================================
% PACKAGES
% ============================================
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[margin=1.5cm]{geometry}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{xcolor}
\usepackage{colortbl}
\usepackage{array}

% ============================================
% COLOR DEFINITIONS
% ============================================
\definecolor{headerblue}{RGB}{41, 98, 155}
"""

    # Add procedure colors
    for proc, color_info in PROCEDURE_COLORS.items():
        r, g, b = color_info["rgb"]
        preamble += f"\\definecolor{{{color_info['name']}}}{{RGB}}{{{r}, {g}, {b}}}\n"

    # Add default color
    r, g, b = DEFAULT_COLOR["rgb"]
    preamble += f"\\definecolor{{{DEFAULT_COLOR['name']}}}{{RGB}}{{{r}, {g}, {b}}}\n"

    preamble += r"""
\pagestyle{plain}

"""
    return preamble


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters."""
    if not isinstance(text, str):
        text = str(text)

    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '\\': r'\textbackslash{}',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def format_value(value, column_name: str) -> str:
    """Format value for LaTeX table based on column type."""
    if value is None or (isinstance(value, float) and not (value == value)):  # NaN check
        return "--"

    # Convert delta_current from A to μA (multiply by 1e6)
    if column_name == "delta_current":
        if isinstance(value, (int, float)):
            value_ua = value * 1e6  # Convert A to μA
            # Scientific notation for very large or very small values
            if abs(value_ua) >= 1000 or (abs(value_ua) < 0.01 and value_ua != 0):
                return f"{value_ua:.2e}"
            else:
                return f"{value_ua:.3f}"

    # Convert delta_voltage from V to mV (multiply by 1e3)
    if column_name == "delta_voltage":
        if isinstance(value, (int, float)):
            value_mv = value * 1e3  # Convert V to mV
            # Scientific notation for very large or very small values
            if abs(value_mv) >= 1000 or (abs(value_mv) < 0.01 and value_mv != 0):
                return f"{value_mv:.2e}"
            else:
                return f"{value_mv:.3f}"

    # CNP voltage and power in original units
    if column_name in ["cnp_voltage", "irradiated_power_w"]:
        if isinstance(value, (int, float)):
            # Scientific notation for very small values
            if abs(value) < 0.001 and value != 0:
                return f"{value:.2e}"
            else:
                return f"{value:.3f}"

    if column_name in ["wavelength_nm"]:
        if isinstance(value, (int, float)):
            return f"{int(value)}"

    if column_name in ["vg_fixed_v", "vds_v", "laser_voltage_v"]:
        if isinstance(value, (int, float)):
            return f"{value:.2f}"

    if column_name == "has_light":
        return "Yes" if value else "No"

    return escape_latex(str(value))


def get_procedure_color(proc: str) -> str:
    """Get LaTeX color name for a procedure."""
    if proc in PROCEDURE_COLORS:
        return PROCEDURE_COLORS[proc]["name"]
    return DEFAULT_COLOR["name"]


def generate_latex_table(history: pl.DataFrame, chip_name: str) -> str:
    """Generate LaTeX longtable from chip history."""

    # Start document
    latex = generate_latex_preamble()
    latex += r"\begin{document}" + "\n\n"

    # Title section
    latex += r"\begin{center}" + "\n"
    latex += f"{{\\Large\\bfseries Device: {escape_latex(chip_name)}}}\\\\[0.5cm]\n"
    latex += r"\end{center}" + "\n\n"

    # Begin longtable (11 columns now: added ΔV)
    latex += r"""\begin{longtable}{
    >{\centering\arraybackslash}p{0.8cm}
    >{\centering\arraybackslash}p{2.0cm}
    >{\centering\arraybackslash}p{1.6cm}
    >{\centering\arraybackslash}p{1.0cm}
    >{\centering\arraybackslash}p{1.0cm}
    >{\centering\arraybackslash}p{1.3cm}
    >{\centering\arraybackslash}p{1.2cm}
    >{\centering\arraybackslash}p{1.2cm}
    >{\centering\arraybackslash}p{1.8cm}
    >{\centering\arraybackslash}p{1.8cm}
    >{\centering\arraybackslash}p{1.8cm}
}
"""

    # Table header (first page)
    latex += r"""\toprule
\rowcolor{headerblue}
\textcolor{white}{\textbf{Seq}} &
\textcolor{white}{\textbf{Datetime}} &
\textcolor{white}{\textbf{Time}} &
\textcolor{white}{\textbf{Proc}} &
\textcolor{white}{\textbf{Light}} &
\textcolor{white}{\textbf{$\lambda$ [nm]}} &
\textcolor{white}{\textbf{$V_g$ [V]}} &
\textcolor{white}{\textbf{$V_{laser}$ [V]}} &
\textcolor{white}{\textbf{CNP [V]}} &
\textcolor{white}{\textbf{$\Delta I$ [$\mu$A]}} &
\textcolor{white}{\textbf{$\Delta V$ [mV]}} \\
\midrule
\endfirsthead

"""

    # Header for continuation pages
    latex += r"""\multicolumn{11}{c}{\textit{Continued from previous page}} \\
\toprule
\rowcolor{headerblue}
\textcolor{white}{\textbf{Seq}} &
\textcolor{white}{\textbf{Datetime}} &
\textcolor{white}{\textbf{Time}} &
\textcolor{white}{\textbf{Proc}} &
\textcolor{white}{\textbf{Light}} &
\textcolor{white}{\textbf{$\lambda$ [nm]}} &
\textcolor{white}{\textbf{$V_g$ [V]}} &
\textcolor{white}{\textbf{$V_{laser}$ [V]}} &
\textcolor{white}{\textbf{CNP [V]}} &
\textcolor{white}{\textbf{$\Delta I$ [$\mu$A]}} &
\textcolor{white}{\textbf{$\Delta V$ [mV]}} \\
\midrule
\endhead

"""

    # Footer
    latex += r"""\midrule
\multicolumn{11}{r}{\textit{Continued on next page}} \\
\endfoot

\bottomrule
\endlastfoot

"""

    # Data rows with procedure-based coloring
    latex += "% ============================================\n"
    latex += "% DATA ROWS (Color-coded by procedure)\n"
    latex += "% ============================================\n"

    for row in history.iter_rows(named=True):
        # Get procedure and color
        proc = row.get("proc", "Unknown")
        color_name = get_procedure_color(proc)

        # Extract values
        seq = row.get("seq", "?")
        date = row.get("date", "")
        time = row.get("time_hms", "")
        light = row.get("has_light", None)
        wavelength = row.get("wavelength_nm", None)
        vg = row.get("vg_fixed_v", None)
        laser_v = row.get("laser_voltage_v", None)
        cnp = row.get("cnp_voltage", None)
        delta_i = row.get("delta_current", None)
        delta_v = row.get("delta_voltage", None)

        # Format row with procedure color
        latex += f"\\rowcolor{{{color_name}}}\n"
        latex += f"{seq} & "
        latex += f"{format_value(date, 'date')} & "
        latex += f"{format_value(time, 'time')} & "
        latex += f"{escape_latex(proc)} & "
        latex += f"{format_value(light, 'has_light')} & "
        latex += f"{format_value(wavelength, 'wavelength_nm')} & "
        latex += f"{format_value(vg, 'vg_fixed_v')} & "
        latex += f"{format_value(laser_v, 'laser_voltage_v')} & "
        latex += f"{format_value(cnp, 'cnp_voltage')} & "
        latex += f"{format_value(delta_i, 'delta_current')} & "
        latex += f"{format_value(delta_v, 'delta_voltage')} \\\\\n"

    # End table
    latex += "\n\\end{longtable}\n\n"

    # Add legend explaining colors
    latex += r"""\vspace{0.5cm}

\noindent\textbf{Color Legend (Procedure Types):}\\[0.2cm]
"""

    latex += r"\begin{tabular}{ll}" + "\n"
    for proc, color_info in sorted(PROCEDURE_COLORS.items()):
        latex += f"\\colorbox{{{color_info['name']}}}{{\\phantom{{XX}}}} & {escape_latex(proc)} \\\\\n"
    latex += r"\end{tabular}" + "\n\n"

    # End document
    latex += r"\end{document}" + "\n"

    return latex


@cli_command(
    name="export-latex",
    group="history",
    description="Export chip history to LaTeX table with color-coded procedures"
)
def export_latex_command(
    chip_number: int = typer.Argument(..., help="Chip number (e.g., 67 for Alisson67)"),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Custom output directory (default: data/04_exports/latex/)"
    ),
    chip_group: str = typer.Option("Alisson", "--group", "-g", help="Chip group name prefix"),
    proc_filter: Optional[str] = typer.Option(
        None,
        "--proc",
        "-p",
        help="Filter by procedure type (IVg, It, IV, etc.)"
    ),
    light_filter: Optional[str] = typer.Option(
        None,
        "--light",
        "-l",
        help="Filter by light status: 'light', 'dark', 'unknown'"
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        "-n",
        help="Export only last N experiments"
    ),
    timestamp: bool = typer.Option(
        True,
        "--timestamp/--no-timestamp",
        help="Add timestamp to filename"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing file"),
):
    """
    Export chip history to LaTeX table with color-coded procedures.

    Generates a professional LaTeX document with:
    - Color-coded rows by procedure type (IVg=blue, It=orange, etc.)
    - Multi-page support (longtable)
    - Formatted columns with units
    - Automatic legend

    The output .tex file can be compiled with pdflatex.

    Directory structure:
        data/04_exports/latex/{ChipGroup}{ChipNumber}/
            - Alisson67_table_YYYYMMDD_HHMMSS.tex
            - Alisson67_metrics_YYYYMMDD_HHMMSS.tex
            - etc.

    Examples
    --------
    # Export full history to LaTeX
    $ python process_and_analyze.py export-latex 67

    # Export filtered data (only IVg)
    $ python process_and_analyze.py export-latex 67 --proc IVg

    # Export without timestamp
    $ python process_and_analyze.py export-latex 67 --no-timestamp

    # Compile the generated LaTeX file
    $ cd data/04_exports/latex/Alisson67/
    $ pdflatex Alisson67_table.tex
    """
    ctx = get_context()

    # Determine output directory
    if output_dir is None:
        output_dir = Path("data/04_exports/latex") / f"{chip_group}{chip_number}"
    else:
        output_dir = Path(output_dir)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load chip history (try enriched first)
    chip_name = f"{chip_group}{chip_number}"
    enriched_dir = Path("data/03_derived/chip_histories_enriched")
    enriched_file = enriched_dir / f"{chip_name}_history.parquet"
    metrics_file = Path("data/03_derived/_metrics/metrics.parquet")

    if enriched_file.exists():
        console.print(f"[green]✓[/green] Loading enriched history from: {enriched_file}")
        history = pl.read_parquet(enriched_file)
        history_type = "enriched"

        # Join with metrics for CNP, delta_current, delta_voltage
        if metrics_file.exists():
            metrics = pl.read_parquet(metrics_file)

            # Filter metrics for this chip
            chip_metrics = metrics.filter(
                (pl.col("chip_number") == chip_number) &
                (pl.col("chip_group") == chip_group)
            )

            # Join CNP voltage
            cnp_metrics = chip_metrics.filter(pl.col("metric_name") == "cnp_voltage")
            if cnp_metrics.height > 0:
                cnp_df = cnp_metrics.select([
                    "run_id",
                    pl.col("value_float").alias("cnp_voltage")
                ])
                history = history.join(cnp_df, on="run_id", how="left")

            # Join delta current (photoresponse)
            delta_i_metrics = chip_metrics.filter(pl.col("metric_name") == "delta_current")
            if delta_i_metrics.height > 0:
                delta_i_df = delta_i_metrics.select([
                    "run_id",
                    pl.col("value_float").alias("delta_current")
                ])
                history = history.join(delta_i_df, on="run_id", how="left")

            # Join delta voltage (photoresponse)
            delta_v_metrics = chip_metrics.filter(pl.col("metric_name") == "delta_voltage")
            if delta_v_metrics.height > 0:
                delta_v_df = delta_v_metrics.select([
                    "run_id",
                    pl.col("value_float").alias("delta_voltage")
                ])
                history = history.join(delta_v_df, on="run_id", how="left")

            console.print(f"[dim]   → Joined derived metrics (CNP, ΔI, ΔV)[/dim]")
        else:
            console.print(f"[yellow]⚠[/yellow]  Metrics file not found, skipping derived metrics")
    else:
        # Fall back to standard history
        history_dir = ctx.history_dir
        history_file = history_dir / f"{chip_name}_history.parquet"

        if not history_file.exists():
            console.print(
                f"[red]Error:[/red] Chip history file not found: {history_file}\n"
                f"Run 'build-all-histories' command first to generate history files."
            )
            raise typer.Exit(1)

        console.print(f"[yellow]⚠[/yellow]  Loading standard history (enriched not found)")
        console.print(f"[dim]   → To get enriched data with metrics, run: enrich-history {chip_number}[/dim]")
        history = pl.read_parquet(history_file)
        history_type = "standard"

    console.print(f"[dim]   Loaded {history.height} experiments[/dim]\n")

    # Apply filters
    original_count = history.height

    if proc_filter:
        history = history.filter(pl.col("proc") == proc_filter)
        console.print(f"[dim]   Filtered to procedure '{proc_filter}': {history.height} experiments[/dim]")

    if light_filter:
        if light_filter.lower() == "light":
            history = history.filter(pl.col("has_light") == True)
        elif light_filter.lower() == "dark":
            history = history.filter(pl.col("has_light") == False)
        elif light_filter.lower() == "unknown":
            history = history.filter(pl.col("has_light").is_null())
        console.print(f"[dim]   Filtered to light='{light_filter}': {history.height} experiments[/dim]")

    if limit:
        history = history.tail(limit)
        console.print(f"[dim]   Limited to last {limit} experiments[/dim]")

    if history.height == 0:
        console.print(f"[yellow]Warning:[/yellow] No experiments match the filters. Nothing to export.")
        raise typer.Exit(0)

    # Build filename
    filename_parts = [chip_name, "table"]

    if proc_filter:
        filename_parts.append(proc_filter.lower())

    if light_filter:
        filename_parts.append(light_filter.lower())

    if timestamp:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_parts.append(ts)

    filename = "_".join(filename_parts) + ".tex"
    output_file = output_dir / filename

    # Check if file exists
    if output_file.exists() and not overwrite:
        console.print(f"[yellow]Warning:[/yellow] File already exists: {output_file}")
        console.print(f"[dim]   Use --overwrite to replace, or --timestamp to create new file[/dim]")
        raise typer.Exit(1)

    # Generate LaTeX
    console.print(f"\n[cyan]Generating LaTeX table...[/cyan]")

    try:
        latex_content = generate_latex_table(history, chip_name)

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(latex_content)

        # Success!
        file_size = output_file.stat().st_size
        size_kb = file_size / 1024

        console.print(f"\n[green]✓ LaTeX export successful![/green]\n")

        # Display summary
        summary_panel = Panel(
            f"[bold]File:[/bold] {output_file}\n"
            f"[bold]Size:[/bold] {size_kb:.2f} KB ({file_size:,} bytes)\n"
            f"[bold]History Type:[/bold] {history_type}\n"
            f"[bold]Experiments:[/bold] {history.height} / {original_count}\n"
            f"[bold]Procedure Colors:[/bold] {len(PROCEDURE_COLORS)} defined",
            title="Export Summary",
            border_style="green"
        )
        console.print(summary_panel)

        # Show compilation instructions
        console.print(f"\n[dim]To compile to PDF:[/dim]")
        console.print(f"[dim]  cd {output_dir}[/dim]")
        console.print(f"[dim]  pdflatex {filename}[/dim]")
        console.print(f"\n[dim]Or open in Overleaf/TeXShop/TeXstudio[/dim]")

    except Exception as e:
        console.print(f"\n[red]Error during LaTeX generation:[/red] {str(e)}")
        raise typer.Exit(1)


@cli_command(
    name="export-all-latex",
    group="history",
    description="Export LaTeX tables for all chips"
)
def export_all_latex_command(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Custom output directory"
    ),
    chip_group: str = typer.Option("Alisson", "--group", "-g", help="Chip group name prefix"),
    timestamp: bool = typer.Option(
        True,
        "--timestamp/--no-timestamp",
        help="Add timestamp to filenames"
    ),
):
    """
    Export LaTeX tables for all available chips.

    Examples
    --------
    # Export all chips to LaTeX
    $ python process_and_analyze.py export-all-latex

    # Export without timestamps
    $ python process_and_analyze.py export-all-latex --no-timestamp
    """
    # Find all chip histories
    enriched_dir = Path("data/03_derived/chip_histories_enriched")
    standard_dir = Path("data/02_stage/chip_histories")

    # Discover chip numbers
    chip_numbers = set()

    if enriched_dir.exists():
        for file in enriched_dir.glob(f"{chip_group}*_history.parquet"):
            chip_str = file.stem.replace(f"{chip_group}", "").replace("_history", "")
            if chip_str.isdigit():
                chip_numbers.add(int(chip_str))

    if standard_dir.exists():
        for file in standard_dir.glob(f"{chip_group}*_history.parquet"):
            chip_str = file.stem.replace(f"{chip_group}", "").replace("_history", "")
            if chip_str.isdigit():
                chip_numbers.add(int(chip_str))

    if not chip_numbers:
        console.print(f"[yellow]Warning:[/yellow] No chip histories found for group '{chip_group}'")
        console.print(f"[dim]   Run 'build-all-histories' to generate chip histories[/dim]")
        raise typer.Exit(0)

    console.print(f"[cyan]Found {len(chip_numbers)} chips:[/cyan] {sorted(chip_numbers)}\n")

    # Export each chip
    success_count = 0
    for chip in sorted(chip_numbers):
        console.print(f"[bold]Exporting LaTeX for chip {chip}...[/bold]")
        try:
            export_latex_command(
                chip_number=chip,
                output_dir=output_dir,
                chip_group=chip_group,
                proc_filter=None,
                light_filter=None,
                limit=None,
                timestamp=timestamp,
                overwrite=True
            )
            success_count += 1
            console.print()
        except Exception as e:
            console.print(f"[red]Failed to export chip {chip}:[/red] {str(e)}\n")

    # Final summary
    console.print(f"\n[green]✓ Exported {success_count}/{len(chip_numbers)} chips successfully[/green]")
