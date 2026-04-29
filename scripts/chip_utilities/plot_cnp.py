#!/usr/bin/env python3
"""
Quick script to visualize CNP detection for IVg measurements.

Usage:
    python3 scripts/plot_cnp.py 75              # First measurement of chip 75
    python3 scripts/plot_cnp.py 75 --seq 3      # Specific sequence number
    python3 scripts/plot_cnp.py 75 --all        # All IVg measurements
    python3 scripts/plot_cnp.py 75 --all --save # Save to figs/cnp_analysis/
"""

import sys
from pathlib import Path
import argparse
import polars as pl

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.utils import read_measurement_parquet
from src.derived.cnp_visualization import plot_cnp_detection, compare_cnp_measurements


def main():
    parser = argparse.ArgumentParser(description='Visualize CNP detection for IVg measurements')
    parser.add_argument('chip_number', type=int, help='Chip number (e.g., 75)')
    parser.add_argument('--group', default='Alisson', help='Chip group (default: Alisson)')
    parser.add_argument('--seq', type=int, help='Specific sequence number to plot')
    parser.add_argument('--all', action='store_true', help='Plot all IVg measurements')
    parser.add_argument('--max', type=int, default=10, help='Max plots when using --all (default: 10)')
    parser.add_argument('--save', action='store_true', help='Save plots instead of displaying')

    args = parser.parse_args()

    chip_name = f"{args.group}{args.chip_number}"

    # Load chip history
    history_path = Path(f"data/02_stage/chip_histories/{chip_name}_history.parquet")
    if not history_path.exists():
        print(f"❌ History not found: {history_path}")
        return 1

    history = pl.read_parquet(history_path)

    # Filter for both IVg and VVg
    ivg_vvg = history.filter(pl.col('proc').is_in(['IVg', 'VVg']))

    if ivg_vvg.height == 0:
        print(f"❌ No IVg/VVg measurements found for {chip_name}")
        return 1

    ivg_count = history.filter(pl.col('proc') == 'IVg').height
    vvg_count = history.filter(pl.col('proc') == 'VVg').height
    print(f"Found {ivg_count} IVg and {vvg_count} VVg measurements for {chip_name}")

    # Handle different modes
    if args.all:
        # Plot multiple measurements
        print(f"Plotting up to {args.max} measurements...")
        save_dir = Path("figs/cnp_analysis") if args.save else None

        compare_cnp_measurements(
            chip_number=args.chip_number,
            chip_group=args.group,
            max_plots=args.max,
            save_dir=save_dir
        )

        if save_dir:
            print(f"✓ Plots saved to {save_dir}/")

    else:
        # Plot single measurement
        if args.seq is not None:
            # Specific sequence number
            ivg_vvg_filtered = ivg_vvg.filter(pl.col('seq') == args.seq)
            if ivg_vvg_filtered.height == 0:
                print(f"❌ No IVg/VVg measurement found with seq={args.seq}")
                print(f"Available seq numbers: {ivg_vvg['seq'].to_list()}")
                return 1
            row = ivg_vvg_filtered.row(0, named=True)
        else:
            # First measurement
            row = ivg_vvg.row(0, named=True)

        print(f"Plotting {row['proc']} seq={row['seq']}, {row['datetime_local']}")

        # Load measurement
        measurement = read_measurement_parquet(Path(row['parquet_path']))

        # Prepare metadata
        metadata = {
            'run_id': row['run_id'],
            'chip_number': args.chip_number,
            'chip_group': args.group,
            'procedure': row['proc'],
            'seq_num': row['seq'],
            'extraction_version': 'v0.1.0'
        }

        # Add procedure-specific parameters
        if row['proc'] == 'IVg':
            metadata['vds_v'] = row.get('vds_v')
        elif row['proc'] == 'VVg':
            # For VVg, we need ids_v (fixed current)
            # TODO: This will be in metadata after re-staging with updated procedures.yml
            # For now, use a default value or read from CSV
            metadata['ids_v'] = row.get('ids_v', 1e-5)  # Default 10 µA if not found

        # Plot
        save_path = None
        if args.save:
            save_dir = Path("figs/cnp_analysis")
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / f"{chip_name}_seq{row['seq']:03d}_cnp.png"

        plot_cnp_detection(
            measurement,
            metadata,
            save_path=save_path,
            show=(not args.save)
        )

        if save_path:
            print(f"✓ Plot saved to {save_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
