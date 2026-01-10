"""
Compare Linear vs Stretched Exponential Models

This script generates synthetic data and fits both models to demonstrate
when each model is appropriate.

Scenarios:
1. Pure Linear Drift - Linear model is better
2. Pure Exponential Relaxation - Stretched exponential is better
3. Mixed Behavior - Both models have limitations
4. Noisy Data - Robustness comparison
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.derived.algorithms import fit_linear, fit_stretched_exponential

# Use scienceplots if available
try:
    plt.style.use(['science', 'no-latex'])
except:
    plt.style.use('seaborn-v0_8-darkgrid')


def generate_linear_drift(t, drift_rate=1e-9, baseline=1e-6, noise_level=1e-10):
    """
    Generate linear drift data: I(t) = I₀ + drift_rate * t

    Parameters
    ----------
    t : np.ndarray
        Time array (seconds)
    drift_rate : float
        Drift rate (A/s)
    baseline : float
        Initial current (A)
    noise_level : float
        Gaussian noise std (A)

    Returns
    -------
    np.ndarray
        Current with drift and noise
    """
    I_clean = baseline + drift_rate * t
    noise = np.random.normal(0, noise_level, len(t))
    return I_clean + noise


def generate_exponential_relaxation(t, baseline=1e-6, amplitude=5e-7,
                                     tau=30.0, beta=0.7, noise_level=1e-10):
    """
    Generate stretched exponential relaxation: I(t) = I₀ + A * exp(-(t/τ)^β)

    Parameters
    ----------
    t : np.ndarray
        Time array (seconds)
    baseline : float
        Final baseline current (A)
    amplitude : float
        Photoresponse amplitude (A)
    tau : float
        Relaxation time (s)
    beta : float
        Stretching exponent
    noise_level : float
        Gaussian noise std (A)

    Returns
    -------
    np.ndarray
        Current with relaxation and noise
    """
    I_clean = baseline + amplitude * np.exp(-((t / tau) ** beta))
    noise = np.random.normal(0, noise_level, len(t))
    return I_clean + noise


def generate_mixed_behavior(t, baseline=1e-6, amplitude=5e-7, tau=30.0,
                            beta=0.7, drift_rate=5e-10, noise_level=1e-10):
    """
    Generate data with both drift and relaxation.

    This is realistic for devices with:
    - Photoresponse relaxation (exponential)
    - Underlying baseline drift (linear)
    """
    # Exponential component
    I_relaxation = amplitude * np.exp(-((t / tau) ** beta))

    # Linear drift component
    I_drift = drift_rate * t

    # Combined
    I_clean = baseline + I_relaxation + I_drift
    noise = np.random.normal(0, noise_level, len(t))
    return I_clean + noise


def plot_comparison(t, I_data, title, scenario_label, output_dir):
    """
    Fit both models and plot comparison.

    Parameters
    ----------
    t : np.ndarray
        Time array
    I_data : np.ndarray
        Current data
    title : str
        Plot title
    scenario_label : str
        Scenario label for filename
    output_dir : Path
        Output directory
    """
    # Normalize time to start at 0
    t_norm = t - t[0]

    # Fit linear model
    linear_result = fit_linear(t_norm, I_data)
    I_linear = linear_result['fitted_curve']

    # Fit stretched exponential
    exp_result = fit_stretched_exponential(t_norm, I_data)
    I_exp = exp_result['fitted_curve']

    # Create figure with 2 subplots
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # ========================================
    # Top plot: Data + both fits
    # ========================================
    ax1 = axes[0]

    # Data points
    ax1.plot(t_norm, I_data * 1e6, 'o', color='#1f77b4', markersize=3,
             alpha=0.6, label='Data')

    # Linear fit
    ax1.plot(t_norm, I_linear * 1e6, '-', color='#ff7f0e', linewidth=2,
             label=f'Linear (R²={linear_result["r_squared"]:.4f})')

    # Exponential fit
    ax1.plot(t_norm, I_exp * 1e6, '-', color='#2ca02c', linewidth=2,
             label=f'Stretched Exp (R²={exp_result["r_squared"]:.4f})')

    ax1.set_ylabel('Current (µA)')
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.legend(loc='best', frameon=True, fancybox=True, shadow=True)
    ax1.grid(False)

    # ========================================
    # Bottom plot: Residuals
    # ========================================
    ax2 = axes[1]

    residuals_linear = (I_data - I_linear) * 1e9
    residuals_exp = (I_data - I_exp) * 1e9

    ax2.plot(t_norm, residuals_linear, 'o', color='#ff7f0e', markersize=3,
             alpha=0.6, label=f'Linear (σ={np.std(residuals_linear):.2f} nA)')
    ax2.plot(t_norm, residuals_exp, 's', color='#2ca02c', markersize=3,
             alpha=0.6, label=f'Stretched Exp (σ={np.std(residuals_exp):.2f} nA)')
    ax2.axhline(0, color='black', linestyle='--', linewidth=1, alpha=0.5)

    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Residuals (nA)')
    ax2.set_title('Fit Residuals', fontsize=12)
    ax2.legend(loc='best', frameon=True, fancybox=True, shadow=True)
    ax2.grid(False)

    # ========================================
    # Add text box with fit parameters
    # ========================================
    textstr = f"""
    Linear Model: I = I₀ + a·t
    • Slope (a): {linear_result['slope']:.2e} A/s
    • Intercept (I₀): {linear_result['intercept']:.2e} A
    • R²: {linear_result['r_squared']:.4f}

    Stretched Exponential: I = I₀ + A·exp(-(t/τ)^β)
    • Baseline (I₀): {exp_result['baseline']:.2e} A
    • Amplitude (A): {exp_result['amplitude']:.2e} A
    • Tau (τ): {exp_result['tau']:.2f} s
    • Beta (β): {exp_result['beta']:.3f}
    • R²: {exp_result['r_squared']:.4f}
    • Converged: {exp_result['converged']}
    """

    props = dict(boxstyle='round', facecolor='wheat', alpha=0.3)
    ax1.text(0.98, 0.02, textstr.strip(), transform=ax1.transAxes,
             fontsize=8, verticalalignment='bottom', horizontalalignment='right',
             bbox=props, family='monospace')

    plt.tight_layout()

    # Save
    output_path = output_dir / f"model_comparison_{scenario_label}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")

    plt.close()

    return linear_result, exp_result


def main():
    """Generate all comparison scenarios."""

    # Create output directory
    output_dir = Path(__file__).parent / "output" / "model_comparisons"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Comparing Linear vs Stretched Exponential Models")
    print("=" * 70)

    # Common parameters
    np.random.seed(42)  # Reproducible results

    # ========================================
    # Scenario 1: Pure Linear Drift
    # ========================================
    print("\n[1/4] Scenario 1: Pure Linear Drift")
    print("     Expected: Linear model should fit better (higher R²)")

    t1 = np.linspace(0, 300, 1000)  # 5 minutes
    I1 = generate_linear_drift(t1, drift_rate=2e-9, baseline=1e-6, noise_level=5e-10)

    linear_r2, exp_r2 = plot_comparison(
        t1, I1,
        title="Scenario 1: Pure Linear Drift\n(Baseline instability, no photoresponse)",
        scenario_label="1_linear_drift",
        output_dir=output_dir
    )

    print(f"     Linear R² = {linear_r2['r_squared']:.5f}")
    print(f"     Exponential R² = {exp_r2['r_squared']:.5f}")
    if linear_r2['r_squared'] > exp_r2['r_squared']:
        print("     ✓ Linear model is better!")

    # ========================================
    # Scenario 2: Pure Exponential Relaxation
    # ========================================
    print("\n[2/4] Scenario 2: Pure Exponential Relaxation")
    print("     Expected: Stretched exponential should fit better")

    t2 = np.linspace(0, 150, 1000)  # 2.5 minutes
    I2 = generate_exponential_relaxation(
        t2, baseline=1.2e-6, amplitude=6e-7, tau=35.0, beta=0.68, noise_level=5e-10
    )

    linear_r2, exp_r2 = plot_comparison(
        t2, I2,
        title="Scenario 2: Pure Exponential Relaxation\n(Photoresponse decay after LED OFF)",
        scenario_label="2_exponential_relaxation",
        output_dir=output_dir
    )

    print(f"     Linear R² = {linear_r2['r_squared']:.5f}")
    print(f"     Exponential R² = {exp_r2['r_squared']:.5f}")
    if exp_r2['r_squared'] > linear_r2['r_squared']:
        print("     ✓ Exponential model is better!")

    # ========================================
    # Scenario 3: Mixed Behavior
    # ========================================
    print("\n[3/4] Scenario 3: Mixed Behavior (Drift + Relaxation)")
    print("     Expected: Neither model perfect, but exponential closer")

    t3 = np.linspace(0, 200, 1000)
    I3 = generate_mixed_behavior(
        t3, baseline=1e-6, amplitude=5e-7, tau=40.0, beta=0.7,
        drift_rate=8e-10, noise_level=8e-10
    )

    linear_r2, exp_r2 = plot_comparison(
        t3, I3,
        title="Scenario 3: Mixed Behavior\n(Photoresponse relaxation + baseline drift)",
        scenario_label="3_mixed_behavior",
        output_dir=output_dir
    )

    print(f"     Linear R² = {linear_r2['r_squared']:.5f}")
    print(f"     Exponential R² = {exp_r2['r_squared']:.5f}")
    print("     → Both models have systematic residuals")
    print("     → Need combined model: I = I₀ + A·exp(-(t/τ)^β) + drift·t")

    # ========================================
    # Scenario 4: High Noise
    # ========================================
    print("\n[4/4] Scenario 4: High Noise (Robustness Test)")
    print("     Expected: Both models should still converge")

    t4 = np.linspace(0, 150, 500)  # Fewer points
    I4 = generate_exponential_relaxation(
        t4, baseline=1.2e-6, amplitude=4e-7, tau=30.0, beta=0.75, noise_level=3e-9
    )  # 10x higher noise

    linear_r2, exp_r2 = plot_comparison(
        t4, I4,
        title="Scenario 4: High Noise\n(Testing robustness with SNR ≈ 10)",
        scenario_label="4_high_noise",
        output_dir=output_dir
    )

    print(f"     Linear R² = {linear_r2['r_squared']:.5f}")
    print(f"     Exponential R² = {exp_r2['r_squared']:.5f}")
    if exp_r2['converged']:
        print("     ✓ Exponential fit converged despite noise!")

    # ========================================
    # Summary
    # ========================================
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("""
    Use LINEAR MODEL when:
    ✓ Data shows monotonic drift (baseline instability)
    ✓ No time-dependent relaxation
    ✓ Fast computation needed (analytical solution)
    ✓ Examples: Dark ITS drift, temperature drift

    Use STRETCHED EXPONENTIAL when:
    ✓ Data shows relaxation/decay behavior
    ✓ Photoresponse dynamics (LED ON/OFF transitions)
    ✓ Carrier trapping/detrapping processes
    ✓ Examples: Post-illumination decay, gate hysteresis recovery

    Need COMBINED MODEL when:
    ⚠ Both drift AND relaxation present
    ⚠ Implement: I = I₀ + A·exp(-(t/τ)^β) + drift·t
    ⚠ Use Levenberg-Marquardt with 5 parameters
    """)

    print(f"\n✓ All plots saved to: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
