"""
Dark It Relaxation Time Extractor using stretched exponential fitting.

Extracts dark relaxation time constants (τ and β) from It measurements
with dark segments (LED OFF periods) using Numba-accelerated fitting.

Note: For illuminated ITS with complete OFF→ON→OFF cycles, use
ITSThreePhaseFitExtractor instead, which fits all three phases separately.

Perfect use case for Numba acceleration: 50-200x faster than pure Python!
"""

from __future__ import annotations

import numpy as np
import polars as pl
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

from src.models.derived_metrics import DerivedMetric, MetricCategory
from src.derived.algorithms import fit_stretched_exponential
from .base import MetricExtractor
import logging

logger = logging.getLogger(__name__)


class ITSRelaxationExtractor(MetricExtractor):
    """
    Extract dark relaxation time from It measurements.

    Uses stretched exponential fitting to characterize dark relaxation dynamics
    in LED OFF periods:
        I(t) = I_baseline + A * exp(-(t/τ)^β)

    Where:
    - τ: Dark relaxation time constant (seconds)
    - β: Stretching exponent (0 < β ≤ 1)
          β = 1 → simple exponential
          β < 1 → stretched (distributed relaxation processes)

    This extractor is specifically designed for dark It measurements.
    For illuminated ITS measurements, use ITSThreePhaseFitExtractor instead.

    Parameters
    ----------
    vl_threshold : float
        LED ON threshold (default: 0.1V)
    min_led_on_time : float
        Minimum LED ON duration for fitting (seconds, default: 10s)
    min_points_for_fit : int
        Minimum data points required for reliable fit (default: 50)
    fit_segment : str
        Which segment to fit: "light" (LED ON), "dark" (LED OFF), or "both"
        - "light": Fit photoresponse buildup during LED ON
        - "dark": Fit photoresponse decay after LED turns OFF
        - "both": Try light first, fallback to dark if light fails
        (default: "light")

    Examples
    --------
    >>> # Fit LED ON relaxation (photoresponse buildup)
    >>> extractor = ITSRelaxationExtractor(fit_segment="light")
    >>> metric = extractor.extract(its_measurement, metadata)
    >>> print(f"Light relaxation time: {metric.value_float:.2f} s")

    >>> # Fit LED OFF relaxation (dark decay)
    >>> extractor = ITSRelaxationExtractor(fit_segment="dark")
    >>> metric = extractor.extract(its_measurement, metadata)
    >>> print(f"Dark relaxation time: {metric.value_float:.2f} s")
    """

    def __init__(
        self,
        vl_threshold: float = 0.1,
        min_led_on_time: float = 10.0,
        min_points_for_fit: int = 50,
        fit_segment: str = "light"  # "light", "dark", or "both"
    ):
        self.vl_threshold = vl_threshold
        self.min_led_on_time = min_led_on_time
        self.min_points_for_fit = min_points_for_fit
        self.fit_segment = fit_segment

        if fit_segment not in ["light", "dark", "both"]:
            raise ValueError(f"fit_segment must be 'light', 'dark', or 'both', got: {fit_segment}")

    @property
    def applicable_procedures(self) -> List[str]:
        """Applies to It measurements (for dark relaxation only)."""
        return ["It"]  # Dark It measurements only

    @property
    def metric_name(self) -> str:
        return "tau_dark"

    @property
    def metric_category(self) -> MetricCategory:
        return "photoresponse"

    def extract(
        self,
        measurement: pl.DataFrame,
        metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        """
        Extract relaxation time from ITS measurement.

        Supports extracting from:
        - LED ON segments (photoresponse buildup)
        - LED OFF segments (photoresponse decay / dark relaxation)
        - Both (tries both, returns best fit)

        Parameters
        ----------
        measurement : pl.DataFrame
            ITS data with columns: t (s), I (A), VL (V)
        metadata : dict
            Measurement metadata

        Returns
        -------
        DerivedMetric or None
            Metric with:
            - value_float: τ (relaxation time in seconds)
            - value_json: Full fitting results (τ, β, amplitude, R², etc.)
        """
        # Validate columns
        required_cols = {"t (s)", "I (A)", "VL (V)"}
        if not required_cols.issubset(measurement.columns):
            missing = required_cols - set(measurement.columns)
            logger.debug(
                f"Extractor {self.metric_name} skipped: MISSING_COLUMN ({missing})",
                extra={"run_id": metadata.get("run_id"), "reason": "MISSING_COLUMN"}
            )
            return None

        # Extract data
        time = measurement["t (s)"].to_numpy()
        current = measurement["I (A)"].to_numpy()
        vl = measurement["VL (V)"].to_numpy()

        # Identify LED states
        led_on_mask = vl > self.vl_threshold
        led_off_mask = ~led_on_mask

        # Try fitting based on configuration
        if self.fit_segment == "light":
            return self._fit_light_segment(time, current, vl, led_on_mask, metadata)
        elif self.fit_segment == "dark":
            return self._fit_dark_segment(time, current, vl, led_off_mask, metadata)
        elif self.fit_segment == "both":
            # Try light first, then dark if light fails
            light_metric = self._fit_light_segment(time, current, vl, led_on_mask, metadata)
            if light_metric is not None:
                return light_metric
            return self._fit_dark_segment(time, current, vl, led_off_mask, metadata)

        return None

    def _fit_light_segment(
        self,
        time: np.ndarray,
        current: np.ndarray,
        vl: np.ndarray,
        led_on_mask: np.ndarray,
        metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        """
        Fit stretched exponential to LED ON segment (photoresponse buildup).

        Returns
        -------
        Optional[DerivedMetric]
            Metric for light relaxation, or None if fitting fails
        """
        if not np.any(led_on_mask):
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (No LED ON segment)",
                extra={"run_id": metadata.get("run_id"), "reason": "PRECONDITION_FAILED"}
            )
            return None

        # Find longest continuous LED ON segment
        led_segment = self._find_longest_led_segment(time, led_on_mask)
        if led_segment is None:
            return None

        segment_start, segment_end = led_segment
        # segment_end is exclusive (for slicing), so use segment_end-1 for time access
        segment_duration = time[segment_end - 1] - time[segment_start]

        # Check if segment is long enough
        if segment_duration < self.min_led_on_time:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (Duration {segment_duration:.2f}s < {self.min_led_on_time}s)",
                extra={"run_id": metadata.get("run_id"), "reason": "PRECONDITION_FAILED"}
            )
            return None

        if segment_end - segment_start < self.min_points_for_fit:
            logger.debug(
                f"Extractor {self.metric_name} skipped: PRECONDITION_FAILED (Points {segment_end - segment_start} < {self.min_points_for_fit})",
                extra={"run_id": metadata.get("run_id"), "reason": "PRECONDITION_FAILED"}
            )
            return None

        # Extract segment data and reset time to start at 0
        # IMPORTANT: Skip first point (tends to be problematic measurement artifact)
        fit_start_idx = segment_start + 1  # Skip first point
        if fit_start_idx >= segment_end:
            return None  # Not enough points after skipping first

        t_segment = time[fit_start_idx:segment_end] - time[fit_start_idx]
        i_segment = current[fit_start_idx:segment_end]

        # Fit stretched exponential (Numba-accelerated!)
        try:
            fit_result = fit_stretched_exponential(t_segment, i_segment)
        except Exception as e:
            logger.debug(
                f"Extractor {self.metric_name} skipped: ALGORITHM_FAILURE (Fit exception: {e})",
                extra={"run_id": metadata.get("run_id"), "reason": "ALGORITHM_FAILURE"}
            )
            return None

        # Check fit quality
        if not fit_result['converged'] or fit_result['r_squared'] < 0.5:
            logger.debug(
                f"Extractor {self.metric_name} skipped: QUALITY_FAILURE (R2={fit_result['r_squared']:.4f}, Converged={fit_result['converged']})",
                extra={"run_id": metadata.get("run_id"), "reason": "QUALITY_FAILURE"}
            )
            return None

        # Extract fitted parameters
        tau = fit_result['tau']
        beta = fit_result['beta']
        amplitude = fit_result['amplitude']
        baseline = fit_result['baseline']
        r_squared = fit_result['r_squared']

        # Compute confidence and flags
        confidence = self._compute_confidence(fit_result)
        flags = self._build_flags(fit_result, tau, beta)

        # Build detailed JSON
        details = {
            'tau': tau,
            'beta': beta,
            'amplitude': amplitude,
            'baseline': baseline,
            'r_squared': r_squared,
            'n_iterations': fit_result['n_iterations'],
            'converged': fit_result['converged'],
            'segment_start': float(time[fit_start_idx]),  # Actual start (first point skipped)
            'segment_end': float(time[segment_end - 1]),  # segment_end is exclusive, use -1
            'segment_duration': float(time[segment_end - 1] - time[fit_start_idx]),
            'n_points_fitted': int(segment_end - fit_start_idx),
            'segment_type': 'light',  # Distinguish from dark fitting
            'first_point_skipped': True  # Flag indicating we skipped first point
        }

        # Return DerivedMetric
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=metadata.get("proc", metadata.get("procedure")),
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=tau,
            value_json=json.dumps(details),
            unit="s",
            extraction_method="stretched_exponential_numba_light",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=flags
        )

    def _fit_dark_segment(
        self,
        time: np.ndarray,
        current: np.ndarray,
        vl: np.ndarray,
        led_off_mask: np.ndarray,
        metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        """
        Fit stretched exponential to LED OFF segment (dark relaxation / photoresponse decay).

        This looks for segments AFTER LED turns off (following a LED ON period)
        to capture the photoresponse decay back to baseline.

        Returns
        -------
        Optional[DerivedMetric]
            Metric for dark relaxation, or None if fitting fails
        """
        if not np.any(led_off_mask):
            return None

        # Find LED OFF→ON transitions to identify dark segments after light exposure
        transitions = np.diff((~led_off_mask).astype(int))
        off_edges = np.where(transitions == -1)[0] + 1  # ON→OFF transitions

        if len(off_edges) == 0:
            # No LED turn-off events, try longest dark segment
            dark_segment = self._find_longest_led_segment(time, led_off_mask)
        else:
            # Find longest dark segment AFTER a LED OFF transition
            dark_segment = self._find_longest_dark_after_light(time, led_off_mask, off_edges)

        if dark_segment is None:
            return None

        segment_start, segment_end = dark_segment
        # segment_end is exclusive (for slicing), so use segment_end-1 for time access
        segment_duration = time[segment_end - 1] - time[segment_start]

        # Check if segment is long enough
        if segment_duration < self.min_led_on_time:  # Same duration threshold
            return None

        if segment_end - segment_start < self.min_points_for_fit:
            return None

        # Extract segment data and reset time to start at 0
        # IMPORTANT: Skip first point (tends to be problematic measurement artifact)
        fit_start_idx = segment_start + 1  # Skip first point
        if fit_start_idx >= segment_end:
            return None  # Not enough points after skipping first

        t_segment = time[fit_start_idx:segment_end] - time[fit_start_idx]
        i_segment = current[fit_start_idx:segment_end]

        # Fit stretched exponential (Numba-accelerated!)
        try:
            fit_result = fit_stretched_exponential(t_segment, i_segment)
        except Exception:
            return None

        # Check fit quality
        if not fit_result['converged'] or fit_result['r_squared'] < 0.5:
            return None

        # Extract fitted parameters
        tau = fit_result['tau']
        beta = fit_result['beta']
        amplitude = fit_result['amplitude']
        baseline = fit_result['baseline']
        r_squared = fit_result['r_squared']

        # Compute confidence and flags
        confidence = self._compute_confidence(fit_result)
        flags = self._build_flags(fit_result, tau, beta)

        # Build detailed JSON
        details = {
            'tau': tau,
            'beta': beta,
            'amplitude': amplitude,
            'baseline': baseline,
            'r_squared': r_squared,
            'n_iterations': fit_result['n_iterations'],
            'converged': fit_result['converged'],
            'segment_start': float(time[fit_start_idx]),  # Actual start (first point skipped)
            'segment_end': float(time[segment_end - 1]),  # segment_end is exclusive, use -1
            'segment_duration': float(time[segment_end - 1] - time[fit_start_idx]),
            'n_points_fitted': int(segment_end - fit_start_idx),
            'segment_type': 'dark',  # Distinguish from light fitting
            'first_point_skipped': True  # Flag indicating we skipped first point
        }

        # Return DerivedMetric
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=metadata.get("proc", metadata.get("procedure")),
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=tau,
            value_json=json.dumps(details),
            unit="s",
            extraction_method="stretched_exponential_numba_dark",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=flags
        )

    def _find_longest_dark_after_light(
        self,
        time: np.ndarray,
        led_off_mask: np.ndarray,
        off_edges: np.ndarray
    ) -> Optional[tuple]:
        """
        Find the longest dark segment that immediately follows a LED ON period.

        Parameters
        ----------
        time : np.ndarray
            Time values
        led_off_mask : np.ndarray
            Boolean mask where True = LED OFF
        off_edges : np.ndarray
            Indices where LED transitioned from ON to OFF

        Returns
        -------
        Optional[tuple]
            (start_index, end_index) of longest dark segment after light, or None
        """
        # For each OFF edge, find the dark segment that follows
        candidate_segments = []

        for off_edge in off_edges:
            # Start from the OFF transition
            start_idx = off_edge

            # Find how long the dark period lasts
            # Scan forward until LED turns back on or end of data
            end_idx = start_idx
            while end_idx < len(led_off_mask) and led_off_mask[end_idx]:
                end_idx += 1

            # Clamp end_idx to array bounds
            end_idx = min(end_idx, len(time))

            if end_idx > start_idx:
                duration = time[end_idx - 1] - time[start_idx]
                candidate_segments.append((start_idx, end_idx, duration))

        if not candidate_segments:
            return None

        # Return the longest segment
        longest = max(candidate_segments, key=lambda x: x[2])  # Sort by duration
        return (int(longest[0]), int(longest[1]))

    def _find_longest_led_segment(
        self,
        time: np.ndarray,
        led_on_mask: np.ndarray
    ) -> Optional[tuple]:
        """
        Find the longest continuous LED ON segment.

        Returns
        -------
        tuple or None
            (start_index, end_index) of longest segment, or None if no segments
        """
        # Find transitions
        transitions = np.diff(led_on_mask.astype(int))
        on_edges = np.where(transitions == 1)[0] + 1  # OFF→ON
        off_edges = np.where(transitions == -1)[0] + 1  # ON→OFF

        # Handle edge cases
        if led_on_mask[0]:
            on_edges = np.concatenate([[0], on_edges])
        if led_on_mask[-1]:
            off_edges = np.concatenate([off_edges, [len(led_on_mask)]])

        if len(on_edges) == 0 or len(off_edges) == 0:
            return None

        # Find longest segment
        segment_lengths = off_edges - on_edges
        longest_idx = np.argmax(segment_lengths)

        return (int(on_edges[longest_idx]), int(off_edges[longest_idx]))

    def _compute_confidence(self, fit_result: dict) -> float:
        """
        Compute confidence score based on fit quality.

        Parameters
        ----------
        fit_result : dict
            Fitting results from fit_stretched_exponential

        Returns
        -------
        float
            Confidence score (0-1)
        """
        confidence = 1.0

        # Penalty for low R²
        r_squared = fit_result['r_squared']
        if r_squared < 0.95:
            confidence *= 0.8
        if r_squared < 0.90:
            confidence *= 0.7
        if r_squared < 0.80:
            confidence *= 0.5

        # Penalty for non-convergence
        if not fit_result['converged']:
            confidence *= 0.6

        # Penalty for many iterations (suggests difficult fit)
        if fit_result['n_iterations'] > 80:
            confidence *= 0.9

        return max(0.0, min(1.0, confidence))

    def _build_flags(self, fit_result: dict, tau: float, beta: float) -> Optional[str]:
        """
        Build warning flags based on fit quality and physical constraints.

        Parameters
        ----------
        fit_result : dict
            Fitting results
        tau : float
            Fitted relaxation time (s)
        beta : float
            Fitted stretching exponent

        Returns
        -------
        str or None
            Comma-separated flags or None
        """
        flags = []

        if not fit_result['converged']:
            flags.append("FIT_NOT_CONVERGED")

        if fit_result['r_squared'] < 0.8:
            flags.append("LOW_R_SQUARED")

        if tau < 1.0:
            flags.append("VERY_FAST_RELAXATION")
        elif tau > 50000.0:
            flags.append("EXTREMELY_SLOW_RELAXATION")  # > ~14 hours
        elif tau > 10000.0:
            flags.append("VERY_SLOW_RELAXATION")  # > ~2.8 hours

        if beta < 0.3:
            flags.append("HIGHLY_STRETCHED")
        elif beta > 0.95:
            flags.append("NEAR_EXPONENTIAL")

        return ",".join(flags) if flags else None

    def validate(self, result: DerivedMetric) -> bool:
        """
        Validate extracted relaxation time is physically reasonable.

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

        tau = result.value_float

        # Relaxation time should be positive and reasonable
        # Dark relaxation can be very slow (persistent photoconductivity)
        # Accept up to ~1 day (86400s), with warnings for very slow times
        return 0.01 < tau < 100000.0
