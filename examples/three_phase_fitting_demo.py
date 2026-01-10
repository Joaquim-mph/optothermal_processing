"""
Three-Phase Fitting Demonstration

For light ITS measurements with LED OFF → ON → OFF cycles, this script:
1. Detects the three phases automatically
2. Fits each phase separately with the appropriate model
3. Visualizes all three fits together

Phases:
- PRE-DARK (LED OFF before illumination): Baseline drift/relaxation
- LIGHT (LED ON): Photoresponse buildup/plateau
- POST-DARK (LED OFF after illumination): Photoresponse decay

Usage:
    python3 examples/three_phase_fitting_demo.py --chip 67 --seq 87
    python3 examples/three_phase_fitting_demo.py --chip 81 --seq 240
"""

import numpy as np
import matplotlib.pyplot as plt
import polars as pl
from pathlib import Path
import sys
import argparse
from typing import Optional, Tuple, List, Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.utils import read_measurement_parquet
from src.derived.algorithms import fit_linear, fit_stretched_exponential

# Use scienceplots if available
try:
    plt.style.use(['science', 'no-latex'])
except:
    plt.style.use('seaborn-v0_8-darkgrid')


def detect_led_transitions(vl: np.ndarray, threshold: float = 0.1) -> Tuple[Optional[int], Optional[int]]:
    """
    Detect LED ON and OFF transitions.

    Parameters
    ----------
    vl : np.ndarray
        Laser voltage array
    threshold : float
        LED ON threshold (V)

    Returns
    -------
    tuple
        (led_on_idx, led_off_idx) or (None, None) if not found
    """
    led_state = vl > threshold

    # Find transitions
    transitions = np.diff(led_state.astype(int))
    on_edges = np.where(transitions == 1)[0] + 1   # OFF→ON
    off_edges = np.where(transitions == -1)[0] + 1  # ON→OFF

    if len(on_edges) == 0 or len(off_edges) == 0:
        return None, None

    # Find main LED pulse (longest ON period)
    if led_state[0]:
        on_edges = np.concatenate([[0], on_edges])
    if led_state[-1]:
        off_edges = np.concatenate([off_edges, [len(led_state)]])

    # Use longest LED ON segment
    led_on_durations = off_edges - on_edges
    main_pulse_idx = np.argmax(led_on_durations)

    return on_edges[main_pulse_idx], off_edges[main_pulse_idx]


