"""
Experiment Selector Screen (Quick Plot Mode).

Step 4a of the wizard: Interactively select experiments for quick plotting.
Wraps the existing interactive_selector.py into the wizard flow.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, List

import polars as pl
from textual.app import ComposeResult
from textual.binding import Binding

from src.tui.screens.base import WizardScreen
from src.interactive_selector import ExperimentSelectorScreen as BaseExperimentSelector


class ExperimentSelectorScreen(WizardScreen):
    """
    Experiment selector screen for the wizard (Step 4a - Quick mode).

    Wraps the existing ExperimentSelectorScreen and integrates it into the wizard.
    """

    SCREEN_TITLE = "Select Experiments"
    STEP_NUMBER = 5  # Step 5 in the wizard flow

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(
        self,
        chip_number: int,
        chip_group: str,
        plot_type: str,
        history_dir: Path,
    ):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group
        self.plot_type = plot_type
        self.history_dir = history_dir

    def compose_content(self) -> ComposeResult:
        """Compose is minimal - the nested screen handles the UI."""
        # This screen doesn't have its own widgets - it immediately pushes the selector
        return []

    def on_mount(self) -> None:
        """Load chip history and launch the interactive selector."""
        # Load chip history from Parquet file
        try:
            chip_name = f"{self.chip_group}{self.chip_number}"
            history_file = self.history_dir / f"{chip_name}_history.parquet"

            if not history_file.exists():
                self.app.notify(
                    f"History file not found: {history_file}",
                    severity="error",
                    timeout=5
                )
                self.app.pop_screen()
                return

            history_df = pl.read_parquet(history_file)

            if history_df.height == 0:
                self.app.notify(
                    f"No experiments found for {self.chip_group}{self.chip_number}",
                    severity="error",
                    timeout=5
                )
                self.app.pop_screen()
                return

            # Create the selector screen with proper filtering
            # Transconductance is calculated from IVg measurements, not a separate measurement type
            proc_filter = "IVg" if self.plot_type == "Transconductance" else self.plot_type

            # Update title to be clear about what experiments are being selected
            if self.plot_type == "Transconductance":
                title = f"Select IVg Experiments (for Transconductance) - {self.chip_group}{self.chip_number}"
            else:
                title = f"Select {self.plot_type} Experiments - {self.chip_group}{self.chip_number}"

            selector = BaseExperimentSelector(
                chip_number=self.chip_number,
                chip_group=self.chip_group,
                history_df=history_df,
                proc_filter=proc_filter,
                title=title
            )

            # Push the selector and handle the result
            self.app.push_screen(selector, callback=self._on_selection)

        except Exception as e:
            self.app.notify(
                f"Error loading experiments: {str(e)}",
                severity="error",
                timeout=5
            )
            self.app.pop_screen()

    def _on_selection(self, result: Optional[List[int]]) -> None:
        """Handle the selection result from the interactive selector."""
        if result is None:
            # User cancelled - go back to config mode
            self.app.pop_screen()
        else:
            # User confirmed selection - save to session (replaces app.update_config)
            self.app.session.seq_numbers = result

            # Pop this screen (experiment selector wrapper)
            self.app.pop_screen()

            # Navigate to preview screen using router
            self.app.router.go_to_preview()

    def action_cancel(self) -> None:
        """Cancel and return to config mode."""
        self.app.pop_screen()

    def action_back(self) -> None:
        """Override back action to cancel."""
        self.action_cancel()
