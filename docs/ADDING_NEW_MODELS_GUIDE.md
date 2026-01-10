# Adding New Models to the Derived Metrics Pipeline

This guide explains how to add new fitting models (like `a*x + b`, exponential decay, polynomial, etc.) to the derived metrics framework.

## Overview

The framework separates **algorithms** (Numba-accelerated fitting) from **extractors** (business logic). To add a new model:

1. Create the **algorithm** (Numba-optimized fitting function)
2. Create the **extractor** (applies algorithm to measurements)
3. Register the **extractor** in the pipeline
4. Add **metric category** if needed (optional)

---

## Example: Linear Model (a*x + b)

We'll walk through the complete implementation of a linear drift model.

### Step 1: Create the Algorithm

**File:** `src/derived/algorithms/linear_fit.py`

```python
"""
Linear fitting algorithm for drift analysis.
"""

import numpy as np
from numba import jit
from typing import Tuple

# Core Numba-accelerated function
@jit(nopython=True)
def linear_model(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """Evaluate linear model: f(x) = a*x + b"""
    return a * x + b

@jit(nopython=True)
def fit_linear_least_squares(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float, float]:
    """
    Fit linear model using analytical least squares.

    minimize: Σ(y - (a*x + b))²

    Solution:
        a = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
        b = (Σy - a*Σx) / n

    Returns: (a, b, r_squared, stderr)
    """
    n = len(x)

    # Compute sums
    sum_x = sum_y = sum_xx = sum_xy = 0.0
    for i in range(n):
        sum_x += x[i]
        sum_y += y[i]
        sum_xx += x[i] * x[i]
        sum_xy += x[i] * y[i]

    # Compute slope and intercept
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        a = 0.0
        b = sum_y / n if n > 0 else 0.0
        r_squared = 0.0
        stderr = 0.0
    else:
        a = (n * sum_xy - sum_x * sum_y) / denom
        b = (sum_y - a * sum_x) / n

        # Compute R² and standard error
        mean_y = sum_y / n
        ss_tot = ss_res = 0.0
        for i in range(n):
            y_pred = a * x[i] + b
            ss_tot += (y[i] - mean_y) ** 2
            ss_res += (y[i] - y_pred) ** 2

        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        stderr = np.sqrt(ss_res / n) if n > 0 else 0.0

    return a, b, r_squared, stderr

# Python wrapper
def fit_linear(x: np.ndarray, y: np.ndarray) -> dict:
    """
    Fit linear model to data.

    Returns dict with 'slope', 'intercept', 'r_squared', 'stderr', 'fitted_curve'
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)

    a, b, r_squared, stderr = fit_linear_least_squares(x, y)
    fitted_curve = linear_model(x, a, b)

    return {
        'slope': float(a),
        'intercept': float(b),
        'r_squared': float(r_squared),
        'stderr': float(stderr),
        'fitted_curve': fitted_curve,
        'n_points': len(x)
    }
```

**Key points:**
- Use `@jit(nopython=True)` for speed (10-200× faster)
- Use analytical solutions when possible (no iteration needed)
- Return Python dict from wrapper for easy use

---

### Step 2: Export the Algorithm

**File:** `src/derived/algorithms/__init__.py`

```python
from .linear_fit import fit_linear, linear_model

__all__ = [
    # ... existing exports
    'fit_linear',
    'linear_model',
]
```

---

### Step 3: Create the Extractor

**File:** `src/derived/extractors/drift_extractor.py`