def fit_three_phases(
    t: np.ndarray,
    I: np.ndarray,
    vl: np.ndarray,
    led_on_idx: int,
    led_off_idx: int
) -> Dict[str, Dict]:
    """
    Fit all three phases separately.

    Parameters
    ----------
    t : np.ndarray
        Time array
    I : np.ndarray
        Current array
    vl : np.ndarray
        Laser voltage array
    led_on_idx : int
        Index where LED turns ON
    led_off_idx : int
        Index where LED turns OFF

    Returns
    -------
    dict
        Results for each phase
    """
    results = {}

    # ========================================
    # Phase 1: PRE-DARK (before LED ON)
    # ========================================
    if led_on_idx > 50:  # Need minimum points
        t_pre = t[:led_on_idx] - t[0]
        I_pre = I[:led_on_idx]

        print(f"  PRE-DARK phase: {len(t_pre)} points, {t_pre[-1]:.1f} s duration")

        # Try both models
        try:
            linear_pre = fit_linear(t_pre, I_pre)
            results['pre_dark_linear'] = {
                'model': 'linear',
                't': t_pre,
                'I_data': I_pre,
                'I_fit': linear_pre['fitted_curve'],
                'params': linear_pre,
                'phase_name': 'PRE-DARK'
            }
            print(f"    Linear: R² = {linear_pre['r_squared']:.4f}")
        except Exception as e:
            print(f"    Linear fit failed: {e}")

        try:
            exp_pre = fit_stretched_exponential(t_pre, I_pre)
            results['pre_dark_exp'] = {
                'model': 'exponential',
                't': t_pre,
                'I_data': I_pre,
                'I_fit': exp_pre['fitted_curve'],
                'params': exp_pre,
                'phase_name': 'PRE-DARK'
            }
            print(f"    Exponential: R² = {exp_pre['r_squared']:.4f}, τ = {exp_pre['tau']:.1f} s")
        except Exception as e:
            print(f"    Exponential fit failed: {e}")

    # ========================================
    # Phase 2: LIGHT (LED ON)
    # ========================================
    if led_off_idx - led_on_idx > 50:
        t_light = t[led_on_idx:led_off_idx] - t[led_on_idx]
        I_light = I[led_on_idx:led_off_idx]

        print(f"  LIGHT phase: {len(t_light)} points, {t_light[-1]:.1f} s duration")

        # For LIGHT phase, try both models
        try:
            linear_light = fit_linear(t_light, I_light)
            results['light_linear'] = {
                'model': 'linear',
                't': t_light + (t[led_on_idx] - t[0]),  # Absolute time
                'I_data': I_light,
                'I_fit': linear_light['fitted_curve'],
                'params': linear_light,
                'phase_name': 'LIGHT'
            }
            print(f"    Linear: R² = {linear_light['r_squared']:.4f}")
        except Exception as e:
            print(f"    Linear fit failed: {e}")

        try:
            exp_light = fit_stretched_exponential(t_light, I_light)
            results['light_exp'] = {
                'model': 'exponential',
                't': t_light + (t[led_on_idx] - t[0]),  # Absolute time
                'I_data': I_light,
                'I_fit': exp_light['fitted_curve'],
                'params': exp_light,
                'phase_name': 'LIGHT'
            }
            print(f"    Exponential: R² = {exp_light['r_squared']:.4f}, τ = {exp_light['tau']:.1f} s")
        except Exception as e:
            print(f"    Exponential fit failed: {e}")

    # ========================================
    # Phase 3: POST-DARK (after LED OFF)
    # ========================================
    if len(t) - led_off_idx > 50:
        t_post = t[led_off_idx:] - t[led_off_idx]
        I_post = I[led_off_idx:]

        print(f"  POST-DARK phase: {len(t_post)} points, {t_post[-1]:.1f} s duration")

        # Try both models
        try:
            linear_post = fit_linear(t_post, I_post)
            results['post_dark_linear'] = {
                'model': 'linear',
                't': t_post + (t[led_off_idx] - t[0]),  # Absolute time
                'I_data': I_post,
                'I_fit': linear_post['fitted_curve'],
                'params': linear_post,
                'phase_name': 'POST-DARK'
            }
            print(f"    Linear: R² = {linear_post['r_squared']:.4f}")
        except Exception as e:
            print(f"    Linear fit failed: {e}")

        try:
            exp_post = fit_stretched_exponential(t_post, I_post)
            results['post_dark_exp'] = {
                'model': 'exponential',
                't': t_post + (t[led_off_idx] - t[0]),  # Absolute time
                'I_data': I_post,
                'I_fit': exp_post['fitted_curve'],
                'params': exp_post,
                'phase_name': 'POST-DARK'
            }
            print(f"    Exponential: R² = {exp_post['r_squared']:.4f}, τ = {exp_post['tau']:.1f} s")
        except Exception as e:
            print(f"    Exponential fit failed: {e}")

    return results


