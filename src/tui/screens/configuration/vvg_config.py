"""
VVg Configuration Screen.

Step 3/4 of the wizard: Configure parameters for VVg (drain-source voltage vs gate voltage) plots.

VVg plots show the output characteristics of the device - how the drain-source
voltage varies with gate voltage sweeps. This is useful for understanding
device behavior under different bias conditions.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, Button
from textual.binding import Binding

from src.tui.screens.base import WizardScreen


class VVgConfigScreen(WizardScreen):
    """VVg plot configuration screen (Step 3/4)."""

    SCREEN_TITLE = "Configure VVg Plot"
    STEP_NUMBER = 3

    def __init__(self, chip_number: int, chip_group: str):
        """
        Initialize VVg configuration screen.

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
    #content-scroll {
        width: 100%;
        height: 1fr;
        min-height: 20;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with title and chip info."""
        yield Static(self.SCREEN_TITLE, id="title")
        yield Static(f"Chip: [bold]{self.chip_group}{self.chip_number}[/bold]", id="chip-info")
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose VVg configuration form."""
        with VerticalScroll(id="content-scroll"):
            yield Static(
                "[bold]VVg Plot Configuration[/bold]\n\n"
                "VVg plots show drain-source voltage vs gate voltage sweeps.\n"
                "These are output characteristic curves that show how the device\n"
                "responds to different gate bias conditions.\n\n"
                "[dim]Default settings work for most cases. Advanced options may\n"
                "be added in future versions.[/dim]",
                classes="info-text"
            )

            with Vertical(id="button-container"):
                yield Button("← Back", id="back-button", variant="default")
                yield Button("Next →", id="next-button", variant="primary")

    def on_mount(self) -> None:
        """Focus the next button when mounted."""
        self.query_one("#next-button", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()

    def action_next(self) -> None:
        """Proceed to experiment selector."""
        # Save minimal config (using quick mode)
        self.app.session.config_mode = "quick"

        # Navigate to experiment selector
        self.app.router.go_to_experiment_selector()
