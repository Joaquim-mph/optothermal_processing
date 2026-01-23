"""
Processing screens - Background work with progress indicators.

Provides screens that show progress while generating plots or processing data.
Phase 4 additions: Data pipeline management screens.
"""

from src.tui.screens.processing.plot_generation import PlotGenerationScreen
from src.tui.screens.processing.process_loading import ProcessLoadingScreen

# Phase 4: Process New Data Hub screens
from src.tui.screens.processing.stage_raw_data import StageRawDataScreen
from src.tui.screens.processing.staging_progress import StagingProgressScreen
from src.tui.screens.processing.staging_summary import StagingSummaryScreen
from src.tui.screens.processing.build_histories import BuildHistoriesScreen
from src.tui.screens.processing.extract_metrics import ExtractMetricsScreen
from src.tui.screens.processing.full_pipeline import FullPipelineScreen
from src.tui.screens.processing.validate_manifest import ValidateManifestScreen
from src.tui.screens.processing.pipeline_status import PipelineStatusScreen

__all__ = [
    "PlotGenerationScreen",
    "ProcessLoadingScreen",
    # Phase 4
    "StageRawDataScreen",
    "StagingProgressScreen",
    "StagingSummaryScreen",
    "BuildHistoriesScreen",
    "ExtractMetricsScreen",
    "FullPipelineScreen",
    "ValidateManifestScreen",
    "PipelineStatusScreen",
]
