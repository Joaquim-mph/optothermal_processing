"""Data processing pipeline commands: parse-all, chip-histories, full-pipeline, quick-stats."""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.tree import Tree
from rich import box
import time
import polars as pl

from src.core.parser import parse_iv_metadata
from src.core.timeline import build_chip_history

console = Console()


def scan_raw_data_folders(raw_dir: Path) -> list[Path]:
    """Find all subdirectories in raw_data that contain CSV files."""
    folders = []
    if not raw_dir.exists():
        console.print(f"[red]Error:[/red] Directory {raw_dir} does not exist")
        return folders

    for item in raw_dir.iterdir():
        if item.is_dir():
            # Check if it contains CSV files
            csv_files = list(item.glob("*.csv"))
            if csv_files:
                folders.append(item)

    return sorted(folders)


def parse_all_command(
    raw_dir: Path = typer.Option(
        Path("raw_data"),
        "--raw",
        "-r",
        help="Raw data directory containing experiment folders"
    ),
    meta_dir: Path = typer.Option(
        Path("metadata"),
        "--meta",
        "-m",
        help="Output directory for metadata files"
    ),
):
    """
    Parse all raw CSV files and generate metadata for all experiment folders.

    Scans raw_data directory, finds all folders with CSV files, and generates
    metadata/<folder>/metadata.csv for each.
    """
    console.print(Panel.fit(
        "[bold cyan]Step 1: Metadata Extraction[/bold cyan]\n"
        "Parsing raw CSV headers and extracting experiment parameters",
        border_style="cyan"
    ))

    # Find all folders
    console.print(f"\n[yellow]Scanning[/yellow] {raw_dir} for experiment folders...")
    folders = scan_raw_data_folders(raw_dir)

    if not folders:
        console.print("[red]No folders with CSV files found![/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Found {len(folders)} folder(s) with CSV files\n")

    # Show folders in a tree
    tree = Tree(f"[bold]{raw_dir}[/bold]")
    for folder in folders:
        csv_count = len(list(folder.glob("*.csv")))
        tree.add(f"{folder.name} [dim]({csv_count} CSV files)[/dim]")
    console.print(tree)
    console.print()

    # Process each folder with progress bar
    meta_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Processing folders...", total=len(folders))

        for folder in folders:
            folder_name = folder.name
            progress.update(task, description=f"[cyan]Processing {folder_name}...")

            # Create output directory
            out_dir = meta_dir / folder_name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / "metadata.csv"

            # Find all CSV files
            csv_files = sorted(folder.glob("*.csv"))

            # Parse each file
            metadata_rows = []
            for csv_file in csv_files:
                try:
                    meta = parse_iv_metadata(csv_file)
                    if meta:
                        # Make source_file relative - just use folder/filename format
                        # This matches the expected format in timeline.py
                        rel_path = f"{raw_dir.name}/{folder_name}/{csv_file.name}"
                        meta['source_file'] = rel_path
                        metadata_rows.append(meta)
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to parse {csv_file.name}: {e}")

            # Save metadata
            if metadata_rows:
                df = pl.DataFrame(metadata_rows)
                df.write_csv(out_file)
                results.append({
                    'folder': folder_name,
                    'csv_count': len(csv_files),
                    'parsed': len(metadata_rows),
                    'output': out_file
                })

            progress.advance(task)

    # Summary table
    console.print()
    table = Table(title="Metadata Generation Summary", box=box.ROUNDED)
    table.add_column("Folder", style="cyan")
    table.add_column("CSV Files", justify="right", style="yellow")
    table.add_column("Parsed", justify="right", style="green")
    table.add_column("Output File", style="dim")

    total_csv = 0
    total_parsed = 0
    for result in results:
        table.add_row(
            result['folder'],
            str(result['csv_count']),
            str(result['parsed']),
            str(result['output'])
        )
        total_csv += result['csv_count']
        total_parsed += result['parsed']

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold yellow]{total_csv}[/bold yellow]",
        f"[bold green]{total_parsed}[/bold green]",
        f"[bold]{len(results)} file(s)[/bold]"
    )

    console.print(table)
    console.print(f"\n[green]✓ Metadata extraction complete![/green]")


