"""
TUI Screens - Organized by function.

This package provides all screen components for the Terminal User Interface,
organized into logical subpackages:

- **base**: Foundation classes (WizardScreen, FormScreen, SelectorScreen, etc.)
- **navigation**: Entry points and flow control (main menu, recent configs)
- **selection**: User choice screens (chip, plot type, experiments, etc.)
- **configuration**: Parameter setting and confirmation screens
- **processing**: Background work with progress indicators
- **results**: Success/error outcome screens

Example Usage
-------------
>>> # Import from subpackages
>>> from src.tui.screens.navigation import MainMenuScreen
>>> from src.tui.screens.selection import ChipSelectorScreen
>>> from src.tui.screens.configuration import ITSConfigScreen
>>> from src.tui.screens.processing import PlotGenerationScreen
>>> from src.tui.screens.results import PlotSuccessScreen
>>>
>>> # Or import base classes
>>> from src.tui.screens.base import WizardScreen, FormScreen
"""

# Base classes - always available at top level
from src.tui.screens.base import (
    WizardScreen,
    FormScreen,
    SelectorScreen,
    ResultScreen,
    SuccessScreen,
    ErrorScreen,
)

# Re-export all screens from subpackages for convenience
from src.tui.screens.navigation import *
from src.tui.screens.selection import *
from src.tui.screens.configuration import *
from src.tui.screens.processing import *
from src.tui.screens.results import *
from src.tui.screens.analysis import *

__all__ = [
    # Base classes
    "WizardScreen",
    "FormScreen",
    "SelectorScreen",
    "ResultScreen",
    "SuccessScreen",
    "ErrorScreen",
    # Navigation
    "MainMenuScreen",
    "RecentConfigsScreen",
    # Selection
    "ChipSelectorScreen",
    "PlotTypeSelectorScreen",
    "ConfigModeSelectorScreen",
    "ExperimentSelectorScreen",
    "ITSPresetSelectorScreen",
    # Configuration
    "ITSConfigScreen",
    "IVgConfigScreen",
    "TransconductanceConfigScreen",
    "PreviewScreen",
    "ProcessConfirmationScreen",
    # Processing
    "PlotGenerationScreen",
    "ProcessLoadingScreen",
    # Results
    "PlotSuccessScreen",
    "PlotErrorScreen",
    "ProcessSuccessScreen",
    "ProcessErrorScreen",
    # Analysis
    "HistoryBrowserScreen",
]
