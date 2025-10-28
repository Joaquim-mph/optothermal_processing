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

from src.tui.screens import MainMenuScreen
from src.tui.config_manager import ConfigManager
from src.tui.session import PlotSession
from src.tui.router import Router


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

    def __init__(
        self,
        stage_dir: Path = Path("data/02_stage/raw_measurements"),
        history_dir: Path = Path("data/03_history"),
        output_dir: Path = Path("figs"),
        chip_group: str = "Alisson",
    ):
        """
        Initialize the TUI application.

        Parameters
        ----------
        stage_dir : Path
            Staged Parquet data directory path
        history_dir : Path
            Chip history directory path (Parquet files)
        output_dir : Path
            Output directory for plots
        chip_group : str
            Default chip group name
        """
        super().__init__()

        # Store configuration paths (kept for backward compatibility)
        self.stage_dir = stage_dir
        self.history_dir = history_dir
        self.output_dir = output_dir
        self.chip_group = chip_group

        # Initialize type-safe session state (replaces plot_config dict)
        self.session = PlotSession(
            stage_dir=stage_dir,
            history_dir=history_dir,
            output_dir=output_dir,
            chip_group=chip_group
        )

        # Initialize configuration manager
        self.config_manager = ConfigManager()

        # Initialize navigation router
        self.router = Router(self)

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

    # ═══════════════════════════════════════════════════════════════════
    # Backward Compatibility Methods (for gradual migration)
    # ═══════════════════════════════════════════════════════════════════

    @property
    def plot_config(self) -> Dict[str, Any]:
        """
        Backward compatibility property for plot_config dict.

        Returns session state as dict. Use self.session instead for new code.

        Returns
        -------
        dict
            Session state as dictionary
        """
        return self.session.to_config_dict()

    def reset_config(self) -> None:
        """
        Reset plot configuration to defaults.

        Resets wizard state while keeping application paths.
        """
        self.session.reset_wizard_state()

    def update_config(self, **kwargs) -> None:
        """
        Update plot configuration (backward compatibility method).

        For new code, use self.session attributes directly:
        - Old: self.app.update_config(chip_number=67)
        - New: self.app.session.chip_number = 67

        Parameters
        ----------
        **kwargs
            Configuration key-value pairs to update
        """
        # Update session fields dynamically
        for key, value in kwargs.items():
            if hasattr(self.session, key):
                setattr(self.session, key, value)
            else:
                # Warn about unknown fields (helps catch typos during migration)
                self.notify(
                    f"Warning: Unknown config field '{key}' (session has no such attribute)",
                    severity="warning",
                    timeout=3
                )

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value (backward compatibility method).

        For new code, use self.session attributes directly:
        - Old: chip = self.app.get_config("chip_number")
        - New: chip = self.app.session.chip_number

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
        return getattr(self.session, key, default)
