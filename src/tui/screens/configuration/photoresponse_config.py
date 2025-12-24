"""
Photoresponse Configuration Screen.

Step 3/4 of the wizard: Configure parameters for photoresponse analysis plots.

Photoresponse plots analyze how device current responds to illumination as a function of:
- Power (irradiated power from laser)
- Wavelength (LED/laser wavelength)
- Gate voltage (device bias conditions)
- Time (evolution during experiment)

IMPORTANT: Photoresponse plots require enriched chip histories with derived metrics
and laser calibration data.
"""

from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, RadioButton, RadioSet, Input
from textual.binding import Binding

from src.tui.screens.base import WizardScreen
from src.tui.history_detection import get_history_status_message


class PhotoresponseConfigScreen(WizardScreen):
    """Photoresponse plot configuration screen (Step 3/4)."""

    SCREEN_TITLE = "Configure Photoresponse Plot"
    STEP_NUMBER = 3

    def __init__(self, chip_number: int, chip_group: str):
        """
        Initialize Photoresponse configuration screen.

        Parameters
        ----------
        chip_number : int
            Chip number
        chip_group : str
            Chip group name
        """
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group

    BINDINGS = WizardScreen.BINDINGS + [
        Binding("enter", "next", "Next", priority=True),
    ]

    CSS = WizardScreen.CSS + """
    #main-container {
        max-height: 90%;
        overflow-y: auto;
    }

    .info-text {
        width: 100%;
        padding: 2;
        background: $panel;
        color: $text;
        margin-bottom: 2;
    }

    .history-status {
        width: 100%;
        padding: 1 2;
        background: $panel;
        margin-bottom: 2;
        border: tall $primary;
    }

    .warning-status {
        border: tall $warning;
        color: $warning;
    }

    .section-header {
        width: 100%;
        color: $accent;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }

    RadioSet {
        width: 100%;
        height: auto;
        margin-bottom: 2;
        padding: 1;
        background: $surface;
    }

    RadioButton {
        margin: 1 0;
    }

    .filter-input {
        width: 50%;
        margin: 1 0;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: center middle;
        margin-top: 2;
    }

    #button-container Button {
        margin: 0 1;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with title and chip info."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static(f"Chip: [bold]{self.chip_group}{self.chip_number}[/bold]", id="chip-info")
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose photoresponse configuration form."""
        # Get history status
        history_dir = self.app.session.history_dir
        enriched_dir = self.app.session.enriched_history_dir
        status_msg = get_history_status_message(
            self.chip_number, self.chip_group, history_dir, enriched_dir
        )

        # Check if enriched history is available
        has_enriched = "✓" in status_msg

        # Show history status with appropriate styling
        if has_enriched:
            yield Static(f"History Status: {status_msg}", classes="history-status")
        else:
            yield Static(
                f"⚠ Warning: {status_msg}\n\n"
                f"Photoresponse plots require enriched history with derived metrics.\n"
                f"Run: python3 process_and_analyze.py enrich-history {self.chip_number}",
                classes="history-status warning-status"
            )

        # Info text
        yield Static(
            "[bold]Photoresponse Analysis Plot[/bold]\n\n"
            "Analyze device response to illumination. Choose analysis mode below.",
            classes="info-text"
        )

        # Plot mode selection
        yield Static("Select photoresponse plot mode:", classes="section-header")
        with RadioSet(id="photoresponse-mode-radio"):
            yield RadioButton("Photoresponse vs Power", id="power-radio", value=True)
            yield RadioButton("Photoresponse vs Wavelength", id="wavelength-radio")
            yield RadioButton("Photoresponse vs Gate Voltage", id="gate-voltage-radio")
            yield RadioButton("Photoresponse vs Time", id="time-radio")

        # Filter options
        yield Static("Filters (optional - leave blank to include all):", classes="section-header")
        yield Static("[dim]Gate voltage filter (V):[/dim]")
        yield Input(
            placeholder="e.g., -0.4",
            id="filter-vg-input",
            classes="filter-input"
        )
        yield Static("[dim]Wavelength filter (nm):[/dim]")
        yield Input(
            placeholder="e.g., 660",
            id="filter-wl-input",
            classes="filter-input"
        )

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default")
            yield Button("Generate Plot", id="next-button", variant="primary")

    def on_mount(self) -> None:
        """Focus the mode selector when mounted."""
        self.query_one("#photoresponse-mode-radio", RadioSet).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()

    def action_next(self) -> None:
        """Save configuration and proceed to plot generation."""
        # Get selected mode
        radio_set = self.query_one("#photoresponse-mode-radio", RadioSet)
        mode_map = {
            "power-radio": "power",
            "wavelength-radio": "wavelength",
            "gate-voltage-radio": "gate_voltage",
            "time-radio": "time",
        }

        if radio_set.pressed_button is None:
            self.app.notify("Please select a photoresponse mode", severity="warning")
            return

        self.app.session.photoresponse_mode = mode_map[radio_set.pressed_button.id]

        # Parse filters (optional)
        vg_input = self.query_one("#filter-vg-input", Input).value.strip()
        if vg_input:
            try:
                self.app.session.photoresponse_filter_vg = float(vg_input)
            except ValueError:
                self.app.notify(
                    f"Invalid gate voltage: '{vg_input}'. Please enter a number (e.g., -0.4)",
                    severity="warning"
                )
                return

        wl_input = self.query_one("#filter-wl-input", Input).value.strip()
        if wl_input:
            try:
                self.app.session.photoresponse_filter_wl = int(wl_input)
            except ValueError:
                self.app.notify(
                    f"Invalid wavelength: '{wl_input}'. Please enter an integer (e.g., 660)",
                    severity="warning"
                )
                return

        # Set config mode
        self.app.session.config_mode = "custom"

        # Photoresponse plots don't need experiment selection (uses all enriched data)
        # Set a placeholder for seq_numbers to satisfy router validation
        self.app.session.seq_numbers = [0]  # Placeholder, not actually used for photoresponse plots

        # Go directly to plot generation
        self.app.router.go_to_plot_generation()
