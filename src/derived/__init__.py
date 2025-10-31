"""
Derived metrics pipeline for extracting analytical results from measurements.

This module orchestrates the extraction of derived metrics (CNP, photoresponse,
mobility, etc.) from staged measurement data.

Main components:
- MetricPipeline: Orchestrates metric extraction
- MetricExtractor: Base class for all extractors
"""

from .metric_pipeline import MetricPipeline
from .extractors.base import MetricExtractor

__all__ = ["MetricPipeline", "MetricExtractor"]
