"""CLI command for batch plotting IVg-by-sample for all chips in a group."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.cli.plugin_system import cli_command
from src.plotting.config import PlotConfig


@cli_command(
    name="plot-ivg-by-sample-group",
    group="plotting",
    description="Plot IVg-by-sample for all chips in a chip group"
)
def plot_ivg_by_sample_group_command(
    chip_group: str = typer.Argument(..., help="Chip group name (e.g., 'Margarita', 'Alisson')"),
    conductance: bool = typer.Option(False, "--conductance", "-g", help="Plot conductance G=I/V instead of current"),
    raw_root: Optional[Path] = typer.Option(None, "--raw-root", help="Raw data directory (for fallback if no manifest)"),
    manifest_path: Optional[Path] = typer.Option(None, "--manifest", help="Path to manifest.parquet (if available)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory for plots"),
    skip_errors: bool = typer.Option(True, "--skip-errors/--fail-on-error", help="Continue if a chip fails (default: skip)"),
):
    """
    Plot IVg-by-sample for all chip numbers in a chip group.

    This command finds all chip numbers for a given chip group and generates
    an IVg-by-sample plot for each chip, showing the last measurement for
    each sample (A-J) in a single comparison figure.

    Examples:

        # Plot all Margarita chips
        plot-ivg-by-sample-group Margarita

        # Plot with conductance mode
        plot-ivg-by-sample-group Alisson --conductance

        # Specify raw data location
        plot-ivg-by-sample-group Laika --raw-root data/01_raw

        # Fail on first error instead of skipping
        plot-ivg-by-sample-group Margarita --fail-on-error

    The command will:
    1. Scan for all chip numbers in the group
    2. Generate one plot per chip
    3. Show progress and summary statistics
    """
    console = Console()

    from src.plotting.ivg_by_sample import plot_ivg_by_sample, scan_csvs_for_chip_samples, load_sample_data_from_manifest
    import polars as pl

    console.print(f"\n[bold cyan]Batch IVg-by-Sample Plotting[/bold cyan]")
    console.print(f"  Chip Group: [green]{chip_group}[/green]")
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

    # Find all chip numbers for this group
    console.print("[cyan]Discovering chip numbers...[/cyan]")

    chip_numbers = set()

    # Try manifest first
    if manifest_path and manifest_path.exists():
        try:
            df = pl.read_parquet(manifest_path)
            filtered = df.filter(
                (pl.col("chip_group") == chip_group) &
                (pl.col("procedure") == "IVg")
            )
            if filtered.height > 0:
                chip_numbers = set(filtered["chip_number"].unique().to_list())
                console.print(f"  ✓ Found {len(chip_numbers)} chips in manifest")
        except Exception as e:
            console.print(f"  ⚠ Could not read manifest: {e}")

    # Fallback to raw CSV scan
    if not chip_numbers and raw_root and raw_root.exists():
        console.print(f"  Scanning raw CSVs...")
        from src.core.stage_raw_measurements import discover_csvs
        import re

        KV_PAT = re.compile(r"^#\s*([^:]+):\s*(.*)\s*$")
        PROC_LINE_RE = re.compile(r"^#\s*Procedure\s*:\s*<.*\.([^.>]+)>.*$", re.I)

        all_csvs = discover_csvs(raw_root)

        for csv_path in all_csvs:
            proc_type = None
            found_chip_group = None
            found_chip_number = None

            try:
                with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()

                        # Stop at data section
                        if line.startswith("#\tData:") or (line and not line.startswith("#")):
                            break

                        # Extract procedure type
                        if proc_type is None:
                            m = PROC_LINE_RE.match(line)
                            if m:
                                proc_type = m.group(1)

                        # Parse key-value pairs
                        m = KV_PAT.match(line)
                        if m:
                            key = m.group(1).strip()
                            value = m.group(2).strip()

                            if key.lower() in ["chip group name", "chip group"]:
                                found_chip_group = value
                            elif key.lower() in ["chip number", "chip"]:
                                try:
                                    found_chip_number = int(value)
                                except ValueError:
                                    pass

            except Exception:
                continue

            # Check if this matches our target group
            if proc_type == "IVg" and found_chip_group == chip_group and found_chip_number is not None:
                chip_numbers.add(found_chip_number)

        console.print(f"  ✓ Found {len(chip_numbers)} chips in raw data")

    if not chip_numbers:
        console.print(f"\n[bold red]✗ No chips found for group '{chip_group}'[/bold red]")
        console.print("[yellow]Hints:[/yellow]")
        console.print("  • Check chip group name (case-sensitive)")
        console.print("  • Verify IVg measurements exist")
        console.print("  • Try: python3 scripts/list_chip_combinations.py")
        raise typer.Exit(1)

    # Sort chip numbers for consistent ordering
    sorted_chips = sorted(chip_numbers)

    console.print(f"\n[bold]Chips to process:[/bold] {', '.join(str(n) for n in sorted_chips)}\n")

    # Process each chip
    successful = []
    failed = []
    skipped = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Processing {len(sorted_chips)} chips...",
            total=len(sorted_chips)
        )

        for chip_number in sorted_chips:
            progress.update(task, description=f"Processing {chip_group} {chip_number}...")

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
                    successful.append((chip_number, output_path))
                else:
                    skipped.append(chip_number)

            except Exception as e:
                failed.append((chip_number, str(e)))
                if not skip_errors:
                    console.print(f"\n[bold red]✗ Error processing {chip_group} {chip_number}:[/bold red] {e}")
                    raise typer.Exit(1)

            progress.advance(task)

    # Summary
    console.print(f"\n[bold cyan]Summary[/bold cyan]")
    console.print(f"  Total chips: {len(sorted_chips)}")
    console.print(f"  [green]✓ Successful: {len(successful)}[/green]")
    if skipped:
        console.print(f"  [yellow]⊘ Skipped (no data): {len(skipped)}[/yellow]")
    if failed:
        console.print(f"  [red]✗ Failed: {len(failed)}[/red]")

    # Show successful plots
    if successful:
        console.print(f"\n[bold green]✓ Generated {len(successful)} plots:[/bold green]")
        for chip_num, output_path in successful:
            console.print(f"  • {chip_group} {chip_num}: {output_path}")

    # Show skipped chips
    if skipped:
        console.print(f"\n[yellow]⊘ Skipped chips (no plottable data):[/yellow]")
        console.print(f"  {', '.join(str(n) for n in skipped)}")

    # Show failed chips
    if failed:
        console.print(f"\n[bold red]✗ Failed chips:[/bold red]")
        for chip_num, error in failed:
            console.print(f"  • {chip_group} {chip_num}: {error}")

    # Exit code
    if failed and not skip_errors:
        raise typer.Exit(1)
    elif not successful:
        console.print("\n[yellow]⚠ No plots generated[/yellow]")
        raise typer.Exit(1)
