#!/usr/bin/env python3
"""
Extract all unique (chip_group, chip_number) combinations from raw CSV files.

This script scans all CSV files in the raw data directory and extracts the
chip group name and chip number from the header metadata, then returns a
sorted list of unique combinations.

Usage:
    python3 scripts/list_chip_combinations.py
    python3 scripts/list_chip_combinations.py --raw-root data/01_raw
    python3 scripts/list_chip_combinations.py --format json
    python3 scripts/list_chip_combinations.py --format yaml
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

from rich.console import Console
from rich.table import Table

# Regex patterns for parsing CSV headers
KV_PAT = re.compile(r"^#\s*([^:]+):\s*(.*)\s*$")
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".ipynb_checkpoints"}


def discover_csvs(root: Path) -> List[Path]:
    """
    Recursively find all CSV files under root directory.

    Args:
        root: Root directory to search

    Returns:
        Sorted list of CSV file paths
    """
    files: List[Path] = []
    for p in root.rglob("*.csv"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.name.startswith("._"):  # macOS resource forks
            continue
        files.append(p)
    files.sort()
    return files


def extract_chip_metadata(csv_path: Path) -> Tuple[str | None, int | None]:
    """
    Extract chip group name and chip number from CSV header.

    Args:
        csv_path: Path to CSV file

    Returns:
        Tuple of (chip_group, chip_number) or (None, None) if not found
    """
    chip_group = None
    chip_number = None

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()

                # Stop at data section
                if line.startswith("#\tData:") or (line and not line.startswith("#")):
                    break

                # Parse key-value pairs
                m = KV_PAT.match(line)
                if m:
                    key = m.group(1).strip()
                    value = m.group(2).strip()

                    if key.lower() in ["chip group name", "chip group"]:
                        chip_group = value
                    elif key.lower() in ["chip number", "chip"]:
                        try:
                            chip_number = int(value)
                        except ValueError:
                            pass  # Invalid chip number, skip

    except Exception as e:
        # File read error, skip silently
        pass

    return chip_group, chip_number


def scan_raw_data(raw_root: Path) -> Dict[str, Set[int]]:
    """
    Scan all CSV files and collect chip group + number combinations.

    Args:
        raw_root: Root directory containing raw CSV files

    Returns:
        Dictionary mapping chip_group -> set of chip_numbers
    """
    console = Console()

    console.print(f"[cyan]Scanning raw data directory:[/cyan] {raw_root}")

    csv_files = discover_csvs(raw_root)
    console.print(f"[cyan]Found {len(csv_files):,} CSV files[/cyan]")

    chip_combinations: Dict[str, Set[int]] = defaultdict(set)
    files_processed = 0
    files_with_metadata = 0

    # Progress tracking
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing CSV files...", total=len(csv_files))

        for csv_path in csv_files:
            chip_group, chip_number = extract_chip_metadata(csv_path)

            if chip_group and chip_number is not None:
                chip_combinations[chip_group].add(chip_number)
                files_with_metadata += 1

            files_processed += 1
            progress.update(task, advance=1)

    console.print(f"[green]✓ Processed {files_processed:,} files[/green]")
    console.print(f"[green]✓ Found metadata in {files_with_metadata:,} files[/green]")
    console.print()

    return chip_combinations


def format_as_table(chip_combinations: Dict[str, Set[int]]) -> None:
    """Display results as a Rich table."""
    console = Console()

    table = Table(title="Chip Combinations Found", show_header=True, header_style="bold magenta")
    table.add_column("Chip Group", style="cyan", no_wrap=True)
    table.add_column("Chip Numbers", style="green")
    table.add_column("Count", justify="right", style="yellow")

    # Sort by chip group name
    for chip_group in sorted(chip_combinations.keys()):
        chip_numbers = sorted(chip_combinations[chip_group])
        chip_numbers_str = ", ".join(str(n) for n in chip_numbers)
        count = len(chip_numbers)

        table.add_row(chip_group, chip_numbers_str, str(count))

    console.print(table)

    # Summary statistics
    total_groups = len(chip_combinations)
    total_chips = sum(len(nums) for nums in chip_combinations.values())

    console.print()
    console.print(f"[bold]Summary:[/bold]")
    console.print(f"  • Total chip groups: [cyan]{total_groups}[/cyan]")
    console.print(f"  • Total unique chips: [green]{total_chips}[/green]")


def format_as_list(chip_combinations: Dict[str, Set[int]]) -> None:
    """Display results as a simple list."""
    console = Console()

    combinations = []
    for chip_group in sorted(chip_combinations.keys()):
        for chip_number in sorted(chip_combinations[chip_group]):
            combinations.append(f"{chip_group}{chip_number}")

    console.print("[bold]Chip Combinations:[/bold]")
    for combo in combinations:
        console.print(f"  • {combo}")

    console.print()
    console.print(f"[bold]Total:[/bold] {len(combinations)} unique chips")


def format_as_json(chip_combinations: Dict[str, Set[int]]) -> None:
    """Display results as JSON."""
    # Convert sets to sorted lists for JSON serialization
    output = {
        chip_group: sorted(list(chip_numbers))
        for chip_group, chip_numbers in chip_combinations.items()
    }

    print(json.dumps(output, indent=2, sort_keys=True))


def format_as_yaml(chip_combinations: Dict[str, Set[int]]) -> None:
    """Display results as YAML."""
    try:
        import yaml
    except ImportError:
        console = Console()
        console.print("[red]✗ Error: PyYAML not installed. Install with: pip install pyyaml[/red]")
        return

    # Convert sets to sorted lists for YAML serialization
    output = {
        chip_group: sorted(list(chip_numbers))
        for chip_group, chip_numbers in chip_combinations.items()
    }

    print(yaml.dump(output, sort_keys=True, default_flow_style=False))


def format_as_csv(chip_combinations: Dict[str, Set[int]]) -> None:
    """Display results as CSV."""
    print("chip_group,chip_number")

    for chip_group in sorted(chip_combinations.keys()):
        for chip_number in sorted(chip_combinations[chip_group]):
            print(f"{chip_group},{chip_number}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract unique chip group + chip number combinations from raw CSV files"
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/01_raw"),
        help="Root directory containing raw CSV files (default: data/01_raw)",
    )
    parser.add_argument(
        "--format",
        choices=["table", "list", "json", "yaml", "csv"],
        default="table",
        help="Output format (default: table)",
    )

    args = parser.parse_args()

    # Validate path
    if not args.raw_root.exists():
        console = Console()
        console.print(f"[red]✗ Error: Directory not found: {args.raw_root}[/red]")
        return 1

    # Scan raw data
    chip_combinations = scan_raw_data(args.raw_root)

    if not chip_combinations:
        console = Console()
        console.print("[yellow]⚠ No chip metadata found in CSV files[/yellow]")
        return 0

    # Display results in requested format
    if args.format == "table":
        format_as_table(chip_combinations)
    elif args.format == "list":
        format_as_list(chip_combinations)
    elif args.format == "json":
        format_as_json(chip_combinations)
    elif args.format == "yaml":
        format_as_yaml(chip_combinations)
    elif args.format == "csv":
        format_as_csv(chip_combinations)

    return 0


if __name__ == "__main__":
    exit(main())
