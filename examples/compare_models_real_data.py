"""
Compare Linear vs Stretched Exponential Models on Real Lab Data

This script loads actual staged measurements from chip histories and compares
both fitting models to demonstrate which works better for different scenarios.

Usage:
    # Analyze specific chip (auto-selects interesting measurements)
    python3 examples/compare_models_real_data.py --chip 67

    # Analyze specific sequences
    python3 examples/compare_models_real_data.py --chip 67 --dark-seq 10 --light-seq 52

    # Analyze all available chips
    python3 examples/compare_models_real_data.py --all-chips

    # Specify output directory
    python3 examples/compare_models_real_data.py --chip 81 --output-dir /tmp/comparisons
"""

import numpy as np
import matplotlib.pyplot as plt
import polars as pl
from pathlib import Path
import sys
import argparse
from typing import Optional, Tuple, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.utils import read_measurement_parquet
from src.derived.algorithms import fit_linear, fit_stretched_exponential

# Use scienceplots if available
try:
    plt.style.use(['science', 'no-latex'])
except:
    plt.style.use('seaborn-v0_8-darkgrid')


def load_chip_history(base_dir: Path, chip_number: int) -> Optional[pl.DataFrame]:
    """
    Load chip history from staged data.

    Parameters
    ----------
    base_dir : Path
        Project base directory
    chip_number : int
        Chip number

    Returns
    -------
    pl.DataFrame or None
        Chip history or None if not found
    """
    history_dir = base_dir / "data" / "02_stage" / "chip_histories"

    # Try to find history file by chip number (handles ChipGroup prefix)
    pattern = f"*{chip_number}_history.parquet"
    matching_files = list(history_dir.glob(pattern))

    if len(matching_files) == 0:
        print(f"⚠ History not found for chip {chip_number}")
        print(f"   Searched: {history_dir / pattern}")
        return None

    if len(matching_files) > 1:
        print(f"⚠ Multiple histories found for chip {chip_number}:")
        for f in matching_files:
            print(f"   - {f.name}")
        print(f"   Using: {matching_files[0].name}")

    history_path = matching_files[0]
    history = pl.read_parquet(history_path)
    print(f"✓ Loaded {history_path.name}: {len(history)} measurements")

    return history


def find_good_dark_its(history: pl.DataFrame) -> Optional[dict]:
    """
    Find a good dark ITS measurement (likely linear drift).

    Parameters
    ----------
    history : pl.DataFrame
        Chip history

    Returns
    -------
    dict or None
        Row as dict with measurement info
    """
    # Filter for dark It measurements
    dark_its = history.filter(
        (pl.col('proc').is_in(['It', 'ITS', 'ITt'])) &
        (~pl.col('has_light'))  # has_light is False for dark
    )

    if len(dark_its) == 0:
        return None

    # Prefer longer measurements
    dark_its = dark_its.sort('seq', descending=True)

    return dark_its.head(1).to_dicts()[0]


def find_good_light_its(history: pl.DataFrame) -> Optional[dict]:
    """
    Find a good light ITS measurement (likely exponential relaxation).

    Parameters
    ----------
    history : pl.DataFrame
        Chip history

    Returns
    -------
    dict or None
        Row as dict with measurement info
    """
    # Filter for light It measurements
    light_its = history.filter(
        (pl.col('proc').is_in(['It', 'ITS', 'ITt'])) &
        (pl.col('has_light'))  # has_light is True for light
    )

    if len(light_its) == 0:
        return None

    # Prefer measurements with reasonable duration
    light_its = light_its.sort('seq', descending=True)

    return light_its.head(1).to_dicts()[0]


def get_measurement_by_seq(history: pl.DataFrame, seq_num: int) -> Optional[dict]:
    """
    Get specific measurement by sequence number.

    Parameters
    ----------
    history : pl.DataFrame
        Chip history
    seq_num : int
        Sequence number

    Returns
    -------
    dict or None
        Row as dict or None if not found
    """
    result = history.filter(pl.col('seq') == seq_num)

    if len(result) == 0:
        return None

    return result.to_dicts()[0]


