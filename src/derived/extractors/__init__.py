"""
Metric extractors for deriving analytical results from measurements.

Each extractor implements the MetricExtractor interface and computes one
or more related metrics from staged measurement data.

Available extractors:
- CNPExtractor: Charge neutrality point from IVg/VVg
- PhotoresponseExtractor: Delta I and Delta V from It/Vt measurements
- CalibrationMatcher: Laser calibration association and power interpolation
"""

from .base import MetricExtractor
from .cnp_extractor import CNPExtractor
from .photoresponse_extractor import PhotoresponseExtractor
from .calibration_matcher import CalibrationMatcher, EnrichmentReport, print_enrichment_report

__all__ = [
    "MetricExtractor",
    "CNPExtractor",
    "PhotoresponseExtractor",
    "CalibrationMatcher",
    "EnrichmentReport",
    "print_enrichment_report",
]
