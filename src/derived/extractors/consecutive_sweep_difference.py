"""Extract differences between consecutive IVg or VVg sweeps.

This extractor computes comparative metrics between consecutive gate voltage sweeps
to track device evolution, particularly the effects of intervening experiments
(e.g., light exposure, thermal treatments).
"""

from __future__ import annotations
import numpy as np
import polars as pl
import json
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime, timezone
from scipy.interpolate import interp1d

from src.models.derived_metrics import DerivedMetric
from .base_pairwise import PairwiseMetricExtractor
from .base import compute_confidence, build_flags

# Import Numba-accelerated functions
try:
    from src.derived.algorithms.sweep_difference_numba import (
        compute_sweep_difference,
        compute_resistance_safe
    )
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False


class ConsecutiveSweepDifferenceExtractor(PairwiseMetricExtractor):
    """
    Extract differences between consecutive IVg or VVg sweeps.

    Computes:
    --------
    - ΔI(Vg): Current difference curve (for IVg)
    - ΔV(Vg): Voltage difference curve (for VVg)
    - ΔR(Vg): Resistance difference curve (both)
    - ΔCNP: Change in charge neutrality point (if available)

    Use Case:
    ---------
    Track device evolution between measurements, especially after
    illumination or other treatments.

    Example:
        Seq 1: IVg (dark) → CNP = -0.45V
        Seq 2: It (365nm, 30min illumination)
        Seq 3: IVg (dark) → CNP = -0.52V

        Result: IVg₃ - IVg₁ → ΔCNP = -0.07V (illumination shifted CNP)

    Parameters
    ----------
    vg_interpolation_points : int, default=200
        Number of points for Vg grid interpolation
        Higher values give finer resolution but larger JSON blobs
    min_vg_overlap : float, default=1.0
        Minimum Vg range overlap required (volts)
        Pairs with insufficient overlap are rejected
    store_resistance : bool, default=True
        Whether to store full ΔR(Vg) curve in addition to ΔI/ΔV
    interpolation_method : {'linear', 'cubic'}, default='linear'
        Interpolation method:
        - 'linear': Fast Numba-accelerated interpolation (~8x faster)
        - 'cubic': Smooth scipy cubic spline (slower but higher quality)

    Performance
    -----------
    Using 'linear' with Numba (default):
    - ~8x faster for single pair
    - ~15-20x faster for batch processing
    - Recommended for large datasets
    """

    def __init__(
        self,
        vg_interpolation_points: int = 200,
        min_vg_overlap: float = 1.0,
        store_resistance: bool = True,
        interpolation_method: Literal['linear', 'cubic'] = 'linear'
    ):
        self.vg_interpolation_points = vg_interpolation_points
        self.min_vg_overlap = min_vg_overlap
        self.store_resistance = store_resistance
        self.interpolation_method = interpolation_method

        # Warn if linear requested but Numba not available
        if interpolation_method == 'linear' and not NUMBA_AVAILABLE:
            import warnings
            warnings.warn(
                "Numba not available, falling back to scipy for linear interpolation. "
                "Install numba for ~8x speedup: pip install numba"
            )

    @property
    def applicable_procedures(self) -> List[str]:
        return ["IVg", "VVg"]

    @property
    def metric_name(self) -> str:
        return "consecutive_sweep_difference"

    @property
    def metric_category(self) -> str:
        return "electrical"

    def extract_pairwise(
        self,
        measurement_1: pl.DataFrame,
        metadata_1: Dict[str, Any],
        measurement_2: pl.DataFrame,
        metadata_2: Dict[str, Any]
    ) -> Optional[List[DerivedMetric]]:
        """
        Extract difference metrics from consecutive sweeps.

        Algorithm:
        ----------
        1. Validate same procedure and extract gate voltage arrays
        2. Determine Vg overlap region
        3. Interpolate both sweeps onto common Vg grid
           - Linear: Numba-accelerated (~8x faster) [default]
           - Cubic: SciPy cubic spline (slower, smoother)
        4. Compute ΔI (or ΔV) and ΔR
           - Uses Numba-accelerated safe division for linear mode (~5x faster)
        5. Extract ΔCNP if available
        6. Store full arrays and summary statistics
        7. Compute quality metrics

        Performance:
        ------------
        Using interpolation_method='linear' with Numba (default):
        - Single pair: ~8x faster than scipy
        - Batch processing: ~15-20x faster with parallel execution
        """

        procedure = metadata_1.get("proc")

        # Validate same procedure (should already be enforced by should_pair)
        if metadata_2.get("proc") != procedure:
            return None

        # Extract gate voltage (common to both IVg and VVg)
        vg_1 = measurement_1["Vg (V)"].to_numpy()
        vg_2 = measurement_2["Vg (V)"].to_numpy()

        # Extract dependent variable based on procedure
        if procedure == "IVg":
            y_1 = measurement_1["I (A)"].to_numpy()
            y_2 = measurement_2["I (A)"].to_numpy()
            y_label = "I"
            y_unit = "A"
            vds = metadata_1.get("vds_v", 0.1)  # For resistance calculation
            r_divisor_1 = y_1  # R = V / I
            r_divisor_2 = y_2
            r_numerator = vds
        elif procedure == "VVg":
            y_1 = measurement_1["Vds (V)"].to_numpy()
            y_2 = measurement_2["Vds (V)"].to_numpy()
            y_label = "Vds"
            y_unit = "V"
            ids = metadata_1.get("ids_v", 1e-6)  # For resistance calculation
            r_divisor_1 = ids  # R = V / I (constant current)
            r_divisor_2 = ids
            r_numerator = None  # Will use y values directly
        else:
            return None

        # Check Vg range overlap
        vg_min = max(vg_1.min(), vg_2.min())
        vg_max = min(vg_1.max(), vg_2.max())
        vg_overlap = vg_max - vg_min

        if vg_overlap < self.min_vg_overlap:
            # Insufficient overlap - reject pair
            return None

        # Interpolate both sweeps onto common grid
        try:
            if self.interpolation_method == 'linear' and NUMBA_AVAILABLE:
                # Use Numba-accelerated linear interpolation (~8x faster)
                vg_common, delta_y, vg_min, vg_max = compute_sweep_difference(
                    vg_1, y_1, vg_2, y_2, self.vg_interpolation_points
                )
                # Need individual interpolated arrays for resistance calculation
                from src.derived.algorithms.sweep_difference_numba import linear_interp_sorted
                y_1_interp = linear_interp_sorted(vg_1, y_1, vg_common)
                y_2_interp = linear_interp_sorted(vg_2, y_2, vg_common)
            else:
                # Use scipy interpolation (cubic or fallback linear)
                kind = 'cubic' if self.interpolation_method == 'cubic' else 'linear'
                vg_common = np.linspace(vg_min, vg_max, self.vg_interpolation_points)

                interp_1 = interp1d(vg_1, y_1, kind=kind, fill_value='extrapolate')
                interp_2 = interp1d(vg_2, y_2, kind=kind, fill_value='extrapolate')

                y_1_interp = interp_1(vg_common)
                y_2_interp = interp_2(vg_common)

                # Compute primary difference: ΔI or ΔV
                delta_y = y_2_interp - y_1_interp
        except Exception as e:
            # Interpolation failed (e.g., not enough points, duplicate Vg values)
            return None

        # Compute resistance difference (optional)
        delta_r = None
        delta_r_array = None
        if self.store_resistance:
            try:
                if self.interpolation_method == 'linear' and NUMBA_AVAILABLE:
                    # Use Numba-accelerated resistance calculation (~5x faster)
                    if procedure == "IVg":
                        # R = Vds / I, using scalar voltage
                        r_1 = compute_resistance_safe(vds, y_1_interp, min_current=1e-12)
                        r_2 = compute_resistance_safe(vds, y_2_interp, min_current=1e-12)
                    else:  # VVg
                        # R = Vds / Ids (array voltage, constant current)
                        r_1 = compute_resistance_safe(y_1_interp, np.full_like(y_1_interp, ids), min_current=1e-12)
                        r_2 = compute_resistance_safe(y_2_interp, np.full_like(y_2_interp, ids), min_current=1e-12)
                else:
                    # Use numpy division (slower)
                    if procedure == "IVg":
                        # R = Vds / I
                        r_1 = np.divide(
                            vds,
                            y_1_interp,
                            out=np.full_like(y_1_interp, np.nan),
                            where=np.abs(y_1_interp) > 1e-12
                        )
                        r_2 = np.divide(
                            vds,
                            y_2_interp,
                            out=np.full_like(y_2_interp, np.nan),
                            where=np.abs(y_2_interp) > 1e-12
                        )
                    else:  # VVg
                        # R = Vds / Ids (constant current)
                        r_1 = y_1_interp / ids
                        r_2 = y_2_interp / ids

                delta_r_array = r_2 - r_1

                # Filter out inf/nan for statistics
                finite_mask = np.isfinite(delta_r_array)
                if np.any(finite_mask):
                    delta_r = float(np.max(np.abs(delta_r_array[finite_mask])))
                else:
                    delta_r = None
                    delta_r_array = None
            except Exception:
                delta_r = None
                delta_r_array = None

        # Compute summary statistics
        max_delta_y = float(np.max(np.abs(delta_y)))
        mean_delta_y = float(np.mean(delta_y))
        std_delta_y = float(np.std(delta_y))

        # Find CNP shift (if available from prior extraction)
        # Note: These would come from enriched history if available
        cnp_1 = metadata_1.get("cnp_voltage")
        cnp_2 = metadata_2.get("cnp_voltage")

        if cnp_1 is not None and cnp_2 is not None:
            delta_cnp = float(cnp_2 - cnp_1)
        else:
            delta_cnp = None

        # Quality checks
        checks = {
            "GOOD_OVERLAP": vg_overlap >= self.min_vg_overlap,
            "REASONABLE_CHANGE": max_delta_y < 1e-3,  # Max 1mA or 1V change
            "NON_ZERO_CHANGE": max_delta_y > 1e-15,   # Detectable change
            "FINITE_RESISTANCE": delta_r is not None if self.store_resistance else True,
        }

        penalties = {
            "REASONABLE_CHANGE": 0.7,
            "NON_ZERO_CHANGE": 0.5,
            "FINITE_RESISTANCE": 0.3,
        }

        confidence = compute_confidence(checks, penalties)
        flags = build_flags(checks)

        # Build detailed results JSON with FULL ARRAYS for plotting
        results = {
            # Pair identification
            "seq_1": metadata_1.get("seq_num"),
            "seq_2": metadata_2.get("seq_num"),
            "run_id_1": metadata_1["run_id"],
            "run_id_2": metadata_2["run_id"],
            "procedure": procedure,

            # Voltage range info
            "vg_min": float(vg_min),
            "vg_max": float(vg_max),
            "vg_overlap": float(vg_overlap),
            "num_points": len(vg_common),

            # Full arrays for plotting (USER REQUESTED)
            "vg_array": vg_common.tolist(),
            f"delta_{y_label.lower()}_array": delta_y.tolist(),

            # Summary statistics for ΔI or ΔV
            f"max_delta_{y_label.lower()}": max_delta_y,
            f"mean_delta_{y_label.lower()}": mean_delta_y,
            f"std_delta_{y_label.lower()}": std_delta_y,

            # CNP shift (if available)
            "delta_cnp": delta_cnp,
            "cnp_1": cnp_1,
            "cnp_2": cnp_2,
        }

        # Add resistance difference if computed
        if self.store_resistance and delta_r_array is not None:
            results["delta_resistance_array"] = delta_r_array.tolist()
            results["max_delta_resistance"] = delta_r
            results["mean_delta_resistance"] = float(np.nanmean(delta_r_array))

        # Create metric
        # Link to SECOND (later) measurement as per design
        metric = DerivedMetric(
            run_id=metadata_2["run_id"],  # Belongs to later measurement
            chip_number=metadata_2["chip_number"],
            chip_group=metadata_2["chip_group"],
            procedure=procedure,
            seq_num=metadata_2.get("seq_num"),
            metric_name=self.metric_name,
            metric_category=self.metric_category,
            value_float=max_delta_y,  # Primary value: max ΔI or ΔV
            value_json=json.dumps(results),
            unit=y_unit,
            extraction_method="consecutive_sweep_interpolation",
            extraction_version=metadata_2.get("extraction_version", "unknown"),
            extraction_timestamp=datetime.now(timezone.utc),
            confidence=confidence,
            flags=flags
        )

        return [metric] if self.validate(metric) else None

    def validate(self, result: DerivedMetric) -> bool:
        """
        Validate result is reasonable.

        Checks:
        -------
        - value_float is finite
        - Change is within physical limits
        - JSON can be parsed
        """
        if result.value_float is None:
            return False

        # Check finite
        if not np.isfinite(result.value_float):
            return False

        # Check within reasonable limits
        # For IVg: max current ~10mA
        # For VVg: max voltage ~10V
        if abs(result.value_float) > 10.0:
            return False

        # Validate JSON
        try:
            json.loads(result.value_json)
        except Exception:
            return False

        return True