```python
"""
Linear Drift Extractor.
"""

import numpy as np
import polars as pl
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

from src.models.derived_metrics import DerivedMetric, MetricCategory
from src.derived.algorithms import fit_linear
from .base import MetricExtractor


class DriftExtractor(MetricExtractor):
    """
    Extract linear drift rate from time-series measurements.

    For measurements with time vs current/voltage/temperature:
        y(t) = y₀ + drift_rate * t
    """

    def __init__(
        self,
        min_points: int = 10,
        min_duration: float = 10.0,
        min_r_squared: float = 0.7,
        dark_only: bool = True
    ):
        self.min_points = min_points
        self.min_duration = min_duration
        self.min_r_squared = min_r_squared
        self.dark_only = dark_only

    @property
    def applicable_procedures(self) -> List[str]:
        """Which procedures this extractor applies to."""
        return ["ITS", "ITt", "Vt", "Tt"]

    @property
    def metric_name(self) -> str:
        return "linear_drift"

    @property
    def metric_category(self) -> MetricCategory:
        return "stability"

    def extract(
        self,
        measurement: pl.DataFrame,
        metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        """Extract linear drift rate from measurement."""

        # Determine procedure type and select columns
        proc = metadata.get("proc", metadata.get("procedure", ""))
        if proc in ["ITS", "ITt"]:
            time_col, value_col, unit = "t (s)", "I (A)", "A/s"
        elif proc == "Vt":
            time_col, value_col, unit = "t (s)", "Vds (V)", "V/s"
        elif proc == "Tt":
            time_col, value_col, unit = "t (s)", "T (K)", "K/s"
        else:
            return None

        # Validate columns
        if time_col not in measurement.columns or value_col not in measurement.columns:
            return None

        # Check if dark (if required)
        if self.dark_only and "VL (V)" in measurement.columns:
            vl = measurement["VL (V)"].to_numpy()
            if np.any(vl > 0.1):  # Has light
                return None

        # Extract data
        time = measurement[time_col].to_numpy()
        values = measurement[value_col].to_numpy()

        # Validate requirements
        if len(time) < self.min_points:
            return None
        duration = time[-1] - time[0]
        if duration < self.min_duration:
            return None

        # Normalize time to start at 0
        time_normalized = time - time[0]

        # Fit linear model
        try:
            fit_result = fit_linear(time_normalized, values)
        except Exception:
            return None

        # Check fit quality
        if fit_result['r_squared'] < self.min_r_squared:
            return None

        # Extract parameters
        drift_rate = fit_result['slope']
        initial_value = fit_result['intercept']
        r_squared = fit_result['r_squared']

        # Build detailed results
        details = {
            "drift_rate": float(drift_rate),
            "initial_value": float(initial_value),
            "r_squared": float(r_squared),
            "duration": float(duration),
            "n_points": int(len(time))
        }

        # Return metric
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=proc,
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=drift_rate,  # Primary value
            value_json=json.dumps(details),
            unit=unit,
            extraction_method="linear_least_squares",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=self._compute_confidence(r_squared, duration),
            flags=self._build_flags(drift_rate, r_squared)
        )

    def _compute_confidence(self, r_squared: float, duration: float) -> float:
        """Compute confidence score."""
        confidence = 1.0
        if r_squared < 0.95:
            confidence *= 0.9
        if duration < 30:
            confidence *= 0.8
        return confidence

    def _build_flags(self, drift_rate: float, r_squared: float) -> Optional[str]:
        """Build warning flags."""
        flags = []
        if r_squared < 0.80:
            flags.append("LOW_R2")
        if drift_rate > 0:
            flags.append("POSITIVE_DRIFT")
        elif drift_rate < 0:
            flags.append("NEGATIVE_DRIFT")
        return ",".join(flags) if flags else None

    def validate(self, result: DerivedMetric) -> bool:
        """Validate extracted metric."""
        if result.value_float is None:
            return False
        if not np.isfinite(result.value_float):
            return False
        return True
```

---

### Step 4: Register the Extractor

**File 1:** `src/derived/extractors/__init__.py`

```python
from .drift_extractor import DriftExtractor

__all__ = [
    # ... existing exports
    "DriftExtractor",
]
```

**File 2:** `src/derived/metric_pipeline.py`

```python
def _default_extractors(self) -> List[MetricExtractor]:
    """Return default set of metric extractors."""
    from .extractors.cnp_extractor import CNPExtractor
    from .extractors.drift_extractor import DriftExtractor
    # ... other imports

    return [
        CNPExtractor(),
        DriftExtractor(min_r_squared=0.7, dark_only=True),
        # ... other extractors
    ]
```

---

### Step 5: Add Metric Category (if new)

**File:** `src/models/derived_metrics.py`

```python
MetricCategory = Literal[
    "electrical",
    "photoresponse",
    "thermal",
    "optical",
    "structural",
    "stability"  # ← Add new category here
]
```

---

### Step 6: Test It

```bash
# Test algorithm directly
python3 -c "
from src.derived.algorithms import fit_linear
import numpy as np

x = np.linspace(0, 100, 1000)
y = 1e-6 + 1e-9*x + np.random.normal(0, 1e-10, len(x))

result = fit_linear(x, y)
print(f'Slope: {result[\"slope\"]:.2e}')
print(f'R² = {result[\"r_squared\"]:.4f}')
"

# Test extractor registration
python3 -c "
from src.derived.extractors import DriftExtractor
extractor = DriftExtractor()
print(f'Applies to: {extractor.applicable_procedures}')
print(f'Metric: {extractor.metric_name}')
"

# Test in pipeline
python3 process_and_analyze.py derive-all-metrics --procedures ITS,Vt
```

---

## Other Model Examples

### Exponential Decay: y = A*exp(-x/τ) + B

```python
@jit(nopython=True)
def exponential_decay(x, A, tau, B):
    return B + A * np.exp(-x / tau)

@jit(nopython=True)
def fit_exponential_levenberg_marquardt(x, y):
    # Initial guess
    B = np.mean(y[-10:])  # Baseline
    A = np.max(y) - B      # Amplitude
    tau = x[np.argmin(np.abs(y - (B + A/np.e)))]  # Time constant

    # Use LM algorithm (similar to stretched_exponential.py)
    # ... implementation

    return A, tau, B, r_squared
```

