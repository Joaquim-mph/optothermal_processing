"""
CNP Configuration Screen.

Step 3/4 of the wizard: Configure parameters for CNP (Charge Neutrality Point) time evolution plots.

CNP plots show how the Dirac point (charge neutrality point voltage) changes over time,
which is useful for tracking device behavior during experiments and identifying trends.

IMPORTANT: CNP plots require enriched chip histories with derived metrics.
If enriched history is not available, the user will see a warning and instructions.
"""

from __future__ import annotations
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, RadioButton, RadioSet, Checkbox
from textual.binding import Binding

from src.tui.screens.base import WizardScreen
from src.tui.history_detection import get_history_status_message


class CNPConfigScreen(WizardScreen):
    """CNP time plot configuration screen (Step 3/4)."""

    SCREEN_TITLE = "Configure CNP Time Plot"
    STEP_NUMBER = 3

    def __init__(self, chip_number: int, chip_group: str):
        """
        Initialize CNP configuration screen.

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

    Checkbox {
        margin: 1 0;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: center middle;
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
        """Compose CNP configuration form."""
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
                f"CNP plots require enriched history with derived metrics.\n"
                f"Run: python3 process_and_analyze.py enrich-history {self.chip_number}",
                classes="history-status warning-status"
            )

        # Info text
        yield Static(
            "[bold]CNP Time Evolution Plot[/bold]\n\n"
            "Track Charge Neutrality Point (Dirac point) voltage changes over time.\n"
            "Useful for monitoring device behavior during experiments:\n"
            "  • Identify doping effects\n"
            "  • Track device degradation\n"
            "  • Correlate CNP shifts with experimental conditions\n"
            "  • Study photodoping effects",
            classes="info-text"
        )

        # CNP metric selection
        yield Static("Select CNP metric to plot:", classes="section-header")
        with RadioSet(id="cnp-metric-radio"):
            yield RadioButton("CNP Voltage (Dirac Point)", id="cnp-voltage-radio", value=True)
            yield RadioButton("CNP Current", id="cnp-current-radio")
            yield RadioButton("Mobility", id="mobility-radio")

        # Options
        yield Static("Display options:", classes="section-header")
        yield Checkbox("Show illumination periods", id="show-illumination", value=True)

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default")
            yield Button("Generate Plot", id="next-button", variant="primary")

    def on_mount(self) -> None:
        """Focus the metric selector when mounted."""
        self.query_one("#cnp-metric-radio", RadioSet).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()

    def action_next(self) -> None:
        """Save configuration and proceed to plot generation."""
        # Get selected metric
        radio_set = self.query_one("#cnp-metric-radio", RadioSet)
        metric_map = {
            "cnp-voltage-radio": "cnp_voltage",
            "cnp-current-radio": "cnp_current",
            "mobility-radio": "mobility",
        }

        if radio_set.pressed_button is None:
            self.app.notify("Please select a CNP metric", severity="warning")
            return

        self.app.session.cnp_metric = metric_map[radio_set.pressed_button.id]

        # Get display options
        checkbox = self.query_one("#show-illumination", Checkbox)
        self.app.session.cnp_show_illumination = checkbox.value

        # Set config mode
        self.app.session.config_mode = "custom"

        # CNP plots don't need experiment selection (uses all IVg data with derived metrics)
        # Set a placeholder for seq_numbers to satisfy router validation
        self.app.session.seq_numbers = [0]  # Placeholder, not actually used for CNP plots

        # Go directly to plot generation
        self.app.router.go_to_plot_generation()
