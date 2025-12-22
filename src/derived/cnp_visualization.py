"""
Visualization tools for debugging and inspecting CNP detection.

Provides plotting functions to visualize:
- Resistance vs Vg with detected CNPs marked
- Sweep segments color-coded by direction
- CNP clusters and hysteresis
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import polars as pl
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

from src.core.utils import read_measurement_parquet
from src.derived.extractors.cnp_extractor import CNPExtractor


def plot_cnp_detection(
    measurement: pl.DataFrame,
    metadata: Dict[str, Any],
    extractor: Optional[CNPExtractor] = None,
    save_path: Optional[Path] = None,
    show: bool = True
) -> None:
    """
    Plot IVg/VVg measurement with detected CNPs highlighted.

    Parameters
    ----------
    measurement : pl.DataFrame
        Measurement data (from read_measurement_parquet)
    metadata : Dict[str, Any]
        Metadata dict (must include vds_v for IVg)
    extractor : Optional[CNPExtractor]
        CNP extractor to use. If None, uses default settings.
    save_path : Optional[Path]
        Path to save figure. If None, not saved.
    show : bool
        Whether to display the plot (default: True)

    Examples
    --------
    >>> from src.core.utils import read_measurement_parquet
    >>> measurement = read_measurement_parquet(parquet_path)
    >>> metadata = {'vds_v': 0.1, 'chip_number': 75, ...}
    >>> plot_cnp_detection(measurement, metadata)
    """
    if extractor is None:
        extractor = CNPExtractor()

    # Extract data based on procedure
    vg = measurement["Vg (V)"].to_numpy()
    procedure = metadata.get("procedure", "IVg")

    if procedure == "IVg":
        # IVg: Fixed Vds, measured Ids
        if "I (A)" not in measurement.columns:
            raise ValueError("I (A) column not found for IVg measurement")

        i = measurement["I (A)"].to_numpy()
        vds = metadata.get("vds_v")

        if vds is None or abs(vds) < 1e-9:
            raise ValueError("vds_v must be provided in metadata for IVg")

        # Calculate resistance
        with np.errstate(divide='ignore', invalid='ignore'):
            resistance = np.abs(vds / i)

    elif procedure == "VVg":
        # VVg: Fixed Ids, measured Vds
        vds_col = None
        for col in ["Vds (V)", "VDS (V)", "V (V)"]:
            if col in measurement.columns:
                vds_col = col
                break

        if vds_col is None:
            raise ValueError("Vds/VDS column not found for VVg measurement")

        vds = measurement[vds_col].to_numpy()
        ids = metadata.get("ids_a")

        if ids is None or abs(ids) < 1e-12:
            raise ValueError("ids_a must be provided in metadata for VVg")

        # Calculate resistance
        with np.errstate(divide='ignore', invalid='ignore'):
            resistance = np.abs(vds / ids)

    else:
        raise ValueError(f"Unsupported procedure: {procedure}")

    # Remove infinities/NaNs
    valid_mask = np.isfinite(resistance)
    vg = vg[valid_mask]
    resistance = resistance[valid_mask]

    # Run extractor
    result = extractor.extract(measurement, metadata)

    if result is None:
        print("CNP extraction failed")
        return

    # Parse results
    details = json.loads(result.value_json)

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # === Top plot: Resistance vs Vg with segments ===
    # Segment the sweep for coloring
    segments = extractor._segment_sweep(vg)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for i_seg, seg in enumerate(segments):
        if len(seg) > 0:
            color = colors[i_seg % len(colors)]
            direction = "→" if vg[seg[-1]] > vg[seg[0]] else "←"
            ax1.plot(vg[seg], resistance[seg], 'o-', markersize=3, alpha=0.7,
                     color=color, label=f'Segment {i_seg+1} {direction}')

    # Mark detected CNPs
    for cnp in details["all_cnps"]:
        marker = 'D' if cnp['direction'] == 'forward' else 's'
        color = 'red' if cnp['direction'] == 'forward' else 'blue'
        ax1.plot(cnp['vg'], cnp['r'], marker, markersize=12,
                 markeredgecolor='black', markeredgewidth=2,
                 color=color, label=f'CNP ({cnp["direction"]})',
                 zorder=10)

    # Mark average CNP
    ax1.axvline(result.value_float, color='green', linestyle='--',
                linewidth=2, alpha=0.7, label=f'Average CNP ({result.value_float:.3f}V)')

    ax1.set_ylabel('Resistance (Ω)', fontsize=12)
    ax1.set_title(
        f'CNP Detection - {metadata.get("chip_group", "")}{metadata.get("chip_number", "")}\n'
        f'CNP={result.value_float:.3f}V, {details["n_clusters"]} cluster(s), '
        f'Confidence={result.confidence:.2f}',
        fontsize=14, fontweight='bold'
    )
    ax1.legend(loc='best', fontsize=9, ncol=2)
    ax1.grid(True, alpha=0.3)
    ax1.set_yscale('log')

    # === Bottom plot: Current/Voltage vs Vg (depends on procedure) ===
    if procedure == "IVg":
        # Plot current for IVg
        i_measured = measurement["I (A)"].to_numpy()[valid_mask]

        for i_seg, seg in enumerate(segments):
            if len(seg) > 0:
                color = colors[i_seg % len(colors)]
                ax2.plot(vg[seg], np.abs(i_measured[seg]), 'o-', markersize=3,
                         alpha=0.7, color=color)

        # Mark CNPs
        for cnp in details["all_cnps"]:
            marker = 'D' if cnp['direction'] == 'forward' else 's'
            color = 'red' if cnp['direction'] == 'forward' else 'blue'
            idx = np.argmin(np.abs(vg - cnp['vg']))
            ax2.plot(cnp['vg'], np.abs(i_measured[idx]), marker, markersize=12,
                     markeredgecolor='black', markeredgewidth=2,
                     color=color, zorder=10)

        ylabel = '|Current| (A)'
        title = 'Current vs Gate Voltage (|Ids|)'

    elif procedure == "VVg":
        # Plot voltage for VVg
        vds_measured = measurement[vds_col].to_numpy()[valid_mask]

        for i_seg, seg in enumerate(segments):
            if len(seg) > 0:
                color = colors[i_seg % len(colors)]
                ax2.plot(vg[seg], np.abs(vds_measured[seg]), 'o-', markersize=3,
                         alpha=0.7, color=color)

        # Mark CNPs
        for cnp in details["all_cnps"]:
            marker = 'D' if cnp['direction'] == 'forward' else 's'
            color = 'red' if cnp['direction'] == 'forward' else 'blue'
            idx = np.argmin(np.abs(vg - cnp['vg']))
            ax2.plot(cnp['vg'], np.abs(vds_measured[idx]), marker, markersize=12,
                     markeredgecolor='black', markeredgewidth=2,
                     color=color, zorder=10)

        ylabel = '|Voltage| (V)'
        title = 'Voltage vs Gate Voltage (|Vds|)'

    ax2.axvline(result.value_float, color='green', linestyle='--',
                linewidth=2, alpha=0.7)

    ax2.set_xlabel('Gate Voltage Vg (V)', fontsize=12)
    ax2.set_ylabel(ylabel, fontsize=12)
    ax2.set_title(title, fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')

    # Add info text
    info_text = f'Flags: {result.flags or "None"}\n'
    if details["n_clusters"] > 1:
        info_text += f'Hysteresis: {details["cnp_spread_v"]:.3f}V\n'
        info_text += 'Clusters:\n'
        for cluster in details["clusters"]:
            info_text += f'  {cluster["cluster_id"]}: {cluster["vg_mean"]:.3f}±{cluster["vg_std"]:.3f}V\n'

    ax2.text(0.02, 0.98, info_text, transform=ax2.transAxes,
             fontsize=10, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {save_path}")

    if show:
        plt.show()
    else:
        plt.close()


def compare_cnp_measurements(
    chip_number: int,
    chip_group: str = "Alisson",
    max_plots: int = 6,
    save_dir: Optional[Path] = None
) -> None:
    """
    Compare CNP detection across multiple measurements for a chip.

    Parameters
    ----------
    chip_number : int
        Chip number
    chip_group : str
        Chip group name (default: "Alisson")
    max_plots : int
        Maximum number of measurements to plot (default: 6)
    save_dir : Optional[Path]
        Directory to save plots. If None, displays interactively.

    Examples
    --------
    >>> compare_cnp_measurements(75, save_dir=Path("figs/cnp_analysis"))
    """
    import polars as pl
    from pathlib import Path

    # Load chip history
    history_path = Path(f"data/02_stage/chip_histories/{chip_group}{chip_number}_history.parquet")
    if not history_path.exists():
        print(f"History not found: {history_path}")
        return

    history = pl.read_parquet(history_path)

    # Filter IVg measurements
    ivg = history.filter(pl.col('proc') == 'IVg').head(max_plots)

    if ivg.height == 0:
        print(f"No IVg measurements found for {chip_group}{chip_number}")
        return

    print(f"Comparing {ivg.height} IVg measurements for {chip_group}{chip_number}")

    extractor = CNPExtractor()

    for i, row in enumerate(ivg.iter_rows(named=True)):
        parquet_path = Path(row['parquet_path'])

        print(f"\n[{i+1}/{ivg.height}] Processing seq={row['seq']}, {row['datetime_local']}")

        try:
            measurement = read_measurement_parquet(parquet_path)

            metadata = {
                'run_id': row['run_id'],
                'chip_number': chip_number,
                'chip_group': chip_group,
                'procedure': 'IVg',
                'seq_num': row['seq'],
                'vds_v': row['vds_v'],
                'extraction_version': 'v0.1.0'
            }

            save_path = None
            if save_dir:
                save_dir = Path(save_dir)
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / f"{chip_group}{chip_number}_seq{row['seq']:03d}_cnp.png"

            plot_cnp_detection(
                measurement,
                metadata,
                extractor=extractor,
                save_path=save_path,
                show=(save_dir is None)  # Only show if not saving
            )

        except Exception as e:
            print(f"  Error: {e}")
            continue

    if save_dir:
        print(f"\nSaved {ivg.height} plots to {save_dir}")