def chip_histories_command(
    meta_dir: Path = typer.Option(
        Path("metadata"),
        "--meta",
        "-m",
        help="Metadata directory"
    ),
    raw_dir: Path = typer.Option(
        Path("."),
        "--raw",
        "-r",
        help="Raw data directory"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name prefix"
    ),
    min_experiments: int = typer.Option(
        1,
        "--min",
        help="Minimum experiments per chip to include"
    ),
    save_csv: bool = typer.Option(
        True,
        "--save/--no-save",
        help="Save individual chip history CSV files"
    ),
    history_dir: Path = typer.Option(
        Path("chip_histories"),
        "--history-dir",
        "-o",
        help="Output directory for chip history CSV files"
    ),
):
    """
    Generate complete experiment histories for all chips found in metadata.

    Automatically discovers all chips, builds their complete timelines,
    and provides detailed statistics.
    """
    console.print(Panel.fit(
        "[bold magenta]Step 2: Chip History Generation[/bold magenta]\n"
        "Building complete experiment timelines for all chips",
        border_style="magenta"
    ))

    console.print(f"\n[yellow]Scanning[/yellow] {meta_dir} for metadata files...")

    # Find metadata files
    metadata_files = list(meta_dir.glob("**/metadata.csv")) + \
                     list(meta_dir.glob("**/*_metadata.csv"))

    if not metadata_files:
        console.print(f"[red]No metadata files found in {meta_dir}![/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Found {len(metadata_files)} metadata file(s)\n")

    # Discover all unique chips
    console.print("[yellow]Discovering chips...[/yellow]")
    all_chips = set()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Scanning metadata...", total=len(metadata_files))

        for meta_file in metadata_files:
            try:
                meta = pl.read_csv(meta_file, ignore_errors=True)
                if "Chip number" in meta.columns:
                    chips = meta.get_column("Chip number").drop_nulls().unique().to_list()
                    for c in chips:
                        try:
                            all_chips.add(int(float(c)))
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Failed to read {meta_file}: {e}")
            progress.advance(task)

    if not all_chips:
        console.print("[red]No chips found in metadata files![/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Found {len(all_chips)} unique chip(s): {sorted(all_chips)}\n")

    # Generate histories
    console.print("[bold]Generating chip histories...[/bold]\n")

    histories = {}
    chip_stats = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Processing chips...", total=len(all_chips))

        for chip_num in sorted(all_chips):
            chip_name = f"{chip_group}{chip_num}"
            progress.update(task, description=f"[cyan]Building history: {chip_name}...")

            history = build_chip_history(
                meta_dir,
                raw_dir,
                chip_num,
                chip_group
            )

            if history.height >= min_experiments:
                histories[chip_num] = history

                # Calculate stats
                dates = [d for d in history["date"].to_list() if d != "unknown"]
                date_range = f"{min(dates)} to {max(dates)}" if dates else "unknown"

                # Count by procedure
                proc_counts = history.group_by("proc").agg([
                    pl.len().alias("count")
                ]).sort("proc")

                proc_breakdown = {row["proc"]: row["count"] for row in proc_counts.iter_rows(named=True)}

                chip_stats.append({
                    'chip_num': chip_num,
                    'chip_name': chip_name,
                    'total': history.height,
                    'date_range': date_range,
                    'num_days': len(set(dates)),
                    'proc_breakdown': proc_breakdown
                })

                # Save CSV
                if save_csv:
                    history_dir.mkdir(parents=True, exist_ok=True)
                    out_file = history_dir / f"{chip_name}_history.csv"
                    history.write_csv(out_file)

            progress.advance(task)

    # Display results
    console.print()
    console.print(Panel.fit(
        f"[bold green]Successfully generated histories for {len(histories)} chip(s)[/bold green]",
        border_style="green"
    ))
    console.print()

    # Overall summary table
    summary_table = Table(title="Overall Summary", box=box.DOUBLE)
    summary_table.add_column("Metric", style="cyan", no_wrap=True)
    summary_table.add_column("Value", style="yellow", justify="right")

    total_experiments = sum(stat['total'] for stat in chip_stats)

    # Aggregate procedure counts
    all_proc_counts = {}
    for stat in chip_stats:
        for proc, count in stat['proc_breakdown'].items():
            all_proc_counts[proc] = all_proc_counts.get(proc, 0) + count

    summary_table.add_row("Chip Group", chip_group)
    summary_table.add_row("Total Chips", str(len(histories)))
    summary_table.add_row("Total Experiments", str(total_experiments))
    summary_table.add_section()

    for proc in sorted(all_proc_counts.keys()):
        summary_table.add_row(f"  {proc} experiments", str(all_proc_counts[proc]))

    console.print(summary_table)
    console.print()

    # Per-chip details table
    details_table = Table(title="Per-Chip Statistics", box=box.ROUNDED, show_lines=True)
    details_table.add_column("Chip", style="cyan", no_wrap=True)
    details_table.add_column("Total\nExpts", justify="right", style="yellow")
    details_table.add_column("Days", justify="right", style="green")
    details_table.add_column("Date Range", style="dim")
    details_table.add_column("Procedure Breakdown", style="magenta")

    for stat in chip_stats:
        # Format procedure breakdown
        proc_str = "\n".join([
            f"{proc}: {count}"
            for proc, count in sorted(stat['proc_breakdown'].items())
        ])

        details_table.add_row(
            stat['chip_name'],
            str(stat['total']),
            str(stat['num_days']),
            stat['date_range'],
            proc_str
        )

    console.print(details_table)
    console.print()

    # Files saved
    if save_csv:
        console.print(f"[green]✓ Chip history CSV files saved to {history_dir}/:[/green]")
        for stat in chip_stats:
            console.print(f"  • {stat['chip_name']}_history.csv")

    console.print(f"\n[green]✓ Chip history generation complete![/green]")


