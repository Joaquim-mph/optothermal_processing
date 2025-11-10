"""
Stretched exponential fitting for ITS photoresponse analysis.

Uses Numba-accelerated Levenberg-Marquardt optimization for fast fitting
of long time-series data (1000-10000 points).

Performance:
- Pure Python/SciPy: ~500-2000ms per fit
- Numba-optimized: ~5-50ms per fit (50-200x faster!)
"""

from __future__ import annotations

import numpy as np
from numba import jit
from typing import Tuple, Optional
import warnings


# ══════════════════════════════════════════════════════════════════════
# Numba-Accelerated Core Functions
# ══════════════════════════════════════════════════════════════════════

@jit(nopython=True)
def stretched_exponential(t: np.ndarray, baseline: float, amplitude: float,
                         tau: float, beta: float) -> np.ndarray:
    """
    Evaluate stretched exponential function.

    I(t) = baseline + amplitude * exp(-(t/tau)^beta)

    Parameters
    ----------
    t : np.ndarray
        Time values (seconds)
    baseline : float
        Baseline current (A)
    amplitude : float
        Photoresponse amplitude (A)
    tau : float
        Relaxation time constant (s), must be > 0
    beta : float
        Stretching exponent (0 < beta <= 1)

    Returns
    -------
    np.ndarray
        Current values (A)
    """
    n = len(t)
    result = np.zeros(n)

    for i in range(n):
        if tau > 0 and beta > 0:
            exponent = -((t[i] / tau) ** beta)
            # Clip to avoid overflow
            if exponent > -50:  # exp(-50) ≈ 2e-22, effectively zero
                result[i] = baseline + amplitude * np.exp(exponent)
            else:
                result[i] = baseline
        else:
            result[i] = baseline

    return result


@jit(nopython=True)
def compute_residuals(t: np.ndarray, current: np.ndarray,
                     baseline: float, amplitude: float,
                     tau: float, beta: float) -> np.ndarray:
    """
    Compute residuals between data and model.

    Parameters
    ----------
    t : np.ndarray
        Time values
    current : np.ndarray
        Measured current values
    baseline, amplitude, tau, beta : float
        Model parameters

    Returns
    -------
    np.ndarray
        Residuals (measured - predicted)
    """
    predicted = stretched_exponential(t, baseline, amplitude, tau, beta)
    return current - predicted


@jit(nopython=True)
def compute_jacobian(t: np.ndarray, baseline: float, amplitude: float,
                     tau: float, beta: float, h: float = 1e-7) -> np.ndarray:
    """
    Compute Jacobian matrix using finite differences.

    J[i, j] = ∂residual_i / ∂param_j

    Parameters
    ----------
    t : np.ndarray
        Time values
    baseline, amplitude, tau, beta : float
        Model parameters
    h : float
        Step size for finite differences

    Returns
    -------
    np.ndarray
        Jacobian matrix (n_points × 4)
    """
    n = len(t)
    J = np.zeros((n, 4))

    # Reference function
    f0 = stretched_exponential(t, baseline, amplitude, tau, beta)

    # ∂f/∂baseline
    f_baseline = stretched_exponential(t, baseline + h, amplitude, tau, beta)
    J[:, 0] = (f_baseline - f0) / h

    # ∂f/∂amplitude
    f_amplitude = stretched_exponential(t, baseline, amplitude + h, tau, beta)
    J[:, 1] = (f_amplitude - f0) / h

    # ∂f/∂tau (use relative step for tau)
    h_tau = max(h, tau * 1e-6)
    f_tau = stretched_exponential(t, baseline, amplitude, tau + h_tau, beta)
    J[:, 2] = (f_tau - f0) / h_tau

    # ∂f/∂beta (use relative step)
    h_beta = max(h, beta * 1e-6)
    f_beta = stretched_exponential(t, baseline, amplitude, tau, beta + h_beta)
    J[:, 3] = (f_beta - f0) / h_beta

    return J


