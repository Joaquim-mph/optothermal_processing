"""
IVg plotting by sample letter (A-J).

Plots the last IVg measurement for each sample letter of a given chip,
allowing comparison across different samples on the same chip substrate.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict, Tuple

import matplotlib.pyplot as plt
import polars as pl

from src.core.utils import read_measurement_parquet
from src.plotting.config import PlotConfig
from src.plotting.plot_utils import ensure_standard_columns


def scan_csvs_for_chip_samples(
    raw_root: Path,
    chip_group: str,
    chip_number: int,
    procedure: str = "IVg"
) -> Dict[str, Tuple[Path, float]]:
    """
    Scan raw CSV files to find the last measurement for each sample.

    This is a fallback method when staged data is not available.

    Args:
        raw_root: Root directory with raw CSV files
        chip_group: Chip group name (e.g., "Margarita")
        chip_number: Chip number (e.g., 1)
        procedure: Procedure type (default: "IVg")

    Returns:
        Dictionary mapping sample letter -> (csv_path, timestamp)
    """
    from src.core.stage_raw_measurements import discover_csvs

    KV_PAT = re.compile(r"^#\s*([^:]+):\s*(.*)\s*$")
    PROC_LINE_RE = re.compile(r"^#\s*Procedure\s*:\s*<.*\.([^.>]+)>.*$", re.I)

    # Find all CSVs
    all_csvs = discover_csvs(raw_root)

    # Track: sample_letter -> (path, timestamp)
    sample_data: Dict[str, Tuple[Path, float]] = {}

    for csv_path in all_csvs:
        # Parse header to extract metadata
        proc_type = None
        found_chip_group = None
        found_chip_number = None
        found_sample = None
        timestamp = None

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
                        elif key.lower() == "sample":
                            found_sample = value.strip().upper()
                        elif key.lower() == "start time":
                            try:
                                timestamp = float(value)
                            except ValueError:
                                pass

        except Exception:
            continue  # Skip files with read errors

        # Check if this matches our target chip and procedure
        if (proc_type == procedure and
            found_chip_group == chip_group and
            found_chip_number == chip_number and
            found_sample and
            timestamp is not None):

            # Keep only the latest measurement for each sample
            if found_sample not in sample_data or timestamp > sample_data[found_sample][1]:
                sample_data[found_sample] = (csv_path, timestamp)

    return sample_data


def load_sample_data_from_manifest(
    chip_group: str,
    chip_number: int,
    manifest_path: Path,
) -> Dict[str, Path]:
    """
    Load the last IVg for each sample from staged manifest.

    Args:
        chip_group: Chip group name
        chip_number: Chip number
        manifest_path: Path to manifest.parquet

    Returns:
        Dictionary mapping sample letter -> parquet_path
    """
    df = pl.read_parquet(manifest_path)

    # Filter for our chip and IVg procedure
    filtered = df.filter(
        (pl.col("chip_group") == chip_group) &
        (pl.col("chip_number") == chip_number) &
        (pl.col("procedure") == "IVg")
    )

    if filtered.height == 0:
        return {}

    # Check if sample column exists
    if "sample" not in filtered.columns:
        raise ValueError(
            "Sample column not found in manifest. "
            "Re-run staging with updated procedures.yml to capture Sample parameter."
        )

    # Group by sample and get the last measurement (max timestamp) for each
    sample_data = {}

    for sample in filtered["sample"].unique().sort():
        if sample is None:
            continue  # Skip null samples

        sample_str = str(sample).strip().upper()

        # Get latest measurement for this sample
        sample_rows = filtered.filter(pl.col("sample") == sample).sort("timestamp_utc")

        if sample_rows.height > 0:
            last_row = sample_rows[-1]
            parquet_path = Path(last_row["parquet_path"][0])
            sample_data[sample_str] = parquet_path

    return sample_data


def plot_ivg_by_sample(
    chip_group: str,
    chip_number: int,
    raw_root: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
    conductance: bool = False,
    config: Optional[PlotConfig] = None,
) -> Optional[Path]:
    """
    Plot the last IVg measurement for each sample (A-J) of a chip.

    Tries to use staged manifest first (fast), falls back to scanning
    raw CSVs if manifest is not available.

    Args:
        chip_group: Chip group name (e.g., "Margarita")
        chip_number: Chip number (e.g., 1)
        raw_root: Root directory with raw CSV files (for fallback)
        manifest_path: Path to manifest.parquet (if available)
        conductance: If True, plot G=I/V instead of current
        config: Plot configuration (includes output_dir)

    Returns:
        Path to saved figure, or None if no data found
    """
    config = config or PlotConfig()

    from src.plotting.styles import set_plot_style
    from src.plotting.transforms import calculate_conductance

    set_plot_style(config.theme)

    # Try to load from manifest first
    sample_files: Dict[str, Path] = {}
    use_manifest = False

    if manifest_path and manifest_path.exists():
        try:
            sample_files = load_sample_data_from_manifest(chip_group, chip_number, manifest_path)
            use_manifest = True
            print(f"✓ Loaded {len(sample_files)} samples from manifest")
        except Exception as e:
            print(f"⚠ Could not load from manifest: {e}")
            print(f"  Falling back to raw CSV scan...")

    # Fallback to scanning raw CSVs
    if not sample_files and raw_root:
        print(f"Scanning raw CSVs for {chip_group} {chip_number}...")
        sample_data = scan_csvs_for_chip_samples(raw_root, chip_group, chip_number)

        if not sample_data:
            print(f"✗ No IVg measurements found for {chip_group} {chip_number}")
            return None

        # Convert to simple dict (we'll load CSVs directly)
        sample_files = {sample: path for sample, (path, _) in sample_data.items()}
        use_manifest = False
        print(f"✓ Found {len(sample_files)} samples in raw data")

    if not sample_files:
        print(f"✗ No IVg measurements found for {chip_group} {chip_number}")
        print(f"  Hint: Ensure manifest exists or provide --raw-root path")
        return None

    # Create figure
    plt.figure(figsize=config.figsize_voltage_sweep)

    # Sort samples alphabetically
    sorted_samples = sorted(sample_files.keys())

    # Track units for conductance mode
    units = None
    plotted_count = 0

    for sample in sorted_samples:
        file_path = sample_files[sample]

        # Load measurement data
        if use_manifest:
            # Load from staged Parquet
            d = read_measurement_parquet(file_path)
        else:
            # Load from raw CSV
            d = load_csv_measurement(file_path)

        if d is None or d.height == 0:
            print(f"⚠ Skipping sample {sample}: could not load data")
            continue

        # Ensure standard column names
        d = ensure_standard_columns(d)

        # Validate required columns
        if not {"VG", "I"} <= set(d.columns):
            print(f"⚠ Skipping sample {sample}: missing VG/I columns")
            continue

        # Plot based on mode
        if conductance:
            # Need VDS for conductance calculation
            # Try to extract from filename or use default
            vds = extract_vds_from_data(d, file_path)

            if vds is None or vds == 0:
                print(f"⚠ Skipping sample {sample}: VDS not found (required for conductance)")
                continue

            G, units = calculate_conductance(d["I"], vds)
            plt.plot(d["VG"], G, label=f"Sample {sample}", linewidth=1.5)
            plotted_count += 1
        else:
            # Plot current
            current_ua = d["I"].to_numpy() * 1e6  # A -> µA
            plt.plot(d["VG"], current_ua, label=f"Sample {sample}", linewidth=1.5)
            plotted_count += 1

    # Check if any data was plotted
    if plotted_count == 0:
        plt.close()
        print(f"✗ No plottable data found for {chip_group} {chip_number}")
        if conductance:
            print(f"  Hint: Conductance mode requires VDS metadata in measurements")
        return None

    # Formatting
    plt.xlabel("$\\rm{V_g\\ (V)}$")

    if conductance:
        plt.ylabel(f"$\\rm{{G\\ ({units})}}$")
        mode_suffix = "_G"
    else:
        plt.ylabel("$\\rm{I_{ds}\\ (\\mu A)}$")
        mode_suffix = ""

    plt.legend(ncol=2 if len(sorted_samples) > 5 else 1)
    plt.grid(False)  # IMPORTANT: No grids
    plt.tight_layout()

    # Generate output filename
    chip_name = f"{chip_group}{chip_number}".replace(" ", "").lower()
    filename = f"{chip_name}_IVg_by_sample{mode_suffix}.{config.format}"

    # Get output path (chip-first hierarchy)
    output_path = config.get_output_path(
        chip_group=chip_group,
        chip_number=chip_number,
        procedure="IVg",
        filename=filename,
        create_dirs=True  # Create directories during save
    )

    plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight')
    plt.close()

    print(f"✓ Saved: {output_path}")
    return output_path


def load_csv_measurement(csv_path: Path) -> Optional[pl.DataFrame]:
    """
    Load measurement data from raw CSV file.

    Args:
        csv_path: Path to CSV file

    Returns:
        DataFrame with measurement data, or None if loading fails
    """
    try:
        # Skip comment lines (start with #) and load data
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            in_data_section = False

            for line in f:
                if line.startswith("#\tData:") or line.startswith("#Data:"):
                    in_data_section = True
                    continue
                if in_data_section and not line.startswith("#"):
                    lines.append(line)

        if not lines:
            return None

        # Write to temp file and load with Polars
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
            tmp.write(''.join(lines))
            tmp_path = tmp.name

        df = pl.read_csv(tmp_path)

        # Clean up temp file
        Path(tmp_path).unlink()

        return df

    except Exception as e:
        print(f"⚠ Error loading {csv_path}: {e}")
        return None


def extract_vds_from_data(df: pl.DataFrame, file_path: Path) -> Optional[float]:
    """
    Try to extract VDS from measurement data or filename.

    Args:
        df: Measurement DataFrame
        file_path: Path to measurement file

    Returns:
        VDS value in volts, or None if not found
    """
    # Check if VDS column exists in data
    for col_name in ["VDS", "Vds", "vds", "VSD", "Vsd"]:
        if col_name in df.columns:
            vds_values = df[col_name].unique()
            if len(vds_values) == 1:
                return float(vds_values[0])

    # Could not extract VDS
    return None