def plot_real_data_comparison(
    measurement_info: dict,
    base_dir: Path,
    title: str,
    scenario_label: str,
    output_dir: Path
) -> Tuple[dict, dict]:
    """
    Load real measurement, fit both models, and plot comparison.

    Parameters
    ----------
    measurement_info : dict
        Measurement metadata from history
    base_dir : Path
        Project base directory
    title : str
        Plot title
    scenario_label : str
        Label for filename
    output_dir : Path
        Output directory

    Returns
    -------
    tuple
        (linear_result, exp_result)
    """
    # Load measurement data
    parquet_path = base_dir / measurement_info['parquet_path']

    if not parquet_path.exists():
        print(f"⚠ Measurement not found: {parquet_path}")
        return None, None

    data = read_measurement_parquet(parquet_path)
    print(f"  Loaded measurement: {len(data)} points")

    # Extract time and current
    time_col = 't (s)'
    current_col = 'I (A)'

    if time_col not in data.columns or current_col not in data.columns:
        print(f"⚠ Missing required columns")
        return None, None

    t = data[time_col].to_numpy()
    I_data = data[current_col].to_numpy()

    # Normalize time to start at 0
    t_norm = t - t[0]
    duration = t_norm[-1]

    print(f"  Duration: {duration:.1f} s")
    print(f"  Current range: {I_data.min()*1e6:.2f} to {I_data.max()*1e6:.2f} µA")

    # Fit linear model
    print("  Fitting linear model...")
    linear_result = fit_linear(t_norm, I_data)
    I_linear = linear_result['fitted_curve']

    # Fit stretched exponential
    print("  Fitting stretched exponential...")
    try:
        exp_result = fit_stretched_exponential(t_norm, I_data)
        I_exp = exp_result['fitted_curve']
    except Exception as e:
        print(f"  ⚠ Exponential fit failed: {e}")
        exp_result = None
        I_exp = np.zeros_like(I_data)

    # Create figure with 2 subplots
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    # ========================================
    # Top plot: Data + both fits
    # ========================================
    ax1 = axes[0]

    # Data points (downsample if too many for clarity)
    plot_every = max(1, len(t_norm) // 2000)
    ax1.plot(t_norm[::plot_every], I_data[::plot_every] * 1e6, 'o',
             color='#1f77b4', markersize=2, alpha=0.5, label='Real Data')

    # Linear fit
    ax1.plot(t_norm, I_linear * 1e6, '-', color='#ff7f0e', linewidth=2.5,
             label=f'Linear (R²={linear_result["r_squared"]:.4f})')

    # Exponential fit
    if exp_result is not None:
        ax1.plot(t_norm, I_exp * 1e6, '-', color='#2ca02c', linewidth=2.5,
                 label=f'Stretched Exp (R²={exp_result["r_squared"]:.4f})')

    ax1.set_ylabel('Current (µA)', fontsize=12)
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.legend(loc='best', frameon=True, fancybox=True, shadow=True, fontsize=10)
    ax1.grid(False)

    # ========================================
    # Bottom plot: Residuals
    # ========================================
    ax2 = axes[1]

    residuals_linear = (I_data - I_linear) * 1e9

    ax2.plot(t_norm[::plot_every], residuals_linear[::plot_every], 'o',
             color='#ff7f0e', markersize=2, alpha=0.5,
             label=f'Linear (σ={np.std(residuals_linear):.2f} nA)')

    if exp_result is not None:
        residuals_exp = (I_data - I_exp) * 1e9
        ax2.plot(t_norm[::plot_every], residuals_exp[::plot_every], 's',
                 color='#2ca02c', markersize=2, alpha=0.5,
                 label=f'Stretched Exp (σ={np.std(residuals_exp):.2f} nA)')

    ax2.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)

    ax2.set_xlabel('Time (s)', fontsize=12)
    ax2.set_ylabel('Residuals (nA)', fontsize=12)
    ax2.set_title('Fit Residuals (Data - Model)', fontsize=12)
    ax2.legend(loc='best', frameon=True, fancybox=True, shadow=True, fontsize=10)
    ax2.grid(False)

    # ========================================
    # Add text box with fit parameters
    # ========================================
    if exp_result is not None:
        textstr = f"""
Linear Model: I = I₀ + a·t
• Slope (a): {linear_result['slope']:.2e} A/s
• Intercept (I₀): {linear_result['intercept']:.2e} A
• R²: {linear_result['r_squared']:.5f}

Stretched Exponential: I = I₀ + A·exp(-(t/τ)^β)
• Baseline (I₀): {exp_result['baseline']:.2e} A
• Amplitude (A): {exp_result['amplitude']:.2e} A
• Tau (τ): {exp_result['tau']:.2f} s
• Beta (β): {exp_result['beta']:.3f}
• R²: {exp_result['r_squared']:.5f}
• Converged: {exp_result['converged']}
• Iterations: {exp_result['n_iterations']}
        """
    else:
        textstr = f"""
Linear Model: I = I₀ + a·t
• Slope (a): {linear_result['slope']:.2e} A/s
• Intercept (I₀): {linear_result['intercept']:.2e} A
• R²: {linear_result['r_squared']:.5f}

Stretched Exponential: FAILED TO CONVERGE
        """

    # Add measurement metadata
    light_status = "light" if measurement_info.get('has_light', False) else "dark"
    textstr += f"""
Measurement Info:
• Chip: {measurement_info['chip_group']}{measurement_info['chip_number']}
• Seq: {measurement_info['seq']}
• Procedure: {measurement_info['proc']}
• Light: {light_status}
• Duration: {duration:.1f} s
• Points: {len(t_norm)}
    """

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.3)
    ax1.text(0.98, 0.02, textstr.strip(), transform=ax1.transAxes,
             fontsize=7, verticalalignment='bottom', horizontalalignment='right',
             bbox=props, family='monospace')

    plt.tight_layout()

    # Save
    chip_label = f"{measurement_info['chip_group']}{measurement_info['chip_number']}"
    output_path = output_dir / f"real_data_{chip_label}_{scenario_label}_seq{measurement_info['seq']}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")

    plt.close()

    return linear_result, exp_result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare linear vs stretched exponential models on real data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--chip', type=int, help='Chip number to analyze')
    parser.add_argument('--all-chips', action='store_true',
                        help='Analyze all available chips')
    parser.add_argument('--dark-seq', type=int,
                        help='Specific dark ITS sequence number')
    parser.add_argument('--light-seq', type=int,
                        help='Specific light ITS sequence number')
    parser.add_argument('--output-dir', type=str,
                        help='Output directory (default: examples/output/real_comparisons)')
    parser.add_argument('--base-dir', type=str, default='.',
                        help='Project base directory (default: current directory)')

    args = parser.parse_args()

    # Setup paths
    base_dir = Path(args.base_dir).resolve()
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(__file__).parent / "output" / "real_comparisons"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Comparing Models on Real Lab Data")
    print("=" * 70)

    # Determine which chips to analyze
    if args.all_chips:
        history_dir = base_dir / "data" / "02_stage" / "chip_histories"
        chip_files = list(history_dir.glob("*_history.parquet"))
        # Extract chip numbers from filenames like "Alisson67_history.parquet"
        chip_numbers = []
        for f in chip_files:
            # Extract number from filename (handles ChipGroup prefix)
            parts = f.stem.replace('_history', '').split('_')
            # Try to find numeric part
            for part in parts:
                # Check if it contains digits
                num_str = ''.join(c for c in part if c.isdigit())
                if num_str:
                    chip_numbers.append(int(num_str))
                    break
        chip_numbers = sorted(set(chip_numbers))  # Remove duplicates
        print(f"\nFound {len(chip_numbers)} chips: {chip_numbers}")
    elif args.chip:
        chip_numbers = [args.chip]
    else:
        print("Error: Must specify --chip or --all-chips")
        parser.print_help()
        return

    # Process each chip
    for chip_num in sorted(chip_numbers):
        print(f"\n{'='*70}")
        print(f"Analyzing Chip {chip_num}")
        print(f"{'='*70}")

        # Load history
        history = load_chip_history(base_dir, chip_num)
        if history is None:
            continue

        # ========================================
        # Dark ITS (expect linear drift)
        # ========================================
        print("\n[1/2] Dark ITS Measurement (Testing Linear Model)")

        if args.dark_seq:
            dark_measurement = get_measurement_by_seq(history, args.dark_seq)
            if dark_measurement is None:
                print(f"  ⚠ Sequence {args.dark_seq} not found")
            else:
                print(f"  Using specified sequence: {args.dark_seq}")
        else:
            dark_measurement = find_good_dark_its(history)
            if dark_measurement:
                print(f"  Auto-selected sequence: {dark_measurement['seq']}")

        if dark_measurement:
            linear_r2, exp_r2 = plot_real_data_comparison(
                dark_measurement,
                base_dir,
                title=f"Dark ITS: Chip {chip_num}, Seq {dark_measurement['seq']}\n(Baseline drift analysis)",
                scenario_label="dark_its",
                output_dir=output_dir
            )

            if linear_r2 and exp_r2:
                print(f"\n  Results:")
                print(f"    Linear R² = {linear_r2['r_squared']:.5f}")
                print(f"    Exponential R² = {exp_r2['r_squared']:.5f}")

                if linear_r2['r_squared'] > exp_r2['r_squared']:
                    print(f"    ✓ Linear model is better (drift dominates)")
                else:
                    print(f"    → Exponential better (may have relaxation component)")
        else:
            print("  ⚠ No dark ITS measurements found")

        # ========================================
        # Light ITS (expect exponential relaxation)
        # ========================================
        print("\n[2/2] Light ITS Measurement (Testing Exponential Model)")

        if args.light_seq:
            light_measurement = get_measurement_by_seq(history, args.light_seq)
            if light_measurement is None:
                print(f"  ⚠ Sequence {args.light_seq} not found")
            else:
                print(f"  Using specified sequence: {args.light_seq}")
        else:
            light_measurement = find_good_light_its(history)
            if light_measurement:
                print(f"  Auto-selected sequence: {light_measurement['seq']}")

        if light_measurement:
            linear_r2, exp_r2 = plot_real_data_comparison(
                light_measurement,
                base_dir,
                title=f"Light ITS: Chip {chip_num}, Seq {light_measurement['seq']}\n(Photoresponse relaxation analysis)",
                scenario_label="light_its",
                output_dir=output_dir
            )

            if linear_r2 and exp_r2:
                print(f"\n  Results:")
                print(f"    Linear R² = {linear_r2['r_squared']:.5f}")
                print(f"    Exponential R² = {exp_r2['r_squared']:.5f}")

                if exp_r2['r_squared'] > linear_r2['r_squared']:
                    print(f"    ✓ Exponential model is better (relaxation dominates)")
                else:
                    print(f"    → Linear better (may be pure drift)")
        else:
            print("  ⚠ No light ITS measurements found")

    # Summary
    print("\n" + "=" * 70)
    print("Analysis Complete")
    print("=" * 70)
    print(f"\n✓ All plots saved to: {output_dir}")
    print("\nInterpretation Guide:")
    print("  • R² > 0.99: Excellent fit, model matches data well")
    print("  • R² > 0.95: Good fit, minor deviations")
    print("  • R² > 0.90: Acceptable fit, some systematic error")
    print("  • R² < 0.90: Poor fit, wrong model or mixed behavior")
    print("\n  • Random residuals: Good model choice")
    print("  • Systematic residuals: Wrong model or missing physics")
    print("=" * 70)


if __name__ == "__main__":
    main()
