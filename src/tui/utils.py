"""
TUI Utility Functions.

Provides helper functions for the TUI, including chip auto-discovery.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

import polars as pl


@dataclass
class ChipInfo:
    """Information about a discovered chip."""

    chip_number: int
    chip_group: str
    total_experiments: int
    ivg_count: int
    its_count: int
    last_experiment_date: Optional[str]
    source: str  # "history" or "metadata"

    def __str__(self) -> str:
        """String representation for display."""
        return f"{self.chip_group}{self.chip_number}"


def discover_chips(
    metadata_dir: Path,
    raw_dir: Path,
    history_dir: Path,
    chip_group: str = "Alisson"
) -> List[ChipInfo]:
    """
    Auto-discover chips from chip_histories and metadata directories.

    Scans chip_histories/*.parquet files first (fastest), then falls back
    to metadata/ directory if needed.

    Parameters
    ----------
    metadata_dir : Path
        Metadata directory path
    raw_dir : Path
        Raw data directory path
    history_dir : Path
        Chip history directory path
    chip_group : str
        Default chip group name (e.g., "Alisson")

    Returns
    -------
    List[ChipInfo]
        List of discovered chips with experiment counts, sorted by chip number
    """
    chips = {}  # chip_number -> ChipInfo

    # 1. Scan chip_histories directory (preferred source)
    if history_dir.exists():
        # Try both parquet and CSV files
        for file_pattern in ["*.parquet", "*.csv"]:
            for history_file in history_dir.glob(file_pattern):
                try:
                    # Parse filename: e.g., "Alisson67.parquet", "Alisson67_history.csv", "chip67_history.csv"
                    filename = history_file.stem

                    # Try different naming patterns
                    chip_num = None
                    group = chip_group

                    # Pattern 1: "Alisson67" or "Alisson67_history"
                    if filename.startswith(chip_group):
                        try:
                            # Remove _history suffix if present
                            num_str = filename[len(chip_group):].replace("_history", "")
                            chip_num = int(num_str)
                        except ValueError:
                            pass

                    # Pattern 2: "chip67_history"
                    elif filename.startswith("chip") and "_history" in filename:
                        try:
                            chip_num = int(filename.replace("chip", "").replace("_history", ""))
                        except ValueError:
                            pass

                    if chip_num is None:
                        continue

                    # Skip if we already processed this chip from parquet
                    if chip_num in chips:
                        continue

                    # Read the file (parquet or CSV)
                    if history_file.suffix == ".parquet":
                        df = pl.read_parquet(history_file)
                    else:  # CSV
                        df = pl.read_csv(history_file)

                    if df.height == 0:
                        continue

                    # Count experiments by procedure type
                    total = df.height
                    ivg_count = df.filter(pl.col("proc") == "IVg").height if "proc" in df.columns else 0
                    its_count = df.filter(pl.col("proc").is_in(["ITS", "It"])).height if "proc" in df.columns else 0

                    # Get last experiment date
                    last_date = None
                    if "date" in df.columns:
                        try:
                            dates = df["date"].drop_nulls()
                            if len(dates) > 0:
                                last_date = str(dates[-1])
                        except Exception:
                            pass

                    chips[chip_num] = ChipInfo(
                        chip_number=chip_num,
                        chip_group=group,
                        total_experiments=total,
                        ivg_count=ivg_count,
                        its_count=its_count,
                        last_experiment_date=last_date,
                        source="history"
                    )

                except Exception as e:
                    # Skip files that can't be read
                    continue

    # 2. Scan metadata directory as fallback
    if metadata_dir.exists():
        for csv_file in metadata_dir.glob("**/"):
            # Look for subdirectories named like "Alisson_15_sept"
            if csv_file.is_dir():
                dir_name = csv_file.name

                # Try to extract chip info from directory name
                # Common patterns: "Alisson_15_sept", "Alisson67", etc.
                # For now, we'll rely on chip_histories as primary source

    # Convert to sorted list
    chip_list = sorted(chips.values(), key=lambda c: c.chip_number, reverse=True)

    return chip_list


def format_chip_display(chip: ChipInfo, show_details: bool = True) -> str:
    """
    Format chip information for display.

    Parameters
    ----------
    chip : ChipInfo
        Chip information
    show_details : bool
        Whether to show experiment counts and dates

    Returns
    -------
    str
        Formatted string for display
    """
    if not show_details:
        return str(chip)

    details = []
    details.append(f"{chip.total_experiments} experiments")

    if chip.ivg_count > 0 or chip.its_count > 0:
        proc_parts = []
        if chip.ivg_count > 0:
            proc_parts.append(f"{chip.ivg_count} IVg")
        if chip.its_count > 0:
            proc_parts.append(f"{chip.its_count} ITS")
        details.append(", ".join(proc_parts))

    if chip.last_experiment_date:
        details.append(f"Last: {chip.last_experiment_date}")

    return f"{chip} - {', '.join(details)}"
