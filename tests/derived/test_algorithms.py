
import sys
import pytest
import numpy as np
from unittest.mock import MagicMock
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

# Mock numba BEFORE importing modules
numba_mock = MagicMock()
numba_mock.jit = lambda *args, **kwargs: (lambda f: f)
numba_mock.prange = range
sys.modules["numba"] = numba_mock

from src.derived.algorithms.sweep_difference_numba import (
    compute_sweep_difference, 
    compute_resistance_safe,
    linear_interp_sorted
)
from src.derived.algorithms.stretched_exponential import (
    fit_stretched_exponential,
    stretched_exponential
)

class TestSweepDifference:
    def test_linear_interpolation(self):
        """Test basic linear interpolation."""
        x_old = np.array([0, 10], dtype=float)
        y_old = np.array([0, 100], dtype=float)
        x_new = np.array([5], dtype=float)
        
        result = linear_interp_sorted(x_old, y_old, x_new)
        assert result[0] == 50.0

    def test_compute_resistance_safe_scalar_voltage(self):
        """Test resistance calculation with scalar voltage (IVg)."""
        voltage = 10.0
        current = np.array([1e-6, 1e-15, -1e-6]) # Normal, too small, normal negative
        min_current = 1e-12
        
        result = compute_resistance_safe(voltage, current, min_current)
        
        assert np.isclose(result[0], 10.0 / 1e-6)
        assert np.isnan(result[1]) # Should be NaN
        assert np.isclose(result[2], 10.0 / -1e-6)

    def test_compute_resistance_safe_array_voltage(self):
        """Test resistance calculation with array voltage (VVg)."""
        voltage = np.array([10.0, 10.0, 10.0])
        current = np.array([1e-6, 1e-15, 1e-6])
        min_current = 1e-12
        
        result = compute_resistance_safe(voltage, current, min_current)
        
        assert np.isclose(result[0], 1e7)
        assert np.isnan(result[1])
        assert np.isclose(result[2], 1e7)

    def test_compute_sweep_difference(self):
        """Test sweep difference calculation."""
        # Simple shift: y2 = y1 + 1
        vg1 = np.linspace(0, 10, 11)
        y1 = vg1
        vg2 = np.linspace(0, 10, 11)
        y2 = vg1 + 1.0
        
        vg_common, delta_y, vg_min, vg_max = compute_sweep_difference(
            vg1, y1, vg2, y2, n_points=11
        )
        
        assert vg_min == 0
        assert vg_max == 10
        assert len(vg_common) == 11
        assert np.allclose(delta_y, 1.0)

class TestStretchedExponential:
    def test_forward_function(self):
        """Test the mathematical function evaluation."""
        t = np.array([0, 10, 100], dtype=float)
        baseline = 0
        amplitude = 1
        tau = 10
        beta = 1
        
        # At t=0: base + amp * exp(0) = 0 + 1 * 1 = 1
        # At t=10: base + amp * exp(-1) = 0.3678
        # At t=100: base + amp * exp(-10) ~ 0
        
        result = stretched_exponential(t, baseline, amplitude, tau, beta)
        
        assert np.isclose(result[0], 1.0)
        assert np.isclose(result[1], np.exp(-1))
        assert np.isclose(result[2], np.exp(-10))

    def test_fit_synthetic_data(self):
        """Test fitting on clean synthetic data."""
        t = np.linspace(0, 50, 100)
        # True params: base=1e-6, amp=1e-6, tau=10, beta=0.8
        y_true = stretched_exponential(t, 1e-6, 1e-6, 10.0, 0.8)
        
        result = fit_stretched_exponential(t, y_true)
        
        assert result['converged'] is True
        assert np.isclose(result['baseline'], 1e-6, rtol=0.1)
        assert np.isclose(result['amplitude'], 1e-6, rtol=0.1)
        assert np.isclose(result['tau'], 10.0, rtol=0.2)
        assert np.isclose(result['beta'], 0.8, rtol=0.2)
        assert result['r_squared'] > 0.99
    
    def test_fit_failure_short_data(self):
        """Test validation for short data."""
        t = np.array([1, 2, 3])
        y = np.array([1, 2, 3])
        
        with pytest.raises(ValueError, match="Need at least 10 data points"):
            fit_stretched_exponential(t, y)

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
