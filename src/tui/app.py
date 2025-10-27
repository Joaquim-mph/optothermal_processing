"""
Main TUI Application.

PlotterApp is the main Textual application that manages the wizard flow
for generating plots from experimental data.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any

from textual.app import App, ComposeResult
from textual.binding import Binding

from src.tui.screens.main_menu import MainMenuScreen
from src.tui.config_manager import ConfigManager


class PlotterApp(App):
    """
    Experiment Plotting Assistant - Main TUI Application.

    A wizard-style interface that guides users through plot generation:
    1. Select plot type (ITS, IVg, Transconductance)
    2. Select chip (auto-discovered)
    3. Configure parameters (Quick or Custom)
    4. Preview and generate plot

    Features:
    - Tokyo Night theme
    - Configuration persistence
    - Recent configurations
    - Batch plotting
    - Error handling with return to config
    """

    TITLE = "Experiment Plotting Assistant"
    SUB_TITLE = "Alisson Lab - Device Characterization"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+h", "help", "Help", show=False),
    ]

    # Shared state for wizard flow
    plot_config: Dict[str, Any] = {}

    def __init__(
        self,
        metadata_dir: Path = Path("metadata"),
        raw_dir: Path = Path("."),
        history_dir: Path = Path("chip_histories"),
        output_dir: Path = Path("figs"),
        chip_group: str = "Alisson",
    ):
        """
        Initialize the TUI application.

        Parameters
        ----------
        metadata_dir : Path
            Metadata directory path
        raw_dir : Path
            Raw data directory path
        history_dir : Path
            Chip history directory path
        output_dir : Path
            Output directory for plots
        chip_group : str
            Default chip group name
        """
        super().__init__()

        # Store configuration paths
        self.metadata_dir = metadata_dir
        self.raw_dir = raw_dir
        self.history_dir = history_dir
        self.output_dir = output_dir
        self.chip_group = chip_group

        # Initialize plot configuration
        self.plot_config = {
            "metadata_dir": metadata_dir,
            "raw_dir": raw_dir,
            "history_dir": history_dir,
            "output_dir": output_dir,
            "chip_group": chip_group,
        }

        # Initialize configuration manager
        self.config_manager = ConfigManager()

    def on_mount(self) -> None:
        """Set theme and show main menu on startup."""
        # Apply Tokyo Night theme
        self.theme = "tokyo-night"

        # Push main menu screen
        self.push_screen(MainMenuScreen())

    def action_help(self) -> None:
        """Show help screen."""
        # TODO: Implement help screen in Phase 7
        self.notify("Help: Use arrow keys to navigate, Enter to select, Ctrl+Q to quit")

    def reset_config(self) -> None:
        """Reset plot configuration to defaults."""
        self.plot_config = {
            "metadata_dir": self.metadata_dir,
            "raw_dir": self.raw_dir,
            "history_dir": self.history_dir,
            "output_dir": self.output_dir,
            "chip_group": self.chip_group,
        }

    def update_config(self, **kwargs) -> None:
        """
        Update plot configuration.

        Parameters
        ----------
        **kwargs
            Configuration key-value pairs to update
        """
        self.plot_config.update(kwargs)

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Parameters
        ----------
        key : str
            Configuration key
        default : Any
            Default value if key not found

        Returns
        -------
        Any
            Configuration value
        """
        return self.plot_config.get(key, default)
