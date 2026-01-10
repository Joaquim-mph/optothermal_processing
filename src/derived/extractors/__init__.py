"""
Metric extractors for deriving analytical results from measurements.

Each extractor implements the MetricExtractor interface and computes one
or more related metrics from staged measurement data.

Available extractors:
- CNPExtractor: Charge neutrality point from IVg/VVg
- PhotoresponseExtractor: Delta I and Delta V from It/Vt measurements (simple difference)
- CalibrationMatcher: Laser calibration association and power interpolation
- ITSRelaxationExtractor: Photoresponse relaxation time from ITS measurements (Numba-accelerated)
- ITSThreePhaseFitExtractor: Three-phase relaxation fitting (PRE-DARK, LIGHT, POST-DARK)
- DriftExtractor: Linear drift rate from time-series measurements (ITS, Vt, Tt)

Pairwise extractors:
- ConsecutiveSweepDifferenceExtractor: Differences between consecutive IVg/VVg sweeps
"""

from .base import MetricExtractor
from .base_pairwise import PairwiseMetricExtractor
from .cnp_extractor import CNPExtractor
from .photoresponse_extractor import PhotoresponseExtractor
from .calibration_matcher import CalibrationMatcher, EnrichmentReport, print_enrichment_report
from .its_relaxation_extractor import ITSRelaxationExtractor
from .its_three_phase_fit_extractor import ITSThreePhaseFitExtractor
from .consecutive_sweep_difference import ConsecutiveSweepDifferenceExtractor
from .drift_extractor import DriftExtractor

__all__ = [
    "MetricExtractor",
    "PairwiseMetricExtractor",
    "CNPExtractor",
    "PhotoresponseExtractor",
    "CalibrationMatcher",
    "EnrichmentReport",
    "print_enrichment_report",
    "ITSRelaxationExtractor",
    "ITSThreePhaseFitExtractor",
    "ConsecutiveSweepDifferenceExtractor",
    "DriftExtractor",
]
