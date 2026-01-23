"""
Data Preview Selector Screen.

Allows users to select chip and experiments for terminal-based preview.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, Label, Select, Input
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class DataPreviewSelectorScreen(WizardScreen):
    """Data preview selector screen."""

    SCREEN_TITLE = "👁️  Data Preview Setup"
    STEP_NUMBER = None

    BINDINGS = WizardScreen.BINDINGS + [Binding("home", "home", "Home", show=True)]

    CSS = WizardScreen.CSS + """
    #breadcrumb {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #selector-form {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    .section-label {
        color: $accent;
        text-style: bold;
        margin-top: 1;
    }

    .form-row {
        height: 3;
        margin: 0 0 1 0;
    }

    .info-text {
        color: $text-muted;
        margin: 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        yield Static("Main Menu > Histories > Data Preview", id="breadcrumb")
        yield Static(self.SCREEN_TITLE, id="title")

    def compose_content(self) -> ComposeResult:
        with Vertical(id="selector-form"):
            yield Label("Select Chip:", classes="section-label")
            yield Select(
                options=[("Select chip...", "")],
                value="",
                id="chip-select",
                classes="form-row"
            )

            yield Label("\nProcedure:", classes="section-label")
            yield Select(
                options=[
                    ("All", "all"),
                    ("It (Current vs Time)", "It"),
                    ("IVg (Gate Sweeps)", "IVg"),
                    ("VVg (Voltage Sweeps)", "VVg"),
                    ("Vt (Voltage vs Time)", "Vt"),
                ],
                value="all",
                id="procedure-select",
                classes="form-row"
            )

            yield Label("\nSequence Number(s):", classes="section-label")
            yield Input(
                placeholder="e.g., 52 or 52,57,58",
                id="seq-input",
                classes="form-row"
            )

            yield Label(
                "\n💡 Enter one or more experiment sequence numbers (comma-separated)",
                classes="info-text"
            )

        yield Button("👁️  Preview Data", id="preview-btn", variant="primary")

    def on_mount(self) -> None:
        """Populate chip selector."""
        self._populate_chip_selector()
        self.query_one("#chip-select", Select).focus()

    def _populate_chip_selector(self) -> None:
        """Populate chip selector with available chips."""
        history_dir = Path("data/02_stage/chip_histories")
        if not history_dir.exists():
            return

        chips = []
        for history_file in history_dir.glob("*_history.parquet"):
            # Extract chip name without "_history" suffix
            chip_name = history_file.stem.replace("_history", "")

            # Parse chip group and number (e.g., "Alisson67" -> group="Alisson", num=67)
            # Try to extract trailing digits
            import re
            match = re.match(r"^([A-Za-z]+)(\d+)$", chip_name)

            if match:
                chip_group = match.group(1)
                chip_num = match.group(2)
                display_name = f"{chip_group}{chip_num}"
                chips.append((display_name, chip_name))
            else:
                # Fallback for non-standard naming
                chips.append((chip_name, chip_name))

        # Sort by chip number if possible
        chips.sort(key=lambda x: int(''.join(filter(str.isdigit, x[1]))) if any(c.isdigit() for c in x[1]) else 0)

        if chips:
            options = [("Select chip...", "")] + chips
            self.query_one("#chip-select", Select).set_options(options)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "preview-btn":
            self._start_preview()

    def _start_preview(self) -> None:
        """Start data preview with selected parameters."""
        chip_value = self.query_one("#chip-select", Select).value
        procedure = self.query_one("#procedure-select", Select).value
        seq_input = self.query_one("#seq-input", Input).value

        # Validate chip selection
        if not chip_value:
            self.app.notify("Please select a chip", severity="error")
            return

        # Validate sequence numbers
        if not seq_input.strip():
            self.app.notify("Please enter sequence number(s)", severity="error")
            return

        # Parse sequence numbers
        try:
            seq_numbers = [int(s.strip()) for s in seq_input.split(",")]
        except ValueError:
            self.app.notify("Invalid sequence numbers. Use format: 52 or 52,57,58", severity="error")
            return

        # Parse chip_value (e.g., "Alisson67" -> group="Alisson", number=67)
        import re
        match = re.match(r"^([A-Za-z]+)(\d+)$", chip_value)

        if match:
            chip_group = match.group(1)
            chip_number = int(match.group(2))
        else:
            self.app.notify(f"Could not parse chip name: {chip_value}", severity="error")
            return

        # Determine plot type based on procedure
        plot_type_map = {
            "It": "ITS",
            "IVg": "IVg",
            "VVg": "VVg",
            "Vt": "Vt",
            "all": "ITS"  # Default to ITS for display purposes
        }
        plot_type = plot_type_map.get(procedure, "ITS")

        # Navigate to experiment preview screen
        from src.tui.screens.analysis.experiment_preview import ExperimentPreviewScreen

        preview_screen = ExperimentPreviewScreen(
            chip_number=chip_number,
            chip_group=chip_group,
            plot_type=plot_type,
            seq_numbers=seq_numbers,
            procedure_filter=procedure  # Pass the actual procedure for filtering
        )
        self.app.push_screen(preview_screen)

    def action_home(self) -> None:
        """Return to main menu."""
        self.app.router.return_to_main_menu()