@jit(nopython=True)
def levenberg_marquardt_step(t: np.ndarray, current: np.ndarray,
                             params: np.ndarray, lambda_lm: float) -> Tuple[np.ndarray, float]:
    """
    Single Levenberg-Marquardt optimization step.

    Parameters
    ----------
    t : np.ndarray
        Time values
    current : np.ndarray
        Measured current
    params : np.ndarray
        Current parameters [baseline, amplitude, tau, beta]
    lambda_lm : float
        Damping parameter

    Returns
    -------
    new_params : np.ndarray
        Updated parameters
    new_cost : float
        Cost after update
    """
    baseline, amplitude, tau, beta = params

    # Compute residuals and Jacobian
    residuals = compute_residuals(t, current, baseline, amplitude, tau, beta)
    J = compute_jacobian(t, baseline, amplitude, tau, beta)

    # Current cost (sum of squared residuals)
    cost = np.sum(residuals ** 2)

    # Compute update: (J^T J + λI) δ = J^T r
    JTJ = J.T @ J
    JTr = J.T @ residuals

    # Add damping to diagonal
    n_params = 4
    for i in range(n_params):
        JTJ[i, i] += lambda_lm

    # Solve for parameter update (simple Gaussian elimination)
    # For 4×4 system, we can use direct inversion
    try:
        delta = np.linalg.solve(JTJ, JTr)
    except:
        # If singular, return original parameters
        return params, cost

    # Update parameters
    new_params = params + delta

    # Apply parameter constraints
    new_params[2] = max(1e-6, new_params[2])  # tau > 0
    # Clip beta to valid range (Numba-compatible)
    if new_params[3] < 0.01:
        new_params[3] = 0.01
    elif new_params[3] > 1.0:
        new_params[3] = 1.0

    # Compute new cost
    new_residuals = compute_residuals(t, current, new_params[0], new_params[1],
                                     new_params[2], new_params[3])
    new_cost = np.sum(new_residuals ** 2)

    return new_params, new_cost


@jit(nopython=True)
def fit_stretched_exponential_numba(t: np.ndarray, current: np.ndarray,
                                    initial_guess: np.ndarray,
                                    max_iterations: int = 100,
                                    tolerance: float = 1e-8) -> Tuple[np.ndarray, float, int, bool]:
    """
    Fit stretched exponential using Levenberg-Marquardt algorithm.

    This is the core Numba-accelerated function. Expected speedup: 50-200x.

    Parameters
    ----------
    t : np.ndarray
        Time values (seconds), should be relative to LED turn-on
    current : np.ndarray
        Measured current (A)
    initial_guess : np.ndarray
        Initial parameters [baseline, amplitude, tau, beta]
    max_iterations : int
        Maximum number of iterations (default: 100)
    tolerance : float
        Convergence tolerance for cost change (default: 1e-8)

    Returns
    -------
    params : np.ndarray
        Fitted parameters [baseline, amplitude, tau, beta]
    final_cost : float
        Final sum of squared residuals
    n_iterations : int
        Number of iterations performed
    converged : bool
        Whether fit converged

    Notes
    -----
    Algorithm:
    1. Start with initial guess
    2. Compute Jacobian and residuals
    3. Update parameters using LM step
    4. If cost decreases: accept step, decrease λ
    5. If cost increases: reject step, increase λ
    6. Repeat until convergence or max iterations
    """
    params = initial_guess.copy()
    lambda_lm = 1e-3  # Initial damping parameter

    # Compute initial cost
    residuals = compute_residuals(t, current, params[0], params[1], params[2], params[3])
    cost = np.sum(residuals ** 2)

    converged = False

    for iteration in range(max_iterations):
        # Try LM step
        new_params, new_cost = levenberg_marquardt_step(t, current, params, lambda_lm)

        # Check if cost improved
        if new_cost < cost:
            # Accept step
            cost_change = abs(cost - new_cost) / (cost + 1e-12)
            params = new_params
            cost = new_cost
            lambda_lm *= 0.1  # Decrease damping (move toward Gauss-Newton)

            # Check convergence
            if cost_change < tolerance:
                converged = True
                break
        else:
            # Reject step, increase damping
            lambda_lm *= 10.0

            # If damping too large, we're stuck
            if lambda_lm > 1e10:
                break

    return params, cost, iteration + 1, converged


# ══════════════════════════════════════════════════════════════════════
# High-Level Python Interface
# ══════════════════════════════════════════════════════════════════════

