"""
Chip Histories sub-screens for Phase 3 TUI reorganization.

This package contains detailed screens for the Chip Histories Hub:
- Standard History Browser
- Enriched History Browser (with derived metrics)
- Metrics Explorer (CNP, photoresponse, relaxation times)
- Experiment Browser (advanced search/filter)
- Export History
"""

from __future__ import annotations

# Standard History
from .standard_history_browser import StandardHistoryBrowserScreen

# Enriched History
from .enriched_history_browser import EnrichedHistoryBrowserScreen

# Metrics Explorer
from .metrics_explorer_hub import MetricsExplorerHubScreen
from .cnp_evolution import CNPEvolutionScreen
from .photoresponse_analysis import PhotoresponseAnalysisScreen
from .relaxation_times import RelaxationTimesScreen

# Experiment Browser
from .experiment_browser import ExperimentBrowserScreen
from .search_results import SearchResultsScreen

# Export
from .export_history import ExportHistoryScreen

# Data Preview
from .data_preview_selector import DataPreviewSelectorScreen

__all__ = [
    # Standard History
    "StandardHistoryBrowserScreen",
    # Enriched History
    "EnrichedHistoryBrowserScreen",
    # Metrics Explorer
    "MetricsExplorerHubScreen",
    "CNPEvolutionScreen",
    "PhotoresponseAnalysisScreen",
    "RelaxationTimesScreen",
    # Experiment Browser
    "ExperimentBrowserScreen",
    "SearchResultsScreen",
    # Export
    "ExportHistoryScreen",
    # Data Preview
    "DataPreviewSelectorScreen",
]
