"""
Photoresponse extractor for It, ITt, and Vt measurements.

Extracts photoresponse metrics (ΔI_ds or ΔV_ds) by analyzing the difference
between LED ON and LED OFF periods using the VL (V) column as a mask.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

from src.models.derived_metrics import DerivedMetric, MetricCategory
from .base import MetricExtractor


class PhotoresponseExtractor(MetricExtractor):
    """
    Extract photoresponse (ΔI or ΔV) from time-series measurements with LED modulation.

    Analyzes It (current vs time), ITt (current vs time with temp), and
    Vt (voltage vs time) measurements to extract the change in signal
    when the LED is switched on/off.

    Parameters
    ----------
    vl_threshold : float
        Voltage threshold for LED state detection (V). VL > threshold = ON.
        Default: 0.1V
    min_samples_per_state : int
        Minimum number of samples required in each state (ON/OFF) for reliable extraction.
        Default: 5

    Metrics Extracted
    -----------------
    - delta_current (It, ITt): ΔI_ds = I_on - I_off (A)
    - delta_voltage (Vt): ΔV_ds = V_on - V_off (V)
    - response_ratio: (mean_on / mean_off) - 1 (fractional change)
    - response_time: Not yet implemented (would need rise/fall time analysis)

    Examples
    --------
    >>> extractor = PhotoresponseExtractor(vl_threshold=0.1)
    >>> metric = extractor.extract(measurement, metadata)
    >>> print(f"ΔI = {metric.value_float} A")
    """

    def __init__(
        self,
        vl_threshold: float = 0.1,
        min_samples_per_state: int = 5
    ):
        """Initialize extractor with detection parameters."""
        self.vl_threshold = vl_threshold
        self.min_samples_per_state = min_samples_per_state

    @property
    def applicable_procedures(self) -> List[str]:
        """This extractor applies to It, ITt, and Vt procedures."""
        return ["It", "ITt", "Vt"]

    @property
    def metric_name(self) -> str:
        """Name of the primary metric extracted."""
        return "photoresponse"

    @property
    def metric_category(self) -> MetricCategory:
        """Category of this metric."""
        return "photoresponse"

    def extract(
        self,
        measurement: pl.DataFrame,
        metadata: Dict[str, Any]
    ) -> Optional[DerivedMetric]:
        """
        Extract photoresponse from It/ITt/Vt measurement.

        Parameters
        ----------
        measurement : pl.DataFrame
            Measurement data with columns: t (s), I (A) or VDS (V), VL (V)
        metadata : dict
            Measurement metadata (run_id, chip info, procedure, etc.)

        Returns
        -------
        DerivedMetric or None
            Metric with photoresponse data, or None if extraction fails
        """
        procedure = metadata.get("proc", metadata.get("procedure"))

        # Validate VL column exists
        if "VL (V)" not in measurement.columns:
            return None

        vl = measurement["VL (V)"].to_numpy()

        # Determine measured quantity based on procedure
        if procedure in ["It", "ITt"]:
            # Current measurement
            if "I (A)" not in measurement.columns:
                return None

            measured_values = measurement["I (A)"].to_numpy()
            metric_name = "delta_current"
            unit = "A"

        elif procedure == "Vt":
            # Voltage measurement
            if "VDS (V)" not in measurement.columns:
                return None

            measured_values = measurement["VDS (V)"].to_numpy()
            metric_name = "delta_voltage"
            unit = "V"
        else:
            return None

        # Identify LED states
        led_on_mask = vl > self.vl_threshold
        led_off_mask = ~led_on_mask

        # Check we have enough samples in each state
        n_on = np.sum(led_on_mask)
        n_off = np.sum(led_off_mask)

        if n_on < self.min_samples_per_state or n_off < self.min_samples_per_state:
            return None

        # Extract values during ON and OFF states
        values_on = measured_values[led_on_mask]
        values_off = measured_values[led_off_mask]

        # Calculate statistics for all ON/OFF samples (for metadata)
        mean_on = np.mean(values_on)
        mean_off = np.mean(values_off)
        std_on = np.std(values_on)
        std_off = np.std(values_off)

        # Analyze LED cycles to assess consistency
        cycle_analysis = self._analyze_cycles(vl, measured_values, led_on_mask)

        # Calculate photoresponse using cycle-based approach to handle drift
        # This compares adjacent ON/OFF periods rather than global means
        delta = self._calculate_photoresponse_from_cycles(
            measured_values, led_on_mask, cycle_analysis
        )

        # Calculate response ratio (fractional change)
        if np.abs(mean_off) > 1e-15:
            response_ratio = (mean_on / mean_off) - 1.0  # Fractional change
        else:
            response_ratio = None

        # Build detailed results
        result = self._build_result(
            delta=delta,
            mean_on=mean_on,
            mean_off=mean_off,
            std_on=std_on,
            std_off=std_off,
            response_ratio=response_ratio,
            n_on=n_on,
            n_off=n_off,
            cycle_analysis=cycle_analysis,
            procedure=procedure
        )

        # Build DerivedMetric
        return DerivedMetric(
            run_id=metadata["run_id"],
            chip_number=metadata["chip_number"],
            chip_group=metadata["chip_group"],
            procedure=procedure,
            seq_num=metadata.get("seq_num"),
            metric_name=metric_name,
            metric_category=self.metric_category,
            value_float=delta,
            value_json=json.dumps(result["details"]),
            unit=unit,
            extraction_method="led_state_difference",
            extraction_version=metadata.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=result["confidence"],
            flags=result["flags"]
        )

    def _calculate_photoresponse_from_cycles(
        self,
        values: np.ndarray,
        led_on_mask: np.ndarray,
        cycle_analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate photoresponse as difference between first and last points of LED ON interval.

        Uses the VL (V) column as a step function mask:
        - VL = 0 → 0 → v_led → v_led → 0 → 0
        - Photoresponse = I(last_ON_point) - I(first_ON_point)

        This simple approach captures the instantaneous change without
        worrying about drift for now (drift will be handled separately later).

        Parameters
        ----------
        values : np.ndarray
            Measured values (current or voltage)
        led_on_mask : np.ndarray
            Boolean mask for LED ON state (VL > threshold)
        cycle_analysis : dict
            Cycle analysis from _analyze_cycles (not used in simple method)

        Returns
        -------
        float
            Photoresponse (last_ON - first_ON) in same units as values
        """
        # Find indices where LED is ON
        on_indices = np.where(led_on_mask)[0]

        if len(on_indices) == 0:
            # No LED ON period detected - return 0
            return 0.0

        # Get first and last points of LED ON interval
        first_on_idx = on_indices[0]
        last_on_idx = on_indices[-1]

        # Photoresponse = difference between last and first ON points
        i_first = values[first_on_idx]
        i_last = values[last_on_idx]

        photoresponse = i_last - i_first

        return float(photoresponse)

    def _analyze_cycles(
        self,
        vl: np.ndarray,
        values: np.ndarray,
        led_on_mask: np.ndarray
    ) -> Dict[str, Any]:
        """
        Analyze individual LED ON/OFF cycles for consistency.

        Returns dict with:
        - n_cycles: Number of complete ON/OFF cycles
        - cycle_deltas: ΔI or ΔV for each cycle
        - delta_consistency: Std dev of cycle deltas
        """
        # Find transitions
        transitions = np.diff(led_on_mask.astype(int))
        on_starts = np.where(transitions == 1)[0] + 1
        off_starts = np.where(transitions == -1)[0] + 1

        # Count cycles (a cycle = one ON period + one OFF period)
        n_cycles = min(len(on_starts), len(off_starts))

        if n_cycles == 0:
            return {
                "n_cycles": 0,
                "cycle_deltas": [],
                "delta_consistency": None
            }

        # Calculate delta for each cycle
        cycle_deltas = []
        for i in range(n_cycles):
            # Find next transition after this ON start
            if i < len(off_starts):
                on_end = off_starts[i]
            else:
                on_end = len(values)

            # Find next transition after this OFF start
            if i + 1 < len(on_starts):
                off_end = on_starts[i + 1]
            else:
                off_end = len(values)

            # Extract values for this cycle
            on_values = values[on_starts[i]:on_end]
            off_values = values[off_starts[i]:off_end]

            if len(on_values) > 0 and len(off_values) > 0:
                cycle_delta = np.mean(on_values) - np.mean(off_values)
                cycle_deltas.append(float(cycle_delta))

        # Calculate consistency
        if len(cycle_deltas) > 1:
            delta_consistency = np.std(cycle_deltas)
        else:
            delta_consistency = None

        return {
            "n_cycles": n_cycles,
            "cycle_deltas": cycle_deltas,
            "delta_consistency": float(delta_consistency) if delta_consistency is not None else None
        }

    def _build_result(
        self,
        delta: float,
        mean_on: float,
        mean_off: float,
        std_on: float,
        std_off: float,
        response_ratio: Optional[float],
        n_on: int,
        n_off: int,
        cycle_analysis: Dict[str, Any],
        procedure: str
    ) -> Dict[str, Any]:
        """
        Build result dictionary with photoresponse metrics and quality assessment.

        Returns dict with:
        - delta: Photoresponse value (ΔI or ΔV)
        - confidence: Quality score
        - flags: Warning string or None
        - details: JSON-serializable dict with all info
        """
        # Quality checks
        checks = {
            "GOOD_SNR": False,
            "MULTIPLE_CYCLES": False,
            "CONSISTENT_CYCLES": False,
            "LOW_NOISE": False,
            "NO_RESPONSE": False
        }

        # Check signal-to-noise ratio
        noise_level = max(std_on, std_off)
        if noise_level > 0:
            snr = np.abs(delta) / noise_level
            if snr > 3.0:  # SNR > 3 is good
                checks["GOOD_SNR"] = True

        # Check for multiple cycles
        if cycle_analysis["n_cycles"] >= 2:
            checks["MULTIPLE_CYCLES"] = True

        # Check cycle consistency
        if (cycle_analysis["delta_consistency"] is not None and
            np.abs(delta) > 0 and
            cycle_analysis["delta_consistency"] / np.abs(delta) < 0.2):  # < 20% variation
            checks["CONSISTENT_CYCLES"] = True

        # Check noise level
        if std_on < np.abs(mean_on) * 0.1 and std_off < np.abs(mean_off) * 0.1:
            checks["LOW_NOISE"] = True

        # Check for no response
        if np.abs(delta) < max(std_on, std_off):
            checks["NO_RESPONSE"] = True

        # Compute confidence score (0.0 to 1.0)
        confidence = 0.0

        if checks["GOOD_SNR"]:
            confidence += 0.4
        if checks["MULTIPLE_CYCLES"]:
            confidence += 0.2
        if checks["CONSISTENT_CYCLES"]:
            confidence += 0.2
        if checks["LOW_NOISE"]:
            confidence += 0.2

        if checks["NO_RESPONSE"]:
            confidence = max(0.1, confidence - 0.5)

        confidence = min(1.0, confidence)

        # Build flags
        flag_list = []
        if checks["NO_RESPONSE"]:
            flag_list.append("NO_RESPONSE")
        if not checks["GOOD_SNR"]:
            flag_list.append("LOW_SNR")
        if not checks["MULTIPLE_CYCLES"]:
            flag_list.append("SINGLE_CYCLE")
        if not checks["CONSISTENT_CYCLES"] and checks["MULTIPLE_CYCLES"]:
            flag_list.append("INCONSISTENT_CYCLES")

        flags = ",".join(flag_list) if flag_list else None

        # Build detailed JSON
        details = {
            "delta": float(delta),
            "mean_on": float(mean_on),
            "mean_off": float(mean_off),
            "std_on": float(std_on),
            "std_off": float(std_off),
            "response_ratio": float(response_ratio) if response_ratio is not None else None,
            "n_samples_on": int(n_on),
            "n_samples_off": int(n_off),
            "n_cycles": cycle_analysis["n_cycles"],
            "cycle_deltas": cycle_analysis["cycle_deltas"],
            "delta_consistency": cycle_analysis["delta_consistency"],
            "snr": float(snr) if 'snr' in locals() else None,
            "checks": checks
        }

        return {
            "delta": delta,
            "confidence": confidence,
            "flags": flags,
            "details": details
        }

    def validate(self, result: DerivedMetric) -> bool:
        """
        Validate extracted photoresponse metric.

        Basic sanity checks:
        - Delta value is finite
        - Confidence is in [0, 1]
        - Unit matches procedure
        """
        if not np.isfinite(result.value_float):
            return False

        if not (0.0 <= result.confidence <= 1.0):
            return False

        # Check unit matches procedure
        if result.procedure in ["It", "ITt"]:
            if result.unit != "A":
                return False
        elif result.procedure == "Vt":
            if result.unit != "V":
                return False

        return True