### Polynomial: y = a₀ + a₁*x + a₂*x² + ...

```python
@jit(nopython=True)
def fit_polynomial(x, y, degree):
    # Use numpy's polyfit equivalent in Numba
    # Build Vandermonde matrix and solve normal equations
    # ... implementation

    return coefficients, r_squared
```

### Power Law: y = A*x^β

```python
@jit(nopython=True)
def fit_power_law(x, y):
    # Transform to linear: log(y) = log(A) + β*log(x)
    log_x = np.log(x)
    log_y = np.log(y)

    # Fit linear
    beta, log_A, r_squared, stderr = fit_linear_least_squares(log_x, log_y)
    A = np.exp(log_A)

    return A, beta, r_squared
```

### Gaussian: y = A*exp(-(x-μ)²/(2σ²)) + B

```python
@jit(nopython=True)
def gaussian(x, A, mu, sigma, B):
    return B + A * np.exp(-((x - mu)**2) / (2 * sigma**2))

@jit(nopython=True)
def fit_gaussian_levenberg_marquardt(x, y):
    # Initial guess
    B = (y[0] + y[-1]) / 2  # Baseline (average of edges)
    A = np.max(y) - B       # Amplitude
    mu = x[np.argmax(y)]    # Center (peak position)
    sigma = (x[-1] - x[0]) / 4  # Width guess

    # Use LM algorithm
    # ... implementation

    return A, mu, sigma, B, r_squared
```

---

## Best Practices

### 1. **Always Use Numba for Performance**
```python
@jit(nopython=True)  # ← Compile to machine code
def my_model(x, params):
    # Pure NumPy code here (no Polars, no Python objects)
    return result
```

### 2. **Provide Smart Initial Guesses**
```python
def estimate_initial_parameters(x, y):
    """Good initial guess = faster convergence"""
    # Use data statistics to estimate parameters
    baseline = np.mean(y[-10:])  # Last 10 points
    amplitude = np.max(y) - baseline
    # ... etc
    return initial_params
```

### 3. **Return Rich Metadata**
```python
return {
    'param_a': float(a),
    'param_b': float(b),
    'r_squared': float(r_squared),
    'n_iterations': int(n_iter),
    'converged': bool(converged),
    'fitted_curve': fitted_curve,
    'residuals': residuals
}
```

### 4. **Validate Inputs**
```python
# Check for NaN/Inf
valid_mask = np.isfinite(x) & np.isfinite(y)
if not np.all(valid_mask):
    warnings.warn(f"Removed {np.sum(~valid_mask)} invalid values")
    x = x[valid_mask]
    y = y[valid_mask]

# Check minimum points
if len(x) < min_points:
    raise ValueError(f"Need at least {min_points} points")
```

### 5. **Compute Confidence Scores**
```python
def _compute_confidence(self, fit_result):
    confidence = 1.0

    # Penalty for poor fit
    if fit_result['r_squared'] < 0.95:
        confidence *= 0.8

    # Penalty for non-convergence
    if not fit_result['converged']:
        confidence *= 0.6

    return confidence
```

### 6. **Add Quality Flags**
```python
def _build_flags(self, fit_result):
    flags = []

    if fit_result['r_squared'] < 0.80:
        flags.append("LOW_R2")

    if fit_result['n_iterations'] > 80:
        flags.append("SLOW_CONVERGENCE")

    if fit_result['param_a'] < 0:
        flags.append("NEGATIVE_AMPLITUDE")

    return ",".join(flags) if flags else None
```

---

## Summary

**To add a new model:**

1. **Algorithm** (`src/derived/algorithms/my_model.py`):
   - Numba-accelerated fitting function
   - Python wrapper returning dict
   - Export in `__init__.py`

2. **Extractor** (`src/derived/extractors/my_extractor.py`):
   - Inherit from `MetricExtractor`
   - Implement `extract()` method
   - Define `applicable_procedures`, `metric_name`, `metric_category`
   - Export in `__init__.py`

3. **Register** (`src/derived/metric_pipeline.py`):
   - Import in `_default_extractors()`
   - Add to returned list

4. **Test**:
   ```bash
   python3 process_and_analyze.py derive-all-metrics
   ```

**Your new model is now automatically applied to all relevant measurements!**

---

## Need Help?

- **Algorithm templates**: See `src/derived/algorithms/stretched_exponential.py`
- **Extractor templates**: See `src/derived/extractors/its_relaxation_extractor.py`
- **Numba guide**: https://numba.pydata.org/numba-doc/latest/user/jit.html
- **Issues**: https://github.com/anthropics/claude-code/issues
