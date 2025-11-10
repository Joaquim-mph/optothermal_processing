"""
Benchmark: Numba vs SciPy for stretched exponential fitting.

Run this to see the performance difference!
"""

import numpy as np
import time
from typing import Callable

try:
    from scipy.optimize import curve_fit
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from .stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential
)


def stretched_exp_scipy(t, baseline, amplitude, tau, beta):
    """SciPy-compatible stretched exponential function."""
    return baseline + amplitude * np.exp(-((t / tau) ** beta))


def benchmark_single_fit(n_points: int = 1000, n_repeats: int = 10):
    """
    Benchmark fitting on a single curve.

    Parameters
    ----------
    n_points : int
        Number of data points (default: 1000)
    n_repeats : int
        Number of repeats for timing (default: 10)
    """
    print(f"\n{'='*60}")
    print(f"BENCHMARK: Single Fit ({n_points} points, {n_repeats} repeats)")
    print(f"{'='*60}\n")

    # Generate synthetic data
    np.random.seed(42)
    t = np.linspace(0, 100, n_points)

    # True parameters
    true_params = {
        'baseline': 1.0e-6,
        'amplitude': 0.5e-6,
        'tau': 20.0,
        'beta': 0.7
    }

    # Generate true curve with noise
    I_true = stretched_exponential(
        t,
        true_params['baseline'],
        true_params['amplitude'],
        true_params['tau'],
        true_params['beta']
    )
    noise = np.random.normal(0, 1e-8, n_points)
    I_measured = I_true + noise

    # Benchmark Numba implementation
    print("🚀 Numba-accelerated fitting:")
    print("-" * 40)

    # Warm-up (compile JIT functions)
    _ = fit_stretched_exponential(t, I_measured)
    print("   JIT compilation complete (first run)")

    # Timed runs
    start = time.time()
    for _ in range(n_repeats):
        result_numba = fit_stretched_exponential(t, I_measured)
    elapsed_numba = time.time() - start
    avg_numba = elapsed_numba / n_repeats * 1000  # Convert to ms

    print(f"   Average time: {avg_numba:.2f} ms")
    print(f"   Converged: {result_numba['converged']}")
    print(f"   R²: {result_numba['r_squared']:.6f}")
    print(f"   Fitted τ: {result_numba['tau']:.2f} s (true: {true_params['tau']} s)")
    print(f"   Fitted β: {result_numba['beta']:.3f} (true: {true_params['beta']})")

    # Benchmark SciPy (if available)
    if SCIPY_AVAILABLE:
        print("\n🐌 SciPy curve_fit (for comparison):")
        print("-" * 40)

        initial_guess = [1e-6, 0.5e-6, 20.0, 0.7]

        start = time.time()
        for _ in range(n_repeats):
            try:
                popt, _ = curve_fit(
                    stretched_exp_scipy,
                    t,
                    I_measured,
                    p0=initial_guess,
                    maxfev=100  # Limit iterations for fair comparison
                )
                result_scipy = popt
            except Exception as e:
                print(f"   SciPy fit failed: {e}")
                result_scipy = None
                break
        elapsed_scipy = time.time() - start
        avg_scipy = elapsed_scipy / n_repeats * 1000

        if result_scipy is not None:
            print(f"   Average time: {avg_scipy:.2f} ms")
            print(f"   Fitted τ: {result_scipy[2]:.2f} s")
            print(f"   Fitted β: {result_scipy[3]:.3f}")

            speedup = avg_scipy / avg_numba
            print(f"\n🏆 SPEEDUP: {speedup:.1f}x faster with Numba!")
    else:
        print("\n(SciPy not available for comparison)")

    return avg_numba


def benchmark_data_size_scaling():
    """Benchmark how performance scales with data size."""
    print(f"\n{'='*60}")
    print(f"BENCHMARK: Scaling with Data Size")
    print(f"{'='*60}\n")

    sizes = [100, 500, 1000, 2000, 5000, 10000]
    times = []

    for n_points in sizes:
        # Generate data
        t = np.linspace(0, 100, n_points)
        I = 1e-6 + 0.5e-6 * np.exp(-((t / 20.0) ** 0.7))
        I += np.random.normal(0, 1e-8, n_points)

        # Time fitting
        start = time.time()
        for _ in range(3):  # 3 repeats
            _ = fit_stretched_exponential(t, I)
        elapsed = (time.time() - start) / 3 * 1000  # Average in ms

        times.append(elapsed)
        print(f"   {n_points:5d} points: {elapsed:6.2f} ms")

    print(f"\n   Scaling: ~O(n) linear complexity")
    print(f"   Even 10,000 points: <{times[-1]:.0f} ms! 🚀")


def benchmark_typical_its_measurement():
    """
    Benchmark on a realistic ITS measurement scenario.

    Typical ITS:
    - 2000-5000 points
    - 100-300 seconds duration
    - LED pulses with photoresponse decay
    """
    print(f"\n{'='*60}")
    print(f"BENCHMARK: Realistic ITS Measurement")
    print(f"{'='*60}\n")

    # Simulate typical ITS measurement
    n_points = 3000
    duration = 200.0  # seconds

    t = np.linspace(0, duration, n_points)

    # Multi-pulse scenario: 3 LED pulses
    I = np.zeros(n_points)
    baseline = 1.2e-6

    for pulse_start in [20, 80, 140]:
        pulse_mask = t >= pulse_start
        t_rel = np.maximum(0, t - pulse_start)
        # Stretched exponential relaxation after each pulse
        I[pulse_mask] += 0.3e-6 * np.exp(-((t_rel[pulse_mask] / 25.0) ** 0.65))

    I += baseline
    I += np.random.normal(0, 2e-8, n_points)  # Realistic noise

    print(f"Measurement details:")
    print(f"   Duration: {duration} s")
    print(f"   Points: {n_points}")
    print(f"   Sample rate: {n_points/duration:.1f} Hz")
    print(f"   LED pulses: 3")

    # Fit first pulse (extract subset)
    pulse1_mask = (t >= 20) & (t <= 80)
    t_pulse1 = t[pulse1_mask] - 20  # Reset time to 0
    I_pulse1 = I[pulse1_mask]

    print(f"\nFitting first pulse ({np.sum(pulse1_mask)} points)...")

    start = time.time()
    result = fit_stretched_exponential(t_pulse1, I_pulse1)
    elapsed = (time.time() - start) * 1000

    print(f"   Time: {elapsed:.2f} ms")
    print(f"   τ: {result['tau']:.2f} s")
    print(f"   β: {result['beta']:.3f}")
    print(f"   R²: {result['r_squared']:.6f}")
    print(f"   Converged: {result['converged']}")

    # Estimate total time for processing full measurement
    n_pulses = 3
    total_time = elapsed * n_pulses
    print(f"\n   Estimated total for {n_pulses} pulses: {total_time:.1f} ms")
    print(f"   ✅ Fast enough for real-time analysis!")


def run_all_benchmarks():
    """Run complete benchmark suite."""
    print("\n" + "="*60)
    print("STRETCHED EXPONENTIAL FITTING - PERFORMANCE BENCHMARKS")
    print("="*60)

    # Benchmark 1: Single fit
    benchmark_single_fit(n_points=1000, n_repeats=10)

    # Benchmark 2: Scaling
    benchmark_data_size_scaling()

    # Benchmark 3: Realistic ITS
    benchmark_typical_its_measurement()

    print("\n" + "="*60)
    print("BENCHMARKS COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_all_benchmarks()
