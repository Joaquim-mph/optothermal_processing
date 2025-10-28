"""
Result screens - Success and error outcomes.

Provides screens that display results after plot generation or data processing completes.
"""

from src.tui.screens.results.plot_success import PlotSuccessScreen
from src.tui.screens.results.plot_error import PlotErrorScreen
from src.tui.screens.results.process_success import ProcessSuccessScreen
from src.tui.screens.results.process_error import ProcessErrorScreen

__all__ = [
    "PlotSuccessScreen",
    "PlotErrorScreen",
    "ProcessSuccessScreen",
    "ProcessErrorScreen",
]