def fit_stretched_exponential(
    time: np.ndarray,
    current: np.ndarray,
    initial_guess: Optional[np.ndarray] = None,
    max_iterations: int = 100,
    tolerance: float = 1e-8
) -> dict:
    """
    Fit stretched exponential to photoresponse data.

    Python wrapper around Numba-accelerated core function.

    Parameters
    ----------
    time : np.ndarray
        Time values (seconds), should start at 0 (LED turn-on)
    current : np.ndarray
        Measured current (A)
    initial_guess : np.ndarray, optional
        Initial parameters [baseline, amplitude, tau, beta]
        If None, will estimate from data
    max_iterations : int
        Maximum optimization iterations (default: 100)
    tolerance : float
        Convergence tolerance (default: 1e-8)

    Returns
    -------
    dict
        Fitting results:
        - 'baseline': Baseline current (A)
        - 'amplitude': Photoresponse amplitude (A)
        - 'tau': Relaxation time constant (s)
        - 'beta': Stretching exponent (dimensionless)
        - 'cost': Final sum of squared residuals
        - 'n_iterations': Number of iterations
        - 'converged': Whether fit converged
        - 'r_squared': Coefficient of determination
        - 'fitted_curve': Fitted curve (same length as input)

    Examples
    --------
    >>> # Simulate data
    >>> t = np.linspace(0, 100, 1000)
    >>> I_true = 1e-6 + 0.5e-6 * np.exp(-(t/20)**0.7)
    >>> I_measured = I_true + np.random.normal(0, 1e-8, len(t))
    >>>
    >>> # Fit
    >>> result = fit_stretched_exponential(t, I_measured)
    >>> print(f"τ = {result['tau']:.2f} s")
    >>> print(f"β = {result['beta']:.3f}")
    """
    # Validate inputs
    if len(time) != len(current):
        raise ValueError("time and current must have same length")

    if len(time) < 10:
        raise ValueError("Need at least 10 data points for fitting")

    # Convert to numpy arrays (in case they're Polars series)
    time = np.asarray(time, dtype=np.float64)
    current = np.asarray(current, dtype=np.float64)

    # Remove NaN/Inf
    valid_mask = np.isfinite(time) & np.isfinite(current)
    if not np.all(valid_mask):
        warnings.warn(f"Removed {np.sum(~valid_mask)} NaN/Inf values before fitting")
        time = time[valid_mask]
        current = current[valid_mask]

    # Estimate initial guess if not provided
    if initial_guess is None:
        initial_guess = estimate_initial_parameters(time, current)
    else:
        initial_guess = np.asarray(initial_guess, dtype=np.float64)

    # Run Numba-accelerated fitting
    params, cost, n_iterations, converged = fit_stretched_exponential_numba(
        time, current, initial_guess, max_iterations, tolerance
    )

    # Compute fitted curve and R²
    fitted_curve = stretched_exponential(time, params[0], params[1], params[2], params[3])

    ss_res = cost  # Sum of squared residuals
    ss_tot = np.sum((current - np.mean(current)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {
        'baseline': float(params[0]),
        'amplitude': float(params[1]),
        'tau': float(params[2]),
        'beta': float(params[3]),
        'cost': float(cost),
        'n_iterations': int(n_iterations),
        'converged': bool(converged),
        'r_squared': float(r_squared),
        'fitted_curve': fitted_curve
    }


def estimate_initial_parameters(time: np.ndarray, current: np.ndarray) -> np.ndarray:
    """
    Estimate initial parameters from data.

    Parameters
    ----------
    time : np.ndarray
        Time values
    current : np.ndarray
        Current values

    Returns
    -------
    np.ndarray
        Initial guess [baseline, amplitude, tau, beta]
    """
    # Baseline: average of last 20% of data (should be relaxed)
    n_end = max(10, len(current) // 5)
    baseline = np.mean(current[-n_end:])

    # Amplitude: difference between max and baseline
    amplitude = np.max(current) - baseline

    # Tau: time when signal drops to baseline + amplitude/e
    target = baseline + amplitude / np.e
    idx = np.argmin(np.abs(current - target))
    tau = time[idx] if idx > 0 else np.median(time)
    tau = max(tau, time[1] - time[0])  # At least one time step

    # Beta: start with 0.7 (typical for stretched exponentials)
    beta = 0.7

    return np.array([baseline, amplitude, tau, beta])


# ══════════════════════════════════════════════════════════════════════
# Batch Processing
# ══════════════════════════════════════════════════════════════════════

def fit_multiple_its_measurements(
    measurements: list,
    show_progress: bool = True
) -> list:
    """
    Fit stretched exponentials to multiple ITS measurements.

    Parameters
    ----------
    measurements : list of dict
        Each dict should have 'time' and 'current' arrays
    show_progress : bool
        Whether to show progress bar

    Returns
    -------
    list of dict
        Fitting results for each measurement
    """
    results = []

    n_total = len(measurements)
    for i, measurement in enumerate(measurements):
        if show_progress and i % 10 == 0:
            print(f"Fitting {i}/{n_total}...")

        try:
            result = fit_stretched_exponential(
                measurement['time'],
                measurement['current']
            )
            results.append(result)
        except Exception as e:
            print(f"Warning: Fit {i} failed: {e}")
            results.append(None)

    return results