def plot_three_phase_analysis(
    t: np.ndarray,
    I: np.ndarray,
    vl: np.ndarray,
    results: Dict[str, Dict],
    led_on_idx: int,
    led_off_idx: int,
    chip_label: str,
    seq_num: int,
    output_dir: Path
):
    """
    Create comprehensive three-phase fitting visualization.

    Parameters
    ----------
    t : np.ndarray
        Time array
    I : np.ndarray
        Current array
    vl : np.ndarray
        Laser voltage array
    results : dict
        Fitting results from fit_three_phases
    led_on_idx : int
        LED ON index
    led_off_idx : int
        LED OFF index
    chip_label : str
        Chip label
    seq_num : int
        Sequence number
    output_dir : Path
        Output directory
    """
    t_norm = t - t[0]

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    # ========================================
    # Top: Full data with LED state
    # ========================================
    ax1 = axes[0]

    # Plot LED state
    ax1_led = ax1.twinx()
    ax1_led.fill_between(t_norm, 0, vl, alpha=0.2, color='yellow', label='LED State')
    ax1_led.set_ylabel('Laser Voltage (V)', fontsize=10, color='orange')
    ax1_led.tick_params(axis='y', labelcolor='orange')
    ax1_led.set_ylim(-0.1, max(vl.max() * 1.2, 1.0))

    # Plot current data
    plot_every = max(1, len(t_norm) // 2000)
    ax1.plot(t_norm[::plot_every], I[::plot_every] * 1e6, 'o',
             markersize=2, alpha=0.5, color='#1f77b4', label='Current Data')

    # Mark phase boundaries
    ax1.axvline(t_norm[led_on_idx], color='green', linestyle='--', linewidth=2,
                label=f'LED ON ({t_norm[led_on_idx]:.1f} s)', alpha=0.7)
    ax1.axvline(t_norm[led_off_idx], color='red', linestyle='--', linewidth=2,
                label=f'LED OFF ({t_norm[led_off_idx]:.1f} s)', alpha=0.7)

    ax1.set_ylabel('Current (µA)', fontsize=12)
    ax1.set_title(f'Three-Phase Analysis: {chip_label}, Seq {seq_num}\n(OFF → ON → OFF cycle)',
                  fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', frameon=True, fontsize=9)
    ax1.grid(False)

    # ========================================
    # Middle: Phase-by-phase fits
    # ========================================
    ax2 = axes[1]

    # Plot all data in background
    ax2.plot(t_norm, I * 1e6, 'o', markersize=1, alpha=0.3, color='lightgray', label='All Data')

    # Colors for each phase
    phase_colors = {
        'PRE-DARK': '#8B4513',   # Brown
        'LIGHT': '#FFD700',      # Gold
        'POST-DARK': '#4169E1'   # Royal Blue
    }

    # Plot best fit for each phase
    for key, result in results.items():
        if 'exp' in key:  # Use exponential fits
            color = phase_colors.get(result['phase_name'], 'black')
            label = f"{result['phase_name']} (τ={result['params']['tau']:.1f}s, R²={result['params']['r_squared']:.3f})"
            ax2.plot(result['t'], result['I_fit'] * 1e6, '-',
                    linewidth=3, color=color, label=label, alpha=0.8)

    # Mark transitions
    ax2.axvline(t_norm[led_on_idx], color='green', linestyle=':', linewidth=1.5, alpha=0.5)
    ax2.axvline(t_norm[led_off_idx], color='red', linestyle=':', linewidth=1.5, alpha=0.5)

    ax2.set_ylabel('Current (µA)', fontsize=12)
    ax2.set_title('Individual Phase Fits (Stretched Exponential)', fontsize=12)
    ax2.legend(loc='best', frameon=True, fontsize=9)
    ax2.grid(False)

    # ========================================
    # Bottom: Residuals for each phase
    # ========================================
    ax3 = axes[2]

    for key, result in results.items():
        if 'exp' in key:  # Use exponential fits
            residuals = (result['I_data'] - result['I_fit']) * 1e9
            color = phase_colors.get(result['phase_name'], 'black')
            ax3.plot(result['t'], residuals, 'o', markersize=2, alpha=0.6,
                    color=color, label=f"{result['phase_name']} (σ={np.std(residuals):.1f} nA)")

    ax3.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    ax3.axvline(t_norm[led_on_idx], color='green', linestyle=':', linewidth=1.5, alpha=0.5)
    ax3.axvline(t_norm[led_off_idx], color='red', linestyle=':', linewidth=1.5, alpha=0.5)

    ax3.set_xlabel('Time (s)', fontsize=12)
    ax3.set_ylabel('Residuals (nA)', fontsize=12)
    ax3.set_title('Fit Residuals (Data - Model)', fontsize=12)
    ax3.legend(loc='best', frameon=True, fontsize=9)
    ax3.grid(False)

    # ========================================
    # Add parameter box
    # ========================================
    param_text = "Fit Parameters:\n\n"

    for phase_name in ['PRE-DARK', 'LIGHT', 'POST-DARK']:
        param_text += f"{phase_name}:\n"

        # Find exponential result for this phase
        exp_key = f"{phase_name.lower().replace('-', '_')}_exp"
        if exp_key in results:
            params = results[exp_key]['params']
            param_text += f"  τ = {params['tau']:.1f} s\n"
            param_text += f"  β = {params['beta']:.3f}\n"
            param_text += f"  A = {params['amplitude']:.2e} A\n"
            param_text += f"  R² = {params['r_squared']:.4f}\n"
        else:
            param_text += "  (no fit)\n"
        param_text += "\n"

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.3)
    ax2.text(0.02, 0.98, param_text.strip(), transform=ax2.transAxes,
             fontsize=8, verticalalignment='top', horizontalalignment='left',
             bbox=props, family='monospace')

    plt.tight_layout()

    # Save
    output_path = output_dir / f"three_phase_{chip_label}_seq{seq_num}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved: {output_path}")

    plt.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Demonstrate three-phase fitting on real ITS data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--chip', type=int, required=True, help='Chip number')
    parser.add_argument('--seq', type=int, required=True, help='Sequence number')
    parser.add_argument('--output-dir', type=str,
                        help='Output directory (default: examples/output/three_phase)')
    parser.add_argument('--led-threshold', type=float, default=0.1,
                        help='LED ON threshold in volts (default: 0.1)')

    args = parser.parse_args()

    # Setup paths
    base_dir = Path('.').resolve()
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(__file__).parent / "output" / "three_phase"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Three-Phase Fitting Demonstration")
    print("=" * 70)

    # Load chip history
    history_dir = base_dir / "data" / "02_stage" / "chip_histories"
    pattern = f"*{args.chip}_history.parquet"
    matching_files = list(history_dir.glob(pattern))

    if len(matching_files) == 0:
        print(f"⚠ History not found for chip {args.chip}")
        return

    history = pl.read_parquet(matching_files[0])
    print(f"✓ Loaded {matching_files[0].name}")

    # Find measurement
    measurement_info = history.filter(pl.col('seq') == args.seq)

    if len(measurement_info) == 0:
        print(f"⚠ Sequence {args.seq} not found in chip {args.chip}")
        return

    measurement_info = measurement_info.to_dicts()[0]
    chip_label = f"{measurement_info['chip_group']}{measurement_info['chip_number']}"

    print(f"✓ Found measurement: {measurement_info['proc']}, {'light' if measurement_info['has_light'] else 'dark'}")

    # Load measurement data
    parquet_path = base_dir / measurement_info['parquet_path']
    data = read_measurement_parquet(parquet_path)
    print(f"✓ Loaded data: {len(data)} points")

    # Extract arrays
    t = data['t (s)'].to_numpy()
    I = data['I (A)'].to_numpy()
    vl = data['VL (V)'].to_numpy()

    # Detect LED transitions
    print("\nDetecting LED transitions...")
    led_on_idx, led_off_idx = detect_led_transitions(vl, args.led_threshold)

    if led_on_idx is None or led_off_idx is None:
        print("⚠ Could not detect LED transitions!")
        print("  This measurement may not have clear OFF → ON → OFF cycle")
        return

    print(f"✓ LED ON at index {led_on_idx} (t = {t[led_on_idx] - t[0]:.1f} s)")
    print(f"✓ LED OFF at index {led_off_idx} (t = {t[led_off_idx] - t[0]:.1f} s)")

    # Fit three phases
    print("\nFitting each phase separately...")
    results = fit_three_phases(t, I, vl, led_on_idx, led_off_idx)

    # Generate visualization
    print("\nGenerating visualization...")
    plot_three_phase_analysis(t, I, vl, results, led_on_idx, led_off_idx,
                              chip_label, args.seq, output_dir)

    print("\n" + "=" * 70)
    print("Analysis Complete")
    print("=" * 70)
    print("\nInterpretation:")
    print("  • Each phase is fitted independently")
    print("  • PRE-DARK: Baseline drift/relaxation before photoresponse")
    print("  • LIGHT: Photoresponse buildup during illumination")
    print("  • POST-DARK: Photoresponse decay after LED OFF")
    print("\n  • Different τ values indicate different dynamics")
    print("  • Check residuals to validate fit quality")
    print("=" * 70)


if __name__ == "__main__":
    main()
