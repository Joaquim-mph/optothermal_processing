"""
ITS Three-Phase Relaxation Extractor.

For illuminated ITS measurements with complete LED cycles (OFF → ON → OFF),
this extractor fits stretched exponentials to all THREE phases:

1. PRE-DARK phase (LED OFF before illumination)
2. LIGHT phase (LED ON - photoresponse buildup)
3. POST-DARK phase (LED OFF after illumination - photoresponse decay)

This provides complete relaxation dynamics across the full measurement cycle.
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


class ITSThreePhaseFitExtractor(MetricExtractor):
    """
    Extract relaxation times from all three phases of illuminated ITS measurements.

    For ITS measurements with complete LED cycles (OFF → ON → OFF), this extractor
    identifies and fits stretched exponentials to each phase:

    Phase 1 (PRE-DARK): LED OFF before illumination
        - Baseline relaxation / drift before photoresponse
        - I(t) = I_baseline + A * exp(-(t/τ_pre)^β_pre)

    Phase 2 (LIGHT): LED ON
        - Photoresponse buildup during illumination
        - I(t) = I_baseline + A * exp(-(t/τ_light)^β_light)

    Phase 3 (POST-DARK): LED OFF after illumination
        - Photoresponse decay back to dark baseline
        - I(t) = I_baseline + A * exp(-(t/τ_post)^β_post)

    This provides 3 complete relaxation characterizations from a single measurement,
    enabling detailed analysis of carrier dynamics.

    Parameters
    ----------
    vl_threshold : float
        LED ON threshold (default: 0.1V)
    min_phase_duration : float
        Minimum duration for each phase (seconds, default: 60s = 1 minute)
    min_points_for_fit : int
        Minimum data points required for reliable fit (default: 50)
    require_all_phases : bool
        If True, only extract if all 3 phases are present
        If False, extract whatever phases are available (default: True)

    Examples
    --------
    >>> extractor = ITSThreePhaseFitExtractor()
    >>> metric = extractor.extract(its_measurement, metadata)
    >>> import json
    >>> details = json.loads(metric.value_json)
    >>> print(f"τ_pre = {details['pre_dark']['tau']:.2f} s")
    >>> print(f"τ_light = {details['light']['tau']:.2f} s")
    >>> print(f"τ_post = {details['post_dark']['tau']:.2f} s")
    """

    def __init__(
        self,
        vl_threshold: float = 0.1,
        min_phase_duration: float = 60.0,  # 1 minute minimum
        min_points_for_fit: int = 50,
        require_all_phases: bool = True
    ):
        self.vl_threshold = vl_threshold
        self.min_phase_duration = min_phase_duration
        self.min_points_for_fit = min_points_for_fit
        self.require_all_phases = require_all_phases

    @property
    def applicable_procedures(self) -> List[str]:
        """Applies to ITS and ITt measurements."""
        return ["ITS", "ITt"]

    @property
    def metric_name(self) -> str:
        return "its_three_phase_relaxation"

    @property
    def metric_category(self) -> MetricCategory:
        return "photoresponse"

    def extract(
        self,
        measurement: pl.DataFrame,
        metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        """
        Extract relaxation times from all three phases of ITS measurement.

        Parameters
        ----------
        measurement : pl.DataFrame
            ITS data with columns: t (s), I (A), VL (V)
        metadata : dict
            Measurement metadata

        Returns
        -------
        DerivedMetric or None
            Metric with three-phase relaxation data, or None if extraction fails
        """
        # Validate columns
        required_cols = {"t (s)", "I (A)", "VL (V)"}
        if not required_cols.issubset(measurement.columns):
            return None

        # Extract data
        time = measurement["t (s)"].to_numpy()
        current = measurement["I (A)"].to_numpy()
        vl = measurement["VL (V)"].to_numpy()

        # Identify LED states
        led_on_mask = vl > self.vl_threshold

        # Find phase boundaries
        phases = self._identify_phases(time, current, vl, led_on_mask)

        if phases is None:
            return None

        # Fit each phase
        pre_dark_fit = None
        light_fit = None
        post_dark_fit = None
        phases_fitted = []

        if phases["pre_dark"] is not None:
            pre_dark_fit = self._fit_phase(
                time, current, phases["pre_dark"], "pre_dark"
            )
            if pre_dark_fit is not None:
                phases_fitted.append("pre_dark")

        if phases["light"] is not None:
            light_fit = self._fit_phase(
                time, current, phases["light"], "light"
            )
            if light_fit is not None:
                phases_fitted.append("light")

        if phases["post_dark"] is not None:
            post_dark_fit = self._fit_phase(
                time, current, phases["post_dark"], "post_dark"
            )
            if post_dark_fit is not None:
                phases_fitted.append("post_dark")

        # Check if we have enough fits
        if self.require_all_phases and len(phases_fitted) < 3:
            return None

        if len(phases_fitted) == 0:
            return None

        # Build comprehensive results
        details = {
            "pre_dark": pre_dark_fit,
            "light": light_fit,
            "post_dark": post_dark_fit,
            "phases_fitted": phases_fitted,
            "n_phases": len(phases_fitted),
            "all_phases_present": len(phases_fitted) == 3
        }

        # Compute overall confidence (average of fitted phases)
        confidences = []
        if pre_dark_fit and "confidence" in pre_dark_fit:
            confidences.append(pre_dark_fit["confidence"])
        if light_fit and "confidence" in light_fit:
            confidences.append(light_fit["confidence"])
        if post_dark_fit and "confidence" in post_dark_fit:
            confidences.append(post_dark_fit["confidence"])

        overall_confidence = np.mean(confidences) if confidences else 0.5

        # Build flags
        flags = self._build_flags(pre_dark_fit, light_fit, post_dark_fit, phases_fitted)

        # Primary value: light phase τ (most important for photoresponse)
        if light_fit and "tau" in light_fit:
            primary_value = light_fit["tau"]
        elif post_dark_fit and "tau" in post_dark_fit:
            primary_value = post_dark_fit["tau"]
        elif pre_dark_fit and "tau" in pre_dark_fit:
            primary_value = pre_dark_fit["tau"]
        else:
            primary_value = 0.0

        # Return DerivedMetric
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=metadata.get("proc", metadata.get("procedure")),
            seq_num=metadata.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=primary_value,  # τ_light as primary value
            value_json=json.dumps(details),
            unit="s",
            extraction_method="three_phase_stretched_exponential",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=overall_confidence,
            flags=flags
        )

    def _identify_phases(
        self,
        time: np.ndarray,
        current: np.ndarray,
        vl: np.ndarray,
        led_on_mask: np.ndarray
    ) -> Optional[Dict[str, Optional[tuple]]]:
        """
        Identify the three phases: PRE-DARK, LIGHT, POST-DARK.

        Returns
        -------
        dict or None
            Dictionary with keys "pre_dark", "light", "post_dark"
            Each value is (start_idx, end_idx) tuple or None
        """
        # Find LED transitions
        transitions = np.diff(led_on_mask.astype(int))
        on_edges = np.where(transitions == 1)[0] + 1   # OFF→ON
        off_edges = np.where(transitions == -1)[0] + 1  # ON→OFF

        # Handle edge cases
        if led_on_mask[0]:
            on_edges = np.concatenate([[0], on_edges])
        if led_on_mask[-1]:
            off_edges = np.concatenate([off_edges, [len(led_on_mask)]])

        # We need at least one LED ON period
        if len(on_edges) == 0 or len(off_edges) == 0:
            return None

        # Find the main LED ON period (assume there's one main pulse)
        # Use the longest LED ON segment
        if len(on_edges) > 0 and len(off_edges) > 0:
            led_on_durations = off_edges - on_edges
            main_pulse_idx = np.argmax(led_on_durations)
            light_start = on_edges[main_pulse_idx]
            light_end = off_edges[main_pulse_idx]
        else:
            return None

        # PRE-DARK: From start to LED ON
        if light_start > 0:
            pre_dark = (0, light_start)
        else:
            pre_dark = None

        # LIGHT: LED ON period
        light = (light_start, light_end)

        # POST-DARK: From LED OFF to end
        if light_end < len(time):
            post_dark = (light_end, len(time))
        else:
            post_dark = None

        # Validate each phase
        phases = {
            "pre_dark": self._validate_phase(time, pre_dark, "pre_dark"),
            "light": self._validate_phase(time, light, "light"),
            "post_dark": self._validate_phase(time, post_dark, "post_dark")
        }

        return phases

    def _validate_phase(
        self,
        time: np.ndarray,
        phase: Optional[tuple],
        phase_name: str
    ) -> Optional[tuple]:
        """
        Validate that a phase meets minimum duration and point requirements.

        Parameters
        ----------
        time : np.ndarray
            Time array
        phase : tuple or None
            (start_idx, end_idx) of phase
        phase_name : str
            Name of phase for logging

        Returns
        -------
        tuple or None
            Validated phase tuple or None if invalid
        """
        if phase is None:
            return None

        start_idx, end_idx = phase

        # Check duration
        if end_idx <= start_idx:
            return None

        duration = time[end_idx - 1] - time[start_idx]
        if duration < self.min_phase_duration:
            return None

        # Check point count
        n_points = end_idx - start_idx
        if n_points < self.min_points_for_fit:
            return None

        return phase

    def _fit_phase(
        self,
        time: np.ndarray,
        current: np.ndarray,
        phase: tuple,
        phase_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fit stretched exponential to a single phase.

        Parameters
        ----------
        time : np.ndarray
            Full time array
        current : np.ndarray
            Full current array
        phase : tuple
            (start_idx, end_idx) of phase to fit
        phase_name : str
            Name of phase ("pre_dark", "light", "post_dark")

        Returns
        -------
        dict or None
            Fitting results with tau, beta, R², etc., or None if fit fails
        """
        start_idx, end_idx = phase

        # Extract phase data
        t_phase = time[start_idx:end_idx] - time[start_idx]  # Reset to t=0
        i_phase = current[start_idx:end_idx]

        # Fit stretched exponential
        try:
            fit_result = fit_stretched_exponential(t_phase, i_phase)
        except Exception:
            return None

        # Check fit quality
        if not fit_result['converged'] or fit_result['r_squared'] < 0.5:
            return None

        # Extract parameters
        tau = fit_result['tau']
        beta = fit_result['beta']
        amplitude = fit_result['amplitude']
        baseline = fit_result['baseline']
        r_squared = fit_result['r_squared']

        # Compute confidence
        confidence = self._compute_phase_confidence(fit_result, tau, beta)

        # Build result dictionary
        result = {
            "phase": phase_name,
            "tau": float(tau),
            "beta": float(beta),
            "amplitude": float(amplitude),
            "baseline": float(baseline),
            "r_squared": float(r_squared),
            "n_iterations": int(fit_result['n_iterations']),
            "converged": bool(fit_result['converged']),
            "segment_start": float(time[start_idx]),
            "segment_end": float(time[end_idx - 1]),
            "segment_duration": float(time[end_idx - 1] - time[start_idx]),
            "n_points_fitted": int(end_idx - start_idx),
            "confidence": float(confidence)
        }

        return result

    def _compute_phase_confidence(
        self,
        fit_result: dict,
        tau: float,
        beta: float
    ) -> float:
        """
        Compute confidence score for a single phase fit.

        Parameters
        ----------
        fit_result : dict
            Fitting results
        tau : float
            Fitted relaxation time
        beta : float
            Fitted stretching exponent

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

        # Penalty for many iterations
        if fit_result['n_iterations'] > 80:
            confidence *= 0.9

        return max(0.0, min(1.0, confidence))

    def _build_flags(
        self,
        pre_dark_fit: Optional[dict],
        light_fit: Optional[dict],
        post_dark_fit: Optional[dict],
        phases_fitted: List[str]
    ) -> Optional[str]:
        """
        Build warning flags based on fit quality and completeness.

        Parameters
        ----------
        pre_dark_fit, light_fit, post_dark_fit : dict or None
            Fit results for each phase
        phases_fitted : list
            List of successfully fitted phase names

        Returns
        -------
        str or None
            Comma-separated flags or None
        """
        flags = []

        # Check completeness
        if len(phases_fitted) < 3:
            missing = set(["pre_dark", "light", "post_dark"]) - set(phases_fitted)
            for phase in missing:
                flags.append(f"MISSING_{phase.upper()}")

        # Check individual phase quality
        for fit, phase_name in [
            (pre_dark_fit, "PRE_DARK"),
            (light_fit, "LIGHT"),
            (post_dark_fit, "POST_DARK")
        ]:
            if fit is None:
                continue

            if not fit.get("converged", False):
                flags.append(f"{phase_name}_NOT_CONVERGED")

            if fit.get("r_squared", 0) < 0.8:
                flags.append(f"{phase_name}_LOW_R2")

            tau = fit.get("tau", 0)
            if tau < 1.0:
                flags.append(f"{phase_name}_VERY_FAST")
            elif tau > 100.0:
                flags.append(f"{phase_name}_VERY_SLOW")

            beta = fit.get("beta", 1.0)
            if beta < 0.3:
                flags.append(f"{phase_name}_HIGHLY_STRETCHED")

        return ",".join(flags) if flags else None

    def validate(self, result: DerivedMetric) -> bool:
        """
        Validate extracted three-phase relaxation metric.

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

        # Primary value (τ_light) should be in reasonable range
        tau = result.value_float
        if not (0.01 < tau < 1000.0):
            return False

        # Check that at least one phase was fitted
        try:
            details = json.loads(result.value_json)
            if details["n_phases"] == 0:
                return False
        except (json.JSONDecodeError, KeyError):
            return False

        return True
