"""
Plot Type Selector Screen.

Step 2 of the wizard: Select the type of plot to generate.

Options:
- ITS (Current vs Time): Photocurrent time series with light/dark cycles
- IVg (Transfer Curves): Gate voltage sweep characteristics
- Transconductance: gm = dI/dVg derivative analysis
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Button, RadioButton, RadioSet
from textual.binding import Binding

from src.tui.screens.base import SelectorScreen


class PlotTypeSelectorScreen(SelectorScreen):
    """Plot type selection screen (Step 2 of wizard)."""

    SCREEN_TITLE = "Select Plot Type"
    STEP_NUMBER = 2

    def __init__(self, chip_number: int = 0, chip_group: str = ""):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group

    BINDINGS = SelectorScreen.BINDINGS + [
        Binding("enter", "next", "Next", priority=True),
        Binding("space", "toggle_selection", "Select", show=False),
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
    ]

    # Plot type selector CSS (extends SelectorScreen CSS)
    CSS = SelectorScreen.CSS + """
    RadioSet {
        width: 100%;
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: $panel;
    }

    RadioButton {
        margin: 1 0;
    }
    """

    def compose_header(self) -> ComposeResult:
        """Compose header with title, chip info, and step indicator."""
        yield Static(self.SCREEN_TITLE, id="title")
        if self.chip_number and self.chip_group:
            yield Static(f"Chip: [bold]{self.chip_group}{self.chip_number}[/bold]", id="chip-info")
        yield Static(f"[Step {self.STEP_NUMBER}/{self.TOTAL_STEPS}]", id="step-indicator")

    def compose_content(self) -> ComposeResult:
        """Compose plot type selector content."""
        with RadioSet(id="plot-type-radio"):
            # v2.x plot types
            yield RadioButton("It (Current vs Time)", id="its-radio")
            yield RadioButton("IVg (Transfer Curves)", id="ivg-radio")
            yield RadioButton("Transconductance", id="transconductance-radio")

            # v3.0 measurement plot types
            yield RadioButton("VVg (Drain-Source vs Gate)", id="vvg-radio")
            yield RadioButton("Vt (Voltage vs Time)", id="vt-radio")

            # v3.0 derived metric plot types (requires enriched histories)
            yield RadioButton("CNP Time Evolution ⭐", id="cnp-radio")
            yield RadioButton("Photoresponse Analysis ⭐", id="photoresponse-radio")
            yield RadioButton("It Relaxation Fits ⭐", id="its-relaxation-radio")

            # Global measurement plots (not chip-specific)
            yield RadioButton("Laser Calibration 🔬", id="laser-calibration-radio")

        # Descriptions below radio buttons
        yield Static(
            "[bold]It (Current vs Time)[/bold]\n"
            "Plot photocurrent time series with light/dark cycles. Best for analyzing photoresponse behavior.",
            classes="plot-description"
        )
        yield Static(
            "[bold]IVg (Transfer Curves)[/bold]\n"
            "Plot gate voltage sweep characteristics. Shows device transfer behavior (Id vs Vg).",
            classes="plot-description"
        )
        yield Static(
            "[bold]Transconductance[/bold]\n"
            "Plot gm = dI/dVg from IVg data. Derivative analysis of transfer curves.",
            classes="plot-description"
        )
        yield Static(
            "[bold]VVg (Drain-Source vs Gate)[/bold]\n"
            "Plot drain-source voltage vs gate voltage sweeps. Shows output characteristics.",
            classes="plot-description"
        )
        yield Static(
            "[bold]Vt (Voltage vs Time)[/bold]\n"
            "Plot voltage time series measurements. Track voltage changes over time.",
            classes="plot-description"
        )
        yield Static(
            "[bold]CNP Time Evolution ⭐[/bold]\n"
            "Track Charge Neutrality Point (Dirac point) evolution over time. Requires enriched history.",
            classes="plot-description"
        )
        yield Static(
            "[bold]Photoresponse Analysis ⭐[/bold]\n"
            "Analyze device response vs power, wavelength, gate voltage, or time. Requires enriched history.",
            classes="plot-description"
        )
        yield Static(
            "[bold]It Relaxation Fits ⭐[/bold]\n"
            "Visualize stretched exponential relaxation time fits. Shows τ, β, R² parameters. Requires derived metrics.",
            classes="plot-description"
        )
        yield Static(
            "[bold]Laser Calibration 🔬[/bold]\n"
            "Plot laser power vs control voltage calibration curves. Global (not chip-specific).",
            classes="plot-description"
        )

        with Vertical(id="button-container"):
            yield Button("← Back", id="back-button", variant="default", classes="nav-button")
            yield Button("Next →", id="next-button", variant="primary", classes="nav-button")

    def on_mount(self) -> None:
        """Initialize screen - focus the radio set."""
        self.query_one(RadioSet).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()

    def action_toggle_selection(self) -> None:
        """Toggle the currently focused radio button with Space key."""
        focused = self.focused
        radio_set = self.query_one(RadioSet)

        # If focused on RadioSet or a RadioButton, toggle it
        if focused == radio_set or (hasattr(focused, 'parent') and focused.parent == radio_set):
            radio_set.action_toggle_button()

    def action_next(self) -> None:
        """Select highlighted option and proceed to next screen."""
        radio_set = self.query_one(RadioSet)
        focused = self.focused

        # Find which RadioButton is currently focused/highlighted
        highlighted_button = None

        # Check if a RadioButton is directly focused
        if isinstance(focused, RadioButton):
            highlighted_button = focused
        # If RadioSet is focused, find the selected one
        elif focused == radio_set:
            # Get all radio buttons and find the one with -selected class
            radio_buttons = list(self.query(RadioButton).results(RadioButton))
            for button in radio_buttons:
                if button.has_class("-selected"):
                    highlighted_button = button
                    break

        # If we found a highlighted button, make sure it's selected
        if highlighted_button:
            # Toggle it if it's not already the pressed button
            if radio_set.pressed_button != highlighted_button:
                highlighted_button.toggle()
            selected = highlighted_button
        else:
            # Fall back to whatever is already selected
            selected = radio_set.pressed_button

        # Validate selection
        if selected is None:
            self.app.notify("Please select a plot type", severity="warning")
            return

        # Map radio button to plot type
        plot_type_map = {
            # v2.x plot types
            "its-radio": "ITS",
            "ivg-radio": "IVg",
            "transconductance-radio": "Transconductance",

            # v3.0 measurement plot types
            "vvg-radio": "VVg",
            "vt-radio": "Vt",

            # v3.0 derived metric plot types (requires enriched histories)
            "cnp-radio": "CNP",
            "photoresponse-radio": "Photoresponse",
            "its-relaxation-radio": "ITSRelaxation",

            # Global measurement plots (not chip-specific)
            "laser-calibration-radio": "LaserCalibration",
        }

        plot_type = plot_type_map.get(selected.id)

        if plot_type is None:
            self.app.notify("Invalid plot type selected", severity="error")
            return

        # Save plot type to session (replaces app.update_config)
        self.app.session.plot_type = plot_type

        # Navigate to config screen using router (smart navigation based on plot type)
        self.app.router.go_to_config_screen()
