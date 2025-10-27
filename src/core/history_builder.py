"""
Build chip histories from staged manifest data.

This module creates chip history CSV files from the manifest.parquet generated
during the staging process. Histories are saved to data/03_history/ and include
sequential experiment numbers, dates, procedures, and summaries.
"""

from pathlib import Path
from typing import Optional
import polars as pl
from datetime import datetime


def build_chip_history_from_manifest(
    manifest_path: Path,
    chip_number: Optional[int] = None,
    chip_group: Optional[str] = None,
    information: Optional[str] = None,
    proc_filter: Optional[str] = None,
) -> pl.DataFrame:
    """
    Build experiment history for a specific chip from manifest.parquet.

    Filters manifest by chip identifier and returns chronologically ordered
    history with sequential experiment numbers.

    Parameters
    ----------
    manifest_path : Path
        Path to manifest.parquet file
    chip_number : int, optional
        Chip numeric ID (e.g., 67 for Alisson67)
    chip_group : str, optional
        Chip group prefix (e.g., "Alisson")
    information : str, optional
        Information field to filter by (used when chip_number/group are missing)
    proc_filter : str, optional
        Filter by procedure type (e.g., "It", "IVg")

    Returns
    -------
    pl.DataFrame
        Chip history with columns: seq, date, time_hms, proc, summary, has_light, etc.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    # Load manifest
    df = pl.read_parquet(manifest_path)

    # Filter by chip identifier
    if chip_number is not None:
        df = df.filter(pl.col("chip_number") == chip_number)
        if chip_group:
            df = df.filter(pl.col("chip_group") == chip_group)
    elif information:
        # Use Information column for filtering
        if "information" in df.columns:
            df = df.filter(pl.col("information") == information)
        else:
            raise ValueError("Information column not found in manifest")
    else:
        raise ValueError("Must provide either (chip_number, chip_group) or information")

    # Apply procedure filter if specified
    if proc_filter:
        df = df.filter(pl.col("proc") == proc_filter)

    # Parse start_time_utc as datetime if it's a string
    if df["start_time_utc"].dtype == pl.Utf8:
        df = df.with_columns([
            pl.col("start_time_utc").str.to_datetime(format="%Y-%m-%d %H:%M:%S%.f%z", time_zone="UTC").alias("start_time_utc")
        ])

    # Sort by time
    df = df.sort("start_time_utc")

    # Add sequential experiment numbers
    df = df.with_row_count("seq", offset=1)

    # Extract date and time from start_time_utc
    df = df.with_columns([
        pl.col("start_time_utc").dt.date().cast(pl.Utf8).alias("date"),
        pl.col("start_time_utc").dt.strftime("%H:%M:%S").alias("time_hms"),
    ])

    # Generate chip_name if it doesn't exist
    if "chip_name" not in df.columns:
        if chip_number is not None and chip_group:
            df = df.with_columns([
                pl.lit(f"{chip_group}{chip_number}").alias("chip_name")
            ])
        elif information:
            import re
            cleaned = re.sub(r'[^\w\s-]', '', information)
            cleaned = re.sub(r'[-\s]+', '_', cleaned)
            df = df.with_columns([
                pl.lit(cleaned or "UnknownChip").alias("chip_name")
            ])

    # Extract file_idx from source_file if it doesn't exist
    if "file_idx" not in df.columns:
        df = df.with_columns([
            pl.col("source_file").str.extract(r'_(\d+)\.csv$', 1).cast(pl.Int64, strict=False).alias("file_idx")
        ])

    # Generate summary if it doesn't exist
    if "summary" not in df.columns:
        summary_parts = []

        # Start with chip name and procedure
        if "chip_name" in df.columns:
            summary_parts.append(pl.col("chip_name") + " " + pl.col("proc"))
        else:
            summary_parts.append(pl.col("proc"))

        # Add light info if available
        if "has_light" in df.columns and "wavelength_nm" in df.columns:
            summary_parts.append(
                pl.when(pl.col("has_light") == True)
                .then(pl.lit(" (λ=") + pl.col("wavelength_nm").cast(pl.Utf8) + pl.lit("nm)"))
                .otherwise(pl.lit(""))
            )

        # Concatenate all parts
        if len(summary_parts) > 1:
            summary_expr = summary_parts[0]
            for part in summary_parts[1:]:
                summary_expr = summary_expr + part
        else:
            summary_expr = summary_parts[0]

        df = df.with_columns([
            summary_expr.alias("summary")
        ])

    # Select relevant columns for history
    history_cols = [
        "seq",
        "date",
        "time_hms",
        "proc",
        "summary",
        "has_light",
        "chip_number",
        "chip_group",
        "chip_name",
        "run_id",
        "source_file",
        "file_idx",
        "date_local",
    ]

    # Only select columns that exist in the dataframe
    available_cols = [col for col in history_cols if col in df.columns]
    history = df.select(available_cols)

    return history


def generate_chip_name(
    chip_number: Optional[int],
    chip_group: Optional[str],
    information: Optional[str],
) -> str:
    """
    Generate chip name for history file.

    Parameters
    ----------
    chip_number : int, optional
        Chip numeric ID
    chip_group : str, optional
        Chip group prefix
    information : str, optional
        Information field value

    Returns
    -------
    str
        Chip name for filename (e.g., "Alisson67" or "CustomChipName")
    """
    if chip_number is not None and chip_group:
        return f"{chip_group}{chip_number}"
    elif information:
        # Clean information string for filename
        import re
        cleaned = re.sub(r'[^\w\s-]', '', information)  # Remove special chars
        cleaned = re.sub(r'[-\s]+', '_', cleaned)  # Replace spaces/hyphens with underscore
        return cleaned or "UnknownChip"
    else:
        return "UnknownChip"


def save_chip_history(
    history: pl.DataFrame,
    output_dir: Path,
    chip_name: str,
) -> Path:
    """
    Save chip history to CSV file.

    Parameters
    ----------
    history : pl.DataFrame
        Chip history dataframe
    output_dir : Path
        Output directory (e.g., data/03_history)
    chip_name : str
        Chip name for filename

    Returns
    -------
    Path
        Path to saved history file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{chip_name}_history.csv"
    history.write_csv(output_path)
    return output_path