def full_pipeline_command(
    raw_dir: Path = typer.Option(
        Path("raw_data"),
        "--raw",
        "-r",
        help="Raw data directory"
    ),
    meta_dir: Path = typer.Option(
        Path("metadata"),
        "--meta",
        "-m",
        help="Metadata directory"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name prefix"
    ),
    min_experiments: int = typer.Option(
        1,
        "--min",
        help="Minimum experiments per chip"
    ),
    history_dir: Path = typer.Option(
        Path("chip_histories"),
        "--history-dir",
        "-o",
        help="Output directory for chip history CSV files"
    ),
):
    """
    Run the complete pipeline: parse all data AND generate chip histories.

    This is a convenience command that runs both parse-all and chip-histories
    in sequence with a single command.
    """
    console.print(Panel.fit(
        "[bold blue]Complete Data Processing Pipeline[/bold blue]\n"
        "Step 1: Parse raw CSV files → metadata\n"
        "Step 2: Generate chip histories from metadata",
        title="Full Pipeline",
        border_style="blue"
    ))
    console.print()

    start_time = time.time()

    # Step 1: Parse
    parse_all_command(raw_dir=raw_dir, meta_dir=meta_dir)

    console.print("\n" + "="*80 + "\n")

    # Step 2: Histories
    chip_histories_command(
        meta_dir=meta_dir,
        raw_dir=Path("."),
        chip_group=chip_group,
        min_experiments=min_experiments,
        save_csv=True,
        history_dir=history_dir
    )

    elapsed = time.time() - start_time

    console.print("\n" + "="*80 + "\n")
    console.print(Panel.fit(
        f"[bold green]Pipeline Complete![/bold green]\n"
        f"Total time: {elapsed:.1f} seconds",
        border_style="green"
    ))


def quick_stats_command(
    meta_dir: Path = typer.Option(
        Path("metadata"),
        "--meta",
        "-m",
        help="Metadata directory"
    ),
    chip_group: str = typer.Option(
        "Alisson",
        "--group",
        "-g",
        help="Chip group name prefix"
    ),
):
    """
    Quick statistics summary without generating full histories.

    Fast overview of what's in your metadata.
    """
    console.print(Panel.fit(
        "[bold cyan]Quick Statistics[/bold cyan]",
        border_style="cyan"
    ))

    metadata_files = list(meta_dir.glob("**/metadata.csv")) + \
                     list(meta_dir.glob("**/*_metadata.csv"))

    if not metadata_files:
        console.print(f"[red]No metadata files found in {meta_dir}![/red]")
        raise typer.Exit(1)

    all_chips = set()
    total_experiments = 0
    proc_counts = {}

    with Progress(SpinnerColumn(), TextColumn("[cyan]Scanning..."), console=console) as progress:
        progress.add_task("scan", total=None)

        for meta_file in metadata_files:
            try:
                meta = pl.read_csv(meta_file, ignore_errors=True)

                # Count experiments
                total_experiments += meta.height

                # Discover chips
                if "Chip number" in meta.columns:
                    chips = meta.get_column("Chip number").drop_nulls().unique().to_list()
                    for c in chips:
                        try:
                            all_chips.add(int(float(c)))
                        except (ValueError, TypeError):
                            pass

                # Count procedures (if source_file exists, infer proc)
                if "source_file" in meta.columns:
                    for src in meta["source_file"].to_list():
                        if isinstance(src, str):
                            if "IVg" in src:
                                proc_counts["IVg"] = proc_counts.get("IVg", 0) + 1
                            elif "It" in src or "ITS" in src:
                                proc_counts["ITS"] = proc_counts.get("ITS", 0) + 1
                            elif "IV" in src:
                                proc_counts["IV"] = proc_counts.get("IV", 0) + 1
            except Exception:
                pass

    # Display
    console.print()
    table = Table(title="Quick Stats", box=box.DOUBLE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow", justify="right")

    table.add_row("Chip Group", chip_group)
    table.add_row("Metadata Files", str(len(metadata_files)))
    table.add_row("Unique Chips", str(len(all_chips)))
    table.add_row("Chips Found", ", ".join(str(c) for c in sorted(all_chips)))
    table.add_row("Total Experiments", str(total_experiments))
    table.add_section()

    for proc in sorted(proc_counts.keys()):
        table.add_row(f"  {proc} (approx)", str(proc_counts[proc]))

    console.print(table)
