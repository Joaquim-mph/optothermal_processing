"""
Linear Drift Extractor.

Extracts linear drift rates from time-series measurements (ITS, Vt, Tt).
Uses Numba-accelerated linear least squares fitting.

Use Cases:
- Current drift in dark ITS measurements
- Voltage drift over time
- Temperature drift
- Baseline stability analysis
"""

from __future__ import annotations

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

    For measurements with time vs current/voltage/temperature data,
    this extractor fits a linear model:

        y(t) = y₀ + drift_rate * t

    Where:
    - y₀: Initial value
    - drift_rate: Linear drift rate (units/second)

    This is useful for:
    1. Baseline stability analysis (dark ITS drift)
    2. Device degradation tracking
    3. Temperature stability
    4. Voltage drift in Vt measurements

    Parameters
    ----------
    min_points : int
        Minimum data points required (default: 10)
    min_duration : float
        Minimum measurement duration in seconds (default: 10.0)
    min_r_squared : float
        Minimum R² for valid fit (default: 0.7)
    dark_only : bool
        Only extract from dark measurements (VL < 0.1V, default: True)

    Examples
    --------
    >>> # Extract drift from dark ITS measurement
    >>> extractor = DriftExtractor(min_r_squared=0.8)
    >>> metric = extractor.extract(its_measurement, metadata)
    >>> import json
    >>> details = json.loads(metric.value_json)
    >>> print(f"Drift rate: {details['drift_rate']:.2e} A/s")
    >>> print(f"R² = {details['r_squared']:.3f}")
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
        """Applies to time-series measurements."""
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
        """
        Extract linear drift rate from time-series measurement.

        Parameters
        ----------
        measurement : pl.DataFrame
            Time-series data with columns: t (s), and I/V/T columns
        metadata : dict
            Measurement metadata

        Returns
        -------
        DerivedMetric or None
            Metric with drift rate, or None if extraction fails
        """
        # Determine procedure type
        proc = metadata.get("proc", metadata.get("procedure", ""))

        # Select appropriate columns based on procedure
        if proc in ["ITS", "ITt"]:
            time_col = "t (s)"
            value_col = "I (A)"
            unit = "A/s"
        elif proc == "Vt":
            time_col = "t (s)"
            value_col = "Vds (V)"
            unit = "V/s"
        elif proc == "Tt":
            time_col = "t (s)"
            value_col = "T (K)"
            unit = "K/s"
        else:
            return None

        # Validate columns exist
        if time_col not in measurement.columns or value_col not in measurement.columns:
            return None

        # Check if dark measurement (if required)
        if self.dark_only and "VL (V)" in measurement.columns:
            vl = measurement["VL (V)"].to_numpy()
            if np.any(vl > 0.1):  # Has light
                return None

        # Extract data
        time = measurement[time_col].to_numpy()
        values = measurement[value_col].to_numpy()

        # Validate minimum requirements
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
        stderr = fit_result['stderr']

        # Compute confidence based on R²
        confidence = self._compute_confidence(r_squared, stderr, duration)

        # Build detailed results
        details = {
            "drift_rate": float(drift_rate),
            "initial_value": float(initial_value),
            "r_squared": float(r_squared),
            "stderr": float(stderr),
            "duration": float(duration),
            "n_points": int(len(time)),
            "normalized_drift": float(abs(drift_rate) / abs(initial_value)) if abs(initial_value) > 1e-15 else 0.0
        }

        # Build flags
        flags = self._build_flags(drift_rate, r_squared, stderr, initial_value)

        # Return DerivedMetric
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=proc,
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=drift_rate,  # Primary value: drift rate
            value_json=json.dumps(details),
            unit=unit,
            extraction_method="linear_least_squares",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=flags
        )

    def _compute_confidence(
        self,
        r_squared: float,
        stderr: float,
        duration: float
    ) -> float:
        """
        Compute confidence score based on fit quality.

        Parameters
        ----------
        r_squared : float
            Coefficient of determination
        stderr : float
            Standard error
        duration : float
            Measurement duration

        Returns
        -------
        float
            Confidence score (0-1)
        """
        confidence = 1.0

        # Penalty for low R²
        if r_squared < 0.95:
            confidence *= 0.9
        if r_squared < 0.90:
            confidence *= 0.8
        if r_squared < 0.85:
            confidence *= 0.7
        if r_squared < 0.80:
            confidence *= 0.6

        # Penalty for short duration
        if duration < 30:
            confidence *= 0.8
        if duration < 60:
            confidence *= 0.9

        return max(0.0, min(1.0, confidence))

    def _build_flags(
        self,
        drift_rate: float,
        r_squared: float,
        stderr: float,
        initial_value: float
    ) -> Optional[str]:
        """
        Build warning flags based on drift characteristics.

        Parameters
        ----------
        drift_rate : float
            Fitted drift rate
        r_squared : float
            Fit quality
        stderr : float
            Standard error
        initial_value : float
            Initial value

        Returns
        -------
        str or None
            Comma-separated flags or None
        """
        flags = []

        # Check fit quality
        if r_squared < 0.80:
            flags.append("LOW_R2")

        # Check drift magnitude
        if abs(initial_value) > 1e-15:
            normalized_drift = abs(drift_rate) / abs(initial_value)
            if normalized_drift > 0.01:  # 1% drift per measurement
                flags.append("LARGE_DRIFT")
            if normalized_drift < 1e-6:
                flags.append("NEGLIGIBLE_DRIFT")

        # Check drift direction
        if drift_rate > 0:
            flags.append("POSITIVE_DRIFT")
        elif drift_rate < 0:
            flags.append("NEGATIVE_DRIFT")

        return ",".join(flags) if flags else None

    def validate(self, result: DerivedMetric) -> bool:
        """
        Validate extracted drift metric.

        Parameters
        ----------
        result : DerivedMetric
            Extracted metric

        Returns
        -------
        bool
            True if valid
        """
        if result.value_float is None:
            return False

        # Drift rate should be finite
        if not np.isfinite(result.value_float):
            return False

        # Check that JSON details are valid
        try:
            details = json.loads(result.value_json)
            if details["r_squared"] < self.min_r_squared:
                return False
        except (json.JSONDecodeError, KeyError):
            return False

        return True