def generate_all_chip_histories(
    manifest_path: Path,
    output_dir: Path,
    min_experiments: int = 5,
    chip_group: Optional[str] = None,
) -> dict[str, Path]:
    """
    Generate history files for all chips found in manifest.

    Automatically discovers all unique chips and creates individual
    history CSV files in the output directory.

    Parameters
    ----------
    manifest_path : Path
        Path to manifest.parquet file
    output_dir : Path
        Output directory for history files (e.g., data/03_history)
    min_experiments : int
        Minimum number of experiments required to generate history
    chip_group : str, optional
        Filter by specific chip group

    Returns
    -------
    dict[str, Path]
        Mapping of chip_name -> history_file_path
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    # Load manifest
    df = pl.read_parquet(manifest_path)

    # Filter by chip group if specified
    if chip_group:
        df = df.filter(pl.col("chip_group") == chip_group)

    # Discover unique chips
    chip_identifiers = []

    # Group by chip_number and chip_group (if available)
    if "chip_number" in df.columns and "chip_group" in df.columns:
        chip_groups = (
            df.filter(pl.col("chip_number").is_not_null())
            .group_by(["chip_number", "chip_group"])
            .agg(pl.count().alias("count"))
            .filter(pl.col("count") >= min_experiments)
        )

        for row in chip_groups.iter_rows(named=True):
            chip_identifiers.append({
                "chip_number": row["chip_number"],
                "chip_group": row["chip_group"],
                "information": None,
                "count": row["count"],
            })

    # Also find chips identified by Information field
    if "information" in df.columns:
        info_groups = (
            df.filter(
                (pl.col("chip_number").is_null()) | (pl.col("chip_group").is_null())
            )
            .filter(pl.col("information").is_not_null())
            .group_by("information")
            .agg(pl.count().alias("count"))
            .filter(pl.col("count") >= min_experiments)
        )

        for row in info_groups.iter_rows(named=True):
            chip_identifiers.append({
                "chip_number": None,
                "chip_group": None,
                "information": row["information"],
                "count": row["count"],
            })

    # Generate history for each chip
    histories = {}

    for chip_id in chip_identifiers:
        try:
            # Build history
            history = build_chip_history_from_manifest(
                manifest_path,
                chip_number=chip_id["chip_number"],
                chip_group=chip_id["chip_group"],
                information=chip_id["information"],
            )

            # Generate chip name
            chip_name = generate_chip_name(
                chip_id["chip_number"],
                chip_id["chip_group"],
                chip_id["information"],
            )

            # Save history
            output_path = save_chip_history(history, output_dir, chip_name)
            histories[chip_name] = output_path

        except Exception as e:
            # Log error but continue with other chips
            print(f"Warning: Failed to generate history for {chip_id}: {e}")
            continue

    return histories


def print_chip_history(
    manifest_path: Path,
    chip_number: Optional[int] = None,
    chip_group: Optional[str] = None,
    information: Optional[str] = None,
    proc_filter: Optional[str] = None,
    max_rows: int = 50,
) -> None:
    """
    Print chip history to console (for debugging/quick viewing).

    Parameters
    ----------
    manifest_path : Path
        Path to manifest.parquet file
    chip_number : int, optional
        Chip numeric ID
    chip_group : str, optional
        Chip group prefix
    information : str, optional
        Information field value
    proc_filter : str, optional
        Filter by procedure type
    max_rows : int
        Maximum rows to display
    """
    history = build_chip_history_from_manifest(
        manifest_path,
        chip_number=chip_number,
        chip_group=chip_group,
        information=information,
        proc_filter=proc_filter,
    )

    chip_name = generate_chip_name(chip_number, chip_group, information)

    print(f"\n{'='*80}")
    print(f"Chip History: {chip_name}")
    print(f"Total Experiments: {len(history)}")
    print(f"{'='*80}\n")

    # Display with polars
    if len(history) > max_rows:
        print(f"Showing first {max_rows} of {len(history)} experiments:\n")
        print(history.head(max_rows))
    else:
        print(history)

    print(f"\n{'='*80}\n")


def get_chip_summary_stats(manifest_path: Path, chip_name: str) -> dict:
    """
    Get summary statistics for a chip.

    Parameters
    ----------
    manifest_path : Path
        Path to manifest.parquet file
    chip_name : str
        Chip name (e.g., "Alisson67")

    Returns
    -------
    dict
        Summary statistics including total experiments, date range, procedures
    """
    # Parse chip name to extract number and group
    import re
    match = re.match(r"^([A-Za-z]+)(\d+)$", chip_name)

    if match:
        chip_group = match.group(1)
        chip_number = int(match.group(2))
        history = build_chip_history_from_manifest(
            manifest_path,
            chip_number=chip_number,
            chip_group=chip_group,
        )
    else:
        # Try as information field
        history = build_chip_history_from_manifest(
            manifest_path,
            information=chip_name,
        )

    if len(history) == 0:
        return {
            "total_experiments": 0,
            "date_range": None,
            "procedures": {},
        }

    # Calculate statistics
    stats = {
        "total_experiments": len(history),
        "date_range": (
            history["date"].min(),
            history["date"].max(),
        ) if "date" in history.columns else None,
        "procedures": {},
    }

    # Count by procedure
    if "proc" in history.columns:
        proc_counts = history.group_by("proc").agg(pl.count().alias("count"))
        stats["procedures"] = {
            row["proc"]: row["count"]
            for row in proc_counts.iter_rows(named=True)
        }

    return stats
