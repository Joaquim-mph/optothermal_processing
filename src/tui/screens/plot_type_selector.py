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
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, RadioButton, RadioSet
from textual.binding import Binding


class PlotTypeSelectorScreen(Screen):
    """Plot type selection screen (Step 2 of wizard)."""

    def __init__(self, chip_number: int = 0, chip_group: str = ""):
        super().__init__()
        self.chip_number = chip_number
        self.chip_group = chip_group

    BINDINGS = [
        Binding("escape", "back", "Back", priority=True),
        Binding("ctrl+b", "back", "Back", show=False),
        Binding("enter", "next", "Next", priority=True),
        Binding("space", "toggle_selection", "Select", show=False),
        Binding("up", "focus_previous", "Up", show=False),
        Binding("down", "focus_next", "Down", show=False),
    ]

    CSS = """
    PlotTypeSelectorScreen {
        align: center middle;
    }

    #main-container {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 2 4;
    }

    #header-container {
        width: 100%;
        height: auto;
        margin-bottom: 2;
    }

    #title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: $accent;
    }

    #chip-info {
        width: 100%;
        content-align: center middle;
        color: $accent;
        margin-bottom: 1;
    }

    #step-indicator {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

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

    .plot-description {
        width: 100%;
        color: $text-muted;
        margin: 0 2 1 2;
        padding: 1;
        background: $panel-lighten-1;
    }

    #button-container {
        width: 100%;
        height: auto;
        layout: horizontal;
    }

    .nav-button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Create plot type selector widgets."""
        yield Header()

        with Container(id="main-container"):
            with Vertical(id="header-container"):
                yield Static("Select Plot Type", id="title")
                if self.chip_number and self.chip_group:
                    yield Static(f"Chip: [bold]{self.chip_group}{self.chip_number}[/bold]", id="chip-info")
                yield Static("[Step 2/6]", id="step-indicator")

            with RadioSet(id="plot-type-radio"):
                yield RadioButton("It (Current vs Time)", id="its-radio")
                yield RadioButton("IVg (Transfer Curves)", id="ivg-radio")
                yield RadioButton("Transconductance", id="transconductance-radio")

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

            with Vertical(id="button-container"):
                yield Button("← Back", id="back-button", variant="default", classes="nav-button")
                yield Button("Next →", id="next-button", variant="primary", classes="nav-button")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen - focus the radio set."""
        self.query_one(RadioSet).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back-button":
            self.action_back()
        elif event.button.id == "next-button":
            self.action_next()

    def action_back(self) -> None:
        """Go back to chip selector."""
        self.app.pop_screen()

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
            "its-radio": "ITS",
            "ivg-radio": "IVg",
            "transconductance-radio": "Transconductance",
        }

        plot_type = plot_type_map.get(selected.id)

        if plot_type is None:
            self.app.notify("Invalid plot type selected", severity="error")
            return

        # Save plot type to app state
        self.app.update_config(plot_type=plot_type)

        # Navigate to Config Mode Selector (Step 3)
        from src.tui.screens.config_mode_selector import ConfigModeSelectorScreen

        self.app.push_screen(ConfigModeSelectorScreen(
            chip_number=self.chip_number,
            chip_group=self.chip_group,
            plot_type=plot_type
        ))
